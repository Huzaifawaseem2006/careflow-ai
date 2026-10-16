# 01: Clinic Catalog

**What to build:** Guests discover the fictional Karachi clinic's active doctors, specialties and services, with authoritative consultation/service fees in PKR.

**Blocked by:** None (Phase 1 complete).

**Status:** ready-for-agent

**Approval gate:** Planning only; individual implementation approval required. Commit/push each need separate approval.

## Scope and existing infrastructure

Implement PRD FR-01 through persistence, scoped services and public HTTP reads. Reuse the existing clinic UUID/settings, Alembic chain, synchronous database access, safe Pydantic/errors and disposable PostgreSQL fixture. Add only doctors, specialties, services and necessary clinic/doctor associations. Distinguish consultation and service fees; use decimal PKR amounts. Provide deterministic synthetic catalog loading through an explicitly confirmed local operator path. Fixture role labels grant no authority.

## Acceptance criteria

- [ ] Fresh/repeated migration reaches the new head and readiness recognizes it. Foreign keys/constraints reject invalid clinic associations and negative/invalid money values.
- [ ] Public specialty/doctor reads provide bounded stable pagination and specialty/clinic filters. Karachi city supplies location context; unsupported locations yield no matches or documented validation, never invented branches.
- [ ] Public service reads and doctor/service price lookup return persisted identifiers and exact decimal PKR fees. Document minimal service/fee routes alongside established catalog contracts.
- [ ] Inactive doctors/services and unrelated-clinic resources are omitted; detail lookup does not expose inactive/private/cross-clinic fields or associations. Invalid IDs/filters produce stable safe errors.
- [ ] Confirmed synthetic loading is repeatable without duplicates or changes to credentials/domain history/unrelated data. Existing fixture reset preserves new catalog data. No unprotected catalog write endpoint exists.
- [ ] An HTTP walkthrough returns seeded doctors, matching specialties/services and persisted fees without frontend/model dependencies.

## Tests and verification

Focused tests suffice for straightforward reads; test-first negative cases cover clinic isolation and any authorization changes. Cover filter combinations, pagination/order/bounds, inactive/missing/cross-clinic IDs and decimal serialization. Real PostgreSQL tests cover migrations, constraints, repeated loading, rollback and preservation of fixture/auth data. Run applicable format/lint/types, catalog unit/HTTP/integration tests and affected foundation/readiness/fixture regression. If auth changes, its permission/concurrency/idempotency/integration coverage is required; prefer leaving it unchanged.

## Out of scope

Schedules, slots, booking, staff login/HTTP CRUD/UI, frontend, AI tools/RAG, real clinic facts, payments and infrastructure changes.

## Completion

Verify every checkbox with executed evidence; required database skips block resolution. Update ticket/progress, implemented contracts and schema status; show documentation before any separately approved commit. Recommend 02 in a fresh session, without starting it here.
