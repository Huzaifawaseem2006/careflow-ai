# Proposed architecture

Status: Phase 0 architecture approved with owner-specified MVP defaults in DECISIONS.md. FastAPI liveness, database configuration, readiness and initial Alembic migration are implemented and verified with local PostgreSQL 17.11 / pgvector 0.8.7. Domain modules below remain planned. Detailed schema/API choices still require task-level review. PRD remains authoritative, with the owner-approved Docker-free amendment dated 2026-10-15.

## Minimal structure and boundaries

The existing Python package is `backend/careflow/`, with tests in `backend/tests/`, opt-in real PostgreSQL tests in `backend/integration_tests/`, and Alembic scripts in `backend/migrations/`. Future additions: `frontend/`, `evals/` and `knowledge/`; `docs/` and `plans/` already exist. Run services and PostgreSQL natively for the MVP. Docker/Compose is deferred and is not a development prerequisite. Create directories only when their first task needs them.

Next.js patient/staff UI -> same-origin FastAPI REST -> domain services -> SQLAlchemy/PostgreSQL. One explicit OpenAI tool loop calls those same services through typed adapters. pgvector stays in PostgreSQL. No Redis, worker, agent framework, separate vector DB or provider abstraction initially.

Group the PRD logical modules to avoid excessive scaffolding:

| Package | Responsibility |
| --- | --- |
| `identity` | Auth, users, patient/staff mappings, clinic assignments |
| `clinic` | Doctors, specialties, schedules, exceptions, fees, availability |
| `appointments` | Proposals, confirmation, booking/cancel/reschedule, idempotency |
| `knowledge` | Approval, ingestion, effective versions, retrieval |
| `chat` | Conversation ownership, bounded AI loop, tools, safety routing |
| `handoffs` | Consent, queue, scoped staff resolution |
| `audit` | Redacted transactional action events |

Routers validate transport inputs; services enforce auth and business rules; persistence code cannot bypass those rules. Tool adapters do not call routers or arbitrary SQL. Cross-module writes run in an explicit shared transaction. Use synchronous SQLAlchemy initially; keep blocking database work off the async model-call event loop. Reassess only with measured need.

Ticket 03 uses a process-environment `DATABASE_URL` with the `postgresql+psycopg` driver, bounded connect/statement timeouts and disposable connections. `GET /ready` verifies the expected Alembic revision and installed vector extension; it does not mutate or migrate. `GET /health` remains independent process liveness. Apply migrations explicitly with an operator role able to install the extension; application readiness only reads. The first migration enables `vector` in `public`, without domain tables or embedding dimensions. Database failure responses and Alembic connection failures omit driver exception details and credentials.

## Database sketch: PRD entities plus explicit proposals

UUID keys; timezone-aware instants in UTC; one fictional Karachi clinic with `Asia/Karachi` for display and schedule generation; fees in fixed-precision PKR. Do not use floats for fees. Foreign keys and resource-scoped indexes are required. DDL and exact field types are a Phase 1/2 review artifact.

Ticket 04 adds `clinics` settings (UUID, name, city, timezone, currency, synthetic marker) and credential-free `demo_identities` linked to a clinic. Demo roles are fixture labels only, not authorization. Actual users/patients/staff/session schemas remain dependent on D02 in Ticket 05. A local operator CLI inserts/restores fixed synthetic fixture IDs atomically with explicit confirmation; no fixture HTTP or LLM tool is exposed. The schema head becomes `0002_synthetic_fixtures`.

Retain the PRD users, patients, staff, clinics, specialties, doctors, schedules, exceptions, appointments, knowledge documents/chunks, conversations/messages, handoffs and audit entities. Seed one fictional clinic while retaining `clinic_id` authorization scope. A staff operator is a permission set rather than implicit access for all staff. Initial patient history is appointments only.

Approved persisted `slots`: 30-minute intervals generated deterministically for a bounded horizon from schedules and blocking exceptions. Propose unique `(doctor_id, start_at)` and a positive interval check. Fixed, non-overlapping slots are a precondition of this design; schedule edits must never create overlaps or silently move booked appointments. Capacity is one patient per slot; derive booked availability from active appointments rather than duplicating a booking flag. Mark invalidated unbooked slots unavailable. Define the generation horizon and DST policy explicitly, even though Karachi currently has no DST transition.

Proposed appointment states: `booked`, `cancelled`; reschedule updates the owned appointment's slot with an audit event. Partial unique index on `slot_id` for `booked` appointments protects capacity; cancelled history remains. Preserve accepted fee/currency snapshot so later catalog edits do not rewrite the confirmed price. These are proposed additions, not existing fields.

Two additional tables are proposed because the PRD sketches do not cover security invariants:

- `action_proposals`: actor, operation, exact normalized payload, resource version, displayed fee/policy version, expiry and consumed state. Store opaque token hashes, not bearer tokens in logs.
- `idempotency_records`: actor, operation, key, request digest and persisted result reference. Unique actor/operation/key; mismatched payload yields conflict. Appointment-only keys cannot cover cancellation or rescheduling retries.

Cookie sessions may require a sessions table if local identity is selected. Auth schema depends on that decision; do not pretend password hash and OIDC subject are interchangeable.

## Transaction design

Explicit user confirmation reaches a dedicated deterministic backend operation. Lock proposal and relevant appointment/slot rows in a stable order, validate current ownership, clinic scope, policy, fee and availability, then update appointment, consume proposal, persist idempotency result and audit atomically. Return persisted state only after commit. Same-key retry returns the prior result after authentication; changed payload conflicts. Consumed confirmation cannot authorize a fresh action.

For reschedule lock source and target slots in stable order and release old capacity only in the successful transaction. A failed target booking preserves the original appointment. Concurrent schedule changes must take compatible locks and invalidate proposals when their resource version changes. Test using independent PostgreSQL connections; SQLite is insufficient for this claim.

PostgreSQL documents row locks and partial unique indexes; combining them is our proposed design, whose correctness still needs integration tests. [Row locks](https://www.postgresql.org/docs/17/explicit-locking.html), [CREATE INDEX](https://www.postgresql.org/docs/current/sql-createindex.html).

## Identity and authorization

Ticket 05 implements D02: pre-provisioned synthetic patients, local Argon2id passwords and operator-only creation/reset, with no public registration/email recovery. Ticket 04 personas remain credential-free; explicit provisioning creates separate users/patients UUIDs linked to a patient persona. Fixture role labels grant no access. Sessions persist opaque token digests, a session-bound CSRF value and absolute expiry; auth_limits provides PostgreSQL-backed peer/account request limits. Schema head is `0003_patient_sessions`.

All auth routes require HTTPS; cookies are Secure/HttpOnly/SameSite=Strict and host-only. Mutations require the exact configured origin and CSRF token, including before login. Login consumes/rotates the pre-login session. Logout revokes its session. Password reset locks the user, changes the hash and revokes every owned session atomically; login takes the same user lock before locking/rotating its session. Thus old-password sessions cannot survive a completed reset. Duplicate/retried provisioning fails without changing credentials. CORS is not enabled. Backend identity lookup checks persisted expiry, account activity and patient mapping; client identity fields grant no authority. Errors omit sensitive input/configuration details. Staff authentication and production recovery remain outside this synthetic demo ticket.

| Actor | Access |
| --- | --- |
| Guest | Public catalog, general availability and approved public FAQ; no MVP handoff submission |
| Patient | Own appointments/conversations and confirmed operations |
| Receptionist | Assigned-clinic appointment/schedule permissions only |
| Handoff operator | Assigned-clinic escalations with explicit conversation access |
| Admin | Assigned-clinic catalog, knowledge approvals, staff permissions and redacted audit |

Admin is not a global bypass. Staff actions reuse the same confirmation and domain validation path. Patient registration/recovery and demo access controls need decisions before auth implementation. Appointment cancellation and rescheduling have an approved cutoff of 24 hours before start, enforced against current server time.

## AI and RAG

Authenticate/resolve conversation -> enforce limits -> safety routing -> expose only permitted tool schemas -> explicit bounded model/tool loop -> validate tool inputs and outputs -> structured response with text, citations and typed action summaries. Model/provider failure cannot count as confirmed success. Model and tool-call budgets, timeout and bounded retry rules are configured and tested. Never retry a mutation with a new key after an ambiguous timeout.

Use strict tool schemas with `additionalProperties: false`, all properties required and nullable values for optional arguments where needed. This constrains shape, not authorization or business validity. Server validation remains mandatory. Provider model and API choice stay pending capability/budget verification. [Official function-calling guide](https://developers.openai.com/api/docs/guides/function-calling). Pydantic strict validation has input-mode differences; test JSON and Python boundaries rather than claiming all coercion disappears. [Strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/).

RAG: approved synthetic local files -> deterministic parse/chunk -> configured embeddings -> versioned pgvector index. Filter by clinic, approval, effective interval and access class before similarity search. Fixed fixtures establish relevance thresholds/top-k; neither numbers nor embedding dimension are invented here. Conflicting or missing evidence causes abstention/handoff. Cite document/version/chunk identifiers and a safe backend source link. Recheck effective approval at answer assembly so withdrawn sources cannot silently remain valid. Pricing in booking comes from authoritative services, not RAG. Retrieval content is untrusted data, never instructions. No internet fetching or arbitrary uploaded URLs in MVP.

## Delivery scope

P0 first; necessary observability starts with the foundation even though FR-13 is P1. Minimal authenticated-patient handoff queue is required by P0 FR-08 before demo; broader staff CRUD remains P1. Arabic and Urdu are post-MVP. Mock reminders, MCP and chat-history expansion remain gated. Minimal synthetic conversation persistence has a proposed 30-day retention period, subject to deletion/exception design. Existing clinic information such as preparation instructions must be reviewed content, not newly generated clinical guidance.
