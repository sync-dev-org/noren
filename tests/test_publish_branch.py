import json

import pytest
import yaml

from test_publish import seed_destination


@pytest.mark.req("SP-NOREN-042")
@pytest.mark.parametrize("branch", [None, "", " ", 1, ["main"], "bad..branch", "main*", "main\n"])
def test_empty_wrongly_typed_or_invalid_branch_cannot_send_files(repos, invoke, result, branch):
    """Empty, wrongly typed, and invalid branch names cannot update the destination."""
    config = repos.configure(branch=branch)
    repos.write("noren.yaml", yaml.safe_dump(config))
    repos.commit("release")

    code, out, err = invoke("publish", "--tag", "release", "--message", "Release", "--initial", "--push")

    assert code != 0 and "branch" in err
    data = result(out)
    assert data["commit"] is None and data["pushed"] is False
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-042")
@pytest.mark.parametrize("remote_tracking", [False, True])
def test_source_requires_a_local_branch_even_when_a_remote_tracking_branch_exists(repos, invoke, result, remote_tracking):
    """A remote-tracking branch cannot substitute for the configured local source branch."""
    repos.configure(branch="v1")
    snapshot = repos.commit()
    if remote_tracking:
        repos.git("update-ref", "refs/remotes/origin/v1", snapshot)

    code, out, err = invoke("publish", "--commit", snapshot, "--message", "Release", "--initial", "--push")

    assert code != 0 and "v1" in err and "branch" in err
    assert result(out)["pushed"] is False and repos.refs() == b""


@pytest.mark.req("SP-NOREN-042")
@pytest.mark.parametrize("selector", ["--commit", "--tag"])
def test_maintenance_commit_cannot_be_sent_with_an_inherited_main_setting(repos, invoke, result, selector):
    """A commit belonging only to the maintenance branch cannot be sent with branch set to main."""
    repos.commit()
    repos.git("checkout", "-b", "v1")
    repos.write("public/readme.txt", "Maintenance correction\n")
    snapshot = repos.commit("release")

    code, out, err = invoke("publish", selector, snapshot if selector == "--commit" else "release",
                            "--message", "Release", "--initial", "--push")

    assert code != 0 and "main" in err and "commit" in err.lower()
    data = result(out)
    assert data["source_commit"] == snapshot and data["pushed"] is False
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-042")
@pytest.mark.req("SP-NOREN-028")
@pytest.mark.parametrize("branch", ["main", "v1"])
def test_common_ancestor_can_be_sent_to_either_branch_from_its_committed_settings(repos, invoke, result, branch):
    """A snapshot shared by both branches passes containment using its committed branch setting."""
    repos.configure(branch=branch)
    snapshot = repos.commit()
    repos.git("branch", "v1")
    repos.write("public/readme.txt", "Later source change\n")
    repos.commit()
    repos.configure(branch="missing")

    code, out, err = invoke("publish", "--commit", snapshot, "--message", "Release", "--initial")

    assert code == 0 and err == ""
    data = result(out)
    assert data["branch"] == branch and data["source_commit"] == snapshot
    assert data["destination_branch_before"] is None and data["commit"] is None
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-012")
@pytest.mark.req("SP-NOREN-020")
@pytest.mark.req("SP-NOREN-023")
@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("selector", ["--commit", "--tag"])
@pytest.mark.parametrize("start", ["existing", "base-lightweight", "base-annotated", "initial"])
def test_maintenance_publication_uses_the_selected_parent_and_preserves_main(repos, invoke, result, monkeypatch, selector, start):
    """Maintenance snapshots extend their branch or the chosen destination tag without changing main."""
    main_before = seed_destination(repos)
    # This tag and its commit exist only at the destination, so they must be fetched there.
    if start == "existing":
        repos.git("update-ref", "refs/heads/v1", main_before, destination=True)
    elif start.startswith("base-"):
        arguments = ["-a", "-m", "Public base"] if start == "base-annotated" else []
        repos.git("tag", *arguments, "base", main_before, destination=True)
    repos.configure(branch="v1")
    snapshot = repos.commit("release")
    repos.git("branch", "v1")
    arguments = ["publish", selector, snapshot if selector == "--commit" else "release", "--message", "Maintenance release"]
    if start.startswith("base-"):
        arguments.extend(["--base-tag", "base"])
    elif start == "initial":
        arguments.append("--initial")
    source_refs = repos.git("show-ref").stdout
    source_index = (repos.source / ".git/index").read_bytes()
    source_objects = sorted(path.relative_to(repos.source / ".git/objects") for path in (repos.source / ".git/objects").rglob("*"))
    destination_before = repos.refs()
    # A single receive operation must contain every requested reference update.
    receipt = repos.destination / "received-updates"
    hook = repos.destination / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\ncat > received-updates\n")
    hook.chmod(0o755)
    trace = repos.source.parent / "git-trace.json"
    monkeypatch.setenv("GIT_TRACE2_EVENT", str(trace))

    code, out, err = invoke(*arguments)

    assert code == 0 and err == ""
    checked = result(out)
    assert checked["branch"] == "v1" and checked["commit"] is None
    assert checked["destination_branch_before"] == (main_before if start == "existing" else None)
    assert repos.refs() == destination_before
    assert not receipt.exists()

    code, out, err = invoke(*arguments, "--push")

    assert code == 0 and err == ""
    sent = result(out)
    assert sent == {**checked, "commit": sent["commit"], "pushed": True}
    parent = [] if start == "initial" else [main_before]
    assert repos.git("rev-list", "--parents", "-1", "v1", destination=True).stdout.decode().split() == [sent["commit"], *parent]
    assert repos.git("rev-parse", "main", destination=True).stdout.decode().strip() == main_before
    assert repos.git("show", "v1:public/readme.txt", destination=True).stdout == b"Public release\n"
    tags = repos.git("tag", "--list", destination=True).stdout.decode().splitlines()
    assert ("release" in tags) == (selector == "--tag")
    requested_refs = {"refs/heads/v1"} | ({"refs/tags/release"} if selector == "--tag" else set())
    assert {line.split()[2] for line in receipt.read_text().splitlines()} == requested_refs
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    pushes = [event["argv"] for event in events if event["event"] == "start" and "push" in event["argv"]]
    assert len(pushes) == 1 and "--atomic" in pushes[0]
    assert not any(argument == "-f" or argument.startswith(("--force", "+")) for argument in pushes[0])
    if selector == "--tag":
        assert repos.git("rev-parse", "refs/tags/release", destination=True).stdout.decode().strip() == sent["commit"]
    assert repos.git("show-ref").stdout == source_refs
    assert (repos.source / ".git/index").read_bytes() == source_index
    assert sorted(path.relative_to(repos.source / ".git/objects") for path in (repos.source / ".git/objects").rglob("*")) == source_objects
    assert not (repos.source / ".git/FETCH_HEAD").exists()
    assert repos.git("cat-file", "-e", snapshot, destination=True, check=False).returncode != 0


@pytest.mark.req("SP-NOREN-012")
@pytest.mark.req("SP-NOREN-030")
@pytest.mark.parametrize("case,flags,reason", [
    ("absent", [], "--base-tag"),
    ("existing", ["--initial"], "--initial"),
    ("existing", ["--base-tag", "base"], "--base-tag"),
    ("absent", ["--base-tag", "missing"], "missing"),
    ("absent", ["--base-tag", "base", "--initial"], "--initial"),
    ("blob", ["--base-tag", "base"], "commit"),
    ("tree", ["--base-tag", "base"], "commit"),
    ("annotated-blob", ["--base-tag", "base"], "commit"),
])
@pytest.mark.parametrize("push", [False, True])
def test_invalid_first_publication_options_cannot_change_any_destination_ref(repos, invoke, result, case, flags, reason, push):
    """Absent branches require a valid explicit parent choice, while existing branches reject that choice."""
    main_before = seed_destination(repos)
    base = main_before
    if case in ("blob", "annotated-blob"):
        base = repos.git("hash-object", "-w", "--stdin", input=b"Public blob\n", destination=True).stdout.decode().strip()
    elif case == "tree":
        base = repos.git("rev-parse", "main^{tree}", destination=True).stdout.decode().strip()
    tag_flags = ["-a", "-m", "Public blob tag"] if case == "annotated-blob" else []
    repos.git("tag", *tag_flags, "base", base, destination=True)
    if case == "existing":
        repos.git("update-ref", "refs/heads/v1", main_before, destination=True)
    repos.configure(branch="v1")
    snapshot = repos.commit()
    repos.git("branch", "v1")
    before = repos.refs()

    code, out, err = invoke("publish", "--commit", snapshot, "--message", "Maintenance", *flags, *(["--push"] if push else []))

    assert code != 0 and reason in err and "unrecognized arguments" not in err
    data = result(out)
    assert data["commit"] is None and data["pushed"] is False
    assert repos.refs() == before


@pytest.mark.req("SP-NOREN-023")
def test_rejected_maintenance_tag_leaves_the_branch_unchanged(repos, invoke, result):
    """An atomic publication cannot update the maintenance branch when its destination tag is rejected."""
    before = seed_destination(repos)
    repos.git("update-ref", "refs/heads/v1", before, destination=True)
    repos.configure(branch="v1")
    repos.commit("release")
    repos.git("branch", "v1")
    hook = repos.destination / "hooks/update"
    hook.write_text('#!/bin/sh\ncase "$1" in refs/tags/*) echo "Tag rejected" >&2; exit 1;; esac\nexit 0\n')
    hook.chmod(0o755)
    destination_before = repos.refs()

    code, out, err = invoke("publish", "--tag", "release", "--message", "Maintenance", "--push")

    assert code != 0 and "Tag rejected" in err
    data = result(out)
    assert data["commit"] is not None and data["pushed"] is False
    assert data["destination_branch_before"] == before and repos.refs() == destination_before


@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("arguments", [["--unexpected"], ["--commit", "HEAD", "--message", "Release"]])
def test_branch_is_unresolved_when_publication_stops_before_reading_settings(repos, invoke, result, arguments):
    """Errors before reading the selected settings retain all nine fields and an unresolved branch."""
    repos.commit()

    code, out, err = invoke("publish", *arguments)

    assert code != 0 and err
    data = result(out)
    assert data["branch"] is None and data["destination_branch_before"] == ""


@pytest.mark.req("SP-NOREN-008")
def test_initialized_branch_setting_can_be_used_for_a_first_dry_run(repos, invoke, result):
    """Setup supplies branch main so the completed template can pass a first publication check."""
    (repos.source / "noren.yaml").unlink()
    (repos.source / "noren-words.txt").unlink()
    code, _, err = invoke("init")
    assert code == 0 and err == ""
    config = yaml.safe_load((repos.source / "noren.yaml").read_text())
    assert config["branch"] == "main"
    config.update(destination="example/public", include="public/**\n",
                  author={"name": "Release Bot", "email": "release@example.invalid"})
    repos.write("noren.yaml", yaml.safe_dump(config))
    snapshot = repos.commit()

    code, out, err = invoke("publish", "--commit", snapshot, "--message", "Release", "--initial")

    assert code == 0 and err == ""
    assert result(out)["branch"] == "main"
