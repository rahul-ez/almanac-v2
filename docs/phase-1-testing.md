# Phase 1: identity, sessions, profiles and permissions

Status: implemented locally. API/contract version 0.2.0; Alembic revision 0002. No frontend is required.

## Run it

For an existing Phase 0 setup:

```sh
make bootstrap migrate provision-demo contract-check dev
make acceptance PHASE=1
make test
```

On a completely fresh setup, run `make seed-demo` as well to retain the Phase 0 event demonstration. `make acceptance PHASE=0` still works once seeded.

`make provision-demo` creates admin, student-a and student-b, plus synthetic departments/buildings/topics. Each account receives its own randomly generated password. Credentials are written to `.local/demo-accounts.json` with mode 0600, inside a directory with mode 0700. Both Git and Docker image builds exclude `.local`. Existing users, passwords, profiles and reference records are preserved on subsequent runs. Credentials are never printed by the provisioner or acceptance script. Open that local file when you need to log in manually; do not publish it. There is no password-reset feature yet. If the file is lost, re-provisioning does not change existing passwords.

## What the live walkthrough proves

`make acceptance PHASE=1` uses real HTTP requests and PostgreSQL. It:

1. Rejects anonymous access with 401.
2. Initializes CSRF and signs in each demo account.
3. Verifies student admin access is 403 and admin access is 200.
4. Reads reference data, changes student A's year, and confirms student B is unchanged.
5. Rejects another session's CSRF token, role escalation, missing CSRF/origin and a hostile origin.
6. Restores student A's original profile, so repeated walkthroughs preserve demo profile values.
7. Signs out and verifies that reusing the old cookie still returns 401.

The script never prints passwords or cookies. Default login limits allow ten attempts per username and per client IP in each fixed 60-second window. Repeated walkthroughs within the same minute may return 429; honor `Retry-After` and retry after that interval. The limit uses database counters, so restarting the API does not reset it. The API uses the directly connected client's address, not untrusted forwarded headers. A future reverse-proxy deployment must explicitly configure trusted proxy behavior.

## Manual Swagger test

Open [Swagger](http://localhost:8000/docs). Use the same hostname throughout (localhost and 127.0.0.1 have separate browser cookie stores).

1. Execute `GET /api/v1/auth/csrf`. The browser receives an HTTP-only pre-login session cookie; copy the returned `csrf_token`.
2. Execute `POST /api/v1/auth/login` with username/password from the local credentials file. Set `x-csrf-token` to the token from step 1. The allowed origin is `http://localhost:8000`; browsers supply their actual Origin automatically. Command-line clients must supply it explicitly.
3. Login returns a new `csrf_token` and `user`; use this new token for subsequent mutations. Both the cookie and token rotate on login.
4. Execute `GET /api/v1/auth/me` and `GET /api/v1/me/profile` as a student. The browser sends cookies automatically; do not try to copy session tokens into Swagger's Authorize dialog.
5. Execute `PATCH /api/v1/me/profile` with the new token and a body such as:

```json
{"department_id":"aiml","year":2,"section":"A","interests":["machine_learning"]}
```

6. Repeat the profile GET to verify persistence. Omitted fields remain unchanged; explicit null clears department/year/section; `interests: []` clears interests. Use `GET /api/v1/reference-data` for supported IDs. Unknown IDs, duplicate interests, role/user_id fields and years outside 1–4 return structured 422 errors.
7. As a student, `GET /api/v1/admin/access` returns 403. As admin, it returns 200. This is a real role-protected access check; domain CRUD comes later. Admins do not have student profiles.
8. Execute `POST /api/v1/auth/logout` with the current token. Subsequent `GET /api/v1/auth/me` returns 401. Fetch CSRF again before a new login.

If a token is lost after a reload, `GET /api/v1/auth/csrf` returns the active session's token. This response is not cached. Never send credentials or CSRF tokens in URL query parameters.

## Implemented endpoints

| Endpoint | Requirement |
| --- | --- |
| GET `/api/v1/auth/csrf` | Issues/reads CSRF pre-session; rate limited |
| POST `/api/v1/auth/login` | Pre-session cookie, matching token, allowed Origin, valid credentials |
| GET `/api/v1/auth/me` | Active authenticated session |
| POST `/api/v1/auth/logout` | Authenticated session, matching token, allowed Origin |
| GET/PATCH `/api/v1/me/profile` | Student; PATCH also needs matching token and allowed Origin |
| GET `/api/v1/reference-data` | Authenticated student or admin |
| GET `/api/v1/admin/access` | Admin assigned in the database |

## Session and configuration behavior

Passwords are Argon2id hashes through pwdlib. PostgreSQL stores SHA-256 hashes of random session tokens, not usable raw cookie values. CSRF tokens are independent random synchronizer tokens stored server-side. Sessions expire after eight hours, pre-login sessions after fifteen minutes; there is no sliding renewal. Logout revokes the stored session and clears its cookie. Role and active status are checked against the database on every authenticated request. Mutations finish their database transaction before the response is sent.

Cookies are HTTP-only, SameSite=Lax, host-only and scoped to `/api/v1`. Local HTTP development uses `COOKIE_SECURE=false`; HTTPS requires true. Production deployment is not enabled in the current environment settings. Credentialed CORS permits only exact configured origins (defaults: localhost/127.0.0.1 on ports 8000 and 5173). Origin validation for mutations applies independently of CORS. No wildcard credentialed origins are allowed. Request bodies are limited to 16 KiB, password inputs to 256 characters, and interest lists to ten IDs.

Optional `.env` fields: `ALLOWED_ORIGINS` (JSON array), `COOKIE_SECURE`, `SESSION_TTL_SECONDS`, `PREAUTH_TTL_SECONDS`, `LOGIN_LIMIT_PER_MINUTE`, `CSRF_LIMIT_PER_MINUTE`. PostgreSQL and migration failures return sanitized 503 responses; raw inputs, passwords and cookies are omitted from logs and validation errors. Authentication/profile responses use `Cache-Control: no-store`.

The automated tests create uniquely named test users in the configured local database and remove those users afterward; existing demo accounts/profiles remain intact. Migration tests create a uniquely named temporary database, verify an empty upgrade plus downgrade/upgrade and metadata consistency, then drop only that database. The local database role needs CREATEDB for that check. All permission and persistence checks use real PostgreSQL.

## Boundaries for the next phase

This checkpoint enforces ownership for profiles by deriving user ID exclusively from the session. Conversation/history/saved-item endpoints do not exist yet; their ownership and deletion checks arrive when those features are implemented. There is no registration, recovery, email verification, domain admin CRUD or assistant query endpoint.

References used for implementation: [OWASP CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [FastAPI password hashing](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [FastAPI dependency transaction scope](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/).

## Browser test bench on port 8000

Open http://localhost:8000/ for a small backend test bench served by FastAPI. It has sign-in/out, a student profile form, health/demo/session/reference/admin checks, and deliberate CSRF/role rejection checks. Cookies and CSRF rotation are handled automatically; displayed responses hide tokens. This utility is independent of the separately developed product frontend.

Sign in manually using the generated credentials, or expand “Use your generated demo accounts” and select `.local/demo-accounts.json`. On macOS, use Command+Shift+G in the file chooser to enter the hidden folder path. The file stays in browser memory; choosing an account fills the login form, and clicking Sign in sends only that account's credentials to the local API. No credentials are served through a new HTTP endpoint or stored in browser local storage.
