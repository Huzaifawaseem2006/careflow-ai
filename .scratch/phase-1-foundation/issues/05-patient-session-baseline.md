# 05: Sign in and end a synthetic patient session

**What to build:** A synthetic patient can sign in, inspect their own server-resolved identity, and sign out. Private requests without a valid session fail safely; staff accounts cannot self-register.

**Blocked by:** 04 — Reset the fictional clinic fixtures.

**Status:** resolved

**Approval gate:** Owner approved Ticket 05, D02 and test boundaries on 2026-10-16. Ticket 04 was committed/pushed separately as `7d80ab6`; implementation starts from its clean checkout. No Ticket 05 commit/push or Ticket 06 implementation is authorized.

- [x] Session cookies use the approved secure, HttpOnly server-managed design and appropriate CSRF protection.
- [x] Identity comes from server session state, never a caller-supplied patient or role field.
- [x] HTTP tests cover sign-in, sign-out, missing/invalid session, CSRF rejection, and staff-registration denial.
- [x] The chosen credential lifecycle and any demo-only limitation are documented before implementation.

## Approved implementation boundary — 2026-10-16

Pre-provisioned synthetic patients with local Argon2id password hashes; operator-only creation/reset; no public registration/email recovery. Keep Ticket 04 personas separate until explicitly provisioned. Backend-resolved identity, server-managed secure sessions, CSRF protection, logout/reset invalidation. Test through HTTP against disposable PostgreSQL and the account-management CLI, including failure, isolation, concurrency and retry cases. D02 and the intended lifecycle are recorded in `docs/DECISIONS.md` before implementation.

## Incomplete implementation checkpoint — 2026-10-16

Started from clean `master` at `7d80ab6`. Applied implement/TDD guidance at the approved HTTP/CLI boundaries. Two observed red/green cycles now pass: missing-session `GET /auth/me` returns 401/no-store; cross-origin `POST /auth/login` returns 403 before database access. These are rejection-only initial slices; working account creation, login, session persistence, logout and reset are **not implemented**. The positive CLI-provisioning/HTTP-login integration test is written but has not run against PostgreSQL.

Pinned/installed `argon2-cffi==25.1.0`; documented D02 before credential code. Focused types and dependency check passed; final focused format/lint results are in progress. No schema migration or authenticated accounts exist yet. TEST_DATABASE_URL is unset. Awaiting the owner's local secure password prompt using ignored `test-results/configure-ticket05-database.ps1`, which writes only Windows-encrypted temporary storage; the accompanying ignored runner sets the test URL only in its child process. No credential file was present at this checkpoint. Resume strict real-PostgreSQL red/green cycles after the owner replies ready; no skipped/live tests are claimed as passing. Keep this ticket open and do not deploy the partial boundary.

## Verified completion — 2026-10-16

Owner supplied the Windows-encrypted local PostgreSQL test credential and explicitly authorized continuation only against disposable databases. Implemented migration `0003_patient_sessions`, separate account/patient records, Argon2id password hashing, operator creation/reset CLI, opaque hashed session tokens, pre-login CSRF, secure cookies, login rotation, backend identity, logout/replay handling, absolute expiry, persisted request limits and bounded/sanitized transport validation. Fixture personas remain separate until explicit provisioning. No public registration/recovery or staff login is exposed.

Strict red/green cycles observed for provisioning/login, logout, password reset, persistent login limiting, oversized requests, CLI noninteractive handling, malformed origin and HTTPS enforcement. The completion review caught a malformed non-ASCII CSRF exception and missing restricted-role coverage. Strengthened the HTTP transport to preserve raw header bytes, reproduced the exception red and fixed it; added a real restricted-role HTTP/CLI test. Both standards/spec follow-ups report no outstanding findings.

Final command, through the temporary child-process credential runner and a fresh ignored basetemp: `python -m pytest backend/tests backend/integration_tests ci_tests -q -rs --basetemp <fresh test-results directory> --junitxml test-results/ticket05-tests.xml`: **52 passed in 219.13s**, **0 failures/errors/skips**, independently confirmed in JUnit (30 offline/unit, 20 real PostgreSQL including 13 identity cases, 2 serial CI regressions). Covers login failures, logout, CSRF (including raw malformed headers), patient isolation, reset/all-session invalidation, expiry, concurrent login/reset, retries, provisioning restrictions and minimum database grants. HTTP uses in-process ASGI transports backed by real PostgreSQL, not a deployed TLS server.

`ruff format --check backend scripts ci_tests`, `ruff check backend scripts ci_tests`, `mypy backend scripts ci_tests` (26 files), `pip check`, and final `git diff --check` passed. The first full run had 50 passes/one CI failure because a newly added review regression was not yet formatted; fixed and reran the complete settled-code suite above. Existing Starlette HTTPX deprecation is non-failing. No model evaluation applies; no hosted run or Phase 1 gate is claimed.

Post-verification read-only maintenance check: PostgreSQL 17.11, zero remaining careflow_test databases and zero temporary careflow_auth roles. No query/migration/fixture/reset targeted the main careflow_ai database. Deleted and verified absent the DPAPI credential file plus both temporary PowerShell helpers. Remaining reports are ignored and contain no database credentials. All acceptance criteria are verified; no blocker remains. README/API/architecture/decisions/phase/progress record the final contract and demo limitations. No Ticket 05 commit/push or Ticket 06 work occurred.
