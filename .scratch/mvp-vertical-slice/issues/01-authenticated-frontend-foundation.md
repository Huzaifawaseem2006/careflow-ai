# 01: Authenticated frontend foundation

**What to build:** A synthetic patient can sign in through the local HTTPS
interface, accept the storage disclosure, create or resume their own saved chat
and sign out. This is a working authenticated browser slice, not a static mockup.

**Blocked by:** None (ticket dependency frontier; individual implementation
approval is still required).

Status: resolved

## Scope and reuse

Follow the approved [MVP PRD](../../../plans/mvp-vertical-slice/PRD.md) and
[implementation plan](../../../plans/mvp-vertical-slice/IMPLEMENTATION.md).
Reuse existing CSRF bootstrap, login/current-user/logout, conversation
creation/history/turn/deletion, ownership, retention and disclosure contracts.
Add only the minimal Next.js/TypeScript/Tailwind interface and trusted local HTTPS
forwarding needed to exercise those services. The existing v1 conversation path
is sufficient for this ticket; v2 and citations belong to Ticket 03. My Appointments
navigation may exist, but its working content belongs to Ticket 04.

No prefactor is required: existing service and provider seams are sufficient.
No backend authorization redesign, guest UI, registration, recovery or streaming.

## Acceptance criteria

- [x] Sign-in, current-session recovery and logout work against the existing real
  backend and synthetic provisioned account. Passwords and tokens are never logged.
- [x] The browser uses one HTTPS origin; an allowlisted API proxy connects to
  HTTPS loopback FastAPI. Certificates are verified at both hops, including the
  Node-to-backend connection. Document certificate trust without committing keys.
- [x] Preserve original browser Origin, secure HttpOnly cookie, CSRF and no-store
  behavior. No permissive CORS, insecure-cookie or TLS-verification bypass is used.
- [x] No chat/history is available in the MVP interface before sign-in. Backend
  session/ownership checks remain authoritative even when the UI is bypassed.
- [x] Present the backend storage disclosure and obtain explicit acceptance before
  conversation creation. Resume owned history without inventing a new ownership,
  transfer or retention mechanism; no multi-conversation manager is required.
- [x] An authenticated patient can submit a turn and view the server response.
  Deterministic tests may script only the external provider and must say so.
- [x] Patient B cannot read patient A's conversation. Foreign Origin, invalid CSRF,
  missing/revoked/expired session and logout-in-flight fail safely through the proxy.
- [x] Clear protected UI state on logout/session expiry; show useful loading,
  validation, unavailable and expiry states. Forms are labelled, keyboard usable
  and responsive. No protected responses enter static or service-worker caches.
- [x] Reserve space for the separate Voyage processing supplement without claiming
  terms were verified or embedding anything before Ticket 03's v2 integration.
- [x] Required checks pass with execution evidence, and changes remain inside this
  slice. No later ticket is silently implemented to make a screenshot look complete.

## Testing requirements

Use the browser -> real same-origin HTTPS proxy -> FastAPI -> disposable PostgreSQL
boundary. Script external provider HTTP for turn tests; do not mock sessions,
authorization or stored history. Verify independently that consent precedes writes
and isolation survives direct API requests. Reuse existing auth/conversation
integration coverage. Strict TDD applies to authorization/private-data changes;
confirm any new high-risk test boundary before implementation.

Run frontend type/lint/build checks, focused browser/auth/conversation checks and
applicable real PostgreSQL permission tests. Use the established PostgreSQL runner
and its private-temp/normal-host recovery and redaction rules. Run PostgreSQL/CI
subprocess suites serially in an idle checkout. External calls are disabled by
default; no live call is necessary for this ticket's mechanical verification.

## Completion evidence and handoff

Record source revision/diff, actual commands, test counts/skips, certificate trust
setup, isolation/origin/CSRF outcomes and redacted screenshots. Document remaining
provider/corpus gates honestly. Update progress after verification stabilizes;
never label a scripted chat as hosted-model quality. Hand off Ticket 01 only;
Ticket 04 becomes dependency-ready after this ticket resolves.

## Approval boundaries

Publication is planning only, not implementation approval. Obtain separate Ticket
01 approval before code/dependency/certificate-store changes. Corpus/indexing and
external calls are outside this ticket. Every branch, commit and push retains its
reserved approval; do not start another ticket automatically.

## Comments

Publication snapshot: published from the owner-approved five-slice plan on
2026-10-23. No implementation or verification had been executed at publication.

Implementation verified 2026-10-23 after owner approval of both TDD seams. See
[the execution ledger](../../../docs/PROGRESS.md) and
[local HTTPS setup](../../../docs/FRONTEND.md). All 15 browser cases pass; backend
foundation has 320 passes. Full PostgreSQL had 297 passes and one interrupted
login failure; the unchanged three-case function passed on retry after access
validation. CI had 14 passes/one timeout, followed by an unchanged passing retry.
Initial failures and numeric timings are retained; no limits or scope were reduced.
No backend runtime changes, later tickets, external AI calls, commits or pushes.
