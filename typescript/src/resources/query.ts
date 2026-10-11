import { BinaryResponse } from '../core/binary.js';
import { Resource } from '../core/resource.js';
import type { CallOptions } from '../core/types.js';
import type {
  QueryDataModel,
  QueryExportParams,
  QueryResult,
  QueryRunParams,
} from '../generated/openapi.js';

/** The entities to describe; all of them when omitted. */
export interface QueryModelParams {
  entities?: string[];
}

/** Read-only SQL over the organization's Captures, Items and Explore tables. */
export class Query extends Resource {
  /**
   * Runs one SELECT or WITH query and returns the rows that fit in one response. `truncated` is
   * true when rows were left out: aggregate, add a LIMIT, or use `export()`. 64-bit integers and
   * decimals arrive as strings.
   */
  run(params: QueryRunParams, options: CallOptions = {}): Promise<QueryResult> {
    return this.http.request('run_query', { body: params, ...options });
  }

  /**
   * Streams every row a query selects as Parquet (default) or JSON Lines. The download must
   * finish within 35 seconds of the request.
   */
  async export(params: QueryExportParams, options: CallOptions = {}): Promise<BinaryResponse> {
    return new BinaryResponse(await this.http.send('export_query', { body: params, ...options }));
  }

  /** Describes the tables, columns, relationships and rules to write SQL against. */
  model({ entities }: QueryModelParams = {}, options: CallOptions = {}): Promise<QueryDataModel> {
    return this.http.request('get_query_model', {
      query: { entities: entities?.length ? entities.join(',') : undefined },
      ...options,
    });
  }
}
