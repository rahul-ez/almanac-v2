# Frontend

React, TypeScript, Vite, React Router, Zod, Phosphor icons, and locally hosted Manrope. Exact dependency versions are recorded in `package.json` and `package-lock.json`. Development was verified on Node 24.12.0 and npm 11.6.2; CI uses Node 24.

## Run

```powershell
cd frontend
npm ci
npm run dev
```

The dev server uses `http://127.0.0.1:5173`. Do not mix `localhost` and `127.0.0.1` during live session tests: they are different cookie origins.

Demo accounts:

| Email | Role | Password |
| --- | --- | --- |
| student@campus.demo | Student | CampusDemo!26 |
| ananya@campus.demo | Second student for isolation checks | CampusDemo!26 |
| admin@campus.demo | Admin | CampusDemo!26 |

The login screen can fill the main student/admin credentials. Roles come from the transport response; there is no client role selector. Demo mode is a browser-local simulation, not secure authentication. Real passwords and private campus records must not be stored in this adapter.

## Mock and live modes

No environment file is needed for mock mode. Copy `.env.example` to `.env.local` to configure the app:

```dotenv
VITE_API_MODE=live
VITE_API_BASE_URL=/api/v1
API_PROXY_TARGET=http://127.0.0.1:8000
```

Restart Vite after changing configuration. `VITE_` variables are public browser configuration; never put secrets in them. Live requests include credentials, initialize CSRF via `GET /auth/csrf`, and send `X-CSRF-Token` for mutations, including login. Live failures remain errors and never load demo records.

The Vite proxy is for development. A deployed build requires one browser origin, HTTPS, a reverse proxy for `/api`, and SPA fallback to `index.html` for `/app/*`, `/admin/*`, and `/login`. Configure secure, HttpOnly session cookies and server permissions in the backend. Campus timezone comes from reference data and assistant responses.

`npm run build` produces `dist/`. `npm run preview` previews the production client; its server does not provide the development API proxy. Live preview needs a matching reverse proxy or an explicitly configured API origin with server CORS/credential support.

## Verification

```powershell
npm run typecheck
npm run contracts:check
npm test
npm run build
npx playwright install chromium
npm run test:browser
```

Browser checks launch mock mode on port 5173 and live mode on port 5174, with intercepted API responses for live tests. Stop conflicting processes on those ports before running. Playwright owns and stops its servers. The desktop/mobile projects use Chromium; the mobile project emulates an iPhone viewport and touch input, not the WebKit engine.

Tests cover fixture validation, HTTP credentials/CSRF/errors, request deduplication, context/clarification, seeded schedule boundaries, snapshot/current-record behavior, account isolation, deletion, browser role guards, profile persistence, unsaved changes, all admin forms, admin-to-student publishing, session expiry, interrupted-request recovery, and responsive layouts. Screenshots and failure traces are saved to ignored `test-results/`.

Generate updated contracts with `npm run contracts:export`. Commit the corresponding fixtures and client changes together after Person B reviews them. Synthetic annotation drafts can be regenerated with `npx tsx scripts/create-pilot.ts`; see `../data/annotations/README.md` before using them.

## Layout

```text
src/app/                  Routing, auth/workspace contexts, loading hooks
src/api/                  Runtime schemas, HTTP adapter, mock service, seed/fixtures
src/components/           Cards, dialogs, form/status helpers, time formatting
src/features/auth/        Login and demo account entry
src/features/assistant/   Composer, history snapshots, answer/context/clarification
src/features/history/     Paginated conversation list and deletion
src/features/saved/       Current saved-record views
src/features/profile/     Profile and interests
src/features/admin/       Resource lists, explicit field definitions, edit forms
tests/unit/               Contract, transport, and demo integration checks
tests/browser/            Desktop/mobile user workflows and live errors
```

Only the mock adapter interprets example questions locally. Its deterministic demo dispatcher is not an NLP model. Live mode delegates all interpretation and domain decisions to the backend.

Demo data persists under `campus.demo.v1`; the demo session uses `campus.demo.session`. To reset the demo, sign out and remove those two keys in the browser's storage inspector, then reload. No reset runs during normal startup. Drafts and interrupted requests use per-user `sessionStorage` keys so an expired login can resume safely. A retry reuses its original `client_request_id` and does not silently resubmit a changed payload.
