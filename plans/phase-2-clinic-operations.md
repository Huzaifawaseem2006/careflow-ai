# Phase 2 — clinic operations

Entry: Phase 1 gate passes; resolve D01–D04 and D12. Split into catalog, schedule/availability, booking, then cancel/reschedule slices. Review PRD and the applicable architecture/contracts/safety docs before each task.

Catalog: one synthetic clinic, active doctors/specialties, scoped read APIs and verified fees. Schedule: fixed duration/horizon and DST policy; materialized slots and exceptions; edits cannot silently alter booked appointments. Booking: server-issued proposal, explicit UI confirmation, transactional commit, unique active capacity, idempotent retries and fee snapshot. Cancel/reschedule: ownership/policy checks, confirmation, audit and rollback preserving old booking on failed reschedule.

Acceptance per slice: deterministic unit and HTTP tests; PostgreSQL integration tests for constraints and migrations. Auth/booking slices additionally require cross-user/clinic negative cases, independent-connection races, replay, stale proposal, changed payload and duplicate-key tests. Run configured format/lint/type checks and the affected suite on every change. Phase exit runs all applicable regressions; any observed unauthorized mutation or duplicate booking blocks advancement. Record command output and failures in progress.
