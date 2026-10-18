# 01: Grounded catalog chat and real-path eval baseline

**What to build:** A guest asks about fictional doctors, specialties, services
or fees and receives authoritative catalog facts through bounded tool calling,
with executable evidence of that behavior.

**Blocked by:** None (can start immediately; Phase 2 entry satisfied).

**Status:** resolved

**Approval gate:** Owner approved Ticket 01 implementation and all four TDD seams
on 2026-10-18. Each paid run, commit and push still requires separate approval.

## Scope and contracts

Follow the Phase 3 plan/spec and existing scoped public catalog services. Deliver
single-turn chat with a multi-step loop, the provider seam, Anthropic adapter and
scripted test provider within this useful slice. No standalone prefactor/framework
ticket is needed. Service fees and doctor consultation fees are distinct.

## Acceptance criteria

- [x] Versioned bounded chat/tool contracts reject extra fields, spoofed roles/authority and malformed arguments/results. Public reads return only active fictional-clinic doctors/specialties/services, exact PKR decimals and bounded pages. Empty/ambiguous matches trigger truthful clarification, not invented doctors, fees or associations.
- [x] A small neutral interface keeps SDK types, Messages formatting, tool_use/tool_result correlation and private continuation inside the Anthropic adapter. Scripted providers exercise the same orchestration/dispatcher. Pin a compatible SDK under Python 3.13; verify strict-schema support for configurable initial claude-sonnet-5-5 and record SDK/model/config without silent fallback.
- [x] Static strict schemas reject extra properties; backend independently validates inputs/outputs. Anthropic uses auto choice with parallel tool use disabled; reject unexpected multiple/illegal calls before dispatch. No copied store=false, forced-tool choices or unsupported sampling parameters. Adapters call services, not routers or arbitrary SQL.
- [x] Server-assembled typed facts/status/action fields cannot be overwritten by model text. Check claims against actual catalog results or use deterministic wording, including free-text fabrication attempts. Citations stay empty; missing policy evidence yields abstention.
- [x] Document/test finite body/context/output/tool-count/provider-call/time budgets and request rate limits. Existing body middleware covers auth/appointments only: cover chat explicitly. No transaction spans provider calls; blocking DB work stays off the async loop. Refusal, malformed/truncated blocks, wrong/duplicate IDs, unknown stops, loops, auth/429/5xx/timeouts and service errors stop safely without partial execution or success claims.
- [x] Synthetic disclosure, injection/exfiltration refusal and no diagnosis/prescription/definitive triage are tested. No invented emergency contact or queued-handoff claim; final clinical wording remains D01/D11-gated.
- [x] Server-only ANTHROPIC_API_KEY configuration uses environment or explicitly loaded ignored local config, examples are placeholders, missing config fails safely. Log/error/report tests exclude keys, cookies, bodies and thinking. Document conditional Anthropic retention separately from local storage; no ZDR claim from key possession.
- [x] Before grading new behavior, wire versioned cases to the real orchestrator/catalog adapters, scripting only the provider and using disposable PostgreSQL for actual service-path assertions. Map scenario personas to real fixtures. Implement executable legality/grounding/state graders and prove wrong-tool, fabricated-fee and forbidden-output behavior fails. Record first mocked behavioral baseline; prior inventory is null quality.
- [x] Positive/negative/adversarial and protocol contract tests verify content ordering, error results, truncation and safe continuation. Reports distinguish executed, pending, blocked and future-phase cases; gate failures are nonzero. Scripted success does not establish live model quality or measured tokens/cost.

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

Implementation and verification are complete at the four approved seams.
POST /chat is public, same-origin,
single-turn and default-disabled for paid access. Five strict read tools call
existing catalog services, with typed fixed-clinic facts and deterministic text.
No persistence, private appointment data, availability or mutations were added.

Decisions/contracts: docs/CHAT.md and docs/DECISIONS.md (2026-10-18 Ticket 01).
Anthropic 1.15.0/httpx2 2.13.1 on Python 3.13.13; configurable Sonnet 5.5, auto
choice, parallel disabled, zero retries. SDK schema transformation uses the
supported strict subset; original backend constraints remain enforced.

Verification so far: final focused chat/provider/real-PostgreSQL/grader suite
67 passed, zero failures/errors/skips (test-results/p3-final-chat.xml). All-case
mocked baseline phase3-ticket01-mocked-v1: 13 passed, 2 future cases pending,
zero failed/blocked/skipped (test-results/p3-catalog-all.json). Dev: 12 passed,
one future case pending. Prior phase1-v1 remains seven unexecuted inventory cases
with null quality; no numeric model-quality delta is claimed. Dataset SHA-256:
5e9ed87ee3216a1a069f4749496eb367241e2d24048bb3ace9685fa981a628d6.

Format/lint/strict types (71 Python files) and pip check pass. Bandit has zero
medium/high findings; 12 low findings were reviewed as fixed Git subprocesses,
shape assertions, null token metadata and empty SDK auth-token override. pip-audit
audited 75 third-party packages with zero vulnerabilities after upgrading the
local venv pip from 26.0.1 to 26.2.1; editable careflow-ai is source-reviewed,
not available on PyPI. Audit tooling was installed only into the ignored venv.

Required code-review skill: Standards found no actionable issues; Spec found a
post-header body-stream error gap. Three red tests reproduced ReadError,
ReadTimeout and RemoteProtocolError; catching HTTPError at the adapter fixed it.
All 27 provider tests pass and the reviewer closed the P1. No remaining findings.

Limitations remain explicit: no paid call/live account verification/model quality,
tokens/cost null in mocked reports, D01/D11 wording/reviewer still release-gated,
hosted exact-SHA CI awaits separate commit/push permission. No Ticket 02 work.

Final broad regression: **316 passed**, zero failures/errors/skips, including
149 backend unit, 129 PostgreSQL integration, 23 eval infrastructure/grader and
15 serial CI command regression cases (test-results/p3-full.xml, 1139.68s).
That run began before four final focused tests were added; the final current-code
suite passed **67/67** (24 chat, 27 provider, 10 PostgreSQL, 6 grader) after the
last fixes. The runs cover **320 distinct test cases**, with 63 overlapping cases;
do not add their counts as distinct tests.
An additional red/green case ensures valid facts followed by an uncorrected
malformed call abstain rather than release partial answers. The affected all-case
baseline reran **13 passed/2 pending**, unchanged with zero regressions, and its
source hash matches final implementation. Final format/lint/strict types pass.

Maintenance-catalog audit passed with **zero disposable database and temporary
role leftovers** (test-results/p3-database-safety.json); audit never connected to
careflow_ai. Removed the exact temporary DPAPI credential, setup/runner/audit and
dataset-generator helpers after verification. Local Markdown links, dataset hash,
whitespace and exclusion of secrets/temporary artifacts from the 28-file review
manifest pass (test-results/p3-review-manifest.json). All required local evidence
is complete. At local handoff nothing was staged, committed or pushed.

## Implementation Git milestone — 2026-10-18

Owner subsequently approved one implementation commit with message
`feat: implement grounded catalog chat and anthropic tools` and a normal push to
origin/master, conditional on final review of the implementation and staged diff.
The staged review must verify no secrets, credentials, temporary helpers,
generated reports or unrelated files, and pass git diff --cached --check.

Final staged review found that core.autocrlf=true would convert the new catalog
dataset to CRLF on a fresh Windows checkout, breaking its exact-byte checksum.
Extended the existing scoped .gitattributes LF rule to that dataset; final scope
is 29 files (the original 28 plus this one-line portability fix). Verify staged
dataset bytes and an exported autocrlf=true checkout against its manifest before
committing. No business behavior, later phase or test-case count changes.

Hosted verification is pending when this implementation commit is prepared.
The latest exact-SHA push/Actions result is recorded in the ignored local report
`test-results/p3-implementation-git-ci.json` and final handoff. This allows the
post-push status to be updated without another commit or a dirty working tree.
Live-provider verification and D01/D11 clinical wording review remain pending;
no paid calls or Ticket 02 work is authorized.
