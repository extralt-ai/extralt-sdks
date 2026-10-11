from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar


@dataclass(frozen=True)
class Operation:
    """One documented API operation, generated from the OpenAPI snapshot."""

    method: str
    path: str
    idempotent: bool
    idempotency_key: bool


F = TypeVar("F", bound=Callable[..., Any])


def operation(operation_id: str) -> Callable[[F], F]:
    """Marks the resource method that exposes an API operation."""

    def mark(function: F) -> F:
        vars(function)["__extralt_operation__"] = operation_id
        return function

    return mark
