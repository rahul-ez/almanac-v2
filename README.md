# Almanac backend

Phase 2 adds event management, structured search, eligibility, audit/version checks and a limited rule-based event assistant to the existing sessions/profiles/runtime. The localhost test bench supports all three checkpoints.

Requires Docker Desktop with Compose and Make. Python runs inside Docker (3.13); no host Python installation is needed.

```sh
make bootstrap
make migrate
make seed-demo
make provision-demo
make seed-events
make contract-check
make dev
make acceptance PHASE=0
make acceptance PHASE=1
make acceptance PHASE=2
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

See [Phase 2 walkthrough](docs/phase-2-testing.md), [Phase 1 walkthrough](docs/phase-1-testing.md), [Phase 0 walkthrough](docs/phase-0-testing.md), [phase sequence](docs/backend-phases-and-testing.md), and [contracts](contracts/README.md).

Two-person continuation and current frontend/backend contract differences: [parallel work handoff](docs/two-person-backend-handoff.md).
