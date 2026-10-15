# 02: Run foundation checks in CI

**What to build:** A reviewer can see a repeatable CI result for the same formatting, lint, type, and test checks used locally. Failed checks fail the job.

**Blocked by:** 01 — Start the API and verify its health (resolved).

**Status:** resolved

**Approval gate:** Satisfied. Owner separately approved ticket implementation, the baseline commit/private repository/push, the failure-probe commit/push, and the closeout commit/push. Closeout commit `3d58e32` is pushed; future commits still require explicit approval.

- [x] CI configuration invokes the documented checks without secrets in logs.
- [x] A failing check produces a failing job; a passing run records its revision and result.
- [x] The same commands pass locally; any unavailable hosted runner is reported as blocked rather than passed.

## Implementation

- `.github/workflows/foundation.yml`: push/PR/manual triggers; Python from `.python-version`; existing pinned dependencies; CI regression suite followed by shared checks; foundation JSON in the job summary.
- `scripts/check_foundation.py`: real format/lint/mypy/backend pytest subprocesses; nonzero exit on any failure; revision, dirty flag and per-check exit codes in JSON.
- `ci_tests/test_foundation_checks.py`: real passing and injected-lint-failure paths, separate temporary reports, no mocked command execution. Runs separately to prevent recursive pytest invocation.
- README documents the exact local commands and serial execution requirement. No product/API behavior changed.

## Verified acceptance evidence — 2026-10-15

| Evidence | Revision | Actual result |
| --- | --- | --- |
| [Hosted baseline run #1](https://github.com/Huzaifawaseem2006/careflow-ai/actions/runs/38693825109) | `af00055cdcce24c561e8f8dc254973fd849fdd99` | Success; 2 CI tests and 1 backend test passed; report `dirty: false`, overall passed, four zero exit codes |
| [Hosted failure run #2](https://github.com/Huzaifawaseem2006/careflow-ai/actions/runs/38694227925) | `a59f3feafbba377c15d219d751ad0750f7473358` | Failure; real Ruff F401 in `backend/ci_failure_probe.py`; CI regression step had 1 failed/1 passed and exited 1; job failed |

GitHub job metadata and actual logs were retrieved through the existing credential helper without printing/storing its credential. The initial browser log-expansion failure was resolved by reading the authenticated Actions API. The failure run stopped at `Verify CI command behavior`; the later `Run foundation checks` step was correctly skipped. No standalone foundation summary is claimed for that failed run.

Final local verification on `master`:

```powershell
.venv\Scripts\python -m pytest ci_tests -q
.venv\Scripts\python scripts/check_foundation.py
git diff --check
```

Results at closeout: 2 CI tests passed; formatting/lint/types passed (5 source files); backend pytest 1 passed. Starlette test-client deprecation and intermittent Windows pytest-cache warnings remain visible. Local runs before the documentation commit were marked dirty. [Final hosted run #3](https://github.com/Huzaifawaseem2006/careflow-ai/actions/runs/38694765791) passed for closeout revision `3d58e32dc887af99e5a0d089d9056ad14e3e99fe` with a clean-revision report.

TDD history: first test failed for the missing entry point, then passed after implementation. The next failing test caught a stale passing report after a real lint failure. Corrected result recording and report isolation, formatted the new code, and verified both tests passed. Reviewed the resulting implementation; no further refactoring was necessary.

## Repository and handoff

Private repository: [Huzaifawaseem2006/careflow-ai](https://github.com/Huzaifawaseem2006/careflow-ai). `origin` is connected; `master` includes the passing implementation and approved closeout. The intentionally red `codex/ci-failure-proof` branch is retained only as evidence; it was not merged. Confirmed `backend/ci_failure_probe.py` is absent on `master`.

Pre-upload scan: 36 candidate files and 61 historical blobs had no matching common secret/private-key/credential patterns; no environment or credential file was proposed for upload. Both hosted logs also had no matches for the token/private-key patterns checked. These bounded scans are not a comprehensive security guarantee. Local logs, structured evidence and the upload audit remain ignored under `test-results/`.

AI evaluations were skipped because no AI path changed; the full Phase 1 gate is not yet applicable. Ticket 02 has no remaining acceptance blocker. Ticket 03 is unstarted and requires separate implementation approval.
