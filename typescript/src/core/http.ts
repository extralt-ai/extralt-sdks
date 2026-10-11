import { OPERATIONS } from '../generated/operations.js';
import { VERSION } from '../version.js';
import { APIConnectionError, APITimeoutError, statusError } from './errors.js';
import type { Logger } from './log.js';
import type { OperationId, RawBody, RequestOptions, SuccessBody } from './types.js';

const RETRYABLE_STATUSES = new Set([408, 429, 500, 502, 503, 504]);
const INITIAL_RETRY_DELAY = 500;
const MAX_RETRY_DELAY = 8_000;
const MAX_RETRY_AFTER = 60_000;

export interface HTTPConfig {
  baseURL: string;
  apiKey: string;
  timeout: number;
  maxRetries: number;
  headers: Record<string, string>;
  fetch: typeof fetch;
  log: Logger;
}

/** Sends documented operations with authentication, retries and idempotency keys. */
export class HTTP {
  readonly config: HTTPConfig;

  constructor(config: HTTPConfig) {
    this.config = config;
  }

  async request<K extends OperationId>(
    operationId: K,
    options: RequestOptions<K>,
  ): Promise<SuccessBody<K>> {
    const response = await this.send(operationId, options);
    if (response.status === 204) return undefined as SuccessBody<K>;
    return (await response.json()) as SuccessBody<K>;
  }

  /** Sends the request and returns the successful response without reading its body. */
  async send<K extends OperationId>(operationId: K, options: RequestOptions<K>): Promise<Response> {
    const operation = OPERATIONS[operationId];
    const url = this.url(operation.path, options.path, options.query);
    const headers = new Headers({
      Authorization: `Bearer ${this.config.apiKey}`,
      Accept: 'application/json',
      'User-Agent': `extralt-typescript/${VERSION} ${runtime()}`,
      ...this.config.headers,
      ...options.headers,
    });
    if (operation.idempotencyKey) {
      headers.set('Idempotency-Key', options.idempotencyKey ?? crypto.randomUUID());
    }
    const body = encodeBody(options.body, headers);
    const replayable = !(body instanceof ReadableStream);

    for (let attempt = 0; ; attempt++) {
      const timeout = new AbortController();
      const timer = setTimeout(() => timeout.abort(), options.timeout ?? this.config.timeout);
      const signal = options.signal
        ? AbortSignal.any([options.signal, timeout.signal])
        : timeout.signal;
      let response: Response;
      try {
        response = await this.config.fetch(url, {
          method: operation.method,
          headers,
          body,
          signal,
          // Node.js requires half-duplex mode to stream a request body.
          ...(body instanceof ReadableStream ? { duplex: 'half' } : {}),
        } as RequestInit);
      } catch (error) {
        if (options.signal?.aborted) throw error;
        const timedOut = timeout.signal.aborted;
        if (attempt < this.config.maxRetries && operation.idempotent && replayable) {
          const delay = retryDelay(attempt, null);
          const reason = error instanceof Error ? error.message : String(error);
          this.config.log.info(`Retrying ${operationId} after ${reason} in ${seconds(delay)}s`);
          await sleep(delay, options.signal);
          continue;
        }
        throw timedOut
          ? new APITimeoutError({ cause: error })
          : new APIConnectionError(error instanceof Error ? error.message : 'Connection error', {
              cause: error,
            });
      } finally {
        clearTimeout(timer);
      }

      const requestId = response.headers.get('x-request-id') ?? 'none';
      this.config.log.debug(
        `${operation.method} ${url} -> ${response.status} (request ${requestId})`,
      );
      if (response.ok) return response;
      if (
        attempt < this.config.maxRetries &&
        operation.idempotent &&
        replayable &&
        RETRYABLE_STATUSES.has(response.status)
      ) {
        await response.body?.cancel();
        const delay = retryDelay(attempt, response.headers.get('retry-after'));
        this.config.log.info(
          `Retrying ${operationId} after HTTP ${response.status} in ${seconds(delay)}s`,
        );
        await sleep(delay, options.signal);
        continue;
      }
      throw await statusError(response);
    }
  }

  private url(path: string, params: object | undefined, query: object | undefined): string {
    const resolved = path.replace(/\{(\w+)\}/g, (_, name: string) => {
      const value = (params as Record<string, unknown> | undefined)?.[name];
      if (value === undefined) throw new TypeError(`Missing path parameter ${name}`);
      return encodeURIComponent(String(value));
    });
    const search = new URLSearchParams();
    for (const [name, value] of Object.entries(query ?? {})) {
      if (value === undefined || value === null) continue;
      for (const item of Array.isArray(value) ? value : [value]) search.append(name, String(item));
    }
    const suffix = search.size > 0 ? `?${search}` : '';
    return `${this.config.baseURL}${resolved}${suffix}`;
  }
}

function encodeBody(body: unknown, headers: Headers): RawBody | undefined {
  if (body === undefined) return undefined;
  if (
    typeof body === 'string' ||
    body instanceof Blob ||
    body instanceof ArrayBuffer ||
    ArrayBuffer.isView(body) ||
    body instanceof ReadableStream ||
    body instanceof URLSearchParams ||
    body instanceof FormData
  ) {
    return body as RawBody;
  }
  headers.set('Content-Type', 'application/json');
  return JSON.stringify(body);
}

export function retryDelay(attempt: number, retryAfter: string | null): number {
  if (retryAfter) {
    const seconds = Number(retryAfter);
    const milliseconds = Number.isFinite(seconds)
      ? seconds * 1000
      : Date.parse(retryAfter) - Date.now();
    if (milliseconds >= 0 && milliseconds <= MAX_RETRY_AFTER) return milliseconds;
  }
  const delay = Math.min(INITIAL_RETRY_DELAY * 2 ** attempt, MAX_RETRY_DELAY);
  return delay * (0.75 + Math.random() * 0.25);
}

export function sleep(milliseconds: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(signal.reason);
    const timer = setTimeout(resolve, milliseconds);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(signal.reason);
      },
      { once: true },
    );
  });
}

function seconds(milliseconds: number): string {
  return (milliseconds / 1000).toFixed(2);
}

function runtime(): string {
  const agent = (globalThis as { navigator?: { userAgent?: string } }).navigator?.userAgent;
  return agent && !agent.startsWith('Mozilla/') ? agent : 'unknown-runtime';
}
