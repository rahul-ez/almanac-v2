# Completed local-demo integration — 5 November 2026

Agreed scope: local deployment and labeled demonstration data; no public hosting or real-student accuracy claim. The product is available at localhost:8000, API under /api/v1, and independent backend test bench under /backend-test. The combined Docker image builds React and serves its immutable assets from /opt/almanac-frontend, so no frontend dev server or host Node installation is required to run it. `make local` is the setup command.

Implemented: live default mode; username/session/CSRF/error alignment; live event/detail/assistant card conversion; nullable interpretation and context/coverage handling; current saved metadata and offset-page compatibility; paged history restoration with active clarification/version; exact replay payload preservation; stale conversation reload; supported clear/refresh controls; route-isolated composer state; whitelist-based admin DTOs for all nine resources; single event topic/eligibility translation; archive query versions; Monday-first weekdays; nullable room hours; faculty publication coverage and separate aliases; profile input limits; deterministic interest ranking with a stable relevance-aware event cursor; configurable NLP now window and bounded horizon.

Verification:

- 105 backend tests passed in a fresh packaged-install rehearsal, plus 74 backend fixtures, frozen semantic/retrieval gate, HTTP Phases 0–6 and hybrid smoke. Cleanup affected only the generated verification project.
- 16 frontend unit tests passed; TypeScript, production build and 15 frontend mock/view-model contract fixtures passed.
- Two explicit unmocked frontend-client HTTP tests passed: student login/query/follow-up/history/deletion/logout and create/read/edit/archive through all nine admin resources with cleanup of only synthetic records.
- Complete browser suite: 18 passed (16 explicit mock UI regressions and two actual-backend desktop/mobile workflows). The real tests use the integrated port-8000 application, actual cookies/CSRF, room clarification, reloading, follow-up, maintained closure behavior, save/unsave and faculty disambiguation. API responses are not intercepted in those two tests.
- Combined package serves /login, /app, /app/history and /admin deep links. /api paths remain API routes; unknown API paths do not receive SPA HTML.
- Local integration CI workflow added; remote CI has not been run for these unpushed changes.

The final presentation cleanup hides implementation-only engine banners while preserving coverage/source warnings and omits unknown faculty department text. It was typechecked/unit-tested and built separately after the complete rehearsal. The new actual-browser suite covers the final built UI again.

Known design boundaries: history/saves retain bounded offset paging translated by the live adapter, while inventory/event pages use backend cursors. Alias editing supports faculty; other recognized aliases use the configured catalog. Supported language remains constrained. The optional hybrid model remains inferior to baseline rules on the labeled synthetic evaluations and is not selected by default. Native Windows execution and external hosting are not claimed. These do not prevent the agreed local demo from running.

No OpenAI dependency or key was introduced. No integration changes were pushed. For commands and demo account handling, see docs/local-demo.md. Final academic evaluation on independently reviewed student data remains a separate future study, explicitly outside this demo-only scope.
