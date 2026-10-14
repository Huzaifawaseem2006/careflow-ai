# Progress and verification ledger

## 2026-10-14 — Phase 0 planning

Status: planning artifacts drafted; owner approval pending. Repository was empty and not a Git repository at inspection. PRD v1.0 was provided as an attachment and copied verbatim to root `PRD.md`. `git init` created an empty local repository. No product source, API, migrations, app tests, eval cases or runnable service existed at inspection.

Changed scope: PRD copy; short `AGENTS.md` rules from owner; planning docs and phase plans; README and `.gitignore` as light repository bootstrap. No product features implemented.

Verified: full PRD attachment read; initial workspace entry count `0`; `git status`/`git log` reported no repository before `git init`; recursive `karpathy-*` path scan yielded no entries; official OpenAI function-calling, Pydantic strict-mode and PostgreSQL locking/index documentation opened. A PowerShell file audit found all 18 expected planning/bootstrap files and matched the copied PRD to the attachment by SHA-256. `rg --files --hidden -g '!.git/**'` and `git status --short` confirmed the scope. `git diff --cached --check` passed. No product source files appeared. The phase checkpoint is the initial Git commit; inspect Git history for its ID.

Tests/evals: none applicable to Markdown-only planning. No mocked or live model-backed evals run. No credentials, budget, model or corpus selected. No safety/clinical validation claimed.

Open risks/assumptions: D01–D12 in DECISIONS.md, especially auth/confirmation, guest handoff and retention; proposed materialized fixed slots require duration/DST approval. Arabic scheduling conflict and reschedule tool gap identified. PRD goals are broad; P1/P2 work is deferred from first demo unless owner approves scope.

Next smallest task: owner approval of Phase 0 plan, then the health-check-only Phase 1 slice in `plans/phase-1-foundation.md`. Exact future verification commands are there. Do not implement it before approval.

## 2026-10-14 — Owner-approved Phase 0 defaults

The owner approved the architecture with specified MVP defaults and explicitly required a separate approval before Phase 1. `PRD.md` was already copied from the supplied attachment and remains unchanged. The previously created `AGENTS.md` included six agent-added lines beyond the owner's nine supplied rules; those lines conflicted with the exact-text instruction and were removed. All nine original rules and heading remain in their supplied order.

Updated the architecture, decisions, safety, API, eval strategy, README and relevant phase plans to reflect one fictional Karachi clinic (`Asia/Karachi`, PKR), English MVP, server sessions, 30-minute persisted capacity-one slots, 24-hour cancellation/rescheduling cutoff, backend proposals and fee revalidation, immutable approved knowledge, authenticated patient handoff, proposed 30-day synthetic conversation retention, configurable model/budget and local Compose. Evaluation infrastructure and a versioned synthetic case set are now a Phase 1 exit requirement, with the real agent path wired before AI behavior.

PRD conflicts are tracked in DECISIONS.md with minimal proposed amendments, not silently edited: Arabic/Urdu post-MVP versus PRD Arabic P1/optional language, and authenticated handoff versus potentially guest-facing J5. Still open: patient credential/recovery details, slot generation horizon, proposal expiry and idempotency retention, detailed corpus/staff permissions, exact deletion exceptions and reviewed escalation wording. No application feature was implemented.

Verification: PowerShell `Get-FileHash -Algorithm SHA256` matched `PRD.md` to the supplied attachment byte-for-byte. A line-by-line comparison of nonempty `AGENTS.md` lines against the supplied heading and nine rules matched wording and order; the chat text has no separate source file for byte-level hash comparison. `Test-Path` found all 16 specifically required PRD/AGENTS/planning files. `git diff --check` passed (Git emitted only LF-to-CRLF working-copy warnings); `git diff --stat` showed 13 documentation files changed and no product source. No application tests, deterministic evals, mocked agent evals or live model-backed evals were run because application/eval code does not exist. Git checkpoint is recorded in Git history once committed. The next task remains the health-check-only Phase 1 slice, pending explicit approval.

## 2026-10-14 — Engineering skills setup

The owner invoked the `setup-matt-pocock-skills` skill and selected local Markdown issues and default triage labels. The repository has no Git remote, issue tracker files, glossary or ADRs, and no monorepo signals. The skill's draft was shown and the owner approved appending its `Agent skills` block to `AGENTS.md`, superseding the earlier exact-text restriction for this addition. Added `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md` and `docs/agents/domain.md`. The domain layout is single-context; a glossary or ADR is created only when a concrete term or decision needs one. No issue tickets, labels in an external service, or application features were created. Phase 1 implementation still awaits explicit approval.

Verification: PowerShell `Test-Path` found all four edited/new setup files; `Select-String` found one `## Agent skills` block; all five approved status strings were present; no glossary or ADR directory was created; `git diff --check` passed. No application tests or agent evals apply to these documentation-only changes. The checkpoint is recorded in Git history.
