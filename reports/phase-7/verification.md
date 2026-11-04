# Phase 7 engineering verification

Verified locally on 4 November 2026. All work remains local/uncommitted on `feature/room-scheduling`; nothing was pushed or deployed.

- **103 tests passed**, one upstream Starlette/httpx deprecation warning, both in the development runtime and in the isolated packaged image.
- **74 schema fixtures** passed drift, Pydantic and JSON Schema validation in the packaged image.
- Frozen synthetic evaluation: baseline **24/24** end-to-end, **16/16** exact meanings, **47/47** normalized gold slots, **40/40** exact span/type entities. Prototype hybrid: **8/24** end-to-end, **3/16** exact meanings, **11/47** gold slots. Both returned zero answers on gold non-answer cases.
- Evaluation uses the same production pure pipeline and typed PostgreSQL services in a uniquely named disposable database, fixed clock and checksum-verified records/gold. No training or tuning occurs during evaluation. The previously reported model is unchanged.
- Regression evaluation found an adjacent masked capacity phrase being included in a time entity's text span. The interpreter was fixed and a focused assertion added against unchanged engineering gold. This suite is known synthetic regression data, not an untouched academic final test set.
- Fresh-install rehearsal built its own image, used no host source bind mounts or published ports, migrated an empty database, seeded/provisioned twice, trained the prototype, evaluated semantics, ran regressions, exercised all HTTP Phases 0–6, selected hybrid and passed hybrid HTTP smoke checks.
- Only the uniquely named verification project's containers/volumes were removed. Existing localhost:8000 and its database were not used by the fresh rehearsal. The local API was then restarted with the verified source; Phase 0 readiness/liveness/demo checks passed.
- CI now uses a rate-aware HTTP acceptance orchestrator rather than weakening/clearing authentication limits. CI configuration was prepared locally; no remote workflow run is claimed.
- `git diff --check` passed. No product frontend integration, native Windows run, real data backup/restore, real-student final evaluation or actual deployment is claimed.

Packaged image: `sha256:d0e052b911a90c5069ab1096cef6b6080cf9ce5f19dd81f75267e048c4f11739`. Fresh rehearsal: 102.78 seconds; cleanup confirmed: True.

Evaluation source SHA-256: `4f390ed8f46b488e0ec7fa1c426b91a276773348e336cb64454c6ad78d11fcc8`. Full stage/timing evidence is in `fresh-install.json`; full per-case metrics and errors are in `semantic-evaluation.json`.

Next handoff: `docs/phase-7-testing.md` and `docs/backend-release-handoff.md`. Rules remain the default because the prototype classifier underperforms them. Warm timings measure only interpreter and retrieval on this small synthetic store; rejection-heavy hybrid timings must not be presented as a throughput advantage.
