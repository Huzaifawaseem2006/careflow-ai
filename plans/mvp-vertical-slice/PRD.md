# CareFlow AI — patient portfolio MVP

Status: owner-approved specification for ticket publication, 2026-10-23;
`ready-for-agent` is a triage label, not implementation or spending approval.
Date: 2026-10-23. Inspected foundation: `faf65fb1fe28d5225adf10cff39ccc6a8df0a372`.

This separate milestone narrows the patient-facing demonstration. It preserves
the [project PRD](../../PRD.md), existing backend behavior and full Phase 4/5
requirements. See the [implementation plan](IMPLEMENTATION.md) and
[local tracker entry](../../.scratch/mvp-vertical-slice/spec.md).
Documentation and publication of the five approved local tickets are authorized.
Implementation, branches, external API calls, embeddings, indexing, commits and
pushes are not authorized. Corpus text approval remains a separate execution gate.

## Problem Statement

The owner needs a credible AI engineering portfolio application that an
interviewer can understand in a five-minute walkthrough and run locally.
The existing synthetic clinic backend already implements patient authentication,
catalog and availability tools, owned conversations, appointment review and
separate booking/cancellation/rescheduling confirmation. It lacks a patient
frontend and knowledge retrieval. Rebuilding these services would delay a usable
demo and risk weakening established authorization and booking guarantees.

The target is about one day of agent-assisted implementation, with minimal
process overhead. This is a scope target, not a delivery guarantee or permission
to omit required checks. Required failures block the relevant completion status.

## Solution

Deliver one English-only synthetic patient journey:

1. Sign in using an existing provisioned synthetic patient account.
2. Read and accept the existing storage disclosure, plus the v2 Voyage supplement,
   before creating a saved conversation.
3. Ask an operational clinic FAQ; the existing AI loop requests genuine retrieval.
4. Read a supported verbatim passage and open its exact versioned source.
5. Find a doctor and available persisted slot through the existing AI tools.
6. Review the backend-issued doctor, time, timezone, fee and proposal expiry.
7. Explicitly click the separate authenticated booking confirmation control.
8. See the committed appointment in My Appointments, including after refresh.

Use minimal sign-in, chat and My Appointments views. Display synthetic-data and
development-only limitations visibly. Loading, empty, expired, unavailable and
uncertain outcomes must be understandable; no transcript or model prose is a
booking receipt. Responsive layout, keyboard operation and labelled forms are
required; a large visual design system is not.

## User Stories

1. As a portfolio owner, I want to reuse the existing backend, so that the demo
   showcases completed engineering rather than a replacement prototype.
2. As an interviewer, I want concise local setup and a walkthrough, so that I can
   inspect a complete working journey.
3. As a synthetic patient, I want secure sign-in, so that my appointments and
   conversations are available only to my account.
4. As a synthetic patient, I want disclosure before storage and embedding use,
   so that I understand the local and external processing boundaries.
5. As a synthetic patient, I want conversational clinic questions, so that I can
   discover operational information without browsing a hardcoded FAQ flow.
6. As a synthetic patient, I want relevant passages retrieved from actual clinic
   documents, so that answers have inspectable evidence.
7. As a synthetic patient, I want each citation to identify its document version
   and passage, so that I can verify the displayed excerpt.
8. As a synthetic patient, I want unsupported questions to abstain, so that a
   merely similar passage is not presented as a verified policy answer.
9. As a synthetic patient, I want missing, conflicting or ineligible evidence to
   produce an honest limitation, so that the assistant does not invent policy.
10. As a synthetic patient, I want doctor and fee information from live domain
    tools, so that knowledge documents cannot override authoritative facts.
11. As a synthetic patient, I want real available slots, so that the assistant
    cannot offer invented appointment times.
12. As a synthetic patient, I want ambiguity clarified, so that a doctor or slot
    is not silently selected for me.
13. As a synthetic patient, I want the exact fee, local time and expiry displayed,
    so that I know precisely what I am confirming.
14. As a synthetic patient, I want a separate confirmation action, so that chat
    text alone cannot book an appointment.
15. As a synthetic patient, I want a stale review rejected with a fresh-review
    route, so that changed inventory or fees are not silently accepted.
16. As a synthetic patient, I want safe confirmation retries, so that a timeout
    or double-click cannot create a second booking.
17. As a synthetic patient, I want uncertainty disclosed after an interrupted
    request, so that missing UI feedback is not mistaken for failure or success.
18. As a synthetic patient, I want My Appointments to read persisted state,
    so that I can reconcile a booking independently of chat availability.
19. As a synthetic patient, I want historical reviews to be non-executable,
    so that reopening a transcript cannot recover a booking proof.
20. As a synthetic patient, I want old FAQ answers labelled as historical,
    so that superseded information is not mistaken for current policy.
21. As a synthetic patient, I want cancellation/rescheduling limitations stated,
    so that the interface does not imply an action it cannot complete.
22. As a synthetic patient, I want logout and session expiry to remove access,
    so that cached UI state cannot supply authority.
23. As a corpus reviewer, I want exact synthetic text reviewed before indexing,
    so that unapproved claims cannot enter the answer pipeline.
24. As a maintainer, I want bounded repeatable indexing with recorded provenance,
    so that embeddings can be traced to approved source inputs.
25. As the owner, I want Voyage calls restricted to verified free allowance,
    so that the demo cannot incur unauthorized embedding overages.
26. As a maintainer, I want legacy v1 responses and evaluations preserved,
    so that adding citations does not silently break existing contracts.
27. As an interviewer, I want mocked and hosted-model evidence distinguished,
    so that test claims accurately describe what was exercised.
28. As the owner, I want implementation, local demo and release statuses separated,
    so that a development-only demo is not presented as production approval.

## Implementation Decisions

### Reuse and authority

Keep the FastAPI modular monolith, PostgreSQL, SQLAlchemy/Alembic, existing
Anthropic adapter and bounded sequential custom tool loop. Reuse catalog,
availability, session, conversation, booking, management, retry and audit services.
No service rewrite, new orchestration framework, unrestricted SQL tool or new
appointment authorization mechanism is permitted. Backend services enforce all
permissions. Source text and LLM output remain untrusted data.

Doctors, fees, availability, patient appointments and executable booking rules
remain authoritative domain-service facts. RAG covers only the reviewed
operational topics in the corpus appendix. It cannot establish a slot, price,
patient identity, reservation, confirmation or handoff.

### Embeddings and reproducible indexing

Select Voyage AI `voyage-4-lite`, explicitly requesting 1,024-dimensional float
vectors; store them as PostgreSQL `vector(1024)`. Use `document` inputs during
indexing and `query` inputs at retrieval. Reject invalid dimensions, nonfinite or
zero vectors and oversized inputs; do not silently truncate source passages.
Use the same configured model/dimension for corpus and queries.

Start with four short source documents, split deterministically by headings and
paragraphs, with bounded passages; do not combine unrelated policies to fill a
chunk. Store immutable document identity/version/title, clinic, access class,
review evidence, approval/effective interval, passage identity/position, exact text
and hashes. Record corpus, chunking and embedding configuration in an index
manifest. Reuse unchanged embeddings on rerun; partial failures cannot activate
an incomplete index. Activation is a confirmed operator operation after review.
No database transaction spans a provider call. Traceable inputs/configuration,
rather than guaranteed byte-identical hosted embeddings, define reproducibility.

The MVP corpus is public operational information for the fixed fictional clinic,
presented through the authenticated interface. Only an operator may approve,
activate, supersede or withdraw versions; no new staff/management UI is needed.
New answers require approved, currently effective, clinic/access-eligible sources.
An approved version becomes effective on explicit activation unless its recorded
review specifies a later date. Conflicting active evidence must not produce an
assertive answer. Supersession/withdrawal must be recorded without rewriting
immutable version content or historical conversation answers.

### Free-only usage and privacy

No Voyage call is allowed merely because a key exists or published pricing lists
a free allowance. Before each bounded external run, verify actual model allowance,
organization/billing restrictions and sufficient headroom; account-wide concurrent
usage must be considered. Establish a defensible free-only stop mechanism before
enabling calls. Token/rate limits and a locally observed counter alone do not
prove an account cannot bill overages. If allowance, billing protection or remaining
headroom cannot be verified, stop and ask the owner. Do not buy credits, enable
recharge, permit paid overages or switch providers automatically.

Use server-only secrets, bounded request/token budgets, finite timeouts and
controlled retry behavior with usage accounting. Tests/CI default to no external
calls. Report actual usage separately from estimates, including potentially
consumed quota after ambiguous failures. No hardcoded keys or body/credential logs.
Anthropic paid runs retain separate model/cases/maximum-cost approvals and their
existing spending ledger; Voyage's free allowance does not authorize chat spend.

Send only bounded search text needed for retrieval to Voyage, never the entire
transcript, account identity, appointment records, cookies, CSRF or booking proof.
Preserve the existing storage disclosure and consent mechanics. Before v2 creation,
show a separate Voyage processing supplement; verify applicable provider retention
terms before external use, and do not claim local deletion deletes provider data.
This supplement must not silently change v1 consent or overload its version field.

### Retrieval, answer support and the custom loop

Add one bounded knowledge-retrieval tool with search text as input. Backend code
fixes clinic/access scope and index configuration; the LLM cannot set approval,
source identity or authority. Retrieve eligible candidates with exact cosine
distance, initially top three with stable tie-breaking. No approximate index,
reranker, hybrid pipeline or extra LLM verifier is needed for this tiny corpus.

Calibrate the acceptance threshold on development examples, then freeze it with
model/corpus/index versions before held-out evaluation. Do not invent a universal
numeric cutoff, interpret similarity as a probability of correctness, or assume
the nearest passage answers the question. Test answerability separately, including
near-matches that omit the requested fact. Render only supported verbatim passages;
reject weak, insufficient, conflicting or invalid evidence with clear abstention.
This is a bounded empirically evaluated extractor, not a proof of general semantic
entailment. If simple retrieval cannot meet the acceptance set, report a blocker
rather than introduce an unapproved validator or weaken the tests.

Return bounded typed passage results through the existing tool-result mechanism.
Revalidate document status and passage provenance after provider waits and before
answer assembly. The backend, not model prose, constructs excerpts and citations.
Ignore instructions embedded in documents. Preserve existing tool/time/context/
output budgets, private authorization rechecks and domain-only mutation rules.
For the first demo, FAQ and protected booking-review issuance can occur in separate
turns; do not add a combined policy/review response state machine.

### Opt-in v2 and citations

Preserve the complete v1 contract, including empty citations, legacy response
shapes, existing tools and public single-turn behavior. Existing conversation
creation requests default to response version 1. The new frontend explicitly
requests response version 2 at creation; persist that immutable selection, with
existing rows defaulting to 1. Share the endpoints, loop and domain services.
Do not overload the storage-disclosure version for protocol negotiation.

V2 adds bounded typed passage/citation fields and new prompt/tool-schema metadata.
A citation carries server-owned document identity, immutable version, passage
identity, title and an allowlisted relative source link. Backend validation binds
the exact excerpt to that source; no LLM citation, arbitrary URL or inferred
provenance is accepted. Source viewing enforces session/scope rules, identifies
the exact version/passage and reports current effective/superseded/withdrawn status.

Decode history and exact replay by response-version discriminator; old saved
responses and metadata remain valid. New turns retrieve current evidence instead
of treating historical excerpts as authority. Save v2 text/citations as immutable
historical snapshots. Exact replay remains historical, including after source
withdrawal; show historical status and current source status separately. Historical
review markers remain proof-free. Version negotiation grants no new authority.

### Local HTTPS and interface behavior

Use one browser origin at HTTPS localhost, with Next.js forwarding an allowlisted
API prefix to HTTPS FastAPI on loopback. Trust local certificates explicitly in
the browser and Node/backend connection; preserve certificate verification. Forward
the original browser Origin, CSRF and cookie semantics; configure the exact browser
origin as the backend authorization origin. Test the real proxy path. No permissive
CORS, insecure cookies, forged client authority, TLS-verification bypass or
unrestricted forwarding destination is allowed. Keep private responses uncached;
API responses and session/proof material must not enter a service worker or static
render cache. Certificate private keys stay outside tracked artifacts.

Require sign-in for all MVP chat and source interactions. Reuse existing provisioned
accounts, conversation ownership/retention and disclosure acceptance. Reuse owned
history to resume a conversation; a sidebar/search/multi-conversation manager is
not required. Show structured real tool results as optional selection controls
that continue the conversation; they do not fabricate facts or bypass the loop.
No hardcoded booking script or success response may substitute for the AI/service
path. No token streaming requirement is added; ordinary bounded responses suffice.

### Protected booking and failures

Render the original backend-issued booking review exactly, including doctor,
offset-aware interval, Asia/Karachi timezone, exact PKR fee and effective deadline.
A review creates no hold. Confirm only on a separate explicit click using the
existing authenticated endpoint, CSRF, issued proof and a stable idempotency key.
Keep proof/key in page memory, out of URLs, browser persistent storage, transcripts,
provider messages, screenshots, analytics and logs. A pending button prevents
accidental duplicate submissions; backend idempotency remains authoritative.

On ambiguous confirmation timeout, show uncertainty and allow exact original
proof/key retry while memory remains. Never automatically submit with a new key.
After refresh or lost proof, reconcile current state through My Appointments and
explain the lost retry capability; do not auto-request and confirm another booking.
Only definitive stale/expired rejection leads to a fresh review and new explicit
confirmation. An absent appointment in a read is not proof an in-flight request
cannot still commit. Provider failure cannot undo a committed booking or fabricate
success. Auth expiry/logout clears protected UI state and prevents cached actions.
Cancellation/rescheduling reviews get an unavailable-in-demo notice and no confirm
control. Backend management services and authorization remain unchanged.

### Three completion statuses

| Status | Required evidence |
| --- | --- |
| Implementation verified | Required implementation, integration and applicable mocked checks pass; missing hosted evidence is identified, never represented as measured semantic/model quality. |
| Local portfolio demo ready | Complete actual synthetic journey works locally, with verified free-only Voyage access, separately authorized Anthropic use, setup, screenshots and walkthrough. Clearly development-only; no clinical or production approval claim. |
| Production/release approved | Applicable live evaluations, D11 human safety review and all other release/phase requirements pass with explicit approvals. |

The owner explicitly permits the development-only local portfolio demo before
outstanding Phase 3 live/D11 gates close. This narrowly supersedes earlier general
"before demo" wording for this milestone only. It neither completes Phase 3/4/5
nor waives release requirements. Critical technical auth, booking, data-integrity,
source-validity or safety test failures still block the local demo.

## Testing Decisions

Prefer the highest existing observable boundary: browser through real same-origin
HTTPS, FastAPI routes, existing services and disposable PostgreSQL. Below that,
use the existing HTTP/orchestrator/service boundary for focused cases. External
Anthropic/Voyage responses may be scripted in deterministic tests; database state,
authorization and transactional claims must be real. A separate direct retrieval
evaluation measures embeddings/search without conflating them with tool selection.
These reuse the agreed planning seams. Any new high-risk seam requires ticket-level
review before implementation; this draft does not grant blanket seam approval.

Prior art is the existing auth, conversation, booking and Phase 3 gate integration
tests and scripted provider transport tests. Test behavior and independent state/
source oracles, not helper implementation details or expected text imported from
the production renderer. Use strict TDD for authorization, private data, protocol
compatibility and protected confirmation integration. No new business mutation
rules are needed.

- Browser: the full journey; source viewing; storage consent; logout/session expiry;
  patient isolation; cookie/CSRF/origin rejection; persisted appointments after refresh.
- Retrieval: direct questions, paraphrases, unknowns, misleading near-matches,
  conflicts, unapproved/future/expired/withdrawn/wrong-clinic/wrong-access sources,
  and withdrawal between lookup and answer assembly.
- Provenance: every excerpt matches its exact source/version/passage; forged model
  text, IDs and URLs cannot populate citations; retrieved instructions cannot
  acquire authority, exfiltrate data or confirm appointments.
- Compatibility: default/legacy v1 payloads, frozen cases and graders unchanged;
  opt-in v2 round trips, immutable negotiated version, mixed-version rejection,
  historical source/replay behavior and proof-free history.
- Booking: original proof, separate click, permission/capacity/idempotency and
  concurrency invariants, stale fees/slots, expiry, ambiguous retry, lost-memory
  refresh, provider failure after commit, unsupported review kinds.
- Indexing/provider: rerun reuse, partial failure, malformed vectors, configuration
  mismatch, secret redaction, quota/billing unknown or exhausted, bounded calls and
  no external network by default in tests/CI.

Freeze a separate MVP development/held-out dataset and report denominators,
abstentions, corpus/index/model/prompt versions and uncertainty. Preserve the
project targets: at least 95% held-out tool selection, at least 90% grounded FAQ
correctness, 100% citation validity and zero observed critical unauthorized access,
unconfirmed mutations or duplicate bookings. Report retrieval recall separately.
Correct abstention on unknowns must not conceal abstention on answerable cases;
report answerable coverage and correctness separately. Negative/adversarial cases
must not produce unsupported assertions. Do not tune on held-out cases; a failed
held-out run needs a documented revision and fresh held-out evidence.

Real provider embeddings on fixed inputs establish semantic-retrieval evidence;
scripted vectors establish mechanics only. Hosted Anthropic evidence establishes
actual tool-selection behavior; mocked runs do not. Neither hosted calls nor their
results are currently authorized or claimed. Preserve existing frozen Phase 3
inputs/graders/spending gates and compare affected current-source results with the
retained baseline. Required failures or missing checks block the associated status.

## Out of Scope

Cancellation/rescheduling confirmation UI; staff dashboards; handoff queues;
knowledge-management screens; uploads; web ingestion; clinical preparation advice;
diagnosis, prescribing, treatment or definitive triage; real patient/clinic data;
Urdu/Roman Urdu/multilingual support; guest frontend chat; registration/recovery;
generated policy paraphrases; streaming; payments; notifications; production
deployment; Docker as a prerequisite; reranking/hybrid retrieval; LangChain,
LangGraph, additional agents, workers or separate vector databases.

Preserve all existing backend cancellation/rescheduling and public/guest behavior.
Frontend exclusions are product scope, never backend security controls. Do not
claim that a staff handoff was queued, collected payment, or reserved capacity.

## Further Notes

### Review and execution gates

The owner approved this specification/plan and invoked `to-tickets` on 2026-10-23.
The five local tickets are published in dependency order; no implementation or
external execution follows from publication. The original tracker specification
entry remains a historical drafting record. Exact corpus text below still needs
explicit approval before indexing. Each implementation ticket, commit and push
retains its own approval boundary. API access, corpus approval, free-only billing
protection, retention disclosure and separately approved live cases are execution
gates, not reasons to reopen settled product scope.

### Draft synthetic corpus for owner review

All four documents below are proposed fictional policies, not existing clinic
facts. Status: **draft / unapproved / not effective / not indexed**. Proposed
version: 1. Clinic: CareFlow Fictional Demo Clinic, Karachi. Access: public
operational information. Reviewer/date/effective interval and actual content
hashes must be recorded after owner approval; do not invent approval evidence.
The exact passage bodies below are the review inputs. Implementation may move
approved text into dedicated source files without silently changing its meaning.

#### Arrival and check-in — proposed document `arrival-check-in`, version 1

Passage `arrival-check-in-01`:

> This is a fictional clinic policy for a synthetic software demonstration.
> Please arrive 15 minutes before your scheduled appointment and check in at the
> reception desk. Appointment times are displayed in Asia/Karachi time.

Passage `arrival-check-in-02`:

> At check-in, tell reception the synthetic patient name used for your booking.
> If you arrive late, ask reception about the next steps. These instructions do
> not guarantee that a late appointment can proceed or that another slot exists.

#### Documents to bring — proposed document `documents-to-bring`, version 1

Passage `documents-to-bring-01`:

> This is a fictional clinic policy for a synthetic software demonstration.
> Bring your appointment confirmation or appointment identifier so reception can
> locate the booking. You can view your saved booking in My Appointments.

Passage `documents-to-bring-02`:

> Use synthetic account and appointment information only. This demo does not
> require you to upload identity documents, medical records or other real
> personal information. It provides no clinical preparation instructions.

#### Accessibility — proposed document `accessibility`, version 1

Passage `accessibility-01`:

> This is a fictional clinic policy for a synthetic software demonstration.
> The fictional clinic has a step-free entrance and seating near reception.

Passage `accessibility-02`:

> Ask reception about an accessibility arrangement that is not described here.
> This demo cannot submit or confirm accessibility assistance requests and does
> not guarantee that a particular arrangement is available.

#### Payment methods — proposed document `payment-methods`, version 1

Passage `payment-methods-01`:

> This is a fictional clinic policy for a synthetic software demonstration.
> The fictional reception desk accepts cash and debit cards for in-person payment.
> The application does not collect payments or card details.

Passage `payment-methods-02`:

> Consult the current doctor information and booking review for consultation fees.
> This document does not set prices, explain refunds or establish insurance
> coverage. A confirmed appointment is not a payment receipt.

Use these deliberate evidence gaps in evaluations: late-arrival guarantees,
specific unlisted assistance, credit cards, refunds, insurance and clinical
preparation. Similar words must not make those questions supported.

### Dated primary-source references

Checked 2026-10-23, documentation only; no account/API access was performed.

- [Voyage text embeddings](https://docs.voyageai.com/docs/embeddings): selected
  model, 1,024 default dimensions, float output and query/document inputs.
- [Voyage pricing](https://docs.voyageai.com/docs/pricing): published free allowance
  and subsequent usage pricing; this does not establish this account's balance.
- [Voyage usage monitoring](https://www.mongodb.com/docs/voyageai/management/monitor-usage/):
  remaining model allowance is visible in organization Free Usage where supported.
- [Voyage billing FAQ](https://docs.voyageai.com/docs/faq): prepaid balance alone
  is not an overage guarantee; usage beyond purchased credits can be billed.
- [pgvector](https://github.com/pgvector/pgvector): float vectors and exact cosine
  search; 1,024 dimensions fit the documented vector capabilities.
- [Next.js local HTTPS](https://nextjs.org/docs/app/api-reference/cli/next#using-https-during-development)
  and [external rewrites](https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites#rewriting-to-an-external-url):
  support the proposed development integration; actual header/cookie behavior
  must be verified through browser tests.
