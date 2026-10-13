// Verifies and reads the events Extralt POSTs to webhook endpoints. Deliveries follow Standard
// Webhooks (https://www.standardwebhooks.com/): the `webhook-id`, `webhook-timestamp` and
// `webhook-signature` headers carry an HMAC-SHA256 signature, made with the endpoint's `whsec_`
// secret, of the id, the timestamp and the raw body.
import { WebhookVerificationError } from './core/errors.js';
import type { Enrichment, Import, Robot, Run } from './generated/openapi.js';

const DEFAULT_TOLERANCE = 300_000;

export interface RobotWebhookEvent {
  /** Stable across retries of the same event to the same endpoint: deduplicate on it. */
  id: string;
  type: 'robot.completed' | 'robot.failed';
  created_at: string;
  data: Robot;
}

export interface RunWebhookEvent {
  /** Stable across retries of the same event to the same endpoint: deduplicate on it. */
  id: string;
  type: 'run.completed' | 'run.stopped' | 'run.failed' | 'run.enrichment_skipped';
  created_at: string;
  data: Run;
}

export interface EnrichmentWebhookEvent {
  /** Stable across retries of the same event to the same endpoint: deduplicate on it. */
  id: string;
  type: 'enrichment.completed' | 'enrichment.stopped' | 'enrichment.failed';
  created_at: string;
  data: Enrichment;
}

export interface ImportWebhookEvent {
  /** Stable across retries of the same event to the same endpoint: deduplicate on it. */
  id: string;
  type: 'import.completed' | 'import.failed';
  created_at: string;
  data: Import;
}

export interface WebhookTestData {
  webhook_id: string;
  message: string;
}

/** Sent by `webhooks.test()` or from the dashboard, whatever event types the endpoint wants. */
export interface TestWebhookEvent {
  id: string;
  type: 'webhook.test';
  created_at: string;
  data: WebhookTestData;
}

/**
 * An event Extralt sends to a webhook endpoint, narrowed by its `type`. New event types are added
 * within v1, so handle a type you do not know, for example in a `default` branch.
 */
export type WebhookEvent =
  | RobotWebhookEvent
  | RunWebhookEvent
  | EnrichmentWebhookEvent
  | ImportWebhookEvent
  | TestWebhookEvent;

/** Request headers: a `Headers` object or a plain object such as Node.js's `request.headers`. */
export type WebhookHeaders = Headers | Record<string, string | string[] | undefined>;

export interface VerifyWebhookOptions {
  /**
   * How far a delivery's timestamp may be from the clock, in milliseconds, before it is refused as
   * a replay. Defaults to five minutes.
   */
  tolerance?: number;
}

/**
 * Checks a delivery's signature and returns its event. Pass the raw request body exactly as
 * received, before any JSON parsing, the request's headers and the endpoint's `whsec_` secret.
 * Throws `WebhookVerificationError` when a header is missing, the signature does not match, or the
 * timestamp is outside the tolerance.
 */
export async function verifyWebhook(
  payload: string | Uint8Array | ArrayBuffer,
  headers: WebhookHeaders,
  secret: string,
  options: VerifyWebhookOptions = {},
): Promise<WebhookEvent> {
  if (
    typeof payload !== 'string' &&
    !(payload instanceof Uint8Array || payload instanceof ArrayBuffer)
  ) {
    throw new TypeError('payload must be the raw request body, not parsed JSON');
  }
  const body =
    typeof payload === 'string' ? new TextEncoder().encode(payload) : new Uint8Array(payload);
  const id = header(headers, 'webhook-id');
  const timestamp = header(headers, 'webhook-timestamp');
  const signatures = header(headers, 'webhook-signature');
  if (!id || !timestamp || !signatures) {
    throw new WebhookVerificationError(
      'The webhook-id, webhook-timestamp and webhook-signature headers are required.',
    );
  }
  if (!/^\d+$/.test(timestamp)) {
    throw new WebhookVerificationError('The webhook-timestamp header is not a number.');
  }
  if (Math.abs(Date.now() - Number(timestamp) * 1000) > (options.tolerance ?? DEFAULT_TOLERANCE)) {
    throw new WebhookVerificationError('The webhook timestamp is outside the tolerance.');
  }
  const key = await crypto.subtle.importKey(
    'raw',
    secretKey(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['verify'],
  );
  const prefix = new TextEncoder().encode(`${id}.${timestamp}.`);
  const signed = new Uint8Array(prefix.length + body.length);
  signed.set(prefix);
  signed.set(body, prefix.length);
  let verified = false;
  for (const signature of signatures.split(' ')) {
    const [version, value] = signature.split(',', 2);
    const bytes = version === 'v1' && value ? base64Bytes(value) : undefined;
    if (bytes && (await crypto.subtle.verify('HMAC', key, bytes, signed))) {
      verified = true;
      break;
    }
  }
  if (!verified) throw new WebhookVerificationError('No webhook signature matches the payload.');
  let event: unknown;
  try {
    event = JSON.parse(new TextDecoder().decode(body));
  } catch {
    throw new WebhookVerificationError('The webhook payload is not JSON.');
  }
  if (event === null || typeof event !== 'object' || Array.isArray(event)) {
    throw new WebhookVerificationError('The webhook payload is not an event.');
  }
  return event as WebhookEvent;
}

function header(headers: WebhookHeaders, name: string): string | undefined {
  if (headers instanceof Headers) return headers.get(name) ?? undefined;
  for (const [key, value] of Object.entries(headers)) {
    if (key.toLowerCase() === name) return Array.isArray(value) ? value.join(' ') : value;
  }
  return undefined;
}

function secretKey(secret: string): Uint8Array<ArrayBuffer> {
  const key = base64Bytes(secret.replace(/^whsec_/, ''));
  if (!key) throw new TypeError("secret must be the endpoint's whsec_ signing secret");
  return key;
}

function base64Bytes(value: string): Uint8Array<ArrayBuffer> | undefined {
  try {
    return Uint8Array.from(atob(value), (char) => char.charCodeAt(0));
  } catch {
    return undefined;
  }
}
