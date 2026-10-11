"""Refresh openapi.json, the SDKs' only input, from a published Extralt OpenAPI document.

Usage: uv run scripts/sync_spec.py [SOURCE] [--check]

SOURCE is `production` (the default), `staging`, a URL, a file path or `-` for stdin. The snapshot
keeps the public `/v1` operations with Bearer API-key auth and production as its server.
`--check` fails instead of writing when the snapshot differs. The API's version changes with every
deploy and is not part of the contract: a document that differs only by it leaves the snapshot as
it is.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SOURCES = {
    "production": "https://api.extralt.com/api-docs/openapi.json",
    "staging": "https://api.extralt.dev/api-docs/openapi.json",
}
DEFAULT_SOURCE = "production"
PRODUCTION_SERVER = "https://api.extralt.com"
SNAPSHOT = Path(__file__).resolve().parent.parent / "openapi.json"
METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")


def load(source: str) -> dict[str, Any]:
    source = SOURCES.get(source, source)
    if source == "-":
        return json.load(sys.stdin)
    if source.startswith(("https://", "http://")):
        return fetch(source)
    return json.loads(Path(source).read_text())


def fetch(url: str, attempts: int = 4) -> dict[str, Any]:
    """Retries server and network errors: an idle API answers 503 while it starts."""
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.load(response)
        except urllib.error.URLError as error:
            client_error = isinstance(error, urllib.error.HTTPError) and error.code < 500
            if client_error or attempt == attempts:
                raise
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def referenced_schemas(value: Any, names: set[str]) -> None:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            names.add(ref.removeprefix("#/components/schemas/"))
        for child in value.values():
            referenced_schemas(child, names)
    elif isinstance(value, list):
        for child in value:
            referenced_schemas(child, names)


def public_document(document: dict[str, Any]) -> dict[str, Any]:
    paths = {path: item for path, item in document["paths"].items() if path.startswith("/v1/")}
    schemas = document["components"]["schemas"]

    reachable: set[str] = set()
    pending: set[str] = set()
    referenced_schemas(paths, pending)
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        referenced_schemas(schemas[name], pending)

    problems = []
    for path, item in paths.items():
        for method in METHODS:
            operation = item.get(method)
            if operation is None:
                continue
            if not operation.get("operationId"):
                problems.append(f"{method.upper()} {path} has no operationId")
            if not isinstance(operation.get("x-extralt-idempotent"), bool):
                problems.append(f"{method.upper()} {path} does not declare x-extralt-idempotent")
    if problems:
        raise SystemExit("\n".join(problems))

    components = dict(document["components"])
    components["schemas"] = {name: schemas[name] for name in sorted(reachable)}
    components["securitySchemes"] = {"bearer_auth": components["securitySchemes"]["bearer_auth"]}
    return {
        **document,
        "servers": [{"url": PRODUCTION_SERVER}],
        "security": [{"bearer_auth": []}],
        "paths": paths,
        "components": components,
    }


def contract(document: dict[str, Any]) -> dict[str, Any]:
    info = {key: value for key, value in document["info"].items() if key != "version"}
    return {**document, "info": info}


def main(arguments: list[str]) -> None:
    check = "--check" in arguments
    sources = [argument for argument in arguments if argument != "--check"]
    if len(sources) > 1:
        raise SystemExit(__doc__)
    document = public_document(load(sources[0] if sources else DEFAULT_SOURCE))

    if SNAPSHOT.exists() and contract(json.loads(SNAPSHOT.read_text())) == contract(document):
        print("openapi.json matches the source document")
        return
    if check:
        raise SystemExit("openapi.json is stale; run scripts/sync_spec.py")
    SNAPSHOT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {SNAPSHOT.name}")


if __name__ == "__main__":
    main(sys.argv[1:])
