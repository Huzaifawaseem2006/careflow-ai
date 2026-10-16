# 03: Appointment Booking

**What to build:** A signed-in synthetic patient reviews an actual slot/current fee, explicitly confirms a server proposal, and receives exactly one persisted booking under contention or retries.

**Blocked by:** 02 — Schedules & Availability (transitively 01).

**Status:** ready-for-agent

**Approval gate:** Individual implementation approval and D04/D12 booking schema/transport approval required. Commit/push each need separate approval.

## Scope and existing infrastructure

Implement PRD FR-03/FR-04 using persisted slots, catalog, patient sessions and real PostgreSQL. Add appointments, actor/action/payload-bound expiring proposals, scoped mutation idempotency and minimal transactional redacted audit. Reuse identity/origin/CSRF rules; make narrow helper changes to revalidate identity inside the mutation transaction. Current patient identity DTO lacks clinic scope: derive it from persisted patient/persona relationships. Do not create a general authorization framework or staff authentication.

## Acceptance criteria

- [ ] Record approved D04 expiry/retention/retry rules and D12 schema/HTTP mappings. Migrations enforce one active booked appointment per slot and consistent patient/doctor/slot/clinic references; readiness advances.
- [ ] Proposal endpoint validates server-resolved patient/scope, active doctor and actual future available slot; returns exact doctor/time/timezone/PKR fee/expiry summary. It creates no appointment and reserves no slot.
- [ ] A separate same-origin CSRF-protected confirmation request binds opaque proposal and idempotency key to the displayed action. Reject missing proof, forged authority fields, expired/wrong-actor/wrong-operation/consumed proposals and changed payload. Model output or `confirmed=true` grants no authority.
- [ ] Recheck account/session validity, clinic scope, resource versions, schedule/exception/slot availability and displayed fee in the transaction. Changed fee/state requires a new proposal/review. Persist immutable accepted fee/currency.
- [ ] Stable lock ordering is compatible with reset/logout and schedule edits. Appointment, proposal consumption, idempotency result and audit commit atomically; return persisted state after commit. Injected failure leaves no partial action.
- [ ] Same actor/operation/key and exact-request retry returns the prior booking after authentication, without duplicate action/audit. Changed payload conflicts; a new key cannot replay consumed proof. Concurrent same-key and post-retention behavior are explicit.
- [ ] Independent-connection same-slot contention produces one active booking and safe losing responses. Complete 02's booked-state integration: booked slots disappear from availability and conflicting edits cannot silently move/invalidate appointments.
- [ ] Appointment writes have bounded transport coverage (existing middleware only bounds auth), private responses are no-store, and safe errors/audit/logs omit tokens, cookies, credentials and unnecessary patient data.
- [ ] HTTP walkthrough uses existing synthetic login to obtain proposal, confirm and verify persisted result/retry without frontend or AI adapters.

## Risk-based TDD and regression

Strict red/green TDD for identity/scope, confirmation, pricing, rollback and idempotency. Cover guests, expired/revoked sessions, disabled accounts, cross-patient/clinic access, invented IDs, malformed/extra fields, origin/CSRF failure and stale proposals. Independent PostgreSQL connections test different-patient same-slot contention, simultaneous same-key retries, different keys sharing proof, booking versus schedule/exception/fee edits, and reset/logout versus booking. Assert actual persisted state/audit, migration constraints and cleanup, not just responses.

Run applicable format/lint/types; affected auth permission/concurrency/idempotency/integration suites; booking/catalog/schedule/availability tests; migration/readiness/fixture regression. AI evals are inapplicable absent AI changes; do not add AI surfaces here.

## Out of scope

Listing/cancel/reschedule APIs (04), staff appointment writes, UI/AI confirmation adapters, payments, notifications, production recovery, real patients and new infrastructure.

## Completion

Executed evidence must verify every criterion; PostgreSQL skips, unauthorized/unconfirmed writes, duplicates or partial transactions block resolution. Update contracts/approved decisions, ticket/progress and schema status; hand off proposal/locking/retry rules to 04 in a fresh session. No commit/push without separate approval.
