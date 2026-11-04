# Phase 4 / Person 1 A2 verification — 4 November 2026

Local continuation on `feature/room-scheduling`; no commit or push performed. API 0.5.0, additive migration 0005 on 0004, synthetic faculty seed v1. Earlier room work and the two separate assignment files remain local.

Verified:

- Applied migration 0005 without resetting existing event/room/account/profile data. Faculty metadata is explicitly registered for Alembic.
- `make test`: **52 passed**. Existing phases plus faculty roles/CSRF, reference and email/source/date validation, versions/archive behavior, exact title/case/whitespace alias normalization, cross-faculty alias ambiguity, duplicate-target rejection, publication completeness, actual-slot overlap boundaries, invalid merged-edit rollback, cancellation/replacement, moved dates outside the original query day, conflict-safe restoration, orphan prevention, concurrent rule conflicts, cursor binding/horizon, local midnight, DST rejection and database replacement integrity.
- Empty-database upgrade, metadata check, downgrade/re-upgrade tests passed using the disposable migration database.
- `make contract-check`: runtime OpenAPI and **61 fixtures** pass Pydantic and JSON Schema checks, including 19 new faculty record/publication/outcome fixtures.
- Faculty seed applied twice without overwriting existing records.
- `make faculty-query-demo`: at the fixed 4 November 2026 clock, Professor Rao resolves to two candidates and Anita's canonical ID returns the 6 November 13:00–14:00 campus-time slot.
- `make acceptance PHASE=4`: live HTTP faculty creation, missing-publication versus no-slots distinction, ambiguous shared aliases, denied student publication, weekly rule, concrete slot retrieval, dated cancellation, moved replacement, stale parent version rejection and archive cleanup all passed.
- Live acceptance Phases 0, 1, 2 and 3 passed afterward, preserving earlier behavior and data.
- Browser: student login succeeded; Rao returned two candidates; selecting Anita and querying 6 November returned one published slot with complete coverage and source metadata. Browser console reported no JavaScript errors. JavaScript syntax and `git diff --check` passed.
- CI configuration includes Phase 4 but has not run remotely. The existing Starlette/httpx test-client deprecation warning remains; all checks passed.

Limits: these are structured faculty services and a direct candidate resolver, not faculty natural-language understanding or stored dialogue clarification. The language assistant remains event-only. Publication completeness is explicit over local dates; no teaching-timetable inference is made. Rules are bounded to 366 days, live queries to the next 30 days, and replacements to seven local dates around the original. Only faculty aliases are supported at the generic aliases route in this checkpoint.

Manual instructions and Windows Docker equivalents: `docs/phase-4-testing.md`. Next Person 1 work is cross-domain entity/time extraction, resolution and validated meaning composition, coordinated with Person 2's intent/dialogue work.
