from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from .._construct import construct

if TYPE_CHECKING:
    from ._http import AsyncHTTP

PageT = TypeVar("PageT")
ItemT = TypeVar("ItemT")


class AsyncPaginator(Generic[PageT, ItemT]):
    """Iterates every item of a cursor-paginated list across pages, or the pages themselves."""

    def __init__(
        self,
        http: AsyncHTTP,
        operation_id: str,
        page_type: type[PageT],
        *,
        items: str,
        path_params: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> None:
        self._http = http
        self._operation_id = operation_id
        self._page_type = page_type
        self._items = items
        self._path_params = dict(path_params or {})
        self._params = dict(params or {})

    async def first_page(self) -> PageT:
        return await self._fetch(self._params.get("cursor"))

    async def pages(self) -> AsyncIterator[PageT]:
        cursor = self._params.get("cursor")
        while True:
            page = await self._fetch(cursor)
            yield page
            cursor = getattr(page, "next_cursor", None)
            if not cursor:
                return

    async def __aiter__(self) -> AsyncIterator[ItemT]:
        async for page in self.pages():
            for item in getattr(page, self._items):
                yield item

    async def _fetch(self, cursor: str | None) -> PageT:
        response = await self._http.request(
            self._operation_id,
            path_params=self._path_params,
            params={**self._params, "cursor": cursor},
        )
        return construct(self._page_type, response.json())
