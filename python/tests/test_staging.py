"""End-to-end reads against the staging API. Run with `uv run pytest -m staging`.

They need EXTRALT_API_KEY for a staging organization that already has Robots, Runs with Captures
and Enrichments, and skip where it has none. They only read. Never add a call here that creates,
changes or deletes anything: the mocked tests cover those requests.
"""

from __future__ import annotations

import datetime as dt
import json
import os

import pytest

from extralt import Extralt

pytestmark = pytest.mark.staging

BASE_URL = os.environ.get("EXTRALT_STAGING_URL", "https://api.extralt.dev")


@pytest.fixture(scope="module")
def client() -> Extralt:
    if not os.environ.get("EXTRALT_API_KEY"):
        pytest.skip("EXTRALT_API_KEY is not set")
    return Extralt(base_url=BASE_URL)


def test_reads_robots(client: Extralt) -> None:
    robots = client.extract.robots.list(limit=5).first_page().data
    if not robots:
        pytest.skip("the staging organization has no Robot")
    for robot in robots:
        assert client.extract.robots.get(robot.id).id == robot.id


def test_reads_schedules(client: Extralt) -> None:
    schedules = client.extract.schedules.list(limit=5).first_page().data
    if not schedules:
        pytest.skip("the staging organization has no Schedule")
    for schedule in schedules:
        assert client.extract.schedules.get(schedule.id).id == schedule.id


def test_reads_runs_and_their_captures(client: Extralt) -> None:
    runs = client.extract.runs.list(limit=50).first_page().data
    for run in runs[:5]:
        assert client.extract.runs.get(run.id).id == run.id

    # The smallest finished Run keeps the export short.
    with_captures = [run for run in runs if run.finished and run.extracted > 0]
    if not with_captures:
        pytest.skip("the staging organization has no finished Run with Captures")
    run = min(with_captures, key=lambda run: run.extracted)

    count = client.extract.captures.count(run_id=run.id)
    page = client.extract.captures.list(run_id=run.id, limit=10).first_page()
    assert len(page.data) == min(count, 10)
    with client.extract.captures.export(run_id=run.id, format="jsonl") as export:
        lines = b"".join(export.iter_bytes()).splitlines()
    assert len(lines) == count


def test_reads_enrichments_and_their_items(client: Extralt) -> None:
    enrichments = client.enrich.enrichments.list(limit=20).first_page().data
    if not enrichments:
        pytest.skip("the staging organization has no Enrichment")
    for enrichment in enrichments[:5]:
        assert client.enrich.enrichments.get(enrichment.id).id == enrichment.id

    for enrichment in enrichments:
        items = client.enrich.items.list(enrichment_id=enrichment.id, limit=5).first_page().data
        if items:
            detail = client.enrich.items.get(items[0].id, enrichment_id=enrichment.id)
            assert detail.id == items[0].id
            return
    pytest.skip("no recent Enrichment in the staging organization has Items")


def test_reads_explore(client: Extralt) -> None:
    now = dt.datetime.now(dt.UTC)
    week_ago = now - dt.timedelta(days=7)
    assert client.explore.overview.get().totals is not None
    assert client.explore.relationships.get().products >= 0
    activity = client.explore.activity.get(from_=week_ago, bucket="day")
    assert len(activity.buckets) >= 7
    client.explore.activity.events(from_=week_ago, kind="price_decrease", limit=3)
    changes = client.explore.changes.list(window="1w", to=now, summary_only=True).first_page()
    assert changes.data == []
    assert changes.next_cursor is None

    stores = [store for store in client.explore.stores.list().stores if store.currencies]
    if not stores:
        pytest.skip("the staging organization has no Explore Store with a known currency")
    store = stores[0]
    country, currency = store.country, store.currencies[0]
    match = client.explore.entities.lookup(kind="store", id=store.store_id)
    assert [option.id for option in match.data] == [store.store_id]
    assert client.explore.facets.get(country=country).countries

    position = client.explore.analyses.price_position(
        reference_store_id=store.store_id, country=country, currency=currency, limit=5
    ).first_page()
    assert position.analysis_id == "price_position"
    movements = client.explore.analyses.price_movements(
        from_=week_ago, country=country, currency=currency, store_id=store.store_id, limit=5
    ).first_page()
    assert movements.analysis_id == "price_movements"
    availability = client.explore.analyses.availability_changes(
        from_=week_ago, country=country, store_id=store.store_id, limit=5
    ).first_page()
    assert availability.analysis_id == "availability_changes"
    others = [other for other in stores if other.country == country and other is not store]
    if others:
        overlap = client.explore.analyses.assortment_overlap(
            reference_store_id=store.store_id,
            comparison_store_id=others[0].store_id,
            country=country,
            limit=5,
        ).first_page()
        assert overlap.analysis_id == "assortment_overlap"

    market = client.explore.markets.list(country=country, store_id=store.store_id, limit=1)
    for row in market.first_page().data:
        variant = client.explore.variants.get(row.variant_id)
        assert variant.variant_id == row.variant_id
        assert variant.reviews.scope_count >= 0
        offers = client.explore.variants.offers(row.variant_id, limit=5).first_page()
        assert all(offer.observed_at for offer in offers.data)
        month_ago = now - dt.timedelta(days=30)
        series = client.explore.variants.price_series(
            row.variant_id,
            from_=month_ago,
            to=now,
            country=row.country,
            currency=row.currency,
            condition=row.condition,
        )
        assert series.scope.variant_id == row.variant_id
        history = client.explore.variants.history(
            row.variant_id,
            from_=month_ago,
            to=now,
            country=row.country,
            currency=row.currency,
            condition=row.condition,
            limit=10,
        ).first_page()
        assert len(history.data) <= 10


def test_runs_sql_queries(client: Extralt) -> None:
    model = client.query.model(entities=["captures"])
    assert [entity.table for entity in model.entities] == ["extralt.captures"]

    sql = "SELECT count() AS captures FROM extralt.captures FINAL"
    result = client.query.run(sql)
    assert (result.count, result.truncated) == (1, False)
    with client.query.export(sql, format="jsonl") as export:
        lines = b"".join(export.iter_bytes()).splitlines()
    assert [json.loads(line) for line in lines] == result.rows
