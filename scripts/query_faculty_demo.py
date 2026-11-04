import json
from datetime import datetime
from app.config import Settings
from app.db.connection import make_engine
from app.schemas.faculty import ResolveQuery,OfficeHoursQuery
from app.services.faculty import resolve_faculty,office_hours

engine=make_engine(Settings());clock=datetime.fromisoformat('2026-11-04T10:00:00+05:30')
try:
    with engine.begin() as conn:
        resolution=resolve_faculty(conn,ResolveQuery(name='Professor Rao'))
        hours=office_hours(conn,'campus-demo-anita-rao',OfficeHoursQuery(from_at='2026-11-06T00:00:00+05:30',to_at='2026-11-07T00:00:00+05:30'),clock)
    print(json.dumps({'demo':True,'reference_clock':clock.isoformat(),'resolution':resolution.model_dump(mode='json'),'office_hours':hours.model_dump(mode='json')},indent=2))
finally: engine.dispose()
