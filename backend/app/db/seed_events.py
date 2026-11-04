import json
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import make_url
from sqlalchemy.dialects.postgresql import insert
from app.config import Settings
from app.db.connection import make_engine
from app.db.models import Event
from app.schemas.events import EventCreate
from app.services.events import db_values, references


def seed_events():
    settings = Settings()
    if make_url(settings.database_url.get_secret_value()).database not in {'almanac_demo','almanac_test'}:
        raise SystemExit('Event demo seed requires almanac_demo or almanac_test')
    engine = make_engine(settings)
    try:
        with engine.begin() as conn:
            for row in json.loads(Path('/workspace/data/demo/campus-events.json').read_text()):
                record_id = row.pop('id')
                values = db_values(EventCreate.model_validate(row))
                references(conn, values)
                conn.execute(insert(Event).values(id=record_id,version=1,updated_at=datetime.now(timezone.utc),**values).on_conflict_do_nothing())
    finally:
        engine.dispose()
    print('Synthetic campus event seed v1 applied; existing records preserved.')

if __name__ == '__main__':
    seed_events()
