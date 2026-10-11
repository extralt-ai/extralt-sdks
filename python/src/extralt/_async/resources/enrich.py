from __future__ import annotations

from typing import Any

from ..._base import json_body
from ..._operation import operation
from ...types import Enrichment, EnrichmentPage, EnrichmentSource, Item, ItemPage
from .._http import AsyncHTTP
from .._pagination import AsyncPaginator
from .._resource import AsyncResource


class AsyncEnrich:
    """Enrichments and the Items they produce."""

    def __init__(self, http: AsyncHTTP) -> None:
        self.enrichments = AsyncEnrichments(http)
        self.items = AsyncItems(http)


class AsyncEnrichments(AsyncResource):
    @operation("start_enrichment")
    async def start(
        self,
        *,
        source: EnrichmentSource | dict[str, Any],
        budget: int | None = None,
        wait: bool = True,
        timeout: float | None = None,
        idempotency_key: str | None = None,
    ) -> Enrichment:
        """Enriches the Captures of a Run or Import and returns the finished Enrichment.

        `source` is `{"kind": "run" | "import", "id": ...}`. The call starts, or continues, the
        Enrichment, waits up to `timeout` seconds (one hour by default) and raises
        `JobFailedError` if it fails. Pass `wait=False` to return at once.
        """
        return await self._start(
            "start_enrichment",
            "get_enrichment",
            Enrichment,
            wait=wait,
            timeout=timeout,
            json=json_body({"source": source, "budget": budget}),
            idempotency_key=idempotency_key,
        )

    @operation("list_enrichments")
    def list(
        self, *, limit: int | None = None, cursor: str | None = None
    ) -> AsyncPaginator[EnrichmentPage, Enrichment]:
        return AsyncPaginator(
            self._http,
            "list_enrichments",
            EnrichmentPage,
            items="data",
            params={"limit": limit, "cursor": cursor},
        )

    @operation("get_enrichment")
    async def get(self, id: str, *, timeout: float | None = None) -> Enrichment:
        return await self._call(
            "get_enrichment", Enrichment, path_params={"id": id}, timeout=timeout
        )

    @operation("stop_enrichment")
    async def stop(self, id: str, *, timeout: float | None = None) -> Enrichment:
        """Requests cancellation; committed Items are still delivered before it is `stopped`."""
        return await self._call(
            "stop_enrichment", Enrichment, path_params={"id": id}, timeout=timeout
        )

    async def wait(
        self, id: str, *, timeout: float | None = None, poll_interval: float | None = None
    ) -> Enrichment:
        """Waits until the Enrichment is completed or stopped; raises `JobFailedError` if failed."""
        return await self._wait(
            "get_enrichment", Enrichment, id, timeout=timeout, poll_interval=poll_interval
        )


class AsyncItems(AsyncResource):
    @operation("list_items")
    def list(
        self, *, enrichment_id: str, limit: int | None = None, cursor: str | None = None
    ) -> AsyncPaginator[ItemPage, Item]:
        """Lists the Items one Enrichment produced."""
        return AsyncPaginator(
            self._http,
            "list_items",
            ItemPage,
            items="data",
            params={"enrichment_id": enrichment_id, "limit": limit, "cursor": cursor},
        )

    @operation("get_item")
    async def get(self, item_id: str, *, enrichment_id: str, timeout: float | None = None) -> Item:
        return await self._call(
            "get_item",
            Item,
            path_params={"item_id": item_id},
            params={"enrichment_id": enrichment_id},
            timeout=timeout,
        )
