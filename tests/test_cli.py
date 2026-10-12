import re

import pytest

from noren._version import __version__


@pytest.mark.req("SP-NOREN-025")
@pytest.mark.req("SP-NOREN-036")
def test_version_prints_generated_version_without_a_command_or_repository(invoke, tmp_path, monkeypatch):
    """The version option prints the installed tag-derived version on one line outside a Git repository."""
    monkeypatch.chdir(tmp_path)

    code, out, err = invoke("--version")

    assert code == 0 and err == ""
    assert out.splitlines() == [__version__]


@pytest.mark.req("SP-NOREN-015")
@pytest.mark.req("SP-NOREN-022")
@pytest.mark.parametrize("command", [(), ("init",), ("publish",)])
def test_help_places_notes_before_examples_related_commands_and_options(invoke, command):
    """Every command's English help presents behavior and cautions before examples and related commands."""
    code, out, err = invoke(*command, "--help")

    assert code == 0 and err == ""
    assert out.index("stderr") < out.index("Notes:") < out.index("Examples:") < out.index("Related:") < out.index("Options:")


@pytest.mark.req("SP-NOREN-015")
@pytest.mark.parametrize("points", [
    ("settings", "word list", "selected source commit", "working tree", "commit", "select"),
    ("noren.yaml", "word list", "source repository", "packages", "destination repository", "build backend", "exclude"),
    ("package registry", "before", "noren", "forbidden", "irreversible"),
    ("tests", "private names", "forbidden", "word-list file"),
    ("source", "hooks", "pre-push", "checks", "before"),
    ("destination", "lightweight", "tags", "commit"),
    ("--commit", "no tag", "uncertain", "destination main", "before", "retry"),
])
def test_publish_notes_explain_each_publication_pitfall_and_remedy(invoke, points):
    """Publication notes explain the committed settings, packaging, scanning, tests, hooks, tags, and uncertain retries."""
    code, out, err = invoke("publish", "--help")

    assert code == 0 and err == ""
    notes = out.split("Notes:", 1)[1].split("Examples:", 1)[0].lower()
    items = [" ".join(item.split()) for item in re.split(r"(?m)^  - ", notes)[1:]]
    assert len(items) == 7
    assert any(all(point in item for point in points) for item in items)


@pytest.mark.req("SP-NOREN-015")
@pytest.mark.parametrize("command,points", [
    ((), ("dry-run", "files", "author", "--push")),
    (("init",), ("noren.yaml", "word list", "exclude")),
    (("init",), ("origin url", "repository name", "forbidden", "commit")),
])
def test_setup_and_root_notes_explain_their_next_safe_steps(invoke, command, points):
    """Root help requests dry-run review and setup help requests exclusions and committed forbidden words."""
    code, out, err = invoke(*command, "--help")

    assert code == 0 and err == ""
    notes = " ".join(out.split("Notes:", 1)[1].split("Examples:", 1)[0].lower().split())
    assert all(point in notes for point in points)
