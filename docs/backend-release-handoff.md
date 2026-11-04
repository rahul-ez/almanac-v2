# Backend handoff and release boundaries

The backend is implemented through dialogue/history/saves and has reproducible local engineering evaluation and packaged-install checks. It remains a local demo/test runtime: `APP_ENV` currently accepts `development` and `test`. No production deployment, public exposure, frontend merge or Git push has been performed.

## Architecture and evidence

FastAPI `/api/v1` authenticates server-side cookie sessions and synchronizer CSRF tokens. PostgreSQL stores profiles, maintained campus records, expiring dialogue state, immutable answer snapshots and owned saved references. Pure rules/optional TF-IDF intent prediction produce validated typed queries. The three domain services perform bounded record retrieval and return source-backed event, scheduled-room and published-office-hour cards. No generative answering or arbitrary SQL execution is involved.

The current Alembic head is **0006_personal**, API **0.7.0**. Check `contracts/openapi.json`, `contracts/README.md`, Phase 0–7 testing guides, `reports/phase-6/verification.md` and the Phase 7 JSON reports. The independent product frontend lives on its own track; the localhost test bench is an API utility, not proof that frontend integration is complete.

Default rule mode is selected because the synthetic prototype classifier underperforms it. Hybrid selection is explicit server configuration and requires a compatible local JSON artifact/checksum. Missing/incompatible artifacts fail readiness and new inference; there is no silent fallback. Retraining never occurs during startup/HTTP handling.

## Reproduce the local handoff

```sh
make bootstrap migrate seed-demo provision-demo seed-events seed-rooms seed-faculty dev
make train-intent evaluate test contract-check
make acceptance-all
make verify-fresh
```

The model artifact and generated credentials are under ignored `.local/`. Never commit them or copy demo accounts into a real deployment. Source, requirements, data manifests, schemas and reports are versioned inputs; the current work remains local until explicitly committed/pushed. Use the exact image identity and source checksum in the reports when reproducing a specific checkpoint. A future source change requires rerunning the relevant gates.

## Target-host configuration to settle before deployment

The current `compose.yaml` binds the API to loopback only and does not publish PostgreSQL. It mounts the checkout for development. `compose.verify.yaml` verifies an immutable packaged image privately and is disposable; it is not a persistent deployment configuration.

A deployment needs its own persistent configuration: private PostgreSQL/volume lifecycle, managed database credentials, an approved HTTPS reverse proxy/hostname, explicit `ALLOWED_ORIGINS`, `COOKIE_SECURE=true` for HTTPS, stable artifact storage and exact dependency/runtime compatibility. Settings accept `DATABASE_URL`, `CAMPUS_TIMEZONE`, `NLP_MODE`, `INTENT_MODEL_PATH`, `ALLOWED_ORIGINS` (JSON list), `COOKIE_SECURE` and bounded session/rate settings. Inject them explicitly into packaged containers; an image does not include the host's `.env` or `.local`. Do not expose the development defaults unchanged. Adding a production environment mode and its validated deployment configuration is still target-specific work.

Run migrations as an explicit release step, never as a request/startup reset. Check `/api/v1/health/live` for process liveness and `/api/v1/health/ready` for database/schema/selected NLP readiness. Keep access/CSRF controls and bounded rates enabled. Runtime logs deliberately omit query text, credentials, cookies and profile data. Error responses expose request IDs for correlation without echoing private input.

## Data backup and restore

Before a real upgrade, create a PostgreSQL custom-format backup with the target's managed credentials and retain its matching source/image revision and artifact. Never print a database URL/password into logs. `pg_dump`/`pg_restore` are available inside the PostgreSQL image; transfer backups using the chosen secure operator workflow rather than committing them to the repository.

Verify restoration into a separate database before relying on the backup. Run migrations, readiness and authorized smoke checks on that restored copy. Do not run synthetic reset/provision/acceptance commands against real campus/student data. Local demo scripts explicitly restrict their database names; acceptance scripts create and archive demo records and are intended only for named non-production workflows. No real backup/restore or live-data upgrade has been claimed by the fresh empty-database rehearsal.

Conversation deletion removes stored questions/answers/state. Text-free hashed request-ID receipts remain to block delayed retries. Saved items point to current canonical records; archived/draft targets expose status with no current details. These behaviors should be explained in the real product's data controls.

## Frontend integration gate

The frontend owner should reconcile against the current OpenAPI/schema fixtures and validate these flows with the real API:

- Login/session rotation/logout with credentials and exact Origin/CSRF headers; cookie handling on the actual hosting origin.
- Profile updates and precedence chips for explicit text, override, prior context, profile and defaults.
- All three card types, sources, coverage/eligibility uncertainty, cancellation and truncation messages.
- Active clarification IDs/options, free-text replies, context expiry, version-conflict reload and fresh domain switches.
- Owned history pagination/reopening/deletion, exact old snapshots, current saved status and changed markers.
- Error handling for 401/403/404/409/410/413/422/429/503; Retry-After and readiness failures.

A separate browser check must confirm actual React rendering/navigation and accessibility. The utility test bench already exercises backend cookies and APIs but does not replace this gate.

## Final NLP study

Obtain and anonymize real student questions, independently review/adjudicate intent/span/normalized-value/record gold, preserve paraphrase and conversation grouping, and freeze independent final test inputs and targets before tuning. Use the engineering evaluator as tooling, not as a substitute for that corpus. Report intent/extraction/normalization/meaning/end-to-end/dialogue outcomes, errors, support counts and cold/warm timing with the actual hardware and maintained dataset size. Current synthetic metrics are deliberately labeled and do not substantiate real-world accuracy claims.
