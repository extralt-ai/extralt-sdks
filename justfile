# Commands for both SDKs. CI runs these same recipes; each package also works with its own tools
# alone, as CONTRIBUTING.md describes.

# List the recipes.
default:
	@just --list --unsorted

# Run every check CI runs.
check: check-python check-typescript check-workflows

# Python: lockfile, formatting, lint, types and the built distributions.
[working-directory: "python"]
check-python:
	uv lock --check
	uv run ruff format --check .
	uv run ruff check .
	uv run ty check
	uv run scripts/check_package.py

# TypeScript: lockfile, Biome, types and the built package.
[working-directory: "typescript"]
check-typescript:
	bun install --frozen-lockfile
	bun run check
	bun run package:check

# GitHub Actions workflows and the Dependabot configuration, audited by zizmor.
check-workflows:
	uvx zizmor@1.30.1 .

# Format and fix both SDKs in place.
format:
	cd python && uv run ruff format . && uv run ruff check --fix .
	cd typescript && bun run format
