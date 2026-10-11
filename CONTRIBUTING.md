# Contributing

## Setup

The Python SDK needs [uv](https://docs.astral.sh/uv/). The TypeScript SDK needs
[Bun](https://bun.sh), Node.js 22 or later and, for the runtime checks, [Deno](https://deno.com).
[just](https://just.systems) runs both from the repository root:

```bash
just check             # everything CI runs
just check-python
just check-typescript
just check-workflows   # zizmor on the GitHub Actions workflows
just format
just generate          # rewrite both SDKs' generated sources from openapi.json
```

`just check` runs each SDK as a release would: generated sources, lint and types, the tests on
Python 3.11 to 3.14 and at the dependency floors, the README snippets, the built packages, and the
TypeScript build on Node.js 22 and current, Bun, Deno and Cloudflare Workers.

Each package also works with its own tools alone:

```bash
cd python
uv run scripts/generate.py        # types.py, _operations.py and the sync client
uv run ruff check
uv run ty check
uv run pytest                     # includes the README snippets
uv run scripts/check_package.py   # builds the distributions and installs them

cd typescript
bun install
bun run generate                  # src/generated/
bun run check                     # Biome and tsc
bun run test                      # includes the README snippets
bun run package:check             # build, publint and Are the Types Wrong
bun run runtimes                  # the build on Node.js 22 and current, Bun, Deno and workerd
```

## The API contract

`openapi.json` is the public `/v1` API document and the SDKs' only input: types, the operation
tables and the contract tests all derive from it. It is never edited by hand. To refresh it from
the API and regenerate both SDKs:

```bash
just spec             # from the production API
just spec staging     # from the staging API
```

A URL or a file path works in place of `staging`.

## Staging tests

`just test-staging` runs both SDKs end to end against the staging API. It needs `EXTRALT_API_KEY`
set to a staging key, so it is not part of `just check`. These tests only read what the
organization already has. They never create, change or delete anything; the mocked tests cover
those requests.

## Pull requests

Pull requests are squash-merged, so the PR title becomes the commit on `main`. Titles follow
[Conventional Commits](https://www.conventionalcommits.org/), scoped to the package they change:
`feat(python): ...`, `fix(typescript): ...`. `feat`, `fix`, `perf`, `revert` and `docs` go into the
next release's changelog and call for a release of the package they change: before `1.0`, a `feat`
or a breaking change (`!` after the type) makes it a minor release, anything else a patch. `chore`,
`ci`, `test`, `refactor`, `build` and `style` are left out of the changelog and don't call for a
release on their own.

## Releases

release-please keeps one release PR open per package and updates it on every merge to `main`, so it
always shows the next version and the changelog of everything merged since the last release.
Nothing is released until that PR is merged. Merging it tags the release (`python-v0.1.0`,
`typescript-v0.1.0`) and publishes the package to PyPI or npm through Trusted Publishing once a
maintainer approves the deployment. Versions and changelogs are never edited by hand.
