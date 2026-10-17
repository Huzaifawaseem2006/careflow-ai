# Proposed API and tool contracts

Status: health/readiness, the Ticket 05 patient-session routes and the Phase 2 public catalog/availability and Ticket 03 booking routes below are implemented. Other domain endpoints and all AI tools remain planned. URL names from PRD are retained where possible; exact schemas, status codes and provider-specific schema support will be checked in their implementation slices. No client or model assertion substitutes for server authorization.

## Common rules

All request/response bodies are versioned Pydantic v2 models with bounded lengths and `extra=forbid` where appropriate. Stable error envelope: `{code, message, correlation_id}`; avoid disclosing private resource existence. Proposed codes: `AUTH_REQUIRED`, `FORBIDDEN`, `NOT_FOUND`, `VALIDATION_ERROR`, `CONFIRMATION_REQUIRED`, `CONFIRMATION_EXPIRED`, `STATE_CHANGED`, `SLOT_UNAVAILABLE`, `POLICY_BLOCKED`, `IDEMPOTENCY_CONFLICT`, `RATE_LIMITED`, `UPSTREAM_UNAVAILABLE`. Exact HTTP mapping remains to be reviewed.

All instants use ISO 8601 with offset; responses include clinic timezone for display. Fee is decimal amount plus ISO currency, never float. Public availability and price are snapshots, not reservations. Mutation response contains persisted appointment ID/state plus correlation ID, or a stable error. Every request is rate/body limited. Auth uses server context; role, patient, clinic and actor IDs are not accepted as authority from JSON or model args.

Approved explicit confirmation flow: `POST /appointments/proposals` or corresponding cancel/reschedule proposal endpoint returns a short-lived opaque proposal ID and exact review summary. UI displays that summary; a distinct user click submits proposal ID and an idempotency key to the appropriate mutation endpoint. The server checks actor, operation, payload digest, slot/resource state, displayed fee and policy version, expiry and one-time consumption. A changed consultation fee requires a new proposal and confirmation. AI `confirm_*` calls alone never prove a user click. A staff UI needs the same principle for appointment writes. Chat-message submission is not an appointment mutation; handoffs require authenticated patients in the MVP.

## REST surface

| Route | Actor | Contract invariant |
| --- | --- | --- |
| `GET /health` | Public | Implemented: HTTP 200 with `{"status":"ok"}`; process liveness only, no database readiness or sensitive details |
| `GET /ready` | Public | Implemented: HTTP 200 with `{"status":"ok"}` only when PostgreSQL is reachable, the expected Alembic revision is applied and `vector` is installed; otherwise HTTP 503 with `{"status":"unavailable"}`. No credentials or dependency details; `Cache-Control: no-store`. Verified against PostgreSQL 17.11 / pgvector 0.8.7. |
| `GET /auth/csrf` | Same-origin browser | Implemented: 200 `{csrf_token}` and a Secure/HttpOnly cookie; creates a 10-minute pre-login session or reuses a valid session without extending its deadline. |
| `POST /auth/login` | Pre-login session | Implemented: JSON `{email, password}`, exact configured Origin and session-bound `X-CSRF-Token`; rotates session/CSRF tokens on success, returning 200 `{csrf_token}` and a new cookie. |
| `GET /auth/me` | Provisioned patient | Implemented: 200 `{user_id, patient_id, email, role: "patient"}` resolved from a valid stored session and active account/patient mapping; otherwise 401. |
| `POST /auth/logout` | Same-origin browser | Implemented: valid sessions require matching CSRF; revokes session and clears cookie, 204. Retrying after revocation/expiry is harmless, 204; origin is still required. |
| `GET /specialties` | Public | Implemented: active specialties in the fixed demo clinic; bounded pagination and clinic/city filters |
| `GET /doctors` | Public | Implemented: active doctors and specialties; specialty UUID and clinic/city filters; exact consultation fee |
| `GET /doctors/{id}/slots` | Public | Implemented in Ticket 02: persisted active future slots, required offset-aware bounded range; GET never generates |
| `POST /appointments/proposals` | Patient | Implemented: strict `{slot_id}`; authenticated, same-origin CSRF; 201 review/proof/expiry, no reservation |
| `POST /appointments` | Patient | Implemented: strict `{proposal_token}` plus Idempotency-Key; 201 persisted booking, 200 exact replay; atomic proof/retry/audit |
| `GET /me/appointments` | Patient | Own records only, bounded pagination |
| `POST /appointments/{id}/cancel-proposal` | Owner or authorized staff | Check ownership/scope and current policy; exact summary |
| `POST /appointments/{id}/cancel` | Owner or authorized staff | Confirm bound proposal; audit; idempotent retry |
| `POST /appointments/{id}/reschedule-proposal` | Owner or authorized staff | Validate target slot and current appointment; no state change |
| `POST /appointments/{id}/reschedule` | Owner or authorized staff | Confirm bound proposal; one transaction, old slot preserved on failure |
| `POST /chat` | Guest or authenticated | Bounded input, scoped conversation access; structured citations/actions |
| `POST /handoffs` | Authenticated patient | Persist owned queue request with consent; return actual ID/status |
| Staff routes, precise paths TBD | Scoped staff/admin | Clinic assignment and explicit permissions for schedule, documents, escalations and redacted audit |

Proposal paths are additions to the PRD draft required for server-verifiable confirmation. J5 should be minimally amended to state that handoff requires patient sign-in. Do not expose staff CRUD before its scoped service rules exist. Slot identifiers refer to persisted 30-minute capacity-one slots; cancellation and rescheduling use the approved 24-hour cutoff.

### Public clinic catalog (Phase 2 Ticket 01)

Implemented guest reads: `GET /specialties`, `GET /doctors`, `GET /services`,
`GET /doctors/{id}`, `GET /services/{id}`, `GET /doctors/{id}/fee` and
`GET /services/{id}/fee`. No catalog write route or AI adapter exists.

Lists return `{items, limit, offset}` ordered by persisted name then UUID.
`limit` defaults to 20 (1–100), `offset` to 0 (0–10000). All lists accept optional
`clinic_id` (UUID) and `city` (1–80 characters, trimmed case-insensitive exact
match); doctors also accept `specialty_id` (UUID). Unknown filters, including
`active=false`, are rejected. Public active status is mandatory, never widened
by a caller. The fixed server scope is demo clinic
`00000000-0000-4000-8000-000000000001`. Another clinic UUID or unsupported city
returns an empty page; no additional branches are inferred. Location is the
persisted clinic city, currently Karachi; no finer location search is implemented.

Specialties expose `{id, clinic_id, name, city}`. Doctors add `specialty_id`,
`consultation_fee`, `currency`; services add `fee`, `currency`. Each doctor has
one clinic-scoped specialty; services are independently clinic-scoped. Fees are
persisted decimal PKR values serialized as strings with exactly two decimal
places (e.g. `"3500.50"`). Fee endpoints return `{id, amount, currency: "PKR"}`,
using the same persisted resource ID and current fee as detail/list reads.
These are price snapshots, not appointment reservations or booking fee snapshots.

Inactive doctors/services, doctors with inactive specialties and resources in
other clinics are omitted. Detail/fee lookups share those restrictions and return
generic 404 `NOT_FOUND`. Malformed IDs/filters return safe 422 `VALIDATION_ERROR`;
database/configuration failures return 503 `CATALOG_UNAVAILABLE`. Errors use the
existing correlation-ID envelope without SQL, credentials or private associations.

### Schedules and public availability (Phase 2 Ticket 02)

`GET /doctors/{id}/slots` requires ISO `start_at` and `end_at` with explicit UTC
offsets (including `Z`). Offset-free dates/timestamps and numeric epochs are
rejected. The half-open interval `[start_at, end_at)` must be positive and lie
within today's Karachi midnight through midnight after the next 29 dates.
Only whole slots contained in the requested interval are returned, excluding
already-started slots. Optional `clinic_id` only narrows the fixed demo-clinic
scope. `limit` defaults to 20 (1–100), `offset` to 0 (0–10000); unknown filters
are rejected. Ordering is start instant then UUID.

Response: `{items, limit, offset, timezone: "Asia/Karachi"}`. Each slot exposes
`{id, clinic_id, doctor_id, start_at, end_at, version, timezone}`. Timestamps are
local ISO instants with `+05:00`; storage uses UTC instants. Slots are persisted
30-minute capacity-one resources. Empty, missing, inactive or other-clinic doctors
produce an empty 200 page; inactive specialties also hide their doctors' slots.
Blocking exceptions and inactive source schedules/slots are excluded. No exception
reason, patient field or internal schedule definition is public. Invalid input
returns safe 422 `VALIDATION_ERROR`; unavailable persistence returns safe 503
`CATALOG_UNAVAILABLE`, using the existing correlation envelope.

No schedule HTTP mutation endpoint or staff authority exists. Local operator CLI
`python -m careflow.schedule_operator` accepts `schedule`, `exception`,
`deactivate-schedule`, `deactivate-exception` and `generate`, a required
`--doctor-id`, bounded JSON `--input` for maintenance, and explicit
`--confirm-synthetic-schedules`. The existing local synthetic-target guard and
current migration head are required. API database roles get SELECT only on
scheduling tables, never scheduling writes or doctor UPDATE authority.

Schedule input: `{id, expected_version, weekday, local_start, local_end,
effective_from, effective_to}`. UUIDs are operator supplied; version 0 creates,
subsequent edits require the current version. Weekdays are Monday=0–Sunday=6;
effective dates are inclusive. Windows use minute-precision Karachi wall times,
contain whole 30-minute intervals and stay within one local date. `local_end`
may be `"24:00"`, the exclusive midnight ending that date; overnight schedules
require separate weekday definitions. Ambiguous/nonexistent local times fail
generation with full rollback. Conflicting effective windows are rejected.

Exception input: `{id, expected_version, start_at, end_at, reason}` with explicit
offsets, positive bounded horizon interval and a 1–160 character synthetic reason.
Any intersection blocks a slot; adjacent endpoints do not intersect. Deactivation
input: `{id, expected_version}`. Each successful maintenance command increments
the resource version and `doctors.schedule_version`; invalidated slots increment
their own versions. Edits invalidate slots sourced from that schedule; exceptions
invalidate intersecting active slots. Removal never automatically restores slots.
Explicit generation inserts/reactivates eligible slots only, using stable IDs;
reactivation increments the slot version, while an unchanged repeat changes none.

Lock order is fixture advisory lock `48405004`, doctor row, schedule/exception,
then affected slots, all in one transaction. Ticket 03 uses the compatible
doctor-before-slot order and revalidates resource versions. It replaces the
earlier fail-closed table guard with actual booked-state checks before
invalidation and active-appointment exclusion in availability. Changes that
invalidate booked appointments fail without moving them. Approved D04/booking
D12 are implemented below.

### Patient-session transport and errors

Auth routes require HTTPS. Cookie `__Host-careflow_session` is host-only, Path=/, Secure, HttpOnly, SameSite=Strict; authenticated sessions expire after eight hours absolutely. Only the session token's SHA-256 digest is persisted. CSRF tokens are random session-bound values; obtaining one does not authenticate a patient. Login/logout require an exact Origin match to AUTH_ORIGIN (default `https://localhost:8000`). GETs reject explicitly foreign origins and cross-site fetch metadata; normal same-origin GETs need no Origin header. CORS is not enabled. URLs, role/patient fields and caller identity headers grant no authority.

All auth responses use Cache-Control: no-store. Auth POST bodies are bounded to 4096 bytes before parsing, including requests without Content-Length. Email is bounded to 160 characters and normalized for lookup; passwords are bounded to 128 characters, never trimmed or echoed in validation errors. Extra login fields are rejected. PostgreSQL persists a shared limit of 30 CSRF/login requests per peer IP per minute and five login attempts per normalized email per five minutes, including successful attempts. New sessions do not reset these limits. Expired counters are cleaned opportunistically. A deployment proxy must supply the real client address only through explicitly trusted configuration; local HTTP tests do not establish proxy/TLS deployment.

Errors use `{code, message, correlation_id}`: 401 AUTH_REQUIRED or generic INVALID_CREDENTIALS; 403 CSRF_REJECTED; 413 REQUEST_TOO_LARGE; 422 VALIDATION_ERROR; 429 RATE_LIMITED with conservative Retry-After: 300; 503 AUTH_UNAVAILABLE. Database/configuration details and passwords are omitted. Wrong-password, unknown-account and unprovisioned-persona login errors have the same body/status; identical whole-request timing is not claimed. Public registration/recovery endpoints are absent (404), including staff registration.

## Agent tools

Strictly allowlisted, versioned tool schemas with validated inputs and outputs. The tool dispatcher receives authenticated context separately. Read-only tool payloads can include normalized search filters or resource identifiers, but never an authoritative `patient_id`, `role` or `clinic_id`. Limits, dates, UUID parsing and results are checked by backend code even if the provider returns schema-conforming JSON. Document the concrete schema and return types alongside each implementation.

| Logical tool | Service operation | Important boundary |
| --- | --- | --- |
| `search_doctors` | Catalog search | Active, public, clinic-scoped |
| `get_available_slots` | Availability query | Validated range and timezone |
| `get_consultation_fee` | Current catalog fee | Backend source; booking rechecks/snapshots |
| `retrieve_clinic_policy` | Approved effective retrieval | Source/version/chunk trace; abstain without evidence |
| `get_my_appointments` | Owned appointments | Auth actor from server only |
| `propose_booking` | Create bound proposal | May return UI review object; no booking |
| `confirm_booking` | Call confirmation service | Only with server-verified UI confirmation capability |
| `propose_cancellation` | Create bound proposal | Ownership/policy checked |
| `confirm_cancellation` | Call confirmation service | Same confirmation rule |
| `propose_reschedule` / `confirm_reschedule` | Proposed additions, D12 | Needed for J4, not in PRD allowlist |
| `request_handoff` | Queue service | Authenticated patient and consent required |

Do not make confirm tools generally callable from ordinary model output. A confirmed user event is the authority to execute; the orchestrator can describe the resulting operation but cannot manufacture confirmation. No SQL, shell, browser or direct provider-backed data tool is exposed to the model. Tool outputs contain only permitted fields and safe errors.


### Patient booking (Phase 2 Ticket 03)

Both POST routes require existing HTTPS patient cookies, exact AUTH_ORIGIN and
X-CSRF-Token; no client identity/clinic/price/confirmed fields are accepted.
Bodies, including chunked requests, are capped at 4096 bytes before JSON parsing.
All private success/error responses use Cache-Control: no-store. Staff writes,
listing/cancellation/rescheduling and AI/UI adapters remain unimplemented.

POST /appointments/proposals accepts only `{slot_id: UUID}`. A 201 response is
`{proposal_token, summary, expires_at}`. The summary contains slot_id, doctor_id,
clinic_id, doctor_name, start_at, end_at, timezone, fee and currency. Timestamps
include Karachi offsets; fee is a two-decimal string and currency is PKR.
The 256-bit random proof is stored only as a SHA-256 digest, bound to the
persisted patient/actor/clinic, operation book and exact server summary/versions.
Expiry is creation plus five minutes; now >= expiry or slot start rejects it.
No capacity is reserved. Resource changes require a new review; a concurrent
booking can win before confirmation.

POST /appointments accepts only `{proposal_token}` with Idempotency-Key matching
`[A-Za-z0-9_-]{1,128}`. Success returns the persisted id, patient_id, clinic_id,
doctor_id, slot_id, status booked, doctor_name, start_at, end_at, timezone,
accepted_fee, currency and created_at. Accepted fee/currency/time/doctor snapshot
is immutable. The separate submission expresses confirmation of the issued
review; booleans/model statements grant no authority. Future UI/AI adapters must
provide the distinct explicit user action; this backend does not attest a click.

The same actor/operation/key with the same proof returns 200 with the prior
persisted booking for 24 hours after successful creation, including after proof
expiry; authentication/CSRF remain mandatory. At now >= replay_until return
409 RETRY_EXPIRED for any well-formed request reusing that key. Within the replay
window, changed proof under a used key returns 409 IDEMPOTENCY_CONFLICT;
a new key with consumed proof returns 409 PROPOSAL_CONSUMED. Minimal bindings and
consumed proofs are retained; no cleanup/retention worker exists. User-row locks
serialize simultaneous keys for one actor; different actors contend on the doctor
then slot, backed by a unique active-booking index. A failure rolls back booking,
proof consumption, retry record and audit together.

Errors use the existing safe envelope: 401 AUTH_REQUIRED; 403 CSRF_REJECTED or
FORBIDDEN; 404 NOT_FOUND for unknown/foreign/wrong-operation proof; 410
CONFIRMATION_EXPIRED; 422 VALIDATION_ERROR; 409 SLOT_UNAVAILABLE, STATE_CHANGED,
PROPOSAL_CONSUMED, IDEMPOTENCY_CONFLICT or RETRY_EXPIRED; 503 BOOKING_UNAVAILABLE
for database failure. No proof/key/session secret or unnecessary patient data
is copied into errors/audit/logs. Schedule edits affecting booked source slots
and overlapping exceptions fail atomically; booked slots disappear from GET
availability. Unrelated valid maintenance remains available.
