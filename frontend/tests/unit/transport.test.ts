import { describe, expect, it, vi } from 'vitest';
import { createHttpTransport, validated } from '../../src/api/client';
import { answerSchema } from '../../src/api/schemas';

describe('HTTP integration boundary', () => {
  it('initializes CSRF before login and includes credentials without retrying a mutation', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: 'csrf-token' })))
      .mockResolvedValueOnce(new Response('{}'));
    await createHttpTransport('/api/v1', fetcher)('/auth/login', { method: 'POST', body: '{}' });
    expect(fetcher.mock.calls.map((c) => c[0])).toEqual([
      '/api/v1/auth/csrf',
      '/api/v1/auth/login',
    ]);
    expect(new Headers(fetcher.mock.calls[1][1]?.headers).get('X-CSRF-Token')).toBe('csrf-token');
    expect(fetcher.mock.calls[1][1]?.credentials).toBe('include');
  });
  it('never turns an outage or bad response into a successful empty answer', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response('gateway down', { status: 503 }));
    await expect(createHttpTransport('/api/v1', fetcher)('/events')).rejects.toMatchObject({
      status: 503,
      code: 'http_error',
    });
    await expect(
      validated(async () => ({ results: [] }), '/assistant/query', answerSchema),
    ).rejects.toMatchObject({ code: 'invalid_response' });
    const network = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('network'));
    await expect(createHttpTransport('/api/v1', network)('/events')).rejects.toMatchObject({
      status: 0,
      code: 'network_error',
    });
  });
  it('invalidates the session on 401 and preserves field errors and request IDs', async () => {
    const expired = vi.fn();
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: 'session_expired',
            message: 'Sign in again.',
            field_errors: {},
            request_id: 'req-1',
          },
        }),
        { status: 401 },
      ),
    );
    await expect(
      createHttpTransport('/api/v1', fetcher, expired)('/conversations'),
    ).rejects.toMatchObject({ status: 401, requestId: 'req-1' });
    expect(expired).toHaveBeenCalledOnce();
  });
  it('passes AbortSignal through without relabeling cancellation as a network failure', async () => {
    const controller = new AbortController();
    controller.abort();
    const fetcher = vi
      .fn<typeof fetch>()
      .mockRejectedValue(new DOMException('Aborted', 'AbortError'));
    await expect(
      createHttpTransport('/api/v1', fetcher)('/events', { signal: controller.signal }),
    ).rejects.toMatchObject({ name: 'AbortError' });
    expect(fetcher.mock.calls[0][1]?.signal?.aborted).toBe(true);
  });
});
