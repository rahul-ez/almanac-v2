# Phase 0 verification — 4 November 2026

Local branch: `backend/phase-0-foundation`, based on upstream `b7e9c2a7b0a41e68073bd45244726a3554a416fb`. Changes are local and not pushed.

Environment: Docker Desktop on macOS arm64; API Python 3.13 container; PostgreSQL 16 Alpine. Resolved Python package versions are in `backend/requirements.lock`. Seed version: v1. Contract/API version: 0.1.0. Fixture clock: 2026-11-04 10:00 +05:30; live API uses the real clock.

Executed successfully:

- `make bootstrap`: built image and created a new empty PostgreSQL data volume.
- `make migrate`: applied revision 0001 to that empty database.
- `make seed-demo`: inserted the synthetic event; repeated seed tests retained one record.
- `make contract-export` then `make contract-check`: exported runtime OpenAPI and future response schemas; twelve fixtures passed Pydantic and JSON Schema validation.
- `make dev`: starts services and waits for API liveness health.
- `make acceptance PHASE=0`: live 200, ready 200, demo event 200, unknown path 404 with consistent request ID.
- Database stopped explicitly: live remained 200, readiness became 503, demo event became 503. Database restarted and the same running API passed acceptance again.
- `make reset-demo CONFIRM=demo-only`: reset the versioned synthetic row successfully; automatic tests confirm unconfirmed CLI reset is rejected.
- `make test`: **5 passed**, covering invalid configuration/intervals, database failure sanitization, real PostgreSQL constraints, repeatable seed, API response, contracts, and reset confirmation.
- `git diff --check`: no whitespace errors in tracked diffs.

One upstream deprecation warning: Starlette's test client warns that its httpx transport is deprecated in favor of httpx2. It does not affect runtime or current test results; review when updating the locked test dependencies.

The initial acceptance run found a startup race; `make dev` was changed to wait on a container health check, and acceptance then passed. No unresolved failing checks remain. GitHub CI configuration is added but has not run remotely.

Limitations: no authentication, live assistant endpoint, trained NLP model, final campus-domain tables, or frontend integration yet. The public demo endpoint contains only synthetic data. Deployment/production settings are intentionally not available at this checkpoint. User test instructions are in `docs/phase-0-testing.md`.
