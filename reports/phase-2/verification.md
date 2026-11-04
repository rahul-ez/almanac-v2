# Phase 2 verification — 4 November 2026

Implemented locally on the existing `backend/phase-0-foundation` branch; no push/merge performed. API 0.3.0, Alembic 0003, strict event baseline `events-rules-v1`, synthetic campus event seed v1.

Verified:

- Additive migration from 0002 to 0003, preserving earlier demo/account/profile records.
- Campus event seed applied twice without overwriting existing records.
- `make test`: **29 passed**. Includes Phases 0–1 plus real PostgreSQL event semantics, validation/authorization/CSRF, audit records, invalid-update rollback, explicit eligibility/unknown price, half-open interval boundaries, deadlines/drafts, bounded cursor queries and literal injection-like inputs.
- Concurrent admin updates with the same version produce one 200 and one 409. Concurrent duplicate assistant requests from different sessions produce the same single turn/response.
- Assistant ownership rejects another student's conversation ID; same request ID/different payload is 409; identical retry returns the old snapshot after cancellation while a new request excludes the cancelled event.
- Empty-database migration/metadata/downgrade/upgrade check passes, using a temporary database removed afterward.
- `make contract-check`: committed OpenAPI and 25 shared fixtures pass Pydantic and JSON Schema validation.
- `make acceptance PHASE=2`: real HTTP admin create -> student structured search -> rule-based natural-language search -> retry -> admin edit -> stale-edit conflict -> cancel -> fresh retrieval -> prior snapshot -> archive all passed. Synthetic acceptance records are archived, not erased; earlier data is preserved.
- Phase 0 live acceptance still passes after the schema update. Phase 1 regression walkthrough is also retained and run at handoff.
- `make query-demo` and `make parse-demo`: fixed 4 November 2026 reference-clock scenarios produce the expected event/meaning and campus-local week boundaries.
- Browser check: local account file loaded without credential output; admin created a synthetic event through the form (201), student natural-language query returned that record (200), admin cancellation succeeded (200), and the synthetic browser record was archived. Browser console showed no warnings/errors during the event query. JavaScript syntax validation (`node --check`) passed.

The existing Starlette/httpx test-client deprecation warning remains. No failed checks remain. CI is updated for all checkpoints but has not run remotely.

Scope limits: this is an event-only rule baseline, not a trained three-domain NLP model. Questions are independent; follow-up/clarification/history/saved interfaces remain later work. Minimal owned conversations/turns exist now for retry-safe snapshots. Currency is INR, event types are bounded, and interest ranking is deferred; none of these limitations imply support for omitted filters. Chat is bounded to 20 cards with an explicit truncation warning. Future academic evaluation must use frozen question splits, records, clock and model metadata.

Manual test instructions: `docs/phase-2-testing.md`; localhost test bench: http://localhost:8000/. Next planned checkpoint: rooms.
