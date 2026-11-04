"""Room CRUD and availability. Every schedule mutation locks its room(s)."""
import base64
import hashlib
import json
from uuid import uuid4
from datetime import timedelta
from pydantic import ValidationError
from sqlalchemy import select, insert, update, delete
from sqlalchemy.exc import IntegrityError
from app.api.errors import ApiError
from app.db.models import Building
from app.db.room_models import Room, RoomFacility, Facility, Booking, BookingException, RoomClosure, RoomAudit
from app.schemas.rooms import (RoomData,RoomView,BookingData,BookingView,ExceptionData,ExceptionView,
    ClosureData,ClosureView,AvailabilityPage,RoomAvailability,RequestedInterval)
from app.services.room_time import effective_occurrences, ensure_no_conflicts, overlaps, within_opening_hours

RESOURCES = {'rooms':(Room,RoomData,RoomView),'bookings':(Booking,BookingData,BookingView),
             'booking-exceptions':(BookingException,ExceptionData,ExceptionView),'room-closures':(RoomClosure,ClosureData,ClosureView)}

def row(conn,model,record_id,lock=False):
    query=select(model.__table__).where(model.id == record_id)
    if lock:
        query=query.with_for_update(read=lock == 'share')
    found=conn.execute(query).mappings().first()
    if found is None:
        raise ApiError(404,'not_found','Record not found')
    return dict(found)


def room_value(conn,record):
    return dict(record,facility_ids=list(conn.execute(select(RoomFacility.facility_id).where(
        RoomFacility.room_id == record['id']).order_by(RoomFacility.facility_id)).scalars()))


def detail(conn,resource,record_id,student=False):
    model,_,schema=RESOURCES[resource]
    result=row(conn,model,record_id)
    if student and result['status'] == 'archived':
        raise ApiError(404,'not_found','Room not found')
    return schema.model_validate(room_value(conn,result) if model is Room else result)


def lock_rooms(conn,ids):
    found=list(conn.execute(select(Room.__table__).where(Room.id.in_(sorted(set(ids)))).order_by(Room.id).with_for_update()).mappings())
    if len(found) != len(set(ids)):
        raise ApiError(422,'validation_error','Unknown room')
    return {r['id']:dict(r) for r in found}


def values(model):
    result=model.model_dump()
    result['source_url']=str(model.source_url) if model.source_url else None
    return result


def validate_room_refs(conn,data):
    if not conn.execute(select(Building.id).where(Building.id == data['building_id'])).first():
        raise ApiError(422,'validation_error','Unknown building')
    known=set(conn.execute(select(Facility.id).where(Facility.id.in_(data['facility_ids']))).scalars())
    if known != set(data['facility_ids']):
        raise ApiError(422,'validation_error','Unknown facility')


def audit(conn,room_id,resource,record_id,actor,action,version,now):
    conn.execute(insert(RoomAudit).values(id=str(uuid4()),room_id=room_id,resource=resource,record_id=record_id,
        actor_id=actor,action=action,version=version,occurred_at=now))


def exceptions_for(conn,booking_id):
    return [dict(r) for r in conn.execute(select(BookingException.__table__).where(BookingException.booking_id == booking_id)).mappings()]


def validate_booking_plan(conn,room,booking,exceptions):
    proposed=effective_occurrences(booking,exceptions,room['timezone'])
    occupied=[]
    others=conn.execute(select(Booking.__table__).where(Booking.room_id == room['id'],Booking.id != booking['id'],Booking.status == 'active')).mappings()
    for other in others:
        occupied.extend(effective_occurrences(other,exceptions_for(conn,other['id']),room['timezone']))
    ensure_no_conflicts(proposed,occupied)


def write(conn,resource,payload,actor,now,campus_timezone,record_id=None):
    model,data_schema,view_schema=RESOURCES[resource]
    existing=None
    if record_id:
        if model is BookingException:
            # Serialize on parent before child, consistently with booking edits.
            before=row(conn,model,record_id)
            parent=row(conn,Booking,before['booking_id'],lock=True)
        existing=row(conn,model,record_id,lock=True)
        if existing['version'] != payload.version:
            raise ApiError(409,'version_conflict','Record changed; reload before editing')
        if existing['status'] == 'archived':
            raise ApiError(409,'record_archived','Archived records cannot be edited')
        prior=room_value(conn,existing) if model is Room else existing
        merged={key:prior[key] for key in data_schema.model_fields}
        merged.update(payload.model_dump(exclude_unset=True,exclude={'version'}))
        try:
            data=values(data_schema.model_validate(merged))
        except ValidationError:
            raise ApiError(422,'validation_error','Invalid fields or schedule interval') from None
    else:
        data=values(payload)
        if data['status'] == 'archived':
            raise ApiError(422,'validation_error','Create an active record before archiving')
        record_id=str(uuid4())
    version=existing['version']+1 if existing else 1
    if model is Room:
        validate_room_refs(conn,data)
        facilities=data.pop('facility_ids')
        # Existing room row is already locked; timezone is immutable per room.
        data['timezone']=existing['timezone'] if existing else campus_timezone
        room_id=record_id
    elif model is Booking:
        ids=[data['room_id']]+([existing['room_id']] if existing else [])
        rooms=lock_rooms(conn,ids)
        target=rooms[data['room_id']]
        if target['status'] == 'archived' and data['status'] == 'active':
            raise ApiError(409,'room_archived','Room is archived')
        validate_booking_plan(conn,target,dict(data,id=record_id),exceptions_for(conn,record_id) if existing else [])
        room_id=data['room_id']
    elif model is BookingException:
        if existing and data['booking_id'] != existing['booking_id']:
            raise ApiError(422,'validation_error','An exception cannot change its parent booking')
        parent=row(conn,Booking,data['booking_id'],lock=True)
        room=lock_rooms(conn,[parent['room_id']])[parent['room_id']]
        if room['status'] == 'archived' and data['status'] == 'active':
            raise ApiError(409,'room_archived','Room is archived')
        current=[r for r in exceptions_for(conn,parent['id']) if r['id'] != record_id]
        validate_booking_plan(conn,room,parent,current+[dict(data,id=record_id)])
        room_id=parent['room_id']
    else:
        ids=[data['room_id']]+([existing['room_id']] if existing else [])
        rooms=lock_rooms(conn,ids)
        if rooms[data['room_id']]['status'] == 'archived' and data['status'] == 'active':
            raise ApiError(409,'room_archived','Room is archived')
        room_id=data['room_id']
        # Closures are allowed to overlap bookings and take precedence in availability.
    try:
        with conn.begin_nested():
            if existing:
                conn.execute(update(model).where(model.id == record_id).values(**data,version=version,updated_at=now))
            else:
                conn.execute(insert(model).values(**data,id=record_id,version=version,updated_at=now))
            if model is Room:
                conn.execute(delete(RoomFacility).where(RoomFacility.room_id == record_id))
                if facilities:
                    conn.execute(insert(RoomFacility),[{'room_id':record_id,'facility_id':f} for f in facilities])
    except IntegrityError:
        raise ApiError(409,'record_conflict','Room code or active exception already exists') from None
    if model is BookingException:
        conn.execute(update(Booking).where(Booking.id == parent['id']).values(version=parent['version']+1,updated_at=now))
        audit(conn,room_id,'bookings',parent['id'],actor,'exception_change',parent['version']+1,now)
    audit(conn,room_id,resource,record_id,actor,'archive' if data['status'] == 'archived' else ('update' if existing else 'create'),version,now)
    return detail(conn,resource,record_id)


def cursor_state(query,scope):
    signature=hashlib.sha256(json.dumps({'scope':scope,**query.model_dump(mode='json',exclude={'cursor'})},sort_keys=True).encode()).hexdigest()
    after=None
    if query.cursor:
        try:
            after,prior=json.loads(base64.urlsafe_b64decode(query.cursor.encode()))
            if not isinstance(after,str) or not after or len(after)>80 or prior != signature:
                raise ValueError()
        except (ValueError,TypeError,UnicodeError):
            raise ApiError(422,'invalid_cursor','Cursor does not match this query') from None
    return after,signature


def next_cursor(record,signature):
    return base64.urlsafe_b64encode(json.dumps([record['id'],signature]).encode()).decode()


def inventory(conn,resource,query,public=False):
    model,_,schema=RESOURCES[resource]
    after,signature=cursor_state(query,resource+(':public' if public else ':admin'))
    conditions=[model.status != 'archived']
    if after:
        conditions.append(model.id > after)
    if query.room_id:
        if model is BookingException:
            conditions.append(model.booking_id.in_(select(Booking.id).where(Booking.room_id == query.room_id)))
        else:
            conditions.append((model.id if model is Room else model.room_id) == query.room_id)
    if query.search:
        field=Room.code if model is Room else Booking.purpose if model is Booking else RoomClosure.reason if model is RoomClosure else BookingException.note
        conditions.append(field.icontains(query.search,autoescape=True))
    found=list(conn.execute(select(model.__table__).where(*conditions).order_by(model.id).limit(query.limit+1)).mappings())
    more=len(found)>query.limit
    found=found[:query.limit]
    return {'items':[schema.model_validate(room_value(conn,r) if model is Room else r) for r in found],
            'next_cursor':next_cursor(found[-1],signature) if more else None}


def evaluate_room(conn,room,start,end):
    reasons=[]
    hours_unknown=room['opening_hours'] is None
    if not hours_unknown and not within_opening_hours(room,start,end):
        reasons.append('outside_opening_hours')
    if conn.execute(select(RoomClosure.id).where(RoomClosure.room_id == room['id'],RoomClosure.status == 'active',RoomClosure.starts_at < end,RoomClosure.ends_at > start).limit(1)).first():
        reasons.append('room_closure')
    for booking in conn.execute(select(Booking.__table__).where(Booking.room_id == room['id'],Booking.status == 'active')).mappings():
        slots=effective_occurrences(booking,exceptions_for(conn,booking['id']),room['timezone'])
        if any(overlaps(slot,(start,end)) for slot in slots):
            reasons.append('scheduled_booking')
            break
    if reasons:
        status='unavailable'
    elif hours_unknown:
        status='unknown'; reasons=['opening_hours_unavailable']
    elif not room['coverage_complete'] or room['coverage_start'] is None or start < room['coverage_start'] or end > room['coverage_end']:
        status='unknown'; reasons=['incomplete_schedule_coverage']
    else:
        status='available'; reasons=['within_open_hours_and_complete_schedule_without_conflicts']
    return RoomAvailability(room=RoomView.model_validate(room_value(conn,room)),availability=status,reasons=reasons,
        requested_interval=RequestedInterval(start=start,end=end))


def validate_query_window(query,now):
    if query.from_at < now or query.to_at > now+timedelta(days=30):
        raise ApiError(422,'query_horizon','Availability must be between now and the next 30 days')


def available_rooms(conn,query,now,room_id=None):
    validate_query_window(query,now)
    if query.building_id and not conn.execute(select(Building.id).where(Building.id == query.building_id)).first():
        raise ApiError(422,'validation_error','Unknown building')
    known=set(conn.execute(select(Facility.id).where(Facility.id.in_(query.facility_ids))).scalars())
    if known != set(query.facility_ids):
        raise ApiError(422,'validation_error','Unknown facility')
    if room_id:
        room=row(conn,Room,room_id,lock='share')
        if room['status'] == 'archived':
            raise ApiError(404,'not_found','Room not found')
        result=evaluate_room(conn,room,query.from_at,query.to_at)
        mismatches=[]
        if room['capacity'] < query.min_capacity:
            mismatches.append('insufficient_capacity')
        if query.building_id and room['building_id'] != query.building_id:
            mismatches.append('building_mismatch')
        actual=set(result.room.facility_ids)
        if not set(query.facility_ids).issubset(actual):
            mismatches.append('missing_facilities')
        if mismatches:
            result=result.model_copy(update={'availability':'unavailable','reasons':mismatches+result.reasons})
        return result
    after,signature=cursor_state(query,'availability')
    conditions=[Room.status == 'active',Room.capacity >= query.min_capacity]
    if query.building_id:
        conditions.append(Room.building_id == query.building_id)
    if after:
        conditions.append(Room.id > after)
    for facility in query.facility_ids:
        conditions.append(Room.id.in_(select(RoomFacility.room_id).where(RoomFacility.facility_id == facility)))
    rows=list(conn.execute(select(Room.__table__).where(*conditions).order_by(Room.id).limit(query.limit+1).with_for_update(read=True)).mappings())
    more=len(rows)>query.limit; rows=rows[:query.limit]
    evaluated=[evaluate_room(conn,r,query.from_at,query.to_at) for r in rows]
    available=[r for r in evaluated if r.availability == 'available']
    unknown=[r for r in evaluated if r.availability == 'unknown']
    warnings=['Availability is based on maintained schedules, not physical occupancy.']
    coverage_missing=sum(1 for r in rows if r['opening_hours'] is None or not r['coverage_complete'] or r['coverage_start'] is None or query.from_at < r['coverage_start'] or query.to_at > r['coverage_end'])
    if coverage_missing:
        warnings.append('Some matching rooms have missing opening hours or incomplete schedule coverage; missing information is not proof of availability.')
    if more:
        warnings.append('Only this candidate page was checked. Continue with next_cursor; no-results applies to this page only.')
    return AvailabilityPage(status='answered' if available else 'information_unavailable' if unknown else 'no_results',items=available,
        unknown_rooms=unknown,checked_count=len(rows),next_cursor=next_cursor(rows[-1],signature) if more else None,
        data_coverage=('unknown' if coverage_missing == len(rows) else 'partial') if coverage_missing else 'complete',warnings=warnings)
