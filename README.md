# CareFlow AI

Synthetic-data clinic front-desk assistant. Phase 1 includes process liveness, PostgreSQL migrations/readiness, synthetic fixtures, patient sessions and offline evaluation infrastructure. Clinic workflows, AI behavior and frontend remain future phases.

Follow [AGENTS.md](AGENTS.md) for development workflow and scoped context loading. Project references: [PRD.md](PRD.md), [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md), [progress](docs/PROGRESS.md), [safety](docs/SAFETY.md), [contracts](docs/API_CONTRACTS.md) and [evaluation strategy](docs/EVAL_STRATEGY.md). Phase 1 tickets 01–06 are complete; see progress for Ticket 07 gate evidence.

The phase plans under `plans/` follow PRD phases 0–7. See progress for actual verification evidence.

For the approved health slice, use Python 3.13.13 from `.python-version`:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e '.[dev]'
.venv\Scripts\python -m uvicorn careflow.main:app --host 127.0.0.1 --port 8000
```

`GET http://127.0.0.1:8000/health` returns `{"status":"ok"}` with HTTP 200. It reports process liveness only; it does not check the database. Run checks from the repository root:

```powershell
.venv\Scripts\python -m ruff format --check backend scripts ci_tests
.venv\Scripts\python -m ruff check backend scripts ci_tests
.venv\Scripts\python -m mypy backend scripts ci_tests
.venv\Scripts\python -m pytest backend/tests -q
```

Ticket 02 adds [GitHub Actions](.github/workflows/foundation.yml) on pushes, pull requests and manual runs. After installing `.[dev]`, run the same verification locally:

```powershell
.venv\Scripts\python -m pytest ci_tests -q
.venv\Scripts\python scripts/check_foundation.py
```

The entry point runs the four checks above, returns nonzero if any fail, and writes `test-results/foundation.json` with the checked-out Git revision, working-tree dirty flag, overall result and each check's exit code. It also prints the report; GitHub Actions copies it to the job summary even when checks fail. Run from a Git checkout at the repository root. An uncommitted local result is identified by `dirty: true`, not proof of a clean committed revision.

The subprocess regression suite runs separately to avoid recursive pytest execution. It invokes the real checks, briefly creates an unused-import probe under `backend/`, and removes it in `finally`. Run this suite serially in an otherwise idle checkout. Each test writes its report to pytest's temporary directory. No model calls or credentials are needed. The private GitHub remote is connected; [baseline hosted run #1 passed](https://github.com/Huzaifawaseem2006/careflow-ai/actions/runs/38693825109), and [isolated failure-proof run #2 failed as intended](https://github.com/Huzaifawaseem2006/careflow-ai/actions/runs/38694227925). Ticket 02 is resolved; its ticket records both commit SHAs and verification details. The failure-proof branch must not be merged into `master`.

## Local PostgreSQL setup (Ticket 03)

The current MVP runs natively. Docker/Compose is deferred and is not required. Python dependencies are pinned to SQLAlchemy 2.0.54, Alembic 1.20.0 and Psycopg/binary 3.3.6; install using the existing `pip install -e '.[dev]'` command. PostgreSQL 17.11 and pgvector 0.8.7 are installed and verified through authenticated SQL, migrations, vector operations and real-database HTTP readiness tests. The existing `careflow_ai` database is at revision `0001_vector`. PostgreSQL 18 is not required. Installation steps below are for fresh machines; do not reinstall on this machine.

1. Keep the existing PostgreSQL 17.11 installation; no reinstall or major-version upgrade is needed. For a fresh machine, use the [official Windows download page](https://www.postgresql.org/download/windows/). Include server/command-line tools and keep the administrator password private. Examples assume `C:\Program Files\PostgreSQL\17` and port 5432.
2. Build pgvector from its official pinned source against this installation, following the [official Windows instructions](https://github.com/pgvector/pgvector#windows). Visual Studio 2022 Community with the C++ tools component is already detected here; PostgreSQL's `include\server\postgres.h` and `lib\postgres.lib` also exist. On a fresh machine, install the **Desktop development with C++** workload and Windows SDK using [Microsoft's instructions](https://learn.microsoft.com/en-us/cpp/build/building-on-the-command-line). Open **x64 Native Tools Command Prompt for VS 2022** as administrator (not ordinary PowerShell). Using a fresh source directory, run:

```bat
set "PGROOT=C:\Program Files\PostgreSQL\17"
cd %TEMP%
git clone --branch v0.8.7 --depth 1 https://github.com/pgvector/pgvector.git careflow-pgvector-0.8.7-pg17
cd careflow-pgvector-0.8.7-pg17
nmake /F Makefile.win
nmake /F Makefile.win install
```

Stop if a command fails. If the source directory already exists, choose another fresh directory to avoid reusing build objects from another PostgreSQL version. `PGROOT` selects the installed PostgreSQL 17 headers/libraries and destination; do not copy a PostgreSQL 18 DLL into this server. The install target copies `vector.dll` to `17\lib` and `vector.control`/versioned SQL files to `17\share\extension`.

These are owner-run installation instructions; the agent has not installed system software. Zero rows from `pg_available_extensions` means pgvector's installation files are unavailable to the queried server; SQL alone cannot install missing files. Installing the files makes the extension available; Alembic enables it per database. Re-run the query in pgAdmin against the same server, or in PowerShell (password is prompted):

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\psql.exe' --version
& 'C:\Program Files\PostgreSQL\17\bin\psql.exe' -h 127.0.0.1 -U postgres -d postgres -W -c "SELECT name, default_version FROM pg_available_extensions WHERE name = 'vector';"
& 'C:\Program Files\PostgreSQL\17\bin\createdb.exe' -h 127.0.0.1 -U postgres -W careflow_ai
```

The extension query must return a row. The owner has already created `careflow_ai`; skip the `createdb` command on this machine. On a fresh setup, create it once; do not recreate/reset an existing database. No domain tables or fixtures are added by Ticket 03.

If availability still returns zero rows after a successful install, verify pgAdmin's host/port and `SELECT version();`, and compare the installation's `pg_config.exe --sharedir` with the directory containing `vector.control`. Multiple PostgreSQL installations can use different extension directories. Keep the migration's extension requirement intact; do not stamp Alembic head or bypass extension creation.

From the repository root, set the migration connection in the process environment, prompting for the password without putting it in shell history:

```powershell
$taskDatabasePassword = [uri]::EscapeDataString((Get-Credential -UserName postgres -Message 'Local migration administrator').GetNetworkCredential().Password)
$env:DATABASE_URL = "postgresql+psycopg://postgres:${taskDatabasePassword}@127.0.0.1:5432/careflow_ai"
Remove-Variable taskDatabasePassword
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic current
```

Expected revision after Phase 2 Ticket 04: `0007_management`. An older database needs the explicit upgrade above; `/ready` returns 503 until upgraded. Migrations require permission to install vector and PostgreSQL's bundled btree_gist extension. Do not run the API with that administrator role. In an interactive `psql -h 127.0.0.1 -U postgres -d careflow_ai -W` session, create the development application role once and enter its password at the prompt:

```sql
CREATE ROLE careflow_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
\password careflow_app
GRANT CONNECT ON DATABASE careflow_ai TO careflow_app;
GRANT USAGE ON SCHEMA public TO careflow_app;
GRANT SELECT ON TABLE public.alembic_version TO careflow_app;
```

Set `DATABASE_URL` for the API using the same password-prompt pattern with `careflow_app` as the username. Future domain tickets must add only their required application permissions. `.env.example` documents the variables, but `.env` is **not auto-loaded**. Use `postgresql+psycopg` URLs, percent-encode special characters in usernames/passwords, and omit URL query parameters; the application sets connect and statement timeouts. Never print the environment URL or commit credentials.

```powershell
.venv\Scripts\python -m uvicorn careflow.main:app --host 127.0.0.1 --port 8000
```

`GET /ready` returns HTTP 200 / `{"status":"ok"}` when connectivity, migration head and vector installation checks succeed; otherwise HTTP 503 / `{"status":"unavailable"}`. It never migrates or returns database details. `GET /health` stays HTTP 200 even when the database is unavailable. For SQL review without a server, run `.venv\Scripts\python -m alembic upgrade head --sql`; this does **not** prove a live migration succeeded.

## Real database verification

Use the reusable [Windows credential workflow](docs/POSTGRES_TESTING.md). One-time
setup saves an account-bound DPAPI credential outside Git at
`%USERPROFILE%\.careflow-ai\credential.clixml`; subsequent sessions reuse it
without prompting. Run from the checkout root:

```powershell
powershell.exe -NoProfile -File .\scripts\postgres-tests.ps1 setup
powershell.exe -NoProfile -File .\scripts\postgres-tests.ps1 validate
powershell.exe -NoProfile -File .\scripts\postgres-tests.ps1 test
```

Use `rotate` to save an updated password or `delete` to remove the saved copy.
Only setup/rotation prompt, using `Read-Host -AsSecureString`. Leave the encrypted
credential in place between sessions. The runner supplies a fixed local `postgres`
maintenance URL only to child processes; no parent environment export is needed.
The existing fixtures create/drop only `careflow_test_<random UUID>` databases;
`careflow_ai` is never a test target. Use synthetic data only. Missing/invalid
credentials fail safely; skipped tests do not satisfy database acceptance.

Before pgvector installation, select the PostgreSQL-only check:

```powershell
powershell.exe -NoProfile -File .\scripts\postgres-tests.ps1 test -TestPath backend/integration_tests/test_database_integration.py::test_unmigrated_database_is_not_ready_but_process_is_alive
```

It confirms SQL connectivity to a fresh database, no migration version table, `/ready` HTTP 503 and `/health` HTTP 200. It does not enable or require pgvector. The complete four-test suite must still pass after extension installation. Credentials must be configured locally; a pgAdmin connection does not configure the API/test process, and no password should be pasted into chat.

Run `.venv\Scripts\python scripts/check_foundation.py` and `.venv\Scripts\python -m pytest ci_tests -q` serially for local foundation verification. Hosted CI currently runs those checks and the offline/unit suite only; it does not claim live database coverage. Ticket 03 closeout passed 15 local tests (9 offline/unit, 4 real PostgreSQL, 2 CI regressions), with no skips. Fresh/repeat migration, vector distance, successful/unmigrated/missing-extension/stale-revision readiness and database-independent liveness are verified. Evidence and remaining phase work are recorded in progress.

If the restricted Windows execution environment blocks pytest temporary directories
with WinError 5, run the credential runner from an ordinary local PowerShell
session. It creates a fresh ignored test-temporary directory on every run. Keep
the separate CI regression suite serial in an otherwise idle checkout.

## Synthetic clinic fixtures (Ticket 04)

The built-in fixture manifest contains one **CareFlow Fictional Demo Clinic** in Karachi (`Asia/Karachi`, PKR) and four explicitly synthetic personas: two patients, one receptionist and one admin. IDs are fixed UUIDs and emails use `careflow.example.invalid`. These are credential-free records in `demo_identities`, not login accounts or granted permissions. D02 and actual authentication remain for Ticket 05. No doctors, appointment slots, clinical facts or policy corpus are seeded here.

Use an operator connection in `DATABASE_URL` pointing to the local synthetic demo database, then explicitly migrate and confirm fixture writes:

```powershell
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m careflow.fixtures load --confirm-synthetic-fixtures
# Restore the known fixture records after demo edits:
.venv\Scripts\python -m careflow.fixtures reset --confirm-synthetic-fixtures
```

`load` inserts missing fixture IDs and preserves existing rows. `reset` inserts missing fixture IDs and restores their manifest fields. Both are repeatable, atomic and serialized against other fixture writers. Reset never deletes/truncates tables, resets the database or removes unrelated rows. A uniqueness conflict rolls the entire operation back. This is a fixture reset, not an appointment/history reset.

Both commands require the confirmation flag, current migration head, a loopback host (`localhost`, `127.0.0.1`, `::1`) and database name `careflow_ai`, `careflow_demo`, or the integration suite's exact `careflow_test_<32 lowercase hex>` pattern. URLs with query parameters are refused. The operator is responsible for using a synthetic-only local database. No HTTP/LLM fixture tool exists, and the API role needs no fixture-write grants. Commands print only generic success/failure, never connection URLs, identity details or credentials. Downgrading the new migration drops its two tables and requires separate explicit approval on any existing database.

For Ticket 04 live verification with a locally configured maintenance `TEST_DATABASE_URL`:

```powershell
.venv\Scripts\python -m pytest backend/integration_tests -v -s -rs --junitxml test-results/ticket04-postgres.xml
```

These tests only create/migrate/reset/drop their disposable databases. The existing `careflow_ai` database is not touched. Ticket 04 verification on 2026-10-16 passed 22 offline/unit tests, 2 CI regressions and 7 owner-run PostgreSQL integration tests across separate runs. The saved PostgreSQL JUnit report confirms zero failures, errors or skips. Details are tracked in the ticket and progress log; skipped tests are not passing PostgreSQL evidence.

## Synthetic patient accounts and sessions (Ticket 05)

D02 uses pre-provisioned synthetic patients. There is no public registration, staff account creation or email recovery. The fixture personas are separate from authenticated accounts: an operator must explicitly provision each patient. Passwords are 12–128 characters and stored using pinned argon2-cffi 25.1.0 (Argon2id, random salts). Duplicate creation fails without changing an existing password. Operator reset preserves identity and atomically revokes all owned sessions. Neither fixture load nor fixture reset creates accounts or changes passwords.

For a deliberately selected local synthetic demo database, configure an operator `DATABASE_URL`, migrate and load fixtures, then use these commands. Each prompts twice without echo; never put a password in command arguments, a URL, a script or Git:

```powershell
.venv\Scripts\python -m careflow.accounts create --email patient.one@careflow.example.invalid --confirm-synthetic-account
.venv\Scripts\python -m careflow.accounts reset-password --email patient.one@careflow.example.invalid --confirm-synthetic-account
```

The same local target allowlist as the fixture CLI applies. `--password-stdin` explicitly accepts one password line from a secure pipe for automation/tests; a noninteractive terminal without that flag fails. Use trusted secret input, not a literal password in shell history. CLI success/failure omits identity details, hashes and credentials. Reset/creation require operator permissions; there is no HTTP or AI account-management endpoint.

Use the separate application role for the API. After the migration, an operator grants only:

```sql
GRANT SELECT ON public.users, public.patients TO careflow_app;
GRANT UPDATE (password_hash) ON public.users TO careflow_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.sessions, public.auth_limits TO careflow_app;
```

Retain the earlier readiness grants. The API role cannot insert accounts/patient mappings or change account activity/email through these grants. No new role or grants were applied to the existing database by Ticket 05 verification.

Set `AUTH_ORIGIN` to the exact HTTPS browser origin, without a trailing slash/path (default `https://localhost:8000`). Authentication requires HTTPS even locally; Secure cookies are never disabled. Run Uvicorn with your locally trusted TLS certificate/key, or use an explicitly trusted same-origin TLS proxy. Plain HTTP still serves health/readiness but is rejected by auth routes. Do not commit certificate private keys. TLS/proxy deployment is not implemented by this ticket.

Browser flow: GET `/auth/csrf`, retaining its HttpOnly cookie and returned CSRF token; POST `/auth/login` with JSON email/password plus matching Origin and X-CSRF-Token. Login replaces both tokens. GET `/auth/me` resolves identity from the stored session; POST `/auth/logout` with matching Origin/CSRF revokes it and clears the cookie. Save the new CSRF value after login; do not put session/CSRF tokens in logs or URLs. Authenticated sessions last eight hours absolutely; pre-login sessions last ten minutes. Reading CSRF does not extend the deadline. All auth responses are no-store. See `docs/API_CONTRACTS.md` for limits, error codes and retry behavior.

Run real identity verification with a local maintenance TEST_DATABASE_URL with CREATEDB, CREATEROLE and pgvector-install privileges. Tests create/drop only disposable databases plus a uniquely named temporary login role for the least-privilege check; grants are confined to its disposable database and the role is removed in `finally`. They do not target/reset `careflow_ai`:

```powershell
.venv\Scripts\python -m pytest backend/integration_tests/test_identity_integration.py -q
.venv\Scripts\python -m pytest backend/tests backend/integration_tests ci_tests -q -rs --junitxml test-results/ticket05-tests.xml
```

Run the CI suite serially and use ordinary Windows permissions/fresh test temporary directories if the documented sandbox restriction recurs. No configured URL means PostgreSQL tests explicitly skip; skips cannot close Ticket 05. The account lifecycle is demo-only; real users, production recovery, staff authentication, deployment and broader release controls are not established here.

Ticket 05 verification on 2026-10-16: 52 local tests passed with no failures/errors/skips (30 offline/unit, 20 real PostgreSQL, 2 CI regressions); format/lint/types/dependencies passed. Standards/spec review findings are closed. Temporary database/role cleanup and encrypted credential-helper deletion were verified. This does not claim a deployed HTTPS service, hosted CI run, or completed Phase 1 gate. Detailed commands/results are in the ticket and progress log.

## Offline evaluation infrastructure (Ticket 06)

From the checkout root, with the existing dev environment:

```powershell
.venv\Scripts\python -m evals.run_local
.venv\Scripts\python -m evals.run_local --partition held-out --report evals/results/held-out.json
.venv\Scripts\python -m evals.run_local --partition all --report evals/results/inventory.json
.venv\Scripts\python -m pytest evals/tests -q
```

The default report is ignored at `evals/results/offline.json`; default partition is `dev`. Reports include Git revision/dirty state, dataset version/hash, fixture version and explicit offline labeling. All seven seeds are pending because chat/orchestrator and behavioral graders do not exist. Exit 0 validates infrastructure execution only. It does not certify agent quality, authorization, safety, citations or booking behavior. No model calls, credentials, database connection or seeded accounts are needed. Invalid dataset/schema/checksum/duplicate IDs fail with exit 2 and a generic error without echoing case text. Check the exit code before reading a previously saved report.

Dataset edits require review, a new manifest dataset version and SHA-256; preserve LF bytes. Held-out cases must stay out of prompt tuning. Expected tool names describe planned contracts; textual response/state assertions are not executed yet. See `docs/EVAL_STRATEGY.md` for report semantics and the required real-path integration before Phase 3. Foundation checks now include eval formatting/lint/types/tests; hosted results require a later approved push.

## Phase 1 regression gate (Ticket 07)

From a fresh checkout, install the pinned Python and `.[dev]` dependencies as above. Configure native PostgreSQL/pgvector and use a local maintenance role with CREATEDB, CREATEROLE and extension-install privileges. Run from the repository root in an otherwise idle checkout:

```powershell
.venv\Scripts\python scripts/check_phase1.py
```

This historical full gate needs a securely supplied child-process maintenance
`TEST_DATABASE_URL` to pass; without one it records missing PostgreSQL evidence
and blocks. The bounded credential runner above runs PostgreSQL integration tests
only and deliberately does not export a URL to the calling shell or launch this
gate. For routine database verification use the runner; a future full gate run
needs a separately reviewed child-process launcher. The former `Get-Credential`
and parent-environment password recipe has been retired. Do not send passwords
through chat.

The gate serially reuses foundation format/lint/types/unit/HTTP/eval-infrastructure tests, all PostgreSQL migration/fixture/session-security tests, CI subprocess regressions, and the full seven-case offline inventory. `test-results/phase1.json` records revision/dirty state, UTC timestamp, exact command argument arrays, exit codes, test counts, offline metadata/statuses and unresolved risks. Each invocation writes companion evidence into a new unique directory beside the report, avoiding stale evidence reuse. `--report <path>` selects another destination. Foundation reports now also record command arrays and companion unit-test JUnit XML.

Exit **0** means the Phase 1 infrastructure gate passed; **1** means a check failed; **2** means required evidence is blocked (including skipped required tests). Any failure blocks progress, including authorization/privacy/security regressions. A failed command takes precedence over missing/skipped evidence. The offline inventory can succeed with seven **pending** behavioral cases: those remain zero executed, zero passed and a null pass rate. They do not certify agent/model quality or safety. Real-path behavioral evaluation is required before Phase 3 AI behavior; this command is not a model-backed deployment gate.

Gate policy tests run within the existing serial `ci_tests` suite, using controlled command outputs to exercise report handling without recursively launching the gate. The existing CI tests still exercise real passing/failing foundation subprocesses. GitHub Actions remains an offline foundation check; hosted success alone cannot satisfy the PostgreSQL phase gate. Inspect the actual hosted run for the exact committed SHA separately.

Ticket 07 verification on 2026-10-16: complete Phase 1 infrastructure gate **passed**, with **82 tests passed and zero skips/failures/errors**, including all 20 real PostgreSQL tests. All seven behavioral cases remain pending and unexecuted. Main database mutation counters were unchanged; disposable databases/role and temporary credential helpers were removed. Ticket 07/progress record exact commands, evidence and limitations. This result covers the uncommitted working tree; no model-backed or deployed-production quality is certified.


## Public clinic catalog (Phase 2 Ticket 01)

After upgrading explicitly to current head and loading the base clinic
fixtures, an operator can load the synthetic catalog using their local operator
`DATABASE_URL`:

```powershell
.venv\Scripts\python -m careflow.catalog_fixtures load --confirm-synthetic-catalog
```

This confirmed command inserts missing fixed IDs in one transaction. Repeating
it preserves edited/inactive catalog rows, credentials, sessions and unrelated
records. Base fixture reset also preserves catalog rows. It requires an existing
fixture clinic and current migration head; it refuses unconfirmed, remote or
unrecognized targets. Do not run this command on `careflow_ai` as part of tests.
All verification uses newly created disposable `careflow_test_<uuid>` databases.
The manifest has two specialties, two explicitly synthetic doctors and two
explicitly synthetic services; it contains no schedules or slots.

After the migration, grant only public catalog reads to the API role, using the
local operator connection:

```sql
GRANT SELECT ON public.clinics, public.specialties, public.doctors, public.services TO careflow_app;
```

These grants permit no catalog writes. See `docs/API_CONTRACTS.md` for filters,
public field lists, bounded pagination and safe errors. A model/frontend-free
HTTP walkthrough against an already migrated/seeded local API is:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/specialties'
Invoke-RestMethod 'http://127.0.0.1:8000/doctors?city=Karachi&limit=20'
Invoke-RestMethod 'http://127.0.0.1:8000/doctors/00000000-0000-4000-8000-000000000201/fee'
Invoke-RestMethod 'http://127.0.0.1:8000/services'
Invoke-RestMethod 'http://127.0.0.1:8000/services/00000000-0000-4000-8000-000000000302/fee'
```

Consultation `2500.00` and service `1500.25` are fictional persisted PKR prices
from this manifest, not real clinic facts. Public reads never grant staff access.

Ticket 01 verification on 2026-10-16: **104 local tests passed**, zero required
skips/failures/errors, including all **27 real PostgreSQL tests** (seven catalog
and 20 existing regressions). PostgreSQL 17.11 cleanup audits found no leftover
disposable databases/roles; temporary credentials/helpers were removed.
The persisted HTTP walkthrough ran through the in-process ASGI API. Hosted CI
was not run for these uncommitted changes; see the ticket/progress evidence.

## Schedules and availability (Phase 2 Ticket 02)

Use a local operator connection to a synthetic demo target, migrate explicitly
to current head (`0006_booking`), and load the existing clinic/catalog fixtures first.
Tests always create disposable `careflow_test_<uuid>` databases; never use
`careflow_ai` for test runs. No schedules or slots are silently seeded by GETs
or fixture loading.

Save a synthetic schedule JSON file (adjust effective dates for the current
Karachi date). IDs below refer to Synthetic Doctor One and an example schedule:

```json
{"id":"00000000-0000-4000-8000-000000000801","expected_version":0,"weekday":6,"local_start":"09:00","local_end":"10:00","effective_from":"2026-10-18","effective_to":"2026-11-15"}
```

```powershell
.venv\Scripts\python -m careflow.schedule_operator schedule --doctor-id 00000000-0000-4000-8000-000000000201 --input schedule.json --confirm-synthetic-schedules
.venv\Scripts\python -m careflow.schedule_operator generate --doctor-id 00000000-0000-4000-8000-000000000201 --confirm-synthetic-schedules
```

Generation covers today plus 29 Karachi calendar dates and excludes already
started slots. Repeating generation is harmless; it creates no duplicate or
overlapping intervals. There is no scheduler. Maintenance requires the current
`expected_version` (0 creates, successful maintenance increments to 1, 2, ...).
To recover current versions, the trusted local operator can inspect the relevant
schedule/exception row using their normal PostgreSQL administration client.
Edits atomically invalidate affected slots; explicit generation restores eligible
slots with incremented versions. Overnight windows are split across weekdays;
use `24:00` for the exclusive midnight ending a local date.

For a blocking exception use action `exception` with JSON `{id, expected_version,
start_at, end_at, reason}`; timestamps require explicit offsets and a range within
the same 30-date horizon. `deactivate-schedule` / `deactivate-exception` take
`{id, expected_version}`. Input files are bounded to 16 KiB; generate takes no
payload. Commands refuse unsafe targets, missing confirmation and stale schema
or versions. No public schedule-write route or staff authentication is added.

Extend API-role read grants through the trusted local operator connection:

```sql
GRANT SELECT ON public.doctor_schedules, public.schedule_exceptions, public.slots TO careflow_app;
GRANT SELECT (id, slot_id, status) ON public.appointments TO careflow_app;
```

Keep scheduling mutation privileges off the API role. Availability is a public
persisted read, for example (adjust dates to the approved horizon):

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/doctors/00000000-0000-4000-8000-000000000201/slots?start_at=2026-10-18T00:00:00%2B05:00&end_at=2026-10-19T00:00:00%2B05:00&limit=20'
```

Responses include local timestamps, UTC offsets, `Asia/Karachi`, stable slot IDs
and versions. Empty results stay empty. See API_CONTRACTS.md for exact filters,
scope, interval semantics and Ticket 03 booked-state exclusion/protection.

Ticket 02 verification on 2026-10-17: **156 full-suite tests passed**, including
47 real PostgreSQL tests (20 Ticket 02), zero failures/errors/skips. Formatting,
lint, strict types and dependency checks passed; standards/spec reviews had zero
findings. Final cleanup found no disposable databases/roles; temporary credentials
and helpers were removed. A failed aggregate safety-counter check was investigated
read-only: application-table update counters were zero, and the delta matched
observed background catalog auto-analysis. See the ticket/progress for exact
evidence and limits. No main application data/schema writes, hosted CI run,
commit or push occurred.

## Patient booking (Phase 2 Ticket 03)

Current schema head is `0006_booking`. Use the existing synthetic account,
catalog and persisted future slot inventory. The implemented flow is:

1. `GET /auth/csrf`, then `POST /auth/login` using that CSRF and cookie.
2. `GET /doctors/{id}/slots` for actual inventory; no invented slot IDs.
3. `POST /appointments/proposals` with only `{slot_id}` and authenticated
   cookie, exact configured Origin and X-CSRF-Token. Display its doctor, local
   times, timezone, exact PKR fee and expiry for explicit review.
4. A separate explicit confirmation submits `POST /appointments` with only
   `{proposal_token}`, the same security headers and an Idempotency-Key.
   Initial creation returns 201; the exact authenticated retry returns 200 with
   the same persisted booking. Keep the same key/proof when a response is lost.

Proposals last five minutes, expire at their deadline or slot start, and hold no
capacity. Changed authoritative state/fee requires a new proposal and review.
Retries replay for 24 hours; afterwards RETRY_EXPIRED prevents reuse. Consumed
proof cannot authorize a new key. No cleanup worker or appointment management
API is included; Ticket 04 requires a separate session/approval.

The executable HTTP walkthrough runs in-process ASGI with real PostgreSQL,
including login, review, confirmation, persisted result and exact retry:

```powershell
.venv\Scripts\python -m pytest backend/integration_tests/test_booking_integration.py::test_http_review_confirmation_and_exact_retry_persist_once -q
```

Set TEST_DATABASE_URL to the local `postgres` maintenance database using the
existing hidden-password process above. Tests now refuse any other maintenance
database and create/drop only fresh careflow_test_<uuid> databases. Never use
careflow_ai for tests. No frontend, AI adapter or real patient is required.

For a fresh restricted API role, these grants cover auth and booking in addition
to public catalog/availability reads. Apply only to an intentionally selected
synthetic deployment using the operator connection; tests exercise these grants
on a temporary role/database, without changing the main database:

```sql
GRANT SELECT ON public.alembic_version, public.users, public.patients,
  public.clinics, public.doctors, public.specialties, public.services,
  public.doctor_schedules, public.schedule_exceptions, public.slots,
  public.appointments, public.booking_proposals, public.booking_retries,
  public.booking_audit TO careflow_app;
GRANT SELECT (id, clinic_id, demo_role, is_synthetic)
  ON public.demo_identities TO careflow_app;
GRANT UPDATE (password_hash) ON public.users TO careflow_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.sessions, public.auth_limits
  TO careflow_app;
GRANT INSERT ON public.appointments, public.booking_proposals,
  public.booking_retries, public.booking_audit TO careflow_app;
GRANT UPDATE (appointment_id) ON public.booking_proposals TO careflow_app;
GRANT UPDATE (status, version, slot_id, doctor_id, doctor_name, start_at,
  end_at, accepted_fee) ON public.appointments TO careflow_app;
GRANT UPDATE (id) ON public.patients, public.demo_identities, public.clinics,
  public.doctors, public.specialties, public.doctor_schedules, public.slots
  TO careflow_app;
```

PostgreSQL row locks need an UPDATE column privilege; the id-only grants support
those locks. The API exposes no scope/catalog/schedule writes. Persona SELECT is
column-limited so the account provisioning/reset CLI cannot run as this role.
Appointment UPDATE is limited to management fields; immutable identity and accepted-price checks remain database-enforced. Audit and retries have no runtime UPDATE/DELETE grants; appointments have no DELETE grant. Revisit
existing broader grants when configuring an existing role; these statements do
not revoke permissions it already has. See docs/API_CONTRACTS.md for exact
request/response fields, status codes, expiry and retry rules.


Ticket 03 verification on 2026-10-17: 82 real PostgreSQL tests (35 booking),
103 offline/unit tests and 15 serial CI regressions passed across the final
suites (200 unique). Two full-run subprocess startup timeouts passed unchanged
on focused rerun and the subsequent complete offline foundation run. Earlier
failed attempts remain in local evidence. Test-only native connection startup
allows 10s and maintenance DDL 30s; production connect/statement limits remain
3s. Startup root cause is unisolated; TestClient deprecation remains. Final
catalog-only safety audit and test DB/role/credential/helper cleanup passed.
No AI behavior, hosted CI, commit, push or Ticket 04 implementation is claimed.


Phase 2 Ticket 04 adds authenticated owned appointment listing and separate
review/confirmation endpoints for cancellation and rescheduling. Changes are
allowed at exactly 24 hours remaining before the current appointment; less is
rejected at review and confirmation. Rescheduling requires review of the current
target fee and retains prior slot/price history. Immutable response snapshots
ensure retries return their original result after later changes. See
`docs/API_CONTRACTS.md` for filters, payloads and safe errors. Readiness requires
`0007_management`; migrate only explicitly authorized synthetic databases.
Ticket 04 local verification passed: 119 offline/unit, 119 PostgreSQL and 15
serial CI tests, zero failures/errors/skips; format/lint/strict types and offline
inventory passed. Seven behavioral evals remain pending, not quality passes.
Final catalog-only safety audit and temporary DB/role/credential/helper cleanup
passed. [Foundation checks](https://github.com/Huzaifawaseem2006/careflow-ai/actions/runs/39060292965) also passed
for approved commit `24051ac1fa30cdf3da3f32eca7a92aa034f607f1`. Ticket 04 is resolved
and the Phase 2 backend exit is verified; hosted offline CI complements the
separate local PostgreSQL results. TestClient deprecation and the seven pending
behavioral evals remain documented limitations. The owner separately approved
the documentation-only closeout commit/push on 2026-10-18. Phase 3 has not begun
and requires a new explicit approval.
See docs/PROGRESS.md for commands and evidence.

## Public grounded chat (Phase 3 Ticket 01)

`POST /chat` now supports single-turn public doctor/specialty/service and exact
PKR fee lookup through five bounded read-only tools. See [chat contracts and
runtime configuration](docs/CHAT.md). Chat is disabled by default; setting an
API key alone does not enable it or authorize spending. Never submit real patient
data. No conversation persistence, appointment chat, retrieval or frontend is added.

Mocked behavior uses the same orchestrator and real catalog services, with a
disposable PostgreSQL database and no Anthropic calls:

```powershell
.venv\Scripts\python -m evals.run_catalog --partition dev --report evals/results/catalog-mocked.json
.venv\Scripts\python -m pytest backend/tests backend/integration_tests evals/tests ci_tests -q -rs
```

Configure TEST_DATABASE_URL securely for the local postgres maintenance database;
the eval command and integration fixture create/drop only careflow_test_* targets.
See [evaluation semantics](docs/EVAL_STRATEGY.md) for executed versus pending cases,
baseline versions, nonzero failure gates and unmeasured live model quality.
