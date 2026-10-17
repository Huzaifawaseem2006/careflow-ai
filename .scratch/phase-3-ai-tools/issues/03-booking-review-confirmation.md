# 03: Booking review and separately confirmed execution

**What to build:** A patient finds a real slot, reviews the exact backend proposal
and separately confirms it, receiving one persisted booking despite retries,
contention or model failure.

**Blocked by:** 02 — Owned conversation context and appointment lookup.

**Status:** ready-for-agent

**Approval gate:** Individual implementation approval required; each paid run,
commit and push requires separate explicit approval.

## Scope and contracts

Follow the shared Phase 3 spec. Reuse persisted availability, booking proposals
and existing confirmation HTTP/domain services. Add get_available_slots and
propose_booking plus the shared typed review/outcome integration needed by 04/05.
No new confirmation endpoint or authorization system is needed. Forward auth/CSRF
outside model messages; proposals persist proof but reserve no capacity.

## Acceptance criteria

- [ ] Availability uses persisted future active free slots, offset-aware half-open ranges, bounded pages and the approved 30-date Karachi horizon. Clarify missing/ambiguous doctor/date/time or empty results instead of inventing slots, IDs or intent.
- [ ] propose_booking checks live patient/clinic scope and returns the exact server doctor/local time/timezone/PKR fee/expiry review. No booking or hold exists yet; stale history cannot override current service facts.
- [ ] Protected action transport carries issued proof and exact review; raw proof/cookies/CSRF/retry keys stay out of Anthropic requests, conversation text and traces. Malicious schema-shaped provider output cannot inject proof/modify summaries. Stop after review issuance to avoid duplicate proposals.
- [ ] A distinct user request confirms through the existing appointment endpoint with issued proof and Idempotency-Key, authenticated HTTPS/origin/CSRF. No ordinary confirm_booking tool. Chat yes, confirmed=true, client receipts and patient/clinic/price/role assertions cannot write.
- [ ] Preserve five-minute/slot-start expiry, fresh review on changed fee/version/eligibility, single active capacity and atomic appointment/proof/retry/audit. Existing services revalidate session/scope/state inside transactions; no locks span model calls.
- [ ] Exact authenticated actor/action/key/request retries replay the immutable result for 24 hours; mismatch, new-key consumed-proof replay and expired retry keys retain existing errors. Ambiguous timeout keeps original proof/key for authorized retry, never invents a new action or successful result.
- [ ] Committed backend outcome remains available if the provider fails afterward. Reconcile later status through authorized domain state or exact replay, not client transcripts. Distinguish replay snapshots from current appointment state.
- [ ] Strict TDD and real PostgreSQL HTTP/tool/service tests cover guest/foreign/revoked access, origin/CSRF, forged/stale/expired proof, phantom slots, changed fee, rollback and actual no-write-before-confirmation. Independent connections cover slot contention, retry/proof races, maintenance changes and reset/logout; inspect capacity/audit/state.
- [ ] Real-path positive/adversarial/failure evals and executable state graders verify that scripted confirmation requests cannot mutate. Compare with 02 baseline; any approved live runs are separately labeled and charged to the cumulative USD 5 ceiling.

## Verification and completion

Run applicable format/lint/types, HTTP/provider-contract, auth/booking permissions,
concurrency/idempotency, real PostgreSQL integration/migration regression and
affected evals. Show a backend-only synthetic search -> review -> separate
confirmation -> committed result/replay walkthrough. Record commands/results,
document shared action/error/reconciliation contracts for 04/05 and update
ticket/progress/material decisions. Required failures/missing checks block closure.

## Out of scope

Cancel/reschedule implementation, direct model confirmation, new booking policy,
staff writes, RAG, frontend, payments, notifications and deployment.

## Comments

Provider revision adds proof-exclusion and failure-after-commit assertions.
Dependency remains 02; this establishes shared action integration for 04/05.
