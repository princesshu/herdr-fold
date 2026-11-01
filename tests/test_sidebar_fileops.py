"""Tests for the sidebar's file operations (src/plugins/sidebar/fileops.py) in a temporary root and home: new, rename
(never overwriting), the Trash (macOS and Windows through stand-ins), the path copied with a stand-in clipboard;
nothing outside the root, in an AI tool's folder or in a folder holding one is ever touched."""
import os
import shutil
import sys
import tempfile
import unittest

from support import SRC, set_env

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import fileops  # noqa: E402
from fileops import Ops, Refused  # noqa: E402


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_env(self, XDG_DATA_HOME=None)                    # the freedesktop Trash under the temporary home only
        self.home = os.path.join(self.tmp, "home")
        self.root = os.path.join(self.home, "projects", "app")
        os.makedirs(self.root)
        self.write("README.md")

    def write(self, rel, root=None):
        path = os.path.join(root or self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("x\n")
        return path

    def ops(self, system="darwin", **kwargs):
        return Ops(self.root, home=self.home, system=system, **kwargs)

    def test_new_files_and_folders_never_overwrite(self):
        ops = self.ops()
        made = ops.new_file(self.root, "notes.md")
        self.assertTrue(os.path.isfile(made))
        self.assertTrue(os.path.isdir(ops.new_folder(self.root, "docs")))
        with self.assertRaises(Refused):
            ops.new_file(self.root, "README.md")
        for bad in ("", "a/b", "..", "."):
            with self.assertRaises(Refused):
                ops.new_file(self.root, bad)

    def test_rename_never_overwrites(self):
        ops = self.ops()
        self.write("other.md")
        moved = ops.rename(os.path.join(self.root, "README.md"), "INTRO.md")
        self.assertTrue(os.path.isfile(moved))
        with self.assertRaises(Refused):
            ops.rename(moved, "other.md")

    def test_a_refusal_is_an_error_the_app_shows(self):
        self.assertTrue(issubclass(Refused, OSError))

    def test_the_macos_trash_through_its_system_call(self):
        trashed = []
        ops = self.ops("darwin", recycle=trashed.append)
        ops.trash(os.path.join(self.root, "README.md"))
        self.assertEqual(trashed, [os.path.join(self.root, "README.md")])

    @unittest.skipUnless(sys.platform == "darwin", "the macOS Trash call")
    def test_the_macos_call_refuses_what_is_not_there(self):
        missing = os.path.join(self.root, "not-there.txt")
        with self.assertRaises(OSError):
            fileops.mac_trash(missing)

    def test_the_recycle_bin_warns_before_deleting_for_good(self):
        allow_undo, want_nuke_warning = 0x40, 0x4000
        self.assertEqual(fileops.RECYCLE_FLAGS & (allow_undo | want_nuke_warning), allow_undo | want_nuke_warning)

    def test_the_freedesktop_trash(self):
        ops = self.ops("linux")
        where = ops.trash(os.path.join(self.root, "README.md"))
        trash = os.path.join(self.home, ".local", "share", "Trash")
        self.assertEqual(where, os.path.join(trash, "files", "README.md"))
        with open(os.path.join(trash, "info", "README.md.trashinfo")) as f:
            info = f.read()
        self.assertIn("[Trash Info]", info)
        self.assertIn("Path=" + os.path.join(self.root, "README.md").replace(" ", "%20"), info)
        self.assertIn("DeletionDate=", info)

    def test_the_windows_recycle_bin_through_its_shell_call(self):
        recycled = []
        ops = self.ops("win32", recycle=recycled.append)
        ops.trash(os.path.join(self.root, "README.md"))
        self.assertEqual(recycled, [os.path.join(self.root, "README.md")])

    def test_nothing_outside_the_root(self):
        ops = self.ops()
        outside = self.write("secret.txt", root=self.tmp)
        os.symlink(outside, os.path.join(self.root, "link.txt"))
        for path in (os.path.join(self.root, "..", "..", "secret.txt"), os.path.join(self.root, "link.txt")):
            with self.assertRaises(Refused):
                ops.trash(path)
        self.assertTrue(os.path.isfile(outside))

    def test_nothing_under_the_ai_tools_folders_even_from_home(self):
        ops = Ops(self.home, home=self.home, system="darwin")
        for rel in (".claude/projects/x/s1.jsonl", ".codex/sessions/r.jsonl",
                    ".local/state/herdr/plugins/herdr-fold.sessions-view/names.json"):
            path = self.write(rel, root=self.home)
            for action in (lambda: ops.trash(path), lambda: ops.rename(path, "y")):
                with self.assertRaises(Refused):
                    action()
            self.assertTrue(os.path.isfile(path))
        with self.assertRaises(Refused):
            ops.new_file(os.path.join(self.home, ".claude"), "x.md")

    def test_nor_a_folder_that_holds_one(self):
        ops = Ops(self.home, home=self.home, system="linux")
        self.write(".local/state/herdr/session.json", root=self.home)
        for rel in (".local", ".local/state"):
            for action in (lambda: ops.trash(os.path.join(self.home, rel)),
                           lambda: ops.rename(os.path.join(self.home, rel), "moved")):
                with self.assertRaises(Refused):
                    action()
        self.assertTrue(os.path.isfile(os.path.join(self.home, ".local/state/herdr/session.json")))
        self.assertTrue(os.path.isfile(ops.new_file(self.home, "notes.md")))      # the home itself still takes files
        ops.trash(os.path.join(self.home, "projects"))                              # a folder without one moves

    def test_the_path_goes_to_the_given_clipboard(self):
        copied = []
        ops = self.ops(clipboard=lambda text: copied.append(text) or True)
        self.assertTrue(ops.copy_path(os.path.join(self.root, "README.md")))
        self.assertEqual(copied, [os.path.join(self.root, "README.md")])


if __name__ == "__main__":
    unittest.main()
