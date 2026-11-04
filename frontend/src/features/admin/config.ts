import type { Resource } from '../../api/schemas';
export type OptionSource =
  'departments' | 'buildings' | 'topics' | 'facilities' | 'years' | Resource | 'canonical';
export type Field = {
  key: string;
  label: string;
  type:
    | 'text'
    | 'textarea'
    | 'email'
    | 'number'
    | 'datetime'
    | 'date'
    | 'time'
    | 'select'
    | 'multi'
    | 'boolean'
    | 'list'
    | 'opening';
  required?: boolean;
  nullable?: boolean;
  options?: string[];
  source?: OptionSource;
  min?: number;
  max?: number;
  hint?: string;
};
export const adminConfig: Record<
  Resource,
  { title: string; singular: string; description: string; fields: Field[] }
> = {
  events: {
    title: 'Events',
    singular: 'event',
    description: 'Give students something to look forward to.',
    fields: [
      { key: 'title', label: 'Event title', type: 'text', required: true },
      { key: 'description', label: 'Description', type: 'textarea', required: true },
      {
        key: 'event_type',
        label: 'Event type',
        type: 'select',
        options: ['workshop', 'talk', 'meetup', 'hackathon', 'seminar', 'other'],
      },
      { key: 'topic_ids', label: 'Topics', type: 'multi', source: 'topics' },
      { key: 'venue', label: 'Venue', type: 'text', required: true },
      { key: 'starts_at', label: 'Starts', type: 'datetime', required: true },
      { key: 'ends_at', label: 'Ends', type: 'datetime', required: true },
      {
        key: 'cost_minor',
        label: 'Cost in minor units (paise)',
        type: 'number',
        min: 0,
        nullable: true,
        hint: '100 paise = ₹1. Enter 0 for free; leave blank if unknown.',
      },
      { key: 'currency', label: 'Currency', type: 'text', required: true, max: 3 },
      {
        key: 'registration_deadline',
        label: 'Registration deadline',
        type: 'datetime',
        nullable: true,
      },
      {
        key: 'eligibility_mode',
        label: 'Eligibility',
        type: 'select',
        options: ['unknown', 'all_students', 'restricted'],
      },
      {
        key: 'allowed_department_ids',
        label: 'Eligible departments',
        type: 'multi',
        source: 'departments',
        hint: 'Used only for restricted eligibility. An empty selection imposes no department restriction.',
      },
      {
        key: 'allowed_years',
        label: 'Eligible years',
        type: 'multi',
        source: 'years',
        hint: 'Used only for restricted eligibility. An empty selection imposes no year restriction.',
      },
    ],
  },
  rooms: {
    title: 'Rooms',
    singular: 'room',
    description: 'Maintain room details, opening hours, and timetable coverage.',
    fields: [
      { key: 'code', label: 'Room code', type: 'text', required: true },
      {
        key: 'building_id',
        label: 'Building',
        type: 'select',
        source: 'buildings',
        required: true,
      },
      { key: 'capacity', label: 'Seating capacity', type: 'number', min: 1, required: true },
      { key: 'facility_ids', label: 'Facilities', type: 'multi', source: 'facilities' },
      {
        key: 'opening_hours',
        label: 'Weekly opening hours',
        type: 'opening',
        hint: 'All times are campus local. Unchecked days are closed.',
      },
      {
        key: 'coverage_start',
        label: 'Timetable coverage starts',
        type: 'datetime',
        nullable: true,
      },
      { key: 'coverage_end', label: 'Timetable coverage ends', type: 'datetime', nullable: true },
      {
        key: 'coverage_complete',
        label: 'Timetable is complete for this interval',
        type: 'boolean',
        hint: 'Confirm only when all scheduled bookings for this interval are recorded.',
      },
    ],
  },
  bookings: {
    title: 'Bookings',
    singular: 'booking',
    description: 'Record scheduled use. Students cannot reserve rooms.',
    fields: [
      { key: 'room_id', label: 'Room', type: 'select', source: 'rooms', required: true },
      { key: 'purpose', label: 'Purpose', type: 'text', required: true },
      { key: 'starts_at', label: 'First start', type: 'datetime', required: true },
      { key: 'ends_at', label: 'First end', type: 'datetime', required: true },
      { key: 'recurrence', label: 'Repeat', type: 'select', options: ['none', 'weekly'] },
      {
        key: 'recurrence_until',
        label: 'Repeat through',
        type: 'date',
        nullable: true,
        hint: 'Required for weekly bookings. Repeats on the weekday of the first booking.',
      },
    ],
  },
  'booking-exceptions': {
    title: 'Booking exceptions',
    singular: 'booking exception',
    description: 'Cancel or replace one occurrence of a recurring booking.',
    fields: [
      {
        key: 'booking_id',
        label: 'Parent booking',
        type: 'select',
        source: 'bookings',
        required: true,
      },
      ...exceptionFields(),
    ],
  },
  'room-closures': {
    title: 'Room closures',
    singular: 'room closure',
    description: 'Closures take priority over all scheduled bookings.',
    fields: [
      { key: 'room_id', label: 'Room', type: 'select', source: 'rooms', required: true },
      { key: 'reason', label: 'Reason for closure', type: 'textarea', required: true },
      { key: 'starts_at', label: 'Closure starts', type: 'datetime', required: true },
      { key: 'ends_at', label: 'Closure ends', type: 'datetime', required: true },
    ],
  },
  faculty: {
    title: 'Faculty',
    singular: 'faculty member',
    description: 'Publish approved faculty details and recognized names.',
    fields: [
      { key: 'name', label: 'Full name', type: 'text', required: true },
      {
        key: 'department_id',
        label: 'Department',
        type: 'select',
        source: 'departments',
        required: true,
      },
      { key: 'location', label: 'Office location', type: 'text' },
      {
        key: 'email',
        label: 'Published email',
        type: 'email',
        hint: 'Only include contact information approved for publication.',
      },
      {
        key: 'aliases',
        label: 'Alternative names',
        type: 'list',
        hint: 'Separate names with commas. Shared names may require clarification.',
      },
    ],
  },
  'office-hours': {
    title: 'Office hours',
    singular: 'office-hour rule',
    description: 'Published weekly meeting hours, bounded by effective dates.',
    fields: [
      {
        key: 'faculty_id',
        label: 'Faculty member',
        type: 'select',
        source: 'faculty',
        required: true,
      },
      { key: 'location', label: 'Meeting location', type: 'text', required: true },
      {
        key: 'weekday',
        label: 'Day of week',
        type: 'select',
        options: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
      },
      { key: 'start_time', label: 'Start time', type: 'time', required: true },
      { key: 'end_time', label: 'End time', type: 'time', required: true },
      { key: 'effective_from', label: 'Effective from', type: 'date', required: true },
      { key: 'effective_until', label: 'Effective through', type: 'date', required: true },
    ],
  },
  'office-hour-exceptions': {
    title: 'Office-hour exceptions',
    singular: 'office-hour exception',
    description: 'Record a dated cancellation or replacement meeting time.',
    fields: [
      {
        key: 'office_hour_id',
        label: 'Parent office-hour rule',
        type: 'select',
        source: 'office-hours',
        required: true,
      },
      ...exceptionFields(),
    ],
  },
  aliases: {
    title: 'Aliases',
    singular: 'alias',
    description: 'Connect campus abbreviations and alternate names to canonical records.',
    fields: [
      {
        key: 'entity_type',
        label: 'Record type',
        type: 'select',
        options: ['department', 'building', 'topic', 'room', 'faculty'],
      },
      {
        key: 'canonical_id',
        label: 'Canonical record',
        type: 'select',
        source: 'canonical',
        required: true,
      },
      { key: 'alias', label: 'Alternative name or abbreviation', type: 'text', required: true },
    ],
  },
};
function exceptionFields(): Field[] {
  return [
    { key: 'occurrence_date', label: 'Original occurrence date', type: 'date', required: true },
    { key: 'action', label: 'Change', type: 'select', options: ['cancel', 'replace'] },
    { key: 'replacement_start', label: 'Replacement starts', type: 'datetime', nullable: true },
    { key: 'replacement_end', label: 'Replacement ends', type: 'datetime', nullable: true },
    { key: 'note', label: 'Note for students', type: 'textarea' },
  ];
}
export const commonFields: Field[] = [
  {
    key: 'source_label',
    label: 'Source label',
    type: 'text',
    required: true,
    hint: 'For example, Department notice or Published semester timetable.',
  },
  {
    key: 'source_url',
    label: 'Source URL',
    type: 'text',
    nullable: true,
    hint: 'Optional http or https link to the original record.',
  },
];
export function recordTitle(record: Record<string, unknown>) {
  return String(
    record.title ||
      record.name ||
      record.code ||
      record.purpose ||
      record.alias ||
      record.reason ||
      (record.faculty_id
        ? 'Office hours · ' + record.faculty_id
        : record.occurrence_date
          ? 'Exception · ' + record.occurrence_date
          : record.id),
  );
}
export function newRecord(resource: Resource, timezone: string): Record<string, unknown> {
  const common = {
    status: resource === 'events' ? 'draft' : 'active',
    source_label: '',
    source_url: null,
    version: 1,
  };
  const defaults: Record<Resource, Record<string, unknown>> = {
    events: {
      title: '',
      description: '',
      event_type: 'workshop',
      topic_ids: [],
      venue: '',
      starts_at: '',
      ends_at: '',
      cost_minor: null,
      currency: 'INR',
      registration_deadline: null,
      eligibility_mode: 'unknown',
      allowed_department_ids: [],
      allowed_years: [],
    },
    rooms: {
      code: '',
      building_id: '',
      capacity: 30,
      facility_ids: [],
      opening_hours: [],
      coverage_start: null,
      coverage_end: null,
      coverage_complete: false,
    },
    bookings: {
      room_id: '',
      purpose: '',
      starts_at: '',
      ends_at: '',
      recurrence: 'none',
      recurrence_until: null,
    },
    'booking-exceptions': {
      booking_id: '',
      occurrence_date: '',
      action: 'cancel',
      replacement_start: null,
      replacement_end: null,
      note: '',
    },
    'room-closures': { room_id: '', reason: '', starts_at: '', ends_at: '' },
    faculty: { name: '', department_id: '', location: '', email: '', aliases: [] },
    'office-hours': {
      faculty_id: '',
      location: '',
      weekday: 1,
      start_time: '14:00',
      end_time: '16:00',
      effective_from: '',
      effective_until: '',
      timezone,
    },
    'office-hour-exceptions': {
      office_hour_id: '',
      occurrence_date: '',
      action: 'cancel',
      replacement_start: null,
      replacement_end: null,
      note: '',
    },
    aliases: { entity_type: 'department', canonical_id: '', alias: '' },
  };
  return { ...common, ...defaults[resource] };
}
