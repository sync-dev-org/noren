# Operating essentials

These recommendations draw on operating practices collected from several repositories that publish with noren. They are a starting point for your own release instructions, not rules that apply to every setup. As with the [other guides](index.md#how-to-use-these-recommendations), adapt them to your build backend, registry, and approval process.

Write your project's chosen policies into its own release and development documentation, with the basis for each decision. Restate shared policies so the documentation can be read without relying on policy identifiers from another project.

## Separate development from publication

Develop in a private source repository. Use a separate public repository to receive only the snapshots sent by noren; do not develop directly there. This keeps public contents under the source repository's selection and review process.

Treat a change to the publication repository's visibility as a decision for its owner. Making it public exposes its earlier snapshots too. The [publication workflow](publication-workflow.md) explains what to review before that change.

## Install noren as a tool

Keep noren out of the project's dependencies. Install it as a tool and invoke `noren` directly:

```sh
uv tool install noren
```

## Check everything that becomes public

Keep the names of applications and projects that use your distribution, private repository names and URLs, host names, development history, and development records out of public repositories, documentation, and release artifacts. Add those identifiers to the excluded forbidden-word list and review the public files as well. See the [snapshot guidance](snapshots-and-tests.md) for keeping development details private.

Use the same word list for everything noren does not inspect, including sdist and wheel contents, their member names and generated metadata, and GitHub Release notes. Apply NFKC normalization and case folding before checking for substrings. The [package checks](package-checks.md) show how to inspect real archives; a successful noren dry-run covers only the selected Git files.

## Keep versions and published artifacts fixed

Use release tags such as `v1.2.3`, in the form `vX.Y.Z`, without a distribution-name prefix. Each new release version should be higher than the version most recently published.

Do not move, rewrite, or delete published tags, GitHub Releases, or package-registry files. Publish release corrections under a new version, including corrections after a failed attempt. Keep any already published artifacts fixed while you investigate the failure.

## Review and verify each publication

Build from the fixed commit identified by a release tag. The build input depends on what you send to the public repository:

- If the public repository receives source files and build settings, you can build from a checkout of its published tag. See [step 5 of the publication workflow](publication-workflow.md#5-build-and-inspect-the-release-packages).
- If it receives only documentation such as `README.md` and `LICENSE`, with packages distributed through GitHub Releases and a registry, it cannot build those packages. Create the tag in the source repository, build from that tag, and inspect the packages before sending the snapshot with noren.

For either setup, review noren's dry-run before sending, and finish the snapshot publication and package checks before distributing the packages. Put the same inspected bytes in the public repository's GitHub Release assets and the package registry. Download the files from both locations and compare their SHA-256 values with the inspected originals. The [publication workflow](publication-workflow.md) and [package checks](package-checks.md) explain the individual checks.

If any step fails, or you cannot confirm its result, stop before the next step. Investigate the published state; do not automatically repeat the same operation.

## Limit credentials to the upload process

Pass registry credentials only to the process performing the upload. Keep their values out of source files, command arguments, and logs. In a shell where credentials are present in environment variables, do not run commands that can display those values, such as `uv publish --help`. Arrange authentication without printing the credential values.

## Publish documentation from reviewed sources

Have the public repository's GitHub Actions build the documentation from the sources sent by noren and deploy it to that repository's GitHub Pages. Do not host Pages in the private development repository. The [documentation guidance](snapshots-and-tests.md) explains the file selection and workflow checks.

Limit GitHub Actions to building and deploying that documentation site. Run tests, build validation, and package-registry uploads outside Actions. Use no secrets in the workflow, and limit its permissions to `contents: read`, `pages: write`, and `id-token: write`. These limits keep the published site tied to inspected sources and restrict automation and permissions to the documentation deployment.

## Notify the people who depend on the release

After verifying publication, tell the maintainers of projects that depend on the distribution which version was released and where to obtain it. Send public download locations that you have checked, so they can update their dependencies using the verified release.
