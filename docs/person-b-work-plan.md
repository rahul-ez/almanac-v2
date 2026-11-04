# Person B — Live integration, dialogue, personal records and NLP evaluation

Repository: https://github.com/rahul-ez/almanac-v2

Starting checkpoint: backend Phases 0–2, API 0.3.0, migrations through 0003. The backend branch contains the tested API, localhost test bench, demo data and setup. Main contains the frontend; live integration is still unverified. These assignments can start simultaneously in separate clones. Nothing in this assignment requires pushing directly to main.

Your responsibility is to connect the completed frontend to the real backend, then implement personal-record/dialogue services and the intent-model/evaluation work. Person A independently builds room scheduling, faculty semantics and extraction/resolution. This assignment includes backend implementation, not just interface polish.

## Start here

In your own clone:

```sh
git fetch origin
git switch -c integration/live-api origin/main
git merge origin/backend
```

Resolve overlapping README/.gitignore, OpenAPI and fixture files on this integration branch. Preserve frontend code and annotation drafts from main, backend source/tests from backend, and both sets of ignore rules. Backend base predates frontend commits; do not treat an add/add conflict as permission to discard either implementation.

The backend runtime OpenAPI is the implemented API contract. Keep any frontend proposal separately named until reconciled. Update frontend export/check tooling so it no longer overwrites runtime OpenAPI. Do not merge into main until the live event slice passes review.

After resolving integration files:

```sh
make bootstrap migrate provision-demo seed-demo seed-events dev
# In frontend/:
npm ci
npm run dev
```

Configure frontend live mode and its API proxy as described in frontend/README.md. Use the same hostname throughout, e.g. localhost:5173 for Vite and localhost:8000 for FastAPI. Backend demo passwords come from ignored `.local/demo-accounts.json`, not the frontend mock credentials. Never put them into public VITE variables or commit them.

## B1 — Live auth/profile/events integration (first deliverable)

Resolve the differences below in the frontend adapter, runtime schemas, forms and fixture tooling. Keep runtime backend semantics unless both owners explicitly agree to a change. Do not weaken CSRF/ownership or add mock fallback to make screens appear to work.

Exit: an actual browser signs in with generated backend accounts, edits a student profile, sees an admin-created event, asks a supported event question and receives a real result, cancels an event and observes current results change. An unauthenticated/student request remains rejected by the server. Use the same hostname throughout, e.g. localhost:5173 for Vite and localhost:8000 for FastAPI, with the Vite API proxy. Backend test bench remains available on :8000. No intercepted responses in this live gate.

### Contract differences to resolve

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

Keep current backend behavior unless a shared contract change is reviewed with Person A. Adapt response parsing and rendering explicitly. Preserve unknown eligibility/price, source timestamps, profile ownership, CSRF rotation, allowed origins and stale-edit conflicts.

## B2 — History and saved records (second deliverable)

Extend existing conversations/turns rather than creating competing tables or a second retry implementation. Add owned list/detail/delete APIs, pagination, deletion of stored turns/state, and unique current-record saves with valid references. Start with events, then add room/faculty targets as A's records land. Do not save an old availability claim as current truth. Test cross-user IDs, cascade deletion, retries and record changes; wire existing frontend screens to the real endpoints.

Implement the missing API/services/migrations and live frontend connection:

- Owned paginated conversation list/detail and deletion of stored turns/state.
- Unique saved targets with valid references, idempotent save/remove and current-record lookup.
- Cancelled/archived event handling; historical answers remain timestamped snapshots.
- Extend room/faculty saved targets as Person A's corresponding records arrive.
- Two-student privacy checks, retry/concurrency behavior and meaningful deletion tests.

Coordinate migration IDs with Person A. Existing conversation/turn storage and request deduplication already exist in backend/app/services/assistant.py and backend/app/db/models.py; extend them instead of introducing a competing assistant route or persistence scheme.

## B3 — Dialogue and clarification

Implement owned server-side dialogue state, versioning or serialized turns, context precedence/clearing, supported filter follow-ups, domain resets, clarification IDs/options/expiry and inactivity expiry. Integrate existing frontend flows only when the backend behavior is real. Test refresh, stale clarification, retries, concurrent turns, cross-user IDs and fresh queries after record changes.

## B4 — Corpus, intent classifier and evaluation

Review the synthetic pilot/dialogue drafts already on main. Validate labels, spans, canonical meaning, expected records and fixed clocks. Collect human examples with consent/anonymization; jointly double-label and adjudicate a sample with Person A. Keep entire paraphrase families/conversations together in train/validation/test splits; freeze the test set before tuning.

Own the TF-IDF/logistic-regression intent pipeline, model/version metadata and reproducible artifact loading interface with Person A. Compare the existing event rule baseline with the hybrid pipeline as domain coverage grows. Report intent macro F1/per-class metrics, entity metrics, normalization and meaning accuracy, end-to-end result/status correctness, dialogue outcomes and latency on fixed records/clock. Report actual results and errors; synthetic examples and mock workflows are not accuracy evidence. Optional encoder comparison comes after required work.

### Interpreter boundary with Person A

Before either owner changes the interpreter, agree the typed meaning shape and the pure interpreter interface: question + explicit context + injected clock/timezone + alias/catalog input -> meaning or uncertainty outcome, with provenance. Person A owns extraction/resolution and domain validation/execution; Person B owns intent model, state/clarification, corpus splits and metrics. One orchestrator composes them; never create a second assistant route. Keep the current event baseline as a separately measurable comparison. Freeze grouped test data before tuning.

## Files and coordination

- Person A coordinates migration numbering and the final linear Alembic head. Reserve each new revision before either owner writes one; avoid independently generating two revisions named 0004. Commit migrations with their owning feature and run empty-database upgrade plus existing-data upgrade checks.
- Add new domain ORM classes in separate room/faculty modules and dialogue/save additions in separate modules when appropriate; register all metadata explicitly. Coordinate edits to central models/main imports instead of editing the same large file concurrently. A small separate refactor can introduce these seams if needed; it is not already done.
- New API/schema/service/test files should be domain-specific. Person A owns shared meaning/response composition and runtime OpenAPI export; Person B owns client adapters/rendering, dataset/evaluation scripts and dialogue state implementation. Cross-owner changes get review.
- Backend dependency lock belongs to Person A; frontend lock belongs to Person B. Model-training dependencies are pinned with Person A's review. Keep private credentials and real histories out of Git.
- Freeze upcoming room/faculty card and admin payload contracts before both owners work on them. The existing frontend proposal is useful input, not automatic proof that the backend supports it.
- A PR includes acceptance commands, expected IDs/intervals/status, migration/seed changes, affected contracts and actual test evidence. Only claim checks that ran.

Prefer separate dialogue/save/model-training/evaluation files. Coordinate edits to central main/model registration and assistant orchestration with Person A. You own frontend schemas/adapters/rendering and the frontend lockfile; Person A maintains runtime OpenAPI export and coordinates backend dependencies/migration heads.

## Acceptance gates

Keep backend tests/contracts and Phases 0–2 acceptance green. After aligning the client, run frontend typecheck, contract check, unit tests and production build. Retain existing intercepted browser tests, then add an unmocked frontend-to-API/PostgreSQL smoke flow:

1. Real login/profile persistence and session expiry/logout.
2. Admin creates/updates/cancels an event; student natural-language query reflects current data.
3. Student admin access rejected; another student's history/save IDs do not grant access.
4. Room/faculty workflows once Person A lands those services.
5. Clarification/follow-up, retry safety, saves and deletion once implemented.

Document what is live and what remains mock-only. Each PR includes exact acceptance commands and actual evidence, with corresponding client/fixture/schema changes. After B1 passes review and is integrated, synchronize both owners' next branches from the common integrated commit. Final evaluation and deployed-origin smoke checks are joint deliverables.
