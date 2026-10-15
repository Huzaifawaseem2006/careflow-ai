# 05: Sign in and end a synthetic patient session

**What to build:** A synthetic patient can sign in, inspect their own server-resolved identity, and sign out. Private requests without a valid session fail safely; staff accounts cannot self-register.

**Blocked by:** 04 — Reset the fictional clinic fixtures.

**Status:** needs-info

**Approval gate:** Explicit owner approval to begin Phase 1 implementation, plus the patient credential and recovery decision D02.

- [ ] Session cookies use the approved secure, HttpOnly server-managed design and appropriate CSRF protection.
- [ ] Identity comes from server session state, never a caller-supplied patient or role field.
- [ ] HTTP tests cover sign-in, sign-out, missing/invalid session, CSRF rejection, and staff-registration denial.
- [ ] The chosen credential lifecycle and any demo-only limitation are documented before implementation.
