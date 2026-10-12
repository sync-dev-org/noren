import pytest
import yaml


@pytest.mark.req("SP-NOREN-003")
@pytest.mark.req("SP-NOREN-006")
@pytest.mark.req("SP-NOREN-008")
@pytest.mark.req("SP-NOREN-018")
@pytest.mark.req("SP-NOREN-024")
@pytest.mark.req("SP-NOREN-026")
@pytest.mark.req("SP-NOREN-027")
def test_init_creates_templates_at_repository_root_without_prompting(repos, invoke, monkeypatch):
    """Setup creates both templates, names the source, and requests all required settings."""
    (repos.source / "noren.yaml").unlink()
    (repos.source / "noren-words.txt").unlink()
    nested = repos.source / "nested"
    nested.mkdir()
    monkeypatch.chdir(nested)

    code, out, err = invoke("init")

    assert code == 0 and err == ""
    config = yaml.safe_load((repos.source / "noren.yaml").read_text())
    assert set(config) == {"destination", "include", "exclude", "word-list"}
    assert config["destination"] == ""
    assert config["include"] == ""
    assert config["word-list"] == "noren-words.txt"
    assert config["exclude"].splitlines() == ["noren.yaml", "noren-words.txt"]
    assert (repos.source / "noren-words.txt").read_text().splitlines() == [
        "git@github.com:example/private.git", "private",
    ]
    for required in ("destination", "include", "exclude", "word-list", "forbidden"):
        assert required in out
    assert not (nested / "noren.yaml").exists()


@pytest.mark.req("SP-NOREN-018")
@pytest.mark.req("SP-NOREN-026")
@pytest.mark.parametrize("existing", ["noren.yaml", "noren-words.txt"])
def test_init_preserves_existing_templates_without_partial_creation(repos, invoke, existing):
    """Setup preserves an existing template and does not create the other template."""
    other = "noren-words.txt" if existing == "noren.yaml" else "noren.yaml"
    original = (repos.source / existing).read_bytes()
    (repos.source / other).unlink()

    code, _, err = invoke("init")

    assert code != 0 and existing in err
    assert (repos.source / existing).read_bytes() == original
    assert not (repos.source / other).exists()


@pytest.mark.req("SP-NOREN-024")
def test_init_requires_origin_without_creating_templates(repos, invoke):
    """Setup reports a missing source URL without creating either template."""
    (repos.source / "noren.yaml").unlink()
    (repos.source / "noren-words.txt").unlink()
    repos.git("remote", "remove", "origin")

    code, _, err = invoke("init")

    assert code != 0 and "origin" in err
    assert not (repos.source / "noren.yaml").exists()
    assert not (repos.source / "noren-words.txt").exists()


@pytest.mark.req("SP-NOREN-026")
def test_init_does_not_accept_destination_as_an_argument(repos, invoke):
    """Setup rejects arguments rather than adding a second source for destination settings."""
    original = (repos.source / "noren.yaml").read_bytes()

    code, _, err = invoke("init", "example/public")

    assert code != 0 and err
    assert (repos.source / "noren.yaml").read_bytes() == original
