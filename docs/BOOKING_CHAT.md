# Appointment reviews — Phase 3 Tickets 03–04

Synthetic clinic operations only. Owner approved Ticket 03, four TDD seams and
protected-action/history mechanics on 2026-10-18. Owner approved Ticket 04 and its
four TDD seams/evals on 2026-10-19. Current prompt: `cancellation-v1`; tool schema:
`4`. Historical `context-v1`/`2` and `booking-v1`/`3` responses remain replayable.
No frontend or confirmation tool exists.

## Tools and authority

| Tool | Required arguments | Existing service |
| --- | --- | --- |
| `get_available_slots` | `doctor_id`, offset-aware `start_at`, `end_at`, integer `limit` 1–20, integer `offset` 0–10000 | `read_availability` |
| `propose_booking` | `slot_id` UUID | `booking.propose` |

Availability is public on both chat paths. It reads persisted future active free
slots within today plus 29 Karachi dates. Ranges are offset-aware and half-open.
`facts[].slots` contains typed id/clinic/doctor/start/end/version/timezone records;
timestamps display in Asia/Karachi. Pagination is a snapshot, never a hold. Empty
pages, missing/malformed or out-of-horizon details ask for clarification. The model
must clarify ambiguous doctor/date/time and use a selected real slot, never invent
IDs or intent. The backend independently rejects phantom or ineligible slots.

Only authenticated patient conversations expose `propose_booking`. Session and
CSRF come from HTTP outside model context. Patient/clinic/role/fee, proof and
confirmation flags are not tool arguments. Domain transactions enforce live
patient/clinic scope and current inventory. Authorize again after provider waits
and before release. No transaction spans a provider call.

## Protected action and history

A successful review returns one `actions[]` entry:

```text
kind: booking_review
proposal_token: <backend-issued opaque proof>
summary: slot_id, doctor_id, clinic_id, doctor_name, start_at, end_at,
         timezone=Asia/Karachi, fee=<exact two-place decimal>, currency=PKR
expires_at: <backend five-minute deadline>
```

The effective deadline is the earlier of `expires_at` and slot start. The server
renders the exact doctor/local interval/timezone/fee/deadline from this validated
review. Proposals persist hashed proof and the versioned domain summary without a
booking or hold. Stop immediately after issuance: no review/proof is sent back
to Anthropic for narration or a second proposal. Provider prose and schema-shaped
forged reviews cannot populate actions or change server summaries.

Only the original authenticated no-store response carries raw proof. Stored
history and completed-turn replay contain a proof-free historical review marker
with `actions: []`. Replay cannot recover proof; request a fresh review if the
original action was lost. This exception to live-response replay was explicitly
approved with the TDD seams. Other completed turns retain immutable response
replay. History markers establish neither current price nor appointment state.
Conversation deletion does not remove proposals, appointments, retries or audit.

Cookies, CSRF, proof and confirmation retry keys are never forwarded from protected
transport to model messages or conversation text and are absent from safe traces.
SDK continuation stays private; provider body logging is disabled. Metrics contain
only allowlisted status/count/latency and usage metadata.

## Confirmation, errors and reconciliation shared with 04/05

Display the exact server review and obtain explicit confirmation. A distinct user
request sends `POST /appointments`, body `{"proposal_token":"<issued-proof>"}`,
session cookie, `X-CSRF-Token`, configured HTTPS Origin and one `Idempotency-Key`.
No new endpoint or authorization system is introduced. Chat yes, confirmed flags,
client receipts and model calls cannot execute confirmation. The existing typed
`BookingResponse` is the committed outcome and needs no provider narration.

Existing transactions revalidate session/scope, expiry, fees, versions and
eligibility and atomically commit appointment/proof/retry/audit. Changed review
state returns `STATE_CHANGED`; unavailable inventory returns `SLOT_UNAVAILABLE`;
expired proof returns `CONFIRMATION_EXPIRED`. Obtain a fresh review and explicit
confirmation after a definite stale/expired rejection. Auth/ownership/CSRF/origin
errors retain existing HTTP codes. Chat provider/service failures fabricate no
success. Interrupted auth/domain exceptions can leave the existing 90-second
turn lease until expiry; successful reviews release it.

Exact authenticated actor/action/key/request retries replay the immutable result
for 24 hours (201 initial booking, 200 replay). Changed-proof same-key, new-key
consumed-proof and expired-key errors remain unchanged. After an ambiguous
transport timeout, retain the original proof/key for an authorized exact retry;
never generate a new-key mutation automatically. Chat failure after commit cannot
undo the booking or authorize another one.

Use authorized `GET /appointments` for current state or exact confirmation replay
for the original operation result. A replay snapshot can differ from current state
after later management operations. Client transcripts prove neither. Tickets
04/05 should reuse this separation, typed server reviews/outcomes and error/retry
pattern with their existing services. Ticket 04 implements cancellation below;
Ticket 05 rescheduling remains outside this implementation.

## Ticket 04 cancellation review and confirmation

Authenticated patient conversations additionally expose `propose_cancellation`,
whose only required argument is `appointment_id` (UUID). Use current scoped
`get_my_appointments` data and an explicit selection; missing or ambiguous selection
requires clarification. Extra patient/clinic/role/proof/confirmation arguments are
invalid. Unknown and foreign appointment IDs return the same `404 NOT_FOUND`.
The tool invokes existing `management.propose_change(id, "cancel", None, ...)`;
it never invokes confirmation or changes appointment/capacity/retry/audit state.

The original protected response contains one `cancellation_review` action with
`proposal_token`, exact `expires_at`, and `summary`: `operation: "cancel"`, the full
owned appointment snapshot and `target: null`. Strict validation requires a booked
source, fixed clinic, increasing offset-aware interval, Asia/Karachi timezone and
exact accepted fee/currency. The snapshot includes patient/clinic/slot IDs and
creation time, matching the existing management HTTP review. The provider never
receives the review; issuance stops the model loop immediately. Server text gives
the source ID, doctor, local interval, accepted fee, expiry and confirmation path.

History/completed-turn replay instead returns a proof-free historical cancellation
marker with `actions: []`; it cannot recover a confirmation action. User text and
history are untrusted context and cannot execute cancellation. A lost original
action requires a fresh review and explicit confirmation. Conversation deletion
does not delete domain proposals, retries or audit records.

After reviewing, the user separately sends `POST /appointments/{id}/cancel`,
`{"proposal_token":"<issued-proof>"}`, live session cookie, configured HTTPS Origin,
`X-CSRF-Token` and one `Idempotency-Key`. No endpoint or confirmation authority is
added. Existing transactions revalidate ownership/clinic/session, status/versions,
five-minute expiry and the inclusive 24-hour cutoff after waits and before commit.
Exactly 24 hours is eligible; less is rejected. Stale, expired, consumed,
wrong-actor/action/path or forged proofs cannot cancel. Cancellation atomically
releases capacity and records proof consumption, immutable retry result and
before/after audit; accepted pricing is preserved.

The typed cancellation response is the committed result, with no provider step.
Both initial cancellation and exact authenticated retry return HTTP 200. Exact
actor/action/key/proof/path replay is valid strictly before its 24-hour deadline;
mismatches conflict, fresh keys cannot reuse consumed proof, and expired keys
cannot re-execute. On ambiguous transport failure retain the same proof/key for an
authorized exact retry. Provider failure cannot imply success or recancel a
consumed action. Current state comes from authorized appointment reads.

`backend/integration_tests/test_chat_cancellation_integration.py` is the synthetic
backend walkthrough: protected transport, current owned selection, proof-free
history, cutoff/proof/retry/staleness, rollback, independent-connection
duplicate/reschedule/reset/logout races and mocked SDK secret/schema checks.
`evals/cancellation_v1` freezes six dev and two held-out scripted cases. The runner
reuses real HTTPS/orchestrator/tools/services/DB and existing provider/snapshot
grading infrastructure. An independent oracle checks complete appointment rows,
immutable retries and before/after audit. Safe reports contain observations and
metadata, with no raw IDs/proofs/messages. Executed evidence and baseline deltas
are recorded in the Ticket 04 progress handoff. No live model quality is claimed.

## Backend-only walkthrough and verification

`backend/integration_tests/test_chat_booking_integration.py` exercises persisted
slot lookup, exact review, no appointment/retry/audit before confirmation, one
separately committed result, replay and authorized lookup after provider failure.
Other cases cover changed fees/fresh reviews, guest/foreign/revoked scope,
origin/CSRF, phantom slots, forged output, ranges/pages and mocked SDK HTTP schemas
and secret exclusion. Run serially through the reusable credential workflow:

```powershell
powershell.exe -NoProfile -File scripts/postgres-tests.ps1 test -TestPath backend/integration_tests/test_chat_booking_integration.py
powershell.exe -NoProfile -File scripts/postgres-tests.ps1 test
```

`evals/booking_v1` has six dev and two frozen held-out cases. Only the provider is
scripted; HTTP/orchestrator/tools/services/DB are real. Graders compare row counts
and complete prior booking records, with deliberately corrupted observations in
grader tests. Safe ignored report: `test-results/ticket03-booking-evals.json`.
Compare rerun context/catalog reports against Ticket 02's 8 context passes and
13 catalog passes/2 pending. The catalog-only pending seeds are not claimed passed
by the booking runner. Scripted results do not measure live model quality.
Final execution evidence belongs in the Ticket 03 progress handoff. No paid call,
live account compatibility, hosted exact-SHA CI or full Phase 3 exit is claimed.
Legacy Ticket 02 metric versions remain valid on exact historical replay.
