"""Real HTTP event vertical slice; create a synthetic record and archive it afterward."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import httpx

accounts = {r['username']:r for r in json.loads(Path('/workspace/.local/demo-accounts.json').read_text())}

def check(response,status,label):
    assert response.status_code == status, f'{label}: expected {status}, got {response.status_code}'
    print(f'PASS {label}: {status}')
    return response.json()

with httpx.Client(base_url='http://127.0.0.1:8000',timeout=10) as admin, httpx.Client(base_url='http://127.0.0.1:8000',timeout=10) as student:
    def login(client,name):
        csrf = check(client.get('/api/v1/auth/csrf'),200,name+' CSRF')['csrf_token']
        account=accounts[name]
        result=check(client.post('/api/v1/auth/login',json={'username':name,'password':account['password']},headers={'Origin':'http://localhost:8000','X-CSRF-Token':csrf}),200,name+' login')
        return {'Origin':'http://localhost:8000','X-CSRF-Token':result['csrf_token']}
    ha, hs = login(admin,'admin'), login(student,'student-a')
    now=datetime.now(timezone.utc)
    marker='[DEMO acceptance] '+uuid4().hex
    payload=dict(title=marker,description='Phase 2 live acceptance record',event_type='workshop',topic_id='machine_learning',venue='Test venue',starts_at=(now+timedelta(days=1)).isoformat(),ends_at=(now+timedelta(days=1,hours=2)).isoformat(),cost_minor=0,eligibility_rules={'mode':'unrestricted'},status='published',source_label='Synthetic acceptance script')
    record=check(admin.post('/api/v1/admin/events',json=payload,headers=ha),201,'admin creates event')
    try:
        check(student.post('/api/v1/admin/events',json=payload,headers=hs),403,'student create denied')
        found=check(student.get('/api/v1/events',params={'q':marker,'max_cost_minor':0}),200,'structured event search')
        assert [r['id'] for r in found['items']] == [record['id']]
        question={'text':'free ML workshops tomorrow','client_request_id':str(uuid4())}
        answer=check(student.post('/api/v1/assistant/query',json=question,headers=hs),200,'event baseline query')
        assert record['id'] in [r['record_id'] for r in answer['results']]
        assert check(student.post('/api/v1/assistant/query',json=question,headers=hs),200,'retry returns prior response') == answer
        changed=check(admin.patch('/api/v1/admin/events/'+record['id'],json={'version':record['version'],'title':marker+' updated'},headers=ha),200,'admin updates event')
        check(admin.patch('/api/v1/admin/events/'+record['id'],json={'version':1,'title':'stale'},headers=ha),409,'stale edit rejected')
        record=changed
        record=check(admin.patch('/api/v1/admin/events/'+record['id'],json={'version':record['version'],'status':'cancelled'},headers=ha),200,'admin cancels event')
        assert check(student.get('/api/v1/events',params={'q':marker}),200,'cancelled event excluded')['items'] == []
        fresh=check(student.post('/api/v1/assistant/query',json={**question,'client_request_id':str(uuid4())},headers=hs),200,'fresh answer after cancellation')
        assert record['id'] not in [r['record_id'] for r in fresh['results']]
        assert check(student.post('/api/v1/assistant/query',json=question,headers=hs),200,'old answer remains snapshot') == answer
    finally:
        current=admin.get('/api/v1/admin/events/'+record['id']).json()
        if current.get('status') != 'archived':
            check(admin.delete('/api/v1/admin/events/'+record['id'],params={'version':current['version']},headers=ha),200,'synthetic acceptance event archived')
        admin.post('/api/v1/auth/logout',headers=ha)
        student.post('/api/v1/auth/logout',headers=hs)
print('Phase 2 live event acceptance passed.')
