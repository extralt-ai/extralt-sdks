import { BinaryResponse } from '../core/binary.js';
import type { HTTP } from '../core/http.js';
import { Paginator } from '../core/pagination.js';
import { type JobOptions, Resource, type WaitOptions } from '../core/resource.js';
import type { CallOptions, QueryParams } from '../core/types.js';
import type { Enrichment, EnrichmentCreateParams, Item } from '../generated/openapi.js';

/** Enrichments and the Items they produce. */
export class Enrich {
  readonly enrichments: Enrichments;
  readonly items: Items;

  constructor(http: HTTP) {
    this.enrichments = new Enrichments(http);
    this.items = new Items(http);
  }
}

export class Enrichments extends Resource {
  /**
   * Enriches the Captures of a Run or Import and returns the finished Enrichment. The call
   * starts, or continues, the Enrichment, waits and throws `JobFailedError` if it fails. Pass
   * `wait: false` to return at once.
   */
  start(params: EnrichmentCreateParams, options: JobOptions = {}): Promise<Enrichment> {
    return this.startJob('Enrichment', 'get_enrichment', options, (request) =>
      this.http.request('start_enrichment', { body: params, ...request }),
    );
  }

  /**
   * Lists Enrichments, newest first. `source_id` keeps the Enrichments of one Run or Import;
   * `finished_since` keeps only those finished at or after that time, oldest finish first. The
   * two cannot be combined.
   */
  list(
    query: QueryParams<'list_enrichments'> = {},
    options: CallOptions = {},
  ): Paginator<'list_enrichments', Enrichment> {
    return new Paginator(this.http, 'list_enrichments', { query, ...options }, (page) => page.data);
  }

  get(id: string, options: CallOptions = {}): Promise<Enrichment> {
    return this.http.request('get_enrichment', { path: { id }, ...options });
  }

  /** Requests cancellation; committed Items are still delivered before it is `stopped`. */
  stop(id: string, options: CallOptions = {}): Promise<Enrichment> {
    return this.http.request('stop_enrichment', { path: { id }, ...options });
  }

  /** Waits until the Enrichment is completed or stopped. Throws `JobFailedError` if it failed. */
  wait(id: string, options: WaitOptions = {}): Promise<Enrichment> {
    return this.waitForJob('Enrichment', 'get_enrichment', id, options);
  }
}

export class Items extends Resource {
  /** Lists the Items one Enrichment produced. */
  list(query: QueryParams<'list_items'>, options: CallOptions = {}): Paginator<'list_items', Item> {
    return new Paginator(this.http, 'list_items', { query, ...options }, (page) => page.data);
  }

  get(itemId: string, query: QueryParams<'get_item'>, options: CallOptions = {}): Promise<Item> {
    return this.http.request('get_item', { path: { item_id: itemId }, query, ...options });
  }

  /** Streams every Item of an Enrichment as Parquet (default) or JSON Lines. */
  async export(
    query: QueryParams<'export_items'>,
    options: CallOptions = {},
  ): Promise<BinaryResponse> {
    return new BinaryResponse(await this.http.send('export_items', { query, ...options }));
  }
}
