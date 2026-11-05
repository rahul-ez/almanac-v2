import { z } from 'zod';
import { createHttpTransport, validated, type Transport } from './client';
import * as s from './schemas';
import { createLiveAdapter } from './live';

export const apiMode = import.meta.env.VITE_API_MODE || 'live';
if (!['mock', 'live'].includes(apiMode)) throw new Error('VITE_API_MODE must be mock or live.');
const mockTransport =
  apiMode === 'mock'
    ? import('./mock').then((m) => m.createMockTransport(window.localStorage))
    : null;
const transport: Transport = mockTransport
  ? async (path, init) => (await mockTransport)(path, init)
  : createLiveAdapter(createHttpTransport(import.meta.env.VITE_API_BASE_URL || '/api/v1'));
const json = (method: string, body?: unknown): RequestInit => ({
  method,
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});
const enc = encodeURIComponent;
export function createApi(t: Transport) {
  const get = <T>(path: string, schema: z.ZodType<T>, signal?: AbortSignal) =>
    validated(t, path, schema, { signal });
  return {
    me: () => get('/auth/me', s.userSchema),
    login: (email: string, password: string) =>
      validated(t, '/auth/login', s.userSchema, json('POST', { email, password })),
    logout: () => t('/auth/logout', json('POST')),
    profile: (signal?: AbortSignal) => get('/me/profile', s.profileSchema, signal),
    updateProfile: (profile: s.Profile) =>
      validated(t, '/me/profile', s.profileSchema, json('PATCH', s.profileSchema.parse(profile))),
    reference: (signal?: AbortSignal) => get('/reference-data', s.referenceSchema, signal),
    events: (cursor?: string | null, signal?: AbortSignal) =>
      get(
        '/events?limit=6' + (cursor ? '&cursor=' + enc(cursor) : ''),
        s.pageSchema(s.eventCardSchema),
        signal,
      ),
    query: (request: s.QueryRequest, signal?: AbortSignal) =>
      validated(t, '/assistant/query', s.answerSchema, {
        ...json('POST', s.queryRequestSchema.parse(request)),
        signal,
      }),
    conversations: (cursor?: string | null, signal?: AbortSignal) =>
      get(
        '/conversations?limit=12' + (cursor ? '&cursor=' + enc(cursor) : ''),
        s.pageSchema(s.conversationSummarySchema),
        signal,
      ),
    conversation: (id: string, signal?: AbortSignal) =>
      get('/conversations/' + enc(id), s.conversationSchema, signal),
    deleteConversation: (id: string) => t('/conversations/' + enc(id), json('DELETE')),
    saved: (cursor?: string | null, signal?: AbortSignal) =>
      get(
        '/me/saved?limit=12' + (cursor ? '&cursor=' + enc(cursor) : ''),
        s.pageSchema(s.savedSchema),
        signal,
      ),
    save: (kind: s.Kind, id: string, saved: boolean) =>
      t('/me/saved/' + kind + '/' + enc(id), json(saved ? 'PUT' : 'DELETE')),
    adminList: (resource: s.Resource, search = '', cursor?: string | null, signal?: AbortSignal) =>
      get(
        `/admin/${resource}?limit=12&search=${enc(search)}` +
          (cursor ? '&cursor=' + enc(cursor) : ''),
        s.pageSchema(s.resourceSchemas[resource]),
        signal,
      ),
    adminGet: (resource: s.Resource, id: string, signal?: AbortSignal) =>
      get<s.DomainRecord>(`/admin/${resource}/${enc(id)}`, s.resourceSchemas[resource], signal),
    adminSave: (resource: s.Resource, data: Record<string, unknown>, id?: string) =>
      validated<s.DomainRecord>(
        t,
        `/admin/${resource}` + (id ? '/' + enc(id) : ''),
        s.resourceSchemas[resource],
        json(id ? 'PATCH' : 'POST', data),
      ),
    adminArchive: (resource: s.Resource, id: string, version: number) =>
      t(`/admin/${resource}/${enc(id)}`, {
        ...json('DELETE'),
        headers: { 'If-Match': String(version) },
      }),
    detail: (kind: s.Kind, id: string, signal?: AbortSignal) =>
      get(
        `/${kind === 'event' ? 'events' : kind === 'room' ? 'rooms' : 'faculty'}/${enc(id)}`,
        s.cardSchema,
        signal,
      ),
  };
}
export const api = createApi(transport);
