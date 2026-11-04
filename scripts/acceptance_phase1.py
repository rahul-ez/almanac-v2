"""Real HTTP walkthrough; credentials stay in a local ignored file, never in output."""
import json
from pathlib import Path
from contextlib import ExitStack
import httpx

BASE = 'http://127.0.0.1:8000'
ORIGIN = 'http://localhost:8000'
path = Path('/workspace/.local/demo-accounts.json')
if not path.exists():
    raise SystemExit('Run make provision-demo first')
accounts = {row['username']: row for row in json.loads(path.read_text())}

def check(response, status, label):
    assert response.status_code == status, f'{label}: expected {status}, got {response.status_code}'
    assert response.headers.get('x-request-id'), label
    print(f'PASS {label}: {status}')
    return response

with ExitStack() as stack:
    def client():
        return stack.enter_context(httpx.Client(base_url=BASE, timeout=10))
    def login(name):
        c = client()
        token = check(c.get('/api/v1/auth/csrf'), 200, name+' CSRF initialization').json()['csrf_token']
        account = accounts[name]
        response = check(c.post('/api/v1/auth/login', json={'username':name, 'password':account['password']},
            headers={'Origin':ORIGIN, 'X-CSRF-Token':token}), 200, name+' login')
        return c, {'Origin':ORIGIN, 'X-CSRF-Token':response.json()['csrf_token']}
    anonymous = client()
    check(anonymous.get('/api/v1/auth/me'), 401, 'anonymous access rejected')
    a, ha = login('student-a')
    b, hb = login('student-b')
    admin, admin_headers = login('admin')
    check(a.get('/api/v1/admin/access'), 403, 'student admin access rejected')
    check(admin.get('/api/v1/admin/access'), 200, 'admin access accepted')
    check(a.get('/api/v1/reference-data'), 200, 'authenticated reference data')
    original = check(a.get('/api/v1/me/profile'), 200, 'student A profile').json()
    original_b = check(b.get('/api/v1/me/profile'), 200, 'student B profile').json()
    desired_year = 2 if original['year'] != 2 else 3
    try:
        result = check(a.patch('/api/v1/me/profile', json={'year':desired_year}, headers=ha), 200, 'own profile update')
        assert result.json()['year'] == desired_year
        assert a.get('/api/v1/me/profile').json()['year'] == desired_year
        assert b.get('/api/v1/me/profile').json() == original_b
        print('PASS persisted profile and student isolation')
        check(b.patch('/api/v1/me/profile', json={'year':4}, headers=ha), 403, 'another session CSRF token rejected')
        check(a.patch('/api/v1/me/profile', json={'role':'admin'}, headers=ha), 422, 'role escalation rejected')
        check(a.patch('/api/v1/me/profile', json={'year':4}), 403, 'missing CSRF/origin rejected')
        check(a.patch('/api/v1/me/profile', json={'year':4}, headers={**ha,'Origin':'https://evil.example'}), 403, 'hostile origin rejected')
    finally:
        restore = {key: original[key] for key in ('department_id','year','section','interests')}
        check(a.patch('/api/v1/me/profile', json=restore, headers=ha), 200, 'original demo profile restored')
    old_token = a.cookies.get('almanac_session')
    check(a.post('/api/v1/auth/logout', headers=ha), 200, 'logout')
    check(a.get('/api/v1/auth/me'), 401, 'logged-out access rejected')
    replay = client()
    replay.cookies.set('almanac_session', old_token, path='/api/v1')
    check(replay.get('/api/v1/auth/me'), 401, 'revoked cookie replay rejected')
    check(b.post('/api/v1/auth/logout', headers=hb), 200, 'student B logout')
    check(admin.post('/api/v1/auth/logout', headers=admin_headers), 200, 'admin logout')
print('Phase 1 live acceptance passed; demo profiles preserved.')
