import pytest


@pytest.mark.req("SP-NOREN-019")
@pytest.mark.req("SP-NOREN-021")
@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("history", ["main-tip", "main-ancestor", "other-branch"])
@pytest.mark.parametrize("push", [False, True])
def test_destination_with_source_branch_history_cannot_receive_files(repos, invoke, result, history, push):
    """A destination containing local source branch history is rejected in checks and sends without changing refs."""
    before = repos.commit()
    if history == "other-branch":
        tree = repos.git("mktree").stdout.decode().strip()
        before = repos.git("commit-tree", tree, "-m", "Other development history").stdout.decode().strip()
        repos.git("branch", "other", before)
    repos.git("fetch", "--no-tags", str(repos.source), f"{before}:refs/heads/main", destination=True)
    if history == "main-ancestor":
        repos.write("public/readme.txt", "Later source snapshot\n")
        repos.commit()
    snapshot = repos.git("rev-parse", "main").stdout.decode().strip()
    source_refs = repos.git("show-ref").stdout
    destination_refs = repos.refs()

    code, out, err = invoke(
        "publish", "--commit", snapshot, "--message", "Public update", *(["--push"] if push else []),
    )

    assert code != 0 and "source" in err.lower()
    data = result(out)
    assert data["source_commit"] == snapshot and data["destination_branch_before"] == before
    assert data["commit"] is None and data["pushed"] is False
    assert repos.refs() == destination_refs
    assert repos.git("show-ref").stdout == source_refs


@pytest.mark.req("SP-NOREN-019")
@pytest.mark.req("SP-NOREN-021")
@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("annotated", [False, True])
@pytest.mark.parametrize("push", [False, True])
def test_destination_base_tag_in_source_tag_history_cannot_receive_files(repos, invoke, result, annotated, push):
    """A destination base tag in history retained only by a source tag cannot start a publication branch."""
    snapshot = repos.commit()
    tree = repos.git("mktree").stdout.decode().strip()
    base = repos.git("commit-tree", tree, "-m", "Earlier development").stdout.decode().strip()
    tagged = repos.git("commit-tree", tree, "-p", base, "-m", "Tagged development").stdout.decode().strip()
    repos.git("tag", "-a", "source-history", tagged, "-m", "Retained development history")
    tag_options = ["-a", "-m", "Base annotation"] if annotated else []
    repos.git("tag", *tag_options, "base", base)
    repos.git("fetch", "--no-tags", str(repos.source), "refs/tags/base:refs/tags/base", destination=True)
    repos.git("tag", "-d", "base")
    source_refs = repos.git("show-ref").stdout
    destination_refs = repos.refs()

    code, out, err = invoke(
        "publish", "--commit", snapshot, "--message", "Public update", "--base-tag", "base",
        *(["--push"] if push else []),
    )

    assert code != 0 and "source" in err.lower()
    data = result(out)
    assert data["destination_branch_before"] is None
    assert data["commit"] is None and data["pushed"] is False
    assert repos.refs() == destination_refs
    assert repos.git("show-ref").stdout == source_refs


@pytest.mark.req("SP-NOREN-019")
@pytest.mark.req("SP-NOREN-021")
@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("push", [False, True])
def test_destination_only_annotated_base_tag_cannot_publish_source_history(repos, invoke, result, push):
    """A base tag annotated only at the destination cannot publish source branch history or change either repository."""
    snapshot = repos.commit()
    repos.git("fetch", "--no-tags", str(repos.source), snapshot, destination=True)
    repos.git("config", "user.name", "Destination Bot", destination=True)
    repos.git("config", "user.email", "destination@example.invalid", destination=True)
    repos.git("tag", "-a", "base", snapshot, "-m", "Destination annotation", destination=True)
    base_oid = repos.git("rev-parse", "refs/tags/base", destination=True).stdout.decode().strip()
    assert repos.git("cat-file", "-e", base_oid, check=False).returncode != 0
    assert repos.git("rev-parse", "refs/tags/base^{commit}", destination=True).stdout.decode().strip() == snapshot
    source_refs = repos.git("show-ref").stdout
    source_index = (repos.source / ".git/index").read_bytes()
    source_objects = sorted(path.relative_to(repos.source / ".git/objects") for path in (repos.source / ".git/objects").rglob("*"))
    assert not (repos.source / ".git/FETCH_HEAD").exists()
    destination_refs = repos.refs()

    code, out, err = invoke(
        "publish", "--commit", snapshot, "--message", "Public update", "--base-tag", "base",
        *(["--push"] if push else []),
    )

    assert code != 0 and "source" in err.lower()
    data = result(out)
    assert data["source_commit"] == snapshot and data["destination_branch_before"] is None
    assert data["commit"] is None and data["pushed"] is False
    assert repos.refs() == destination_refs
    assert repos.git("show-ref").stdout == source_refs
    assert (repos.source / ".git/index").read_bytes() == source_index
    assert sorted(path.relative_to(repos.source / ".git/objects") for path in (repos.source / ".git/objects").rglob("*")) == source_objects
    assert not (repos.source / ".git/FETCH_HEAD").exists()


@pytest.mark.req("SP-NOREN-019")
@pytest.mark.parametrize("retain_remote_ref", [False, True])
def test_fetched_public_history_outside_local_branches_and_tags_can_receive_files(repos, invoke, result, retain_remote_ref):
    """Fetching published history into a remote-tracking ref or leaving its objects unreferenced permits further publication."""
    repos.commit("v1")
    code, out, err = invoke("publish", "--tag", "v1", "--message", "First release", "--initial", "--push")
    assert code == 0 and err == ""
    before = result(out)["commit"]
    repos.git("remote", "add", "published", "https://github.com/example/public.git")
    repos.git("fetch", "--no-tags", "published")
    assert repos.git("rev-parse", "refs/remotes/published/main").stdout.decode().strip() == before
    if not retain_remote_ref:
        repos.git("update-ref", "-d", "refs/remotes/published/main")
    assert repos.git("cat-file", "-t", before).stdout.strip() == b"commit"
    assert repos.git("for-each-ref", f"--contains={before}", "refs/heads/", "refs/tags/").stdout == b""
    repos.write("public/readme.txt", "Second release\n")
    repos.commit("v2")
    source_refs = repos.git("show-ref").stdout
    destination_refs = repos.refs()

    code, out, err = invoke("publish", "--tag", "v2", "--message", "Second release")

    assert code == 0 and err == ""
    checked = result(out)
    assert checked["destination_branch_before"] == before
    assert checked["commit"] is None and checked["pushed"] is False
    assert repos.refs() == destination_refs

    code, out, err = invoke("publish", "--tag", "v2", "--message", "Second release", "--push")

    assert code == 0 and err == ""
    sent = result(out)
    assert sent["pushed"] is True and sent["commit"] is not None
    assert sent["destination_branch_before"] == before
    assert repos.git("rev-list", "--parents", "-1", "main", destination=True).stdout.decode().split() == [sent["commit"], before]
    assert repos.git("rev-parse", "refs/tags/v2", destination=True).stdout.decode().strip() == sent["commit"]
    assert repos.git("show-ref").stdout == source_refs
