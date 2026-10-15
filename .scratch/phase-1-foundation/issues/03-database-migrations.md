# 03: Start the local database and apply migrations

**What to build:** A reviewer can start local PostgreSQL with pgvector, apply an initial Alembic migration, and verify database readiness separately from API process liveness.

**Blocked by:** 01 — Start the API and verify its health.

**Status:** needs-info

**Approval gate:** Explicit owner approval to begin Phase 1 implementation.

- [ ] Local Compose starts the configured database and enables the required vector extension.
- [ ] A clean database migrates to head and the migration can be re-run without unexpected changes.
- [ ] An integration check uses PostgreSQL and reports readiness without exposing credentials.
- [ ] Migration and integration commands, versions, and results are recorded.
