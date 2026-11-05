**Current local release:** live integration is now implemented via `frontend/src/api/live.ts` and verified against the real backend. Start the combined app with `make local` at the repository root; see `docs/local-demo.md`. The proposal details below remain historical/mock references.

# Person A handoff

The client is independently runnable and has no dependency on a backend for demo development. Live integration remains unverified because this repository has no Person B implementation. All service assumptions are expressed in runtime schemas and the generated `contracts/openapi.json` proposal.

## Completed frontend deliverables

| Plan | Delivered |
| --- | --- |
| F0 | Pinned React/TypeScript/Vite setup, feature folders, credentialed HTTP client, CSRF, request IDs, cancellation, runtime response validation, explicit mock/live modes, shared fixtures, responsive components and role-aware shell |
| F1 | Login, session restoration/expiry, logout, demo entry, reference-backed profile and interests, unsaved-change protection, home questions and upcoming events |
| F2 | Composer, safe retries and interrupted-request recovery, all three record cards, eligibility/cost distinctions, source/time metadata, distinct NLP outcomes and service errors, truncation/coverage notices |
| F3 | Server conversation IDs, context provenance and clearing, option-ID/free-text clarification, refresh/new conversation, serialized UI submissions and recovery reads before retry |
| F4 | Paginated/searchable loaded history, immutable snapshots, continuation, deletion, paginated saved records and kind filters, current status, synchronized bookmark controls |
| F5 | Searchable/paginated lists and dedicated forms for all nine resources, recurring schedules, dated exceptions, coverage/opening hours, field validation, conflict feedback, versioned edits, cancellation/archive confirmation |
| F6 | Annotation guidelines, 60 explicitly synthetic drafts, six dialogue drafts, fixed-clock/record expected cases, browser scenario suite and categorized frontend error analysis |
| F7 | Type/build checks, contract validation, integration tests, desktop/mobile browser workflows, setup/deployment assumptions, demo script, CI workflow |

Human student collection/consent, independent double annotation and adjudication, corpus expansion, backend permission enforcement, model metrics, and live deployment checks remain joint/backend work. The synthetic pilot has no frozen test split and supplies no accuracy claim.

## Contract decisions to adopt or revise with Person B

- Base path is `/api/v1`; snake_case fields and opaque string IDs follow the shared plan.
- `GET /auth/csrf` returns `{csrf_token}`. Login returns the authenticated `User` directly. Mutations include `X-CSRF-Token`; logout may return 204. Server cookie identity is authoritative.
- Reference data includes departments/buildings/topics/facilities as `{id,label}`, supported years, and `campus_timezone`.
- Student detail endpoints return typed cards. Faculty cards use `kind: faculty`, because faculty is the saved target; they include concrete `meeting_interval` when answering office-hour questions.
- Every card includes `record_status` in addition to source/update metadata. This permits cancelled/archived current saves without confusing a historical answer with the present record.
- Saved entries are `{kind,record_id,saved_at,record}`. `record` can be null when unavailable. Saving a room/faculty record does not retain an availability claim.
- The runtime `applied_context` is a map of field to `{value,origin}`. A null override explicitly clears a filter and must not immediately refill it from profile state.
- Event eligibility uses `eligibility_mode: unknown | all_students | restricted` with explicit department/year arrays. Unknown cost is null; free is 0 integer minor units. The backend computes card eligibility.
- Room records carry local weekday opening intervals, bounded instant coverage, and completeness metadata. Booking recurrence is `none | weekly` with an inclusive `recurrence_until` local date. Office-hour rules have weekday/local start/end, IANA timezone, and effective dates.
- Exceptions name a parent rule, original occurrence date, `action: cancel | replace`, optional replacement instants, and a public note. Replacement start/end are required when replacing.
- Edits send `version`; stale edits return 409. Archive DELETE sends `If-Match` with that version. Admin lists accept `search`, `cursor`, and bounded `limit`. Parent-record selects load paginated options.
- Requests deduplicate by user and `client_request_id`. Repeated identical payloads return the original answer; changed payloads return 409. No generic mutation is automatically retried.
- Assistant results are bounded; `next_cursor` remains null. Errors follow the shared structured envelope; outages never become empty results. Unsupported/clarification/no-results/unavailable are successful HTTP responses with distinct statuses.

## Live integration gate

1. Person B reviews this proposal and exports the backend schema. Resolve differences in both fixtures and client types together.
2. Configure `.env.local` for live mode and start the real backend/database with the agreed demo seeds.
3. Verify CSRF, login, role assignment, credentialed origin behavior, and session expiry in an actual browser.
4. Run admin creates event → student natural-language retrieval, then all three domains, recurrence boundaries, exceptions, clarification, follow-ups, saves, and deletion against maintained records.
5. Backend tests must independently verify CSRF, rate/input bounds, authorization/ownership, transactional schedule conflicts, semantic correctness, and persistence. Mock checks are not proof of backend security.
6. Validate migrations/seeds on a fresh database and smoke-test the deployed HTTPS origin. The frontend does not deploy a backend or create production accounts.

Backend merge note: frontend mock contract exports now live in `contracts/frontend-proposal/`. The implemented API in `contracts/openapi.json` is authoritative for live integration. This merge preserves mock behavior; client/schema alignment and end-to-end integration remain pending.
