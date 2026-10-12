"""Validate a source snapshot before constructing a destination commit."""

import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from tempfile import TemporaryDirectory
import unicodedata
from urllib.parse import unquote, urlsplit

import yaml

from noren.git import NorenError, Repository, run_git


def settings(repository, entries, output):
    config_entry = next((entry for entry in entries if entry.path == "noren.yaml"), None)
    if config_entry is None:
        raise NorenError("noren.yaml is missing from the selected source commit.")
    try:
        config = yaml.safe_load(repository.blob(config_entry).decode("utf-8"))
    except (UnicodeError, yaml.YAMLError, NorenError) as error:
        raise NorenError(f"Cannot read noren.yaml from the selected source commit: {error}") from error
    if not isinstance(config, dict):
        raise NorenError("noren.yaml must be a YAML mapping.")
    if isinstance(config.get("destination"), str):
        output["destination"] = config["destination"]
    for key in ("destination", "include", "exclude", "word-list"):
        if key not in config:
            raise NorenError(f"noren.yaml requires the {key} setting.")
        if not isinstance(config[key], str):
            raise NorenError(f"noren.yaml: {key} must be a string.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", config["destination"]):
        raise NorenError("noren.yaml: destination must be a GitHub OWNER/REPO.")
    words_path = PurePosixPath(config["word-list"])
    if not config["word-list"] or words_path.is_absolute() or ".." in words_path.parts:
        raise NorenError("noren.yaml: word-list must name a file inside the repository.")
    config["word-list"] = str(words_path)
    return config


def match_lists(entries, config):
    # The virtual worktree has no source files or .gitignore files. Git infers
    # parent directories from the paths; a trailing slash identifies gitlinks
    # as directories. Only the two committed noren lists supply ignore rules.
    requests = {
        entry.path + ("/" if entry.kind == "commit" else ""): entry.path
        for entry in entries
    }
    paths = "".join(path + "\0" for path in requests).encode("utf-8", errors="surrogateescape")
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    with TemporaryDirectory(prefix="noren-patterns-") as temporary:
        directory = Path(temporary)
        worktree = directory / "tree"
        worktree.mkdir()
        rules = directory / "rules"
        run_git(worktree, "init", "--quiet", "--template=", "--initial-branch=main", env=environment)
        matches = {}
        for name in ("include", "exclude"):
            rules.write_text(config[name], encoding="utf-8")
            matched = run_git(
                worktree, "-c", f"core.excludesFile={rules}", "-c", "core.ignoreCase=false",
                "check-ignore", "--no-index", "-z", "--stdin",
                input=paths, env=environment, valid_exit_codes=(0, 1),
            )
            matches[name] = {
                requests[path.decode("utf-8", errors="surrogateescape")]
                for path in matched.split(b"\0") if path
            }
    return matches


def choose_files(entries, config, output):
    matches = match_lists(entries, config)
    selected = []
    unclassified = []
    for entry in entries:
        if entry.path in matches["exclude"]:
            continue
        if entry.path in matches["include"]:
            selected.append(entry)
        else:
            unclassified.append(entry.path)
    selected.sort(key=lambda entry: entry.path)
    output["files"] = [entry.path for entry in selected]
    if unclassified:
        raise NorenError("Files missing from both include and exclude:\n" + "\n".join(unclassified))
    return selected


def normalized(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def inspect_content(repository, entries, selected, config):
    word_entry = next((entry for entry in entries if entry.path == config["word-list"]), None)
    if word_entry is None:
        raise NorenError(f"The word-list file {config['word-list']} is missing from the selected source commit.")
    words = [
        normalized(line.strip())
        for line in repository.blob(word_entry).decode("utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    if not words:
        raise NorenError("The forbidden word-list must contain at least one word.")
    blobs = {}
    matches = []
    for entry in selected:
        if entry.kind != "blob":
            raise NorenError(f"Cannot publish submodule gitlink {entry.path}; exclude it to continue.")
        blob = repository.blob(entry)
        blobs[entry.path] = blob
        text = normalized(blob.decode("utf-8", errors="replace"))
        for word in words:
            position = text.find(word)
            if position >= 0:
                line = text.count("\n", 0, position) + 1
                matches.append(f"Forbidden word in {entry.path} at line {line}.")
                break
    if matches:
        raise NorenError("\n".join(matches))
    return blobs


def github_repository(url: str) -> str | None:
    if re.match(r"^(?:[^/@]+@)?github\.com:", url, flags=re.IGNORECASE):
        path = url.split(":", 1)[1]
    else:
        parsed = urlsplit(url)
        if parsed.hostname is None or parsed.hostname.lower() != "github.com":
            return None
        path = unquote(parsed.path).lstrip("/")
    return path.rstrip("/").removesuffix(".git").casefold()


def reject_source_destination(repository, config, url):
    destination = config["destination"].casefold()
    if "origin" in repository.git("remote").decode().splitlines():
        # Origin's fetch URL identifies the source, as it does for setup. Other
        # remotes and push URLs may deliberately point at the public destination.
        urls = [repository.origin(), repository.git("remote", "get-url", "origin").decode().strip()]
        if any(github_repository(source) == destination for source in urls):
            raise NorenError("The destination is the source repository; no files will be sent.")
    effective = repository.git("ls-remote", "--get-url", url).decode().strip()
    parsed = urlsplit(effective)
    if parsed.scheme == "file":
        local_path = Path(unquote(parsed.path))
    elif not parsed.scheme and ":" not in effective:
        local_path = repository.root / effective
    else:
        return
    source_git = repository.git("rev-parse", "--absolute-git-dir").decode().strip()
    if local_path.resolve() in (repository.root.resolve(), Path(source_git).resolve()):
        raise NorenError("The destination is the source repository; no files will be sent.")


def author(repository, config):
    if "author" in config:
        identity = config["author"]
        if not isinstance(identity, dict):
            raise NorenError("noren.yaml: author must have name and email strings.")
        name, email = identity.get("name"), identity.get("email")
    else:
        try:
            completed = subprocess.run(["gh", "api", "user"], capture_output=True)
            if completed.returncode:
                raise NorenError("GitHub account is unavailable.")
            account = json.loads(completed.stdout)
            login, identifier = account["login"], account["id"]
            if not isinstance(login, str) or not login or type(identifier) is not int:
                raise NorenError("GitHub account is invalid.")
            name = account.get("name") or login
            email = f"{identifier}+{login}@users.noreply.github.com"
        except (OSError, ValueError, KeyError, TypeError, NorenError) as error:
            raise NorenError("Configure author.name and author.email in noren.yaml; gh is unavailable.") from error
    if not all(isinstance(value, str) and value.strip() and not any(char in value for char in "\r\n<>") for value in (name, email)):
        raise NorenError("noren.yaml: author needs valid nonempty name and email strings.")
    environment = os.environ.copy()
    environment.update(GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email)
    try:
        identity = repository.git("var", "GIT_AUTHOR_IDENT", env=environment).decode("utf-8")
    except NorenError as error:
        raise NorenError(f"noren.yaml: author is invalid: {error}") from error
    name, email_and_date = identity.split(" <", 1)
    email = email_and_date.split("> ", 1)[0]
    if not name or not email:
        raise NorenError("noren.yaml: author needs valid nonempty name and email strings.")
    return name, email


def send(repository, selected, blobs, identity, url, options, output):
    # Use source git configuration for authentication and URL rewrites, while all
    # new objects and index changes live in a disposable directory. The created
    # commit references only selected blobs and the destination's previous main.
    with TemporaryDirectory(prefix="noren-") as temporary:
        directory = Path(temporary)
        objects = directory / "objects"
        objects.mkdir()
        source_objects = repository.git("rev-parse", "--path-format=absolute", "--git-path", "objects").decode().strip()
        environment = os.environ.copy()
        environment["GIT_INDEX_FILE"] = str(directory / "index")
        environment["GIT_OBJECT_DIRECTORY"] = str(objects)
        alternates = [source_objects]
        if environment.get("GIT_ALTERNATE_OBJECT_DIRECTORIES"):
            alternates.append(environment["GIT_ALTERNATE_OBJECT_DIRECTORIES"])
        environment["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = os.pathsep.join(alternates)
        name, email = identity
        for role in ("AUTHOR", "COMMITTER"):
            environment[f"GIT_{role}_NAME"] = name
            environment[f"GIT_{role}_EMAIL"] = email
        previous = output["destination_main_before"]
        if previous is not None:
            repository.git(
                "fetch", "--no-tags", "--no-write-fetch-head", "--no-auto-maintenance",
                url, previous, env=environment,
            )
        repository.git("read-tree", "--empty", env=environment)
        index_records = []
        for entry in selected:
            oid = repository.git("hash-object", "-w", "--stdin", input=blobs[entry.path], env=environment).decode().strip()
            index_records.append(f"{entry.mode} {oid}\t{entry.path}\0".encode("utf-8", errors="surrogateescape"))
        repository.git("update-index", "--add", "-z", "--index-info", input=b"".join(index_records), env=environment)
        tree = repository.git("write-tree", env=environment).decode().strip()
        parents = ["-p", previous] if previous is not None else []
        output["commit"] = repository.git(
            "-c", "commit.gpgSign=false", "commit-tree", tree, *parents,
            input=(options.message if options.message.endswith("\n") else options.message + "\n").encode("utf-8"), env=environment,
        ).decode().strip()
        refspecs = [f"{output['commit']}:refs/heads/main"]
        if options.tag is not None:
            refspecs.append(f"{output['commit']}:refs/tags/{options.tag}")
        repository.git(
            "push", "--atomic", "--no-verify", "--no-follow-tags", url,
            *refspecs,
            env=environment,
        )
        output["pushed"] = True


def source_commit(repository, options):
    if options.tag is not None:
        repository.git("check-ref-format", f"refs/tags/{options.tag}")
        try:
            return repository.git("rev-parse", "--verify", f"refs/tags/{options.tag}^{{commit}}").decode().strip()
        except NorenError as error:
            raise NorenError(f"Source tag {options.tag} is missing or does not point to a commit.") from error
    if not re.fullmatch(r"[0-9a-fA-F]+", options.commit):
        raise NorenError("--commit requires a hexadecimal commit ID, not a branch, tag, or HEAD.")
    # Disambiguate object IDs directly so a hexadecimal ref name cannot override
    # the selected object. Do not peel annotated-tag objects into commits.
    candidates = repository.git("rev-parse", f"--disambiguate={options.commit.lower()}").decode().splitlines()
    if len(candidates) != 1 or repository.git("cat-file", "-t", candidates[0]).strip() != b"commit":
        raise NorenError(f"Source commit ID {options.commit} is missing, ambiguous, or does not identify a commit.")
    return candidates[0]


def publish(options, output):
    if (options.tag is None) == (options.commit is None):
        raise NorenError("Specify exactly one of --tag or --commit.")
    if options.tag == "":
        raise NorenError("--tag requires an existing source tag name.")
    if not options.message or not options.message.strip():
        raise NorenError("--message is required. Example: --message 'Release v1.0.0'.")
    repository = Repository.discover()
    commit = source_commit(repository, options)
    output["source_commit"] = commit
    entries = repository.entries(commit)
    config = settings(repository, entries, output)
    selected = choose_files(entries, config, output)
    blobs = inspect_content(repository, entries, selected, config)
    url = f"https://github.com/{config['destination']}.git"
    reject_source_destination(repository, config, url)
    identity = author(repository, config)
    output["author"] = {"name": identity[0], "email": identity[1]}
    remote_refs = {}
    refs = ["refs/heads/main"]
    if options.tag is not None:
        refs.append(f"refs/tags/{options.tag}")
    for line in repository.git("ls-remote", "--refs", url, *refs).decode().splitlines():
        oid, ref = line.split("\t", 1)
        remote_refs[ref] = oid
    output["destination_main_before"] = remote_refs.get("refs/heads/main")
    if options.initial and output["destination_main_before"] is not None:
        raise NorenError("--initial requires destination main to be absent.")
    if not options.initial and output["destination_main_before"] is None:
        raise NorenError("Destination main is absent; use --initial for the first publication.")
    if options.tag is not None and f"refs/tags/{options.tag}" in remote_refs:
        raise NorenError(f"Destination tag {options.tag} already exists; main and tag are unchanged.")
    if options.push:
        send(repository, selected, blobs, identity, url, options, output)
