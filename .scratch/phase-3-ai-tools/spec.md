# Phase 3 — AI tool calling specification

Status: owner retained six-ticket planning structure and selected Anthropic,
2026-10-18. This is a specification, not implementation or spending approval.
The Phase 3 plan supplies dependencies, requirement coverage and dated provider
sources. Each ticket inherits the shared requirements below.

## Existing domain boundaries

Serve synthetic clinic operations only. Catalog supports active specialties,
doctors and services with independent service versus consultation fees. Public
filters cannot widen the fixed clinic. PKR amounts are exact decimals. Slots are
persisted, future, capacity-one 30-minute intervals, within today plus 29 Karachi
dates. Availability uses bounded pages, offset-aware half-open intervals and
Asia/Karachi display. It is a snapshot, not a hold. Owned appointment listing uses
bounded stable cursor/status/date filters and persisted patient/clinic scope.

Reuse catalog, availability, booking and management domain services and current
patient-session/CSRF/origin rules. Adapters do not call routers or direct SQL.
Model/client patient, clinic and role fields never grant authority. Revalidate
current auth at private access and final result release, including after model
waits; cached context cannot survive logout/reset as authority. Offload sync DB
work from the event loop and close transactions before network calls.

## Provider and response boundary

One small provider interface accepts neutral messages/tool definitions/budgets
and returns normalized calls/text/usage/stop status. Implement Anthropic and a
scripted test provider only. SDK imports, tool_use/tool_result IDs and ordering,
provider errors and necessary private continuation blocks stay in the adapter.
Policy, limits, dispatch, service authorization, action rendering and eval graders
stay independent. No provider routing framework or second live integration.

Initial configurable model is claude-sonnet-5-5. Verify compatibility and strict
tool support against a pinned SDK under Python 3.13. Record requested/resolved
model, SDK, prompt/schema/config versions. Do not silently replace the model.
Static schemas reject extra fields and undergo backend validation of arguments
and results, including UUID/date/decimal/business constraints. No patient-specific
schema enums/descriptions. Set auto selection with parallel tool use disabled;
reject multiple calls before dispatch. Do not copy OpenAI parameters or force
tool choice unsupported by this model. Bound body/history/output/tool count,
provider calls, timeout and retries; never execute partial/truncated arguments.

Handle refusal, malformed blocks, unknown stop reasons, wrong/duplicate call IDs,
provider auth/429/5xx and ambiguous transport as safe bounded errors. Thinking
content cannot appear in responses/logs. A timeout does not prove rollback.
Response envelope includes version, status, safe text, authoritative typed data,
actions, correlation ID and empty citations until Phase 4. Validate clinic facts
against actual results or render them deterministically; prompting alone does
not prevent fabricated claims. Historical results must be re-read when volatile.

Logical tools cover doctor/specialty/service discovery, consultation/service fees,
available slots, owned appointments and booking/cancellation/reschedule proposals.
Document exact versioned names/contracts in each slice. No ordinary confirm tools,
unrestricted SQL, shell, browser, policy retrieval or handoff tool before its
authorized service exists. Client-supplied assistant/tool transcripts are untrusted.

## Conversation state, secrets and retention

01 is public single-turn chat with a multi-step tool loop and no durable content.
02 introduces disclosed PostgreSQL-owned history, bounded context and serialized
turns. A bare conversation UUID cannot confer ownership. Reject role spoofing
and cross-patient/clinic/guest access. Truncation preserves complete tool pairs.
Provider continuation remains private and bounded; minimize retained/transmitted
content and never expose reasoning.

Owner reaffirmed D10's 30-day synthetic-history direction and security boundaries.
Original planning left guest identity/lifetime/transfer, deletion timing/trigger
and exceptions unsettled. Before storing content, 02 presents concrete mechanics
for approval. Recommend isolated guest ownership without automatic transfer,
expiry denied on reads, owner-scoped deletion and an explicit native purge path
instead of new scheduler infrastructure. Do not label these mechanics approved
until reviewed. Define deletion versus in-flight completion to prevent restoring
deleted history. No new handoff/audit retention exceptions; chat deletion leaves
appointment/proof/retry/audit invariants intact.

ANTHROPIC_API_KEY comes from process environment or explicitly loaded ignored
local configuration; existing env ignore rules suffice. Placeholder examples only.
No secrets in browser/model arguments, prompts, logs, errors or reports. No key
inspection/provisioning in planning. Provider retention differs from CareFlow
retention: commercial API policy has a general 30-day period and exceptions;
ZDR/account terms are unverified. Strict compiled schemas can be cached. Recheck
applicable account/model terms before live use, disclose both boundaries and
never promise provider deletion through local deletion or store=false.

## Proposals and confirmed operations

Proposals persist proof but create no appointment or hold. Forward auth/CSRF
outside model context. Exact server summary/expiry and proof travel only through
protected action transport. Keep raw proof, cookies, CSRF and retry keys out of
provider messages, stored conversation text and traces. Stop the loop once a
review is issued to avoid duplicate proposal creation.

Separate authenticated same-origin CSRF requests to existing appointment endpoints
are the confirmation event. Chat yes, booleans, model calls and client receipts
cannot authorize writes or prove success. Backend summaries/committed outcomes
remain usable without further model narration. Verify any later status through
current authorized service data or exact replay, never trusted client transcripts.

Retain five-minute actor/action/payload-bound proof expiry, also bounded by slot
start, with fresh review on relevant versions/fee/eligibility changes. Preserve
atomic appointment/proof/retry/audit, capacity uniqueness and deterministic locks.
Exact successful authenticated actor/action/key/request replay lasts 24 hours;
expired keys cannot re-execute. Replay snapshots describe the original operation,
not necessarily today's appointment state. Ambiguous timeout retains the same
proof/key for an authorized retry; never start a new-key mutation automatically.
Provider failure after commit cannot undo it or authorize another operation.

Cancellation/reschedule allow exactly 24 hours before source start, reject less,
and recheck after waits. Reschedule reviews target fee even when unchanged,
updates the same appointment, retains before/after audit and preserves the source
on failure. No new scheduling, price, cutoff or retention policy.

## Evaluation and completion contract

Wire existing versioned cases to the real orchestrator/domain adapters, scripting
only the external provider in mocked behavioral runs. Use real disposable DBs for
state claims. Map personas to actual test accounts; labels are not authentication.
Implement executable tool-legality/grounding/auth/state graders and prove they
reject deliberately wrong behavior. Preserve Phase 1's null inventory as history,
establish first executed baseline in 01, version/checksum dataset updates and
compare affected cases in every later slice. Keep held-out cases out of tuning;
future-phase cases remain pending/inapplicable, never passed by stubs.

Strict TDD for auth, patient handling, confirmation, retries and state effects.
Real PostgreSQL tests use disposable databases only, including independent-
connection races, rollback, permissions and revoked/expired sessions. Every
ticket runs applicable format/lint/types and focused unit/HTTP/integration/evals,
records commands/results/baseline deltas, updates ticket/progress/contracts and
material decisions, and hands off one ticket per session. Required failures or
missing checks block resolution; never claim incomplete work passed.

Live mode substitutes Anthropic only at the provider seam. USD 5 is cumulative
across Phase 3 and each paid run still requires explicit approval of model/cases
and estimated maximum cost. Reserve conservative cost before calls, including
schema/context, thinking/output, retries and ambiguous charged calls; persist a
cross-run ledger. Unknown prices/usage/remaining budget stop further calls. No
paid CI by default. Reports separate modes and record code/dirty state, versions,
counts/statuses, safe traces, latency, usage/cost methodology and null unavailable
metrics. Scripted behavior does not measure model tool-selection accuracy.

06 combines all applicable regression, zero observed critical violations and
approved live held-out >=95% tool-selection with sample sizes/uncertainty. Missing
live evidence blocks combined phase exit, not just a footnote. Hosted exact-SHA
Actions needs a separately approved commit/push; local PostgreSQL remains separate.

RAG/corpus/embeddings/citations are Phase 4. Frontend/staff queue are Phase 5; no
queued-handoff claim before an actual service accepts it. D01/D11 exact locale
clinical wording and named reviewer remain release gates. No diagnosis,
prescribing, definitive triage, real patients, Docker/Compose, deployment,
notifications, MCP or new identity lifecycle. Later P0 obligations remain intact.
