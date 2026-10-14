# CareFlow AI — Codex Instructions

- Read PRD.md and the relevant plan before editing. Inspect real code; never assume.
- Think before coding; choose simple designs and surgical changes. Avoid unrelated refactors.
- Healthcare operations only: no autonomous diagnosis, prescribing or definitive triage; synthetic data only.
- Authorization is enforced by backend services, never by the LLM. Require confirmation for writes.
- No unrestricted SQL tool, fabricated appointment slots, fabricated clinic facts or unsourced policy answers.
- After every relevant code change run tests. After every AI/prompt/RAG/tool change run targeted evals; at phase gates run full regression. Distinguish mocked from live model-backed runs.
- Never report success without execution evidence. Block release for critical auth, booking or safety failures.
- Keep context compact using docs/PROGRESS.md, docs/DECISIONS.md and scoped plans; do not duplicate the entire conversation.
- Update progress with verified results and open issues. Request approval before changing architecture or scope.
- Phase 0 is planning only. Do not begin Phase 1 until the owner approves the plan.
- Follow the fixed stack in PRD.md; use one bounded orchestrator, not a multi-agent product architecture.
- Before each task state acceptance criteria; after each task report changed files, exact checks, passed/failed/skipped/blocked results, risks and next smallest task. Never silently treat a missing check as passing.
- For booking/auth changes run applicable permission, concurrency, idempotency and integration tests. At every phase gate run the complete applicable regression suite.
- Keep changes reviewable and checkpoint them in Git after verification. Never commit secrets or raw sensitive traces.
- Karpathy-inspired principles here are third-party adaptations, not official Andrej Karpathy-authored skills. Review third-party skill contents before executing scripts; never blindly run remote installers.
