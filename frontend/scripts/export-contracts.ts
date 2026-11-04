import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { z } from 'zod';
import * as s from '../src/api/schemas';
import {
  answerFixtures,
  errorFixtures,
  historicalFixture,
  savedFixture,
} from '../src/api/fixtures';

const root = fileURLToPath(new URL('../../', import.meta.url));
const check = process.argv.includes('--check');
const schemas = {
  User: s.userSchema,
  Profile: s.profileSchema,
  ReferenceData: s.referenceSchema,
  AssistantRequest: s.queryRequestSchema,
  AssistantResponse: s.answerSchema,
  Card: s.cardSchema,
  EventCard: s.eventCardSchema,
  RoomCard: s.roomCardSchema,
  FacultyCard: s.officeHourCardSchema,
  Conversation: s.conversationSchema,
  ConversationSummary: s.conversationSummarySchema,
  SavedItem: s.savedSchema,
  Error: s.errorSchema,
  Event: s.eventRecordSchema,
  Room: s.roomRecordSchema,
  Booking: s.bookingRecordSchema,
  BookingException: s.bookingExceptionSchema,
  RoomClosure: s.closureRecordSchema,
  Faculty: s.facultyRecordSchema,
  OfficeHour: s.officeHourRecordSchema,
  OfficeHourException: s.officeHourExceptionSchema,
  Alias: s.aliasRecordSchema,
};
const ref = (name: string) => ({ $ref: '#/components/schemas/' + name });
const page = (name: string) => ({
  type: 'object',
  required: ['items', 'next_cursor'],
  properties: {
    items: { type: 'array', items: ref(name) },
    next_cursor: { type: ['string', 'null'] },
  },
});
const parameter = (name: string, location = 'path') => ({
  name,
  in: location,
  required: location === 'path',
  schema: { type: 'string' },
});
const paths: Record<string, Record<string, unknown>> = {};
function operation(
  url: string,
  method: string,
  schema: object | null,
  options: {
    body?: object;
    auth?: boolean;
    status?: number;
    parameters?: object[];
    description?: string;
  } = {},
) {
  const status = options.status || 200;
  const mutating = !['get', 'head'].includes(method);
  const errors = Object.fromEntries(
    [401, 403, 404, 409, 422, 429, 500, 503].map((code) => [
      String(code),
      {
        description: 'Structured API error',
        content: { 'application/json': { schema: ref('Error') } },
      },
    ]),
  );
  const parameters = [...url.matchAll(/\{([^}]+)\}/g)].map((m) => parameter(m[1]));
  if (mutating)
    parameters.push({
      name: 'X-CSRF-Token',
      in: 'header',
      required: true,
      schema: { type: 'string' },
    });
  paths[url] ||= {};
  paths[url][method] = {
    summary: `${method.toUpperCase()} ${url}`,
    description: options.description,
    security: options.auth === false ? [] : [{ cookieAuth: [] }],
    parameters: [...parameters, ...(options.parameters || [])],
    ...(options.body
      ? {
          requestBody: {
            required: true,
            content: { 'application/json': { schema: options.body } },
          },
        }
      : {}),
    responses: {
      ...errors,
      [String(status)]: schema
        ? { description: 'Successful response', content: { 'application/json': { schema } } }
        : { description: 'Successful response, no body' },
    },
  };
}
const listParams = [
  { name: 'limit', in: 'query', schema: { type: 'integer', minimum: 1, maximum: 50, default: 12 } },
  parameter('cursor', 'query'),
];
operation(
  '/auth/csrf',
  'get',
  { type: 'object', required: ['csrf_token'], properties: { csrf_token: { type: 'string' } } },
  { auth: false },
);
operation('/auth/login', 'post', ref('User'), {
  auth: false,
  body: {
    type: 'object',
    required: ['email', 'password'],
    properties: { email: { type: 'string', format: 'email' }, password: { type: 'string' } },
  },
});
operation('/auth/logout', 'post', null, { status: 204 });
operation('/auth/me', 'get', ref('User'));
operation('/me/profile', 'get', ref('Profile'));
operation('/me/profile', 'patch', ref('Profile'), { body: ref('Profile') });
operation('/reference-data', 'get', ref('ReferenceData'));
operation('/assistant/query', 'post', ref('AssistantResponse'), {
  body: ref('AssistantRequest'),
  description:
    'Valid NLP outcomes return 200. Deduplicate by authenticated user and client_request_id; a changed payload for a reused ID returns 409. Chat next_cursor stays null until retrieval is defined.',
});
operation('/conversations', 'get', page('ConversationSummary'), { parameters: listParams });
operation('/conversations/{id}', 'get', ref('Conversation'));
operation('/conversations/{id}', 'delete', null, { status: 204 });
operation('/me/saved', 'get', page('SavedItem'), { parameters: listParams });
operation('/me/saved/{kind}/{id}', 'put', null, { status: 204 });
operation('/me/saved/{kind}/{id}', 'delete', null, { status: 204 });
operation('/events', 'get', page('EventCard'), { parameters: listParams });
operation('/events/{id}', 'get', ref('EventCard'));
operation('/rooms/{id}', 'get', ref('RoomCard'));
operation('/faculty/{id}', 'get', ref('FacultyCard'));
operation('/faculty/{id}/office-hours', 'get', page('FacultyCard'), { parameters: listParams });
for (const [resource, name] of Object.entries({
  events: 'Event',
  rooms: 'Room',
  bookings: 'Booking',
  'booking-exceptions': 'BookingException',
  'room-closures': 'RoomClosure',
  faculty: 'Faculty',
  'office-hours': 'OfficeHour',
  'office-hour-exceptions': 'OfficeHourException',
  aliases: 'Alias',
})) {
  operation(`/admin/${resource}`, 'get', page(name), {
    parameters: [...listParams, parameter('search', 'query')],
  });
  const inputSchema = z.toJSONSchema(
    (s.resourceSchemas[resource as s.Resource] as z.ZodObject<z.ZodRawShape>).omit({
      id: true,
      updated_at: true,
    }),
    { target: 'draft-2020-12' },
  );
  operation(`/admin/${resource}`, 'post', ref(name), { status: 201, body: inputSchema });
  operation(`/admin/${resource}/{id}`, 'get', ref(name));
  operation(`/admin/${resource}/{id}`, 'patch', ref(name), {
    body: inputSchema,
    description: 'Include the current edit version. Stale edits return 409.',
  });
  operation(`/admin/${resource}/{id}`, 'delete', null, {
    status: 204,
    parameters: [{ name: 'If-Match', in: 'header', required: true, schema: { type: 'string' } }],
    description: 'Archives referenced records. If-Match carries the edit version.',
  });
}
for (const endpoint of ['/health/live', '/health/ready'])
  operation(
    endpoint,
    'get',
    { type: 'object', properties: { status: { type: 'string' } }, required: ['status'] },
    { auth: false },
  );
const contract = {
  openapi: '3.1.0',
  info: {
    title: 'Campus Companion API — frontend integration proposal',
    version: '0.1.0',
    description:
      'Generated from frontend runtime schemas. Person B must review and adopt or update this contract before live integration. Instants carry offsets; query execution and eligibility remain server responsibilities.',
  },
  servers: [{ url: '/api/v1' }],
  paths,
  components: {
    securitySchemes: { cookieAuth: { type: 'apiKey', in: 'cookie', name: 'session' } },
    schemas: Object.fromEntries(
      Object.entries(schemas).map(([name, schema]) => [name, z.toJSONSchema(schema)]),
    ),
  },
};
async function output(relative: string, value: unknown) {
  const target = path.join(root, relative);
  const contents = JSON.stringify(value, null, 2) + '\n';
  if (check) {
    if ((await readFile(target, 'utf8')) !== contents)
      throw new Error(`${relative} is out of date. Run npm run contracts:export.`);
  } else {
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, contents);
  }
}
await output('contracts/openapi.json', contract);
for (const [name, value] of Object.entries(answerFixtures)) {
  s.answerSchema.parse(value);
  await output(`contracts/fixtures/${name}.json`, value);
}
for (const [name, value] of Object.entries(errorFixtures)) {
  s.errorSchema.parse(value.body);
  await output(`contracts/fixtures/${name}.json`, value);
}
s.savedSchema.parse(savedFixture);
s.conversationSchema.parse(historicalFixture);
await output('contracts/fixtures/changed-cancelled-saved-item.json', savedFixture);
await output('contracts/fixtures/historical-snapshot.json', historicalFixture);
process.stdout.write(
  check
    ? 'Contract and all 15 fixtures are current and schema-valid.\n'
    : 'Exported contract and 15 validated fixtures.\n',
);
