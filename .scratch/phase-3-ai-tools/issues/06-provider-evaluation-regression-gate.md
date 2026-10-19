# 06: Live-provider evaluation and Phase 3 regression gate

**What to build:** Produce reproducible evidence that the assistant selects legal
tools, preserves backend invariants and handles failures safely, separating
deterministic orchestration from actual Claude behavior.

**Blocked by:** 04 — Chat-assisted cancellation review and confirmation;
05 — Chat-assisted rescheduling review and confirmation (transitively 01–03).

**Status:** ready-for-human

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

- [x] Freeze versioned/checksummed held-out synthetic cases before tuning, with required/forbidden tools, partitions/fixtures, severity and state/response assertions. Cover catalog/service fees, slots, context/privacy, all proposals/confirmations, ambiguity/staleness, injection/clinical boundaries, malformed output and provider/transport failure. Persona labels map to actual disposable accounts.
- [x] Mocked/live modes exercise identical application paths and deterministic legality/grounding/auth/state graders; only the external provider is scripted in mocked runs. Do not mock transactional claims. Demonstrate deliberately wrong tool, fabricated success, cross-user access and unconfirmed mutation fail grading and gate exit.
- [x] Safe reports separate modes and include code/dirty state, provider/SDK, requested/resolved model/config, prompt/tool/dataset/fixture versions, partition, counts/statuses, failures/deltas, safe tool traces, latency distribution, usage and cost methodology. Unknown metrics stay null; pending/inventory/future-RAG cases are not passes.
- [x] Live entry requires explicit paid approval, safe server key configuration, account/model access and applicable retention disclosure. Durable cumulative ledger reserves conservative schema/history/input/thinking/output/retry cost before each call. Unknown pricing, ambiguous charged calls or insufficient remaining budget stop dispatch; disable uncontrolled SDK retries/fallbacks and automatic paid CI.
- [x] Record dated pricing source and actual reported usage separately from estimates, including earlier Phase 3 paid spend. Missing approval/key/network/credits/safe budget is blocked. Stop at USD 5; remaining requested cases are blocked, not silently omitted. Model changes require reevaluation, not a silent cheaper fallback.
- [x] Full applicable format/lint/types, unit/HTTP/provider/context/auth/booking/management, migration/readiness, independent-connection concurrency/idempotency and serial CI regression pass without required skips. Full real-path mocked suite has zero observed unauthorized read/mutation, unconfirmed write, duplicate booking or critical safety failure. Compare earlier baselines and retain failed attempts/reruns honestly.
- [ ] Explicitly approved live held-out tool-selection accuracy meets provisional >=95%, with numerator/denominator, repeat policy, sample size and uncertainty. Critical cases all pass; no LLM judge replaces auth/state checks. Missing live evidence blocks model quality and combined Phase 3 exit. FAQ correctness/citation targets are Phase 4, explicitly inapplicable here.
- [x] Backend-only synthetic walkthroughs cover booking/cancel/reschedule review and separate confirmations, stale fee/slot, cutoff, replay and provider failure after commit. No fabricated receipt or queued-handoff claim. D01/D11 exact wording/named-reviewer approval remains a relevant safety/release gate; technical refusal tests do not approve wording.
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

2026-10-19 implementation handoff: 32/32 real-path mocked scenarios and all four
fault controls passed; full PostgreSQL 283 passed, offline/backend/eval/CI 297
passed, no required skips, formatting/lint/strict types/dependencies passed.
Earlier baselines reran unchanged. Both Standards and Spec reviews found no
remaining actionable issues. Failed/interrupted attempts and the timestamp
oracle correction are retained in [PROGRESS](../../../docs/PROGRESS.md).

Live: zero paid calls, zero measured live observations, all 23 requested held-out
cases blocked before dispatch. Separate model/cases/USD 4.50 maximum approval,
server key, verified account access and retention acknowledgment are pending.
Exact-SHA hosted evidence and D01/D11 wording/reviewer approval remain blocked.
Ticket 06 and Phase 3 are **not complete**. Follow the fixed credential-isolated
resume command and gates in [the evaluation guide](../../../docs/PHASE3_EVALUATION.md).
At that handoff no commit, push or next-phase work was authorized.

2026-10-20 publication review: owner authorized a scoped commit/push after passing
review/local gates, while explicitly prohibiting live calls. Three independent
review findings were fixed with red/green regressions: current SDK/schema/dependency
provenance, effective configuration validation and blocked live-quality CLI exits.
Fresh results: 36 PostgreSQL tests (all 32 cases/four controls), 307 full offline/
backend/eval/CI tests, no skips, clean DB teardown, format/lint/types/dependencies
passed. Prior full 283-test PostgreSQL evidence is reused for unchanged scope.
Exact-SHA hosted evidence is pending publication and recorded separately in
`test-results/ticket06-publication-git-ci.json`. Live and D01/D11 remain blocked;
the ticket stays ready-for-human and Phase 3 stays incomplete. No frozen cases or
spending policy changed. See the newest PROGRESS entry for evidence and next steps.
