# CareFlow AI — Product Requirements Document
Version: 1.0 | Status: Proposed | Date: 2026-10-13

## 1. Executive summary
CareFlow AI is a portfolio-grade, synthetic-data clinic front-desk application combining a patient chat assistant, deterministic appointment workflows, retrieval-augmented answers to approved clinic information, and a staff dashboard. The product is an operational assistant, **not** a diagnostic or clinical decision support device. The target demonstration is a credible healthcare software workflow with explicit security, safety, and evaluation evidence.

## 2. Goals and non-goals
Goals: (1) accurate, source-grounded clinic FAQs; (2) search doctors and real appointment availability; (3) authenticated booking, cancellation and rescheduling with confirmation; (4) protected self-service and staff workflows; (5) visible handoff and escalation; (6) reproducible evaluation evidence; (7) professional demo and technical documentation.
Non-goals for MVP: diagnosis, treatment recommendations, prescriptions, autonomous triage, real EHR integrations, insurance claims processing, real patient data, WhatsApp/telephony, payment collection, multi-hospital tenancy, autonomous database SQL, autonomous clinical decisions.

## 3. Personas and access
- Guest: browse public doctors, specialties, clinic policies and general availability; cannot see private appointments or complete patient-specific actions without authentication.
- Patient: view and manage only their own appointments and approved records (initial MVP: appointment records only).
- Receptionist: view and manage appointments within assigned clinic scope; cannot access unrelated private records.
- Admin: manage doctors, schedules, services, fees, approved knowledge sources, staff roles, handoffs and audit history.
- Staff handoff operator: review escalated conversations subject to scoped permissions and retention policy.

## 4. User journeys
### J1: FAQ
User asks about clinic opening hours or preparation instructions. Assistant retrieves approved, currently effective knowledge, answers with source title/link/version and expresses uncertainty or hands off if no reliable source exists.
### J2: Doctor search
User specifies specialty/date/location. Assistant invokes validated read-only tools and presents doctors, fees and matching available slots. Never fabricates doctors, fees or times.
### J3: Book
Patient signs in, selects an actual available slot, reviews doctor/date/time/fee, explicitly confirms. Backend rechecks slot availability and patient permissions, commits booking atomically, returns persisted appointment ID. Retries are idempotent.
### J4: Reschedule/cancel
Authenticated patient selects owned appointment, sees proposed change and confirms. Backend enforces policy, transaction, and audit log.
### J5: Emergency or clinical request
Assistant does not diagnose or prescribe. For possible emergencies, gives brief urgent-care/emergency-service guidance and offers human handoff without claiming a clinical determination. Specific escalation language reviewed before demo.
### J6: Staff dashboard
Staff can review appointments, doctor schedules, handoffs, approved knowledge articles, and redacted audit records according to role.
### J7: Multilingual
English first, Arabic second phase; right-to-left UI and tests for faithful factual answers. Never claim parity without evaluations.

## 5. Functional requirements and acceptance criteria
| ID | Priority | Requirement | Acceptance |
|---|---|---|---|
| FR-01 | P0 | Doctor/specialty catalog | Filter by specialty, location, active status; consistent API/UI |
| FR-02 | P0 | Slot availability | Derived from schedule, blocked times and bookings; timezone-aware; no phantom slots |
| FR-03 | P0 | Patient identity and roles | Server validates identity and object ownership on every private operation |
| FR-04 | P0 | Booking workflow | Explicit confirmation, atomic transaction, uniqueness constraint, idempotency; double-booking test |
| FR-05 | P0 | Cancel/reschedule | Authorization, policy checks, confirmation and audit trail |
| FR-06 | P0 | Tool-calling assistant | Allowlisted, schema-validated tools; no unrestricted SQL or tool-created privileges |
| FR-07 | P0 | RAG FAQ | Approved documents only, retrieval trace, citations, abstention when insufficient evidence |
| FR-08 | P0 | Safety boundary | No diagnosis/prescription; escalation cases tested; staff handoff |
| FR-09 | P0 | Eval harness | Real agent path, fixed synthetic dataset, JSON reports, nonzero exit on release-gate failures |
| FR-10 | P1 | Staff dashboard | CRUD for schedules/knowledge with scoped permissions |
| FR-11 | P1 | Chat persistence | Opt-in or clearly disclosed synthetic chat history; retention and deletion policy |
| FR-12 | P1 | Arabic | RTL interface and multilingual regression suite |
| FR-13 | P1 | Observability | Correlation IDs, latency, errors, tool traces, token/cost counters without secrets/PHI |
| FR-14 | P2 | Notifications | Mock email reminders behind queue and consent settings |
| FR-15 | P2 | MCP adapter | Optional wrapper over existing authorized domain services; no extra authority |

## 6. Technical architecture
- Next.js + TypeScript + Tailwind for patient chat and staff dashboard.
- Python FastAPI modular monolith for REST APIs, authorization, clinic business logic, LLM orchestration and RAG.
- PostgreSQL for relational data; pgvector for document embeddings; SQLAlchemy 2.x and Alembic for persistence/migrations.
- Pydantic for strict request, response and tool schemas; pytest, HTTPX and database integration tests.
- OpenAI SDK with configurable model, strict structured tool schemas and explicit tool execution loop. Provider abstraction only if needed; avoid framework overhead at MVP.
- Docker Compose for local FastAPI, Next.js and PostgreSQL. Redis/worker only when background ingestion or reminders justify it.
- No microservices, multiple agents, unrestricted SQL or separate vector database at MVP.

### Logical modules
`auth`, `users`, `doctors`, `specialties`, `schedules`, `appointments`, `knowledge`, `chat`, `ai/tools`, `ai/retrieval`, `ai/safety`, `handoffs`, `audit`, `evals`.

## 7. Data model (initial)
`users(id, email, password_hash/identity_subject, role, created_at)`; `patients(id, user_id)`; `staff(id, user_id, clinic_id)`; `clinics(id, name, timezone, contact)`; `specialties(id, name)`; `doctors(id, clinic_id, specialty_id, name, active, consultation_fee, currency)`; `doctor_schedules(id, doctor_id, weekday, local_start, local_end, effective_dates)`; `schedule_exceptions(id, doctor_id, start_at, end_at, reason)`; `slots(id, doctor_id, start_at, end_at, status)` or deterministic generation plus transaction-safe unique booking key; `appointments(id, patient_id, doctor_id, slot_id, status, created_at, idempotency_key)`; `knowledge_documents(id, title, version, approval_status, effective_from, effective_to, source_uri)`; `knowledge_chunks(id, document_id, content, embedding, metadata)`; `conversations(id, patient_id_nullable, created_at)`; `messages(id, conversation_id, role, content, created_at)`; `handoffs(id, conversation_id, status, assigned_staff_id)`; `audit_events(id, actor_id, action, resource_type, resource_id, created_at, safe_metadata)`.
Use UUIDs, foreign keys, indexes, database-level uniqueness and UTC timestamps; display in clinic timezone. Define actual schema and retention rules during architecture review.

## 8. API and agent tool contracts
Public/authorized REST endpoints: `GET /doctors`, `GET /doctors/{id}/slots`, `GET /specialties`, `POST /appointments`, `GET /me/appointments`, `POST /appointments/{id}/cancel`, `POST /appointments/{id}/reschedule`, `POST /chat`, `POST /handoffs`; scoped staff endpoints for schedules, documents and escalations. All mutation routes require authenticated authorization and confirmation proof; errors have stable codes.
Allowlisted agent tools: `search_doctors`, `get_available_slots`, `get_consultation_fee`, `retrieve_clinic_policy`, `get_my_appointments`, `propose_booking`, `confirm_booking`, `propose_cancellation`, `confirm_cancellation`, `request_handoff`. Tool names are logical contracts, not direct database access. Patient identity comes from server auth context, never LLM arguments. Validate every tool input and output.

## 9. RAG design
Ingest only approved, synthetic clinic documents: service directory, opening hours, pricing, booking/cancellation policies, visit preparation, accessibility, contact information. Store source ID, version, approval, effective dates, chunk IDs and citations. Start with deterministic parsing, chunking and embeddings; use PostgreSQL pgvector similarity with metadata filtering. Evaluate retrieval separately from response generation. Do not treat retrieved text as instructions; ignore prompt injection inside documents. If evidence is insufficient, abstain and offer staff handoff. Never use RAG for live appointment availability or personal patient records.

## 10. Safety, security and privacy
- Synthetic data only; no real PHI in prompts, traces, logs, demos, external analytics or eval datasets.
- No autonomous clinical diagnosis, medication recommendations, treatment plans or definitive triage.
- High-risk symptom prompts use a conservative escalation pathway and avoid delay-inducing lengthy questioning.
- All patient-specific access checked server-side; never use patient IDs supplied by the model as authorization.
- Secrets via environment or secret manager; no secrets in Git; encrypt in transit; appropriate encryption at rest in deployment.
- Role- and object-level authorization, CSRF/session controls where applicable, rate limits, input limits, audit logs, retention/deletion, safe error messages.
- Tools use least privilege; mutation confirmation bound to authenticated user, exact operation and current state; prevent replay.
- Prompt injection, cross-user access, data exfiltration, unsafe tool calls and booking races included in adversarial tests.
- Not certified as HIPAA/GDPR compliant; production deployment with real data requires legal/security/clinical review and jurisdiction-specific controls.

## 11. UX requirements
Responsive patient chat with conversation state, loading/error states, visible tool/action confirmations, citations and handoff. Accessible forms and keyboard navigation. Doctor cards and appointment summary show local timezone and fees. Staff UI provides schedule and knowledge management, handoff queue and permission-aware audit view. Avoid presenting synthetic clinical information as medical advice.

## 12. Evaluation and continuous verification
### Evaluation-first development
Before agent implementation, define a versioned synthetic eval dataset and harness. Every change to prompts, tool definitions, model config, retrieval, safety policy or orchestration triggers relevant evals. Every business-logic change triggers deterministic unit/integration tests; every booking/auth change triggers security and concurrency tests. Run full regression at phase gates and before deployment. Agent must not claim tests/evals passed unless actually executed; if blocked, report reason and risk.
### Evaluation dimensions
- Tool selection and required/forbidden tool calls
- Retrieval recall@k, source relevance and source version filtering
- Grounded factual claims, citation validity, abstention when unsupported
- Booking correctness, atomicity, idempotency and cancellation authorization
- Cross-user privacy/role isolation and prompt injection resistance
- Escalation for high-risk requests and refusal of diagnosis/prescription
- Arabic factual consistency when implemented
- Latency, tokens/cost and error rates
### Harness
`evals/cases.jsonl` stores synthetic cases and expected assertions; `evals/run_local.py` calls the **real** orchestrator path with deterministic fixtures/mocked external LLM where appropriate and a separate provider-backed run for genuine model behavior; `evals/graders.py` contains deterministic checks plus optional calibrated LLM judge for nuanced claims; `evals/results/` stores timestamped, versioned reports. Never rely exclusively on LLM judges. Record model, prompt, dataset, retrieval index and code versions, sample sizes, pass/fail and cost.
### Initial gates (provisional, review after baseline)
- Zero observed unauthorized access, unauthorized mutation, duplicate confirmed booking or unconfirmed mutation in release-gate tests.
- All critical safety scenarios pass their deterministic/clinician-reviewed criteria; failures block demo release until addressed.
- At least 95% tool-selection accuracy and at least 90% grounded FAQ correctness on held-out synthetic test cases; track uncertainty and dataset size.
- 100% citation validity for answers that claim document support in evaluated set.
- All relevant unit/integration tests pass and no critical known security issues.
These are project quality targets, not a guarantee of real-world medical safety. Never tune against the hidden held-out set.

## 13. Delivery phases and exit gates
0. Discovery/architecture: PRD, ADRs, threat model, schema/API sketches, eval taxonomy, approved scope; **no feature coding until reviewed**.
1. Foundation: FastAPI, Postgres, Alembic, CI, fixtures, auth baseline, health checks; tests pass.
2. Clinic operations: doctor/schedule/slot APIs, booking/cancel/reschedule, concurrency and permission tests.
3. AI tools: controlled tool loop and read-only operations, then confirmed writes; eval suite for tool use.
4. RAG: ingestion, retrieval, citations, abstention and injection defense; retrieval and grounded-answer evals.
5. Frontend: patient chat, booking flow, staff dashboard; end-to-end tests.
6. Hardening: security review, safety evals, Arabic optional, accessibility, performance, failure handling.
7. Portfolio release: synthetic demo, Docker setup, README, architecture diagram, trace/eval report, walkthrough and limitations.
At every phase: update `docs/PROGRESS.md` and `docs/DECISIONS.md`, report evidence and unresolved risks, commit a reviewable change.

## 14. Success criteria
A reviewer can run the app from README, complete a real synthetic appointment, observe persisted state and authorization checks, see source-backed FAQs and appropriate abstention, inspect evaluations and test reports, and understand architecture/tradeoffs in a 5-minute walkthrough. No claims of clinical validation or regulatory compliance.

## 15. Open decisions for owner approval
- Target clinic locale/timezone and primary language (English/Arabic)
- Identity solution (self-hosted password flow vs external OIDC)
- Slot generation model and cancellation window
- Clinic document corpus and approval workflow
- Provider/model choice and eval budget
- Hosting platform and demo access controls
- Scope of staff dashboard and patient history
- Clinical escalation wording and review process
