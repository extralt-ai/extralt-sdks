// Exercises the built package through the Fetch API alone, so every supported runtime runs it.
import { Extralt, NotFoundError, verifyWebhook } from '../../dist/index.js';

async function respond(request) {
  const { pathname, searchParams } = new URL(request.url);
  if (request.method === 'GET' && pathname === '/v1/extract/robots') {
    const last = searchParams.get('cursor') === 'page-2';
    return Response.json({
      data: [{ id: last ? 'robot_2' : 'robot_1' }],
      next_cursor: last ? null : 'page-2',
    });
  }
  if (request.method === 'POST' && pathname === '/v1/extract/imports') {
    return Response.json(
      { id: 'import_1', status: 'completed', finished: true, received: await request.text() },
      { status: 202 },
    );
  }
  if (request.method === 'GET' && pathname === '/v1/extract/captures/export') {
    return new Response('{"id":"1"}\n', { headers: { 'Content-Type': 'application/x-ndjson' } });
  }
  return Response.json(
    { error: { code: 'not_found', message: 'Not found', request_id: 'req_1' } },
    { status: 404 },
  );
}

const SECRET = 'whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw';

async function sign(content) {
  const key = await crypto.subtle.importKey(
    'raw',
    Uint8Array.from(atob(SECRET.slice('whsec_'.length)), (char) => char.charCodeAt(0)),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  return btoa(
    String.fromCharCode(
      ...new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(content))),
    ),
  );
}

function check(condition, message) {
  if (!condition) throw new Error(message);
}

export async function smoke() {
  const client = new Extralt({
    apiKey: 'k',
    fetch: (input, init) => respond(new Request(input, init)),
  });

  const ids = [];
  for await (const robot of client.extract.robots.list()) ids.push(robot.id);
  check(ids.join() === 'robot_1,robot_2', `pagination returned ${ids}`);

  const upload = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('sku,title\n1,Shoe\n'));
      controller.close();
    },
  });
  const imported = await client.extract.imports.create(upload, { country: 'US' });
  check(imported.received === 'sku,title\n1,Shoe\n', 'a streamed upload must arrive whole');

  const exported = await client.extract.captures.export({ run_id: 'run_1', format: 'jsonl' });
  check((await exported.text()) === '{"id":"1"}\n', 'an export must stream its body');

  // Signs and verifies a delivery through each runtime's Web Crypto.
  const delivery = '{"type":"webhook.test"}';
  const timestamp = String(Math.floor(Date.now() / 1000));
  const event = await verifyWebhook(
    delivery,
    {
      'webhook-id': 'msg_1',
      'webhook-timestamp': timestamp,
      'webhook-signature': `v1,${await sign(`msg_1.${timestamp}.${delivery}`)}`,
    },
    SECRET,
  );
  check(event.type === 'webhook.test', 'a signed webhook must verify');

  try {
    await client.extract.robots.get('missing');
  } catch (error) {
    check(error instanceof NotFoundError && error.requestId === 'req_1', `unexpected ${error}`);
    return;
  }
  throw new Error('a 404 must reject with NotFoundError');
}
