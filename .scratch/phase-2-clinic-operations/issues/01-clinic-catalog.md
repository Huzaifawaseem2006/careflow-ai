# 01: Clinic Catalog

**What to build:** Guests discover the fictional Karachi clinic's active doctors, specialties and services, with authoritative consultation/service fees in PKR.

**Blocked by:** None (Phase 1 complete).

**Status:** resolved

**Approval gate:** Owner approved Ticket 01 implementation on 2026-10-16. All acceptance criteria verified locally; see final evidence below. Commit/push each need separate approval.

## Scope and existing infrastructure

Implement PRD FR-01 through persistence, scoped services and public HTTP reads. Reuse the existing clinic UUID/settings, Alembic chain, synchronous database access, safe Pydantic/errors and disposable PostgreSQL fixture. Add only doctors, specialties, services and necessary clinic/doctor associations. Distinguish consultation and service fees; use decimal PKR amounts. Provide deterministic synthetic catalog loading through an explicitly confirmed local operator path. Fixture role labels grant no authority.

## Acceptance criteria

- [x] Fresh/repeated migration reaches the new head and readiness recognizes it. Foreign keys/constraints reject invalid clinic associations and negative/invalid money values.
- [x] Public specialty/doctor reads provide bounded stable pagination and specialty/clinic filters. Karachi city supplies location context; unsupported locations yield no matches or documented validation, never invented branches.
- [x] Public service reads and doctor/service price lookup return persisted identifiers and exact decimal PKR fees. Document minimal service/fee routes alongside established catalog contracts.
- [x] Inactive doctors/services and unrelated-clinic resources are omitted; detail lookup does not expose inactive/private/cross-clinic fields or associations. Invalid IDs/filters produce stable safe errors.
- [x] Confirmed synthetic loading is repeatable without duplicates or changes to credentials/domain history/unrelated data. Existing fixture reset preserves new catalog data. No unprotected catalog write endpoint exists.
- [x] An HTTP walkthrough returns seeded doctors, matching specialties/services and persisted fees without frontend/model dependencies.

## Tests and verification

Focused tests suffice for straightforward reads; test-first negative cases cover clinic isolation and any authorization changes. Cover filter combinations, pagination/order/bounds, inactive/missing/cross-clinic IDs and decimal serialization. Real PostgreSQL tests cover migrations, constraints, repeated loading, rollback and preservation of fixture/auth data. Run applicable format/lint/types, catalog unit/HTTP/integration tests and affected foundation/readiness/fixture regression. If auth changes, its permission/concurrency/idempotency/integration coverage is required; prefer leaving it unchanged.

## Out of scope

Schedules, slots, booking, staff login/HTTP CRUD/UI, frontend, AI tools/RAG, real clinic facts, payments and infrastructure changes.

## Completion

Verify every checkbox with executed evidence; required database skips block resolution. Update ticket/progress, implemented contracts and schema status; show documentation before any separately approved commit. Recommend 02 in a fresh session, without starting it here.

## Implementation evidence — 2026-10-16

Started from clean `master`, `fc3c66be04bbd0a6aeb37b267fa97d30329a8fbe`.
Added migration `0004_clinic_catalog`, matching SQLAlchemy tables and readiness
head, public clinic-scoped read service/HTTP routes, exact decimal PKR responses
and the confirmed insert-only `careflow.catalog_fixtures` operator CLI. Added
15 offline checks and seven disposable PostgreSQL cases; updated API/schema and
operator documentation. No authentication implementation, infrastructure,
scheduling/booking, AI behavior or later ticket was changed. D03/D04/D12 remain
pending and did not block this catalog slice.

- Local foundation report `test-results/catalog-foundation-verified.json`:
  **passed**, 62 offline/unit/HTTP/eval-infrastructure tests, no skips/failures;
  format/lint/strict types passed (41 files). Dependency `pip check` passed.
- Real PostgreSQL command `python -m pytest backend/integration_tests -q -rs
  --junitxml test-results/catalog-postgres-without-credentials.xml`:
  **27 skipped** (seven new catalog + 20 existing), because TEST_DATABASE_URL
  is unset. This is **not** database acceptance evidence; all acceptance boxes
  remain unchecked pending real migration/constraint/read/filter/load/rollback
  and HTTP walkthrough execution. No connection to `careflow_ai` was made.
- Initial foundation attempts exposed an unused import/format issue (fixed)
  and Windows sandbox temp-directory errors. The successful final foundation
  command used a fresh ignored basetemp and ordinary Windows execution outside
  the sandbox. Existing Starlette deprecation remains non-failing.
- Hosted CI and model-backed evals were not run. No AI behavior changed; the
  existing seven behavioral evals remain pending. No commit/push authorized.

Resume Ticket 01 only after local PostgreSQL credential setup. Ignored
`test-results/configure-catalog-tests.ps1` securely prompts and stores a
Windows-encrypted temporary credential; `run-catalog-tests.ps1` supplies a
child-process TEST_DATABASE_URL targeting maintenance `postgres` and runs the
disposable integration suite. Never send the password through chat. Inspect
zero required skips/failures and cleanup, remove temporary credential/helpers,
then check acceptance criteria and resolve. Ticket 02 has not been started.

Additional final local evidence: serial `python -m pytest ci_tests -q --basetemp
 test-results/catalog-ci --junitxml test-results/catalog-ci.xml` completed with
**15 passed** in 72.14 seconds, including the real foundation subprocess checks.
Together with foundation: **77 passed / 27 required PostgreSQL skipped**.
No required database acceptance criterion is resolved by these offline results.

## Final verification — 2026-10-16 (supersedes pending status above)

Owner confirmed secure local credential setup and authorized continuation.
Fixed the ignored setup helper to use `Read-Host -AsSecureString`, construct a
`postgres` PSCredential and verify its Windows-encrypted Export-Clixml file.
No application source changes were needed for this continuation.

Ran `powershell -NoProfile -File .\test-results\run-catalog-tests.ps1` outside
the Windows sandbox, supplying child-process-only TEST_DATABASE_URL to local
maintenance `postgres`. **27 PostgreSQL tests passed in 124.32 seconds**, zero
failures/errors/skips: all seven new catalog cases and all 20 existing
database/fixture/auth regressions. This verifies all six acceptance criteria,
including fresh/repeated migrations/readiness, clinic and money constraints,
active-only clinic isolation, bounded filters/pages, exact persisted PKR fees,
atomic repeatable loading, fixture/auth preservation and the seeded HTTP
walkthrough. HTTP tests use the in-process ASGI API, not a deployed server.

Together with the earlier passing 62 foundation and 15 serial CI tests:
**104 passed / zero skips/failures/errors**. Independently parsed all three
JUnit reports; recorded summary `test-results/catalog-verified.json`.
Format/lint/strict types/dependencies passed as recorded above; application
source stayed unchanged. Known Starlette deprecation remains non-failing.

Read-only maintenance audits before/after authenticated PostgreSQL **17.11**
and found **zero leftover test databases or temporary auth/catalog roles**.
Integration fixtures used only generated disposable databases; no command
connected to or mutated `careflow_ai`. Removed and verified absence of the
encrypted credential, setup script, runner and temporary audit helper. Parent
DATABASE_URL/TEST_DATABASE_URL are unset. Nonsecret reports remain ignored.

Ticket 01 is **resolved**, all acceptance boxes checked. No outstanding blocker.
D03/D04/D12 remain unapproved and unchanged. No hosted CI or model-backed evals
ran; seven existing behavioral cases remain pending. Owner review and separate
commit/push approval are next. Ticket 02 requires its own approval in a fresh
session and has not been started.
