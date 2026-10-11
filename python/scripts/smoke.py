"""Exercises an installed `extralt` without the test dependencies; run by check_package.py."""

from __future__ import annotations

import asyncio
import importlib.metadata
import importlib.resources

import httpx

import extralt
from extralt import AsyncExtralt, Extralt, NotFoundError


def respond(request: httpx.Request) -> httpx.Response:
    if request.method == "GET" and request.url.path == "/v1/extract/robots":
        if request.url.params.get("cursor") == "page-2":
            return httpx.Response(200, json={"data": [{"id": "robot_2"}], "next_cursor": None})
        return httpx.Response(200, json={"data": [{"id": "robot_1"}], "next_cursor": "page-2"})
    return httpx.Response(
        404, json={"error": {"code": "not_found", "message": "Not found", "request_id": "req_1"}}
    )


def check_sync() -> None:
    client = Extralt(api_key="k", http_client=httpx.Client(transport=httpx.MockTransport(respond)))
    assert [robot.id for robot in client.extract.robots.list()] == ["robot_1", "robot_2"]
    try:
        client.extract.robots.get("missing")
    except NotFoundError as error:
        request_id = error.request_id
    else:
        raise AssertionError("a 404 must raise NotFoundError")
    assert request_id == "req_1"


async def check_async() -> None:
    transport = httpx.MockTransport(respond)
    async with AsyncExtralt(api_key="k", http_client=httpx.AsyncClient(transport=transport)) as c:
        assert [robot.id async for robot in c.extract.robots.list()] == ["robot_1", "robot_2"]


def main() -> None:
    assert extralt.__version__ == importlib.metadata.version("extralt")
    assert importlib.resources.files("extralt").joinpath("py.typed").is_file()
    check_sync()
    asyncio.run(check_async())
    pydantic = importlib.metadata.version("pydantic")
    print(f"extralt {extralt.__version__} works with pydantic {pydantic}")


if __name__ == "__main__":
    main()
