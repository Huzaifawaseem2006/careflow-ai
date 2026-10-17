# 01: Grounded catalog chat and real-path eval baseline

**What to build:** A guest asks about fictional doctors, specialties, services
or fees and receives authoritative catalog facts through bounded tool calling,
with executable evidence of that behavior.

**Blocked by:** None (can start immediately; Phase 2 entry satisfied).

**Status:** ready-for-agent

**Approval gate:** Planning only approved. Obtain individual implementation
approval. Each paid run, commit and push requires separate explicit approval.

## Scope and contracts

Follow the Phase 3 plan/spec and existing scoped public catalog services. Deliver
single-turn chat with a multi-step loop, the provider seam, Anthropic adapter and
scripted test provider within this useful slice. No standalone prefactor/framework
ticket is needed. Service fees and doctor consultation fees are distinct.

## Acceptance criteria

- [ ] Versioned bounded chat/tool contracts reject extra fields, spoofed roles/authority and malformed arguments/results. Public reads return only active fictional-clinic doctors/specialties/services, exact PKR decimals and bounded pages. Empty/ambiguous matches trigger truthful clarification, not invented doctors, fees or associations.
- [ ] A small neutral interface keeps SDK types, Messages formatting, tool_use/tool_result correlation and private continuation inside the Anthropic adapter. Scripted providers exercise the same orchestration/dispatcher. Pin a compatible SDK under Python 3.13; verify strict-schema support for configurable initial claude-sonnet-5-5 and record SDK/model/config without silent fallback.
- [ ] Static strict schemas reject extra properties; backend independently validates inputs/outputs. Anthropic uses auto choice with parallel tool use disabled; reject unexpected multiple/illegal calls before dispatch. No copied store=false, forced-tool choices or unsupported sampling parameters. Adapters call services, not routers or arbitrary SQL.
- [ ] Server-assembled typed facts/status/action fields cannot be overwritten by model text. Check claims against actual catalog results or use deterministic wording, including free-text fabrication attempts. Citations stay empty; missing policy evidence yields abstention.
- [ ] Document/test finite body/context/output/tool-count/provider-call/time budgets and request rate limits. Existing body middleware covers auth/appointments only: cover chat explicitly. No transaction spans provider calls; blocking DB work stays off the async loop. Refusal, malformed/truncated blocks, wrong/duplicate IDs, unknown stops, loops, auth/429/5xx/timeouts and service errors stop safely without partial execution or success claims.
- [ ] Synthetic disclosure, injection/exfiltration refusal and no diagnosis/prescription/definitive triage are tested. No invented emergency contact or queued-handoff claim; final clinical wording remains D01/D11-gated.
- [ ] Server-only ANTHROPIC_API_KEY configuration uses environment or explicitly loaded ignored local config, examples are placeholders, missing config fails safely. Log/error/report tests exclude keys, cookies, bodies and thinking. Document conditional Anthropic retention separately from local storage; no ZDR claim from key possession.
- [ ] Before grading new behavior, wire versioned cases to the real orchestrator/catalog adapters, scripting only the provider and using disposable PostgreSQL for actual service-path assertions. Map scenario personas to real fixtures. Implement executable legality/grounding/state graders and prove wrong-tool, fabricated-fee and forbidden-output behavior fails. Record first mocked behavioral baseline; prior inventory is null quality.
- [ ] Positive/negative/adversarial and protocol contract tests verify content ordering, error results, truncation and safe continuation. Reports distinguish executed, pending, blocked and future-phase cases; gate failures are nonzero. Scripted success does not establish live model quality or measured tokens/cost.

## Verification and completion

Run applicable format/lint/strict types, unit/HTTP/provider-contract/catalog and
real PostgreSQL integration checks plus affected versioned evals. Record redacted
correlation/tool outcome/latency metrics and unavailable usage honestly. Update
actual contracts, ticket/progress and material decisions with commands/results,
baseline identifiers and limitations. No paid run is needed for deterministic
acceptance; never silently convert blocked live evidence to a pass.

## Out of scope

Durable history, private appointment data, availability, proposals, confirmation,
RAG, frontend, staff queue, real patients and automatic paid calls.

## Comments

Provider revision changes adapter/schema/secret/retention acceptance criteria,
not the outcome or dependency edge. No implementation has begun.
