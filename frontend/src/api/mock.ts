/** Browser-local demo transport, not the production NLP pipeline or an authorization boundary. */
import { ApiError } from './errors';
import type { Transport } from './client';
import {
  answerSchema,
  queryRequestSchema,
  profileSchema,
  resourceSchemas,
  type Answer,
  type BookingRecord,
  type Card,
  type Conversation,
  type DomainRecord,
  type EventRecord,
  type FacultyRecord,
  type Kind,
  type OfficeHourRecord,
  type Profile,
  type QueryRequest,
  type Resource,
  type RoomRecord,
  type SavedItem,
  type User,
} from './schemas';
import {
  CAMPUS_ZONE,
  DEMO_NOW,
  DEMO_PASSWORD,
  defaultProfile,
  demoUsers,
  referenceData,
  seedRecords,
} from './seed';

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}
type Filters = Answer['interpreted_query']['filters'];
type DemoConversation = Conversation & {
  owner: string;
  filters: Filters;
  intent: Answer['intent'];
  context: Answer['applied_context'];
  active_at: number;
  pending: Answer['clarification'];
  pending_at: number;
};
type State = {
  records: Record<Resource, DomainRecord[]>;
  profiles: Record<string, Profile>;
  conversations: DemoConversation[];
  saved: Record<string, Omit<SavedItem, 'record'>[]>;
  dedupe: Record<string, { payload: string; answer: Answer }>;
};
const KEY = 'campus.demo.v1';
const SESSION = 'campus.demo.session';
const clone = <T>(v: T): T => structuredClone(v);
const fail = (
  status: number,
  code: string,
  message: string,
  fields: Record<string, string[]> = {},
): never => {
  throw new ApiError(status, code, message, fields, crypto.randomUUID());
};
const label = (key: 'buildings' | 'departments' | 'topics' | 'facilities', id: string) =>
  referenceData[key].find((x) => x.id === id)?.label || id;
const timeNumber = (date: string) => new Date(date).getTime();
const day = (date: string) =>
  new Intl.DateTimeFormat('en-CA', {
    timeZone: CAMPUS_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(date));
const minute = (date: string) =>
  new Intl.DateTimeFormat('en-GB', {
    timeZone: CAMPUS_ZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(date));
export function eventCard(
  e: EventRecord,
  profile: Profile,
  saved = false,
): Extract<Card, { kind: 'event' }> {
  let eligibility: 'eligible' | 'ineligible' | 'unknown' = 'unknown';
  let basis = 'Eligibility has not been published.';
  if (e.eligibility_mode === 'all_students') {
    eligibility = 'eligible';
    basis = 'Open to all students.';
  }
  if (e.eligibility_mode === 'restricted') {
    const depMismatch =
      !!profile.department_id &&
      e.allowed_department_ids.length > 0 &&
      !e.allowed_department_ids.includes(profile.department_id);
    const yearMismatch =
      !!profile.year && e.allowed_years.length > 0 && !e.allowed_years.includes(profile.year);
    const missing =
      (e.allowed_department_ids.length > 0 && !profile.department_id) ||
      (e.allowed_years.length > 0 && !profile.year);
    eligibility = depMismatch || yearMismatch ? 'ineligible' : missing ? 'unknown' : 'eligible';
    basis =
      [
        e.allowed_department_ids.map((x) => label('departments', x)).join(', '),
        e.allowed_years.length ? 'Years ' + e.allowed_years.join(', ') : '',
      ]
        .filter(Boolean)
        .join('; ') || 'See the organizer for eligibility.';
  }
  return {
    kind: 'event',
    record_id: e.id,
    title: e.title,
    source_label: e.source_label,
    source_url: e.source_url,
    record_updated_at: e.updated_at,
    record_status: e.status,
    saved,
    description: e.description,
    starts_at: e.starts_at,
    ends_at: e.ends_at,
    venue: e.venue,
    event_type: e.event_type,
    topics: e.topic_ids.map((x) => label('topics', x)),
    cost_minor: e.cost_minor,
    currency: e.currency,
    eligibility,
    eligibility_basis: basis,
    registration_deadline: e.registration_deadline,
  };
}
export function roomCard(
  r: RoomRecord,
  requested: Extract<Card, { kind: 'room' }>['requested_interval'] = null,
  saved = false,
): Extract<Card, { kind: 'room' }> {
  return {
    kind: 'room',
    record_id: r.id,
    title: r.code,
    building: label('buildings', r.building_id),
    capacity: r.capacity,
    facilities: r.facility_ids.map((x) => label('facilities', x)),
    requested_interval: requested,
    schedule_coverage: r.coverage_complete ? 'complete' : 'unknown',
    availability_basis: 'scheduled_bookings',
    saved,
    record_status: r.status,
    source_label: r.source_label,
    source_url: r.source_url,
    record_updated_at: r.updated_at,
  };
}
export function facultyCard(
  f: FacultyRecord,
  meeting: Extract<Card, { kind: 'faculty' }>['meeting_interval'] = null,
  note: string | null = null,
  saved = false,
): Extract<Card, { kind: 'faculty' }> {
  return {
    kind: 'faculty',
    record_id: f.id,
    title: f.name,
    faculty_name: f.name,
    department: label('departments', f.department_id),
    location: f.location,
    meeting_interval: meeting,
    exception_note: note,
    saved,
    record_status: f.status,
    source_label: f.source_label,
    source_url: f.source_url,
    record_updated_at: f.updated_at,
  };
}
export function createMockTransport(storage: StorageLike, latency = 180): Transport {
  const stored = storage.getItem(KEY);
  let state: State;
  try {
    state = stored ? JSON.parse(stored) : null;
  } catch {
    state = null!;
  }
  if (!state)
    state = {
      records: seedRecords(),
      profiles: Object.fromEntries(demoUsers.map((u) => [u.id, clone(defaultProfile)])),
      conversations: [],
      saved: {},
      dedupe: {},
    };
  const persist = () => {
    try {
      storage.setItem(KEY, JSON.stringify(state));
    } catch {
      fail(
        507,
        'storage_full',
        'Demo storage is full. Delete older conversations or free browser storage.',
      );
    }
  };
  const user = (): User => {
    let session: { id: string; expires: number } | null = null;
    try {
      session = JSON.parse(storage.getItem(SESSION) || 'null');
    } catch {
      /* invalid session */
    }
    const u = demoUsers.find((u) => u.id === session?.id);
    if (!u || !session || session.expires < Date.now()) {
      storage.removeItem(SESSION);
      fail(401, 'session_expired', 'Your session has expired. Sign in to continue.');
    }
    return u!;
  };
  const isSaved = (uid: string, kind: Kind, id: string) =>
    (state.saved[uid] || []).some((s) => s.kind === kind && s.record_id === id);
  const cardFor = (uid: string, kind: Kind, id: string): Card | null => {
    const r = state.records[
      kind === 'event' ? 'events' : kind === 'room' ? 'rooms' : 'faculty'
    ].find((r) => r.id === id);
    if (!r) return null;
    return kind === 'event'
      ? eventCard(r as EventRecord, state.profiles[uid], isSaved(uid, kind, id))
      : kind === 'room'
        ? roomCard(r as RoomRecord, null, isSaved(uid, kind, id))
        : facultyCard(r as FacultyRecord, null, null, isSaved(uid, kind, id));
  };
  const page = <T>(items: T[], url: URL) => {
    const offset = Number(url.searchParams.get('cursor') || 0);
    const limit = Math.max(1, Math.min(Number(url.searchParams.get('limit') || 12), 50));
    if (!Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(limit))
      fail(422, 'invalid_cursor', 'Invalid page. Return to the first page.');
    return {
      items: items.slice(offset, offset + limit),
      next_cursor: offset + limit < items.length ? String(offset + limit) : null,
    };
  };
  const owned = (uid: string, id: string) =>
    state.conversations.find((c) => c.id === id && c.owner === uid) ||
    fail(404, 'not_found', 'This conversation is unavailable or has been deleted.');
  function query(uid: string, raw: unknown): Answer {
    const parsed = queryRequestSchema.safeParse(raw);
    if (!parsed.success) fail(422, 'validation_error', 'Check your question and try again.');
    const req = parsed.data as QueryRequest;
    if (!req.text.trim() && !req.clarification?.option_id)
      fail(422, 'text_required', 'Enter a question.');
    const key = uid + ':' + req.client_request_id;
    const payload = JSON.stringify(req);
    if (state.dedupe[key]) {
      if (state.dedupe[key].payload !== payload)
        fail(
          409,
          'request_conflict',
          'This request ID was already used for a different question. Start a new request.',
        );
      return clone(state.dedupe[key].answer);
    }
    const c: DemoConversation = req.conversation_id
      ? owned(uid, req.conversation_id)
      : {
          id: crypto.randomUUID(),
          title: req.text.slice(0, 90),
          updated_at: DEMO_NOW,
          turn_count: 0,
          turns: [],
          owner: uid,
          filters: {},
          intent: null,
          context: {},
          active_at: 0,
          pending: null,
          pending_at: 0,
        };
    const text = req.text.toLowerCase();
    const warnings: string[] = [];
    let intent: Answer['intent'] = /\b(rooms?|classrooms?|class room|labs?|capacity)\b/.test(text)
      ? 'find_available_rooms'
      : /\b(prof|professor|faculty|rao|nair|office hours|meet dr)\b/.test(text)
        ? 'find_faculty_office_hours'
        : /\b(events?|workshops?|talks?|meetups?|hackathons?|open.source|happening|attend)\b/.test(
              text,
            )
          ? 'find_events'
          : c.intent;
    if (/placement|weather|canteen|reserve|book a room|write.*essay|joke|notification/.test(text))
      intent = null;
    const expired = c.active_at > 0 && Date.now() - c.active_at > 30 * 60 * 1000;
    if (expired) {
      warnings.push(
        'Previous conversation context expired after 30 minutes. Please include your filters again.',
      );
      if (!/event|workshop|room|faculty|rao|nair|office hours/.test(text)) intent = null;
    }
    const same = intent === c.intent && !expired;
    const filters: Filters = same ? { ...c.filters } : {};
    const context: Answer['applied_context'] = same
      ? Object.fromEntries(
          Object.entries(c.context).map(([k, v]) => [k, { ...v, origin: 'prior_turn' }]),
        )
      : {};
    const set = (
      key: string,
      value: Filters[string],
      origin: Answer['applied_context'][string]['origin'],
    ) => {
      filters[key] = value;
      context[key] = { value, origin };
    };
    const allowed =
      intent === 'find_events'
        ? ['year', 'department_id', 'topic', 'event_type', 'date', 'free', 'venue']
        : intent === 'find_available_rooms'
          ? ['building_id', 'capacity', 'starts_at', 'ends_at', 'facility']
          : ['faculty_id', 'date'];
    for (const [k, v] of Object.entries(req.context_overrides)) {
      if (!allowed.includes(k))
        fail(
          422,
          'unsupported_override',
          'That context filter is not supported for this question.',
        );
      set(k, v, 'override');
    }
    if (intent === 'find_events') {
      const p = state.profiles[uid];
      if (filters.year === undefined && p.year) set('year', p.year, 'profile');
      if (filters.department_id === undefined && p.department_id)
        set('department_id', p.department_id, 'profile');
      const year = text.match(
        /(?:year\s*([1-4])|([1-4])(?:st|nd|rd|th)?[ -]year|\b(first|second|third|fourth)[ -]year)/,
      );
      if (year)
        set(
          'year',
          Number(year[1] || year[2]) || ['first', 'second', 'third', 'fourth'].indexOf(year[3]) + 1,
          'explicit_question',
        );
      if (/\bworkshops?\b/.test(text)) set('event_type', 'workshop', 'explicit_question');
      if (/\btalks?\b/.test(text)) set('event_type', 'talk', 'explicit_question');
      if (/\b(ai|artificial intelligence)\b/.test(text)) set('topic', 'ai', 'explicit_question');
      if (/\b(ml|machine learning)\b/.test(text)) set('topic', 'ml', 'explicit_question');
      if (/\bdesign\b/.test(text)) set('topic', 'design', 'explicit_question');
      if (/\bfree\b/.test(text)) set('free', true, 'explicit_question');
    }
    const date = /friday/.test(text)
      ? '2026-11-06'
      : /tomorrow/.test(text)
        ? '2026-11-05'
        : /today|right now/.test(text)
          ? '2026-11-04'
          : text.match(/\b2026-\d{2}-\d{2}\b/)?.[0];
    if (date) set('date', date, 'explicit_question');
    if (/this week/.test(text) && intent !== 'find_available_rooms')
      set('date', '2026-11-02/2026-11-09', 'explicit_question');
    let clarification: Answer['clarification'] = null;
    const ask = (field: string, prompt: string, options: { id: string; label: string }[] = []) => {
      clarification = { id: crypto.randomUUID(), field, prompt, options };
    };
    if (req.clarification) {
      if (
        !c.pending ||
        req.clarification.id !== c.pending.id ||
        Date.now() - c.pending_at > 10 * 60 * 1000
      )
        fail(
          409,
          'clarification_expired',
          'This clarification has expired. Ask your question again.',
        );
      if (
        req.clarification.option_id &&
        !c.pending!.options.some((o) => o.id === req.clarification!.option_id)
      )
        fail(422, 'invalid_option', 'Choose one of the offered options.');
      if (c.pending!.field === 'faculty_id') {
        const choice =
          req.clarification.option_id ||
          (state.records.faculty as FacultyRecord[]).find((f) =>
            text.includes(f.name.toLowerCase().replace('dr. ', '')),
          )?.id;
        if (choice) set('faculty_id', choice, 'explicit_question');
      }
    }
    if (intent === 'find_available_rooms') {
      if (/\bb[ -]?block\b/.test(text)) set('building_id', 'b', 'explicit_question');
      if (/\ba[ -]?block\b/.test(text)) set('building_id', 'a', 'explicit_question');
      const cap = text.match(/(?:for|least|capacity)\s*(\d+)\s*(?:people|students|seats)?/);
      if (cap) set('capacity', Number(cap[1]), 'explicit_question');
      const times = text.match(
        /(?:from\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:to|[-–])\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)/,
      );
      if (times) {
        const hour = (h: string, mer: string) => (Number(h) % 12) + (mer === 'pm' ? 12 : 0);
        const start = hour(times[1], times[3] || times[6]);
        const end = hour(times[4], times[6]);
        const d =
          typeof filters.date === 'string' && !filters.date.includes('/')
            ? filters.date
            : '2026-11-04';
        if (!date && !filters.date)
          warnings.push('For this demo, the interval uses today, 4 November 2026.');
        set(
          'starts_at',
          `${d}T${String(start).padStart(2, '0')}:${times[2] || '00'}:00+05:30`,
          'explicit_question',
        );
        set(
          'ends_at',
          `${d}T${String(end).padStart(2, '0')}:${times[5] || '00'}:00+05:30`,
          'explicit_question',
        );
      } else if (/right now/.test(text)) {
        set('starts_at', DEMO_NOW, 'explicit_question');
        set('ends_at', '2026-11-04T10:30:00+05:30', 'default');
        warnings.push('“Right now” means the next 30 minutes, using the fixed demo clock.');
      }
      if (!filters.starts_at || !filters.ends_at)
        ask(
          'interval',
          'What date and time do you need the room? For example, today from 2 to 3 PM.',
        );
      else if (timeNumber(String(filters.ends_at)) <= timeNumber(String(filters.starts_at)))
        ask('interval', 'The end must be after the start. What interval do you need?');
      else if (timeNumber(String(filters.ends_at)) - timeNumber(DEMO_NOW) > 30 * 86400000)
        ask(
          'interval',
          'Room searches cover the next 30 days. Which date within that period do you need?',
        );
    }
    if (intent === 'find_faculty_office_hours' && !filters.faculty_id) {
      const faculties = state.records.faculty as FacultyRecord[];
      const matches = faculties.filter((f) =>
        [f.name.replace(/^Dr\.\s*/, ''), ...f.aliases].some((name) =>
          name.trim() ? text.includes(name.trim().toLowerCase()) : false,
        ),
      );
      if (matches.length === 1) set('faculty_id', matches[0].id, 'explicit_question');
      else
        ask(
          'faculty_id',
          matches.length > 1
            ? 'Which Professor Rao do you mean?'
            : 'Whose published office hours would you like?',
          (matches.length ? matches : faculties).map((f) => ({
            id: f.id,
            label: f.name + ' · ' + label('departments', f.department_id),
          })),
        );
    }
    if (/\bfree\b/.test(text) && !intent)
      ask('domain', 'Do you mean a free event or a room with no scheduled booking?');
    if (/\b(room|classroom)\b/.test(text) && /\b(event|workshop)\b/.test(text)) {
      intent = null;
      ask(
        'domain',
        'Please ask about one thing at a time: events, rooms, or faculty office hours.',
      );
    }
    let results: Card[] = [];
    let coverage: Answer['data_coverage'] = {
      status: 'complete',
      message: 'Demo campus records. These are fictional examples.',
    };
    if (intent && !clarification) {
      if (intent === 'find_events') {
        const p = {
          ...state.profiles[uid],
          year: typeof filters.year === 'number' ? filters.year : null,
          department_id: typeof filters.department_id === 'string' ? filters.department_id : null,
        };
        results = (state.records.events as EventRecord[])
          .filter((e) => e.status === 'published' && timeNumber(e.ends_at) > timeNumber(DEMO_NOW))
          .filter((e) => !filters.event_type || e.event_type === filters.event_type)
          .filter((e) => !filters.topic || e.topic_ids.includes(String(filters.topic)))
          .filter((e) => !filters.free || e.cost_minor === 0)
          .filter((e) => {
            if (!filters.date) return true;
            const [a, b] = String(filters.date).split('/');
            return b ? e.starts_at < b && e.ends_at > a : day(e.starts_at) === a;
          })
          .filter(
            (e) =>
              !filters.venue || e.venue.toLowerCase().includes(String(filters.venue).toLowerCase()),
          )
          .map((e) => eventCard(e, p, isSaved(uid, 'event', e.id)))
          .sort(
            (a, b) =>
              a.starts_at.localeCompare(b.starts_at) || a.record_id.localeCompare(b.record_id),
          );
        if (/eligible|can i attend|for .*years?/.test(text))
          results = results.filter((c) => c.kind === 'event' && c.eligibility === 'eligible');
        if (/quantum|astronomy|underwater|no matches/.test(text)) results = [];
      } else if (intent === 'find_available_rooms') {
        const start = String(filters.starts_at);
        const end = String(filters.ends_at);
        const date = day(start);
        const candidates = (state.records.rooms as RoomRecord[]).filter(
          (r) =>
            r.status === 'active' &&
            (!filters.building_id || r.building_id === filters.building_id) &&
            (!filters.capacity || r.capacity >= Number(filters.capacity)),
        );
        let gaps = false;
        results = candidates
          .filter((r) => {
            if (
              !r.coverage_complete ||
              !r.coverage_start ||
              !r.coverage_end ||
              timeNumber(start) < timeNumber(r.coverage_start) ||
              timeNumber(end) > timeNumber(r.coverage_end)
            ) {
              gaps = true;
              return false;
            }
            const weekday = new Date(date + 'T12:00:00Z').getUTCDay();
            if (
              !r.opening_hours.some(
                (o) => o.weekday === weekday && minute(start) >= o.start && minute(end) <= o.end,
              ) ||
              day(start) !== day(end)
            )
              return false;
            const closed = state.records['room-closures'].some((x) => {
              const b = x as unknown as {
                room_id: string;
                starts_at: string;
                ends_at: string;
                status: string;
              };
              return (
                b.status === 'active' &&
                b.room_id === r.id &&
                timeNumber(b.starts_at) < timeNumber(end) &&
                timeNumber(b.ends_at) > timeNumber(start)
              );
            });
            const booked = (state.records.bookings as BookingRecord[]).some((b) => {
              if (b.room_id !== r.id || b.status !== 'active') return false;
              let bs = b.starts_at;
              let be = b.ends_at;
              if (b.recurrence === 'weekly') {
                if (
                  date < day(b.starts_at) ||
                  date > (b.recurrence_until || date) ||
                  new Date(b.starts_at).getUTCDay() !== weekday
                )
                  return false;
                bs = `${date}T${minute(b.starts_at)}:00+05:30`;
                be = `${date}T${minute(b.ends_at)}:00+05:30`;
              }
              const exception = state.records['booking-exceptions'].find(
                (x) =>
                  (x as unknown as { booking_id: string; occurrence_date: string }).booking_id ===
                    b.id &&
                  (x as unknown as { occurrence_date: string }).occurrence_date === date &&
                  x.status === 'active',
              ) as unknown as
                { action: string; replacement_start: string; replacement_end: string } | undefined;
              if (exception?.action === 'cancel') return false;
              if (exception?.action === 'replace') {
                bs = exception.replacement_start;
                be = exception.replacement_end;
              }
              return timeNumber(bs) < timeNumber(end) && timeNumber(be) > timeNumber(start);
            });
            return !closed && !booked;
          })
          .map((r) => roomCard(r, { starts_at: start, ends_at: end }, isSaved(uid, 'room', r.id)));
        if (gaps) {
          coverage = {
            status: results.length ? 'partial' : 'unknown',
            message:
              'Some matching rooms have incomplete timetable coverage. They are not shown as available.',
          };
          warnings.push(coverage.message);
        }
      } else {
        const f = (state.records.faculty as FacultyRecord[]).find(
          (f) => f.id === filters.faculty_id && f.status === 'active',
        );
        const rules = (state.records['office-hours'] as OfficeHourRecord[]).filter(
          (h) => h.faculty_id === f?.id && h.status === 'active',
        );
        const range = String(filters.date || '2026-11-04/2026-11-11').split('/');
        if (!rules.length)
          coverage = {
            status: 'unknown',
            message: 'No published office hours are available for this faculty member.',
          };
        for (const rule of rules)
          for (let n = 0; n < (range[1] ? 7 : 1); n++) {
            const dt = new Date(range[0] + 'T12:00:00Z');
            dt.setUTCDate(dt.getUTCDate() + n);
            const d = dt.toISOString().slice(0, 10);
            if (
              dt.getUTCDay() !== rule.weekday ||
              d < rule.effective_from ||
              d > rule.effective_until
            )
              continue;
            let starts_at = `${d}T${rule.start_time}:00+05:30`;
            let ends_at = `${d}T${rule.end_time}:00+05:30`;
            let note: string | null = null;
            const exc = state.records['office-hour-exceptions'].find(
              (x) =>
                (x as unknown as { office_hour_id: string; occurrence_date: string })
                  .office_hour_id === rule.id &&
                (x as unknown as { occurrence_date: string }).occurrence_date === d &&
                x.status === 'active',
            ) as unknown as
              | { action: string; replacement_start: string; replacement_end: string; note: string }
              | undefined;
            if (exc?.action === 'cancel') continue;
            if (exc?.action === 'replace') {
              starts_at = exc.replacement_start;
              ends_at = exc.replacement_end;
              note = exc.note;
            }
            if (f)
              results.push(
                facultyCard(
                  { ...f, location: rule.location },
                  { starts_at, ends_at },
                  note,
                  isSaved(uid, 'faculty', f.id),
                ),
              );
          }
      }
    }
    const truncated = results.length > 6;
    results = results.slice(0, 6);
    if (truncated)
      warnings.push(
        'Showing the first 6 matches. Narrow your question to see a smaller result set.',
      );
    const status: Answer['status'] = clarification
      ? 'clarification_required'
      : !intent
        ? 'unsupported'
        : coverage.status === 'unknown' && results.length === 0
          ? 'information_unavailable'
          : results.length
            ? 'answered'
            : 'no_results';
    const message =
      status === 'clarification_required'
        ? clarification!.prompt
        : status === 'unsupported'
          ? 'I can help with campus events, scheduled room availability, and published faculty office hours. Try one of those.'
          : status === 'information_unavailable'
            ? 'There is not enough published information to answer this confidently.'
            : status === 'no_results'
              ? 'No matching records were found. Try a different date or remove a filter.'
              : intent === 'find_events'
                ? `Here ${results.length === 1 ? 'is an event' : 'are ' + results.length + ' events'} to explore.`
                : intent === 'find_available_rooms'
                  ? `Found ${results.length} room${results.length === 1 ? '' : 's'} with no scheduled booking for your interval.`
                  : 'Here are the published office hours.';
    const answer = answerSchema.parse({
      conversation_id: c.id,
      turn_id: crypto.randomUUID(),
      request_id: req.client_request_id,
      status,
      intent,
      message,
      interpreted_query: { intent, filters },
      applied_context: context,
      results,
      clarification,
      answered_at: DEMO_NOW,
      campus_timezone: CAMPUS_ZONE,
      warnings,
      data_coverage: coverage,
      next_cursor: null,
    });
    c.turns.push({
      id: answer.turn_id,
      question: req.text || 'Selected clarification option',
      answer,
    });
    c.turn_count = c.turns.length;
    c.updated_at = new Date().toISOString();
    c.intent = intent;
    c.filters = filters;
    c.context = context;
    c.pending = clarification;
    c.pending_at = Date.now();
    c.active_at = Date.now();
    if (!req.conversation_id) state.conversations.push(c);
    state.dedupe[key] = { payload, answer: clone(answer) };
    persist();
    return answer;
  }
  let queue = Promise.resolve<unknown>(undefined);
  async function dispatch(path: string, init: RequestInit = {}): Promise<unknown> {
    if (init.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    const url = new URL(path, 'http://demo.local');
    const parts = url.pathname.split('/').filter(Boolean);
    const method = init.method || 'GET';
    const body = init.body ? JSON.parse(String(init.body)) : {};
    if (url.pathname === '/auth/csrf') return { csrf_token: 'demo-only-csrf' };
    if (url.pathname === '/auth/login' && method === 'POST') {
      const u = demoUsers.find((u) => u.email.toLowerCase() === String(body.email).toLowerCase());
      if (!u || body.password !== DEMO_PASSWORD)
        fail(401, 'invalid_credentials', 'Email or password is incorrect.');
      storage.setItem(SESSION, JSON.stringify({ id: u!.id, expires: Date.now() + 8 * 3600000 }));
      return u!;
    }
    if (url.pathname === '/auth/logout') {
      storage.removeItem(SESSION);
      return null;
    }
    const u = user();
    if (url.pathname === '/auth/me') return u;
    if (url.pathname === '/reference-data') return referenceData;
    if (url.pathname === '/me/profile') {
      if (method === 'PATCH') {
        state.profiles[u.id] = profileSchema.parse(body);
        persist();
      }
      return state.profiles[u.id];
    }
    if (url.pathname === '/assistant/query' && method === 'POST') return query(u.id, body);
    if (parts[0] === 'conversations') {
      if (parts[1]) {
        const c = owned(u.id, parts[1]);
        if (method === 'DELETE') {
          state.conversations = state.conversations.filter((x) => x.id !== c.id);
          for (const [k, v] of Object.entries(state.dedupe))
            if (v.answer.conversation_id === c.id) delete state.dedupe[k];
          persist();
          return null;
        }
        return c;
      }
      return page(
        state.conversations
          .filter((c) => c.owner === u.id)
          .sort((a, b) => b.updated_at.localeCompare(a.updated_at) || a.id.localeCompare(b.id)),
        url,
      );
    }
    if (parts[0] === 'me' && parts[1] === 'saved') {
      if (parts[2] && parts[3]) {
        const kind = parts[2] as Kind;
        const id = parts[3];
        if (method !== 'DELETE' && !cardFor(u.id, kind, id))
          fail(404, 'not_found', 'This record is no longer available.');
        const entries = (state.saved[u.id] ||= []);
        if (method === 'PUT' && !isSaved(u.id, kind, id))
          entries.push({ kind, record_id: id, saved_at: new Date().toISOString() });
        if (method === 'DELETE')
          state.saved[u.id] = entries.filter((s) => s.kind !== kind || s.record_id !== id);
        persist();
        return null;
      }
      return page(
        (state.saved[u.id] || [])
          .map((s) => ({ ...s, record: cardFor(u.id, s.kind, s.record_id) }))
          .sort((a, b) => b.saved_at.localeCompare(a.saved_at)),
        url,
      );
    }
    if (parts[0] === 'admin') {
      if (u.role !== 'admin') fail(403, 'forbidden', 'Admin access is required.');
      const resource = parts[1] as Resource;
      const schema = resourceSchemas[resource];
      if (!schema) fail(404, 'not_found', 'Unknown resource.');
      const records = state.records[resource];
      const existing = parts[2] ? records.find((r) => r.id === parts[2]) : null;
      if (parts[2] && !existing) fail(404, 'not_found', 'This record no longer exists.');
      if (method === 'GET') {
        if (existing) return existing;
        const q = (url.searchParams.get('search') || '').toLowerCase();
        return page(
          records
            .filter((r) => JSON.stringify(r).toLowerCase().includes(q))
            .sort((a, b) => a.id.localeCompare(b.id)),
          url,
        );
      }
      if (method === 'DELETE' && existing) {
        if (new Headers(init.headers).get('If-Match') !== String(existing.version))
          fail(409, 'stale_version', 'This record changed. Reload before archiving.');
        existing.status = 'archived';
        existing.version++;
        existing.updated_at = new Date().toISOString();
        persist();
        return null;
      }
      if (method === 'PATCH' && existing && body.version !== existing.version)
        fail(
          409,
          'stale_version',
          'Another admin changed this record. Reload their changes before saving.',
        );
      const parsed = schema.safeParse({
        ...existing,
        ...body,
        id: existing?.id || crypto.randomUUID(),
        version: existing ? existing.version + 1 : 1,
        updated_at: new Date().toISOString(),
      });
      if (!parsed.success) {
        const fields: Record<string, string[]> = {};
        for (const issue of parsed.error.issues)
          (fields[String(issue.path[0])] ||= []).push(issue.message);
        fail(422, 'validation_error', 'Please check the highlighted fields.', fields);
      }
      const record = parsed.data as DomainRecord;
      const r = record as unknown as Record<string, unknown>;
      const fields: Record<string, string[]> = {};
      if (
        r.starts_at &&
        r.ends_at &&
        timeNumber(String(r.ends_at)) <= timeNumber(String(r.starts_at))
      )
        fields.ends_at = ['End must be after start.'];
      if (
        r.effective_from &&
        r.effective_until &&
        String(r.effective_until) < String(r.effective_from)
      )
        fields.effective_until = ['End date must be on or after start.'];
      if (r.start_time && r.end_time && String(r.end_time) <= String(r.start_time))
        fields.end_time = ['End time must be after start.'];
      if (
        r.coverage_start &&
        r.coverage_end &&
        timeNumber(String(r.coverage_end)) <= timeNumber(String(r.coverage_start))
      )
        fields.coverage_end = ['Coverage end must be after start.'];
      if (
        r.action === 'replace' &&
        (!r.replacement_start ||
          !r.replacement_end ||
          timeNumber(String(r.replacement_end)) <= timeNumber(String(r.replacement_start)))
      )
        fields.replacement_end = ['A replacement needs a valid start and end.'];
      if (
        r.recurrence === 'weekly' &&
        (!r.recurrence_until || String(r.recurrence_until) < day(String(r.starts_at)))
      )
        fields.recurrence_until = ['Choose a recurrence end date on or after the first booking.'];
      if (
        r.registration_deadline &&
        r.ends_at &&
        timeNumber(String(r.registration_deadline)) > timeNumber(String(r.ends_at))
      )
        fields.registration_deadline = ['Deadline must be before the event ends.'];
      if (
        resource === 'rooms' &&
        records.some(
          (x) =>
            x.id !== record.id &&
            (x as RoomRecord).code.toLowerCase() === String(r.code).toLowerCase(),
        )
      )
        fields.code = ['Room code is already in use.'];
      for (const [key, target] of Object.entries({
        room_id: 'rooms',
        faculty_id: 'faculty',
        booking_id: 'bookings',
        office_hour_id: 'office-hours',
      }))
        if (r[key] && !state.records[target as Resource].some((x) => x.id === r[key]))
          fields[key] = ['Choose an existing record.'];
      if (
        resource === 'aliases' &&
        records.some(
          (x) =>
            x.id !== record.id &&
            (x as unknown as { alias: string }).alias.toLowerCase() ===
              String(r.alias).toLowerCase(),
        )
      )
        fields.alias = ['This alias already exists. Check for ambiguity.'];
      if (Object.keys(fields).length)
        fail(422, 'validation_error', 'Please check the highlighted fields.', fields);
      if (resource === 'bookings' && r.status === 'active') {
        const b = record as BookingRecord;
        const occurrences = (v: BookingRecord) => {
          const list: [number, number][] = [];
          let start = timeNumber(v.starts_at);
          let end = timeNumber(v.ends_at);
          do {
            list.push([start, end]);
            start += 7 * 86400000;
            end += 7 * 86400000;
          } while (
            v.recurrence === 'weekly' &&
            list.length < 54 &&
            day(new Date(start).toISOString()) <= (v.recurrence_until || '')
          );
          return list;
        };
        if (
          (records as BookingRecord[]).some(
            (x) =>
              x.id !== b.id &&
              x.status === 'active' &&
              x.room_id === b.room_id &&
              occurrences(x).some(([xs, xe]) =>
                occurrences(b).some(([bs, be]) => xs < be && xe > bs),
              ),
          )
        )
          fail(409, 'booking_conflict', 'This room already has a booking during that interval.', {
            starts_at: ['Choose a different room or time.'],
          });
      }
      if (existing) records[records.indexOf(existing)] = record;
      else records.push(record);
      persist();
      return record;
    }
    if (parts[0] === 'events') {
      if (parts[1])
        return cardFor(u.id, 'event', parts[1]) || fail(404, 'not_found', 'Event not found.');
      return page(
        (state.records.events as EventRecord[])
          .filter((e) => e.status === 'published' && timeNumber(e.ends_at) > timeNumber(DEMO_NOW))
          .sort((a, b) => a.starts_at.localeCompare(b.starts_at) || a.id.localeCompare(b.id))
          .map((e) => eventCard(e, state.profiles[u.id], isSaved(u.id, 'event', e.id))),
        url,
      );
    }
    if (parts[0] === 'rooms' || parts[0] === 'faculty')
      return (
        cardFor(u.id, parts[0] === 'rooms' ? 'room' : 'faculty', parts[1]) ||
        fail(404, 'not_found', 'Record not found.')
      );
    fail(404, 'not_found', 'This demo endpoint does not exist.');
  }
  return (path, init) => {
    const result = queue.then(async () => {
      if (latency) await new Promise((resolve) => setTimeout(resolve, latency));
      try {
        return clone(await dispatch(path, init));
      } catch (e) {
        if (
          e instanceof ApiError &&
          e.status === 401 &&
          !path.startsWith('/auth/') &&
          typeof window !== 'undefined'
        )
          window.dispatchEvent(new Event('session-expired'));
        throw e;
      }
    });
    queue = result.catch(() => undefined);
    return result;
  };
}
