import re

import pytest
import yaml


def publish(invoke, result, tag="v1", initial=True):
    code, out, err = invoke(
        "publish", "--tag", tag, "--message", f"Public release {tag}",
        *(["--initial"] if initial else []), "--push",
    )
    return code, result(out), err


def seed_destination(repos):
    repos.git("config", "user.name", "Public Bot", destination=True)
    repos.git("config", "user.email", "public@example.invalid", destination=True)
    tree = repos.git("mktree", destination=True).stdout.decode().strip()
    commit = repos.git("commit-tree", tree, "-m", "Existing public history", destination=True).stdout.decode().strip()
    repos.git("update-ref", "refs/heads/main", commit, destination=True)
    return commit


@pytest.mark.req("SP-NOREN-001")
@pytest.mark.req("SP-NOREN-002")
@pytest.mark.req("SP-NOREN-009")
@pytest.mark.req("SP-NOREN-010")
@pytest.mark.req("SP-NOREN-012")
@pytest.mark.req("SP-NOREN-021")
@pytest.mark.req("SP-NOREN-023")
@pytest.mark.req("SP-NOREN-030")
@pytest.mark.req("SP-NOREN-032")
@pytest.mark.req("SP-NOREN-033")
def test_two_releases_only_extend_public_history_and_keep_source_untouched(repos, invoke, result, gh_boundary):
    """Each release adds one public commit with only selected files, supplied metadata, and public parents."""
    repos.write("private/key.txt", "Do not send")
    first_source = repos.commit()
    repos.write("public/readme.txt", "Public version one\n")
    tagged_source = repos.commit("v1")
    refs_before = repos.git("show-ref").stdout
    index_before = (repos.source / ".git/index").read_bytes()
    source_objects = {path.relative_to(repos.source / ".git/objects") for path in (repos.source / ".git/objects").rglob("*")}
    (repos.source / ".git/hooks/pre-push").write_text("#!/bin/sh\nexit 1\n")
    (repos.source / ".git/hooks/pre-push").chmod(0o755)
    repos.git("config", "core.hooksPath", str(repos.source / ".git/hooks"))
    code, first, err = publish(invoke, result)
    assert code == 0 and err == "" and first["pushed"] is True
    first_commit = first["commit"]
    assert re.fullmatch(r"[0-9a-f]{40}", first_commit)
    assert first["destination_main_before"] is None
    assert repos.git("rev-list", "--parents", "main", destination=True).stdout.decode().strip() == first_commit
    assert repos.git("ls-tree", "-r", "--name-only", "main", destination=True).stdout.decode().splitlines() == ["public/readme.txt"]
    assert repos.git("show", "main:public/readme.txt", destination=True).stdout == b"Public version one\n"
    assert repos.git("rev-parse", "refs/tags/v1", destination=True).stdout.decode().strip() == first_commit
    assert repos.git("show", "-s", "--format=%an%n%ae%n%cn%n%ce%n%B", "main", destination=True).stdout.decode().splitlines() == [
        "Release Bot", "release@example.invalid", "Release Bot", "release@example.invalid", "Public release v1", "",
    ]
    assert repos.git("show-ref").stdout == refs_before
    assert (repos.source / ".git/index").read_bytes() == index_before
    assert {path.relative_to(repos.source / ".git/objects") for path in (repos.source / ".git/objects").rglob("*")} == source_objects
    assert not (repos.source / ".git/FETCH_HEAD").exists()

    (repos.source / "public/readme.txt").unlink()
    repos.write("public/new.txt", "New file\n")
    second_source = repos.commit("v2")
    code, dry_out, err = invoke("publish", "--tag", "v2", "--message", "Public release v2")
    assert code == 0 and err == ""
    dry_run = result(dry_out)
    code, second, err = publish(invoke, result, tag="v2", initial=False)
    assert code == 0 and err == ""
    assert second["files"] == dry_run["files"]
    assert second["destination_main_before"] == dry_run["destination_main_before"] == first_commit
    second_commit = second["commit"]
    assert repos.git("rev-list", "--parents", "main", destination=True).stdout.decode().splitlines() == [f"{second_commit} {first_commit}", first_commit]
    assert repos.git("rev-parse", "refs/tags/v1", destination=True).stdout.decode().strip() == first_commit
    assert repos.git("rev-parse", "refs/tags/v2", destination=True).stdout.decode().strip() == second_commit
    assert repos.git("ls-tree", "-r", "--name-only", "main", destination=True).stdout.decode().splitlines() == ["public/new.txt"]
    assert repos.git("show", "refs/tags/v1:public/readme.txt", destination=True).stdout == b"Public version one\n"
    for source_commit in (first_source, tagged_source, second_source):
        assert repos.git("cat-file", "-e", source_commit, destination=True, check=False).returncode != 0
    assert b"PRIVATE" not in repos.git("log", "--format=%B", "--all", destination=True).stdout
    assert gh_boundary["calls"] == []


@pytest.mark.req("SP-NOREN-012")
@pytest.mark.req("SP-NOREN-030")
@pytest.mark.parametrize("main_exists", [False, True])
def test_initial_flag_must_agree_with_main_and_correct_flag_allows_publication(repos, invoke, result, main_exists):
    """Publication rejects an incorrect first-release flag and proceeds with the correct flag."""
    before = seed_destination(repos) if main_exists else None
    repos.commit("v1")
    refs_before = repos.refs()
    code, failed, err = publish(invoke, result, initial=main_exists)
    assert code != 0 and "--initial" in err
    assert failed["destination_main_before"] == before
    assert failed["commit"] is None and failed["pushed"] is False
    assert repos.refs() == refs_before
    code, sent, err = publish(invoke, result, initial=not main_exists)
    assert code == 0 and err == "" and sent["pushed"] is True


@pytest.mark.req("SP-NOREN-023")
def test_existing_destination_tag_prevents_all_updates_and_a_new_tag_can_be_sent(repos, invoke, result):
    """A destination tag cannot be reused, while a new tag can extend the same main branch."""
    before = seed_destination(repos)
    repos.git("tag", "v1", before, destination=True)
    repos.commit("v1")
    refs_before = repos.refs()
    code, failed, err = publish(invoke, result, initial=False)
    assert code != 0 and "v1" in err
    assert failed["commit"] is None
    assert repos.refs() == refs_before
    repos.git("tag", "v2")
    code, sent, err = publish(invoke, result, tag="v2", initial=False)
    assert code == 0 and err == "" and sent["pushed"] is True


@pytest.mark.req("SP-NOREN-010")
@pytest.mark.parametrize("account_name,expected_name", [("GitHub Release", "GitHub Release"), ("", "publisher"), (None, "publisher")])
def test_author_defaults_to_github_name_or_username_and_noreply_address(repos, invoke, result, gh_boundary, account_name, expected_name):
    """An available GitHub account supplies both identities using its public name and noreply address."""
    config = repos.configure()
    del config["author"]
    repos.write("noren.yaml", yaml.safe_dump(config))
    repos.commit("v1")
    gh_boundary["user"] = {"id": 1234, "login": "publisher", "name": account_name}
    code, sent, err = publish(invoke, result)
    assert code == 0 and err == "" and sent["pushed"] is True
    assert repos.git("show", "-s", "--format=%an%n%ae%n%cn%n%ce", "main", destination=True).stdout.decode().splitlines() == [
        expected_name, "1234+publisher@users.noreply.github.com", expected_name, "1234+publisher@users.noreply.github.com",
    ]
    assert gh_boundary["calls"] == [["gh", "api", "user"]]


@pytest.mark.req("SP-NOREN-010")
@pytest.mark.req("SP-NOREN-033")
def test_unavailable_gh_requires_author_and_configured_identity_does_not_use_gh(repos, invoke, result, gh_boundary):
    """Without gh an absent author prevents publication, and explicit settings then permit it without gh."""
    config = repos.configure()
    del config["author"]
    repos.write("noren.yaml", yaml.safe_dump(config))
    repos.commit("v1")
    code, failed, err = publish(invoke, result)
    assert code != 0 and "author" in err
    assert failed["author"] is None and failed["commit"] is None and repos.refs() == b""
    calls_before = list(gh_boundary["calls"])
    repos.configure()
    repos.commit("v2")
    code, sent, err = publish(invoke, result, tag="v2")
    assert code == 0 and err == "" and sent["pushed"] is True
    assert sent["author"] == {"name": "Release Bot", "email": "release@example.invalid"}
    assert gh_boundary["calls"] == calls_before


@pytest.mark.req("SP-NOREN-020")
@pytest.mark.req("SP-NOREN-021")
@pytest.mark.req("SP-NOREN-033")
def test_failed_push_reports_created_commit_and_previous_main(repos, invoke, result):
    """A rejected push prints the attempted commit and previous main, with no false success or ref updates."""
    before = seed_destination(repos)
    hook = repos.destination / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\necho 'Publication rejected' >&2\nexit 1\n")
    hook.chmod(0o755)
    repos.commit("v1")
    refs_before = repos.refs()
    code, failed, err = publish(invoke, result, initial=False)
    assert code != 0 and "Publication rejected" in err
    assert failed["destination_main_before"] == before
    assert failed["author"] == {"name": "Release Bot", "email": "release@example.invalid"}
    assert re.fullmatch(r"[0-9a-f]{40}", failed["commit"])
    assert failed["pushed"] is False
    assert repos.refs() == refs_before


@pytest.mark.req("SP-NOREN-012")
@pytest.mark.req("SP-NOREN-023")
def test_rejected_tag_keeps_main_and_tag_unchanged_in_atomic_push(repos, invoke, result):
    """Rejection of the destination tag also prevents the main branch update."""
    before = seed_destination(repos)
    hook = repos.destination / "hooks/update"
    hook.write_text('#!/bin/sh\ncase "$1" in refs/tags/*) echo "Tag rejected" >&2; exit 1;; esac\nexit 0\n')
    hook.chmod(0o755)
    repos.commit("v1")
    refs_before = repos.refs()
    code, failed, err = publish(invoke, result, initial=False)
    assert code != 0 and "Tag rejected" in err
    assert failed["destination_main_before"] == before
    assert failed["commit"] is not None and failed["pushed"] is False
    assert repos.refs() == refs_before


@pytest.mark.req("SP-NOREN-002")
@pytest.mark.req("SP-NOREN-005")
def test_executable_files_and_symlinks_preserve_git_modes_and_blob_contents(repos, invoke, result):
    """Selected executable files and symlinks retain their Git modes and exact tagged bytes."""
    repos.write("public/run.sh", "#!/bin/sh\necho release\n")
    (repos.source / "public/run.sh").chmod(0o755)
    (repos.source / "public/link").symlink_to("readme.txt")
    repos.commit("v1")
    code, sent, err = publish(invoke, result)
    assert code == 0 and err == "" and sent["pushed"] is True
    tree = repos.git("ls-tree", "main:public", destination=True).stdout.decode()
    assert "100755 blob" in tree and "120000 blob" in tree
    assert repos.git("show", "main:public/link", destination=True).stdout == b"readme.txt"
    assert repos.git("show", "main:public/run.sh", destination=True).stdout == b"#!/bin/sh\necho release\n"


@pytest.mark.req("SP-NOREN-002")
@pytest.mark.req("SP-NOREN-005")
def test_forbidden_symlink_target_is_rejected_then_safe_target_can_be_sent(repos, invoke, result):
    """Symlink target strings are inspected without reading files outside the tagged tree."""
    link = repos.source / "public/link"
    link.symlink_to("../../private-token")
    repos.commit("v1")
    code, failed, err = publish(invoke, result)
    assert code != 0 and "public/link" in err
    assert failed["commit"] is None and repos.refs() == b""
    link.unlink()
    link.symlink_to("../../safe-missing-file")
    repos.commit("v2")
    code, sent, err = publish(invoke, result, tag="v2")
    assert code == 0 and err == ""
    assert repos.git("show", "main:public/link", destination=True).stdout == b"../../safe-missing-file"


@pytest.mark.req("SP-NOREN-002")
@pytest.mark.req("SP-NOREN-005")
def test_included_submodule_stops_and_excluded_submodule_does_not_send_its_commit(repos, invoke, result):
    """A selected gitlink prevents publication; an excluded gitlink never brings its commit into public history."""
    source_commit = repos.commit()
    repos.git("update-index", "--add", "--cacheinfo", f"160000,{source_commit},public/module")
    repos.git("commit", "-m", "PRIVATE submodule")
    repos.git("tag", "v1")
    code, failed, err = publish(invoke, result)
    assert code != 0 and "gitlink" in err and "public/module" in err
    assert failed["commit"] is None and repos.refs() == b""
    config = repos.configure()
    repos.configure(exclude=config["exclude"] + "public/module\n")
    # Preserve the index-only gitlink while staging the changed settings.
    repos.git("add", "noren.yaml")
    repos.git("commit", "-m", "PRIVATE excluded submodule")
    repos.git("tag", "v2")
    code, sent, err = publish(invoke, result, tag="v2")
    assert code == 0 and err == "" and sent["pushed"] is True
    assert "public/module" not in sent["files"]
    assert repos.git("cat-file", "-e", source_commit, destination=True, check=False).returncode != 0


@pytest.mark.req("SP-NOREN-023")
@pytest.mark.req("SP-NOREN-028")
@pytest.mark.req("SP-NOREN-033")
def test_publication_uses_annotated_tag_even_when_current_files_are_different(repos, invoke, result):
    """An annotated tag supplies the published bytes and settings regardless of later commits and dirty files."""
    tagged = repos.commit()
    repos.git("tag", "-a", "v1", "-m", "PRIVATE annotation", tagged)
    repos.configure(destination="other/unwanted", include="**", exclude="")
    repos.write("public/readme.txt", "HEAD private-token")
    repos.write("noren-words.txt", "release")
    repos.commit()
    repos.write("public/readme.txt", "WORKTREE private-token")
    repos.write("noren.yaml", "broken: [")
    code, sent, err = publish(invoke, result)
    assert code == 0 and err == "" and sent["destination"] == "example/public"
    assert sent["source_commit"] == tagged
    assert repos.git("show", "main:public/readme.txt", destination=True).stdout == b"Public release\n"
    assert repos.git("cat-file", "-t", "refs/tags/v1", destination=True).stdout == b"commit\n"
