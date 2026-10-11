from __future__ import annotations

import time
from typing import Any, TypeVar, cast

from anyio import sleep

from .._base import log
from .._constants import DEFAULT_WAIT_TIMEOUT, INITIAL_POLL_INTERVAL, MAX_POLL_INTERVAL
from .._construct import construct
from .._exceptions import JobFailedError, WaitTimeoutError
from ._http import AsyncHTTP

T = TypeVar("T")

FAILED_STATUSES = frozenset({"failed", "validation_failed"})


class AsyncResource:
    def __init__(self, http: AsyncHTTP) -> None:
        self._http = http

    async def _call(self, operation_id: str, result_type: type[T], **request: Any) -> T:
        response = await self._http.request(operation_id, **request)
        return construct(result_type, response.json())

    async def _start(
        self,
        operation_id: str,
        get_operation_id: str,
        result_type: type[T],
        *,
        wait: bool,
        timeout: float | None,
        **request: Any,
    ) -> T:
        """Starts a job and returns it finished, or as started when `wait` is false."""
        if not wait:
            return await self._call(operation_id, result_type, timeout=timeout, **request)
        wait_timeout = DEFAULT_WAIT_TIMEOUT if timeout is None else timeout
        deadline = time.monotonic() + wait_timeout
        job = await self._call(
            operation_id, result_type, timeout=self._request_timeout(deadline), **request
        )
        return await self._finish(get_operation_id, result_type, job, wait_timeout, deadline, None)

    async def _wait(
        self,
        operation_id: str,
        result_type: type[T],
        resource_id: str,
        *,
        timeout: float | None,
        poll_interval: float | None,
    ) -> T:
        wait_timeout = DEFAULT_WAIT_TIMEOUT if timeout is None else timeout
        deadline = time.monotonic() + wait_timeout
        job = await self._call(
            operation_id,
            result_type,
            path_params={"id": resource_id},
            timeout=self._request_timeout(deadline),
        )
        return await self._finish(
            operation_id, result_type, job, wait_timeout, deadline, poll_interval
        )

    async def _finish(
        self,
        operation_id: str,
        result_type: type[T],
        started: T,
        wait_timeout: float,
        deadline: float,
        poll_interval: float | None,
    ) -> T:
        """Polls a job until it is finished; a job that ends as failed raises."""
        job = cast(Any, started)
        kind = result_type.__name__
        status = job.status
        if not job.finished:
            log.info("Waiting for %s %s, now %s", kind, job.id, status)
        interval = poll_interval or INITIAL_POLL_INTERVAL
        while not job.finished:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WaitTimeoutError(
                    f"{kind} {job.id} is still {job.status} after {wait_timeout:g}s. "
                    "It keeps running on Extralt; wait() with its id resumes waiting.",
                    resource=job,
                )
            await sleep(min(interval, remaining))
            if poll_interval is None:
                interval = min(interval * 1.5, MAX_POLL_INTERVAL)
            job = cast(
                Any,
                await self._call(
                    operation_id,
                    result_type,
                    path_params={"id": job.id},
                    timeout=self._request_timeout(deadline),
                ),
            )
            if job.status != status:
                status = job.status
                log.info("%s %s is %s", kind, job.id, status)
        if job.status in FAILED_STATUSES:
            reason = f": {job.status_reason}" if job.status_reason else ""
            raise JobFailedError(f"{kind} {job.id} ended as {job.status}{reason}", resource=job)
        return cast(T, job)

    def _request_timeout(self, deadline: float) -> float:
        """One request never outlasts the client's timeout or what is left of the wait."""
        return max(min(self._http.timeout, deadline - time.monotonic()), 0.001)
