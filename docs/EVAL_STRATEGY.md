# Evaluation and continuous verification strategy

Status: Ticket 06 implements Phase 1 offline infrastructure: versioned synthetic cases, strict validation and JSON reports. No behavioral baseline, model-backed run or real-agent-path result exists. PRD Section 12 defines provisional targets; this document defines how to measure them.

## Taxonomy and case contract

Case groups: FAQ grounded answer and citation; absent/expired/conflicting source; retrieval recall and access filtering; doctor/fee/slot lookup; required/forbidden tool calls; ownership/role isolation; proposal/confirmation/replay; booking concurrency/idempotency; cancellation/reschedule; prompt injection and exfiltration; symptoms/medication/escalation; provider timeout/malformed output; Arabic/Urdu factual parity only when post-MVP support is implemented.

`evals/cases.jsonl` is immutable per dataset version. Its reviewed SHA-256 and schema/dataset/fixture versions are recorded in `evals/manifest.json`; changes require a new dataset version and checksum. LF checkout is enforced for byte reproducibility. Each synthetic case has a stable ID, category/group, input turns, actor/clinic fixture, knowledge corpus version, expected required/forbidden tool calls, expected source IDs or abstention, expected state/response assertions, severity, provenance and partition (`dev` or `held-out`). Never include real patient data. Keep held-out cases separate from prompt tuning; add regression cases for observed failures with provenance and review.

## Harness and evidence

`evals/run_local.py` should invoke the **same orchestrator and service adapters** used by `/chat`, with deterministic fixtures and a mocked external model boundary. It tests actual routing, authorization and state effects, but cannot measure model behavior. A separately labeled live-provider mode calls the configured OpenAI model through the same path. It needs credentials, network and budget; absence is a blocked live run, never a pass. `evals/graders.py` uses deterministic assertions for tool legality, auth, state, idempotency, source IDs and critical safety responses. Any model judge is supplementary and must be calibrated against human-reviewed examples.

Report JSON per run: UTC time, Git revision/dirty flag, model ID, API mode, prompt version, tool schema version, dataset version and partition, corpus/index version, fixture version, case counts, pass rates by group/severity, retrieval recall@k, citation validity, grounded FAQ correctness, tool-selection accuracy, refusal/escalation counts, latency distribution, token counts, estimated/actual cost methodology, failures and skipped/blocked cases. Preserve only safe synthetic traces. Never combine mocked/offline and live metrics in one unlabeled rate.

For retrieval, compare source/chunk recall independently of answer quality. For cited answers, validate that each citation exists, is approved and effective, and supports the associated claim via deterministic expected facts/human review. For booking, inspect committed DB state across distinct connections. Use provider-backed runs to assess natural-language behavior and drift, with repeat counts noted because model output varies.

## Gates

- Every code change: relevant format/lint/type/unit checks where configured; record exact commands and unavailable tooling.
- Every prompt/tool/retrieval/orchestration change: affected cases, compare to previous baseline and record regressions.
- Every auth/booking change: permission, concurrency, idempotency and PostgreSQL integration tests.
- Phase boundary and demo: complete applicable regression suite, both mocked and live where credentials/budget permit; block if critical cases fail. If live is blocked, do not claim live quality targets or deploy a model-backed demo on that evidence.
- PRD provisional targets: zero observed unauthorized access/mutation, duplicate confirmed booking and unconfirmed mutation in gate suite; all critical safety cases pass; >=95% tool-selection, >=90% grounded FAQ correctness, 100% evaluated citation validity. Report sample sizes and confidence limits. Tune gates after a baseline with owner approval; no claim of real-world safety follows from these rates.

## Phase 1 obligation

Ticket 06 supplies seven synthetic seeds: positive, negative, adversarial, missing-evidence, tool-misuse, privacy and escalation. `python -m evals.run_local` validates the entire dataset before selecting the dev partition (five cases); use `--partition held-out` for its two separate cases or `--partition all` for inventory. No agent adapter exists, so all selected cases are pending. Persona references describe scenarios, not authenticated accounts. Corpus/index/model/prompt/tool schema versions are unavailable (`null` or an empty corpus list); no sources, slots, accounts or clinical wording approval are fabricated. Fixture version `ticket04-v1` references the existing synthetic manifest.

Reports label `api_mode` as `offline-infrastructure-only`, include Git revision/dirty state and dataset hash, and explicitly state that the real agent path was not exercised. Status counts always include passed, failed, skipped, blocked and pending. Pass rates use only executed passed/failed cases; no executions means `null`. Group/severity summaries use the same denominator. Behavioral metrics are `null` with an unavailable reason; no latency, tokens, costs, citations or safety success is inferred. Reports omit input turns and credentials. Exit 0 means valid infrastructure execution only; invalid data or unavailable Git metadata exits 2, not a behavioral pass. Output-write errors also fail the command.

`evals/graders.py` currently supplies status accounting only; state/response assertions are human-readable expectations awaiting actual behavioral graders. There is no mocked orchestrator run or live mode yet. Wire this harness to the same `/chat` orchestrator/service adapters and implement deterministic behavioral assertions before Phase 3 AI behavior. Live-provider evidence remains separately gated on explicit approval, credentials and budget. Current output is an infrastructure inventory, not a behavioral baseline or release gate.
