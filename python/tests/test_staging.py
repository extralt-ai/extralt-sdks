"""End-to-end flows against the staging API. Run with `uv run pytest -m staging`.

They need EXTRALT_API_KEY for a staging organization with at least one completed Robot. Each run
creates one Run with a budget of one Capture, enriches it, and creates one Schedule that is deleted
before it can run. Explore is only read, scoped by the first Store with a known currency.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import uuid

import pytest

from extralt import Extralt, NotFoundError
from extralt.types import Robot

pytestmark = pytest.mark.staging

BASE_URL = os.environ.get("EXTRALT_STAGING_URL", "https://api.extralt.dev")


@pytest.fixture(scope="module")
def client() -> Extralt:
    if not os.environ.get("EXTRALT_API_KEY"):
        pytest.skip("EXTRALT_API_KEY is not set")
    return Extralt(base_url=BASE_URL)


@pytest.fixture(scope="module")
def robot(client: Extralt) -> Robot:
    for candidate in client.extract.robots.list(limit=100):
        if candidate.status == "completed":
            return candidate
    pytest.skip("the staging organization has no completed Robot")


def test_reads_robots_and_runs(client: Extralt, robot: Robot) -> None:
    assert client.extract.robots.get(robot.id).id == robot.id
    first = client.extract.runs.list(limit=5).first_page()
    for run in first.data:
        assert client.extract.runs.get(run.id).id == run.id


def test_schedule_lifecycle(client: Extralt, robot: Robot) -> None:
    schedule = client.extract.schedules.create(
        robot_id=robot.id,
        cadence={"interval_amount": 1, "interval_unit": "month"},
        name=f"SDK smoke {uuid.uuid4().hex[:8]}",
        budget=1,
    )
    try:
        assert schedule.enabled
        assert client.extract.schedules.get(schedule.id).name == schedule.name
        updated = client.extract.schedules.update(
            schedule.id, budget="unlimited", auto_enrich=False
        )
        assert updated.budget is None
        assert client.extract.schedules.pause(schedule.id).enabled is False
        assert client.extract.schedules.resume(schedule.id).enabled is True
    finally:
        client.extract.schedules.delete(schedule.id)
    with pytest.raises(NotFoundError):
        client.extract.schedules.get(schedule.id)


def test_run_to_captures(client: Extralt, robot: Robot) -> None:
    started = client.extract.runs.create(robot_id=robot.id, budget=1, auto_enrich=False, wait=False)
    assert started.finished is False
    run = client.extract.runs.wait(started.id, timeout=900)
    assert run.status in {"completed", "stopped"}

    count = client.extract.captures.count(run_id=run.id)
    captures = list(client.extract.captures.list(run_id=run.id, limit=10))
    assert len(captures) == count
    with client.extract.captures.export(run_id=run.id, format="jsonl") as export:
        lines = b"".join(export.iter_bytes()).splitlines()
    assert len(lines) == count

    if count == 0:
        pytest.skip("the Run produced no Capture to enrich")
    enrichment = client.enrich.enrichments.start(
        source={"kind": "run", "id": run.id}, budget=1, timeout=900
    )
    assert enrichment.finished
    items = list(client.enrich.items.list(enrichment_id=enrichment.id))
    for item in items[:1]:
        detail = client.enrich.items.get(item.id, enrichment_id=enrichment.id)
        assert detail.id == item.id


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
