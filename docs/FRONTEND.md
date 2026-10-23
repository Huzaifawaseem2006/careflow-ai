# Ticket 01 patient interface

This is a local, synthetic-data, development-only interface over the existing
Phase 3 backend. It provides sign-in, disclosure acceptance, one saved v1 chat,
session recovery and logout. Appointment navigation is a placeholder. RAG,
citations, booking confirmation and provider-term verification are later tickets.

## Local HTTPS setup

Use Node 22 and the project's Python 3.13 environment. Install with
`npm ci --prefix frontend` and `.venv\Scripts\python -m pip install -e '.[dev]'`.
The lockfile pins frontend dependencies. Next telemetry can be disabled with
`$env:NEXT_TELEMETRY_DISABLED = '1'` before building or starting the frontend.

Both browser-to-frontend and frontend-to-backend connections use verified HTTPS.
Use an existing trusted localhost certificate and its matching key, in a private
directory outside Git. The current Windows account already has a localhost
certificate in both its personal and trusted-root stores. Its private key must
be exportable to serve TLS. Check validity when repeating setup; do not assume
the certificate remains valid indefinitely.

PowerShell 7 can export this **existing** certificate without changing either
store. First prepare an owner-only private directory, for example beneath
`%USERPROFILE%\.careflow-ai\tls`, then run:

```powershell
pwsh -NoProfile -File scripts/export-localhost-tls.ps1 -OutputDirectory "$env:USERPROFILE\.careflow-ai\tls"
```

The helper chooses an unexpired current-user personal certificate for localhost
whose thumbprint is also in current-user trusted roots. It writes `localhost.pem`
and `localhost.key`; it never installs a certificate. Keep the output private and
do not sync it. If no suitable certificate exists, stop and arrange explicit
approval for local certificate provisioning/trust installation. Never use a TLS
verification bypass. New trust-store changes were not needed for this ticket.

In the backend terminal, configure the existing synthetic database and provisioned
patient account using [the backend instructions](../README.md). Then:

```powershell
$env:AUTH_ORIGIN = 'https://localhost:3000'
$env:CHAT_ENABLED = 'false'
.venv\Scripts\python -m uvicorn careflow.main:app --host 127.0.0.1 --port 8000 --ssl-certfile "$env:USERPROFILE\.careflow-ai\tls\localhost.pem" --ssl-keyfile "$env:USERPROFILE\.careflow-ai\tls\localhost.key" --no-access-log
```

In a separate frontend terminal:

```powershell
$env:NEXT_TELEMETRY_DISABLED = '1'
$env:CAREFLOW_TLS_CERT = "$env:USERPROFILE\.careflow-ai\tls\localhost.pem"
$env:CAREFLOW_TLS_KEY = "$env:USERPROFILE\.careflow-ai\tls\localhost.key"
$env:CAREFLOW_BACKEND_CA = $env:CAREFLOW_TLS_CERT
$env:CAREFLOW_BACKEND_ORIGIN = 'https://localhost:8000'
$env:PORT = '3000'
npm.cmd run build --prefix frontend
npm.cmd run start --prefix frontend
```

Open `https://localhost:3000` (not the numeric IP, which may not match the
certificate). `npm run dev --prefix frontend` serves the same TLS/proxy path with
Next development mode. Do not start Next directly: `server.mjs` owns HTTPS and
the restricted API proxy. Binding is loopback only. The Node HTTPS agent trusts
the configured backend CA and verifies the hostname; no redirects or arbitrary
upstream URLs are accepted. API method/path forwarding is limited to existing
auth, disclosure and conversation routes. Original Origin, CSRF and fetch metadata
reach FastAPI; cookies are relayed without rewriting. Client authority and
forwarded-IP headers are not accepted. The backend sees the loopback peer, so
local clients share its existing IP limits; this is not a public deployment.

Chat is disabled unless separately authorized and enabled in the backend.
Without a provider, real sign-in/history still work and new turns show an
unavailable state. Neither key possession nor this setup authorizes an AI call.
There is no scripted production chat mode.

## Browser state and recovery

Only `careflow.conversation`, a conversation UUID, is written to localStorage.
It is a resume pointer, never authorization. The interface checks `/auth/me`
before requesting history; the backend independently checks current ownership.
Missing/deleted/expired/inaccessible pointers are cleared and the interface offers
new disclosure acceptance. Logging out retains this pointer so the same patient
can sign in and resume; another patient receives no history from it.

CSRF, input text, response text and retry UUIDs stay in page memory. The session
cookie remains Secure, HttpOnly and SameSite=Strict. Logout/session rejection
clears protected UI state and invalidates pending UI response generations.
CSRF bootstrap precedes the final current-patient check, so a replacement guest
cookie cannot retain an earlier patient identity. Session validity and user/patient
identity are also checked on focus, visibility restoration and every 30 seconds
while authenticated. A changed account clears the previous patient's UI state.
A failed logout is reported as unconfirmed and offers an explicit retry.
No service worker, transcript cache or appointment
confirmation control is installed. A static shell contains no private data.

## Verification

```powershell
npm.cmd run typecheck --prefix frontend
npm.cmd run lint --prefix frontend
npm.cmd run build --prefix frontend
powershell.exe -NoProfile -File scripts/postgres-tests.ps1 test -TestPath backend/integration_tests/test_frontend_integration.py
```

The browser tests require Playwright Chromium; install it with
`.venv\Scripts\python -m playwright install chromium` when absent. They export
the existing trusted certificate into the runner's private temporary directory,
start real HTTPS servers and use standard disposable PostgreSQL fixtures. Exported
test private-key copies are removed after server teardown. The Windows trust setup
is required for this browser harness; Linux static typing was checked separately.
Tests do not change certificate stores or the demo database. No browser TLS errors are
ignored. Only the external Anthropic HTTP transport is scripted, through the real
pinned SDK and provider adapter. This measures mechanical integration, not hosted
model quality. Test-clock controls, when used, exist only in the test process.

Follow [PostgreSQL runner recovery and timing rules](POSTGRES_TESTING.md). Database
and CI subprocess regressions run serially in an idle checkout. Browser captures
must omit credentials, cookies, CSRF and action proofs; traces/HAR recording are
not enabled. Evidence belongs under ignored `test-results/`.

The initial audit reported five high development-only findings in the Next ESLint
configuration's `fast-glob` / `micromatch` / `braces` chain. The upstream
[advisory was withdrawn on 2026-10-23](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).
Final production-only and explicitly development-inclusive audits both report zero
findings, without dependency changes or an automatic downgrade. See the exact
reports and execution results in [the progress ledger](PROGRESS.md).
