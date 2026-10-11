import { type Job, JobFailedError, WaitTimeoutError } from './errors.js';
import { type HTTP, sleep } from './http.js';
import type { CallOptions, IdempotentCallOptions, OperationId, RequestOptions } from './types.js';

const INITIAL_POLL_INTERVAL = 2_000;
const MAX_POLL_INTERVAL = 30_000;
const DEFAULT_WAIT_TIMEOUT = 3_600_000;
const FAILED_STATUSES = new Set(['failed', 'validation_failed']);

/** Options for `wait()`. */
export interface WaitOptions extends CallOptions {
  /** How long to wait, in milliseconds, before a `WaitTimeoutError`. Defaults to one hour. */
  timeout?: number;
  /** Fixed polling interval in milliseconds. Defaults to a backoff from 2 to 30 seconds. */
  pollInterval?: number;
}

/** Options for a call that starts a job: a Robot build, a Run, an Import or an Enrichment. */
export interface JobOptions extends IdempotentCallOptions {
  /** Pass `false` to return the job as started instead of waiting for it to finish. */
  wait?: boolean;
  /**
   * How long the call may take in milliseconds, waiting included, before a `WaitTimeoutError`.
   * Defaults to one hour. With `wait: false` it bounds the request, as on other calls.
   */
  timeout?: number;
  /** Fixed polling interval in milliseconds. Defaults to a backoff from 2 to 30 seconds. */
  pollInterval?: number;
}

export abstract class Resource {
  protected readonly http: HTTP;

  constructor(http: HTTP) {
    this.http = http;
  }

  /** Starts a job and returns it finished, or as started when `options.wait` is false. */
  protected async startJob<T extends Job>(
    kind: string,
    getOperationId: OperationId,
    options: JobOptions,
    start: (request: IdempotentCallOptions) => Promise<T>,
  ): Promise<T> {
    const { wait = true, timeout, pollInterval, ...request } = options;
    if (!wait) return start({ ...request, timeout });
    const waitTimeout = timeout ?? DEFAULT_WAIT_TIMEOUT;
    const deadline = Date.now() + waitTimeout;
    const job = await start({ ...request, timeout: this.requestTimeout(deadline) });
    return this.finish(kind, getOperationId, job, waitTimeout, deadline, {
      signal: request.signal,
      pollInterval,
    });
  }

  protected async waitForJob<T extends Job>(
    kind: string,
    getOperationId: OperationId,
    id: string,
    options: WaitOptions,
  ): Promise<T> {
    const waitTimeout = options.timeout ?? DEFAULT_WAIT_TIMEOUT;
    const deadline = Date.now() + waitTimeout;
    const job = await this.getJob<T>(getOperationId, id, deadline, options.signal);
    return this.finish(kind, getOperationId, job, waitTimeout, deadline, options);
  }

  /** Polls a job until it is finished; a job that ends as failed throws. */
  private async finish<T extends Job>(
    kind: string,
    getOperationId: OperationId,
    started: T,
    waitTimeout: number,
    deadline: number,
    options: { signal?: AbortSignal; pollInterval?: number },
  ): Promise<T> {
    const { log } = this.http.config;
    let job = started;
    let status = job.status;
    if (!job.finished) log.info(`Waiting for ${kind} ${job.id}, now ${status}`);
    let interval = options.pollInterval ?? INITIAL_POLL_INTERVAL;
    while (!job.finished) {
      const remaining = deadline - Date.now();
      if (remaining <= 0) {
        throw new WaitTimeoutError(
          `${kind} ${job.id} is still ${job.status} after ${waitTimeout / 1000}s. ` +
            'It keeps running on Extralt; wait() with its id resumes waiting.',
          job,
        );
      }
      await sleep(Math.min(interval, remaining), options.signal);
      if (options.pollInterval === undefined) {
        interval = Math.min(interval * 1.5, MAX_POLL_INTERVAL);
      }
      job = await this.getJob<T>(getOperationId, job.id, deadline, options.signal);
      if (job.status !== status) {
        status = job.status;
        log.info(`${kind} ${job.id} is ${status}`);
      }
    }
    if (FAILED_STATUSES.has(job.status)) {
      const reason = job.status_reason ? `: ${job.status_reason}` : '';
      throw new JobFailedError(`${kind} ${job.id} ended as ${job.status}${reason}`, job);
    }
    return job;
  }

  private getJob<T extends Job>(
    operationId: OperationId,
    id: string,
    deadline: number,
    signal: AbortSignal | undefined,
  ): Promise<T> {
    return this.http.request(operationId, {
      path: { id },
      signal,
      timeout: this.requestTimeout(deadline),
    } as unknown as RequestOptions<OperationId>) as unknown as Promise<T>;
  }

  /** One request never outlasts the client's timeout or what is left of the wait. */
  private requestTimeout(deadline: number): number {
    return Math.max(Math.min(this.http.config.timeout, deadline - Date.now()), 1);
  }
}
