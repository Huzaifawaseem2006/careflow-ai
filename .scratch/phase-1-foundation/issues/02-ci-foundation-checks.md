# 02: Run foundation checks in CI

**What to build:** A reviewer can see a repeatable CI result for the same formatting, lint, type, and test checks used locally. Failed checks fail the job.

**Blocked by:** 01 — Start the API and verify its health.

**Status:** needs-info

**Approval gate:** Explicit owner approval to begin Phase 1 implementation. Select a CI runner or repository host before claiming a hosted CI pass.

Owner approved ticket 02, the subprocess test boundary and GitHub Actions on 2026-10-15. Local implementation is verified; status remains `needs-info` pending a connected remote and hosted job evidence. No commit or remote creation is authorized.

- [x] CI configuration invokes the documented checks without secrets in logs.
- [ ] A failing check produces a failing job; a passing run records its revision and result.
- [x] The same commands pass locally; any unavailable hosted runner is reported as blocked rather than passed.

## Verification — 2026-10-15

- **Red:** `.venv\Scripts\python -m pytest ci_tests/test_foundation_checks.py -q` failed because the entry point did not exist. After the minimal passing implementation, 1 test passed.
- **Red:** `.venv\Scripts\python -m pytest ci_tests/test_foundation_checks.py::test_real_lint_failure_returns_nonzero_and_records_failure -q` caught a stale passing report after a real Ruff F401 failure.
- **Green:** after collecting check return codes and writing a fresh failure report, `.venv\Scripts\python -m pytest ci_tests/test_foundation_checks.py -q` passed both tests. A formatting issue in the new argument declaration was corrected with `.venv\Scripts\python -m ruff format scripts ci_tests` before the final green run.
- **Passed locally:** `.venv\Scripts\python scripts/check_foundation.py` ran format, lint, mypy and the backend test. Report records HEAD `be3c5b9becf243d677b4c8a3d58dcda933e4d195`, `dirty: true`, overall pass and four zero exit codes. This is uncommitted working-tree evidence.
- **Partial criterion 2:** real failure propagation and revision/result reporting are verified locally; workflow uses normal failing-step behavior without `continue-on-error`. Actual passing/failing GitHub jobs are **blocked**, since no remote is connected. Do not mark this ticket resolved until hosted evidence verifies the remaining criterion.
- **Warnings:** existing Starlette test-client deprecation; an intermittent Windows pytest-cache access warning. Both are visible and unsuppressed.
- **Skipped:** AI evaluations (no AI path changed). Workflow syntax was reviewed against official GitHub documentation; no automated workflow linter is installed and no hosted syntax validation ran.

## Files and next step

Added `.github/workflows/foundation.yml`, `scripts/check_foundation.py` and `ci_tests/test_foundation_checks.py`; updated README, this ticket, progress, decisions and the Phase 1 plan. No product behavior or API contract changed. Review the changes, then separately authorize a commit/remote setup if desired. Run the workflow after connecting the repository; capture both passing and deliberately failing job evidence before closing this ticket.

## Closeout review — awaiting owner approvals and GitHub sign-in

Reviewed the workflow, check entry point, subprocess tests, dependency configuration and related documentation against all three acceptance criteria. No blocking local implementation defect was found. Repeated `.venv\Scripts\python -m pytest ci_tests -q` (2 passed), `.venv\Scripts\python scripts/check_foundation.py` (all four checks passed; 1 backend test), and `git diff --check` (passed). The two known warnings remain visible.

The owner selected a new private `careflow-ai` repository under their authenticated personal GitHub account (provided profile: `Huzaifawaseem2006`), with no generated README, license or gitignore. Repository creation, Git commits and pushes still require explicit approval. The available in-app browser is signed out, so account ownership is not yet verified. GitHub CLI is not installed. No remote has been added.

Before upload, a local pattern scan covered 36 candidate source/document files and 61 reachable historical Git blobs. No matching token/private-key/credential-assignment patterns or sensitive candidate filenames were found. No `.env`, credential file, virtual environment, cache or test-result artifact is in the proposed upload. This is a bounded scan, not a guarantee that automated detection finds every secret or sensitive datum. The exact 24-file pending-change manifest and complete working-tree review patch (including untracked code) are available as ignored review artifacts under `test-results/`.

Remaining closeout sequence:

1. Owner signs into GitHub; verify the authenticated account and empty private repository settings.
2. Owner reviews and explicitly approves the proposed baseline commit, private repository creation and initial push. Baseline includes earlier approved handoff/planning and ticket 01 changes required for a reproducible project; tickets 03–07 are planning documents only.
3. Connect `origin`, push the baseline, then record the actual successful Actions run URL, commit SHA, job/step conclusions and foundation report.
4. Prepare a separate `codex/ci-failure-proof` branch with one temporary unused-import file; obtain explicit approval for its commit and push. Verify the actual hosted job fails on the injected problem. Never merge the probe into `master`.
5. Return to the passing branch, record both run URLs/SHAs and final local checks, then check the remaining acceptance box and mark `resolved` only after evidence is complete. Show closeout documentation and obtain separate approval before committing it.

Ticket 03 remains unstarted. This review does not close ticket 02.
