from __future__ import annotations

import mimetypes
import os
from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from ..._base import NOT_GIVEN, Budget, NotGiven, budget_limit, json_body, update_body
from ..._operation import operation
from ...types import (
    Cadence,
    Capture,
    CaptureCount,
    CapturePage,
    CountryCode,
    ExportFormat,
    Import,
    LanguageCode,
    Robot,
    RobotPage,
    Run,
    RunPage,
    RunSummary,
    Schedule,
    SchedulePage,
)
from .._http import AsyncHTTP
from .._pagination import AsyncPaginator
from .._resource import AsyncResource
from .._streaming import AsyncBinaryStream
from .explore import Timestamp

CHUNK_SIZE = 1024 * 1024


class AsyncExtract:
    """Robots, Runs, Schedules, Captures and Imports."""

    def __init__(self, http: AsyncHTTP) -> None:
        self.robots = AsyncRobots(http)
        self.runs = AsyncRuns(http)
        self.schedules = AsyncSchedules(http)
        self.captures = AsyncCaptures(http)
        self.imports = AsyncImports(http)


class AsyncRobots(AsyncResource):
    @operation("create_robot")
    async def create(
        self,
        *,
        url: str,
        country: CountryCode,
        wait: bool = True,
        timeout: float | None = None,
        idempotency_key: str | None = None,
    ) -> Robot:
        """Creates a Robot for a store and country, or returns the existing one, once it is built.

        The build checks the store first and reuses an earlier build of the same store, which
        finishes within seconds. The call waits for it, up to `timeout` seconds (one hour by
        default), and raises `JobFailedError` if it fails, including when it refuses the store:
        the Robot's `refusal` then says why. Pass `wait=False` to return the queued Robot.
        """
        return await self._start(
            "create_robot",
            "get_robot",
            Robot,
            wait=wait,
            timeout=timeout,
            json=json_body({"url": url, "country": country}),
            idempotency_key=idempotency_key,
        )

    @operation("list_robots")
    def list(
        self, *, limit: int | None = None, cursor: str | None = None
    ) -> AsyncPaginator[RobotPage, Robot]:
        return AsyncPaginator(
            self._http,
            "list_robots",
            RobotPage,
            items="data",
            params={"limit": limit, "cursor": cursor},
        )

    @operation("get_robot")
    async def get(self, id: str, *, timeout: float | None = None) -> Robot:
        return await self._call("get_robot", Robot, path_params={"id": id}, timeout=timeout)

    @operation("delete_robot")
    async def delete(self, id: str, *, timeout: float | None = None) -> None:
        await self._http.request("delete_robot", path_params={"id": id}, timeout=timeout)

    async def wait(
        self, id: str, *, timeout: float | None = None, poll_interval: float | None = None
    ) -> Robot:
        """Waits until the Robot is built. Raises `JobFailedError` if its build failed."""
        return await self._wait(
            "get_robot", Robot, id, timeout=timeout, poll_interval=poll_interval
        )


class AsyncRuns(AsyncResource):
    @operation("create_run")
    async def create(
        self,
        *,
        robot_id: str,
        budget: Budget,
        start_urls: Sequence[str] | None = None,
        auto_enrich: bool | None = None,
        wait: bool = True,
        timeout: float | None = None,
        idempotency_key: str | None = None,
    ) -> Run:
        """Runs a completed Robot and returns the finished Run.

        `budget` is the most Captures to produce, or `"unlimited"` to crawl until the store is
        done or credits run out. The call waits up to `timeout` seconds (one hour by default)
        and raises `JobFailedError` if the Run fails. Pass `wait=False` to return the started
        Run at once.
        """
        return await self._start(
            "create_run",
            "get_run",
            Run,
            wait=wait,
            timeout=timeout,
            json=json_body(
                {
                    "robot_id": robot_id,
                    "start_urls": start_urls,
                    "budget": budget_limit(budget),
                    "auto_enrich": auto_enrich,
                }
            ),
            idempotency_key=idempotency_key,
        )

    @operation("list_runs")
    def list(
        self,
        *,
        finished_since: Timestamp | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AsyncPaginator[RunPage, RunSummary]:
        """Lists Runs, newest first.

        With `finished_since`, lists only the Runs finished at or after that time, oldest finish
        first: pass the last `finished_at` you processed to pick up what finished since.
        """
        return AsyncPaginator(
            self._http,
            "list_runs",
            RunPage,
            items="data",
            params={"finished_since": finished_since, "limit": limit, "cursor": cursor},
        )

    @operation("get_run")
    async def get(self, id: str, *, timeout: float | None = None) -> Run:
        return await self._call("get_run", Run, path_params={"id": id}, timeout=timeout)

    @operation("restart_run")
    async def restart(
        self,
        id: str,
        *,
        budget: int | None = None,
        wait: bool = True,
        timeout: float | None = None,
        idempotency_key: str | None = None,
    ) -> Run:
        """Restarts a finished Run, optionally with a new budget, and returns it finished again.

        Waits and raises like `create()`; pass `wait=False` to return at once.
        """
        return await self._start(
            "restart_run",
            "get_run",
            Run,
            wait=wait,
            timeout=timeout,
            path_params={"id": id},
            json=json_body({"budget": budget}),
            idempotency_key=idempotency_key,
        )

    @operation("stop_run")
    async def stop(self, id: str, *, timeout: float | None = None) -> Run:
        """Requests cancellation. The Run may finish its current work before it is `stopped`."""
        return await self._call("stop_run", Run, path_params={"id": id}, timeout=timeout)

    async def wait(
        self, id: str, *, timeout: float | None = None, poll_interval: float | None = None
    ) -> Run:
        """Waits until the Run is completed or stopped. Raises `JobFailedError` if it failed."""
        return await self._wait("get_run", Run, id, timeout=timeout, poll_interval=poll_interval)


class AsyncSchedules(AsyncResource):
    @operation("create_schedule")
    async def create(
        self,
        *,
        robot_id: str,
        cadence: Cadence | dict[str, Any],
        budget: Budget,
        name: str | None = None,
        start_urls: Sequence[str] | None = None,
        auto_enrich: bool | None = None,
        idempotency_key: str | None = None,
        timeout: float | None = None,
    ) -> Schedule:
        """Schedules Runs of a completed Robot. `budget` limits each Run, as in `runs.create`."""
        return await self._call(
            "create_schedule",
            Schedule,
            json=json_body(
                {
                    "robot_id": robot_id,
                    "cadence": cadence,
                    "name": name,
                    "start_urls": start_urls,
                    "budget": budget_limit(budget),
                    "auto_enrich": auto_enrich,
                }
            ),
            idempotency_key=idempotency_key,
            timeout=timeout,
        )

    @operation("list_schedules")
    def list(
        self, *, limit: int | None = None, cursor: str | None = None
    ) -> AsyncPaginator[SchedulePage, Schedule]:
        return AsyncPaginator(
            self._http,
            "list_schedules",
            SchedulePage,
            items="data",
            params={"limit": limit, "cursor": cursor},
        )

    @operation("get_schedule")
    async def get(self, id: str, *, timeout: float | None = None) -> Schedule:
        return await self._call("get_schedule", Schedule, path_params={"id": id}, timeout=timeout)

    @operation("update_schedule")
    async def update(
        self,
        id: str,
        *,
        robot_id: str | NotGiven = NOT_GIVEN,
        cadence: Cadence | dict[str, Any] | NotGiven = NOT_GIVEN,
        name: str | NotGiven = NOT_GIVEN,
        start_urls: Sequence[str] | NotGiven | None = NOT_GIVEN,
        budget: Budget | NotGiven = NOT_GIVEN,
        auto_enrich: bool | NotGiven = NOT_GIVEN,
        timeout: float | None = None,
    ) -> Schedule:
        """Changes only the arguments passed.

        `start_urls=None` clears the start URLs and `budget="unlimited"` removes the limit.
        """
        return await self._call(
            "update_schedule",
            Schedule,
            path_params={"id": id},
            json=update_body(
                {
                    "robot_id": robot_id,
                    "cadence": cadence,
                    "name": name,
                    "start_urls": start_urls,
                    "budget": budget if isinstance(budget, NotGiven) else budget_limit(budget),
                    "auto_enrich": auto_enrich,
                }
            ),
            timeout=timeout,
        )

    @operation("pause_schedule")
    async def pause(self, id: str, *, timeout: float | None = None) -> Schedule:
        return await self._call("pause_schedule", Schedule, path_params={"id": id}, timeout=timeout)

    @operation("resume_schedule")
    async def resume(self, id: str, *, timeout: float | None = None) -> Schedule:
        return await self._call(
            "resume_schedule", Schedule, path_params={"id": id}, timeout=timeout
        )

    @operation("delete_schedule")
    async def delete(self, id: str, *, timeout: float | None = None) -> None:
        await self._http.request("delete_schedule", path_params={"id": id}, timeout=timeout)


class AsyncCaptures(AsyncResource):
    @operation("list_captures")
    def list(
        self,
        *,
        run_id: str | None = None,
        import_id: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AsyncPaginator[CapturePage, Capture]:
        """Lists the Captures of one Run or Import."""
        return AsyncPaginator(
            self._http,
            "list_captures",
            CapturePage,
            items="data",
            params={"run_id": run_id, "import_id": import_id, "limit": limit, "cursor": cursor},
        )

    @operation("count_captures")
    async def count(
        self,
        *,
        run_id: str | None = None,
        import_id: str | None = None,
        timeout: float | None = None,
    ) -> int:
        result = await self._call(
            "count_captures",
            CaptureCount,
            params={"run_id": run_id, "import_id": import_id},
            timeout=timeout,
        )
        return result.count

    @operation("export_captures")
    @asynccontextmanager
    async def export(
        self,
        *,
        run_id: str | None = None,
        import_id: str | None = None,
        format: ExportFormat | None = None,
        timeout: float | None = None,
    ) -> AsyncGenerator[AsyncBinaryStream]:
        """Streams every Capture of a Run or Import as Parquet (default) or JSON Lines.

        Use it as a context manager and read the stream inside the block, for example with
        `write_to(path)`.
        """
        response = await self._http.request(
            "export_captures",
            params={"run_id": run_id, "import_id": import_id, "format": format},
            timeout=timeout,
            stream=True,
        )
        try:
            yield AsyncBinaryStream(response)
        finally:
            await response.aclose()


class AsyncImports(AsyncResource):
    @operation("create_import")
    async def create(
        self,
        file: bytes | str | os.PathLike[str],
        *,
        file_name: str | None = None,
        content_type: str | None = None,
        country: CountryCode | None = None,
        language: LanguageCode | None = None,
        source_host: str | None = None,
        wait: bool = True,
        timeout: float | None = None,
        idempotency_key: str | None = None,
    ) -> Import:
        """Uploads a catalog file and returns the finished Import. Paths are streamed from disk.

        The call waits up to `timeout` seconds (one hour by default) and raises `JobFailedError`
        if the Import fails or its file is rejected. Pass `wait=False` to return at once.
        """
        if isinstance(file, bytes):
            content: Any = file
        else:
            path = Path(file)
            file_name = file_name or path.name

            def content() -> AsyncIterator[bytes]:
                return _read_chunks(path)

        guessed = mimetypes.guess_type(file_name)[0] if file_name else None
        return await self._start(
            "create_import",
            "get_import",
            Import,
            wait=wait,
            timeout=timeout,
            params={
                "file_name": file_name,
                "country": country,
                "language": language,
                "source_host": source_host,
            },
            content=content,
            headers={"Content-Type": content_type or guessed or "application/octet-stream"},
            idempotency_key=idempotency_key,
        )

    @operation("get_import")
    async def get(self, id: str, *, timeout: float | None = None) -> Import:
        return await self._call("get_import", Import, path_params={"id": id}, timeout=timeout)

    async def wait(
        self, id: str, *, timeout: float | None = None, poll_interval: float | None = None
    ) -> Import:
        """Waits until the Import is completed. Raises `JobFailedError` if it failed."""
        return await self._wait(
            "get_import", Import, id, timeout=timeout, poll_interval=poll_interval
        )


async def _read_chunks(path: Path) -> AsyncIterator[bytes]:
    with path.open("rb") as file:
        while chunk := file.read(CHUNK_SIZE):
            yield chunk
