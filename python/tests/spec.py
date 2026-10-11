"""Reads the OpenAPI snapshot the SDK is generated from, for contract tests."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import httpx
import jsonschema

SPEC_PATH = Path(__file__).resolve().parents[2] / "openapi.json"
METHODS = ("get", "put", "post", "delete", "patch")


@cache
def spec() -> dict[str, Any]:
    return json.loads(SPEC_PATH.read_text())


@cache
def operations() -> dict[str, tuple[str, str, dict[str, Any]]]:
    """Operation ID to (HTTP method, path template, operation)."""
    found = {}
    for path, item in spec()["paths"].items():
        for method in METHODS:
            if method in item:
                found[item[method]["operationId"]] = (method.upper(), path, item[method])
    return found


def components() -> dict[str, Any]:
    return spec()["components"]


def validate(schema: dict[str, Any], instance: Any) -> None:
    root = {"allOf": [schema], "components": components()}
    jsonschema.Draft202012Validator(
        root, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
    ).validate(instance)


def assert_request_matches(operation_id: str, request: httpx.Request) -> None:
    method, template, operation = operations()[operation_id]
    assert request.method == method, operation_id
    segments = template.split("/")
    actual = request.url.path.split("/")
    assert len(segments) == len(actual), f"{operation_id}: {request.url.path}"
    for expected, value in zip(segments, actual, strict=True):
        assert expected.startswith("{") or expected == value, f"{operation_id}: {request.url.path}"

    parameters = operation.get("parameters", [])
    query = {p["name"]: p for p in parameters if p["in"] == "query"}
    for name in request.url.params:
        assert name in query, f"{operation_id} sends undocumented query parameter {name}"
        validate(query[name].get("schema", {}), _coerce(request.url.params[name], query[name]))
    for name, parameter in query.items():
        if parameter.get("required"):
            assert name in request.url.params, f"{operation_id} omits required {name}"

    headers = {p["name"].lower() for p in parameters if p["in"] == "header"}
    assert ("idempotency-key" in request.headers) == ("idempotency-key" in headers), operation_id

    body = operation.get("requestBody", {}).get("content", {})
    if "application/json" in body:
        validate(body["application/json"]["schema"], json.loads(request.content or b"null"))
    elif body:
        assert request.headers.get("content-type"), f"{operation_id} sends no content type"


def success_response(operation_id: str) -> tuple[int, dict[str, Any] | None]:
    """The documented success status and its JSON schema, if any."""
    _, _, operation = operations()[operation_id]
    status, response = next(
        (code, value) for code, value in operation["responses"].items() if code.startswith("2")
    )
    schema = response.get("content", {}).get("application/json", {}).get("schema")
    return int(status), schema


def example(schema: dict[str, Any], *, future: bool = False) -> Any:
    """A schema-valid instance; `future` adds an unknown field and unknown enum values."""
    if "$ref" in schema:
        return example(components()["schemas"][schema["$ref"].split("/")[-1]], future=future)
    for keyword in ("oneOf", "anyOf"):
        if keyword in schema:
            branches = [branch for branch in schema[keyword] if branch.get("type") != "null"]
            return example(branches[0], future=future)
    if "enum" in schema:
        return "value_added_later" if future else schema["enum"][0]
    kind = schema.get("type")
    if isinstance(kind, list):
        kind = next(item for item in kind if item != "null")
    if kind == "object":
        value = {
            name: example(child, future=future)
            for name, child in schema.get("properties", {}).items()
        }
        if isinstance(schema.get("additionalProperties"), dict) and not value:
            value = {"key": example(schema["additionalProperties"], future=future)}
        if future:
            value["field_added_later"] = {"nested": True}
        return value
    if kind == "array":
        return [example(schema.get("items", {}), future=future)]
    if kind == "string":
        if schema.get("format") == "date-time":
            return "2026-10-08T10:00:00Z"
        if "pattern" in schema:
            return "USD" if "A-Z" in schema["pattern"] else "12.5"
        return "text"
    if kind == "integer":
        return 1
    if kind == "number":
        return 1.5
    if kind == "boolean":
        return True
    return {}


def _coerce(value: str, parameter: dict[str, Any]) -> Any:
    kind = parameter.get("schema", {}).get("type")
    if isinstance(kind, list):
        kind = next((item for item in kind if item != "null"), None)
    if kind == "integer":
        return int(value)
    if kind == "boolean":
        return value == "true"
    return value
