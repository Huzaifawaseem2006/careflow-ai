# Evaluation and continuous verification strategy

Status: design only. No dataset, harness, baseline, model-backed run or results exist. The owner requires evaluation infrastructure and a versioned synthetic dataset during Phase 1, before AI behavior. PRD Section 12 defines provisional targets; this document defines how to measure them.

## Taxonomy and case contract

Case groups: FAQ grounded answer and citation; absent/expired/conflicting source; retrieval recall and access filtering; doctor/fee/slot lookup; required/forbidden tool calls; ownership/role isolation; proposal/confirmation/replay; booking concurrency/idempotency; cancellation/reschedule; prompt injection and exfiltration; symptoms/medication/escalation; provider timeout/malformed output; Arabic/Urdu factual parity only when post-MVP support is implemented.

Future `evals/cases.jsonl` is immutable per dataset version. Each synthetic case needs stable ID, group, input turns, actor/clinic fixture, knowledge corpus version, expected required/forbidden tool calls, expected source IDs or abstention, expected state assertions, severity and partition (`dev` or held-out). Never include real patient data. Keep held-out cases separate from prompt tuning; add regression cases for observed failures with provenance and review.

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

The first Phase 1 task creates only deterministic foundation and verification entry points. During Phase 1, add a versioned synthetic `evals/cases.jsonl`, schema validation and a report-producing harness entry point with a clearly labeled offline mode. The real orchestrator path cannot be exercised until it exists; wire the same harness to that path before Phase 3 AI behavior. Seed positive, negative, adversarial, missing-evidence, misuse, privacy and escalation cases even if some are initially marked pending implementation. A pending case is never counted as passed. Fixture/corpus content, baseline, model ID and schema versions remain pending because none exists.
