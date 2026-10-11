# Repository Instructions

The public repository of the Extralt SDKs: `python/` is the `extralt` package on PyPI and
`typescript/` the `extralt` package on npm, each versioned and released on its own. Both are
placeholders until `0.1.0`.

- The root justfile is the command source of truth, and CI runs the same recipes. Run `just check`
  before finishing. Recipes only call `uv` and the `package.json` scripts, so each package stays
  usable with its own tools alone.
- Never commit secrets, tokens or `.env` files. Packages publish through Trusted Publishing; never
  add registry tokens.
- PR titles follow Conventional Commits as CONTRIBUTING.md describes; release-please derives
  versions and changelogs from them. Never edit versions, `CHANGELOG.md` files or
  `.release-please-manifest.json` by hand.
- Workflows pin every action to a full commit SHA with its version in a comment, start from
  `permissions: {}` and grant each job only what it needs, never persist checkout credentials, and
  pass untrusted context such as PR titles through `env`. `just check-workflows` (zizmor) enforces
  most of this.
