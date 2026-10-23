# 02: Reviewed corpus and bounded indexing

**What to build:** An operator can turn the exact reviewed synthetic clinic
documents into a traceable, versioned pgvector corpus, safely repeat the operation
and activate only a complete eligible index. This is independently verifiable
through the operator interface and real database; no patient UI is required yet.

**Blocked by:** None (ticket dependency frontier; implementation, corpus approval
and external-run gates below still apply).

Status: ready-for-agent

## Scope and reuse

Follow the approved [MVP PRD and draft corpus](../../../plans/mvp-vertical-slice/PRD.md#draft-synthetic-corpus-for-owner-review)
and [implementation plan](../../../plans/mvp-vertical-slice/IMPLEMENTATION.md).
Reuse PostgreSQL/pgvector, SQLAlchemy/Alembic/readiness, confirmed synthetic
operator/fixture patterns and disposable database safeguards. Add the smallest
versioned source/chunk storage, Voyage adapter and bounded operator indexing/
activation/status maintenance. No uploads, remote ingestion, staff UI or scheduler.
No prefactor or embedding-provider framework is required.

## Acceptance criteria

- [ ] Prepare only the four agreed topics: arrival/check-in, documents to bring,
  accessibility and payment methods. Obtain explicit owner review of exact text
  before indexing; specification approval alone is not recorded as corpus approval.
- [ ] Record immutable document identity/version/title, exact text, clinic/access
  class, reviewer/approval evidence, effective interval and current status. Preserve
  immutable content when superseding or withdrawing it; application reads cannot
  approve or activate sources.
- [ ] Deterministically split self-contained headings/paragraphs into bounded
  passages. Record passage identities/positions/hashes and corpus/chunking/model
  configuration in a manifest; do not silently change approved source meaning.
- [ ] Use Voyage `voyage-4-lite`, explicit 1,024-dimensional float output and
  document input type; store PostgreSQL `vector(1024)`. Disable silent truncation
  and reject wrong dimensions, nonfinite/zero vectors and configuration mismatch.
- [ ] Explicit confirmed activation exposes only a complete approved/effective
  version. Partial provider/database failure never activates partial content and
  preserves the previous usable index. No transaction spans a provider call.
- [ ] Repeating the same indexing inputs neither duplicates passages nor re-embeds
  unchanged content. Changed corpus/model configuration has traceable versioned
  output rather than silently mixing incompatible vectors.
- [ ] Verify the account's actual model-specific free allowance, billing
  restrictions, sufficient headroom and defensible free-only protection before
  any external run. Consider other account usage. Unknown/unavailable/exhausted
  protection stops calls; no overages, recharge, purchased credits or fallback.
- [ ] Bound texts, requests/tokens, timeouts and retry behavior. Account for
  potentially consumed quota after ambiguous failures. Published allowances,
  rate limits and a local counter alone do not prove overages cannot occur.
- [ ] Secrets stay server-side and out of source, command arguments, logs and
  reports. Default tests/CI cannot invoke Voyage or Anthropic. No provider deletion
  or retention claim is invented.
- [ ] Migration/readiness and least-privilege application/operator access reflect
  the new storage. Unsafe targets and unapproved writes fail without weakening
  existing synthetic fixture/database safeguards.
- [ ] Required mechanical checks pass; actual account verification/indexing is
  recorded separately. A blocked external run is never reported as real embedding
  generation or measured semantic retrieval success.

## Testing requirements

Use the confirmed operator command -> real service -> disposable PostgreSQL seam,
with only Voyage HTTP scripted for deterministic cases. Verify exact source/
passage oracles, constraints, activation, rerun reuse, partial failures, unsafe
targets, malformed embeddings, redaction and fail-closed quota behavior. This is
an operator vertical slice, not a request for a new patient/admin frontend.
Use strict TDD for source authorization and integrity boundaries; review any new
high-risk seam before implementation.

Run focused adapter/operator tests, real PostgreSQL migration/readiness/permission
tests and applicable format/lint/type/dependency checks. Use the established
PostgreSQL runner serially in an idle checkout. Real Voyage execution requires a
separately authorized bounded free-only run; mocked quota tests cannot establish
the real account's balance or billing protection.

## Completion evidence and handoff

Record commands, counts/skips, migration/permission results, manifest/configuration,
approval record and rerun/failure outcomes. If real indexing is authorized, retain
redacted allowance/protection evidence and actual token usage separately from
estimates. Keep runtime reports/embeddings out of tracked documentation. Distinguish
mechanical implementation verification from real indexing evidence; do not resolve
unmet acceptance criteria silently. Ticket 03 is dependency-ready only once this
ticket's required criteria are satisfied or the owner explicitly approves a change.

## Approval boundaries

Publication does not authorize implementation, source approval, indexing or calls.
Obtain individual ticket approval, exact corpus approval and bounded external-run
authorization at their respective gates. Voyage paid usage is forbidden. No
branch, commit or push without separate approval; no other ticket implementation.

## Comments

Published from the owner-approved five-slice plan on 2026-10-23. The existing
corpus appendix remains unapproved/not effective/not indexed unless later approval
is explicitly recorded. No implementation or external account check occurred here.
