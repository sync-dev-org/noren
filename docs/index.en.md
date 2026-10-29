# Publication with noren

noren sends selected files to another Git repository as one commit. A package upload, a GitHub Release, and a documentation deployment are separate operations. These guides explain how to put those operations together and where to check what becomes public.

For installation, initial setup, command usage, and result fields, start with the [README](https://github.com/sync-dev-org/noren#readme). For command help, run:

```sh
noren --help
noren init --help
noren publish --help
```

## Choose a guide

- [Operating essentials](operating-essentials.md): recommendations for separating development from publication, checking public content, and handling releases.
- [Publication workflow](publication-workflow.md): a suggested order from preparation through registry and documentation verification.
- [Package checks](package-checks.md): inspect sdist and wheel contents, generated metadata, private identifiers, and published downloads.
- [Snapshots and tests](snapshots-and-tests.md): compare selected files, test configuration without network access, and migrate an existing publication process.

## How to use these recommendations

The recommendations draw on first-hand publication reports collected in October 2026, mainly with noren 0.2–0.3, uv, Hatchling, and hatch-vcs. The reports were not independently reproduced as a universal workflow. Where a report establishes only an observation or a possible cause, the guide keeps that limit. A build backend or registry with different settings can behave differently.

Commands are examples to adapt to your project, version, destination, build backend, registry, and approval process. They are not a project's release instructions. Follow the current documentation for the tools you use.

English and Japanese have the same five guides. Use the language selector to switch to the corresponding page.

## Preview this documentation

In a checkout of noren with uv installed:

```sh
uv sync --locked
uv run --locked mkdocs build --strict
uv run --locked mkdocs serve
```

One MkDocs configuration builds English at the site root and Japanese under `ja/`, using Material for MkDocs and mkdocs-static-i18n. The dependency versions are recorded in `uv.lock`.
