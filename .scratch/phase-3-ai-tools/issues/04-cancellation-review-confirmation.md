# 04: Chat-assisted cancellation review and confirmation

**What to build:** A patient selects their appointment, reviews its backend
cancellation proposal and separately confirms cancellation without bypassing
ownership, cutoff or retry rules.

**Blocked by:** 03 — Booking review and separately confirmed execution.

**Status:** ready-for-agent

**Approval gate:** Individual implementation approval required; paid runs,
commits and pushes each require separate explicit approval.

## Scope and contracts

Follow the shared Phase 3 spec. Extend 03's review/outcome integration with
propose_cancellation. Reuse owned listing, existing management proposal and
confirmation services plus immutable retry/audit snapshots. 05 is not a blocker.

## Acceptance criteria

- [ ] Select an owned appointment using current scoped data; ambiguous matches need clarification. Foreign/invented IDs and context cannot change patient/clinic authority or disclose another patient's existence.
- [ ] Proposal returns exact source/action/expiry review, without cancellation or capacity release. Proof/CSRF/session/retry keys stay out of provider context, stored conversation text and traces. Extend strict schemas/output validation without exposing confirm_cancellation.
- [ ] Separate authenticated HTTPS/origin/CSRF user confirmation uses the issued action/path-bound proof at the existing endpoint. Missing/forged/wrong-actor/wrong-action/stale/consumed/expired proof, chat consent and direct model calls cannot mutate.
- [ ] Preserve inclusive 24-hour cutoff and reject less at proposal and confirmation after waits; reject past/cancelled/ineligible sources. Existing service atomically commits cancellation/capacity release/proof/retry/history; no transaction spans provider calls.
- [ ] Preserve exact 24-hour authenticated key replay, mismatch conflict and expired-key rejection. Ambiguous transport or model failure cannot imply cancellation, trigger a new key or recancel a consumed action. Deterministic committed outcome survives provider failure.
- [ ] Strict TDD plus disposable PostgreSQL HTTP/tool/service tests inspect appointment/capacity/audit under permissions, CSRF/session, stale versions, exact cutoff boundaries and rollback. Independent connections cover duplicate confirmations/retries, cancellation versus reschedule and reset/logout versus confirmation.
- [ ] Real-path mocked positive/ambiguity/foreign-scope/bypass/stale-review/failure evals inspect actual state and reject invented success. Compare with 03 baseline and retain all applicable earlier behavior; label any separately approved live runs accurately.

## Verification and completion

Run applicable format/lint/types, auth/management/booking permission/concurrency/
idempotency regression, real PostgreSQL integration and affected evals. Provide
backend-only synthetic review/confirmation evidence, commands/results and baseline
deltas. Update contracts, ticket/progress and material decisions; required missing
checks or failures block completion.

## Out of scope

Reschedule tool implementation, new cutoff/retention rules, richer patient
records, staff writes, frontend, RAG and handoff queue.

## Comments

Provider revision changes proof-exclusion and protocol-failure assertions only.
Dependency stays 03; 05 may start independently after 03 resolves.
