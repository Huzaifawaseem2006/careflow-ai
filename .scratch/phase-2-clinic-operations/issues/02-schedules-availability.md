# 02: Schedules & Availability

**What to build:** Guests query real persisted slots generated from doctor schedules and blocking exceptions; an explicitly confirmed local operator maintains synthetic schedules safely.

**Blocked by:** 01 — Clinic Catalog.

**Status:** resolved

**Approval gate:** Implementation, D03 and TDD seams approved 2026-10-17. Commit/push each still need separate approval.

## Scope and existing infrastructure

Implement PRD FR-02 using the catalog, clinic timezone, migrations/readiness and disposable PostgreSQL harness. Add effective weekly schedules, exceptions and persisted slots. Provide a bounded confirmed local operator maintenance/generation path following existing CLI target guards; no staff HTTP authority exists yet. Establish compatible doctor/schedule/slot locking and resource versions for booking. Appointment-dependent queries wait until 03 creates appointments; no scheduler is needed.

## Acceptance criteria

- [x] Record approved D03 horizon, query bounds, local-time/DST interpretation and edit policy. Owner approved 2026-10-17; recorded in decisions.
- [x] Effective schedules generate deterministic, non-overlapping 30-minute capacity-one slots within the approved horizon. UTC instants round-trip to `Asia/Karachi`; responses include timezone/offsets.
- [x] Repeated/concurrent generation creates no duplicate/overlapping intervals. Constraints and transactional validation enforce positive exact duration, references and uniqueness; shifted schedule starts cannot bypass overlap protection.
- [x] Confirmed edits/exceptions atomically invalidate affected unbooked slots and version stale resources. Establish the contract rejecting edits affecting booked appointments; 03 completes/tests actual appointment integration.
- [x] Public availability returns only persisted active future unblocked slots, with bounded validated ranges and clinic scope. Empty results remain empty; inactive/missing/cross-clinic doctors expose no slots or patient data. GETs never generate slots.
- [x] Operator writes refuse missing confirmation/unsafe targets, serialize competing edits/generation and roll back fully on failure. No public schedule mutation endpoint exists.
- [x] Migration/repeat/readiness checks and an operator-generation-to-HTTP-query walkthrough pass independently of booking/frontend/AI.

## Tests and verification

Strict TDD for overlap/concurrent-write integrity; focused tests for query formatting. Cover local midnight/weekday/effective-date edges, horizon boundaries, invalid/offset-free inputs, exceptions, shifted overlaps, repeated generation and clinic isolation. Independent PostgreSQL connections test edit/generation races, constraints and rollback; SQLite is insufficient. Run applicable format/lint/types, unit/HTTP/PostgreSQL and catalog/fixture/readiness regression. Report booking-aware coverage as deferred to 03, not passed here.

## Out of scope

Reservations/booking, proposals/idempotency, patient history, variable slot lengths, recurring patient bookings, staff auth/HTTP/UI, background jobs, frontend and AI tools.

## Completion

Verify acceptance with executed evidence and no required database skips. Update contracts, approved D03 choice, ticket/progress and schema status. Hand off locking/version rules and deferred booking integration to 03; do not start it or commit/push without separate approval.

## Verified completion — 2026-10-17

Started from clean master at e7bd30632e70107abb9f94b8c3be97ef2dcb368c,
matching live origin/master; Ticket 01 committed. Implemented head
0005_scheduling, constraints/versions, effective schedules/exceptions, confirmed
local operator maintenance/generation and public persisted availability. No
booking, staff HTTP authority, frontend, AI, Docker or Python dependency added.
Same-day windows support exclusive 24:00 for a lossless overnight split.

Executed verification:

- Focused Ticket 02 PostgreSQL suite: **20 passed**, no failures/errors/skips,
  115.27s; ignored schedules-postgres-complete.xml. Covers independent-connection
  generation/edit/exception races, stale concurrent edits, shifted overlap
  constraints, rollback after partial generation and failed edits, restricted
  application role, foreign clinic/inactive resources, fixture preservation,
  migration/repeat/readiness, 30-date horizon, midnight and real CLI-to-HTTP flow.
- Full `.venv\Scripts\python -m pytest backend/tests backend/integration_tests
  ci_tests evals/tests -q -rs --tb=short
  --basetemp=test-results/schedules-final-tmp
  --junitxml=test-results/schedules-final.xml`: **156 passed in 498.39s**, zero
  failures/errors/skips. Parsed JUnit independently: 77 unit/HTTP, 47 real
  PostgreSQL (including the 20 above), 15 serial CI and 17 eval-infrastructure.
- Ruff format/lint, strict mypy (50 source files), pip check and diff checks:
  **passed**. Known Starlette TestClient deprecation remains non-failing.
- Standards/spec reviews: **0 findings on each axis**. Reviewers were read-only.
  No hosted CI or live-model eval executed. Seven behavioral evals remain pending.

The full-run wrapper initially exited 1 after pytest passed because its aggregate
main-database update counter check changed 73→91. This failure is retained, not
reported as a passing original audit. Follow-up forced-read-only catalog checks
found zero application-table updates; all 91 local updates are system catalogs.
Observed pg_database auto-analysis at 10:31:42 Asia/Karachi and its 18 statistic
rows match the delta, consistent with background planner-statistics maintenance.
No main application data/schema writes or statistics resets were executed.
Tests connected only to disposable databases; subsequent main inspection read
catalog counters only with transaction_read_only=on. Final maintenance audit:
**passed**, zero disposable databases/roles; main OID 16388 and inserted/deleted
counters (1498/21) preserved. This is bounded catalog/source evidence, not a
content snapshot. Ignored schedules-final-safety.json and
schedules-verification.json preserve the results and initial audit distinction.

All seven temporary credential/helper files were removed and absence verified;
parent DATABASE_URL/TEST_DATABASE_URL unset. No credential was logged or tracked.
The earlier missing-credential skip is superseded by executed passing DB tests.

Files added: backend/careflow/{scheduling,schedule_schema,schedule_operator,
availability,availability_api}.py; backend/migrations/versions/0005_scheduling.py;
backend/tests/{test_scheduling,test_availability}.py;
backend/integration_tests/test_scheduling_integration.py.
Files modified: backend/careflow/{catalog_schema,database,main,readiness}.py;
README.md; docs/{API_CONTRACTS,ARCHITECTURE,DECISIONS,PROGRESS}.md;
plans/phase-2-clinic-operations.md; this issue.

All seven acceptance criteria verified. Actual booked-state queries/protection
and proposal invalidation remain explicitly deferred to Ticket 03. Its integration
must replace the fail-closed appointment-table guard, preserve doctor-before-slot
locking and revalidate doctor/resource versions. D04/D12 remain unapproved.
Ready for owner code/documentation review; no commit/push or Ticket 03 work.
