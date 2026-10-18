# Standalone test tooling performance and Windows reliability

Owner approved Phase 2 on 2026-10-19 after the Phase 1 diagnosis, subject to
AGENTS.md and the explicit constraints in this chat. Baseline is `46d17de`.
Phase 3 Ticket 04 and paid calls are outside this task. After local verification,
the owner separately approved final scoped review, one tooling commit and one
push to origin/master; no additional commits or application changes are approved.

Improve sanitized timing/progress evidence, detect private-temp incompatibility
before expensive regressions, measure database setup before optimizing it, and
contain timed-out Windows subprocess trees. Preserve every mandatory check,
existing timeout, isolated database, real transaction/concurrency behavior and
the unchanged DPAPI credential workflow. A migrated template is conditional on
measured benefit; any isolation/security boundary change needs separate approval.

One implementation ticket: [01-test-infrastructure.md](issues/01-test-infrastructure.md).
Execution artifacts remain ignored under `test-results/tooling-diagnosis/`.
