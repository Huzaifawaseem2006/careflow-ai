# Patient portfolio MVP — implementation plan

Status: owner-approved plan; five local tickets published 2026-10-23. Ticket 01
implementation verified on 2026-10-23; later tickets retain separate approval gates.
Authority: [MVP PRD](PRD.md), the existing project contracts and the owner's scoped
decisions. The five slices below are published as separate local tickets; their
`ready-for-agent` labels are not executable work approvals. The
[local specification entry](../../.scratch/mvp-vertical-slice/spec.md) is retained
unchanged as the historical drafting record; approval/publication is recorded here
and in DECISIONS/PROGRESS. Ticket 01 now provides the authenticated v1 frontend;
see [execution evidence and remaining gates](../../docs/PROGRESS.md).

## Foundation and scope

Inspected clean checkout: `faf65fb1fe28d5225adf10cff39ccc6a8df0a372`.
Existing backend includes sessions/CSRF/origin controls, catalog, persisted
availability, owned conversation storage and real booking/cancel/reschedule
review/confirmation services. Current chat discards provider prose and renders
validated service results. V1 explicitly requires empty citations. PostgreSQL has
the vector extension, but no corpus, embeddings or retrieval implementation.
No frontend package exists at this checkpoint. Architecture overview prose had
older status statements; code and specific implemented contracts establish reuse.

Preserve the [project PRD](../../PRD.md), [Phase 3 plan](../phase-3-ai-tools.md),
[Phase 4 plan](../phase-4-rag.md) and [Phase 5 plan](../phase-5-frontend.md).
This milestone does not claim their exit gates or remaining features are complete.
Its scoped development-demo exception is recorded in [DECISIONS](../../docs/DECISIONS.md).

## Sequence and dependencies

| Ticket | Main result | Dependencies |
| --- | --- | --- |
| [01 — Authenticated frontend foundation](../../.scratch/mvp-vertical-slice/issues/01-authenticated-frontend-foundation.md) | Next.js, same-origin HTTPS, sign-in and disclosed conversation lifecycle | No ticket blockers; individual implementation approval |
| [02 — Reviewed corpus and bounded indexing](../../.scratch/mvp-vertical-slice/issues/02-reviewed-corpus-bounded-indexing.md) | Approved source versions, pgvector storage, Voyage adapter and repeatable indexing | No ticket blockers; individual implementation approval; corpus/free-only gates before real indexing |
| [03 — Retrieval chat and verified citations](../../.scratch/mvp-vertical-slice/issues/03-retrieval-chat-verified-citations.md) | One retrieval tool, opt-in v2, source viewer, abstention and evals | 02 |
| [04 — Conversational booking journey](../../.scratch/mvp-vertical-slice/issues/04-conversational-booking-journey.md) | Real doctor/slot results, protected review/confirmation and persisted appointments | 01 |
| [05 — Integrated verification and portfolio handoff](../../.scratch/mvp-vertical-slice/issues/05-integrated-verification-portfolio-handoff.md) | Complete journey, regression/eval evidence, setup, screenshots and walkthrough | 03 and 04, transitively 01/02 |

Recommended execution order is 01, 02, 03, 04, 05, one approved implementation
ticket per fresh session. The dependency graph permits 04 before 03; this is not
authorization for simultaneous agents or overlapping mutable test runs. Ticket 03
can verify its backend API without requiring a complete frontend; source rendering
in the integrated chat is finalized with the frontend during the existing slices.
Do not add a sixth infrastructure, corpus, evaluation or portfolio ticket silently.

The target is approximately one agent-assisted day. Preserve necessary checks;
if access/setup or failures exceed that target, report the limitation. Defer
optional polish before proposing any change to agreed functional scope.

## Ticket 01 — Authenticated frontend foundation

Reuse: existing CSRF bootstrap, patient login/current-user/logout, owned
conversation creation/read/delete/turn endpoints, storage disclosure and retention.

Add: minimal Next.js/TypeScript/Tailwind shell; sign-in, main chat and My
Appointments navigation; same-origin HTTPS API forwarding; authenticated UI state;
disclosure acceptance and conversation resumption using backend-owned history.
Use normal responses, not streaming. No registration, guest interface or recovery.

Integration: browser HTTPS localhost origin proxies an allowlisted API prefix to
HTTPS loopback FastAPI. Certificates must be trusted at both hops. Configure the
backend to the exact browser origin; preserve original Origin, cookies, CSRF and
no-store. Keep certificates/private keys and configuration secrets out of Git.
Do not make runtime/test security depend on permissive CORS or disabled TLS checks.
The existing v1 path can establish this slice before v2 is available. Prepare a
place for the Voyage supplement without falsely asserting its terms are verified.

Acceptance: real sign-in and logout, current patient session recovery, consent
before storage, no protected chat before sign-in, useful auth errors, cleared
protected state on expiry/logout, keyboard-accessible responsive forms. Patient B
cannot read patient A's history; CSRF/foreign Origin fail through the real proxy.
No model calls are required to verify auth. Script only the external provider for
conversation behavior; label it. My Appointments content completes in slice 04.

Checks/evidence: frontend build/type/lint; focused browser tests using real API/DB;
affected auth/conversation tests and real PostgreSQL permission tests. Record
commands, versions, counts/skips, local certificate trust procedure and redacted
screenshots. Unverified proxy behavior is a blocker, not a documentation-only pass.

## Ticket 02 — Reviewed corpus and bounded indexing

Reuse: native PostgreSQL/pgvector, SQLAlchemy, Alembic/readiness, fixture/operator
safety patterns, disposable integration databases and server-only secret handling.

Add: the four [draft corpus documents](PRD.md#draft-synthetic-corpus-for-owner-review)
after owner text approval; immutable source/version/chunk metadata; vector storage;
bounded Voyage embedding adapter; deterministic chunking and index manifest;
confirmed operator indexing/activation and status maintenance. No staff UI,
uploaded files, remote ingestion or scheduler. Operator status maintenance exists
only to enforce effective/superseded/withdrawn source rules.

Integration: use `voyage-4-lite`, explicit 1,024-dimensional floats and document
input type; query input type is exercised in slice 03. Store `vector(1024)` and
record model/dimension/chunk hashes. Validate input/output bounds, disable silent
truncation, reuse unchanged vectors and prevent incomplete activation. Keep
network calls outside DB transactions. Update readiness and minimal application
permissions for the new migration; application code cannot approve source data.

Acceptance: exact owner-approved content/version is traceable to every passage;
unapproved/partial data is not active; repeat indexing does not duplicate chunks
or re-embed unchanged content; failures retain the previous usable index. Reject
malformed vectors, wrong configuration and unsafe targets. Keys never enter source,
arguments, logs or reports. External execution stays disabled without verified
account allowance, free-only protection and explicit bounded-run authorization.

Checks/evidence: focused adapter tests with mocked HTTP; real PostgreSQL migration,
constraints/operator activation and rerun/failure tests; an approved external
indexing record later identifies corpus/hash/model/config/usage and quota evidence.
Actual account balance/billing protection cannot be established with mocks.
If that gate is blocked, report mechanical implementation separately from actual
indexing; do not claim real embeddings were generated or a semantic index passed.

## Ticket 03 — Retrieval chat and verified citations

Reuse: the custom sequential loop, Anthropic provider seam, typed tool arguments/
results, deterministic rendering, conversation storage/leases/ownership and existing
mocked/live eval separation. Reuse slice 02's source/index metadata and adapter.

Add: one bounded retrieval tool; exact cosine search over eligible sources;
development-calibrated threshold/top-three candidates; supported extractive
answers, typed citations, protected exact-version source API/view and abstention.
Add opt-in response v2 at conversation creation, immutable stored version and
version-discriminated history/replay. Old requests/rows stay v1; public chat stays
v1; no duplicate loop or replacement endpoints. New prompt/tool metadata applies
only where negotiated. Integrate v2 citation display and provider disclosure in
the frontend shell when present; backend acceptance remains independently testable.

Acceptance: model requests retrieval through the real loop, never a hardcoded FAQ
branch; sources are eligible before search and rechecked before answer release;
every excerpt and relative source URL has verified provenance. Model text cannot
forge citations or claim unsupported policy. Unsupported/weak/conflicting evidence
abstains. Historical excerpts stay immutable and visibly historical; source view
shows current status. New turns use current evidence. No history/replay can recover
booking proofs. Existing v1 exact payload behavior, frozen cases and graders stay
unchanged. The Voyage supplement is presented before v2 conversation acceptance;
no transcript/private appointment payload is embedded.

Checks/evidence: real HTTP/orchestrator/DB tests with external responses scripted;
legacy v1/v2 replay, source transition races, patient isolation, retrieved injection
and fabricated citation tests. Separate real-pgvector retrieval evals with real
Voyage embeddings from mocked-vector tests. Freeze dev/held-out cases/config and
report recall, FAQ correctness, unknown/near-match rejection, answerable coverage,
100% citation validity, counts and usage. Reuse the project's >=95% tool selection,
>=90% grounded FAQ correctness targets; retain all critical negative-case gates.
Run affected existing evals and compare with the current-source baseline without
editing frozen Phase 3 inputs. Missing external evidence stays labelled blocked.

## Ticket 04 — Conversational booking journey

Reuse: actual doctor/fee/availability tools, conversation turn semantics, booking
review action, separate `POST /appointments`, owned appointment listing and
backend permission/capacity/revalidation/idempotency/audit services. Do not change
appointment business rules or invent a frontend confirmation service.

Add: render real tool facts as readable/selectable results that feed conversation;
render exact live booking reviews; an explicit confirm control; My Appointments
from the existing authorized API. Handle loading/empty/auth/provider errors,
expired/stale review, uncertain confirmation, exact retry and refresh reconciliation.
Cancellation/rescheduling actions display an unavailable-in-demo notice; never
route them to booking confirmation. Frontend restrictions confer no authorization.

Acceptance: model/tool-based discovery leads to a real persisted slot; no fixture
response substitutes for actual domain results. Review displays exact fee/time/
timezone/deadline and no-hold semantics. A chat message alone cannot book. Proof
and one stable retry key exist only in page memory and protected requests. After
timeout, exact retry uses the same proof/key; refresh never auto-submits a new-key
mutation or treats an absent list item as proof of no in-flight booking. Definitive
stale rejection requires fresh review/confirmation. Current DB state establishes
success; history stays non-executable; provider failure after commit cannot erase
the appointment. Clear protected UI state on logout/expiry.

Checks/evidence: browser positive/negative flows through real HTTPS/API/DB with
external provider scripted; actual provider walkthrough only with separate paid
approval. Run affected appointment/auth/conversation checks, including real
PostgreSQL permissions, concurrency and idempotency. Record independent state
assertions for no unconfirmed/duplicate mutation and preserved cancel/reschedule
backend behavior. Do not capture proofs, credentials or keys in screenshots/traces.

## Ticket 05 — Integrated verification and portfolio handoff

Reuse: all four slices, existing gate/eval/report conventions, saved PostgreSQL
credential runner, CI and outstanding Phase 3 gate records. No new product feature.

Add: README/local setup instructions, bounded synthetic fixture/account/schedule
preparation, a short walkthrough and redacted screenshots, current-source regression
and evaluation evidence, explicit known limitations and all three status labels.
Use the existing confirmed operator provisioning and slot generation; do not
silently create credentials, schedules or fabricated slots through a GET/chat tool.

Acceptance: owner/reviewer can follow setup and complete the actual synthetic
journey with real providers under separately authorized calls. Show a verified
source and independently persisted booking. Also demonstrate unsupported policy
abstention and explicit confirmation separation. No screenshots or scripted
provider run alone can establish local portfolio demo readiness. Record source
revision, commands, dependencies, corpus/index/model/config versions, results,
quota/usage and any blocked/skipped checks. Preserve Phase 3 live/D11 status and
do not mark Phase 4/5 complete. No critical known auth, safety, booking, citation
or data-integrity failure is acceptable for the development-only demo.

Checks/evidence: full applicable backend/offline/real-PostgreSQL/CI subprocess
regression; frontend type/lint/build and end-to-end browser checks; affected evals
against baseline; supported screenshots/walkthrough and setup verification.
Reuse passing evidence for unchanged scope within this task and avoid overlapping
full suites without cause. Hosted Actions at the milestone follows separately
approved publication; report hosted status separately, never imply a run occurred.
Actual Phase 3 held-out live quality closure remains separate from the bounded
local walkthrough; one successful walkthrough cannot satisfy its accuracy gate.

## Test boundaries, approvals and execution discipline

The primary seam is browser -> same-origin HTTPS -> real FastAPI services -> real
disposable PostgreSQL. Focused tests reuse the existing HTTP/orchestrator seam;
direct retrieval evaluation separates vector relevance from tool choice. Script
external Anthropic/Voyage calls in deterministic regressions, never transactional
state. This reuses the test approach in the owner-approved specification.
Ticket-specific TDD seam
approval remains necessary for new high-risk boundaries, with prior approvals
reused only within their established scope.

Use [the existing PostgreSQL runner](../../docs/POSTGRES_TESTING.md) for integration
tests; preserve private credentials outside Git. Observe private-temp preflight,
normal-host retry and timing/recovery instructions. Run PostgreSQL suites and CI
subprocess regressions serially in an otherwise idle checkout. Parallel checks
are allowed only with independent mutable outputs. No password requests in chat,
temporary credential substitutes or unsafe database targets. Preserve redacted
logs/numeric artifacts under ignored test-results locations.

## Completion statuses and external gates

| Status | Required distinction |
| --- | --- |
| Implementation verified | Required code/checks and applicable mocked evaluations pass. Real embedding/model quality is separately labelled; no inferred live pass. |
| Local portfolio demo ready | Actual journey runs locally with real providers, setup/screenshots/walkthrough, verified free-only Voyage use and separately authorized Anthropic calls. Development-only; outstanding Phase 3 live/D11 gates disclosed. |
| Production/release approved | All applicable held-out live, D11 human review and other release requirements actually completed and explicitly approved. |

Remaining execution gates: individual ticket implementation approval; exact corpus
text approval; actual Voyage model allowance and enforceable
free-only controls/headroom; provider account access and retention disclosure;
bounded external-run authorization; separate Anthropic model/cases/cost approval.
If quota protection cannot be established, stop external work rather than assume
the published free allowance is available. No provider switch or overage is allowed.
Threshold values are intentionally deferred until calibration, not a product
decision to guess now. Required check failures block the relevant status.

## Documentation and Git handoff

The owner-approved `to-tickets` step publishes exactly five issue files in the local
tracker. Keep the parent specification entry unchanged. Do not rewrite the
project PRD, original phase plans or historical implementation evidence. Keep new
milestone decisions and planned API/architecture notes clearly separate from
implemented behavior. A root glossary/ADR is unnecessary for this scoped draft;
no new ambiguous domain term or hard-to-reverse unexplained design requires one.

After review, propose `codex/mvp-vertical-slice` from the then-verified `master`;
do not create the branch without approval. This session permits documentation
only, with no production code, schema, dependency, certificate-store or runtime
changes. Every commit/push requires separate approval after documentation/diff
review. No credentials, generated vectors, runtime reports or corpus approval
claims may be included inadvertently.

First implementation step after separate Ticket 01 approval: verify current
Git/contracts, then establish the local HTTPS/auth browser
slice against the existing backend using the agreed test boundary. Do not start
that step during this documentation session.
