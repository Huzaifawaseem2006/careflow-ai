# 04: Conversational booking journey

**What to build:** A synthetic patient discovers a real doctor and persisted slot
through chat, reviews the exact booking details, explicitly confirms through the
protected operation and sees the committed appointment in My Appointments.

**Blocked by:** 01 — Authenticated frontend foundation.

Status: ready-for-agent

## Scope and reuse

Follow the approved [MVP PRD](../../../plans/mvp-vertical-slice/PRD.md) and
[implementation plan](../../../plans/mvp-vertical-slice/IMPLEMENTATION.md).
Reuse actual catalog/fee/availability tools, owned conversations, booking reviews,
separate protected confirmation, appointment listing, capacity/revalidation,
idempotency/audit and existing cancellation/rescheduling backend services.
No business-rule rewrite, new confirmation service or prefactor is required.
This journey works with v1 before retrieval is available; Ticket 03 is not a blocker.

## Acceptance criteria

- [ ] Doctor and slot discovery uses the actual custom AI loop and domain-tool
  results. Display readable/selectable actual results that continue conversation;
  clarify ambiguity. No fabricated slots, hardcoded booking script or fixture
  success response substitutes for real service data.
- [ ] Render the original live booking review with exact doctor, interval,
  Asia/Karachi timezone, PKR decimal fee and effective expiry. Explain no hold;
  display no executable control for a historical review marker.
- [ ] A distinct confirmation click uses the existing protected appointment
  endpoint, live session/CSRF, issued proof and one stable idempotency key.
  Chat yes/confirm messages and model output alone cannot mutate appointments.
- [ ] Keep raw proof/key in page memory and protected requests only, never browser
  persistent storage, URLs, transcripts, model context, logs, analytics or traces.
  Disable duplicate UI submissions while pending; backend idempotency remains
  authoritative when UI controls are bypassed.
- [ ] On ambiguous timeout, display uncertainty and retry only the same proof/key
  while retained. Do not auto-submit another mutation with a new key.
- [ ] Refresh/lost proof clears executable review state and reconciles through
  authorized My Appointments. Never automatically request and confirm a replacement
  booking; an absent list item cannot prove an in-flight request will not commit.
- [ ] Definitive stale/fee/slot/expiry rejection requires fresh review and another
  explicit confirmation. Auth expiry/logout invalidates protected UI state and
  cannot reuse cached authority.
- [ ] Show committed backend outcome independently of provider narration. Provider
  failure after commit cannot erase the appointment or create a false failure/
  success receipt. My Appointments uses actual owned state and survives refresh.
- [ ] Cancellation/rescheduling reviews show an unavailable-in-demo notice and
  no confirmation control; never route them through booking confirmation. Their
  existing backend functionality/authorization remains intact. UI restrictions
  are not security controls.
- [ ] Loading/empty/provider/auth/stale/uncertain states are understandable and
  keyboard accessible. No protected response/proof is cached or exposed in screenshots.
- [ ] Permission, concurrency, capacity, audit and retry invariants pass on real
  PostgreSQL. No unconfirmed mutation, duplicate booking or cross-user access is
  permitted in evaluated scenarios.

## Testing requirements

Use browser -> actual HTTPS proxy -> existing handlers/services -> disposable
PostgreSQL. Script only external provider responses in deterministic tests;
independently inspect state rather than trusting UI/transcript receipts. Reuse
booking/auth/conversation/management tests, including independent-connection races,
exact idempotency retries, stale resources and session revocation. Strict TDD
applies to booking/auth/private-data integration; preserve existing approved seams
and confirm any new high-risk boundary before implementation.

Run frontend type/lint/build and focused browser tests, affected frozen/eval cases
and real PostgreSQL permission/concurrency/idempotency regression serially using
the established runner. No test relies on fabricated domain facts. Any hosted
walkthrough is separately authorized and labelled; mocked provider success does
not establish live tool-selection quality.

## Completion evidence and handoff

Record commands, counts/skips, state assertions, race/retry outcomes, preserved
backend management coverage and redacted browser evidence. Show that review/chat
does not mutate and that confirmed state persists independently of the provider.
List unresolved external-evaluation gates and update progress after stabilization.
Ticket 05 remains blocked until Ticket 03 is also resolved. Do not label this
booking-only slice as the complete RAG portfolio demo.

## Approval boundaries

Publication is planning only; obtain individual Ticket 04 implementation approval.
No live calls without explicit provider/cases/cost authorization. No appointment
business-policy changes, extra management UI, branch, commit, push or later ticket
without the applicable approval.

## Comments

Published from the approved five-slice plan on 2026-10-23. No implementation,
appointment operation, browser execution or evaluation occurred in this ticket.
