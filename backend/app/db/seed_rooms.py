"""Explicit repeatable synthetic semester timetable. Does not overwrite existing rows."""
import json
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import make_url,select,insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.config import Settings
from app.db.connection import make_engine
from app.db.room_models import Room,RoomFacility,Booking,BookingException,RoomClosure
from app.schemas.rooms import RoomData,BookingData,ExceptionData,ClosureData
from app.services.rooms import values,validate_room_refs,validate_booking_plan,lock_rooms,exceptions_for,row,audit


def seed_rooms():
    settings=Settings()
    if make_url(settings.database_url.get_secret_value()).database not in {'almanac_demo','almanac_test'}:
        raise SystemExit('Room seed requires almanac_demo or almanac_test')
    source=json.loads(Path('/workspace/data/demo/rooms.json').read_text())
    now=datetime.now(timezone.utc)
    engine=make_engine(settings)
    label='Synthetic room timetable v1'
    try:
        with engine.begin() as conn:
            for entry in source['rooms']:
                room_id=entry.pop('id')
                payload=RoomData(**entry,opening_hours=[{'weekday':d,'start':'08:00','end':'18:00'} for d in range(5)],
                    coverage_start='2026-11-02T00:00:00+05:30',coverage_end='2027-01-01T00:00:00+05:30',source_label=label)
                data=values(payload);validate_room_refs(conn,data);facilities=data.pop('facility_ids')
                created=conn.execute(pg_insert(Room).values(**data,id=room_id,version=1,updated_at=now,timezone=settings.campus_timezone)
                                     .on_conflict_do_nothing(index_elements=['id']).returning(Room.id)).scalar_one_or_none()
                if created:
                    if facilities:
                        conn.execute(insert(RoomFacility),[{'room_id':room_id,'facility_id':f} for f in facilities])
                    audit(conn,room_id,'rooms',room_id,None,'seed',1,now)
            for key,model,schema in [('bookings',Booking,BookingData),('exceptions',BookingException,ExceptionData),('closures',RoomClosure,ClosureData)]:
                for entry in source[key]:
                    record_id=entry.pop('id')
                    if conn.execute(select(model.id).where(model.id == record_id)).first():
                        continue
                    data=values(schema(**entry,source_label=label))
                    if model is BookingException:
                        parent=row(conn,Booking,data['booking_id'],lock=True)
                        room=lock_rooms(conn,[parent['room_id']])[parent['room_id']]
                        validate_booking_plan(conn,room,parent,exceptions_for(conn,parent['id'])+[dict(data,id=record_id)])
                        room_id=parent['room_id']
                    else:
                        room=lock_rooms(conn,[data['room_id']])[data['room_id']];room_id=room['id']
                        if model is Booking:
                            validate_booking_plan(conn,room,dict(data,id=record_id),[])
                    conn.execute(insert(model).values(**data,id=record_id,version=1,updated_at=now))
                    audit(conn,room_id,model.__tablename__.replace('_','-'),record_id,None,'seed',1,now)
    finally:
        engine.dispose()
    print('Synthetic room timetable v1 seeded; existing records preserved.')

if __name__ == '__main__':
    seed_rooms()
