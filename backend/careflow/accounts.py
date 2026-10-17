"""Explicit local operator provisioning; fixture personas are not login accounts."""

import argparse
import getpass
import sys
from uuid import uuid4

from alembic.migration import MigrationContext
from argon2.exceptions import HashingError
from sqlalchemy import select

from careflow.database import SCHEMA_REVISION
from careflow.fixture_schema import demo_identities
from careflow.identity import HASHER, IdentityError, transaction
from careflow.identity_schema import patients, sessions, users


def provision(
    email: str, password: str, *, confirmed: bool, reset: bool = False
) -> None:
    if not 12 <= len(password) <= 128:
        raise ValueError("Invalid password length")
    with transaction(local_confirmation=confirmed) as connection:
        if MigrationContext.configure(connection).get_current_heads() != (
            SCHEMA_REVISION,
        ):
            raise ValueError("Schema is not current")
        persona = (
            connection.execute(
                select(demo_identities).where(
                    demo_identities.c.email == email.strip().lower(),
                    demo_identities.c.demo_role == "patient",
                    demo_identities.c.is_synthetic.is_(True),
                )
            )
            .mappings()
            .first()
        )
        if persona is None:
            raise ValueError("Patient persona not found")
        if reset:
            user_id = connection.scalar(
                select(users.c.id)
                .join(patients)
                .where(
                    patients.c.demo_identity_id == persona["id"],
                )
                .with_for_update(of=users)
            )
            if user_id is None:
                raise ValueError("Patient account not provisioned")
            connection.execute(
                users.update()
                .where(users.c.id == user_id)
                .values(
                    password_hash=HASHER.hash(password),
                )
            )
            connection.execute(sessions.delete().where(sessions.c.user_id == user_id))
            return
        user_id = uuid4()
        connection.execute(
            users.insert().values(
                id=user_id,
                email=persona["email"],
                password_hash=HASHER.hash(password),
            )
        )
        connection.execute(
            patients.insert().values(
                id=uuid4(),
                clinic_id=persona["clinic_id"],
                user_id=user_id,
                demo_identity_id=persona["id"],
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "reset-password"))
    parser.add_argument("--email", required=True)
    parser.add_argument("--confirm-synthetic-account", action="store_true")
    parser.add_argument("--password-stdin", action="store_true")
    options = parser.parse_args()
    try:
        if not options.confirm_synthetic_account:
            raise ValueError("Confirmation required")
        if options.password_stdin:
            password = sys.stdin.readline(1024).rstrip("\r\n")
        else:
            if not sys.stdin.isatty():
                raise ValueError("Interactive terminal or explicit stdin mode required")
            password = getpass.getpass("New synthetic account password: ")
            if password != getpass.getpass("Confirm password: "):
                raise ValueError("Password mismatch")
        provision(
            options.email,
            password,
            confirmed=options.confirm_synthetic_account,
            reset=options.action == "reset-password",
        )
    except (IdentityError, ValueError, HashingError, EOFError):
        print(
            "Account operation failed; check target, confirmation, "
            "persona and credentials.",
            file=sys.stderr,
        )
        return 1
    print("Synthetic patient account operation completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
