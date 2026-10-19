# 05: Chat-assisted rescheduling review and confirmation

**What to build:** A patient chooses a real target slot, reviews its current fee
and explicitly confirms an atomic move of the same appointment; failure leaves
the original booking intact.

**Blocked by:** 03 — Booking review and separately confirmed execution.

**Status:** resolved

**Approval gate:** Individual implementation approval required; paid runs,
commits and pushes each require separate explicit approval.

## Scope and contracts

Follow the shared Phase 3 spec. Reuse 03's action integration, owned listing,
availability and management proposal/confirmation services. Add propose_reschedule;
ordinary model output cannot call confirm_reschedule. 04 is not a prerequisite.

## Acceptance criteria

- [x] Resolve an owned source and real bounded future target through current services. Clarify ambiguity/absent slots; reject foreign/invented/same-slot targets without mutation. Preserve offset/timezone/decimal contracts.
- [x] Proposal contains exact source/target doctor/local time/timezone, current target PKR fee and expiry, including unchanged fee. It neither moves source nor holds target. Raw proof/CSRF/session/retry keys never enter provider context, conversation text or traces.
- [x] Separate authenticated HTTPS/origin/CSRF user request confirms issued action/path-bound proof with original idempotency key. Model assertions, forged receipts and authority fields cannot confirm. Changed review requires fresh proposal and explicit confirmation.
- [x] Preserve inclusive source 24-hour cutoff and five-minute/slot-start proof boundaries, rechecked after locks. Existing transactions revalidate source version, target capacity/eligibility/fee/versions and scope. No locks span model calls.
- [x] Successful move updates the same appointment, preserving before/after slot/fee history and atomic state/proof/retry/audit. Target conflict, stale review or rollback cannot expose intermediate source release or imply a completed move.
- [x] Preserve authenticated exact 24-hour response replay, mismatch and consumed/expired-key errors. Ambiguous failure never generates a new key; committed outcome stays available without model narration. Original replay snapshot and current state are distinguishable.
- [x] Strict TDD and disposable PostgreSQL HTTP/tool/service tests inspect actual source/target capacity/audit under permissions, CSRF/session, exact cutoff, fee/version changes and rollback. Independent connections cover target contention, opposite moves, same-key/different-key proof races, cancellation versus reschedule and reset/logout.
- [x] Real-path mocked positive/ambiguity/phantom-target/stale-fee/bypass/provider-failure evals use executable state graders. Compare against 03 baseline and 04 if already completed, without adding a false dependency. Separately approved live evidence remains distinct.

## Verification and completion

Run applicable format/lint/types, auth/management/booking permission/concurrency/
idempotency regression, real PostgreSQL integration and affected evals. Provide
backend review/confirmation/move/replay evidence and failed-target preservation.
Update contracts, ticket/progress and material decisions with commands/results
and baseline deltas; required missing checks/failures block completion.

## Out of scope

Cancellation tool implementation, new pricing/scheduling/cutoff rules, staff
writes, frontend, RAG, payments, notifications and new retention infrastructure.

## Comments

Provider revision adds proof exclusion and continuation/failure assertions.
Dependency remains 03, not 04.

## Implementation and verification - 2026-10-19

Owner approved implementation and all four TDD seams. Proposal-only chat adapter
reuses existing management review/confirmation with protected original actions,
proof-free history, exact target fee/versions and separate authenticated user
confirmation. No domain policy/schema/transaction/endpoint change.

Final normal-host PostgreSQL: 247 passed in 1541.08s, exit 0, no failures/skips,
no new disposable databases left. Full offline/backend/eval/CI: 270 passed in
160.83s, exit 0, no failures/skips. Ruff format/check, strict mypy (96 files),
pip check passed. Real-path scripted rescheduling evals 10/0; prior booking 8/0,
cancellation 8/0, context 8/0 and catalog 13/0 with 2 pending unchanged. Independent
Standards/Spec reviews: zero actionable findings. Focused red/green, intermediate
runner/environment failures and exact final evidence paths are in
[PROGRESS](../../../docs/PROGRESS.md) and
[review contracts](../../../docs/BOOKING_CHAT.md).

No paid/live call, staging, commit, push, hosted exact-SHA CI, Ticket 06 or combined
Phase 3 exit. Ready for owner Git review; no implementation blocker remains.
