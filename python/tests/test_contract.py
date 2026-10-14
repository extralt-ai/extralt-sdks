"""Checks every SDK method against the OpenAPI snapshot it is generated from."""

from __future__ import annotations

import datetime as dt
import inspect
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from extralt import AsyncExtralt, Extralt
from extralt.types import Cadence

from . import spec


def sdk_methods(client: Extralt | AsyncExtralt) -> dict[str, str]:
    """Operation ID to the SDK method that exposes it."""
    found: dict[str, str] = {}

    def collect(path: str, resource: object) -> None:
        for name, member in inspect.getmembers(type(resource)):
            operation_id = getattr(member, "__extralt_operation__", None)
            if operation_id:
                assert operation_id not in found, f"{operation_id} has two methods"
                found[operation_id] = f"{path}.{name}"

    for area in ("extract", "enrich", "explore"):
        for resource_name, resource in vars(getattr(client, area)).items():
            collect(f"{area}.{resource_name}", resource)
    collect("query", client.query)
    collect("webhooks", client.webhooks)
    return found


@pytest.mark.parametrize("client_class", [Extralt, AsyncExtralt])
def test_every_operation_has_exactly_one_method(client_class: type) -> None:
    assert set(sdk_methods(client_class(api_key="k"))) == set(spec.operations())


START = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)

Call = Callable[[Extralt], Any]
CALLS: dict[str, Call] = {
    "create_robot": lambda c: c.extract.robots.create(
        url="https://example.com", country="US", wait=False
    ),
    "list_robots": lambda c: c.extract.robots.list(limit=10).first_page(),
    "get_robot": lambda c: c.extract.robots.get("robot_1"),
    "delete_robot": lambda c: c.extract.robots.delete("robot_1"),
    "create_run": lambda c: c.extract.runs.create(
        robot_id="robot_1",
        start_urls=["https://example.com/a"],
        budget=5,
        auto_enrich=True,
        wait=False,
    ),
    "list_runs": lambda c: c.extract.runs.list(
        finished_since="2026-01-31T00:00:00Z", limit=10, cursor="c"
    ).first_page(),
    "get_run": lambda c: c.extract.runs.get("run_1"),
    "restart_run": lambda c: c.extract.runs.restart("run_1", budget=3, wait=False),
    "stop_run": lambda c: c.extract.runs.stop("run_1"),
    "create_schedule": lambda c: c.extract.schedules.create(
        robot_id="robot_1",
        cadence=Cadence(interval_amount=1, interval_unit="day"),
        name="Daily",
        budget=10,
    ),
    "list_schedules": lambda c: c.extract.schedules.list().first_page(),
    "get_schedule": lambda c: c.extract.schedules.get("schedule_1"),
    "update_schedule": lambda c: c.extract.schedules.update(
        "schedule_1", cadence={"interval_amount": 2, "interval_unit": "week"}, budget="unlimited"
    ),
    "pause_schedule": lambda c: c.extract.schedules.pause("schedule_1"),
    "resume_schedule": lambda c: c.extract.schedules.resume("schedule_1"),
    "delete_schedule": lambda c: c.extract.schedules.delete("schedule_1"),
    "list_captures": lambda c: c.extract.captures.list(run_id="run_1").first_page(),
    "count_captures": lambda c: c.extract.captures.count(import_id="import_1"),
    "export_captures": lambda c: _export(c),
    "export_items": lambda c: _export_items(c),
    "create_import": lambda c: c.extract.imports.create(
        b"sku,title\n1,Shoe\n", file_name="catalog.csv", country="US", wait=False
    ),
    "get_import": lambda c: c.extract.imports.get("import_1"),
    "start_enrichment": lambda c: c.enrich.enrichments.start(
        source={"kind": "run", "id": "run_1"}, budget=50, wait=False
    ),
    "list_enrichments": lambda c: c.enrich.enrichments.list(
        source_id="run_1", limit=10
    ).first_page(),
    "get_enrichment": lambda c: c.enrich.enrichments.get("enrichment_1"),
    "stop_enrichment": lambda c: c.enrich.enrichments.stop("enrichment_1"),
    "list_items": lambda c: c.enrich.items.list(enrichment_id="enrichment_1").first_page(),
    "get_item": lambda c: c.enrich.items.get("1", enrichment_id="enrichment_1"),
    "get_overview": lambda c: c.explore.overview.get(),
    "get_facets": lambda c: c.explore.facets.get(country="US", condition="new", limit=20),
    "get_activity": lambda c: c.explore.activity.get(from_=START, bucket="day"),
    "list_activity_events": lambda c: c.explore.activity.events(
        from_="2026-01-01T00:00:00Z", to="2026-01-08T00:00:00Z", kind="new_low", limit=5
    ),
    "list_stores": lambda c: c.explore.stores.list(max_staleness_days=30),
    "lookup_entities": lambda c: c.explore.entities.lookup(kind="listing", search="shoe"),
    "get_relationships": lambda c: c.explore.relationships.get(
        from_=START, to=START + dt.timedelta(days=7)
    ),
    "list_changes": lambda c: c.explore.changes.list(
        window="1d", to=START, event="price_changed", condition="unknown", limit=50
    ).first_page(),
    "list_market_variants": lambda c: c.explore.markets.list(
        country="US", sort="lowest_price_asc", limit=25
    ).first_page(),
    "get_variant": lambda c: c.explore.variants.get("9007199254740993"),
    "list_variant_offers": lambda c: c.explore.variants.offers("1", limit=25).first_page(),
    "list_variant_history": lambda c: c.explore.variants.history(
        "1",
        from_=START,
        to=START + dt.timedelta(days=30),
        country="US",
        currency="USD",
        condition="new",
        interval="raw",
    ).first_page(),
    "get_variant_price_series": lambda c: c.explore.variants.price_series(
        "1",
        from_=START,
        to=START + dt.timedelta(days=30),
        country="US",
        currency="USD",
        condition="new",
    ),
    "analyze_price_position": lambda c: c.explore.analyses.price_position(
        reference_store_id="store_1", country="US", currency="USD"
    ).first_page(),
    "analyze_price_movements": lambda c: c.explore.analyses.price_movements(
        from_=START, country="US", currency="USD", sort="absolute_change_desc"
    ).first_page(),
    "analyze_availability_changes": lambda c: c.explore.analyses.availability_changes(
        from_=START, country="US", condition="new"
    ).first_page(),
    "analyze_assortment_overlap": lambda c: c.explore.analyses.assortment_overlap(
        reference_store_id="store_1", comparison_store_id="store_2", country="US"
    ).first_page(),
    "run_query": lambda c: c.query.run("SELECT count() FROM extralt.current_offers"),
    "export_query": lambda c: _export_query(c),
    "get_query_model": lambda c: c.query.model(entities=["listings", "current_offers"]),
    "create_webhook": lambda c: c.webhooks.create(
        url="https://hooks.example.com/extralt",
        event_types=["run.completed", "run.failed"],
        description="Price alerts workflow",
    ),
    "list_webhooks": lambda c: c.webhooks.list(),
    "get_webhook": lambda c: c.webhooks.get("webhook_1"),
    "delete_webhook": lambda c: c.webhooks.delete("webhook_1"),
    "test_webhook": lambda c: c.webhooks.test("webhook_1"),
}


def _export(client: Extralt) -> bytes:
    with client.extract.captures.export(run_id="run_1", format="jsonl") as stream:
        return b"".join(stream.iter_bytes())


def _export_items(client: Extralt) -> bytes:
    with client.enrich.items.export(enrichment_id="enrichment_1", format="jsonl") as stream:
        return b"".join(stream.iter_bytes())


def _export_query(client: Extralt) -> bytes:
    with client.query.export("SELECT id FROM extralt.listings", format="jsonl") as stream:
        return b"".join(stream.iter_bytes())


def test_every_implemented_operation_has_a_contract_case() -> None:
    assert set(CALLS) == set(sdk_methods(Extralt(api_key="k")))


def respond(operation_id: str, *, future: bool) -> Callable[[httpx.Request], httpx.Response]:
    status, schema = spec.success_response(operation_id)

    def handler(request: httpx.Request) -> httpx.Response:
        if schema is None:
            return httpx.Response(status, content=b"" if status == 204 else b"binary")
        return httpx.Response(status, json=spec.example(schema, future=future))

    return handler


@pytest.mark.parametrize("operation_id", sorted(CALLS))
def test_requests_match_the_spec(operation_id: str) -> None:
    sent: list[httpx.Request] = []
    handler = respond(operation_id, future=False)

    def record(request: httpx.Request) -> httpx.Response:
        request.read()
        sent.append(request)
        return handler(request)

    client = Extralt(api_key="k", http_client=httpx.Client(transport=httpx.MockTransport(record)))
    CALLS[operation_id](client)
    assert len(sent) == 1
    spec.assert_request_matches(operation_id, sent[0])


@pytest.mark.parametrize("future", [False, True], ids=["current", "future"])
@pytest.mark.parametrize("operation_id", sorted(CALLS))
def test_responses_parse_including_later_additions(operation_id: str, future: bool) -> None:
    client = Extralt(
        api_key="k",
        http_client=httpx.Client(
            transport=httpx.MockTransport(respond(operation_id, future=future))
        ),
    )
    result = CALLS[operation_id](client)
    _, schema = spec.success_response(operation_id)
    if schema is not None and "$ref" in schema:
        assert isinstance(result, (BaseModel, int))
        if isinstance(result, BaseModel):
            assert (result.model_extra or {}).get("field_added_later") == (
                {"nested": True} if future else None
            )
