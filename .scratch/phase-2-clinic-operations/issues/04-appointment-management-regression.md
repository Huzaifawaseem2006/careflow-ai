# 04: Appointment Management & Regression

**What to build:** Patients list only their appointments and explicitly confirm safe cancellation/rescheduling under the 24-hour policy; complete Phase 2 backend regression evidence is recorded.

**Blocked by:** 03 — Appointment Booking.

**Status:** ready-for-human

**Approval gate:** Implementation, D12 change contracts, inclusive cutoff, target pricing and three TDD seams approved 2026-10-17. Commit/push each still need separate approval. Hosted acceptance and Phase 2 exit remain pending.

## Scope and existing infrastructure

Implement PRD FR-03/FR-05 on existing booking transactions, session security, slots, proposals/idempotency/audit and migration infrastructure. Add bounded owned listing and cancel/reschedule proposal plus confirmation endpoints. Reuse booking's mechanism, without a second workflow engine. Complete phase regression; hosted evidence may await separately authorized Git actions.

## Acceptance criteria

- [x] Owned listing provides bounded stable pagination/order and documented status/date filters, persisted doctor/local time/timezone/state/accepted fee. No foreign-patient/clinic records or private metadata leak across pages.
- [x] Change proposals validate owned active booking, clinic scope, policy and target slot; return exact review summaries without changing booking/capacity. Each mutation requires its own separate confirmation request.
- [x] Enforce 24 hours before the current appointment start using server time at proposal and confirmation, including elapsed review time. Test the owner-approved exact boundary. Cancelled/past bookings and same-slot/no-op targets have documented safe behavior.
- [x] Cancellation atomically marks cancelled, releases capacity, consumes proposal and records retry result/audit, preserving history/accepted fee. Exact authenticated retry returns prior result; fresh actions cannot reuse proof.
- [x] Reschedule locks appointment/source/target slots in stable order and atomically updates the same owned appointment plus audit/retry/proposal. Failed/unavailable/stale target preserves original booking/capacity. Review/recheck target price under approved policy; audit retains prior price/slot history.
- [x] Missing/expired/mismatched proof, wrong actor/operation, changed payload, revoked identity, CSRF/origin failure and cross-clinic access neither mutate nor disclose private data. Reuse bounded writes, no-store responses and safe errors.
- [x] Independent-connection races cover cancel versus reschedule, two reschedules, target booking contention, target schedule edit and same-key retries. Persisted outcomes preserve capacity one, complete moves, consistent availability/history and no duplicate action/audit.
- [x] HTTP scenario demonstrates login, catalog/availability, booking, own listing, cancellation, another booking and rescheduling with persisted IDs/explicit confirmations. Ownership/cutoff negatives demonstrate rejection.
- [x] Full applicable local regression passes with no required skips: format/lint/types, foundation/backend/eval-infrastructure tests, all PostgreSQL integration and serial CI regressions. Record commands, revision, counts and disposable-resource cleanup. Preserve Phase 1 auth/fixture/readiness behavior and offline inventory semantics. Any minimal gate extension rejects failed/missing/skipped evidence.
- [ ] Following separately approved commit/push, verify hosted Actions for the exact reviewed SHA at the phase milestone. Hosted offline CI does not replace PostgreSQL evidence. If authorization/evidence is pending, report local results separately and keep hosted criterion/phase exit pending.

## Risk-based TDD and integration

Strict red/green TDD for private listing, ownership, policy, confirmation and transactions. Test just below/exactly/above 24 hours, UTC/local rollover, cutoff crossed during review, stale versions, fee changes and cancelled/invalid targets. Cover cross-user/clinic pagination leakage, guest/expired/reset sessions and forged authority fields. Verify constraints, failure-injection rollback, payload conflicts/retention and independent-connection races on PostgreSQL. Re-run booking concurrency/auth idempotency/security regression; mocked races are insufficient.

No AI changes are planned. Run offline inventory as infrastructure regression, preserving seven pending behavioral cases and null quality pass rate. Only if AI surfaces change, run affected evals against baseline and distinguish mocked/live results.

## Out of scope

Phase 3 AI/tools, Phase 5 frontend/staff authentication/dashboard, broad staff CRUD, reminders, payments, deployment, real patients, new infrastructure and production-hardening projects.

## Completion

Verify every acceptance criterion before `resolved`; critical auth/booking/policy failures and required database skips block completion. Update contracts, meaningful approved decisions, ticket/progress and phase milestone with actual evidence/pending hosted status. Show documentation before separately approved commit/push. Recommend Phase 3 planning/approval in a fresh session only after Phase 2 exit; do not begin it here.


## 2026-10-17 implementation checkpoint — PostgreSQL credential pending

Owner approved Ticket 04 D12 contract, inclusive 24-hour cutoff, target pricing,
immutable retries and service/HTTP/real-PostgreSQL TDD seams. Recorded approvals
in docs/DECISIONS.md before implementation and corrected stale Ticket 03 plan status.

Partial work only: listing filter/auth and change confirmation validation/origin/
auth scaffolding; draft 0007_management migration for retry snapshots/history
and change operations. Listing still returns an empty page after authentication;
confirmation scaffolding rejects authenticated requests with NOT_FOUND. No actual
listing/cancel/reschedule business behavior is complete. Migration has only offline
DDL verification; no application database was contacted or migrated.

TDD observations: missing listing failed 405 vs 401 then passed; missing change
routes failed 404 vs 422 then security tests passed; invalid listing filters
failed 401 vs 422 then passed; migration snapshot DDL absent then present.
Checkpoint: 23 focused offline tests passed, zero failures/skips; repository-wide
Ruff format/lint and strict mypy (59 files) passed; git diff --check passed.
New real PostgreSQL ownership test skipped because TEST_DATABASE_URL is absent
(management-no-credentials.xml). Required skip blocks acceptance; no criterion
is checked complete. Focused passing report: management-offline-checkpoint.xml.
Initial Ruff findings fixed; initial pytest cache ACL warnings avoided with
-p no:cacheprovider. Existing TestClient deprecation persists.

No TEST_DATABASE_URL, PGPASSFILE or default pgpass is available. Asked owner for
a secure local credential source for the local postgres maintenance database.
PostgreSQL service is running. No password requested in chat; no credential read
or logged. No database connection, mutation, new test DB/role or cleanup needed.

Next: obtain credential source; run the prepared owned-listing test to observe
its expected failure, then implement one service/HTTP/PostgreSQL slice at a time.
Finish cancellation/rescheduling/retry preservation, migration/permissions, race
coverage, contracts and full required local regression. Code review remains due
after implementation. All criteria remain unverified; hosted CI/phase exit pending
separately approved commit/push and exact-SHA verification. No commit/push/Phase 3.


## 2026-10-17 verified local handoff — hosted acceptance pending

First nine criteria verified locally; hosted criterion remains unchecked. Status
is ready-for-human for Git review, not resolved. Implemented owned bounded cursor
listing/filters, separate change reviews, confirmed atomic cancellation and
same-appointment rescheduling, inclusive cutoff (including lock waits), current
fee/version checks, historical audit and immutable booking/change retry results.
0007_management backfills existing responses before enabling changes; cancelled
rows/identity stay immutable and active-slot capacity remains database-enforced.

Complete local gate passed on baseline f35e7472f57eb5ba923744cebb0ed37353b9f4d5
with working changes: 119 offline/unit + 119 PostgreSQL + 15 serial CI = 253 unique
passing tests, zero failures/errors/skips. PostgreSQL includes all 37 management
cases, prior booking/auth/fixture/catalog/scheduling/readiness regressions, five
independent-connection management races, injected rollback, restricted-role HTTP
operations, cross-doctor fee history, midnight/UTC cutoff and target-start expiry.
Ruff format/lint, strict mypy (59 sources), pip check and whitespace checks passed.
Offline inventory: seven pending, none executed, null quality pass rate; no AI
behavior was evaluated or changed. Reused the existing infrastructure gate with
all current tests, without expanding its reported Phase 1 infrastructure label.

Actual commands and evidence are retained in test-results/management-phase2-local.json
and its evidence directory; management-verification.json consolidates local-only
results, and management-attempts.json preserves earlier failed/skipped attempts
without double-counting reruns. Initial listing, absent change routes, origin and
target-start expiry failures were fixed; focused reruns and the final full gate
passed. The backfill attempt named red passed initially. Existing TestClient
deprecation remains; prior test-only connection/DDL allowances are unchanged.

Final separate maintenance-catalog safety audit passed: no test databases or
temporary booking/catalog/auth/schedule roles remain; careflow_ai OID 16388 and
counters 1498/91/21 match before/after. No connection to/migration/reset/mutation
of careflow_ai occurred. Removed encrypted credential, setup/runner/regression/
safety helpers, safety bytecode and generated gate temporary directories; verified
absence and unset verification-shell DATABASE_URL/TEST_DATABASE_URL. No permanent
credential storage added. Source hashes match all 59 Python files used by the gate.

Review: Standards zero findings. Spec review's stale endpoint/actor table fixed
and independently rechecked clear. Full changed-file manifest is in PROGRESS.md.
Next: owner reviews the code/documentation diff; separately approve any commit
and push, then verify Actions for that exact SHA before resolving Ticket 04 or
claiming Phase 2 exit. No commit, push, hosted run or Phase 3 work occurred.
