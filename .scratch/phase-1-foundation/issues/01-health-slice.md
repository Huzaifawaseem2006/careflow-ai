# 01: Start the API and verify its health

**What to build:** A reviewer can start the minimal FastAPI service and receive a typed liveness response from its health endpoint. The response reveals no secrets or database details.

**Blocked by:** None.

**Status:** resolved

**Approval gate:** Satisfied for this ticket by the owner's explicit approval on 2026-10-15.

- [x] A fresh environment installs the pinned project and development dependencies.
- [x] An HTTPX test confirms the documented liveness response and HTTP status.
- [x] Formatting, lint, type checking, and unit tests pass using the commands in the Phase 1 plan.
- [x] The endpoint reports only process liveness; it does not claim database readiness.

**Verification:** A Python 3.13.13 virtual environment installed the pinned direct runtime and development dependencies. Ruff format and lint, mypy, pytest, and `pip check` passed. Pytest reported one passing test and one Starlette deprecation warning about its HTTPX-backed test client. Uvicorn started and a local HTTP request returned 200 with exactly `{"status":"ok"}`. No database or model evaluation ran.
