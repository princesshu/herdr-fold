"""Tests for the file operations (core/fileops.py: the TUI sidebar's and the app mod's) in a temporary root and home:
new, rename (never overwriting), the Trash (macOS and Windows through stand-ins), the path copied with a stand-in
clipboard; nothing outside the root, in an AI tool's folder or in a folder holding one is ever touched."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from support import PACKAGE, set_env

sys.path.insert(0, os.path.join(PACKAGE, "core"))
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


class ChatFiles(Files):
    """The one thing of an AI tool's the Trash takes: a chat's own file (Claude's with its sub-agents' folder beside
    it, Codex's rollout), by the Chats list's Delete…; anything else under their folders stays refused."""

    def setUp(self):
        super().setUp()
        self.trashed = []

    def chat(self, session="s1", folder="-work-app"):
        return self.write(f".claude/projects/{folder}/{session}.jsonl", root=self.home)

    def rollout(self, session="c1"):
        return self.write(f".codex/sessions/2026/10/26/rollout-2026-10-26T10-00-00-{session}.jsonl", root=self.home)

    def trash(self, kind, session, path, system="darwin"):
        return fileops.trash_chat(kind, session, path, home=self.home, system=system, recycle=self.trashed.append)

    def test_a_claude_chat_goes_with_its_sub_agents_folder(self):
        path, other = self.chat(), self.chat("s2")
        helper = self.write(".claude/projects/-work-app/s1/subagents/agent-a1.jsonl", root=self.home)
        self.assertEqual(self.trash("claude", "s1", path), "Trash")
        real = os.path.realpath(path)
        self.assertEqual(self.trashed, [real, os.path.join(os.path.dirname(real), "s1")])
        self.assertTrue(os.path.isfile(other) and os.path.isfile(helper))       # the stand-in moved nothing

    def test_a_codex_chat_is_its_rollout_file(self):
        path = self.rollout()
        self.trash("codex", "c1", path)
        self.assertEqual(self.trashed, [os.path.realpath(path)])

    def test_on_linux_it_lands_in_the_homes_trash(self):
        path = self.chat()
        where = self.trash("claude", "s1", path, system="linux")
        self.assertEqual(where, os.path.join(self.home, ".local", "share", "Trash", "files", "s1.jsonl"))
        self.assertTrue(os.path.isfile(where))
        self.assertFalse(os.path.exists(path))

    def test_nothing_but_a_chats_own_file(self):
        chat, rollout = self.chat(), self.rollout()
        refused = [("claude", "s2", chat),                                      # another chat's file
                   ("codex", "s1", chat), ("claude", "c1", rollout),            # the other agent's
                   ("codex", "c2", rollout),
                   ("claude", "s1", os.path.dirname(chat)),                     # a folder
                   ("claude", "s1", self.write(".claude/projects/-work-app/s1/subagents/s1.jsonl", root=self.home)),
                   ("claude", "s1", self.write(".claude/s1.jsonl", root=self.home)),
                   ("claude", "settings", self.write(".claude/settings.jsonl", root=self.home)),
                   ("claude", "s1", self.write("s1.jsonl")),                    # a project's file of that name
                   ("codex", "c1", self.write(".codex/sessions/rollout-c1.jsonl", root=self.home)),
                   ("codex", "c1", self.write(".codex/sessions/2026/10/26/c1.jsonl", root=self.home)),
                   ("claude", "../-work-app/s1", chat), ("claude", "*", chat), ("claude", "", chat),
                   ("gemini", "s1", chat),
                   ("claude", "gone", os.path.join(os.path.dirname(chat), "gone.jsonl"))]
        for kind, session, path in refused:
            with self.assertRaises(Refused, msg=(kind, session, path)):
                self.trash(kind, session, path)
        self.assertEqual(self.trashed, [])

    def test_a_linked_project_folder_gives_the_real_file_once(self):
        path = self.chat()
        linked = os.path.join(self.home, ".claude", "projects", "-work")
        os.symlink(os.path.dirname(path), linked)
        self.trash("claude", "s1", os.path.join(linked, "s1.jsonl"))
        self.assertEqual(self.trashed, [os.path.realpath(path)])

    def test_a_link_leading_out_of_the_chats_folder_is_refused(self):
        outside = self.write("kept/s1.jsonl", root=self.tmp)
        projects = os.path.join(self.home, ".claude", "projects")
        os.makedirs(projects)
        os.symlink(os.path.dirname(outside), os.path.join(projects, "-work-app"))        # a project's folder
        os.makedirs(os.path.join(projects, "-work-web"))
        os.symlink(outside, os.path.join(projects, "-work-web", "s1.jsonl"))             # a chat's file
        for folder in ("-work-app", "-work-web"):
            with self.assertRaises(Refused):
                self.trash("claude", "s1", os.path.join(projects, folder, "s1.jsonl"))
        self.assertEqual(self.trashed, [])

    def test_a_linked_sub_agents_folder_stays(self):
        path = self.chat()
        os.symlink(self.root, os.path.join(os.path.dirname(path), "s1"))
        self.trash("claude", "s1", path)
        self.assertEqual(self.trashed, [os.path.realpath(path)])

    def test_the_files_own_trash_still_refuses_a_chat(self):
        path = self.chat()
        with self.assertRaises(Refused):
            Ops(self.home, home=self.home, system="darwin", recycle=self.trashed.append).trash(path)
        self.assertEqual(self.trashed, [])


class CommandLine(Files):
    """The Herdr app mod's Files and Changes on the space's machine: python3 fileops.py trash, new-file, new-folder or
    rename, paths from ROOT, answering in JSON; the system's Trash through a stand-in, Linux's under the temporary
    home."""

    def cli(self, *args):
        trashed = os.path.join(self.tmp, "trashed")
        os.makedirs(trashed, exist_ok=True)
        stand_in = lambda path: shutil.move(path, trashed)                     # noqa: E731
        out = io.StringIO()
        with mock.patch.object(fileops, "mac_trash", stand_in), \
                mock.patch.object(fileops, "windows_recycle", stand_in), \
                mock.patch.dict(os.environ, {"HOME": self.home}), contextlib.redirect_stdout(out):
            code = fileops.main(["fileops.py", *args])
        return code, (json.loads(out.getvalue()) if out.getvalue() else None)

    def test_a_new_file_goes_to_the_trash(self):
        self.write("notes/new.txt")
        code, answer = self.cli("trash", self.root, "notes/new.txt")
        self.assertEqual((code, answer["ok"]), (0, True))
        self.assertFalse(os.path.exists(os.path.join(self.root, "notes", "new.txt")))

    def test_nothing_outside_the_root(self):
        self.write("kept.txt", root=self.home)
        for rel in ("../../kept.txt", os.path.join(self.home, "kept.txt")):
            code, answer = self.cli("trash", self.root, rel)
            self.assertEqual((code, answer["ok"]), (0, False))
            self.assertIn("outside", answer["advice"])
        self.assertTrue(os.path.exists(os.path.join(self.home, "kept.txt")))

    def test_a_new_file_and_a_new_folder_in_a_folder(self):
        self.write("notes/a.txt")
        self.assertEqual(self.cli("new-file", self.root, "notes", "b.txt"), (0, {"ok": True, "path": "notes/b.txt"}))
        self.assertEqual(self.cli("new-folder", self.root, "", "docs"), (0, {"ok": True, "path": "docs"}))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "notes", "b.txt")))
        self.assertTrue(os.path.isdir(os.path.join(self.root, "docs")))

    def test_a_rename_in_its_folder(self):
        self.write("notes/a.txt")
        self.assertEqual(self.cli("rename", self.root, "notes/a.txt", "c.txt"),
                         (0, {"ok": True, "path": "notes/c.txt"}))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "notes", "c.txt")))

    def test_a_name_taken_or_no_name_says_why(self):
        self.write("notes/a.txt")
        for args in (("new-file", self.root, "notes", "a.txt"), ("new-folder", self.root, "notes", "../x"),
                     ("rename", self.root, "notes/a.txt", ""), ("new-file", self.root, "..", "x.txt")):
            code, answer = self.cli(*args)
            self.assertEqual((code, answer["ok"]), (0, False), args)
            self.assertTrue(answer["advice"], args)

    def test_a_path_goes_on_the_clipboard_of_the_machine_it_runs_on(self):
        copied = []
        with mock.patch.object(fileops, "system_clipboard", lambda system: lambda text: copied.append(text) or True):
            self.assertEqual(self.cli("copy", "/work/lumen-api/src/a.py"), (0, {"ok": True}))
        self.assertEqual(copied, ["/work/lumen-api/src/a.py"])

    def test_anything_else_is_a_usage_error(self):
        self.assertEqual(self.cli("rename", self.root, "README.md"), (2, None))
        self.assertEqual(self.cli("trash", self.root), (2, None))


if __name__ == "__main__":
    unittest.main()
