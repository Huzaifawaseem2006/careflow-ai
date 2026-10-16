# 04: Appointment Management & Regression

**What to build:** Patients list only their appointments and explicitly confirm safe cancellation/rescheduling under the 24-hour policy; complete Phase 2 backend regression evidence is recorded.

**Blocked by:** 03 — Appointment Booking.

**Status:** ready-for-agent

**Approval gate:** Individual implementation approval; resolve D12 change contracts, exact cutoff boundary and reschedule fee policy before implementation. Commit/push each need separate approval.

## Scope and existing infrastructure

Implement PRD FR-03/FR-05 on existing booking transactions, session security, slots, proposals/idempotency/audit and migration infrastructure. Add bounded owned listing and cancel/reschedule proposal plus confirmation endpoints. Reuse booking's mechanism, without a second workflow engine. Complete phase regression; hosted evidence may await separately authorized Git actions.

## Acceptance criteria

- [ ] Owned listing provides bounded stable pagination/order and documented status/date filters, persisted doctor/local time/timezone/state/accepted fee. No foreign-patient/clinic records or private metadata leak across pages.
- [ ] Change proposals validate owned active booking, clinic scope, policy and target slot; return exact review summaries without changing booking/capacity. Each mutation requires its own separate confirmation request.
- [ ] Enforce 24 hours before the current appointment start using server time at proposal and confirmation, including elapsed review time. Test the owner-approved exact boundary. Cancelled/past bookings and same-slot/no-op targets have documented safe behavior.
- [ ] Cancellation atomically marks cancelled, releases capacity, consumes proposal and records retry result/audit, preserving history/accepted fee. Exact authenticated retry returns prior result; fresh actions cannot reuse proof.
- [ ] Reschedule locks appointment/source/target slots in stable order and atomically updates the same owned appointment plus audit/retry/proposal. Failed/unavailable/stale target preserves original booking/capacity. Review/recheck target price under approved policy; audit retains prior price/slot history.
- [ ] Missing/expired/mismatched proof, wrong actor/operation, changed payload, revoked identity, CSRF/origin failure and cross-clinic access neither mutate nor disclose private data. Reuse bounded writes, no-store responses and safe errors.
- [ ] Independent-connection races cover cancel versus reschedule, two reschedules, target booking contention, target schedule edit and same-key retries. Persisted outcomes preserve capacity one, complete moves, consistent availability/history and no duplicate action/audit.
- [ ] HTTP scenario demonstrates login, catalog/availability, booking, own listing, cancellation, another booking and rescheduling with persisted IDs/explicit confirmations. Ownership/cutoff negatives demonstrate rejection.
- [ ] Full applicable local regression passes with no required skips: format/lint/types, foundation/backend/eval-infrastructure tests, all PostgreSQL integration and serial CI regressions. Record commands, revision, counts and disposable-resource cleanup. Preserve Phase 1 auth/fixture/readiness behavior and offline inventory semantics. Any minimal gate extension rejects failed/missing/skipped evidence.
- [ ] Following separately approved commit/push, verify hosted Actions for the exact reviewed SHA at the phase milestone. Hosted offline CI does not replace PostgreSQL evidence. If authorization/evidence is pending, report local results separately and keep hosted criterion/phase exit pending.

## Risk-based TDD and integration

Strict red/green TDD for private listing, ownership, policy, confirmation and transactions. Test just below/exactly/above 24 hours, UTC/local rollover, cutoff crossed during review, stale versions, fee changes and cancelled/invalid targets. Cover cross-user/clinic pagination leakage, guest/expired/reset sessions and forged authority fields. Verify constraints, failure-injection rollback, payload conflicts/retention and independent-connection races on PostgreSQL. Re-run booking concurrency/auth idempotency/security regression; mocked races are insufficient.

No AI changes are planned. Run offline inventory as infrastructure regression, preserving seven pending behavioral cases and null quality pass rate. Only if AI surfaces change, run affected evals against baseline and distinguish mocked/live results.

## Out of scope

Phase 3 AI/tools, Phase 5 frontend/staff authentication/dashboard, broad staff CRUD, reminders, payments, deployment, real patients, new infrastructure and production-hardening projects.

## Completion

Verify every acceptance criterion before `resolved`; critical auth/booking/policy failures and required database skips block completion. Update contracts, meaningful approved decisions, ticket/progress and phase milestone with actual evidence/pending hosted status. Show documentation before separately approved commit/push. Recommend Phase 3 planning/approval in a fresh session only after Phase 2 exit; do not begin it here.
