"""Owned history through HTTPS with real disposable PostgreSQL."""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from careflow.chat_api import chat_provider
from careflow.chat_contracts import Limits, ToolCall, ToolDefinition, ToolResult
from careflow.chat_provider import ProviderReply, ScriptedProvider
from careflow.database import database_engine
from careflow.main import app
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_booking_integration import ORIGIN, login, propose
from test_booking_integration import clinic as clinic

pytestmark = pytest.mark.usefixtures("disposable_database")


@pytest.fixture(autouse=True)
def configure_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ORIGIN", ORIGIN)


def provide(provider: ScriptedProvider) -> Callable[[], ScriptedProvider]:
    return lambda: provider


def seed() -> None:
    command.upgrade(Config("alembic.ini"), "head")


def guest(client: TestClient) -> dict[str, str]:
    result = client.get("/auth/csrf")
    assert result.status_code == 200
    return {"origin": ORIGIN, "x-csrf-token": result.json()["csrf_token"]}


def test_disclosure_precedes_storage_and_creation_requires_acceptance() -> None:
    seed()
    with TestClient(app, base_url=ORIGIN) as client:
        disclosure = client.get("/chat/disclosure")
        assert disclosure.status_code == 200
        assert "provider" in disclosure.json()["text"].lower()
        headers = guest(client)
        rejected = client.post("/conversations", json={}, headers=headers)
        assert rejected.status_code == 422
        result = client.post(
            "/conversations",
            json={"disclosure_version": disclosure.json()["version"]},
            headers=headers,
        )
        assert result.status_code == 201
        identifier = result.json()["id"]
        history = client.get(f"/conversations/{identifier}")
        assert history.status_code == 200 and history.json()["turns"] == []
        assert history.headers["cache-control"] == "no-store"
        with TestClient(app, base_url=ORIGIN) as foreign:
            guest(foreign)
            assert foreign.get(f"/conversations/{identifier}").status_code == 404
            assert foreign.get(f"/conversations/{uuid4()}").status_code == 404


def test_complete_turn_is_saved_once_and_replayed_without_provider() -> None:
    seed()
    provider = ScriptedProvider([ProviderReply(stop="end")])
    app.dependency_overrides[chat_provider] = lambda: provider
    try:
        with TestClient(app, base_url=ORIGIN) as client:
            headers = guest(client)
            identifier = client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
            body = {"turn_id": str(uuid4()), "message": "Hello"}
            url = f"/conversations/{identifier}/turns"
            first = client.post(url, json=body, headers=headers)
            assert first.status_code == 200, first.text
            second = client.post(url, json=body, headers=headers)
            assert second.status_code == 200
            assert second.json()["replayed"] is True
            assert second.json()["response"] == first.json()["response"]
            assert len(client.get(f"/conversations/{identifier}").json()["turns"]) == 1
            assert (
                client.post(
                    url, json=body | {"message": "Changed"}, headers=headers
                ).status_code
                == 409
            )
    finally:
        app.dependency_overrides.clear()


def test_private_listing_uses_live_patient_and_rejects_model_identity(
    clinic: UUID,
) -> None:
    call = ToolCall(
        name="get_my_appointments",
        arguments={
            "limit": 1,
            "cursor": None,
            "status": "booked",
            "start_at": None,
            "end_at": None,
        },
    )
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        proposal = propose(client, clinic, headers)
        booked = client.post(
            "/appointments",
            json={"proposal_token": proposal["proposal_token"]},
            headers=headers | {"Idempotency-Key": "chat-listing"},
        )
        assert booked.status_code == 201
        identifier = client.post(
            "/conversations", json={"disclosure_version": "history-v1"}, headers=headers
        ).json()["id"]
        for tool, expected in [
            (call, "answered"),
            (
                call.model_copy(
                    update={"arguments": call.arguments | {"patient_id": str(uuid4())}}
                ),
                "abstained",
            ),
        ]:
            provider = ScriptedProvider(
                [ProviderReply(stop="tool", calls=[tool]), ProviderReply(stop="end")]
            )
            app.dependency_overrides[chat_provider] = provide(provider)
            try:
                result = client.post(
                    f"/conversations/{identifier}/turns",
                    json={"turn_id": str(uuid4()), "message": "My appointments"},
                    headers=headers,
                )
                assert result.status_code == 200, result.text
                assert result.json()["response"]["status"] == expected
                if expected == "answered":
                    page = result.json()["response"]["facts"][0]["appointments"]
                    assert page["items"][0]["id"] == booked.json()["id"]
                    assert "patient_id" not in provider.results[0].model_dump_json()
            finally:
                app.dependency_overrides.clear()


def test_expiry_denies_reads_before_native_purge_physically_deletes() -> None:
    from careflow.conversation_purge import purge

    seed()
    with TestClient(app, base_url=ORIGIN) as client:
        headers = guest(client)
        identifier = client.post(
            "/conversations", json={"disclosure_version": "history-v1"}, headers=headers
        ).json()["id"]
        engine = database_engine()
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE conversations SET "
                        "created_at=created_at-interval '1 day', "
                        "expires_at=now()-interval '1 second' WHERE id=:id"
                    ),
                    {"id": UUID(identifier)},
                )
            assert client.get(f"/conversations/{identifier}").status_code == 404
            assert purge(dry_run=True, limit=1, confirmed=True) == 1
            with engine.connect() as connection:
                assert (
                    connection.scalar(text("SELECT count(*) FROM conversations")) == 1
                )
            assert purge(dry_run=False, limit=1, confirmed=True) == 1
            assert purge(dry_run=False, limit=1, confirmed=True) == 0
            import subprocess
            import sys

            cli = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "careflow.conversation_purge",
                    "--confirm-local-synthetic",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert cli.returncode == 0
            assert cli.stdout.strip() == "Eligible in batch conversations: 0"
        finally:
            engine.dispose()


@pytest.mark.parametrize("interruption", ["delete", "logout", "expire", "reset"])
def test_inflight_completion_cannot_restore_deleted_or_revoked_history(
    clinic: UUID,
    interruption: str,
) -> None:
    from careflow.accounts import provision
    from careflow.identity_api import COOKIE
    from test_booking_integration import EMAIL, PASSWORD

    entered, resume = Event(), Event()

    class WaitingProvider(ScriptedProvider):
        async def complete(
            self,
            message: str,
            tools: Sequence[ToolDefinition],
            result: ToolResult | None,
            limits: Limits,
        ) -> ProviderReply:
            from starlette.concurrency import run_in_threadpool

            entered.set()
            assert await run_in_threadpool(resume.wait, 15)
            return ProviderReply(stop="end", text="Private fabricated success")

    app.dependency_overrides[chat_provider] = lambda: WaitingProvider([])
    engine = database_engine()
    try:
        with TestClient(app, base_url=ORIGIN) as client:
            headers = login(client)
            identifier = client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
            cookie = str(client.cookies.get(COOKIE))

            def send() -> int:
                with TestClient(app, base_url=ORIGIN) as worker:
                    worker.cookies.set(COOKIE, cookie)
                    result = worker.post(
                        f"/conversations/{identifier}/turns",
                        json={"turn_id": str(uuid4()), "message": "Hello"},
                        headers=headers,
                    )
                    assert "Private fabricated success" not in result.text
                    return result.status_code

            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(send)
                try:
                    assert entered.wait(15)
                    if interruption == "delete":
                        assert (
                            client.delete(
                                f"/conversations/{identifier}", headers=headers
                            ).status_code
                            == 204
                        )
                    elif interruption == "logout":
                        assert (
                            client.post("/auth/logout", headers=headers).status_code
                            == 204
                        )
                    elif interruption == "reset":
                        provision(EMAIL, PASSWORD, confirmed=True, reset=True)
                    else:
                        with engine.begin() as connection:
                            connection.execute(
                                text(
                                    "UPDATE sessions "
                                    "SET expires_at=now()-interval '1 second'"
                                )
                            )
                finally:
                    resume.set()
                assert future.result(20) in {401, 404}
            with engine.connect() as connection:
                assert (
                    connection.scalar(
                        text(
                            "SELECT count(*) FROM conversation_turns "
                            "WHERE response IS NOT NULL"
                        )
                    )
                    == 0
                )
                if interruption == "delete":
                    assert (
                        connection.scalar(text("SELECT count(*) FROM conversations"))
                        == 0
                    )
    finally:
        engine.dispose()
        app.dependency_overrides.clear()


def test_turn_lease_fences_old_worker_and_reclaimed_turn_orders_after_newer_turn() -> (
    None
):
    from careflow import conversations
    from careflow.chat_contracts import ChatResponse
    from careflow.identity import IdentityError
    from careflow.identity_api import COOKIE

    seed()
    with TestClient(app, base_url=ORIGIN) as client:
        headers = guest(client)
        identifier = UUID(
            client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
        )
        token = str(client.cookies.get(COOKIE))
        csrf = headers["x-csrf-token"]
        first_id = uuid4()
        first = conversations.begin(token, csrf, identifier, first_id, "First", 32768)
        with pytest.raises(IdentityError) as busy:
            conversations.begin(token, csrf, identifier, uuid4(), "Other", 32768)
        assert busy.value.code == "TURN_BUSY"
        engine = database_engine()
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE conversations SET lease_until=now()-interval '1 second'"
                    )
                )
            later = conversations.begin(
                token, csrf, identifier, uuid4(), "Second", 32768
            )
            conversations.finish(
                token, later, ChatResponse(status="abstained", text="Safe second reply")
            )
            reclaimed = conversations.begin(
                token, csrf, identifier, first_id, "First", 32768
            )
            with pytest.raises(IdentityError) as stale:
                conversations.finish(
                    token, first, ChatResponse(status="answered", text="Stale")
                )
            assert stale.value.code == "TURN_EXPIRED"
            conversations.finish(
                token,
                reclaimed,
                ChatResponse(status="abstained", text="Safe first reply"),
            )
            turns = client.get(f"/conversations/{identifier}").json()["turns"]
            assert [turn["user_text"] for turn in turns] == ["Second", "First"]
        finally:
            engine.dispose()


def test_guest_signin_deletes_history_patient_logout_retains_owned_history(
    clinic: UUID,
) -> None:
    from test_booking_integration import OTHER

    with TestClient(app, base_url=ORIGIN) as client:
        headers = guest(client)
        guest_id = client.post(
            "/conversations", json={"disclosure_version": "history-v1"}, headers=headers
        ).json()["id"]
        headers = login(client)
        assert client.get(f"/conversations/{guest_id}").status_code == 404
        patient_id = client.post(
            "/conversations", json={"disclosure_version": "history-v1"}, headers=headers
        ).json()["id"]
        assert client.post("/auth/logout", headers=headers).status_code == 204
        assert client.get(f"/conversations/{patient_id}").status_code == 401
        login(client, OTHER)
        assert client.get(f"/conversations/{patient_id}").status_code == 404
        headers = login(client)
        assert client.get(f"/conversations/{patient_id}").status_code == 200
        engine = database_engine()
        try:
            with engine.connect() as connection:
                assert (
                    connection.scalar(
                        text(
                            "SELECT count(*) FROM conversations "
                            "WHERE guest_hash IS NOT NULL"
                        )
                    )
                    == 0
                )
        finally:
            engine.dispose()


@pytest.mark.parametrize(
    "attack", ["csrf", "origin", "http", "role", "body", "guest_private"]
)
def test_storage_and_private_tool_security_boundaries(attack: str) -> None:
    seed()
    app.dependency_overrides[chat_provider] = lambda: ScriptedProvider(
        [
            ProviderReply(
                stop="tool", calls=[ToolCall(name="get_my_appointments", arguments={})]
            )
        ]
    )
    try:
        with TestClient(app, base_url=ORIGIN) as client:
            headers = guest(client)
            identifier = client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
            body = {"turn_id": str(uuid4()), "message": "My appointments"}
            url = f"/conversations/{identifier}/turns"
            if attack == "csrf":
                headers.pop("x-csrf-token")
            elif attack == "origin":
                headers["origin"] = "https://foreign.invalid"
            elif attack == "http":
                url = "http://localhost:8000" + url
            elif attack == "role":
                body["role"] = "assistant"
            elif attack == "body":
                body["message"] = "x" * 5000
            result = client.post(url, json=body, headers=headers)
            assert (
                result.status_code
                == {
                    "csrf": 403,
                    "origin": 403,
                    "http": 403,
                    "role": 422,
                    "body": 413,
                    "guest_private": 503,
                }[attack]
            )
            assert result.headers["cache-control"] == "no-store"
            engine = database_engine()
            try:
                with engine.connect() as connection:
                    assert (
                        connection.scalar(
                            text(
                                "SELECT count(*) FROM conversation_turns "
                                "WHERE response IS NOT NULL"
                            )
                        )
                        == 0
                    )
                    assert (
                        connection.scalar(text("SELECT count(*) FROM appointments"))
                        == 0
                    )
            finally:
                engine.dispose()
    finally:
        app.dependency_overrides.clear()


def test_history_context_is_ordered_bounded_and_contains_only_complete_pairs() -> None:
    import json

    from careflow import conversations
    from careflow.chat_contracts import ChatResponse
    from careflow.identity_api import COOKIE

    seed()
    with TestClient(app, base_url=ORIGIN) as client:
        headers = guest(client)
        identifier = UUID(
            client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
        )
        token = str(client.cookies.get(COOKIE))
        for index in range(22):
            claim = conversations.begin(
                token,
                headers["x-csrf-token"],
                identifier,
                uuid4(),
                f"Question {index}",
                32768,
            )
            conversations.finish(
                token,
                claim,
                ChatResponse(status="abstained", text=f"Reply {index} " + "x" * 1800),
            )
        final = conversations.begin(
            token, headers["x-csrf-token"], identifier, uuid4(), "Current", 32768
        )
        context = json.loads(final.context)
        pairs = context["untrusted_history"]
        assert len(pairs) <= 20
        assert len(json.dumps(pairs).encode()) <= 32768
        assert pairs[-1]["user"] == "Question 21"
        assert all(set(pair) == {"user", "assistant"} for pair in pairs)
        history = client.get(f"/conversations/{identifier}")
        assert len(history.content) <= 32768


def test_two_independent_requests_cannot_acquire_same_turn_lease() -> None:
    from threading import Barrier

    from careflow import conversations
    from careflow.identity import IdentityError
    from careflow.identity_api import COOKIE

    seed()
    with TestClient(app, base_url=ORIGIN) as client:
        headers = guest(client)
        identifier = UUID(
            client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
        )
        token = str(client.cookies.get(COOKIE))
    barrier = Barrier(2)
    turn_id = uuid4()

    def acquire(_: int) -> str:
        barrier.wait(timeout=10)
        try:
            conversations.begin(
                token, headers["x-csrf-token"], identifier, turn_id, "Same", 32768
            )
            return "acquired"
        except IdentityError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(acquire, (0, 1))) == ["TURN_BUSY", "acquired"]


def test_restricted_runtime_supports_history_but_cannot_change_ownership_or_audit(
    clinic: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import secrets

    import psycopg
    from careflow import conversations
    from careflow.chat_contracts import ChatResponse
    from careflow.identity_api import COOKIE
    from psycopg import sql
    from sqlalchemy.exc import SQLAlchemyError

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        token = str(client.cookies.get(COOKIE))
    admin = database_engine()
    role = "careflow_history_" + uuid4().hex
    password = secrets.token_urlsafe(32)
    created = False
    try:
        with admin.begin() as connection:
            driver = connection.connection.driver_connection
            assert isinstance(driver, psycopg.Connection)
            driver.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} "
                    "NOSUPERUSER NOCREATEDB NOCREATEROLE"
                ).format(sql.Identifier(role), sql.Literal(password))
            )
        created = True
        with admin.begin() as connection:
            for grant in (
                "GRANT USAGE ON SCHEMA public",
                "GRANT SELECT ON users,patients,clinics,sessions,"
                "conversations,conversation_turns",
                "GRANT SELECT(id,clinic_id,demo_role,is_synthetic) ON demo_identities",
                "GRANT UPDATE(id) ON patients,demo_identities,clinics",
                "GRANT UPDATE(password_hash) ON users",
                "GRANT UPDATE(csrf_token) ON sessions",
                "GRANT INSERT ON conversations,conversation_turns",
                "GRANT UPDATE(lease_id,lease_until,version) ON conversations",
                "GRANT UPDATE(user_text,response,sequence) ON conversation_turns",
                "GRANT DELETE ON conversations",
            ):
                connection.execute(text(grant + f' TO "{role}"'))
        monkeypatch.setenv(
            "DATABASE_URL",
            admin.url.set(username=role, password=password).render_as_string(
                hide_password=False
            ),
        )
        identifier = conversations.create(token, headers["X-CSRF-Token"])["id"]
        assert isinstance(identifier, UUID)
        claim = conversations.begin(
            token, headers["X-CSRF-Token"], identifier, uuid4(), "Hello", 32768
        )
        conversations.finish(
            token, claim, ChatResponse(status="abstained", text="Safe reply")
        )
        saved_turns = conversations.history(token, identifier)["turns"]
        assert isinstance(saved_turns, list) and len(saved_turns) == 1
        runtime = database_engine()
        try:
            for statement in (
                "UPDATE conversations SET patient_id=NULL",
                "UPDATE conversation_turns SET request_hash='forged'",
                "DELETE FROM booking_audit",
                "DELETE FROM appointments",
            ):
                with pytest.raises(SQLAlchemyError), runtime.begin() as connection:
                    connection.execute(text(statement))
        finally:
            runtime.dispose()
        conversations.delete(token, headers["X-CSRF-Token"], identifier)
        with admin.connect() as connection:
            assert (
                connection.scalar(text("SELECT count(*) FROM conversation_turns")) == 0
            )
    finally:
        if created:
            with admin.begin() as connection:
                connection.execute(text(f'DROP OWNED BY "{role}"'))
                connection.execute(text(f'DROP ROLE "{role}"'))
        admin.dispose()


def test_patient_expiry_is_fixed_30_days_and_checked_at_exact_boundary(
    clinic: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import datetime, timedelta

    from careflow import conversations

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        identifier = client.post(
            "/conversations", json={"disclosure_version": "history-v1"}, headers=headers
        ).json()["id"]
        engine = database_engine()
        try:
            with engine.connect() as connection:
                row = connection.execute(
                    text("SELECT created_at,expires_at FROM conversations")
                ).one()
            assert row.expires_at - row.created_at == timedelta(days=30)
            boundary: datetime = row.expires_at
            monkeypatch.setattr(
                conversations, "now", lambda: boundary - timedelta(microseconds=1)
            )
            assert client.get(f"/conversations/{identifier}").status_code == 200
            monkeypatch.setattr(conversations, "now", lambda: boundary)
            assert client.get(f"/conversations/{identifier}").status_code == 404
        finally:
            engine.dispose()


def test_versioned_context_evals_execute_real_http_tools_and_state_graders(
    clinic: UUID,
) -> None:
    import json
    from pathlib import Path

    from test_booking_integration import PASSWORD

    from evals.context_behavior import build_report

    report = build_report(origin=ORIGIN, password=PASSWORD, partition="all")
    destination = Path("test-results/ticket02-context-evals.json")
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    assert report["failed"] == 0, report
    assert report["passed"] == 8
    observed_results = report["results"]
    assert isinstance(observed_results, list)
    for observed_result in observed_results:
        metrics = observed_result["metrics"]
        assert metrics["input_tokens"] is None and metrics["output_tokens"] is None
        if observed_result["observation"]["http_status"] == 200:
            assert metrics["latency_ms"] >= 0 and metrics["provider_calls"] >= 1
    import asyncio

    from evals.catalog_behavior import build_report as catalog_report

    catalog = asyncio.run(catalog_report(partition="all"))
    Path("test-results/ticket02-catalog-evals.json").write_text(
        json.dumps(catalog, indent=2) + "\n", encoding="utf-8"
    )
    summary = catalog["summary"]
    assert isinstance(summary, dict)
    assert summary["counts"] == {
        "passed": 13,
        "failed": 0,
        "pending": 2,
        "skipped": 0,
        "blocked": 0,
    }


def test_migration_enforces_owned_conversation_and_complete_pair_integrity() -> None:
    from sqlalchemy.exc import IntegrityError

    seed()
    with TestClient(app, base_url=ORIGIN) as client:
        headers = guest(client)
        identifier = UUID(
            client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
        )
        engine = database_engine()
        try:
            for statement in (
                "UPDATE conversations SET guest_hash=NULL WHERE id=:id",
                "UPDATE conversations SET expires_at=created_at+interval '31 days' "
                "WHERE id=:id",
                "UPDATE conversations SET guest_hash=NULL, "
                "patient_id=gen_random_uuid(), clinic_id=gen_random_uuid() "
                "WHERE id=:id",
                "INSERT INTO conversation_turns"
                "(conversation_id,id,request_hash,sequence,user_text) "
                "VALUES(:id,gen_random_uuid(),'synthetic',1,'orphaned')",
            ):
                with pytest.raises(IntegrityError), engine.begin() as connection:
                    connection.execute(text(statement), {"id": identifier})
        finally:
            engine.dispose()
