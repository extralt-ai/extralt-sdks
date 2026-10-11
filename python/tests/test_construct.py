from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal

from extralt._construct import construct
from extralt.types import PricePositionRow, Run, RunPage, RunSummary

from . import spec


def run_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "run_1",
        "robot_id": "robot_1",
        "robot_name": "example_com_US",
        "name": "example_com_US_1",
        "status": "running",
        "finished": False,
        "status_reason": None,
        "triggered_by": "api",
        "auto_enrich": False,
        "budget": 10,
        "start_urls": None,
        "extracted": 3,
        "in_queue": 1,
        "created_at": "2026-10-08T10:00:00Z",
        "started_at": None,
        "updated_at": "2026-10-08T10:01:00.250Z",
    }
    payload.update(overrides)
    return payload


def test_parses_nested_models_lists_and_timestamps() -> None:
    page = construct(RunPage, {"data": [run_payload()], "next_cursor": "c2"})
    assert isinstance(page.data[0], RunSummary)
    assert page.data[0].budget == 10
    assert page.data[0].created_at == dt.datetime(2026, 10, 8, 10, 0, tzinfo=dt.UTC)
    assert page.data[0].started_at is None
    assert page.next_cursor == "c2"


def test_keeps_additive_api_changes_readable() -> None:
    run = construct(Run, run_payload(status="paused", new_field={"x": 1}))
    assert run.status == "paused"
    assert run.model_extra == {"new_field": {"x": 1}}
    assert run.model_dump()["new_field"] == {"x": 1}


def test_decimal_strings_become_decimals_that_compare_as_numbers() -> None:
    payload = {
        **spec.example(spec.components()["schemas"]["PricePositionRow"]),
        "reference_price": "99.00",
        "lowest_comparison_price": "129.99",
        "delta_to_lowest": "-30.99",
        "delta_to_lowest_percent": None,
    }
    row = construct(PricePositionRow, payload)

    assert row.reference_price < row.lowest_comparison_price
    assert row.reference_price - row.lowest_comparison_price == row.delta_to_lowest
    assert row.delta_to_lowest == Decimal("-30.99")
    assert row.delta_to_lowest_percent is None
    assert json.loads(row.model_dump_json())["reference_price"] == "99.00"
