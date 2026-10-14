# Proposed API and tool contracts

Status: planning sketch. No endpoint or tool is implemented. URL names from PRD are retained where possible; exact schemas, status codes and provider-specific schema support will be checked in the implementation slice. No client or model assertion substitutes for server authorization.

## Common rules

All request/response bodies are versioned Pydantic v2 models with bounded lengths and `extra=forbid` where appropriate. Stable error envelope: `{code, message, correlation_id}`; avoid disclosing private resource existence. Proposed codes: `AUTH_REQUIRED`, `FORBIDDEN`, `NOT_FOUND`, `VALIDATION_ERROR`, `CONFIRMATION_REQUIRED`, `CONFIRMATION_EXPIRED`, `STATE_CHANGED`, `SLOT_UNAVAILABLE`, `POLICY_BLOCKED`, `IDEMPOTENCY_CONFLICT`, `RATE_LIMITED`, `UPSTREAM_UNAVAILABLE`. Exact HTTP mapping remains to be reviewed.

All instants use ISO 8601 with offset; responses include clinic timezone for display. Fee is decimal amount plus ISO currency, never float. Public availability and price are snapshots, not reservations. Mutation response contains persisted appointment ID/state plus correlation ID, or a stable error. Every request is rate/body limited. Auth uses server context; role, patient, clinic and actor IDs are not accepted as authority from JSON or model args.

Approved explicit confirmation flow: `POST /appointment-proposals` or corresponding cancel/reschedule proposal endpoint returns a short-lived opaque proposal ID and exact review summary. UI displays that summary; a distinct user click submits proposal ID and an idempotency key to the appropriate mutation endpoint. The server checks actor, operation, payload digest, slot/resource state, displayed fee and policy version, expiry and one-time consumption. A changed consultation fee requires a new proposal and confirmation. AI `confirm_*` calls alone never prove a user click. A staff UI needs the same principle for appointment writes. Chat-message submission is not an appointment mutation; handoffs require authenticated patients in the MVP.

## REST surface

| Route | Actor | Contract invariant |
| --- | --- | --- |
| `GET /specialties` | Public | Active clinic catalog only |
| `GET /doctors` | Public | Filter active, specialty and the single Karachi clinic; any finer location filter needs a separate requirement |
| `GET /doctors/{id}/slots` | Public | Derived available, timezone-aware, bounded date range; never invent |
| `POST /appointment-proposals` | Patient | Validate owned actor, actual slot and current summary; no booking mutation |
| `POST /appointments` | Patient | Confirm proposal + idempotency key; atomic booking, persisted ID |
| `GET /me/appointments` | Patient | Own records only, bounded pagination |
| `POST /appointments/{id}/cancel-proposal` | Owner or authorized staff | Check ownership/scope and current policy; exact summary |
| `POST /appointments/{id}/cancel` | Owner or authorized staff | Confirm bound proposal; audit; idempotent retry |
| `POST /appointments/{id}/reschedule-proposal` | Owner or authorized staff | Validate target slot and current appointment; no state change |
| `POST /appointments/{id}/reschedule` | Owner or authorized staff | Confirm bound proposal; one transaction, old slot preserved on failure |
| `POST /chat` | Guest or authenticated | Bounded input, scoped conversation access; structured citations/actions |
| `POST /handoffs` | Authenticated patient | Persist owned queue request with consent; return actual ID/status |
| Staff routes, precise paths TBD | Scoped staff/admin | Clinic assignment and explicit permissions for schedule, documents, escalations and redacted audit |

Proposal paths are additions to the PRD draft required for server-verifiable confirmation. J5 should be minimally amended to state that handoff requires patient sign-in. Do not expose staff CRUD before its scoped service rules exist. Slot identifiers refer to persisted 30-minute capacity-one slots; cancellation and rescheduling use the approved 24-hour cutoff.

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
