# 03: Retrieval chat and verified citations

**What to build:** A signed-in patient can ask an operational question through
the existing conversational harness and receive either a supported exact source
passage with a verified citation or an honest abstention. The source can be
inspected by exact version, including its current historical/withdrawn status.

**Blocked by:** 02 — Reviewed corpus and bounded indexing.

Status: ready-for-agent

## Scope and reuse

Follow the approved [MVP PRD](../../../plans/mvp-vertical-slice/PRD.md) and
[implementation plan](../../../plans/mvp-vertical-slice/IMPLEMENTATION.md).
Reuse Ticket 02's corpus/adapter, the existing bounded sequential loop, Anthropic
continuation/provider seam, strict tool validation, server-controlled rendering,
owned conversation storage/leases and separate booking confirmation. No alternate
loop, hardcoded FAQ branch, reranker, verifier model or agent framework is needed.

This slice is independently observable through authenticated HTTP, orchestrator,
source read and PostgreSQL. Ticket 01 is not a backend dependency. In the recommended
01-to-05 order, integrate citation/source display into its shell here; if 01 is
not yet available, hand off the tested v2/source contracts and complete that same
presentation scope before Ticket 05's integrated demo gate. Do not claim absent
browser presentation has passed or create a sixth UI ticket.

## Acceptance criteria

- [ ] Add one bounded retrieval tool to the existing loop. It accepts search text;
  backend code supplies clinic/access scope and index configuration. Embed only
  bounded needed search text with Voyage query input type, matching the indexed
  `voyage-4-lite` / 1,024-float configuration. Never embed account/appointment
  records, whole transcripts, cookies, CSRF or action proofs.
- [ ] Use eligible-source exact cosine search, initially top three with stable
  ties; no approximate index. Calibrate threshold on development questions, freeze
  corpus/model/index/configuration before held-out evaluation and never interpret
  similarity as proof that a passage answers the question.
- [ ] Recheck approval, effective interval, clinic/access, source identity/version
  and exact passage provenance before release, including after provider waits.
  Weak, missing, insufficient, conflicting or invalid evidence cannot support an
  assertive answer; show clear abstention without inventing a handoff or policy.
- [ ] Render verbatim supported passages and bounded typed citations in backend
  code. Document/version/passage/title and safe relative source link come only
  from validated metadata; model prose/IDs/links cannot populate citations.
- [ ] Introduce opt-in response version 2 at existing conversation creation and
  persist it immutably. Old requests/rows default to v1. Preserve v1 exact response
  shape, empty citations, current tools and public single-turn behavior.
- [ ] Share endpoints, loop and services; version-discriminate history/replay and
  retain old prompt/tool metadata. Reject negotiation/version mismatch without
  silently migrating a conversation or granting authority.
- [ ] Keep storage disclosure acceptance separate from response negotiation. Show
  a separate Voyage processing supplement before v2 use and verify applicable
  terms before external execution; no implicit change to v1 consent or provider
  deletion promise.
- [ ] The source read returns only known bounded version/passage content under
  existing session/HTTPS/origin/scope/no-store rules, never arbitrary paths/URLs.
  Display exact excerpt provenance and current effective/superseded/withdrawn
  status; historical excerpts remain inspectable as history.
- [ ] Preserve immutable historical answers/citations. Completed replay is visibly
  historical, new questions retrieve current evidence and historical reviews
  cannot recover action proofs. Retrieved/history text remains untrusted data.
- [ ] Preserve doctors, fees, availability, private appointments and all mutation
  rules in existing domain tools. Policy answers and protected review issuance
  may occur in separate turns; no combined review state machine is required.
- [ ] Frozen Phase 3 cases/graders remain unchanged and applicable current-source
  regressions pass. Affected safety wording accurately distinguishes v2 evidence
  without weakening v1 or approved clinical/escalation boundaries.
- [ ] Record separate mechanical/mock, real-embedding retrieval and hosted-tool
  quality results. Missing external evidence remains blocked; no inferred pass.

## Testing requirements

Use authenticated HTTP -> real orchestrator/services -> disposable PostgreSQL,
with external Anthropic/Voyage scripted for deterministic behavior. Test v1/v2
negotiation/replay, source status races, session revocation, cross-user/clinic
denial, forged citations, provider prose, retrieved injection and exact excerpt
oracles. Query private authority must never come from tool arguments/history.
Apply strict TDD to compatibility, authorization and private-source handling;
confirm any new high-risk seam before implementation.

Evaluate retrieval separately against real pgvector and separately approved real
Voyage embeddings: direct questions, paraphrases, unrelated questions, misleading
near-matches, conflicts and unapproved/future/expired/withdrawn/inaccessible sources.
Report retrieval recall, answerable coverage, abstentions and unsupported assertions.
Preserve >=95% held-out tool selection, >=90% grounded FAQ correctness, 100%
citation validity and zero critical safety/auth failures. Freeze development/
held-out sets; no tuning on held-out outcomes. Mocked vectors prove mechanics only.

Run applicable format/lint/type, PostgreSQL integration, v1/frozen eval regression
and affected frontend checks when present. Compare current-source results with
retained baseline without modifying its inputs. Use existing serial database/CI
execution and credential-runner safeguards; external tests remain default-off.

## Completion evidence and handoff

Record exact version/compatibility outcomes, source provenance checks, immutable
history/status behavior, schema/config versions, commands/counts/skips, eval
denominators/uncertainty, measured usage and approval references. Redact secrets
and distinguish API-only from browser evidence. If thresholds fail, report the
blocker rather than reduce coverage or add an unapproved relevance pipeline.
No full Phase 3/4 closure or clinical approval follows from this ticket.

## Approval boundaries

Publication is planning only. Obtain individual implementation approval; new
source text requires owner review. Voyage calls require verified free-only access
and bounded-run approval; Anthropic paid cases/model/maximum cost require their
existing approval/ledger. No unauthorized branch, commit, push or next ticket.

## Comments

Published from the approved dependency graph on 2026-10-23. No implementation,
embedding generation, API call or evaluation was executed for this ticket.
