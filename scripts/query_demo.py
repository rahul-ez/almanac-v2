"""Local typed service walkthrough; no debug meaning endpoint is exposed."""
import json
from datetime import datetime
from app.config import Settings
from app.db.connection import make_engine
from app.schemas.events import EventSearch
from app.services.events import search_events

settings = Settings()
engine = make_engine(settings)
clock = datetime.fromisoformat('2026-11-04T10:00:00+05:30')
try:
    with engine.connect() as conn:
        result = search_events(conn,EventSearch(from_at='2026-11-02T00:00:00+05:30',to_at='2026-11-09T00:00:00+05:30',event_type='workshop',max_cost_minor=0,student_year=2,eligible_only=True),clock)
    print(json.dumps({'demo':True,'reference_clock':clock.isoformat(),'result':result.model_dump(mode='json')},indent=2))
finally:
    engine.dispose()
