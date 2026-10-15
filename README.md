# CareFlow AI

Synthetic-data clinic front-desk assistant. Phase 1 ticket 01 adds a process-liveness API. The database, authentication, clinic workflows, AI behavior, frontend, and evaluation harness are future tickets.

Read [PRD.md](PRD.md), [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md), [progress](docs/PROGRESS.md), [safety](docs/SAFETY.md), [contracts](docs/API_CONTRACTS.md) and [evaluation strategy](docs/EVAL_STRATEGY.md). Phase 1 tickets 01 and 02 are approved; later tickets need separate implementation approval.

The phase plans under `plans/` follow PRD phases 0–7. See progress for actual verification evidence.

For the approved health slice, use Python 3.13.13 from `.python-version`:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e '.[dev]'
.venv\Scripts\python -m uvicorn careflow.main:app --host 127.0.0.1 --port 8000
```

`GET http://127.0.0.1:8000/health` returns `{"status":"ok"}` with HTTP 200. It reports process liveness only; it does not check the database. Run checks from the repository root:

```powershell
.venv\Scripts\python -m ruff format --check backend scripts ci_tests
.venv\Scripts\python -m ruff check backend scripts ci_tests
.venv\Scripts\python -m mypy backend scripts ci_tests
.venv\Scripts\python -m pytest backend/tests -q
```

Ticket 02 adds [GitHub Actions](.github/workflows/foundation.yml) on pushes, pull requests and manual runs. After installing `.[dev]`, run the same verification locally:

```powershell
.venv\Scripts\python -m pytest ci_tests -q
.venv\Scripts\python scripts/check_foundation.py
```

The entry point runs the four checks above, returns nonzero if any fail, and writes `test-results/foundation.json` with the checked-out Git revision, working-tree dirty flag, overall result and each check's exit code. It also prints the report; GitHub Actions copies it to the job summary even when checks fail. Run from a Git checkout at the repository root. An uncommitted local result is identified by `dirty: true`, not proof of a clean committed revision.

The subprocess regression suite runs separately to avoid recursive pytest execution. It invokes the real checks, briefly creates an unused-import probe under `backend/`, and removes it in `finally`. Run this suite serially in an otherwise idle checkout. Each test writes its report to pytest's temporary directory. No model calls or credentials are needed. The private GitHub remote is connected; [baseline hosted run #1 passed](https://github.com/Huzaifawaseem2006/careflow-ai/actions/runs/38693825109), and [isolated failure-proof run #2 failed as intended](https://github.com/Huzaifawaseem2006/careflow-ai/actions/runs/38694227925). Ticket 02 is resolved; its ticket records both commit SHAs and verification details. The failure-proof branch must not be merged into `master`.
