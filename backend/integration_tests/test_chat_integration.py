"""Real orchestrator and catalog services; disposable PostgreSQL, scripted provider."""

import asyncio
import secrets
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from careflow.catalog_fixtures import DOCTORS, SERVICES, SPECIALTIES, load_catalog
from careflow.catalog_schema import doctors, specialties
from careflow.chat import run_chat
from careflow.chat_contracts import Limits, ToolCall, ToolDefinition, ToolResult
from careflow.chat_provider import ProviderError, ProviderReply, ScriptedProvider
from careflow.database import database_engine
from careflow.fixture_schema import clinics
from careflow.fixtures import CLINIC, apply_fixtures
from psycopg import sql
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

pytestmark = pytest.mark.usefixtures("disposable_database")


def seed() -> None:
    command.upgrade(Config("alembic.ini"), "head")
    apply_fixtures("load", confirmed=True)
    load_catalog(confirmed=True)


def search(name: str = "search_doctors", **changes: object) -> ToolCall:
    arguments: dict[str, object] = {
        "query": None,
        "resource_id": None,
        "city": None,
        "limit": 20,
        "offset": 0,
    }
    if name == "search_doctors":
        arguments["specialty_id"] = None
    return ToolCall(name=name, arguments=arguments | changes)


def test_real_catalog_tools_return_exact_authoritative_fees_and_no_model_prose() -> (
    None
):
    seed()
    for call, expected in [
        (search(), ["2500.00", "3500.50"]),
        (
            ToolCall(
                name="get_consultation_fee",
                arguments={"resource_id": str(DOCTORS[1]["id"])},
            ),
            ["3500.50"],
        ),
        (search("search_services"), ["500.00", "1500.25"]),
        (
            ToolCall(
                name="get_service_fee",
                arguments={"resource_id": str(SERVICES[1]["id"])},
            ),
            ["1500.25"],
        ),
    ]:
        provider = ScriptedProvider(
            [
                ProviderReply(stop="tool", calls=[call]),
                ProviderReply(
                    stop="end",
                    text="Dr Fake charges PKR 1.00 and has an open slot. secret-value",
                ),
            ]
        )
        result = asyncio.run(run_chat("catalog fees", provider))
        assert result.status == "answered"
        assert len(result.facts) == 1
        assert all(fee in result.text for fee in expected)
        assert "secret-value" not in result.model_dump_json()
        assert result.actions == [] and result.citations == []
        assert provider.results[0].status == "ok"


def test_empty_ambiguous_and_specialty_matches_are_truthful() -> None:
    seed()
    for call, expected_status, count in [
        (search(query="Synthetic Doctor"), "clarification", 2),
        (search(query="Phantom Doctor"), "clarification", 0),
        (search(city="Lahore"), "clarification", 0),
        (search("search_specialties"), "answered", 2),
        (search(specialty_id=str(SPECIALTIES[1]["id"])), "answered", 1),
        (search(limit=1, offset=1), "answered", 1),
        (
            ToolCall(
                name="get_service_fee", arguments={"resource_id": str(DOCTORS[0]["id"])}
            ),
            "clarification",
            0,
        ),
    ]:
        provider = ScriptedProvider(
            [ProviderReply(stop="tool", calls=[call]), ProviderReply(stop="end")]
        )
        result = asyncio.run(run_chat("lookup", provider))
        assert result.status == expected_status
        assert len(result.facts[0].data) == count
        assert "not establish availability" in result.text
        if count == 0:
            assert "Please clarify" in result.text
        if call.arguments.get("query") == "Synthetic Doctor":
            assert "Please select" in result.text


def test_chat_never_exposes_inactive_or_foreign_clinic_records() -> None:
    seed()
    foreign_clinic, foreign_specialty, foreign_doctor = (
        UUID(int=999),
        UUID(int=998),
        UUID(int=997),
    )
    engine = database_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                clinics.insert().values(**{**CLINIC, "id": foreign_clinic})
            )
            connection.execute(
                specialties.insert().values(
                    **{
                        **SPECIALTIES[0],
                        "id": foreign_specialty,
                        "clinic_id": foreign_clinic,
                    }
                )
            )
            connection.execute(
                doctors.insert().values(
                    **{
                        **DOCTORS[0],
                        "id": foreign_doctor,
                        "clinic_id": foreign_clinic,
                        "specialty_id": foreign_specialty,
                        "name": "Foreign Doctor",
                    }
                )
            )
            connection.execute(
                doctors.update()
                .where(doctors.c.id == DOCTORS[0]["id"])
                .values(active=False)
            )
        for call in [
            search(resource_id=str(foreign_doctor)),
            search(resource_id=str(DOCTORS[0]["id"])),
            search(specialty_id=str(foreign_specialty)),
        ]:
            result = asyncio.run(
                run_chat(
                    "foreign doctor",
                    ScriptedProvider(
                        [
                            ProviderReply(stop="tool", calls=[call]),
                            ProviderReply(stop="end"),
                        ]
                    ),
                )
            )
            assert result.status == "clarification" and result.facts[0].data == []
            assert "Foreign Doctor" not in result.text
        result = asyncio.run(
            run_chat(
                "clinic authority",
                ScriptedProvider(
                    [
                        ProviderReply(
                            stop="tool", calls=[search(clinic_id=str(foreign_clinic))]
                        ),
                        ProviderReply(stop="end"),
                    ]
                ),
            )
        )
        assert not result.facts and result.status == "abstained"
    finally:
        engine.dispose()


def test_malformed_arguments_can_be_corrected_without_executing_the_invalid_call() -> (
    None
):
    seed()
    provider = ScriptedProvider(
        [
            ProviderReply(stop="tool", calls=[search(limit=True)]),
            ProviderReply(stop="tool", calls=[search(limit=1)]),
            ProviderReply(stop="end"),
        ]
    )
    result = asyncio.run(run_chat("doctors", provider))
    assert [r.status for r in provider.results] == ["invalid", "ok"]
    assert result.status == "answered" and len(result.facts[0].data) == 1
    assert [o.status for o in result.metrics.tools] == ["invalid", "ok"]


def test_failures_after_reads_discard_partial_facts_and_loop_budgets_stop() -> None:
    seed()
    cases: list[tuple[list[ProviderReply | Exception], Limits, str]] = [
        (
            [
                ProviderReply(stop="tool", calls=[search()]),
                ProviderError("secret-value"),
            ],
            Limits(),
            "unavailable",
        ),
        (
            [ProviderReply(stop="tool", calls=[search()])] * 6,
            Limits(provider_calls=2),
            "limited",
        ),
        (
            [ProviderReply(stop="tool", calls=[search()])] * 6,
            Limits(tool_calls=1),
            "limited",
        ),
        (
            [
                ProviderReply(stop="tool", calls=[search()]),
                ProviderReply(stop="refused"),
            ],
            Limits(),
            "abstained",
        ),
    ]
    oversized: list[ProviderReply | Exception] = [
        ProviderReply(stop="tool", calls=[search()])
    ]
    oversized *= 4
    oversized.append(ProviderReply(stop="end"))
    cases.append((oversized, Limits(response_bytes=2048), "limited"))
    uncorrected: list[ProviderReply | Exception] = [
        ProviderReply(stop="tool", calls=[search()]),
        ProviderReply(stop="tool", calls=[search(limit=True)]),
        ProviderReply(stop="end"),
    ]
    cases.append((uncorrected, Limits(), "abstained"))
    for replies, limits, status in cases:
        result = asyncio.run(run_chat("doctors", ScriptedProvider(replies), limits))
        assert result.status == status and result.facts == []
        assert "secret-value" not in result.model_dump_json()
        assert result.metrics.provider_calls <= limits.provider_calls


def test_no_catalog_transaction_spans_provider_waits() -> None:
    from sqlalchemy import text

    seed()

    class InspectingProvider(ScriptedProvider):
        async def complete(
            self,
            message: str,
            tools: Sequence[ToolDefinition],
            result: ToolResult | None,
            limits: Limits,
        ) -> ProviderReply:
            def check() -> None:
                engine = database_engine()
                try:
                    with engine.connect() as connection:
                        assert (
                            connection.scalar(
                                text(
                                    "SELECT count(*) FROM pg_stat_activity "
                                    "WHERE datname = current_database() "
                                    "AND state = 'idle in transaction' "
                                    "AND pid <> pg_backend_pid()"
                                )
                            )
                            == 0
                        )
                finally:
                    engine.dispose()

            await asyncio.to_thread(check)
            return await super().complete(message, tools, result, limits)

    provider = InspectingProvider(
        [ProviderReply(stop="tool", calls=[search()]), ProviderReply(stop="end")]
    )
    assert asyncio.run(run_chat("doctors", provider)).status == "answered"


def test_http_chat_envelope_origin_rate_and_transport_secrets() -> None:
    from careflow.chat_api import chat_limits, chat_provider
    from careflow.main import app
    from fastapi.testclient import TestClient

    seed()
    observed: list[str] = []

    class ObservedProvider(ScriptedProvider):
        async def complete(
            self,
            message: str,
            tools: Sequence[ToolDefinition],
            result: ToolResult | None,
            limits: Limits,
        ) -> ProviderReply:
            observed.append(message)
            return await super().complete(message, tools, result, limits)

    async def provider() -> AsyncIterator[ScriptedProvider]:
        yield ObservedProvider(
            [
                ProviderReply(stop="tool", calls=[search(limit=1)]),
                ProviderReply(stop="end"),
            ]
        )

    app.dependency_overrides[chat_provider] = provider
    app.dependency_overrides[chat_limits] = lambda: Limits(rate_per_minute=2)
    try:
        with TestClient(app, base_url="https://localhost:8000") as client:
            for _ in range(2):
                response = client.post(
                    "/chat",
                    json={"version": "1", "message": "doctors"},
                    headers={
                        "origin": "https://localhost:8000",
                        "cookie": "__Host-careflow_session=secret-cookie",
                        "x-csrf-token": "secret-csrf",
                    },
                )
                assert response.status_code == 200
                assert response.json()["status"] == "answered"
                assert (
                    response.json()["facts"][0]["data"][0]["consultation_fee"]
                    == "2500.00"
                )
                assert response.headers["cache-control"] == "no-store"
                assert response.json()["metrics"]["input_tokens"] is None
            response = client.post(
                "/chat",
                json={"version": "1", "message": "doctors"},
                headers={"origin": "https://localhost:8000"},
            )
            assert response.status_code == 429 and "retry-after" in response.headers
            response = client.post(
                "/chat",
                json={"version": "1", "message": "doctors"},
                headers={"origin": "https://evil.invalid"},
            )
            assert response.status_code == 403
        assert set(observed) == {"doctors"}
    finally:
        app.dependency_overrides.clear()


def test_mocked_behavioral_baseline_executes_real_orchestrator_and_catalog() -> None:
    from evals.catalog_behavior import build_report
    from evals.run_catalog import seed_behavior

    seed_behavior()
    report = asyncio.run(build_report(partition="dev"))
    assert report["real_agent_path_exercised"] is True
    assert report["summary"] == {
        "total": 13,
        "executed": 12,
        "pass_rate": 1.0,
        "counts": {"passed": 12, "failed": 0, "skipped": 0, "blocked": 0, "pending": 1},
    }
    metrics = report["metrics"]
    assert isinstance(metrics, dict) and metrics["token_counts"] is None


def test_behavioral_cli_returns_nonzero_for_an_executed_grader_failure(
    tmp_path: Path,
) -> None:
    import hashlib
    import json
    import subprocess
    import sys

    from evals.catalog_behavior import ROOT

    directory = tmp_path / "bad-oracle"
    directory.mkdir()
    cases = [
        json.loads(line)
        for line in (ROOT / "evals/catalog_v1/cases.jsonl").read_text().splitlines()
    ]
    cases[0]["expected"]["required_tools"] = ["search_services"]
    data = ("\n".join(json.dumps(case) for case in cases) + "\n").encode()
    (directory / "cases.jsonl").write_bytes(data)
    manifest = json.loads((ROOT / "evals/catalog_v1/manifest.json").read_text())
    manifest["cases_sha256"] = hashlib.sha256(data).hexdigest()
    manifest["dataset_version"] = "deliberately-invalid-oracle"
    (directory / "manifest.json").write_text(json.dumps(manifest))
    output = tmp_path / "failed-report.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evals.run_catalog",
            "--dataset",
            str(directory),
            "--report",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 1
    report = json.loads(output.read_text())
    assert report["summary"]["counts"]["failed"] == 1
    assert report["summary"]["counts"]["passed"] == 11


def test_chat_catalog_works_with_read_only_catalog_grants_and_no_patient_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from careflow.identity_schema import patients

    seed()
    owner = database_engine()
    role = "careflow_catalog_" + uuid4().hex
    password = secrets.token_urlsafe(32)
    created = False
    try:
        with owner.begin() as connection:
            driver = connection.connection.driver_connection
            assert isinstance(driver, psycopg.Connection)
            driver.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} "
                    "NOSUPERUSER NOCREATEDB NOCREATEROLE"
                ).format(sql.Identifier(role), sql.Literal(password))
            )
        created = True
        with owner.begin() as connection:
            connection.execute(text("GRANT USAGE ON SCHEMA public TO " + role))
            connection.execute(
                text(
                    "GRANT SELECT ON public.clinics, public.specialties, "
                    "public.doctors, public.services TO " + role
                )
            )
        monkeypatch.setenv(
            "DATABASE_URL",
            owner.url.set(username=role, password=password).render_as_string(
                hide_password=False
            ),
        )
        result = asyncio.run(
            run_chat(
                "doctors",
                ScriptedProvider(
                    [
                        ProviderReply(stop="tool", calls=[search()]),
                        ProviderReply(stop="end"),
                    ]
                ),
            )
        )
        assert result.status == "answered" and len(result.facts[0].data) == 2
        with owner.begin() as connection:
            connection.execute(text("REVOKE SELECT ON public.doctors FROM " + role))
        unavailable = asyncio.run(
            run_chat(
                "doctors",
                ScriptedProvider([ProviderReply(stop="tool", calls=[search()])]),
            )
        )
        assert unavailable.status == "unavailable" and not unavailable.facts
        assert unavailable.metrics.tools[0].status == "unavailable"
        reader = database_engine()
        try:
            with pytest.raises(SQLAlchemyError), reader.connect() as connection:
                connection.execute(select(patients.c.id))
            with pytest.raises(SQLAlchemyError), reader.begin() as connection:
                connection.execute(doctors.delete())
        finally:
            reader.dispose()
    finally:
        try:
            if created:
                with owner.begin() as connection:
                    connection.execute(text("DROP OWNED BY " + role))
                    connection.execute(text("DROP ROLE " + role))
        finally:
            owner.dispose()
