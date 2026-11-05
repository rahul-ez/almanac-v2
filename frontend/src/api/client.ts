import { z } from 'zod';
import { ApiError } from './errors';
import { errorSchema } from './schemas';

export type Transport = (path: string, init?: RequestInit) => Promise<unknown>;
export function createHttpTransport(
  baseUrl: string,
  fetcher: typeof fetch = fetch,
  onUnauthorized = () => window.dispatchEvent(new Event('session-expired')),
): Transport {
  let csrf: string | null = null;
  let csrfPending: Promise<string> | null = null;
  const base = baseUrl.replace(/\/$/, '');
  async function request(path: string, init: RequestInit = {}): Promise<unknown> {
    const method = init.method || 'GET';
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && !csrf) {
      csrfPending ??= request('/auth/csrf')
        .then((data) => {
          csrf = z.object({ csrf_token: z.string().min(1) }).parse(data).csrf_token;
          return csrf;
        })
        .finally(() => {
          csrfPending = null;
        });
      await csrfPending;
    }
    const headers = new Headers(init.headers);
    headers.set('Accept', 'application/json');

    if (init.body) headers.set('Content-Type', 'application/json');
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrf) headers.set('X-CSRF-Token', csrf);
    let response: Response;
    const timeout = AbortSignal.timeout(25_000);
    const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
    try {
      response = await fetcher(base + path, { ...init, headers, signal, credentials: 'include' });
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') throw error;
      if (timeout.aborted)
        throw new ApiError(
          504,
          'request_timeout',
          'The campus service took too long to respond. Retry to check the result safely.',
        );
      throw new ApiError(
        0,
        'network_error',
        'Could not reach the campus service. Check your connection and try again.',
      );
    }
    let body: unknown = null;
    if (response.status !== 204) {
      try {
        body = await response.json();
      } catch {
        /* handled as protocol error below */
      }
    }
    if (!response.ok) {
      const wire = body as {error?: {field_errors?: unknown}};
      if(Array.isArray(wire?.error?.field_errors)) wire.error.field_errors=Object.fromEntries(wire.error.field_errors.map((e:{field:string;message:string})=>[e.field.replace(/^body\./,''),[e.message]]));
      const parsed = errorSchema.safeParse(body);
      if (response.status === 401) {
        csrf = null;
        if (!path.startsWith('/auth/')) onUnauthorized();
      }
      if (response.status === 403 && parsed.success && parsed.data.error.code === 'csrf_failed')
        csrf = null;
      if (parsed.success) {
        const e = parsed.data.error;
        throw new ApiError(response.status, e.code, e.message, e.field_errors, e.request_id);
      }
      throw new ApiError(
        response.status,
        'http_error',
        response.status >= 500
          ? 'The campus service is temporarily unavailable. Try again shortly.'
          : 'The request could not be completed. Please reload and try again.',
        {},
        response.headers.get('X-Request-ID') || '',
      );
    }
    if (path === '/auth/login' || path === '/auth/logout') csrf = null;
    return body;
  }
  return request;
}

export async function validated<T>(
  transport: Transport,
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const data = await transport(path, init);
  const parsed = schema.safeParse(data);
  if (!parsed.success)
    throw new ApiError(
      502,
      'invalid_response',
      'The campus service returned an unexpected response. Please contact the administrator.',
    );
  return parsed.data;
}
