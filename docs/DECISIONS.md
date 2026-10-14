# Decisions and PRD review

2026-10-14. Status labels: **fixed** = explicitly required by owner/PRD; **proposed** = needs review; **open** = no selection. No owner approval of proposed architecture has been received.

## Fixed

- Stack and synthetic-data restriction; one modular monolith, one bounded tool orchestrator.
- Appointment records are the only initial patient history.
- Auth and ownership in services; confirmation before domain writes; atomic booking and idempotency.
- Evaluation before AI behavior; actual execution evidence; critical failures block release.
- Phase 0 only until owner approves. Supplied AGENTS instructions preserved with short operating additions.

## Approval register

| ID | Decision | Recommendation / consequence | Needed before |
| --- | --- | --- | --- |
| D01 | Clinic locale, timezone, currency, emergency locale | One synthetic clinic, English first; do not infer clinic locale from developer timezone. Owner supplies locale values. | Seed/schedule and safety wording |
| D02 | Identity | Local password + server sessions for a self-contained demo, or external OIDC if owner prefers reduced credential handling. Registration/recovery and hosted access must be defined. | Auth task in Phase 1 |
| D03 | Slot model / duration / horizon / cancellation window | Materialized fixed non-overlapping slots; duration, horizon and cancellation/reschedule rules require owner values. | Phase 2 |
| D04 | Confirmation and idempotency | Server proposals bound to actor, payload, resource/policy/fee version; separate confirmed UI event. TTL and key retention require values. | Phase 2 |
| D05 | Handoffs and guest actions | Allow guest request using server-scoped conversation capability and explicit consent; all staff access assigned-clinic only. Resolve PRD mutation-auth conflict. | Chat/handoff |
| D06 | Corpus and approval | Local synthetic documents, admin approval, immutable published versions; withdraw/version rather than overwrite. Name content reviewer. | Phase 4 |
| D07 | Model, embeddings and eval budget | Configurable explicit model IDs; compare a baseline only after capability check. No live run or price claim yet. | Phase 3 live eval |
| D08 | Hosting and demo access | Local Compose first; select host, TLS and protected demo accounts before publishing. | Phase 7 |
| D09 | Staff and multilingual scope | Minimal appointments/handoff queue for P0; catalog/schedule/knowledge CRUD P1; Arabic after English gates. No reminders/MCP for first demo. | Phase plan approval |
| D10 | Retention and deletion | Disclosed synthetic history, configurable retention, redacted audit. Exact durations, deletion behavior, handoff retention and audit exceptions require approval. | Persistence for chat |
| D11 | Clinical wording review | Owner names appropriate reviewer and approves locale-specific escalation text before demo; no clinical validation claim. | Safety eval/release |
| D12 | Schema additions and API changes | Proposals/idempotency tables, fee snapshot, session storage as applicable; reschedule tools/proposal endpoints described in contracts. | Schema/API implementation |

Only overall Phase 1 entry approval blocks the first health-check slice; the remaining decisions block their specific dependent tasks. Do not ask every open question before making unrelated progress.

## Contradictions, gaps and risks

- J7 says Arabic in a second phase, FR-12 marks it P1 and Phase 6 says optional. Recommend later explicit gate; no parity claim.
- J5 offers handoff, but Section 8 requires all mutation routes to be authenticated. Guest handoff needs an approved exception with capability/consent or a sign-in requirement. Public chat itself writes ephemeral state; distinguish domain writes from routine message submission instead of demanding confirmation per message.
- Cancel/reschedule are P0, but tool list omits propose/confirm reschedule. Add only after contract approval.
- Section 8 exposes mutation routes without proposal routes or proof transport. A model-generated `confirmed=true` is insufficient; bind a server proposal to an actual user event.
- Single `role` does not fully express clinic scope or handoff-operator access. Define permission mapping without adding enterprise RBAC.
- Slot duration/horizon, overlapping schedule edits, fee changes, DST behavior and status transitions are unspecified. Do not assume unique start time prevents arbitrary interval overlap.
- Appointment idempotency key alone cannot cover all mutations. Define actor/operation scoping, payload mismatch and retry retention.
- Doctor filters include location, but initial clinic schema has no explicit location field. For one-clinic MVP filter by clinic ID; decide whether free-text location is actually needed before adding fields.
- Source links can be invalid or unsafe; use stable backend citation endpoints, never model-invented URLs. Decide knowledge clinic/access scope and effective-version conflicts.
- Chat ownership, guest-to-patient transfer, disclosure/deletion, staff access and audit retention are not fully modeled.
- Handoff is P0 but broad dashboard P1/Phase 5; an actual authorized queue is needed to avoid a fake handoff claim.
- Observability is P1 yet eval evidence and safety require traces from the first AI slice. Implement minimal redacted metrics early.
- Eval targets are provisional, sample size and held-out governance are missing. Baseline must precede calibration; zero observed violations is not a security guarantee.
- Preparation instructions can cross into medical advice. Only approved clinic material; never generate treatment guidance.
- P0 surface is large: defer Arabic, Redis, reminders, MCP, richer records and real integrations to avoid scope creep.

## Skills audit

Recursive name scan of `C:/Users/USER/.codex/skills` and `C:/Users/USER/.codex/plugins` returned no `karpathy-*` paths. No such skill is in the supplied skills catalog. No third-party skill was installed or executed; compatibility cannot be assessed without source contents.

Options if later requested: provide a specific repository/version for read-only review, then manually place a reviewed Codex-compatible `SKILL.md` under the personal skills directory; or use the available skill-installer after source review and explicit installation authorization. Review instructions, referenced resources and scripts, provenance/license, path assumptions and Codex tool compatibility. Never pipe a remote installer into a shell. Current AGENTS rules apply the requested principles without a third-party package.

## Source checks

Official OpenAI function-calling, Pydantic strict-mode and PostgreSQL locking/index pages were opened on 2026-10-14; links and limited implications are in ARCHITECTURE.md. No package version or model capability has been selected by this check. Reverify relevant APIs against pinned versions when implementing.
