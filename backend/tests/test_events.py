from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from uuid import uuid4
import pytest
from sqlalchemy import delete, select, func, update
from test_identity import env, headers
from app.db.models import Event, EventAudit, AssistantTurn, Topic
from app.nlp.event_baseline import parse_event_question, UnsupportedQuestion
from app.schemas.events import EventSearch
from app.services.events import eligibility, eligibility_expression, search_events

@pytest.fixture
def event_env(env):
    base = datetime.fromisoformat('2035-11-01T10:00:00+05:30')
    env['clock'][0] = base + timedelta(days=(2-base.weekday())%7)
    admin, csrf = env['login']('admin')
    student, student_csrf = env['login']('a')
    created = []
    def create(**changes):
        now = env['clock'][0]
        payload = dict(title='Test '+uuid4().hex, description='Isolated test record', event_type='workshop',
            topic_id=env['topic'],venue='Test venue',starts_at=(now+timedelta(days=2)).isoformat(),
            ends_at=(now+timedelta(days=2,hours=2)).isoformat(),cost_minor=0,
            eligibility_rules={'mode':'unrestricted'},status='published',source_label='Automated test')
        payload.update(changes)
        result = admin.post('/api/v1/admin/events',json=payload,headers=headers(csrf))
        if result.status_code == 201:
            created.append(result.json()['id'])
        return result
    def search(**changes):
        now = env['clock'][0]
        params = dict(from_at=(now-timedelta(days=1)).isoformat(),to_at=(now+timedelta(days=10)).isoformat(),topic_id=env['topic'])
        params.update(changes)
        return student.get('/api/v1/events',params=params)
    yield dict(env,admin=admin,csrf=csrf,student=student,student_csrf=student_csrf,create=create,search=search)
    with env['engine'].begin() as conn:
        conn.execute(delete(Event).where(Event.id.in_(created)))


def test_event_crud_roles_csrf_conflicts_cancellation_archive(event_env):
    e = event_env
    denied = e['student'].post('/api/v1/admin/events',json={},headers=headers(e['student_csrf']))
    assert denied.status_code == 403
    created = e['create']()
    assert created.status_code == 201, created.text
    record = created.json(); event_id = record['id']
    assert record['version'] == 1
    assert e['student'].get('/api/v1/events/'+event_id).status_code == 200
    assert e['admin'].patch('/api/v1/admin/events/'+event_id,json={'version':1,'title':'Updated'}).status_code == 403
    changed = e['admin'].patch('/api/v1/admin/events/'+event_id,json={'version':1,'title':'Updated'},headers=headers(e['csrf']))
    assert changed.status_code == 200 and changed.json()['version'] == 2
    stale = e['admin'].patch('/api/v1/admin/events/'+event_id,json={'version':1,'title':'Stale'},headers=headers(e['csrf']))
    assert stale.status_code == 409
    cancelled = e['admin'].patch('/api/v1/admin/events/'+event_id,json={'version':2,'status':'cancelled'},headers=headers(e['csrf']))
    assert cancelled.status_code == 200
    assert event_id not in [r['id'] for r in e['search']().json()['items']]
    assert e['student'].get('/api/v1/events/'+event_id).json()['status'] == 'cancelled'
    archived = e['admin'].delete('/api/v1/admin/events/'+event_id,params={'version':3},headers=headers(e['csrf']))
    assert archived.status_code == 200 and archived.json()['status'] == 'archived'
    assert e['student'].get('/api/v1/events/'+event_id).status_code == 404
    assert e['admin'].get('/api/v1/admin/events/'+event_id).status_code == 200
    with e['engine'].connect() as conn:
        actions = list(conn.execute(select(EventAudit.action).where(EventAudit.event_id == event_id).order_by(EventAudit.version)).scalars())
        assert actions == ['create','update','update','archive']


def test_invalid_events_are_atomic_and_unknown_is_distinct(event_env):
    e = event_env
    for changes in ({'ends_at':e['clock'][0].isoformat()}, {'title':'   '}, {'cost_minor':-1}, {'cost_minor':True},
                    {'starts_at':'2035-11-01T10:00:00'}, {'topic_id':'unknown'},
                    {'eligibility_rules':{'mode':'restricted'}},
                    {'eligibility_rules':{'mode':'restricted','departments':['unknown']}},
                    {'eligibility_rules':{'mode':'unrestricted','years':[2]}},
                    {'source_url':'javascript:alert(1)'}, {'source_url':'https://user:password@example.com/'},
                    {'registration_deadline':(e['clock'][0]+timedelta(days=5)).isoformat()}):
        result = e['create'](**changes)
        assert result.status_code == 422, (changes,result.text)
    unknown = e['create'](cost_minor=None,eligibility_rules={'mode':'unknown'}).json()
    assert unknown['eligibility'] == 'unknown' and unknown['cost_minor'] is None
    assert e['search'](max_cost_minor=0).json()['items'] == []
    assert e['search'](eligible_only=True).json()['items'] == []
    assert e['search'](eligible_only=True).json()['warnings']
    failed = e['admin'].patch('/api/v1/admin/events/'+unknown['id'],json={'version':1,'title':'Should roll back','ends_at':e['clock'][0].isoformat()},headers=headers(e['csrf']))
    assert failed.status_code == 422
    stored = e['admin'].get('/api/v1/admin/events/'+unknown['id']).json()
    assert stored['version'] == 1 and stored['title'] == unknown['title']


def test_eligibility_unknown_mismatch_and_database_parity(event_env):
    e = event_env
    rules = {'mode':'restricted','years':[2],'departments':[e['department']]}
    record = e['create'](eligibility_rules=rules).json()
    for year, department, expected in [(None,None,'unknown'),(2,None,'unknown'),(3,None,'ineligible'),
                                       (2,e['department'],'eligible'),(3,e['department'],'ineligible')]:
        assert eligibility(rules,year,department)[0] == expected
        with e['engine'].connect() as conn:
            assert conn.execute(select(eligibility_expression(year,department)).where(Event.id == record['id'])).scalar_one() == expected
    assert e['search'](student_year=2,department_id=e['department'],eligible_only=True).json()['items'][0]['eligibility'] == 'eligible'
    assert e['search'](student_year=3,department_id=e['department'],eligible_only=True).json()['items'] == []


def test_overlap_boundaries_price_deadlines_and_drafts(event_env):
    e = event_env
    start = e['clock'][0]+timedelta(days=2)
    end = start+timedelta(hours=2)
    record = e['create'](registration_deadline=(e['clock'][0]-timedelta(days=1)).isoformat()).json()
    assert record['registration_status'] == 'closed' and record['status'] == 'published'
    draft = e['create'](status='draft').json()
    assert e['student'].get('/api/v1/events/'+draft['id']).status_code == 404
    assert [r['id'] for r in e['search'](from_at=(start-timedelta(hours=1)).isoformat(),to_at=start.isoformat()).json()['items']] == []
    assert e['search'](from_at=end.isoformat(),to_at=(end+timedelta(hours=1)).isoformat()).json()['items'] == []
    hit = e['search'](from_at=(start+timedelta(minutes=1)).isoformat(),to_at=(end+timedelta(minutes=1)).isoformat())
    assert [r['id'] for r in hit.json()['items']] == [record['id']]
    assert e['search'](from_at=start.isoformat(),to_at=(start+timedelta(days=367)).isoformat()).status_code == 422
    assert e['search'](from_at=start.isoformat(),to_at=None).status_code == 422


def test_bound_pagination_filter_cursor_and_literal_search(event_env):
    e = event_env
    records = [e['create']().json() for _ in range(3)]
    first = e['search'](limit=2)
    assert first.status_code == 200
    cursor = first.json()['next_cursor']; assert cursor
    second = e['search'](limit=2,cursor=cursor)
    ids = [r['id'] for r in first.json()['items']+second.json()['items']]
    assert len(ids) == 3 and len(set(ids)) == 3
    assert second.json()['next_cursor'] is None
    assert e['search'](limit=2,cursor=cursor,max_cost_minor=1).status_code == 422
    assert e['search'](cursor='invalid!').status_code == 422
    assert e['search'](q="%' OR 1=1 --").json()['items'] == []
    assert e['search'](limit=101).status_code == 422


def test_concurrent_admin_edits_prevent_lost_update(event_env):
    e = event_env
    record = e['create']().json()
    second, csrf2 = e['login']('admin')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda args:args[0].patch('/api/v1/admin/events/'+record['id'],json={'version':1,'title':args[2]},headers=headers(args[1])),
                                [(e['admin'],e['csrf'],'First edit'),(second,csrf2,'Second edit')]))
    assert sorted(r.status_code for r in results) == [200,409]
    assert e['admin'].get('/api/v1/admin/events/'+record['id']).json()['version'] == 2


def ask(e, text='workshops for second years this week', key=None, client=None, csrf=None, **fields):
    return (client or e['student']).post('/api/v1/assistant/query',json={'text':text,'client_request_id':key or str(uuid4()),**fields},headers=headers(csrf or e['student_csrf']))


def test_assistant_event_slice_retries_ownership_and_snapshot(event_env):
    e = event_env
    record = e['create'](eligibility_rules={'mode':'restricted','years':[2]}).json()
    key = str(uuid4())
    result = ask(e,key=key)
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['status'] == 'answered' and record['id'] in [r['record_id'] for r in data['results']]
    assert data['interpreted_query']['filters']['student_year'] == 2
    assert ask(e,key=key).json() == data
    assert ask(e,text='free workshops this week',key=key).status_code == 409
    with e['engine'].connect() as conn:
        assert conn.execute(select(func.count()).select_from(AssistantTurn).where(AssistantTurn.user_id == e['ids']['a'],AssistantTurn.client_request_id == key)).scalar_one() == 1
    b, csrf_b = e['login']('b')
    assert ask(e,client=b,csrf=csrf_b,conversation_id=data['conversation_id']).status_code == 404
    followup = ask(e,text='only friday',conversation_id=data['conversation_id']).json()
    assert followup['status'] == 'answered' and followup['interpreted_query']['filters']['event_type']=='workshop'
    e['admin'].patch('/api/v1/admin/events/'+record['id'],json={'version':1,'status':'cancelled'},headers=headers(e['csrf']))
    assert ask(e,key=key).json() == data
    fresh = ask(e).json()
    assert record['id'] not in [r['record_id'] for r in fresh['results']]


def test_assistant_unknown_filters_rejection_and_context_precedence(event_env):
    e = event_env
    e['create'](eligibility_rules={'mode':'unknown'})
    # Unknown eligibility must not turn into an eligible card.
    data = ask(e).json()
    assert data['status'] == 'information_unavailable' and data['results'] == []
    for text in ('workshops and rooms', 'workshops after 2pm', 'free workshops under 500', 'delete all events', 'events today tomorrow'):
        response = ask(e,text=text)
        assert response.status_code == 200, response.text
        assert response.json()['status'] == 'unsupported' and response.json()['results'] == []
    missing = ask(e,text='find rooms').json()
    assert missing['status'] == 'clarification_required' and missing['results'] == []
    e['student'].patch('/api/v1/me/profile',json={'year':1},headers=headers(e['student_csrf']))
    result = ask(e,context_overrides={'year':3}).json()
    assert result['interpreted_query']['filters']['student_year'] == 2
    result = ask(e,text='workshops this week',context_overrides={'year':3}).json()
    assert result['interpreted_query']['filters']['student_year'] == 3
    assert any(c['origin'] == 'override' for c in result['applied_context'])


def test_concurrent_assistant_retries_are_atomic(event_env):
    e = event_env
    e['create']()
    second, token = e['login']('a')
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda args:ask(e,key=key,client=args[0],csrf=args[1]),[(e['student'],e['student_csrf']),(second,token)]))
    assert [r.status_code for r in results] == [200,200]
    assert results[0].json() == results[1].json()


def test_baseline_time_and_conservative_grammar():
    now = datetime.fromisoformat('2026-11-04T10:00:00+05:30')
    query, origins = parse_event_question('Any ML workshops for second years this week?',now,'Asia/Kolkata')
    assert query.from_at.isoformat() == '2026-11-02T00:00:00+05:30'
    assert query.to_at.isoformat() == '2026-11-09T00:00:00+05:30'
    assert query.topic_id == 'machine_learning' and query.student_year == 2 and query.eligible_only
    assert origins['interval'] == 'explicit_question'
    query, _ = parse_event_question('free events on Friday',now,'Asia/Kolkata')
    assert query.from_at.isoformat() == '2026-11-06T00:00:00+05:30' and query.max_cost_minor == 0
    with pytest.raises(UnsupportedQuestion):
        parse_event_question('events on 2026-02-30',now,'Asia/Kolkata')
