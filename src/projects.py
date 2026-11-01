"""Where the folder picker starts: the folder holding the most git repositories under home (on Linux also /srv, /opt,
/var/www), searched for a moment at most; else ~/Documents or home. Only the user's and root's repositories count: on
a shared server, another user's never steer the picker."""
import collections
import os
import sys
import time

DEPTH = 4                       # folder levels below a root that are searched
BUDGET = 0.5                    # seconds the search may take: the picker opens right after it
ELSEWHERE = 8                   # repositories outside the start folder offered at the top
# Not searched: hidden folders, the ones macOS guards with a question of its own (Desktop, Downloads) or that hold no
# projects (Library, Applications, the media folders), and the bulky ones inside a project
SKIP = {"Applications", "Desktop", "Downloads", "Library", "Movies", "Music", "Pictures", "Public", "__pycache__",
        "build", "dist", "node_modules", "snap", "target", "vendor", "venv"}


def roots(platform=sys.platform):
    home = os.path.expanduser("~")
    return [home] + (["/srv", "/opt", "/var/www"] if platform.startswith("linux") else [])


def repositories(where=None, depth=DEPTH, budget=BUDGET):
    """The git repositories (a folder with .git) under WHERE (roots()), the nearest first; none is searched inside
    another, but a root is searched inside even when it is one (a home folder kept in git)."""
    found, level, end = [], [(root, 0) for root in where or roots() if os.path.isdir(root)], time.monotonic() + budget
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
            elif deep < depth:
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


def start(repos):
    """The folder holding the most of REPOS, the one nearer the root on a tie; without any, ~/Documents or home."""
    counts = collections.Counter(os.path.dirname(repo) for repo in repos)
    if counts:
        return min(counts, key=lambda folder: (-counts[folder], folder.count(os.sep), folder))
    documents = os.path.join(os.path.expanduser("~"), "Documents")
    return documents if os.path.isdir(documents) else os.path.expanduser("~")


def changed(repo):
    try:
        return os.stat(os.path.join(repo, ".git")).st_mtime
    except OSError:
        return 0


def elsewhere(repos, folder, count=ELSEWHERE):
    """REPOS not right in FOLDER, the most recently changed first (their .git), at most COUNT."""
    return sorted((repo for repo in repos if os.path.dirname(repo) != folder), key=changed, reverse=True)[:count]
