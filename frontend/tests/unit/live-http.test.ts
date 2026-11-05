/** Explicit opt-in: real local API, generated demo credentials, no intercepted responses. */
import {it,expect,vi} from 'vitest';
import {readFileSync} from 'node:fs';
import {createHttpTransport} from '../../src/api/client';
import {createLiveAdapter} from '../../src/api/live';

it.skipIf(process.env.ALMANAC_LIVE_TEST!=='1')('real login -> query -> history -> save -> deletion -> logout',async()=>{
 vi.stubEnv('VITE_API_MODE','live');
 const {createApi}=await import('../../src/api');
 const accounts=JSON.parse(readFileSync(new URL('../../../.local/demo-accounts.json',import.meta.url),'utf8'));
 let cookie='';
 const fetcher:typeof fetch=async(input,init)=>{
  const headers=new Headers(init?.headers);headers.set('Origin','http://localhost:5173');if(cookie)headers.set('Cookie',cookie);
  const result=await fetch(input,{...init,headers});
  const set=result.headers.get('set-cookie');if(set)cookie=set.split(';')[0];return result;
 };
 const api=createApi(createLiveAdapter(createHttpTransport('http://127.0.0.1:8000/api/v1',fetcher,()=>true)));
 const account=accounts.find((a:any)=>a.username==='student-a');
 const user=await api.login(account.username,account.password);expect(user.role).toBe('student');
 let conversation='';
 try{
  expect((await api.me()).id).toBe(user.id);expect((await api.reference()).campus_timezone).toBe('Asia/Kolkata');
  const answer=await api.query({text:'workshops this week',client_request_id:crypto.randomUUID(),conversation_id:null,context_overrides:{},clarification:null});
  conversation=answer.conversation_id;
  const history=await api.conversation(conversation);expect(history.turns[0].answer.turn_id).toBe(answer.turn_id);
  expect((await api.conversations()).items.some(c=>c.id===conversation)).toBe(true);
  await api.saved();await api.events();
  const follow=await api.query({text:'only Friday',client_request_id:crypto.randomUUID(),conversation_id:conversation,context_overrides:{},clarification:null});
  expect(follow.intent).toBe('find_events');
 }finally{if(conversation)await api.deleteConversation(conversation);await api.logout();}
},30000);
it.skipIf(process.env.ALMANAC_LIVE_TEST!=='1')('real admin payloads for every resource',async()=>{
 vi.stubEnv('VITE_API_MODE','live');const {createApi}=await import('../../src/api');
 const accounts=JSON.parse(readFileSync(new URL('../../../.local/demo-accounts.json',import.meta.url),'utf8'));let cookie='';
 const fetcher:typeof fetch=async(input,init)=>{const headers=new Headers(init?.headers);headers.set('Origin','http://localhost:5173');if(cookie)headers.set('Cookie',cookie);const r=await fetch(input,{...init,headers});if(r.headers.get('set-cookie'))cookie=r.headers.get('set-cookie')!.split(';')[0];return r;};
 const api=createApi(createLiveAdapter(createHttpTransport('http://127.0.0.1:8000/api/v1',fetcher,()=>true)));const admin=accounts.find((a:any)=>a.username==='admin');await api.login(admin.username,admin.password);
 const day=new Date(Date.now()+86400000).toISOString().slice(0,10),until=new Date(Date.now()+14*86400000).toISOString().slice(0,10),start=day+'T14:00:00+05:30',end=day+'T15:00:00+05:30';
 const made:Array<{resource:any;id:string}>=[];
 const create=async(resource:any,fields:any)=>{const r=await api.adminSave(resource,{source_label:'Synthetic integration',source_url:null,status:'active',version:1,...fields});made.push({resource,id:r.id});expect((await api.adminGet(resource,r.id)).id).toBe(r.id);await api.adminList(resource);return r;};
 try{
 const event=await create('events',{title:'Integration '+crypto.randomUUID(),description:'Synthetic',event_type:'workshop',topic_ids:['machine_learning'],venue:'Test',starts_at:start,ends_at:end,cost_minor:0,currency:'INR',registration_deadline:null,eligibility_mode:'all_students',allowed_years:[],allowed_department_ids:[],status:'published'});
 expect((await api.adminSave('events',{...event,title:'Edited integration'},event.id)).version).toBe(2);
 const room=await create('rooms',{code:'TEST-'+crypto.randomUUID().slice(0,8),building_id:'block-b',capacity:40,facility_ids:['projector'],opening_hours:[],opening_hours_unknown:true,coverage_start:null,coverage_end:null,coverage_complete:false});
 const faculty=await create('faculty',{name:'Integration '+crypto.randomUUID(),department_id:'aiml',location:'Office',email:'',aliases:[],office_hours_coverage_start:day,office_hours_coverage_end:until,office_hours_complete:true});
 const booking=await create('bookings',{room_id:room.id,purpose:'Test',starts_at:start,ends_at:end,recurrence:'none',recurrence_until:null});
 await create('booking-exceptions',{booking_id:booking.id,occurrence_date:day,action:'cancel',replacement_start:null,replacement_end:null,note:'Test'});
 await create('room-closures',{room_id:room.id,reason:'Test',starts_at:start,ends_at:end});
 const rule=await create('office-hours',{faculty_id:faculty.id,location:'Office',weekday:(new Date(day+'T00:00:00Z').getUTCDay()+6)%7,start_time:'14:00',end_time:'15:00',effective_from:day,effective_until:until,timezone:'Asia/Kolkata'});
 await create('office-hour-exceptions',{office_hour_id:rule.id,occurrence_date:day,action:'cancel',replacement_start:null,replacement_end:null,note:'Test'});
 await create('aliases',{entity_type:'faculty',canonical_id:faculty.id,alias:'Alias '+crypto.randomUUID()});
 }finally{for(const r of made.sort((a,b)=>Number(['rooms','faculty'].includes(a.resource))-Number(['rooms','faculty'].includes(b.resource)))){const current=await api.adminGet(r.resource,r.id);await api.adminArchive(r.resource,r.id,current.version);}await api.logout();}
},60000);
