"""Real browser/proxy/TLS/FastAPI/PostgreSQL; only external provider scripted."""

import asyncio
import os
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import httpx2
import pytest
import uvicorn
from alembic import command
from alembic.config import Config
from anthropic import AsyncAnthropic
from careflow import conversations, identity
from careflow.accounts import provision
from careflow.anthropic_provider import AnthropicProvider
from careflow.chat_api import chat_provider
from careflow.chat_provider import Provider
from careflow.database import database_engine
from careflow.fixtures import apply_fixtures
from careflow.main import app
from playwright.sync_api import Request as BrowserRequest
from playwright.sync_api import Route as BrowserRoute
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "Synthetic-Only-Password-For-Tests!"
EMAIL = "patient.one@careflow.example.invalid"


@dataclass
class ProviderHTTP:
    unavailable: bool = False
    entered: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)

    def __post_init__(self) -> None:
        self.release.set()


@pytest.fixture
def scripted_http() -> Iterator[ProviderHTTP]:
    """Real pinned SDK/adapter with only external HTTP scripted, no live calls."""

    control = ProviderHTTP()

    async def handler(request: httpx2.Request) -> httpx2.Response:
        control.entered.set()
        assert await asyncio.to_thread(control.release.wait, 20)
        if control.unavailable:
            return httpx2.Response(
                503,
                json={
                    "error": {
                        "type": "overloaded_error",
                        "message": "Scripted unavailable",
                    }
                },
            )
        return httpx2.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-5-5",
                "content": [{"type": "text", "text": "Untrusted provider prose"}],
                "stop_reason": "end_turn",
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

    app.dependency_overrides[chat_provider] = provide
    try:
        yield control
    finally:
        control.release.set()
        app.dependency_overrides.pop(chat_provider, None)


def port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@pytest.fixture
def frontend(
    disposable_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scripted_http: ProviderHTTP,
    request: pytest.FixtureRequest,
) -> Iterator[tuple[str, ssl.SSLContext]]:
    """Use the standard disposable DB runner; no test endpoint in production."""
    command.upgrade(Config("alembic.ini"), "head")
    apply_fixtures("load", confirmed=True)
    provision(EMAIL, PASSWORD, confirmed=True)
    tls = subprocess.run(
        [
            "pwsh.exe",
            "-NoProfile",
            "-File",
            str(ROOT / "scripts/export-localhost-tls.ps1"),
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert tls.returncode == 0, "Existing trusted localhost TLS export failed"
    certificate, key = tmp_path / "localhost.pem", tmp_path / "localhost.key"
    # Remove only this test's exported private-key copy, after server teardown.
    request.addfinalizer(lambda: key.unlink(missing_ok=True))
    backend_ca = certificate
    untrusted_backend = getattr(request, "param", "trusted") == "untrusted"
    if untrusted_backend:
        if sys.platform != "win32":
            pytest.fail("This TLS fixture requires the documented Windows trust setup")
        backend_ca = tmp_path / "unrelated-root.pem"
        unrelated = next(
            der
            for der, encoding, _ in ssl.enum_certificates("ROOT")
            if encoding == "x509_asn"
            and ssl.DER_cert_to_PEM_cert(der).strip() != certificate.read_text().strip()
        )
        backend_ca.write_text(ssl.DER_cert_to_PEM_cert(unrelated), encoding="ascii")
    context = ssl.create_default_context(cafile=str(certificate))
    api_port, ui_port = port(), port()
    origin = f"https://localhost:{ui_port}"
    monkeypatch.setenv("AUTH_ORIGIN", origin)
    monkeypatch.setenv("CHAT_ENABLED", "false")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=api_port,
            ssl_certfile=str(certificate),
            ssl_keyfile=str(key),
            log_level="warning",
            access_log=False,
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in {"DATABASE_URL", "TEST_DATABASE_URL", "ANTHROPIC_API_KEY"}
    } | {
        "PORT": str(ui_port),
        "CAREFLOW_BACKEND_ORIGIN": f"https://localhost:{api_port}",
        "CAREFLOW_TLS_CERT": str(certificate),
        "CAREFLOW_TLS_KEY": str(key),
        "CAREFLOW_BACKEND_CA": str(backend_ca),
        "NEXT_TELEMETRY_DISABLED": "1",
    }
    log = tmp_path / "frontend.log"
    try:
        with (
            log.open("w", encoding="utf-8") as output,
            subprocess.Popen(
                [shutil.which("node") or "node", "server.mjs", "--production"],
                cwd=ROOT / "frontend",
                env=environment,
                stdout=output,
                stderr=output,
            ) as process,
        ):
            try:
                with httpx.Client(verify=context, trust_env=False) as client:
                    for _ in range(180):
                        if process.poll() is not None:
                            pytest.fail(
                                "Frontend exited before readiness; inspect frontend.log"
                            )
                        try:
                            if client.get(origin + "/api/auth/me").status_code == (
                                502 if untrusted_backend else 401
                            ):
                                break
                        except httpx.TransportError:
                            pass
                        time.sleep(0.25)
                    else:
                        pytest.fail("Frontend HTTPS readiness timed out")
                yield origin, context
            finally:
                process.terminate()
                process.wait(timeout=20)
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        assert not thread.is_alive(), "HTTPS backend did not stop"


def test_proxy_preserves_secure_auth_and_rejects_foreign_origin(
    frontend: tuple[str, ssl.SSLContext],
) -> None:
    origin, context = frontend
    with httpx.Client(base_url=origin, verify=context, trust_env=False) as client:
        csrf = client.get("/api/auth/csrf")
        assert csrf.status_code == 200
        cookie = csrf.headers["set-cookie"].lower()
        assert "__host-careflow_session=" in cookie
        assert all(
            flag in cookie
            for flag in ["secure", "httponly", "samesite=strict", "path=/"]
        )
        headers = {
            "Origin": "https://foreign.invalid",
            "X-CSRF-Token": csrf.json()["csrf_token"],
        }
        rejected = client.post(
            "/api/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
            headers=headers,
        )
        assert rejected.status_code == 403
        headers["Origin"] = origin
        signed_in = client.post(
            "/api/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
            headers=headers,
        )
        assert signed_in.status_code == 200
        identity = client.get("/api/auth/me")
        assert identity.status_code == 200
        assert identity.headers["cache-control"] == "no-store"


def test_browser_signin_requires_explicit_consent_before_saving(
    frontend: tuple[str, ssl.SSLContext],
) -> None:
    origin, _ = frontend
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(origin)
            expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
            expect(page.get_by_label("Message")).to_have_count(0)
            page.get_by_label("Email").fill(EMAIL)
            page.get_by_label("Password", exact=True).fill(PASSWORD)
            page.get_by_label("Password", exact=True).press("Enter")
            expect(
                page.get_by_role("heading", name="Before you save a chat")
            ).to_be_visible()
            expect(
                page.get_by_role("button", name="Create saved chat")
            ).to_be_disabled()
            engine = database_engine()
            try:
                with engine.connect() as connection:
                    assert (
                        connection.scalar(text("SELECT count(*) FROM conversations"))
                        == 0
                    )
            finally:
                engine.dispose()
            page.get_by_label("I accept the storage disclosure").check()
            page.get_by_role("button", name="Create saved chat").click()
            expect(page.get_by_label("Message", exact=True)).to_be_visible()
            page.screenshot(
                path=str(ROOT / "test-results/ticket01-desktop.png"), full_page=True
            )
            page.set_viewport_size({"width": 375, "height": 812})
            expect(page.get_by_label("Message", exact=True)).to_be_visible()
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            )
            page.screenshot(
                path=str(ROOT / "test-results/ticket01-mobile.png"), full_page=True
            )
        finally:
            browser.close()


def api_login(client: httpx.Client, origin: str, email: str = EMAIL) -> dict[str, str]:
    token = client.get("/api/auth/csrf").json()["csrf_token"]
    result = client.post(
        "/api/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"Origin": origin, "X-CSRF-Token": token},
    )
    assert result.status_code == 200
    return {"Origin": origin, "X-CSRF-Token": result.json()["csrf_token"]}


def test_proxy_preserves_patient_isolation_csrf_expiry_and_route_boundaries(
    frontend: tuple[str, ssl.SSLContext],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin, context = frontend
    other = "patient.two@careflow.example.invalid"
    provision(other, PASSWORD, confirmed=True)
    with (
        httpx.Client(base_url=origin, verify=context, trust_env=False) as first,
        httpx.Client(base_url=origin, verify=context, trust_env=False) as second,
        httpx.Client(base_url=origin, verify=context, trust_env=False) as anonymous,
    ):
        headers = api_login(first, origin)
        created = first.post(
            "/api/conversations",
            json={"disclosure_version": "history-v1"},
            headers=headers,
        )
        assert created.status_code == 201
        path = "/api/conversations/" + created.json()["id"]
        api_login(second, origin, other)
        assert second.get(path).status_code == 404
        assert second.get("/api/conversations/" + str(uuid4())).status_code == 404
        assert (
            anonymous.get(
                path, headers={"X-Forwarded-User": EMAIL, "X-Forwarded-Proto": "https"}
            ).status_code
            == 401
        )
        assert (
            first.get(path, headers={"Origin": "https://foreign.invalid"}).status_code
            == 403
        )
        assert (
            first.get(path, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
        )
        assert (
            first.delete(
                path, headers={"Origin": origin, "X-CSRF-Token": "invalid"}
            ).status_code
            == 403
        )
        assert first.get(path).status_code == 200
        assert first.post("/api/auth/logout", headers=headers).status_code == 204
        assert first.get(path).status_code == 401
        assert first.post("/api/auth/logout", headers=headers).status_code == 204
        for forbidden in [
            "/api/appointments",
            "/api/chat",
            "/api/health",
            "/api/auth/me?target=https://foreign.invalid",
            "/api/conversations/%2e%2e/auth/me",
        ]:
            assert anonymous.get(forbidden).status_code == 404
        assert anonymous.post("/api/auth/me").status_code == 405
        oversized = anonymous.post(
            "/api/auth/login",
            content=b"x" * 4097,
            headers={"Origin": origin, "Content-Type": "application/json"},
        )
        assert oversized.status_code == 413
        assert oversized.headers["cache-control"] == "no-store"
        assert "access-control-allow-origin" not in oversized.headers
        frozen = datetime.now(UTC) + timedelta(hours=9)
        monkeypatch.setattr(identity, "now", lambda: frozen)
        assert second.get("/api/auth/me").status_code == 401


def test_browser_session_expiry_discards_protected_state(
    frontend: tuple[str, ssl.SSLContext],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin, _ = frontend
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(origin)
            page.get_by_label("Email").fill(EMAIL)
            page.get_by_label("Password", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.get_by_label("I accept the storage disclosure").check()
            page.get_by_role("button", name="Create saved chat").click()
            page.get_by_label("Message", exact=True).fill("Synthetic expiring input")
            frozen = datetime.now(UTC) + timedelta(hours=9)
            monkeypatch.setattr(identity, "now", lambda: frozen)
            page.get_by_role("button", name="Send message").click()
            expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
            expect(page.get_by_role("log")).to_have_count(0)
            expect(page.get_by_label("Message", exact=True)).to_have_count(0)
            assert page.evaluate("sessionStorage.length") == 0
        finally:
            browser.close()


def test_logout_inflight_rejects_late_result_without_restoring_ui(
    frontend: tuple[str, ssl.SSLContext],
    scripted_http: ProviderHTTP,
) -> None:
    origin, _ = frontend
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(origin)
            page.get_by_label("Email").fill(EMAIL)
            page.get_by_label("Password", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.get_by_label("I accept the storage disclosure").check()
            page.get_by_role("button", name="Create saved chat").click()
            scripted_http.release.clear()
            page.get_by_label("Message", exact=True).fill("Synthetic delayed input")
            page.get_by_role("button", name="Send message").click()
            assert scripted_http.entered.wait(15)
            page.get_by_role("button", name="Sign out", exact=True).click()
            expect(page.get_by_role("status")).to_have_text("You are signed out.")
            with page.expect_response(
                lambda response: response.url.endswith("/turns")
            ) as completed:
                scripted_http.release.set()
            assert completed.value.status == 401
            expect(page.get_by_role("status")).to_have_text("You are signed out.")
            expect(page.get_by_role("log")).to_have_count(0)
            expect(page.get_by_label("Message", exact=True)).to_have_count(0)
        finally:
            scripted_http.release.set()
            browser.close()


@pytest.mark.parametrize("condition", ["unknown", "expired", "foreign"])
def test_browser_resume_pointer_never_grants_access(
    frontend: tuple[str, ssl.SSLContext],
    condition: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin, context = frontend
    with httpx.Client(base_url=origin, verify=context, trust_env=False) as client:
        headers = api_login(client, origin)
        created = client.post(
            "/api/conversations",
            json={"disclosure_version": "history-v1"},
            headers=headers,
        ).json()
    identifier = str(uuid4()) if condition == "unknown" else created["id"]
    email = EMAIL
    if condition == "expired":
        frozen = datetime.now(UTC) + timedelta(days=31)
        monkeypatch.setattr(conversations, "now", lambda: frozen)
    if condition == "foreign":
        email = "patient.two@careflow.example.invalid"
        provision(email, PASSWORD, confirmed=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(origin)
            page.evaluate(
                "id => localStorage.setItem('careflow.conversation', id)", identifier
            )
            page.reload()
            expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
            expect(page.get_by_role("log")).to_have_count(0)
            page.get_by_label("Email").fill(email)
            page.get_by_label("Password", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(
                page.get_by_role("heading", name="Before you save a chat")
            ).to_be_visible()
            assert (
                page.evaluate("localStorage.getItem('careflow.conversation')") is None
            )
        finally:
            browser.close()


@pytest.mark.parametrize("frontend", ["untrusted"], indirect=True)
def test_proxy_rejects_untrusted_backend_certificate(
    frontend: tuple[str, ssl.SSLContext],
) -> None:
    origin, context = frontend
    with httpx.Client(base_url=origin, verify=context, trust_env=False) as client:
        result = client.get("/api/auth/me")
        assert result.status_code == 502
        assert result.json()["code"] == "API_UNAVAILABLE"
        assert result.headers["cache-control"] == "no-store"


def test_expiry_at_csrf_bootstrap_cannot_downgrade_patient_ui_to_guest(
    frontend: tuple[str, ssl.SSLContext],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin, context = frontend
    with httpx.Client(base_url=origin, verify=context, trust_env=False) as client:
        api_login(client, origin)
        token = client.cookies.get("__Host-careflow_session")
        assert token is not None
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            browser_context = browser.new_context()
            browser_context.add_cookies(
                [
                    {
                        "name": "__Host-careflow_session",
                        "value": token,
                        "domain": "localhost",
                        "path": "/",
                        "secure": True,
                        "httpOnly": True,
                        "sameSite": "Strict",
                    }
                ]
            )
            page = browser_context.new_page()

            def expire_before_bootstrap(route: BrowserRoute) -> None:
                # Delay only transport. The real request/session service runs;
                # clock control stays in this test process, never an API hook.
                frozen = datetime.now(UTC) + timedelta(hours=9)
                monkeypatch.setattr(identity, "now", lambda: frozen)
                route.continue_()

            page.route("**/api/auth/csrf", expire_before_bootstrap)
            page.goto(origin)
            expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
            expect(
                page.get_by_role("heading", name="Before you save a chat")
            ).to_have_count(0)
            expect(page.get_by_label("Message", exact=True)).to_have_count(0)
        finally:
            browser.close()


def test_changed_authenticated_patient_clears_previous_patient_transcript(
    frontend: tuple[str, ssl.SSLContext],
) -> None:
    origin, context = frontend
    other = "patient.two@careflow.example.invalid"
    provision(other, PASSWORD, confirmed=True)
    with httpx.Client(base_url=origin, verify=context, trust_env=False) as client:
        api_login(client, origin, other)
        other_token = client.cookies.get("__Host-careflow_session")
        assert other_token is not None
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            browser_context = browser.new_context()
            page = browser_context.new_page()
            page.goto(origin)
            page.get_by_label("Email").fill(EMAIL)
            page.get_by_label("Password", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.get_by_label("I accept the storage disclosure").check()
            page.get_by_role("button", name="Create saved chat").click()
            page.get_by_label("Message", exact=True).fill("Synthetic patient A history")
            page.get_by_role("button", name="Send message").click()
            expect(
                page.get_by_role("log").get_by_text(
                    "Synthetic patient A history", exact=True
                )
            ).to_be_visible()
            # A second real login supplies B's cookie, just as another tab can
            # replace the shared cookie jar. No sessions/ownership are mocked.
            browser_context.add_cookies(
                [
                    {
                        "name": "__Host-careflow_session",
                        "value": other_token,
                        "domain": "localhost",
                        "path": "/",
                        "secure": True,
                        "httpOnly": True,
                        "sameSite": "Strict",
                    }
                ]
            )
            page.evaluate("window.dispatchEvent(new Event('focus'))")
            expect(page.get_by_role("log")).to_have_count(0)
            expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
            expect(page.get_by_label("Message", exact=True)).to_have_count(0)
        finally:
            browser.close()


def test_browser_turn_persists_resumes_and_logout_clears_private_state(
    frontend: tuple[str, ssl.SSLContext],
) -> None:
    origin, _ = frontend
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(origin)
            page.get_by_label("Email").fill(EMAIL)
            page.get_by_label("Password", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.get_by_label("I accept the storage disclosure").check()
            page.get_by_role("button", name="Create saved chat").click()
            page.get_by_label("Message", exact=True).fill("Synthetic saved message")
            page.get_by_role("button", name="Send message").click()
            expect(
                page.get_by_text("Synthetic saved message", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_text(
                    "This chat has no verified clinic-policy source.", exact=False
                )
            ).to_be_visible()
            page.reload()
            expect(
                page.get_by_text("Synthetic saved message", exact=True)
            ).to_be_visible()
            assert page.evaluate("Object.keys(localStorage)") == [
                "careflow.conversation"
            ]
            assert (
                page.evaluate("localStorage.getItem('careflow.conversation')").count(
                    "-"
                )
                == 4
            )
            assert page.evaluate("sessionStorage.length") == 0
            page.get_by_role("button", name="Sign out", exact=True).click()
            expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
            expect(
                page.get_by_text("Synthetic saved message", exact=True)
            ).to_have_count(0)
            page.reload()
            expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
            expect(page.get_by_label("Message", exact=True)).to_have_count(0)
        finally:
            browser.close()


def test_browser_reports_invalid_credentials_without_claiming_session_expiry(
    frontend: tuple[str, ssl.SSLContext],
) -> None:
    origin, _ = frontend
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(origin)
            page.get_by_label("Email").fill(EMAIL)
            page.get_by_label("Password", exact=True).fill("Wrong-Synthetic-Password!")
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.get_by_role("status")).to_have_text(
                "Email or password was not accepted."
            )
            expect(page.get_by_label("Message", exact=True)).to_have_count(0)
        finally:
            browser.close()


def test_unavailable_turn_can_retry_the_original_uuid_without_duplicate_history(
    frontend: tuple[str, ssl.SSLContext],
    scripted_http: ProviderHTTP,
) -> None:
    origin, _ = frontend
    scripted_http.unavailable = True
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            turns: list[str] = []

            def capture_turn(request: BrowserRequest) -> None:
                if request.url.endswith("/turns"):
                    body = request.post_data_json
                    assert isinstance(body, dict)
                    turns.append(body["turn_id"])

            page.on("request", capture_turn)
            page.goto(origin)
            page.get_by_label("Email").fill(EMAIL)
            page.get_by_label("Password", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.get_by_label("I accept the storage disclosure").check()
            page.get_by_role("button", name="Create saved chat").click()
            page.get_by_label("Message", exact=True).fill("Synthetic retry message")
            page.get_by_role("button", name="Send message").click()
            expect(page.get_by_role("status")).to_have_text(
                "Chat is unavailable. Retry your message "
                "or reload to check saved history."
            )
            scripted_http.unavailable = False
            page.get_by_role("button", name="Retry message").click()
            expect(
                page.get_by_role("log").get_by_text(
                    "Synthetic retry message", exact=True
                )
            ).to_be_visible()
            page.reload()
            expect(
                page.get_by_role("log").get_by_text(
                    "Synthetic retry message", exact=True
                )
            ).to_have_count(1)
            assert len(turns) == 2 and turns[0] == turns[1]
        finally:
            browser.close()


def test_deleted_open_conversation_clears_transcript_and_offers_new_consent(
    frontend: tuple[str, ssl.SSLContext],
) -> None:
    origin, _ = frontend
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(origin)
            page.get_by_label("Email").fill(EMAIL)
            page.get_by_label("Password", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.get_by_label("I accept the storage disclosure").check()
            page.get_by_role("button", name="Create saved chat").click()
            expect(page.get_by_label("Message", exact=True)).to_be_visible()
            assert (
                page.evaluate("""async () => {
                const token = await (await fetch('/api/auth/csrf')).json();
                const id = localStorage.getItem('careflow.conversation');
                return (await fetch('/api/conversations/' + id, {
                    method: 'DELETE', headers: {'X-CSRF-Token': token.csrf_token}
                })).status;
            }""")
                == 204
            )
            page.get_by_label("Message", exact=True).fill("Synthetic deleted chat")
            page.get_by_role("button", name="Send message").click()
            expect(
                page.get_by_role("heading", name="Before you save a chat")
            ).to_be_visible()
            expect(page.get_by_role("log")).to_have_count(0)
            expect(
                page.get_by_role("button", name="Create saved chat")
            ).to_be_disabled()
            assert (
                page.evaluate("localStorage.getItem('careflow.conversation')") is None
            )
        finally:
            browser.close()
