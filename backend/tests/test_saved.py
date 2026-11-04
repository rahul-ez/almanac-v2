from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from sqlalchemy import select,func
from app.db.models import SavedRecord
from test_identity import env,headers
from test_events import event_env
from test_rooms import room_env
from test_faculty import faculty_env
from test_dialogue import ask


def test_saved_events_are_current_private_and_idempotent_but_history_stays_a_snapshot(event_env):
    e=event_env;event=e['create']().json();url='/api/v1/me/saved/event/'+event['id'];h=headers(e['student_csrf'])
    original=ask(e,'workshops this week').json()
    assert not next(c for c in original['results'] if c['record_id']==event['id'])['saved']
    assert e['student'].put(url).status_code==403
    first=e['student'].put(url,headers=h)
    assert first.status_code==200 and not first.json()['changed']
    assert e['student'].put(url,headers=h).json()==first.json()
    assert next(c for c in ask(e,'workshops this week').json()['results'] if c['record_id']==event['id'])['saved']
    b,token=e['login']('b')
    assert b.get('/api/v1/me/saved').json()['items']==[]
    b.delete(url,headers=headers(token))
    assert len(e['student'].get('/api/v1/me/saved').json()['items'])==1
    cancelled=e['admin'].patch('/api/v1/admin/events/'+event['id'],json={'version':1,'status':'cancelled'},headers=headers(e['csrf']))
    assert cancelled.status_code==200
    changed=e['student'].get('/api/v1/me/saved').json()['items'][0]
    assert changed['changed'] and changed['record_status']=='cancelled' and changed['current']['status']=='cancelled'
    history=e['student'].get('/api/v1/conversations/'+original['conversation_id']).json()
    assert history['turns'][0]['response']==original
    e['admin'].delete('/api/v1/admin/events/'+event['id'],params={'version':2},headers=headers(e['csrf']))
    archived=e['student'].get('/api/v1/me/saved').json()['items'][0]
    assert archived['record_status']=='archived' and archived['current'] is None
    assert e['student'].put(url,headers=h).json()==archived  # Existing save survives archive.
    assert e['student'].delete(url,headers=h).status_code==200
    assert e['student'].delete(url,headers=h).status_code==200
    assert e['student'].put(url,headers=h).status_code==404  # Cannot newly save hidden records.


def test_room_saves_reference_metadata_not_physical_availability(room_env):
    e=room_env;room=e['create_room']().json();url='/api/v1/me/saved/room/'+room['id']
    result=e['student'].put(url,headers=headers(e['token']))
    assert result.status_code==200 and result.json()['current']['code']==room['code']
    assert 'availability' not in result.json()['current']
    assert e['student'].put('/api/v1/me/saved/booking/'+room['id'],headers=headers(e['token'])).status_code==422
    assert e['admin'].get('/api/v1/me/saved').status_code==403


def test_faculty_save_concurrency_and_pagination(faculty_env):
    e=faculty_env;one=e['create_faculty']().json();two=e['create_faculty']().json();other,token=e['login']('a')
    url='/api/v1/me/saved/faculty/'+one['id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda pair:pair[0].put(url,headers=headers(pair[1])),[(e['student'],e['token']),(other,token)]))
    assert all(r.status_code==200 for r in results) and results[0].json()==results[1].json()
    e['student'].put('/api/v1/me/saved/faculty/'+two['id'],headers=headers(e['token']))
    page=e['student'].get('/api/v1/me/saved',params={'limit':1}).json()
    assert page['next_offset']==1
    next_page=e['student'].get('/api/v1/me/saved',params={'limit':1,'offset':1}).json()
    assert next_page['items'][0]['record_id']!=page['items'][0]['record_id']
    with e['engine'].connect() as conn:
        assert conn.execute(select(func.count()).select_from(SavedRecord).where(SavedRecord.user_id==e['ids']['a'])).scalar_one()==2
