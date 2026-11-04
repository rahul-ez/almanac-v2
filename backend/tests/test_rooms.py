from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from uuid import uuid4
import pytest
from sqlalchemy import insert,delete,select,func
from test_identity import env,headers
from app.db.models import Building
from app.db.room_models import Facility,Room,Booking,RoomClosure,RoomAudit
from app.services.room_time import base_occurrences,within_opening_hours

@pytest.fixture
def room_env(env):
    env['clock'][0]=datetime.fromisoformat('2036-11-04T10:00:00+05:30')
    building='building-'+uuid4().hex; facility='facility-'+uuid4().hex
    with env['engine'].begin() as conn:
        conn.execute(insert(Building).values(id=building,label='Test block'))
        conn.execute(insert(Facility).values(id=facility,label='Test projector'))
    admin,csrf=env['login']('admin'); student,token=env['login']('a')
    ids=[]
    def create_room(**changes):
        now=env['clock'][0]
        payload=dict(code='TEST-'+uuid4().hex,building_id=building,capacity=40,facility_ids=[facility],
            opening_hours=[{'weekday':d,'start':'00:00','end':'24:00'} for d in range(7)],
            coverage_start=(now-timedelta(days=1)).isoformat(),coverage_end=(now+timedelta(days=90)).isoformat(),
            coverage_complete=True,source_label='Synthetic test room')
        payload.update(changes)
        response=admin.post('/api/v1/admin/rooms',json=payload,headers=headers(csrf))
        if response.status_code == 201:
            ids.append(response.json()['id'])
        return response
    def booking(room_id,start=None,end=None,**changes):
        now=env['clock'][0]
        payload=dict(room_id=room_id,purpose='Test class',starts_at=(start or now+timedelta(hours=4)).isoformat(),
                     ends_at=(end or now+timedelta(hours=5)).isoformat(),source_label='Synthetic timetable')
        payload.update(changes)
        return admin.post('/api/v1/admin/bookings',json=payload,headers=headers(csrf))
    def availability(room_id,start=None,end=None,**filters):
        now=env['clock'][0]
        return student.get('/api/v1/rooms/'+room_id+'/availability',params={
            'from_at':(start or now+timedelta(hours=5)).isoformat(),'to_at':(end or now+timedelta(hours=6)).isoformat(),**filters})
    yield dict(env,admin=admin,csrf=csrf,student=student,token=token,building=building,facility=facility,
               create_room=create_room,booking=booking,availability=availability)
    with env['engine'].begin() as conn:
        conn.execute(delete(RoomClosure).where(RoomClosure.room_id.in_(ids)))
        conn.execute(delete(Booking).where(Booking.room_id.in_(ids)))
        conn.execute(delete(Room).where(Room.id.in_(ids)))
        conn.execute(delete(Facility).where(Facility.id == facility))
        conn.execute(delete(Building).where(Building.id == building))


def test_room_role_csrf_reference_validation_and_versions(room_env):
    e=room_env
    assert e['student'].post('/api/v1/admin/rooms',json={},headers=headers(e['token'])).status_code == 403
    for bad in ({'capacity':0},{'capacity':True},{'building_id':'unknown'},{'facility_ids':['unknown']},
                {'coverage_start':None},{'opening_hours':[{'weekday':0,'start':'14:00','end':'13:00'}]},
                {'opening_hours':[{'weekday':0,'start':'09:00','end':'12:00'},{'weekday':0,'start':'11:00','end':'13:00'}]}):
        response=e['create_room'](**bad)
        assert response.status_code == 422,(bad,response.text)
    record=e['create_room']().json(); url='/api/v1/admin/rooms/'+record['id']
    assert e['admin'].patch(url,json={'version':1,'capacity':50}).status_code == 403
    updated=e['admin'].patch(url,json={'version':1,'capacity':50},headers=headers(e['csrf']))
    assert updated.status_code == 200 and updated.json()['version'] == 2
    assert e['admin'].patch(url,json={'version':1,'capacity':60},headers=headers(e['csrf'])).status_code == 409
    assert e['create_room'](code=record['code'].lower()).status_code == 409
    assert e['admin'].delete(url,params={'version':2},headers=headers(e['csrf'])).status_code == 200
    assert e['student'].get('/api/v1/rooms/'+record['id']).status_code == 404
    assert e['booking'](record['id']).status_code == 409


def test_booking_boundaries_conflicts_and_unknown_coverage(room_env):
    e=room_env; room=e['create_room']().json(); now=e['clock'][0]
    first=e['booking'](room['id']); assert first.status_code == 201,first.text
    assert e['availability'](room['id']).json()['availability'] == 'available'
    hit=e['availability'](room['id'],start=now+timedelta(hours=4,minutes=59))
    assert hit.json()['availability'] == 'unavailable' and 'scheduled_booking' in hit.json()['reasons']
    assert e['booking'](room['id'],start=now+timedelta(hours=4,minutes=59),end=now+timedelta(hours=6)).status_code == 409
    assert e['booking'](room['id'],start=now+timedelta(hours=5),end=now+timedelta(hours=6)).status_code == 201
    unknown=e['create_room'](coverage_complete=False,coverage_start=None,coverage_end=None).json()
    assert e['availability'](unknown['id']).json()['availability'] == 'unknown'
    assert e['booking'](unknown['id']).status_code == 201
    assert e['availability'](unknown['id'],start=now+timedelta(hours=4),end=now+timedelta(hours=5)).json()['availability'] == 'unavailable'


def exception(e,booking,**changes):
    payload=dict(booking_id=booking['id'],occurrence_date=booking['starts_at'][:10],action='cancel',source_label='Synthetic exception')
    # UTC record date can differ; fixtures here occur during daytime campus time.
    payload.update(changes)
    return e['admin'].post('/api/v1/admin/booking-exceptions',json=payload,headers=headers(e['csrf']))


def test_weekly_recurrence_inclusive_end_and_cancellation(room_env):
    e=room_env; room=e['create_room']().json(); now=e['clock'][0]
    last=(now+timedelta(days=14)).date().isoformat()
    booking=e['booking'](room['id'],recurrence='weekly',recurrence_until=last).json()
    start=now+timedelta(days=14,hours=4); end=start+timedelta(hours=1)
    assert e['availability'](room['id'],start,end).json()['availability'] == 'unavailable'
    assert e['availability'](room['id'],start+timedelta(days=7),end+timedelta(days=7)).json()['availability'] == 'available'
    cancelled=exception(e,booking,occurrence_date=start.date().isoformat())
    assert cancelled.status_code == 201,cancelled.text
    assert e['availability'](room['id'],start,end).json()['availability'] == 'available'
    fresh=e['admin'].get('/api/v1/admin/bookings/'+booking['id']).json()
    assert fresh['version'] == 2
    assert e['admin'].patch('/api/v1/admin/bookings/'+booking['id'],json={'version':1,'purpose':'stale'},headers=headers(e['csrf'])).status_code == 409
    assert exception(e,booking,occurrence_date=start.date().isoformat()).status_code == 409
    assert exception(e,booking,occurrence_date=(start+timedelta(days=1)).date().isoformat()).status_code == 422


def test_replacement_moves_dates_and_detects_conflicts(room_env):
    e=room_env; room=e['create_room']().json(); now=e['clock'][0]
    booking=e['booking'](room['id'],recurrence='weekly',recurrence_until=(now+timedelta(days=14)).date().isoformat()).json()
    original=now+timedelta(days=7,hours=4)
    moved=original+timedelta(days=1)
    replacement=exception(e,booking,occurrence_date=original.date().isoformat(),action='replace',replacement_start=moved.isoformat(),replacement_end=(moved+timedelta(hours=1)).isoformat())
    assert replacement.status_code == 201,replacement.text
    assert e['availability'](room['id'],original,original+timedelta(hours=1)).json()['availability'] == 'available'
    assert e['availability'](room['id'],moved,moved+timedelta(hours=1)).json()['availability'] == 'unavailable'
    assert e['booking'](room['id'],start=moved,end=moved+timedelta(hours=1)).status_code == 409
    assert exception(e,booking,action='replace',replacement_start=(now+timedelta(days=20,hours=4)).isoformat(),replacement_end=(now+timedelta(days=20,hours=5)).isoformat()).status_code == 422


def test_restoring_cancelled_occurrence_cannot_overbook(room_env):
    e=room_env; room=e['create_room']().json(); booking=e['booking'](room['id']).json()
    cancelled=exception(e,booking).json()
    assert e['booking'](room['id']).status_code == 201
    restore=e['admin'].delete('/api/v1/admin/booking-exceptions/'+cancelled['id'],params={'version':1},headers=headers(e['csrf']))
    assert restore.status_code == 409
    assert e['admin'].get('/api/v1/admin/booking-exceptions/'+cancelled['id']).json()['status'] == 'active'
    # Parent schedule edits are also validated against effective occurrences.
    stale=e['admin'].get('/api/v1/admin/bookings/'+booking['id']).json()
    result=e['admin'].patch('/api/v1/admin/bookings/'+booking['id'],json={'version':stale['version'],'starts_at':(e['clock'][0]+timedelta(days=1,hours=4)).isoformat(),'ends_at':(e['clock'][0]+timedelta(days=1,hours=5)).isoformat()},headers=headers(e['csrf']))
    assert result.status_code == 422  # Would orphan the active exception.


def test_closures_override_booking_cancellations_and_opening_hours(room_env):
    e=room_env; room=e['create_room']().json(); now=e['clock'][0]
    booking=e['booking'](room['id']).json()
    payload=dict(room_id=room['id'],reason='Maintenance',starts_at=(now+timedelta(hours=4)).isoformat(),ends_at=(now+timedelta(hours=6)).isoformat(),source_label='Synthetic closure')
    closure=e['admin'].post('/api/v1/admin/room-closures',json=payload,headers=headers(e['csrf']))
    assert closure.status_code == 201,closure.text
    assert exception(e,booking).status_code == 201
    assert e['availability'](room['id']).json()['reasons'] == ['room_closure']
    assert e['admin'].delete('/api/v1/admin/room-closures/'+closure.json()['id'],params={'version':1},headers=headers(e['csrf'])).status_code == 200
    assert e['availability'](room['id']).json()['availability'] == 'available'
    closed=e['create_room'](opening_hours=[]).json()
    assert e['availability'](closed['id']).json()['reasons'] == ['outside_opening_hours']
    missing=e['create_room'](opening_hours=None).json()
    assert e['availability'](missing['id']).json()['availability'] == 'unknown'
    partial=e['create_room'](opening_hours=[{'weekday':(now+timedelta(hours=5)).weekday(),'start':'15:00','end':'15:30'}]).json()
    assert e['availability'](partial['id']).json()['availability'] == 'unavailable'


def test_concurrent_booking_inserts_and_reactivation(room_env):
    e=room_env; room=e['create_room']().json(); now=e['clock'][0]
    second,csrf=e['login']('admin')
    payload=dict(room_id=room['id'],purpose='Concurrent class',starts_at=(now+timedelta(hours=4)).isoformat(),ends_at=(now+timedelta(hours=5)).isoformat(),source_label='Test')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda args:args[0].post('/api/v1/admin/bookings',json=payload,headers=headers(args[1])),[(e['admin'],e['csrf']),(second,csrf)]))
    assert sorted(r.status_code for r in results) == [201,409]
    record=next(r.json() for r in results if r.status_code == 201)
    assert e['admin'].patch('/api/v1/admin/bookings/'+record['id'],json={'version':1,'status':'cancelled'},headers=headers(e['csrf'])).status_code == 200
    assert e['booking'](room['id']).status_code == 201
    assert e['admin'].patch('/api/v1/admin/bookings/'+record['id'],json={'version':2,'status':'active'},headers=headers(e['csrf'])).status_code == 409


def test_availability_filters_pagination_and_unknown_page(room_env):
    e=room_env
    good=e['create_room']().json(); unknown=e['create_room'](coverage_complete=False).json(); small=e['create_room'](capacity=5).json()
    now=e['clock'][0]
    params=dict(from_at=(now+timedelta(hours=5)).isoformat(),to_at=(now+timedelta(hours=6)).isoformat(),building_id=e['building'],min_capacity=10,limit=1)
    seen=[]; statuses=[]
    while True:
        result=e['student'].get('/api/v1/rooms/availability',params=params)
        assert result.status_code == 200,result.text
        data=result.json(); seen.extend([r['room']['id'] for r in data['items']+data['unknown_rooms']]);statuses.append(data['status'])
        if not data['next_cursor']:
            break
        params['cursor']=data['next_cursor']
    assert set(seen) == {good['id'],unknown['id']}
    assert 'answered' in statuses and 'information_unavailable' in statuses
    if params.get('cursor'):
        assert e['student'].get('/api/v1/rooms/availability',params={**params,'min_capacity':20}).status_code == 422
    assert e['availability'](small['id'],min_capacity=10).json()['availability'] == 'unavailable'
    assert e['availability'](good['id'],facility_ids='unknown').status_code == 422
    assert e['availability'](good['id'],start=now-timedelta(seconds=1)).status_code == 422
    assert e['availability'](good['id'],start=now+timedelta(days=30),end=now+timedelta(days=30,hours=1)).status_code == 422
    assert e['student'].get('/api/v1/rooms/availability',params={'to_at':params['to_at']}).status_code == 422


def test_recurrence_limits_dst_and_local_midnight():
    booking=dict(starts_at=datetime.fromisoformat('2026-03-01T02:30:00-05:00'),ends_at=datetime.fromisoformat('2026-03-01T03:30:00-05:00'),recurrence='weekly',recurrence_until=datetime.fromisoformat('2026-03-08').date())
    from app.api.errors import ApiError
    with pytest.raises(ApiError):
        base_occurrences(booking,'America/New_York')  # nonexistent spring-forward occurrence
    booking.update(starts_at=datetime.fromisoformat('2026-10-25T01:30:00-04:00'),ends_at=datetime.fromisoformat('2026-10-25T02:30:00-04:00'),recurrence_until=datetime.fromisoformat('2026-11-01').date())
    with pytest.raises(ApiError):
        base_occurrences(booking,'America/New_York')  # ambiguous fall-back occurrence
    start=datetime.fromisoformat('2026-11-04T23:30:00+05:30');end=start+timedelta(hours=1)
    room=dict(timezone='Asia/Kolkata',opening_hours=[{'weekday':2,'start':'23:00','end':'24:00'},{'weekday':3,'start':'00:00','end':'01:00'}])
    assert within_opening_hours(room,start,end)


def test_inventory_audit_and_cancel_exception_mutation_permissions(room_env):
    e=room_env; room=e['create_room']().json()
    booking=e['booking'](room['id']).json()
    assert e['student'].get('/api/v1/admin/bookings').status_code == 403
    assert e['student'].post('/api/v1/admin/booking-exceptions',json={},headers=headers(e['token'])).status_code == 403
    assert e['admin'].get('/api/v1/admin/bookings',params={'room_id':room['id']}).json()['items'][0]['id'] == booking['id']
    assert e['admin'].get('/api/v1/admin/rooms',params={'search':"%' OR 1=1 --"}).json()['items'] == []
    assert e['booking'](room['id'],recurrence='weekly',recurrence_until=(e['clock'][0]+timedelta(days=400)).date().isoformat()).status_code == 422
    with e['engine'].connect() as conn:
        assert conn.execute(select(func.count()).select_from(RoomAudit).where(RoomAudit.room_id == room['id'])).scalar_one() == 2


def test_concurrent_exception_moves_are_serialized(room_env):
    e=room_env; room=e['create_room']().json(); now=e['clock'][0]
    one=e['booking'](room['id']).json()
    two=e['booking'](room['id'],start=now+timedelta(hours=5),end=now+timedelta(hours=6)).json()
    second,csrf=e['login']('admin')
    def move(args):
        client,token,booking=args
        return client.post('/api/v1/admin/booking-exceptions',json=dict(booking_id=booking['id'],occurrence_date=now.date().isoformat(),action='replace',
            replacement_start=(now+timedelta(hours=8)).isoformat(),replacement_end=(now+timedelta(hours=9)).isoformat(),source_label='Test moved class'),headers=headers(token))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(move,[(e['admin'],e['csrf'],one),(second,csrf,two)]))
    assert sorted(r.status_code for r in results) == [201,409]
    assert e['availability'](room['id'],start=now+timedelta(hours=8),end=now+timedelta(hours=9)).json()['availability'] == 'unavailable'


def test_campus_local_occurrence_date_and_coverage_boundaries(room_env):
    e=room_env; room=e['create_room']().json(); now=e['clock'][0]
    local_midnight=now.replace(hour=0,minute=30)+timedelta(days=1)
    booking=e['booking'](room['id'],start=local_midnight,end=local_midnight+timedelta(hours=1)).json()
    # Its UTC calendar date is the previous day, but the exception uses the campus date.
    assert booking['starts_at'][:10] != local_midnight.date().isoformat()
    assert exception(e,booking,occurrence_date=local_midnight.date().isoformat()).status_code == 201
    assert e['availability'](room['id'],start=local_midnight,end=local_midnight+timedelta(hours=1)).json()['availability'] == 'available'
    changed=e['admin'].patch('/api/v1/admin/rooms/'+room['id'],json={'version':1,'coverage_start':local_midnight.isoformat(),'coverage_end':(local_midnight+timedelta(hours=1)).isoformat()},headers=headers(e['csrf']))
    assert changed.status_code == 200
    assert e['availability'](room['id'],start=local_midnight,end=local_midnight+timedelta(hours=1)).json()['availability'] == 'available'
    assert e['availability'](room['id'],start=local_midnight,end=local_midnight+timedelta(hours=1,seconds=1)).json()['availability'] == 'unknown'
    assert e['availability'](room['id'],facility_ids='projector').json()['availability'] == 'unavailable'


def test_database_rejects_missing_replacement_end(room_env):
    from app.db.room_models import BookingException
    from sqlalchemy.exc import IntegrityError
    e=room_env; room=e['create_room']().json(); booking=e['booking'](room['id']).json()
    now=e['clock'][0]
    with e['engine'].begin() as conn:
        with pytest.raises(IntegrityError):
            with conn.begin_nested():
                conn.execute(insert(BookingException).values(id='bad-'+uuid4().hex,version=1,updated_at=now,
                    booking_id=booking['id'],occurrence_date=now.date(),action='replace',replacement_start=now,
                    replacement_end=None,note='',status='active',source_label='Test',source_url=None))
