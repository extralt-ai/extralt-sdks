// The `extralt` module as README snippets see it in readme.test.ts: the real SDK, with a client
// that answers every request with a spec-shaped response, and the values a reader brings.
import { type ClientOptions, type Robot, type Run, Extralt as SdkExtralt } from '../src/index.js';
import { example, operations, successResponse } from './spec.js';

export * from '../src/index.js';

function operationFor(request: Request): string {
  const { pathname } = new URL(request.url);
  for (const [operationId, { method, path }] of operations) {
    const pattern = new RegExp(`^${path.replace(/\{[^}]+\}/g, '[^/]+')}$`);
    if (request.method === method && pattern.test(pathname)) return operationId;
  }
  throw new Error(`${request.method} ${pathname} is not in the spec`);
}

/** Every job finished and every list on its last page, so waits and iteration end. */
function settled(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(settled);
  if (value === null || typeof value !== 'object') return value;
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [
      key,
      key === 'next_cursor' ? null : key === 'finished' ? true : settled(item),
    ]),
  );
}

async function respond(input: string | URL | Request, init?: RequestInit): Promise<Response> {
  const request = new Request(input, init);
  const { status, schema } = successResponse(operationFor(request));
  if (!schema) return new Response(status === 204 ? null : 'binary', { status });
  return Response.json(settled(example(schema)), { status });
}

/** Keeps the reader's options but answers every request locally. */
export class Extralt extends SdkExtralt {
  constructor(options: ClientOptions = {}) {
    super({ ...options, apiKey: 'k', fetch: respond });
  }
}

export const variantId = '9007199254740993';
export const client: Extralt = new Extralt();
export const robot: Robot = await client.extract.robots.get('robot_1');
export const run: Run = await client.extract.runs.get('run_1');
