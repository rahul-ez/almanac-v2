# Backend phases and independent acceptance testing

Status: Phases 0–2 are implemented locally; Phases 3–7 remain planned. See `phase-2-testing.md` for the latest runnable checkpoint.
Reviewed against all four repository planning documents at commit `b7e9c2a7b0a41e68073bd45244726a3554a416fb` on 4 November 2026.

This document supplements `backend-build-plan.md` and uses `build-plan.md` as the shared API/behavior source of truth. Frontend work continues separately. Each phase must be demonstrable without React or a browser UI; final browser integration remains a separate release check.

The updated two-person ownership split and integration tickets are in [two-person-backend-handoff.md](two-person-backend-handoff.md). The frontend is now on main; live contract reconciliation is its first parallel task.

## Working agreement

- Build one phase at a time. Deliver its setup steps, sample requests, expected results, automated checks, and known limitations so the user can test it before the next phase starts.
- Keep each phase runnable on its own at its delivered revision. Later phases also run regression checks for earlier behavior.
- Retain Python/FastAPI, PostgreSQL, versioned migrations, server-side cookie sessions, and `/api/v1` from the shared plan. Select and lock compatible dependency versions during scaffolding.
- Keep HTTP, domain services, and NLP separable. Both structured requests and language interpretation execute the same validated domain services.
- Do not add a public debug endpoint accepting arbitrary meaning objects. Test domain services directly; provide a local structured-query CLI for manual testing.
- Share committed OpenAPI and schema-valid fixtures with the frontend owner at every contract change. The backend acceptance gate does not depend on frontend availability.

## Phase map

| Phase | Deliverable | How the user tests it | Exit gate | Existing plan coverage |
| --- | --- | --- | --- | --- |
| 0 — Contract and runtime | API skeleton, configuration, PostgreSQL connection, initial migrations, explicit demo seed/reset, errors, OpenAPI and fixtures | Start dependencies/API; call health endpoints; inspect `/docs`; validate fixtures | Fresh setup works; liveness/readiness differ correctly; schema and fixtures agree | B0, initial B1 |
| 1 — Identity and permissions | Provisioned admin and two students, sessions, CSRF, logout, profile, reference data | Cookie-aware request script logs in each role and exercises allowed/denied calls | Sessions revoke; roles cannot be changed through profile; cross-user access and CSRF protections pass | B1–B2 foundation |
| 2 — Events vertical slice | Event schema/CRUD, eligibility, filtering, deterministic ranking, sources, cancellation, version conflicts | Admin creates an event; student lists/reads it; local structured query finds it; a small rule-based event question calls the same service | Create → retrieve → cancel → retrieve produces expected IDs/status; unknown eligibility stays unknown | B1–B3 events, narrow B5 baseline |
| 3 — Room scheduling | Rooms, bounded recurring bookings/exceptions, closures, opening hours, schedule coverage, transactional conflicts | Seed a timetable; query exact intervals through CLI; create/cancel conflicting bookings through API | Boundary, recurrence, coverage, and concurrent conflict cases pass | B1–B3 rooms |
| 4 — Faculty office hours | Faculty/aliases, bounded weekly office hours, dated cancellations/replacements | Create published hours via API; query slots through CLI; apply an exception and repeat | Exact slots change correctly; missing publication differs from no slots; name collisions remain ambiguous | B1–B3 faculty |
| 5 — NLP across all domains | Keyword baseline, TF-IDF/logistic regression, extraction, resolution, campus time, semantic validation, templated cards | Run parser CLI against fixed examples; send independent questions to assistant API | Three domains return valid interpretations/results; uncertainty cannot trigger broad queries; both methods are reproducible | B4–B5 |
| 6 — Conversations and personal records | Authoritative dialogue, clarification, history/deletion, saves, idempotency and turn concurrency | Multi-request scripts reuse conversation IDs, reply to clarifications, retry, switch users, update saved records | Follow-ups and privacy pass; retries create one turn; deletion removes turns/state; snapshots and current saves behave differently | B6, remaining B2 |
| 7 — Evaluation and release handoff | Frozen comparative evaluation, permission/domain regression suite, packaging, deployment instructions | Bootstrap an empty database; run acceptance/evaluation suites; repeat smoke checks on deployment | Critical deterministic tests pass; metrics and limitations reported; fresh setup and model loading reproducible | B7–B8 |

Phase numbers are delivery checkpoints, not promises of equal effort. Room recurrence and dialogue concurrency will likely require more work than the runtime foundation. Estimate duration after Phase 0 verifies the local tooling and Phase 1 establishes authentication.

## Testing tools delivered during implementation

Setup, Phases 0–2 acceptance, event query/parser demos, test and contract targets are implemented. Full model evaluation remains a later phase:

| Interface | Intended command/access | Purpose |
| --- | --- | --- |
| Setup | `make bootstrap`, `make migrate`, `make seed-demo`, `make dev` | Documented installation and explicit repeatable data provisioning; startup never resets records |
| Interactive API | FastAPI `/docs` | Explore schemas and individual calls; command-line scripts remain authoritative for cookie/CSRF flows |
| Phase acceptance | `make acceptance PHASE=2` | Run that phase's ordered manual-equivalent API/service scenarios and print pass/fail with actual IDs/statuses |
| Automated regression | `make test` | Unit/domain tests plus PostgreSQL-backed integration, permissions, and contract checks |
| Structured query | `make query-demo CASE=room-boundary` | Exercise a validated meaning object directly against real services/database; isolate retrieval from language understanding |
| NLP inspection | `make parse-demo CASE=events-this-week` | Show intent, spans, normalized filters, provenance, and clarification needs locally |
| Contract export | `make contract-check` | Export OpenAPI, compare with committed schema, validate fixtures |
| Academic evaluation | `make evaluate` | Evaluate baseline/hybrid on frozen split, records, clock and model metadata |

Use pytest for meaningful automated behavior checks and a cookie-aware CLI client for repeatable API walkthroughs. Provide a checked-in `.http` request collection or curl examples for manual exploration. Login walkthroughs must fetch CSRF state, retain cookies, and send the required token and origin; do not weaken authentication for testing convenience.

Acceptance scripts must call the running backend and real PostgreSQL for persistence/permission claims. Mocked response fixtures verify the contract but do not prove backend correctness. Run destructive reset only against an explicitly selected disposable test/demo database, with safeguards against using another database.

## Fixed demo scenario and expected evidence

Use a versioned, visibly labeled demo dataset and a documented reference clock, initially `2026-11-04T10:00:00+05:30`, campus zone `Asia/Kolkata`. Inject the clock into tests and local demo execution; HTTP clients cannot set server time. Normal runtime uses the real server clock. Keep the test clock clearly identified in demo output.

| Area | Minimum scenario | Expected observation |
| --- | --- | --- |
| Contract/runtime | Database unavailable; then restored | Liveness remains healthy while process runs; readiness fails then recovers; errors do not claim no results |
| Identity | Anonymous, student A, student B, admin | Protected call 401; student admin call 403; another student's conversation 404; authorized call succeeds |
| Sessions | Missing CSRF; invalid origin; logout followed by reuse | Mutations rejected; revoked session cannot authenticate |
| Events | Free ML workshop for year 2 in the reference week; restricted and unknown-eligibility examples | Expected IDs and eligibility reasons; unknown price differs from free; cancellation removes event from active search |
| Updates | Two admins submit edits using the same prior version | First edit succeeds; second returns 409 without overwriting it |
| Rooms | Booking 14:00–15:00; request 15:00–16:00 versus 14:59–16:00 | First interval can qualify if all other conditions hold; second conflicts |
| Room limits | Coverage gap, closure, outside opening hours, recurrence cancellation | Gap reported as unknown; closure/hours exclude room; cancelled occurrence releases its interval when otherwise covered/open |
| Faculty | Two similar names; published slot; dated cancellation/replacement | Ambiguous identity requires selection; cancelled slot removed; replacement shown at its new time |
| Language | “Any ML workshops for second years this week?” | Week resolves to 2 November 00:00 through 9 November 00:00 in campus time; correct meaning and records |
| Uncertainty | Missing room interval; unsupported placement query; compound question | Clarification or unsupported result, HTTP 200; no accidental unfiltered answer |
| Dialogue | “Workshops this week” → “Only Friday” → room question | Friday 6 November retains workshop type; room domain discards event-specific fields and requests missing room slots |
| Retry/concurrency | Same user/request ID/payload twice; then changed payload | Same completed response with one stored turn; changed payload returns 409; concurrent turns cannot corrupt state |
| Personal data | Save event, update/cancel it, reopen old conversation, delete conversation | Save shows current event; old answer stays a timestamped snapshot; deleted conversation's turns/state are removed |

Every phase handoff includes exact commands, request payloads, expected status/result IDs, current contract revision, seed version, test output, and limitations. Save this evidence under `reports/phase-N/` when implementation exists. Never label a command or acceptance case as passed before running it.

## Dependencies and sequencing details

Start the 60–90-question annotation pilot during Phase 2 and grow the corpus while room/faculty services are built. Use the original 400–600-question and 30–50-dialogue targets as planning targets. Review labels and double-annotation before scaling collection. Group paraphrase families and whole conversations before splitting; freeze final test data before tuning the hybrid pipeline. Phase 7 reports the final comparison; evaluation tooling starts in Phase 5.

Phase 2 deliberately includes a narrow rule-based event question so the first useful language-to-data slice is available early. Label it as a baseline, with unsupported language handled explicitly. It is not evidence of full NLP quality. From the first assistant request, enforce ownership and request-ID deduplication and persist the minimal turn/response snapshot needed to honor the shared retry contract; Phase 6 adds full dialogue behavior and history APIs. Do not expose an assistant implementation that promises conversation features it does not support.

Readiness checks reflect the selected implementation: early baseline mode requires its configuration and database; hybrid mode additionally requires its compatible trusted model artifact. No silent fallback from a missing hybrid model to a baseline. Mock fixtures are explicit contract artifacts, never a fallback after a live error.

Before starting Phase 0, settle exact meaning/card schemas, CSRF wire format, supported admin payloads, and reproducible demo IDs through committed schemas/fixtures. Preserve shared precedence: current explicit text > current override > compatible conversation > profile > documented default. Keep half-open intervals, unknown eligibility/coverage, source timestamps, bounded results and explicit truncation warnings throughout.

Final backend acceptance is possible without the frontend. A separate joint browser gate must still validate credentialed requests, same-origin deployment, actual card rendering, and UI workflows before calling the complete application released.

## Current next action

Run the Phase 2 walkthrough in `phase-2-testing.md`. The next implementation checkpoint is Phase 3 (room scheduling), after user testing of events.
