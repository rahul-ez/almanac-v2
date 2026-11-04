# Two-person continuation from the tested backend checkpoint

Prepared 4 November 2026. Backend Phases 0–2 are implemented; `main` was reviewed at `bf479b913cf0a9fce5dad9f8cefdc8d7f7de87db`. The frontend is implemented there, but its own handoff explicitly says real-backend integration is unverified. This plan replaces the original frontend/backend-only ownership split for the remaining work.

## Branches and starting point

- `backend`: published snapshot of the tested backend, contracts, localhost test bench, seeds and Phase 0–2 instructions. Its base predates the frontend commits. It does not remove or rewrite anything on `main`.
- Person A (current backend owner): branch `feature/room-scheduling` from `origin/backend`.
- Person B (available frontend owner): branch `integration/live-api` from `origin/main`; merge `origin/backend` into this integration branch, resolve overlapping files, then connect the existing frontend to the tested API. Never merge blindly into main.
- Keep `backend` as the reviewed backend integration branch while live integration is being reconciled. Use short feature branches and PRs. Do not have both people commit directly to the same working branch or share a checkout/database during migration work.

Suggested commands after fetching:

```sh
# Person A, in their own clone
 git switch -c feature/room-scheduling origin/backend

# Person B, in their own clone
 git switch -c integration/live-api origin/main
 git merge origin/backend
```

The second merge will require decisions for README, .gitignore, contracts/openapi.json and shared fixture paths. Preserve both sets of documentation and ignore rules; use the backend runtime schema as the implemented API contract. Keep any frontend proposals separately named until reconciled. Do not overwrite the backend OpenAPI using the frontend proposal exporter. Regenerate frontend types/mocks/tests from the agreed behavior, and update its contract-export/check tooling accordingly. Preserve frontend code and annotation drafts already on main.

After the first live event slice passes review, integrate it with main through a PR, then both owners synchronize their next feature branches from the common integrated commit. Future domain/UI changes should merge as small tested increments.

## Ownership and parallel work

| Area | Person A: backend domains and execution | Person B: live integration, dialogue and evaluation |
| --- | --- | --- |
| Immediately | Phase 3 rooms, opening hours, coverage, bookings, bounded recurrence, exceptions, closures and transactional conflicts | Reconcile implemented auth/profile/event contracts and run the existing frontend against the real API; start reviewing annotation drafts |
| Next | Phase 4 faculty, aliases, office-hour recurrence and exceptions | Owned history APIs/deletion, current-record saves and their frontend integration, extending the existing retry-safe conversation storage |
| NLP | Date/alias/entity resolution and typed meaning validation; domain service interfaces and safe execution across three domains | Corpus schema/validation, group-safe splits, TF-IDF classifier/training artifacts, dialogue transitions/clarification and evaluation scripts |
| Tests | Domain/time/recurrence/coverage, permissions for new endpoints, database conflicts and migration/seed tests | Live browser/contract checks, dialogue ownership/retries/deletion, dataset leakage checks and model comparison |
| Final | Operational readiness, migrations, deployment reproducibility, domain performance fixes | Real-browser workflow coverage, final evaluation/error analysis and report; joint deployment smoke check |

Each owner implements and tests their own endpoints/services and updates the relevant client/fixtures with review where needed. Person B is not restricted to UI polish; persistence/dialogue and NLP evaluation are substantial backend work. Both people collect/review annotations and double-label an agreed sample. Rebalance after each checkpoint based on actual effort, rather than treating the rows as equal durations.

## Immediate concrete tickets

### A1 — Rooms against structured queries (Phase 3)

Deliver room records with capacity/building/facilities, campus-local opening hours, explicit schedule coverage, bounded one-off/weekly bookings, dated cancellation/replacement exceptions and closures. Add typed service queries, admin CRUD and a localhost test-bench walkthrough. No student room reservation feature.

Exit: an interval ending at a booking start is allowed, overlap is rejected, recurring exceptions work, closures win, missing coverage is unknown, and conflicting concurrent bookings cannot both commit. Test through API/CLI without relying on NLP or frontend availability. Retain all Phase 0–2 checks.

### B1 — Existing frontend talking to Phase 0–2 (start simultaneously)

Resolve the differences below in the frontend adapter, runtime schemas, forms and fixture tooling. Keep runtime backend semantics unless both owners explicitly agree to a change. Do not weaken CSRF/ownership or add mock fallback to make screens appear to work.

Exit: an actual browser signs in with generated backend accounts, edits a student profile, sees an admin-created event, asks a supported event question and receives a real result, cancels an event and observes current results change. An unauthenticated/student request remains rejected by the server. Use the same hostname throughout, e.g. localhost:5173 for Vite and localhost:8000 for FastAPI, with the Vite API proxy. Backend test bench remains available on :8000. No intercepted responses in this live gate.

### A2 — Faculty/office hours (after A1)

Deliver canonical faculty/alias resolution, published weekly office hours with effective dates and dated cancellations/replacements. Provide a typed query service and API/CLI examples. Similar names remain ambiguous; no inference from teaching timetables. Test exact concrete intervals and missing publication separately from no matching slots.

### B2 — History and saves (after B1; can overlap A2)

Extend existing conversations/turns rather than creating competing tables or a second retry implementation. Add owned list/detail/delete APIs, pagination, deletion of stored turns/state, and unique current-record saves with valid references. Start with events, then add room/faculty targets as A's records land. Do not save an old availability claim as current truth. Test cross-user IDs, cascade deletion, retries and record changes; wire existing frontend screens to the real endpoints.

### Shared NLP handoff

Before either owner changes the interpreter, agree the typed meaning shape and the pure interpreter interface: question + explicit context + injected clock/timezone + alias/catalog input -> meaning or uncertainty outcome, with provenance. Person A owns extraction/resolution and domain validation/execution; Person B owns intent model, state/clarification, corpus splits and metrics. One orchestrator composes them; never create a second assistant route. Keep the current event baseline as a separately measurable comparison. Freeze grouped test data before tuning.

## Observed contract differences to resolve first

| Area | Frontend main assumes | Backend 0.3.0 actually implements | Initial integration action |
| --- | --- | --- | --- |
| Login request | email + password | username + password | Update live login/labels and demo credential handling; do not assume mock passwords authenticate |
| Login/me response | User with name/email/role; login returns User directly | Login `{user, csrf_token}`; identity id/username/role/session_expires_at | Update schemas/adapter/display; consume rotation or fetch active CSRF again |
| CSRF failure | code `csrf_invalid` | code `csrf_failed` | Align error handling; keep allowed Origin checks |
| Errors | field_errors is a map of string arrays | field_errors is an array of `{field,message}` | Adapt errors/forms or agree one versioned representation |
| References/profile | facilities + campus_timezone; profile years up to 6 | departments/buildings/topics/supported_years; initial years 1–4, owner derived from cookie | Read supported_years dynamically; add future reference fields with agreed schema changes |
| Event records | topic_ids array, eligibility_mode/all_students and allowed arrays | topic_id plus eligibility_rules `{mode:unknown/unrestricted/restricted,years,departments}` | Map frontend forms and list schemas to the implemented record, preserving unknown values |
| Event student reads | event cards | EventView records in paginated lists/detail | Introduce an explicit record-to-view adapter or agree the API output before rendering |
| Archive/search | If-Match version header and `search` parameter | `?version=N` on DELETE; `q` literal title filter | Update live adapter to existing wire format |
| Assistant cards | flat starts/ends, topics, record_status, description; room/faculty kinds | event card with interval, topic, eligibility_rules, registration_status; other domains not live yet | Align event rendering first; agree later room/faculty schemas before A implements them |
| Assistant context/coverage | context map and coverage object; non-null meaning | context list with field/origin/value, coverage enum; meaning may be null | Update parsing/rendering and fixtures; unsupported responses must remain renderable |
| Request limits/state | text up to 2000; generic overrides/clear and full conversations | text up to 1000; year/department overrides; independent event questions; follow-ups explicitly unsupported | Respect current limits, indicate unimplemented flows and add capabilities as B2/dialogue land |
| OpenAPI generation | frontend exporter writes contracts/openapi.json proposal | backend exporter writes runtime OpenAPI at same path | Establish a single runtime export owner and stop the two generators overwriting each other |

Other endpoints (room/faculty, history, saves, full dialogue) are future backend work. A completed mock screen does not make those endpoints implemented. Keep mock mode explicit, and document which workflows are currently live.

## Conflict prevention and integration rules

- Person A coordinates migration numbering and the final linear Alembic head. Reserve each new revision before either owner writes one; avoid independently generating two revisions named 0004. Commit migrations with their owning feature and run empty-database upgrade plus existing-data upgrade checks.
- Add new domain ORM classes in separate room/faculty modules and dialogue/save additions in separate modules when appropriate; register all metadata explicitly. Coordinate edits to central models/main imports instead of editing the same large file concurrently. A small separate refactor can introduce these seams if needed; it is not already done.
- New API/schema/service/test files should be domain-specific. Person A owns shared meaning/response composition and runtime OpenAPI export; Person B owns client adapters/rendering, dataset/evaluation scripts and dialogue state implementation. Cross-owner changes get review.
- Backend dependency lock belongs to Person A; frontend lock belongs to Person B. Model-training dependencies are pinned with Person A's review. Keep private credentials and real histories out of Git.
- Freeze upcoming room/faculty card and admin payload contracts before both owners work on them. The existing frontend proposal is useful input, not automatic proof that the backend supports it.
- A PR includes acceptance commands, expected IDs/intervals/status, migration/seed changes, affected contracts and actual test evidence. Only claim checks that ran.

## Joint user-test checkpoints

1. Current backend Phases 0–2 stay green; B1 proves the same event slice in the real frontend.
2. A1 room semantics plus a structured browser/API/CLI walkthrough; user tests boundary/coverage cases.
3. A2 faculty semantics plus published schedule exceptions; user tests concrete slots and ambiguity.
4. B2 history/saves plus full dialogue later: user tests two accounts, refresh, current records, retry safety and deletion.
5. Hybrid NLP + fixed-split baseline comparison + final real-browser/deployment gate.

Backend baseline checks are `make test`, `make contract-check`, and `make acceptance PHASE=0/1/2`. After integration, also run the frontend type/build/unit checks and its schema checks updated to the agreed runtime contract. Existing intercepted “live mode” browser tests remain useful transport tests, but they do not replace an unmocked frontend-to-PostgreSQL smoke test.
