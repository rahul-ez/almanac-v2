from datetime import timedelta
from sqlalchemy import delete, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.api.errors import ApiError
from app.auth.security import COOKIE_NAME, digest, new_token
from app.db.models import WebSession, AuthRateLimit


def rate_limit(request, scope, identity, limit):
    now = request.app.state.now()
    window = int(now.timestamp()) // 60
    key = digest(f"{scope}:{identity}:{window}")
    expiry = now.fromtimestamp((window + 1) * 60, tz=now.tzinfo)
    # Commit independently: failed authentication/CSRF transactions must still count.
    with request.app.state.engine.begin() as conn:
        conn.execute(delete(AuthRateLimit).where(AuthRateLimit.expires_at <= now))
        statement = pg_insert(AuthRateLimit).values(key=key, count=1, expires_at=expiry)
        count = conn.execute(statement.on_conflict_do_update(
            index_elements=['key'], set_={'count': AuthRateLimit.count + 1}).returning(AuthRateLimit.count)).scalar_one()
    if count > limit:
        retry = max(1, int((expiry - now).total_seconds()) + 1)
        raise ApiError(429, "rate_limited", "Too many attempts; try again later", headers={'Retry-After': str(retry)})


def issue_session(request, response, conn, user_id=None):
    now = request.app.state.now()
    seconds = request.app.state.settings.session_ttl_seconds if user_id else request.app.state.settings.preauth_ttl_seconds
    token, csrf = new_token(), new_token()
    expires_at = now + timedelta(seconds=seconds)
    conn.execute(insert(WebSession).values(token_hash=digest(token), user_id=user_id, csrf_token=csrf,
                                          created_at=now, expires_at=expires_at, revoked_at=None))
    response.set_cookie(COOKIE_NAME, token, max_age=seconds, httponly=True,
                        secure=request.app.state.settings.cookie_secure, samesite="lax", path="/api/v1")
    return csrf, expires_at
