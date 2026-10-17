# Publication workflow

Use this order as a starting point for your own release instructions. The examples assume a Python package, a GitHub destination, and a version tag; other projects may need different steps. noren does not run your tests, build packages, upload to a registry, create GitHub Releases, or deploy documentation.

## 1. Prepare the first snapshot as public

Review the destination URL, selected paths, file contents, dependency sources, licenses, and data you may redistribute. Keep `noren.yaml` and the forbidden-word file excluded. Add private project, package, and host identifiers to the word list before choosing the source commit.

noren adds commits without rewriting destination history. Removing a file from the next snapshot leaves it readable in previous commits and tags. Making an initially private destination public exposes earlier snapshots too, including the first `--initial` publication. Inspect its entire history before changing visibility; an unpublished package version does not make its Git snapshot private.

## 2. Validate and commit the source

Run the project's tests, formatting, linting, package checks, and documentation build as applicable. For example, in a project that uses pytest and MkDocs:

```sh
uv run pytest -q
uv run mkdocs build --strict
```

Commit the intended source files, configuration, and word list. noren reads all of them from the selected commit. A working-directory correction does not repair an older tag. A tag created before `noren.yaml` was added cannot supply that configuration; select a later commit or create a new tag that includes it.

After review and any required approval, create the intended version tag. For example:

```sh
git tag v1.2.3
```

With a VCS-derived version, check that the tag, the intended package version, and the commit to send agree. The destination commit has a different ID from the source commit. Keep already published tags fixed and use a new version for corrections.

## 3. Review a dry-run

Set the required `branch` key in `noren.yaml` to the destination branch name and commit it. The selected source commit must belong to the local source branch with that same name; remote-tracking branches do not count. A missing branch key, a missing local branch, or a commit outside that branch stops publication. The examples here use `branch: main`, with an existing destination `main`:

```sh
noren publish --tag v1.2.3 --message "Release v1.2.3" > /tmp/noren-check.yaml
```

If the destination branch is absent, add exactly one of `--initial` (no parent) or `--base-tag <tag>` (the commit of an existing destination tag as parent) to both the dry-run and the eventual push. Either option is rejected when the branch already exists, and they cannot be combined. A base tag must exist at the destination and point to a commit, directly or through an annotated tag; noren fetches it from there. Dry-run still needs Git access to read destination references. Without a configured author, noren also needs the authenticated GitHub CLI identity.

Check the exit code, stderr, `source_commit`, `destination`, `branch`, `author`, every entry in `files`, and `destination_branch_before`. The YAML always has nine keys, including on errors; `branch` is null until the settings supply its name, and `destination_branch_before` is null when the destination branch is absent or an empty string when unread. Compare added and removed files with the previous snapshot; [snapshots and tests](snapshots-and-tests.md) shows an example. Keep the review output outside the public selection.

## 4. Send the reviewed snapshot

Use the same selector, message, and initial-publication option, adding only `--push`:

```sh
noren publish --tag v1.2.3 --message "Release v1.2.3" --push
git ls-remote --refs https://github.com/OWNER/public-project.git refs/heads/main refs/tags/v1.2.3
```

Successful publication reports `pushed: true` and a destination `commit`. Check that the requested references identify that destination commit, replacing `main` in the example with the output's `branch`. With `--tag`, the branch and tag move together in one atomic push without force; with `--commit`, only the branch moves. If a push result is uncertain, follow the [README's verification procedure](https://github.com/sync-dev-org/noren#verify-the-result) before retrying. Source Git hooks, including `pre-push`, do not run; run additional checks before this step.

## 5. Build and inspect the release packages

Prefer building from a checkout of the published destination tag: it contains the selected files and a matching tag name for VCS version tools. Build hooks can still add files and metadata, so inspect the actual output. If you build from the source repository instead, configure the packaging tool separately to exclude private settings and development files.

Use a fresh output directory and review the exact artifacts you will upload. Examples in a suitable checkout are:

```sh
uv build
uvx twine check dist/*.tar.gz dist/*.whl
```

Inspect archive paths, contents, generated versions, license files, metadata, README links, and dependency URLs with the same forbidden-word list. [Package checks](package-checks.md) explains the boundary between noren's check and this check. A successful noren dry-run does not inspect an sdist or wheel.

## 6. Upload only inspected artifacts

Send with noren and finish package inspection before a registry upload. For example, after replacing the filenames with those inspected:

```sh
uv publish dist/project-1.2.3.tar.gz dist/project-1.2.3-py3-none-any.whl
```

Use the registry's supported authentication method. Keep credentials out of source files, command arguments, and logs. Do not rely on deletion to undo exposure: a reported registry file remained downloadable from its CDN about 45 hours after deletion. That is one observation, not a retention-period guarantee for any registry.

## 7. Verify the tag and create a GitHub Release

A GitHub Release is separate from noren's destination tag. An example targeting the public repository is:

```sh
gh release create v1.2.3 --repo OWNER/public-project --verify-tag \
  --title "v1.2.3" --notes-file release-notes.md
```

Review release notes and any attached packages before publishing them; noren has not checked files outside its selected snapshot. Destination tags are lightweight and point directly to the snapshot commit. An annotated source tag's message is not copied.

## 8. Verify documentation and registry downloads

For a private development repository and a public publication repository, build the documentation on the public repository's GitHub Pages from the sources sent by noren. This keeps the published site tied to the inspected files. The [documentation tips](snapshots-and-tests.md) explain why direct publication from the development repository bypasses that check.

The public repository's workflow can start as soon as noren updates a branch that triggers it; wait for it and verify the result. Check which branches your workflow publishes before sending a maintenance snapshot. `mkdocs build --strict` validates a build locally; it does not publish it. See [GitHub's Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) and [MkDocs deployment options](https://www.mkdocs.org/user-guide/deploying-your-docs/).

Open the published site, follow README links, switch languages if provided, and check representative searches. Compare the registry's version, license, project URLs, and downloadable file SHA-256 values with the inspected artifacts. Check the rendered package README as well.

## Documentation corrections without a new version

For a correction that needs no new version, commit it and use its hexadecimal ID, for example:

```sh
noren publish --commit a1b2c3d --message "Correct the documentation"
noren publish --commit a1b2c3d --message "Correct the documentation" --push
```

Replace the ID with yours. `--commit` creates no destination tag and does not publish a package or a GitHub Release. Deploy or verify documentation as your project requires. Check the configured destination branch before retrying an uncertain push; there is no destination tag to prevent a duplicate snapshot.

## Publish a maintenance series

To maintain 1.x after 2.x has moved onto `main`, create a local source branch such as `v1` from the last 1.x source release:

```sh
git switch -c v1 v1.2.3
```

Change only the `branch` setting in `noren.yaml` to `v1`, keeping the other settings, then commit it with the maintenance corrections before choosing the new source tag:

```yaml
branch: v1
```

```sh
git add noren.yaml
git commit -m "Configure maintenance publication branch"
git tag v1.2.4
```

The inherited `branch: main` must be changed: a maintenance-only source commit does not belong to local `main` and will be rejected. An older common ancestor can belong to both branches, so also review the configured name and the dry-run's `branch` value.

If destination `v1` is absent and destination tag `v1.2.3` identifies the last public 1.x release, check and send the first maintenance snapshot with that tag as its parent:

```sh
noren publish --tag v1.2.4 --message "Release v1.2.4" --base-tag v1.2.3
noren publish --tag v1.2.4 --message "Release v1.2.4" --base-tag v1.2.3 --push
git ls-remote --refs https://github.com/OWNER/public-project.git refs/heads/v1 refs/tags/v1.2.4
```

Expect `branch: v1` and `destination_branch_before: null`. The new destination commit has the destination tag's commit as its only parent; destination `main` stays unchanged. Use `--initial` instead only when you deliberately want no parent. A missing base tag or one pointing to a non-commit object stops both dry-run and push.

For subsequent maintenance tags, keep `branch: v1` and omit both first-publication options. Each publication extends the existing destination `v1` tip. Use `--commit` for corrections that need no destination tag. Build and inspect packages from the published tag, then create the public repository's GitHub Release using its existing tag, for example:

```sh
gh release create v1.2.4 --repo OWNER/public-project --verify-tag \
  --title "v1.2.4" --notes-file release-notes.md
```

noren sends the branch and tag; package uploads, GitHub Releases, and documentation deployment still follow your project's release instructions.
