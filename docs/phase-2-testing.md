# Phase 2: events and the first language-to-data slice

Status: implemented locally. API/contract 0.3.0, migration 0003, baseline model `events-rules-v1`. This is a standalone backend checkpoint; no product frontend is required.

## Start and test

```sh
make bootstrap migrate provision-demo seed-demo seed-events contract-check dev
make acceptance PHASE=0
make acceptance PHASE=1
make acceptance PHASE=2
make test
make query-demo
make parse-demo
```

Open http://localhost:8000/ and refresh the existing page to load the new controls. Swagger remains at `/docs`. On this machine the migration/seed have already run and the API is running.

`make seed-events` inserts three fixed November 2026 synthetic campus events without overwriting existing values: a free ML workshop restricted to year 2, an AI seminar with unknown eligibility/price, and an unrestricted paid web lecture with an earlier registration deadline. Run provisioning first so reference IDs exist. Original Phase 0 demo records and endpoint remain independent. Startup never seeds or resets data. Phase 0 `reset-demo` resets only its original fixture, not campus events or user profiles.

## Browser walkthrough

1. Sign in as admin using the existing demo account loader.
2. Scroll to **Admin event management**. Create a published workshop with a unique title, future start/end, topic `machine_learning`, venue, source and price 0. Set eligibility to **Explicitly open to all**, or choose **Restricted** and supply allowed years/departments. Unknown eligibility is a separate option.
3. The form retains the created record ID and version. Edit a field and save; version increments. **Load admin events** shows current records and load buttons. You can also load an event by its ID.
4. Switch to student-a. Under **Search events**, search its unique title. Compare price 0 with blank (unknown) and try **Only confirmed eligible events**.
5. Under **Ask an event question**, ask “free ML workshops tomorrow” if you created the event for tomorrow. Inspect the meaning, provenance, cards, time range, registration status and source in Latest API response.
6. **Retry previous request** must return the same turn/response. Each new question uses a new request ID.
7. Switch back to admin; load the record and cancel it. Student searches and new assistant questions exclude it; direct event details report cancellation. Retrying the earlier request returns its original timestamped snapshot.
8. Archive the record to remove it from active management/search. Archives retain the record and audit entries. Stale edits/archive versions return 409 rather than overwriting a newer change.

The live acceptance script performs the same create/search/edit/cancel/archive flow with real HTTP and PostgreSQL, checks student denial and stale edits, then archives its synthetic event. It leaves existing demo records and student profile values unchanged. Archived acceptance records/audits and private test conversations remain until an explicit future cleanup; tests do not drop your database.

## Implemented API

| Endpoint | Behavior |
| --- | --- |
| GET `/api/v1/events` | Authenticated published-event list with bounded filters and cursor pagination |
| GET `/api/v1/events/{id}` | Published/cancelled details; draft/archived records are inaccessible |
| GET/POST `/api/v1/admin/events` | Admin list/create; create returns 201 |
| GET/PATCH/DELETE `/api/v1/admin/events/{id}` | Admin detail/versioned edit/archive; DELETE requires `?version=N` |
| POST `/api/v1/assistant/query` | Student-only independent event questions, CSRF protected, per-user rate limit |

All mutations keep existing CSRF/origin/session protections. Event fields include title/description/type/topic, venue, UTC-offset-bearing times, nullable price, INR currency, nullable deadline, explicit eligibility rules, lifecycle status and source/update metadata. Event types: workshop, seminar, hackathon, lecture. Topic/department IDs must exist in reference data. Source links accept HTTP(S), reject credentials and are not fetched by the backend.

PATCH requires the loaded version; fields omitted stay unchanged. Nullable price/deadline/source URL may be cleared. Validation checks the whole merged record, so changing an end/start/deadline cannot create an invalid interval. Creation and mutations write an audit actor/action/version/time in the same transaction. DELETE archives; archived records cannot be edited in this phase.

## Search and semantic rules

- Dates use half-open overlap: `event.start < query.end AND event.end > query.start`.
- Supply both `from_at` and `to_at`, or neither. Explicit windows are positive and at most 366 days. Without dates, return not-ended events up to 366 days from the current UTC calendar day. Use explicit offsets/dates for campus-local windows.
- Other filters: `event_type`, `topic_id`, exact `venue`, literal title substring `q`, `max_cost_minor`, `eligible_only`, `student_year`, `department_id`, `limit` (1–100, default 20), and `cursor`.
- Null price never matches a maximum-price filter. Zero means free. The first version supports INR only.
- Unrestricted eligibility requires an explicit rule. Unknown rules/incomplete profiles remain unknown. A known violated restriction is ineligible even if another context field is missing. Eligible-only searches exclude unknowns with a warning. A baseline question with no eligible results but unknown candidates returns `information_unavailable`.
- Profile context supplies year/department for student reads; search overrides can replace them for that request. Explicit eligibility uses published department/year restrictions, never interests. Interests do not establish eligibility; personalized interest ranking is deferred.
- Fixed filter relevance and eligibility selection are followed by chronological order and ID tie-breaker. Cursors bind the query/limits/effective context and use this order; mismatched or malformed cursors return 422. Lists reflect current data, not a frozen pagination snapshot.
- Registration closure is distinct from event cancellation/end. A published future event can have registration closed. Missing deadline is unknown while active; a cancelled/ended event is closed.

## Deliberately limited event baseline

Supported patterns combine one event type, optional ML/AI/web-development topic, optional `free`, optional year (first–fourth / 1st–4th / `year 2`), optional `aiml`/`cse`, and one date expression: today, tomorrow, this week, next week, weekday or YYYY-MM-DD. An omitted date means the next 30 days. Weekdays mean the next occurrence within seven days (including today); weeks run Monday 00:00 to next Monday 00:00 in campus time.

Examples: “Any ML workshops for second years this week?”, “free AI seminars tomorrow”, “events on 2026-11-06”. New domain requests, unknown leftover constraints, compound/contradictory filters and invalid dates return HTTP 200 `unsupported` with no query execution. This parser is a small strict rule baseline, not the trained three-domain pipeline or academic evaluation.

Precedence is explicit question > request context override > profile > documented default. `context_overrides` supports year/department (explicit null clears profile context for that request). No dialogue context is carried yet. Existing owned conversation IDs receive an explicit unsupported follow-up response; foreign conversation IDs return 404. Clarification replies are not implemented.

A per-user request key and normalized payload hash protect retries. Database advisory locking plus a uniqueness constraint prevent concurrent duplicates, including different sessions for the same user. Conversation, question, response snapshot and model version commit atomically. A reused ID/different payload is 409; same ID/payload returns the previous body even after records change. Its body retains the original request_id while X-Request-ID identifies the current HTTP attempt. Assistant requests are rate limited to 30/user/fixed minute, including retries; honor Retry-After.

Question text is not logged. Minimal conversations/turns are stored privately now to honor retry semantics; history/saved/deletion APIs and full dialogue behavior arrive in Phase 6. Cards include sources, answer and record timestamps, eligibility and registration state. Chat returns at most 20 cards with a truncation warning; chat next_cursor stays null.

## Verification scope and next step

Automated tests cover earlier phases plus CRUD/permissions/CSRF, audit records, invalid atomic updates, SQL/Python eligibility parity, boundary overlap, nullable cost, deadlines/drafts, pagination/query binding, literal injection-like inputs, concurrent stale edits and concurrent duplicate turns, ownership and snapshot freshness. Migration tests check empty upgrades, schema metadata and downgrade/upgrade without touching existing data.

`make query-demo` exercises typed query services directly on the fixed campus seed and 4 November 2026 clock. `make parse-demo` prints the rule interpretation/provenance at that clock. Live HTTP obtains its own current clock; clients cannot set it.

Next planned checkpoint: Phase 3 room scheduling. Advanced event types, interest ranking, model training, rooms/faculty understanding and full conversations remain later work.
