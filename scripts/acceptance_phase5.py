"""Live cross-domain language -> validated query -> real record checks."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo
import httpx

accounts = {r['username']: r for r in json.loads(Path('/workspace/.local/demo-accounts.json').read_text())}

def check(response, expected, label):
    assert response.status_code == expected, f'{label}: expected {expected}, got {response.status_code}'
    print(f'PASS {label}: {expected}')
    return response.json()

with httpx.Client(base_url='http://127.0.0.1:8000', timeout=10) as admin, httpx.Client(base_url='http://127.0.0.1:8000', timeout=10) as student:
    def login(client, name):
        csrf = check(client.get('/api/v1/auth/csrf'), 200, name+' CSRF')['csrf_token']
        data = check(client.post('/api/v1/auth/login', json={'username':name,'password':accounts[name]['password']},
            headers={'Origin':'http://localhost:8000','X-CSRF-Token':csrf}), 200, name+' login')
        return {'Origin':'http://localhost:8000','X-CSRF-Token':data['csrf_token']}
    ha, hs = login(admin, 'admin'), login(student, 'student-a')
    refs = check(student.get('/api/v1/reference-data'), 200, 'reference data')
    now = datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo(refs['campus_timezone'])).date()+timedelta(days=1)
    start = datetime.combine(day, datetime.min.time(), tzinfo=ZoneInfo(refs['campus_timezone']))
    records = []
    def ask(text, endpoint='query', **extra):
        payload = {'text':text,'client_request_id':str(uuid4()), **extra}
        return check(student.post('/api/v1/assistant/'+endpoint, json=payload, headers=hs), 200, endpoint+' '+text)
    try:
        room = check(admin.post('/api/v1/admin/rooms', json={
            'code':'DEMO-NLP-'+uuid4().hex[:10], 'building_id':'block-b','capacity':40,'facility_ids':['projector'],
            'opening_hours':[{'weekday':d,'start':'00:00','end':'24:00'} for d in range(7)],
            'coverage_start':now.isoformat(),'coverage_end':(now+timedelta(days=60)).isoformat(),
            'coverage_complete':True,'source_label':'Synthetic language acceptance'}, headers=ha), 201, 'create room')
        records.append(('rooms',room['id']))
        faculty = check(admin.post('/api/v1/admin/faculty', json={
            'name':'Nlp Person '+uuid4().hex[:10], 'department_id':'aiml','location':'Synthetic office',
            'office_hours_coverage_start':day.isoformat(),'office_hours_coverage_end':(day+timedelta(days=60)).isoformat(),
            'office_hours_complete':True,'source_label':'Synthetic language acceptance'}, headers=ha), 201, 'create faculty')
        records.append(('faculty',faculty['id']))
        rule = check(admin.post('/api/v1/admin/office-hours', json={
            'faculty_id':faculty['id'],'location':'Synthetic office','weekday':day.weekday(),
            'start_time':'13:00','end_time':'14:00','effective_from':day.isoformat(),
            'effective_until':(day+timedelta(days=14)).isoformat(),'source_label':'Synthetic language acceptance'}, headers=ha), 201, 'publish hours')
        records.append(('office-hours',rule['id']))
        room_text = f'Is room {room["code"]} free tomorrow from 14:00 to 15:00?'
        parsed = ask(room_text, 'interpret')
        assert parsed['status']=='ready' and parsed['execution']['room_id']==room['id']
        for entity in parsed['entities']:
            assert room_text[entity['start']:entity['end']]==entity['text']
        room_answer = ask(room_text)
        assert room_answer['results'][0]['record_id']==room['id']
        assert room_answer['results'][0]['kind']=='room_availability'
        hours = ask(f'Professor {faculty["name"]} office hours tomorrow')
        assert hours['results'][0]['faculty_id']==faculty['id']
        events = ask('free ML workshops tomorrow', 'interpret')
        assert events['execution']['kind']=='event' and events['meaning']['filters']['max_cost_minor']==0
        assert ask('find rooms')['status']=='clarification_required'
        assert ask('events and rooms tomorrow')['status']=='unsupported'
        assert ask('workshops after 2pm')['results']==[]
        payload={'text':room_text,'client_request_id':str(uuid4())}
        first=check(student.post('/api/v1/assistant/query',json=payload,headers=hs),200,'first retry-safe question')
        second=check(student.post('/api/v1/assistant/query',json=payload,headers=hs),200,'exact retry')
        assert first==second
        check(student.post('/api/v1/assistant/query',json={**payload,'text':'events tomorrow'},headers=hs),409,'changed retry payload rejected')
        booking=check(admin.post('/api/v1/admin/bookings',json={'room_id':room['id'],'purpose':'Synthetic blocking class',
            'starts_at':(start+timedelta(hours=14)).isoformat(),'ends_at':(start+timedelta(hours=15)).isoformat(),
            'source_label':'Synthetic language acceptance'},headers=ha),201,'publish blocking booking')
        records.append(('bookings',booking['id']))
        assert ask(room_text)['status']=='no_results'
        replay=check(student.post('/api/v1/assistant/query',json=payload,headers=hs),200,'snapshot survives schedule change')
        assert replay==first
    finally:
        for resource, record_id in sorted(records,key=lambda value: 1 if value[0] in {'rooms','faculty'} else 0):
            current=admin.get('/api/v1/admin/'+resource+'/'+record_id)
            if current.status_code==200:
                check(admin.delete('/api/v1/admin/'+resource+'/'+record_id,params={'version':current.json()['version']},headers=ha),200,'archive synthetic '+resource)
        admin.post('/api/v1/auth/logout',headers=ha)
        student.post('/api/v1/auth/logout',headers=hs)
print('Phase 5 rule-interpreter acceptance passed; hybrid-mode smoke checks are separate; full dialogue is pending.')
