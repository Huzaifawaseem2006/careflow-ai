# Phase 1 — foundation

Entry: owner explicitly approves Phase 1 implementation. Begin with one small health-check slice, then separate tasks for database/Alembic, CI, identity and evaluation infrastructure. Read PRD, architecture, contracts, decisions and progress as relevant. Owner-approved defaults: fictional Karachi clinic, `Asia/Karachi`, PKR, English MVP, server sessions, persisted 30-minute slots and 24-hour change cutoff; these belong in later slices.

## Completed first slice — Ticket 01 reference

Create a minimal Python FastAPI project under `backend/` with pinned Python/dependency tooling, a single `GET /health` endpoint that reports process liveness only, a Pydantic v2 response model and one HTTPX/pytest test. Add Ruff and a type-check configuration, plus a minimal README command. No database, authentication, AI, frontend or clinic behavior in this slice. Keep health response free of secrets or dependency details.

Acceptance: fresh environment can install pinned dependencies; `GET /health` returns HTTP 200 and the documented response; test asserts response schema and status; formatting/lint/type/unit checks pass. Do not claim DB readiness. Review lockfile and exact package APIs before implementation.

Proposed exact verification commands, from repository root after task implementation (tool config must provide these entry points):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e '.[dev]'
.venv\Scripts\python -m ruff format --check backend
.venv\Scripts\python -m ruff check backend
.venv\Scripts\python -m mypy backend
.venv\Scripts\python -m pytest backend/tests -q
```

Package location, Python version and checker dependencies are to be pinned in the task; if the toolchain cannot run, report blocked checks rather than passing them. After the first slice, define a separate Postgres/pgvector/Compose/Alembic task with migration and integration checks. Patient credential flow D02 must be decided before identity work. Phase 1 also requires a versioned synthetic evaluation dataset, schema validation, a report-producing offline harness entry point and honest pending-case accounting. Wire it to the real orchestrator path before Phase 3 AI behavior. The eval work is its own small task; it does not expand the first health-check slice.

Phase exit: health, reproducible migrations, synthetic fixtures and auth baseline demonstrated; versioned eval dataset and infrastructure created; all applicable tests pass with actual command output, and known security gaps are stated. No AI behavior until the harness is wired to the real path.

The owner approved a seven-ticket Phase 1 breakdown on 2026-10-15. Tickets cover health, CI, database migration, synthetic fixtures, patient sessions, offline eval infrastructure, and the phase gate. Breakdown approval was planning approval only; implementation requires separate authorization per ticket/session under `AGENTS.md`. The patient session ticket also requires D02. GitHub Actions is the selected CI host.

Tickets 01 and 02 are resolved as of 2026-10-15, confirmed against source, tests and actual hosted results. Private remote `Huzaifawaseem2006/careflow-ai` is connected. Baseline run #1 passed (`af00055`); isolated failure-proof run #2 failed as intended (`a59f3fe`); approved closeout run #3 passed (`3d58e32`). `master` includes the closeout, with no probe. Run URLs and verification limits are in ticket 02/progress. Keep the red evidence branch isolated; use the accelerated one-ticket/session workflow in `AGENTS.md` and retain explicit commit/push approval.

Tickets 03–07 remain unimplemented and require separate approval. The Phase 1 gate has not run. Next implementation slice is ticket 03 database migrations, but no work on it is authorized during this session.

Ticket 03 handoff: its dependency on ticket 01 is satisfied. Before implementation in a fresh session, obtain owner approval and confirm a usable Docker/Compose/PostgreSQL runtime (Docker and `psql` were not found on PATH in this audit). Select/verify compatible PostgreSQL/pgvector, SQLAlchemy 2.x, Alembic and driver versions; define only the initial migration contents needed by ticket 03 and resolve D12 if adding schema beyond approved requirements. D02 blocks later identity work, not an infrastructure-only database slice. Acceptance remains the ticket's existing four checks: Compose/extension, repeatable migration to head, real-PostgreSQL readiness integration separate from `/health`, and recorded commands/versions/results. No database files or dependencies have been added yet.
