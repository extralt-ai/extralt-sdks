import { BinaryResponse } from '../core/binary.js';
import type { HTTP } from '../core/http.js';
import { Paginator } from '../core/pagination.js';
import { type JobOptions, Resource, type WaitOptions } from '../core/resource.js';
import {
  type Budget,
  budgetLimit,
  type CallOptions,
  type IdempotentCallOptions,
  type QueryParams,
  type RawBody,
} from '../core/types.js';
import type {
  Capture,
  Import,
  Robot,
  RobotCreateParams,
  Run,
  RunCreateParams as RunCreateBody,
  RunRestartParams,
  RunSummary,
  Schedule,
  ScheduleCreateParams as ScheduleCreateBody,
  ScheduleUpdateParams as ScheduleUpdateBody,
} from '../generated/openapi.js';

/** A Run to start. `budget` is the most Captures to produce, or `'unlimited'`. */
export type RunCreateParams = Omit<RunCreateBody, 'budget'> & { budget: Budget };
/** A Schedule to create. `budget` limits each of its Runs, or is `'unlimited'`. */
export type ScheduleCreateParams = Omit<ScheduleCreateBody, 'budget'> & { budget: Budget };
/** The fields to change. `budget: 'unlimited'` removes the limit. */
export type ScheduleUpdateParams = Omit<ScheduleUpdateBody, 'budget'> & { budget?: Budget };

/** Robots, Runs, Schedules, Captures and Imports. */
export class Extract {
  readonly robots: Robots;
  readonly runs: Runs;
  readonly schedules: Schedules;
  readonly captures: Captures;
  readonly imports: Imports;

  constructor(http: HTTP) {
    this.robots = new Robots(http);
    this.runs = new Runs(http);
    this.schedules = new Schedules(http);
    this.captures = new Captures(http);
    this.imports = new Imports(http);
  }
}

export class Robots extends Resource {
  /**
   * Creates a Robot for a store and country, or returns the existing one, once it is built. A new
   * Robot is ready at once when an earlier build of the same store exists; otherwise the call
   * waits for its build and throws `JobFailedError` if the build fails. Pass `wait: false` to
   * return the queued Robot.
   */
  create(params: RobotCreateParams, options: JobOptions = {}): Promise<Robot> {
    return this.startJob('Robot', 'get_robot', options, (request) =>
      this.http.request('create_robot', { body: params, ...request }),
    );
  }

  list(
    query: QueryParams<'list_robots'> = {},
    options: CallOptions = {},
  ): Paginator<'list_robots', Robot> {
    return new Paginator(this.http, 'list_robots', { query, ...options }, (page) => page.data);
  }

  get(id: string, options: CallOptions = {}): Promise<Robot> {
    return this.http.request('get_robot', { path: { id }, ...options });
  }

  async delete(id: string, options: CallOptions = {}): Promise<void> {
    await this.http.request('delete_robot', { path: { id }, ...options });
  }

  /** Waits until the Robot is built. Throws `JobFailedError` if its build failed. */
  wait(id: string, options: WaitOptions = {}): Promise<Robot> {
    return this.waitForJob('Robot', 'get_robot', id, options);
  }
}

export class Runs extends Resource {
  /**
   * Runs a completed Robot and returns the finished Run. The call waits up to `timeout`
   * milliseconds (one hour by default) and throws `JobFailedError` if the Run fails. Pass
   * `wait: false` to return the started Run at once.
   */
  create(params: RunCreateParams, options: JobOptions = {}): Promise<Run> {
    return this.startJob('Run', 'get_run', options, async (request) =>
      this.http.request('create_run', {
        body: { ...params, budget: budgetLimit(params.budget) },
        ...request,
      }),
    );
  }

  /**
   * Lists Runs, newest first. With `finished_since`, lists only the Runs finished at or after
   * that time, oldest finish first: pass the last `finished_at` you processed.
   */
  list(
    query: QueryParams<'list_runs'> = {},
    options: CallOptions = {},
  ): Paginator<'list_runs', RunSummary> {
    return new Paginator(this.http, 'list_runs', { query, ...options }, (page) => page.data);
  }

  get(id: string, options: CallOptions = {}): Promise<Run> {
    return this.http.request('get_run', { path: { id }, ...options });
  }

  /**
   * Restarts a finished Run, optionally with a new budget, and returns it finished again. Waits
   * and throws like `create()`; pass `wait: false` to return at once.
   */
  restart(id: string, params: RunRestartParams = {}, options: JobOptions = {}): Promise<Run> {
    return this.startJob('Run', 'get_run', options, (request) =>
      this.http.request('restart_run', { path: { id }, body: params, ...request }),
    );
  }

  /** Requests cancellation. The Run may finish its current work before it is `stopped`. */
  stop(id: string, options: CallOptions = {}): Promise<Run> {
    return this.http.request('stop_run', { path: { id }, ...options });
  }

  /** Waits until the Run is completed or stopped. Throws `JobFailedError` if it failed. */
  wait(id: string, options: WaitOptions = {}): Promise<Run> {
    return this.waitForJob('Run', 'get_run', id, options);
  }
}

export class Schedules extends Resource {
  /** Schedules Runs of a completed Robot. `budget` limits each Run, as in `runs.create`. */
  async create(
    params: ScheduleCreateParams,
    options: IdempotentCallOptions = {},
  ): Promise<Schedule> {
    return this.http.request('create_schedule', {
      body: { ...params, budget: budgetLimit(params.budget) },
      ...options,
    });
  }

  list(
    query: QueryParams<'list_schedules'> = {},
    options: CallOptions = {},
  ): Paginator<'list_schedules', Schedule> {
    return new Paginator(this.http, 'list_schedules', { query, ...options }, (page) => page.data);
  }

  get(id: string, options: CallOptions = {}): Promise<Schedule> {
    return this.http.request('get_schedule', { path: { id }, ...options });
  }

  /**
   * Changes only the fields given. `start_urls: null` clears the start URLs and
   * `budget: 'unlimited'` removes the limit.
   */
  async update(
    id: string,
    { budget, ...params }: ScheduleUpdateParams,
    options: CallOptions = {},
  ): Promise<Schedule> {
    const body: ScheduleUpdateBody =
      budget === undefined ? params : { ...params, budget: budgetLimit(budget) ?? null };
    return this.http.request('update_schedule', { path: { id }, body, ...options });
  }

  pause(id: string, options: CallOptions = {}): Promise<Schedule> {
    return this.http.request('pause_schedule', { path: { id }, ...options });
  }

  resume(id: string, options: CallOptions = {}): Promise<Schedule> {
    return this.http.request('resume_schedule', { path: { id }, ...options });
  }

  async delete(id: string, options: CallOptions = {}): Promise<void> {
    await this.http.request('delete_schedule', { path: { id }, ...options });
  }
}

export class Captures extends Resource {
  /** Lists the Captures of one Run or Import. */
  list(
    query: QueryParams<'list_captures'>,
    options: CallOptions = {},
  ): Paginator<'list_captures', Capture> {
    return new Paginator(this.http, 'list_captures', { query, ...options }, (page) => page.data);
  }

  async count(query: QueryParams<'count_captures'>, options: CallOptions = {}): Promise<number> {
    const result = await this.http.request('count_captures', { query, ...options });
    return result.count;
  }

  /** Streams every Capture of a Run or Import as Parquet (default) or JSON Lines. */
  async export(
    query: QueryParams<'export_captures'>,
    options: CallOptions = {},
  ): Promise<BinaryResponse> {
    return new BinaryResponse(await this.http.send('export_captures', { query, ...options }));
  }
}

/** Where an uploaded catalog comes from and how to read it. */
export type ImportCreateQuery = QueryParams<'create_import'> & {
  /** Defaults to the Blob's type, then `application/octet-stream`. */
  contentType?: string;
};

export class Imports extends Resource {
  /**
   * Uploads a catalog file and returns the finished Import. In Node.js, pass
   * `await fs.openAsBlob(path)` to stream it from disk. The call waits and throws `JobFailedError`
   * if the Import fails or its file is rejected. Pass `wait: false` to return at once.
   */
  create(
    file: Blob | ArrayBuffer | ArrayBufferView | ReadableStream<Uint8Array>,
    { contentType, ...query }: ImportCreateQuery = {},
    options: JobOptions = {},
  ): Promise<Import> {
    const type =
      contentType ?? (file instanceof Blob && file.type ? file.type : 'application/octet-stream');
    return this.startJob('Import', 'get_import', options, (request) =>
      this.http.request('create_import', {
        query,
        body: file as RawBody,
        headers: { 'Content-Type': type },
        ...request,
      }),
    );
  }

  get(id: string, options: CallOptions = {}): Promise<Import> {
    return this.http.request('get_import', { path: { id }, ...options });
  }

  /** Waits until the Import is completed. Throws `JobFailedError` if it failed. */
  wait(id: string, options: WaitOptions = {}): Promise<Import> {
    return this.waitForJob('Import', 'get_import', id, options);
  }
}
