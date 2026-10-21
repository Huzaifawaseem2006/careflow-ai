# Safety and threat model

Status: threat-model controls are implemented and technically verified only where
the ticket evidence in PROGRESS records them; later-phase controls remain planned.
D01 wording is owner-approved, implemented and technically tested; D11 human
clinical wording sign-off is pending.
This is an operational assistant using synthetic data. No clinical or regulatory
certification is claimed.

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

See the current [conversation lifecycle](CONVERSATIONS.md) for approved and
implemented D10 mechanics; the original planning paragraph below is historical.

Development fixtures, model prompts, embeddings, logs, evals and demos use synthetic people and one fictional Karachi clinic. Disclose conversation persistence before opt-in. The owner proposed 30-day retention for synthetic demo conversations; deletion timing, handoff and audit exceptions still need a concrete policy before storing chat content. Staff views and audit events should redact unnecessary content. Limit provider payload to the minimum synthetic context. Prevent raw request bodies, credentials and tokens from entering correlation traces. Deletion needs to cover messages and derived embeddings where applicable, with an explicit audit exception policy.

## Phase 3 wording review — 2026-10-20

**D01: owner-approved, implemented and technically tested. D11: pending.** The owner
approved preserving the existing number-free escalation sentence and improving the
full deterministic fallback, with the exact capability-based closing sentences below.
No external clinical reviewer has been nominated or completed a review. Technical
tests and this engineering review supply no human clinical approval.

The current complete rendered fallback is `DISCLOSURE + ABSTENTION` in
[`chat.py`](../backend/careflow/chat.py). The old response put operational
instructions before emergency guidance and repeated selection prompts. The
owner-approved improvement is now implemented as:

> Synthetic demo: fictional clinic data only. For clinical assistance, contact a qualified clinician; for a possible emergency, contact local emergency services or seek urgent in-person care. I cannot diagnose, prescribe or assess urgency. I can help with clinic catalog and fees, availability, owned appointments in signed-in conversations, and booking, cancellation or rescheduling reviews. Chat cannot confirm appointments. This chat has no verified clinic-policy source. This chat cannot queue a staff handoff.

The implementation retains the accepted escalation sentence unchanged, moves it
immediately after disclosure, removes repeated selection prompts and removes
internal secret/instruction language from the fallback. Current chat has no policy
retrieval or handoff service/tool; the approved closing sentences state those
capabilities, without asserting the status of an earlier/external handoff. The
change adds no routing, clinical capability, telephone number, tool, prompt,
grader or threshold change. The shared fallback also serves nonclinical abstention;
this is not a new emergency classifier or a guarantee that this text appears on
every clinical input. Error responses remain separate; historical turn replay
retains its immutable original wording. See PROGRESS for technical evidence.

Before D11 can close, retain the following actual evidence:

1. Owner nomination of an appropriate named reviewer, with their stated role and
   relevant qualifications/experience; none is supplied or inferred here.
2. The full rendered response and code revision/text version they reviewed,
   covering disclosure, escalation, surrounding operational prompts, refusal of
   diagnosis/prescribing/urgency assessment and honest handoff limitations.
3. Review of the clinical-request and possible-emergency examples for the English
   Karachi synthetic demo: understandable, brief guidance, no severity judgment,
   no delaying questions/booking instructions and no invented contact details.
4. Dated reviewer findings, required amendments and explicit approval of the final
   wording, plus owner acceptance. Any changes require affected technical checks
   and review of the resulting full response, without weakening frozen evals.

This closes only the defined wording review when completed. It cannot establish
project-wide clinical validation, regulatory compliance or real-patient readiness.
Existing contracts treat D01/D11 as safety/release gates separate from internal
synthetic technical evaluation. A separately authorized live run may gather
technical evidence while D11 is pending, but cannot close Phase 3 or authorize
demo/release. No paid run is currently authorized.

## Release blocks and residual risk

Any observed unauthorized access or mutation, duplicate confirmed booking, unconfirmed state change, or critical safety-case failure blocks demo/release. Passing a finite synthetic suite shows only the evaluated behavior, not clinical safety or compliance. Real patient data and public production use require separate legal, security and clinical review. Review external dependencies, TLS, backups, key storage, monitoring and incident response before hosting.
