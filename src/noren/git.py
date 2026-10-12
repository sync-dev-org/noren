"""Git plumbing with captured output and no shell interpolation."""

from dataclasses import dataclass
from pathlib import Path
import subprocess


class NorenError(Exception):
    """An error that can be reported to the operator without a traceback."""


def run_git(cwd: Path, *args: str, input: bytes | None = None, env=None, valid_exit_codes=(0,)) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "--no-replace-objects", "-C", str(cwd), *args], input=input, env=env, capture_output=True,
        )
    except OSError as error:
        raise NorenError(f"Cannot run git: {error}") from error
    if completed.returncode not in valid_exit_codes:
        reason = completed.stderr.decode("utf-8", errors="replace").strip()
        raise NorenError(f"git {args[0]} failed: {reason}")
    return completed.stdout


@dataclass(frozen=True)
class Repository:
    root: Path

    @classmethod
    def discover(cls):
        root = run_git(Path.cwd(), "rev-parse", "--show-toplevel").decode().strip()
        return cls(Path(root))

    def git(self, *args: str, input: bytes | None = None, env=None) -> bytes:
        return run_git(self.root, *args, input=input, env=env)

    def origin(self) -> str:
        try:
            return self.git("config", "--get", "remote.origin.url").decode().strip()
        except NorenError as error:
            raise NorenError("The source repository needs an origin remote URL.") from error

    def entries(self, commit: str):
        entries = []
        for record in self.git("ls-tree", "-r", "--full-tree", "-z", commit).split(b"\0"):
            if record:
                metadata, path = record.split(b"\t", 1)
                mode, kind, oid = metadata.decode("ascii").split()
                entries.append(Entry(path.decode("utf-8", errors="surrogateescape"), mode, kind, oid))
        return entries

    def blob(self, entry) -> bytes:
        if entry.kind != "blob":
            raise NorenError(f"Cannot read file contents for {entry.path} ({entry.kind}).")
        return self.git("cat-file", "blob", entry.oid)


@dataclass(frozen=True)
class Entry:
    path: str
    mode: str
    kind: str
    oid: str
