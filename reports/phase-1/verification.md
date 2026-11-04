# Phase 1 verification — 4 November 2026

Implemented locally on `backend/phase-0-foundation`, continuing the existing checkout; nothing pushed. API/contract 0.2.0, migration 0002, synthetic reference/account seed from explicit provisioning.

Verified:

- Docker image rebuilt using pinned dependencies, including pwdlib/Argon2.
- Existing PostgreSQL upgraded from Phase 0 revision 0001 to 0002 without resetting the demo event.
- Explicit demo provisioning generated separate passwords for admin, student-a and student-b in the ignored `.local/demo-accounts.json`; directory mode 0700 and file mode 0600 verified. Re-provisioning preserved existing accounts/profiles.
- `make test`: **19 passed**. Covers both prior foundation checks and real PostgreSQL-backed Phase 1 role/ownership, input validation, CSRF/origin/session binding, cookie rotation/revocation, expiry, deactivation, live role lookup, profile persistence/clearing/atomic rejection, database-backed throttling, CORS and input-size controls.
- The migration test created a uniquely named empty database; checked upgrade to head, metadata consistency, downgrade to 0001, and re-upgrade; then removed that test database.
- `make contract-check`: runtime schema matches committed OpenAPI; twelve original assistant/error and seven identity fixtures validate with Pydantic and JSON Schema.
- `make acceptance PHASE=1`: all three demo users logged in through real HTTP; student admin access rejected, admin accepted, own profile persisted, other student unchanged, CSRF/origin/role injection rejected, original profile restored, logout and old-cookie replay rejected.
- Phase 0 live acceptance still passes after the upgrade.
- Credential file is ignored by Git and excluded from Docker build context. No credentials were printed by provisioning or acceptance scripts.

The previously recorded Starlette/httpx test-client deprecation warning remains; tests pass. CI configuration includes both checkpoints but has not run remotely.

Limits: only profiles have implemented ownership checks at this phase. Conversation/history/saved endpoints and domain CRUD are future work; `/admin/access` is a role-protected diagnostic, not a domain-management implementation. Development HTTP cookies use Secure=false; only development/test environment settings exist. No public signup, password recovery or deployment hardening is claimed.

User walkthrough: `docs/phase-1-testing.md`. Next planned checkpoint: Phase 2 events.
