import type {
  DomainRecord,
  EventRecord,
  FacultyRecord,
  Profile,
  ReferenceData,
  Resource,
  RoomRecord,
  User,
} from './schemas';

export const DEMO_NOW = '2026-11-04T10:00:00+05:30';
export const CAMPUS_ZONE = 'Asia/Kolkata';
export const DEMO_PASSWORD = 'CampusDemo!26';
export const demoUsers: User[] = [
  { id: 'student-aarav', name: 'Aarav Sharma', email: 'student@campus.demo', role: 'student' },
  { id: 'student-ananya', name: 'Ananya Iyer', email: 'ananya@campus.demo', role: 'student' },
  { id: 'admin-meera', name: 'Meera Nair', email: 'admin@campus.demo', role: 'admin' },
];
export const referenceData: ReferenceData = {
  departments: [
    { id: 'aiml', label: 'AI & Machine Learning' },
    { id: 'cse', label: 'Computer Science' },
    { id: 'ece', label: 'Electronics & Communication' },
    { id: 'design', label: 'Design' },
  ],
  buildings: [
    { id: 'a', label: 'A Block' },
    { id: 'b', label: 'B Block' },
    { id: 'library', label: 'Central Library' },
  ],
  topics: [
    { id: 'ai', label: 'Artificial intelligence' },
    { id: 'ml', label: 'Machine learning' },
    { id: 'design', label: 'Design' },
    { id: 'coding', label: 'Programming' },
    { id: 'community', label: 'Campus life' },
  ],
  facilities: [
    { id: 'projector', label: 'Projector' },
    { id: 'whiteboard', label: 'Whiteboard' },
    { id: 'ac', label: 'Air conditioning' },
    { id: 'computers', label: 'Computers' },
  ],
  supported_years: [1, 2, 3, 4],
  campus_timezone: CAMPUS_ZONE,
};
export const defaultProfile: Profile = {
  department_id: 'aiml',
  year: 2,
  section: 'B',
  interests: ['ai', 'coding'],
};
const base = {
  version: 1,
  updated_at: '2026-11-03T09:00:00+05:30',
  source_label: 'Demo campus records',
  source_url: null,
  status: 'active' as const,
};
const event = {
  ...base,
  status: 'published' as const,
  event_type: 'workshop',
  currency: 'INR',
  eligibility_mode: 'all_students' as const,
  allowed_department_ids: [],
  allowed_years: [],
  registration_deadline: '2026-11-05T18:00:00+05:30',
  cost_minor: 0,
};
export const seedEvents: EventRecord[] = [
  {
    ...event,
    id: 'event-ai',
    title: 'Build something with AI',
    description:
      'An afternoon of small ideas and hands-on machine learning. Bring your laptop; leave with a working project.',
    topic_ids: ['ai', 'ml'],
    venue: 'Innovation Lab, B Block',
    starts_at: '2026-11-06T14:00:00+05:30',
    ends_at: '2026-11-06T17:00:00+05:30',
  },
  {
    ...event,
    id: 'event-design',
    title: 'Design beyond the screen',
    description:
      'Explore the spaces, systems, and everyday interactions that make a campus feel like home.',
    topic_ids: ['design'],
    venue: 'Studio 02, A Block',
    starts_at: '2026-11-05T11:00:00+05:30',
    ends_at: '2026-11-05T13:00:00+05:30',
    event_type: 'talk',
    cost_minor: 15000,
    registration_deadline: null,
  },
  {
    ...event,
    id: 'event-git',
    title: 'Your first open-source contribution',
    description:
      'Find a good first issue, meet a collaborator, and make your first pull request. All experience levels welcome.',
    topic_ids: ['coding', 'community'],
    venue: 'Seminar Hall, Central Library',
    starts_at: '2026-11-07T10:00:00+05:30',
    ends_at: '2026-11-07T12:30:00+05:30',
  },
  {
    ...event,
    id: 'event-robotics',
    title: 'Robotics, from the ground up',
    description: 'A practical introduction to sensors, motors, and your first autonomous robot.',
    topic_ids: ['coding'],
    venue: 'Electronics Lab, A Block',
    starts_at: '2026-11-09T10:00:00+05:30',
    ends_at: '2026-11-09T13:00:00+05:30',
    eligibility_mode: 'restricted',
    allowed_department_ids: ['ece'],
    allowed_years: [3, 4],
    cost_minor: null,
  },
  {
    ...event,
    id: 'event-meet',
    title: 'The Friday campus exchange',
    description:
      'Share an idea, find your people, and discover what students are making across campus.',
    topic_ids: ['community'],
    venue: 'Courtyard, B Block',
    starts_at: '2026-11-06T16:00:00+05:30',
    ends_at: '2026-11-06T18:00:00+05:30',
    event_type: 'meetup',
    eligibility_mode: 'unknown',
    registration_deadline: null,
  },
  {
    ...event,
    id: 'event-cancelled',
    title: 'Data stories: a visual introduction',
    description: 'This session has been cancelled. The organizer will publish a replacement date.',
    topic_ids: ['design', 'ml'],
    venue: 'B-204, B Block',
    starts_at: '2026-11-08T11:00:00+05:30',
    ends_at: '2026-11-08T13:00:00+05:30',
    status: 'cancelled',
  },
];
export const seedRooms: RoomRecord[] = [
  {
    ...base,
    id: 'room-b204',
    code: 'B-204',
    building_id: 'b',
    capacity: 60,
    facility_ids: ['projector', 'whiteboard', 'ac'],
    opening_hours: [0, 1, 2, 3, 4, 5, 6].map((weekday) => ({
      weekday,
      start: '08:00',
      end: '20:00',
    })),
    coverage_start: '2026-11-01T00:00:00+05:30',
    coverage_end: '2026-12-01T00:00:00+05:30',
    coverage_complete: true,
  },
  {
    ...base,
    id: 'room-b102',
    code: 'B-102',
    building_id: 'b',
    capacity: 35,
    facility_ids: ['projector', 'whiteboard'],
    opening_hours: [1, 2, 3, 4, 5].map((weekday) => ({ weekday, start: '08:00', end: '18:00' })),
    coverage_start: '2026-11-01T00:00:00+05:30',
    coverage_end: '2026-12-01T00:00:00+05:30',
    coverage_complete: true,
  },
  {
    ...base,
    id: 'room-a301',
    code: 'A-301',
    building_id: 'a',
    capacity: 80,
    facility_ids: ['computers', 'projector', 'ac'],
    opening_hours: [{ weekday: 3, start: '08:00', end: '20:00' }],
    coverage_start: null,
    coverage_end: null,
    coverage_complete: false,
  },
];
export const seedFaculty: FacultyRecord[] = [
  {
    ...base,
    id: 'faculty-rao-anil',
    name: 'Dr. Anil Rao',
    department_id: 'aiml',
    location: 'Faculty Wing, B-308',
    email: 'anil.rao@campus.demo',
    aliases: ['Professor Rao', 'Anil Rao'],
  },
  {
    ...base,
    id: 'faculty-rao-kavita',
    name: 'Dr. Kavita Rao',
    department_id: 'cse',
    location: 'Faculty Wing, A-201',
    email: 'kavita.rao@campus.demo',
    aliases: ['Professor Rao', 'Kavita Rao'],
  },
  {
    ...base,
    id: 'faculty-nair',
    name: 'Dr. Priya Nair',
    department_id: 'design',
    location: 'Design Studio, A-104',
    email: '',
    aliases: ['Priya', 'Nair'],
  },
];
export function seedRecords(): Record<Resource, DomainRecord[]> {
  return {
    events: structuredClone(seedEvents),
    rooms: structuredClone(seedRooms),
    faculty: structuredClone(seedFaculty),
    bookings: [
      {
        ...base,
        id: 'booking-ml',
        room_id: 'room-b204',
        purpose: 'Machine learning tutorial',
        starts_at: '2026-11-04T13:00:00+05:30',
        ends_at: '2026-11-04T14:00:00+05:30',
        recurrence: 'weekly',
        recurrence_until: '2026-11-30',
      },
    ],
    'booking-exceptions': [],
    'room-closures': [
      {
        ...base,
        id: 'closure-b102',
        room_id: 'room-b102',
        reason: 'Projector maintenance',
        starts_at: '2026-11-04T14:00:00+05:30',
        ends_at: '2026-11-04T15:00:00+05:30',
      },
    ],
    'office-hours': seedFaculty.map((f, i) => ({
      ...base,
      id: 'hours-' + i,
      faculty_id: f.id,
      location: f.location,
      weekday: 4,
      start_time: '14:00',
      end_time: '16:00',
      effective_from: '2026-11-01',
      effective_until: '2026-11-30',
      timezone: CAMPUS_ZONE,
    })),
    'office-hour-exceptions': [
      {
        ...base,
        id: 'hours-exception',
        office_hour_id: 'hours-2',
        occurrence_date: '2026-11-05',
        action: 'replace',
        replacement_start: '2026-11-05T15:00:00+05:30',
        replacement_end: '2026-11-05T16:00:00+05:30',
        note: 'Starts one hour later this Thursday.',
      },
    ],
    aliases: [
      {
        ...base,
        id: 'alias-aiml',
        entity_type: 'department',
        canonical_id: 'aiml',
        alias: 'AI & ML',
      },
    ],
  };
}
