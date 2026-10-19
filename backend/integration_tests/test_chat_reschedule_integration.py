"""Rescheduling reviews through real HTTPS/tools/services with synthetic data."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from careflow import booking
from careflow.chat_api import chat_provider
from careflow.chat_contracts import ToolCall
from careflow.chat_provider import ProviderError, ProviderReply, ScriptedProvider
from careflow.main import app
from fastapi.testclient import TestClient
from test_booking_integration import ORIGIN, OTHER, counts, login, propose
from test_booking_integration import clinic as clinic
from test_management_integration import book, other_slot
from test_management_integration import management_clock as management_clock


def reschedule_turn(
    client: TestClient, headers: dict[str, str], appointment_id: str, target_id: UUID
) -> dict[str, Any]:
    provider = ScriptedProvider(
        [
            ProviderReply(
                stop="tool",
                calls=[
                    ToolCall(
                        name="propose_reschedule",
                        arguments={
                            "appointment_id": appointment_id,
                            "slot_id": str(target_id),
                        },
                    )
                ],
            )
        ]
    )
    app.dependency_overrides[chat_provider] = lambda: provider
    try:
        identifier = client.post(
            "/conversations", json={"disclosure_version": "history-v1"}, headers=headers
        ).json()["id"]
        result = client.post(
            f"/conversations/{identifier}/turns",
            json={
                "turn_id": str(uuid4()),
                "message": f"Review reschedule of {appointment_id}",
            },
            headers=headers,
        )
        assert result.status_code == 200, result.text
        return dict(result.json()["response"]["actions"][0])
    finally:
        app.dependency_overrides.clear()


def test_reschedule_review_is_exact_non_executable_history_and_separate_confirm(
    clinic: UUID,
) -> None:
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        target = other_slot(clinic)
        provider = ScriptedProvider(
            [
                ProviderReply(
                    stop="tool",
                    calls=[
                        ToolCall(
                            name="propose_reschedule",
                            arguments={
                                "appointment_id": original["id"],
                                "slot_id": str(target),
                            },
                        )
                    ],
                ),
                ProviderError(),
            ]
        )
        app.dependency_overrides[chat_provider] = lambda: provider
        try:
            identifier = client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
            url = f"/conversations/{identifier}/turns"
            body = {
                "turn_id": str(uuid4()),
                "message": "Review reschedule of selected appointment",
            }
            result = client.post(url, json=body, headers=headers)
            assert result.status_code == 200, result.text
            response = result.json()["response"]
            action = response["actions"][0]
            assert action["kind"] == "reschedule_review"
            assert action["summary"]["operation"] == "reschedule"
            assert action["summary"]["appointment"] == original
            proof = action["proposal_token"]
            assert action["summary"]["target"]["slot_id"] == str(target)
            assert action["summary"]["target"]["fee"] == original["accepted_fee"]
            assert proof not in response["text"]
            assert provider.results == []
            assert counts() == [1, 1, 1]
            assert client.get("/appointments").json()["items"] == [original]
            history = client.get(f"/conversations/{identifier}")
            replay = client.post(url, json=body, headers=headers)
            for historical in (history, replay):
                assert proof not in historical.text
            assert replay.json()["response"]["actions"] == []
            assert "rescheduling" in replay.json()["response"]["text"].lower()
            confirm_url = f"/appointments/{original['id']}/reschedule"
            confirm_body = {"proposal_token": proof}
            confirm_headers = headers | {"Idempotency-Key": "chat-cancel-one"}
            moved = client.post(confirm_url, json=confirm_body, headers=confirm_headers)
            assert moved.status_code == 200, moved.text
            assert moved.json()["status"] == "booked"
            assert moved.json()["id"] == original["id"]
            assert moved.json()["slot_id"] == str(target)
            assert (
                client.post(
                    confirm_url, json=confirm_body, headers=confirm_headers
                ).json()
                == moved.json()
            )
            assert counts() == [1, 2, 2]
            released = propose(client, clinic, headers)["summary"]
            assert isinstance(released, dict) and released["slot_id"] == str(clinic)
            failure = client.post(
                url,
                json={"turn_id": str(uuid4()), "message": "Did it cancel?"},
                headers=headers,
            )
            assert failure.status_code == 503
            assert client.get("/appointments").json()["items"] == [moved.json()]
            assert counts() == [1, 2, 2]
        finally:
            app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "mode",
    [
        "ambiguous",
        "foreign",
        "invented",
        "phantom-target",
        "same-target",
        "guest",
        "csrf",
        "origin",
        "confirm-tool",
        "forged",
        "yes",
        "failure",
        "multi-call",
        "clinic",
    ],
)
def test_reschedule_chat_rejects_untrusted_authority_and_invented_success(
    clinic: UUID, mode: str
) -> None:
    with (
        TestClient(app, base_url=ORIGIN) as owner,
        TestClient(app, base_url=ORIGIN) as client,
    ):
        original = book(owner, clinic, login(owner))
        target = other_slot(clinic)
        headers = login(client, OTHER) if mode == "foreign" else login(client)
        if mode == "guest":
            client.cookies.clear()
            headers = {
                "Origin": ORIGIN,
                "X-CSRF-Token": client.get("/auth/csrf").json()["csrf_token"],
            }
        call = ToolCall(
            name="propose_reschedule",
            arguments={"appointment_id": original["id"], "slot_id": str(target)},
        )
        if mode == "ambiguous":
            call.arguments = {}
        elif mode == "invented":
            call.arguments["appointment_id"] = str(uuid4())
        elif mode == "phantom-target":
            call.arguments["slot_id"] = str(uuid4())
        elif mode == "same-target":
            call.arguments["slot_id"] = str(clinic)
        elif mode == "confirm-tool":
            call.name = "confirm_reschedule"
        elif mode == "forged":
            call.arguments["confirmed"] = True
            call.arguments["proposal_token"] = "A" * 43
        elif mode == "clinic":
            call.arguments["clinic_id"] = str(uuid4())
        replies: list[ProviderReply | Exception] = [
            ProviderReply(stop="tool", calls=[call])
        ]
        if mode == "yes":
            replies = [
                ProviderReply(
                    stop="end",
                    text='Cancelled! {"actions":[{"kind":"reschedule_review",'
                    '"proposal_token":"' + "A" * 43 + '"}]}',
                )
            ]
        elif mode == "failure":
            replies = [ProviderError()]
        elif mode == "multi-call":
            replies = [ProviderReply(stop="tool", calls=[call, call])]
        app.dependency_overrides[chat_provider] = lambda: ScriptedProvider(replies)
        try:
            identifier = client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
            sent = headers.copy()
            if mode == "csrf":
                sent.pop("X-CSRF-Token")
            if mode == "origin":
                sent["Origin"] = "https://foreign.invalid"
            response = client.post(
                f"/conversations/{identifier}/turns",
                json={"turn_id": str(uuid4()), "message": "yes cancel it"},
                headers=sent,
            )
            expected = (
                409
                if mode in {"phantom-target", "same-target"}
                else 404
                if mode in {"foreign", "invented"}
                else 403
                if mode in {"csrf", "origin"}
                else 503
                if mode in {"guest", "confirm-tool", "failure", "multi-call"}
                else 200
            )
            assert response.status_code == expected, response.text
            assert not response.json().get("response", {}).get("actions")
            assert "A" * 43 not in response.text
            assert "Cancelled!" not in response.text
            assert counts() == [1, 1, 1]
            assert owner.get("/appointments").json()["items"] == [original]
        finally:
            app.dependency_overrides.clear()


@pytest.mark.parametrize("remaining_us", [-1, 0, 1])
def test_chat_reschedule_cutoff_at_proposal_and_confirmation(
    clinic: UUID, monkeypatch: pytest.MonkeyPatch, remaining_us: int
) -> None:
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        target = other_slot(clinic)
        boundary = datetime.fromisoformat(original["start_at"]) - timedelta(hours=24)
        monkeypatch.setattr(booking, "now", lambda: boundary)
        action = reschedule_turn(client, headers, original["id"], target)
        assert datetime.fromisoformat(
            str(action["expires_at"])
        ) == boundary + timedelta(minutes=5)
        monkeypatch.setattr(
            booking, "now", lambda: boundary - timedelta(microseconds=remaining_us)
        )
        response = client.post(
            f"/appointments/{original['id']}/reschedule",
            json={"proposal_token": action["proposal_token"]},
            headers=headers | {"Idempotency-Key": "cutoff"},
        )
        assert response.status_code == (409 if remaining_us < 0 else 200), response.text
        assert counts() == ([1, 1, 1] if remaining_us < 0 else [1, 2, 2])
        if remaining_us < 0:
            assert response.json()["code"] == "CHANGE_CUTOFF"
            provider = ScriptedProvider(
                [
                    ProviderReply(
                        stop="tool",
                        calls=[
                            ToolCall(
                                name="propose_reschedule",
                                arguments={
                                    "appointment_id": original["id"],
                                    "slot_id": str(target),
                                },
                            )
                        ],
                    )
                ]
            )
            app.dependency_overrides[chat_provider] = lambda: provider
            try:
                conversation = client.post(
                    "/conversations",
                    json={"disclosure_version": "history-v1"},
                    headers=headers,
                ).json()["id"]
                rejected = client.post(
                    f"/conversations/{conversation}/turns",
                    json={"turn_id": str(uuid4()), "message": "Fresh review"},
                    headers=headers,
                )
                assert (
                    rejected.status_code == 409
                    and rejected.json()["code"] == "CHANGE_CUTOFF"
                )
            finally:
                app.dependency_overrides.clear()


def test_chat_issued_proof_binds_actor_path_action_and_exact_retry(
    clinic: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        TestClient(app, base_url=ORIGIN) as client,
        TestClient(app, base_url=ORIGIN) as other,
    ):
        headers = login(client)
        original = book(client, clinic, headers)
        target = other_slot(clinic)
        action = reschedule_turn(client, headers, original["id"], target)
        path = f"/appointments/{original['id']}/reschedule"
        body = {"proposal_token": action["proposal_token"]}
        keyed = headers | {"Idempotency-Key": "cancel-bound"}
        foreign = login(other, OTHER) | {"Idempotency-Key": "foreign"}
        assert other.post(path, json=body, headers=foreign).status_code == 404
        assert (
            client.post(
                path,
                json=body,
                headers={"Origin": ORIGIN, "Idempotency-Key": "no-csrf"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                path, json=body, headers=keyed | {"Origin": "https://foreign.invalid"}
            ).status_code
            == 403
        )
        assert client.post(path, json={}, headers=keyed).status_code == 422
        assert (
            client.post(
                path, json={"proposal_token": "z" * 43}, headers=keyed
            ).status_code
            == 404
        )
        assert (
            client.post(
                path.replace(original["id"], str(uuid4())), json=body, headers=keyed
            ).status_code
            == 404
        )
        assert (
            client.post(
                path.replace("/reschedule", "/cancel"), json=body, headers=keyed
            ).status_code
            == 404
        )
        assert counts() == [1, 1, 1]
        result = client.post(path, json=body, headers=keyed)
        assert result.status_code == 200
        assert client.post(path, json=body, headers=keyed).json() == result.json()
        assert (
            client.post(path, json={"proposal_token": "z" * 43}, headers=keyed).json()[
                "code"
            ]
            == "IDEMPOTENCY_CONFLICT"
        )
        assert (
            client.post(
                path, json=body, headers=keyed | {"Idempotency-Key": "new-key"}
            ).json()["code"]
            == "PROPOSAL_CONSUMED"
        )
        committed = booking.now()
        monkeypatch.setattr(
            booking,
            "now",
            lambda: committed + timedelta(hours=24) - timedelta(microseconds=1),
        )
        assert client.post(path, json=body, headers=keyed).json() == result.json()
        monkeypatch.setattr(booking, "now", lambda: committed + timedelta(hours=24))
        assert (
            client.post(path, json=body, headers=keyed).json()["code"]
            == "RETRY_EXPIRED"
        )
        assert counts() == [1, 2, 2]


@pytest.mark.parametrize("mode", ["stale", "expired", "cancelled", "past"])
def test_reschedule_review_revalidates_state_without_partial_mutation(
    clinic: UUID, mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from careflow.booking_schema import appointments
    from careflow.database import database_engine
    from sqlalchemy import select

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        target = other_slot(clinic)
        action = reschedule_turn(client, headers, original["id"], target)
        if mode in {"expired", "past"}:
            deadline = (
                datetime.fromisoformat(str(action["expires_at"]))
                if mode == "expired"
                else datetime.fromisoformat(original["end_at"])
            )
            monkeypatch.setattr(booking, "now", lambda: deadline)
        else:
            engine = database_engine()
            try:
                with engine.begin() as connection:
                    connection.execute(
                        appointments.update()
                        .where(appointments.c.id == UUID(original["id"]))
                        .values(
                            version=appointments.c.version + 1,
                            **({"status": "cancelled"} if mode == "cancelled" else {}),
                        )
                    )
            finally:
                engine.dispose()
        engine = database_engine()
        try:
            with engine.connect() as connection:
                before = connection.execute(select(appointments)).mappings().all()
            result = client.post(
                f"/appointments/{original['id']}/reschedule",
                json={"proposal_token": action["proposal_token"]},
                headers=headers | {"Idempotency-Key": "stale"},
            )
            assert result.json()["code"] == (
                "CONFIRMATION_EXPIRED"
                if mode in {"expired", "past"}
                else "APPOINTMENT_INACTIVE"
                if mode == "cancelled"
                else "STATE_CHANGED"
            ), result.text
            with engine.connect() as connection:
                assert (
                    connection.execute(select(appointments)).mappings().all() == before
                )
            assert counts() == [1, 1, 1]
        finally:
            engine.dispose()


def test_sdk_reschedule_review_secrets_schemas_and_current_owned_selection(
    clinic: UUID, caplog: pytest.LogCaptureFixture
) -> None:
    import json
    import logging
    from collections.abc import AsyncIterator

    import httpx2
    from anthropic import AsyncAnthropic
    from careflow.anthropic_provider import AnthropicProvider
    from careflow.chat_provider import Provider
    from careflow.identity_api import COOKIE

    captured: list[str] = []
    selected: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request.content.decode())
        body = json.loads(request.content)
        schemas = {tool["name"]: tool["input_schema"] for tool in body["tools"]}
        assert schemas["propose_reschedule"]["required"] == [
            "appointment_id",
            "slot_id",
        ]
        assert schemas["propose_reschedule"]["additionalProperties"] is False
        assert not any(name.startswith("confirm") for name in schemas)
        if len(captured) == 1:
            name, arguments = (
                "get_my_appointments",
                {
                    "limit": 20,
                    "cursor": None,
                    "status": "booked",
                    "start_at": None,
                    "end_at": None,
                },
            )
        elif len(captured) == 2:
            facts = json.loads(body["messages"][-1]["content"][0]["content"])
            assert facts["appointments"]["items"][0]["id"] == selected[0]
            source = facts["appointments"]["items"][0]
            name, arguments = (
                "get_available_slots",
                {
                    "doctor_id": source["doctor_id"],
                    "start_at": source["start_at"],
                    "end_at": (
                        datetime.fromisoformat(source["end_at"]) + timedelta(hours=2)
                    ).isoformat(),
                    "limit": 20,
                    "offset": 0,
                },
            )
        elif len(captured) == 3:
            facts = json.loads(body["messages"][-1]["content"][0]["content"])
            assert selected[1] in {slot["id"] for slot in facts["slots"]}
            name, arguments = (
                "propose_reschedule",
                {
                    "appointment_id": selected[0],
                    "slot_id": selected[1],
                },
            )
        else:
            name, arguments = "", {}
        return httpx2.Response(
            200,
            json={
                "id": f"msg_{len(captured)}",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-5-5",
                "content": [
                    {
                        "type": "tool_use",
                        "id": f"tool_{len(captured)}",
                        "name": name,
                        "input": arguments,
                    }
                ]
                if name
                else [{"type": "text", "text": "Cancelled!"}],
                "stop_reason": "tool_use" if name else "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 20, "output_tokens": 10},
            },
        )

    async def provide() -> AsyncIterator[Provider]:
        async with AsyncAnthropic(
            api_key="synthetic-placeholder",
            max_retries=0,
            open_telemetry=False,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
        ) as sdk:
            yield AnthropicProvider(sdk)

    caplog.set_level(logging.DEBUG)
    app.dependency_overrides[chat_provider] = provide
    try:
        with TestClient(app, base_url=ORIGIN) as client:
            headers = login(client)
            original = book(client, clinic, headers)
            target = other_slot(clinic)
            selected.extend([original["id"], str(target)])
            cookie = str(client.cookies.get(COOKIE))
            conversation = client.post(
                "/conversations",
                json={"disclosure_version": "history-v1"},
                headers=headers,
            ).json()["id"]
            url = f"/conversations/{conversation}/turns"
            result = client.post(
                url,
                json={
                    "turn_id": str(uuid4()),
                    "message": f"Review reschedule of {original['id']}",
                },
                headers=headers,
            )
            assert result.status_code == 200, result.text
            proof = result.json()["response"]["actions"][0]["proposal_token"]
            assert len(captured) == 3
            assert result.headers["Cache-Control"] == "no-store"
            followup = client.post(
                url, json={"turn_id": str(uuid4()), "message": "yes"}, headers=headers
            )
            assert (
                followup.status_code == 200
                and not followup.json()["response"]["actions"]
            )
            assert "Cancelled!" not in followup.text
            history = client.get(f"/conversations/{conversation}")
            for secret in (
                proof,
                cookie,
                headers["X-CSRF-Token"],
                "synthetic-placeholder",
            ):
                assert secret not in " ".join(captured) + history.text + caplog.text
            assert counts() == [1, 1, 1]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("revocation", ["logout", "reset"])
def test_reschedule_review_rechecks_authority_after_provider_wait(
    clinic: UUID, revocation: str
) -> None:
    from functools import partial

    from careflow.accounts import provision
    from careflow.identity import sign_out
    from careflow.identity_api import COOKIE
    from test_booking_integration import EMAIL, PASSWORD

    from evals.context_behavior import ObservedProvider

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        target = other_slot(clinic)
        conversation = client.post(
            "/conversations", json={"disclosure_version": "history-v1"}, headers=headers
        ).json()["id"]
        token = str(client.cookies.get(COOKIE))
        effect = partial(sign_out, token, headers["X-CSRF-Token"])
        if revocation == "reset":
            effect = partial(provision, EMAIL, PASSWORD, confirmed=True, reset=True)
        provider = ObservedProvider(
            [
                ProviderReply(
                    stop="tool",
                    calls=[
                        ToolCall(
                            name="propose_reschedule",
                            arguments={
                                "appointment_id": original["id"],
                                "slot_id": str(target),
                            },
                        )
                    ],
                )
            ],
            effect,
        )
        app.dependency_overrides[chat_provider] = lambda: provider
        try:
            result = client.post(
                f"/conversations/{conversation}/turns",
                json={"turn_id": str(uuid4()), "message": "Review reschedule"},
                headers=headers,
            )
            assert result.status_code == 401, result.text
            assert counts() == [1, 1, 1]
        finally:
            app.dependency_overrides.clear()


def test_chat_issued_reschedule_rolls_back_proof_retry_capacity_and_audit(
    clinic: UUID,
) -> None:
    from careflow.booking_schema import proposals
    from careflow.database import database_engine
    from sqlalchemy import select, text

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        target = other_slot(clinic)
        action = reschedule_turn(client, headers, original["id"], target)
        engine = database_engine()
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE FUNCTION fail_cancel() RETURNS trigger "
                        "LANGUAGE plpgsql AS $$ BEGIN "
                        "RAISE EXCEPTION 'synthetic failure'; END $$"
                    )
                )
                connection.execute(
                    text(
                        "CREATE TRIGGER fail_cancel BEFORE INSERT ON booking_audit "
                        "FOR EACH ROW EXECUTE FUNCTION fail_cancel()"
                    )
                )
            path = f"/appointments/{original['id']}/reschedule"
            body = {"proposal_token": action["proposal_token"]}
            keyed = headers | {"Idempotency-Key": "rollback"}
            result = client.post(path, json=body, headers=keyed)
            assert result.status_code == 503
            assert client.get("/appointments").json()["items"] == [original]
            assert counts() == [1, 1, 1]
            assert (
                client.post(
                    "/appointments/proposals",
                    json={"slot_id": str(clinic)},
                    headers=headers,
                ).status_code
                == 409
            )
            with engine.begin() as connection:
                assert (
                    connection.scalar(
                        select(proposals.c.appointment_id).where(
                            proposals.c.proof_hash
                            == booking.digest(action["proposal_token"])
                        )
                    )
                    is None
                )
                connection.execute(text("DROP TRIGGER fail_cancel ON booking_audit"))
                connection.execute(text("DROP FUNCTION fail_cancel()"))
            assert client.post(path, json=body, headers=keyed).status_code == 200
            assert counts() == [1, 2, 2]
        finally:
            engine.dispose()


def test_versioned_reschedule_evals_use_real_http_tools_and_state(clinic: UUID) -> None:
    import json
    from pathlib import Path

    from test_booking_integration import PASSWORD
    from test_management_integration import future_doctor_slot

    from evals.reschedule_behavior import build_report

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        target = future_doctor_slot(original)
    report = build_report(
        origin=ORIGIN,
        password=PASSWORD,
        appointment_id=UUID(original["id"]),
        slot_id=target,
        partition="all",
    )
    Path("test-results/ticket05-reschedule-evals.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    assert report["counts"] == {"passed": 10, "failed": 0}, report["results"]


@pytest.mark.parametrize(
    "change", ["fee", "version", "inactive", "same-slot", "invented"]
)
def test_chat_target_changes_and_invalid_targets_preserve_original(
    clinic: UUID, change: str
) -> None:
    from careflow.catalog_schema import doctors
    from careflow.database import database_engine
    from careflow.schedule_schema import slots
    from test_booking_integration import DOCTOR

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        target = other_slot(clinic)
        path = f"/appointments/{original['id']}/reschedule"
        if change in {"same-slot", "invented"}:
            response = client.post(
                path + "/proposals",
                json={"slot_id": str(clinic if change == "same-slot" else uuid4())},
                headers=headers,
            )
            assert response.status_code == 409
        else:
            review = reschedule_turn(client, headers, original["id"], target)
            engine = database_engine()
            try:
                with engine.begin() as connection:
                    if change == "fee":
                        connection.execute(
                            doctors.update()
                            .where(doctors.c.id == DOCTOR)
                            .values(consultation_fee="2600.00")
                        )
                    elif change == "version":
                        connection.execute(
                            slots.update()
                            .where(slots.c.id == target)
                            .values(version=slots.c.version + 1)
                        )
                    else:
                        connection.execute(
                            slots.update()
                            .where(slots.c.id == target)
                            .values(active=False)
                        )
            finally:
                engine.dispose()
            response = client.post(
                path,
                json={"proposal_token": review["proposal_token"]},
                headers={**headers, "Idempotency-Key": "stale"},
            )
            assert response.status_code == 409
        assert client.get("/appointments").json()["items"] == [original]
        assert counts() == [1, 1, 1]
        if change == "fee":
            fresh = reschedule_turn(client, headers, original["id"], target)
            assert fresh["summary"]["target"]["fee"] == "2600.00"
            moved = client.post(
                path,
                json={"proposal_token": fresh["proposal_token"]},
                headers={**headers, "Idempotency-Key": "fresh"},
            )
            assert (
                moved.status_code == 200 and moved.json()["accepted_fee"] == "2600.00"
            )


@pytest.mark.parametrize(
    "race", ["duplicate", "different-keys", "cancel", "reset", "logout"]
)
def test_chat_issued_reschedule_proof_independent_connection_races(
    clinic: UUID, race: str
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from careflow.accounts import provision
    from careflow.booking_schema import appointments, proposals
    from careflow.database import database_engine
    from careflow.identity import IdentityError, sign_out
    from careflow.identity_api import COOKIE
    from careflow.management import confirm_change
    from sqlalchemy import select
    from test_booking_integration import EMAIL, PASSWORD
    from test_management_integration import change_review, other_slot

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        target = other_slot(clinic)
        action = reschedule_turn(client, headers, original["id"], target)
        token = str(client.cookies.get(COOKIE))
        move = (
            change_review(client, original, "cancel", headers)
            if race == "cancel"
            else None
        )
    barrier = Barrier(2)

    def attempt(index: int) -> str:
        barrier.wait(timeout=10)
        try:
            if index == 1 and race == "reset":
                provision(EMAIL, PASSWORD, confirmed=True, reset=True)
                return "revoked"
            if index == 1 and race == "logout":
                sign_out(token, headers["X-CSRF-Token"])
                return "revoked"
            if index == 1 and move is not None:
                confirm_change(
                    UUID(original["id"]),
                    "cancel",
                    move["proposal_token"],
                    "move-race",
                    token,
                    headers["X-CSRF-Token"],
                )
                return "cancelled"
            confirm_change(
                UUID(original["id"]),
                "reschedule",
                action["proposal_token"],
                "same" if race == "duplicate" else f"cancel-{index}",
                token,
                headers["X-CSRF-Token"],
            )
            return "moved"
        except IdentityError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, (0, 1)))
    if race == "duplicate":
        assert outcomes == ["moved", "moved"]
    elif race == "different-keys":
        assert sorted(outcomes) == ["PROPOSAL_CONSUMED", "moved"]
    elif race == "cancel":
        assert sorted(outcomes) in (
            ["APPOINTMENT_INACTIVE", "cancelled"],
            ["STATE_CHANGED", "moved"],
        )
    else:
        assert outcomes[1] == "revoked" and outcomes[0] in {
            "AUTH_REQUIRED",
            "moved",
        }
    engine = database_engine()
    try:
        with engine.connect() as connection:
            row = connection.execute(select(appointments)).mappings().one()
            consumed = connection.scalar(
                select(proposals.c.appointment_id).where(
                    proposals.c.proof_hash == booking.digest(action["proposal_token"])
                )
            )
            changed = (
                row["status"] == "cancelled"
                or str(row["slot_id"]) != original["slot_id"]
            )
            assert row["version"] == (2 if changed else 1)
            assert counts() == ([1, 2, 2] if changed else [1, 1, 1])
            assert (consumed is not None) == (str(row["slot_id"]) == str(target))
            if "moved" in outcomes:
                assert row["slot_id"] == target and row["status"] == "booked"
    finally:
        engine.dispose()


@pytest.mark.parametrize("opposite", [False, True])
def test_independent_sources_contend_for_target_or_reject_opposite_moves(
    clinic: UUID, opposite: bool
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from careflow.booking_schema import appointments, audit
    from careflow.database import database_engine
    from careflow.identity import IdentityError
    from careflow.identity_api import COOKIE
    from careflow.management import confirm_change, propose_change
    from careflow.schedule_schema import slots
    from sqlalchemy import select

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        first = book(client, clinic, headers)
        second_slot = other_slot(clinic)
        second = book(client, second_slot, headers, "second-source")
        token = str(client.cookies.get(COOKIE))
        engine = database_engine()
        try:
            with engine.connect() as connection:
                target = connection.scalar(
                    select(slots.c.id)
                    .where(slots.c.id.not_in([clinic, second_slot]))
                    .order_by(slots.c.start_at)
                )
            assert isinstance(target, UUID)
        finally:
            engine.dispose()
        sources = [first, second]
        reviews = (
            []
            if opposite
            else [
                reschedule_turn(client, headers, row["id"], target) for row in sources
            ]
        )
    barrier = Barrier(2)

    def attempt(index: int) -> str:
        barrier.wait(timeout=10)
        try:
            if opposite:
                propose_change(
                    UUID(sources[index]["id"]),
                    "reschedule",
                    UUID(sources[1 - index]["slot_id"]),
                    token,
                    headers["X-CSRF-Token"],
                )
            else:
                confirm_change(
                    UUID(sources[index]["id"]),
                    "reschedule",
                    reviews[index]["proposal_token"],
                    f"contend-{index}",
                    token,
                    headers["X-CSRF-Token"],
                )
            return "moved"
        except IdentityError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, [0, 1]))
    assert sorted(outcomes) == (
        ["SLOT_UNAVAILABLE", "SLOT_UNAVAILABLE"]
        if opposite
        else ["SLOT_UNAVAILABLE", "moved"]
    )
    engine = database_engine()
    try:
        with engine.connect() as connection:
            rows = connection.execute(select(appointments)).mappings().all()
            active = [row["slot_id"] for row in rows if row["status"] == "booked"]
            assert len(active) == len(set(active)) == 2
            assert counts() == ([2, 2, 2] if opposite else [2, 3, 3])
            for row in rows:
                source = next(item for item in sources if item["id"] == str(row["id"]))
                if row["slot_id"] != target:
                    assert str(row["slot_id"]) == source["slot_id"]
                history = (
                    connection.execute(
                        select(audit)
                        .where(audit.c.appointment_id == row["id"])
                        .order_by(audit.c.created_at)
                    )
                    .mappings()
                    .all()
                )
                assert history[-1]["after_snapshot"]["slot_id"] == str(row["slot_id"])
    finally:
        engine.dispose()


def test_chat_target_start_expires_review_even_before_five_minutes(
    clinic: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_management_integration import change_review, future_doctor_slot

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        original = book(client, clinic, headers)
        future = future_doctor_slot(original)
        review = change_review(client, original, "reschedule", headers, future)
        path = f"/appointments/{original['id']}/reschedule"
        moved = client.post(
            path,
            json={"proposal_token": review["proposal_token"]},
            headers={**headers, "Idempotency-Key": "future"},
        ).json()
        target_start = datetime.fromisoformat(original["start_at"])
        monkeypatch.setattr(booking, "now", lambda: target_start - timedelta(minutes=1))
        review = reschedule_turn(client, headers, moved["id"], clinic)
        monkeypatch.setattr(booking, "now", lambda: target_start)
        result = client.post(
            path,
            json={"proposal_token": review["proposal_token"]},
            headers={**headers, "Idempotency-Key": "started"},
        )
        assert result.status_code == 410, result.text
        assert result.json()["code"] == "CONFIRMATION_EXPIRED"
        assert client.get("/appointments").json()["items"] == [moved]
