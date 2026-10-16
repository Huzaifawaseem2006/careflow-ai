# 04: Reset the fictional clinic fixtures

**What to build:** A reviewer can reproducibly load and reset the approved fictional Karachi clinic and synthetic demo identities, with the clinic timezone and PKR settings preserved.

**Blocked by:** 03 — Start the local database and apply migrations.

**Status:** resolved

**Approval gate:** Owner explicitly approved Ticket 04 only on 2026-10-16. Commits/pushes and Ticket 05 remain separately gated.

- [x] Fixture creation and reset are deterministic and safe for the local demo database.
- [x] Tests verify one fictional Karachi clinic, `Asia/Karachi`, PKR, and synthetic identities.
- [x] No real patient data or credentials are committed or logged.
- [x] Fixture commands and PostgreSQL integration results are recorded.

## Implementation — 2026-10-16

Added migration `0002_synthetic_fixtures`, minimal SQLAlchemy clinic/demo-persona tables and `python -m careflow.fixtures {load,reset} --confirm-synthetic-fixtures`. The manifest has one explicitly fictional Karachi clinic (`Asia/Karachi`, PKR) and four credential-free synthetic personas (two patients, receptionist, admin), fixed UUIDs and `.invalid` emails. Persona labels grant no permissions; D02/authentication remain for Ticket 05.

Load inserts missing known IDs without overwriting edits; reset restores only those IDs. Both use a single transaction and advisory lock, never delete/truncate data, and refuse missing confirmation, nonlocal/unrecognized targets or a stale schema. CLI errors are generic and credential-safe. README records exact commands and target restrictions. Existing `careflow_ai` has not been migrated or seeded by this session.

The owner ran integration locally with credentials kept out of chat:

```powershell
.venv\Scripts\python -m pytest backend/integration_tests -v -s -rs --junitxml test-results/ticket04-postgres.xml
```

Configure maintenance `TEST_DATABASE_URL` using the README password prompt first. The seven tests create/drop only disposable databases. On 2026-10-16, inspected the saved `test-results/ticket04-postgres.xml`: **7 passed in 15.444s, 0 failures, 0 errors, 0 skipped**. All seven expected database/fixture test cases are present and passing. This verifies migration/readiness regression plus deterministic load/reset, preservation of unrelated rows, atomic rollback and refusal before migration. No existing-demo reset or CLI success is inferred from this service-level integration run.

Verification so far: new tests initially failed collection because the fixture module did not exist. After implementation, `scripts/check_foundation.py` passed format/lint/types (19 Python files) and **22 offline/unit tests**; `pip check` passed. Reviewed generated `alembic upgrade head --sql` output and scoped tracked/new source files. An attempted live suite explicitly **skipped all 7 tests** because TEST_DATABASE_URL is unset. Known Starlette deprecation/cache-access warnings remain. CI regression results and final audit follow in progress. No AI changes/evals, hosted run, phase gate, commit or push.

Closeout: **2 CI regression tests passed** in 69.93s with ordinary Windows execution permissions after sandbox temp-directory failures. Together with the 22 offline/unit and 7 owner-run PostgreSQL tests, all applicable suites passed (31 cases across separate runs). Reviewed fixture source contains only explicitly synthetic identities and no credentials; offline tests verify credential-safe CLI failures. `git diff --check` passed. Ticket 04 has no remaining acceptance blocker. Ticket 05 requires separate approval and D02; commits/pushes remain separately gated.
