import hashlib

import pytest

from test_publish import seed_destination


@pytest.mark.req("SP-NOREN-012")
@pytest.mark.req("SP-NOREN-023")
@pytest.mark.req("SP-NOREN-028")
@pytest.mark.req("SP-NOREN-030")
@pytest.mark.req("SP-NOREN-033")
@pytest.mark.req("SP-NOREN-035")
@pytest.mark.parametrize("form", ["full", "abbreviated", "uppercase"])
@pytest.mark.parametrize("initial", [False, True])
def test_commit_check_and_push_use_the_chosen_snapshot_and_only_update_main(repos, invoke, result, form, initial):
    """A commit ID selects the same files and settings for checking and sending without adding destination tags."""
    before = None if initial else seed_destination(repos)
    if before is not None:
        repos.git("tag", "existing", before, destination=True)
        repos.git("fetch", str(repos.destination), "main")
        repos.git("tag", "-a", "source-annotation", "-m", "PRIVATE annotation", before)
        before = seed_destination(repos, parent=before)
    repos.git("config", "push.followTags", "true")
    snapshot = repos.commit()
    identifier = snapshot
    if form == "abbreviated":
        identifier = repos.git("rev-parse", "--short", snapshot).stdout.decode().strip()
    elif form == "uppercase":
        identifier = snapshot.upper()
    # A hexadecimal branch name must not override the requested object ID.
    repos.configure(destination="other/unwanted", include="**", exclude="")
    repos.write("noren-words.txt", "release\n")
    repos.write("public/readme.txt", "HEAD private-token\n")
    head = repos.commit()
    repos.git("branch", identifier, head)
    repos.write("noren.yaml", "broken: [")
    repos.write("noren-words.txt", "release\n")
    repos.write("public/readme.txt", "WORKTREE private-token\n")
    source_refs = repos.git("show-ref").stdout
    source_index = (repos.source / ".git/index").read_bytes()
    destination_refs = repos.refs()
    destination_tags = repos.git("tag", "--list", destination=True).stdout
    hook = repos.destination / "hooks/update"
    hook.write_text('#!/bin/sh\ncase "$1" in refs/tags/*) exit 1;; esac\nexit 0\n')
    hook.chmod(0o755)
    arguments = ["publish", "--commit", identifier, "--message", "Correct the README"]
    if initial:
        arguments.append("--initial")

    code, out, err = invoke(*arguments)

    assert code == 0 and err == ""
    checked = result(out)
    assert checked == {
        "tag": None, "source_commit": snapshot, "destination": "example/public", "branch": "main",
        "author": {"name": "Release Bot", "email": "release@example.invalid"},
        "files": ["public/readme.txt"], "destination_branch_before": before,
        "commit": None, "pushed": False,
    }
    assert repos.refs() == destination_refs

    code, out, err = invoke(*arguments, "--push")

    assert code == 0 and err == ""
    sent = result(out)
    assert sent == {**checked, "commit": sent["commit"], "pushed": True}
    assert sent["commit"] is not None
    assert repos.git("rev-parse", "main", destination=True).stdout.decode().strip() == sent["commit"]
    parents = [sent["commit"]] + ([before] if before is not None else [])
    assert repos.git("rev-list", "--parents", "-1", "main", destination=True).stdout.decode().split() == parents
    assert repos.git("ls-tree", "-r", "--name-only", "main", destination=True).stdout.decode().splitlines() == sent["files"]
    assert repos.git("show", "main:public/readme.txt", destination=True).stdout == b"Public release\n"
    assert repos.git("tag", "--list", destination=True).stdout == destination_tags
    assert repos.git("show-ref").stdout == source_refs
    assert (repos.source / ".git/index").read_bytes() == source_index
    assert repos.git("cat-file", "-e", snapshot, destination=True, check=False).returncode != 0


@pytest.mark.req("SP-NOREN-030")
@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("both", [False, True])
def test_publication_requires_exactly_one_source_selector(repos, invoke, result, both):
    """Supplying both selectors or neither selector stops before resolving a source commit or updating the destination."""
    snapshot = repos.commit("v1")
    arguments = ["--tag", "v1", "--commit", snapshot] if both else []
    code, out, err = invoke("publish", *arguments, "--message", "Update", "--initial", "--push")
    assert code != 0 and "--tag" in err and "--commit" in err
    data = result(out)
    assert data["source_commit"] is None and data["commit"] is None and data["pushed"] is False
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-033")
@pytest.mark.req("SP-NOREN-035")
@pytest.mark.parametrize("identifier", ["HEAD", "main", "v1", "HEAD^{commit}", "0" * 40, ""])
def test_names_and_missing_commit_ids_cannot_publish(repos, invoke, result, identifier):
    """Names, revision expressions, empty IDs, and nonexistent hexadecimal IDs cannot update destination refs."""
    repos.commit("v1")
    code, out, err = invoke("publish", "--commit", identifier, "--message", "Update", "--initial", "--push")
    assert code != 0 and "commit" in err.lower()
    data = result(out)
    assert data["tag"] is None and data["source_commit"] is None
    assert data["commit"] is None and data["pushed"] is False
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-035")
@pytest.mark.parametrize("object_kind", ["blob", "tree", "tag"])
def test_hexadecimal_ids_must_identify_commit_objects(repos, invoke, result, object_kind):
    """A blob, tree, or annotated-tag object ID cannot be used as a source commit ID."""
    repos.commit()
    if object_kind == "tag":
        repos.git("tag", "-a", "annotated", "-m", "Source annotation")
        revision = "refs/tags/annotated"
    else:
        revision = "HEAD:public/readme.txt" if object_kind == "blob" else "HEAD^{tree}"
    identifier = repos.git("rev-parse", revision).stdout.decode().strip()
    code, out, err = invoke("publish", "--commit", identifier, "--message", "Update", "--initial", "--push")
    assert code != 0 and "commit" in err.lower()
    assert result(out)["source_commit"] is None
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-035")
def test_ambiguous_commit_prefix_stops_without_sending(repos, invoke, result):
    """A hexadecimal prefix shared by two real commit objects cannot select a publication snapshot."""
    repos.commit()
    tree = repos.git("rev-parse", "HEAD^{tree}").stdout.decode().strip()
    algorithm = repos.git("rev-parse", "--show-object-format").stdout.decode().strip()
    prefixes = {}
    for number in range(65537):
        content = (
            f"tree {tree}\nauthor Test <test@example.invalid> 1 +0000\n"
            f"committer Test <test@example.invalid> 1 +0000\n\nSnapshot {number}\n"
        ).encode()
        oid = hashlib.new(algorithm, f"commit {len(content)}\0".encode() + content).hexdigest()
        prefix = oid[:4]
        if prefix in prefixes:
            for blob in (prefixes[prefix], content):
                repos.git("hash-object", "-t", "commit", "-w", "--stdin", input=blob)
            break
        prefixes[prefix] = content
    else:
        pytest.fail("No colliding commit prefix found")

    code, out, err = invoke("publish", "--commit", prefix, "--message", "Update", "--initial", "--push")

    assert code != 0 and "ambiguous" in err.lower()
    assert result(out)["source_commit"] is None
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-012")
@pytest.mark.req("SP-NOREN-030")
@pytest.mark.parametrize("main_exists", [False, True])
def test_commit_publication_rejects_an_initial_flag_that_disagrees_with_main(repos, invoke, result, main_exists):
    """Commit publication requires the same explicit first-publication flag as tag publication."""
    before = seed_destination(repos) if main_exists else None
    snapshot = repos.commit()
    refs = repos.refs()
    flags = ["--initial"] if main_exists else []
    code, out, err = invoke("publish", "--commit", snapshot, "--message", "Update", *flags, "--push")
    assert code != 0 and "--initial" in err
    data = result(out)
    assert data["source_commit"] == snapshot and data["destination_branch_before"] == before
    assert data["commit"] is None and data["pushed"] is False
    assert repos.refs() == refs


@pytest.mark.req("SP-NOREN-028")
@pytest.mark.req("SP-NOREN-033")
def test_commit_word_list_stops_forbidden_content_despite_later_safe_settings(repos, invoke, result):
    """The selected commit's forbidden words remain effective when later commits and working files allow its content."""
    repos.write("noren-words.txt", "release\n")
    snapshot = repos.commit()
    repos.write("noren-words.txt", "absent-word\n")
    repos.commit()
    code, out, err = invoke("publish", "--commit", snapshot, "--message", "Update", "--initial", "--push")
    assert code != 0 and "Forbidden word in public/readme.txt" in err
    data = result(out)
    assert data["tag"] is None and data["source_commit"] == snapshot
    assert data["commit"] is None and data["pushed"] is False
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-030")
@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("extra", [[], ["--message"], ["--unexpected"]])
def test_commit_option_failures_print_a_complete_unresolved_result(repos, invoke, result, extra):
    """Missing messages and invalid options report all nine result fields with an unresolved source commit and author."""
    snapshot = repos.commit()
    code, out, err = invoke("publish", "--commit", snapshot, *extra)
    assert code != 0 and err
    data = result(out)
    assert data["tag"] is None and data["source_commit"] is None
    assert data["author"] is None
    assert data["commit"] is None and data["pushed"] is False
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-015")
@pytest.mark.req("SP-NOREN-022")
@pytest.mark.req("SP-NOREN-030")
@pytest.mark.req("SP-NOREN-033")
def test_publish_help_explains_commit_selection_examples_and_result_fields(invoke):
    """English publication help describes the commit selector, shows its use, and lists the nine output fields."""
    code, out, err = invoke("publish", "--help")
    assert code == 0 and err == ""
    examples = out.split("Examples:", 1)[1].split("Related:", 1)[0]
    options = out.split("Options:", 1)[1]
    assert "--commit" in examples and "--commit ID" in options
    assert out.index("Examples:") < out.index("Related:") < out.index("Options:")
    behavior = out.split("Notes:", 1)[0]
    for field in ("tag", "source_commit", "destination", "branch", "author", "files", "destination_branch_before", "commit", "pushed"):
        assert field in behavior
    for detail in ("name", "email", "null", "unresolved"):
        assert detail in behavior
