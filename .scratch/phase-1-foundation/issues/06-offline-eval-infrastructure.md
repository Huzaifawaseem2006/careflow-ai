# 06: Run the versioned synthetic eval set offline

**What to build:** A reviewer can validate a versioned synthetic case set and run an offline evaluation command that emits a JSON report with honest case status and version metadata.

**Blocked by:** 01 — Start the API and verify its health.

**Status:** resolved

**Approval gate:** Owner explicitly approved Ticket 06 implementation on 2026-10-16. No commit or push is authorized.

- [x] The dataset includes positive, negative, adversarial, missing-evidence, tool-misuse, privacy, and escalation cases using synthetic data only.
- [x] Invalid case data fails validation; pending agent cases are never counted as passed.
- [x] Reports distinguish passed, failed, skipped, blocked, and pending cases and record code/dataset versions.
- [x] The offline run is clearly labeled as such; no model-backed or real-agent-path result is claimed before those paths exist.

## Implementation and evidence — 2026-10-16

Started clean on `master` at `22cf968` (Ticket 05 committed); Tickets 01–05 are resolved and committed. Added seven synthetic JSONL cases, strict Pydantic contract validation, duplicate-ID/contradiction/empty-data checks, checksum/version manifest and LF checkout rule. CLI validates the full dataset before partition selection; dev is default and held-out is separately selectable. Existing dependencies only; no application/auth/booking/database changes.

`python -m evals.run_local --partition all` exited 0 with **7 pending, 0 passed/failed/skipped/blocked, 0 executed, null pass rate**. Separate dev and held-out invocations exited 0 with 5 and 2 pending respectively. Reports in ignored `evals/results/` include UTC/Git dirty state, dataset/schema/fixture versions, group/severity summaries and explicit offline-infrastructure-only/no-real-path labels. Behavioral metrics and unimplemented versions remain unavailable. A successful exit is not a behavioral gate pass.

Focused `python -m pytest evals/tests -q`: **17 passed**. Tests reject malformed contracts, contradictory tool expectations, checksum drift, duplicate IDs, malformed JSON and empty datasets; exercise real CLI partitions and ensure pending/skipped/blocked cannot become passes or enter pass-rate denominators. Format/lint/types/dependency checks passed after fixing initial line-length/test-typing errors. Foundation checks include eval code/tests.

Independent standards and spec reviews against `22cf968` plus new/uncommitted files each reported zero code findings. Documentation explains the remaining boundaries: no orchestrator, behavioral graders, corpus, live mode or behavioral baseline; wire the same production chat/service path before Phase 3 AI behavior. No live model or real DB evidence is claimed by this ticket. No Ticket 07 work, commit or push.

Final regression: `.venv\Scripts\python -m pytest backend/tests backend/integration_tests evals/tests ci_tests -q -rs --basetemp test-results/ticket06-pytest --junitxml test-results/ticket06-tests.xml`: **49 passed, 20 skipped, 0 failed/errors in 86.50s**, one existing Starlette deprecation warning. Includes 30 existing offline/unit, 17 eval-infrastructure and 2 serial CI subprocess tests. PostgreSQL tests skipped because `TEST_DATABASE_URL` is unset; they are not passing DB evidence. No auth/booking code changed. JUnit counts independently checked. `ruff format --check backend scripts ci_tests evals`, `ruff check backend scripts ci_tests evals`, `mypy backend scripts ci_tests evals` (31 files), `pip check`, and `git diff --check` passed. Bounded common credential-pattern scan of nine implementation/config/dataset files found no matches. Reports/caches/test artifacts remain ignored; no CI probe remains. Hosted CI not run (no approved push); Phase 1 gate not run. All Ticket 06 acceptance criteria verified; ready for owner review.
