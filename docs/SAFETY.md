# Safety and threat model

Status: proposed controls, unimplemented and unvalidated. This is an operational assistant using synthetic data. No clinical or regulatory certification is claimed.

## Trust boundaries and assets

The browser, chat text, retrieved documents and model output are untrusted. Authenticated server context, approved knowledge metadata and committed database state are authoritative within their limited scopes. Protect account/session credentials, appointment ownership, capacity, approved source integrity, staff handoffs, audit records, API keys and synthetic conversation content. Synthetic data can still expose access-control flaws; never invite real patient data into the demo.

| Threat / failure | Proposed control | Verification gate |
| --- | --- | --- |
| Cross-user appointments or conversation access | Server-derived actor and scoped service query, deny by default, non-enumerating error | Patient A/B and staff clinic-isolation tests across REST and tools |
| Model asks for privileged tool or for another patient | Per-request allowlist and service authorization; no caller-selected patient ID | Adversarial tool calls; zero unauthorized reads/mutations |
| Forged/replayed confirmation | Opaque expiring server proposal bound to actor, exact action and resource version; consumed atomically | Confirmation bypass, replay, stale fee/policy and payload-change tests |
| Double booking / failed reschedule | PostgreSQL unique active-slot invariant plus transaction and lock discipline | Separate-connection race tests; old appointment survives failure |
| Prompt injection in clinic source or chat | Retrieved text treated as data; strict tool boundary; final claims grounded to approved source | Injection cases that request secrets, tools or altered policy |
| Fabricated policy, price, clinician or slot | Cite effective approved source for policy; read price/slots from service; abstain on insufficient evidence | Missing/expired/conflicting source, phantom-slot and fee tests |
| Unsafe symptom or medication request | Short non-diagnostic escalation, human handoff; exact wording reviewed for demo locale | Deterministic safety assertions plus human wording review |
| Data leakage in traces or analytics | Allowlisted safe metadata, redaction, no full prompt/secret/credential logging by default | Log/trace inspection tests and manual audit |
| Session abuse, CSRF, brute force | Same-origin session controls, Origin/CSRF checks, rate and body limits | Negative HTTP tests and deployment review |
| Inappropriate staff handoff access | Clinic assignment and explicit handoff permission; limited retention | Staff role/scope and expired-access tests |

## Operating behavior

No diagnosis, prescription, treatment plan or definitive triage. The assistant should briefly direct a user describing a possible emergency to local emergency services or urgent in-person care, without judging severity or asking lengthy follow-ups that delay care. Location-specific numbers and exact wording are owner/reviewer decisions. Handoff is offered honestly: return a persisted queue item only if the service actually accepted it.

Knowledge preparation text may include sensitive health context. Publish only reviewed clinic-authored instructions, with explicit version/effective status; avoid making independent medical recommendations. When a source is missing, expired, conflicting or inaccessible, abstain and offer a human route. A citation is not a safety guarantee; verify that the cited source actually supports the claim.

## Privacy and retention

Development fixtures, model prompts, embeddings, logs, evals and demos use synthetic people and clinics. Disclose conversation persistence before opt-in. The PRD has no concrete retention periods or deletion exceptions; decide these before storing chat or handoff content. Staff views and audit events should redact unnecessary content. Limit provider payload to the minimum synthetic context. Prevent raw request bodies, credentials and tokens from entering correlation traces. Deletion needs to cover messages and derived embeddings where applicable, with an explicit audit exception policy.

## Release blocks and residual risk

Any observed unauthorized access or mutation, duplicate confirmed booking, unconfirmed state change, or critical safety-case failure blocks demo/release. Passing a finite synthetic suite shows only the evaluated behavior, not clinical safety or compliance. Real patient data and public production use require separate legal, security and clinical review. Review external dependencies, TLS, backups, key storage, monitoring and incident response before hosting.
