# 06: Live-provider evaluation and Phase 3 regression gate

**What to build:** Produce reproducible evidence that the assistant selects legal
tools, preserves backend invariants and handles failures safely, separating
deterministic orchestration from actual Claude behavior.

**Blocked by:** 04 — Chat-assisted cancellation review and confirmation;
05 — Chat-assisted rescheduling review and confirmation (transitively 01–03).

**Status:** ready-for-agent

**Approval gate:** Individual implementation approval required. Every paid run
needs explicit model/cases/estimated-maximum-cost approval. USD 5 is cumulative
across Phase 3, not a per-run allowance or permission to spend. Each commit and
push needs separate approval.

## Scope and contracts

Follow the shared Phase 3 spec. Extend the existing harness/reporting with
separately labeled scripted-provider and Anthropic modes through the same real
orchestrator/domain adapters. Reuse earlier executable graders, not a second
framework. Earlier tickets already run affected evals; this combines the gate.

## Acceptance criteria

- [ ] Freeze versioned/checksummed held-out synthetic cases before tuning, with required/forbidden tools, partitions/fixtures, severity and state/response assertions. Cover catalog/service fees, slots, context/privacy, all proposals/confirmations, ambiguity/staleness, injection/clinical boundaries, malformed output and provider/transport failure. Persona labels map to actual disposable accounts.
- [ ] Mocked/live modes exercise identical application paths and deterministic legality/grounding/auth/state graders; only the external provider is scripted in mocked runs. Do not mock transactional claims. Demonstrate deliberately wrong tool, fabricated success, cross-user access and unconfirmed mutation fail grading and gate exit.
- [ ] Safe reports separate modes and include code/dirty state, provider/SDK, requested/resolved model/config, prompt/tool/dataset/fixture versions, partition, counts/statuses, failures/deltas, safe tool traces, latency distribution, usage and cost methodology. Unknown metrics stay null; pending/inventory/future-RAG cases are not passes.
- [ ] Live entry requires explicit paid approval, safe server key configuration, account/model access and applicable retention disclosure. Durable cumulative ledger reserves conservative schema/history/input/thinking/output/retry cost before each call. Unknown pricing, ambiguous charged calls or insufficient remaining budget stop dispatch; disable uncontrolled SDK retries/fallbacks and automatic paid CI.
- [ ] Record dated pricing source and actual reported usage separately from estimates, including earlier Phase 3 paid spend. Missing approval/key/network/credits/safe budget is blocked. Stop at USD 5; remaining requested cases are blocked, not silently omitted. Model changes require reevaluation, not a silent cheaper fallback.
- [ ] Full applicable format/lint/types, unit/HTTP/provider/context/auth/booking/management, migration/readiness, independent-connection concurrency/idempotency and serial CI regression pass without required skips. Full real-path mocked suite has zero observed unauthorized read/mutation, unconfirmed write, duplicate booking or critical safety failure. Compare earlier baselines and retain failed attempts/reruns honestly.
- [ ] Explicitly approved live held-out tool-selection accuracy meets provisional >=95%, with numerator/denominator, repeat policy, sample size and uncertainty. Critical cases all pass; no LLM judge replaces auth/state checks. Missing live evidence blocks model quality and combined Phase 3 exit. FAQ correctness/citation targets are Phase 4, explicitly inapplicable here.
- [ ] Backend-only synthetic walkthroughs cover booking/cancel/reschedule review and separate confirmations, stale fee/slot, cutoff, replay and provider failure after commit. No fabricated receipt or queued-handoff claim. D01/D11 exact wording/named-reviewer approval remains a relevant safety/release gate; technical refusal tests do not approve wording.
- [ ] Verify existing hosted Actions for the exact approved commit/push milestone separately from local PostgreSQL evidence. Missing hosted evidence is pending/blocked, not passed. No extra manual CI/failure experiment absent material CI need; ticket approval never authorizes commit/push.

## Verification and completion

Execute full applicable deterministic/real PostgreSQL/mock-eval gates and only
specifically approved live cases within the budget. Preserve redacted reports,
failed attempts and disposable DB/credential cleanup evidence. Update actual
phase status/gate, evaluation strategy, contracts, ticket/progress and material
decisions. Any required failed/blocked check prevents corresponding gate closure;
provide an exact resume path rather than weakening acceptance criteria.

## Out of scope

RAG/embeddings/corpus evaluation, frontend, staff queue, production hardening or
hosting, clinical validation claims, real data and spending above USD 5.

## Comments

Provider revision changes live protocol/usage/retention/cost criteria. Dependencies
remain 04 and 05. API key possession is not paid-run approval.
