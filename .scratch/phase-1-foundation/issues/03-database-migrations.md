# 03: Start the local database and apply migrations

**What to build:** A reviewer can run native local PostgreSQL with pgvector, apply an initial Alembic migration, and verify database readiness separately from API process liveness. Docker/Compose is deferred and is not required.

**Blocked by:** 01 — Start the API and verify its health.

**Status:** resolved

**Approval gate:** Owner approved Ticket 03 implementation and the Docker-free scope change on 2026-10-15. System software installation, commits and pushes still require separate approval.

- [x] Native local PostgreSQL is available and the migration enables the required vector extension; no Docker/Compose prerequisite.
- [x] A clean database migrates to head and the migration can be re-run without unexpected changes.
- [x] An integration check uses PostgreSQL and reports readiness without exposing credentials.
- [x] Migration and integration commands, versions, and results are recorded.

## Implementation checkpoints — 2026-10-15 (superseded by verified closeout below)

Implemented synchronous environment-based PostgreSQL configuration, Alembic `0001_vector` (extension only), credential-safe migration errors, and `/ready` independently of `/health`. Added offline/unit tests plus four opt-in integration tests that create/drop fresh randomly named local databases. Domain schema, fixtures and Tickets 04–07 are excluded. README contains native Windows installation and setup commands. No system software was installed.

Versions: Python 3.13.13; SQLAlchemy 2.0.54; Alembic 1.20.0; Psycopg and psycopg-binary 3.3.6, installed and verified by imports; `pip check` passed. PostgreSQL 17.11 is now installed; binaries report 17.11, its Windows service is running and pg_isready reports port 5432 accepts connections. The owner connected with pgAdmin and reported zero available `vector` extensions. pgvector 0.8.7 remains the pinned installation target; live extension compatibility is not yet verified.

Blocked: `vector.control` and `vector.dll` are absent from the PostgreSQL 17 installation; database URLs are not configured for the agent/test process. Visual Studio 2022 Community with C++ build tools, PostgreSQL server headers and postgres.lib are present. README now gives the official pinned pgvector build/install commands with PGROOT pointing to PostgreSQL 17. System installation remains owner-run. Real migration-to-head, repeat migration, vector functionality, and ready-success/unmigrated-state checks remain unverified. All acceptance checkboxes stay unchecked until real database evidence is available. Code completion does not resolve this ticket.

Commands from the repository root:

```powershell
.venv\Scripts\python -m pip install -e '.[dev]'
.venv\Scripts\python -m pip check
.venv\Scripts\python -m alembic upgrade head --sql
.venv\Scripts\python scripts/check_foundation.py
.venv\Scripts\python -m pytest ci_tests -q
# After native PostgreSQL/pgvector setup and setting TEST_DATABASE_URL per README:
.venv\Scripts\python -m pytest backend/integration_tests -v -s -rs
```

The foundation command covers formatting, lint, type checks and offline/unit tests. The integration command without TEST_DATABASE_URL reports explicit skips; it is not a database pass. Complete this ticket's real database verification before starting Ticket 04. No commit or push has been made.

Executed results: `scripts/check_foundation.py` passed all four checks (14 Python files, 9 offline/unit tests); report `test-results/foundation.json` records starting HEAD `fc006e94f4235032ff32e0b88511cbab8af3f2a4` and `dirty: true`. `alembic upgrade head --sql` passed and emitted transactional vector/version-table DDL; this is offline SQL only. Combined `pytest backend/tests backend/integration_tests ci_tests -q -rs` passed 11 tests (9 offline/unit + 2 real-subprocess CI regressions), with 4 real-PostgreSQL tests skipped because TEST_DATABASE_URL is absent. Known Starlette deprecation and intermittent Windows pytest-cache warnings remain non-failing. `pip check` and `git diff --check` passed. Standards and spec reviews found no actionable issues. No new hosted CI, AI eval or full Phase 1 gate was run; live DB acceptance remains blocked.

PostgreSQL 17 follow-up: strengthened the existing unmigrated-database integration test to first verify SQL connectivity and no version table. It can run before pgvector using the focused command in README. Attempted it after the change: 1 skipped, because TEST_DATABASE_URL is unset. Re-ran foundation verification: format/lint/types passed (14 files), 9 offline/unit tests passed in 12.80s. PostgreSQL 17.11 binary/service/port checks passed; pgvector files are absent. Migration requirements are unchanged; the full four-test live suite still needs to run after owner installation. No system software installation, commit or push was performed.

## Verified closeout — 2026-10-15

Owner installed pgvector and created `careflow_ai`. Authenticated SQL confirmed PostgreSQL **17.11** and available/installed pgvector **0.8.7**. Ran `python -m alembic upgrade head` twice using process-environment DATABASE_URL: existing `careflow_ai` initially had no revision, reached `0001_vector`, and a repeat left the checked extension/type catalog state unchanged. No database reset or domain fixtures were performed. A direct vector distance calculation returned **5.0**. Real PostgreSQL-backed HTTP checks returned `/ready` 200 and `/health` 200; changing the connection to an unavailable target returned `/ready` 503 while `/health` stayed 200.

Final combined verification command, with locally configured DATABASE_URL and TEST_DATABASE_URL:

```powershell
$taskTestTemp = Join-Path (Get-Location).Path ('test-results\pytest-ticket03-' + [guid]::NewGuid().ToString('N'))
.venv\Scripts\python -m pytest backend/tests backend/integration_tests ci_tests -v -s -rs --basetemp $taskTestTemp --junitxml test-results/ticket03-tests.xml
```

**Passed: 15 tests, 0 failures, 0 errors, 0 skips in 45.34s.** Includes 9 offline/unit, all 4 real disposable-PostgreSQL integration tests, and 2 actual subprocess CI regressions. The tests demonstrate clean migration and repeat upgrade, functional vector operations, ready-success, unmigrated/missing-extension/stale-revision failures and independent liveness. Disposable databases were cleaned up by their fixtures. `scripts/check_foundation.py` passed formatting/lint/types for 14 Python files and 9 offline/unit tests; `pip check` passed. The existing Starlette deprecation remains non-failing.

Two initial combined attempts hit Windows sandbox WinError 5 during pytest temporary-directory setup/cleanup; the final ordinary-permissions run above passed without application changes. The successful JUnit file confirms all 15 cases and zero skips. Nonsecret local evidence: ignored `test-results/database-verification.json`, `test-results/ticket03-tests.xml` and `test-results/foundation.json`; the database report records versions, initial/final revisions, repeat-upgrade result, vector distance and HTTP statuses. Git revision remains `fc006e94f4235032ff32e0b88511cbab8af3f2a4` with uncommitted Ticket 03 changes (`dirty: true`).

Credentials were entered locally via a secure PowerShell prompt, temporarily Windows-encrypted under ignored test-results, decrypted only into child-process environment variables, and removed after verification along with password helpers. No password or credential URL was printed, committed or pushed. Local URLs were cleared after use; future API runs must set their own environment using README and a separate application role. No new hosted CI, AI evaluation or full Phase 1 gate is claimed. All four Ticket 03 acceptance criteria are now verified. Ticket 04 remains unstarted; owner review and explicit commit/push approvals are still required.
