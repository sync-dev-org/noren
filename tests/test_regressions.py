import pytest
import yaml

from test_publish import publish, seed_destination


@pytest.mark.req("SP-NOREN-021")
@pytest.mark.req("SP-NOREN-030")
@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("extra", [["--message"], ["--unexpected"], ["--message", "--help"]])
def test_parse_failures_preserve_known_tag_and_always_print_one_yaml_result(repos, invoke, result, extra):
    """Invalid publication options preserve the specified tag and report errors with a complete YAML result."""
    repos.commit("v1")
    code, out, err = invoke("publish", "--tag", "v1", *extra)
    assert code != 0 and err
    data = result(out)
    assert data["tag"] == "v1"
    assert data["destination"] == "" and data["files"] == []
    assert data["destination_main_before"] == ""
    assert data["commit"] is None and data["pushed"] is False
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-002")
@pytest.mark.req("SP-NOREN-023")
def test_follow_tags_configuration_does_not_send_source_tag_annotations(repos, invoke, result):
    """Only the requested release tag is pushed even when Git normally follows annotated ancestor tags."""
    parent = seed_destination(repos)
    repos.git("fetch", str(repos.destination), "main")
    repos.git("tag", "-a", "private-annotation", "-m", "PRIVATE source tag annotation", parent)
    repos.git("config", "push.followTags", "true")
    repos.commit("v1")
    code, sent, err = publish(invoke, result, initial=False)
    assert code == 0 and err == "" and sent["pushed"] is True
    assert repos.git("tag", "--list", destination=True).stdout.decode().splitlines() == ["v1"]


@pytest.mark.req("SP-NOREN-023")
@pytest.mark.req("SP-NOREN-028")
def test_replace_refs_do_not_change_the_tagged_release_snapshot(repos, invoke, result):
    """Local replacement refs cannot change the canonical files selected by an existing source tag."""
    tagged = repos.commit("v1")
    repos.write("public/readme.txt", "PRIVATE-TOKEN replaced commit\n")
    replacement = repos.commit()
    repos.git("replace", tagged, replacement)
    code, sent, err = publish(invoke, result)
    assert code == 0 and err == "" and sent["pushed"] is True
    assert repos.git("show", "main:public/readme.txt", destination=True).stdout == b"Public release\n"


@pytest.mark.req("SP-NOREN-011")
def test_multiline_message_preserves_supplied_paragraphs_and_trailing_newlines(repos, invoke, result):
    """The destination commit retains the exact supplied multiline message rather than trimming its paragraphs."""
    repos.commit("v1")
    message = "Public title\n\nDetailed public notes\n\n"
    code, out, err = invoke("publish", "--tag", "v1", "--message", message, "--initial", "--push")
    assert code == 0 and err == "" and result(out)["pushed"] is True
    commit = repos.git("cat-file", "commit", "main", destination=True).stdout
    assert commit.split(b"\n\n", 1)[1] == message.encode()


@pytest.mark.req("SP-NOREN-019")
@pytest.mark.parametrize("connection", ["additional-remote", "origin-pushurl"])
def test_a_destination_remote_does_not_make_the_destination_the_source(repos, invoke, result, connection):
    """A separate publishing remote or push URL does not change the source repository identified by origin's fetch URL."""
    if connection == "additional-remote":
        repos.git("remote", "add", "release", "https://github.com/example/public.git")
    else:
        repos.git("remote", "set-url", "--push", "origin", "git@github.com:example/public.git")
    repos.commit("v1")
    code, sent, err = publish(invoke, result)
    assert code == 0 and err == "" and sent["pushed"] is True


@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("failure", ["missing-settings", "forbidden-content", "inaccessible-destination"])
def test_unobserved_main_is_empty_string_rather_than_claiming_main_is_absent(repos, invoke, result, monkeypatch, tmp_path, failure):
    """Stopping before destination main can be read reports an unknown value rather than false absence."""
    seed_destination(repos)
    if failure == "missing-settings":
        config = repos.configure()
        del config["exclude"]
        repos.write("noren.yaml", yaml.safe_dump(config))
    elif failure == "forbidden-content":
        repos.write("public/readme.txt", "PRIVATE-TOKEN")
    else:
        monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{(tmp_path / 'inaccessible.git').as_uri()}.insteadOf")
    repos.commit("v1")
    before = repos.refs()
    code, failed, err = publish(invoke, result, initial=False)
    assert code != 0 and err
    assert failed["destination_main_before"] == ""
    assert failed["commit"] is None and failed["pushed"] is False
    assert repos.refs() == before
