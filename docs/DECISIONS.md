# Decisions and PRD review

2026-10-14. Status labels: **approved** = explicitly chosen by owner; **proposed** = needs review; **open** = no selection. The owner approved the Phase 0 architecture with the MVP defaults below. Implementation tickets require individual approval; see progress for completed work.

## Approved MVP decisions

- One fictional clinic in Karachi, Pakistan; `Asia/Karachi` timezone, PKR fees, English first. Arabic and Urdu are post-MVP.
- Fixed stack: FastAPI modular monolith; PostgreSQL/pgvector; SQLAlchemy 2.x, Pydantic v2, Alembic; Next.js, TypeScript, Tailwind; OpenAI SDK with explicit tool calling and structured outputs. One bounded orchestrator.
- Server-managed sessions using secure HttpOnly cookies and appropriate CSRF protection; no public staff registration. D02 uses pre-provisioned synthetic patient accounts with local passwords and operator-only creation/reset; no public registration or email recovery (approved 2026-10-16).
- Persisted 30-minute appointment slots, capacity one; database integrity, transactional writes and idempotency. Cancellation and rescheduling allowed until 24 hours before the appointment.
- Explicit frontend confirmation for state-changing actions using backend-issued expiring proposals bound to authenticated actor and exact operation. Revalidate fees before booking; changed fees require fresh confirmation.
- Admin-approved immutable versioned knowledge documents. Authenticated patient handoffs initially.
- Minimal conversation persistence with a **proposed** 30-day synthetic demo retention period; duration and deletion exceptions remain for final approval.
- Configurable OpenAI model and evaluation budget; native local services and PostgreSQL for the current MVP. Docker/Compose deployment is deferred (owner-approved change, 2026-10-15). No clinical diagnosis, prescribing or definitive triage.
- Establish evaluation infrastructure and a versioned synthetic dataset during Phase 1, before AI behavior. Deterministic security assertions; mocked and live runs labeled separately.
- `PRD.md` is authoritative; its Docker requirements were narrowly amended with explicit owner approval on 2026-10-15. Other PRD requirements are preserved. `AGENTS.md` carries the owner's current workflow and safety rules, including the approved accelerated workflow below; local issue tracking, triage and domain-doc pointers remain in place.

## Approval register

| ID | Decision | Recommendation / consequence | Needed before |
| --- | --- | --- | --- |
| D01 | Emergency locale language | Clinic location is Karachi/`Asia/Karachi`/PKR. Approve exact local escalation wording and any emergency contact reference through D11. | Safety wording |
| D02 | Patient identity lifecycle | Approved 2026-10-16: pre-provisioned synthetic patients, local password hashes, operator-only account creation/password reset, no public registration or email recovery. | Resolved for Ticket 05 demo |
| D03 | Slot horizon and DST handling | Approved 2026-10-17 for Phase 2 Ticket 02; see the scheduling decision below. The 24-hour appointment-change cutoff remains separate. | Resolved for Ticket 02 |
| D04 | Proposal expiry / retry retention | Actor/action-bound proposals and fee revalidation approved. Choose expiry, stale-state behavior and idempotency retention without weakening invariants. | Phase 2 |
| D05 | Handoff scope | Authenticated patient handoff approved; guest handoff deferred. Define staff queue permission and consent/retention. | Chat/handoff |
| D06 | Corpus details | Immutable admin-approved versions approved. Choose synthetic source set, reviewer and withdrawal policy. | Phase 4 |
| D07 | Model, embeddings and eval budget | Configurable model/budget approved; select actual IDs, embedding setup and budget after capability check. No live run or price claim yet. | Phase 3 live eval |
| D08 | Hosted demo | Native local setup for MVP; Docker/Compose deferred by owner on 2026-10-15. Select host, TLS and protected demo accounts before publishing. | Phase 7 |
| D09 | Staff scope | Arabic and Urdu post-MVP. Minimal appointments/handoff queue for P0 proposed; choose detailed staff CRUD scope. No reminders/MCP for first demo. | Frontend scope |
| D10 | Retention and deletion | Proposed 30-day synthetic conversation retention, with deletion behavior, handoff/audit exceptions and disclosure still to decide. | Persistence for chat |
| D11 | Clinical wording review | Owner names appropriate reviewer and approves locale-specific escalation text before demo; no clinical validation claim. | Safety eval/release |
| D12 | Schema additions and API changes | Proposals/idempotency tables, fee snapshot, session storage as applicable; reschedule tools/proposal endpoints described in contracts. | Schema/API implementation |

Tickets 01–02 were individually approved and are complete. Remaining decisions block only dependent tasks; resolve only the decisions needed for the approved ticket.

## Contradictions, gaps and risks

- J7 says Arabic in a second phase, FR-12 marks it P1 and Phase 6 says optional. Owner resolved MVP scope: Arabic and Urdu post-MVP. PRD remains unchanged; propose a minimal PRD amendment marking FR-12 post-MVP and removing ambiguity at Phase 6.
- J5 offers handoff to a possible guest, but Section 8 requires authenticated mutation. Owner resolved MVP scope: authenticated patient handoff. Propose a minimal J5 amendment stating that handoff requires sign-in. Public chat submission can remain guest-accessible without claiming a persisted handoff.
- Cancel/reschedule are P0, but tool list omits propose/confirm reschedule. Add only after contract approval.
- Section 8 exposes mutation routes without proposal routes or proof transport. A model-generated `confirmed=true` is insufficient; bind a server proposal to an actual user event.
- Single `role` does not fully express clinic scope or handoff-operator access. Define permission mapping without adding enterprise RBAC.
- Slot duration is 30 minutes, with capacity one. D03 now defines horizon, timezone and schedule-edit rules; Ticket 02 uses exclusion constraints because unique start times cannot prevent shifted overlap. Appointment status transitions remain for Ticket 03/D12.
- Appointment idempotency key alone cannot cover all mutations. Define actor/operation scoping, payload mismatch and retry retention.
- Doctor filters include location, but initial clinic schema has no explicit location field. For one-clinic MVP filter by clinic ID; decide whether free-text location is actually needed before adding fields.
- Source links can be invalid or unsafe; use stable backend citation endpoints, never model-invented URLs. Decide knowledge clinic/access scope and effective-version conflicts.
- Chat ownership, guest-to-patient transfer, disclosure/deletion, staff access and audit retention are not fully modeled. The owner proposed 30 days for synthetic conversations; this is not yet a complete deletion policy.
- Handoff is P0 but broad dashboard P1/Phase 5; an actual authorized queue is needed to avoid a fake handoff claim.
- Observability is P1 yet eval evidence and safety require traces from the first AI slice. Implement minimal redacted metrics early.
- Eval targets are provisional, sample size and held-out governance are missing. Baseline must precede calibration; zero observed violations is not a security guarantee.
- Preparation instructions can cross into medical advice. Only approved clinic material; never generate treatment guidance.
- P0 surface is large: defer Arabic, Urdu, Redis, reminders, MCP, richer records and real integrations to avoid scope creep.

## Skills audit

Recursive name scan of `C:/Users/USER/.codex/skills` and `C:/Users/USER/.codex/plugins` returned no `karpathy-*` paths. No such skill is in the supplied skills catalog. No third-party skill was installed or executed; compatibility cannot be assessed without source contents.

Options if later requested: provide a specific repository/version for read-only review, then manually place a reviewed Codex-compatible `SKILL.md` under the personal skills directory; or use the available skill-installer after source review and explicit installation authorization. Review instructions, referenced resources and scripts, provenance/license, path assumptions and Codex tool compatibility. Never pipe a remote installer into a shell. Current AGENTS rules apply the requested principles without a third-party package.

## Source checks

Official OpenAI function-calling, Pydantic strict-mode and PostgreSQL locking/index pages were opened on 2026-10-14; links and limited implications are in ARCHITECTURE.md. No package version or model capability has been selected by this check. Reverify relevant APIs against pinned versions when implementing.

## Session handoff workflow — approved 2026-10-14

The owner requires repository documents to carry verified state between sessions. `AGENTS.md` now directs agents to inspect the checkout and scoped documentation at task start, update progress/decisions/phase plans after meaningful work, and report a concise evidence-based handoff. This keeps the next session independent of full chat history. Documentation changes are shown before commit, and every Git commit requires explicit owner approval. Trade-off: documentation takes a small amount of upkeep; keep entries short and update other design documents only when their subject actually changes. This process decision does not authorize Phase 1 implementation.

## Phase 1 health baseline — 2026-10-15

For the approved first ticket, use Python 3.13.13, a small editable FastAPI package and exact direct runtime/development dependency pins in project metadata. `GET /health` returns only process liveness through a Pydantic response model; database readiness gets a separate later contract. This keeps the first slice independently verifiable and avoids implying a database exists. A full transitive lockfile is not yet present, so future resolutions may select newer compatible transitive packages. The installed Starlette version emits a deprecation warning for its HTTPX-backed test client; the test passes, and the warning remains tracked rather than treated as a failure or silently suppressed.

## Foundation CI — approved 2026-10-15

The owner approved ticket 02, GitHub Actions and tests through the actual check command's subprocess boundary without mocks. Use a standard-library Python entry point shared by local runs and CI; record Git HEAD, working-tree dirtiness and check exit codes in JSON. The separate CI regression suite prevents recursive test execution and exercises a temporary real lint violation. Trade-off: it must run serially in an idle checkout, and its report describes foundation checks rather than the regression suite's own result (pytest reports that separately). The workflow needs only read access to contents, disables persisted checkout credentials, and uses no project secrets. Major action tags follow official action documentation; they are not immutable SHA pins. No CI host was connected, no hosted execution is claimed, and no new package dependency was needed. A clean committed baseline and transitive dependency locking remain later work.

Sources checked: [GitHub Python workflow guide](https://docs.github.com/en/actions/tutorials/build-and-test-code/python), [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), [setup-python](https://github.com/actions/setup-python), and [checkout](https://github.com/actions/checkout). Configuration review does not establish that a hosted run passes.

Owner selected a new private `careflow-ai` repository under their authenticated personal account on 2026-10-15; the provided profile is `Huzaifawaseem2006`. Keep it empty at creation because source and documentation already exist locally. Verify the account at sign-in; creation, commits and pushes each require explicit approval. Hosted failure evidence will use a separate branch with a deliberate lint violation; keep the passing branch free of the probe. This confines the experiment to CI verification and does not authorize ticket 03.

The owner subsequently approved the baseline commit, private repository creation and initial push. Authenticated ownership and Private visibility were verified; `origin` now points to `https://github.com/Huzaifawaseem2006/careflow-ai.git`. Retained the existing `master` branch. Baseline `af00055` has an actual successful hosted run. The deliberate failure branch and final closeout commit have separate approval boundaries; baseline approval does not authorize either commit.

The owner separately approved the failure-probe commit/push. Commit `a59f3fe` on `codex/ci-failure-proof` has an actual failed hosted run caused by the deliberate Ruff F401 violation; retain that branch only as evidence and never merge it. Returned to `master`, which still points to passing baseline `af00055` and contains no probe. Both hosted outcomes are verified, so ticket 02 is resolved. Final documentation commit/push requires its own approval; ticket 03 remains outside this session's scope.

## Accelerated ticket workflow — approved 2026-10-15

The owner set a two-day functional MVP target and adopted one implementation ticket per session, normally followed by a fresh session. `AGENTS.md` is the authoritative workflow: scoped context reads, ordinary technical autonomy under one ticket approval, risk-based TDD/testing, milestone CI and concise end-of-ticket documentation. This supersedes the earlier unconditional full-PRD read and documentation-after-each-meaningful-edit rules. It preserves PRD/architecture/acceptance criteria, critical security and clinical boundaries, applicable tests/evals and phase/release gates. The schedule is a target, not a completion guarantee or permission to reduce scope.

Review found avoidable overhead in repeated context loads, intermediate documentation, repeated routine approvals and unnecessary broad skill reviews. Installed guidance was inspected without invoking its implementation/review/handoff workflows: `implement` encourages TDD, invokes `code-review` and instructs a commit; `tdd` requires an agreed test boundary once invoked; `code-review` uses a fixed comparison point and two reviewers; `handoff` avoids duplicating existing artifacts; setup guidance already configures our local tracker. Use these selectively and follow invoked instructions subject to owner rules; a skill's commit step never grants commit approval. Applied `writing-for-agents` to consolidate rules and use scoped references. No installed skill was modified.

Trade-off: focused tests and fewer process steps improve delivery speed, while high-risk logic retains strict TDD and necessary security/integration coverage. Existing automatic CI triggers remain unchanged; the deliberate failure experiment used to validate ticket 02 is not a recurring ticket requirement.

### Proposed routine commit/push policy — NOT APPROVED

If separately approved, a ticket implementation approval would also authorize at most one final commit and ordinary push for that ticket, after its acceptance criteria and applicable checks pass (or are explicitly inapplicable), the scoped diff is reviewed and shown, and secrets/sensitive data are excluded. Include only that ticket's changes and handoff docs; push only to a `codex/<ticket>` branch on the existing private `origin`, creating the branch if needed. Report the resulting SHA and actual CI outcome. This would not authorize direct `master` pushes, merges, force-pushes/history rewrites, unrelated files, extra commits, remote/visibility/access changes, release/deployment or destructive operations. Pause for approval when these bounds cannot be met or required checks are failed/blocked. Until the owner explicitly approves this policy, retain explicit approval before every commit and push, including this workflow update.

## Docker-free MVP and Ticket 03 — approved 2026-10-15

The owner explicitly removed Docker and Docker Compose from current MVP development/deployment requirements and authorized narrow PRD, architecture, plan and Ticket 03 amendments. Native local PostgreSQL plus pgvector replaces Compose verification; containerization remains optional deferred work and cannot block this ticket. This supersedes earlier Compose-first decisions and historical progress entries. PostgreSQL, pgvector, synchronous SQLAlchemy, Alembic, migration correctness and real database integration requirements remain unchanged. No system software installation, commit or push is authorized by this change.

Ticket 03 enables only the `vector` extension and Alembic version tracking. D12 proposals/idempotency/session tables and D02 identity choices are deferred to their dependent slices. Use SQLAlchemy 2.0.54 (the maintained 2.0 API line), Alembic 1.20.0 and Psycopg/binary 3.3.6, verified from PyPI and installed together under Python 3.13.13. Native setup now uses the owner's PostgreSQL 17.11 installation and targets pgvector 0.8.7; no PostgreSQL 18 upgrade is required. The extension version must be recorded after real verification. No embedding dimension is selected. A bounded synchronous `/ready` probe checks revision plus extension and returns generic failure; `/health` stays database-independent. Migrations are explicit operator actions. Use a separate minimally privileged API role, and an operator role for extension installation. The initial downgrade drops the extension without CASCADE; never run it on valuable data without explicit approval.

Trade-off: native Windows pgvector setup requires matching PostgreSQL binaries and C++ build tooling; installation is owner-controlled. Disposable integration databases require local CREATEDB/extension privileges. The owner installed PostgreSQL 17.11 / pgvector 0.8.7, and real migration/vector/readiness verification passed on 2026-10-15. Credentials were entered locally, used through process environment variables and excluded from Git; temporary credential storage was Windows-encrypted and removed after verification. API runtime credentials remain separate from operator/test credentials, as documented in README.

PostgreSQL 17 setup follow-up: use the existing Visual Studio 2022 C++ tools and build the pinned official pgvector v0.8.7 source with `PGROOT=C:\Program Files\PostgreSQL\17`, following upstream's Windows instructions. This links against the installed major-version headers/library instead of introducing a second PostgreSQL distribution or unverified DLL download. Native PostgreSQL 17 is within pgvector's documented PostgreSQL 13+ support range; actual migration/vector tests are still required. No migration, extension or readiness requirement is reduced.

API references checked: [SQLAlchemy Psycopg dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg), [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html), [pgvector Windows installation](https://github.com/pgvector/pgvector#windows), and [PostgreSQL Windows installer](https://www.postgresql.org/download/windows/). Package versions were queried with `pip index versions` and verified by imports; no live server or extension version is inferred from documentation.

## Ticket 04 fixture implementation — 2026-10-16

Within the owner's Ticket 04 approval, use fixed UUIDs and explicit fictional labels for one Karachi clinic and four demo personas. Store clinic settings in `clinics` and credential-free personas in `demo_identities`; `demo_role` does not confer access. This meets fixture requirements without selecting D02 credentials/recovery or implementing Ticket 05. Later identity work must explicitly map or replace these personas rather than treating them as authenticated accounts.

Use an operator-only, explicitly confirmed local CLI. Load inserts missing known IDs; reset upserts only those IDs, restoring settings/personas without deleting unrelated data or resetting domain history. Both run in one transaction under an advisory lock. Refuse nonlocal/unrecognized targets and stale migration heads. The trade-off is that reset restores a fixture manifest rather than wiping a complete demo database; future booking/history reset behavior needs its own scope and approval. No fixture grants are added to the API role, no credentials are seeded, and schema changes use the existing Alembic chain. Real PostgreSQL verification was completed by the owner on 2026-10-16; the inspected JUnit report records all seven integration tests passing without skips.

## Ticket 05 identity lifecycle — approved before implementation, 2026-10-16

The owner approved pre-provisioned synthetic patient accounts, operator-only account creation/password reset, no public registration or email recovery, and HTTP tests with real disposable PostgreSQL plus account-management CLI tests. Ticket 04 personas stay separate until explicit provisioning; fixture role labels never authorize authentication. Passwords use a reputable Argon2id implementation, never plaintext. Sessions are opaque, server-managed, and revoked by logout/reset. Backend state alone determines the patient identity. Cover login failures, CSRF, patient isolation, credential reset, session invalidation, permission, concurrency and retry behavior.

Implementation approach: HTTPS-only Secure/HttpOnly/SameSite=Strict host-only session cookies, same-origin checks on mutations, a session-bound CSRF token including pre-login sessions, absolute expiry and rotation at login. Account/session changes use PostgreSQL transactions and consistent user-before-session locking so a reset cannot race a stale password into a surviving session. Public account registration/recovery and staff authentication are outside this ticket. This is a synthetic demo lifecycle, not a production identity/recovery service. No credentials, session tokens or request bodies belong in logs. No Ticket 06 work or Git commit/push is authorized.

Implementation choices: argon2-cffi 25.1.0 uses Argon2id with its RFC 9106 low-memory defaults (64 MiB, three passes, four lanes) and random salts; check for rehash on successful login. Session secrets have 256 bits of randomness and are stored only as SHA-256 digests. CSRF values are separately random and session-bound. Absolute lifetimes are eight hours authenticated and ten minutes before login. Persist request limits in PostgreSQL rather than process memory: 30 bootstrap/login requests per peer IP/minute and five login attempts per email/five minutes, including successes. This is deliberately conservative for a small synthetic demo; proxy peer attribution needs deployment configuration. Account reset and login share the user-row lock; duplicate provisioning fails safely via database uniqueness rather than inventing authentication idempotency keys.

References checked during implementation: [argon2-cffi API](https://argon2-cffi.readthedocs.io/en/stable/api.html), [OWASP sessions](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html). These guide implementation; they do not certify the demo as production-secure.

## Ticket 07 regression gate semantics — 2026-10-16

Reuse the existing foundation checker, serial CI regressions, disposable PostgreSQL suite and offline inventory. Required test skips or missing evidence block the Phase 1 gate (exit 2); failures take precedence (exit 1). Every invocation writes fresh companion evidence and records command arrays/revision/dirty state. This preserves the approved Phase 1 infrastructure boundary: the seven unexecuted agent cases remain pending, never passing behavioral evidence. Real-path integration remains required before Phase 3 AI behavior; no live-model or production-security claim follows from Phase 1 success. Hosted CI is verified separately for an exact SHA and cannot replace local PostgreSQL evidence. No architecture, dependency, clinical-operation or Git approval boundary changes.

## Phase 2 Ticket 02 scheduling — approved 2026-10-17

The owner approved D03 and the scheduling service/operator CLI, public HTTP,
and PostgreSQL integrity/concurrency test seams. Generate persisted capacity-one
30-minute slots for today through the next 29 calendar dates in Asia/Karachi,
excluding slots already started. Generation is explicit, repeatable and operator
triggered; no scheduler or automatic regeneration on edit. The trade-off is a
small bounded inventory requiring operator refresh.

Availability requires offset-aware start_at/end_at, half-open intervals, bounded
pagination and a range within that same horizon; reject invalid ranges. Weekly
schedules use Asia/Karachi wall times and same-day windows (split overnight
windows across weekdays). Persist UTC instants and return local timestamps with
offsets and the timezone name. Reject ambiguous/nonexistent local times instead
of silently shifting them.

Confirmed schedule edits/exceptions atomically invalidate affected unbooked
slots and increment relevant versions. Protect booked appointments from changes
that would invalidate them. Ticket 02 establishes compatible locking/version
and edit contracts; Ticket 03 completes actual appointment integration and tests
once appointment storage exists. D04 and D12 remain pending. This approval
authorizes Ticket 02 implementation only, not booking, commit or push.

Implementation within this approval uses PostgreSQL's bundled btree_gist for
database-enforced active interval exclusions, including shifted start times.
Weekly-rule exclusion conservatively rejects rules sharing a doctor/weekday and
intersecting effective-date/local-time ranges; consolidate rules or split their
effective dates rather than relying on empty recurrence intersections. This keeps
the small operator workflow simple and safe. Same-day windows may end at the
exclusive `24:00` boundary so split overnight schedules lose no half-hour.
Fixture advisory lock then doctor/resource/slot locks serialize maintenance with
generation; doctor, schedule/exception and affected slot versions carry staleness
into the later proposal contract. These implementation details do not select
proposal expiry, booking schema or D04/D12 policy.

## Phase 2 Ticket 03 booking — approved 2026-10-17

Owner approved D04 and booking-only D12, and booking service, authenticated HTTP
and real PostgreSQL constraint/transaction/concurrency TDD seams. Five-minute
actor/action-bound hashed opaque proposals reserve no capacity; expire at
now >= expires_at or slot start. Changed authoritative fee, relevant versions
or eligibility requires fresh review. Immutable accepted PKR pricing is persisted.

POST /appointments/proposals accepts only slot_id and returns proof, exact server
review summary and expiry. Separate POST /appointments accepts only
proposal_token, with Idempotency-Key, same-origin HTTPS and session CSRF. No
patient/clinic/price/confirmed authority fields. Initial creation returns 201;
authenticated exact successful replay returns 200 for 24 hours after commit,
even after proposal expiry, with CSRF still required. At the boundary return
409 RETRY_EXPIRED; preserve minimal actor/action/key/request binding and consumed
proof to prevent re-execution. No general cleanup/retention system is approved.

Use existing 401 authentication, 403 origin/CSRF, 422 validation; 404 for
unavailable/foreign proof, 410 for expired proof; stable 409 codes for stale
state, unavailable slot, consumed proof, retry expiry and idempotency mismatch.
Appointment, proposal consumption, retry result and minimal redacted audit commit
atomically with database-enforced single active booking and clinic-consistent
references. Locks follow user -> session -> doctor -> schedule/slot ->
proposal/retry ordering, compatible with reset/logout and operator maintenance.
Concurrent requests serialize; revalidate authority and state inside transactions.
Confirmation is a distinct authenticated submission of issued proof after review;
a model assertion or boolean cannot grant authority. Frontend/AI adapters remain
out of scope. Cancellation/rescheduling/cutoff/pricing decisions remain pending
for Ticket 04. No commit or push is authorized.
