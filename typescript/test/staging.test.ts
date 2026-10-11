/**
 * End-to-end flows against the staging API: `bun run test:staging` with EXTRALT_API_KEY for a
 * staging organization that has at least one completed Robot. Each run creates one Run with a
 * budget of one Capture, enriches it, and one Schedule that is deleted before it can run. Explore is
 * only read, scoped by the first Store with a known currency.
 */
import { beforeAll, describe, expect, it } from 'vitest';
import { Extralt, NotFoundError, type Robot } from '../src/index.js';

const enabled = process.env.EXTRALT_STAGING === '1' && Boolean(process.env.EXTRALT_API_KEY);

describe.runIf(enabled)('staging', () => {
  const client = new Extralt({
    baseURL: process.env.EXTRALT_STAGING_URL ?? 'https://api.extralt.dev',
  });
  let robot: Robot;

  beforeAll(async () => {
    for await (const candidate of client.extract.robots.list({ limit: 100 })) {
      if (candidate.status === 'completed') {
        robot = candidate;
        return;
      }
    }
    throw new Error('the staging organization has no completed Robot');
  }, 60_000); // the first request can wake an idle staging API

  it('reads Robots and Runs', async () => {
    expect((await client.extract.robots.get(robot.id)).id).toBe(robot.id);
    const page = await client.extract.runs.list({ limit: 5 }).firstPage();
    for (const run of page.data) expect((await client.extract.runs.get(run.id)).id).toBe(run.id);
  });

  it('runs a Schedule lifecycle', async () => {
    const schedule = await client.extract.schedules.create({
      robot_id: robot.id,
      cadence: { interval_amount: 1, interval_unit: 'month' },
      name: `SDK smoke ${crypto.randomUUID().slice(0, 8)}`,
      budget: 1,
    });
    try {
      expect(schedule.enabled).toBe(true);
      const updated = await client.extract.schedules.update(schedule.id, {
        budget: 'unlimited',
        auto_enrich: false,
      });
      expect(updated.budget ?? null).toBeNull();
      expect((await client.extract.schedules.pause(schedule.id)).enabled).toBe(false);
      expect((await client.extract.schedules.resume(schedule.id)).enabled).toBe(true);
    } finally {
      await client.extract.schedules.delete(schedule.id);
    }
    await expect(client.extract.schedules.get(schedule.id)).rejects.toBeInstanceOf(NotFoundError);
  });

  it('runs a Robot into Captures and Items', { timeout: 1_800_000 }, async () => {
    const started = await client.extract.runs.create(
      { robot_id: robot.id, budget: 1, auto_enrich: false },
      { wait: false },
    );
    expect(started.finished).toBe(false);
    const run = await client.extract.runs.wait(started.id, { timeout: 840_000 });
    expect(['completed', 'stopped']).toContain(run.status);

    const count = await client.extract.captures.count({ run_id: run.id });
    let listed = 0;
    for await (const _ of client.extract.captures.list({ run_id: run.id, limit: 10 })) listed += 1;
    expect(listed).toBe(count);
    const exported = await client.extract.captures.export({ run_id: run.id, format: 'jsonl' });
    const lines = (await exported.text()).split('\n').filter(Boolean);
    expect(lines).toHaveLength(count);
    if (count === 0) return;

    const enrichment = await client.enrich.enrichments.start(
      { source: { kind: 'run', id: run.id }, budget: 1 },
      { timeout: 840_000 },
    );
    expect(enrichment.finished).toBe(true);
    const page = await client.enrich.items.list({ enrichment_id: enrichment.id }).firstPage();
    for (const item of page.data.slice(0, 1)) {
      const detail = await client.enrich.items.get(item.id, { enrichment_id: enrichment.id });
      expect(detail.id).toBe(item.id);
    }
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
