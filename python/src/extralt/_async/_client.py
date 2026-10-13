from __future__ import annotations

from collections.abc import Mapping
from types import TracebackType

import httpx

from .._base import configure_logging, default_headers, resolve_api_key, validate_base_url
from .._constants import DEFAULT_BASE_URL, DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT
from ._http import AsyncHTTP
from .resources.enrich import AsyncEnrich
from .resources.explore import AsyncExplore
from .resources.extract import AsyncExtract
from .resources.query import AsyncQuery
from .resources.webhooks import AsyncWebhooks


class AsyncExtralt:
    """Asynchronous client for the Extralt API.

    The API key defaults to the EXTRALT_API_KEY environment variable. Requests that fail with a
    connection error, 408, 429 or 5xx are retried with backoff when the operation is safe to
    repeat; create and restart operations send an idempotency key that every retry reuses.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        headers: Mapping[str, str] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        configure_logging()
        self.base_url = validate_base_url(base_url)
        self._http = AsyncHTTP(
            base_url=self.base_url,
            headers={**default_headers(resolve_api_key(api_key)), **(headers or {})},
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client,
        )
        self.extract = AsyncExtract(self._http)
        self.enrich = AsyncEnrich(self._http)
        self.explore = AsyncExplore(self._http)
        self.query = AsyncQuery(self._http)
        self.webhooks = AsyncWebhooks(self._http)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncExtralt:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(base_url={self.base_url!r})"
