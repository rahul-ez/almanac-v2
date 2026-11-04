'use strict';
const el = id => document.getElementById(id);
let csrf = null;
let accounts = [];
let busy = false;
function notify(text, error = false) {
  el('notice').textContent = text;
  el('notice').classList.toggle('error', error);
}
function redact(value) {
  if (Array.isArray(value)) return value.map(redact);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k,v]) => [k, /password|csrf_token|cookie/i.test(k) ? '[hidden]' : redact(v)]));
  return value;
}
async function api(path, {method = 'GET', body, protect = true} = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (method !== 'GET' && protect) {
    if (!csrf) {
      const init = await fetch('/api/v1/auth/csrf', {credentials:'same-origin', cache:'no-store'});
      const data = await init.json();
      if (!init.ok) throw new Error(data.error?.message || 'Could not initialize session');
      csrf = data.csrf_token;
    }
    headers['X-CSRF-Token'] = csrf;
  }
  const response = await fetch('/api/v1' + path, {method, headers, credentials:'same-origin', cache:'no-store', body:body === undefined ? undefined : JSON.stringify(body)});
  const data = await response.json();
  if (data.csrf_token) csrf = data.csrf_token;
  if (response.status === 401) {
    csrf = null;
    if (typeof resetPersonalView === 'function') resetPersonalView();
    el('identity').textContent = 'Signed out or session expired';
    el('profile-fields').disabled = true;
  }
  el('response-meta').textContent = `${method} /api/v1${path} · HTTP ${response.status} · Request ${response.headers.get('X-Request-ID') || 'unknown'}`;
  el('result').textContent = JSON.stringify(redact(data), null, 2);
  return {response, data};
}
async function run(action) {
  if (busy) return;
  busy = true;
  document.querySelectorAll('button').forEach(button => button.disabled = true);
  try { await action(); } catch (error) { notify(error.message || 'Request failed. Check that the API is running.', true); }
  finally { busy = false; document.querySelectorAll('button').forEach(button => button.disabled = false); }
}
function must(result) {
  if (!result.response.ok) throw new Error(result.data.error?.message || `Request failed (${result.response.status})`);
  return result.data;
}
function showIdentity(user) {
  el('identity').textContent = `${user.username} · ${user.role}`;
}
function options(id, rows, unknown = false) {
  const select = el(id);
  select.replaceChildren();
  if (unknown) select.add(new Option('Unknown / not supplied', ''));
  rows.forEach(row => select.add(new Option(row.label, row.id)));
}
async function loadProfile() {
  el('profile-fields').disabled = true;
  const refs = must(await api('/reference-data'));
  const profile = must(await api('/me/profile'));
  options('department', refs.departments, true);
  options('year', refs.supported_years.map(year => ({id:String(year), label:String(year)})), true);
  options('interests', refs.topics);
  el('department').value = profile.department_id || '';
  el('year').value = profile.year || '';
  el('section').value = profile.section || '';
  Array.from(el('interests').options).forEach(option => option.selected = profile.interests.includes(option.value));
  el('profile-fields').disabled = false;
}
el('login-form').addEventListener('submit', event => {
  event.preventDefault();
  run(async () => {
    csrf = null;
    el('profile-fields').disabled = true;
    el('profile-form').reset();
    if (typeof resetPersonalView === 'function') resetPersonalView();
    const data = must(await api('/auth/login', {method:'POST', body:{username:el('username').value, password:el('password').value}}));
    el('password').value = '';
    showIdentity(data.user);
    if (data.user.role === 'student') await loadProfile();
    notify(`Signed in as ${data.user.username}.`);
  });
});
el('logout').addEventListener('click', () => run(async () => {
  must(await api('/auth/logout', {method:'POST'}));
  csrf = null;
  if (typeof resetPersonalView === 'function') resetPersonalView();
  el('identity').textContent = 'Signed out';
  el('profile-fields').disabled = true;
  el('profile-form').reset();
  notify('Signed out. Check Current session to verify 401.');
}));
el('load-profile').addEventListener('click', () => run(async () => { await loadProfile(); notify('Profile loaded from the database.'); }));
el('profile-form').addEventListener('submit', event => {
  event.preventDefault();
  run(async () => {
    must(await api('/me/profile', {method:'PATCH', body:{department_id:el('department').value || null, year:el('year').value ? Number(el('year').value) : null, section:el('section').value.trim() || null, interests:Array.from(el('interests').selectedOptions).map(option => option.value)}}));
    notify('Profile saved. Reload the profile or this page to verify persistence.');
  });
});
document.querySelectorAll('[data-check]').forEach(button => button.addEventListener('click', () => run(async () => {
  const result = await api(button.dataset.check);
  if (button.dataset.check === '/auth/me' && result.response.ok) showIdentity(result.data);
  notify(`${button.textContent}: HTTP ${result.response.status}. See the response below.`, !result.response.ok);
})));
for (const [id, expected, body, protect] of [['test-csrf',403,{},false], ['test-role',422,{role:'admin'},true]]) {
  el(id).addEventListener('click', () => run(async () => {
    const result = await api('/me/profile', {method:'PATCH', body, protect});
    notify(result.response.status === expected ? `PASS: request rejected with HTTP ${expected}.` : `Expected HTTP ${expected}; got ${result.response.status}. Sign in as a student first.`, result.response.status !== expected);
  }));
}
el('accounts-file').addEventListener('change', () => run(async () => {
  const file = el('accounts-file').files[0];
  if (!file) return;
  if (file.size > 16384) throw new Error('Choose the small demo accounts JSON file.');
  const parsed = JSON.parse(await file.text());
  if (!Array.isArray(parsed) || !parsed.length || parsed.some(row => typeof row.username !== 'string' || typeof row.password !== 'string')) throw new Error('This is not a demo accounts file.');
  accounts = parsed;
  options('account', accounts.map(row => ({id:row.username,label:row.username})));
  chooseAccount();
  notify('Demo accounts loaded locally. Click Sign in to test the selected account.');
}));
function chooseAccount() {
  const account = accounts.find(row => row.username === el('account').value);
  if (account) { el('username').value = account.username; el('password').value = account.password; }
}
el('account').addEventListener('change', chooseAccount);
run(async () => {
  const result = await api('/auth/me');
  if (result.response.ok) {
    showIdentity(result.data);
    if (result.data.role === 'student') await loadProfile();
    notify('Existing session restored.');
  } else if (result.response.status === 401) notify('Sign in to test profiles and permissions, or try the public health checks.');
  else must(result);
});

let eventCursor = null;
let lastEventParams = null;
let lastQuestion = null;
let loadedEvent = null;
const csv = value => value.split(',').map(x => x.trim()).filter(Boolean);
function showEventResults(data, admin = false) {
  const host = el('event-results');
  host.replaceChildren();
  const summary = document.createElement('p');
  summary.textContent = `${data.items.length} event(s). ${(data.warnings || []).join(' ')} ${data.next_cursor ? 'More records exist; use Next page for student searches or API pagination for admin lists.' : ''}`;
  host.append(summary);
  for (const event of data.items) {
    const row = document.createElement('div');
    row.style.cssText = 'padding:12px 0;border-top:1px solid #d9e2da';
    const title = document.createElement('strong');
    title.textContent = event.title;
    const detail = document.createElement('p');
    detail.textContent = `${event.starts_at} · ${event.venue} · ${event.status} · ${event.cost_minor === null ? 'price unknown' : '₹'+(event.cost_minor/100).toFixed(2)} · eligibility: ${event.eligibility} · registration: ${event.registration_status}`;
    row.append(title, detail);
    if (admin) {
      const button = document.createElement('button');
      button.type = 'button'; button.textContent = 'Load for editing';
      button.addEventListener('click', () => run(async () => { fillEvent(must(await api('/admin/events/'+encodeURIComponent(event.id)))); notify('Event loaded with its current version.'); }));
      row.append(button);
    }
    host.append(row);
  }
}
async function searchEvents(next = false) {
  if (!next) {
    const params = new URLSearchParams();
    for (const [id, key] of [['search-title','q'],['search-type','event_type'],['search-topic','topic_id'],['search-cost','max_cost_minor'],['search-from','from_at'],['search-to','to_at'],['search-year','student_year'],['search-department','department_id']]) {
      if (el(id).value !== '') params.set(key,el(id).value);
    }
    params.set('eligible_only',String(el('search-eligible').checked));
    lastEventParams = params; eventCursor = null;
  }
  if (!lastEventParams || (next && !eventCursor)) throw new Error('No next page. Run a search first.');
  const params = new URLSearchParams(lastEventParams);
  if (next) params.set('cursor',eventCursor);
  const data = must(await api('/events?'+params.toString()));
  eventCursor = data.next_cursor;
  showEventResults(data);
  notify(`Loaded ${data.items.length} event(s). ${eventCursor ? 'Another page is available.' : 'End of results.'}`);
}
el('event-search-form').addEventListener('submit', event => { event.preventDefault(); run(() => searchEvents()); });
el('event-next').addEventListener('click', () => run(() => searchEvents(true)));
el('assistant-form').addEventListener('submit', event => {
  event.preventDefault();
  run(async () => {
    lastQuestion = dialoguePayload(el('event-question').value);
    el('question-request').textContent = 'Request ID: '+lastQuestion.client_request_id;
    const data = must(await api('/assistant/query',{method:'POST',body:lastQuestion}));
    showConversationState(data);
    notify(`${data.status}: ${data.message}`);
  });
});
el('retry-question').addEventListener('click', () => run(async () => {
  if (!lastQuestion) throw new Error('Ask a question first.');
  const data = must(await api('/assistant/query',{method:'POST',body:lastQuestion}));
  showConversationState(data);
  notify(`Reused the same request ID: ${data.status}.`);
}));
function fillEvent(event) {
  loadedEvent = event;
  const values = {'event-id':event.id,'event-version':event.version,'event-title':event.title,'event-type':event.event_type,'event-topic':event.topic_id,'event-venue':event.venue,'event-start':event.starts_at,'event-end':event.ends_at,'event-cost':event.cost_minor ?? '', 'event-deadline':event.registration_deadline || '', 'event-eligibility':event.eligibility_rules.mode,'event-years':(event.eligibility_rules.years || []).join(','),'event-departments':(event.eligibility_rules.departments || []).join(','),'event-status':event.status,'event-source':event.source_label,'event-source-url':event.source_url || '', 'event-description':event.description};
  for (const [id,value] of Object.entries(values)) el(id).value = value;
  el('save-event').textContent = 'Save event changes';
}
function newEvent() {
  loadedEvent = null;
  el('event-form').reset();
  el('event-id').value = ''; el('event-version').value = '';
  const start = new Date(Date.now()+86400000);
  el('event-start').value = start.toISOString();
  el('event-end').value = new Date(start.getTime()+7200000).toISOString();
  el('save-event').textContent = 'Create event';
}
function eventBody() {
  const mode = el('event-eligibility').value;
  const years = csv(el('event-years').value).map(Number);
  const departments = csv(el('event-departments').value);
  return {title:el('event-title').value,description:el('event-description').value,event_type:el('event-type').value,topic_id:el('event-topic').value,venue:el('event-venue').value,starts_at:el('event-start').value,ends_at:el('event-end').value,cost_minor:el('event-cost').value === '' ? null : Number(el('event-cost').value),currency:'INR',registration_deadline:el('event-deadline').value || null,eligibility_rules:{mode,years:mode === 'restricted' && years.length ? years : null,departments:mode === 'restricted' && departments.length ? departments : null},status:el('event-status').value,source_label:el('event-source').value,source_url:el('event-source-url').value || null};
}
el('new-event').addEventListener('click', () => { newEvent(); notify('New event form ready.'); });
el('list-admin-events').addEventListener('click', () => run(async () => {
  const data = must(await api('/admin/events'));
  showEventResults(data,true);
  notify('Admin events loaded above. Use Load for editing, or enter a record ID.');
}));
el('load-event').addEventListener('click', () => run(async () => {
  if (!el('event-id').value) throw new Error('Enter an event ID first.');
  fillEvent(must(await api('/admin/events/'+encodeURIComponent(el('event-id').value))));
  notify('Event and edit version loaded.');
}));
el('event-form').addEventListener('submit', event => {
  event.preventDefault();
  run(async () => {
    if (el('event-id').value && (!loadedEvent || el('event-id').value !== loadedEvent.id)) throw new Error('Load that record first, or use New event form.');
    const body = eventBody();
    const data = must(await api(loadedEvent ? '/admin/events/'+encodeURIComponent(loadedEvent.id) : '/admin/events', {method:loadedEvent ? 'PATCH' : 'POST', body:loadedEvent ? {...body,version:loadedEvent.version} : body}));
    fillEvent(data);
    notify(`Event saved: ${data.id} · version ${data.version}. Students can now search published records.`);
  });
});
for (const [id,status] of [['cancel-event','cancelled'],['archive-event','archived']]) {
  el(id).addEventListener('click', () => run(async () => {
    if (!loadedEvent || el('event-id').value !== loadedEvent.id) throw new Error('Load the event before changing its status.');
    const data = must(await api('/admin/events/'+encodeURIComponent(loadedEvent.id)+(status === 'archived' ? '?version='+loadedEvent.version : ''),status === 'archived' ? {method:'DELETE',body:undefined} : {method:'PATCH',body:{version:loadedEvent.version,status}}));
    fillEvent(data); notify(`Event ${status}.`);
  }));
}
newEvent();

el('interpret-question').addEventListener('click', () => run(async () => {
  const data = must(await api('/assistant/interpret', {method:'POST', body:{text:el('event-question').value,client_request_id:crypto.randomUUID()}}));
  notify(`${data.status}: ${data.message} No turn was saved.`);
}));
