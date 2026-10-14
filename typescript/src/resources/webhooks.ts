import { Resource } from '../core/resource.js';
import type { CallOptions, IdempotentCallOptions } from '../core/types.js';
import type {
  Webhook,
  WebhookCreateParams,
  WebhookList,
  WebhookTestResult,
  WebhookWithSecret,
} from '../generated/openapi.js';

/**
 * HTTPS endpoints that receive the organization's events. Verify each delivery with
 * `verifyWebhook`.
 */
export class Webhooks extends Resource {
  /**
   * Registers an HTTPS endpoint and returns it with its signing `secret`. Leave out `event_types`
   * to receive every event type, including ones added later. The API returns the secret only
   * here; keep it to verify deliveries.
   */
  create(
    params: WebhookCreateParams,
    options: IdempotentCallOptions = {},
  ): Promise<WebhookWithSecret> {
    return this.http.request('create_webhook', { body: params, ...options });
  }

  list(options: CallOptions = {}): Promise<WebhookList> {
    return this.http.request('list_webhooks', options);
  }

  get(id: string, options: CallOptions = {}): Promise<Webhook> {
    return this.http.request('get_webhook', { path: { id }, ...options });
  }

  /** Deletes the endpoint and its delivery history. */
  async delete(id: string, options: CallOptions = {}): Promise<void> {
    await this.http.request('delete_webhook', { path: { id }, ...options });
  }

  /** Sends a `webhook.test` event to the endpoint once, without retries. */
  test(id: string, options: CallOptions = {}): Promise<WebhookTestResult> {
    return this.http.request('test_webhook', { path: { id }, ...options });
  }
}
