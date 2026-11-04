# Phase 4 / Person 1 A2: faculty and published office hours

Implemented locally; API 0.5.0, migration `0005_faculty` on top of `0004_rooms`. Faculty interpretation is structured at this checkpoint; the language assistant still supports the Phase 2 event baseline only.

## Start and verify

```sh
make bootstrap migrate provision-demo seed-demo seed-events seed-rooms seed-faculty dev
make acceptance PHASE=4
make test
make contract-check
make faculty-query-demo
```

The local database is already migrated/seeded and the API is running. Refresh http://localhost:8000/ for **10. Faculty office hours** and **11. Admin faculty publication**. Swagger is at `/docs`. Existing generated demo accounts/passwords remain unchanged.

Windows PowerShell (with Docker Desktop; Make is optional):

```powershell
docker compose build api
docker compose up -d db
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.db.provision
docker compose run --rm api python -m app.db.seed_faculty
docker compose up -d --wait api
docker compose exec -T api python /workspace/scripts/acceptance_phase4.py
docker compose run --rm api pytest -q
```

Other domain seeds are separate commands as in README. `/workspace` paths are inside the Linux container. Windows itself has not been directly tested.

## Browser walkthrough

1. Sign in as a student using the existing local account loader.
2. In **Faculty office hours**, resolve `Rao`. The synthetic seed deliberately maps it to two faculty members. The page must show candidates and clear any previous selection rather than silently choosing a person.
3. Select Anita Rao, supply a future date window and click **Find published office hours**. With the fixed seed, Friday 6 November 2026 has a 13:00–14:00 Asia/Kolkata slot; Friday 13 November is explicitly cancelled. Supply timestamps with offsets, e.g. 2026-11-06T00:00:00+05:30 to 2026-11-07T00:00:00+05:30, while that window is within the live 30-day horizon.
4. Select Bharat Rao and query the same window: his publication is incomplete, so no slots means `information_unavailable`, not confirmed absence. Anita's complete coverage and a day without a published slot means `no_results`.
5. Sign in as admin. In **Admin faculty publication**, start a new Faculty template, edit its name/department/location and explicit coverage dates/completeness, then create it. Its ID is retained for queries and later templates.
6. Select **Office-hour rules** and create the template for that faculty. It publishes a weekly local weekday/time interval over inclusive effective dates. Query the selected faculty to verify concrete meeting slots and source metadata.
7. Select **Office-hour exceptions**. The template targets the first original local occurrence date; adjust it to the slot you are testing. `action: cancel` removes it. For rescheduling, use `action: replace`, replacement_start/replacement_end and a note. The original date stays fixed; the slot can move to another day within seven local dates.
8. Query the replacement day, even when the original occurrence date lies outside the query window. The moved slot and exception note must appear. The original slot must be absent.
9. Create Faculty aliases as separate records. The same normalized alias may identify different faculty, producing an ambiguous result. A duplicate active alias for the same target is 409. This checkpoint supports only `entity_type: faculty`.
10. Reload records before edits/archive. Alias changes increment the faculty version; exception changes increment the parent rule version. Stale parent/record versions return 409. Students cannot publish or modify records.

The admin editor uses explicit JSON payloads from exported schemas; it sends the loaded version and preserves source fields. Listings are bounded to 20 in this utility; API cursors provide further pages. Deletion routes archive, retain audit/history references, and take `?version=N`. Archived records cannot be edited or reactivated in this checkpoint. Archive parent rules before retiring their exceptions to avoid reinstating a conflicting interval.

## API

All routes are under `/api/v1`; reads require login. Admin routes enforce server roles, and mutations retain cookie/CSRF/Origin protections.

| Endpoint | Behavior |
| --- | --- |
| GET `/faculty` | Active faculty list, literal name search, department filter and pagination |
| GET `/faculty/resolve?name=...` | Exact normalized canonical-name/alias resolution, optional department filter, explicit candidates |
| GET `/faculty/{id}` | Active faculty details, sources, current aliases and publication metadata |
| GET `/faculty/{id}/office-hours` | Concrete published slots in an explicit future window, after exceptions |
| GET/POST collections `/admin/faculty`, `/admin/aliases`, `/admin/office-hours`, `/admin/office-hour-exceptions` | Paginated admin list/create |
| GET/PATCH/DELETE item paths for those resources | Admin detail, versioned edit/archive |

Admin/public faculty lists accept `search`, `department_id`, `faculty_id`, `limit` (1–100, default 20) and query-bound `cursor`. Search is a literal substring; resolution is exact canonical/alias matching. Malformed/different-query cursors return 422. Resolve candidates are capped at 20 with an explicit warning when truncated; ambiguity is preserved.

Office-hour queries require offset-bearing `from_at`/`to_at`, entirely between server now and now + 30 days; `limit` and `cursor` bound results. Resolution and office-hour reads share a 60/user/fixed-minute rate limit with Retry-After on 429. HTTP clients cannot provide a server clock. Missing/archived faculty IDs return 404; unknown reference departments return 422.

## Publication and time semantics

- Faculty department IDs are foreign-key validated. Faculty names need not be unique; canonical IDs disambiguate people. The stored campus timezone is assigned at creation and immutable through the faculty API.
- Name/alias normalization applies NFKC, case folding, whitespace normalization and leading Prof/Professor/Dr removal. There is no fuzzy auto-selection. Aliases remain bound to one canonical faculty ID; archive/recreate to change a target. Collisions across people are allowed and surfaced, not silently resolved by profile context.
- Faculty publication metadata has inclusive local coverage dates and an explicit `office_hours_complete` flag. Complete coverage requires both bounds. No schedule/class timetable is used to infer meeting availability.
- Complete coverage + zero matching slots is `no_results`; missing/incomplete coverage + zero slots is `information_unavailable`. Known published slots may still be shown with partial coverage and warnings. The complete flag is an admin assertion about the maintained published data, not an inference from having a rule.
- Weekly rules use Monday=0 through Sunday=6, local start_time/end_time, IANA timezone and inclusive effective_from/effective_until dates. End 24:00 is allowed. A rule must include at least one matching weekday; effective dates are bounded to 366 days and must use the faculty's campus timezone.
- Local times expand into concrete instants before overlap tests. Ambiguous/nonexistent DST occurrences are rejected at publication rather than guessed. The implementation shares the tested time conversion primitive with rooms; initial campus time remains Asia/Kolkata.
- Query intervals are half-open [start,end) and select overlapping published meeting slots. Returned start/end are the actual published interval, not fabricated bounds clipped to the question. Boundary-only contact is not an overlap.
- Active exceptions uniquely target an original local occurrence date. Cancel removes it; replace requires a positive, explicit interval of at most 24 hours within seven local dates of the original. Replacement metadata/source/note is retained. Expansion considers moved occurrences even when their original date is outside the requested day.
- Effective slots for one faculty cannot overlap, including across rules and replacements. Back-to-back slots are allowed. Publication changes lock the faculty; parent rule/exception edits serialize on the rule as well. Queries take a shared faculty lock while reading schedules.
- Reinstating a cancelled slot by removing an exception, reactivating a rule or editing effective dates is checked for conflicts. Edits that orphan active exceptions are rejected. Version and audit updates commit atomically; failed requests do not leave partial edits.
- Sources, rule/exception identity, original local date, location, timezone and record-updated timestamp are returned with every slot. An old class schedule is never treated as a current office-hour source.

## Synthetic seed and deterministic CLI

`make seed-faculty` is explicit and insert-only. It never resets existing records or passwords. It seeds:

- Anita Rao (AIML): complete publication for 2 November–31 December 2026; Friday 13:00–14:00 office hours through 25 December; 13 November cancelled.
- Bharat Rao (CSE): publication completeness unknown.
- Both have alias Rao, intentionally creating ambiguity.

`make faculty-query-demo` injects 4 November 2026 10:00 Asia/Kolkata, resolves Professor Rao to two candidates, then queries Anita's 6 November slot by canonical ID. The live API uses current server time, so fixed old dates can fall outside its horizon later. Sources/names are visibly marked synthetic; this is not real-campus data or model evaluation.

The live acceptance script creates separate synthetic faculty, aliases, a weekly rule and an exception, verifies publication/ambiguity/cancellation/replacement/stale versions and student denial, then archives its records. Automated tests remove only their uniquely named rows. Archived live test records/audits remain; no database reset or hard-delete endpoint is added.

## Person 2 handoff and remaining work

Migration `0005_faculty` follows `0004_rooms`; coordinate subsequent revisions against that head. Faculty models/schemas/services/routes live in separate modules. Existing event/room/identity behavior and assistant conversation storage remain intact. Common Record/Source/patch/cursor helpers and safe local-time conversion are reused.

Runtime OpenAPI and 19 faculty fixtures cover records, aliases, rules, exceptions, resolved/ambiguous/no-match names and answered/no-slots/missing-publication responses. Review them before connecting frontend forms. Alias fields differ from generic campus aliases because only faculty targets are implemented now. Structured office-hour results are distinct from a future assistant faculty card. The direct resolver's candidate response does not establish stored dialogue/clarification state.

Next Person 1 work: extraction/resolution of natural-language dates/entities and validated meanings across domains, connected to these same typed services. Person 2 retains ownership of dialogue/history/saves, intent training and academic evaluation. A fully working three-domain language assistant is not claimed by this checkpoint.
