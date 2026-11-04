from fastapi import APIRouter, Request, Response
from sqlalchemy import select, update, delete
from app.api.errors import ApiError
from app.auth.dependencies import Db, CsrfSession, CurrentUser, Student, Admin
from app.auth.security import COOKIE_NAME, DUMMY_HASH, digest, passwords
from app.auth.sessions import issue_session, rate_limit
from app.db.models import User, WebSession, Department, Building, Topic
from app.repositories.profiles import read_profile, patch_profile
from app.schemas.identity import (LoginRequest, LoginResponse, Identity, CsrfResponse,
    LogoutResponse, Profile, ProfilePatch, ReferenceData, AdminAccess)
from app.schemas.contracts import ErrorResponse
from app.db.room_models import Facility

router = APIRouter(prefix='/api/v1', responses={code: {'model': ErrorResponse} for code in (401, 403, 413, 422, 429, 503)})

def identity(user, expires_at=None):
    return Identity(id=user['id'], username=user['username'], role=user['role'],
                    session_expires_at=expires_at or user['session_expires_at'])

@router.get('/auth/csrf', response_model=CsrfResponse, tags=['session'])
def csrf(request: Request, response: Response, conn: Db):
    # Reject hostile browser origins even though this is a read; no Origin is allowed for a same-origin GET.
    origin = request.headers.get('origin')
    if origin is not None and origin not in request.app.state.settings.allowed_origins:
        raise ApiError(403, 'origin_rejected', 'Request origin is not allowed')
    rate_limit(request, 'csrf', request.client.host, request.app.state.settings.csrf_limit_per_minute)
    token = request.cookies.get(COOKIE_NAME)
    now = request.app.state.now()
    if token and len(token) == 43:
        row = conn.execute(select(WebSession.__table__).where(WebSession.token_hash == digest(token),
            WebSession.revoked_at.is_(None), WebSession.expires_at > now)).mappings().first()
        if row:
            return CsrfResponse(csrf_token=row['csrf_token'], expires_at=row['expires_at'])
    # Bounded garbage collection; never remove live sessions.
    expired = select(WebSession.token_hash).where(WebSession.expires_at <= now).limit(100)
    conn.execute(delete(WebSession).where(WebSession.token_hash.in_(expired)))
    token, expires_at = issue_session(request, response, conn)
    return CsrfResponse(csrf_token=token, expires_at=expires_at)

@router.post('/auth/login', response_model=LoginResponse, tags=['session'])
def login(payload: LoginRequest, request: Request, response: Response, conn: Db, session: CsrfSession):
    limit = request.app.state.settings.login_limit_per_minute
    rate_limit(request, 'login-ip', request.client.host, limit)
    rate_limit(request, 'login-user', payload.username, limit)
    user = conn.execute(select(User.__table__).where(User.username == payload.username)).mappings().first()
    valid = passwords.verify(payload.password.get_secret_value(), user['password_hash'] if user else DUMMY_HASH)
    if not valid or user is None or not user['active']:
        raise ApiError(401, 'invalid_credentials', 'Invalid username or password')
    conn.execute(update(WebSession).where(WebSession.token_hash == session['token_hash']).values(revoked_at=request.app.state.now()))
    csrf_token, expires_at = issue_session(request, response, conn, user['id'])
    return LoginResponse(user=identity(user, expires_at), csrf_token=csrf_token)

@router.get('/auth/me', response_model=Identity, tags=['session'])
def me(user: CurrentUser):
    return identity(user)

@router.post('/auth/logout', response_model=LogoutResponse, tags=['session'])
def logout(request: Request, response: Response, conn: Db, session: CsrfSession, user: CurrentUser):
    conn.execute(update(WebSession).where(WebSession.token_hash == session['token_hash']).values(revoked_at=request.app.state.now()))
    response.delete_cookie(COOKIE_NAME, path='/api/v1', secure=request.app.state.settings.cookie_secure, httponly=True, samesite='lax')
    return LogoutResponse()

@router.get('/me/profile', response_model=Profile, tags=['profile'])
def profile(conn: Db, user: Student):
    return read_profile(conn, user['id'])

@router.patch('/me/profile', response_model=Profile, tags=['profile'])
def profile_update(payload: ProfilePatch, conn: Db, user: Student, session: CsrfSession):
    return patch_profile(conn, user['id'], payload)

@router.get('/reference-data', response_model=ReferenceData, tags=['reference'])
def reference_data(request: Request, conn: Db, user: CurrentUser):
    def rows(model):
        return list(conn.execute(select(model.__table__).order_by(model.id)).mappings())
    return ReferenceData(departments=rows(Department), buildings=rows(Building), topics=rows(Topic), facilities=rows(Facility), campus_timezone=request.app.state.settings.campus_timezone, supported_years=[1, 2, 3, 4])

@router.get('/admin/access', response_model=AdminAccess, tags=['admin'])
def admin_access(user: Admin):
    return AdminAccess(user_id=user['id'])
