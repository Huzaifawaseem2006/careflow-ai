# CareFlow AI — Codex Instructions

- Think before coding; choose simple designs and surgical changes. Avoid unrelated refactors.
- Healthcare operations only: no autonomous diagnosis, prescribing or definitive triage; synthetic data only.
- Authorization is enforced by backend services, never by the LLM. Require explicit user confirmation for clinic state-changing operations.
- No unrestricted SQL tool, fabricated appointment slots, fabricated clinic facts or unsourced policy answers.

## Ticket workflow

- Work on one implementation ticket per Codex session; do not batch tickets. After verifying and handing off a ticket, normally start the next ticket in a fresh session.
- At task/session start, inspect the actual repository state and read the current ticket, latest relevant `docs/PROGRESS.md` and `docs/DECISIONS.md` entries, and the relevant phase plan. Inspect real source before editing and reconcile discrepancies. Use repository evidence rather than full conversation history.
- Read relevant portions of `PRD.md`, architecture, API and other documents only when needed to establish requirements or resolve uncertainty. Reuse established context; avoid repeatedly loading the entire PRD, all plans or unrelated files.
- Prioritize a functional MVP within the owner's two-day target. Deliver the approved ticket with minimal planning and process overhead; the target does not reduce scope or quality gates without approval.
- One explicit ticket implementation approval authorizes normal work within its scope: creating files, modifying code, running tests, fixing failures and updating documentation. Make reasonable technical decisions within the approved PRD, architecture and ticket; ask only about material blockers or reserved approvals below.

## Verification

- Use strict TDD for complex or high-risk business logic, especially booking, authentication, authorization and patient data handling. For straightforward tasks, use focused tests without mandatory strict TDD.
- After relevant code changes, run applicable local tests, formatting, lint and type checks. Booking/auth changes require permission, concurrency, idempotency and integration tests. Preserve patient privacy, security, booking correctness and data integrity; fix failures before completion.
- After AI/prompt/tool/retrieval/orchestration changes, run affected evals and compare with the prior baseline. Distinguish offline/mocked from live model-backed results. Run full applicable regression at phase boundaries and before demo/deployment; critical auth, booking or safety failures block release.
- Use hosted GitHub Actions at meaningful milestones. Existing automatic triggers still apply; extra manual CI runs or deliberate failure experiments are needed only when acceptance criteria or a material CI change justify them. Repeat checks when changes, failures or unresolved risks warrant it.

## Session Handoff and Context Management

- At ticket completion and before session end, update ticket status and `docs/PROGRESS.md` with completed work, implementation status, verification results, issues, blockers and next steps. Record important decisions/rationale/trade-offs in `docs/DECISIONS.md` only when needed; update the phase plan when milestones or the plan change, and other documents when implementation or contracts change. Avoid redundant documentation after minor edits and large copies of the PRD or conversation.
- Mark a task complete only after verifying its acceptance criteria; never silently weaken them. Report checks as passed, failed, skipped or blocked, with execution evidence. If interrupted, record actual progress at the next opportunity and never claim incomplete work or unexecuted checks passed.
- Before ending a session, give a concise handoff: completed work; files created or modified; tests and evaluations actually run with results; important decisions; outstanding issues and blockers; and the next recommended task.

## Reserved approvals and Git

- Obtain approval for destructive actions, architectural changes, scope changes/reductions and actions outside the approved ticket.
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
