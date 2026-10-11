from __future__ import annotations

from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager

from ..._base import json_body
from ..._operation import operation
from ...types import ExportFormat, QueryDataModel, QueryResult
from .._resource import AsyncResource
from .._streaming import AsyncBinaryStream


class AsyncQuery(AsyncResource):
    """Read-only SQL over the organization's Captures, Items and Explore tables."""

    @operation("run_query")
    async def run(self, sql: str, *, timeout: float | None = None) -> QueryResult:
        """Runs one SELECT or WITH query and returns the rows that fit in one response.

        `truncated` is true when rows were left out: aggregate, add a LIMIT, or use `export()`.
        64-bit integers and decimals arrive as strings.
        """
        return await self._call("run_query", QueryResult, json={"sql": sql}, timeout=timeout)

    @operation("export_query")
    @asynccontextmanager
    async def export(
        self,
        sql: str,
        *,
        format: ExportFormat | None = None,
        timeout: float | None = None,
    ) -> AsyncGenerator[AsyncBinaryStream]:
        """Streams every row a query selects as Parquet (default) or JSON Lines.

        Use it as a context manager and read the stream inside the block, for example with
        `write_to(path)`. The download must finish within 35 seconds of the request.
        """
        response = await self._http.request(
            "export_query",
            json=json_body({"sql": sql, "format": format}),
            timeout=timeout,
            stream=True,
        )
        try:
            yield AsyncBinaryStream(response)
        finally:
            await response.aclose()

    @operation("get_query_model")
    async def model(
        self, *, entities: Sequence[str] | None = None, timeout: float | None = None
    ) -> QueryDataModel:
        """Describes the tables, columns, relationships and rules to write SQL against.

        Name the `entities` a question needs, such as `["listings", "current_offers"]`; omit
        them for the whole model.
        """
        return await self._call(
            "get_query_model",
            QueryDataModel,
            params={"entities": ",".join(entities) if entities else None},
            timeout=timeout,
        )
