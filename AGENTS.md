# CareFlow AI — Codex Instructions

- Think before coding; choose simple designs and surgical changes. Avoid unrelated refactors.
- Healthcare operations only: no autonomous diagnosis, prescribing or definitive triage; synthetic data only.
- Authorization is enforced by backend services, never by the LLM. Require explicit user confirmation for clinic state-changing operations.
- No unrestricted SQL tool, fabricated appointment slots, fabricated clinic facts or unsourced policy answers.

## Ticket workflow

- Work on one implementation ticket per Codex session; do not batch tickets. After verifying and handing off a ticket, normally start the next ticket in a fresh session.
- Read `AGENTS.md` once at session start; reload only if changed or no longer available in context. Inspect Git state and read the active ticket (or standalone request), latest relevant `docs/PROGRESS.md` and `docs/DECISIONS.md` entries, and relevant plan/spec sections. Use repository evidence rather than reconstructing conversation history; reconcile discrepancies before editing.
- Inspect source relevant to the change. Use targeted `rg` searches and file sections; load PRD, architecture, API and other references only to establish requirements or resolve uncertainty. Reuse unchanged material already in context; reread only for changes, missing context or a specific unresolved question. Keep context scoped to the active task.
- Prioritize a functional MVP within the owner's two-day target. Deliver the approved ticket with minimal planning and process overhead; the target does not reduce scope or quality gates without approval.
- One explicit ticket implementation approval authorizes normal work within its scope: creating files, modifying code, running tests, fixing failures and updating documentation. Make reasonable technical decisions within the approved PRD, architecture and ticket; ask only about material blockers or reserved approvals below.
- Keep communication concise: report meaningful discoveries, blockers, approval checkpoints, important failures and outcomes. Avoid command-by-command narration, repeated running-test updates and restating settled facts; follow any higher-priority update requirements.

## Verification

- For local PostgreSQL integration tests, reuse `powershell.exe -NoProfile -File scripts/postgres-tests.ps1 test`, optionally with `-TestPath` for focused tests; use `validate` when access needs checking. Keep the DPAPI credential at `%USERPROFILE%\.careflow-ai\credential.clixml` outside Git between sessions. Read [commands, isolation and limitations](docs/POSTGRES_TESTING.md) before setup, rotation, deletion or troubleshooting. Ask for interactive `setup` only when missing/inaccessible, or `rotate` when invalid/intentionally changed; never ask for the password in chat, decrypt it for diagnosis, or substitute temporary helpers/parent-shell URL exports.
- A private-temp preflight failure requires normal-host execution of the same command before regression work. Preserve redacted console logs and numeric timing artifacts under ignored `test-results/`; use completed test/stage messages to distinguish active work from a stall. Consult [timing interpretation and Windows recovery](docs/POSTGRES_TESTING.md#timings-and-progress) before changing fixtures or retrying a failed suite.
- Use strict TDD for complex or high-risk business logic, especially booking, authentication, authorization and patient data handling. Preserve required test-boundary/seam approval checkpoints from the ticket or invoked skill; reuse approvals already granted within their scope. For straightforward tasks, use focused tests without mandatory strict TDD.
- During implementation, run focused tests for each change. Once implementation stabilizes, run the full applicable regression and required format/lint/type checks for the task, including its ticket/phase gates. Booking/auth changes require permission, concurrency, idempotency and real PostgreSQL integration tests. Required failures or missing checks block completion; preserve patient privacy, security, booking correctness and data integrity.
- Reuse passing evidence for unchanged scope in the same task; do not repeat overlapping full suites without changes, failures, stale evidence or unresolved risk. Diagnose environmental failures before retrying. After a change, rerun affected checks and any mandated final gate. Keep final verification focused on fixes needed to satisfy acceptance criteria; defer unrelated improvements.
- Run independent checks concurrently only when they do not share mutable files, reports, caches or temporary paths. PostgreSQL suites and CI subprocess regressions require serial execution in an otherwise idle checkout; do not overlap them with other checks or edits. Use distinct Windows temporary/report paths for safely concurrent processes. Preserve disposable-database target checks and teardown safeguards.
- For documentation-only tasks, review the diff, links and whitespace plus configured documentation checks; application suites are unnecessary unless executable behavior changed or a specific risk warrants them.
- After AI/prompt/tool/retrieval/orchestration changes, run affected evals and compare with the prior baseline. Distinguish offline/mocked from live model-backed results. Run full applicable regression at phase boundaries and before demo/deployment; critical auth, booking or safety failures block release.
- Use hosted GitHub Actions at meaningful milestones. Existing automatic triggers still apply; extra manual CI runs or deliberate failure experiments are needed only when acceptance criteria or a material CI change justify them. Repeat checks when changes, failures or unresolved risks warrant it.

## Session Handoff and Context Management

- Record important decisions/rationale/trade-offs when they occur in `docs/DECISIONS.md`. Batch routine ticket-status and `docs/PROGRESS.md` handoff updates after implementation and verification stabilize, or record actual partial progress if interrupted. Include results, issues, blockers and next steps sufficient for a fresh session. Update phase plans only when milestones/plans change and other docs only when their subject changes; avoid per-edit logs and copies of the PRD or conversation.
- Mark a task complete only after verifying its acceptance criteria; never silently weaken them. Report checks as passed, failed, skipped or blocked, with execution evidence. If interrupted, record actual progress at the next opportunity and never claim incomplete work or unexecuted checks passed.
- Finish with a concise handoff: acceptance criteria met; files changed; checks/evals actually run and results; important decisions; remaining issues/blockers; Git-review readiness and next task. Reference evidence rather than narrating every command or duplicating logs.

## Reserved approvals and Git

- Obtain approval for destructive actions, architectural changes, scope changes/reductions and actions outside the approved ticket.
- Each paid API run requires explicit owner approval of model/cases and estimated maximum cost; credentials or a budget ceiling alone do not authorize calls. Preserve the applicable spending ledger and budget gates.
- Inspect Git at task start, when a specific change or risk warrants it, and in one comprehensive final review of scope, full diff, untracked files and sensitive/generated artifacts before requesting commit approval. Avoid repeated status/diff inventories and file counts without a concrete need. Recheck affected content after subsequent edits; after authorized staging, review the exact staged diff and whitespace before committing.
- Show documentation changes for review before committing. Each Git commit and each push requires explicit owner approval; ticket implementation approval alone does not authorize either. The proposed routine commit/push policy in `docs/DECISIONS.md` is not active until separately approved.
- Preserve unrelated work and existing Git history; do not discard unrelated changes or rewrite history.

## Agent skills

Use relevant installed Matt Pocock skills selectively when they materially improve the task. Read and follow their instructions once invoked, subject to explicit owner instructions and the approval boundaries above. Do not invoke a broad skill workflow solely to add routine reviews or ceremony.

### Issue tracker

Track issues as local Markdown under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the five default triage status strings. See `docs/agents/triage-labels.md`.

### Domain docs

Use one root glossary and root ADR directory when those documents are needed. See `docs/agents/domain.md`.
