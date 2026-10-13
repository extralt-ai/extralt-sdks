import { createHmac } from 'node:crypto';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { verifyWebhook, WebhookVerificationError } from '../src/index.js';
import { example, successResponse } from './spec.js';

const SECRET = 'whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw';

/** Headers as Extralt sends them, signed like the delivery action in Convex. */
function signed(
  body: string,
  { secret = SECRET, sentAt = Math.floor(Date.now() / 1000) } = {},
): Record<string, string> {
  const key = Buffer.from(secret.replace(/^whsec_/, ''), 'base64');
  const digest = createHmac('sha256', key).update(`evt_1.${sentAt}.${body}`).digest('base64');
  return {
    'webhook-id': 'evt_1',
    'webhook-timestamp': String(sentAt),
    'webhook-signature': `v1,${digest}`,
  };
}

function event(type: string, data: unknown): string {
  return JSON.stringify({ id: 'evt_1', type, created_at: '2026-10-12T10:40:50Z', data });
}

const testEvent = event('webhook.test', { webhook_id: 'webhook_1', message: 'Hello' });

afterEach(() => {
  vi.useRealTimers();
});

describe('verifyWebhook', () => {
  it('matches the Standard Webhooks reference signature', async () => {
    vi.useFakeTimers({ now: 1614265330 * 1000 });
    const headers = {
      'webhook-id': 'msg_p5jXN8AQM9LWM0D4loKWxJek',
      'webhook-timestamp': '1614265330',
      'webhook-signature': 'v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE=',
    };
    await expect(verifyWebhook('{"test": 2432232314}', headers, SECRET)).resolves.toEqual({
      test: 2432232314,
    });
    await expect(verifyWebhook('{"test": 2432232315}', headers, SECRET)).rejects.toThrow(
      'No webhook signature',
    );
  });

  it('returns the event, narrowed by its type', async () => {
    const run = example(successResponse('get_run').schema ?? {});
    const body = event('run.completed', run);
    const verified = await verifyWebhook(new TextEncoder().encode(body), signed(body), SECRET);
    expect(verified.type).toBe('run.completed');
    if (verified.type !== 'run.completed') throw new Error('not narrowed');
    expect(verified.data.id).toBe(run.id);
  });

  it('reads a Headers object and any matching signature', async () => {
    const headers = new Headers(signed(testEvent));
    headers.set('Webhook-Signature', `v1,bm90IGl0 ${headers.get('webhook-signature')}`);
    const verified = await verifyWebhook(testEvent, headers, SECRET);
    expect(verified).toMatchObject({ type: 'webhook.test', data: { webhook_id: 'webhook_1' } });
  });

  it('refuses a body changed after signing', async () => {
    await expect(
      verifyWebhook(testEvent.replace('Hello', 'Bye'), signed(testEvent), SECRET),
    ).rejects.toThrow(WebhookVerificationError);
  });

  it("refuses another endpoint's secret", async () => {
    const other = `whsec_${Buffer.from("another endpoint's secret!!!!!!!").toString('base64')}`;
    await expect(
      verifyWebhook(testEvent, signed(testEvent, { secret: other }), SECRET),
    ).rejects.toThrow(WebhookVerificationError);
  });

  it.each([-301, 301])('refuses a timestamp %is away', async (age) => {
    const headers = signed(testEvent, { sentAt: Math.floor(Date.now() / 1000) - age });
    await expect(verifyWebhook(testEvent, headers, SECRET)).rejects.toThrow('tolerance');
    await expect(
      verifyWebhook(testEvent, headers, SECRET, { tolerance: 600_000 }),
    ).resolves.toEqual(JSON.parse(testEvent));
  });

  it.each(['webhook-id', 'webhook-timestamp', 'webhook-signature'])(
    'refuses a delivery without %s',
    async (name) => {
      const headers = signed(testEvent);
      delete headers[name];
      await expect(verifyWebhook(testEvent, headers, SECRET)).rejects.toThrow('required');
    },
  );

  it('refuses parsed JSON and a malformed secret', async () => {
    await expect(verifyWebhook(JSON.parse(testEvent), signed(testEvent), SECRET)).rejects.toThrow(
      TypeError,
    );
    await expect(verifyWebhook(testEvent, signed(testEvent), 'whsec_not base64!')).rejects.toThrow(
      'whsec_',
    );
  });
});
