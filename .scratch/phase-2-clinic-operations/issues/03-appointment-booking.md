# 03: Appointment Booking

**What to build:** A signed-in synthetic patient reviews an actual slot/current fee, explicitly confirms a server proposal, and receives exactly one persisted booking under contention or retries.

**Blocked by:** 02 — Schedules & Availability (transitively 01).

**Status:** resolved

**Approval gate:** Owner approved implementation, D04 and booking-only D12 on 2026-10-17; see docs/DECISIONS.md. Commit/push each need separate approval.

## Scope and existing infrastructure

Implement PRD FR-03/FR-04 using persisted slots, catalog, patient sessions and real PostgreSQL. Add appointments, actor/action/payload-bound expiring proposals, scoped mutation idempotency and minimal transactional redacted audit. Reuse identity/origin/CSRF rules; make narrow helper changes to revalidate identity inside the mutation transaction. Current patient identity DTO lacks clinic scope: derive it from persisted patient/persona relationships. Do not create a general authorization framework or staff authentication.

## Acceptance criteria

- [x] Record approved D04 expiry/retention/retry rules and D12 schema/HTTP mappings. Migrations enforce one active booked appointment per slot and consistent patient/doctor/slot/clinic references; readiness advances.
- [x] Proposal endpoint validates server-resolved patient/scope, active doctor and actual future available slot; returns exact doctor/time/timezone/PKR fee/expiry summary. It creates no appointment and reserves no slot.
- [x] A separate same-origin CSRF-protected confirmation request binds opaque proposal and idempotency key to the displayed action. Reject missing proof, forged authority fields, expired/wrong-actor/wrong-operation/consumed proposals and changed payload. Model output or `confirmed=true` grants no authority.
- [x] Recheck account/session validity, clinic scope, resource versions, schedule/exception/slot availability and displayed fee in the transaction. Changed fee/state requires a new proposal/review. Persist immutable accepted fee/currency.
- [x] Stable lock ordering is compatible with reset/logout and schedule edits. Appointment, proposal consumption, idempotency result and audit commit atomically; return persisted state after commit. Injected failure leaves no partial action.
- [x] Same actor/operation/key and exact-request retry returns the prior booking after authentication, without duplicate action/audit. Changed payload conflicts; a new key cannot replay consumed proof. Concurrent same-key and post-retention behavior are explicit.
- [x] Independent-connection same-slot contention produces one active booking and safe losing responses. Complete 02's booked-state integration: booked slots disappear from availability and conflicting edits cannot silently move/invalidate appointments.
- [x] Appointment writes have bounded transport coverage (existing middleware only bounds auth), private responses are no-store, and safe errors/audit/logs omit tokens, cookies, credentials and unnecessary patient data.
- [x] HTTP walkthrough uses existing synthetic login to obtain proposal, confirm and verify persisted result/retry without frontend or AI adapters.

## Risk-based TDD and regression

Strict red/green TDD for identity/scope, confirmation, pricing, rollback and idempotency. Cover guests, expired/revoked sessions, disabled accounts, cross-patient/clinic access, invented IDs, malformed/extra fields, origin/CSRF failure and stale proposals. Independent PostgreSQL connections test different-patient same-slot contention, simultaneous same-key retries, different keys sharing proof, booking versus schedule/exception/fee edits, and reset/logout versus booking. Assert actual persisted state/audit, migration constraints and cleanup, not just responses.

Run applicable format/lint/types; affected auth permission/concurrency/idempotency/integration suites; booking/catalog/schedule/availability tests; migration/readiness/fixture regression. AI evals are inapplicable absent AI changes; do not add AI surfaces here.

## Out of scope

Listing/cancel/reschedule APIs (04), staff appointment writes, UI/AI confirmation adapters, payments, notifications, production recovery, real patients and new infrastructure.

## Completion

Executed evidence must verify every criterion; PostgreSQL skips, unauthorized/unconfirmed writes, duplicates or partial transactions block resolution. Update contracts/approved decisions, ticket/progress and schema status; hand off proposal/locking/retry rules to 04 in a fresh session. No commit/push without separate approval.

## Comments

2026-10-17 checkpoint: owner decisions recorded before implementation. Added
bounded strict HTTP proposal/confirmation transport, migration 0006_booking DDL,
booking storage definitions, patient clinic backfill/provisioning support and
the initial disposable-PostgreSQL HTTP walkthrough test. Booking service still
contains explicit NotImplementedError placeholders; no proposal/confirmation
persistence exists. Ticket 02 booked-state integration is still pending.
This checkout is incomplete and must not be deployed or migrated outside tests.

HTTP transport and offline migration tests were observed failing before their
implementation, then passing. The 19-test booking/migration/auth HTTP selection,
strict mypy (56 source files), Ruff format/lint and pip check passed. Real PG
behavior, constraints, concurrency, rollback and full regression remain pending;
no acceptance checkbox is verified yet. Test-client deprecation and a sandbox
pytest-cache write warning were observed. Ignored test-results helpers accept a
local hidden password encrypted with Windows DPAPI; no credential exists yet.
Owner must run configure-booking-tests.ps1 locally and reply ready. Resume via
run-booking-tests.ps1 against maintenance database postgres, creating disposable
careflow_test_<uuid> databases only. Remove helper/credential files at completion.
Final checkpoint report: test-results/booking-checkpoint.xml records 19 passed,
1 PostgreSQL test skipped (TEST_DATABASE_URL unset), zero failures. No
migration/database mutation, commit, push, AI evaluation or Ticket 04 work.


## Verified completion — 2026-10-17

All nine acceptance criteria verified. Implemented 0006_booking persistence,
server-resolved patient/clinic ownership, strict proposal/confirmation transport,
immutable accepted fee, version/window/exception/eligibility checks, compatible
locks, atomic appointment/proof/retry/audit and booked-state schedule protection.
Exact committed retries replay for 24 hours after authenticated CSRF validation;
at the boundary any well-formed reuse of the key returns RETRY_EXPIRED. A new
key cannot reuse consumed proof. No Ticket 04 surface was added.

Verification covers 200 unique tests across passing suites: 82 real PostgreSQL,
103 offline/unit and 15 serial CI regressions. Thirty-five PostgreSQL cases are
booking-specific. Full backend/offline attempt recorded 183 passed plus two
subprocess wall-clock timeout failures; the unchanged affected files then passed
23 tests, and serial CI's real foundation run passed all 103 offline/unit tests.
Final expiry/retry contract recheck passed two overlapping PostgreSQL tests.
No final required failure/error/skip remains across those passing suites.
Formatting, Ruff, strict mypy (56 files), pip check and git diff --check passed.
Both standards/spec reviews are clear after specialty-lock fix. AI evaluations
are inapplicable (no AI changes); hosted CI awaits an approved commit/push.

Retained ignored evidence: booking-verification.json, booking-foundation-final.*,
booking-ci.xml, booking-full-verified.xml, booking-offline-recheck.xml,
booking-retry-final.xml, booking-safety-final.json and booking-cleanup.json.
Earlier failing attempts remain retained, not passing: booking-full.xml (176
passed, one old role-grant failure, seven setup errors plus sandbox temp cleanup
failure), booking-full-final.xml (27 passed, one local connection timeout).
Test harness allows 10s local startup and 30s maintenance DDL only; application
connect/statement budgets remain 3s. Intermittent startup cause is unisolated.

Final independent catalog-only audit connected to postgres, found no test
DBs/roles and retained main OID 16388, inserted/updated/deleted counters
1498/91/21 matching the during-run snapshot. Tests never connected to or migrated
careflow_ai. Removed encrypted credential, four helpers and five generated test
directories; verified absence and unset verification-process database env vars.
All actual booking/fixture/migration actions used disposable careflow_test UUID
DBs. No commit/push or Ticket 04 work. See docs/PROGRESS.md for file manifest,
commands, trade-offs and next-session handoff.
