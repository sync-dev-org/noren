"""Create editable setup templates without replacing existing files."""

import os

from noren.git import NorenError, Repository


def initialize() -> None:
    repository = Repository.discover()
    origin = repository.origin()
    name = origin.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1].removesuffix(".git")
    templates = {
        "noren.yaml": (
            "destination: ''\n"
            "include: ''\n"
            "exclude: |\n"
            "  noren.yaml\n"
            "  noren-words.txt\n"
            "word-list: noren-words.txt\n"
        ),
        "noren-words.txt": f"{origin}\n{name}\n",
    }
    for name in templates:
        if os.path.lexists(repository.root / name):
            raise NorenError(f"{name} already exists; setup will not overwrite it.")
    created = []
    try:
        for name, content in templates.items():
            path = repository.root / name
            with path.open("x", encoding="utf-8") as stream:
                created.append(path)
                stream.write(content)
    except OSError:
        for path in created:
            path.unlink()
        raise
    print(
        "Created noren.yaml and noren-words.txt.\n"
        "Edit noren.yaml to set destination, include, exclude, and word-list.\n"
        "Configure the required forbidden words in noren-words.txt before publishing.\n"
        "Commit these settings and create a tag, then run noren publish to check them."
    )
