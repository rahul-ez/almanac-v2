# Backend contracts — API 0.3.0

`openapi.json` describes implemented health/demo, session/profile/reference, event CRUD/search and a narrow event-only assistant. Rooms, faculty and full conversations are not implemented.

`assistant-response.schema.json` describes future assistant responses; `error.schema.json` is the shared error envelope. The twelve original fixtures in `fixtures/` are synthetic future assistant/error examples, not NLP quality evidence. Phase 1 adds seven identity schemas and matching examples in `identity-fixtures/`. The example password/token values in these fixtures are placeholders and never authenticate.

Run `make contract-check` to verify schema drift, Pydantic invariants and JSON Schema formats. Run `make contract-export` after intentional schema changes, and share the diff with the frontend owner.

Implemented CSRF wire contract: `GET /api/v1/auth/csrf` returns `{csrf_token, expires_at}` and establishes or reuses an HTTP-only server-side session cookie, `almanac_session`, path `/api/v1`. Mutations, including login/logout, send `X-CSRF-Token` plus an exact allowed `Origin`. Login rotates the cookie and token and returns `{user, csrf_token}`; clients must use the new token. `GET /auth/me` returns `{id, username, role, session_expires_at}`. Identity and role come exclusively from the server. All API responses are marked no-store. Use credentialed requests (`credentials: "include"`) in a separate frontend origin.

Profile PATCH accepts only department_id, year, section and interests. Omitted fields retain their values; nullable fields accept explicit null; an empty interests list clears it. There is no client-settable owner or role. Reference IDs come from `GET /reference-data`. Profile, reference and admin-access calls require login; profiles require a student role.

Cookie/CSRF walkthrough and local development origin settings: `docs/phase-1-testing.md`.

Phase 2 adds six event/request schemas and examples in `event-fixtures/`. Event response cards now have explicit eligibility rule mode (`unknown`, `unrestricted`, `restricted`) and registration_status. Re-exported assistant fixtures include that rule mode; frontend consumers must review this contract change. Event list filters and admin version semantics are documented in `docs/phase-2-testing.md`.
