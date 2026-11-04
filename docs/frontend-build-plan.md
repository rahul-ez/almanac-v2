# Frontend build plan — Person A

Use the [shared contract and integration plan](build-plan.md) as the source of truth. Your deliverable includes student UI, admin UI, typed API integration, corpus collection, and browser acceptance testing.

## F0. Foundation and independent development

Dependencies: agree M0 schemas, session behavior, enum values, and fixtures with Person B.

- [ ] Scaffold the proposed React/TypeScript app and pin dependencies.
- [ ] Organize `src/app`, `features/auth`, `features/assistant`, `features/history`, `features/saved`, `features/profile`, `features/admin`, `components`, and `api`.
- [ ] Build a central API adapter for credentials, CSRF headers, structured errors, cancellation, and request IDs.
- [ ] Provide explicit mock/live modes that share types and fixtures; document the selected mode.
- [ ] Create reusable form controls, status notices, cards, dialogs, pagination, and date/time display helpers.
- [ ] Establish spacing, typography, colors, focus states, keyboard behavior, and mobile layouts.
- [ ] Implement role-aware navigation and page loading/error boundaries. Frontend guards improve UX; backend permissions remain authoritative.

Acceptance: frontend runs without backend using fixtures and builds successfully; live mode can render a response without changing components.

## F1. Login, navigation, and profile

Routes: `/login`, `/app`, `/app/profile`; admin shell at `/admin`.

- [ ] Login form, invalid-credential feedback, pending submission, logout, and expired-session handling.
- [ ] Restore identity from `/auth/me` on refresh and navigate using the server role.
- [ ] Profile fields: department, year, section, optional interests; load options from reference data.
- [ ] Distinguish unknown profile fields from defaults; explain their effect on answers.
- [ ] Save validation, unsaved-change handling, and success feedback.
- [ ] Home view: question input, example questions, relevant upcoming events, compact saved-event summary if time permits.

Acceptance: both roles reach their correct workspace; profile changes survive reload; expired login preserves unsent question text where practical.

## F2. Assistant and answer cards

Route: `/app` and optionally `/app/conversations/:id` for a selected conversation.

- [ ] Conversation list of user questions and structured assistant turns; multi-line composer with clear submit behavior.
- [ ] Pending state and double-submit prevention. Retry transient failures with the same request ID; do not auto-retry mutations indiscriminately.
- [ ] Event cards: venue, dates, price/unknown price, eligibility and its basis, deadline, cancellation, source, update time, save control.
- [ ] Room cards: building, capacity, facilities, requested interval, schedule coverage, and the scheduling-based availability limitation.
- [ ] Faculty cards: resolved faculty identity, published slot, location, exception notes, source.
- [ ] Separate views for no matches, unknown information, unsupported requests, and server/network errors.
- [ ] Display answered time separately from record update time.
- [ ] Show truncation and partial-coverage notices. Never infer completeness from the number of cards.
- [ ] Render text safely and restrict source links to acceptable protocols.

Acceptance: every response fixture has a useful readable view on desktop and mobile, including empty and failed states. A screen reader can identify new results without moving keyboard focus unexpectedly.

## F3. Clarifications and context

- [ ] Show effective context as readable filters with origin labels where useful: profile, prior turn, explicit question, default.
- [ ] Allow changing/clearing supported context through new requests, without silently updating the permanent profile.
- [ ] Render clarification options using IDs; support free-text replies when options are absent.
- [ ] Handle expired clarification IDs and deleted conversations gracefully.
- [ ] Add clear new-conversation action and preserve compatible follow-ups through the server conversation ID.
- [ ] Prevent overlapping submissions in one conversation for the initial version.
- [ ] On network cancellation, reload conversation state before retrying; aborting a browser request does not guarantee server rollback.

Acceptance: “workshops this week” -> “only Friday” changes only the intended filter; duplicate faculty names can be resolved; a domain switch does not retain an irrelevant event filter.

## F4. History and saved records

Routes: `/app/history`, `/app/saved`.

- [ ] Paginated history list with title/first question and timestamp.
- [ ] Reopen history as original answer snapshots; label them as historical.
- [ ] Continue a conversation and provide a fresh-query action for current information.
- [ ] Delete confirmation and empty state; clear local state when deletion succeeds.
- [ ] Save/unsave events, rooms, and faculty records using stable IDs. Saving a room does not save a claim that it remains available.
- [ ] Display current saved-record details and cancelled/archived/unavailable status.
- [ ] Reconcile saved-state changes across assistant cards and saved list.

Acceptance: reload preserves history and saves; deleting one conversation does not affect another; changed saved events show current data while old answer snapshots remain unchanged.

## F5. Admin workspace

Build simple searchable lists and dedicated edit forms before elaborate calendars. Reuse form patterns but keep domain fields explicit.

| Screen | Required controls and validation |
| --- | --- |
| Events | Title, description, topic/type, venue, start/end, cost/currency, eligibility, deadline, source, status |
| Rooms | Room code, building, capacity, facilities, local opening hours, schedule coverage metadata |
| Bookings | Room, purpose, start/end, one-off or weekly bounded recurrence, dated cancellation; conflict feedback |
| Room closures | Room, interval, reason; closures override availability |
| Faculty | Name, department, location/contact fields approved for publication, aliases |
| Office hours | Faculty, location, weekly schedule/effective dates; dated cancellations or replacement hours |
| Aliases | Canonical record, alternative spelling/name; collision feedback |

- [ ] Lists include search/filter, pagination, empty/loading/error states, and clear create/edit actions.
- [ ] Show local time zone next to date/time controls and recurrence previews.
- [ ] Surface backend field errors and conflict responses next to affected inputs.
- [ ] Warn before cancelling/archive operations; explain impact on visible student records.
- [ ] Include an update version in edits and offer reload on conflict instead of overwriting another admin's changes.
- [ ] After mutation, refresh affected lists/details and verify the student answer changes.

Acceptance: admins can create every record required for a realistic demo without editing the database manually. Invalid intervals and conflicting edits produce actionable feedback.

## F6. Dataset and evaluation responsibilities

- [ ] Co-write annotation guidelines with Person B before collecting a large corpus.
- [ ] Collect questions across all domains, unsupported requests, ambiguity, typos, and follow-up sequences. Obtain consent and remove identifying information.
- [ ] Annotate original-text spans, normalized values, intent, expected meaning, and clarification requirements.
- [ ] Assign paraphrase-family and conversation IDs to support leakage-safe splitting.
- [ ] Double-annotate a shared sample and resolve disagreement before continuing.
- [ ] Write expected end-to-end results against the fixed demo database.
- [ ] Run the browser scenario suite and write a categorized error analysis with examples.
- [ ] Keep final test examples out of iterative training/debugging after the split is frozen.

## F7. Verification and handoff

Automate behavior that spans components: login/session expiration, assistant success and failure, clarification/follow-up, history privacy UX/deletion, saved-state updates, and admin create-to-query flow. Backend tests separately enforce permissions.

Check keyboard-only navigation, readable labels/errors, focus after dialogs, narrow viewport layouts, long titles, missing values, and campus time display. Run type checks and production build. Use deterministic fixtures for browser checks and a small live smoke suite for integration.

Deliver: complete interface, API adapter, schema-aligned fixtures/types, representative browser tests, setup instructions, dataset annotations, error-analysis contribution, and a demo script. Do not spend the last week replacing the visual system.
