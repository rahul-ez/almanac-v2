from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select,func,update
from app.db.models import Conversation,AssistantTurn,DeletedRequest
from test_identity import env,headers
from test_rooms import room_env
from test_faculty import faculty_env
from test_events import event_env


def ask(e,text,**changes):
    token=e.get('token',e.get('student_csrf'))
    return e['student'].post('/api/v1/assistant/query',json={'text':text,'client_request_id':str(uuid4()),**changes},headers=headers(token))


def test_followup_precedence_week_filter_clear_domain_reset_expiry(event_env):
    e=event_env;e['create']()
    first=ask(e,'workshops next week for second years').json();cid=first['conversation_id']
    friday=ask(e,'Only Friday',conversation_id=cid).json()
    assert friday['interpreted_query']['filters']['event_type']=='workshop'
    assert friday['interpreted_query']['filters']['student_year']==2
    assert friday['interpreted_query']['filters']['interval']['start']>=first['interpreted_query']['filters']['interval']['start']
    assert any(c['field']=='event_type' and c['origin']=='prior_turn' for c in friday['applied_context'])
    changed=ask(e,'for third years',conversation_id=cid,context_overrides={'year':4}).json()
    assert changed['interpreted_query']['filters']['student_year']==3
    cleared=ask(e,'clear year',conversation_id=cid).json()
    assert cleared['interpreted_query']['filters']['student_year'] is None
    switched=ask(e,'rooms tomorrow',conversation_id=cid).json()
    assert switched['status']=='clarification_required' and switched['clarification']['field']=='time_interval'
    e['clock'][0]+=timedelta(minutes=31)
    expired=ask(e,'only Friday',conversation_id=cid).json()
    assert expired['status']=='unsupported' and any('expired' in w for w in expired['warnings'])


def test_missing_room_time_reply_restored_history_and_stale_reply(room_env):
    e=room_env;room=e['create_room']().json()
    first=ask(e,f'room {room["code"]} tomorrow').json();cid=first['conversation_id'];clar=first['clarification']
    assert first['status']=='clarification_required'
    restored=e['student'].get('/api/v1/conversations/'+cid).json()
    assert restored['active_clarification']==clar
    reply={'id':clar['id']}
    answered=ask(e,'from 2 to 3pm',conversation_id=cid,clarification=reply).json()
    assert answered['status']=='answered' and answered['results'][0]['record_id']==room['id']
    assert ask(e,'from 3 to 4pm',conversation_id=cid,clarification=reply).status_code==409
    shifted=ask(e,'from 3 to 4pm',conversation_id=cid).json()
    assert shifted['status']=='answered'
    assert shifted['interpreted_query']['filters']['room_id']==room['id']


def test_faculty_options_are_bound_to_active_conversation_and_user(faculty_env):
    e=faculty_env;one=e['create_faculty']().json();two=e['create_faculty']().json();e['rule'](one['id'])
    alias='Same Person '+uuid4().hex
    e['alias'](one['id'],alias);e['alias'](two['id'],alias)
    first=ask(e,f'Professor {alias} office hours tomorrow').json();cid=first['conversation_id'];clar=first['clarification']
    option=next(o for o in clar['options'] if o['id']==one['id'])
    assert ask(e,option['label'],conversation_id=cid,clarification={'id':clar['id'],'option_id':'not-listed'}).status_code==422
    other=ask(e,'events tomorrow').json()
    assert ask(e,option['label'],conversation_id=other['conversation_id'],clarification={'id':clar['id'],'option_id':option['id']}).status_code==409
    b,token=e['login']('b')
    assert b.post('/api/v1/assistant/query',json={'text':option['label'],'client_request_id':str(uuid4()),'conversation_id':cid,'clarification':{'id':clar['id'],'option_id':option['id']}},headers=headers(token)).status_code==404
    result=ask(e,option['label'],conversation_id=cid,clarification={'id':clar['id'],'option_id':option['id']}).json()
    assert result['status']=='answered' and result['results'][0]['faculty_id']==one['id']


def test_expired_clarification_and_version_conflicts(room_env):
    e=room_env;first=ask(e,'rooms tomorrow').json();cid=first['conversation_id']
    assert ask(e,'from 2 to 3pm',conversation_id=cid,conversation_version=999).status_code==409
    e['clock'][0]+=timedelta(minutes=31)
    assert ask(e,'from 2 to 3pm',conversation_id=cid,clarification={'id':first['clarification']['id']}).status_code==409
    assert ask(e,'from 2 to 3pm',clarification={'id':first['clarification']['id']}).status_code==422


def test_private_history_order_snapshot_pagination_delete_and_delayed_retry(event_env):
    e=event_env;created=e['create']().json();request_id=str(uuid4())
    first=ask(e,'workshops this week',client_request_id=request_id).json();cid=first['conversation_id']
    second=ask(e,'only Friday',conversation_id=cid).json()
    detail=e['student'].get('/api/v1/conversations/'+cid,params={'limit':1}).json()
    assert detail['turns'][0]['response']==first and detail['next_offset']==1
    page2=e['student'].get('/api/v1/conversations/'+cid,params={'limit':1,'offset':1}).json()
    assert page2['turns'][0]['response']==second
    b,token=e['login']('b')
    assert b.get('/api/v1/conversations/'+cid).status_code==404
    assert b.delete('/api/v1/conversations/'+cid,headers=headers(token)).status_code==404
    assert b.get('/api/v1/conversations').json()['items']==[]
    assert e['student'].delete('/api/v1/conversations/'+cid).status_code==403
    assert e['student'].delete('/api/v1/conversations/'+cid,headers=headers(e['student_csrf'])).status_code==200
    assert e['student'].get('/api/v1/conversations/'+cid).status_code==404
    retry=ask(e,'workshops this week',client_request_id=request_id)
    assert retry.status_code==410
    with e['engine'].connect() as conn:
        assert conn.execute(select(func.count()).select_from(AssistantTurn).where(AssistantTurn.conversation_id==cid)).scalar_one()==0
        assert conn.execute(select(func.count()).select_from(Conversation).where(Conversation.id==cid)).scalar_one()==0
        assert conn.execute(select(func.count()).select_from(DeletedRequest).where(DeletedRequest.user_id==e['ids']['a'])).scalar_one()==2


def test_concurrent_turn_versions_prevent_lost_state(event_env):
    e=event_env;first=ask(e,'events this week').json()
    # Different sessions exercise owner serialization rather than just the session-row lock.
    second,token=e['login']('a')
    payload={'text':'only Friday','conversation_id':first['conversation_id'],'conversation_version':first['conversation_version']}
    def post(pair):
        client,csrf=pair
        return client.post('/api/v1/assistant/query',json={**payload,'client_request_id':str(uuid4())},headers=headers(csrf))
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(post,[(e['student'],e['student_csrf']),(second,token)]))
    assert sorted(r.status_code for r in responses)==[200,409]


def test_ambiguous_time_reply_replaces_the_ambiguous_range(room_env):
    e=room_env;room=e['create_room']().json()
    first=ask(e,f'room {room["code"]} tomorrow from 2 to 3').json()
    assert first['status']=='clarification_required'
    reply=ask(e,'from 14:00 to 15:00',conversation_id=first['conversation_id'],clarification={'id':first['clarification']['id']})
    assert reply.status_code==200 and reply.json()['status']=='answered'


def test_free_followup_and_turn_limit_preserve_exact_retries(event_env):
    e=event_env;key=str(uuid4())
    first=ask(e,'events tomorrow',client_request_id=key).json();cid=first['conversation_id']
    free=ask(e,'only free',conversation_id=cid).json()
    assert free['interpreted_query']['filters']['max_cost_minor']==0
    with e['engine'].begin() as conn: conn.execute(update(Conversation).where(Conversation.id==cid).values(version=200))
    assert ask(e,'only Friday',conversation_id=cid).status_code==409
    assert ask(e,'events tomorrow',client_request_id=key).json()==first
