# Phase 3 / Person 1 A1: rooms and scheduled availability

Implemented locally on `feature/room-scheduling`. API 0.4.0; migration `0004` is reserved for Person 1's room tables. Earlier phases remain implemented. No room NLP or student reservations are claimed.

## Setup and checks

```sh
make bootstrap migrate provision-demo seed-demo seed-events seed-rooms dev
make acceptance PHASE=3
make test
make contract-check
make room-query-demo
```

This machine is already migrated/seeded and running. Refresh http://localhost:8000/ to load sections **8. Room availability** and **9. Admin room scheduling**. `/docs` includes typed endpoints for direct exploration. Existing generated demo credentials remain in ignored `.local/demo-accounts.json`.

Windows PowerShell equivalents (Docker Desktop running; Make not required):

```powershell
docker compose build api
docker compose up -d db
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.db.provision
docker compose run --rm api python -m app.db.seed_rooms
docker compose up -d --wait api
docker compose exec -T api python /workspace/scripts/acceptance_phase3.py
docker compose run --rm api pytest -q
```

Python and `/workspace` paths are inside the Linux container. Windows itself has not been directly tested. Fresh setups can also run the original event/demo seeds as in README.

## Localhost walkthrough

1. Sign in as a student. Under **Room availability**, supply a future interval within 30 days, a building ID, minimum capacity and optional comma-separated facility IDs. Leave specific room ID blank to search matching rooms, or supply it for a detailed availability decision with reason codes.
2. The response separates confirmed available rooms from unknown rooms. A candidate page with no matches is not an exhaustive campus result when next_cursor exists. Use **Next candidate page** to continue. A warning always explains the schedule-based meaning.
3. Sign in as admin. Under **Admin room scheduling**, choose **Rooms** and **New scheduling template**. Edit the JSON as needed, then create it. The resulting room ID is retained for availability checks and booking templates.
4. Check that room's selected interval: the template supplies explicit opening hours and complete coverage, so it is available if no conflicts exist.
5. Choose **Bookings** and **New scheduling template**. Its room ID and interval come from the current room/availability controls. Create the booking, then check availability again: `scheduled_booking` makes it unavailable. A second overlapping booking returns 409; a booking beginning exactly at the prior end is permitted.
6. Choose **Booking exceptions** and **New scheduling template**. Use `action: cancel` and the original campus-local occurrence date. After creation the cancelled interval becomes available if all other conditions hold. To reschedule, use `action: replace` and concrete replacement_start/replacement_end timestamps instead.
7. Choose **Room closures** and create a closure over the same interval. It blocks availability even after a class cancellation. Archiving the closure releases only the closure; any active booking still blocks.
8. Reload the room record, change `coverage_complete` to false and save with the loaded version. A conflict-free interval becomes unknown, never available. Stale edits return 409. Student mutation attempts remain 403.
9. List records using the resource selector and optional room ID filter. Copy a record ID to **Load scheduling record** before editing/archiving. The editor strips response-only fields and sends the loaded version. Inspect the latest response for the authoritative record/version; exception changes also increment the parent booking version.

Rooms/bookings/closures/exceptions are archived through DELETE with `?version=N`; no hard deletion is exposed. Archived records remain available to admin detail reads, but cannot be edited or reactivated in this checkpoint. Archiving an exception can restore an original occurrence and is rejected if that restoration would cause a conflict. Cancel/archive a parent booking first when retiring an entire rule.

## API surface

All routes are under `/api/v1` and require login. Admin mutations additionally require the existing matching CSRF token and exact allowed Origin.

| Endpoint | Result |
| --- | --- |
| GET `/rooms` | Paginated active room records |
| GET `/rooms/{id}` | Active room details; archived records return 404 |
| GET `/rooms/availability` | Candidate page of confirmed availability plus unknown_rooms and coverage warnings |
| GET `/rooms/{id}/availability` | Available/unavailable/unknown with explicit reasons for one room |
| GET/POST `/admin/rooms`, `/admin/bookings`, `/admin/booking-exceptions`, `/admin/room-closures` | Admin paginated list/create |
| GET/PATCH/DELETE item paths under those admin resources | Admin detail, versioned patch and archive |

Availability parameters: required `from_at`, `to_at` (offset-bearing ISO instants), optional `building_id`, `min_capacity` (default 1), repeated `facility_ids`, bounded `limit` 1–100 (default 20) and query-bound `cursor`. The interval must be positive and entirely between server now and now + 30 days. HTTP clients cannot set the server clock. The fixed-clock CLI is for deterministic demo testing.

Lists use `limit`, `cursor`, optional `room_id` and literal `search` (code/purpose/note/reason). Ordering uses immutable ID; malformed/different-query cursors return 422. Admin lists exclude archives, but admin detail can inspect an archived record. Availability queries are limited to 60 per user per fixed minute and return 429/Retry-After when exceeded.

A single-room availability call still respects capacity/building/facility filters. Unknown reference IDs return 422. No SQL/query text is accepted from clients.

## Room and timetable semantics

- Capacity must be positive; room codes normalize to uppercase and are unique. Building/facility IDs are validated and foreign-key constrained.
- Each room stores its campus timezone, assigned at creation and immutable through this API. Opening hours use Monday=0 through Sunday=6 and local HH:MM. End 24:00 is allowed. Overlapping opening intervals are rejected; adjacent intervals may join, including across midnight. Split overnight hours over the two local dates.
- `opening_hours: null` means unknown. `[]` explicitly means closed. No missing-data condition is treated as unrestricted access.
- Coverage uses explicit instant bounds and a completeness flag. Complete coverage requires both bounds, and the entire query must fit inside them. Known bookings/closures can establish unavailability even when coverage is incomplete; absence of a booking cannot establish availability without coverage.
- Intervals are half-open [start,end): adjacent bookings do not overlap.
- A booking is a concrete first interval of at most 24 hours. Recurrence is none or weekly; weekly recurrence_until is an inclusive campus-local date, at most 366 days after the first local date. Expansion is bounded (at most 53 occurrences).
- Weekly rules preserve local wall-clock times. Ambiguous or nonexistent DST occurrences are rejected rather than silently selecting a fold. One-off offset-bearing instants are unambiguous. The initial campus timezone remains Asia/Kolkata.
- Exceptions target an original local occurrence date. An active exception is unique per rule/date. Cancel removes that occurrence; replace supplies a positive interval of at most 24 hours, within seven local dates of the original. Moved occurrences are checked even when their original date is outside the queried day.
- Effective occurrences are checked against one another and every other active booking for that room. Editing, moving, cancelling, reactivating, adding/removing exceptions and reinstating an original occurrence use the same validation.
- Schedule mutations lock their room rows in ID order; parent booking/exception edits also serialize on the booking. Conflicting concurrent requests cannot both commit. Availability reads hold shared room locks while reading schedules, so they do not combine partially updated timetable state.
- Closure intervals are concrete, positive and at most 366 days. They may overlap existing bookings and always block availability while active.
- Admin changes and their actor/resource/version/time audit entries commit together. Exception edits increment the parent's version. A failed conflict/validation rolls back the proposed edit and audit.

Unavailable reason codes include outside_opening_hours, scheduled_booking, room_closure and filter mismatches. Unknown reasons distinguish opening_hours_unavailable from incomplete_schedule_coverage. Available means only: within published hours, complete schedule coverage, and no active booking/closure. It does not establish permission to enter or physical vacancy.

## Seed and deterministic examples

`make seed-rooms` explicitly inserts a fixed synthetic semester without overwriting existing records:

- DEMO-B201: projector, 40 seats, weekday 08:00–18:00, complete coverage from 2 November 2026 through 1 January 2027. Wednesday 14:00–15:00 weekly class through 23 December; 11 November occurrence cancelled; 6 November 15:00–16:00 maintenance closure.
- DEMO-B202: projector, 30 seats, published opening hours but incomplete coverage.
- DEMO-B203: whiteboard, 80 seats and complete coverage.

`make room-query-demo` injects 4 November 2026 10:00 Asia/Kolkata and checks 15:00–16:00: the class ends exactly at 15:00, so DEMO-B201 qualifies; DEMO-B202 remains unknown. Live API checks use real time, so the same historical interval may fall outside its horizon later. These records are visibly synthetic and do not imply campus-wide coverage.

Normal startup performs no migrations, seeds or resets. The live acceptance script creates separate synthetic records, then archives them while preserving earlier records/profiles. Repeated runs retain archived audits; automatic tests remove only their uniquely named test rows. The existing Phase 0 reset command does not reset room data.

## Person 2 integration handoff

Migration 0004 belongs to this room checkpoint; coordinate subsequent revisions against this head. New code is in `db/room_models.py`, `schemas/rooms.py`, `services/room_time.py`, `services/rooms.py` and `api/rooms.py`; Alembic registers the new metadata explicitly. Existing conversation/assistant/event storage is unchanged.

`GET /reference-data` now also supplies facilities and campus_timezone, both additive fields. Room schemas and 17 fixtures are exported under contracts. Structured availability returns RoomAvailability/AvailabilityPage, separate from the future assistant room card. The assistant still accepts only the Phase 2 event baseline; room language understanding is not silently enabled.

Review the room/booking/exception/closure schemas before wiring live frontend forms. Match the backend's query-version archive convention, null-versus-empty opening hours, explicit coverage and exception action fields. Provide an unmocked browser gate against these endpoints.

Next Person 1 checkpoint after user testing: A2 / Phase 4 faculty office hours.
