import type { Answer, Conversation } from './schemas';
import { DEMO_NOW, defaultProfile, seedEvents, seedFaculty, seedRooms } from './seed';
import { eventCard, facultyCard, roomCard } from './mock';

const base: Answer = {
  conversation_id: 'fixture-conversation',
  turn_id: 'fixture-turn',
  request_id: 'fixture-request',
  status: 'answered',
  intent: 'find_events',
  message: 'Here is an event to explore.',
  interpreted_query: {
    intent: 'find_events',
    filters: { event_type: 'workshop', year: 2, date: '2026-11-02/2026-11-09' },
  },
  applied_context: {
    year: { value: 2, origin: 'profile' },
    event_type: { value: 'workshop', origin: 'explicit_question' },
  },
  results: [eventCard(seedEvents[0], defaultProfile)],
  clarification: null,
  answered_at: DEMO_NOW,
  campus_timezone: 'Asia/Kolkata',
  warnings: [],
  data_coverage: { status: 'complete', message: 'Fictional demo campus records.' },
  next_cursor: null,
};
export const answerFixtures: Record<string, Answer> = {
  'event-answer': base,
  'room-answer': {
    ...base,
    intent: 'find_available_rooms',
    interpreted_query: {
      intent: 'find_available_rooms',
      filters: { starts_at: '2026-11-04T14:00:00+05:30', ends_at: '2026-11-04T15:00:00+05:30' },
    },
    applied_context: {},
    message: 'B-204 has no scheduled booking for your interval.',
    results: [
      roomCard(seedRooms[0], {
        starts_at: '2026-11-04T14:00:00+05:30',
        ends_at: '2026-11-04T15:00:00+05:30',
      }),
    ],
  },
  'office-hours-answer': {
    ...base,
    intent: 'find_faculty_office_hours',
    interpreted_query: {
      intent: 'find_faculty_office_hours',
      filters: { faculty_id: seedFaculty[0].id, date: '2026-11-05' },
    },
    applied_context: {},
    message: 'Here are the published office hours.',
    results: [
      facultyCard(seedFaculty[0], {
        starts_at: '2026-11-05T14:00:00+05:30',
        ends_at: '2026-11-05T16:00:00+05:30',
      }),
    ],
  },
  'no-matches': {
    ...base,
    status: 'no_results',
    results: [],
    message: 'No matching events were found. Try another date.',
  },
  'missing-coverage': {
    ...base,
    status: 'information_unavailable',
    intent: 'find_available_rooms',
    interpreted_query: { intent: 'find_available_rooms', filters: { building_id: 'a' } },
    applied_context: {},
    results: [],
    message: 'There is not enough timetable coverage to answer confidently.',
    warnings: ['Missing schedules do not establish availability.'],
    data_coverage: { status: 'unknown', message: 'A Block timetable coverage is incomplete.' },
  },
  'ambiguous-faculty': {
    ...base,
    intent: 'find_faculty_office_hours',
    status: 'clarification_required',
    interpreted_query: { intent: 'find_faculty_office_hours', filters: { date: '2026-11-05' } },
    applied_context: {},
    results: [],
    message: 'Which Professor Rao do you mean?',
    clarification: {
      id: 'clarification-faculty',
      field: 'faculty_id',
      prompt: 'Which Professor Rao do you mean?',
      options: seedFaculty.slice(0, 2).map((f) => ({ id: f.id, label: f.name })),
    },
  },
  'missing-room-interval': {
    ...base,
    intent: 'find_available_rooms',
    status: 'clarification_required',
    interpreted_query: { intent: 'find_available_rooms', filters: {} },
    applied_context: {},
    results: [],
    message: 'What date and time do you need the room?',
    clarification: {
      id: 'clarification-interval',
      field: 'interval',
      prompt: 'What date and time do you need the room?',
      options: [],
    },
  },
  'follow-up-filter-change': {
    ...base,
    interpreted_query: {
      intent: 'find_events',
      filters: { event_type: 'workshop', year: 2, date: '2026-11-06' },
    },
    applied_context: {
      event_type: { value: 'workshop', origin: 'prior_turn' },
      year: { value: 2, origin: 'prior_turn' },
      date: { value: '2026-11-06', origin: 'explicit_question' },
    },
  },
  'unsupported-request': {
    ...base,
    status: 'unsupported',
    intent: null,
    interpreted_query: { intent: null, filters: {} },
    applied_context: {},
    results: [],
    message: 'I can help with events, scheduled room availability, and published office hours.',
  },
  'truncated-answer': {
    ...base,
    warnings: ['Showing the first 6 matches. Narrow your question to see a smaller result set.'],
  },
};
export const errorFixtures = {
  'expired-login': {
    status: 401,
    body: {
      error: {
        code: 'session_expired',
        message: 'Your session has expired. Sign in to continue.',
        field_errors: {},
        request_id: 'fixture-expired',
      },
    },
  },
  'validation-error': {
    status: 422,
    body: {
      error: {
        code: 'validation_error',
        message: 'Check the highlighted fields.',
        field_errors: { ends_at: ['End must be after start.'] },
        request_id: 'fixture-validation',
      },
    },
  },
  'backend-outage': {
    status: 503,
    body: {
      error: {
        code: 'service_unavailable',
        message: 'The campus service is temporarily unavailable. Try again shortly.',
        field_errors: {},
        request_id: 'fixture-outage',
      },
    },
  },
};
export const savedFixture = {
  kind: 'event' as const,
  record_id: 'event-ai',
  saved_at: DEMO_NOW,
  record: eventCard(
    { ...seedEvents[0], status: 'cancelled', version: 2, updated_at: '2026-11-04T11:00:00+05:30' },
    defaultProfile,
    true,
  ),
};
export const historicalFixture: Conversation = {
  id: base.conversation_id,
  title: 'Any ML workshops this week?',
  updated_at: DEMO_NOW,
  turn_count: 1,
  turns: [{ id: base.turn_id, question: 'Any ML workshops this week?', answer: base }],
};
