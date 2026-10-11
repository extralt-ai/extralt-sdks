from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
import pytest

from extralt import AsyncExtralt, Extralt, JobFailedError, WaitTimeoutError

from . import spec


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    delays: list[float] = []
    monkeypatch.setattr("extralt._sync._resource.sleep", delays.append)
    return delays


def client(handler: httpx.MockTransport) -> Extralt:
    return Extralt(api_key="k", http_client=httpx.Client(transport=handler))


def run(**fields: object) -> dict[str, object]:
    _, schema = spec.success_response("get_run")
    assert schema is not None
    return {**spec.example(schema), **fields}


def test_iterating_a_list_follows_cursors_across_pages() -> None:
    cursors: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        cursors.append(cursor)
        if cursor is None:
            return httpx.Response(
                200, json={"data": [run(id="a"), run(id="b")], "next_cursor": "2"}
            )
        return httpx.Response(200, json={"data": [run(id="c")], "next_cursor": None})

    runs = client(httpx.MockTransport(handler)).extract.runs.list(limit=2)
    assert [item.id for item in runs] == ["a", "b", "c"]
    assert cursors == [None, "2"]


@pytest.mark.anyio
async def test_async_iteration_follows_cursors_too() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("cursor") is None:
            return httpx.Response(200, json={"data": [run(id="a")], "next_cursor": "2"})
        return httpx.Response(200, json={"data": [run(id="b")], "next_cursor": None})

    async with AsyncExtralt(
        api_key="k", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ) as extralt:
        assert [item.id async for item in extralt.extract.runs.list()] == ["a", "b"]


def test_wait_polls_until_finished_with_backoff(no_sleep: list[float]) -> None:
    states = iter(
        [run(status="running", finished=False)] * 3 + [run(status="completed", finished=True)]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(states))

    result = client(httpx.MockTransport(handler)).extract.runs.wait("run_1")
    assert result.status == "completed"
    assert no_sleep == [2.0, 3.0, 4.5]


def test_wait_gives_up_with_the_job_still_running() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=run(status="running", finished=False))

    with pytest.raises(WaitTimeoutError) as raised:
        client(httpx.MockTransport(handler)).extract.runs.wait("run_1", timeout=0)
    assert raised.value.resource.status == "running"


def test_starting_a_job_returns_it_finished(caplog: pytest.LogCaptureFixture) -> None:
    states = iter(
        [
            run(id="run_1", status="pending", finished=False),
            run(id="run_1", status="running", finished=False),
            run(id="run_1", status="completed", finished=True),
        ]
    )
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(f"{request.method} {request.url.path}")
        return httpx.Response(200, json=next(states))

    with caplog.at_level(logging.INFO, logger="extralt"):
        result = client(httpx.MockTransport(handler)).extract.runs.create(
            robot_id="robot_1", budget=5
        )
    assert result.status == "completed"
    assert requests == [
        "POST /v1/extract/runs",
        "GET /v1/extract/runs/run_1",
        "GET /v1/extract/runs/run_1",
    ]
    assert [record.getMessage() for record in caplog.records] == [
        "Waiting for Run run_1, now pending",
        "Run run_1 is running",
        "Run run_1 is completed",
    ]


def test_starting_a_job_without_waiting_returns_it_as_started() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=run(status="pending", finished=False))

    result = client(httpx.MockTransport(handler)).extract.runs.create(
        robot_id="robot_1", budget=5, wait=False
    )
    assert (result.status, len(requests)) == ("pending", 1)


def test_starting_a_job_gives_up_within_its_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=run(status="running", finished=False))

    with pytest.raises(WaitTimeoutError) as raised:
        client(httpx.MockTransport(handler)).extract.runs.create(
            robot_id="robot_1", budget=5, timeout=0
        )
    assert raised.value.resource.status == "running"


@pytest.mark.parametrize(
    ("operation_id", "status"), [("get_run", "failed"), ("get_import", "validation_failed")]
)
def test_a_job_that_ends_as_failed_raises_with_its_reason(operation_id: str, status: str) -> None:
    _, schema = spec.success_response(operation_id)
    assert schema is not None
    job = {
        **spec.example(schema),
        "id": "job_1",
        "status": status,
        "finished": True,
        "status_reason": "The store blocked the crawl",
    }
    extract = client(httpx.MockTransport(lambda request: httpx.Response(200, json=job))).extract
    wait = extract.runs.wait if operation_id == "get_run" else extract.imports.wait

    with pytest.raises(JobFailedError, match="The store blocked the crawl") as raised:
        wait("job_1")
    assert raised.value.resource.status == status


def test_a_stopped_job_is_returned() -> None:
    stopped = run(status="stopped", finished=True)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=stopped))

    assert client(transport).extract.runs.wait("run_1").status == "stopped"


def test_a_run_needs_a_budget_and_unlimited_sends_none() -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.read()))
        return httpx.Response(200, json=run(status="completed", finished=True))

    runs = client(httpx.MockTransport(handler)).extract.runs
    with pytest.raises(TypeError, match="budget"):
        runs.create(robot_id="robot_1", budget=None)  # ty: ignore[invalid-argument-type]
    assert bodies == []

    runs.create(robot_id="robot_1", budget="unlimited")
    runs.create(robot_id="robot_1", budget=5)
    assert bodies == [{"robot_id": "robot_1"}, {"robot_id": "robot_1", "budget": 5}]


def test_import_streams_a_file_with_its_media_type(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.csv"
    catalog.write_bytes(b"sku,title\n1,Shoe\n")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request.read()
        seen.append(request)
        _, schema = spec.success_response("get_import")
        assert schema is not None
        return httpx.Response(202, json=spec.example(schema))

    client(httpx.MockTransport(handler)).extract.imports.create(catalog, country="US", wait=False)
    assert seen[0].content == b"sku,title\n1,Shoe\n"
    assert seen[0].headers["content-type"] == "text/csv"
    assert seen[0].url.params["file_name"] == "catalog.csv"


def export_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=b'{"id":"a"}\n{"id":"b"}\n')


def test_an_export_writes_its_stream_to_a_file(tmp_path: Path) -> None:
    target = tmp_path / "captures.jsonl"
    captures = client(httpx.MockTransport(export_response)).extract.captures
    with captures.export(run_id="run_1", format="jsonl") as export:
        export.write_to(target)
    assert target.read_bytes() == b'{"id":"a"}\n{"id":"b"}\n'


@pytest.mark.anyio
async def test_an_async_export_writes_its_stream_to_a_file(tmp_path: Path) -> None:
    target = tmp_path / "captures.jsonl"
    transport = httpx.MockTransport(export_response)
    async with (
        AsyncExtralt(api_key="k", http_client=httpx.AsyncClient(transport=transport)) as extralt,
        extralt.extract.captures.export(run_id="run_1", format="jsonl") as export,
    ):
        await export.write_to(target)
    assert target.read_bytes() == b'{"id":"a"}\n{"id":"b"}\n'


def test_update_sends_only_given_fields_and_explicit_nulls() -> None:
    bodies: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.read()))
        _, schema = spec.success_response("update_schedule")
        assert schema is not None
        return httpx.Response(200, json=spec.example(schema))

    client(httpx.MockTransport(handler)).extract.schedules.update(
        "schedule_1", name="Weekly", budget="unlimited"
    )
    assert bodies == [{"name": "Weekly", "budget": None}]
