"""Explicit fixed synthetic faculty publication; insert-only and repeatable."""
import json
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import insert,select,make_url
from app.config import Settings
from app.db.connection import make_engine
from app.db.faculty_models import Faculty,FacultyAlias,OfficeHour,OfficeHourException
from app.schemas.faculty import FacultyData,AliasData,OfficeHourData,OfficeExceptionData
from app.services.rooms import row,values
from app.services.faculty import normalize_name,validate_department,lock_faculty,validate_plan,exceptions_for,audit


def seed_faculty():
    settings=Settings()
    if make_url(settings.database_url.get_secret_value()).database not in {'almanac_demo','almanac_test'}:
        raise SystemExit('Faculty seed requires almanac_demo or almanac_test')
    engine=make_engine(settings);now=datetime.now(timezone.utc)
    source=json.loads(Path('/workspace/data/demo/faculty.json').read_text())
    try:
        with engine.begin() as conn:
            for key,model,schema in [('faculty',Faculty,FacultyData),('aliases',FacultyAlias,AliasData),('office-hours',OfficeHour,OfficeHourData),('exceptions',OfficeHourException,OfficeExceptionData)]:
                for record in source[key]:
                    record_id=record.pop('id')
                    if conn.execute(select(model.id).where(model.id == record_id)).first(): continue
                    data=values(schema(**record,source_label='Synthetic published faculty timetable v1'))
                    if model is Faculty:
                        validate_department(conn,data['department_id']);data['normalized_name']=normalize_name(data['name']);data['timezone']=settings.campus_timezone;faculty_id=record_id
                    elif model is FacultyAlias:
                        lock_faculty(conn,[data['canonical_id']]);data['normalized_alias']=normalize_name(data['alias']);faculty_id=data['canonical_id']
                    elif model is OfficeHour:
                        faculty=lock_faculty(conn,[data['faculty_id']])[data['faculty_id']];data['timezone']=faculty['timezone']
                        validate_plan(conn,faculty,dict(data,id=record_id),[]);faculty_id=faculty['id']
                    else:
                        rule=row(conn,OfficeHour,data['office_hour_id'],lock=True);faculty=lock_faculty(conn,[rule['faculty_id']])[rule['faculty_id']]
                        validate_plan(conn,faculty,rule,exceptions_for(conn,rule['id'])+[dict(data,id=record_id)]);faculty_id=faculty['id']
                    conn.execute(insert(model).values(**data,id=record_id,version=1,updated_at=now))
                    audit(conn,faculty_id,key,record_id,None,'seed',1,now)
    finally: engine.dispose()
    print('Synthetic faculty timetable v1 seeded; existing records preserved.')

if __name__ == '__main__': seed_faculty()
