'use strict';
let roomCursor = null;
let roomSearchParams = null;
let loadedSchedule = null;
let lastRoom = null;
let lastBooking = null;
function resetRoomTimes() {
  const start = new Date(); start.setDate(start.getDate()+1); start.setHours(15,0,0,0);
  el('room-from').value = start.toISOString();
  el('room-to').value = new Date(start.getTime()+3600000).toISOString();
}
function showRooms(data) {
  const host = el('room-results'); host.replaceChildren();
  const summary = document.createElement('p');
  summary.textContent = data.room ? `${data.room.code}: ${data.availability}` : `${data.status} · ${data.checked_count} candidate rooms checked on this page · coverage: ${data.data_coverage}`;
  host.append(summary);
  const results = data.room ? [data] : [...data.items,...data.unknown_rooms];
  for (const result of results) {
    const row = document.createElement('p');
    row.textContent = `${result.room.code} · ${result.room.id} · ${result.room.capacity} seats · ${result.availability} · ${result.reasons.join(', ')} · ${result.room.timezone}`;
    host.append(row);
  }
  for (const warning of data.warnings || []) {
    const note = document.createElement('p'); note.textContent = warning; host.append(note);
  }
}
async function checkRooms(next = false) {
  if (!next) {
    roomSearchParams = new URLSearchParams({from_at:el('room-from').value,to_at:el('room-to').value,min_capacity:el('room-capacity').value});
    if (el('room-building').value.trim()) roomSearchParams.set('building_id',el('room-building').value.trim());
    for (const id of csv(el('room-facilities').value)) roomSearchParams.append('facility_ids',id);
    roomCursor = null;
  }
  if (!roomSearchParams || (next && !roomCursor)) throw new Error('There is no next candidate page. Run a search first.');
  const params = new URLSearchParams(roomSearchParams);
  if (next) params.set('cursor',roomCursor);
  const id = el('room-check-id').value.trim();
  const path = id ? '/rooms/'+encodeURIComponent(id)+'/availability' : '/rooms/availability';
  const data = must(await api(path+'?'+params.toString()));
  roomCursor = data.next_cursor || null;
  showRooms(data); notify(data.room ? `${data.room.code}: ${data.availability}.` : `${data.status}: check the candidate page and coverage warnings.`);
}
el('room-search-form').addEventListener('submit', event => { event.preventDefault(); run(() => checkRooms()); });
el('room-next').addEventListener('click', () => run(() => checkRooms(true)));
function templateFor(resource) {
  const start = el('room-from').value, end = el('room-to').value;
  const source = {source_label:'Synthetic localhost room test',source_url:null};
  const roomId = lastRoom?.id || el('room-check-id').value.trim() || 'REPLACE_WITH_ROOM_ID';
  if (resource === 'rooms') return {...source,code:'DEMO-LOCAL-'+Date.now().toString().slice(-6),building_id:'block-b',capacity:40,facility_ids:['projector'],
    opening_hours:Array.from({length:7},(_,weekday) => ({weekday,start:'08:00',end:'18:00'})),
    coverage_start:new Date().toISOString(),coverage_end:new Date(Date.now()+90*86400000).toISOString(),coverage_complete:true,status:'active'};
  if (resource === 'bookings') return {...source,room_id:roomId,purpose:'[DEMO] Scheduled class',starts_at:start,ends_at:end,recurrence:'none',recurrence_until:null,status:'active'};
  if (resource === 'booking-exceptions') {
    const when = new Date(lastBooking?.starts_at || start);
    const parts = new Intl.DateTimeFormat('en-CA',{timeZone:lastRoom?.timezone || 'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(when);
    const part = type => parts.find(value => value.type === type).value;
    return {...source,booking_id:lastBooking?.id || 'REPLACE_WITH_BOOKING_ID',occurrence_date:`${part('year')}-${part('month')}-${part('day')}`,action:'cancel',replacement_start:null,replacement_end:null,note:'[DEMO] Cancel this occurrence',status:'active'};
  }
  return {...source,room_id:roomId,reason:'[DEMO] Maintenance closure',starts_at:start,ends_at:end,status:'active'};
}
function newSchedule() {
  loadedSchedule = null;
  el('schedule-id').value = ''; el('schedule-version').value = '';
  el('schedule-json').value = JSON.stringify(templateFor(el('room-resource').value),null,2);
  el('schedule-save').textContent = 'Create scheduling record';
}
function fillSchedule(data) {
  const resource = el('room-resource').value;
  loadedSchedule = {resource,id:data.id,version:data.version};
  el('schedule-id').value = data.id; el('schedule-version').value = data.version;
  const {id,version,updated_at,timezone,...body} = data;
  el('schedule-json').value = JSON.stringify(body,null,2);
  el('schedule-save').textContent = 'Save scheduling changes';
  if (resource === 'rooms') { lastRoom = data; el('room-check-id').value = data.id; el('schedule-room-filter').value = data.id; }
  if (resource === 'bookings') lastBooking = data;
}
el('room-resource').addEventListener('change',newSchedule);
el('schedule-new').addEventListener('click',newSchedule);
el('schedule-load').addEventListener('click', () => run(async () => {
  if (!el('schedule-id').value.trim()) throw new Error('Enter a record ID to load.');
  fillSchedule(must(await api('/admin/'+el('room-resource').value+'/'+encodeURIComponent(el('schedule-id').value.trim()))));
  notify('Scheduling record loaded with its current version.');
}));
el('schedule-list').addEventListener('click', () => run(async () => {
  const params = new URLSearchParams({limit:'20'});
  if (el('schedule-room-filter').value.trim()) params.set('room_id',el('schedule-room-filter').value.trim());
  const data = must(await api('/admin/'+el('room-resource').value+'?'+params.toString()));
  notify(`Loaded ${data.items.length} scheduling records. ${data.next_cursor ? 'More records exist; use API pagination or a room filter.' : ''} Copy a record ID from the response to edit it.`);
}));
el('schedule-save').addEventListener('click', () => run(async () => {
  const resource = el('room-resource').value;
  if (el('schedule-id').value.trim() && (!loadedSchedule || loadedSchedule.resource !== resource || loadedSchedule.id !== el('schedule-id').value.trim())) throw new Error('Load that record first, or start a new template.');
  const body = JSON.parse(el('schedule-json').value);
  if (!body || Array.isArray(body) || typeof body !== 'object') throw new Error('The payload must be a JSON object.');
  const data = must(await api('/admin/'+resource+(loadedSchedule ? '/'+encodeURIComponent(loadedSchedule.id) : ''),{
    method:loadedSchedule ? 'PATCH' : 'POST',body:loadedSchedule ? {...body,version:loadedSchedule.version} : body}));
  fillSchedule(data); notify(`Saved ${resource}: ${data.id} · version ${data.version}.`);
}));
el('schedule-archive').addEventListener('click', () => run(async () => {
  if (!loadedSchedule || loadedSchedule.resource !== el('room-resource').value || loadedSchedule.id !== el('schedule-id').value.trim()) throw new Error('Load the record before archiving it.');
  const data = must(await api('/admin/'+loadedSchedule.resource+'/'+encodeURIComponent(loadedSchedule.id)+'?version='+loadedSchedule.version,{method:'DELETE'}));
  fillSchedule(data); notify('Scheduling record archived. Restoring a cancelled occurrence is rejected if it would overbook the room.');
}));
resetRoomTimes();
newSchedule();
