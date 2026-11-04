# Almanac — frontend and backend

The backend is implemented through conversations, history and saved records, with local evaluation and packaged-install checks. The existing frontend is included in `frontend/` and currently defaults to mock mode. Live integration and joint testing remain pending.

Requires Docker Desktop with Compose and Make. Python runs inside Docker (3.13); no host Python installation is needed.

```sh
make bootstrap
make migrate
make seed-demo
make provision-demo
make seed-events
make seed-rooms
make seed-faculty
make contract-check
make dev
make acceptance PHASE=0
make acceptance PHASE=1
make acceptance PHASE=2
make acceptance PHASE=3
make acceptance PHASE=4
make test
```

Open the [browser test bench](http://localhost:8000/) to sign in, edit profiles and test permissions. [API documentation](http://localhost:8000/docs) remains available. Try:

```sh
curl -i http://localhost:8000/api/v1/health/live
curl -i http://localhost:8000/api/v1/health/ready
curl -i http://localhost:8000/api/v1/demo/event
```

Expected: 200 for all three after migration and seed. The event is labeled DEMO and has ID `demo-event-ml-workshop`. It is a fixed November 2026 fixture, not a claim of a current campus event. Startup uses real server time and never seeds, migrates, or resets data automatically.

`make stop` stops services while preserving PostgreSQL data. `make dev` resumes them. API binds to localhost:8000; the database is only reachable on the Compose network. `.env.example` lists optional local configuration; Compose defaults work without copying it. This configuration is for local development only.

Demo passwords are generated into the ignored local file `.local/demo-accounts.json`; they are not committed or printed.

See [Phase 4 walkthrough](docs/phase-4-testing.md), [Phase 3 walkthrough](docs/phase-3-testing.md), [Phase 2 walkthrough](docs/phase-2-testing.md), [Phase 1 walkthrough](docs/phase-1-testing.md), [Phase 0 walkthrough](docs/phase-0-testing.md), [phase sequence](docs/backend-phases-and-testing.md), and [contracts](contracts/README.md).

Two-person continuation and current frontend/backend contract differences: [parallel work handoff](docs/two-person-backend-handoff.md).

Latest backend checkpoint: [Phase 5 interpretation testing](docs/phase-5-testing.md). Backend ownership currently covers both original person work plans; no parallel handoff is required to continue.

Intent-model checkpoint: [train and test optional hybrid mode](docs/phase-5-intent-testing.md). Run `make train-intent` to reproduce the synthetic prototype; default localhost service remains in rule mode.

Latest backend checkpoint: [Phase 6 conversations, history and saves](docs/phase-6-testing.md). Local test bench sections 6 and 12 exercise the real API at localhost:8000.

Backend engineering verification: [Phase 7 evaluation and fresh packaged installation](docs/phase-7-testing.md), plus [release/integration handoff](docs/backend-release-handoff.md). Commands: `make evaluate`, `make acceptance-all`, `make verify-fresh`. These do not publish or deploy the application.

## Frontend

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. See [frontend setup](frontend/README.md) and [integration handoff](docs/frontend-handoff.md). Mock accounts and data remain fictional. The backend test bench runs independently at http://localhost:8000/.

The implemented API is [contracts/openapi.json](contracts/openapi.json). The frontend's existing mock proposal and fixtures are preserved separately under [contracts/frontend-proposal](contracts/frontend-proposal/README.md). Align the frontend client/schema with the implemented API before enabling live workflows; merging code does not complete that integration.
