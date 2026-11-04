'use strict';
let activeClarification = null, historyOffset = null, turnOffset = null, savedOffset = null;
function showConversationState(data) {
  el('conversation-id').value = data.conversation_id;
  el('conversation-version').value = data.conversation_version || '';
  activeClarification = data.clarification || null;
  el('reply-active').checked = Boolean(activeClarification);
  el('clarification-prompt').textContent = activeClarification ? activeClarification.prompt : 'No active clarification.';
  el('clarification-option').replaceChildren(new Option('Text reply using question field', ''));
  for (const option of activeClarification?.options || []) el('clarification-option').append(new Option(option.label, option.id));
}
function dialoguePayload(text) {
  const payload = {text, client_request_id:crypto.randomUUID()};
  if (el('conversation-id').value) {
    payload.conversation_id = el('conversation-id').value;
    if (el('conversation-version').value) payload.conversation_version = Number(el('conversation-version').value);
  }
  if (el('reply-active').checked) {
    if (!activeClarification) throw new Error('Open the conversation to restore its active clarification.');
    payload.clarification = {id:activeClarification.id};
    if (el('clarification-option').value) payload.clarification.option_id = el('clarification-option').value;
  }
  return payload;
}
el('clarification-option').addEventListener('change', () => {
  const selected = activeClarification?.options.find(o => o.id === el('clarification-option').value);
  if (selected) el('event-question').value = selected.label;
});
el('conversation-id').addEventListener('input', () => {
  el('conversation-version').value = ''; activeClarification = null;
  el('reply-active').checked = false; el('clarification-prompt').textContent = 'Open this conversation to load its current version and clarification.';
});
el('conversation-new').addEventListener('click', () => {
  showConversationState({conversation_id:'',conversation_version:null});lastQuestion = null;
  notify('New conversation ready. Enter a complete question.');
});
async function loadHistory(next = false) {
  if (next && historyOffset === null) throw new Error('No next history page.');
  const data = must(await api('/conversations?limit=10&offset='+(next ? historyOffset : 0)));
  historyOffset = data.next_offset;el('history-results').replaceChildren();
  for (const item of data.items) {
    const row = document.createElement('p'), button = document.createElement('button');
    button.type = 'button';button.textContent = `Open ${item.title} (${item.turn_count} turns)`;
    button.addEventListener('click', () => run(async () => {el('conversation-id').value = item.id;await openHistory();}));
    row.append(button);el('history-results').append(row);
  }
  notify(`Loaded ${data.items.length} owned conversations.`);
}
async function openHistory(next = false) {
  if (!el('conversation-id').value) throw new Error('Select or enter a conversation ID.');
  if (next && turnOffset === null) throw new Error('No next turn page.');
  const data = must(await api('/conversations/'+encodeURIComponent(el('conversation-id').value)+'?limit=10&offset='+(next ? turnOffset : 0)));
  turnOffset = data.next_offset;
  showConversationState({conversation_id:data.conversation.id,conversation_version:data.conversation.version,clarification:data.active_clarification});
  notify(`Opened ${data.conversation.title}. ${data.conversation.turn_count} saved turns; context expiry ${data.conversation.state_expires_at || 'none'}.`);
}
el('history-list').addEventListener('click', () => run(() => loadHistory()));
el('history-next').addEventListener('click', () => run(() => loadHistory(true)));
el('history-load').addEventListener('click', () => run(() => openHistory()));
el('history-turn-next').addEventListener('click', () => run(() => openHistory(true)));
el('history-delete').addEventListener('click', () => run(async () => {
  const id = el('conversation-id').value;
  if (!id) throw new Error('Select a conversation first.');
  if (!window.confirm('Permanently delete this conversation and its stored questions, answers and dialogue state?')) return;
  must(await api('/conversations/'+encodeURIComponent(id),{method:'DELETE'}));
  showConversationState({conversation_id:'',conversation_version:null});lastQuestion = null;
  el('history-results').replaceChildren();notify('Conversation deleted. Saved records were retained.');
}));
async function loadSaved(next = false) {
  if (next && savedOffset === null) throw new Error('No next saved page.');
  const data = must(await api('/me/saved?limit=10&offset='+(next ? savedOffset : 0)));
  savedOffset = data.next_offset;el('saved-results').replaceChildren();
  for (const item of data.items) {
    const row = document.createElement('p'), button = document.createElement('button');
    button.type='button';button.textContent=`${item.kind} · ${item.current?.title || item.current?.code || item.current?.name || item.record_id} · ${item.record_status}${item.changed ? ' · changed since save' : ''}`;
    button.addEventListener('click', () => {el('saved-kind').value=item.kind;el('saved-id').value=item.record_id;});
    row.append(button);el('saved-results').append(row);
  }
  notify(`Loaded ${data.items.length} current saved records. Room saves contain metadata, not current vacancy.`);
}
for (const [id, method] of [['saved-put','PUT'],['saved-remove','DELETE']]) el(id).addEventListener('click', () => run(async () => {
  if (!el('saved-id').value) throw new Error('Enter a canonical record ID.');
  const data = must(await api('/me/saved/'+el('saved-kind').value+'/'+encodeURIComponent(el('saved-id').value),{method}));
  notify(method === 'PUT' ? `Saved ${data.kind} ${data.record_id}.` : 'Save removed.');
}));
el('saved-list').addEventListener('click', () => run(() => loadSaved()));
el('saved-next').addEventListener('click', () => run(() => loadSaved(true)));
function resetPersonalView() {
  showConversationState({conversation_id:'',conversation_version:null});
  lastQuestion=null;historyOffset=null;turnOffset=null;savedOffset=null;
  el('history-results').replaceChildren();el('saved-results').replaceChildren();
  el('saved-id').value='';el('event-question').value='';el('question-request').textContent='Each new question gets a new request ID; retries reuse it.';
}
