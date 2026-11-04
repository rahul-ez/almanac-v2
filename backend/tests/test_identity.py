from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, insert, select, update
from app.auth.security import COOKIE_NAME, digest, passwords
from app.config import Settings
from app.db.connection import make_engine
from app.db.models import User, StudentProfile, Department, Topic, WebSession
from app.main import create_app

ORIGIN = 'http://localhost:8000'
PASSWORD = 'Only-for-isolated-test-accounts!'

@pytest.fixture
def env():
    key = uuid4().hex
    settings = Settings(login_limit_per_minute=1000, csrf_limit_per_minute=1000)
    engine = make_engine(settings)
    ids = {name: f'test-{key}-{name}' for name in ('a', 'b', 'admin')}
    department, topic = f'test-{key}-dept', f'test-{key}-topic'
    with engine.begin() as conn:
        conn.execute(insert(Department).values(id=department, label='Test department'))
        conn.execute(insert(Topic).values(id=topic, label='Test topic'))
        for name, user_id in ids.items():
            conn.execute(insert(User).values(id=user_id, username=user_id, password_hash=passwords.hash(PASSWORD), role='admin' if name == 'admin' else 'student', active=True))
            if name != 'admin':
                conn.execute(insert(StudentProfile).values(user_id=user_id, department_id=None, year=None, section=None))
    clock = [datetime.now(timezone.utc)]
    app = create_app(settings, now=lambda: clock[0])
    with ExitStack() as stack:
        def client():
            return stack.enter_context(TestClient(app, client=(f'test-{uuid4().hex}', 50000)))
        def login(name='a', c=None):
            c = c or client()
            pre = c.get('/api/v1/auth/csrf')
            assert pre.status_code == 200, pre.text
            result = c.post('/api/v1/auth/login', json={'username': ids[name], 'password': PASSWORD},
                            headers={'Origin': ORIGIN, 'X-CSRF-Token': pre.json()['csrf_token']})
            assert result.status_code == 200, result.text
            return c, result.json()['csrf_token']
        yield dict(client=client, login=login, ids=ids, department=department, topic=topic, clock=clock, app=app, engine=engine)
    with engine.begin() as conn:
        conn.execute(delete(User).where(User.id.in_(list(ids.values()))))
        conn.execute(delete(Department).where(Department.id == department))
        conn.execute(delete(Topic).where(Topic.id == topic))
    engine.dispose()


def headers(csrf):
    return {'Origin': ORIGIN, 'X-CSRF-Token': csrf}


def test_anonymous_roles_and_identity(env):
    anonymous = env['client']()
    for path in ('/auth/me', '/me/profile', '/reference-data', '/admin/access'):
        assert anonymous.get('/api/v1'+path).status_code == 401
    student, _ = env['login']()
    assert student.get('/api/v1/admin/access').status_code == 403
    identity = student.get('/api/v1/auth/me')
    assert identity.status_code == 200
    assert set(identity.json()) == {'id', 'username', 'role', 'session_expires_at'}
    assert identity.headers['cache-control'] == 'no-store'
    admin, _ = env['login']('admin')
    assert admin.get('/api/v1/admin/access').json()['role'] == 'admin'
    assert admin.get('/api/v1/me/profile').status_code == 403


def test_login_rotates_session_csrf_and_hashes_cookie(env):
    client = env['client']()
    csrf = client.get('/api/v1/auth/csrf').json()['csrf_token']
    before = client.cookies.get(COOKIE_NAME)
    response = client.post('/api/v1/auth/login', json={'username': env['ids']['a'], 'password': PASSWORD}, headers=headers(csrf))
    assert response.status_code == 200
    assert response.json()['csrf_token'] != csrf
    token = client.cookies.get(COOKIE_NAME)
    assert token != before
    cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=lax' in cookie and 'path=/api/v1' in cookie
    assert client.patch('/api/v1/me/profile', json={'year': 2}, headers=headers(csrf)).status_code == 403
    with env['engine'].connect() as conn:
        stored = conn.execute(select(WebSession.__table__).where(WebSession.token_hash == digest(token))).mappings().one()
        assert stored['token_hash'] != token and stored['user_id'] == env['ids']['a']
        assert conn.execute(select(User.password_hash).where(User.id == env['ids']['a'])).scalar_one().startswith('$argon2id$')
    replay = env['client']()
    replay.cookies.set(COOKIE_NAME, before, path='/api/v1')
    assert replay.get('/api/v1/auth/me').status_code == 401


def test_login_requires_bound_csrf_and_origin(env):
    client = env['client']()
    csrf = client.get('/api/v1/auth/csrf').json()['csrf_token']
    payload = {'username': env['ids']['a'], 'password': PASSWORD}
    for supplied in ({'Origin': ORIGIN}, {'X-CSRF-Token': csrf}, {'Origin': 'https://evil.example', 'X-CSRF-Token': csrf}):
        assert client.post('/api/v1/auth/login', json=payload, headers=supplied).status_code == 403
    other = env['client']()
    other.get('/api/v1/auth/csrf')
    assert other.post('/api/v1/auth/login', json=payload, headers=headers(csrf)).status_code == 403
    assert client.get('/api/v1/auth/csrf', headers={'Origin': 'https://evil.example'}).status_code == 403


def test_profile_validation_ownership_and_clear(env):
    a, csrf_a = env['login']('a')
    b, csrf_b = env['login']('b')
    patch = {'department_id': env['department'], 'year': 2, 'section': 'A', 'interests': [env['topic']]}
    saved = a.patch('/api/v1/me/profile', json=patch, headers=headers(csrf_a))
    assert saved.status_code == 200, saved.text
    assert saved.json()['user_id'] == env['ids']['a']
    assert b.get('/api/v1/me/profile').json()['year'] is None
    assert b.patch('/api/v1/me/profile', json={'year': 3}, headers=headers(csrf_a)).status_code == 403
    for payload in ({'role':'admin'}, {'user_id':env['ids']['a']}, {'year':0}, {'year':True}, {'department_id':'does-not-exist'}, {'interests':['does-not-exist']}, {'interests':[env['topic']]*2}, {'interests':None}):
        result = b.patch('/api/v1/me/profile', json=payload, headers=headers(csrf_b))
        assert result.status_code == 422, (payload, result.text)
        assert result.json()['error']['code'] == 'validation_error'
        assert 'input' not in result.text
    assert b.get('/api/v1/auth/me').json()['role'] == 'student'
    assert b.get('/api/v1/me/profile').json()['department_id'] is None
    # An invalid second field must roll back the whole update.
    assert a.patch('/api/v1/me/profile', json={'year': 4, 'interests':['bad-topic']}, headers=headers(csrf_a)).status_code == 422
    assert a.get('/api/v1/me/profile').json()['year'] == 2
    assert a.patch('/api/v1/me/profile', json={'section':None}, headers=headers(csrf_a)).json()['interests'] == [env['topic']]
    cleared = a.patch('/api/v1/me/profile', json={'department_id':None, 'year':None, 'interests':[]}, headers=headers(csrf_a))
    assert cleared.status_code == 200 and cleared.json()['interests'] == []
    assert a.get('/api/v1/me/profile/'+env['ids']['b']).status_code == 404


def test_profile_survives_new_app_instance(env):
    client, csrf = env['login']()
    assert client.patch('/api/v1/me/profile', json={'year': 2}, headers=headers(csrf)).status_code == 200
    token = client.cookies.get(COOKIE_NAME)
    with TestClient(create_app(Settings())) as restarted:
        restarted.cookies.set(COOKIE_NAME, token, path='/api/v1')
        assert restarted.get('/api/v1/me/profile').json()['year'] == 2


def test_logout_revokes_and_deletes_cookie(env):
    client, csrf = env['login']()
    old = client.cookies.get(COOKIE_NAME)
    assert client.post('/api/v1/auth/logout', headers={'Origin':ORIGIN}).status_code == 403
    assert client.post('/api/v1/auth/logout', headers=headers(csrf)).status_code == 200
    assert client.cookies.get(COOKIE_NAME) is None
    replay = env['client']()
    replay.cookies.set(COOKIE_NAME, old, path='/api/v1')
    assert replay.get('/api/v1/auth/me').status_code == 401
    assert replay.patch('/api/v1/me/profile', json={'year':2}, headers=headers(csrf)).status_code == 401


def test_expiry_deactivation_and_session_role_changes(env):
    client, _ = env['login']()
    with env['engine'].begin() as conn:
        conn.execute(update(User).where(User.id == env['ids']['a']).values(active=False))
    assert client.get('/api/v1/auth/me').status_code == 401
    with env['engine'].begin() as conn:
        conn.execute(update(User).where(User.id == env['ids']['a']).values(active=True))
    env['clock'][0] += timedelta(seconds=env['app'].state.settings.session_ttl_seconds)
    assert client.get('/api/v1/auth/me').status_code == 401


def test_invalid_login_and_rate_limit_commits_across_failures(env):
    env['app'].state.settings.login_limit_per_minute = 2
    client = env['client']()
    csrf = client.get('/api/v1/auth/csrf').json()['csrf_token']
    payload = {'username': env['ids']['a'], 'password':'wrong-password'}
    first = client.post('/api/v1/auth/login', json=payload, headers=headers(csrf))
    assert first.status_code == 401 and first.json()['error']['code'] == 'invalid_credentials'
    assert client.post('/api/v1/auth/login', json=payload, headers=headers(csrf)).status_code == 401
    limited = client.post('/api/v1/auth/login', json=payload, headers=headers(csrf))
    assert limited.status_code == 429 and int(limited.headers['retry-after']) > 0
    env['clock'][0] += timedelta(seconds=61)
    payload['password'] = PASSWORD
    assert client.post('/api/v1/auth/login', json=payload, headers=headers(csrf)).status_code == 200


def test_account_limit_shared_between_clients(env):
    env['app'].state.settings.login_limit_per_minute = 1
    one, two = env['client'](), env['client']()
    for index, client in enumerate((one, two)):
        csrf = client.get('/api/v1/auth/csrf').json()['csrf_token']
        result = client.post('/api/v1/auth/login', json={'username':env['ids']['a'], 'password':'wrong'}, headers=headers(csrf))
        assert result.status_code == (401 if index == 0 else 429)


def test_csrf_expiry_rate_limit_cors_and_body_limits(env):
    client = env['client']()
    csrf = client.get('/api/v1/auth/csrf').json()['csrf_token']
    env['clock'][0] += timedelta(seconds=env['app'].state.settings.preauth_ttl_seconds)
    assert client.post('/api/v1/auth/login', json={'username':env['ids']['a'], 'password':PASSWORD}, headers=headers(csrf)).status_code == 401
    env['app'].state.settings.csrf_limit_per_minute = 1
    fresh = env['client']()
    assert fresh.get('/api/v1/auth/csrf').status_code == 200
    assert fresh.get('/api/v1/auth/csrf').status_code == 429
    preflight = client.options('/api/v1/me/profile', headers={'Origin':ORIGIN, 'Access-Control-Request-Method':'PATCH','Access-Control-Request-Headers':'X-CSRF-Token,Content-Type'})
    assert preflight.status_code == 200
    assert preflight.headers['access-control-allow-origin'] == ORIGIN
    assert preflight.headers['access-control-allow-credentials'] == 'true'
    evil = client.options('/api/v1/me/profile', headers={'Origin':'https://evil.example','Access-Control-Request-Method':'PATCH'})
    assert evil.status_code == 400 and 'access-control-allow-origin' not in evil.headers
    oversized = client.post('/api/v1/auth/login', content='x'*16385)
    assert oversized.status_code == 413 and oversized.json()['error']['code'] == 'request_too_large'


def test_secure_cookie_configuration(env):
    settings = Settings(cookie_secure=True)
    with TestClient(create_app(settings), base_url='https://testserver', client=('secure-'+uuid4().hex, 50000)) as client:
        response = client.get('/api/v1/auth/csrf')
        assert response.status_code == 200
        assert 'Secure' in response.headers['set-cookie']


def test_session_role_is_read_from_database(env):
    client, _ = env['login']('admin')
    assert client.get('/api/v1/admin/access').status_code == 200
    with env['engine'].begin() as conn:
        conn.execute(update(User).where(User.id == env['ids']['admin']).values(role='student'))
    assert client.get('/api/v1/admin/access').status_code == 403


def test_unknown_username_and_wrong_password_share_error(env):
    client = env['client']()
    csrf = client.get('/api/v1/auth/csrf').json()['csrf_token']
    errors = []
    for username in (env['ids']['a'], 'missing-'+uuid4().hex):
        response = client.post('/api/v1/auth/login', json={'username':username, 'password':'wrong'}, headers=headers(csrf))
        assert response.status_code == 401
        errors.append((response.json()['error']['code'], response.json()['error']['message']))
    assert errors[0] == errors[1]


def test_empty_database_migrations():
    import subprocess
    import sys
    subprocess.run([sys.executable, '/workspace/scripts/check_migrations.py'], check=True)
