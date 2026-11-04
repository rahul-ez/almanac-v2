# Frontend verification and evaluation contribution

The frontend has deterministic integration and browser checks. These measure interface/adapter behavior against declared fixtures, not NLP model quality. Campus records are fictional. No real student data, consent, annotation agreement, model accuracy, or deployment success is claimed.

## Evidence

- `frontend/tests/unit/transport.test.ts`: credentials and CSRF initialization; cancellation; structured errors and unauthorized-session handling; invalid responses and outages remain failures.
- `frontend/tests/unit/demo.test.ts`: all 15 shared fixtures validate; campus-local datetime conversion and safe source protocols; request deduplication; follow-up state; clarification binding; domain reset; schedule boundaries/closures/coverage; snapshot vs current saved data; demo account isolation/deletion.
- `frontend/tests/browser/workflows.spec.ts`: desktop/mobile student journeys, all admin forms, publishing to student retrieval, detail-dialog focus, unsaved profile warnings, session expiry and draft preservation, and no horizontal overflow.
- `frontend/tests/browser/live-mode.spec.ts`: intercepted live API failure/recovery with the same request ID, no fallback to demo data, and safe rendering of all assistant outcome fixtures.
- `contracts/fixtures/`: expected answers, missing/ambiguous/unsupported states, truncation, validation/auth/service errors, changed saved records, and historical snapshots.

Run the commands in `frontend/README.md` for current pass counts. Browser screenshots and traces live in ignored `frontend/test-results/`. The CI workflow repeats the checks on a clean Linux runner. A local pass does not claim CI has already run remotely.

Local verification completed with 11 integration/unit tests and 20 desktop/mobile browser checks passing, together with strict type checking, the production build, and validation of the contract plus all 15 fixtures. Home and admin-form screenshots were visually reviewed. The browser suite was run against stable source after correcting the development context-refresh issue.

## Error taxonomy and examples

| Category | Representative case | Interface behavior |
| --- | --- | --- |
| Intent/support | Weather or placement request | Explicit supported-domain guidance, no invented answer |
| Extraction/missing slot | Room request without interval | Free-text clarification; preserve compatible building filter |
| Resolution | Two faculty named Rao | Server-issued option IDs, no silent faculty selection |
| Time/context | Only Friday after workshops this week | Retain event type, replace date, display provenance |
| Query semantics | Booking ends when requested interval begins | Adjacent intervals do not overlap in demo fixtures |
| Data coverage | A Block timetable unavailable | Information unavailable, distinct from zero matches |
| Record freshness | Cancel an event after saving | Current saved status changes; historical response stays intact |
| Session/ownership | Expired session or another user's history ID | Reauthenticate with draft preserved; inaccessible records handled as missing |
| Transport | API 503 or malformed response | Error with retry/reference, no empty answer or mock fallback |
| Rendering | Narrow viewport, long titles, missing prices | Responsive layout; unknown values labeled explicitly |

The browser pass identified and corrected small/faint secondary text, a sign-in identity-restore race, a test account-switching race, and stale saved controls when reopening snapshots. Interrupted queries preserve their request payload/ID in per-user session storage and read current conversation state before retrying. The new-query recovery uses the same idempotency key because its server-created conversation ID may not yet be known.

## Academic work still requiring the team

The 60 synthetic pilot drafts and six dialogue drafts in `data/annotations/` are starting material. They need independent review and more natural language variety. Person A must collect consented/anonymized student questions and double-label a shared sample with Person B. Person B owns canonical interpretation/schema adjudication, frozen group-based splits, trained baselines, normalization/entity/meaning/end-to-end/dialogue metrics, and latency measurements. Final evaluation requires a versioned real seed database, reference clock, and actual model artifacts.

Browser tests use Chromium on desktop and an emulated phone viewport. Other engines, real devices, screen-reader manual testing, and the real deployed backend remain integration checks; they are not implied by the current suite.
