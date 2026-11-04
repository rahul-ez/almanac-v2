# Phase 5 — cross-domain rule interpreter checkpoint

The assistant now accepts independent event, room and published office-hour questions. Its pure interpreter returns a typed query only after all supported constraints are understood. Missing dates/times, ambiguous faculty names, invalid intervals and unsupported constraints cannot execute a broad search. This checkpoint is the rule-based part of Phase 5; prototype trained intent classification/loading is now available through `phase-5-intent-testing.md`; final corpus evaluation remains pending.

## Run locally

From the repository root with Docker Desktop running:

```sh
make bootstrap migrate seed-demo provision-demo seed-events seed-rooms seed-faculty dev
make acceptance PHASE=5
make test contract-check
make interpret-demo
```

On Windows PowerShell, use Docker Compose directly if Make is unavailable:

```powershell
docker compose build api
docker compose up -d db
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.db.seed
docker compose run --rm api python -m app.db.provision
docker compose run --rm api python -m app.db.seed_events
docker compose run --rm api python -m app.db.seed_rooms
docker compose run --rm api python -m app.db.seed_faculty
docker compose up -d --wait api
docker compose exec -T api python /workspace/scripts/acceptance_phase5.py
docker compose run --rm api pytest -q
docker compose run --rm api python /workspace/scripts/contracts.py
docker compose run --rm api python /workspace/scripts/interpret_demo.py
```

These are container commands that avoid host Python dependencies. Native Windows execution has not been separately verified. Startup and acceptance do not reset your existing campus records; acceptance archives only records it creates.

## Test in your browser

Open [the local test bench](http://localhost:8000/), refresh if it was already open, and sign in as `student-a` using your local generated accounts file. Section 6 now has **Ask assistant**, **Interpret only** and **Retry previous request**.

| Question | Expected behavior |
| --- | --- |
| `Any ML workshops for second years this week?` | Workshop/ML/year-2 filters, campus-local week; matching event cards or an explicit empty result |
| `Rooms tomorrow from 2 to 3pm with projector` | Tomorrow 14:00–15:00 in the campus zone; projector requirement; only confirmed schedule availability returned |
| `Is B201 free tomorrow from 14:00 to 15:00?` | Resolve the synthetic room code; use its maintained bookings, closures, opening hours and coverage |
| `Professor Anita Rao office hours on Friday` | Resolve Anita; use published concrete slots and exceptions; results depend on the running date |
| `Professor Rao office hours tomorrow` | Faculty ambiguity with candidate IDs; no retrieval |
| `Find rooms` | Ask for a date and time interval; no retrieval |
| `Events and rooms tomorrow` | Unsupported compound request; no retrieval |
| `Workshops after 2pm` | Unsupported time constraint; no retrieval |

**Interpret only** calls authenticated, CSRF-protected `POST /api/v1/assistant/interpret`. It shows the meaning, original character offsets, canonical IDs, applied context and executable query or uncertainty in Latest API response. It creates no conversation or turn. It accepts standalone requests only and never accepts arbitrary query/SQL execution input.

**Ask assistant** uses `POST /api/v1/assistant/query` and persists a timestamped result snapshot. Exact retries return the exact original response, even after a schedule changes. Reusing a request ID with a changed question or a changed explicit context clear returns 409.

The `interpret-demo` CLI uses the fixed reference clock `2026-11-04T10:00:00+05:30`; the running HTTP server always uses its actual clock. Therefore CLI and browser dates can differ. No public parameter can set server time.

## Scope and next checkpoint

Supported constraints include explicit catalog entities, dates/weekday/week windows, bounded start/end times, room capacity/facilities, event price/type/year/department and faculty names/aliases. Unicode normalization preserves original input offsets. Exact names and aliases may be ambiguous; the interpreter does not choose a similar-looking faculty name. Unrecognized words are rejected conservatively, so supported natural-language coverage remains intentionally limited.

Room availability means no conflict in the maintained schedule, not physical occupancy. Unknown schedule coverage is never advertised as available. The room default for “right now” is 30 minutes and is disclosed in warnings. Cards are bounded and truncation is disclosed; chat pagination is pending.

Full clarification replies, follow-ups, history browsing/deletion and saves remain Phase 6. Until then, rephrase a complete question or use a canonical context override. The inspection endpoint rejects conversation/clarification fields rather than silently ignoring them.

Prototype TF-IDF/logistic-regression training and compatible model loading are now implemented; see [intent testing](phase-5-intent-testing.md). Next: authoritative dialogue/history/saves. One backend owner covers both original person work plans. The synthetic intent pilot under `data/annotations/prototype/` is preparation, not a reviewed student corpus or an accuracy claim.
