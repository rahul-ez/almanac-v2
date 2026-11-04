# Backend, database, and NLP build plan — Person B

Use the [shared contract and integration plan](build-plan.md) as the source of truth. Implement an end-to-end event slice early; then add room and faculty semantics. Keep NLP independently testable from HTTP and the database.

## B0. Foundation and contract

- [ ] Scaffold the proposed Python API with pinned dependencies, configuration validation, and structured sanitized logs.
- [ ] Organize `app/api`, `schemas`, `auth`, `services`, `repositories`, `db`, `nlp`, and `tests`.
- [ ] Define API schemas, meaning schemas, enums, structured errors, and fixtures with Person A.
- [ ] Export OpenAPI, add contract checks, and provide a deterministic example response before the full model exists.
- [ ] Create database migrations and repeatable, explicitly labeled seed data.
- [ ] Separate demo reset commands from normal startup; never reset records automatically.
- [ ] Provide readiness checks for database and selected model artifact. Document environment variables with a secret-free example file.

Acceptance: a fresh checkout can migrate/seed the database and return a schema-valid event response to the frontend.

## B1. Data model

| Entity | Essential information and relationships |
| --- | --- |
| User/session | Identity, password hash, assigned role; hashed session token, expiry, revocation |
| Student profile | User ID, department, year, section, interests |
| Reference records | Departments, buildings, topics, facilities; canonical IDs |
| Event | Title, description, type/topics, venue, start/end, cost/currency, deadline, publication/cancellation state |
| Event eligibility | Explicit allowed departments/years and rule semantics; unknown distinct from unrestricted |
| Room | Unique room code, building, positive capacity, facilities, opening hours |
| Booking | Room, start/end, purpose/status, optional weekly recurrence and effective dates |
| Booking exception | Parent recurring booking, occurrence date, cancellation or replacement |
| Room closure | Room, concrete interval, reason |
| Schedule coverage | Room/data source, covered dates, completeness, update time |
| Faculty | Canonical name, department, published location and contact fields |
| Office-hour rule/exception | Faculty, local weekday/time, effective dates; dated cancellation/replacement |
| Alias | Entity type, alias text, canonical target; collisions may require clarification |
| Conversation/turn | Owner, ordered turn IDs, raw text, interpreted query, response snapshot, timestamps, model version |
| Dialogue state | Conversation intent, filters/provenance, pending clarification, last activity/version |
| Saved item | User plus target kind/ID, unique per target; current-record lookup |
| Admin audit | Actor, action, record ID, timestamp; exclude secrets |

Campus records carry source label/URL where appropriate, update time, optional validity/verification metadata, and edit version. Use database constraints for positive capacity, valid intervals, valid foreign keys, and uniqueness. Index common room/time, event/date, faculty, and owner/history lookups. Keep referential integrity for saved targets; use validated separate foreign keys or a shared resource identity rather than unchecked arbitrary IDs.

Start with weekly recurrence bounded by semester/effective dates. Expand only inside the requested bounded interval. An unrestricted recurrence engine is unnecessary for this version.

## B2. Authentication, permissions, and CRUD

- [ ] Provision demo accounts; hash passwords using a maintained password-hashing implementation.
- [ ] Implement expiring, revocable sessions and secure cookie configuration per environment.
- [ ] Provide CSRF protection for cookie-authenticated mutations, including the login flow; validate allowed origins and configure development credentials explicitly.
- [ ] Derive role/identity from the session, not body fields. Prevent profile updates from modifying roles.
- [ ] Enforce ownership on every conversation, turn, saved item, and profile lookup.
- [ ] Add input limits, pagination limits, login/query rate limits, and bounded query horizons.
- [ ] Implement reference data, profile, student detail reads, and all admin CRUD resources.
- [ ] Validate recurrence, intervals, deadlines, source links, eligibility fields, and referenced IDs.
- [ ] Use edit versions for optimistic concurrency and return 409 for stale writes.
- [ ] Reject conflicting room bookings transactionally, accounting for recurrence. Record closures even when they overlap bookings; closures still take precedence for availability.

Acceptance: anonymous, student, admin, and cross-student requests behave correctly through direct API calls; editing or cancelling an event changes subsequent retrieval.

## B3. Domain query services before NLP integration

Expose internal typed query functions that accept validated meaning objects. HTTP and NLP both call these services; never accept model-produced SQL.

**Events:** filter publication/cancellation, dates, topic/type, location, cost, and eligibility. Specify whether date filtering selects overlapping events (recommended) and show the actual start/end. Apply deterministic ranking: eligibility where requested, relevance, date, ID. Registration deadline and event end are distinct; an upcoming event can already have registration closed.

**Rooms:** a candidate must meet capacity/location/facility filters, lie wholly within opening hours and known schedule coverage, and have no active overlapping booking or closure. Overlap is `existing.start < requested.end AND existing.end > requested.start`. Expand recurrence with dated exceptions before testing overlap. A booking ending at 15:00 does not conflict with one beginning at 15:00. Return coverage limitations instead of treating missing schedules as availability.

**Faculty:** resolve faculty identity, expand published office-hour recurrence into the requested interval, then apply cancellations/replacements. No matching published information is different from a confirmed absence of slots. Faculty with similar names require clarification.

Acceptance: direct structured queries produce expected IDs and time intervals on a fixed seed database, including boundaries and exceptions, before classifier accuracy affects the result.

## B4. Corpus and annotation protocol

Initial target: approximately 400–600 carefully labeled questions, including around 100 or more per supported domain, plus unsupported/ambiguous questions and 30–50 short dialogue sequences. These are planning targets, not proof that a model is accurate. Start with a 60–90-example pilot to validate the labels.

Each annotation records:

- Example ID, anonymized provenance, original text, language.
- Intent and supported/unsupported status.
- Entity spans as original-text character offsets, entity types, normalized values, canonical IDs where appropriate.
- Expected structured interpretation and explicit assumptions.
- Fixed reference clock/time zone for relative dates.
- Conversation turns/context and expected clarification behavior where relevant.
- Paraphrase-family/conversation group IDs, split assignment, annotation version.
- Expected result IDs or intervals for end-to-end cases tied to a specific seed database version.

Entity types include department, year, section when meaningful, faculty, room, building, event type/topic, date, time interval, capacity, and cost constraint. Distinguish extracted spans from inferred/profile values.

Person A collects and drafts labels; jointly double-label at least 15–20% and adjudicate disagreements. Split by paraphrase family and entire conversation, approximately 70/15/15 with label coverage checks. Freeze the test set. Do not tune extraction rules, thresholds, alias heuristics, or models using test failures and still report that same set as untouched. A fixed campus alias catalog is allowed if its availability is declared consistently for all methods.

## B5. NLP pipeline and experiments

Implement each stage as a testable function with typed outputs and diagnostic metadata:

1. **Normalize:** normalize whitespace/case variants without destroying room codes, punctuation relevant to time, or original span offsets. Preserve an offset mapping if normalized text is used for extraction.
2. **Intent:** establish a keyword/rule baseline, then train TF-IDF plus logistic regression in a fitted preprocessing/classifier pipeline. Fit only on training data; tune on validation data.
3. **Extract:** use tested patterns and dictionaries for campus codes/names, years, amounts, capacities, dates, and time expressions. A learned entity recognizer is optional; evaluate the deterministic extractor honestly.
4. **Resolve:** map aliases to canonical IDs. Ambiguous candidates remain candidates. Conservative spelling correction must not silently select the wrong faculty or room.
5. **Interpret time:** use injected clock and configured campus time zone. Resolve relative dates to concrete boundaries. Ask about ambiguous times and invalid/reversed intervals.
6. **Compose meaning:** merge explicit entities with compatible dialogue/profile context according to shared precedence. Mark origins and missing slots.
7. **Validate:** enforce known intent/filter combinations, known IDs, interval limits, and domain rules. Reject unsupported combinations or clarify missing constraints.
8. **Execute:** call allowlisted parameterized query functions; never concatenate user text into SQL.
9. **Respond:** build deterministic messages and typed cards with sources, timestamps, coverage, and warnings.

Meaning objects should contain `intent`, normalized `filters`, `context_provenance`, `missing_fields`, `ambiguities`, and `unsupported_constraints`. The frontend receives safe, user-relevant interpretation fields, not internal SQL or training diagnostics.

Handle “free” by domain/context: cost for events versus unbooked interval for rooms; ask if context is insufficient. Detect multi-domain/compound requests and ask the user to choose one in the initial version rather than silently answering half.

Do not assume a classifier's maximum score proves support. Validate rejection thresholds against ambiguous/out-of-domain validation examples; combine them with missing-slot and unsupported-constraint checks. Report unsupported detection separately.

Acceptance: all three domains produce structured interpretations; malformed or uncertain interpretations never execute broad accidental queries; both baseline and hybrid runs are reproducible.

## B6. Dialogue, history, and saved records

- [ ] Store authoritative state per owned conversation; use versioning or serialize concurrent turns.
- [ ] Support narrowing a filter, replacing a date, clearing a filter, answering pending clarification, and switching domains.
- [ ] Bind clarification options to a server-created ID, conversation, expected field, and expiry. Reject stale or unrelated answers.
- [ ] Define an inactivity expiry for active dialogue context (proposed 30 minutes); retain historical snapshots while making expired context visible in responses.
- [ ] Apply new explicit values over previous state; carry only supported compatible fields.
- [ ] Save question, interpretation, response snapshot, answer time, and model version atomically with the completed turn where possible.
- [ ] Implement per-user request deduplication and handle partial failures without duplicate turns.
- [ ] Cascade conversation deletion through turns and state; omit raw questions from ordinary logs so deletion is meaningful.
- [ ] Resolve saves to current records; show archived/cancelled status. Never reuse an old availability answer as current truth.

Acceptance: persisted follow-ups work after page reload, expired states are handled predictably, repeated requests are safe, and user A cannot discover user B's history.

## B7. Evaluation and meaningful tests

| Measurement | Required output |
| --- | --- |
| Intent | Macro F1, per-class precision/recall/F1, confusion matrix, support counts |
| Entity extraction | Exact span-and-type entity precision/recall/F1; per-type breakdown |
| Normalization | Canonical ID/date/time accuracy with explicitly defined denominator |
| Meaning | Exact match of canonical structured query; exclude metadata/order differences |
| End-to-end | Correct result set/interval and response-status rate against frozen records |
| Dialogue | Correct state transition and clarification resolution on multi-turn cases |
| Unsupported/ambiguous | Rejection/clarification precision and recall, false-answer examples |
| Performance | Cold start and warmed query latency on documented hardware/dataset size |

Compare the keyword baseline and hybrid pipeline on the same split, records, and clock. Include an ablation without profile/dialogue context if feasible. A pretrained encoder experiment is optional and must not delay the required comparison. Report actual measured results even if they miss aspirational accuracy; never substitute training scores or a handful of demo queries.

Automated tests should cover:

- Time boundaries, campus-local midnight, week boundaries, recurrence end dates, and booking overlap/closures/coverage.
- Ambiguous faculty aliases, missing slots, contradictory filters, unknown eligibility, cancelled events, and office-hour exceptions.
- Profile and dialogue precedence, domain switching, clarification expiry, and concurrent/retried turns.
- Authentication/authorization, cross-user IDs, CSRF, input limits, save uniqueness, and deletion.
- Database migrations on an empty database, seed repeatability, and response/fixture schema validation.
- Injection-like inputs cannot alter query structure; operational failures never become empty-result answers.

Critical deterministic domain and permission cases must all pass. Choose model-quality targets after the pilot and validation analysis; freeze them before final test evaluation. Retain an error taxonomy: intent, extraction, resolution, time, context, query semantics, data coverage, or rendering.

## B8. Packaging and handoff

- [ ] Version model artifact, corpus, split manifests, label maps, configuration, and evaluation seed/clock.
- [ ] Load only trusted serialized artifacts. Fail readiness clearly if required artifacts are missing or incompatible.
- [ ] Document database startup, migration, seed import, API startup, training, and evaluation once commands exist.
- [ ] Record dependency lockfiles, runtime versions, environment variables, and artifact checksums.
- [ ] Verify final hosting origin, sessions, database persistence, and readiness with Person A.
- [ ] Deliver evaluation tables, representative errors, limitations, and a concise architecture description for the report.

The backend is complete when a fresh setup serves the real frontend, all three domains and dialogue work against maintained records, permission/domain checks pass, and the academic evaluation can be reproduced independently.
