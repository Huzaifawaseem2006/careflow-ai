# 05: Integrated verification and portfolio handoff

**What to build:** A reviewer can follow local setup, complete the actual cited
FAQ-to-confirmed-booking journey and inspect credible screenshots, walkthrough,
test/evaluation evidence and limitations. This integrates existing slices without
adding a new product feature or claiming production approval.

**Blocked by:** 03 — Retrieval chat and verified citations; 04 — Conversational
booking journey (transitively 01 and 02).

Status: ready-for-agent

## Scope and reuse

Follow the approved [MVP PRD](../../../plans/mvp-vertical-slice/PRD.md) and
[implementation plan](../../../plans/mvp-vertical-slice/IMPLEMENTATION.md).
Reuse all four slices, existing gate/report/eval conventions, confirmed synthetic
account/catalog/schedule/slot provisioning and PostgreSQL credential runner.
Finish only agreed integration wiring, setup, source display if not yet integrated,
screenshots, short walkthrough and evidence. Do not expand scope into staff,
management UI, clinical content, deployment or a sixth ticket.

## Acceptance criteria

- [ ] Setup instructions take a reviewer from the supported local prerequisites
  to the real application without committing credentials/certificates or weakening
  HTTPS/CSRF/origin protections. Account creation and fresh slot generation use
  existing explicit confirmed operator workflows, never chat/GET side effects.
- [ ] The actual local journey succeeds: sign in -> disclosure/supplement ->
  operational FAQ -> verified exact source -> AI-tool doctor/slot discovery ->
  exact fee/time review -> distinct confirmation -> persisted My Appointments.
  Citation/source presentation is integrated with the authenticated frontend.
- [ ] Demonstrate unsupported/misleading policy abstention and no appointment
  mutation from chat alone. Current data comes from authoritative services, not
  fabricated walkthrough fixtures or pre-rendered success screens.
- [ ] Real provider execution uses reviewed corpus, verified Voyage free-only
  allowance/protection and separately authorized bounded Anthropic calls. If
  blocked, finish unaffected no-cost verification but do not claim the actual
  journey or local portfolio demo readiness passed.
- [ ] Screenshots and a short walkthrough are redacted and clearly synthetic/
  development-only. They are evidence of executed behavior, not substitutes for
  tests, source provenance or live quality evaluation.
- [ ] Full applicable backend/offline/real PostgreSQL/CI subprocess regression,
  frontend type/lint/build/browser checks and affected evaluations pass. Preserve
  frozen Phase 3 inputs/graders and record baseline comparison with current-source
  fingerprints; no required failure/skip is silently treated as a pass.
- [ ] Report >=95% held-out tool selection, >=90% grounded FAQ correctness and
  100% citation validity only where actually measured with sample size/uncertainty.
  Distinguish deterministic/scripted, real-embedding retrieval and hosted-model
  evidence; do not infer full Phase 3 live-gate closure from a single walkthrough.
- [ ] Critical auth/private-data, unconfirmed mutation, duplicate booking,
  source-validity, injection/safety or integrity failures block even this local
  demo. Historical citations/reviews and cancellation/rescheduling notices retain
  their agreed behavior after integration.
- [ ] Publish three separate statuses with evidence: implementation verified,
  local portfolio demo ready and production/release approved. The development-only
  local-demo exception does not complete Phase 3/4/5, D11 review or clinical approval.
- [ ] Preserve all exclusions and outstanding Phase 3 live/D11 gates. Production/
  release approval remains pending unless separately completed and authorized;
  no public deployment is part of this ticket.
- [ ] Document actual setup, source revision, dependency/corpus/index/model/prompt
  versions, commands/results, quota/usage, remaining limitations and the next
  owner action. Do not mark incomplete acceptance criteria resolved.

## Testing requirements

Run the complete browser path through the real trusted HTTPS proxy/API/services
and disposable PostgreSQL with scripted external providers for deterministic
regressions. Separately execute only the specifically authorized real-provider
walkthrough/eval cases. Exercise auth/isolation, citation/source transitions,
unsupported questions, stale/expired review, ambiguous retry/refresh and provider
failure after commit. Validate state and passage provenance independently.

Run the full applicable regression once implementation stabilizes, reusing passing
unchanged evidence rather than overlapping full suites. PostgreSQL and CI
subprocess regressions run serially in an otherwise idle checkout using the
existing runner, private-temp recovery, teardown and redacted timing rules.
Frontend checks may run independently only with separate mutable outputs.
Hosted Actions at publication remains subject to separate Git approval; a missing
hosted run is reported explicitly, not manufactured. No paid/default external CI.

## Completion evidence and handoff

Retain redacted commands/logs, numeric timings, counts/skips, cleanup outcomes,
baseline comparisons, real-provider approval/usage references, walkthrough and
screenshots. State which readiness level is achieved and why others are blocked.
Review the complete working diff, untracked files and sensitive/generated artifacts
before requesting any Git approval; show documentation changes. Before an authorized
commit, review the exact staged diff and whitespace. Every commit and push requires
separate owner approval.
Hand off the completed milestone without starting production work or another phase.

## Approval boundaries

Publication is planning only. Obtain individual implementation/integration approval
and every applicable external-run approval. No Voyage paid overages, provider
fallback, branch, commit, push, deployment or clinical/production-readiness claim
is authorized by this ticket's existence.

## Comments

Published from the approved five-slice plan on 2026-10-23. No implementation,
integration test, external call, screenshot or demo result has been executed here.
