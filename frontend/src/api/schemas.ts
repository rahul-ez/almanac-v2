import { z } from 'zod';

export const id = z.string().min(1);
export const instant = z.iso.datetime({ offset: true });
const nullableText = z.string().nullable();
export const roleSchema = z.enum(['student', 'admin']);
export const userSchema = z.object({ id, name: z.string(), email: z.union([z.email(),z.literal('')]), role: roleSchema });
export const profileSchema = z.object({
  department_id: id.nullable(),
  year: z.number().int().min(1).max(6).nullable(),
  section: nullableText,
  interests: z.array(z.string()),
});
const option = z.object({ id, label: z.string() });
export const referenceSchema = z.object({
  departments: z.array(option),
  buildings: z.array(option),
  topics: z.array(option),
  facilities: z.array(option),
  supported_years: z.array(z.number().int()),
  campus_timezone: z.string(),
});
const base = z.object({
  id,
  version: z.number().int().positive(),
  source_label: z.string().min(1),
  source_url: z.url().nullable(),
  updated_at: instant,
  status: z.enum(['draft', 'published', 'active', 'cancelled', 'archived']),
});
export const eventRecordSchema = base.extend({
  title: z.string().min(1).max(200),
  description: z.string().max(4000),
  event_type: z.string().min(1),
  topic_ids: z.array(id),
  venue: z.string().min(1),
  starts_at: instant,
  ends_at: instant,
  cost_minor: z.number().int().min(0).nullable(),
  currency: z.string().length(3),
  eligibility_mode: z.enum(['unknown', 'all_students', 'restricted']),
  allowed_department_ids: z.array(id),
  allowed_years: z.array(z.number().int().min(1).max(6)),
  registration_deadline: instant.nullable(),
});
export const openingHourSchema = z.object({
  weekday: z.number().int().min(0).max(6),
  start: z.string().regex(/^\d{2}:\d{2}$/),
  end: z.string().regex(/^\d{2}:\d{2}$/),
});
export const roomRecordSchema = base.extend({
  code: z.string().min(1),
  building_id: id,
  capacity: z.number().int().positive(),
  facility_ids: z.array(id),
  opening_hours: z.array(openingHourSchema),
  opening_hours_unknown: z.boolean().optional(),
  coverage_start: instant.nullable(),
  coverage_end: instant.nullable(),
  coverage_complete: z.boolean(),
});
export const facultyRecordSchema = base.extend({
  name: z.string().min(1),
  department_id: id,
  location: z.string(),
  email: z.union([z.email(), z.literal('')]),
  aliases: z.array(z.string()),
  office_hours_coverage_start: z.iso.date().nullable().optional(),
  office_hours_coverage_end: z.iso.date().nullable().optional(),
  office_hours_complete: z.boolean().optional(),
});
const interval = { starts_at: instant, ends_at: instant };
export const bookingRecordSchema = base.extend({
  room_id: id,
  purpose: z.string().min(1),
  ...interval,
  recurrence: z.enum(['none', 'weekly']),
  recurrence_until: z.iso.date().nullable(),
});
export const closureRecordSchema = base.extend({
  room_id: id,
  reason: z.string().min(1),
  ...interval,
});
export const officeHourRecordSchema = base.extend({
  faculty_id: id,
  location: z.string().min(1),
  weekday: z.number().int().min(0).max(6),
  start_time: z.string().regex(/^\d{2}:\d{2}$/),
  end_time: z.string().regex(/^\d{2}:\d{2}$/),
  effective_from: z.iso.date(),
  effective_until: z.iso.date(),
  timezone: z.string(),
});
const exception = base.extend({
  occurrence_date: z.iso.date(),
  action: z.enum(['cancel', 'replace']),
  replacement_start: instant.nullable(),
  replacement_end: instant.nullable(),
  note: z.string(),
});
export const bookingExceptionSchema = exception.extend({ booking_id: id });
export const officeHourExceptionSchema = exception.extend({ office_hour_id: id });
export const aliasRecordSchema = base.extend({
  entity_type: z.enum(['department', 'building', 'topic', 'room', 'faculty']),
  canonical_id: id,
  alias: z.string().min(1),
});
export const resourceSchemas = {
  events: eventRecordSchema,
  rooms: roomRecordSchema,
  bookings: bookingRecordSchema,
  'booking-exceptions': bookingExceptionSchema,
  'room-closures': closureRecordSchema,
  faculty: facultyRecordSchema,
  'office-hours': officeHourRecordSchema,
  'office-hour-exceptions': officeHourExceptionSchema,
  aliases: aliasRecordSchema,
};
export const resourceNames = Object.keys(resourceSchemas) as Resource[];
export type Resource = keyof typeof resourceSchemas;
export type DomainRecord = z.infer<(typeof resourceSchemas)[Resource]>;
export type EventRecord = z.infer<typeof eventRecordSchema>;
export type RoomRecord = z.infer<typeof roomRecordSchema>;
export type FacultyRecord = z.infer<typeof facultyRecordSchema>;
export type BookingRecord = z.infer<typeof bookingRecordSchema>;
export type OfficeHourRecord = z.infer<typeof officeHourRecordSchema>;
export type Profile = z.infer<typeof profileSchema>;
export type User = z.infer<typeof userSchema>;
export type ReferenceData = z.infer<typeof referenceSchema>;

const cardBase = z.object({
  record_id: id,
  title: z.string(),
  source_label: z.string(),
  source_url: z.url().nullable(),
  record_updated_at: instant,
  saved: z.boolean(),
  record_status: z.enum(['draft', 'published', 'active', 'cancelled', 'archived']),
});
export const eventCardSchema = cardBase.extend({
  kind: z.literal('event'),
  description: z.string(),
  starts_at: instant,
  ends_at: instant,
  venue: z.string(),
  event_type: z.string(),
  topics: z.array(z.string()),
  cost_minor: z.number().int().min(0).nullable(),
  currency: z.string(),
  eligibility: z.enum(['eligible', 'ineligible', 'unknown']),
  eligibility_basis: z.string(),
  registration_deadline: instant.nullable(),
});
export const roomCardSchema = cardBase.extend({
  kind: z.literal('room'),
  building: z.string(),
  capacity: z.number().int().positive(),
  facilities: z.array(z.string()),
  requested_interval: z.object(interval).nullable(),
  schedule_coverage: z.enum(['complete', 'partial', 'unknown']),
  availability_basis: z.literal('scheduled_bookings'),
});
export const officeHourCardSchema = cardBase.extend({
  kind: z.literal('faculty'),
  faculty_name: z.string(),
  department: z.string(),
  location: z.string(),
  meeting_interval: z.object(interval).nullable(),
  exception_note: nullableText,
});
export const cardSchema = z.discriminatedUnion('kind', [
  eventCardSchema,
  roomCardSchema,
  officeHourCardSchema,
]);
export type Card = z.infer<typeof cardSchema>;
export type Kind = Card['kind'];
export const intentSchema = z.enum([
  'find_events',
  'find_available_rooms',
  'find_faculty_office_hours',
]);
export const contextValue = z.union([
  z.string(),
  z.number(),
  z.boolean(),
  z.array(z.string()),
  z.null(),
]);
export const queryFiltersSchema = z.record(z.string(), contextValue);
export const clarificationSchema = z.object({
  id,
  field: z.string(),
  prompt: z.string(),
  options: z.array(option),
});
export const queryRequestSchema = z.object({
  conversation_version: z.number().int().positive().optional(),
  text: z.string().max(2000),
  conversation_id: id.nullable(),
  client_request_id: id,
  context_overrides: queryFiltersSchema,
  clarification: z.object({ id, option_id: id.optional() }).nullable(),
});
export const answerSchema = z.object({
  conversation_id: id,
  turn_id: id,
  request_id: id,
  status: z.enum([
    'answered',
    'no_results',
    'clarification_required',
    'unsupported',
    'information_unavailable',
  ]),
  intent: intentSchema.nullable(),
  message: z.string(),
  interpreted_query: z.object({ intent: intentSchema.nullable(), filters: queryFiltersSchema }),
  applied_context: z.record(
    z.string(),
    z.object({
      value: contextValue,
      origin: z.enum(['explicit_question', 'override', 'profile', 'prior_turn', 'default']),
    }),
  ),
  results: z.array(cardSchema),
  clarification: clarificationSchema.nullable(),
  answered_at: instant,
  campus_timezone: z.string(),
  warnings: z.array(z.string()),
  data_coverage: z.object({
    status: z.enum(['complete', 'partial', 'unknown']),
    message: z.string(),
  }),
  next_cursor: z.string().nullable(),
});
export type QueryRequest = z.infer<typeof queryRequestSchema>;
export type Answer = z.infer<typeof answerSchema>;
export const turnSchema = z.object({ id, question: z.string(), answer: answerSchema });
export const conversationSummarySchema = z.object({
  version:z.number().int().positive().optional(),
  state_expires_at:instant.nullable().optional(),
  id,
  title: z.string(),
  updated_at: instant,
  turn_count: z.number().int(),
});
export const conversationSchema = conversationSummarySchema.extend({ turns: z.array(turnSchema),active_clarification:clarificationSchema.nullable().optional() });
export type Conversation = z.infer<typeof conversationSchema>;
export const savedSchema = z.object({
  kind: z.enum(['event', 'room', 'faculty']),
  record_id: id,
  saved_at: instant,
  record: cardSchema.nullable(),
});
export type SavedItem = z.infer<typeof savedSchema>;
export const errorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    field_errors: z.record(z.string(), z.array(z.string())),
    request_id: z.string(),
  }),
});
export const pageSchema = <T extends z.ZodType>(schema: T) =>
  z.object({ items: z.array(schema), next_cursor: z.string().nullable() });
