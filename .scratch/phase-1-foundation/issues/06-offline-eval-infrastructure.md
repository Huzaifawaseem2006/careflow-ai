# 06: Run the versioned synthetic eval set offline

**What to build:** A reviewer can validate a versioned synthetic case set and run an offline evaluation command that emits a JSON report with honest case status and version metadata.

**Blocked by:** 01 — Start the API and verify its health.

**Status:** needs-info

**Approval gate:** Explicit owner approval to begin Phase 1 implementation.

- [ ] The dataset includes positive, negative, adversarial, missing-evidence, tool-misuse, privacy, and escalation cases using synthetic data only.
- [ ] Invalid case data fails validation; pending agent cases are never counted as passed.
- [ ] Reports distinguish passed, failed, skipped, blocked, and pending cases and record code/dataset versions.
- [ ] The offline run is clearly labeled as such; no model-backed or real-agent-path result is claimed before those paths exist.
