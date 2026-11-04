# Two-person build and integration plan

Based on `project-overview.md`. The repository currently contains the overview, with no application implementation. All architecture and estimates below are proposed decisions, not existing functionality.

Read this first, then use your workstream:

- [Frontend build plan](frontend-build-plan.md)
- [Backend, database, and NLP build plan](backend-build-plan.md)

## 1. Recommended split

Yes: split frontend and backend, but connect them throughout development. Waiting until both are finished makes incompatible assumptions expensive to fix.

| Responsibility | Person A: frontend lead | Person B: backend/NLP lead |
| --- | --- | --- |
| Student and admin interfaces | Own | Review behavior |
| Browser API client, mocks, accessibility | Own | Supply contract and fixtures |
| Authentication, permissions, persistence | Integrate UI | Own server behavior |
| Campus data, availability, API | Review usability | Own |
| NLP corpus | Own collection, initial annotation, ambiguity examples | Own schema, adjudication, split and training |
| NLP models and semantic execution | Help with examples | Own |
| Evaluation | Own end-to-end cases and error analysis write-up | Own metric scripts and model comparison |
| Integration and demonstration | Joint | Joint |

The backend track is heavier. Person A must reserve roughly a quarter of their time for data annotation, system evaluation, and documentation. Simplify visual polish before cutting the NLP evaluation.

## 2. Scope and assumptions

Deliver one campus, English questions, one configurable campus time zone (initial proposal: `Asia/Kolkata`), student and admin roles, and three retrieval domains: events, scheduled room availability, and published faculty office hours.

Required: login, profile context, assistant, structured answer cards, clarification, constrained follow-ups, private history with deletion, saved records, admin maintenance, reproducible NLP evaluation, and a working demonstration.

Defer placements, scraping, notifications, actual room reservation by students, multiple campuses, additional administrative roles, unrestricted conversations, and generative LLM answering. A pretrained encoder comparison is optional after the baseline and complete app work.

Use provisioned demo accounts initially; public registration, email verification, and password recovery are outside the first demonstration. Demo data must be visibly labeled. Obtain authorized campus records when available.

## 3. Proposed architecture

| Layer | Recommendation | Reason |
| --- | --- | --- |
| Frontend | React + TypeScript, Vite build | Independently runnable client; typed API boundary |
| Backend | Python + FastAPI | Keep API and NLP in one language and process initially |
| Data | PostgreSQL, versioned migrations | Shared relational data and explicit constraints |
| NLP | scikit-learn TF-IDF classifier plus deterministic extraction/resolution | Measurable baseline with controlled execution |
| Communication | Versioned JSON HTTP API under `/api/v1` | Straightforward fixtures and integration |
| Authentication | Server-side sessions, secure HTTP-only cookie | Central session revocation and role enforcement |
| Hosting | One browser origin; reverse proxy `/api` to backend | Simplifies session behavior in the final demo |

The React documentation describes a Vite/TypeScript starting point. FastAPI response models provide validation and OpenAPI schemas. scikit-learn recommends splitting before fitting preprocessing and using pipelines to avoid leakage. These capabilities were checked through Context7; pin compatible dependency versions when scaffolding, rather than treating any unverified version as required.

References: [React setup](https://react.dev/learn/build-a-react-app-from-scratch), [FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/), [scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage).

```text
Student/admin browser -> API authentication and validation
                         |-> CRUD services -> PostgreSQL
                         |-> NLP -> validated meaning -> query services
                                                      -> answer templates
Offline annotated corpus -> training/evaluation -> versioned model artifact
```

Model training is offline. Load the selected trusted model at application startup; do not retrain during requests. The frontend neither runs NLP nor decides eligibility or room availability.

## 4. Repository and ownership

```text
frontend/                 Person A
backend/                  Person B; includes runtime NLP modules
contracts/                Joint review; Person B maintains API schema
  openapi.json
  fixtures/
data/
  demo/                   Person B, reviewed by Person A
  annotations/            Person A collects; Person B validates
  splits/                 Person B freezes manifests
experiments/              Person B; offline training and evaluation
reports/                  Joint evaluation and academic report
docs/                     Joint plans, setup, demo instructions
```

These are target directories, not scaffolded application files. Keep secrets, real private histories, local databases, and large model artifacts out of version control. Keep reproducible dataset/model metadata and acquisition instructions in version control.

Use one repository, separate local clones, and short feature branches. Examples: `frontend/assistant-cards`, `backend/event-search`. Review and merge working increments into the shared main branch at least every one or two work sessions. Avoid two long-lived branches that meet only at the end. Root configuration and contract changes need the other person's review; each owner controls their own dependency lockfile.

## 5. Shared contract: agree before implementing screens

Person B defines request/response schemas and exports OpenAPI. Person A reviews their rendering needs. Check that the exported schema matches the committed contract in CI. Validate shared fixtures against the schema, and keep frontend types aligned with it. Contract changes include updated fixtures and affected client code in the same integrated change.

### Common conventions

- Opaque string IDs; API field names use `snake_case`.
- Offset-bearing ISO 8601 timestamps; store instants in UTC and interpret user dates in campus time. Recurring schedules also retain local wall-clock time and time zone.
- Intervals use inclusive start and exclusive end: `[start, end)`.
- Lists use `{items, next_cursor}` with a bounded `limit`; stable ordering breaks ties by ID.
- `null` means unknown/not supplied, never automatically zero, false, or unrestricted.
- Amounts use integer minor units plus currency. Unknown cost differs from a free event.
- Errors use `{error: {code, message, field_errors, request_id}}`; never return SQL, stack traces, or secret data.
- HTTP 401 means unauthenticated, 403 unauthorized, 404 absent/inaccessible record, 409 conflicting update, 422 malformed input, 429 rate limit, and 5xx service failure.
- Valid NLP outcomes, including clarification and unsupported questions, return HTTP 200. A service failure is not a no-results response.

### Endpoint inventory

All paths below are relative to `/api/v1`.

| Area | Endpoints | Purpose |
| --- | --- | --- |
| Session | `GET /auth/csrf`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` | Session, CSRF initialization, server-assigned role |
| Profile | `GET /me/profile`, `PATCH /me/profile` | Department, year, section, interests |
| Reference data | `GET /reference-data` | Departments, buildings, topics, supported years |
| Assistant | `POST /assistant/query` | New question, follow-up, or clarification reply |
| History | `GET /conversations`, `GET /conversations/{id}`, `DELETE /conversations/{id}` | Owned conversation retrieval/deletion |
| Saved | `GET /me/saved`, `PUT /me/saved/{kind}/{id}`, `DELETE /me/saved/{kind}/{id}` | Idempotent save/remove and current record view |
| Student data | `GET /events`, `GET /events/{id}`, `GET /rooms/{id}`, `GET /faculty/{id}`, `GET /faculty/{id}/office-hours` | Home events and detail views |
| Admin | Collection `GET/POST`, item `GET/PATCH/DELETE` under `/admin/{resource}` | Maintain campus records |
| Operations | `GET /health/live`, `GET /health/ready` | Process and dependency/model readiness |

Admin resources: `events`, `rooms`, `bookings`, `booking-exceptions`, `room-closures`, `faculty`, `office-hours`, `office-hour-exceptions`, and `aliases`. Opening hours and schedule coverage metadata belong to room records. Bookings and office hours support bounded weekly recurrence and dated exceptions; cancellations are explicit status updates. DELETE archives referenced domain records; history deletion actually removes the student's stored turns/state. Bulk import is optional and comes after forms.

### Assistant request

```json
{
  "text": "Any ML workshops for second years this week?",
  "conversation_id": null,
  "client_request_id": "opaque-request-id",
  "context_overrides": {"year": 2},
  "clarification": null
}
```

The backend infers user identity from the session, obtains the clock itself, and validates context overrides. Repeating a request ID with the same authenticated user and payload returns the prior response; a different payload with that ID is a conflict. This prevents duplicate history after retries. An existing conversation must belong to that user.

For clarification replies, send `clarification: {"id": "...", "option_id": "..."}` or a text answer with that clarification ID. Only the active clarification for this conversation is valid.

### Assistant response schema to formalize on day one

| Field | Meaning |
| --- | --- |
| `conversation_id`, `turn_id`, `request_id` | Identity and troubleshooting |
| `status` | `answered`, `no_results`, `clarification_required`, `unsupported`, `information_unavailable` |
| `intent` | `find_events`, `find_available_rooms`, `find_faculty_office_hours`, or null |
| `message` | Template-based readable summary |
| `interpreted_query` | Validated intent and normalized filters; no SQL |
| `applied_context` | Each effective value and origin: explicit question, override, profile, prior turn, or default |
| `results` | Discriminated union of event, room-availability, or office-hour cards |
| `clarification` | Null or `{id, field, prompt, options: [{id, label}]}`; options may be empty for free text |
| `answered_at`, `campus_timezone` | Query timestamp and display zone |
| `warnings`, `data_coverage` | Missing/stale coverage and scheduling limitations |
| `next_cursor` | Null or a cursor bound to this result/query; define retrieval before adding pagination to chat |

For the first chat implementation return a bounded result set and an explicit truncation warning; keep `next_cursor` null until a follow-on retrieval contract exists. Do not silently imply an exhaustive list.

Every card has `kind`, `record_id`, `title`, `source_label`, optional approved `source_url`, and `record_updated_at`. Add:

- Event: start/end, venue, topic/type, cost/currency, eligibility rules and result (`eligible`, `ineligible`, `unknown`), deadline, cancellation state, saved state.
- Room availability: building, capacity, facilities, requested interval, schedule coverage, and explicit `availability_basis: "scheduled_bookings"`.
- Office hours: faculty identity, location, concrete meeting interval, applicable exception, and source.

Event eligibility filters use explicit rules. Interests influence ordering only. An unknown eligibility rule or incomplete student profile must never imply eligibility.

### Fixtures required before either side waits on the other

Create one realistic, schema-valid fixture for each: event answer, room answer, office-hours answer, no matches, missing coverage, ambiguous faculty, missing room interval, follow-up filter change, unsupported request, expired login, validation error, and backend outage. Include changed/cancelled saved items and historical snapshots in later fixtures.

Person A builds against these fixtures. Person B implements the same schemas. Switch the API adapter from mock to live without rewriting page components. Mock mode must be explicit and visibly labeled; never fall back to mocks after a live API failure.

## 6. Shared behavior decisions

1. Initial intents are the three domain queries plus unsupported. Clarification and follow-up are dialogue actions, not necessarily classifier labels.
2. Precedence: current explicit statement > current override > compatible conversation state > profile > documented default. Preserve provenance. A new domain resets incompatible filters.
3. Resolve `this week` as Monday 00:00 through next Monday 00:00 campus time. Bare ambiguous dates/times and multiple faculty matches require clarification.
4. For `right now`, propose a configurable next-30-minute interval and show that assumption. If no interval or such phrase exists, ask. Bound room search to a configurable horizon (initially 30 days).
5. Room availability requires open hours, adequate timetable coverage, no overlapping booking, and no closure. Missing timetable coverage means unknown. No booking is not proof of physical vacancy.
6. Faculty availability comes only from published office hours after exceptions. No class schedule inference.
7. Old conversation answers remain timestamped snapshots. A refresh or resumed follow-up runs against current records. Saved items reference current records and display cancellation/archive status.
8. Distinguish a valid query with zero matches from missing records/coverage, ambiguity, unsupported requests, and service failure.
9. Admin status is assigned server-side; clients cannot elevate roles. Student data and conversation access always use authenticated ownership checks.

## 7. Milestones and schedule

Illustrative schedule: six weeks at approximately 15–20 focused hours per person per week. This is a planning estimate, not a commitment; revise after the first milestone. Each row ends with an integrated demonstration.

| Milestone | Person A | Person B | Exit gate |
| --- | --- | --- | --- |
| M0: first joint session | Screen inventory, response review, fixture needs | Meaning schema, data model, API contract | Agree behavior, roles, ownership, seed examples |
| M1: week 1 | App shell, login/profile, mock assistant, start corpus | Database, sessions, seeds, stub/real event endpoint | Browser logs in and renders a live seeded event response |
| M2: week 2 | Event cards/admin, annotate corpus, conversation layout | Event CRUD, event NLP baseline, validated query execution | Admin adds event; student finds it with natural language |
| M3: week 3 | Room and faculty screens/forms | Room intervals/recurrence/coverage, office-hour exceptions, domain extraction | Three domains work with boundary fixtures |
| M4: week 4 | Clarification, context chips, history, saved items | Dialogue state, history/saved persistence, classifier integration | Follow-up and clarification persist across refresh |
| M5: week 5 | Browser workflows, accessibility, failure cases, report | Frozen evaluation, authorization tests, performance/error fixes | Evaluation report and critical scenario suite complete |
| M6: week 6 | Demo walkthrough, usability fixes, screenshots | Deployment, migration/seed verification, reproducibility | Fresh setup works; both can run the final demo |

Critical path: agreed contract -> seed records and sessions -> event vertical slice -> all domain semantics -> dialogue -> frozen evaluation -> demo. Frontend pages can proceed with mocks, but these integration gates cannot be postponed.

If time shrinks, drop the encoder experiment, rich dashboard, bulk imports, advanced filters, and visual polish first. Keep the three domains, semantics, permission checks, and evaluation. Any further scope reduction should be an explicit change to the project overview.

## 8. Integration routine and release gate

- Start each session with a brief update: completed work, contract changes, blockers, next integration target.
- End each milestone by running against the same seeded dataset and campus clock assumptions.
- Review schema changes together before either side updates dependent code.
- Keep an issue per deliverable with owner, dependency, acceptance criteria, and evidence.
- CI should run frontend type/build checks, backend domain/permission tests, contract/fixture validation, and a small browser smoke flow. Full NLP experiments are reproducible offline jobs, not a training run on every UI commit.
- Test a fresh database with migrations and seeds; document startup, required environment variables, model acquisition, and demo credentials supplied through a safe setup mechanism.
- Deploy a working build with explicit demo-data labels, persistent database, HTTPS, secure sessions, narrowly configured origins, migrations, and sanitized operational logs. Run the same smoke flow on the deployed origin.

Minimum release scenarios:

1. Student login, profile edit, and logout work; a student cannot access admin APIs.
2. An admin creates/edits/cancels an event; answers and saved items reflect changes.
3. Natural-language queries return correct records in all three domains.
4. An ambiguous name prompts selection; a missing interval prompts a question.
5. A follow-up changes one filter while retaining compatible ones; switching domains resets inappropriate context.
6. Back-to-back bookings do not overlap; closures and timetable gaps are respected.
7. Office-hour exceptions override recurrence.
8. Histories are private and deletable; another student's IDs do not grant access.
9. Network/service errors are distinguishable from no results; retries do not duplicate turns.
10. Academic results are reproducible from fixed splits, clock, seed database, and model metadata.

## 9. Start today

Spend the first 60–90 minutes together approving M0. Then Person A builds the shell and event response UI while drafting annotation examples; Person B creates the API schemas, seeded event records, and session foundation. Reconnect at the end of the session to render one API response in the browser. The first full slice is: admin enters event -> student asks a question -> matching event card appears.
