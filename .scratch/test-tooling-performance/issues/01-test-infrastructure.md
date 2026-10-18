# Test timing, Windows preflight and subprocess containment

Status: resolved

## Acceptance criteria

- [x] Fixed-label numeric timings cover database create/migrate/seed/provision/drop
  and subprocess work; redacted console progress identifies active tests.
- [x] Incompatible private temp access fails before database work, with a tested
  normal-host path and unchanged permissions/DPAPI credentials.
- [x] Compare measured raw/template setup; retain cloning only if justified.
- [x] Real child/grandchild regression proves bounded timeout and descendant
  cleanup, preserving the 120-second CI deadlines and all real CI checks.
- [x] Focused tests and one stabilized full applicable regression pass; preserve
  primary-database exclusion, UUID database teardown and unchanged transaction/
  concurrency coverage. Record timings, final review and remaining limitations.
- [x] Update AGENTS, PostgreSQL testing guidance and handoff/decisions evidence.

## Comments

Owner implementation approval covers this one standalone tooling task. The clone
experiment is rejected: stabilized raw 24-case run 120.45s versus cloned 119.56s;
0.89s is within observed host variance. Final fixture isolation remains unchanged.
The earlier raw 138.93s profile included repeated profiler module discovery and
must not be used to claim clone speedup. Raw/clone/safety logs remain ignored.

Verified handoff: 175 PostgreSQL passes with cleanup; 237 offline/eval/CI
passes; final-source format/lint/types and dependency checks pass. Comprehensive
source/documentation/untracked-artifact review found no unresolved issue. See
docs/PROGRESS.md (2026-10-19) and ignored tooling-diagnosis/FINAL_REPORT.md for
measurements and limitations. The owner subsequently authorized one commit and
push after final review. Exact-commit remote/Actions evidence is recorded under
ignored `test-results/tooling-git-ci.json` when publication completes.
