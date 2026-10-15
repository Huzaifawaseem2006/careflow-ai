# 04: Reset the fictional clinic fixtures

**What to build:** A reviewer can reproducibly load and reset the approved fictional Karachi clinic and synthetic demo identities, with the clinic timezone and PKR settings preserved.

**Blocked by:** 03 — Start the local database and apply migrations.

**Status:** needs-info

**Approval gate:** Explicit owner approval to begin Phase 1 implementation.

- [ ] Fixture creation and reset are deterministic and safe for the local demo database.
- [ ] Tests verify one fictional Karachi clinic, `Asia/Karachi`, PKR, and synthetic identities.
- [ ] No real patient data or credentials are committed or logged.
- [ ] Fixture commands and PostgreSQL integration results are recorded.
