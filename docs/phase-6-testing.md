# Phase 6 — conversations, clarification, history and saves

This checkpoint extends the existing conversation/turn tables with server-owned context, active clarifications and owned history APIs. It adds saved references to current records. Default runtime remains the rule interpreter at [localhost:8000](http://localhost:8000/); prototype hybrid mode remains optional.

## Start and verify

From the repository root:

```sh
make migrate dev
make acceptance PHASE=6
make test contract-check
```

If the API was already running while code changed, reload its process with `docker compose restart api`. For a fresh installation, follow the README bootstrap/provision/seed steps first. Startup never resets your records.

Windows PowerShell without Make:

```powershell
docker compose run --rm api alembic upgrade head
docker compose up -d --wait api
docker compose restart api
docker compose exec -T api python /workspace/scripts/acceptance_phase6.py
docker compose run --rm api pytest -q
docker compose run --rm api python /workspace/scripts/contracts.py
```

Migration head is `0006_personal`. Old questions and answer snapshots are preserved. Existing turns receive a stable sequence; future same-clock turns are ordered by sequence rather than random UUID. No native Windows run is claimed.

## Browser walkthrough

Refresh the test bench and sign in as `student-a` using your local generated demo accounts file.

1. In Section 6, select **Start new conversation**, enter `Is B201 free tomorrow?`, and ask. Expect a time-interval clarification and a conversation ID/version.
2. Leave **Reply to active clarification** checked, replace the question with `from 2 to 3pm`, and ask. Expect a confirmed room card if the synthetic schedule permits it. The clarification clears and the conversation version advances.
3. Enter `from 3 to 4pm` and ask again. The existing room/date are retained with prior-turn provenance. This is a fresh schedule query, not a replay of the previous availability.
4. In Section 12, select **Open selected conversation** to retrieve its exact stored questions/answers. Copy its conversation ID before refreshing; enter the ID and open it to restore its current version and active clarification. **List my conversations** also provides Open buttons. Turn/history pages are bounded and have Next controls.
5. For faculty ambiguity, start new and ask `Professor Rao office hours on Friday`. Choose one of the offered faculty options; the question field becomes that option's label. Ask while the reply checkbox is checked. Only a listed option from that active clarification is accepted.
6. Start new and ask `workshops next week for second years`, then `Only Friday`, then `for third years`, then `clear year`. Inspect the changed meanings and provenance. Friday stays in the prior week window. A new room question resets event-specific filters.
7. In Section 12, save kind **Room**, ID `campus-demo-b201`. List saved records, select the row to populate the controls, then remove the save when finished. Save kinds are `event`, `room`, `faculty`; office-hour cards save the canonical faculty, not a dated slot.
8. To test deletion, create a disposable conversation and delete that selected conversation in Section 12. The browser asks for confirmation. Its stored text/answers/state are permanently removed; saves are independent. Never delete a conversation you want to retain.

Interpret only remains a standalone diagnostic action; it does not inspect or mutate an existing conversation. Its input is independent of the selected conversation controls.

## API behavior

| Interface | Behavior |
| --- | --- |
| `POST /api/v1/assistant/query` | New question, follow-up, or active clarification reply; cookie/session, student role and CSRF required |
| `GET /api/v1/conversations?limit=20&offset=0` | Only owned conversation summaries |
| `GET /api/v1/conversations/{id}?limit=20&offset=0` | Exact saved turn snapshots plus current version and unexpired active clarification |
| `DELETE /api/v1/conversations/{id}` | Permanently deletes owned history/state; requires CSRF |
| `GET /api/v1/me/saved?limit=20&offset=0` | Current saved records with status and changed flag |
| `PUT /api/v1/me/saved/{kind}/{id}` | Idempotent save of a visible canonical record; requires CSRF |
| `DELETE /api/v1/me/saved/{kind}/{id}` | Idempotent removal of your own save; requires CSRF |

History/saved pages have a maximum limit of 50 and return `next_offset`; concurrent additions/removals can shift offset pages, so refresh a list after a mutation. Another student's conversation ID returns 404. Admin sessions do not gain student history/saved access. Mutations cannot take an owner ID from the request.

A new question includes `text` and `client_request_id`. Continue with its `conversation_id`; send `conversation_version` from the previous response or current history detail to detect stale concurrent sends. Stale versions return `conversation_conflict` (409). The server serializes a user's assistant turns and history deletion even when clients omit the version. Conversations are bounded to 200 turns; exact completed retries still work at that limit.

Clarification replies include `clarification: {"id":"active-id"}` and the conversation ID. Free-text replies replace the unresolved slot while retaining the original question. Option replies additionally include `option_id`; text must be that option's label or ID. Extra constraints belong in a later turn, so they cannot be silently discarded. Expired/consumed/unrelated clarification IDs return 409; unlisted options return 422. New independent questions in an existing conversation should omit clarification; uncheck the reply control to do this in the test bench.

Context expires 30 minutes after the latest successful turn. Expired context is not inherited; a complete new question can resume the same history, with a warning. Expired clarification replies must be replaced by a new question. Precedence remains current explicit text > current overrides > compatible prior state > profile > default. Changing domains discards incompatible inherited fields. The original question and every executed answer stay immutable snapshots.

Supported follow-ups narrow/replace known filters, dates or time windows. `clear/remove` supports topic, event type, year, department, price, building, room, faculty, capacity and facilities. Clearing a required faculty/room interval causes clarification as needed. Language remains constrained: unsupported text never executes a broadened query. Hybrid mode classifies independent/domain-explicit questions; compatible fragments and clarification intent use trusted dialogue state, with the same semantic checks.

## Snapshots, saves and deletion

An old answer remains unchanged after campus edits. A new follow-up queries current records. A save references the current canonical entity and shows record-version changes since saving. Cancelled events remain visible with cancelled status. Draft/archived saved targets remain listed with their status but `current=null`; they cannot be newly saved. Room/faculty saves contain current metadata, not a physical-vacancy or meeting-availability promise. Booking/office-hour child changes do not imply a change to the saved parent metadata version.

A request retry with the same user/ID/payload returns the exact original answer, even if its conversation version or clarification is now stale. Changed payload with that ID returns 409. After history deletion, retries of its requests return `history_deleted` (410), preventing delayed requests from recreating private history. Only the user ID and a SHA-256 digest of the client request ID remain as text-free retry receipts; questions, answers, context and conversation rows are removed.

The live acceptance script creates its own synthetic room, conversation and save; it updates that room to demonstrate current saves versus historical snapshots, checks student isolation, deletes only its own test conversation, removes its save and archives its room. Existing records/history/saves are preserved. Automated tests also exercise faculty ambiguity, expiry, optimistic concurrency, duplicate saves, cancellation/archive behavior and migration paths.

Final reviewed NLP evaluation, fresh release packaging/deployment verification and product frontend integration remain outstanding. The original handoff ownership split no longer blocks backend work.
