"""Verify migration paths in a newly created, uniquely named local database."""
import os
import subprocess
import sys
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.config import Settings

url = make_url(Settings().database_url.get_secret_value())
name = 'almanac_migration_' + uuid4().hex
admin = create_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT')
created = False
try:
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
        created = True
    env = dict(os.environ, DATABASE_URL=url.set(database=name).render_as_string(hide_password=False))
    for args in [('upgrade','head'), ('check',), ('downgrade','0001'), ('upgrade','head')]:
        result = subprocess.run(['alembic', *args], env=env, capture_output=True, text=True)
        if result.returncode:
            # Migration output may contain DSNs; never echo it to CI logs.
            raise SystemExit(f'Migration verification failed at {args}; inspect locally without exposing credentials')
    print('PASS empty database -> head, metadata check, downgrade to 0001 -> head')
finally:
    if created:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()
