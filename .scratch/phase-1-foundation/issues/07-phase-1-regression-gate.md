# 07: Demonstrate the Phase 1 regression gate

**What to build:** A reviewer can run the complete applicable foundation checks from a fresh checkout and inspect an evidence-based Phase 1 report before later phases begin.

**Blocked by:** 02 — Run foundation checks in CI; 03 — Start the local database and apply migrations; 04 — Reset the fictional clinic fixtures; 05 — Sign in and end a synthetic patient session; 06 — Run the versioned synthetic eval set offline.

**Status:** resolved

**Approval gate:** Owner explicitly approved Ticket 07 on 2026-10-16; Tickets 01–06 are resolved. Each commit/push still requires separate approval.

- [x] Formatting, lint, type, unit, HTTP, migration, PostgreSQL integration, session-security, and offline eval checks run as applicable.
- [x] The report records exact commands, revision, passed/failed/skipped/blocked results, and unresolved risks.
- [x] Critical authorization, privacy, or safety failures block the phase gate; no live model quality claim is made from offline results.
- [x] Progress, decisions, and the Phase 1 plan reflect verified results and the next small task.

## Implementation and evidence — 2026-10-16

Verified clean `master` at `5498a7997dfbb49b05057312ab39420c6ffeba30` before editing; local/cached/live remote master all match. All six prerequisites are resolved. Ticket 06's issue records 49 passed / 20 PostgreSQL skips and seven pending behavioral cases; its closeout was missing from progress and is reconciled there.

Added `scripts/check_phase1.py`, `scripts/__init__.py`, and 13 gate policy tests in `ci_tests/test_phase1_gate.py`. Extended the existing foundation report with exact command arrays and companion unit-test JUnit. The gate reuses existing foundation, real PostgreSQL and serial CI suites, then runs the all-partition offline inventory. Unique per-run evidence directories prevent stale artifacts from satisfying a check. Required skips/missing evidence block; any failed command/test takes precedence. No application, auth, migration, model, dependency or Phase 2 code changed.

Executed `.venv\Scripts\python scripts/check_phase1.py --report test-results/ticket07-without-database-final.json` with ordinary Windows permissions after sandbox pytest directory access failed. Result **blocked, exit 2** at baseline revision with `dirty: true`:

- Foundation format/lint/types passed (34 Python files); **47 offline/unit/HTTP/eval-infrastructure tests passed**.
- PostgreSQL suite: **20 skipped**, zero passing DB tests, because TEST_DATABASE_URL is unset. Earlier Ticket 05 database evidence is historical and does not substitute for this gate.
- Serial CI suite: **15 passed** (2 existing real foundation subprocess regressions + 13 gate policy cases).
- Offline inventory: **7 pending, 0 passed/failed/skipped/blocked, 0 executed, null pass rate**. Infrastructure command exited 0; no agent/model path or behavioral safety quality was evaluated.

Independently parsed the report and JUnit counts. Separate focused gate run: **13 passed**. `pip check` and final `git diff --check` passed. Initial full attempt correctly failed on a new line-length error, recording foundation/CI failure alongside DB skips and pending evals; corrected before the final run. Focused tests exercise failure precedence, missing/invalid evidence, empty suites, required skips and offline failure/pending separation through controlled command outputs, not live model runs. Existing Starlette deprecation warning remains non-failing.

Authenticated GitHub Actions API verified [Foundation checks success](https://github.com/Huzaifawaseem2006/careflow-ai/actions/runs/38911997790) for exact SHA `5498a7997dfbb49b05057312ab39420c6ffeba30` (completed/success). This is the committed baseline's offline CI, not CI for these uncommitted changes or PostgreSQL evidence. No hosted run was triggered. Independent standards/spec reviews found zero actionable findings. README, progress, decisions and phase plan describe actual scope/evidence; no commit/push occurred.

**Earlier checkpoint blocker (resolved below):** local PostgreSQL credentials were unavailable. The owner subsequently completed the secure local setup and authorized disposable-database continuation. The historical blocked report remains valid evidence of skip handling; it is superseded for phase exit by the successful run below.

## PostgreSQL continuation and Phase 1 exit — 2026-10-16

Owner confirmed local credential setup and explicitly authorized the real PostgreSQL gate and cleanup. Executed `powershell -NoProfile -ExecutionPolicy Bypass -File .\test-results\with-ticket07-database.ps1` with ordinary Windows permissions. This decrypted the temporary Windows-protected credential only into child-process memory/environment, targeted maintenance database `postgres`, performed read-only catalog checks and invoked `.venv\Scripts\python scripts/check_phase1.py`. No password/URL was printed or tracked.

The complete gate **passed (exit 0)** at `2026-10-16T14:56:30.284796+00:00` (19:56:30 Asia/Karachi), revision `5498a7997dfbb49b05057312ab39420c6ffeba30`, dirty true for this uncommitted ticket. Independently parsed `test-results/phase1.json` and its fresh companion JUnit files:

- Foundation: format/lint/types passed; **47 tests passed**, JUnit duration 22.656s.
- PostgreSQL: **all 20 distinct integration tests passed**, zero skips/failures/errors, 97.425s. Includes fresh/repeat migrations, readiness/vector, fixture integrity and patient-session permission/security/concurrency/retry coverage against real PostgreSQL **17.11**.
- Serial CI regressions: **15 passed**, zero skips/failures/errors, 56.559s.
- Total constituent suites: **82 passed / 0 skipped / 0 failures / 0 errors**. Offline inventory remains **7 pending / 0 passed / 0 executed / null pass rate**, with offline-infrastructure-only labeling and no real-agent-path/model quality claim.

`test-results/ticket07-verified.json` preserves the independent count/status verification. Catalog snapshots `ticket07-catalog-before.json`, `ticket07-catalog-after.json` and `ticket07-catalog-final.json` show **zero temporary careflow_test databases and careflow_auth roles**, both before and after. The fixture/source targets only disposable databases, and audit connections used `postgres`, never `careflow_ai`. Main database identity and mutation counters stayed unchanged: OID 16388, inserts 1498, updates 73, deletes 21, no statistics reset. Four additional committed transactions appeared (1141 to 1145), while rollback count stayed 12. The initial extra audit asserted equality of all counters and therefore returned 1 after the gate itself passed; transaction commits include reads/background activity and are not a mutation measure. A follow-up read-only audit compared identity/mutation counters, confirmed no further changes or main-database connections, and passed. This is source plus catalog evidence of no test writes to the main database, not a byte-for-byte database snapshot claim; no additional product test run was needed.

Removed and verified absence of all six ignored temporary files: encrypted `ticket07-database.dpapi`, configuration/execution/cleanup PowerShell helpers, database audit Python helper and earlier CI inspection Python helper. Nonsecret JSON/JUnit evidence remains ignored. DATABASE_URL and TEST_DATABASE_URL are unset in the parent; child environment was cleared. `pip check` passed; final `git diff --check` passed. No source changed during continuation; previous standards/spec review remains applicable. Existing Starlette deprecation is non-failing. Hosted baseline CI evidence above is unchanged; no CI run, commit or push was triggered for these uncommitted changes.

All four Ticket 07 acceptance criteria are now verified; **Phase 1 infrastructure exit achieved**. Remaining limitations: seven behavioral cases have no orchestrator/model execution; no deployed HTTPS/production-security assurance. Next is owner review of the scoped documentation/code diff and separately approved commit/push. Phase 2 requires explicit approval in a fresh session and was not started.
