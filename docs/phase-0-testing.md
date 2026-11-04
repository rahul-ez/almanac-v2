# Phase 0: runtime and contract acceptance

## Implemented scope

FastAPI application factory, validated PostgreSQL/time-zone/mode configuration, pinned Python dependencies, Alembic revision `0001`, constrained demo-event storage, repeatable insert-only seed, liveness/readiness, a database-backed demo endpoint, sanitized request logs and errors, and twelve shared response fixtures. The selected baseline mode needs no model artifact; unsupported model modes fail configuration validation.

The isolated `demo_events` table supports the first runtime checkpoint; it is not the final events domain schema. The demo endpoint is public and contains only synthetic data. No student or campus records should be placed there.

## Fresh setup

From the repository root, with Docker Desktop running:

```sh
make bootstrap
make migrate
make seed-demo
make contract-check
make dev
make acceptance PHASE=0
make test
```

`make bootstrap` builds the API image and starts PostgreSQL. Migration, seed and startup are separate, intentional operations. `make seed-demo` may be run twice: it retains one row and preserves existing values. It is restricted to database names `almanac_demo` and `almanac_test`.

`make acceptance PHASE=0` calls the running server. `make test` checks configuration/interval validation, database failures, schema drift, fixtures and real PostgreSQL constraints/seed repeatability. It expects the migrated Compose demo database and uses no drop/reset operations. Full auth, migration upgrade-path and domain regression suites grow with later phases.

## Database failure and recovery

With the API running:

```sh
docker compose stop db
curl -i http://localhost:8000/api/v1/health/live
curl -i http://localhost:8000/api/v1/health/ready
curl -i http://localhost:8000/api/v1/demo/event
docker compose start db
```

Expected while DB is stopped: live 200; ready 503 with `not_ready` and unavailable database/schema checks; demo 503 with `dependency_unavailable`. Repeat `make acceptance PHASE=0` after PostgreSQL is healthy. Readiness recovers without restarting the API. A database error must never become an empty-results response. Readiness before migration is also 503; missing seed is a distinct 404 on the demo endpoint.

## Contract and frontend handoff

- `contracts/openapi.json`: implemented operations only.
- `contracts/assistant-response.schema.json`: proposed future typed response cards and statuses.
- `contracts/error.schema.json`: common structured error envelope.
- `contracts/fixtures/`: event, room, faculty, no matches, missing coverage, ambiguous faculty, missing interval, follow-up, unsupported, expired login, validation error, backend outage.

Assistant fixtures validate against both Pydantic and JSON Schema but are not exposed as a live assistant API. Domain-specific meaning validation, request/admin schemas and final session behavior will be added in their implementing phases. The proposed CSRF wire format is recorded in `contracts/README.md`.

Use `make contract-export` after intentional schema edits, then `make contract-check`. Share contract diffs with the frontend owner. `/docs` is available for inspection but no login/query forms exist yet.

## Logs and troubleshooting

`docker compose logs api` shows request ID, method, route template, status and duration. Logs omit request bodies, raw URLs/query strings, cookie values, database URLs and exception text. Responses include `X-Request-ID`; structured errors include the same ID.

A 404 at `/api/v1/demo/event` means seed is missing. A 503 means database or migration schema is unavailable. A port conflict means another process uses 8000. Do not delete Docker volumes to resolve an application error. `make stop` preserves data.

## Reset only the versioned synthetic fixture

`make reset-demo CONFIRM=demo-only` replaces only the IDs present in `data/demo/events.json`, within one transaction. It does not drop tables or remove other rows. The same database-name restriction applies. Missing confirmation refuses the command. This is separate from both seed and startup.
