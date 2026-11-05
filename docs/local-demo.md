# Complete local demo

The combined application runs at **http://localhost:8000/**. React is compiled into the Docker image and served by FastAPI on the same origin as `/api/v1`; no frontend dev server is required. It uses labeled synthetic campus records. There is no OpenAI API dependency or key.

## Start

With Docker Desktop running, from the repository root:

```sh
make local
```

This builds the frontend/backend image, applies migrations and insert-only seeds/provisioning, and starts the app. Existing demo data is preserved. Open `/login` and sign in using username `student-a`, `student-b` or `admin` and the matching generated password in the ignored `.local/demo-accounts.json` file. Do not use the fictional frontend mock passwords in live mode.

The API docs remain at http://localhost:8000/docs. The independent backend test bench moved to http://localhost:8000/backend-test. React deep links under `/app` and `/admin` work after reload. API and SPA routes are separate; an unknown `/api/v1` path still produces an API error.

PowerShell without Make:

```powershell
docker compose build api
docker compose up -d db
docker compose run --rm api alembic upgrade head
foreach ($module in @('seed','provision','seed_events','seed_rooms','seed_faculty')) {
  docker compose run --rm api python -m "app.db.$module"
}
docker compose up -d --wait api
```

The same Linux Docker package is used on Windows; no native Windows execution is claimed. `docker compose stop` preserves the local database. Rebuild/recreate the API after frontend source changes to update the packaged UI.

## Exercise the product

- Student: log in, edit/reload profile, ask event/room/faculty questions, reply to a clarification, change a filter and reload a conversation.
- Save/unsave a returned entity. Saves contain current metadata; historical answers retain snapshots. Room saves do not claim continuing vacancy.
- Try `Is B201 free tomorrow?`, answer `from 14:00 to 15:00`, and follow up with a different time. Maintained bookings/closures may correctly produce no availability.
- Try `Professor Rao office hours on Friday`, then choose a listed faculty option. Use the new-question control to avoid treating an independent question as a pending reply.
- Admin: create/edit/archive events and maintain rooms, bookings, closures, faculty, office hours, their exceptions and faculty aliases. Weekdays are Monday=0 throughout.
- New events use exactly one topic. Faculty aliases are maintained in Aliases. Faculty publication coverage is explicit; unpublished room opening hours remain distinct from a published closed schedule.

The seed calendar is November–December 2026. Live questions use the actual server date, so demo schedules can age; the evaluator uses its explicit frozen clock. Records may be maintained through the admin UI. No student-collected or real campus data is implied.

## Verify

Backend and model/record regression:

```sh
make test contract-check
make acceptance-all
make train-intent evaluate
make verify-fresh
```

Frontend and actual live client/browser integration (requires host Node/npm for tests only):

```sh
npm ci --prefix frontend
npm run typecheck --prefix frontend
npm test --prefix frontend
npm run contracts:check --prefix frontend
cd frontend
npx playwright install chromium
ALMANAC_LIVE_TEST=1 npx vitest run tests/unit/live-http.test.ts
ALMANAC_LIVE_TEST=1 ALMANAC_APP_ORIGIN=http://127.0.0.1:8000 npx playwright test
```

In PowerShell set `$env:ALMANAC_LIVE_TEST='1'` and `$env:ALMANAC_APP_ORIGIN='http://127.0.0.1:8000'` before running the two test commands. The opt-in tests use local generated accounts and create/archive only synthetic admin records. The real client smoke deletes only its own conversation. Browser conversations are retained as demo verification examples. Mock UI tests run separately on the explicit mock server; live tests do not intercept API responses.

`make verify-fresh` builds a separate immutable combined image and exercises a new disposable database without host ports or source mounts. It removes only its own verification resources. The normal localhost database remains untouched by that rehearsal.

The frontend's live adapter validates UI-facing results and explicitly translates wire shapes. Raw backend OpenAPI is authoritative; `contracts/frontend-proposal/` describes the retained mock/view-model shapes, not an alternate live API. History/saved offset pagination is translated at the boundary; other resource pages retain opaque backend cursors.

Profile interests influence deterministic event ordering without granting eligibility or dropping nonmatching topics. NLP settings `NOW_INTERVAL_MINUTES` (default 30) and `NLP_HORIZON_DAYS` (default 30, maximum 30) can be set in root `.env`. Structured availability retains its 30-day maximum. The baseline rules remain default because the optional synthetic-trained classifier performs worse on the reported benchmarks.

This is the agreed local labeled-demo release. Real-student accuracy claims, public hosting, HTTPS/domain setup and real campus-data acquisition are outside this local scope. No new dependency on an external AI service has been added.
