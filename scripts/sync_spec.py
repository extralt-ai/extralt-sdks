"""Refresh openapi.json, the SDKs' only input, from a published Extralt OpenAPI document.

Usage: uv run scripts/sync_spec.py [SOURCE] [--check]

SOURCE is a URL, a file path or `-` for stdin; it defaults to the staging document. The snapshot
keeps the public `/v1` operations with Bearer API-key auth and production as its server.
`--check` fails instead of writing when the snapshot differs.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_SOURCE = "https://api.extralt.dev/api-docs/openapi.json"
PRODUCTION_SERVER = "https://api.extralt.com"
SNAPSHOT = Path(__file__).resolve().parent.parent / "openapi.json"
METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")


def load(source: str) -> dict[str, Any]:
    if source == "-":
        return json.load(sys.stdin)
    if source.startswith(("https://", "http://")):
        with urllib.request.urlopen(source, timeout=30) as response:
            return json.load(response)
    return json.loads(Path(source).read_text())


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


def main(arguments: list[str]) -> None:
    check = "--check" in arguments
    sources = [argument for argument in arguments if argument != "--check"]
    if len(sources) > 1:
        raise SystemExit(__doc__)
    snapshot = json.dumps(public_document(load(sources[0] if sources else DEFAULT_SOURCE)), indent=2, sort_keys=True) + "\n"

    if check:
        if not SNAPSHOT.exists() or SNAPSHOT.read_text() != snapshot:
            raise SystemExit("openapi.json is stale; run scripts/sync_spec.py")
        print("openapi.json matches the source document")
        return
    SNAPSHOT.write_text(snapshot)
    print(f"Wrote {SNAPSHOT.name}")


if __name__ == "__main__":
    main(sys.argv[1:])
