# 02: Schedules & Availability

**What to build:** Guests query real persisted slots generated from doctor schedules and blocking exceptions; an explicitly confirmed local operator maintains synthetic schedules safely.

**Blocked by:** 01 — Clinic Catalog.

**Status:** ready-for-agent

**Approval gate:** Individual implementation approval and D03 horizon/time/edit policy approval required. Commit/push each need separate approval.

## Scope and existing infrastructure

Implement PRD FR-02 using the catalog, clinic timezone, migrations/readiness and disposable PostgreSQL harness. Add effective weekly schedules, exceptions and persisted slots. Provide a bounded confirmed local operator maintenance/generation path following existing CLI target guards; no staff HTTP authority exists yet. Establish compatible doctor/schedule/slot locking and resource versions for booking. Appointment-dependent queries wait until 03 creates appointments; no scheduler is needed.

## Acceptance criteria

- [ ] Record approved D03 horizon, query bounds, local-time/DST interpretation and edit policy. Recommendations in the phase plan are not existing approvals.
- [ ] Effective schedules generate deterministic, non-overlapping 30-minute capacity-one slots within the approved horizon. UTC instants round-trip to `Asia/Karachi`; responses include timezone/offsets.
- [ ] Repeated/concurrent generation creates no duplicate/overlapping intervals. Constraints and transactional validation enforce positive exact duration, references and uniqueness; shifted schedule starts cannot bypass overlap protection.
- [ ] Confirmed edits/exceptions atomically invalidate affected unbooked slots and version stale resources. Establish the contract rejecting edits affecting booked appointments; 03 completes/tests actual appointment integration.
- [ ] Public availability returns only persisted active future unblocked slots, with bounded validated ranges and clinic scope. Empty results remain empty; inactive/missing/cross-clinic doctors expose no slots or patient data. GETs never generate slots.
- [ ] Operator writes refuse missing confirmation/unsafe targets, serialize competing edits/generation and roll back fully on failure. No public schedule mutation endpoint exists.
- [ ] Migration/repeat/readiness checks and an operator-generation-to-HTTP-query walkthrough pass independently of booking/frontend/AI.

## Tests and verification

Strict TDD for overlap/concurrent-write integrity; focused tests for query formatting. Cover local midnight/weekday/effective-date edges, horizon boundaries, invalid/offset-free inputs, exceptions, shifted overlaps, repeated generation and clinic isolation. Independent PostgreSQL connections test edit/generation races, constraints and rollback; SQLite is insufficient. Run applicable format/lint/types, unit/HTTP/PostgreSQL and catalog/fixture/readiness regression. Report booking-aware coverage as deferred to 03, not passed here.

## Out of scope

Reservations/booking, proposals/idempotency, patient history, variable slot lengths, recurring patient bookings, staff auth/HTTP/UI, background jobs, frontend and AI tools.

## Completion

Verify acceptance with executed evidence and no required database skips. Update contracts, approved D03 choice, ticket/progress and schema status. Hand off locking/version rules and deferred booking integration to 03; do not start it or commit/push without separate approval.
