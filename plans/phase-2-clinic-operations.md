# Phase 2 — Clinic Operations

Status: Tickets 01–02 resolved. Ticket 02/D03 approved and verified on 2026-10-17: all seven criteria checked, 156 full-suite tests passed (47 PostgreSQL, including 20 Ticket 02 cases), no failures/errors/skips; standards/spec reviews found no issues. Final disposable database/role cleanup and application-data safety checks passed after investigating a background system-catalog statistics counter change; see ticket/progress for the retained initial audit failure. Tickets 03–04 remain unimplemented and need separate approval. Hosted CI is verified separately for an approved committed/pushed SHA; no new commit/push occurred. Original planning checkout: clean `master` at `8a9925bc50daae32776f3d86f8a123321e2c8a91`, matching the owner's completed Phase 1 baseline. Owner reports hosted CI verified; the planning session did not independently fetch or rerun it.

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

Reuse FastAPI, synchronous SQLAlchemy, native PostgreSQL/pgvector, fictional clinic/persona fixtures, confirmed local operator CLIs, HTTPS/origin/CSRF checks, safe errors and disposable PostgreSQL tests. Ticket 01 advances Alembic head from `0003_patient_sessions` to `0004_clinic_catalog` and implements scoped doctors, specialties, services and PKR fees. Ticket 02 advances to `0005_scheduling` with effective schedules, exceptions, persisted slots and confirmed maintenance. Ticket 03 adds 0006_booking appointment/proposal/retry/audit storage and scoped patient clinic backfill.

Ticket 03 extends existing body limits to appointment writes and resolves/revalidates identity and persisted patient/persona clinic scope inside the mutation transaction, using compatible auth locks. The public identity DTO remains unchanged; caller claims confer no authority.

Staff persona labels confer no authenticated permissions. Use explicitly confirmed local operator commands for synthetic catalog/schedule maintenance, following existing CLI safety conventions. Do not expose staff HTTP writes before staff authentication/scoped permissions exist. Staff UI/CRUD remains later D09/Phase 5 work. This provides a verifiable backend slice without making staff authentication a new dependency.

## Approved invariants and pending choices

One fictional Karachi clinic; fixed-precision PKR; `Asia/Karachi` schedule/display timezone and UTC instants; persisted non-overlapping 30-minute slots, capacity one; synthetic data only. Backend authorization, explicit confirmation, fee revalidation, atomic mutation/audit/idempotency, and no invented clinic facts/slots are mandatory. Cancel/reschedule cutoff is 24 hours before the current appointment start.

D03, D04 and booking-only D12 are approved and recorded in decisions/contracts. Ticket 04-specific D12 decisions remain **unapproved**; resolve those separately before Ticket 04. No change to the four-ticket breakdown is needed.

- **D03, approved 2026-10-17:** today plus 29 Karachi dates; exclude started slots; explicit repeatable generation without a scheduler. Queries require explicit offsets, a positive half-open range within that horizon and bounded pages. Reject ambiguous/nonexistent local times; same-day windows with overnight schedules split across weekdays. Confirmed maintenance invalidates affected unbooked slots and increments versions. Ticket 02 establishes doctor-before-slot locking and a fail-closed appointment integration boundary; 03 adds actual booked-state enforcement, availability exclusion and proposal version revalidation.
- **D04, approved 2026-10-17:** five-minute proposals without capacity holds, expiry at deadline or slot start, fresh review on changed state/fee. Exact authenticated/CSRF retries replay for 24 hours; at the boundary return RETRY_EXPIRED and preserve key/proof bindings. No cleanup system; this does not select appointment/audit retention.
- **D12, booking approved 2026-10-17:** 0006_booking schema, immutable accepted PKR fee, POST /appointments/proposals {slot_id} and POST /appointments {proposal_token} plus Idempotency-Key; 201 creation/200 replay and stable errors. Extend only with separately approved cancel/reschedule contracts in 04. Before 04, approve exact cutoff boundary (recommend allow exactly 24 hours remaining, reject less) and reschedule price treatment (recommend review/reconfirm current target fee, preserve prior price in audit).

## Verification and exit

Each ticket requires applicable format/lint/strict types, focused unit/HTTP tests, migration/readiness regression and real PostgreSQL integration evidence. Strict red/green TDD covers authorization, patient data and transactional logic. Independent connections are required for races; SQLite/mocks cannot establish concurrency correctness. Update readiness revision as migrations advance; preserve fixture reset safety and existing auth coverage.

Ticket 04 runs full applicable foundation/backend/PostgreSQL/serial CI regression with commands, revision, counts, skips and cleanup evidence. Required PostgreSQL skips block completion; unauthorized access/mutation, unconfirmed changes, duplicate booking or partial reschedule blocks phase exit. Reuse gate/report conventions with minimal extension only if needed. Verify hosted Actions at the phase milestone after separately approved commit/push; offline hosted checks do not substitute for PostgreSQL evidence. Report local implementation verification separately while hosted evidence is pending.

No AI behavior changes are planned. Preserve seven pending offline behavioral cases as pending; inventory is infrastructure evidence, not live quality. Run affected evals against baseline only if AI/tool/retrieval/prompt surfaces change. Update ticket/progress, implemented contracts and meaningful approved decisions at handoff. Do not begin Phase 3 here.
