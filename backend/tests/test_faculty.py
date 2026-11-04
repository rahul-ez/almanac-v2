import base64
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select,delete,func,insert
from test_identity import env,headers
from app.db.faculty_models import Faculty,OfficeHour,FacultyAudit,OfficeHourException
from app.services.faculty_time import base_office_slots
from app.api.errors import ApiError

@pytest.fixture
def faculty_env(env):
    env['clock'][0]=datetime.fromisoformat('2037-11-04T10:00:00+05:30')
    admin,csrf=env['login']('admin');student,token=env['login']('a');ids=[]
    day=(env['clock'][0]+timedelta(days=1)).date()
    def create_faculty(**changes):
        payload=dict(name='Faculty '+uuid4().hex,department_id=env['department'],location='Test office',
            office_hours_coverage_start=(day-timedelta(days=7)).isoformat(),office_hours_coverage_end=(day+timedelta(days=60)).isoformat(),
            office_hours_complete=True,source_label='Synthetic faculty test')
        payload.update(changes)
        result=admin.post('/api/v1/admin/faculty',json=payload,headers=headers(csrf))
        if result.status_code == 201: ids.append(result.json()['id'])
        return result
    def rule(faculty_id,**changes):
        payload=dict(faculty_id=faculty_id,location='Published office',weekday=day.weekday(),start_time='13:00',end_time='14:00',
            effective_from=env['clock'][0].date().isoformat(),effective_until=(day+timedelta(days=21)).isoformat(),source_label='Published test schedule')
        payload.update(changes)
        return admin.post('/api/v1/admin/office-hours',json=payload,headers=headers(csrf))
    def query(faculty_id,start=None,end=None,**params):
        start=start or datetime.combine(day,datetime.min.time(),tzinfo=env['clock'][0].tzinfo)
        end=end or start+timedelta(days=1)
        return student.get('/api/v1/faculty/'+faculty_id+'/office-hours',params=dict(from_at=start.isoformat(),to_at=end.isoformat(),**params))
    def alias(faculty_id,value):
        return admin.post('/api/v1/admin/aliases',json={'canonical_id':faculty_id,'alias':value,'source_label':'Synthetic alias'},headers=headers(csrf))
    yield dict(env,admin=admin,csrf=csrf,student=student,token=token,day=day,create_faculty=create_faculty,rule=rule,query=query,alias=alias)
    with env['engine'].begin() as conn:
        conn.execute(delete(OfficeHour).where(OfficeHour.faculty_id.in_(ids)))
        conn.execute(delete(Faculty).where(Faculty.id.in_(ids)))


def exception(e,rule,**changes):
    payload=dict(office_hour_id=rule['id'],occurrence_date=e['day'].isoformat(),action='cancel',source_label='Published exception')
    payload.update(changes)
    return e['admin'].post('/api/v1/admin/office-hour-exceptions',json=payload,headers=headers(e['csrf']))


def test_faculty_roles_input_versions_and_archival(faculty_env):
    e=faculty_env
    assert e['student'].post('/api/v1/admin/faculty',json={},headers=headers(e['token'])).status_code == 403
    for bad in ({'name':' '},{'department_id':'unknown'},{'email':'not-an-email'},
                {'office_hours_coverage_start':None},{'office_hours_coverage_end':(e['day']-timedelta(days=8)).isoformat()},
                {'source_url':'javascript:alert(1)'}):
        result=e['create_faculty'](**bad);assert result.status_code == 422,(bad,result.text)
    faculty=e['create_faculty']().json();url='/api/v1/admin/faculty/'+faculty['id']
    assert e['admin'].patch(url,json={'version':1,'location':'Changed'}).status_code == 403
    result=e['admin'].patch(url,json={'version':1,'location':'Changed'},headers=headers(e['csrf']))
    assert result.status_code == 200 and result.json()['version'] == 2
    assert e['admin'].patch(url,json={'version':1,'location':'Stale'},headers=headers(e['csrf'])).status_code == 409
    assert e['admin'].delete(url,params={'version':2},headers=headers(e['csrf'])).status_code == 200
    assert e['student'].get('/api/v1/faculty/'+faculty['id']).status_code == 404
    assert e['query'](faculty['id']).status_code == 404
    assert e['rule'](faculty['id']).status_code == 409
    assert e['query']('missing-faculty').status_code == 404


def test_alias_normalization_collision_candidates_and_parent_version(faculty_env):
    e=faculty_env; key='Rao-'+uuid4().hex[:8]
    one=e['create_faculty']().json();two=e['create_faculty']().json()
    alias=e['alias'](one['id'],key);assert alias.status_code == 201,alias.text
    assert e['alias'](one['id'],'Prof. '+key.upper()).status_code == 409
    collision=e['alias'](two['id'],key)
    assert collision.status_code == 201 and collision.json()['matching_faculty_count'] == 2
    result=e['student'].get('/api/v1/faculty/resolve',params={'name':'Professor '+key.upper()})
    assert result.status_code == 200
    assert result.json()['status'] == 'clarification_required'
    assert {r['id'] for r in result.json()['candidates']} == {one['id'],two['id']}
    assert e['student'].get('/api/v1/faculty/resolve',params={'name':key+'x'}).json()['status'] == 'no_results'
    parent=e['admin'].get('/api/v1/admin/faculty/'+one['id']).json();assert parent['version'] == 2
    assert e['admin'].patch('/api/v1/admin/faculty/'+one['id'],json={'version':1,'name':'stale'},headers=headers(e['csrf'])).status_code == 409
    assert e['admin'].delete('/api/v1/admin/aliases/'+alias.json()['id'],params={'version':1},headers=headers(e['csrf'])).status_code == 200
    resolved=e['student'].get('/api/v1/faculty/resolve',params={'name':key}).json()
    assert resolved['status'] == 'resolved' and resolved['candidates'][0]['id'] == two['id']


def test_published_slots_boundaries_and_missing_publication(faculty_env):
    e=faculty_env;faculty=e['create_faculty']().json()
    assert e['query'](faculty['id']).json()['status'] == 'no_results'
    rule=e['rule'](faculty['id']);assert rule.status_code == 201,rule.text
    data=e['query'](faculty['id']).json()
    assert data['status'] == 'answered' and len(data['items']) == 1 and data['data_coverage'] == 'complete'
    slot=data['items'][0];assert slot['location'] == 'Published office' and slot['exception_id'] is None
    start=datetime.fromisoformat(slot['starts_at'].replace('Z','+00:00'));end=datetime.fromisoformat(slot['ends_at'].replace('Z','+00:00'))
    assert e['query'](faculty['id'],start-timedelta(hours=1),start).json()['items'] == []
    assert e['query'](faculty['id'],end,end+timedelta(hours=1)).json()['items'] == []
    overlap=e['query'](faculty['id'],start+timedelta(minutes=30),end+timedelta(minutes=30)).json()
    assert overlap['items'][0]['starts_at'] == slot['starts_at']  # Return the real published interval, not fabricated bounds.
    unknown=e['create_faculty'](office_hours_complete=False,office_hours_coverage_start=None,office_hours_coverage_end=None).json()
    assert e['query'](unknown['id']).json()['status'] == 'information_unavailable'
    assert e['rule'](unknown['id']).status_code == 201
    partial=e['query'](unknown['id']).json()
    assert partial['status'] == 'answered' and partial['data_coverage'] == 'partial' and partial['warnings']


def test_office_rule_validation_and_atomic_merged_patch(faculty_env):
    e=faculty_env;faculty=e['create_faculty']().json()
    for bad in ({'weekday':7},{'weekday':True},{'start_time':'14:00'},{'end_time':'25:00'},
                {'effective_until':(e['day']+timedelta(days=400)).isoformat()},{'timezone':'invalid/zone'},
                {'timezone':'UTC'},{'location':' '}):
        result=e['rule'](faculty['id'],**bad);assert result.status_code == 422,(bad,result.text)
    rule=e['rule'](faculty['id']).json()
    bad=e['admin'].patch('/api/v1/admin/office-hours/'+rule['id'],json={'version':1,'location':'Should roll back','start_time':'15:00'},headers=headers(e['csrf']))
    assert bad.status_code == 422
    stored=e['admin'].get('/api/v1/admin/office-hours/'+rule['id']).json()
    assert stored['location'] == rule['location'] and stored['version'] == 1
    assert e['rule'](faculty['id']).status_code == 409


def test_cancel_replace_and_original_date_outside_query(faculty_env):
    e=faculty_env;faculty=e['create_faculty']().json();rule=e['rule'](faculty['id']).json()
    cancelled=exception(e,rule);assert cancelled.status_code == 201,cancelled.text
    assert e['query'](faculty['id']).json()['status'] == 'no_results'
    assert e['admin'].get('/api/v1/admin/office-hours/'+rule['id']).json()['version'] == 2
    assert exception(e,rule).status_code == 409
    assert e['admin'].delete('/api/v1/admin/office-hour-exceptions/'+cancelled.json()['id'],params={'version':1},headers=headers(e['csrf'])).status_code == 200
    day=datetime.combine(e['day']+timedelta(days=1),datetime.min.time(),tzinfo=e['clock'][0].tzinfo)
    replacement=exception(e,rule,action='replace',replacement_start=(day+timedelta(hours=15)).isoformat(),replacement_end=(day+timedelta(hours=16)).isoformat(),note='Rescheduled')
    assert replacement.status_code == 201,replacement.text
    moved=e['query'](faculty['id'],day,day+timedelta(days=1)).json()
    assert len(moved['items']) == 1 and moved['items'][0]['exception_note'] == 'Rescheduled'
    assert moved['items'][0]['occurrence_date'] == e['day'].isoformat()
    assert e['query'](faculty['id']).json()['items'] == []
    assert exception(e,rule,occurrence_date=(e['day']+timedelta(days=2)).isoformat()).status_code == 422


def test_restoring_cancelled_slot_cannot_overbook_and_orphans_rejected(faculty_env):
    e=faculty_env;faculty=e['create_faculty']().json();rule=e['rule'](faculty['id']).json()
    cancelled=exception(e,rule).json()
    assert e['rule'](faculty['id'],effective_from=e['day'].isoformat(),effective_until=e['day'].isoformat()).status_code == 201
    restore=e['admin'].delete('/api/v1/admin/office-hour-exceptions/'+cancelled['id'],params={'version':1},headers=headers(e['csrf']))
    assert restore.status_code == 409
    assert e['admin'].get('/api/v1/admin/office-hour-exceptions/'+cancelled['id']).json()['status'] == 'active'
    assert e['admin'].patch('/api/v1/admin/office-hours/'+rule['id'],json={'version':2,'weekday':(rule['weekday']+1)%7},headers=headers(e['csrf'])).status_code == 422


def test_concurrent_published_rules_prevent_overlapping_slots(faculty_env):
    e=faculty_env;faculty=e['create_faculty']().json();second,csrf=e['login']('admin')
    payload=dict(faculty_id=faculty['id'],location='Test',weekday=e['day'].weekday(),start_time='13:00',end_time='14:00',
                 effective_from=e['day'].isoformat(),effective_until=(e['day']+timedelta(days=14)).isoformat(),source_label='Published test')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda args:args[0].post('/api/v1/admin/office-hours',json=payload,headers=headers(args[1])),[(e['admin'],e['csrf']),(second,csrf)]))
    assert sorted(r.status_code for r in results) == [201,409]
    assert next(r.json() for r in results if r.status_code==409)['error']['code'] == 'office_hour_conflict'
    with e['engine'].connect() as conn:
        assert conn.execute(select(func.count()).select_from(FacultyAudit).where(FacultyAudit.faculty_id == faculty['id'])).scalar_one() == 2


def test_slots_pagination_query_bound_cursor_and_horizon(faculty_env):
    e=faculty_env;faculty=e['create_faculty']().json();e['rule'](faculty['id'])
    start=datetime.combine(e['day'],datetime.min.time(),tzinfo=e['clock'][0].tzinfo);end=start+timedelta(days=22)
    first=e['query'](faculty['id'],start,end,limit=1).json();cursor=first['next_cursor'];assert cursor
    second=e['query'](faculty['id'],start,end,limit=1,cursor=cursor).json()
    assert first['items'][0]['starts_at'] != second['items'][0]['starts_at']
    assert e['query'](faculty['id'],start,end,limit=2,cursor=cursor).status_code == 422
    assert e['query'](faculty['id'],start,end,cursor='invalid').status_code == 422
    assert e['query'](faculty['id'],start=e['clock'][0]-timedelta(seconds=1),end=end).status_code == 422
    assert e['query'](faculty['id'],start=start,end=e['clock'][0]+timedelta(days=31)).status_code == 422
    assert e['student'].get('/api/v1/faculty/'+faculty['id']+'/office-hours').status_code == 422


def test_inclusive_dates_local_midnight_and_dst_rejection(faculty_env):
    e=faculty_env;faculty=e['create_faculty']().json()
    rule=e['rule'](faculty['id'],start_time='00:00',end_time='01:00',effective_from=e['day'].isoformat(),effective_until=e['day'].isoformat())
    assert rule.status_code == 201,rule.text
    slots=e['query'](faculty['id']).json()['items'];assert len(slots)==1
    assert slots[0]['starts_at'][:10] != e['day'].isoformat()  # UTC date is earlier.
    assert exception(e,rule.json()).status_code == 201
    assert e['query'](faculty['id']).json()['items'] == []
    direct=dict(weekday=6,start_time='02:30',end_time='03:30',effective_from=datetime(2026,3,1).date(),effective_until=datetime(2026,3,8).date(),timezone='America/New_York')
    with pytest.raises(ApiError): base_office_slots(direct)


def test_inventory_literal_search_and_database_exception_constraint(faculty_env):
    from sqlalchemy.exc import IntegrityError
    e=faculty_env;faculty=e['create_faculty']().json();rule=e['rule'](faculty['id']).json()
    assert e['student'].get('/api/v1/admin/office-hours').status_code == 403
    assert e['admin'].get('/api/v1/admin/office-hours',params={'faculty_id':faculty['id']}).json()['items'][0]['id'] == rule['id']
    assert e['student'].get('/api/v1/faculty',params={'search':"%' OR 1=1 --"}).json()['items'] == []
    with e['engine'].begin() as conn:
        with pytest.raises(IntegrityError):
            with conn.begin_nested():
                conn.execute(insert(OfficeHourException).values(id='bad-'+uuid4().hex,version=1,updated_at=e['clock'][0],office_hour_id=rule['id'],
                    occurrence_date=e['day'],action='replace',replacement_start=e['clock'][0],replacement_end=None,note='',status='active',source_label='Test',source_url=None))
