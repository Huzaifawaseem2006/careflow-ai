# Owned conversations — Phase 3 Ticket 02

Synthetic operations only. Owner approved the concrete D10 mechanics and four
TDD seams on 2026-10-18; see the [approved mechanics](../.scratch/phase-3-ai-tools/d10-mechanics-review.md).
Ticket 03 adds [booking reviews](BOOKING_CHAT.md); clinical decisions, staff access
and frontend remain outside scope.
Public single-turn `POST /chat` remains available without durable content.

## Disclosure, ownership and lifecycle

`GET /chat/disclosure` returns `version: history-v1` and the disclosure text without
storing content or issuing a session. Before storage, obtain the existing session
and CSRF token through `/auth/csrf`, present this disclosure, and explicitly accept
its version when creating a conversation. Acceptance is per conversation.

Anonymous conversations belong to that anonymous session's digest, never a bare
conversation UUID. The existing ten-minute prelogin expiry is not extended.
Guest tools remain public-only. Sign-in rotates/removes that session and cascades
deletion of its guest conversations; no transfer occurs. Guest logout similarly
deletes the history. Expiry immediately denies reads/completion even when the
expired session has not yet been physically removed.

Patient ownership derives from live patient/clinic records. A newly authenticated
session for the same patient can resume owned history. Logout/password reset
revoke access and block in-flight result release, retaining patient history until
owned deletion or fixed expiry. Other patients/clinics/guests get the same 404 as
an unknown conversation; missing/revoked/expired sessions get 401. No client/model
identity, role, transcript or conversation ID supplies authority.

## HTTP contracts

| Method/path | Request | Result |
| --- | --- | --- |
| `GET /chat/disclosure` | None | Version and disclosure text |
| `POST /conversations` | `{"disclosure_version":"history-v1"}` | 201: `id`, `expires_at`, `disclosure_version` |
| `GET /conversations/{id}` | Session cookie | `id`, `expires_at`, ordered `turns`, `truncated` |
| `POST /conversations/{id}/turns` | `{"turn_id":"<UUID>","message":"..."}` | `replayed`, `historical`, `response` |
| `DELETE /conversations/{id}` | No body | 204; immediate local content deletion |

Every route requires HTTPS and the existing origin/fetch-site rules. Mutations
require the exact configured Origin plus live session and session CSRF header.
Responses/errors use `Cache-Control: no-store`. Create/turn requests reject extra
fields; user messages are nonblank and at most 2000 characters. The existing
middleware bounds POST bodies to 4096 bytes, including chunked bodies. Persisted
peer-IP limits allow ten creates/minute and configurable `CHAT_RATE_PER_MINUTE`
turn attempts/minute; forwarding headers do not establish peer identity.

History returns the newest complete turns in ascending completion sequence, at
most 20 and within 32 KiB; `truncated` discloses omitted older turns. Each contains
`id`, `user_text`, and the server response snapshot. History and replay are records
of past responses, not current appointment state. The nested response retains the
version-1 authoritative envelope; citations remain empty. Tickets 03/04 live booking
and cancellation reviews carry protected actions; stored history/replay carries
only a proof-free historical marker with empty actions. Prompt: `cancellation-v1`;
tool schema: `4` (historical `context-v1`/`2` and `booking-v1`/`3` remain valid),
including public-path reports.

Turn UUIDs are scoped to a conversation. Exact completed retries revalidate live
ownership and return the immutable stored response with both `replayed` and
`historical` true, even if the provider is unavailable. Changed content under an
existing UUID returns 409 `TURN_CONFLICT`. A live competing lease returns 409
`TURN_BUSY`. An expired/stolen lease returns 409 `TURN_EXPIRED` to its old worker.
Provider failures/limits return safe 503 envelopes and save no partial pair.
Failures release a valid lease; abandoned work expires after 90 seconds. Retrying
that UUID can acquire a new fenced lease and completion sequence. A newer turn
can also proceed after expiry. Read-only tools may run again on a reclaimed turn;
proposals may persist hashed proof without booking or holding capacity. Completed
reviews replay historical markers without new proof. Turn hashes last only until
conversation deletion/expiry. Interrupted authorization failures may leave the
finite lease until expiry; they cannot append or release private results.

## Context and private reads

Load at most 20 newest complete user/server text pairs within 32 KiB and half the
configured total context budget; omit entire oldest pairs. This is untrusted
context in a single user message, not replayed assistant/tool authority. Historical
tool calls/results and SDK continuation/thinking are never persisted or restored;
there can be no orphaned historical call/result pair. Historical private assistant
results are replaced with an instruction to re-read appointments. Full private
typed data is retained only in the owned response snapshot for history/replay.

Only authenticated patient conversations receive `get_my_appointments`. Its
required arguments are `limit` (integer 1–20), `cursor` (nullable, max 100),
`status` (nullable `booked`/`cancelled`), `start_at` and `end_at` (nullable explicit
offset timestamps, max 40). Extra identity/clinic/role parameters are invalid.
Existing `ListingFilters` enforces cursor/date semantics, half-open ranges and
current scoped `list_appointments` supplies the page. Result validation exposes
appointment/doctor IDs, doctor name, offset times, timezone, fee/currency and status,
with an opaque next cursor. Patient/user/clinic identifiers, cookies, CSRF values
and credentials are not automatically forwarded in model context. All wording
comes from validated facts or fixed server text; provider prose grants no authority.

Live session/scope is checked before and after every provider wait, at private
service access, completion and final response release. User/session locks follow
the existing reset-compatible order, then short conversation row locks. A fenced
90-second lease serializes turns without holding transactions during model calls.
Deletion cascades turns; completion can update only a surviving, unexpired owned
conversation under the same lease. It cannot reinsert deleted history.

## Migration, runtime grants and physical purge

Native `alembic upgrade head` advances readiness to `0008_conversations`. It adds
conversation ownership/expiry/lease constraints, composite patient/clinic integrity,
guest-session and turn cascade foreign keys, unique per-conversation turn IDs and
sequences, and a constraint requiring both members of a completed message pair.
The earlier patient/clinic uniqueness constraint is reused.

After applying the existing session/appointment runtime grants in README, add:

```sql
GRANT SELECT, INSERT ON public.conversations, public.conversation_turns TO careflow_app;
GRANT UPDATE (lease_id, lease_until, version) ON public.conversations TO careflow_app;
GRANT UPDATE (user_text, response, sequence) ON public.conversation_turns TO careflow_app;
GRANT DELETE ON public.conversations TO careflow_app;
```

Do not grant runtime ownership-field changes, turn-hash changes, schema changes,
appointment deletion or audit/retry update/deletion. Conversation deletion cascades
turn deletion without a separate turn DELETE grant. No grants are applied to the
existing demo database by this ticket. Restricted-role tests use disposable DBs.

Patient expiry is exactly 30 days after conversation creation, without extension.
Guest expiry is the earlier session deadline. Access expires immediately;
physical cleanup occurs when the operator runs the bounded native command:

```powershell
# Uses the operator's explicitly configured local synthetic DATABASE_URL.
.venv\Scripts\python -m careflow.conversation_purge --confirm-local-synthetic
.venv\Scripts\python -m careflow.conversation_purge --confirm-local-synthetic --delete --limit 1000
```

The default is a count-only dry run of up to 1000 eligible unlocked conversations.
Run deletion at least daily, repeating batches until empty; recheck once active
transactions finish because locked rows are skipped. The command permits only the
existing named local synthetic targets and requires explicit local confirmation.
It removes expired conversations and guest history whose session expired, cascading
their message/retry metadata. No scheduler or automatic physical deadline is
claimed. Explicit owned deletion removes content immediately in its transaction.
No chat deletion/purge removes appointments, proposals, appointment retries or audit.

No handoff/audit retention exception exists. Provider retention is independent:
general Anthropic commercial retention has exceptions, account terms/ZDR remain
unverified, and local deletion cannot promise provider deletion. Only synthetic
context is allowed. No live call/spend is authorized by enabling history.

## Verification evidence

The Ticket 02 handoff in `docs/PROGRESS.md` records executed checks. New immutable
`evals/context_v1` cases exercise real HTTPS handlers, storage, orchestration and
services with only the provider scripted. Reports omit raw messages, identifiers
and credentials, keep dev/held-out labels, and compare with the separately rerun
Ticket 01 catalog baseline. Scripted results do not measure live model accuracy.
