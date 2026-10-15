# 07: Demonstrate the Phase 1 regression gate

**What to build:** A reviewer can run the complete applicable foundation checks from a fresh checkout and inspect an evidence-based Phase 1 report before later phases begin.

**Blocked by:** 02 — Run foundation checks in CI; 03 — Start the local database and apply migrations; 04 — Reset the fictional clinic fixtures; 05 — Sign in and end a synthetic patient session; 06 — Run the versioned synthetic eval set offline.

**Status:** needs-info

**Approval gate:** Explicit owner approval to begin Phase 1 implementation and completion of all blocking tickets.

- [ ] Formatting, lint, type, unit, HTTP, migration, PostgreSQL integration, session-security, and offline eval checks run as applicable.
- [ ] The report records exact commands, revision, passed/failed/skipped/blocked results, and unresolved risks.
- [ ] Critical authorization, privacy, or safety failures block the phase gate; no live model quality claim is made from offline results.
- [ ] Progress, decisions, and the Phase 1 plan reflect verified results and the next small task.
