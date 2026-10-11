import type { HTTP } from './http.js';
import type { OperationId, RequestOptions, SuccessBody } from './types.js';

/**
 * Iterates every item of a cursor-paginated list across pages: `for await (const item of list)`.
 * Use `pages()` for whole pages or `firstPage()` for a single request.
 */
export class Paginator<K extends OperationId, Item> implements AsyncIterable<Item> {
  readonly #http: HTTP;
  readonly #operationId: K;
  readonly #options: RequestOptions<K>;
  readonly #items: (page: SuccessBody<K>) => Item[];

  constructor(
    http: HTTP,
    operationId: K,
    options: RequestOptions<K>,
    items: (page: SuccessBody<K>) => Item[],
  ) {
    this.#http = http;
    this.#operationId = operationId;
    this.#options = options;
    this.#items = items;
  }

  firstPage(): Promise<SuccessBody<K>> {
    return this.#http.request(this.#operationId, this.#options);
  }

  async *pages(): AsyncGenerator<SuccessBody<K>, void, undefined> {
    const query = (this.#options.query ?? {}) as { cursor?: string };
    let cursor = query.cursor;
    while (true) {
      const page = await this.#http.request(this.#operationId, {
        ...this.#options,
        query: { ...query, cursor },
      } as RequestOptions<K>);
      yield page;
      cursor = (page as { next_cursor?: string | null }).next_cursor ?? undefined;
      if (!cursor) return;
    }
  }

  async *[Symbol.asyncIterator](): AsyncGenerator<Item, void, undefined> {
    for await (const page of this.pages()) yield* this.#items(page);
  }
}
