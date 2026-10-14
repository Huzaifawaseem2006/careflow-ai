# Phase 1 — foundation

Entry: owner approves Phase 0 plan. Begin with one small health-check slice, then separate tasks for database/Alembic, CI and identity. Read PRD, architecture, contracts, decisions and progress as relevant.

## First smallest implementation task proposed for approval

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

Package location, Python version and checker dependencies are to be pinned in the task; if the toolchain cannot run, report blocked checks rather than passing them. After the first slice, define a separate Postgres/pgvector/Compose/Alembic task with migration and integration checks. Auth solution D02 must be decided before identity work.

Phase exit: health, reproducible migrations, synthetic fixtures and auth baseline demonstrated; all applicable tests pass with actual command output, and known security gaps are stated. No AI behavior until the eval harness and dataset exist.
