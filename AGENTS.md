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
