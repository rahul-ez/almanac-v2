# Person A — Backend domains, query execution and operations

Repository: https://github.com/rahul-ez/almanac-v2

Starting checkpoint: backend Phases 0–2, API 0.3.0, migrations through 0003. The backend branch contains the tested API, localhost test bench, demo data and setup. Main contains the frontend; live integration is still unverified. These assignments can start simultaneously in separate clones. Nothing in this assignment requires pushing directly to main.

Your responsibility is to complete room/faculty semantics, extraction/resolution and safe execution. Person B independently connects the frontend, then implements history/saves, dialogue and model evaluation. You do not need to wait for frontend integration to test domain services.

## Start here

```sh
git fetch origin
git switch -c feature/room-scheduling origin/backend
make bootstrap migrate provision-demo seed-demo seed-events dev
make test
make contract-check
```

Use http://localhost:8000/ for the backend test bench and /docs for API inspection. Demo credentials are generated locally in ignored `.local/demo-accounts.json`; do not commit them.

## A1 — Room scheduling (first deliverable)

Deliver room records with capacity/building/facilities, campus-local opening hours, explicit schedule coverage, bounded one-off/weekly bookings, dated cancellation/replacement exceptions and closures. Add typed service queries, admin CRUD and a localhost test-bench walkthrough. No student room reservation feature.

Exit: an interval ending at a booking start is allowed, overlap is rejected, recurring exceptions work, closures win, missing coverage is unknown, and conflicting concurrent bookings cannot both commit. Test through API/CLI without relying on NLP or frontend availability. Retain all Phase 0–2 checks.

Implementation scope:

- Room code/building, positive capacity, facilities, opening hours and explicit schedule coverage.
- One-off and bounded weekly bookings, cancellation/replacement exceptions and closures.
- Typed availability query service, admin CRUD, schema-valid fixtures and deterministic demo cases.
- Transactional booking conflicts, edit versions and server-enforced admin permissions.
- API/CLI walkthrough and localhost controls for user testing.

Keep “scheduled availability” explicit. Missing timetable coverage is unknown; no booking does not prove physical vacancy. Preserve half-open intervals [start,end).

## A2 — Faculty office hours (second deliverable)

Deliver canonical faculty/alias resolution, published weekly office hours with effective dates and dated cancellations/replacements. Provide a typed query service and API/CLI examples. Similar names remain ambiguous; no inference from teaching timetables. Test exact concrete intervals and missing publication separately from no matching slots.

Deliver faculty/alias CRUD, bounded published schedules, dated cancellations/replacements, typed query services, contracts and test data. Coordinate the card/admin payload shape with Person B before implementation so the existing screens can consume it.

## A3 — NLP extraction, resolution and execution

Before either owner changes the interpreter, agree the typed meaning shape and the pure interpreter interface: question + explicit context + injected clock/timezone + alias/catalog input -> meaning or uncertainty outcome, with provenance. Person A owns extraction/resolution and domain validation/execution; Person B owns intent model, state/clarification, corpus splits and metrics. One orchestrator composes them; never create a second assistant route. Keep the current event baseline as a separately measurable comparison. Freeze grouped test data before tuning.

Your components handle original span preservation, campus aliases/codes, dates/intervals, supported constraints, canonical IDs and domain validation. Inject the reference clock/timezone. Unknown or contradictory meaning must not execute broad queries. Route only validated meanings to the same services used by structured queries. Evaluate extraction/normalization with Person B; do not tune on the frozen test set.

## A4 — Operations and handoff

Own readiness, schema evolution, repeatable seeds, dependency compatibility, domain performance, fresh setup and deployment reproducibility. Join Person B for final live-browser and deployed-origin checks.

## Files and coordination

- Person A coordinates migration numbering and the final linear Alembic head. Reserve each new revision before either owner writes one; avoid independently generating two revisions named 0004. Commit migrations with their owning feature and run empty-database upgrade plus existing-data upgrade checks.
- Add new domain ORM classes in separate room/faculty modules and dialogue/save additions in separate modules when appropriate; register all metadata explicitly. Coordinate edits to central models/main imports instead of editing the same large file concurrently. A small separate refactor can introduce these seams if needed; it is not already done.
- New API/schema/service/test files should be domain-specific. Person A owns shared meaning/response composition and runtime OpenAPI export; Person B owns client adapters/rendering, dataset/evaluation scripts and dialogue state implementation. Cross-owner changes get review.
- Backend dependency lock belongs to Person A; frontend lock belongs to Person B. Model-training dependencies are pinned with Person A's review. Keep private credentials and real histories out of Git.
- Freeze upcoming room/faculty card and admin payload contracts before both owners work on them. The existing frontend proposal is useful input, not automatic proof that the backend supports it.
- A PR includes acceptance commands, expected IDs/intervals/status, migration/seed changes, affected contracts and actual test evidence. Only claim checks that ran.

Person B needs early stable room/faculty schemas, fixture examples and typed service interfaces. Review B's history/save migrations and assistant orchestration changes; extend existing conversations/turns rather than duplicating storage. Reserve migration IDs before either owner starts writing one.

## Acceptance gates

For every deliverable, provide exact commands, request payloads, expected record IDs/intervals/status and actual test output. Keep prior checkpoints green:

```sh
make test
make contract-check
make acceptance PHASE=0
make acceptance PHASE=1
make acceptance PHASE=2
```

Add a dedicated room walkthrough, then a faculty walkthrough, each testable without NLP or frontend availability. The user tests each checkpoint before it is treated as accepted. PRs should be small and include migration/contract/seed changes together. After Person B's first live integration PR is reviewed and integrated, synchronize subsequent feature branches from the common integrated commit.
