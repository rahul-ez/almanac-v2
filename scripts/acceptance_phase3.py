"""Live PostgreSQL room walk-through; archives its synthetic records afterward."""
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
import httpx

accounts={row['username']:row for row in json.loads(Path('/workspace/.local/demo-accounts.json').read_text())}

def check(response,status,label):
    assert response.status_code == status,f'{label}: expected {status}, got {response.status_code}'
    print(f'PASS {label}: {status}')
    return response.json()

with httpx.Client(base_url='http://127.0.0.1:8000',timeout=10) as admin,httpx.Client(base_url='http://127.0.0.1:8000',timeout=10) as student:
    def login(client,name):
        csrf=check(client.get('/api/v1/auth/csrf'),200,name+' CSRF')['csrf_token']
        data=check(client.post('/api/v1/auth/login',json={'username':name,'password':accounts[name]['password']},headers={'Origin':'http://localhost:8000','X-CSRF-Token':csrf}),200,name+' login')
        return {'Origin':'http://localhost:8000','X-CSRF-Token':data['csrf_token']}
    ha,hs=login(admin,'admin'),login(student,'student-a')
    now=datetime.now(timezone.utc);start=(now+timedelta(days=1)).replace(microsecond=0);end=start+timedelta(hours=1)
    room=None; cleanup=[]
    def get_availability(label,status='available'):
        result=check(student.get('/api/v1/rooms/'+room['id']+'/availability',params={'from_at':start.isoformat(),'to_at':end.isoformat()}),200,label)
        assert result['availability'] == status,(label,result['availability'])
        return result
    try:
        room=check(admin.post('/api/v1/admin/rooms',json={'code':'DEMO-ACCEPT-'+uuid4().hex[:12],'building_id':'block-b','capacity':40,'facility_ids':['projector'],
            'opening_hours':[{'weekday':d,'start':'00:00','end':'24:00'} for d in range(7)],'coverage_start':now.isoformat(),'coverage_end':(now+timedelta(days=60)).isoformat(),
            'coverage_complete':True,'source_label':'Synthetic Phase 3 acceptance'},headers=ha),201,'create covered room')
        get_availability('initial room availability')
        check(student.post('/api/v1/admin/bookings',json={},headers=hs),403,'student booking mutation denied')
        booking_payload={'room_id':room['id'],'purpose':'[DEMO] Class','starts_at':start.isoformat(),'ends_at':end.isoformat(),'source_label':'Synthetic acceptance timetable'}
        booking=check(admin.post('/api/v1/admin/bookings',json=booking_payload,headers=ha),201,'create scheduled booking');cleanup.append(('bookings',booking['id']))
        get_availability('booking blocks requested interval','unavailable')
        boundary=check(student.get('/api/v1/rooms/'+room['id']+'/availability',params={'from_at':end.isoformat(),'to_at':(end+timedelta(hours=1)).isoformat()}),200,'back-to-back boundary')
        assert boundary['availability'] == 'available'
        check(admin.post('/api/v1/admin/bookings',json=booking_payload,headers=ha),409,'conflicting booking rejected')
        from zoneinfo import ZoneInfo
        occurrence=start.astimezone(ZoneInfo(room['timezone'])).date().isoformat()
        exception=check(admin.post('/api/v1/admin/booking-exceptions',json={'booking_id':booking['id'],'occurrence_date':occurrence,'action':'cancel','source_label':'Synthetic cancellation'},headers=ha),201,'cancel original occurrence');cleanup.append(('booking-exceptions',exception['id']))
        get_availability('exception releases scheduled interval')
        closure=check(admin.post('/api/v1/admin/room-closures',json={'room_id':room['id'],'reason':'[DEMO] Maintenance','starts_at':start.isoformat(),'ends_at':end.isoformat(),'source_label':'Synthetic closure'},headers=ha),201,'create overlapping closure');cleanup.append(('room-closures',closure['id']))
        blocked=get_availability('closure takes precedence','unavailable');assert 'room_closure' in blocked['reasons']
        check(admin.delete('/api/v1/admin/room-closures/'+closure['id'],params={'version':1},headers=ha),200,'archive closure')
        get_availability('availability recovers after closure removal')
        check(admin.patch('/api/v1/admin/rooms/'+room['id'],json={'version':1,'coverage_complete':False},headers=ha),200,'mark incomplete schedule coverage')
        get_availability('missing coverage is unknown','unknown')
        check(admin.patch('/api/v1/admin/rooms/'+room['id'],json={'version':1,'capacity':50},headers=ha),409,'stale room update rejected')
    finally:
        # Cancel/archive parents before removing exceptions to avoid reinstating occupied slots.
        for resource,record_id in sorted(cleanup,key=lambda value:0 if value[0]=='bookings' else 1):
            current=admin.get('/api/v1/admin/'+resource+'/'+record_id)
            if current.status_code == 200 and current.json()['status'] != 'archived':
                check(admin.delete('/api/v1/admin/'+resource+'/'+record_id,params={'version':current.json()['version']},headers=ha),200,'archive test '+resource)
        if room:
            current=admin.get('/api/v1/admin/rooms/'+room['id']).json()
            check(admin.delete('/api/v1/admin/rooms/'+room['id'],params={'version':current['version']},headers=ha),200,'archive synthetic room')
        admin.post('/api/v1/auth/logout',headers=ha);student.post('/api/v1/auth/logout',headers=hs)
print('Phase 3 live acceptance passed; original records preserved.')
