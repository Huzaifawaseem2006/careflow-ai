# CareFlow AI — Codex Instructions

- Think before coding; choose simple designs and surgical changes. Avoid unrelated refactors.
- Healthcare operations only: no autonomous diagnosis, prescribing or definitive triage; synthetic data only.
- Authorization is enforced by backend services, never by the LLM. Require confirmation for writes.
- No unrestricted SQL tool, fabricated appointment slots, fabricated clinic facts or unsourced policy answers.
- After every relevant code change run tests. After every AI/prompt/RAG/tool change run targeted evals; at phase gates run full regression. Distinguish mocked from live model-backed runs.
- Never report success without execution evidence. Block release for critical auth, booking or safety failures.
- Request approval before changing architecture or scope.

## Session Handoff and Context Management

- At the start of each development task or new session, inspect the actual repository state and read `PRD.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md`, and the relevant phase plan. Read architecture, API, and other documents only when the task needs them. Inspect real code before editing; reconcile discrepancies with the latest verified progress.
- Use these repository documents to understand current state instead of relying on the full prior conversation. Keep them concise; do not copy large portions of the PRD or conversation history.
- After each meaningful task and before ending a development session, update `docs/PROGRESS.md` with completed work, implementation status, verification results, issues, blockers, and next steps. Record important decisions, rationale, and trade-offs in `docs/DECISIONS.md`; update the relevant phase plan with completed milestones, remaining tasks, and plan changes. Update other documents when implementation or contracts actually change.
- Mark a task complete only after verifying its acceptance criteria. Report checks as passed, failed, skipped, or blocked; never claim that an interrupted task or an unexecuted check passed. If work is interrupted, update the documentation at the next opportunity.
- Before ending a session, give a concise handoff: completed work; files created or modified; tests and evaluations actually run with results; important decisions; outstanding issues and blockers; and the next recommended task.
- Show documentation changes to the user for review before committing them. Create Git commits only with the user's explicit approval.

## Agent skills

### Issue tracker

Track issues as local Markdown under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the five default triage status strings. See `docs/agents/triage-labels.md`.

### Domain docs

Use one root glossary and root ADR directory when those documents are needed. See `docs/agents/domain.md`.
