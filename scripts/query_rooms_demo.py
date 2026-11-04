"""Fixed-clock room query, independently testable from HTTP/NLP."""
import json
from datetime import datetime
from app.config import Settings
from app.db.connection import make_engine
from app.schemas.rooms import AvailabilityQuery
from app.services.rooms import available_rooms

settings=Settings(); engine=make_engine(settings)
clock=datetime.fromisoformat('2026-11-04T10:00:00+05:30')
try:
    with engine.begin() as conn:
        result=available_rooms(conn,AvailabilityQuery(from_at='2026-11-04T15:00:00+05:30',to_at='2026-11-04T16:00:00+05:30',
            building_id='block-b',facility_ids=['projector'],min_capacity=20),clock)
    print(json.dumps({'demo':True,'reference_clock':clock.isoformat(),'result':result.model_dump(mode='json')},indent=2))
finally:
    engine.dispose()
