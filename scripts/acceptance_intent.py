"""Hybrid-mode engineering smoke check; these examples are not quality evidence."""
import json
from pathlib import Path
from uuid import uuid4
import httpx
accounts={r['username']:r for r in json.loads(Path('/workspace/.local/demo-accounts.json').read_text())}
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=10) as client:
    ready=client.get('/api/v1/health/ready')
    assert ready.status_code==200 and ready.json()['nlp_mode']=='hybrid'
    print('PASS hybrid readiness with loaded artifact')
    csrf=client.get('/api/v1/auth/csrf').json()['csrf_token']
    login=client.post('/api/v1/auth/login',json={'username':'student-a','password':accounts['student-a']['password']},
        headers={'Origin':'http://localhost:8000','X-CSRF-Token':csrf})
    assert login.status_code==200
    headers={'Origin':'http://localhost:8000','X-CSRF-Token':login.json()['csrf_token']}
    try:
        payload={'text':'Any free events on Friday?','client_request_id':str(uuid4())}
        parsed=client.post('/api/v1/assistant/interpret',json=payload,headers=headers)
        assert parsed.status_code==200,parsed.status_code
        data=parsed.json()
        assert data['intent_source']=='model' and data['model_version'].startswith('tfidf-')
        assert data['status']=='ready' and data['execution']['kind']=='event'
        assert data['meaning']['filters']['max_cost_minor']==0
        print('PASS trained intent -> validated free-event query (training smoke example)')
        first=client.post('/api/v1/assistant/query',json=payload,headers=headers)
        second=client.post('/api/v1/assistant/query',json=payload,headers=headers)
        assert first.status_code==200 and second.json()==first.json()
        print('PASS hybrid persisted snapshot and exact retry')
        unsupported=client.post('/api/v1/assistant/interpret',json={'text':'Fix hostel plumbing please','client_request_id':str(uuid4())},headers=headers)
        assert unsupported.status_code==200 and unsupported.json()['status']=='unsupported' and unsupported.json()['execution'] is None
        print('PASS unsupported intent has no executable query')
    finally:
        assert client.post('/api/v1/auth/logout',headers=headers).status_code==200
print('Hybrid HTTP smoke passed; no accuracy claim is made by these wiring checks.')
