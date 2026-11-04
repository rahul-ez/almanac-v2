# Phase 6 local verification

Verified on 4 November 2026. Work remains local and uncommitted; no push was performed.

- **100 tests passed**, with one upstream Starlette/httpx deprecation warning. This includes ordered same-clock turns, follow-up precedence/clears/domain reset, expired state, active faculty options, ambiguous-time replacement, optimistic concurrent turns, deletion retry receipts and idempotent/private current saves.
- **74 fixtures** validated by Pydantic and JSON Schema. OpenAPI 0.7.0 includes dialogue versions and the history/saved routes. Historical snapshots replay unchanged.
- Applied migration **0006_personal** to the existing local demo database, preserving existing turns. Disposable database verification passed empty upgrade -> head, ORM metadata check, downgrade -> 0001 -> head.
- Live Phase 0 acceptance passed: liveness/readiness/demo 200 and unknown route 404.
- Live Phase 6 acceptance passed: missing-time clarification, restored pending state, time reply, exact retry, stale/consumed clarification 409, another student's history/delete 404, inherited room/date, stale version 409, idempotent save, current capacity after admin change, unchanged historical capacity, bounded turn pagination, real deletion, deleted request 410 and independent retained save. Only the script's synthetic conversation/save/room were cleaned up.
- Browser verification passed: demo student asked `Is B201 free tomorrow?`, received a time clarification, replied `from 2 to 3pm`, received DEMO-B201 availability, and reopened the conversation showing two stored turns/version 2. Screenshot: `/private/tmp/almanac-phase6-history.png`. The temporary browser tab was closed; existing user tabs were preserved.
- JavaScript syntax and `git diff --check` passed. The test bench clears personal selection/list data on login/logout/session expiry. CI was updated but not run remotely.

Local API remains at localhost:8000 in baseline rule mode. The optional prototype model and its previously reported limitations remain unchanged. Windows Docker commands are documented, but native Windows testing, product frontend integration, independent final corpus evaluation and release/deployment verification remain outstanding.

History deletion removes stored questions, answer snapshots and dialogue state. Text-free user/request-ID hash receipts remain solely to prevent delayed retries from recreating deleted history. Saved parent metadata versions track the parent record, not changes to child schedules. Draft/archived saves expose status with current=null. Offset pages can shift during concurrent list mutations; refresh after changes.
