# Commands for both SDKs. CI runs these same recipes; each package also works with its own tools
# alone, as CONTRIBUTING.md describes.

# List the recipes.
default:
	@just --list --unsorted

# Run every check CI runs.
check: check-python check-typescript check-workflows

# Python: lockfile, generated sources, formatting, lint, types, the tests on every supported Python
# and at the dependency floors, and the built distributions.
[working-directory: "python"]
check-python:
	uv lock --check
	uv run scripts/generate.py --check
	uv run ruff format --check .
	uv run ruff check .
	uv run ty check
	for python in 3.11 3.12 3.13 3.14; do uv run --isolated --python "$python" pytest -q || exit 1; done
	uv run --isolated --python 3.11 --resolution lowest-direct pytest -q
	uv run scripts/check_package.py

# TypeScript: lockfile, generated sources, Biome, types, tests, the built package and the runtimes
# it supports (Node.js 22 and current, Bun, Deno and Cloudflare Workers).
[working-directory: "typescript"]
check-typescript:
	bun install --frozen-lockfile
	bun run generate --check
	bun run check
	bun run test
	bun run package:check
	bun run runtimes

# GitHub Actions workflows and the Dependabot configuration, audited by zizmor.
check-workflows:
	uvx zizmor@1.30.1 .

# Format and fix both SDKs in place.
format:
	cd python && uv run ruff format . && uv run ruff check --fix .
	cd typescript && bun run format

# Regenerate both SDKs' sources from openapi.json.
generate:
	cd python && uv run scripts/generate.py
	cd typescript && bun run generate

# Refresh openapi.json from an API document (a URL or a file; staging when omitted), then
# regenerate both SDKs.
spec source="":
	uv run scripts/sync_spec.py {{source}}
	just generate

# Run both SDKs end to end against the staging API. Needs EXTRALT_API_KEY, and creates real
# resources there.
test-staging:
	cd python && uv run pytest -m staging
	cd typescript && bun run test:staging
