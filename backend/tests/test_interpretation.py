from datetime import datetime,timedelta
from uuid import uuid4
import pytest
from sqlalchemy import insert,select,func
from app.schemas.interpretation import CampusCatalog,CatalogEntry
from app.nlp.interpreter import interpret
from app.nlp.text import TextView
from app.services.execute_meaning import execute_interpretation
from app.api.errors import ApiError
from app.db.models import AssistantTurn
from test_rooms import room_env
from test_faculty import faculty_env
from test_identity import env,headers

NOW=datetime.fromisoformat('2026-11-04T10:00:00+05:30')

@pytest.fixture
def catalog():
    return CampusCatalog(entries=[
        CatalogEntry(kind='department',id='aiml',label='AIML',aliases=['AI & ML']),
        CatalogEntry(kind='department',id='cse',label='CSE'),
        CatalogEntry(kind='topic',id='machine_learning',label='Machine Learning',aliases=['ML']),
        CatalogEntry(kind='topic',id='artificial_intelligence',label='Artificial Intelligence',aliases=['AI']),
        CatalogEntry(kind='building',id='block-b',label='B Block',aliases=['block B']),
        CatalogEntry(kind='room',id='room-1',label='B-201',aliases=['B201']),
        CatalogEntry(kind='facility',id='projector',label='Projector'),
        CatalogEntry(kind='facility',id='whiteboard',label='Whiteboard'),
        CatalogEntry(kind='faculty',id='faculty-1',label='Anita Rao',aliases=['Rao'],department_id='aiml'),
        CatalogEntry(kind='faculty',id='faculty-2',label='Bharat Rao',aliases=['Rao'],department_id='cse'),
        CatalogEntry(kind='venue',id='B-201',label='B-201')])


def parse(catalog,text,**kwargs):
    return interpret(text,catalog=catalog,now=NOW,campus_timezone='Asia/Kolkata',**kwargs)


def test_events_normalized_fields_and_original_spans(catalog):
    text='Any ML workshops for second years this week?'
    report=parse(catalog,text)
    assert report.status=='ready',report.model_dump()
    assert report.execution.query.topic_id=='machine_learning'
    assert report.meaning.filters.student_year==2 and report.meaning.filters.eligible_only
    assert report.meaning.filters.interval.start.isoformat()=='2026-11-02T00:00:00+05:30'
    for entity in report.entities: assert text[entity.start:entity.end]==entity.text
    assert next(e for e in report.entities if e.label=='topic').text=='ML'
    assert report.applied_context[-1].origin=='explicit_question'


def test_unicode_offset_mapping_and_casefold_expansion(catalog):
    text='ＡＩ workshops tomorrow'
    report=parse(catalog,text)
    assert report.status=='ready'
    entity=next(e for e in report.entities if e.label=='topic')
    assert entity.text=='ＡＩ' and text[entity.start:entity.end]=='ＡＩ'
    view=TextView('Straße')
    assert view.text=='strasse' and view.original_span(4,6)==(4,5,'ß')
    assert TextView('e\u0301').text=='é'


def test_room_filters_meridiem_and_facilities(catalog):
    report=parse(catalog,'Find rooms in B block tomorrow from 2 to 3 PM for 40 students with a projector and whiteboard.')
    assert report.status=='ready',report.model_dump()
    query=report.execution.query
    assert query.building_id=='block-b' and query.min_capacity==40
    assert query.facility_ids==['projector','whiteboard']
    assert next(e.text for e in report.entities if e.label=='time_interval')=='from 2 to 3 PM'
    spans=sorted((e.start,e.end) for e in report.entities)
    assert all(end<=start for (_,end),(start,_) in zip(spans,spans[1:]))
    assert query.from_at.astimezone(NOW.tzinfo).hour==14 and query.to_at.astimezone(NOW.tzinfo).hour==15
    code=parse(catalog,'Is B-201 free tomorrow from 14:00 to 15:00?')
    assert code.status=='ready' and code.execution.room_id=='room-1'


@pytest.mark.parametrize('text,field',[
    ('find rooms','date_and_time_interval'),('rooms tomorrow','time_interval'),
    ('rooms from 14:00 to 15:00','date'),('rooms tomorrow from 2 to 3','time_interval'),
    ('rooms tomorrow from 11 to 1 pm','time_interval'),('office hours tomorrow','faculty_id'),
    ('free','intent')])
def test_missing_or_ambiguous_slots_never_execute(catalog,text,field):
    report=parse(catalog,text)
    assert report.status=='clarification_required' and report.execution is None
    assert report.ambiguities[0].field==field
    with pytest.raises(ApiError): execute_interpretation(None,report,catalog,NOW)


@pytest.mark.parametrize('text',[
    'workshops and rooms','events today tomorrow','rooms tomorrow from 15:00 to 14:00 extra_constraint',
    'workshops after 2pm','free workshops under 500','events for 40 students','rooms under ₹500 tomorrow from 2 to 3pm',
    'events today or tomorrow','delete all events','rooms tomorrow from 99:00 to 99:30','events on 2026-02-30'])
def test_unknown_compound_or_invalid_constraints_are_not_executed(catalog,text):
    report=parse(catalog,text)
    assert report.status!='ready' and report.execution is None


def test_faculty_ambiguity_explicit_department_and_canonical_override(catalog):
    ambiguous=parse(catalog,'When can I meet Professor Rao tomorrow?')
    assert ambiguous.status=='clarification_required'
    assert {o.id for o in ambiguous.ambiguities[0].options}=={'faculty-1','faculty-2'}
    resolved=parse(catalog,'When can I meet Professor Rao in AIML tomorrow?')
    assert resolved.status=='ready' and resolved.execution.faculty_id=='faculty-1'
    override=parse(catalog,'Professor Rao office hours tomorrow',overrides={'faculty_id':'faculty-2'})
    assert override.status=='ready' and override.execution.faculty_id=='faculty-2'
    conflict=parse(catalog,'Professor Rao office hours tomorrow',overrides={'faculty_id':'not-real'})
    assert conflict.status=='unsupported'


def test_context_precedence_explicit_clear_and_invalid_domain_override(catalog):
    profile={'student_year':1,'department_id':'aiml'}
    report=parse(catalog,'workshops for second years tomorrow',profile=profile,overrides={'year':3})
    assert report.status=='ready' and report.meaning.filters.student_year==2
    report=parse(catalog,'workshops tomorrow',profile=profile,overrides={'year':3})
    assert report.meaning.filters.student_year==3
    assert any(c.field=='student_year' and c.origin=='override' for c in report.applied_context)
    cleared=parse(catalog,'workshops tomorrow',profile=profile,overrides={'year':None,'department_id':None})
    assert cleared.meaning.filters.student_year is None and cleared.meaning.filters.department_id is None
    assert parse(catalog,'rooms right now',overrides={'year':2}).status=='unsupported'


def test_right_now_prices_past_dates_and_model_hook(catalog):
    report=parse(catalog,'rooms with projector right now')
    assert report.status=='ready' and report.execution.query.to_at-NOW==timedelta(minutes=30)
    assert any('30 minutes' in warning for warning in report.warnings)
    strict=parse(catalog,'events under ₹500 tomorrow')
    inclusive=parse(catalog,'events up to 500 rupees tomorrow')
    assert strict.meaning.filters.max_cost_minor==49999 and inclusive.meaning.filters.max_cost_minor==50000
    assert parse(catalog,'rooms today from 09:00 to 10:00').status=='clarification_required'
    model=parse(catalog,'free ML tomorrow',selected_intent='find_events')
    assert model.status=='ready' and model.intent_source=='model'
    assert parse(catalog,'rooms tomorrow from 14:00 to 15:00',selected_intent='find_events').status=='unsupported'


def test_reserved_catalog_alias_cannot_swallow_date(catalog):
    extra=CatalogEntry(kind='faculty',id='faculty-tomorrow',label='Other Person',aliases=['tomorrow'])
    extended=CampusCatalog(entries=[*catalog.entries,extra])
    report=parse(extended,'Professor Anita Rao office hours tomorrow')
    assert report.status=='ready'
    assert report.meaning.filters.interval.start.date().isoformat()=='2026-11-05'


def ask(e,text,**updates):
    return e['student'].post('/api/v1/assistant/query',json={'text':text,'client_request_id':str(uuid4()),**updates},headers=headers(e.get('token',e.get('student_csrf'))))


def test_room_assistant_and_inspection_are_backed_by_real_services(room_env):
    e=room_env;room=e['create_room']().json();tomorrow=(e['clock'][0]+timedelta(days=1)).date().isoformat()
    text=f'Is room {room["code"]} free on {tomorrow} from 14:00 to 15:00?'
    response=ask(e,text)
    assert response.status_code==200,response.text
    data=response.json();assert data['status']=='answered' and data['results'][0]['kind']=='room_availability'
    assert data['results'][0]['record_id']==room['id']
    before=None
    with e['engine'].connect() as conn: before=conn.execute(select(func.count()).select_from(AssistantTurn).where(AssistantTurn.user_id==e['ids']['a'])).scalar_one()
    inspected=e['student'].post('/api/v1/assistant/interpret',json={'text':text,'client_request_id':str(uuid4())},headers=headers(e['token']))
    assert inspected.status_code==200 and inspected.json()['status']=='ready'
    with e['engine'].connect() as conn: assert conn.execute(select(func.count()).select_from(AssistantTurn).where(AssistantTurn.user_id==e['ids']['a'])).scalar_one()==before
    e['booking'](room['id'],start=e['clock'][0]+timedelta(days=1,hours=4),end=e['clock'][0]+timedelta(days=1,hours=5))
    blocked=ask(e,text).json()
    assert blocked['status']=='no_results' and blocked['results']==[]


def test_faculty_assistant_returns_published_cards_and_safe_ambiguity(faculty_env):
    e=faculty_env;faculty=e['create_faculty']().json();e['rule'](faculty['id'])
    response=ask(e,f'When can I meet {faculty["name"]} tomorrow?')
    assert response.status_code==200,response.text
    data=response.json();assert data['status']=='answered' and data['results'][0]['kind']=='office_hours'
    assert data['results'][0]['faculty_id']==faculty['id']
    assert ask(e,'rooms tomorrow').json()['status']=='clarification_required'
    assert ask(e,'events and rooms tomorrow').json()['results']==[]


def test_request_fingerprint_preserves_explicit_context_clears():
    from app.schemas.events import AssistantRequest
    from app.services.assistant import canonical_payload
    base={'text':'events tomorrow','client_request_id':'same-id'}
    omitted=canonical_payload(AssistantRequest(**base))
    cleared=canonical_payload(AssistantRequest(**base,context_overrides={'year':None}))
    assert omitted != cleared
    assert '_explicit_null_context' not in omitted
    assert cleared['_explicit_null_context']==['year']


def test_configurable_nlp_now_window_and_horizon(catalog):
    report=interpret('rooms right now',catalog=catalog,now=NOW,campus_timezone='Asia/Kolkata',now_minutes=15,horizon_days=2)
    assert report.status=='ready' and report.execution.query.to_at-NOW==timedelta(minutes=15)
    assert any('15 minutes' in warning for warning in report.warnings)
    far=interpret('rooms on 2026-11-10 from 14:00 to 15:00',catalog=catalog,now=NOW,campus_timezone='Asia/Kolkata',horizon_days=2)
    assert far.status=='clarification_required' and far.execution is None


def test_calendar_month_boundaries_and_year_rollover(catalog):
    report=parse(catalog,'is there any event this month')
    assert report.status=='ready'
    assert report.meaning.filters.interval.start.isoformat()=='2026-11-01T00:00:00+05:30'
    assert report.meaning.filters.interval.end.isoformat()=='2026-12-01T00:00:00+05:30'
    report=interpret('events next month',catalog=catalog,now=datetime.fromisoformat('2026-12-20T10:00:00+05:30'),campus_timezone='Asia/Kolkata')
    assert report.status=='ready' and report.meaning.filters.interval.start.year==2027
    assert report.meaning.filters.interval.end.month==2


from test_events import event_env


def test_user_created_event_title_is_retrievable_without_sample_topic_alias(event_env):
    e=event_env
    created=e['create'](title='CP Integration '+uuid4().hex).json()
    for text in ('is there any cp event this month','any CP events this month?','show cp integration events this month'):
        result=ask(e,text)
        assert result.status_code==200,result.text
        data=result.json()
        assert data['status']=='answered',data
        assert created['id'] in [r['record_id'] for r in data['results']]
        assert 'cp' in data['interpreted_query']['filters']['search_terms']
    unknown=ask(e,'is there any flarnyx event this month').json()
    assert unknown['status']=='unsupported' and unknown['results']==[]
