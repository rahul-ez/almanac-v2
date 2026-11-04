"""Fixed synthetic records loaded only into a newly created disposable evaluation database."""
import json
from datetime import datetime
from pathlib import Path
from sqlalchemy import insert
from app.db.models import Event
from app.db.provision import REFERENCES
from app.db.room_models import Room,RoomFacility,Booking,BookingException,RoomClosure
from app.db.faculty_models import Faculty,FacultyAlias,OfficeHour,OfficeHourException
from app.schemas.events import EventCreate
from app.schemas.rooms import RoomData,BookingData,ExceptionData,ClosureData
from app.schemas.faculty import FacultyData,AliasData,OfficeHourData,OfficeExceptionData
from app.services.events import db_values
from app.services.rooms import values
from app.services.faculty import normalize_name


def load_records(conn,root,clock,zone):
    for model,entries in REFERENCES.items():
        conn.execute(insert(model),[{'id':key,'label':label} for key,label in entries])
    source=Path(root)/'data/demo'
    for record in json.loads((source/'campus-events.json').read_text()):
        record_id=record.pop('id')
        conn.execute(insert(Event).values(id=record_id,version=1,updated_at=clock,**db_values(EventCreate(**record))))
    rooms=json.loads((source/'rooms.json').read_text())
    for record in rooms['rooms']:
        record_id=record.pop('id')
        data=values(RoomData(**record,opening_hours=[{'weekday':d,'start':'08:00','end':'18:00'} for d in range(5)],
            coverage_start='2026-11-02T00:00:00+05:30',coverage_end='2027-01-01T00:00:00+05:30',source_label='Frozen synthetic evaluation'))
        facilities=data.pop('facility_ids')
        conn.execute(insert(Room).values(**data,id=record_id,version=1,updated_at=clock,timezone=zone))
        if facilities: conn.execute(insert(RoomFacility),[{'room_id':record_id,'facility_id':f} for f in facilities])
    for key,model,schema in [('bookings',Booking,BookingData),('exceptions',BookingException,ExceptionData),('closures',RoomClosure,ClosureData)]:
        for record in rooms[key]:
            record_id=record.pop('id')
            conn.execute(insert(model).values(**values(schema(**record,source_label='Frozen synthetic evaluation')),id=record_id,version=1,updated_at=clock))
    faculty=json.loads((source/'faculty.json').read_text())
    for key,model,schema in [('faculty',Faculty,FacultyData),('aliases',FacultyAlias,AliasData),('office-hours',OfficeHour,OfficeHourData),('exceptions',OfficeHourException,OfficeExceptionData)]:
        for record in faculty[key]:
            record_id=record.pop('id');data=values(schema(**record,source_label='Frozen synthetic evaluation'))
            if model is Faculty: data.update(normalized_name=normalize_name(data['name']),timezone=zone)
            elif model is FacultyAlias: data['normalized_alias']=normalize_name(data['alias'])
            elif model is OfficeHour: data['timezone']=zone
            conn.execute(insert(model).values(**data,id=record_id,version=1,updated_at=clock))
