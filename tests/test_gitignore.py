import pytest


@pytest.mark.req("SP-NOREN-002")
@pytest.mark.req("SP-NOREN-016")
@pytest.mark.req("SP-NOREN-027")
@pytest.mark.parametrize("rules,excluded", [
    ("public/internal/\n!public/internal/leak.txt\n", True),
    ("public/internal/\n!public/internal/\n!public/internal/leak.txt\n", False),
    ("public/internal/**\n!public/internal/leak.txt\n", False),
])
def test_excluded_parent_requires_directory_reopening_before_a_file_can_be_sent(repos, invoke, result, rules, excluded):
    """A file stays excluded under an excluded parent until its parent directory is explicitly restored."""
    settings = repos.configure()
    repos.configure(exclude=settings["exclude"] + rules)
    repos.write("public/internal/leak.txt", "Content that does not match a forbidden word\n")
    repos.commit("v1")
    # Git evaluates the same rules independently; this working file is not in the tag.
    repos.write(".gitignore", rules)
    git_decision = repos.git("check-ignore", "--no-index", "public/internal/leak.txt", check=False)
    assert git_decision.returncode == (0 if excluded else 1)

    code, out, err = invoke("publish", "--tag", "v1", "--message", "Release", "--initial", "--push")

    assert code == 0 and err == ""
    expected = ["public/readme.txt"] if excluded else ["public/internal/leak.txt", "public/readme.txt"]
    assert result(out)["files"] == expected
    assert result(out)["pushed"] is True
    assert repos.git("ls-tree", "-r", "--name-only", "main", destination=True).stdout.decode().splitlines() == expected


@pytest.mark.req("SP-NOREN-004")
@pytest.mark.req("SP-NOREN-016")
@pytest.mark.req("SP-NOREN-027")
@pytest.mark.parametrize("rules,included", [
    ("public/\n!public/internal/leak.txt\n", True),
    ("public/\n!public/\npublic/**\n!public/internal/\n!public/internal/leak.txt\n", False),
    ("public/readme.txt\npublic/internal/**\n!public/internal/leak.txt\n", False),
])
def test_include_list_uses_the_same_parent_directory_rules_as_gitignore(repos, invoke, result, rules, included):
    """The include list retains parent matches and permits file negation only when its parent is not matched."""
    repos.configure(include=rules)
    repos.write("public/internal/leak.txt", "Safe content\n")
    repos.commit("v1")
    repos.write(".gitignore", rules)
    git_decision = repos.git("check-ignore", "--no-index", "public/internal/leak.txt", check=False)
    assert git_decision.returncode == (0 if included else 1)

    code, out, err = invoke("publish", "--tag", "v1", "--message", "Release", "--initial", "--push")

    data = result(out)
    if included:
        assert code == 0 and err == ""
        assert data["files"] == ["public/internal/leak.txt", "public/readme.txt"]
        assert repos.git("ls-tree", "-r", "--name-only", "main", destination=True).stdout.decode().splitlines() == data["files"]
    else:
        assert code != 0 and "public/internal/leak.txt" in err
        assert data["files"] == ["public/readme.txt"] and data["pushed"] is False
        assert repos.refs() == b""
