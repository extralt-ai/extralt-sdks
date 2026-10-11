import type { operations } from '../generated/openapi.js';

export type OperationId = keyof operations;

type Parameters<K extends OperationId> = operations[K]['parameters'];
type IsNever<T> = [T] extends [never] ? true : false;
type JsonContent<R> = R extends { content: { 'application/json': infer Body } } ? Body : never;
type SuccessStatus = 200 | 201 | 202 | 204;

export type PathParams<K extends OperationId> = NonNullable<Parameters<K>['path']>;
export type QueryParams<K extends OperationId> = NonNullable<Parameters<K>['query']>;
export type RequestBody<K extends OperationId> = JsonContent<
  NonNullable<operations[K]['requestBody']>
>;

/** The JSON body of an operation's success response; `undefined` for `204 No Content`. */
export type SuccessBody<K extends OperationId> =
  IsNever<
    JsonContent<
      operations[K]['responses'][Extract<keyof operations[K]['responses'], SuccessStatus>]
    >
  > extends true
    ? undefined
    : JsonContent<
        operations[K]['responses'][Extract<keyof operations[K]['responses'], SuccessStatus>]
      >;

/** Per-request options accepted by every method. */
export interface CallOptions {
  /** Aborts the request, including pending retries. */
  signal?: AbortSignal;
  /** Overrides the client timeout for this request, in milliseconds. */
  timeout?: number;
}

/** A number of Captures, or `'unlimited'` to crawl until the store is done or credits run out. */
export type Budget = number | 'unlimited';

/**
 * The limit the API takes, `undefined` for no limit. Rejects a missing value, such as an unset
 * configuration entry, so that it cannot start an unlimited crawl.
 */
export function budgetLimit(budget: Budget): number | undefined {
  if (budget === 'unlimited') return undefined;
  if (typeof budget === 'number') return budget;
  throw new TypeError(`budget must be a number of Captures or 'unlimited', not ${String(budget)}`);
}

/** Options for operations that accept an `Idempotency-Key`. */
export interface IdempotentCallOptions extends CallOptions {
  /** Replaces the generated key; reuse it to retry the same request safely. */
  idempotencyKey?: string;
}

/**
 * A body sent as is, typed through the `RequestInit` global that the DOM library and @types/node
 * both declare, unlike `BodyInit`.
 */
export type RawBody = NonNullable<RequestInit['body']>;

export type RequestOptions<K extends OperationId> = (IsNever<PathParams<K>> extends true
  ? { path?: undefined }
  : { path: PathParams<K> }) &
  (IsNever<QueryParams<K>> extends true ? { query?: undefined } : { query?: QueryParams<K> }) &
  (IsNever<RequestBody<K>> extends true ? { body?: RawBody } : { body: RequestBody<K> }) &
  IdempotentCallOptions & { headers?: Record<string, string> };
