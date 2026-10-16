# Phase 2 — Clinic Operations

Status: planning complete; exactly four implementation tickets prepared, none implemented or individually approved. Entry checkout: clean `master` at `8a9925bc50daae32776f3d86f8a123321e2c8a91`, matching the owner's completed Phase 1 baseline. Owner reports hosted CI verified; this planning session did not independently fetch or rerun it.

## Scope and sequence

Deliver PRD FR-01–FR-05 backend operations in four focused sessions. Each slice includes persistence, deterministic services, HTTP behavior and tests. Frontend integration remains Phase 5; AI tool adapters/orchestration remain Phase 3. No new framework, worker or infrastructure is needed.

| Ticket | Delivers | Blocked by |
| --- | --- | --- |
| [01 — Clinic Catalog](../.scratch/phase-2-clinic-operations/issues/01-clinic-catalog.md) | Public scoped doctors, specialties, services and PKR fees | Phase 1 complete |
| [02 — Schedules & Availability](../.scratch/phase-2-clinic-operations/issues/02-schedules-availability.md) | Confirmed operator schedule maintenance, persisted slots, public availability | 01 |
| [03 — Appointment Booking](../.scratch/phase-2-clinic-operations/issues/03-appointment-booking.md) | Patient proposals, confirmation and transaction-safe booking | 02, transitively 01 |
| [04 — Appointment Management & Regression](../.scratch/phase-2-clinic-operations/issues/04-appointment-management-regression.md) | Owned listing, confirmed cancel/reschedule and Phase 2 gate | 03 |

`ready-for-agent` is triage, not implementation approval. Obtain individual approval, finish/hand off one ticket, then start the next in a fresh session. Every commit and push requires separate explicit approval after documentation review.

## Existing infrastructure and integration seams

Reuse FastAPI, synchronous SQLAlchemy, Alembic head `0003_patient_sessions`, native PostgreSQL/pgvector, fictional clinic/persona fixtures, confirmed local fixture/account CLIs, HTTPS/origin/CSRF checks, safe errors and disposable PostgreSQL tests. Doctors, services, schedules, slots, appointments, proposals, mutation idempotency and appointment audit storage do not yet exist; add them incrementally.

Current auth body-limit middleware covers auth routes only; appointment writes need bounded transport coverage. Current patient identity exposes no clinic assignment: derive scope from persisted patient/persona relationships, never request claims. Its lookup helper owns a separate transaction; mutations need identity revalidation in their own transaction with compatible auth locking.

Staff persona labels confer no authenticated permissions. Use explicitly confirmed local operator commands for synthetic catalog/schedule maintenance, following existing CLI safety conventions. Do not expose staff HTTP writes before staff authentication/scoped permissions exist. Staff UI/CRUD remains later D09/Phase 5 work. This provides a verifiable backend slice without making staff authentication a new dependency.

## Approved invariants and pending choices

One fictional Karachi clinic; fixed-precision PKR; `Asia/Karachi` schedule/display timezone and UTC instants; persisted non-overlapping 30-minute slots, capacity one; synthetic data only. Backend authorization, explicit confirmation, fee revalidation, atomic mutation/audit/idempotency, and no invented clinic facts/slots are mandatory. Cancel/reschedule cutoff is 24 hours before the current appointment start.

Recommendations below are **not approvals**. Resolve only the dependent choice with the owner before implementation and record it in decisions/contracts. No change to the four-ticket breakdown is needed.

- **D03, before 02:** recommend a 30-local-calendar-day generation horizon, bounded queries within it and idempotent explicit generation without a scheduler. Reject ambiguous/nonexistent local times rather than silently shifting them. Reject edits/exceptions affecting booked appointments; invalidate affected unbooked slots and stale proposals. Ticket 02 establishes the edit contract; 03 adds booked-state enforcement/tests when appointments exist.
- **D04, before 03:** recommend five-minute proposals, stale-state rejection with fresh review, and actor/operation/key-scoped retry records for at least 24 hours. Define exact expiry, post-retention behavior and safe cleanup without permitting consumed proposals to execute again. Retry retention does not set appointment/audit retention.
- **D12, before 03:** approve concrete proposal/idempotency/audit schema, fee snapshot, booking proposal/confirmation transport and errors. Extend that mechanism for cancel/reschedule in 04. Before 04, approve exact cutoff boundary (recommend allow exactly 24 hours remaining, reject less) and reschedule price treatment (recommend review/reconfirm current target fee, preserve prior price in audit).

## Verification and exit

Each ticket requires applicable format/lint/strict types, focused unit/HTTP tests, migration/readiness regression and real PostgreSQL integration evidence. Strict red/green TDD covers authorization, patient data and transactional logic. Independent connections are required for races; SQLite/mocks cannot establish concurrency correctness. Update readiness revision as migrations advance; preserve fixture reset safety and existing auth coverage.

Ticket 04 runs full applicable foundation/backend/PostgreSQL/serial CI regression with commands, revision, counts, skips and cleanup evidence. Required PostgreSQL skips block completion; unauthorized access/mutation, unconfirmed changes, duplicate booking or partial reschedule blocks phase exit. Reuse gate/report conventions with minimal extension only if needed. Verify hosted Actions at the phase milestone after separately approved commit/push; offline hosted checks do not substitute for PostgreSQL evidence. Report local implementation verification separately while hosted evidence is pending.

No AI behavior changes are planned. Preserve seven pending offline behavioral cases as pending; inventory is infrastructure evidence, not live quality. Run affected evals against baseline only if AI/tool/retrieval/prompt surfaces change. Update ticket/progress, implemented contracts and meaningful approved decisions at handoff. Do not begin Phase 3 here.
