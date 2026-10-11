/**
 * End-to-end reads against the staging API: `bun run test:staging` with EXTRALT_API_KEY for a
 * staging organization that already has Robots, Runs with Captures and Enrichments. Tests skip
 * where it has none. They only read. Never add a call here that creates, changes or deletes
 * anything: the mocked tests cover those requests.
 */
import { beforeAll, describe, expect, it } from 'vitest';
import { Extralt } from '../src/index.js';

const enabled = process.env.EXTRALT_STAGING === '1' && Boolean(process.env.EXTRALT_API_KEY);

describe.runIf(enabled)('staging', () => {
  const client = new Extralt({
    baseURL: process.env.EXTRALT_STAGING_URL ?? 'https://api.extralt.dev',
  });

  beforeAll(async () => {
    await client.extract.robots.list({ limit: 1 }).firstPage();
  }, 60_000); // the first request can wake an idle staging API

  it('reads Robots', async ({ skip }) => {
    const page = await client.extract.robots.list({ limit: 5 }).firstPage();
    if (page.data.length === 0) skip('the staging organization has no Robot');
    for (const robot of page.data) {
      expect((await client.extract.robots.get(robot.id)).id).toBe(robot.id);
    }
  });

  it('reads Schedules', async ({ skip }) => {
    const page = await client.extract.schedules.list({ limit: 5 }).firstPage();
    if (page.data.length === 0) skip('the staging organization has no Schedule');
    for (const schedule of page.data) {
      expect((await client.extract.schedules.get(schedule.id)).id).toBe(schedule.id);
    }
  });

  it('reads Runs and their Captures', { timeout: 300_000 }, async ({ skip }) => {
    const runs = (await client.extract.runs.list({ limit: 50 }).firstPage()).data;
    for (const run of runs.slice(0, 5)) {
      expect((await client.extract.runs.get(run.id)).id).toBe(run.id);
    }

    // The smallest finished Run keeps the export short.
    const [run] = runs
      .filter((run) => run.finished && run.extracted > 0)
      .sort((a, b) => a.extracted - b.extracted);
    if (!run) return skip('the staging organization has no finished Run with Captures');

    const count = await client.extract.captures.count({ run_id: run.id });
    const page = await client.extract.captures.list({ run_id: run.id, limit: 10 }).firstPage();
    expect(page.data).toHaveLength(Math.min(count, 10));
    const exported = await client.extract.captures.export({ run_id: run.id, format: 'jsonl' });
    const lines = (await exported.text()).split('\n').filter(Boolean);
    expect(lines).toHaveLength(count);
  });

  it('reads Enrichments and their Items', { timeout: 300_000 }, async ({ skip }) => {
    const enrichments = (await client.enrich.enrichments.list({ limit: 20 }).firstPage()).data;
    if (enrichments.length === 0) skip('the staging organization has no Enrichment');
    for (const enrichment of enrichments.slice(0, 5)) {
      expect((await client.enrich.enrichments.get(enrichment.id)).id).toBe(enrichment.id);
    }

    for (const enrichment of enrichments) {
      const scope = { enrichment_id: enrichment.id };
      const [item] = (await client.enrich.items.list({ ...scope, limit: 5 }).firstPage()).data;
      if (item) {
        expect((await client.enrich.items.get(item.id, scope)).id).toBe(item.id);
        return;
      }
    }
    skip('no recent Enrichment in the staging organization has Items');
  });

  it('reads Explore', { timeout: 300_000 }, async () => {
    const now = new Date();
    const daysAgo = (days: number) => new Date(now.getTime() - days * 86_400_000).toISOString();
    expect((await client.explore.overview.get()).totals).toBeDefined();
    expect((await client.explore.relationships.get()).products).toBeGreaterThanOrEqual(0);
    const activity = await client.explore.activity.get({ from: daysAgo(7), bucket: 'day' });
    expect(activity.buckets.length).toBeGreaterThanOrEqual(7);
    await client.explore.activity.events({ from: daysAgo(7), kind: 'price_decrease', limit: 3 });
    const changes = await client.explore.changes
      .list({ window: '1w', to: now.toISOString(), summary_only: true })
      .firstPage();
    expect(changes.data).toEqual([]);
    expect(changes.next_cursor).toBeNull();

    const stores = (await client.explore.stores.list()).stores.filter((s) => s.currencies.length);
    const store = stores[0];
    if (!store) return;
    const { country } = store;
    const currency = store.currencies[0] as string;
    const match = await client.explore.entities.lookup({ kind: 'store', id: store.store_id });
    expect(match.data.map((option) => option.id)).toEqual([store.store_id]);
    expect((await client.explore.facets.get({ country })).countries.length).toBeGreaterThan(0);

    const position = await client.explore.analyses
      .pricePosition({ reference_store_id: store.store_id, country, currency, limit: 5 })
      .firstPage();
    expect(position.analysis_id).toBe('price_position');
    const movements = await client.explore.analyses
      .priceMovements({ from: daysAgo(7), country, currency, store_id: store.store_id, limit: 5 })
      .firstPage();
    expect(movements.analysis_id).toBe('price_movements');
    const availability = await client.explore.analyses
      .availabilityChanges({ from: daysAgo(7), country, store_id: store.store_id, limit: 5 })
      .firstPage();
    expect(availability.analysis_id).toBe('availability_changes');
    const other = stores.find((s) => s.country === country && s.store_id !== store.store_id);
    if (other) {
      const overlap = await client.explore.analyses
        .assortmentOverlap({
          reference_store_id: store.store_id,
          comparison_store_id: other.store_id,
          country,
          limit: 5,
        })
        .firstPage();
      expect(overlap.analysis_id).toBe('assortment_overlap');
    }

    const market = await client.explore.markets
      .list({ country, store_id: store.store_id, limit: 1 })
      .firstPage();
    for (const row of market.data) {
      const variant = await client.explore.variants.get(row.variant_id);
      expect(variant.variant_id).toBe(row.variant_id);
      expect(variant.reviews.scope_count).toBeGreaterThanOrEqual(0);
      await client.explore.variants.offers(row.variant_id, { limit: 5 }).firstPage();
      const scope = {
        from: daysAgo(30),
        to: now.toISOString(),
        country: row.country,
        currency: row.currency,
        condition: row.condition,
      };
      const series = await client.explore.variants.priceSeries(row.variant_id, scope);
      expect(series.scope.variant_id).toBe(row.variant_id);
      const history = await client.explore.variants
        .history(row.variant_id, { ...scope, limit: 10 })
        .firstPage();
      expect(history.data.length).toBeLessThanOrEqual(10);
    }
  });

  it('runs SQL queries', { timeout: 120_000 }, async () => {
    const model = await client.query.model({ entities: ['captures'] });
    expect(model.entities.map((entity) => entity.table)).toEqual(['extralt.captures']);

    const sql = 'SELECT count() AS captures FROM extralt.captures FINAL';
    const result = await client.query.run({ sql });
    expect([result.count, result.truncated]).toEqual([1, false]);
    const exported = await client.query.export({ sql, format: 'jsonl' });
    const lines = (await exported.text()).split('\n').filter(Boolean);
    expect(lines.map((line) => JSON.parse(line))).toEqual(result.rows);
  });
});
