# Repository Instructions

The public repository of the Extralt SDKs: `python/` is the `extralt` package on PyPI and
`typescript/` the `extralt` package on npm, each versioned and released on its own. Both are
clients for the public Extralt API v1, described by `openapi.json`.

## Repository

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

## SDKs

- `openapi.json` is the SDKs' only link to the API. It is refreshed from a published API document
  (`just spec`), never edited by hand. Names and shapes change in the API first; never patch
  generated types to fix a contract.
- Never edit generated files: `python/src/extralt/types.py`, `python/src/extralt/_operations.py`,
  `python/src/extralt/_sync/` and `typescript/src/generated/`. `just generate` rewrites them.
- The sync Python client is rewritten from `_async/` by `scripts/generate.py`. Write async code
  that unasync can convert: import `sleep` from `anyio` and use no other anyio API there. Code that
  needs a different sync and async implementation lives outside `_async/`, as `_files.py` does.
- Every resource method that calls the API marks its operation (`@operation("create_run")` in
  Python, the operation ID in TypeScript); the coverage test relies on it.
- Responses are constructed, not validated, so additive v1 changes never break parsing. Requests are
  not validated client-side; the API is authoritative.
- The TypeScript package exports the API's schemas by name and none of the type generator's own
  types, so that the generator can be replaced without a breaking change. TypeScript stays on 5.9
  while the generator, `openapi-typescript`, needs the compiler API that TypeScript 7 removed.
- README snippets are executed by the tests: keep them runnable.
- Staging tests (`just test-staging`) only read. Never add a call to them that creates, changes or
  deletes anything; the mocked tests cover those requests.
