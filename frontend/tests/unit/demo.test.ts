import { describe, expect, it } from 'vitest';
import { createMockTransport, type StorageLike } from '../../src/api/mock';
import {
  answerFixtures,
  errorFixtures,
  historicalFixture,
  savedFixture,
} from '../../src/api/fixtures';
import { DEMO_PASSWORD, seedFaculty } from '../../src/api/seed';
import {
  answerSchema,
  conversationSchema,
  errorSchema,
  savedSchema,
  type Answer,
  type Conversation,
} from '../../src/api/schemas';
import { inputInstant, localInput, safeSource } from '../../src/components/format';
const storage = (): StorageLike => {
  const data = new Map<string, string>();
  return {
    getItem: (k) => data.get(k) || null,
    setItem: (k, v) => {
      data.set(k, v);
    },
    removeItem: (k) => {
      data.delete(k);
    },
  };
};
const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });
async function setup(email = 'student@campus.demo') {
  const store = storage();
  const t = createMockTransport(store, 0);
  await t('/auth/login', json('POST', { email, password: DEMO_PASSWORD }));
  return { t, store };
}
const request = (text: string, conversation_id: string | null = null) => ({
  text,
  conversation_id,
  client_request_id: crypto.randomUUID(),
  context_overrides: {},
  clarification: null,
});
describe('contract fixtures', () => {
  it('validates every shared success, clarification, failure, saved, and historical fixture', () => {
    for (const f of Object.values(answerFixtures))
      expect(answerSchema.safeParse(f).success).toBe(true);
    for (const f of Object.values(errorFixtures))
      expect(errorSchema.safeParse(f.body).success).toBe(true);
    expect(savedSchema.safeParse(savedFixture).success).toBe(true);
    expect(conversationSchema.safeParse(historicalFixture).success).toBe(true);
  });
  it('uses campus-local controls and rejects unsafe source protocols', () => {
    expect(localInput('2026-11-04T08:30:00Z')).toBe('2026-11-04T14:00');
    expect(inputInstant('2026-11-04T14:00')).toBe('2026-11-04T08:30:00.000Z');
    expect(safeSource('javascript:alert(1)')).toBeNull();
    expect(safeSource('data:text/html,test')).toBeNull();
    expect(safeSource('https://example.edu/notice')).toBe('https://example.edu/notice');
  });
});
describe('persistent demo integration', () => {
  it('deduplicates retries, rejects changed retry payloads, and persists follow-up context', async () => {
    const { t, store } = await setup();
    const req = request('Any workshops this week?');
    const first = (await t('/assistant/query', json('POST', req))) as Answer;
    expect(await t('/assistant/query', json('POST', req))).toEqual(first);
    await expect(
      t('/assistant/query', json('POST', { ...req, text: 'A different question' })),
    ).rejects.toMatchObject({ status: 409 });
    const follow = (await t(
      '/assistant/query',
      json('POST', request('Only Friday', first.conversation_id)),
    )) as Answer;
    expect(follow.interpreted_query.filters).toMatchObject({
      event_type: 'workshop',
      date: '2026-11-06',
    });
    expect(follow.applied_context.event_type.origin).toBe('prior_turn');
    expect(
      (
        (await createMockTransport(
          store,
          0,
        )('/conversations/' + first.conversation_id)) as Conversation
      ).turn_count,
    ).toBe(2);
  });
  it('binds clarification to the conversation and resets incompatible filters on a domain change', async () => {
    const { t } = await setup('admin@campus.demo');
    // Legacy imported blank aliases must not make an unrelated person match every name.
    await t(
      '/admin/faculty',
      json('POST', { ...seedFaculty[2], name: 'Dr. Test Faculty', aliases: [''] }),
    );
    await t('/auth/login', json('POST', { email: 'student@campus.demo', password: DEMO_PASSWORD }));
    const a = (await t(
      '/assistant/query',
      json('POST', request('Professor Rao office hours tomorrow')),
    )) as Answer;
    expect(a.status).toBe('clarification_required');
    expect(a.clarification?.options.length).toBe(2);
    const b = (await t(
      '/assistant/query',
      json('POST', {
        ...request('Dr. Anil Rao', a.conversation_id),
        clarification: { id: a.clarification!.id, option_id: 'faculty-rao-anil' },
      }),
    )) as Answer;
    expect(b.results[0].kind).toBe('faculty');
    const c = (await t(
      '/assistant/query',
      json('POST', request('Any workshops this week?', a.conversation_id)),
    )) as Answer;
    expect(c.interpreted_query.filters).not.toHaveProperty('faculty_id');
    await expect(
      t(
        '/assistant/query',
        json('POST', {
          ...request('Anil', a.conversation_id),
          clarification: { id: a.clarification!.id, option_id: 'faculty-rao-anil' },
        }),
      ),
    ).rejects.toMatchObject({ status: 409 });
  });
  it('distinguishes missing room coverage and respects adjacent bookings and closures', async () => {
    const { t } = await setup();
    const a = (await t(
      '/assistant/query',
      json('POST', request('Room in B Block today from 2 to 3 PM')),
    )) as Answer;
    expect(a.results.map((c) => c.record_id)).toEqual(['room-b204']);
    const b = (await t(
      '/assistant/query',
      json('POST', request('Room in A Block today from 2 to 3 PM')),
    )) as Answer;
    expect(b.status).toBe('information_unavailable');
    expect(b.results).toEqual([]);
  });
  it('keeps snapshots unchanged while saved records reflect cancellation', async () => {
    const { t } = await setup();
    const a = (await t(
      '/assistant/query',
      json('POST', request('Any AI workshops this week?')),
    )) as Answer;
    await t('/me/saved/event/event-ai', { method: 'PUT' });
    await t('/auth/login', json('POST', { email: 'admin@campus.demo', password: DEMO_PASSWORD }));
    await t('/admin/events/event-ai', json('PATCH', { status: 'cancelled', version: 1 }));
    await t('/auth/login', json('POST', { email: 'student@campus.demo', password: DEMO_PASSWORD }));
    const saved = (await t('/me/saved')) as { items: (typeof savedFixture)[] };
    expect(saved.items[0].record?.record_status).toBe('cancelled');
    const history = (await t('/conversations/' + a.conversation_id)) as Conversation;
    expect(history.turns[0].answer.results[0].record_status).toBe('published');
  });
  it('enforces demo user isolation, deletes state, and rejects student administration', async () => {
    const { t } = await setup();
    const a = (await t(
      '/assistant/query',
      json('POST', request('Any events this week?')),
    )) as Answer;
    await expect(t('/admin/events')).rejects.toMatchObject({ status: 403 });
    await t('/auth/login', json('POST', { email: 'ananya@campus.demo', password: DEMO_PASSWORD }));
    await expect(t('/conversations/' + a.conversation_id)).rejects.toMatchObject({ status: 404 });
    await t('/auth/login', json('POST', { email: 'student@campus.demo', password: DEMO_PASSWORD }));
    await t('/conversations/' + a.conversation_id, { method: 'DELETE' });
    await expect(t('/conversations/' + a.conversation_id)).rejects.toMatchObject({ status: 404 });
  });
});
