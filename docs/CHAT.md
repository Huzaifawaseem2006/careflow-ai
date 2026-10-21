# Grounded catalog chat — Phase 3 Ticket 01

Ticket 02 adds [disclosed owned conversations and appointment lookup](CONVERSATIONS.md).
Ticket 03 adds [persisted availability and protected booking reviews](BOOKING_CHAT.md).
Tickets 04/05 add cancellation/rescheduling reviews through the same protected
action transport.
The single-turn path remains public-only. Current prompt/schema versions are
`reschedule-v1`/`5`; historical `context-v1`/`2`, `booking-v1`/`3` and
`cancellation-v1`/`4`
remain replayable. Catalog argument
schemas are unchanged.

The public single-turn endpoint performs catalog and persisted availability lookup,
with no durable conversation content, private patient access, appointment writes,
RAG or handoff. Booking/cancellation/rescheduling reviews require authenticated
conversations.
Only synthetic input belongs in this demo. Live account/model access is unverified.
On 2026-10-20 the owner approved the exact number-free escalation sentence and
contract-compatible fallback improvement. The [complete current fallback](SAFETY.md#phase-3-wording-review--2026-10-20)
is implemented and technically tested; D11 reviewer/human clinical sign-off remains
pending. Deterministic tests are not model quality or clinical sign-off.

## HTTP and authoritative response

`POST /chat` accepts exactly `{"version":"1","message":"..."}`. Extra fields,
roles, transcripts, identity and clinic authority are rejected with safe 422 errors.
Message length is 1–2000 characters with non-whitespace content. The shared ASGI
middleware bounds the complete body to 4096 bytes before JSON parsing, including
chunked requests. HTTPS, exact `AUTH_ORIGIN` and no cross-site fetch are required.
The public read creates no session and does not use a supplied cookie or CSRF
header as authority. CSRF tokens remain required by the existing mutation routes.

The persisted limiter reuses `auth_limits`, with a separate hash of `chat:ip:<peer>`:
10 requests per 60 seconds by default, shared across workers. It trusts the server
peer, not a user-supplied forwarding header. Deployment must configure trusted
proxies intentionally. Limiter transactions close before provider calls. A 429
uses the existing safe error envelope and conservative 300-second Retry-After.
Traffic counters are infrastructure state, not clinic/patient mutations.

Successful envelopes contain `version`, `status`, `text`, `facts`, `actions`,
`citations`, server UUID `correlation_id` and redacted `metrics`. Status is
`answered`, `clarification`, `abstained`, `unavailable` or `limited`. The latter
two use HTTP 503; other chat outcomes use 200. Validation/origin/rate/configuration
errors reuse existing 422/403/429/503 safe envelopes. Every response is no-store.

Facts are bounded tool-result pages: `name`, `status` (`ok`, `empty`, `ambiguous`,
`invalid`, `unavailable`), `data`, `limit`, `offset`. Only successful/empty/ambiguous
catalog results enter final facts. Rows use the public Phase 2 record fields:
specialties have UUID id/clinic_id, name and city; doctors additionally carry
specialty_id, consultation_fee and PKR currency; services carry fee and PKR
currency. Extra output fields and foreign clinic IDs fail validation. Amounts are
exact nonnegative two-place decimal strings, below PKR 10 billion. Ticket 03 adds
typed slot facts and protected review actions; see [booking chat](BOOKING_CHAT.md).
Citations remain empty. Neither a model statement nor an incoming role can
replace these fields.

The server renders all response text from validated catalog records or fixed
clarification/abstention/error wording. Provider prose is discarded completely.
Empty pages are described as empty pages, not proof that a resource cannot exist.
Multiple name matches require selection. Listing records does not establish
availability, policy coverage or a doctor-service association. No verified policy
source means abstention. D01 owner-approved wording puts the exact escalation
sentence immediately after synthetic disclosure, omits selection prompts and
states that this chat has no verified clinic-policy source and cannot queue a
staff handoff. It makes no claim about an earlier/external handoff. Human clinical
review remains pending under D11. No policy retrieval/handoff service or new
clinical routing is added; confirmation, error and historical replay contracts
are unchanged.

## Tool schema version 1

| Name | Required arguments | Authoritative service |
| --- | --- | --- |
| search_doctors | query, resource_id, city, limit, offset, specialty_id | read_catalog(doctors) |
| search_specialties | query, resource_id, city, limit, offset | read_catalog(specialties) |
| search_services | query, resource_id, city, limit, offset | read_catalog(services) |
| get_consultation_fee | resource_id | read_catalog(doctors), consultation_fee |
| get_service_fee | resource_id | read_catalog(services), fee |

All listed properties are required. Search query/resource_id/city/specialty_id
can be null; UUID values use UUID strings. Query is nonblank, at most 120
characters; city is 1–80 characters. Limit is an integer 1–20; offset is 0–10000.
Query matches case-insensitive record names **within the selected bounded page**;
specialty and city filters use the existing service. This avoids an unbounded
scan and discloses when another page may be needed. Fee resource_id is non-null.
No clinic, patient, role, price, SQL or unrestricted execution parameter exists.

Neutral static schemas reject extra properties. The Anthropic adapter uses the
pinned SDK's `transform_schema` to move unsupported numeric/length constraints
into descriptions; supported UUID/pattern/required/extra-field constraints remain.
Backend JSON-strict Pydantic validation enforces the full original schema,
including bool-versus-int distinctions. Strict provider schemas are not authority.

Catalog adapters call existing services, not HTTP routers or arbitrary SQL. Each
read owns a short connection and runs off the async event loop. No transaction
spans a provider wait. The service still fixes clinic scope and active/synthetic
eligibility. A read already running when a deadline expires may finish under the
existing SQL timeout. Ticket 03's proposal-only tool persists hashed proof without
an appointment or hold and stops the loop; no confirmation tool is exposed.

## Provider and limits

SDK `anthropic==1.15.0`, transport `httpx2==2.13.1`, Python 3.13. Initial model is
`claude-sonnet-5-5`, configurable without fallback. The adapter owns Messages
formatting, tool-use IDs, ordered continuation and private thinking blocks.
It requests auto choice, disables parallel tool use and uses zero SDK retries.
No sampling, forced tool choice, store parameter or agent framework is added.
Protocol tests verify the real SDK's serialized requests with mocked HTTP; they
do not establish live model/account acceptance.

Reject multiple calls, unknown tools/stops, duplicate/wrong IDs, model substitution,
bad ordering, unsupported blocks, truncation and incomplete JSON before dispatch.
A single malformed argument set produces an `invalid` tool result; the provider
may correct it within the same finite budget. Service errors, protocol failures,
refusals after reads and exhausted budgets expose no partial facts or success.
Safe metrics include correlation, counts, allowlisted tool outcomes and latencies;
usage is null for scripted runs and incomplete failures. Successful SDK usage
includes cache input tokens. No measured live cost or token claim is made.

| Environment field | Default | Permitted bound |
| --- | --- | --- |
| CHAT_MODEL | claude-sonnet-5-5 | nonempty, <=100 characters |
| CHAT_PROVIDER_CALLS | 5 | 1–8 |
| CHAT_TOOL_CALLS | 4 | 0–6 |
| CHAT_OUTPUT_TOKENS | 1024 per call | 64–2048 |
| CHAT_CONTEXT_BYTES | 48000 | 4096–64000 |
| CHAT_RESPONSE_BYTES | 16000 | 2048–32000 |
| CHAT_TIMEOUT_SECONDS | 20 | >0, <=60 |
| CHAT_RATE_PER_MINUTE | 10 | 1–30 |

The loop deadline covers provider and tool execution. Context covers schemas,
message and accumulated results/continuation; raw provider response size is also
bounded. Final serialized response size is checked. Rate-check connection/SQL
timeouts retain existing database limits. Tiny configured budgets may fail closed
before any call. Invalid configuration returns a safe 503.

`CHAT_ENABLED=true` and server-only `ANTHROPIC_API_KEY` must both be present for a
live provider. Defaults remain disabled even if a key exists. No .env autoload,
key provisioning or key inspection is added. Each paid run still requires owner
approval; the separate [Ticket 06 evaluation gate](PHASE3_EVALUATION.md) now
provides cumulative paid-run accounting. Live quality remains unverified.
Transport uses the fixed official HTTPS host, disables environment proxies and
redirects, disables SDK telemetry and suppresses its body-emitting request logger.
Application logs never contain keys, bodies, cookies, CSRF or thinking.

CareFlow stores no chat content in Ticket 01. Conditional Anthropic commercial
retention is separate (normally within 30 days, with contractual/service/legal
exceptions); compiled schemas may be cached. Account ZDR is unverified. Local
deletion would not promise provider deletion. Recheck account terms before live
use. Sources checked 2026-10-18: [strict tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use),
[schema subset](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
[Sonnet restrictions](https://platform.claude.com/docs/en/models/sonnet-5-5/whats-new-sonnet-5-5),
[SDK](https://pypi.org/project/anthropic/1.15.0/),
[retention](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data).
