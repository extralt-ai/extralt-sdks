import { ExtraltError } from './core/errors.js';
import { HTTP } from './core/http.js';
import { type Logger, type LogLevel, levelledLogger, logLevel } from './core/log.js';
import { Enrich } from './resources/enrich.js';
import { Explore } from './resources/explore.js';
import { Extract } from './resources/extract.js';
import { Query } from './resources/query.js';

const DEFAULT_BASE_URL = 'https://api.extralt.com';
const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]']);

export interface ClientOptions {
  /** Defaults to the `EXTRALT_API_KEY` environment variable where the runtime exposes one. */
  apiKey?: string;
  /** Defaults to production. Must use HTTPS unless it targets localhost. */
  baseURL?: string;
  /** Request timeout in milliseconds, up to response headers. Defaults to 60 seconds. */
  timeout?: number;
  /** Retries for operations that are safe to repeat. Defaults to 2. */
  maxRetries?: number;
  /** Extra headers sent with every request. */
  headers?: Record<string, string>;
  /** Custom fetch, for proxies, tracing or tests. */
  fetch?: typeof fetch;
  /**
   * `debug` logs every response and retry, `info` only retries. Defaults to the `EXTRALT_LOG`
   * environment variable where the runtime exposes one, else `off`. API keys are never logged.
   */
  logLevel?: LogLevel;
  /** Receives the log lines. Defaults to `console`. */
  logger?: Logger;
}

/**
 * Client for the Extralt API.
 *
 * Requests that fail with a network error, 408, 429 or 5xx are retried with backoff when the
 * operation is safe to repeat; create and restart operations send an idempotency key that every
 * retry reuses.
 */
export class Extralt {
  readonly baseURL: string;
  /** @internal */
  readonly http: HTTP;
  readonly extract: Extract;
  readonly enrich: Enrich;
  readonly explore: Explore;
  readonly query: Query;

  constructor(options: ClientOptions = {}) {
    const apiKey = options.apiKey ?? environment('EXTRALT_API_KEY');
    if (!apiKey) {
      throw new ExtraltError(
        'Pass apiKey or set the EXTRALT_API_KEY environment variable to an Extralt API key.',
      );
    }
    this.baseURL = validateBaseURL(options.baseURL ?? DEFAULT_BASE_URL);
    this.http = new HTTP({
      baseURL: this.baseURL,
      apiKey,
      timeout: options.timeout ?? 60_000,
      maxRetries: options.maxRetries ?? 2,
      headers: options.headers ?? {},
      fetch: options.fetch ?? globalThis.fetch.bind(globalThis),
      log: levelledLogger(
        options.logLevel ?? logLevel(optionalEnvironment('EXTRALT_LOG')),
        options.logger,
      ),
    });
    this.extract = new Extract(this.http);
    this.enrich = new Enrich(this.http);
    this.explore = new Explore(this.http);
    this.query = new Query(this.http);
  }
}

function environment(name: string): string | undefined {
  return (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.[
    name
  ];
}

/** An optional setting: never prompts for or fails on access a runtime such as Deno restricts. */
function optionalEnvironment(name: string): string | undefined {
  const permissions = (
    globalThis as {
      Deno?: {
        permissions: {
          querySync(descriptor: { name: 'env'; variable: string }): { state: string };
        };
      };
    }
  ).Deno?.permissions;
  if (permissions && permissions.querySync({ name: 'env', variable: name }).state !== 'granted') {
    return undefined;
  }
  try {
    return environment(name);
  } catch {
    return undefined;
  }
}

function validateBaseURL(baseURL: string): string {
  const url = new URL(baseURL);
  if (url.protocol !== 'https:' && !LOCAL_HOSTS.has(url.hostname)) {
    throw new ExtraltError('baseURL must use HTTPS unless it targets localhost.');
  }
  return url.toString().replace(/\/$/, '');
}
