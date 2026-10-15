"""The two noninteractive commands exposed by noren."""

import argparse
import sys

import yaml

from noren import __version__
from noren.git import NorenError
from noren.publishing import publish
from noren.setup import initialize


class Parser(argparse.ArgumentParser):
    def parse_known_args(self, args=None, namespace=None):
        self.partial_options = namespace if namespace is not None else argparse.Namespace()
        return super().parse_known_args(args, self.partial_options)

    def error(self, message):
        raise NorenError(message)

    def format_help(self):
        formatter = self._get_formatter()
        groups = sorted(self._action_groups, key=lambda group: group.title == "options")
        for group in groups:
            if group._group_actions:
                formatter.start_section("Options" if group.title == "options" else group.title)
                formatter.add_arguments(group._group_actions)
                formatter.end_section()
        return f"{self.description}\n\n{formatter.format_help()}"


def parser() -> Parser:
    command = Parser(
        prog="noren", allow_abbrev=False,
        description=(
            "Send selected files from one git repository to another as a single commit.\n\n"
            "Use init to create settings and publish to check a source tag or commit.\n"
            "Publish defaults to dry-run and prints one YAML document.\n"
            "Commands exit with 0 on success and nonzero on errors, reported to stderr.\n\n"
            "Notes:\n"
            "  - Review files and author in dry-run before adding --push to send them.\n"
            "  - Commit settings and the word list before selecting a source tag or commit.\n\n"
            "Examples:\n  noren init\n"
            "  noren publish --tag v1.0.0 --message 'Release v1.0.0' --initial\n\n"
            "Related:\n  noren init --help\n  noren publish --help"
        ),
    )
    command.add_argument("--version", action="version", version=__version__, help="Print the installed version and exit.")
    commands = command.add_subparsers(dest="command", title="Commands")
    commands.add_parser(
        "init", allow_abbrev=False,
        help="Create the settings and forbidden-word templates.",
        description=(
            "Create setup templates at the source repository root.\n\n"
            "Create noren.yaml and noren-words.txt using the origin URL and repository name.\n"
            "Set destination, include, exclude, and word-list; configure forbidden words.\n"
            "Existing templates are preserved. No arguments or interactive input are needed.\n"
            "Print setup instructions to stdout; exit 0 on success, nonzero on errors to stderr.\n\n"
            "Notes:\n"
            "  - Keep noren.yaml and the word list in exclude to avoid sending private settings.\n"
            "  - Keep the origin URL and repository name in the forbidden words; add private\n"
            "    identifiers, edit the settings, and commit both files before publishing.\n\n"
            "Examples:\n  noren init\n\n"
            "Related:\n  Commit the settings, then run noren publish --help to choose a tag or commit ID."
        ),
    )
    publish = commands.add_parser(
        "publish", allow_abbrev=False,
        help="Check or send a source tag or commit to the destination repository.",
        description=(
            "Send selected files from a source tag or commit to a GitHub repository as one commit.\n\n"
            "Specify exactly one of --tag or --commit, and supply --message even for dry-run.\n"
            "Read noren.yaml, the forbidden words, and all files from the selected source commit.\n"
            "Reject unclassified files and forbidden content. Exclude takes precedence over include.\n"
            "Default to dry-run. With --push, extend destination main without force or source history.\n"
            "With --tag, update main and the same tag together in one atomic push.\n"
            "With --commit, update only main and create no tag; names such as HEAD are rejected.\n"
            "Print one YAML document with tag, source_commit, destination, author, files,\n"
            "destination_main_before, commit, and pushed, on success and failure.\n"
            "tag is null with --commit. source_commit is the full source commit ID, or null\n"
            "if unresolved. Dry-run has commit: null. pushed confirms all requested updates.\n"
            "author has name and email for the destination commit's author and committer,\n"
            "or null if unresolved.\n"
            "destination_main_before is an empty string when unread and null when main is absent.\n"
            "Exit 0 on success, nonzero on errors with reasons on stderr.\n\n"
            "Notes:\n"
            "  - Settings and the word list come from the selected source commit, not the working tree.\n"
            "    Commit corrections, then select a tag or commit containing them.\n"
            "  - noren.yaml and the word list are committed to the source repository and may enter packages.\n"
            "    Build from the destination repository or exclude both files in your build backend.\n"
            "  - Send with noren before publishing to a package registry so forbidden-word checks\n"
            "    run before irreversible publication. Only selected files are checked; files added\n"
            "    by the build backend are not checked. Check built packages with the same word list\n"
            "    before publishing them.\n"
            "  - Each publication adds a commit; destination history is never rewritten.\n"
            "    Removed files remain readable in old commits and tags. Making a private destination\n"
            "    public exposes every snapshot; prepare the first --initial publication as public.\n"
            "  - Published tests containing literal private names fail forbidden-word checks.\n"
            "    Read those names from the excluded word-list file instead.\n"
            "  - Source Git hooks such as pre-push do not run; run additional checks before sending.\n"
            "  - Destination tags are lightweight and point directly to the destination commit.\n"
            "  - --commit creates no tag. If a push result is uncertain, check destination main\n"
            "    before you retry.\n\n"
            "Examples:\n"
            "  noren publish --tag v1.0.0 --message 'Release v1.0.0' --initial\n"
            "  noren publish --tag v1.0.0 --message 'Release v1.0.0' --initial --push\n"
            "  noren publish --tag v1.1.0 --message 'Release v1.1.0' --push\n"
            "  noren publish --commit a1b2c3d --message 'Correct the README'\n"
            "  noren publish --commit a1b2c3d --message 'Correct the README' --push\n\n"
            "Related:\n  Run noren init first, then commit the settings and choose a tag or commit ID.\n"
            "  After publishing, compare destination main and any requested tag with the printed commit ID."
        ),
    )
    publish.add_argument("--tag", metavar="NAME", help="Source tag to read and publish; choose exactly one of --tag or --commit.")
    publish.add_argument("--commit", metavar="ID", help="Hexadecimal source commit ID, including a unique abbreviation; update main without a tag.")
    publish.add_argument("--message", metavar="TEXT", help="Required destination commit message, including for dry-run.")
    publish.add_argument("--push", action="store_true", help="Actually update destination main and any requested tag; default is dry-run.")
    publish.add_argument("--initial", action="store_true", help="Explicit first publication: require main to be absent and create a root commit.")
    command.publish_parser = publish
    return command


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    output = {
        "tag": "", "source_commit": None, "destination": "", "author": None, "files": [],
        "destination_main_before": "", "commit": None, "pushed": False,
    }
    publishing = bool(arguments and arguments[0] == "publish")
    try:
        command = parser()
        try:
            options = command.parse_args(arguments)
        except SystemExit as exit:
            publishing = False
            return int(exit.code)
        finally:
            partial = getattr(command.publish_parser, "partial_options", None)
            output["tag"] = getattr(partial, "tag", None) or (
                None if getattr(partial, "commit", None) is not None else ""
            )
        if options.command == "init":
            initialize()
        elif options.command == "publish":
            publish(options, output)
        else:
            print(command.format_help(), end="")
        return 0
    except (NorenError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        if publishing:
            print(yaml.safe_dump(output, sort_keys=False, allow_unicode=True), end="")
