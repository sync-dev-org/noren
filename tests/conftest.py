"""Real repositories isolated from the user's git configuration and credentials."""

from dataclasses import dataclass
from pathlib import Path
import json
import subprocess

import pytest
import yaml


@dataclass
class Repositories:
    source: Path
    destination: Path

    def git(self, *args: str, destination: bool = False, check: bool = True, input: bytes | None = None):
        return subprocess.run(
            ["git", "-C", str(self.destination if destination else self.source), *args],
            capture_output=True,
            check=check,
            input=input,
        )

    def write(self, name: str, content: str | bytes):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode() if isinstance(content, str) else content)

    def configure(self, **changes):
        settings = {
            "destination": "example/public",
            "include": "public/**\n",
            "exclude": "noren.yaml\nnoren-words.txt\nprivate/**\n",
            "word-list": "noren-words.txt",
            "author": {"name": "Release Bot", "email": "release@example.invalid"},
        }
        settings.update(changes)
        self.write("noren.yaml", yaml.safe_dump(settings))
        return settings

    def commit(self, tag: str | None = None):
        self.git("add", "--all")
        self.git("commit", "-m", "PRIVATE source message")
        if tag:
            self.git("tag", tag)
        return self.git("rev-parse", "HEAD").stdout.decode().strip()

    def refs(self):
        return self.git("show-ref", destination=True, check=False).stdout


@pytest.fixture
def gh_boundary(monkeypatch):
    """Only gh is replaced; all git subprocesses execute real git."""
    real_run = subprocess.run
    boundary = {"user": None, "calls": []}

    def run(arguments, *args, **kwargs):
        if arguments[0] == "gh":
            boundary["calls"].append(arguments)
            if boundary["user"] is None:
                raise FileNotFoundError("gh is unavailable in the test")
            return subprocess.CompletedProcess(arguments, 0, json.dumps(boundary["user"]).encode(), b"")
        return real_run(arguments, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    return boundary


@pytest.fixture
def repos(tmp_path, monkeypatch, gh_boundary):
    for key in (
        "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_CONFIG", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
        "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "unused-global-config"))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "unused-system-config"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    monkeypatch.setenv("GIT_ASKPASS", "/bin/false")
    monkeypatch.setenv("GIT_SSH_COMMAND", "/bin/false")
    source = tmp_path / "source"
    destination = tmp_path / "destination.git"
    source.mkdir()
    destination.mkdir()
    repositories = Repositories(source, destination)
    repositories.git("init", "--initial-branch=main")
    repositories.git("config", "user.name", "Private Developer")
    repositories.git("config", "user.email", "private@example.invalid")
    repositories.git("config", "core.hooksPath", "/dev/null")
    repositories.git("init", "--bare", "--initial-branch=main", destination=True)
    repositories.git("remote", "add", "origin", "git@github.com:example/private.git")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{destination.as_uri()}.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "https://github.com/example/public.git")
    monkeypatch.chdir(source)
    repositories.configure()
    repositories.write("noren-words.txt", "private-token\nprivate@example.invalid\n")
    repositories.write("public/readme.txt", "Public release\n")
    return repositories


@pytest.fixture
def invoke(capsys):
    def run(*arguments: str):
        from noren.cli import main

        code = main(list(arguments))
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return run


@pytest.fixture
def result():
    def read(output):
        documents = list(yaml.safe_load_all(output))
        assert len(documents) == 1
        data = documents[0]
        assert set(data) == {
            "tag", "source_commit", "destination", "files", "destination_main_before", "commit", "pushed",
        }
        assert data["tag"] is None or isinstance(data["tag"], str)
        assert data["source_commit"] is None or isinstance(data["source_commit"], str)
        assert isinstance(data["destination"], str)
        assert isinstance(data["files"], list)
        assert all(isinstance(path, str) for path in data["files"])
        assert data["destination_main_before"] is None or isinstance(data["destination_main_before"], str)
        assert data["commit"] is None or isinstance(data["commit"], str)
        assert isinstance(data["pushed"], bool)
        return data

    return read
