"""Patient authentication; no caller-supplied identity grants authorization."""

import hashlib
import re
import secrets
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from pydantic import BaseModel
from sqlalchemy import Connection, RowMapping, case, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from careflow.database import database_engine
from careflow.fixture_schema import clinics, demo_identities
from careflow.fixtures import CLINIC, validate_target
from careflow.identity_schema import auth_limits, patients, sessions, users

HASHER = PasswordHasher()
# Unknown accounts do the same expensive verification as wrong passwords.
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(32))
SESSION_SECONDS = 8 * 60 * 60
PRELOGIN_SECONDS = 10 * 60


class IdentityError(Exception):
    def __init__(
        self, status: int, code: str, message: str = "Request rejected."
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class PatientIdentity(BaseModel):
    user_id: UUID
    patient_id: UUID
    email: str
    role: Literal["patient"] = "patient"


@dataclass(frozen=True)
class SessionGrant:
    token: str
    csrf_token: str
    max_age: int


def now() -> datetime:
    return datetime.fromtimestamp(time.time(), UTC)


def token_hash(token: str | None) -> str:
    if token is None or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise IdentityError(
            401, "AUTH_REQUIRED", "A valid patient session is required."
        )
    return hashlib.sha256(token.encode("ascii")).hexdigest()


@contextmanager
def transaction(*, local_confirmation: bool | None = None) -> Iterator[Connection]:
    try:
        engine = database_engine()
        try:
            if local_confirmation is not None:
                validate_target(engine.url, confirmed=local_confirmation)
            with engine.begin() as connection:
                yield connection
        finally:
            engine.dispose()
    except (SQLAlchemyError, ValueError):
        raise IdentityError(
            503, "AUTH_UNAVAILABLE", "Authentication unavailable."
        ) from None


def read_session(
    connection: Connection, token: str | None, *, lock: bool = False
) -> RowMapping:
    statement = select(sessions).where(
        sessions.c.token_hash == token_hash(token),
        sessions.c.expires_at > now(),
    )
    if lock:
        statement = statement.with_for_update()
    row = connection.execute(statement).mappings().first()
    if row is None:
        raise IdentityError(
            401, "AUTH_REQUIRED", "A valid patient session is required."
        )
    return row


def new_session(connection: Connection, user_id: UUID | None) -> SessionGrant:
    grant = SessionGrant(
        secrets.token_urlsafe(32),
        secrets.token_urlsafe(32),
        SESSION_SECONDS if user_id else PRELOGIN_SECONDS,
    )
    connection.execute(
        sessions.insert().values(
            token_hash=token_hash(grant.token),
            user_id=user_id,
            csrf_token=grant.csrf_token,
            expires_at=now() + timedelta(seconds=grant.max_age),
        )
    )
    return grant


def csrf_session(token: str | None) -> SessionGrant:
    with transaction() as connection:
        try:
            row = read_session(connection, token)
        except IdentityError:
            connection.execute(sessions.delete().where(sessions.c.expires_at <= now()))
            return new_session(connection, None)
        return SessionGrant(
            str(token),
            row["csrf_token"],
            max(1, int((row["expires_at"] - now()).total_seconds())),
        )


def require_csrf(row: RowMapping, csrf: str | None) -> None:
    if (
        not csrf
        or re.fullmatch(r"[A-Za-z0-9_-]{43}", csrf) is None
        or not secrets.compare_digest(row["csrf_token"], csrf)
    ):
        raise IdentityError(403, "CSRF_REJECTED")


def sign_in(
    email: str, password: str, token: str | None, csrf: str | None
) -> SessionGrant:
    with transaction() as connection:
        # Reject missing CSRF before spending password-hashing resources.
        require_csrf(read_session(connection, token), csrf)
        user = (
            connection.execute(
                select(users)
                .where(
                    users.c.email == email.strip().lower(),
                )
                .with_for_update()
            )
            .mappings()
            .first()
        )
        # Account lock precedes session lock, also used by credential reset.
        row = read_session(connection, token, lock=True)
        require_csrf(row, csrf)
        try:
            HASHER.verify(user["password_hash"] if user else DUMMY_HASH, password)
        except (VerificationError, InvalidHashError):
            raise IdentityError(
                401, "INVALID_CREDENTIALS", "Invalid credentials."
            ) from None
        if user is None or not user["active"]:
            raise IdentityError(401, "INVALID_CREDENTIALS", "Invalid credentials.")
        if (
            connection.scalar(
                select(patients.c.id).where(patients.c.user_id == user["id"])
            )
            is None
        ):
            raise IdentityError(401, "INVALID_CREDENTIALS", "Invalid credentials.")
        if HASHER.check_needs_rehash(user["password_hash"]):
            connection.execute(
                users.update()
                .where(users.c.id == user["id"])
                .values(
                    password_hash=HASHER.hash(password),
                )
            )
        connection.execute(
            sessions.delete().where(sessions.c.token_hash == row["token_hash"])
        )
        return new_session(connection, user["id"])


def patient_identity(token: str | None) -> PatientIdentity:
    token_hash(token)  # Missing/malformed sessions fail without opening a connection.
    with transaction() as connection:
        session = read_session(connection, token)
        row = (
            connection.execute(
                select(
                    users.c.id.label("user_id"),
                    patients.c.id.label("patient_id"),
                    users.c.email,
                )
                .join(patients)
                .where(
                    users.c.id == session["user_id"],
                    users.c.active.is_(True),
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise IdentityError(
                401, "AUTH_REQUIRED", "A valid patient session is required."
            )
        return PatientIdentity(**row)


def mutation_patient(
    connection: Connection,
    token: str | None,
    csrf: str | None,
    *,
    check_csrf: bool = True,
) -> RowMapping:
    """Revalidate identity under reset-compatible user-before-session locks."""
    initial = read_session(connection, token)
    user = (
        connection.execute(
            select(users).where(users.c.id == initial["user_id"]).with_for_update()
        )
        .mappings()
        .first()
    )
    session = read_session(connection, token, lock=True)
    if user is None or not user["active"] or session["user_id"] != user["id"]:
        raise IdentityError(401, "AUTH_REQUIRED")
    if check_csrf:
        require_csrf(session, csrf)
    patient = (
        connection.execute(
            select(patients.c.id, patients.c.clinic_id, patients.c.user_id)
            .select_from(
                patients.join(
                    demo_identities, patients.c.demo_identity_id == demo_identities.c.id
                ).join(clinics, patients.c.clinic_id == clinics.c.id)
            )
            .where(
                patients.c.user_id == user["id"],
                patients.c.clinic_id == demo_identities.c.clinic_id,
                patients.c.clinic_id == CLINIC["id"],
                demo_identities.c.demo_role == "patient",
                demo_identities.c.is_synthetic.is_(True),
                clinics.c.is_synthetic.is_(True),
                clinics.c.currency == "PKR",
                clinics.c.timezone == "Asia/Karachi",
            )
            .with_for_update(read=True, of=(patients, demo_identities, clinics))
        )
        .mappings()
        .first()
    )
    if patient is None:
        raise IdentityError(403, "FORBIDDEN")
    return patient


def sign_out(token: str | None, csrf: str | None) -> None:
    if not token:
        return
    with transaction() as connection:
        try:
            row = read_session(connection, token, lock=True)
        except IdentityError:
            return  # Already revoked/expired; retry does not create a new session.
        require_csrf(row, csrf)
        connection.execute(
            sessions.delete().where(sessions.c.token_hash == row["token_hash"])
        )


def limit_attempts(bucket: str, *, limit: int, seconds: int) -> None:
    key = hashlib.sha256(bucket.encode()).hexdigest()
    current = now()
    with transaction() as connection:
        connection.execute(
            auth_limits.delete().where(auth_limits.c.window_end <= current)
        )
        statement = insert(auth_limits).values(
            bucket_key=key,
            attempts=1,
            window_end=current + timedelta(seconds=seconds),
        )
        expired = auth_limits.c.window_end <= current
        counted = statement.on_conflict_do_update(
            index_elements=["bucket_key"],
            set_={
                "attempts": case((expired, 1), else_=auth_limits.c.attempts + 1),
                "window_end": case(
                    (expired, statement.excluded.window_end),
                    else_=auth_limits.c.window_end,
                ),
            },
        ).returning(auth_limits.c.attempts)
        attempts = connection.scalar(counted)
    # Commit the count even when authentication fails or the limit is exceeded.
    if attempts is None or attempts > limit:
        raise IdentityError(429, "RATE_LIMITED", "Too many requests; try later.")
