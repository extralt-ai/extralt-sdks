import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  APIConnectionError,
  Extralt,
  ExtraltError,
  InternalServerError,
  NotFoundError,
  RateLimitError,
} from '../src/index.js';

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

/** Settles a request while fast-forwarding its retry delays. */
async function settle<T>(request: Promise<T>): Promise<T> {
  const outcome = request.then(
    (value) => ({ ok: true as const, value }),
    (reason: unknown) => ({ ok: false as const, reason }),
  );
  let settled = false;
  void outcome.finally(() => {
    settled = true;
  });
  while (!settled) await vi.advanceTimersByTimeAsync(1_000);
  const result = await outcome;
  if (!result.ok) throw result.reason;
  return result.value;
}

type Handler = (request: Request) => Response | Promise<Response>;

function client(handler: Handler, options: { maxRetries?: number } = {}): Extralt {
  return new Extralt({
    apiKey: 'test-key',
    ...options,
    fetch: async (input, init) => handler(new Request(input, init)),
  });
}

function error(status: number, code: string, headers: Record<string, string> = {}): Response {
  return Response.json(
    { error: { code, message: `${code} happened`, request_id: 'req_1' } },
    { status, headers },
  );
}

describe('transport', () => {
  it('retries an idempotent create with one idempotency key', async () => {
    const requests: Request[] = [];
    const extralt = client((request) => {
      requests.push(request);
      if (requests.length === 1) return error(429, 'rate_limit_exceeded', { 'Retry-After': '0' });
      if (requests.length === 2) return error(503, 'upstream_unavailable');
      return Response.json({ id: 'run_1' }, { status: 202 });
    });

    const run = await settle(extralt.http.request('create_run', { body: { robot_id: 'robot_1' } }));

    expect(run).toEqual({ id: 'run_1' });
    expect(requests).toHaveLength(3);
    expect(new Set(requests.map((request) => request.headers.get('Idempotency-Key'))).size).toBe(1);
    expect(requests[0]?.headers.get('Authorization')).toBe('Bearer test-key');
    expect(requests[0]?.headers.get('Content-Type')).toBe('application/json');
    expect(requests[0]?.url).toBe('https://api.extralt.com/v1/extract/runs');
  });

  it('sends a caller idempotency key unchanged', async () => {
    const keys: (string | null)[] = [];
    const extralt = client((request) => {
      keys.push(request.headers.get('Idempotency-Key'));
      return Response.json({}, { status: 202 });
    });
    await extralt.http.request('create_run', {
      body: { robot_id: 'robot_1' },
      idempotencyKey: 'mine',
    });
    expect(keys).toEqual(['mine']);
  });

  it('does not retry an operation that is not idempotent', async () => {
    let calls = 0;
    const extralt = client(() => {
      calls += 1;
      return error(503, 'upstream_unavailable');
    });
    await expect(
      settle(extralt.http.request('update_schedule', { path: { id: 's' }, body: {} })),
    ).rejects.toBeInstanceOf(InternalServerError);
    expect(calls).toBe(1);
  });

  it('gives up after the configured retries with the typed error', async () => {
    let calls = 0;
    const extralt = client(
      () => {
        calls += 1;
        return error(429, 'rate_limit_exceeded');
      },
      { maxRetries: 1 },
    );
    const failure = settle(extralt.http.request('list_runs', {}));
    await expect(failure).rejects.toBeInstanceOf(RateLimitError);
    await expect(failure).rejects.toMatchObject({ code: 'rate_limit_exceeded', status: 429 });
    expect(calls).toBe(2);
  });

  it('maps the error envelope and escapes path parameters', async () => {
    const urls: string[] = [];
    const extralt = client((request) => {
      urls.push(request.url);
      return error(404, 'not_found');
    });
    const failure = settle(extralt.http.request('get_run', { path: { id: 'a/b c' } }));
    await expect(failure).rejects.toBeInstanceOf(NotFoundError);
    await expect(failure).rejects.toMatchObject({
      message: '404 not_found: not_found happened (request req_1)',
      requestId: 'req_1',
    });
    expect(urls[0]).toBe('https://api.extralt.com/v1/extract/runs/a%2Fb%20c');
  });

  it('wraps network failures after retrying idempotent operations', async () => {
    let calls = 0;
    const extralt = client(() => {
      calls += 1;
      throw new TypeError('fetch failed');
    });
    await expect(settle(extralt.http.request('list_runs', {}))).rejects.toBeInstanceOf(
      APIConnectionError,
    );
    expect(calls).toBe(3);
  });
});

describe('logging', () => {
  function logged(options: { logLevel?: 'debug' | 'info' | 'off' }) {
    const lines: string[] = [];
    let calls = 0;
    const extralt = new Extralt({
      apiKey: 'test-key',
      ...options,
      logger: {
        debug: (message) => lines.push(`debug ${message}`),
        info: (message) => lines.push(`info ${message}`),
      },
      fetch: async () =>
        ++calls === 1
          ? error(429, 'rate_limit_exceeded', { 'Retry-After': '2', 'x-request-id': 'req_1' })
          : Response.json({ data: [], next_cursor: null }),
    });
    return { lines, run: () => settle(extralt.extract.robots.list({ limit: 5 }).firstPage()) };
  }

  const url = 'https://api.extralt.com/v1/extract/robots?limit=5';

  it('logs responses at debug and retries at info, never the API key', async () => {
    const { lines, run } = logged({ logLevel: 'debug' });
    await run();
    expect(lines).toEqual([
      `debug GET ${url} -> 429 (request req_1)`,
      'info Retrying list_robots after HTTP 429 in 2.00s',
      `debug GET ${url} -> 200 (request none)`,
    ]);
    expect(lines.join('\n')).not.toContain('test-key');
  });

  it('logs only retries at info, and nothing unless enabled', async () => {
    const info = logged({ logLevel: 'info' });
    await info.run();
    expect(info.lines).toEqual(['info Retrying list_robots after HTTP 429 in 2.00s']);

    const off = logged({});
    await off.run();
    expect(off.lines).toEqual([]);
  });

  it('takes the level from EXTRALT_LOG', async () => {
    vi.stubEnv('EXTRALT_LOG', 'info');
    try {
      const { lines, run } = logged({});
      await run();
      expect(lines).toEqual(['info Retrying list_robots after HTTP 429 in 2.00s']);
    } finally {
      vi.unstubAllEnvs();
    }
  });
});

describe('configuration', () => {
  it('requires an API key', () => {
    vi.stubEnv('EXTRALT_API_KEY', '');
    expect(() => new Extralt()).toThrow(ExtraltError);
    vi.unstubAllEnvs();
  });

  it('rejects plain HTTP except locally', () => {
    expect(() => new Extralt({ apiKey: 'k', baseURL: 'http://api.example.com' })).toThrow('HTTPS');
    expect(new Extralt({ apiKey: 'k', baseURL: 'http://localhost:8080/' }).baseURL).toBe(
      'http://localhost:8080',
    );
  });
});
