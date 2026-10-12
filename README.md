# noren

[日本語](README.ja.md)

noren sends selected files from one Git repository to another as a single commit; it does not publish packages to a registry.

Use it, for example, to send a public snapshot of a private repository to GitHub. The destination receives the selected files, the commit message you supply, and the configured author and committer. Source commits, their messages, and annotated-tag messages are not copied. File paths and file contents that you select are copied.

## Install and choose how to run

You need Python 3.12 or later, Git, and [uv](https://docs.astral.sh/uv/). Run commands inside the source Git repository.

Add noren as a development dependency of your Python project:

```sh
uv add --dev noren
uv run noren --help
```

Alternatively, [uvx](https://docs.astral.sh/uv/guides/tools/) runs noren in an isolated environment without adding it to your project's dependencies:

```sh
uvx noren --help
```

The examples below use `uv run noren`. If you chose uvx, replace that prefix with `uvx noren`. If noren is already available in your environment, you can use `noren` directly. `noren init` and `noren publish` work without interactive input.

To check the installed version, run `uv run noren --version`. It prints the version derived from Git tags on one line and exits with 0; it also works outside a Git repository.

## Initial setup

The source repository must have an `origin` remote. Create a separate destination repository on GitHub and make sure your usual Git authentication can read it and push to it. noren uses `https://github.com/OWNER/REPO.git`, with your existing Git configuration.

```sh
uv run noren init
```

`noren init` takes no arguments and creates `noren.yaml` and `noren-words.txt` at the source repository root, even when run from a subdirectory. It prints setup instructions, exits with 0 on success, and reports errors to stderr with a nonzero exit code. It refuses to overwrite either file and creates neither file if `origin` is missing.

### Configure noren.yaml

Edit the generated template. This example sends `README.md`, `LICENSE`, and files under `src/`, except `src/internal/`. Replace `OWNER/public-project` with your destination:

```yaml
destination: OWNER/public-project
include: |
  README.md
  LICENSE
  src/
exclude: |
  src/internal/
  private/
  tests/
  .github/
  .nf/
  .gitignore
  pyproject.toml
  uv.lock
  noren.yaml
  noren-words.txt
word-list: noren-words.txt
author:
  name: Release Bot
  email: release@example.invalid
```

| Key | What to write |
| --- | --- |
| `destination` | The destination's GitHub `OWNER/REPO`, rather than a URL. The source repository itself is rejected. |
| `include` | Files to send, as a multiline string in `.gitignore` syntax. |
| `exclude` | Files to leave out, in the same syntax. If both lists match a file, `exclude` wins. |
| `word-list` | The forbidden-word file's path, relative to the repository root. The file must be inside the repository. |
| `author` | Optional `name` and `email`. Both the destination commit's author and committer use these values. Replace the example identity with yours. |

Every file in the selected source commit's tree must match `include` or `exclude`; a file in neither list stops the command. These lists classify tracked files in that commit, not untracked files in the working directory. Each list follows Git's `.gitignore` rules, including `#` comments, `!` negation, `/`-anchored paths, and `**`. Within a list, later matching rules take precedence. A negated child pattern cannot bring back a file while its parent directory remains excluded.

Keep the configuration and forbidden-word file in `exclude`, and add rules for any other tracked files in your repository. If you change `word-list`, update its exclusion too. All four required keys must be present; an explicitly empty `include` or `exclude` string is allowed, but every file still needs classification.

If you omit `author`, noren uses the authenticated [GitHub CLI](https://cli.github.com/) account when `gh` is available: its name (or username if the name is empty) and `ID+USERNAME@users.noreply.github.com`. If that account cannot be obtained, noren stops and asks you to configure `author.name` and `author.email`. `gh` is optional and only supplies this default identity; push authentication comes from Git.

For SSH authentication, you can configure Git to rewrite the GitHub HTTPS URLs inside this source repository:

```sh
git config --local url."git@github.com:".insteadOf https://github.com/
```

### Configure noren-words.txt

Write one forbidden word or phrase per line. The generated file already contains the source `origin` URL and its repository name. Keep those entries and add identifiers or text that must not appear in selected file contents. For example, with `origin` set to `git@github.com:OWNER/source-private.git`:

```text
git@github.com:OWNER/source-private.git
source-private
internal-project
private@example.invalid
```

The list must contain at least one nonblank line. Every nonblank line is an entry, including a line beginning with `#`; the word list has no comment syntax. noren compares substrings after Unicode NFKC normalization and case folding, so case and full-width forms also match. Bytes that cannot be decoded as UTF-8 are replaced for the inspection. The files are sent with their original bytes.

If published tests check private names, writing those names as literals in the tests can trigger forbidden-word rejection. Read the names from the excluded word-list file instead. For example, a test file directly under `tests/` can load the list as follows; run checks that need this excluded file in the source repository:

```python
from pathlib import Path

word_list = Path(__file__).resolve().parents[1] / "noren-words.txt"
forbidden_words = [
    line.strip()
    for line in word_list.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
```

### Commit the settings before selecting a tag or commit ID

noren reads the selected files, `noren.yaml`, and the word list from the commit named by `--tag` or `--commit`. Changes in the working directory or later commits do not affect that commit's check or publication.

Commit the source files you intend to send, then commit the settings:

```sh
git add noren.yaml noren-words.txt
git commit -m "Configure noren"
```

Use `--tag` when you want to put the same tag name on the destination:

```sh
git tag v1.0.0
```

For changes that do not increase the version, such as correcting a README, use `--commit` to send without creating a destination tag. Obtain the source commit ID with `git rev-parse HEAD`, then pass the printed ID to `--commit`. Only hexadecimal commit IDs and unique abbreviations are accepted; `HEAD`, branch names, tag names, nonexistent IDs, and ambiguous abbreviations stop the command.

If you correct settings or file contents after a failed check, commit the correction and choose a tag or commit ID that contains it before checking again.

Tags and commits created before you added `noren.yaml` cannot be sent, because noren reads the settings from the selected commit. For the first publication after adopting noren, create a new tag, or choose a commit ID, that contains the committed settings.

### Keep the settings out of packages you build

`noren.yaml` and the word list are committed to the source repository, and the word list names the private identifiers you want to keep in. noren never sends them unless you include them, but other tools that package the source repository can. For example, a Python sdist built from the source checkout includes every tracked file by default, so publishing it to PyPI would publish the word list.

Build packages from the destination repository, which holds only the selected files, or exclude the settings in the packaging tool. With hatchling:

```toml
[tool.hatch.build.targets.sdist]
exclude = ["/noren.yaml", "/noren-words.txt"]
```

If the packaging tool selects files with an allow list, such as hatchling's `only-include`, the two settings files stay out unless the list names them, and adding them to `exclude` has no effect. In either case, check the files in built packages before publishing them.

Sending with noren before publishing to a package registry lets the forbidden-word check run before that irreversible publication.

## Check before sending

`noren publish` defaults to dry-run. Exactly one of `--tag` or `--commit` is required; providing both or neither stops the command. `--message` is also required, even for a check. For the first publication, when the destination has no `main` branch:

```sh
uv run noren publish --tag v1.0.0 --message "Release v1.0.0" --initial
```

For a tag containing only `README.md` and `src/app.py` among the included files, a successful first check prints:

```yaml
tag: v1.0.0
source_commit: 0123456789abcdef0123456789abcdef01234567
destination: OWNER/public-project
author:
  name: Release Bot
  email: release@example.invalid
files:
- README.md
- src/app.py
destination_main_before: null
commit: null
pushed: false
```

Check `source_commit`, `destination`, `author`, and every path in `files`. The printed `author.name` and `author.email` will be used for both the destination commit's author and committer. Dry-run creates no destination commit and updates no destination branches or tags, but it reads the destination's references, so Git access is needed. A successful dry-run does not guarantee permission to push.

The command exits with 0 if the check succeeds. It exits with a nonzero code and writes the reason to stderr if, for example, a file is in neither list, selected contents contain a forbidden word, a required setting or a nonempty word list is missing, or the destination cannot be read. Unclassified-file errors list paths; forbidden-word errors identify the file and line. Selected submodules must be excluded; symlinks are inspected using their link target text and sent as symlinks.

Use `--initial` only when destination `main` is absent, for both dry-run and push, with either source selector. noren stops if `--initial` is given and `main` already exists, or if `--initial` is omitted and `main` does not exist. With `--tag`, an existing destination tag of the requested name also stops publication.

## Send the checked files

Add `--push` to the command you checked:

```sh
uv run noren publish --tag v1.0.0 --message "Release v1.0.0" --initial --push
```

The first publication creates a commit with no parent. Each later publication adds one commit whose only parent is the destination's previous `main` tip. Its tree contains exactly the selected source files; files absent from the selection are absent from the new destination tree. With `--tag`, noren updates destination `main` and a tag with the source tag's name together in one atomic push, without force. The destination tag is lightweight (not annotated) and points directly to the new commit, even if the source tag is annotated. With `--commit`, noren updates only destination `main` and creates no tag.

noren pushes with `--no-verify`, so Git hooks in the source repository, such as `pre-push`, do not run. Run any additional checks, such as secret scanning, before you send.

For a later source tag, omit `--initial`:

```sh
uv run noren publish --tag v1.1.0 --message "Release v1.1.0"
uv run noren publish --tag v1.1.0 --message "Release v1.1.0" --push
```

To send a README correction without a tag, replace the example ID below with your source commit ID. Check and send the same ID:

```sh
uv run noren publish --commit a1b2c3d --message "Correct the README"
uv run noren publish --commit a1b2c3d --message "Correct the README" --push
```

Add `--initial` to both commands if destination `main` does not exist yet. With `--commit`, the result has `tag: null` and `source_commit` contains the full ID even when you supplied an abbreviation.

Choose a destination commit message appropriate for the files you are sending. noren uses that message instead of the source commit messages.

## Verify the result

`noren publish` writes one YAML document to stdout on success and failure. Save this document and stderr, and check the exit code. To save the output of the later push above, use this form in place of that push command:

```sh
uv run noren publish --tag v1.1.0 --message "Release v1.1.0" --push > /tmp/noren-result.yaml 2> /tmp/noren-error.txt
```

| Key | Meaning |
| --- | --- |
| `tag` | The requested source tag name; `null` with `--commit`, or an empty string if no selector is available. |
| `source_commit` | The full ID of the source commit read for publication; `null` if the command stopped before resolving it. |
| `destination` | The destination `OWNER/REPO`; an empty string if unavailable. |
| `author` | The resolved `name` and `email` used for both the destination commit's author and committer; `null` if the command stopped before resolving the identity. |
| `files` | The selected file paths as a YAML list, possibly empty. This list alone does not indicate a successful check or push. |
| `destination_main_before` | The destination's `main` commit ID read before sending. `null` means the destination was read and `main` was absent; `''` means that value could not be obtained. |
| `commit` | The created destination commit ID. `null` for dry-run or a failure before creating a commit. |
| `pushed` | `true` when Git reported that destination `main` and, with `--tag`, the requested tag were updated; `false` for dry-run or when the command could not confirm a successful push. |

A successful push exits with 0 and has `pushed: true` and a non-null `commit`. The ID is the destination commit's ID, not the source commit's ID.

If a push fails or its result is uncertain and `commit` is non-null, keep that ID and `destination_main_before`. `pushed: false` by itself cannot establish whether the remote received the update. Read the destination references, replacing the example repository and tag with those in your result:

```sh
git ls-remote --refs https://github.com/OWNER/public-project.git refs/heads/main refs/tags/v1.1.0
```

If both references show the printed `commit` ID, the update is present. If `main` has advanced since then, a matching tag still identifies the published snapshot; check the destination history to confirm that commit is an ancestor of the current `main`. If `main` still equals `destination_main_before` and the tag is absent, the update is not present at the time of the check. If the references differ otherwise, inspect the destination history before deciding what to do. A failed `ls-remote` does not establish whether the push succeeded. Do not infer the result from the exit code alone or blindly repeat the initial command: existing `main` or an existing tag will stop it.

When `tag` is `null`, read only `main`:

```sh
git ls-remote --refs https://github.com/OWNER/public-project.git refs/heads/main
```

If `main` equals the printed destination `commit`, the update is present. If `main` has advanced, inspect the destination history to confirm that commit is an ancestor of the current `main`. If `main` still equals `destination_main_before`, the update is not present at the time of the check. Resolve an uncertain result before repeating the command; commit publication has no destination tag to prevent sending the same snapshot again.

## Command help

```sh
uv run noren --help
uv run noren init --help
uv run noren publish --help
```

Command help is in English. This README covers setup, checks, sending, and verification. Your project's version changes, builds, and publication to package registries belong to its own release instructions.

The commands and their YAML output are noren's stable interface. The Python modules inside the noren package are internal and may change between versions. Do not import them from your project's tests; to check which files noren selects, use the `files` list from a dry-run.
