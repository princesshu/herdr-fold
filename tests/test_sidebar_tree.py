"""Tests for the sidebar's file tree and change watching (tree.py, watch.py): the order, hidden and ignored folders,
"… N more", reloads; the watcher's changed folders and git changes, slowing down when idle, and git status timing."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import SRC, set_env

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
from tree import Tree  # noqa: E402
from watch import Watcher  # noqa: E402


def make(root, rel):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("x\n")


class Trees(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        for rel in ("b.txt", "A.txt", ".hidden", "src/b.py", "src/sub/c.py", "node_modules/x/y.js", "zdir/k.txt"):
            make(self.root, rel)
        self.scanned = []

    def scandir(self, path):
        self.scanned.append(os.path.relpath(path, self.root))
        return os.scandir(path)

    def names(self, tree):
        return [("  " * node.depth) + node.name for node in tree.rows()]

    def test_folders_first_then_files_hidden_ones_on_request(self):
        tree = Tree(self.root)
        self.assertEqual(self.names(tree), ["node_modules", "src", "zdir", "A.txt", "b.txt"])
        tree.set_hidden(True)
        self.assertIn(".hidden", self.names(tree))

    def test_a_folder_opens_with_its_depth_and_collapses(self):
        tree = Tree(self.root)
        tree.toggle(os.path.join(self.root, "src"))
        tree.toggle(os.path.join(self.root, "src", "sub"))
        self.assertEqual(self.names(tree)[1:5], ["src", "  sub", "    c.py", "  b.py"])
        tree.collapse_all()
        self.assertEqual(len(tree.rows()), 5)

    def test_an_ignored_folder_is_marked_and_not_walked(self):
        tree = Tree(self.root, ignored={"node_modules/"}, scandir=self.scandir)
        rows = tree.rows()
        modules = next(node for node in rows if node.name == "node_modules")
        self.assertTrue(tree.is_ignored(modules.path))
        self.assertTrue(tree.is_ignored(os.path.join(modules.path, "x", "y.js")))
        tree.toggle(os.path.join(self.root, "src"))
        tree.rows()
        self.assertNotIn("node_modules", self.scanned)
        self.assertEqual(sorted(set(self.scanned)), [".", "src"])

    def test_a_very_full_folder_ends_in_a_more_row(self):
        for i in range(5):
            make(self.root, f"many/f{i}.txt")
        tree = Tree(self.root, limit=3)
        tree.toggle(os.path.join(self.root, "many"))
        rows = [node.name for node in tree.rows() if node.depth == 1]
        self.assertEqual(rows, ["f0.txt", "f1.txt", "f2.txt", "… 2 more"])

    def test_a_folder_opened_again_is_read_again(self):
        tree = Tree(self.root)
        src = os.path.join(self.root, "src")
        tree.toggle(src)
        tree.rows()
        tree.toggle(src)                                          # closed: no longer watched
        make(self.root, "src/later.py")
        tree.toggle(src)
        self.assertIn("  later.py", self.names(tree))

    def test_a_reload_picks_up_new_files_and_survives_a_deleted_folder(self):
        tree = Tree(self.root)
        tree.toggle(os.path.join(self.root, "zdir"))
        tree.rows()
        make(self.root, "new.txt")
        shutil.rmtree(os.path.join(self.root, "zdir"))
        tree.reload()
        names = self.names(tree)
        self.assertIn("new.txt", names)
        self.assertNotIn("zdir", names)


class Watching(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.now = 0.0

    def clock(self):
        return self.now

    def test_a_new_file_changes_its_folder(self):
        watcher = Watcher(lambda: [self.root], None)
        self.assertEqual(watcher.poll(), set())
        make(self.root, "new.txt")
        os.utime(self.root, ns=(1, 1))                         # a different mtime, whatever the clock's resolution
        self.assertEqual(watcher.poll(), {self.root})

    def test_a_commit_changes_git(self):
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull)
        git = ["git", "-C", self.root, "-c", "user.name=dev", "-c", "user.email=dev@example.com"]
        subprocess.run(git + ["init", "-q"], check=True)
        make(self.root, "a.txt")
        watcher = Watcher(lambda: [], os.path.join(self.root, ".git"))
        watcher.poll()
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "one"], check=True)
        self.assertIn("git", watcher.poll())

    def test_the_pace_slows_when_nothing_happens(self):
        watcher = Watcher(lambda: [], None, clock=self.clock)
        watcher.touch()
        self.assertEqual(watcher.interval(), 1.0)
        self.now = 31
        self.assertEqual(watcher.interval(), 3.0)
        self.now = 400
        self.assertEqual(watcher.interval(), 10.0)

    def test_git_status_is_due_on_a_change_and_on_a_slow_beat(self):
        watcher = Watcher(lambda: [], None, clock=self.clock)
        self.assertTrue(watcher.status_due(changed=False, scm_shown=False))        # never run yet
        watcher.status_done(started=0.0, finished=0.05)
        self.now = 1
        self.assertFalse(watcher.status_due(changed=False, scm_shown=True))
        self.assertTrue(watcher.status_due(changed=True, scm_shown=False))
        self.now = 6
        self.assertTrue(watcher.status_due(changed=False, scm_shown=True))         # the 5 s beat
        self.assertFalse(watcher.status_due(changed=False, scm_shown=False))       # 15 s when not shown
        watcher.status_done(started=6, finished=7)                                 # a slow repository: 1 s
        self.now = 30
        self.assertFalse(watcher.status_due(changed=False, scm_shown=True))        # at least 50 × 1 s apart
        self.now = 57.5
        self.assertTrue(watcher.status_due(changed=False, scm_shown=True))


if __name__ == "__main__":
    unittest.main()
