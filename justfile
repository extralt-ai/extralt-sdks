# Commands for both SDKs. CI runs these same recipes; each package also works with its own tools
# alone, as CONTRIBUTING.md describes.

# List the recipes.
default:
	@just --list --unsorted

# Run every check CI runs.
check: check-python check-typescript check-workflows

# Python: lockfile, generated sources, lint, types, tests on 3.11 to 3.14 and at the dependency floors, built package.
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

# TypeScript: lockfile, generated sources, Biome, types, tests, built package on Node.js, Bun, Deno and Workers.
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

# Refresh openapi.json from the production API and regenerate both SDKs; `just spec staging` reads staging instead.
spec source="production":
	uv run scripts/sync_spec.py {{source}}
	just generate

# Run both SDKs end to end against the staging API. Needs EXTRALT_API_KEY. The tests only read.
test-staging:
	cd python && uv run pytest -m staging
	cd typescript && bun run test:staging
