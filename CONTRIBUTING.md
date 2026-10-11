# Contributing

## Setup

The Python SDK needs [uv](https://docs.astral.sh/uv/). The TypeScript SDK needs
[Bun](https://bun.sh) and Node.js 22 or later. [just](https://just.systems) runs both from the
repository root:

```bash
just check             # everything CI runs
just check-python
just check-typescript
just check-workflows   # zizmor on the GitHub Actions workflows
just format
```

Each package also works with its own tools alone:

```bash
cd python
uv run ruff check
uv run ty check
uv run scripts/check_package.py   # builds the distributions and installs them

cd typescript
bun install
bun run check                     # Biome and tsc
bun run package:check             # build, publint and Are the Types Wrong
```

## Pull requests

Pull requests are squash-merged, so the PR title becomes the commit on `main`. Titles follow
[Conventional Commits](https://www.conventionalcommits.org/), scoped to the package they change:
`feat(python): ...`, `fix(typescript): ...`. `feat`, `fix`, `perf` and `revert` go into the next
release's changelog and set its version: before `1.0`, a `feat` or a breaking change (`!` after the
type) makes it a minor release, anything else a patch. `chore`, `docs`, `ci`, `test`, `refactor` and
`build` are left out of the changelog and don't call for a release on their own.

## Releases

release-please keeps one release PR open per package and updates it on every merge to `main`, so it
always shows the next version and the changelog of everything merged since the last release.
Nothing is released until that PR is merged. Merging it tags the release (`python-v0.1.0`,
`typescript-v0.1.0`) and publishes the package to PyPI or npm through Trusted Publishing once a
maintainer approves the deployment. Versions and changelogs are never edited by hand.
