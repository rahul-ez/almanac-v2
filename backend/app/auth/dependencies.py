from typing import Annotated
from secrets import compare_digest
from fastapi import Depends, Header, Request
from fastapi.security import APIKeyCookie
from sqlalchemy import Connection, select
from app.api.errors import ApiError
from app.auth.security import COOKIE_NAME, digest
from app.db.models import User, WebSession

session_cookie = APIKeyCookie(name=COOKIE_NAME, auto_error=False)

def connection(request: Request):
    # Commit before sending response; a commit failure cannot report success.
    with request.app.state.engine.begin() as conn:
        yield conn

Db = Annotated[Connection, Depends(connection, scope="function")]

def current_session(request: Request, conn: Db, token: Annotated[str | None, Depends(session_cookie)]):
    if not token or len(token) != 43:
        raise ApiError(401, "unauthenticated", "Please sign in")
    row = conn.execute(select(WebSession.__table__).where(WebSession.token_hash == digest(token)).with_for_update()).mappings().first()
    if row is None or row['revoked_at'] is not None or row['expires_at'] <= request.app.state.now():
        raise ApiError(401, "unauthenticated", "Session missing, expired or revoked")
    return row

Session = Annotated[dict, Depends(current_session, scope="function")]

def csrf_session(request: Request, session: Session,
                 x_csrf_token: Annotated[str | None, Header()] = None,
                 origin: Annotated[str | None, Header()] = None):
    if origin not in request.app.state.settings.allowed_origins:
        raise ApiError(403, "origin_rejected", "Request origin is not allowed")
    if not x_csrf_token or not x_csrf_token.isascii() or not compare_digest(session['csrf_token'], x_csrf_token):
        raise ApiError(403, "csrf_failed", "A valid CSRF token is required")
    return session

CsrfSession = Annotated[dict, Depends(csrf_session, scope="function")]

def authenticated(request: Request, conn: Db, session: Session):
    if session['user_id'] is None:
        raise ApiError(401, "unauthenticated", "Please sign in")
    user = conn.execute(select(User.__table__).where(User.id == session['user_id'], User.active.is_(True))).mappings().first()
    if user is None:
        raise ApiError(401, "unauthenticated", "Please sign in")
    return dict(user, session_expires_at=session['expires_at'])

CurrentUser = Annotated[dict, Depends(authenticated, scope="function")]

def student(user: CurrentUser):
    if user['role'] != 'student':
        raise ApiError(403, "forbidden", "Student access required")
    return user

Student = Annotated[dict, Depends(student, scope="function")]

def admin(user: CurrentUser):
    if user['role'] != 'admin':
        raise ApiError(403, "forbidden", "Admin access required")
    return user

Admin = Annotated[dict, Depends(admin, scope="function")]
