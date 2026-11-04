import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

// Synthetic annotation drafts for team review; never present these as collected student data.
type Group = {
  family: string;
  intent: string | null;
  status: string;
  filters: Record<string, unknown>;
  results: string[] | null;
  missing?: string[];
  questions: string[];
};
const groups: Group[] = [
  {
    family: 'events-ai-week',
    intent: 'find_events',
    status: 'answered',
    filters: {
      event_type: 'workshop',
      topic: 'ai',
      starts_at: '2026-11-02T00:00:00+05:30',
      ends_at: '2026-11-09T00:00:00+05:30',
    },
    results: ['event-ai'],
    questions: [
      'Any AI workshops this week?',
      'Find AI workshops this week.',
      'What AI workshops are happening this week?',
      'Show me AI workshops this week.',
      'Are there AI workshops this week?',
      'I want an AI workshop this week.',
    ],
  },
  {
    family: 'events-free-friday',
    intent: 'find_events',
    status: 'answered',
    filters: {
      free: true,
      starts_at: '2026-11-06T00:00:00+05:30',
      ends_at: '2026-11-07T00:00:00+05:30',
    },
    results: ['event-ai', 'event-meet'],
    questions: [
      'Any free events on Friday?',
      'Find free events on Friday.',
      'Show free events on Friday.',
      'Which events are free on Friday?',
      'What free events are happening on Friday?',
      'I want a free event on Friday.',
    ],
  },
  {
    family: 'events-design-tomorrow',
    intent: 'find_events',
    status: 'answered',
    filters: {
      topic: 'design',
      starts_at: '2026-11-05T00:00:00+05:30',
      ends_at: '2026-11-06T00:00:00+05:30',
    },
    results: ['event-design'],
    questions: [
      'Any design events tomorrow?',
      'Find design events tomorrow.',
      'Show design events tomorrow.',
      'What design events happen tomorrow?',
      'Is there a design event tomorrow?',
      'I want to attend a design event tomorrow.',
    ],
  },
  {
    family: 'rooms-b-adjacent',
    intent: 'find_available_rooms',
    status: 'answered',
    filters: {
      building_id: 'b',
      starts_at: '2026-11-04T14:00:00+05:30',
      ends_at: '2026-11-04T15:00:00+05:30',
    },
    results: ['room-b204'],
    questions: [
      'Find a room in B Block today from 2 to 3 PM.',
      'Any rooms in B Block today from 2 to 3 PM?',
      'A classroom in B Block today from 2 to 3 PM please.',
      'Which room in B Block has no scheduled booking today from 2 to 3 PM?',
      'Show rooms in B Block today from 2 to 3 PM.',
      'I need a room in B Block today from 2 to 3 PM.',
    ],
  },
  {
    family: 'rooms-missing-interval',
    intent: 'find_available_rooms',
    status: 'clarification_required',
    filters: { building_id: 'b' },
    missing: ['interval'],
    results: null,
    questions: [
      'Find a room in B Block.',
      'Any rooms in B Block?',
      'Show classrooms in B Block.',
      'I need a classroom in B Block.',
      'Which rooms are available in B Block?',
      'Can you find a room in B Block?',
    ],
  },
  {
    family: 'rooms-missing-coverage',
    intent: 'find_available_rooms',
    status: 'information_unavailable',
    filters: {
      building_id: 'a',
      starts_at: '2026-11-04T14:00:00+05:30',
      ends_at: '2026-11-04T15:00:00+05:30',
    },
    results: [],
    questions: [
      'Find a room in A Block today from 2 to 3 PM.',
      'Any rooms in A Block today from 2 to 3 PM?',
      'A classroom in A Block today from 2 to 3 PM please.',
      'Which room in A Block has no scheduled booking today from 2 to 3 PM?',
      'Show rooms in A Block today from 2 to 3 PM.',
      'I need a room in A Block today from 2 to 3 PM.',
    ],
  },
  {
    family: 'faculty-rao-ambiguous',
    intent: 'find_faculty_office_hours',
    status: 'clarification_required',
    filters: { date: '2026-11-05' },
    missing: ['faculty_id'],
    results: null,
    questions: [
      'Professor Rao office hours tomorrow?',
      'When can I meet Professor Rao tomorrow?',
      'Show Professor Rao office hours tomorrow.',
      'Is Professor Rao available for a meeting tomorrow?',
      'Find published office hours for Professor Rao tomorrow.',
      'I want to meet Professor Rao tomorrow.',
    ],
  },
  {
    family: 'faculty-anil-tomorrow',
    intent: 'find_faculty_office_hours',
    status: 'answered',
    filters: { faculty_id: 'faculty-rao-anil', date: '2026-11-05' },
    results: ['faculty-rao-anil'],
    questions: [
      'Dr. Anil Rao office hours tomorrow?',
      'When can I meet Anil Rao tomorrow?',
      'Show Anil Rao office hours tomorrow.',
      'Find published office hours for Anil Rao tomorrow.',
      'I want to meet Anil Rao tomorrow.',
      'What are Anil Rao office hours tomorrow?',
    ],
  },
  {
    family: 'faculty-nair-exception',
    intent: 'find_faculty_office_hours',
    status: 'answered',
    filters: { faculty_id: 'faculty-nair', date: '2026-11-05' },
    results: ['faculty-nair'],
    questions: [
      'Dr. Priya Nair office hours tomorrow?',
      'When can I meet Priya Nair tomorrow?',
      'Show Priya Nair office hours tomorrow.',
      'Find published office hours for Priya Nair tomorrow.',
      'I want to meet Priya Nair tomorrow.',
      'What are Priya Nair office hours tomorrow?',
    ],
  },
  {
    family: 'unsupported-services',
    intent: null,
    status: 'unsupported',
    filters: {},
    results: null,
    questions: [
      'What is the weather tomorrow?',
      'Reserve a classroom for me.',
      'Write my assignment for me.',
      'Which placement applications are open?',
      'Send a notification to my class.',
      'What is the canteen menu?',
    ],
  },
];
const lexicon: [string, string, unknown][] = [
  ['AI', 'topic', 'ai'],
  ['workshops', 'event_type', 'workshop'],
  ['workshop', 'event_type', 'workshop'],
  ['design', 'topic', 'design'],
  ['free', 'cost_constraint', 0],
  ['this week', 'date', { start: '2026-11-02', end: '2026-11-09' }],
  ['Friday', 'date', '2026-11-06'],
  ['tomorrow', 'date', '2026-11-05'],
  ['today', 'date', '2026-11-04'],
  ['B Block', 'building', 'b'],
  ['A Block', 'building', 'a'],
  ['2 to 3 PM', 'time_interval', { start: '14:00', end: '15:00' }],
  ['Professor Rao', 'faculty', { candidates: ['faculty-rao-anil', 'faculty-rao-kavita'] }],
  ['Anil Rao', 'faculty', 'faculty-rao-anil'],
  ['Priya Nair', 'faculty', 'faculty-nair'],
];
let index = 0;
const rows = groups.flatMap((g) =>
  g.questions.map((text) => {
    const entities: {
      start: number;
      end: number;
      text: string;
      type: string;
      normalized: unknown;
    }[] = [];
    for (const [surface, type, normalized] of lexicon) {
      const regex = new RegExp(
        '\\b' + surface.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b',
        'gi',
      );
      for (const match of text.matchAll(regex)) {
        const start = match.index!;
        const end = start + match[0].length;
        if (!entities.some((e) => start < e.end && end > e.start))
          entities.push({ start, end, text: match[0], type, normalized });
      }
    }
    const example = {
      id: `synthetic-${String(++index).padStart(3, '0')}`,
      provenance: 'Agent-authored synthetic draft; no real student data',
      annotation_status: 'draft_needs_independent_review',
      annotation_version: '0.1-draft',
      language: 'en',
      text,
      intent: g.intent,
      supported: !!g.intent,
      entities: entities.sort((a, b) => a.start - b.start),
      expected_interpretation: {
        intent: g.intent,
        explicit_filters: g.filters,
        missing_fields: g.missing || [],
        expected_status: g.status,
      },
      profile_context: { department_id: 'aiml', year: 2, section: 'B' },
      reference_clock: '2026-11-04T10:00:00+05:30',
      campus_timezone: 'Asia/Kolkata',
      paraphrase_family_id: g.family,
      conversation_group_id: null,
      split: 'unassigned',
      seed_version: 'frontend-demo-v1',
      expected_result_ids: g.results,
      expected_intervals:
        g.family === 'faculty-anil-tomorrow'
          ? [{ start: '2026-11-05T14:00:00+05:30', end: '2026-11-05T16:00:00+05:30' }]
          : g.family === 'faculty-nair-exception'
            ? [{ start: '2026-11-05T15:00:00+05:30', end: '2026-11-05T16:00:00+05:30' }]
            : [],
      assumptions: [
        'Dates use the fixed campus clock.',
        'Demo records are fictional.',
        'Eligibility is separate from topical relevance.',
      ],
    };
    for (const entity of entities)
      if (text.slice(entity.start, entity.end) !== entity.text) throw new Error('Invalid span');
    return example;
  }),
);
if (rows.length !== 60) throw new Error('Expected 60 pilot drafts');
const dir = fileURLToPath(new URL('../../data/annotations/', import.meta.url));
await mkdir(dir, { recursive: true });
await writeFile(
  dir + 'pilot.synthetic.jsonl',
  rows.map((x) => JSON.stringify(x)).join('\n') + '\n',
);
const dialogues = [
  {
    id: 'dialogue-events-friday',
    turns: [
      {
        text: 'Any workshops this week?',
        expected: {
          intent: 'find_events',
          event_type: 'workshop',
          date_range: ['2026-11-02', '2026-11-09'],
        },
      },
      {
        text: 'Only Friday',
        expected: { intent: 'find_events', event_type: 'workshop', date: '2026-11-06' },
      },
    ],
  },
  {
    id: 'dialogue-faculty-clarify',
    turns: [
      {
        text: 'Professor Rao office hours tomorrow?',
        expected: {
          status: 'clarification_required',
          field: 'faculty_id',
          candidates: ['faculty-rao-anil', 'faculty-rao-kavita'],
        },
      },
      {
        text: 'Anil Rao',
        expected: { faculty_id: 'faculty-rao-anil', date: '2026-11-05', status: 'answered' },
      },
    ],
  },
  {
    id: 'dialogue-room-interval',
    turns: [
      {
        text: 'Room in B Block?',
        expected: { status: 'clarification_required', missing: ['interval'] },
      },
      {
        text: 'Today from 2 to 3 PM',
        expected: {
          building_id: 'b',
          result_ids: ['room-b204'],
          starts_at: '2026-11-04T14:00:00+05:30',
          ends_at: '2026-11-04T15:00:00+05:30',
        },
      },
    ],
  },
  {
    id: 'dialogue-domain-switch',
    turns: [
      {
        text: 'Any free workshops this week?',
        expected: { intent: 'find_events', free: true, event_type: 'workshop' },
      },
      {
        text: 'Professor Rao office hours tomorrow?',
        expected: {
          intent: 'find_faculty_office_hours',
          removed_filters: ['free', 'event_type'],
          status: 'clarification_required',
        },
      },
    ],
  },
  {
    id: 'dialogue-clear-year',
    turns: [
      { text: 'Workshops for second years', expected: { year: 2, origin: 'explicit_question' } },
      {
        text: 'Update the search without this filter.',
        context_overrides: { year: null },
        expected: { year: null, origin: 'override', permanent_profile_year: 2 },
      },
    ],
  },
  {
    id: 'dialogue-office-exception',
    turns: [
      {
        text: 'Priya Nair office hours tomorrow?',
        expected: {
          faculty_id: 'faculty-nair',
          meeting_interval: ['2026-11-05T15:00:00+05:30', '2026-11-05T16:00:00+05:30'],
          exception: 'replacement',
        },
      },
    ],
  },
];
await writeFile(
  dir + 'dialogues.synthetic.json',
  JSON.stringify(
    {
      provenance: 'Synthetic draft, not independently reviewed or frozen',
      reference_clock: '2026-11-04T10:00:00+05:30',
      seed_version: 'frontend-demo-v1',
      split: 'unassigned',
      dialogues,
    },
    null,
    2,
  ) + '\n',
);
process.stdout.write(
  'Wrote 60 synthetic annotation drafts and 6 dialogue drafts; all require independent review.\n',
);
