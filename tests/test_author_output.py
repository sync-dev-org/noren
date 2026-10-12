import pytest
import yaml


@pytest.mark.req("SP-NOREN-010")
@pytest.mark.req("SP-NOREN-028")
@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("selector", ["--tag", "--commit"])
@pytest.mark.parametrize("identity_source", ["settings", "github-name", "github-username"])
def test_checked_author_matches_sent_author_and_both_destination_identities(
    repos, invoke, result, gh_boundary, selector, identity_source,
):
    """Checking and sending expose the same configured or GitHub identity used for both destination identities."""
    expected = {"name": "Release Bot", "email": "release@example.invalid"}
    if identity_source != "settings":
        config = repos.configure()
        del config["author"]
        repos.write("noren.yaml", yaml.safe_dump(config))
        account_name = "GitHub Release" if identity_source == "github-name" else ""
        gh_boundary["user"] = {"id": 1234, "login": "publisher", "name": account_name}
        expected = {"name": account_name or "publisher", "email": "1234+publisher@users.noreply.github.com"}
    snapshot = repos.commit("v1")
    # The printed identity must come from the selected snapshot, not dirty settings.
    repos.configure(author={"name": "Unselected Author", "email": "unselected@example.invalid"})
    arguments = ["publish", selector, "v1" if selector == "--tag" else snapshot, "--message", "Release", "--initial"]

    code, out, err = invoke(*arguments)

    assert code == 0 and err == ""
    checked = result(out)
    assert checked["author"] == expected
    assert checked["commit"] is None and checked["pushed"] is False
    assert repos.refs() == b""

    code, out, err = invoke(*arguments, "--push")

    assert code == 0 and err == ""
    sent = result(out)
    assert sent["author"] == checked["author"]
    assert sent["pushed"] is True
    metadata = repos.git("show", "-s", "--format=%an%n%ae%n%cn%n%ce", sent["commit"], destination=True)
    assert metadata.stdout.decode().splitlines() == [
        expected["name"], expected["email"], expected["name"], expected["email"],
    ]
    assert gh_boundary["calls"] == ([] if identity_source == "settings" else [["gh", "api", "user"]] * 2)


@pytest.mark.req("SP-NOREN-010")
@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("failure", ["forbidden-content", "invalid-author"])
def test_failure_before_resolving_author_prints_null_without_sending(repos, invoke, result, failure):
    """Content rejection and invalid identity settings report an unresolved author without updating destination refs."""
    if failure == "forbidden-content":
        repos.write("public/readme.txt", "private-token\n")
    else:
        repos.configure(author={"name": "Release Bot", "email": ""})
    repos.commit("v1")

    code, out, err = invoke("publish", "--tag", "v1", "--message", "Release", "--initial", "--push")

    assert code != 0
    assert ("Forbidden word" if failure == "forbidden-content" else "author") in err
    data = result(out)
    assert data["author"] is None and data["commit"] is None and data["pushed"] is False
    assert repos.refs() == b""


@pytest.mark.req("SP-NOREN-010")
@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("selector", ["--tag", "--commit"])
@pytest.mark.parametrize("identity_source", ["settings", "github-name"])
@pytest.mark.parametrize("name", ["Release Bot", "Release Bot."])
def test_author_with_surrounding_whitespace_matches_git_metadata(
    repos, invoke, result, gh_boundary, selector, identity_source, name,
):
    """Checking and sending print Git's recorded name and email when the resolved identity has surrounding whitespace."""
    if identity_source == "settings":
        email = "release@example.invalid"
        repos.configure(author={"name": f" {name} ", "email": f" {email} "})
    else:
        email = "1234+publisher@users.noreply.github.com"
        config = repos.configure()
        del config["author"]
        repos.write("noren.yaml", yaml.safe_dump(config))
        gh_boundary["user"] = {"id": 1234, "login": "publisher", "name": f" {name} "}
    snapshot = repos.commit("v1")
    arguments = ["publish", selector, "v1" if selector == "--tag" else snapshot, "--message", "Release", "--initial"]

    code, out, err = invoke(*arguments)

    assert code == 0 and err == ""
    checked = result(out)
    assert checked["author"] == {"name": name, "email": email}
    assert checked["commit"] is None and checked["pushed"] is False and repos.refs() == b""

    code, out, err = invoke(*arguments, "--push")

    assert code == 0 and err == ""
    sent = result(out)
    assert sent["author"] == checked["author"] and sent["pushed"] is True
    metadata = repos.git("show", "-s", "--format=%an%n%ae%n%cn%n%ce", sent["commit"], destination=True)
    assert metadata.stdout.decode().splitlines() == [name, email, name, email]


@pytest.mark.req("SP-NOREN-010")
@pytest.mark.req("SP-NOREN-033")
@pytest.mark.parametrize("push", [False, True])
@pytest.mark.parametrize("identity_source", ["settings-name", "settings-email", "github-name"])
def test_identity_that_git_normalizes_to_an_empty_value_stops_with_null_author(
    repos, invoke, result, gh_boundary, identity_source, push,
):
    """Checking and sending reject an empty normalized name or email before reporting an author or updating destination refs."""
    disallowed = ' ,;:"\\ '
    if identity_source == "github-name":
        config = repos.configure()
        del config["author"]
        repos.write("noren.yaml", yaml.safe_dump(config))
        gh_boundary["user"] = {"id": 1234, "login": "publisher", "name": disallowed}
    else:
        identity = {"name": "Release Bot", "email": "release@example.invalid"}
        identity[identity_source.removeprefix("settings-")] = disallowed
        repos.configure(author=identity)
    repos.commit("v1")

    code, out, err = invoke(
        "publish", "--tag", "v1", "--message", "Release", "--initial", *(["--push"] if push else []),
    )

    assert code != 0 and err
    data = result(out)
    assert data["author"] is None and data["commit"] is None and data["pushed"] is False
    assert "author" in err.lower()
    assert repos.refs() == b""
