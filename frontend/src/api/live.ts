/** Explicit backend wire-to-view boundary. Mock contracts never validate live wire data. */
import type { Transport } from './client';
import { ApiError } from './errors';

type Obj = Record<string, any>;
const object = (value: unknown): Obj => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid backend response');
  return value as Obj;
};
export function liveRecord(resource: string, r: Obj): Obj {
  if (resource === 'events') return {...r, topic_ids:[r.topic_id],eligibility_mode:r.eligibility_rules.mode==='unrestricted'?'all_students':r.eligibility_rules.mode,
    allowed_years:r.eligibility_rules.years || [],allowed_department_ids:r.eligibility_rules.departments || []};
  if (resource === 'rooms') return {...r,opening_hours_unknown:r.opening_hours===null,opening_hours:r.opening_hours || []};
  if (resource === 'faculty') return {...r,email:r.email || ''};
  return r;
}
export function liveCard(r: Obj, kind?: string): Obj {
  const k=kind || ({room_availability:'room',office_hours:'faculty'} as Obj)[r.kind] || r.kind;
  const metadata={record_id:r.record_id || r.id,title:r.title || r.code || r.name,source_label:r.source_label,source_url:r.source_url,
    record_updated_at:r.record_updated_at || r.updated_at,saved:r.saved ?? false,record_status:r.status || r.record_status || (r.cancelled?'cancelled':k==='event'?'published':'active')};
  if(k==='event') return {...metadata,kind:k,description:r.description || '',starts_at:r.interval?.start || r.starts_at,ends_at:r.interval?.end || r.ends_at,
    venue:r.venue,event_type:r.event_type,topics:[r.topic || r.topic_id],cost_minor:r.cost_minor,currency:r.currency,eligibility:r.eligibility,
    eligibility_basis:r.eligibility_reason || (r.eligibility==='unknown'?'Eligibility information is incomplete.':'Eligibility based on published rules.'),registration_deadline:r.registration_deadline};
  if(k==='room') return {...metadata,kind:k,building:r.building || r.building_id,capacity:r.capacity,facilities:r.facilities || r.facility_ids,
    requested_interval:r.requested_interval?{starts_at:r.requested_interval.start,ends_at:r.requested_interval.end}:null,
    schedule_coverage:r.schedule_coverage || (r.coverage_complete?'complete':'unknown'),availability_basis:'scheduled_bookings'};
  return {...metadata,kind:'faculty',faculty_name:r.faculty_name || r.name,department:r.department_id || '',location:r.location,
    meeting_interval:r.interval?{starts_at:r.interval.start,ends_at:r.interval.end}:null,exception_note:r.exception || null};
}
export function liveAnswer(r: Obj): Obj {
  const filters={...(r.interpreted_query?.filters || {})};
  if(filters.interval) {filters.date=`${filters.interval.start}/${filters.interval.end}`;delete filters.interval;}
  const warnings=r.warnings.filter((w:string)=>!w.startsWith('Deterministic cross-domain rules.') && !w.startsWith('Prototype trained intent with deterministic semantic checks.'));
  return {...r,warnings,interpreted_query:{intent:r.intent,filters},applied_context:Object.fromEntries(r.applied_context.map((v:Obj)=>[v.field,{value:v.value,origin:v.origin}])),
    results:r.results.map((c:Obj)=>liveCard(c)),data_coverage:{status:r.data_coverage==='not_applicable'?'unknown':r.data_coverage,message:warnings.join(' ')}};
}
const allowed: Record<string,string[]>={
  events:['title','description','event_type','topic_id','venue','starts_at','ends_at','cost_minor','currency','registration_deadline','eligibility_rules'],
  rooms:['code','building_id','capacity','facility_ids','opening_hours','coverage_start','coverage_end','coverage_complete'],
  faculty:['name','department_id','location','email','office_hours_coverage_start','office_hours_coverage_end','office_hours_complete'],
  bookings:['room_id','purpose','starts_at','ends_at','recurrence','recurrence_until'],
  'booking-exceptions':['booking_id','occurrence_date','action','replacement_start','replacement_end','note'],
  'room-closures':['room_id','reason','starts_at','ends_at'],
  'office-hours':['faculty_id','location','weekday','start_time','end_time','effective_from','effective_until','timezone'],
  'office-hour-exceptions':['office_hour_id','occurrence_date','action','replacement_start','replacement_end','note'],
  aliases:['entity_type','canonical_id','alias'],
};
export function livePayload(resource:string, value:Obj, patch:boolean):Obj {
  const r={...value};
  if(resource==='events') {
    if(r.topic_ids?.length!==1) throw new Error('Choose exactly one event topic.');
    r.topic_id=r.topic_ids[0];
    r.eligibility_rules={mode:r.eligibility_mode==='all_students'?'unrestricted':r.eligibility_mode,
      years:r.eligibility_mode==='restricted' && r.allowed_years?.length?r.allowed_years:null,
      departments:r.eligibility_mode==='restricted' && r.allowed_department_ids?.length?r.allowed_department_ids:null};
  }
  if(resource==='rooms' && r.opening_hours_unknown) r.opening_hours=null;
  if(resource==='faculty') {
    if(r.aliases?.length && !patch) throw new Error('Create faculty first, then add alternative names through Aliases.');
    r.email=r.email || null;
  }
  return Object.fromEntries([...allowed[resource],'status','source_label','source_url',...(patch?['version']:[])].filter(k=>k in r).map(k=>[k,r[k]]));
}
export function createLiveAdapter(raw:Transport):Transport {
  return async(path,init={})=>{
    const url=new URL(path,'http://local');const parts=url.pathname.split('/').filter(Boolean);const method=init.method || 'GET';
    let body=init.body?JSON.parse(String(init.body)):undefined;
    if(path==='/auth/login') body={username:body.email,password:body.password};
    if(['conversations','me'].includes(parts[0]) && (parts[0]==='conversations' && parts.length===1 || parts[1]==='saved')) {
      if(url.searchParams.has('cursor')) {url.searchParams.set('offset',url.searchParams.get('cursor')!);url.searchParams.delete('cursor');}
    }
    if(parts[0]==='admin') {
      if(parts[1]==='events' && url.searchParams.has('search')) {const q=url.searchParams.get('search');url.searchParams.delete('search');if(q)url.searchParams.set('q',q);}
      if(method==='POST' || method==='PATCH') body=livePayload(parts[1],body,method==='PATCH');
      if(method==='DELETE') {url.searchParams.set('version',new Headers(init.headers).get('If-Match') || '');init={...init,headers:undefined};}
    }
    let result:Obj;
    try { result=object(await raw(url.pathname+url.search,{...init,...(body?{body:JSON.stringify(body)}:{})})); }
    catch(e) { if(e instanceof ApiError && e.code==='version_conflict') e.code='stale_version';throw e; }
    if(parts[0]==='auth' && (parts[1]==='me' || parts[1]==='login')) {
      const u=result.user || result;return {...u,name:u.username,email:''};
    }
    if(parts[0]==='assistant') {
      return liveAnswer(result);
    }
    if(parts[0]==='conversations') {
      if(method==='DELETE') return result;
      if(parts.length===1) return {items:result.items.map((r:Obj)=>({...r,updated_at:r.last_turn_at || r.created_at})),next_cursor:result.next_offset===null?null:String(result.next_offset)};
      const first=result;let turns=[...result.turns];let offset=result.next_offset;
      while(offset!==null) {const next=object(await raw(url.pathname+'?limit=50&offset='+offset,{signal:init.signal}));turns.push(...next.turns);offset=next.next_offset;}
      return {...first.conversation,active_clarification:first.active_clarification,updated_at:first.conversation.last_turn_at || first.conversation.created_at,
        turns:turns.map((t:Obj)=>({id:t.id,question:t.question,answer:liveAnswer(t.response)}))};
    }
    if(parts[0]==='me' && parts[1]==='saved' && method==='GET') return {items:result.items.map((r:Obj)=>({...r,record:r.current?liveCard({...r.current,saved:true},r.kind):null})),next_cursor:result.next_offset===null?null:String(result.next_offset)};
    if(parts[0]==='admin') return result.items?{...result,items:result.items.map((r:Obj)=>liveRecord(parts[1],r))}:liveRecord(parts[1],result);
    if(parts[0]==='events' && parts.length===1) return {...result,items:result.items.map((r:Obj)=>liveCard(r,'event'))};
    if(['events','rooms','faculty'].includes(parts[0]) && parts.length===2) return liveCard(result,parts[0]==='events'?'event':parts[0]==='rooms'?'room':'faculty');
    return result;
  };
}
