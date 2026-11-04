"""Real HTTP dialogue, current saves and private deletion; only deletes its own synthetic conversation."""
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
import httpx
accounts={r['username']:r for r in json.loads(Path('/workspace/.local/demo-accounts.json').read_text())}

def check(response,status,label):
    assert response.status_code==status,f'{label}: expected {status}, got {response.status_code}'
    print(f'PASS {label}: {status}');return response.json()

with httpx.Client(base_url='http://127.0.0.1:8000',timeout=10) as admin,httpx.Client(base_url='http://127.0.0.1:8000',timeout=10) as a,httpx.Client(base_url='http://127.0.0.1:8000',timeout=10) as b:
    def login(client,name):
        csrf=check(client.get('/api/v1/auth/csrf'),200,name+' CSRF')['csrf_token']
        data=check(client.post('/api/v1/auth/login',json={'username':name,'password':accounts[name]['password']},headers={'Origin':'http://localhost:8000','X-CSRF-Token':csrf}),200,name+' login')
        return {'Origin':'http://localhost:8000','X-CSRF-Token':data['csrf_token']}
    ha,hs,hb=login(admin,'admin'),login(a,'student-a'),login(b,'student-b')
    conversations=[];room=None;saved=False
    def ask(text,**extra):
        body={'text':text,'client_request_id':str(uuid4()),**extra}
        data=check(a.post('/api/v1/assistant/query',json=body,headers=hs),200,'ask '+text)
        if data['conversation_id'] not in conversations: conversations.append(data['conversation_id'])
        return body,data
    try:
        now=datetime.now(timezone.utc)
        room=check(admin.post('/api/v1/admin/rooms',json={'code':'DEMO-DIALOGUE-'+uuid4().hex[:8],'building_id':'block-b','capacity':40,'facility_ids':['projector'],
            'opening_hours':[{'weekday':d,'start':'00:00','end':'24:00'} for d in range(7)],'coverage_start':now.isoformat(),
            'coverage_end':(now+timedelta(days=60)).isoformat(),'coverage_complete':True,'source_label':'Synthetic phase 6 acceptance'},headers=ha),201,'create covered room')
        _,first=ask('room '+room['code']+' tomorrow');cid=first['conversation_id'];clar=first['clarification']
        restored=check(a.get('/api/v1/conversations/'+cid),200,'restore active clarification')
        assert restored['active_clarification']==clar
        check(b.get('/api/v1/conversations/'+cid),404,'other student history denied')
        check(b.delete('/api/v1/conversations/'+cid,headers=hb),404,'other student delete denied')
        original_payload,answer=ask('from 2 to 3pm',conversation_id=cid,conversation_version=first['conversation_version'],clarification={'id':clar['id']})
        assert answer['results'][0]['record_id']==room['id'] and not answer['results'][0]['saved']
        check(a.post('/api/v1/assistant/query',json=original_payload,headers=hs),200,'exact clarification retry')
        check(a.post('/api/v1/assistant/query',json={'text':'from 3 to 4pm','client_request_id':str(uuid4()),'conversation_id':cid,'clarification':{'id':clar['id']}},headers=hs),409,'consumed clarification rejected')
        _,follow=ask('from 3 to 4pm',conversation_id=cid,conversation_version=answer['conversation_version'])
        assert follow['results'][0]['record_id']==room['id']
        assert any(c['origin']=='prior_turn' for c in follow['applied_context'])
        check(a.post('/api/v1/assistant/query',json={'text':'tomorrow','client_request_id':str(uuid4()),'conversation_id':cid,'conversation_version':first['conversation_version']},headers=hs),409,'stale conversation version rejected')
        save_path='/api/v1/me/saved/room/'+room['id']
        before=check(a.put(save_path,headers=hs),200,'save current room');saved=True
        assert check(a.put(save_path,headers=hs),200,'idempotent save')==before
        assert not any(item['record_id']==room['id'] for item in check(b.get('/api/v1/me/saved'),200,'other student saved list')['items'])
        room=check(admin.patch('/api/v1/admin/rooms/'+room['id'],json={'version':room['version'],'capacity':45},headers=ha),200,'update saved room')
        current=check(a.get('/api/v1/me/saved'),200,'saved current view')
        item=next(item for item in current['items'] if item['record_id']==room['id'])
        assert item['changed'] and item['current']['capacity']==45
        snapshot=check(a.get('/api/v1/conversations/'+cid),200,'old answer remains snapshot')
        assert snapshot['turns'][1]['response']==answer and snapshot['turns'][1]['response']['results'][0]['capacity']==40
        page=check(a.get('/api/v1/conversations/'+cid,params={'limit':1}),200,'bounded turn pagination');assert page['next_offset']==1
        check(a.delete('/api/v1/conversations/'+cid,headers=hs),200,'delete only synthetic test conversation');conversations.remove(cid)
        check(a.get('/api/v1/conversations/'+cid),404,'deleted history absent')
        check(a.post('/api/v1/assistant/query',json=original_payload,headers=hs),410,'deleted request cannot recreate history')
        assert any(i['record_id']==room['id'] for i in check(a.get('/api/v1/me/saved'),200,'save survives history deletion')['items'])
    finally:
        for cid in conversations:
            a.delete('/api/v1/conversations/'+cid,headers=hs)
        if room:
            if saved: check(a.delete('/api/v1/me/saved/room/'+room['id'],headers=hs),200,'remove synthetic save')
            record=admin.get('/api/v1/admin/rooms/'+room['id']).json()
            check(admin.delete('/api/v1/admin/rooms/'+room['id'],params={'version':record['version']},headers=ha),200,'archive synthetic room')
        for client,h in [(admin,ha),(a,hs),(b,hb)]: client.post('/api/v1/auth/logout',headers=h)
print('Phase 6 live acceptance passed; pre-existing conversations and saves preserved.')
