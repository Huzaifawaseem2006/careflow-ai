# Decisions and PRD review

2026-10-14. Status labels: **approved** = explicitly chosen by owner; **proposed** = needs review; **open** = no selection. The owner approved the Phase 0 architecture with the MVP defaults below. Phase 1 implementation still requires separate explicit approval.

## Approved MVP decisions

- One fictional clinic in Karachi, Pakistan; `Asia/Karachi` timezone, PKR fees, English first. Arabic and Urdu are post-MVP.
- Fixed stack: FastAPI modular monolith; PostgreSQL/pgvector; SQLAlchemy 2.x, Pydantic v2, Alembic; Next.js, TypeScript, Tailwind; OpenAI SDK with explicit tool calling and structured outputs. One bounded orchestrator.
- Server-managed sessions using secure HttpOnly cookies and appropriate CSRF protection; no public staff registration. Precise patient registration/recovery flow remains open.
- Persisted 30-minute appointment slots, capacity one; database integrity, transactional writes and idempotency. Cancellation and rescheduling allowed until 24 hours before the appointment.
- Explicit frontend confirmation for state-changing actions using backend-issued expiring proposals bound to authenticated actor and exact operation. Revalidate fees before booking; changed fees require fresh confirmation.
- Admin-approved immutable versioned knowledge documents. Authenticated patient handoffs initially.
- Minimal conversation persistence with a **proposed** 30-day synthetic demo retention period; duration and deletion exceptions remain for final approval.
- Configurable OpenAI model and evaluation budget; local Docker Compose deployment first. No clinical diagnosis, prescribing or definitive triage.
- Establish evaluation infrastructure and a versioned synthetic dataset during Phase 1, before AI behavior. Deterministic security assertions; mocked and live runs labeled separately.
- `PRD.md` is authoritative and remains byte-for-byte unchanged. The owner's nine original `AGENTS.md` instructions are preserved; an `Agent skills` block was later appended with explicit owner approval for local issue tracking, triage and domain-doc pointers.

## Approval register

| ID | Decision | Recommendation / consequence | Needed before |
| --- | --- | --- | --- |
| D01 | Emergency locale language | Clinic location is Karachi/`Asia/Karachi`/PKR. Approve exact local escalation wording and any emergency contact reference through D11. | Safety wording |
| D02 | Patient identity lifecycle | Server-managed cookie sessions approved. Choose local credentials/recovery or a compatible identity backend; no public staff registration. | Auth task in Phase 1 |
| D03 | Slot horizon and DST handling | 30-minute persisted slots and 24-hour change cutoff approved. Choose generation horizon and schedule-edit behavior; use clinic timezone. | Phase 2 |
| D04 | Proposal expiry / retry retention | Actor/action-bound proposals and fee revalidation approved. Choose expiry, stale-state behavior and idempotency retention without weakening invariants. | Phase 2 |
| D05 | Handoff scope | Authenticated patient handoff approved; guest handoff deferred. Define staff queue permission and consent/retention. | Chat/handoff |
| D06 | Corpus details | Immutable admin-approved versions approved. Choose synthetic source set, reviewer and withdrawal policy. | Phase 4 |
| D07 | Model, embeddings and eval budget | Configurable model/budget approved; select actual IDs, embedding setup and budget after capability check. No live run or price claim yet. | Phase 3 live eval |
| D08 | Hosted demo | Local Compose first approved; select host, TLS and protected demo accounts before publishing. | Phase 7 |
| D09 | Staff scope | Arabic and Urdu post-MVP. Minimal appointments/handoff queue for P0 proposed; choose detailed staff CRUD scope. No reminders/MCP for first demo. | Frontend scope |
| D10 | Retention and deletion | Proposed 30-day synthetic conversation retention, with deletion behavior, handoff/audit exceptions and disclosure still to decide. | Persistence for chat |
| D11 | Clinical wording review | Owner names appropriate reviewer and approves locale-specific escalation text before demo; no clinical validation claim. | Safety eval/release |
| D12 | Schema additions and API changes | Proposals/idempotency tables, fee snapshot, session storage as applicable; reschedule tools/proposal endpoints described in contracts. | Schema/API implementation |

Explicit Phase 1 approval blocks the first health-check slice. Remaining decisions block only dependent tasks. Do not ask every open question before making unrelated progress.

## Contradictions, gaps and risks

- J7 says Arabic in a second phase, FR-12 marks it P1 and Phase 6 says optional. Owner resolved MVP scope: Arabic and Urdu post-MVP. PRD remains unchanged; propose a minimal PRD amendment marking FR-12 post-MVP and removing ambiguity at Phase 6.
- J5 offers handoff to a possible guest, but Section 8 requires authenticated mutation. Owner resolved MVP scope: authenticated patient handoff. Propose a minimal J5 amendment stating that handoff requires sign-in. Public chat submission can remain guest-accessible without claiming a persisted handoff.
- Cancel/reschedule are P0, but tool list omits propose/confirm reschedule. Add only after contract approval.
- Section 8 exposes mutation routes without proposal routes or proof transport. A model-generated `confirmed=true` is insufficient; bind a server proposal to an actual user event.
- Single `role` does not fully express clinic scope or handoff-operator access. Define permission mapping without adding enterprise RBAC.
- Slot duration is now 30 minutes, with capacity one. Generation horizon, overlapping schedule edits, DST behavior and status transitions remain unspecified. Do not assume unique start time prevents arbitrary interval overlap.
- Appointment idempotency key alone cannot cover all mutations. Define actor/operation scoping, payload mismatch and retry retention.
- Doctor filters include location, but initial clinic schema has no explicit location field. For one-clinic MVP filter by clinic ID; decide whether free-text location is actually needed before adding fields.
- Source links can be invalid or unsafe; use stable backend citation endpoints, never model-invented URLs. Decide knowledge clinic/access scope and effective-version conflicts.
- Chat ownership, guest-to-patient transfer, disclosure/deletion, staff access and audit retention are not fully modeled. The owner proposed 30 days for synthetic conversations; this is not yet a complete deletion policy.
- Handoff is P0 but broad dashboard P1/Phase 5; an actual authorized queue is needed to avoid a fake handoff claim.
- Observability is P1 yet eval evidence and safety require traces from the first AI slice. Implement minimal redacted metrics early.
- Eval targets are provisional, sample size and held-out governance are missing. Baseline must precede calibration; zero observed violations is not a security guarantee.
- Preparation instructions can cross into medical advice. Only approved clinic material; never generate treatment guidance.
- P0 surface is large: defer Arabic, Urdu, Redis, reminders, MCP, richer records and real integrations to avoid scope creep.

## Skills audit

Recursive name scan of `C:/Users/USER/.codex/skills` and `C:/Users/USER/.codex/plugins` returned no `karpathy-*` paths. No such skill is in the supplied skills catalog. No third-party skill was installed or executed; compatibility cannot be assessed without source contents.

Options if later requested: provide a specific repository/version for read-only review, then manually place a reviewed Codex-compatible `SKILL.md` under the personal skills directory; or use the available skill-installer after source review and explicit installation authorization. Review instructions, referenced resources and scripts, provenance/license, path assumptions and Codex tool compatibility. Never pipe a remote installer into a shell. Current AGENTS rules apply the requested principles without a third-party package.

## Source checks

Official OpenAI function-calling, Pydantic strict-mode and PostgreSQL locking/index pages were opened on 2026-10-14; links and limited implications are in ARCHITECTURE.md. No package version or model capability has been selected by this check. Reverify relevant APIs against pinned versions when implementing.
