"""Tests for core/tree.py, the file tree the TUI sidebar's Files and the Herdr app mod's share: the order, hidden and
ignored folders, "… N more", reloads; git's marks; and the command line the mod reads a folder through, on any
machine."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from support import PACKAGE, set_env

sys.path.insert(0, os.path.join(PACKAGE, "core"))
from git import Change, Status  # noqa: E402
from tree import Tree, git_marks  # noqa: E402

TREE = os.path.join(PACKAGE, "core", "tree.py")


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


class Marks(unittest.TestCase):
    def test_marks_for_a_huge_status_come_quickly(self):
        root = os.path.realpath(tempfile.gettempdir())
        many = Status(changes=[Change(f"fresh/f{i}.js", "?") for i in range(50_000)],
                      ignored={f"build/out{i}.js" for i in range(100_000)})
        started = time.process_time()                   # its own work only, however busy the machine is
        files, folders, ignored = git_marks(many, root, root)
        self.assertLess(time.process_time() - started, 0.5)
        self.assertEqual((len(files), folders[os.path.join(root, "fresh")], len(ignored)), (50_000, "?", 100_000))


class CommandLine(unittest.TestCase):
    """tree.py list ROOT [--hidden] FOLDER...: the folders the Herdr app mod shows, read on the space's machine."""

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="dev", GIT_AUTHOR_EMAIL="dev@example.com",
                GIT_COMMITTER_NAME="dev", GIT_COMMITTER_EMAIL="dev@example.com")
        for rel in ("a.txt", "src/b.py", ".gitignore", ".hidden"):
            make(self.root, rel)
        with open(os.path.join(self.root, ".gitignore"), "w") as f:
            f.write("build/\n")
        git = ["git", "-C", self.root]
        subprocess.run(git + ["init", "-q", "-b", "main"], check=True)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "init"], check=True)
        make(self.root, "build/out.js")
        make(self.root, "src/c.py")
        with open(os.path.join(self.root, "a.txt"), "a") as f:
            f.write("more\n")

    def list(self, *args, root=None):
        done = subprocess.run([sys.executable, "-B", TREE, "list", root or self.root, *args], capture_output=True,
                              text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)["folders"]

    def rows(self, folder):
        return [(e["name"], e["dir"], e["mark"], e["ignored"]) for e in folder["entries"]]

    def test_a_folder_lists_folders_first_with_gits_marks(self):
        self.assertEqual(self.rows(self.list("")[""]), [("build", True, None, True), ("src", True, "?", False),
                                                       ("a.txt", False, "M", False)])

    def test_hidden_files_on_request(self):
        names = [row[0] for row in self.rows(self.list("--hidden", "")[""])]
        self.assertEqual(names, [".git", "build", "src", ".gitignore", ".hidden", "a.txt"])   # as the TUI shows them

    def test_each_folder_read_alone_in_one_answer(self):
        folders = self.list("", "src")
        self.assertEqual(self.rows(folders["src"]), [("b.py", False, None, False), ("c.py", False, "?", False)])
        self.assertEqual(folders["src"]["more"], 0)

    def test_outside_a_repository_nothing_is_marked(self):
        plain = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, plain)
        make(plain, "x.txt")
        self.assertEqual(self.rows(self.list("", root=plain)[""]), [("x.txt", False, None, False)])

    def test_a_folder_outside_the_root_is_refused(self):
        done = subprocess.run([sys.executable, "-B", TREE, "list", os.path.join(self.root, "src"), ".."],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertEqual(done.stdout, "")
