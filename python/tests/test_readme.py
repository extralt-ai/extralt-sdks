"""Runs the README's Python snippets in order, as a reader would, against spec-shaped responses."""

from __future__ import annotations

import ast
import asyncio
import inspect
import re
from pathlib import Path
from typing import Any

import httpx
import pytest

import extralt

from . import spec

README = Path(__file__).resolve().parents[1] / "README.md"
# Values a reader brings from their own context.
CONTEXT = {"run_id": "run_1", "variant_id": "9007199254740993"}


def snippets() -> list[str]:
    return re.findall(r"```python\n(.*?)```", README.read_text(), re.DOTALL)


def operation_for(request: httpx.Request) -> str:
    for operation_id, (method, template, _) in spec.operations().items():
        pattern = "^" + re.sub(r"\{[^}]+\}", "[^/]+", template) + "$"
        if request.method == method and re.match(pattern, request.url.path):
            return operation_id
    raise AssertionError(f"{request.method} {request.url.path} is not in the spec")


def settled(value: Any) -> Any:
    """Every job finished and every list on its last page, so waits and iteration end."""
    if isinstance(value, dict):
        return {
            key: None if key == "next_cursor" else True if key == "finished" else settled(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [settled(item) for item in value]
    return value


def respond(request: httpx.Request) -> httpx.Response:
    status, schema = spec.success_response(operation_for(request))
    if schema is None:
        return httpx.Response(status, content=b"" if status == 204 else b"binary")
    return httpx.Response(status, json=settled(spec.example(schema)))


class Extralt(extralt.Extralt):
    """Keeps the reader's options but answers every request locally."""

    def __init__(self, **options: Any) -> None:
        options.pop("api_key", None)
        options.pop("http_client", None)
        transport = httpx.MockTransport(respond)
        super().__init__(api_key="k", http_client=httpx.Client(transport=transport), **options)


class AsyncExtralt(extralt.AsyncExtralt):
    def __init__(self, **options: Any) -> None:
        options.pop("api_key", None)
        options.pop("http_client", None)
        transport = httpx.MockTransport(respond)
        super().__init__(api_key="k", http_client=httpx.AsyncClient(transport=transport), **options)


def test_readme_snippets_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(extralt, "Extralt", Extralt)
    monkeypatch.setattr(extralt, "AsyncExtralt", AsyncExtralt)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "catalog.csv").write_text("sku,title\n1,Shoe\n")
    namespace: dict[str, Any] = dict(CONTEXT)
    found = snippets()
    assert found, "the README has no Python snippet"
    for index, source in enumerate(found):
        code = compile(
            source, f"README.md snippet {index + 1}", "exec", ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
        )
        result = eval(code, namespace)
        if inspect.iscoroutine(result):
            asyncio.run(result)
