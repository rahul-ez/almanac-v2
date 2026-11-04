'use strict';
let selectedFaculty = null;
let lastOfficeRule = null;
let loadedFacultyRecord = null;
let officeCursor = null;
let lastOfficeQuery = null;
function facultyDay(value,zone = selectedFaculty?.timezone || 'Asia/Kolkata') {
  const parts = new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(value));
  const field = type => parts.find(part => part.type === type).value;
  return `${field('year')}-${field('month')}-${field('day')}`;
}
function shiftFacultyDay(value,days) { const date = new Date(value+'T12:00:00Z'); date.setUTCDate(date.getUTCDate()+days); return date.toISOString().slice(0,10); }
function showFacultyResolution(data) {
  const host = el('faculty-results'); host.replaceChildren();
  const summary = document.createElement('p'); summary.textContent = data.status+': '+data.warnings.join(' '); host.append(summary);
  for (const faculty of data.candidates) {
    const row = document.createElement('p'); row.textContent = `${faculty.name} · ${faculty.department_id} · ${faculty.id} `;
    const button = document.createElement('button'); button.type = 'button'; button.textContent = 'Select this faculty';
    button.addEventListener('click', () => { selectedFaculty = faculty; el('faculty-query-id').value = faculty.id; el('faculty-admin-filter').value = faculty.id; notify(`Selected ${faculty.name}. Query their published schedule next.`); });
    row.append(button); host.append(row);
  }
}
async function resolveFaculty() {
  const params = new URLSearchParams({name:el('faculty-name').value});
  if (el('faculty-department').value.trim()) params.set('department_id',el('faculty-department').value.trim());
  const data = must(await api('/faculty/resolve?'+params.toString()));
  showFacultyResolution(data);
  // An ambiguous new lookup must clear an earlier selection rather than silently reusing it.
  selectedFaculty = data.status === 'resolved' ? data.candidates[0] : null;
  el('faculty-query-id').value = selectedFaculty?.id || '';
  notify(data.status === 'clarification_required' ? 'Ambiguous name: select a candidate before querying.' : 'Faculty resolution: '+data.status);
  return data;
}
async function queryOfficeHours(next = false) {
  if (!next) {
    if (!el('faculty-query-id').value.trim()) {
      const resolved = await resolveFaculty();
      if (resolved.status !== 'resolved') return;
    }
    lastOfficeQuery = {id:el('faculty-query-id').value.trim(),params:new URLSearchParams({from_at:el('faculty-from').value,to_at:el('faculty-to').value})};
    officeCursor = null;
  }
  if (!lastOfficeQuery || (next && !officeCursor)) throw new Error('No next page. Run an office-hour query first.');
  const params = new URLSearchParams(lastOfficeQuery.params);
  if (next) params.set('cursor',officeCursor);
  const data = must(await api('/faculty/'+encodeURIComponent(lastOfficeQuery.id)+'/office-hours?'+params.toString()));
  selectedFaculty = data.faculty; officeCursor = data.next_cursor;
  const host = el('faculty-results'); host.replaceChildren();
  const title = document.createElement('p'); title.textContent = `${data.faculty.name}: ${data.status} · coverage ${data.data_coverage}`; host.append(title);
  for (const slot of data.items) {
    const row = document.createElement('p'); row.textContent = `${slot.starts_at} → ${slot.ends_at} · ${slot.location} · ${slot.timezone} · original date ${slot.occurrence_date}${slot.exception_note ? ' · '+slot.exception_note : ''} · ${slot.source_label}`; host.append(row);
  }
  for (const warning of data.warnings) { const note = document.createElement('p'); note.textContent = warning; host.append(note); }
  notify(`Published office hours: ${data.status}. ${officeCursor ? 'More slots are available.' : ''}`);
}
el('faculty-resolve').addEventListener('click', () => run(resolveFaculty));
el('faculty-hours').addEventListener('click', () => run(() => queryOfficeHours()));
el('faculty-next').addEventListener('click', () => run(() => queryOfficeHours(true)));
function facultyTemplate(resource) {
  const source = {source_label:'Synthetic localhost faculty publication',source_url:null};
  const facultyId = selectedFaculty?.id || el('faculty-query-id').value.trim() || 'REPLACE_WITH_FACULTY_ID';
  const day = facultyDay(el('faculty-from').value);
  if (resource === 'faculty') return {...source,name:'[DEMO] Faculty '+Date.now().toString().slice(-6),department_id:'aiml',location:'Faculty Block 101',email:null,
    office_hours_coverage_start:facultyDay(new Date()),office_hours_coverage_end:shiftFacultyDay(day,90),office_hours_complete:true,status:'active'};
  if (resource === 'aliases') return {...source,entity_type:'faculty',canonical_id:facultyId,alias:'Rao',status:'active'};
  if (resource === 'office-hours') return {...source,faculty_id:facultyId,location:selectedFaculty?.location || 'Faculty Block 101',weekday:(new Date(day+'T12:00:00Z').getUTCDay()+6)%7,
    start_time:'13:00',end_time:'14:00',effective_from:day,effective_until:shiftFacultyDay(day,21),timezone:selectedFaculty?.timezone || null,status:'active'};
  const first = lastOfficeRule ? shiftFacultyDay(lastOfficeRule.effective_from,(lastOfficeRule.weekday-(new Date(lastOfficeRule.effective_from+'T12:00:00Z').getUTCDay()+6)%7+7)%7) : day;
  return {...source,office_hour_id:lastOfficeRule?.id || 'REPLACE_WITH_OFFICE_HOUR_ID',occurrence_date:first,action:'cancel',replacement_start:null,replacement_end:null,note:'[DEMO] Published cancellation',status:'active'};
}
function newFacultyTemplate() {
  loadedFacultyRecord = null; el('faculty-record-id').value = ''; el('faculty-record-version').value = '';
  el('faculty-json').value = JSON.stringify(facultyTemplate(el('faculty-resource').value),null,2);
  el('faculty-admin-save').textContent = 'Create faculty publication record';
}
function fillFacultyRecord(data) {
  const resource = el('faculty-resource').value;
  loadedFacultyRecord = {resource,id:data.id,version:data.version};
  el('faculty-record-id').value = data.id; el('faculty-record-version').value = data.version;
  const {id,version,updated_at,aliases,matching_faculty_count,...payload} = data;
  if (resource === 'faculty') { delete payload.timezone; selectedFaculty = data; el('faculty-query-id').value = data.id; el('faculty-admin-filter').value = data.id; }
  if (resource === 'office-hours') lastOfficeRule = data;
  el('faculty-json').value = JSON.stringify(payload,null,2); el('faculty-admin-save').textContent = 'Save faculty publication changes';
}
el('faculty-resource').addEventListener('change',newFacultyTemplate);
el('faculty-admin-new').addEventListener('click',newFacultyTemplate);
el('faculty-admin-list').addEventListener('click', () => run(async () => {
  const params = new URLSearchParams({limit:'20'});
  if (el('faculty-admin-filter').value.trim()) params.set('faculty_id',el('faculty-admin-filter').value.trim());
  const data = must(await api('/admin/'+el('faculty-resource').value+'?'+params.toString()));
  notify(`Loaded ${data.items.length} records. Copy a record ID to load it. ${data.next_cursor ? 'More records exist; use API pagination or a faculty filter.' : ''}`);
}));
el('faculty-admin-load').addEventListener('click', () => run(async () => {
  if (!el('faculty-record-id').value.trim()) throw new Error('Enter a publication record ID.');
  fillFacultyRecord(must(await api('/admin/'+el('faculty-resource').value+'/'+encodeURIComponent(el('faculty-record-id').value.trim()))));
  notify('Faculty publication loaded with its current version.');
}));
el('faculty-admin-save').addEventListener('click', () => run(async () => {
  const resource = el('faculty-resource').value;
  if (el('faculty-record-id').value.trim() && (!loadedFacultyRecord || loadedFacultyRecord.resource !== resource || loadedFacultyRecord.id !== el('faculty-record-id').value.trim())) throw new Error('Load that record first or start a new template.');
  const body = JSON.parse(el('faculty-json').value);
  if (!body || Array.isArray(body) || typeof body !== 'object') throw new Error('Payload must be a JSON object.');
  const data = must(await api('/admin/'+resource+(loadedFacultyRecord ? '/'+encodeURIComponent(loadedFacultyRecord.id) : ''),{
    method:loadedFacultyRecord ? 'PATCH' : 'POST',body:loadedFacultyRecord ? {...body,version:loadedFacultyRecord.version} : body}));
  fillFacultyRecord(data); notify(`Saved ${resource}: ${data.id} · version ${data.version}. Reload parent versions after alias or exception changes.`);
}));
el('faculty-admin-archive').addEventListener('click', () => run(async () => {
  if (!loadedFacultyRecord || loadedFacultyRecord.resource !== el('faculty-resource').value || loadedFacultyRecord.id !== el('faculty-record-id').value.trim()) throw new Error('Load the record before archiving it.');
  const data = must(await api('/admin/'+loadedFacultyRecord.resource+'/'+encodeURIComponent(loadedFacultyRecord.id)+'?version='+loadedFacultyRecord.version,{method:'DELETE'}));
  fillFacultyRecord(data); notify('Faculty publication record archived.');
}));
const facultyStart = new Date(); facultyStart.setDate(facultyStart.getDate()+1); facultyStart.setHours(0,0,0,0);
el('faculty-from').value = facultyStart.toISOString(); el('faculty-to').value = new Date(facultyStart.getTime()+86400000).toISOString();
newFacultyTemplate();
