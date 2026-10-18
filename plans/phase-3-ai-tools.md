# Phase 3 — AI tool calling

Status: owner approved Ticket 01 implementation and its four TDD seams on
2026-10-18. Catalog/fee chat and the first real-path mocked baseline are implemented
and verified locally: 316 broad regression passes, 67 final focused passes and 13
mocked behavioral passes (2 later-ticket cases pending; counts overlap).
Ticket 01 is resolved; evidence is tracked in the ticket and progress log.
Owner subsequently approved one implementation commit and normal push, subject to
final staged review; hosted verification is recorded via the Ticket 01 handoff.
The remaining five tickets, paid runs and additional commits/pushes are not
authorized. The six-ticket dependency structure is unchanged.
Shared requirements: [Phase 3 spec](../.scratch/phase-3-ai-tools/spec.md).

## Entry and sequence

Inspected clean master at `5b98387` (Phase 2 documentation closeout). Phase 2
exit records implementation `24051ac`, successful exact-SHA Actions and 253 local
passes; those checks were not rerun here. Seven existing eval cases are pending
inventory with null behavioral quality. No provider dependency, chat route,
conversation storage or real-path behavioral baseline exists yet.

| Ticket | Outcome | Blocked by |
| --- | --- | --- |
| [01 — Grounded catalog chat](../.scratch/phase-3-ai-tools/issues/01-grounded-catalog-chat.md) | Bounded public catalog/fee chat, isolated Claude adapter, real-path mocked baseline | None; Phase 2 entry satisfied |
| [02 — Conversation context and appointments](../.scratch/phase-3-ai-tools/issues/02-conversation-context-appointments.md) | Disclosed owned history, bounded follow-ups, deletion and private listing | 01; D10 mechanics review before persistence |
| [03 — Booking review and confirmation](../.scratch/phase-3-ai-tools/issues/03-booking-review-confirmation.md) | Real slots, exact review, separate user confirmation and persisted booking | 02 |
| [04 — Cancellation](../.scratch/phase-3-ai-tools/issues/04-cancellation-review-confirmation.md) | Owned cancellation review and confirmed cancellation | 03 |
| [05 — Rescheduling](../.scratch/phase-3-ai-tools/issues/05-reschedule-review-confirmation.md) | Current target slot/fee review and confirmed atomic move | 03 |
| [06 — Evaluation and regression gate](../.scratch/phase-3-ai-tools/issues/06-provider-evaluation-regression-gate.md) | Combined deterministic/live evidence and Phase 3 gate | 04, 05; explicit approval before paid runs |

04 and 05 share 03's completed action-review integration and do not gate each
other. One individually approved implementation ticket per fresh session.
`ready-for-agent` is triage, not implementation or spending approval.

## Architecture and provider decision

One bounded explicit loop stays inside FastAPI. A small provider interface accepts
neutral conversation items, tool definitions and budgets, returning normalized
tool requests, text, usage and termination/error status. Only the Anthropic
adapter owns SDK objects, Messages formatting, tool_use/tool_result correlation
and necessary private continuation blocks. A scripted provider uses the same
interface for tests. No second paid provider, routing framework or agent SDK.

Select configurable `claude-sonnet-5-5` initially for multi-step capability with
documented fast latency and moderate cost. Official base prices checked today:
USD 2/input and USD 10/output per million tokens. These are not measured CareFlow
latency/cost. Haiku is a cheaper alternative; Opus is a more expensive alternative
if evaluated quality warrants it. Do not silently switch. Ticket 01 pins a
compatible SDK and verifies selected-model schema/config support.

Use static strict custom tool schemas, extra-property rejection, independent
backend input/output validation and sequential execution. Anthropic requests use
auto tool choice with disable_parallel_tool_use enabled; reject unexpected
multi-call responses before execution. Sonnet 5.5 does not support forced any/
named-tool choices; do not copy those or OpenAI store parameters. Handle content
blocks, refusal, truncation and unknown stop reasons without partial execution or
exposing thinking. Recheck model constraints against the pinned SDK.

Tools call existing domain services, not routers or arbitrary SQL. Resolve live
identity/scope outside model arguments. No database transaction/locks span model
calls; keep synchronous SQL off the async event loop. Read-only tools and proposal
tools are model-callable; confirmation tools are not. Confirm through a separate
authenticated same-origin CSRF request
to existing appointment endpoints. Backend-issued exact review and committed
results populate typed action summaries; model narration grants no authority.

## Privacy, context and paid-run boundaries

Retain D10's disclosed PostgreSQL history, bounded context, serialized turns and
30-day synthetic-history direction as reaffirmed by the owner. Earlier planning
did not settle guest ownership/transfer, purge/deletion timing or exceptions.
Ticket 02 must present these concrete mechanics for approval before storage; do
not pretend they were approved. No implicit guest transfer or new handoff/audit
retention exception is authorized. Chat deletion cannot delete appointment,
proposal, retry or audit history.

Use ANTHROPIC_API_KEY in server process environment or an explicitly loaded
Git-ignored local file. Existing .env/.env.* ignore rules apply; examples contain
placeholders only. Never request the key in chat, expose it to browser/model,
inspect/log its value or write it into reports. No key file is created here.

Anthropic commercial API inputs/outputs are generally deleted within 30 days,
with service-specific, contractual, usage-policy and legal exceptions. Possessing
a key does not establish zero data retention; account terms/settings remain
unverified. Covered-model rules can change ZDR eligibility. Strict-tool compiled
schemas may be cached up to 24 hours since last use: keep schemas static and free
of patient-specific values. Feature-specific retention wording does not establish
account-wide ZDR. Local deletion cannot promise removal of provider copies, and
no OpenAI store=false equivalent is assumed. Send minimal synthetic context only.

USD 5 is a cumulative Phase 3 live-evaluation ceiling, not per invocation. Every
paid run needs explicit approval of model/cases and estimated upper cost before
execution. Reserve worst-case cost before calls, including schema/history,
thinking/output and retries; maintain a durable cross-run ledger and stop when
pricing/remaining allowance is unknown. Key availability authorizes no spend.
Missing approval/credentials/network/credits is blocked live evidence, never a
pass. Disable uncontrolled SDK retries and automatic paid CI.

## Requirements and verification

| Requirement | Coverage |
| --- | --- |
| FR-01 discovery and accurate service/consultation fees | 01 |
| FR-02 persisted availability/timezones | 03, 05 |
| FR-03 patient/session/clinic isolation | 01 public boundary; 02–05 private paths |
| FR-04 booking, confirmation, pricing, atomicity and retries | 03 |
| FR-05 cancellation/reschedule and cutoff | 04, 05 |
| FR-06 bounded allowlists, validation and failure handling | 01 onward; combined 06 |
| FR-08 clinical/injection refusal and honest handoff limitation | Every slice; combined 06; actual queue remains Phase 5 |
| FR-09 real-path graders and baseline comparisons | Every slice; live/combined 06 |
| FR-11 minimum owned history/deletion | 02 |
| FR-13 redacted traces, latency/usage/cost accounting | 01 onward; combined 06 |
| FR-07 retrieval/citations/grounded FAQ metrics | Phase 4; missing-source abstention now |

Each slice runs applicable format/lint/strict types/unit/HTTP/integration checks
and affected versioned evals compared with the preceding baseline. 01 establishes
the first executed baseline; Phase 1 null inventory is not measured quality.
Strict TDD covers authorization, patient data, confirmation and retries. Use real
disposable PostgreSQL and independent connections for permission/concurrency/
idempotency/rollback claims; never connect tests to the main demo database.

06 requires full applicable backend/provider/context/auth/booking/management,
migration/readiness, serial CI and mocked eval regression without required skips;
zero observed critical auth/booking/safety failures; and explicitly approved
live held-out tool-selection accuracy >=95%, with counts, repeats and uncertainty.
Freeze held-out cases before tuning. FAQ/citation targets stay Phase 4 and are
explicitly inapplicable here. Required blocked live evidence leaves model quality
and combined Phase 3 exit blocked; deterministic success is not model quality.
Verify exact-SHA hosted Actions at an approved commit/push milestone separately
from local PostgreSQL evidence. No extra CI failure experiment is needed.

## Exclusions, changes and next step

No RAG/embeddings, frontend, staff auth/queue, clinical diagnosis/prescribing/
definitive triage, real data, deployment, Docker/Compose, notifications, MCP or
SQL/shell/browser tools. Offer human help without claiming a queue item. D01/D11
exact locale wording/reviewer remain relevant release gates; D05/D06/D09 stay
with later dependent work. The P0 handoff obligation is preserved for Phase 5.

Provider revision changes 01's adapter/schema/secret/retention criteria, 02's
continuation/disclosure criteria, 03–05's proof-exclusion/failure criteria and
06's live/usage/cost evidence. Six tickets and dependency edges stay unchanged.
Existing service seams need no standalone prefactoring ticket. Update actual
ticket/progress/contracts and material decisions at each completion, recording
executed results and blockers. Next: individually approve 01 in a fresh session.

## Official sources checked 2026-10-18

- [Models](https://platform.claude.com/docs/en/models/overview) and [Sonnet 5.5](https://platform.claude.com/docs/en/models/sonnet-5-5/overview): lifecycle, cost/speed comparison and configuration restrictions.
- [Strict tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use), [sequential controls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use), [tool handling](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls): SDK adapter requirements, not business authorization.
- [Commercial retention](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data) and [covered models](https://privacy.claude.com/en/articles/15425996-data-retention-practices-for-covered-models): conditional retention, not verification of this account.
