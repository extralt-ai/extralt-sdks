import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Extralt, JobFailedError, WaitTimeoutError } from '../src/index.js';
import { example, successResponse } from './spec.js';

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

function client(
  handler: (request: Request) => Response | Promise<Response>,
  options: { logged?: string[] } = {},
): Extralt {
  const { logged } = options;
  return new Extralt({
    apiKey: 'k',
    fetch: async (input, init) => handler(new Request(input, init)),
    ...(logged && {
      logLevel: 'info',
      logger: { debug: () => {}, info: (message) => logged.push(message) },
    }),
  });
}

function run(fields: Record<string, unknown> = {}): Record<string, unknown> {
  return { ...example(successResponse('get_run').schema ?? {}), ...fields };
}

describe('resources', () => {
  it('iterates every item across pages', async () => {
    const cursors: (string | null)[] = [];
    const extralt = client((request) => {
      const cursor = new URL(request.url).searchParams.get('cursor');
      cursors.push(cursor);
      return cursor === null
        ? Response.json({ data: [run({ id: 'a' }), run({ id: 'b' })], next_cursor: '2' })
        : Response.json({ data: [run({ id: 'c' })], next_cursor: null });
    });
    const ids: string[] = [];
    for await (const item of extralt.extract.runs.list({ limit: 2 })) ids.push(item.id);
    expect(ids).toEqual(['a', 'b', 'c']);
    expect(cursors).toEqual([null, '2']);
  });

  it('waits until a run is finished, backing off between polls', async () => {
    const states = [
      run({ status: 'running', finished: false }),
      run({ status: 'running', finished: false }),
      run({ status: 'completed', finished: true }),
    ];
    const polledAt: number[] = [];
    const extralt = client(() => {
      polledAt.push(Date.now());
      return Response.json(states.shift());
    });
    const waiting = extralt.extract.runs.wait('run_1');
    await vi.advanceTimersByTimeAsync(10_000);
    const result = await waiting;
    expect(result.status).toBe('completed');
    expect(polledAt.map((time) => time - (polledAt[0] ?? 0))).toEqual([0, 2_000, 5_000]);
  });

  it('gives up waiting with the job still running', async () => {
    const extralt = client(() => Response.json(run({ status: 'running', finished: false })));
    const failure = extralt.extract.runs.wait('run_1', { timeout: 0 });
    await expect(failure).rejects.toBeInstanceOf(WaitTimeoutError);
    await expect(failure).rejects.toMatchObject({ resource: { status: 'running' } });
  });

  it('returns a started job finished', async () => {
    const states = [
      run({ id: 'run_1', status: 'pending', finished: false }),
      run({ id: 'run_1', status: 'running', finished: false }),
      run({ id: 'run_1', status: 'completed', finished: true }),
    ];
    const requests: string[] = [];
    const logged: string[] = [];
    const extralt = client(
      (request) => {
        requests.push(`${request.method} ${new URL(request.url).pathname}`);
        return Response.json(states.shift());
      },
      { logged },
    );
    const starting = extralt.extract.runs.create({ robot_id: 'robot_1', budget: 5 });
    await vi.advanceTimersByTimeAsync(10_000);
    expect((await starting).status).toBe('completed');
    expect(requests).toEqual([
      'POST /v1/extract/runs',
      'GET /v1/extract/runs/run_1',
      'GET /v1/extract/runs/run_1',
    ]);
    expect(logged).toEqual([
      'Waiting for Run run_1, now pending',
      'Run run_1 is running',
      'Run run_1 is completed',
    ]);
  });

  it('returns a job as started without waiting', async () => {
    let requests = 0;
    const extralt = client(() => {
      requests += 1;
      return Response.json(run({ status: 'pending', finished: false }));
    });
    const started = await extralt.extract.runs.create(
      { robot_id: 'robot_1', budget: 5 },
      { wait: false },
    );
    expect([started.status, requests]).toEqual(['pending', 1]);
  });

  it('gives up on a started job within its timeout', async () => {
    const extralt = client(() => Response.json(run({ status: 'running', finished: false })));
    const failure = extralt.extract.runs.create({ robot_id: 'robot_1', budget: 5 }, { timeout: 0 });
    await expect(failure).rejects.toBeInstanceOf(WaitTimeoutError);
    await expect(failure).rejects.toMatchObject({ resource: { status: 'running' } });
  });

  it.each([
    ['get_run', 'failed'],
    ['get_import', 'validation_failed'],
  ] as const)('throws when a job from %s ends as %s', async (operationId, status) => {
    const job = {
      ...example(successResponse(operationId).schema ?? {}),
      id: 'job_1',
      status,
      finished: true,
      status_reason: 'The store blocked the crawl',
    };
    const { extract } = client(() => Response.json(job));
    const failure =
      operationId === 'get_run' ? extract.runs.wait('job_1') : extract.imports.wait('job_1');
    await expect(failure).rejects.toBeInstanceOf(JobFailedError);
    await expect(failure).rejects.toMatchObject({
      message: expect.stringContaining('The store blocked the crawl'),
      resource: { status },
    });
  });

  it('returns a stopped job', async () => {
    const extralt = client(() => Response.json(run({ status: 'stopped', finished: true })));
    expect((await extralt.extract.runs.wait('run_1')).status).toBe('stopped');
  });

  it('needs a budget for a run, and sends none when it is unlimited', async () => {
    const bodies: unknown[] = [];
    const { runs } = client(async (request) => {
      bodies.push(await request.json());
      return Response.json(run({ status: 'completed', finished: true }));
    }).extract;
    // @ts-expect-error a missing budget, as read from an unset configuration entry
    await expect(runs.create({ robot_id: 'robot_1', budget: undefined })).rejects.toThrow(/budget/);
    expect(bodies).toEqual([]);

    await runs.create({ robot_id: 'robot_1', budget: 'unlimited' });
    await runs.create({ robot_id: 'robot_1', budget: 5 });
    expect(bodies).toEqual([{ robot_id: 'robot_1' }, { robot_id: 'robot_1', budget: 5 }]);
  });

  it('uploads an import with its media type', async () => {
    const seen: Request[] = [];
    const extralt = client((request) => {
      seen.push(request);
      return Response.json(example(successResponse('get_import').schema ?? {}), { status: 202 });
    });
    await extralt.extract.imports.create(
      new Blob(['sku\n1\n'], { type: 'text/csv' }),
      { file_name: 'catalog.csv' },
      { wait: false },
    );
    expect(seen[0]?.headers.get('Content-Type')).toBe('text/csv');
    expect(await seen[0]?.text()).toBe('sku\n1\n');
  });

  it('sends only the given fields and explicit nulls when updating', async () => {
    const bodies: unknown[] = [];
    const extralt = client(async (request) => {
      bodies.push(await request.json());
      return Response.json(example(successResponse('update_schedule').schema ?? {}));
    });
    await extralt.extract.schedules.update('schedule_1', { name: 'Weekly', budget: 'unlimited' });
    expect(bodies).toEqual([{ name: 'Weekly', budget: null }]);
  });
});
