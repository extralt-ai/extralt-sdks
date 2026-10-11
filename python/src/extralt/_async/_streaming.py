from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator

import httpx

from .._files import awrite_chunks


class AsyncBinaryStream:
    """A streamed binary response, readable once inside the block that opened it."""

    def __init__(self, response: httpx.Response) -> None:
        self.response = response

    @property
    def content_type(self) -> str | None:
        return self.response.headers.get("content-type")

    @property
    def file_name(self) -> str | None:
        disposition = self.response.headers.get("content-disposition", "")
        match = re.search(r'filename="?([^";]+)"?', disposition)
        return match.group(1) if match else None

    async def iter_bytes(self, chunk_size: int | None = None) -> AsyncIterator[bytes]:
        async for chunk in self.response.aiter_bytes(chunk_size):
            yield chunk

    async def write_to(self, path: str | os.PathLike[str]) -> None:
        await awrite_chunks(path, self.response.aiter_bytes())
