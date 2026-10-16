"""Patient sessions tested at HTTP and operator CLI boundaries with PostgreSQL."""

import asyncio
import secrets
import subprocess
import sys
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import httpx
import psycopg
import pytest
from alembic import command
from alembic.config import Config
from careflow.database import database_engine
from careflow.fixtures import apply_fixtures
from careflow.main import app
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import text

ORIGIN = "https://testserver"
PATIENT_ONE = "patient.one@careflow.example.invalid"
PATIENT_TWO = "patient.two@careflow.example.invalid"
PASSWORD = "Synthetic-Only-Password-For-Tests!"
NEW_PASSWORD = "Synthetic-Only-Replacement-For-Tests!"
COOKIE = "__Host-careflow_session"


def account(
    action: str, email: str, password: str = PASSWORD
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "careflow.accounts",
            action,
            "--email",
            email,
            "--confirm-synthetic-account",
            "--password-stdin",
        ],
        input=password + "\n",
        capture_output=True,
        text=True,
        timeout=20,
    )


@pytest.fixture
def patient_database(
    disposable_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    monkeypatch.setenv("AUTH_ORIGIN", ORIGIN)
    command.upgrade(Config("alembic.ini"), "head")
    apply_fixtures("load", confirmed=True)
    yield


def login(
    client: TestClient, email: str = PATIENT_ONE, password: str = PASSWORD
) -> tuple[str, str]:
    csrf = client.get("/auth/csrf")
    assert csrf.status_code == 200
    before = client.cookies.get(COOKIE)
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf.json()["csrf_token"]},
    )
    assert response.status_code == 200, response.text
    assert client.cookies.get(COOKIE) != before
    return str(client.cookies.get(COOKIE)), response.json()["csrf_token"]


def test_explicit_provisioning_enables_patient_login_and_server_identity(
    patient_database: None,
) -> None:
    result = account("create", PATIENT_ONE)
    assert result.returncode == 0, result.stdout + result.stderr
    assert PASSWORD not in result.stdout + result.stderr
    with TestClient(app, base_url=ORIGIN) as client:
        token, csrf = login(client)
        response = client.get("/auth/me")
        assert response.status_code == 200
        identity = response.json()
        assert identity["email"] == PATIENT_ONE
        assert identity["role"] == "patient"
        assert identity["patient_id"] != "00000000-0000-4000-8000-000000000011"
        assert identity["user_id"] != identity["patient_id"]
        assert set(identity) == {"user_id", "patient_id", "email", "role"}
        assert token not in response.text and csrf not in response.text
        cookie = client.get("/auth/csrf").headers.get("set-cookie", "")
        assert "Secure" in cookie and "HttpOnly" in cookie
        assert "SameSite=strict" in cookie and "Path=/" in cookie
        assert "Domain=" not in cookie


def test_logout_revokes_the_session_and_retries_are_harmless(
    patient_database: None,
) -> None:
    assert account("create", PATIENT_ONE).returncode == 0
    with TestClient(app, base_url=ORIGIN) as client:
        token, csrf = login(client)
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
        assert client.post("/auth/logout", headers=headers).status_code == 204
        assert client.cookies.get(COOKIE) is None
        assert client.get("/auth/me").status_code == 401
        client.cookies.set(COOKIE, token)
        assert client.get("/auth/me").status_code == 401
        assert client.post("/auth/logout", headers=headers).status_code == 204


def test_password_reset_revokes_all_owned_sessions_and_preserves_other_patients(
    patient_database: None,
) -> None:
    assert account("create", PATIENT_ONE).returncode == 0
    assert account("create", PATIENT_TWO).returncode == 0
    with (
        TestClient(app, base_url=ORIGIN) as first,
        TestClient(app, base_url=ORIGIN) as second,
        TestClient(app, base_url=ORIGIN) as other,
    ):
        login(first)
        login(second)
        login(other, PATIENT_TWO)
        original_id = first.get("/auth/me").json()["patient_id"]
        result = account("reset-password", PATIENT_ONE, NEW_PASSWORD)
        assert result.returncode == 0, result.stdout + result.stderr
        assert NEW_PASSWORD not in result.stdout + result.stderr
        assert first.get("/auth/me").status_code == 401
        assert second.get("/auth/me").status_code == 401
        assert other.get("/auth/me").json()["email"] == PATIENT_TWO
        csrf = first.get("/auth/csrf").json()["csrf_token"]
        failure = first.post(
            "/auth/login",
            json={"email": PATIENT_ONE, "password": PASSWORD},
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )
        assert failure.status_code == 401
        login(first, password=NEW_PASSWORD)
        assert first.get("/auth/me").json()["patient_id"] == original_id


def test_login_failure_is_generic_and_unprovisioned_personas_cannot_sign_in(
    patient_database: None,
) -> None:
    assert account("create", PATIENT_ONE).returncode == 0
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = client.get("/auth/csrf").json()["csrf_token"]
        for email, password in (
            (PATIENT_ONE, NEW_PASSWORD),
            (PATIENT_TWO, PASSWORD),
            ("missing@careflow.example.invalid", PASSWORD),
        ):
            response = client.post(
                "/auth/login",
                json={"email": email, "password": password},
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            )
            assert response.status_code == 401
            assert response.json()["code"] == "INVALID_CREDENTIALS"
            assert response.json()["message"] == "Invalid credentials."
            assert password not in response.text and email not in response.text
        assert client.get("/auth/me").status_code == 401


def test_csrf_and_client_identity_fields_cannot_authorize_actions(
    patient_database: None,
) -> None:
    assert account("create", PATIENT_ONE).returncode == 0
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = client.get("/auth/csrf").json()["csrf_token"]
        for headers in (
            {"Origin": ORIGIN},
            {"Origin": ORIGIN, "X-CSRF-Token": "x" * 43},
            {"X-CSRF-Token": csrf},
            {"Origin": "https://attacker.invalid", "X-CSRF-Token": csrf},
        ):
            result = client.post(
                "/auth/login",
                json={"email": PATIENT_ONE, "password": PASSWORD},
                headers=headers,
            )
            assert result.status_code == 403
        response = client.post(
            "/auth/login",
            json={
                "email": PATIENT_ONE,
                "password": PASSWORD,
                "role": "admin",
                "patient_id": "caller-owned",
            },
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )
        assert response.status_code == 422
        assert PASSWORD not in response.text
        _, csrf = login(client)
        for path in ("/auth/register", "/auth/recover"):
            assert (
                client.post(
                    path, json={"role": "admin", "email": PATIENT_ONE}
                ).status_code
                == 404
            )
        assert (
            client.post("/auth/logout", headers={"Origin": ORIGIN}).status_code == 403
        )
        assert client.get("/auth/me").status_code == 200


def test_patients_cannot_select_each_others_identity(patient_database: None) -> None:
    assert account("create", PATIENT_ONE).returncode == 0
    assert account("create", PATIENT_TWO).returncode == 0
    with (
        TestClient(app, base_url=ORIGIN) as first,
        TestClient(app, base_url=ORIGIN) as other,
    ):
        login(first)
        login(other, PATIENT_TWO)
        first_identity = first.get("/auth/me").json()
        other_identity = other.get("/auth/me").json()
        assert first_identity["patient_id"] != other_identity["patient_id"]
        response = first.get(
            "/auth/me",
            params={"patient_id": other_identity["patient_id"], "role": "admin"},
            headers={"X-Patient-ID": other_identity["patient_id"]},
        )
        assert response.json() == first_identity
        first.cookies.set(COOKIE, "invented-session-token")
        # Use an explicit cookie header to replace the authenticated cookie entirely.
        assert (
            first.get(
                "/auth/me", headers={"Cookie": COOKIE + "=invented-session-token"}
            ).status_code
            == 401
        )


def test_sessions_expire_without_sliding_extension(
    patient_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert account("create", PATIENT_ONE).returncode == 0
    with TestClient(app, base_url=ORIGIN) as client:
        token, _ = login(client)
        real_time = time.time()
        with monkeypatch.context() as clock:
            clock.setattr(time, "time", lambda: real_time + 7 * 3600)
            refreshed = client.get("/auth/csrf")
            assert refreshed.status_code == 200
            assert (
                "Max-Age=3599" in refreshed.headers["set-cookie"]
                or "Max-Age=3600" in refreshed.headers["set-cookie"]
            )
        with monkeypatch.context() as clock:
            clock.setattr(time, "time", lambda: real_time + 8 * 3600 + 1)
            assert (
                client.get(
                    "/auth/me", headers={"Cookie": COOKIE + "=" + token}
                ).status_code
                == 401
            )


def test_repeated_login_failures_are_limited_across_new_sessions(
    patient_database: None,
) -> None:
    assert account("create", PATIENT_ONE).returncode == 0
    with TestClient(app, base_url=ORIGIN) as client:
        for attempt in range(6):
            client.cookies.clear()
            csrf = client.get("/auth/csrf").json()["csrf_token"]
            response = client.post(
                "/auth/login",
                json={"email": PATIENT_ONE, "password": NEW_PASSWORD},
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            )
            assert response.status_code == (401 if attempt < 5 else 429)
        assert response.json()["code"] == "RATE_LIMITED"
        assert response.headers["retry-after"] == "300"


def test_malformed_csrf_is_a_safe_rejection(patient_database: None) -> None:
    async def request() -> httpx.Response:
        # ASGITransport preserves raw header bytes; TestClient re-encodes them.
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=ORIGIN
        ) as client:
            assert (await client.get("/auth/csrf")).status_code == 200
            return await client.post(
                "/auth/login",
                json={"email": PATIENT_ONE, "password": PASSWORD},
                headers=[(b"Origin", ORIGIN.encode()), (b"X-CSRF-Token", b"\xff" * 43)],
            )

    response = asyncio.run(request())
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_REJECTED"


def test_provisioning_denies_staff_and_retries_cannot_change_credentials(
    patient_database: None,
) -> None:
    for email in (
        "admin@careflow.example.invalid",
        "receptionist@careflow.example.invalid",
    ):
        assert account("create", email).returncode == 1
    assert account("reset-password", PATIENT_ONE).returncode == 1
    assert account("create", PATIENT_ONE, "short").returncode == 1
    assert account("create", PATIENT_ONE).returncode == 0
    assert account("create", PATIENT_ONE, NEW_PASSWORD).returncode == 1
    assert account("reset-password", PATIENT_ONE, "short").returncode == 1
    with TestClient(app, base_url=ORIGIN) as client:
        login(client)
        assert client.get("/auth/me").json()["email"] == PATIENT_ONE


def test_concurrent_login_consumes_a_prelogin_session_only_once(
    patient_database: None,
) -> None:
    assert account("create", PATIENT_ONE).returncode == 0
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = client.get("/auth/csrf").json()["csrf_token"]
        cookie = str(client.cookies.get(COOKIE))
    barrier = Barrier(2)

    def attempt() -> int:
        with TestClient(app, base_url=ORIGIN) as client:
            barrier.wait(timeout=10)
            result = client.post(
                "/auth/login",
                json={"email": PATIENT_ONE, "password": PASSWORD},
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": csrf,
                    "Cookie": COOKIE + "=" + cookie,
                },
            )
            return int(result.status_code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results) == [200, 401]
    with TestClient(app, base_url=ORIGIN) as client:
        replay = client.post(
            "/auth/login",
            json={"email": PATIENT_ONE, "password": PASSWORD},
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": csrf,
                "Cookie": COOKIE + "=" + cookie,
            },
        )
        assert replay.status_code == 401


def test_password_reset_racing_login_cannot_leave_an_old_password_session(
    patient_database: None,
) -> None:
    assert account("create", PATIENT_ONE).returncode == 0
    barrier = Barrier(2)

    def reset() -> int:
        barrier.wait(timeout=10)
        return account("reset-password", PATIENT_ONE, NEW_PASSWORD).returncode

    with TestClient(app, base_url=ORIGIN) as client:
        csrf = client.get("/auth/csrf").json()["csrf_token"]
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(reset)
            barrier.wait(timeout=10)
            signed_in = client.post(
                "/auth/login",
                json={"email": PATIENT_ONE, "password": PASSWORD},
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            )
            assert result.result(timeout=30) == 0
        assert signed_in.status_code in {200, 401}
        assert client.get("/auth/me").status_code == 401
        login(client, password=NEW_PASSWORD)
        assert client.get("/auth/me").status_code == 200


def test_application_role_can_authenticate_but_cannot_provision_or_reset(
    patient_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert account("create", PATIENT_ONE).returncode == 0
    owner = database_engine()
    role = "careflow_auth_" + uuid4().hex
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
            for grant in (
                "GRANT USAGE ON SCHEMA public",
                "GRANT SELECT ON public.alembic_version, public.users, public.patients",
                "GRANT UPDATE (password_hash) ON public.users",
                "GRANT SELECT, INSERT, UPDATE, DELETE "
                "ON public.sessions, public.auth_limits",
            ):
                connection.execute(text(grant + f' TO "{role}"'))
        monkeypatch.setenv(
            "DATABASE_URL",
            owner.url.set(
                username=role,
                password=password,
            ).render_as_string(hide_password=False),
        )
        with TestClient(app, base_url=ORIGIN) as client:
            _, csrf = login(client)
            assert client.get("/ready").status_code == 200
            assert client.get("/auth/me").json()["email"] == PATIENT_ONE
            assert account("create", PATIENT_TWO).returncode == 1
            assert account("reset-password", PATIENT_ONE, NEW_PASSWORD).returncode == 1
            assert client.get("/auth/me").status_code == 200
            assert (
                client.post(
                    "/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}
                ).status_code
                == 204
            )
    finally:
        try:
            if created:
                with owner.begin() as connection:
                    connection.execute(text(f'DROP OWNED BY "{role}"'))
                    connection.execute(text(f'DROP ROLE "{role}"'))
        finally:
            owner.dispose()
