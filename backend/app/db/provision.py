"""Explicit local-only demo provisioning. Never prints passwords or updates existing users."""
import json
import os
from pathlib import Path
from sqlalchemy import make_url
from sqlalchemy.dialects.postgresql import insert
from app.auth.security import passwords, new_token
from app.config import Settings
from app.db.connection import make_engine
from app.db.models import User, StudentProfile, Department, Building, Topic
from app.db.room_models import Facility

CREDENTIALS = Path('/workspace/.local/demo-accounts.json')
REFERENCES = {
    Facility: [('projector','Projector'),('whiteboard','Whiteboard'),('computers','Computers')],
    Department: [('aiml', 'Artificial Intelligence and Machine Learning'), ('cse', 'Computer Science')],
    Building: [('block-b', 'B Block'), ('faculty-block', 'Faculty Block')],
    Topic: [('artificial_intelligence', 'Artificial Intelligence'), ('machine_learning', 'Machine Learning'), ('web_development', 'Web Development')],
}

def provision():
    settings = Settings()
    if make_url(settings.database_url.get_secret_value()).database not in {'almanac_demo', 'almanac_test'}:
        raise SystemExit('Demo provisioning requires almanac_demo or almanac_test')
    CREDENTIALS.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(CREDENTIALS.parent, 0o700)
    if not CREDENTIALS.exists():
        accounts = [{'id': 'demo-' + name, 'username': name, 'role': role, 'password': new_token()}
                    for name, role in [('admin', 'admin'), ('student-a', 'student'), ('student-b', 'student')]]
        descriptor = os.open(CREDENTIALS, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(accounts, stream, indent=2)
            stream.write('\n')
    else:
        accounts = json.loads(CREDENTIALS.read_text())
        os.chmod(CREDENTIALS, 0o600)
    engine = make_engine(settings)
    try:
        with engine.begin() as conn:
            for model, rows in REFERENCES.items():
                conn.execute(insert(model).values([{'id': key, 'label': label} for key, label in rows]).on_conflict_do_nothing())
            for account in accounts:
                conn.execute(insert(User).values(id=account['id'], username=account['username'], role=account['role'],
                    active=True, password_hash=passwords.hash(account['password'])).on_conflict_do_nothing())
                if account['role'] == 'student':
                    conn.execute(insert(StudentProfile).values(user_id=account['id'], department_id=None, year=None, section=None).on_conflict_do_nothing())
    finally:
        engine.dispose()
    print('Demo identities/reference data provisioned; existing users/profiles preserved.')
    print('Passwords are in .local/demo-accounts.json (ignored by Git); no passwords printed.')

if __name__ == '__main__':
    provision()
