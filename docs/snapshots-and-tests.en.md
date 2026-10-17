# Snapshots and tests

## Publish documentation from the public repository

When noren sends a private development repository to a public publication repository, build and publish MkDocs documentation on the publication repository's GitHub Pages, using the sources sent by noren. Publishing directly from the development repository creates a route that bypasses noren's selection and forbidden-word check; the published site can then differ from the inspected sources.

Keep the site's source files, configuration, build dependency lock, and Pages workflow in the public selection. Restrict the publication workflow to the public repository. `exclude` wins over `include`, so excluding all of `.github/` also excludes an included workflow. Narrow the exclusions to private files, such as issue templates, and check the actual dry-run selection.

For noren's own documentation, the public repository's workflow installs dependencies with `uv sync --locked --no-install-project`, builds both languages with `uv run --locked --no-sync mkdocs build --strict`, and deploys the Pages artifact. The same build works from a public checkout; no private configuration is required. See [GitHub's custom Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

A workflow restricted to the public repository first runs after noren sends it, so local builds and tests do not catch a broken action reference. Before sending, confirm that every `uses:` reference exists in the action's repository, for example with `git ls-remote https://github.com/<owner>/<action> <ref>`. Do not assume a major version tag exists: some actions publish only full version tags, so `astral-sh/setup-uv@v9` cannot be resolved while `astral-sh/setup-uv@v9.0.0` can. If you pin actions to full commit SHAs, resolve each SHA from its tag when you write the workflow and keep the version as a comment; a missing tag then fails at that point instead of during publication.

## Keep development details out of public documentation

Write the public site and README for public users. Leave out secrets and authentication details, development environment configuration, host names, internal paths, development tool settings, private repository names, and internal procedures. Explain reproducible public usage instead.

Put internal names in the excluded forbidden-word file and check the selected sources with noren before publication. Read the public files as well: a forbidden-word list cannot identify every sensitive detail or prove that the whole document is appropriate to publish. Do not copy private reports, internal links, logs, or example values into public guides.

## Classify paths without hiding new files

Root-anchored directory rules, such as `/src/`, `/tests/`, and `/docs/`, let file changes within those directories follow their classification. A new top-level path remains unclassified until you choose whether it belongs in `include` or `exclude`. Exclude development instructions, private scripts, settings, and the word list explicitly. A matching exclusion takes precedence over an inclusion.

Keep the original source URL and repository name written by `noren init` in the word list. Add private dependency, application, package, and host identifiers. The word list has no comment syntax: a nonblank line beginning with `#` is still a forbidden phrase.

Commit corrections before choosing a tag or commit ID. An older tag does not see new settings. The required `branch` key names both the destination branch and a local source branch that must contain the selected commit; remote-tracking branches cannot substitute for it. `noren init` supplies `branch: main`, but existing configurations must also contain that key. Review both `destination` and `branch` rather than assuming the configured names are the intended publication target.

If the destination branch is absent, use either `--initial` for a parentless commit or `--base-tag <tag>` for a commit based on an existing destination tag. Use the same option in dry-run and push. Both options together, either option on an existing branch, a missing base tag, or a base tag pointing to a non-commit object stop publication. See the [maintenance workflow](publication-workflow.md#publish-a-maintenance-series) for branching from an existing public release.

## Compare dry-run files with a destination snapshot

Save the successful dry-run YAML, then compare its `files` with a checkout of the configured destination branch. For example, replace `../public-checkout` with that checkout, and replace `main` with the output's `branch`:

```sh
noren publish --commit a1b2c3d --message "Review snapshot" > /tmp/noren-check.yaml
git -C ../public-checkout fetch origin main
git -C ../public-checkout ls-tree -rz --name-only origin/main > /tmp/noren-previous-files
```

Replace the source commit ID too. In an environment with PyYAML installed:

```sh
python - <<'PY'
from pathlib import Path
import yaml

result = yaml.safe_load(Path("/tmp/noren-check.yaml").read_text())
selected = set(result["files"])
previous = set(Path("/tmp/noren-previous-files").read_bytes().decode().split("\0")) - {""}
print("Added:", sorted(selected - previous))
print("Removed:", sorted(previous - selected))
PY
```

Inspect every change. Fetching first avoids comparing with a stale local branch. For a first snapshot with `--initial`, compare with an empty file set; with `--base-tag`, compare with the destination tag's tree. After sending, the tree of the reported destination commit should contain exactly the selected paths; read the destination history if the branch has advanced. File-set equality does not check contents or erase older snapshots.

## Test configuration without importing noren internals

noren's commands and YAML output are its stable interface. Its Python modules are internal and can change between versions. Test your own configuration and word-list data without importing noren internals. A dry-run is an integration check: it reads a committed tree, needs destination Git access, and may need GitHub CLI identity. It does not inspect uncommitted changes and is not an offline unit test.

Published tests should not spell private names as literals or split strings to evade the check. Read those names from the excluded word-list file. For example, a pytest module directly under `tests/` can load it this way:

```python
from pathlib import Path
import pytest

word_list = Path(__file__).resolve().parents[1] / "noren-words.txt"
if not word_list.is_file():
    pytest.skip("Source-only word list is absent", allow_module_level=True)
forbidden_words = [
    line.strip()
    for line in word_list.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
```

Use those values in the checks that need them. Skip only source-specific tests when excluded inputs are absent in a public checkout; keep ordinary package tests running there. Do not silently skip a missing configuration in the source repository: check that the source-only tests run as part of its validation. Test real built packages when the promise concerns [package contents](package-checks.md).

## Migrate an existing publication process

At the same source commit, compare the old process's selected file set with noren's dry-run `files`. Explain each difference before sending. Separately compare package members; generated metadata can account for differences, but it still needs inspection. Run applicable tests from a directory containing only the selected files to expose dependencies on private inputs.

After an upgrade, check `noren --version` and repeat a dry-run against the intended commit. The reported 0.2-to-0.3 upgrades needed no configuration changes in those projects; that is not a compatibility guarantee for every setup. Current `--commit` accepts unique hexadecimal abbreviations; do not turn an unverified recollection about an older version into a requirement for full-length IDs.

If you rename the source repository and reuse its old name for the public repository, inspect managed clones' remote URLs before publication. One report found that the old name then resolved to the new public repository instead of redirecting to the renamed source. If moving a checkout leaves virtual-environment scripts pointing to its old path, recreate the environment using your dependency tool. These are environment observations, not operations performed by noren.
