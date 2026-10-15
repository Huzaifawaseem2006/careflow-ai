# Phase 1 — foundation

Entry: owner explicitly approves Phase 1 implementation. Begin with one small health-check slice, then separate tasks for database/Alembic, CI, identity and evaluation infrastructure. Read PRD, architecture, contracts, decisions and progress as relevant. Owner-approved defaults: fictional Karachi clinic, `Asia/Karachi`, PKR, English MVP, server sessions, persisted 30-minute slots and 24-hour change cutoff; these belong in later slices.

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

Package location, Python version and checker dependencies are to be pinned in the task; if the toolchain cannot run, report blocked checks rather than passing them. After the first slice, define a separate Postgres/pgvector/Compose/Alembic task with migration and integration checks. Patient credential flow D02 must be decided before identity work. Phase 1 also requires a versioned synthetic evaluation dataset, schema validation, a report-producing offline harness entry point and honest pending-case accounting. Wire it to the real orchestrator path before Phase 3 AI behavior. The eval work is its own small task; it does not expand the first health-check slice.

Phase exit: health, reproducible migrations, synthetic fixtures and auth baseline demonstrated; versioned eval dataset and infrastructure created; all applicable tests pass with actual command output, and known security gaps are stated. No AI behavior until the harness is wired to the real path.

The owner approved a seven-ticket Phase 1 breakdown on 2026-10-15. Tickets cover health, CI, database migration, synthetic fixtures, patient sessions, offline eval infrastructure, and the phase gate in that dependency order. Breakdown approval was planning approval only; implementation requires separate authorization. The patient session ticket also requires D02, and hosted CI evidence requires a runner/host decision.

Tickets 01 and 02 are resolved as of 2026-10-15. Ticket 02's GitHub Actions workflow, shared check command and real-subprocess regression tests pass locally. Private remote `Huzaifawaseem2006/careflow-ai` is connected. Hosted baseline run #1 passed for `af00055`, with a clean-revision report; isolated failure-proof run #2 failed for `a59f3fe` on the deliberate Ruff F401 violation. Run URLs, full SHAs, commands and limitations are recorded in ticket 02 and progress. `master` remains on the passing baseline, with no probe; retain the red branch only as evidence and never merge it. Review the closeout documentation before explicitly approving its commit/push.

Tickets 03–07 remain unimplemented and require separate approval. The Phase 1 gate has not run. Next implementation slice is ticket 03 database migrations, but no work on it is authorized during this session.
