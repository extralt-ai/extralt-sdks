import { describe, expect, it } from 'vitest';
import { Extralt } from '../src/index.js';
import { assertRequestMatches, example, operations, successResponse } from './spec.js';

const START = '2026-01-01T00:00:00Z';
const LATER = '2026-01-31T00:00:00Z';

type Call = (client: Extralt) => Promise<unknown>;
const CALLS: Record<string, Call> = {
  create_robot: (c) =>
    c.extract.robots.create({ url: 'https://example.com', country: 'US' }, { wait: false }),
  list_robots: (c) => c.extract.robots.list({ limit: 10 }).firstPage(),
  get_robot: (c) => c.extract.robots.get('robot_1'),
  delete_robot: (c) => c.extract.robots.delete('robot_1'),
  create_run: (c) =>
    c.extract.runs.create(
      { robot_id: 'robot_1', start_urls: ['https://example.com/a'], budget: 5, auto_enrich: true },
      { wait: false },
    ),
  list_runs: (c) => c.extract.runs.list({ limit: 10, cursor: 'c' }).firstPage(),
  get_run: (c) => c.extract.runs.get('run_1'),
  restart_run: (c) => c.extract.runs.restart('run_1', { budget: 3 }, { wait: false }),
  stop_run: (c) => c.extract.runs.stop('run_1'),
  create_schedule: (c) =>
    c.extract.schedules.create({
      robot_id: 'robot_1',
      cadence: { interval_amount: 1, interval_unit: 'day' },
      name: 'Daily',
      budget: 10,
    }),
  list_schedules: (c) => c.extract.schedules.list().firstPage(),
  get_schedule: (c) => c.extract.schedules.get('schedule_1'),
  update_schedule: (c) =>
    c.extract.schedules.update('schedule_1', {
      cadence: { interval_amount: 2, interval_unit: 'week' },
      budget: 'unlimited',
    }),
  pause_schedule: (c) => c.extract.schedules.pause('schedule_1'),
  resume_schedule: (c) => c.extract.schedules.resume('schedule_1'),
  delete_schedule: (c) => c.extract.schedules.delete('schedule_1'),
  list_captures: (c) => c.extract.captures.list({ run_id: 'run_1' }).firstPage(),
  count_captures: (c) => c.extract.captures.count({ import_id: 'import_1' }),
  export_captures: async (c) =>
    (await c.extract.captures.export({ run_id: 'run_1', format: 'jsonl' })).arrayBuffer(),
  create_import: (c) =>
    c.extract.imports.create(
      new Blob(['sku,title\n1,Shoe\n'], { type: 'text/csv' }),
      { file_name: 'catalog.csv', country: 'US' },
      { wait: false },
    ),
  get_import: (c) => c.extract.imports.get('import_1'),
  start_enrichment: (c) =>
    c.enrich.enrichments.start(
      { source: { kind: 'run', id: 'run_1' }, budget: 50 },
      { wait: false },
    ),
  list_enrichments: (c) => c.enrich.enrichments.list({ limit: 10 }).firstPage(),
  get_enrichment: (c) => c.enrich.enrichments.get('enrichment_1'),
  stop_enrichment: (c) => c.enrich.enrichments.stop('enrichment_1'),
  list_items: (c) => c.enrich.items.list({ enrichment_id: 'enrichment_1' }).firstPage(),
  get_item: (c) => c.enrich.items.get('1', { enrichment_id: 'enrichment_1' }),
  get_overview: (c) => c.explore.overview.get(),
  get_facets: (c) => c.explore.facets.get({ country: 'US', condition: 'new', limit: 20 }),
  get_activity: (c) => c.explore.activity.get({ from: START, bucket: 'day' }),
  list_activity_events: (c) =>
    c.explore.activity.events({ from: START, to: LATER, kind: 'new_low', limit: 5 }),
  list_stores: (c) => c.explore.stores.list({ max_staleness_days: 30 }),
  lookup_entities: (c) => c.explore.entities.lookup({ kind: 'listing', search: 'shoe' }),
  get_relationships: (c) => c.explore.relationships.get({ from: START, to: LATER }),
  list_changes: (c) =>
    c.explore.changes
      .list({ window: '1d', to: START, event: 'price_changed', condition: 'unknown', limit: 50 })
      .firstPage(),
  list_market_variants: (c) =>
    c.explore.markets.list({ country: 'US', sort: 'lowest_price_asc', limit: 25 }).firstPage(),
  get_variant: (c) => c.explore.variants.get('9007199254740993'),
  list_variant_offers: (c) => c.explore.variants.offers('1', { limit: 25 }).firstPage(),
  list_variant_history: (c) =>
    c.explore.variants
      .history('1', {
        from: START,
        to: LATER,
        country: 'US',
        currency: 'USD',
        condition: 'new',
        interval: 'raw',
      })
      .firstPage(),
  get_variant_price_series: (c) =>
    c.explore.variants.priceSeries('1', {
      from: START,
      to: LATER,
      country: 'US',
      currency: 'USD',
      condition: 'new',
    }),
  analyze_price_position: (c) =>
    c.explore.analyses
      .pricePosition({ reference_store_id: 'store_1', country: 'US', currency: 'USD' })
      .firstPage(),
  analyze_price_movements: (c) =>
    c.explore.analyses
      .priceMovements({
        from: START,
        country: 'US',
        currency: 'USD',
        sort: 'absolute_change_desc',
      })
      .firstPage(),
  analyze_availability_changes: (c) =>
    c.explore.analyses
      .availabilityChanges({ from: START, country: 'US', condition: 'new' })
      .firstPage(),
  analyze_assortment_overlap: (c) =>
    c.explore.analyses
      .assortmentOverlap({
        reference_store_id: 'store_1',
        comparison_store_id: 'store_2',
        country: 'US',
      })
      .firstPage(),
  run_query: (c) => c.query.run({ sql: 'SELECT count() FROM extralt.current_offers' }),
  export_query: async (c) =>
    (
      await c.query.export({ sql: 'SELECT id FROM extralt.listings', format: 'jsonl' })
    ).arrayBuffer(),
  get_query_model: (c) => c.query.model({ entities: ['listings', 'current_offers'] }),
  create_webhook: (c) =>
    c.webhooks.create({
      url: 'https://hooks.example.com/extralt',
      event_types: ['run.completed', 'run.failed'],
      description: 'Price alerts workflow',
    }),
  list_webhooks: (c) => c.webhooks.list(),
  get_webhook: (c) => c.webhooks.get('webhook_1'),
  delete_webhook: (c) => c.webhooks.delete('webhook_1'),
  test_webhook: (c) => c.webhooks.test('webhook_1'),
};

function client(operationId: string, future: boolean, sent: Request[] = []): Extralt {
  const { status, schema } = successResponse(operationId);
  return new Extralt({
    apiKey: 'k',
    fetch: async (input, init) => {
      sent.push(new Request(input, init));
      if (!schema) return new Response(status === 204 ? null : 'binary', { status });
      return Response.json(example(schema, future), { status });
    },
  });
}

describe('contract', () => {
  it('covers every operation exactly once', () => {
    expect(Object.keys(CALLS).sort()).toEqual([...operations.keys()].sort());
  });

  it.each(Object.keys(CALLS))('%s sends a request that matches the spec', async (operationId) => {
    const sent: Request[] = [];
    await CALLS[operationId]?.(client(operationId, false, sent));
    expect(sent).toHaveLength(1);
    await assertRequestMatches(operationId, sent[0] as Request);
  });

  it.each(Object.keys(CALLS))('%s parses responses with later additions', async (operationId) => {
    const result = await CALLS[operationId]?.(client(operationId, true));
    const { schema } = successResponse(operationId);
    if (schema?.$ref && typeof result === 'object' && result !== null) {
      expect((result as Record<string, unknown>).field_added_later).toEqual({ nested: true });
    }
  });
});
