"""The two noninteractive commands exposed by noren."""

import argparse
import sys

import yaml

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
            "Use init to create settings and publish to check a tagged snapshot.\n"
            "Publish defaults to dry-run and prints one YAML document.\n"
            "Commands exit with 0 on success and nonzero on errors, reported to stderr.\n\n"
            "Examples:\n  noren init\n"
            "  noren publish --tag v1.0.0 --message 'Release v1.0.0' --initial\n\n"
            "Related:\n  noren init --help\n  noren publish --help"
        ),
    )
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
            "Examples:\n  noren init\n\n"
            "Related:\n  Commit the settings, create a tag, then run noren publish --help."
        ),
    )
    publish = commands.add_parser(
        "publish", allow_abbrev=False,
        help="Check or send a tagged release to the destination repository.",
        description=(
            "Send selected files from a source tag to a GitHub repository as one commit.\n\n"
            "Read noren.yaml, the forbidden words, and all files from the specified tag.\n"
            "Reject unclassified files and forbidden content. Exclude takes precedence over include.\n"
            "Default to dry-run. With --push, extend destination main and update the same tag\n"
            "together in one atomic push without force or source history.\n"
            "Print one YAML document with tag, destination, files, destination_main_before,\n"
            "commit, and pushed, on success and failure. Dry-run has commit: null.\n"
            "destination_main_before is an empty string when unread and null when main is absent.\n"
            "Exit 0 on success, nonzero on errors with reasons on stderr.\n\n"
            "Examples:\n"
            "  noren publish --tag v1.0.0 --message 'Release v1.0.0' --initial\n"
            "  noren publish --tag v1.0.0 --message 'Release v1.0.0' --initial --push\n"
            "  noren publish --tag v1.1.0 --message 'Release v1.1.0' --push\n\n"
            "Related:\n  Run noren init first, then commit the settings and create a source tag.\n"
            "  After publishing, compare destination main and tag with the printed commit ID."
        ),
    )
    publish.add_argument("--tag", metavar="NAME", help="Required source tag to read and publish.")
    publish.add_argument("--message", metavar="TEXT", help="Required destination commit message, including for dry-run.")
    publish.add_argument("--push", action="store_true", help="Actually update destination main and tag; default is dry-run.")
    publish.add_argument("--initial", action="store_true", help="Explicit first publication: require main to be absent and create a root commit.")
    command.publish_parser = publish
    return command


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    output = {
        "tag": "", "destination": "", "files": [],
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
        except NorenError:
            partial = getattr(command.publish_parser, "partial_options", None)
            output["tag"] = getattr(partial, "tag", None) or ""
            raise
        if options.command == "init":
            initialize()
        elif options.command == "publish":
            output["tag"] = options.tag or ""
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
