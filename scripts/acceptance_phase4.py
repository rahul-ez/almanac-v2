"""Real HTTP publication/ambiguity/exception flow; archives only its synthetic records."""
import json
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from uuid import uuid4
import httpx
accounts={r['username']:r for r in json.loads(Path('/workspace/.local/demo-accounts.json').read_text())}

def check(response,status,label):
    assert response.status_code == status,f'{label}: expected {status}, got {response.status_code}'
    print(f'PASS {label}: {status}');return response.json()

with httpx.Client(base_url='http://127.0.0.1:8000',timeout=10) as admin,httpx.Client(base_url='http://127.0.0.1:8000',timeout=10) as student:
    def login(client,name):
        csrf=check(client.get('/api/v1/auth/csrf'),200,name+' CSRF')['csrf_token']
        result=check(client.post('/api/v1/auth/login',json={'username':name,'password':accounts[name]['password']},headers={'Origin':'http://localhost:8000','X-CSRF-Token':csrf}),200,name+' login')
        return {'Origin':'http://localhost:8000','X-CSRF-Token':result['csrf_token']}
    ha,hs=login(admin,'admin'),login(student,'student-a')
    refs=check(student.get('/api/v1/reference-data'),200,'campus reference data');zone=ZoneInfo(refs['campus_timezone'])
    now=datetime.now(timezone.utc);day=now.astimezone(zone).date()+timedelta(days=1)
    start=datetime.combine(day,datetime.min.time(),tzinfo=zone);end=start+timedelta(days=1)
    query={'from_at':start.isoformat(),'to_at':end.isoformat()};faculty_ids=[];records=[]
    try:
        for number,complete in [(1,True),(2,False)]:
            faculty=check(admin.post('/api/v1/admin/faculty',json={'name':'[DEMO acceptance] '+uuid4().hex,'department_id':'aiml','location':'Faculty Test Office',
                'office_hours_coverage_start':day.isoformat() if complete else None,'office_hours_coverage_end':(day+timedelta(days=60)).isoformat() if complete else None,
                'office_hours_complete':complete,'source_label':'Synthetic acceptance publication'},headers=ha),201,'create faculty '+str(number));faculty_ids.append(faculty['id'])
        missing=check(student.get('/api/v1/faculty/'+faculty_ids[1]+'/office-hours',params=query),200,'missing publication');assert missing['status']=='information_unavailable'
        known=check(student.get('/api/v1/faculty/'+faculty_ids[0]+'/office-hours',params=query),200,'complete publication without slots');assert known['status']=='no_results'
        alias_name='Acceptance Rao '+uuid4().hex
        for faculty_id in faculty_ids:
            alias=check(admin.post('/api/v1/admin/aliases',json={'canonical_id':faculty_id,'alias':alias_name,'source_label':'Synthetic alias'},headers=ha),201,'create shared alias');records.append(('aliases',alias['id']))
        ambiguous=check(student.get('/api/v1/faculty/resolve',params={'name':alias_name}),200,'ambiguous alias resolution')
        assert ambiguous['status']=='clarification_required' and len(ambiguous['candidates'])==2
        rule_payload={'faculty_id':faculty_ids[0],'location':'Published Test Office','weekday':day.weekday(),'start_time':'13:00','end_time':'14:00',
            'effective_from':day.isoformat(),'effective_until':(day+timedelta(days=21)).isoformat(),'source_label':'Synthetic published schedule'}
        check(student.post('/api/v1/admin/office-hours',json=rule_payload,headers=hs),403,'student publication mutation denied')
        rule=check(admin.post('/api/v1/admin/office-hours',json=rule_payload,headers=ha),201,'publish recurring office hours');records.append(('office-hours',rule['id']))
        first=check(student.get('/api/v1/faculty/'+faculty_ids[0]+'/office-hours',params=query),200,'retrieve concrete published slot');assert first['status']=='answered' and len(first['items'])==1
        exception=check(admin.post('/api/v1/admin/office-hour-exceptions',json={'office_hour_id':rule['id'],'occurrence_date':day.isoformat(),'action':'cancel','source_label':'Synthetic cancellation'},headers=ha),201,'publish dated cancellation');records.append(('office-hour-exceptions',exception['id']))
        cancelled=check(student.get('/api/v1/faculty/'+faculty_ids[0]+'/office-hours',params=query),200,'cancelled occurrence removed');assert cancelled['items']==[] and cancelled['status']=='no_results'
        replacement_start=start+timedelta(days=1,hours=15);replacement_end=replacement_start+timedelta(hours=1)
        check(admin.patch('/api/v1/admin/office-hour-exceptions/'+exception['id'],json={'version':1,'action':'replace','replacement_start':replacement_start.isoformat(),'replacement_end':replacement_end.isoformat(),'note':'Published replacement'},headers=ha),200,'replace dated cancellation with moved slot')
        moved=check(student.get('/api/v1/faculty/'+faculty_ids[0]+'/office-hours',params={'from_at':(start+timedelta(days=1)).isoformat(),'to_at':(start+timedelta(days=2)).isoformat()}),200,'query moved slot outside original day')
        assert len(moved['items'])==1 and moved['items'][0]['exception_note']=='Published replacement'
        check(admin.patch('/api/v1/admin/office-hours/'+rule['id'],json={'version':1,'location':'Stale edit'},headers=ha),409,'stale parent update rejected')
    finally:
        # Archive rules before exceptions so cleanup cannot reinstate conflicting slots.
        for resource,record_id in sorted(records,key=lambda r:0 if r[0]=='office-hours' else 1):
            current=admin.get('/api/v1/admin/'+resource+'/'+record_id)
            if current.status_code==200 and current.json()['status']!='archived':
                check(admin.delete('/api/v1/admin/'+resource+'/'+record_id,params={'version':current.json()['version']},headers=ha),200,'archive synthetic '+resource)
        for faculty_id in faculty_ids:
            current=admin.get('/api/v1/admin/faculty/'+faculty_id).json()
            check(admin.delete('/api/v1/admin/faculty/'+faculty_id,params={'version':current['version']},headers=ha),200,'archive synthetic faculty')
        admin.post('/api/v1/auth/logout',headers=ha);student.post('/api/v1/auth/logout',headers=hs)
print('Phase 4 live acceptance passed; earlier records preserved.')
