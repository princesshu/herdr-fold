# Generated from core/tree.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""The file tree of the TUI sidebar's Files and the Herdr app mod's: folders first, then files, by name; links listed,
not followed; a folder read only when open (an ignored or closed one never walked); a very full one ends in … N more.
Usage: tree.py list ROOT [--hidden] [--limit N] FOLDER... (paths from ROOT, "" itself): each one's entries, as JSON."""
import json
import os
import sys
from dataclasses import dataclass

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import git  # noqa: E402

RANK = "UDARM?"               # the stronger change gives a file's, or a folder's, mark


def stronger(code, other):
    return other if code is None or RANK.index(other) < RANK.index(code) else code


def git_marks(status, repo, root):
    """Git's marks for the tree under ROOT, from a STATUS of the repository at REPO: (each changed file's mark, each
    folder's above one, the ignored paths from the root with a folder ending in "/"). The sidebar works them out on the
    status job's thread: a status of 50 000 untracked files must not stall the view."""
    marks, folders, ignored = {}, {}, set()
    for change in [*status.staged, *status.changes]:
        path = os.path.normpath(os.path.join(repo, change.path))
        marks[path] = stronger(marks.get(path), change.code)
    for path, code in marks.items():
        folder = os.path.dirname(path)
        while folder.startswith(root + os.sep):
            if folders.get(folder) == stronger(folders.get(folder), code):
                break                                   # this folder, and every one above it, has as strong a mark
            folders[folder] = code
            folder = os.path.dirname(folder)
    if os.path.normcase(repo) == os.path.normcase(root):
        return marks, folders, set(status.ignored)      # git's paths are the root's own
    for entry in status.ignored:
        try:
            rel = os.path.relpath(os.path.join(repo, entry), root).replace(os.sep, "/")
        except ValueError:                              # another drive (Windows)
            continue
        if rel != "." and not rel.startswith("../"):
            ignored.add(rel + "/" if entry.endswith("/") else rel)
    return marks, folders, ignored


@dataclass
class Node:
    path: str                 # None for a "… N more" row
    name: str
    is_dir: bool
    depth: int
    expanded: bool = False


class Tree:
    def __init__(self, root, ignored=(), show_hidden=False, limit=5000, scandir=os.scandir):
        self.root = os.path.abspath(root)
        self.ignored = set(ignored)
        self.show_hidden, self.limit, self.scandir = show_hidden, limit, scandir
        self.expanded, self.cache = set(), {}

    def read(self, folder):
        try:
            with self.scandir(folder) as entries:
                items = [(entry.name, entry.is_dir(follow_symlinks=False)) for entry in entries]
        except OSError:
            return []
        items.sort(key=lambda item: (not item[1], item[0].lower(), item[0]))
        return items

    def entries(self, folder):
        if folder not in self.cache:
            self.cache[folder] = self.read(folder)
        return self.cache[folder]

    def rows(self):
        out = []
        self.add(self.root, 0, out)
        return out

    def shown(self, folder):
        """FOLDER's entries as listed (hidden ones on request, at most the limit), and how many more there are."""
        items = [item for item in self.entries(folder) if self.show_hidden or not item[0].startswith(".")]
        return items[:self.limit], max(0, len(items) - self.limit)

    def add(self, folder, depth, out):
        items, more = self.shown(folder)
        for name, is_dir in items:
            path = os.path.join(folder, name)
            node = Node(path, name, is_dir, depth, is_dir and path in self.expanded)
            out.append(node)
            if node.expanded:
                self.add(path, depth + 1, out)
        if more:
            out.append(Node(None, f"… {more} more", False, depth))

    def toggle(self, path):
        if path in self.expanded:
            self.expanded.discard(path)
            return
        self.expanded.add(path)
        for folder in [f for f in self.cache if f == path or f.startswith(path + os.sep)]:
            del self.cache[folder]

    def collapse_all(self):
        self.expanded.clear()

    def set_hidden(self, show):
        self.show_hidden = show

    def set_ignored(self, ignored):
        self.ignored = set(ignored)

    def is_ignored(self, path):
        """Whether git ignores PATH, or a folder it is in (the ignored set holds paths from the root; folders end
        in "/")."""
        rel = os.path.relpath(path, self.root).replace(os.sep, "/")
        if rel in self.ignored:
            return True
        parts = rel.split("/")
        return any("/".join(parts[:i]) + "/" in self.ignored for i in range(1, len(parts) + 1))

    def reload(self, paths=None):
        """Read again the given folders (all, if none given); open folders that are gone are forgotten."""
        if paths is None:
            self.cache.clear()
        else:
            for path in paths:
                self.cache.pop(path, None)
        self.expanded = {path for path in self.expanded if os.path.isdir(path)}

    def expanded_dirs(self):
        return [self.root] + sorted(self.expanded)


def listing(root, folders, hidden=False, limit=5000):
    """FOLDERS (paths from ROOT, "" itself) as the Herdr app mod's Files shows them: each entry with git's mark (a
    folder's, its strongest change's) and whether git ignores it, and how many a very full one leaves out."""
    root = os.path.realpath(root)
    repo = git.top(root)
    marks, folder_marks, ignored = git_marks(git.status(repo), repo, root) if repo else ({}, {}, set())
    tree, answer = Tree(root, ignored, hidden, limit), {}
    for rel in folders:
        folder = os.path.realpath(os.path.join(root, rel))
        if folder != root and not folder.startswith(root + os.sep):
            raise ValueError(f"{rel}: not in {root}")
        items, more = tree.shown(folder)
        answer[rel] = {"more": more, "entries": [
            {"name": name, "dir": is_dir, "mark": (folder_marks if is_dir else marks).get(os.path.join(folder, name)),
             "ignored": tree.is_ignored(os.path.join(folder, name))} for name, is_dir in items]}
    return answer


def main(argv):
    args, options = argv[2:], {"hidden": False, "limit": 5000}
    if "--hidden" in args:
        args.remove("--hidden")
        options["hidden"] = True
    if "--limit" in args[:-1]:
        at = args.index("--limit")
        options["limit"] = int(args[at + 1]) if args[at + 1].isdigit() else 0
        del args[at:at + 2]
    if argv[1:2] != ["list"] or len(args) < 2 or not options["limit"]:
        print("usage: tree.py list ROOT [--hidden] [--limit N] FOLDER...", file=sys.stderr)
        return 2
    try:
        print(json.dumps({"folders": listing(args[0], args[1:], **options)}))
    except ValueError as err:
        print(err, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
