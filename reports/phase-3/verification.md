# Phase 3 / Person 1 A1 verification — 4 November 2026

Local branch: `feature/room-scheduling`, starting from backend checkpoint `0b02e1a`. No commit or push performed. API 0.4.0, migration 0004, room seed v1. Existing two assignment Markdown files remain local.

Executed successfully:

- Applied the additive room migration and provisioned facility reference data without resetting earlier records or accounts. The unreleased replacement CHECK was tightened on the development database to match 0004 without deleting records.
- `make test`: **42 passed**, including earlier phases, room code/reference/version validation, RBAC/CSRF, positive intervals, half-open overlap, unknown coverage/opening hours, closed schedules, inclusive recurrence end, cancellation/replacement exceptions, moved dates, closure precedence, conflict-safe exception removal, rejected reactivation, pagination/filter binding, SQL-level replacement integrity, local midnight and rejected DST ambiguity/nonexistence.
- Concurrent booking inserts and concurrent exception moves into the same slot each produce one success and one 409. Availability uses shared room locks while schedule changes lock the same room exclusively.
- Empty-database migration upgrade/metadata/downgrade/re-upgrade verification passed using a disposable temporary database; existing demo data was preserved.
- `make contract-check`: committed runtime OpenAPI and **42 fixtures** validated with Pydantic and JSON Schema, including available/unknown/no-results room responses.
- `make seed-rooms` repeated successfully without overwriting existing rows.
- `make room-query-demo`: fixed 4 November 2026 clock returns DEMO-B201 available at 15:00 after its 14:00–15:00 class; DEMO-B202 remains unknown because coverage is incomplete.
- `make acceptance PHASE=3`: live create room -> availability -> booking -> unavailable -> back-to-back allowed -> conflicting insert rejected -> exception cancellation -> available -> closure -> unavailable -> closure archive -> available -> incomplete coverage -> unknown -> stale update rejected -> synthetic cleanup all passed.
- Live Phase 0, Phase 1 and Phase 2 regression walkthroughs passed after the room migration.
- Browser: created a synthetic room (201), confirmed available (200), created its booking (201), and confirmed scheduled_booking/unavailable (200). Booking archive returned 200; recovery after removal was also verified by the live API walkthrough. Temporary browser test records are archived after verification.
- JavaScript syntax and `git diff --check` passed. CI configuration now includes Phase 3 but has not run remotely.

The existing Starlette/httpx test-client deprecation warning remains; all checks passed. Browser credential-file selection was slow, but login and subsequent room requests succeeded.

Boundaries: structured room queries only; the assistant is still event-only. No student reservation, faculty domain, full dialogue/history/save APIs, real-campus data coverage or physical-vacancy guarantee is claimed. Room search is bounded to the next 30 days, weekly rules to 366 days and replacements to seven local dates around the original occurrence. Missing hours/coverage remain unknown. Currency/event behavior and existing session/profile checks remain intact.

Manual steps and Windows Docker command equivalents are in `docs/phase-3-testing.md`. Next Person 1 checkpoint after user review: faculty office hours.
