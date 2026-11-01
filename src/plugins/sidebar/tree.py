"""The sidebar's file tree: folders first, then files, by name; links listed, not followed. A folder is read only when
open (an ignored or closed one is never walked), once until a reload or reopening; a very full one ends in … N more."""
import os
from dataclasses import dataclass


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

    def add(self, folder, depth, out):
        items = [item for item in self.entries(folder) if self.show_hidden or not item[0].startswith(".")]
        for name, is_dir in items[:self.limit]:
            path = os.path.join(folder, name)
            node = Node(path, name, is_dir, depth, is_dir and path in self.expanded)
            out.append(node)
            if node.expanded:
                self.add(path, depth + 1, out)
        if len(items) > self.limit:
            extra = len(items) - self.limit
            out.append(Node(None, f"… {extra} more", False, depth))

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
