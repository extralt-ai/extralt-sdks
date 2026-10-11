"""Builds response models from decoded JSON without validating them.

The API may add fields and enum values within v1. Constructing instead of validating keeps those
responses readable by older SDK versions: unknown fields stay available as extra attributes and
unknown enum values keep their string.
"""

from __future__ import annotations

import datetime as dt
import types
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal, TypeVar, Union, get_args, get_origin

from pydantic import AwareDatetime, BaseModel

M = TypeVar("M", bound=BaseModel)


def construct(type_: Any, value: Any) -> Any:
    type_ = _unwrap(type_)
    if value is None:
        return None
    origin = get_origin(type_)
    if origin is Union or origin is types.UnionType:
        return _construct_union(get_args(type_), value)
    if isinstance(type_, type) and issubclass(type_, BaseModel):
        return construct_model(type_, value) if isinstance(value, dict) else value
    if origin is list and isinstance(value, list):
        (item_type,) = get_args(type_) or (Any,)
        return [construct(item_type, item) for item in value]
    if origin is dict and isinstance(value, dict):
        arguments = get_args(type_)
        value_type = arguments[1] if len(arguments) == 2 else Any
        return {key: construct(value_type, item) for key, item in value.items()}
    if type_ in (dt.datetime, AwareDatetime) and isinstance(value, str):
        try:
            return dt.datetime.fromisoformat(value)
        except ValueError:
            return value
    if type_ is Decimal and isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            return value
    return value


def construct_model(model: type[M], data: dict[str, Any]) -> M:
    values: dict[str, Any] = {}
    known: set[str] = set()
    for name, field in model.model_fields.items():
        key = field.alias or name
        known.add(key)
        if key in data:
            values[name] = construct(field.annotation, data[key])
    extra = {key: value for key, value in data.items() if key not in known}
    return model.model_construct(**values, **extra)


def _unwrap(type_: Any) -> Any:
    while True:
        if type(type_).__name__ == "TypeAliasType" and hasattr(type_, "__value__"):
            type_ = type_.__value__
        elif get_origin(type_) is Annotated:
            type_ = get_args(type_)[0]
        else:
            return type_


def _construct_union(candidates: tuple[Any, ...], value: Any) -> Any:
    options = [_unwrap(candidate) for candidate in candidates if candidate is not type(None)]
    if len(options) == 1:
        return construct(options[0], value)
    if isinstance(value, dict):
        models = [
            option
            for option in options
            if isinstance(option, type) and issubclass(option, BaseModel)
        ]
        for model in models:
            if _matches(model, value):
                return construct_model(model, value)
        return construct_model(models[0], value) if models else value
    for option in options:
        if get_origin(option) is list and isinstance(value, list):
            return construct(option, value)
        if option in (dt.datetime, AwareDatetime) and isinstance(value, str):
            return construct(option, value)
    return value


def _matches(model: type[BaseModel], value: dict[str, Any]) -> bool:
    for name, field in model.model_fields.items():
        key = field.alias or name
        if field.is_required() and key not in value:
            return False
        literal = _unwrap(field.annotation)
        if get_origin(literal) is Literal and key in value and value[key] not in get_args(literal):
            return False
    return True
