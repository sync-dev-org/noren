import pytest
import yaml


@pytest.mark.req("SP-NOREN-003")
@pytest.mark.req("SP-NOREN-017")
@pytest.mark.req("SP-NOREN-021")
@pytest.mark.req("SP-NOREN-030")
@pytest.mark.req("SP-NOREN-033")
def test_default_dry_run_reports_files_without_changing_either_repository(repos, invoke, result):
    """Checking a release prints one complete YAML result without creating a commit or updating refs."""
    source_commit = repos.commit("v1")
    source_refs = repos.git("show-ref").stdout
    source_index = (repos.source / ".git/index").read_bytes()

    code, out, err = invoke("publish", "--tag", "v1", "--message", "Release", "--initial")

    assert code == 0 and err == ""
    assert result(out) == {
        "tag": "v1", "source_commit": source_commit,
        "destination": "example/public", "files": ["public/readme.txt"],
        "destination_main_before": None, "commit": None, "pushed": False,
    }
    assert repos.refs() == b""
    assert repos.git("rev-parse", "HEAD").stdout.decode().strip() == source_commit
    assert repos.git("show-ref").stdout == source_refs
    assert (repos.source / ".git/index").read_bytes() == source_index


@pytest.mark.req("SP-NOREN-004")
@pytest.mark.req("SP-NOREN-018")
@pytest.mark.req("SP-NOREN-021")
@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("push", [False, True])
def test_unclassified_files_stop_checks_and_pushes(repos, invoke, result, push):
    """Any file missing from both lists prevents publication and is named on stderr."""
    repos.write("forgotten.txt", "Unknown file")
    repos.commit("v1")

    code, out, err = invoke("publish", "--tag", "v1", "--message", "Release", "--initial", *(["--push"] if push else []))

    assert code != 0 and "forgotten.txt" in err
    assert result(out)["commit"] is None
    assert result(out)["pushed"] is False
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-005")
@pytest.mark.req("SP-NOREN-018")
@pytest.mark.req("SP-NOREN-031")
@pytest.mark.parametrize("content,words", [
    (b"a PRIVATE-TOKEN here", "private-token\n"),
    ("a ＰＲＩＶＡＴＥ－ＴＯＫＥＮ here".encode(), "private-token\n"),
    (b"prefixprivate-tokensuffix", "private-token\n"),
    (b"\xff\xfe\nPRIVATE-TOKEN", "private-token\n"),
    (b"prefixprivate-tokensuffix", "ＰＲＩＶＡＴＥ－ＴＯＫＥＮ\n"),
])
@pytest.mark.parametrize("push", [False, True])
def test_forbidden_words_stop_after_normalization_and_invalid_utf8(repos, invoke, result, content, words, push):
    """Every forbidden substring is detected across case and width differences and invalid UTF-8 bytes."""
    repos.write("public/readme.txt", content)
    repos.write("noren-words.txt", words)
    repos.commit("v1")

    code, out, err = invoke("publish", "--tag", "v1", "--message", "Release", "--initial", *(["--push"] if push else []))

    assert code != 0 and "public/readme.txt" in err and "line" in err
    assert result(out)["pushed"] is False
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-007")
@pytest.mark.req("SP-NOREN-008")
@pytest.mark.req("SP-NOREN-027")
@pytest.mark.parametrize("missing", ["destination", "include", "exclude", "word-list"])
def test_missing_required_setting_stops_before_sending(repos, invoke, result, missing):
    """Each of the four required settings must be present before files can be sent."""
    settings = repos.configure()
    del settings[missing]
    repos.write("noren.yaml", yaml.safe_dump(settings))
    repos.commit("v1")

    code, out, err = invoke("publish", "--tag", "v1", "--message", "Release", "--initial", "--push")

    assert code != 0 and missing in err
    data = result(out)
    assert data["destination"] == ("" if missing == "destination" else "example/public")
    assert data["files"] == [] and data["commit"] is None and data["pushed"] is False
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-007")
@pytest.mark.req("SP-NOREN-016")
@pytest.mark.parametrize("words", [None, "", "\n  \n"])
def test_missing_or_empty_word_list_stops_before_sending(repos, invoke, result, words):
    """A missing or empty forbidden-word list prevents publication even when all other settings exist."""
    if words is None:
        (repos.source / "noren-words.txt").unlink()
    else:
        repos.write("noren-words.txt", words)
    repos.commit("v1")

    code, out, err = invoke("publish", "--tag", "v1", "--message", "Release", "--initial", "--push")

    assert code != 0 and "word" in err.lower()
    assert result(out)["pushed"] is False
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-007")
@pytest.mark.req("SP-NOREN-016")
def test_configured_empty_include_and_exclude_are_valid_lists(repos, invoke, result):
    """An explicitly empty list is valid settings rather than a missing setting."""
    repos.configure(include="", exclude="**")
    repos.commit("v1")
    code, out, err = invoke("publish", "--tag", "v1", "--message", "Release", "--initial")
    assert code == 0 and err == "" and result(out)["files"] == []

    repos.configure(include="**", exclude="")
    repos.write("noren-words.txt", "absent-secret\n")
    repos.commit("v2")
    code, out, err = invoke("publish", "--tag", "v2", "--message", "Release", "--initial")
    # With no exclusions the list itself is selected and contains a forbidden word.
    assert code != 0 and "Forbidden word in noren-words.txt" in err
    assert result(out)["files"] == ["noren-words.txt", "noren.yaml", "public/readme.txt"]


@pytest.mark.req("SP-NOREN-016")
@pytest.mark.req("SP-NOREN-029")
def test_gitignore_rules_choose_files_and_exclude_wins(repos, invoke, result):
    """Negation, last-match priority, anchored paths, directories, and globstars select the intended files."""
    repos.configure(
        include="/root.txt\nassets/\n!assets/private/**\nassets/private/ok.txt\npublic/**\n!public/no.txt\n",
        exclude="noren.yaml\nnoren-words.txt\nprivate/**\n**/root.txt\n!/root.txt\nassets/private/**\n!assets/private/ok.txt\npublic/no.txt\npublic/internal/\n",
    )
    for name in ("root.txt", "deep/root.txt", "assets/icon.txt", "assets/private/key.txt", "assets/private/ok.txt", "public/no.txt", "public/internal/key.txt", "public/a/b/c.txt"):
        repos.write(name, "Safe\n")
    repos.commit("v1")

    code, out, err = invoke("publish", "--tag", "v1", "--message", "Release", "--initial")

    assert code == 0 and err == ""
    assert result(out)["files"] == ["assets/icon.txt", "assets/private/ok.txt", "public/a/b/c.txt", "public/readme.txt", "root.txt"]


@pytest.mark.req("SP-NOREN-016")
def test_word_list_reads_separate_lines_as_separate_words(repos, invoke, result):
    """A forbidden word on the second line is checked independently of the first line."""
    repos.write("noren-words.txt", "absent-word\nrelease\n")
    repos.commit("v1")
    code, out, err = invoke("publish", "--tag", "v1", "--message", "Release", "--initial")
    assert code != 0 and "public/readme.txt" in err
    assert result(out)["commit"] is None


@pytest.mark.req("SP-NOREN-011")
@pytest.mark.req("SP-NOREN-023")
@pytest.mark.req("SP-NOREN-030")
@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("arguments,reason", [
    (["--tag", "v1"], "--message"),
    (["--message", "Release"], "--tag"),
    (["--tag", "absent", "--message", "Release"], "absent"),
])
def test_required_options_and_existing_tag_are_checked(repos, invoke, result, arguments, reason):
    """Missing required options or tags stop publication, and missing messages include an example."""
    repos.commit("v1")
    code, out, err = invoke("publish", *arguments, "--initial", "--push")
    assert code != 0 and reason in err
    if reason == "--message":
        assert "--message 'Release" in err
    assert result(out)["commit"] is None
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-023")
@pytest.mark.req("SP-NOREN-028")
def test_check_uses_tagged_files_settings_and_word_list_instead_of_head_or_worktree(repos, invoke, result):
    """A check reads its entire release snapshot from the tag even when HEAD and working files disagree."""
    repos.commit("v1")
    repos.configure(destination="other/unwanted", include="**", exclude="")
    repos.write("noren-words.txt", "release\n")
    repos.write("public/readme.txt", "HEAD private-token")
    repos.commit()
    repos.write("noren.yaml", "broken: [")
    repos.write("noren-words.txt", "public\n")
    repos.write("public/readme.txt", "WORKTREE private-token")
    code, out, err = invoke("publish", "--tag", "v1", "--message", "Release", "--initial")
    assert code == 0 and err == ""
    assert result(out)["destination"] == "example/public"
    assert result(out)["files"] == ["public/readme.txt"]


@pytest.mark.req("SP-NOREN-009")
@pytest.mark.req("SP-NOREN-032")
def test_unreadable_destination_stops_without_creating_a_commit(repos, invoke, result, monkeypatch, tmp_path):
    """Failure to read destination main stops publication without a separate access check."""
    repos.commit("v1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{(tmp_path / 'missing.git').as_uri()}.insteadOf")
    code, out, err = invoke("publish", "--tag", "v1", "--message", "Release", "--initial", "--push")
    assert code != 0 and "ls-remote" in err
    data = result(out)
    assert data["files"] == ["public/readme.txt"]
    assert data["destination"] == "example/public"
    assert data["commit"] is None
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-019")
@pytest.mark.parametrize("origin", ["git@github.com:example/public.git", "https://github.com/EXAMPLE/PUBLIC.git", "ssh://git@github.com/example/public.git"])
def test_destination_cannot_be_the_source_repository(repos, invoke, result, origin):
    """Equivalent GitHub repository addresses prevent sending a release back into its source."""
    repos.git("remote", "set-url", "origin", origin)
    repos.commit("v1")
    code, out, err = invoke("publish", "--tag", "v1", "--message", "Release", "--initial", "--push")
    assert code != 0 and "source" in err.lower()
    assert result(out)["commit"] is None
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("configuration", [None, "broken: [", "- list", "destination: example/public\ninclude: [list]\nexclude: ''\nword-list: noren-words.txt\n"])
def test_missing_invalid_or_wrongly_typed_config_stops_with_a_complete_result(repos, invoke, result, configuration):
    """Invalid tagged settings stop cleanly and preserve the seven public output fields and their types."""
    if configuration is None:
        (repos.source / "noren.yaml").unlink()
    else:
        repos.write("noren.yaml", configuration)
    repos.commit("v1")
    code, out, err = invoke("publish", "--tag", "v1", "--message", "Release", "--initial", "--push")
    assert code != 0 and "noren.yaml" in err
    assert result(out)["files"] == []
    assert repos.refs() == b""
