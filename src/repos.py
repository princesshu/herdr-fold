# Generated from core/repos.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""The git repositories under a folder, for the folder picker (where it starts) and the sidebar (the repositories of a
workspace that is none itself): searched level by level for a moment at most; only the user's and root's count, so on
a shared server another user's never show."""
import os
import time

BUDGET = 1.0                    # seconds a search may take
# Not searched: hidden folders, the ones macOS guards with a question of its own (Desktop, Downloads) or that hold no
# projects (Library, Applications, the media folders), and the bulky ones inside a project
SKIP = {"Applications", "Desktop", "Downloads", "Library", "Movies", "Music", "Pictures", "Public", "__pycache__",
        "build", "dist", "node_modules", "snap", "target", "vendor", "venv"}


def repositories(where, depth=None, budget=BUDGET):
    """The repositories (a folder with .git) under the folders WHERE, the nearest first, at most DEPTH levels down
    (None: any); none is searched inside another, but a folder of WHERE is searched inside even when it is one."""
    found, level, end = [], [(root, 0) for root in where if os.path.isdir(root)], time.monotonic() + budget
    while level:
        below = []
        for path, deep in level:
            if time.monotonic() >= end:
                return found
            try:
                entries = list(os.scandir(path))
            except OSError:
                continue
            if deep and any(entry.name == ".git" for entry in entries):
                if owned(path):
                    found.append(path)
            elif depth is None or deep < depth:
                below += [(entry.path, deep + 1) for entry in entries
                          if entry.is_dir(follow_symlinks=False) and not entry.name.startswith(".")
                          and entry.name not in SKIP]
        level = below
    return found


def owned(path):
    """True if PATH is the user's own or root's."""
    try:
        return os.stat(path).st_uid in (os.getuid(), 0)
    except OSError:
        return False
