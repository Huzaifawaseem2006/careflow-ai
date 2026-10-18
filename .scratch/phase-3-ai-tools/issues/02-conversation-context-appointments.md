# 02: Owned conversation context and appointment lookup

**What to build:** A patient follows up in a server-owned conversation and views
only their own appointments; disclosed history remains isolated, bounded and
deletable. Guests retain public-only access under defined ownership.

**Blocked by:** 01 — Grounded catalog chat and real-path eval baseline.

**Status:** resolved

**Approval gate:** Owner approved Ticket 02 and the concrete D10 mechanics/four
TDD seams on 2026-10-18, before tests/content persistence implementation. The
[approved mechanics](../d10-mechanics-review.md) resolve the earlier guest,
transfer, purge and exception questions. Owner subsequently authorized exactly
one scoped implementation commit and normal push after final review. Paid calls,
additional commits and later tickets remain unauthorized.

## Scope and contracts

Follow the shared Phase 3 spec. Reuse server-managed sessions, persisted patient/
clinic scope and stable bounded cursor/status/date listing. Add minimum owned
conversation/message storage, native migrations/readiness and runtime privileges.
Recommend isolated guest ownership without automatic transfer for D10 review.

## Acceptance criteria

- [x] Record approved D10 mechanics before storing content. Disclosure precedes storage; ownership derives from live auth or defined guest proof, never a bare conversation ID. Specify logout/reset, guest expiry and sign-in transitions, with no implicit guest-to-patient transfer unless approved.
- [x] PostgreSQL migration constraints/runtime grants enforce conversation/message integrity and least privilege; readiness advances. Chat deletion does not delete appointment/proof/retry/audit records; no staff access or new retention exceptions.
- [x] Bounded follow-ups load ordered history server-side. Reject spoofed assistant/tool roles and cross-patient/clinic/guest IDs with non-enumerating errors. get_my_appointments reuses scoped cursor/status/date filters; model args/history cannot supply identity.
- [x] Concurrent turns cannot interleave or duplicate history/tool effects. Tested finite lease/version or equivalent ordering uses no DB transaction across model calls. Define retries, abandoned turns and deletion versus in-flight completion so deleted history cannot reappear.
- [x] Context truncation preserves complete call/result pairs and re-reads volatile facts. Anthropic continuation/thinking stays behind the provider seam, private and bounded, without unnecessary persistence. Revalidate expired/revoked sessions before private access and result release, including after waits.
- [x] Approved 30-day expiry, owned deletion and actual purge have boundary tests and an operator-verifiable native path. Disclose purge timing and provider retention independently; local deletion makes no Anthropic-deletion promise. No handoff/audit exception is inferred.
- [x] HTTPS/origin/CSRF for state storage, safe guest controls, body/rate/context limits and no-store private responses cover new routes. Keys, cookies, proof, CSRF and unnecessary history stay out of provider context/logs.
- [x] Strict TDD plus real disposable PostgreSQL tests inspect actual state under ownership failures, reset/logout, concurrent/retried turns and deletion races with independent connections. Cover guest/patient/clinic isolation, migrations, cleanup and idempotency semantics.
- [x] Versioned real-path multi-turn/ownership/history-injection evals use executable graders, compare to 01 baseline and preserve held-out separation. Scripted results are not live model quality.

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

2026-10-18: Owner selected Ticket 02 for this fresh implementation session,
explicitly excluding commit/push and any other ticket. Clean baseline `3acce71`.
Inspected existing single-turn chat/provider, session ownership/rotation and
appointment listing interfaces. Concrete D10 mechanics and TDD seams are proposed
in [the mechanics review](../d10-mechanics-review.md); approval is pending.
No application/test implementation or content persistence has occurred.

Owner subsequently replied `approved` to all D10 mechanics and four TDD seams,
before application/test implementation. See [current contracts](../../../docs/CONVERSATIONS.md).
The prior pending-review statements above describe the earlier checkpoint only.

Provider revision adds continuation isolation and separate retention disclosure.
Dependency remains 01; D10 is a decision gate, not a new infrastructure ticket.

Completion verified 2026-10-18: full disposable PostgreSQL suite **151 passed in
901.49s**; full backend/eval/CI suite **224 passed in 232.45s**, independently
checked JUnit has zero failures/errors/skips. Final report-only follow-up test
**1 passed in 37.10s** (overlaps the full integration suite), with **8/8** new
mocked context cases and unchanged **13 passing/2 pending** catalog-only baseline.
The catalog runner does not execute private/booking seeds; this ticket verifies
private ownership through its separate real HTTP/context tests. No live quality
claim follows. Both final DB runs reported no new disposable databases remaining.
Ruff format/check, strict mypy (80 files), pip check, dataset checksum/LF and local
link checks pass. Standards/Spec reviews have zero open findings after correcting
the history grader. See docs/PROGRESS.md and docs/CONVERSATIONS.md for evidence,
runtime grants and operator purge obligations. No staging/commit/push, paid call,
main demo database migration or later ticket implementation occurred.

Owner subsequently approved final scoped Git review and exactly one commit
`feat: add owned chat history and appointment lookup`, followed by normal push
to `origin/master` if review passes. Both review axes have zero actionable
findings. Fresh maintenance-catalog verification found zero disposable test DBs.
See the latest progress entry; actual final commit/ref/hosted exact-SHA status is
recorded in ignored `test-results/ticket02-git-ci.json` after execution. No second
tracked documentation commit, later ticket or paid call is authorized.
