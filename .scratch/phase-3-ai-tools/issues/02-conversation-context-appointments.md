# 02: Owned conversation context and appointment lookup

**What to build:** A patient follows up in a server-owned conversation and views
only their own appointments; disclosed history remains isolated, bounded and
deletable. Guests retain public-only access under defined ownership.

**Blocked by:** 01 — Grounded catalog chat and real-path eval baseline.

**Status:** ready-for-agent

**Approval gate:** Individual implementation approval and D10 mechanics review
before content persistence. Owner reaffirmed disclosed PostgreSQL history,
bounded context, serialized turns and the 30-day direction; exact guest ownership/
transfer, purge timing/trigger and exceptions were not settled. Present those
choices early, without inventing approval. Each paid run/commit/push is separate.

## Scope and contracts

Follow the shared Phase 3 spec. Reuse server-managed sessions, persisted patient/
clinic scope and stable bounded cursor/status/date listing. Add minimum owned
conversation/message storage, native migrations/readiness and runtime privileges.
Recommend isolated guest ownership without automatic transfer for D10 review.

## Acceptance criteria

- [ ] Record approved D10 mechanics before storing content. Disclosure precedes storage; ownership derives from live auth or defined guest proof, never a bare conversation ID. Specify logout/reset, guest expiry and sign-in transitions, with no implicit guest-to-patient transfer unless approved.
- [ ] PostgreSQL migration constraints/runtime grants enforce conversation/message integrity and least privilege; readiness advances. Chat deletion does not delete appointment/proof/retry/audit records; no staff access or new retention exceptions.
- [ ] Bounded follow-ups load ordered history server-side. Reject spoofed assistant/tool roles and cross-patient/clinic/guest IDs with non-enumerating errors. get_my_appointments reuses scoped cursor/status/date filters; model args/history cannot supply identity.
- [ ] Concurrent turns cannot interleave or duplicate history/tool effects. Tested finite lease/version or equivalent ordering uses no DB transaction across model calls. Define retries, abandoned turns and deletion versus in-flight completion so deleted history cannot reappear.
- [ ] Context truncation preserves complete call/result pairs and re-reads volatile facts. Anthropic continuation/thinking stays behind the provider seam, private and bounded, without unnecessary persistence. Revalidate expired/revoked sessions before private access and result release, including after waits.
- [ ] Approved 30-day expiry, owned deletion and actual purge have boundary tests and an operator-verifiable native path. Disclose purge timing and provider retention independently; local deletion makes no Anthropic-deletion promise. No handoff/audit exception is inferred.
- [ ] HTTPS/origin/CSRF for state storage, safe guest controls, body/rate/context limits and no-store private responses cover new routes. Keys, cookies, proof, CSRF and unnecessary history stay out of provider context/logs.
- [ ] Strict TDD plus real disposable PostgreSQL tests inspect actual state under ownership failures, reset/logout, concurrent/retried turns and deletion races with independent connections. Cover guest/patient/clinic isolation, migrations, cleanup and idempotency semantics.
- [ ] Versioned real-path multi-turn/ownership/history-injection evals use executable graders, compare to 01 baseline and preserve held-out separation. Scripted results are not live model quality.

## Verification and completion

Run applicable format/lint/types, HTTP/provider-contract, permission/concurrency/
idempotency, migration/readiness, real PostgreSQL and affected eval checks.
Document actual D10 approval, commands/results and baseline changes; update
contracts, ticket/progress and material decisions. Unapproved persistence
mechanics or required missing checks block the affected acceptance.

## Out of scope

Booking/proposals, frontend history browser, guest history merging, staff/handoff
storage, embeddings and production compliance or appointment/audit retention.

## Comments

Provider revision adds continuation isolation and separate retention disclosure.
Dependency remains 01; D10 is a decision gate, not a new infrastructure ticket.
