# Phase 5 — patient and staff UI

Entry: API contracts and Phase 4 gates pass. Build Next.js/TypeScript/Tailwind in small slices: public catalog; patient auth and booking review/confirmation; chat with citations and handoff; scoped staff appointment/handoff queue; then P1 schedule/knowledge CRUD if approved under D09.

Show clinic timezone, fee and exact proposed action before a user confirms. Handle expired proposals, booking races, retries, provider failures and handoff status visibly. Session/CSRF controls belong at the backend boundary. Accessible forms, keyboard use and responsive layout are acceptance criteria.

Run frontend lint/type/unit checks and Playwright flows for positive and negative auth/booking cases. Use real backend/DB in end-to-end tests where practical; mark mocks. Phase exit runs the full applicable backend, agent and UI suite. Do not claim a handoff if no queue item persists.
