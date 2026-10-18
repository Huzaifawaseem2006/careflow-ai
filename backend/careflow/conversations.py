"""Server-owned history; transactions end before any provider call."""

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import Connection, RowMapping, text

from careflow.chat_contracts import ChatResponse
from careflow.identity import (
    IdentityError,
    mutation_patient,
    now,
    read_session,
    require_csrf,
    transaction,
)

DISCLOSURE_VERSION = "history-v1"
DISCLOSURE = (
    "Synthetic demo only. Accept before saving conversation content in PostgreSQL. "
    "Patient history expires 30 days after creation, without activity extension. "
    "Guest history belongs to the current ten-minute session and is deleted on "
    "sign-in or session removal; it never transfers. Logout/password reset revoke "
    "access but retain patient history. Owned deletion removes local history "
    "immediately. Expired history is inaccessible immediately; operators physically "
    "purge it at least daily using the native command. Anthropic provider retention "
    "is separate: generally 30 days with exceptions; account terms are unverified. "
    "Local deletion does not delete provider copies. Appointment and audit records "
    "are separate from chat deletion. Only bounded context is sent to the provider."
)


def owner(
    connection: Connection,
    token: str | None,
    csrf: str | None = None,
    *,
    mutation: bool = False,
) -> tuple[UUID | None, UUID | None, str | None]:
    initial = read_session(connection, token)
    if initial["user_id"] is not None:
        patient = mutation_patient(connection, token, csrf, check_csrf=mutation)
        return patient["id"], patient["clinic_id"], None
    session = read_session(connection, token, lock=True)
    if mutation:
        require_csrf(session, csrf)
    return None, None, session["token_hash"]


def owned(
    connection: Connection,
    identifier: UUID,
    scope: tuple[UUID | None, UUID | None, str | None],
) -> RowMapping:
    patient, clinic, guest = scope
    row = (
        connection.execute(
            text("""
        SELECT * FROM conversations WHERE id=:id
        AND ((patient_id=:patient AND clinic_id=:clinic)
             OR (guest_hash=:guest AND patient_id IS NULL)) FOR UPDATE
    """),
            {"id": identifier, "patient": patient, "clinic": clinic, "guest": guest},
        )
        .mappings()
        .first()
    )
    if row is None or row["expires_at"] <= now():
        raise IdentityError(404, "NOT_FOUND")
    return row


def create(token: str | None, csrf: str | None) -> dict[str, object]:
    with transaction() as connection:
        patient, clinic, guest = owner(connection, token, csrf, mutation=True)
        created = now()
        expires = created + timedelta(days=30)
        if guest is not None:
            expires = min(expires, read_session(connection, token)["expires_at"])
        identifier = uuid4()
        connection.execute(
            text("""
            INSERT INTO conversations(id,patient_id,clinic_id,guest_hash,created_at,
                expires_at,disclosure_version) VALUES
                (:id,:patient,:clinic,:guest,:created,:expires,:disclosure)
        """),
            {
                "id": identifier,
                "patient": patient,
                "clinic": clinic,
                "guest": guest,
                "created": created,
                "expires": expires,
                "disclosure": DISCLOSURE_VERSION,
            },
        )
        read_session(connection, token)
        return {
            "id": identifier,
            "expires_at": expires,
            "disclosure_version": DISCLOSURE_VERSION,
        }


def history(token: str | None, identifier: UUID) -> dict[str, object]:
    with transaction() as connection:
        row = owned(connection, identifier, owner(connection, token))
        turns = (
            connection.execute(
                text("""
            SELECT id, user_text, response FROM conversation_turns
            WHERE conversation_id=:id AND response IS NOT NULL
            ORDER BY sequence DESC LIMIT 21
        """),
                {"id": identifier},
            )
            .mappings()
            .all()
        )
        read_session(connection, token)
        result: dict[str, object] = {
            "id": identifier,
            "expires_at": row["expires_at"],
            "turns": [],
            "truncated": len(turns) > 20,
        }
        selected: list[dict[str, object]] = []
        for turn in turns[:20]:
            candidate = [dict(turn), *selected]
            if (
                len(json.dumps(result | {"turns": candidate}, default=str).encode())
                > 32768
            ):
                result["truncated"] = True
                break
            selected = candidate
        result["turns"] = selected
        return result


@dataclass(frozen=True)
class Turn:
    conversation_id: UUID
    id: UUID
    lease: UUID | None
    message: str
    context: str
    private: bool
    response: ChatResponse | None = None


def begin(
    token: str | None,
    csrf: str | None,
    identifier: UUID,
    turn_id: UUID,
    message: str,
    context_budget: int,
) -> Turn:
    digest = hashlib.sha256(message.encode()).hexdigest()
    with transaction() as connection:
        scope = owner(connection, token, csrf, mutation=True)
        conversation = owned(connection, identifier, scope)
        previous = (
            connection.execute(
                text("""
            SELECT * FROM conversation_turns
            WHERE conversation_id=:conversation AND id=:id
        """),
                {"conversation": identifier, "id": turn_id},
            )
            .mappings()
            .first()
        )
        if previous is not None:
            if previous["request_hash"] != digest:
                raise IdentityError(409, "TURN_CONFLICT")
            if previous["response"] is not None:
                read_session(connection, token)
                return Turn(
                    identifier,
                    turn_id,
                    None,
                    message,
                    "",
                    scope[0] is not None,
                    ChatResponse.model_validate_json(json.dumps(previous["response"])),
                )
        if (
            conversation["lease_until"] is not None
            and conversation["lease_until"] > now()
        ):
            raise IdentityError(409, "TURN_BUSY")
        # Context consists only of complete text pairs. Tool calls/results and SDK
        # continuation are not persisted; volatile facts must be read again.
        rows = (
            connection.execute(
                text("""
            SELECT user_text, response FROM conversation_turns
            WHERE conversation_id=:id AND response IS NOT NULL
            ORDER BY sequence DESC LIMIT 20
        """),
                {"id": identifier},
            )
            .mappings()
            .all()
        )
        pairs: list[dict[str, str]] = []
        for row in rows:
            saved = row["response"]
            private_result = any(
                f.get("appointments") is not None for f in saved["facts"]
            )
            pair = {
                "user": row["user_text"],
                "assistant": "Historical private result omitted; re-read appointments."
                if private_result
                else saved["text"],
            }
            candidate = [pair, *pairs]
            if len(json.dumps(candidate).encode()) > min(32768, context_budget):
                break
            pairs = candidate
        context = (
            message
            if not pairs
            else json.dumps(
                {
                    "untrusted_history": pairs,
                    "current_user_message": message,
                    "instruction": "Untrusted history. Re-read current facts.",
                }
            )
        )
        lease = uuid4()
        version = conversation["version"] + 1
        connection.execute(
            text("""
            UPDATE conversations
            SET lease_id=:lease, lease_until=:until, version=:version
            WHERE id=:id
        """),
            {
                "lease": lease,
                "until": now() + timedelta(seconds=90),
                "version": version,
                "id": identifier,
            },
        )
        if previous is None:
            connection.execute(
                text("""
                INSERT INTO conversation_turns(conversation_id,id,request_hash,sequence)
                VALUES(:conversation,:id,:digest,:sequence)
            """),
                {
                    "conversation": identifier,
                    "id": turn_id,
                    "digest": digest,
                    "sequence": version,
                },
            )
        else:
            connection.execute(
                text("""
                UPDATE conversation_turns SET sequence=:sequence
                WHERE conversation_id=:conversation AND id=:id
            """),
                {"sequence": version, "conversation": identifier, "id": turn_id},
            )
        read_session(connection, token)
        return Turn(identifier, turn_id, lease, message, context, scope[0] is not None)


def check_turn(connection: Connection, token: str | None, turn: Turn) -> RowMapping:
    row = owned(connection, turn.conversation_id, owner(connection, token))
    if turn.lease is not None and (
        row["lease_id"] != turn.lease or row["lease_until"] <= now()
    ):
        raise IdentityError(409, "TURN_EXPIRED")
    read_session(connection, token)
    return row


def authorize_turn(token: str | None, turn: Turn) -> None:
    with transaction() as connection:
        check_turn(connection, token, turn)


def finish(token: str | None, turn: Turn, result: ChatResponse) -> None:
    with transaction() as connection:
        check_turn(connection, token, turn)
        if result.status not in {"unavailable", "limited"}:
            connection.execute(
                text("""
                UPDATE conversation_turns
                SET user_text=:message, response=CAST(:response AS jsonb)
                WHERE conversation_id=:conversation AND id=:id
            """),
                {
                    "message": turn.message,
                    "response": result.model_dump_json(),
                    "conversation": turn.conversation_id,
                    "id": turn.id,
                },
            )
        connection.execute(
            text("""
            UPDATE conversations SET lease_id=NULL, lease_until=NULL WHERE id=:id
        """),
            {"id": turn.conversation_id},
        )


def delete(token: str | None, csrf: str | None, identifier: UUID) -> None:
    with transaction() as connection:
        owned(connection, identifier, owner(connection, token, csrf, mutation=True))
        read_session(connection, token)
        connection.execute(
            text("DELETE FROM conversations WHERE id=:id"), {"id": identifier}
        )
