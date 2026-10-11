from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from extralt import (
    APIConnectionError,
    AsyncExtralt,
    Extralt,
    ExtraltError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
)

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    delays: list[float] = []
    monkeypatch.setattr("extralt._sync._http.sleep", delays.append)
    return delays


def client(handler: Handler, *, max_retries: int = 2) -> Extralt:
    return Extralt(
        api_key="test-key",
        max_retries=max_retries,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def error(status: int, code: str, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        status,
        headers=headers,
        json={"error": {"code": code, "message": f"{code} happened", "request_id": "req_1"}},
    )


def test_retries_an_idempotent_create_with_the_same_key_and_honors_retry_after(
    no_sleep: list[float],
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return error(429, "rate_limit_exceeded", {"Retry-After": "3"})
        if len(requests) == 2:
            return error(503, "upstream_unavailable")
        return httpx.Response(202, json={"id": "run_1"})

    response = client(handler)._http.request("create_run", json={"robot_id": "robot_1"})

    assert response.json() == {"id": "run_1"}
    assert len(requests) == 3
    keys = {request.headers["Idempotency-Key"] for request in requests}
    assert len(keys) == 1, "every retry must reuse the original idempotency key"
    assert no_sleep[0] == 3.0
    assert requests[0].headers["Authorization"] == "Bearer test-key"
    assert requests[0].url == "https://api.extralt.com/v1/extract/runs"


def test_caller_idempotency_key_is_sent_unchanged() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["Idempotency-Key"])
        return httpx.Response(202, json={})

    client(handler)._http.request("create_run", json={}, idempotency_key="mine")
    assert seen == ["mine"]


def test_does_not_retry_an_operation_that_is_not_idempotent() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return error(503, "upstream_unavailable")

    with pytest.raises(InternalServerError):
        client(handler)._http.request("update_schedule", path_params={"id": "s"}, json={})
    assert calls == 1


def test_gives_up_after_max_retries_with_the_typed_error() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return error(429, "rate_limit_exceeded")

    with pytest.raises(RateLimitError) as raised:
        client(handler, max_retries=1)._http.request("list_runs")
    assert calls == 2
    assert raised.value.code == "rate_limit_exceeded"


def test_maps_the_error_envelope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return error(404, "not_found")

    with pytest.raises(NotFoundError) as raised:
        client(handler)._http.request("get_run", path_params={"id": "run/1"})
    assert raised.value.status_code == 404
    assert raised.value.message == "not_found happened"
    assert raised.value.request_id == "req_1"
    assert str(raised.value) == "404 not_found: not_found happened (request req_1)"


def test_path_parameters_are_escaped() -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, json={})

    client(handler)._http.request("get_run", path_params={"id": "a/b c"})
    assert urls == ["https://api.extralt.com/v1/extract/runs/a%2Fb%20c"]


def test_retries_connection_failures_then_raises_connection_error() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(APIConnectionError):
        client(handler)._http.request("update_schedule", path_params={"id": "s"}, json={})
    assert calls == 3, "a request that never connected is safe to resend for any operation"


def test_logs_responses_at_debug_and_retries_at_info_never_the_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    responses = iter(
        [
            error(429, "rate_limit_exceeded", {"Retry-After": "2", "x-request-id": "req_1"}),
            httpx.Response(200, json={"data": [], "next_cursor": None}),
        ]
    )

    with caplog.at_level("DEBUG", logger="extralt"):
        client(lambda request: next(responses))._http.request("list_robots", params={"limit": 5})

    url = "https://api.extralt.com/v1/extract/robots?limit=5"
    assert [(record.levelname, record.getMessage()) for record in caplog.records] == [
        ("DEBUG", f"GET {url} -> 429 (request req_1)"),
        ("INFO", "Retrying list_robots after HTTP 429 in 2.00s"),
        ("DEBUG", f"GET {url} -> 200 (request none)"),
    ]
    assert "test-key" not in caplog.text


def test_requires_an_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXTRALT_API_KEY", raising=False)
    with pytest.raises(ExtraltError, match="EXTRALT_API_KEY"):
        Extralt()


def test_rejects_plain_http_except_locally() -> None:
    with pytest.raises(ExtraltError, match="HTTPS"):
        Extralt(api_key="k", base_url="http://api.example.com")
    assert Extralt(api_key="k", base_url="http://localhost:8080").base_url == (
        "http://localhost:8080"
    )


@pytest.mark.anyio
async def test_async_client_retries_like_the_sync_client(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_wait(delay: float) -> None:
        return None

    monkeypatch.setattr("extralt._async._http.sleep", no_wait)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return error(503, "upstream_unavailable") if calls == 1 else httpx.Response(200, json={})

    async with AsyncExtralt(
        api_key="k", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ) as extralt:
        response = await extralt._http.request("list_runs")
    assert response.status_code == 200
    assert calls == 2
