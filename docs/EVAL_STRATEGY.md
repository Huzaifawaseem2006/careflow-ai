# Evaluation and continuous verification strategy

Ticket 06 adds the [combined Phase 3 gate and proposed live approval plan](PHASE3_EVALUATION.md).
The frozen 32-case real-path matrix, paid controls and held-out model denominator
supersede future-harness descriptions below. Actual evidence remains in PROGRESS;
scripted results never establish live model quality.

Status: Phase 1's offline inventory remains historical. Phase 3 Ticket 01 adds a separate versioned mocked behavioral catalog baseline on the real orchestrator and PostgreSQL service path. No live model quality or phase-exit result is established. PRD Section 12 defines provisional targets; this document defines how to measure them.

## Phase 3 Ticket 01 mocked behavior

`python -m evals.run_catalog --partition dev --report evals/results/catalog-mocked.json`
requires a local `TEST_DATABASE_URL` pointing to the `postgres` maintenance DB.
It creates/drops only a random `careflow_test_<32 hex>` database, migrates and
loads real fixtures plus a foreign-clinic distractor, then scripts only the
external provider. The snapshot grader refuses any other target before queries.
No API key, paid call, permanent credential storage or conversation store is used.

`evals/catalog_v1/` preserves the seven seed cases and adds eight Ticket 01 cases,
with its own manifest/version/SHA-256. `evals/cases.jsonl` and its Phase 1 manifest
remain unchanged. Default dev selection has 13 cases: 12 executable and one
future booking case. All selection has 15: 13 executable and two future cases
(booking and owned appointments). Held-out clinical structural behavior is checked
only at final verification; it is not used to tune provider/prompt behavior.
D01/D11 exact wording/reviewer remains a separate release gate.

Graders check executed tool legality, literal known-good fixture rows, exact
price/name grounding, forbidden success/clinical outputs, abstention and full
before/after database state hashes. Mutation controls must reject wrong tools,
fabricated fees, forbidden outputs and changed state; a CLI integration test
deliberately changes an oracle and requires exit 1 with a failed-case report.
Exit 2 indicates blocked/invalid infrastructure. Exit 0 covers the applicable
Ticket 01 cases only; pending later cases do not become passed placeholders.

Baseline ID: `phase3-ticket01-mocked-v1`. Reports include Git/dirty/source hashes,
dataset/schema/prompt/config/SDK versions, fixture persona resolution to existing
demo identities and effective public-guest access, safe correlations/tool outcomes
and latency. No request/response bodies, secrets or private reasoning are reported.
Tokens, costs and model tool-selection accuracy remain null: scripting measures
the application's behavior under selected provider outputs, not model quality.
The previous inventory had zero executions and null quality; there is no numeric
quality improvement to infer. Final executed evidence belongs in ticket/progress.

The following sections retain the Phase 1 inventory contract as history.

## Taxonomy and case contract

Case groups: FAQ grounded answer and citation; absent/expired/conflicting source; retrieval recall and access filtering; doctor/fee/slot lookup; required/forbidden tool calls; ownership/role isolation; proposal/confirmation/replay; booking concurrency/idempotency; cancellation/reschedule; prompt injection and exfiltration; symptoms/medication/escalation; provider timeout/malformed output; Arabic/Urdu factual parity only when post-MVP support is implemented.

`evals/cases.jsonl` is immutable per dataset version. Its reviewed SHA-256 and schema/dataset/fixture versions are recorded in `evals/manifest.json`; changes require a new dataset version and checksum. LF checkout is enforced for byte reproducibility. Each synthetic case has a stable ID, category/group, input turns, actor/clinic fixture, knowledge corpus version, expected required/forbidden tool calls, expected source IDs or abstention, expected state/response assertions, severity, provenance and partition (`dev` or `held-out`). Never include real patient data. Keep held-out cases separate from prompt tuning; add regression cases for observed failures with provenance and review.

## Harness and evidence

`evals/run_local.py` should invoke the **same orchestrator and service adapters** used by `/chat`, with deterministic fixtures and a mocked external model boundary. It tests actual routing, authorization and state effects, but cannot measure model behavior. A separately labeled live-provider mode calls the configured Anthropic model through the same path. It needs credentials, network and budget; absence is a blocked live run, never a pass. `evals/graders.py` uses deterministic assertions for tool legality, auth, state, idempotency, source IDs and critical safety responses. Any model judge is supplementary and must be calibrated against human-reviewed examples.

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
