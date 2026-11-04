import json
import subprocess
import sys
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.config import Settings
from app.db.connection import make_engine
from app.db.seed import seed
from app.main import create_app
from app.schemas.contracts import Interval


def test_config_and_intervals():
    with pytest.raises(ValidationError):
        Settings(database_url='sqlite:///local.db')
    with pytest.raises(ValidationError):
        Settings(campus_timezone='invalid/zone')
    with pytest.raises(ValidationError):
        Settings(nlp_mode='hybrid')
    with pytest.raises(ValidationError):
        Interval(start='2026-11-04T10:00:00', end='2026-11-04T11:00:00')
    with pytest.raises(ValidationError):
        Interval(start='2026-11-04T11:00:00Z', end='2026-11-04T10:00:00Z')


def test_live_survives_database_outage(caplog):
    settings = Settings(database_url='postgresql+psycopg://no:secret@127.0.0.1:1/almanac_demo')
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/v1/health/live').status_code == 200
        ready = client.get('/api/v1/health/ready')
        assert ready.status_code == 503
        assert ready.json()['checks']['database'] == 'unavailable'
        failed = client.get('/api/v1/demo/event')
        assert failed.status_code == 503
        assert failed.json()['error']['code'] == 'dependency_unavailable'
        missing = client.get('/missing?password=do-not-log')
        assert missing.status_code == 404
        assert missing.json()['error']['request_id'] == missing.headers['x-request-id']
    assert 'do-not-log' not in '\n'.join(r.message for r in caplog.records if r.name == 'almanac')
    assert 'secret' not in ready.text + failed.text


def test_real_database_and_seed():
    # Tests use a transaction for invalid rows and leave existing demo data intact.
    seed()
    seed()
    engine = make_engine(Settings())
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM demo_events WHERE id='demo-event-ml-workshop'")).scalar_one() == 1
        with pytest.raises(IntegrityError):
            conn.execute(text("INSERT INTO demo_events VALUES ('invalid-test', 'bad', now(), now(), -1, 'test', now())"))
        conn.rollback()
    engine.dispose()
    with TestClient(create_app()) as client:
        assert client.get('/api/v1/health/ready').status_code == 200
        event = client.get('/api/v1/demo/event')
        assert event.status_code == 200 and event.json()['demo'] is True
        assert event.json()['cost_minor'] == 0
        assert datetime.fromisoformat(event.json()['starts_at']).astimezone(timezone.utc).hour == 8


def test_committed_contracts_and_fixtures():
    subprocess.run([sys.executable, '/workspace/scripts/contracts.py'], check=True)


def test_seed_reset_requires_confirmation():
    result = subprocess.run([sys.executable, '-m', 'app.db.seed', '--reset'], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'Reset requires --confirm-demo-only' in result.stderr
