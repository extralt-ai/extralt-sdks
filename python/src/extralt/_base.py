from __future__ import annotations

import datetime as dt
import email.utils
import logging
import os
import platform
import random
import time
from collections.abc import Mapping
from typing import Any, Literal
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from ._constants import INITIAL_RETRY_DELAY, MAX_RETRY_AFTER, MAX_RETRY_DELAY
from ._exceptions import ExtraltError
from ._operation import Operation
from ._version import __version__

log = logging.getLogger("extralt")

RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def resolve_api_key(api_key: str | None) -> str:
    key = api_key or os.environ.get("EXTRALT_API_KEY")
    if not key:
        raise ExtraltError(
            "Pass api_key or set the EXTRALT_API_KEY environment variable to an Extralt API key."
        )
    return key


def validate_base_url(base_url: str) -> str:
    url = httpx.URL(base_url)
    if url.scheme != "https" and url.host not in LOCAL_HOSTS:
        raise ExtraltError("base_url must use HTTPS unless it targets localhost.")
    return str(url).rstrip("/")


def default_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": (
            f"extralt-python/{__version__} python/{platform.python_version()} "
            f"httpx/{httpx.__version__}"
        ),
    }


def configure_logging() -> None:
    level = os.environ.get("EXTRALT_LOG", "").lower()
    if level in {"debug", "info"} and not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s extralt %(levelname)s %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.DEBUG if level == "debug" else logging.INFO)


def build_path(operation: Operation, path_params: Mapping[str, str]) -> str:
    path = operation.path
    for name, value in path_params.items():
        path = path.replace("{" + name + "}", quote(str(value), safe=""))
    return path


def query_params(params: Mapping[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in (params or {}).items():
        if value is None:
            continue
        if isinstance(value, bool):
            result[name] = "true" if value else "false"
        elif isinstance(value, dt.datetime):
            result[name] = value.isoformat()
        else:
            result[name] = value
    return result


class NotGiven:
    """Marks an argument left out, as opposed to an explicit `None` that clears a value."""

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "NOT_GIVEN"


NOT_GIVEN = NotGiven()


Budget = int | Literal["unlimited"]
"""A number of Captures, or `"unlimited"` to crawl until the store is done or credits run out."""


def budget_limit(budget: Budget) -> int | None:
    """The limit the API takes, `None` for no limit. Rejects a missing value, such as a `None`
    read from configuration, so that it cannot start an unlimited crawl."""
    if budget == "unlimited":
        return None
    if isinstance(budget, int) and not isinstance(budget, bool):
        return budget
    raise TypeError(f'budget must be a number of Captures or "unlimited", not {budget!r}')


def json_body(values: Mapping[str, Any]) -> dict[str, Any]:
    """Drops arguments left out: `None` for create bodies, `NOT_GIVEN` for partial updates."""
    return {
        name: jsonable(value)
        for name, value in values.items()
        if value is not None and value is not NOT_GIVEN
    }


def update_body(values: Mapping[str, Any]) -> dict[str, Any]:
    """Keeps explicit `None` so a partial update can clear a field."""
    return {name: jsonable(value) for name, value in values.items() if value is not NOT_GIVEN}


def jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_unset=True)
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def retry_delay(attempt: int, response: httpx.Response | None) -> float:
    if response is not None:
        retry_after = _retry_after_seconds(response.headers.get("retry-after"))
        if retry_after is not None and 0 <= retry_after <= MAX_RETRY_AFTER:
            return retry_after
    delay = min(INITIAL_RETRY_DELAY * 2**attempt, MAX_RETRY_DELAY)
    return delay * (0.75 + random.random() * 0.25)


def retries_transport_error(operation: Operation, error: httpx.TransportError) -> bool:
    """A request that never connected is safe to resend; anything else only when idempotent."""
    return isinstance(error, (httpx.ConnectError, httpx.ConnectTimeout)) or operation.idempotent


def retries_status(operation: Operation, status_code: int) -> bool:
    return operation.idempotent and status_code in RETRYABLE_STATUSES


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        pass
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return parsed.timestamp() - time.time()
