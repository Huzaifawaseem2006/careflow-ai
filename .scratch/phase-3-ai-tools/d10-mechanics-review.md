# Ticket 02: D10 mechanics proposed for owner approval

Status: owner approved all mechanics and four TDD seams in this chat on
2026-10-18. That approval covered Ticket 02 implementation only. Subsequent
one-time Git approval is recorded in docs/PROGRESS.md; no paid calls or later ticket.

## Ownership and disclosure

- Reuse the existing secure HttpOnly session cookie and CSRF token. No new guest
  identity system. A conversation UUID alone grants no access.
- Guest conversations belong exclusively to the current anonymous prelogin
  session, whose existing lifetime is ten minutes. No sliding extension. Guests
  have public catalog tools only. Expired/revoked sessions cannot read or finish
  turns; removing the owning session deletes its guest history.
- Sign-in rotates the session as today and deletes its guest history; nothing
  transfers to the patient. Patient conversations belong to the persisted
  patient/clinic, and can resume through a new valid session for that same patient.
  Logout/password reset revoke access and invalidate in-flight release, but do
  not erase patient history; explicit deletion or retention expiry does that.
- Before content storage, expose a versioned disclosure through a non-storing
  endpoint. Conversation creation requires explicit acceptance of that version,
  valid session, origin and CSRF. Disclose synthetic-only use, local retention,
  guest transitions, deletion and separate provider retention. Existing public
  single-turn chat can remain available without persistent history.

## Retention and deletion

- Patient conversations expire exactly 30 days after creation, without extension
  on activity. Guest expiry is the earlier of that limit and session expiry.
  All access and completion paths enforce expiry immediately.
- Owner-scoped deletion immediately removes conversation content and turn/retry
  records in one transaction. Completion may only update an existing, unexpired
  conversation with its current lease/version; it cannot recreate a deleted row.
- Add a native bounded purge command with a dry-run/count mode, deleting expired
  history and abandoned expired guest history. Operators run it at least daily;
  physical cleanup happens on execution, not at a falsely promised automatic
  deadline. No scheduler infrastructure is added in this ticket. Document and
  test both access expiry and actual physical purge separately.
- No new staff/handoff/audit exceptions. Chat deletion/purge never deletes
  appointment, proposal, appointment retry or audit history. Local deletion does
  not delete provider copies; provider/account retention remains separate and
  unverified, as already documented. No paid provider calls are authorized.

## Turns, retries and context

- Use short database transactions and a finite 90-second exclusive turn lease
  (greater than the existing maximum 60-second provider timeout), with fencing
  against late completion. No transaction/lock spans a provider request.
- Require a client turn UUID. Completed exact retries return the recorded turn
  under current authorization, labeled as a historical response; they do not
  rerun tools. Changed content with the same UUID conflicts. Concurrent or still
  running retries return a bounded busy response. After lease expiry a retry can
  reclaim the same turn; stale workers cannot save or release a result.
- Persist completed user/server response pairs only; failed/abandoned turns leave
  no partial message pair. Retain minimal turn coordination metadata until
  conversation deletion/expiry. Do not persist SDK continuation or thinking.
- Load at most the newest 20 complete turns within a 32 KiB history budget and
  the existing total context budget; drop entire oldest pairs. Historical
  content is untrusted context, never authority. Re-read current appointments
  and other volatile facts; exclude historical private appointment result data
  from subsequent provider context. Revalidate session/scope at private access,
  turn completion and result release after waits.

## Approved TDD seams

1. HTTPS HTTP API with scripted external provider and disposable PostgreSQL:
   ownership, disclosure/CSRF, transitions, deletion, expiry, turn retries and
   races. Observe actual DB state where required by AGENTS/ticket; this does not
   measure live model quality.
2. Neutral chat/provider boundary: bounded ordered history, spoofing/injection,
   complete pairs, fresh private tool reads and safe failure. This cannot prove
   actual provider wire formatting.
3. Anthropic adapter with mocked HTTP transport: history/continuation protocol
   and secret exclusion. This cannot prove live account/model compatibility.
4. Native migration/readiness/runtime permissions and purge interfaces on real
   disposable PostgreSQL, including independent connections: integrity, least
   privilege, physical cleanup and races. This cannot establish deployed
   operator scheduling or production retention.

Owner approved these mechanics and seams before implementation. Work follows
one vertical test/implementation slice at a time,
run full applicable local regression and affected versioned mocked evals, compare
with Ticket 01, and perform the implement skill's completion review. Git actions
require the separate one-time approval recorded in PROGRESS; no later ticket or
paid call is authorized.
