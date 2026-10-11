from __future__ import annotations

import os
from collections.abc import AsyncIterable, Iterable

import anyio


def write_chunks(path: str | os.PathLike[str], chunks: Iterable[bytes]) -> None:
    with open(path, "wb") as file:
        for chunk in chunks:
            file.write(chunk)


async def awrite_chunks(path: str | os.PathLike[str], chunks: AsyncIterable[bytes]) -> None:
    """Writes through anyio, so that disk writes do not block the event loop."""
    async with await anyio.open_file(path, "wb") as file:
        async for chunk in chunks:
            await file.write(chunk)
