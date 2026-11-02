"""Tests for open_file.py (Cmd+Shift+L): the files a pane's output names that are there, the newest first, with their
lines; the list as the folder picker's (filter while typing, mouse, Cancel and Open); Open shows the file at its line
in the sidebar's preview tab, laid out as the pane's tab, Files on the file."""
import fcntl
import json
import os
import pty
import select
import shutil
import struct
import subprocess
import tempfile
import termios
import time
import unittest

from support import ANSI, catalog_text, set_attrs

import open_file


class Root(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        for rel in ("src/app.py", "src/web/page.tsx", "README.md", "lib/db.rs"):
            os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
            with open(self.path(rel), "w") as f:
                f.write("x\n")
        os.makedirs(self.path(".git"))
        os.makedirs(self.path("src/sub"))

    def path(self, rel):
        return os.path.join(self.root, rel)


class Named(Root):
    def names(self, text, cwd=None):
        return [(os.path.relpath(found.path, self.root), found.line)
                for found in open_file.named(text, open_file.folders(cwd or self.root))]

    def test_a_path_with_its_line_as_tools_write_it(self):
        text = "src/app.py:42:7 failed\nsee src/web/page.tsx(12,5): error\nREADME.md#L3\nlib/db.rs:10-20"
        self.assertEqual(self.names(text), [("lib/db.rs", 10), ("README.md", 3), ("src/web/page.tsx", 12),
                                            ("src/app.py", 42)])

    def test_a_python_traceback_names_its_line(self):
        self.assertEqual(self.names('  File "src/app.py", line 9, in main'), [("src/app.py", 9)])

    def test_only_files_that_are_there(self):
        self.assertEqual(self.names("src/gone.py:3, the folder src/sub and the end. https://example.com/a.py"), [])

    def test_the_newest_first_each_once_a_bare_name_left_out_once_its_line_is_named(self):
        text = "Update(src/app.py)\nsrc/app.py:42\nREADME.md\nsrc/app.py:42"
        self.assertEqual(self.names(text), [("src/app.py", 42), ("README.md", None)])

    def test_quotes_brackets_and_a_sentence_end_around_it(self):
        text = "Edited `src/app.py`, (README.md) and lib/db.rs."
        self.assertEqual(self.names(text), [("lib/db.rs", None), ("README.md", None), ("src/app.py", None)])

    def test_relative_to_the_repository_from_a_subfolder_and_a_diffs_sides(self):
        self.assertEqual(self.names("src/app.py:1", cwd=self.path("src/web")), [("src/app.py", 1)])
        self.assertEqual(self.names("--- a/src/app.py\n+++ b/src/app.py"), [("src/app.py", None)])

    def test_an_absolute_path(self):
        self.assertEqual(self.names(f"wrote {self.path('lib/db.rs')}:7"), [("lib/db.rs", 7)])


class Picker(Root):
    def setUp(self):
        super().setUp()
        set_attrs(self, open_file, HOME=os.path.dirname(self.root), icons_on=lambda state_dir: False)
        self.picker = open_file.Picker([open_file.Found(self.path("src/app.py"), 42),
                                        open_file.Found(self.path("README.md"), None)], self.root)

    def lines(self, width=60):
        return ANSI.sub("", open_file.screen(self.picker, 10, width)).split("\n")

    def press(self, *keys):
        return [self.picker.press(key, 10) for key in keys][-1]

    def test_the_title_is_the_folder_each_file_under_it_with_its_line(self):
        lines = self.lines()
        self.assertEqual(lines[0].rstrip(), "~/" + os.path.basename(self.root))
        self.assertEqual([line.strip() for line in lines[2:4]], ["src/app.py:42", "README.md"])

    def test_typing_narrows_the_list_and_shows_what_was_typed(self):
        self.press("r", "e", "a")
        lines = self.lines()
        self.assertIn("rea", lines[1])
        self.assertEqual([line.strip() for line in lines[2:4]], ["README.md", ""])
        self.assertEqual(self.picker.chosen_file().path, self.path("README.md"))

    def test_enter_opens_the_chosen_one_esc_first_clears_what_was_typed_then_cancels(self):
        self.assertIsNone(self.press("\x1b[B"))
        self.assertEqual(self.press("\r"), "open")
        self.assertEqual(self.picker.chosen_file().path, self.path("README.md"))
        self.press("x")
        self.assertIsNone(self.press("\x1b"))
        self.assertEqual(self.picker.filt, "")
        self.assertEqual(self.press("\x1b"), "cancel")

    def test_a_click_chooses_a_second_one_at_once_opens_it_and_the_buttons(self):
        lines = self.lines()
        self.assertIsNone(self.picker.click((0, 5, 4, True), 10.0, 60, 10))
        self.assertEqual(self.picker.chosen_file().path, self.path("README.md"))
        self.assertEqual(self.picker.click((0, 5, 4, True), 10.3, 60, 10), "open")
        last = len(lines)
        self.assertEqual(self.picker.click((0, lines[-1].index("Cancel") + 1, last, True), 20.0, 60, 10), "cancel")
        self.assertEqual(self.picker.click((0, lines[-1].index("Open") + 1, last, True), 20.0, 60, 10), "open")
        self.picker.click((65, 1, 3, True), 30.0, 60, 10)
        self.assertEqual(self.picker.chosen, 1)

    def test_every_row_fits_the_width_with_the_icons_too(self):
        # a row one cell too wide wraps, and every click below it lands a row off
        set_attrs(self, open_file, icons_on=lambda state_dir: True)
        self.picker.files.append(open_file.Found(self.path("src/web/page.tsx"), 12))
        for width in (40, 60):
            self.assertLessEqual(max(len(line) for line in self.lines(width)), width, width)

    def test_the_wheel_on_an_empty_list_stays_on_the_top(self):
        self.press("z", "z")
        self.picker.click((65, 1, 3, True), 10.0, 60, 10)
        self.assertEqual(self.picker.chosen, 0)
        self.assertEqual(self.lines()[2].strip(), "")

    def test_the_buttons_and_no_line_of_keys(self):
        self.assertTrue(self.lines()[-1].rstrip().endswith("Cancel    Open"), self.lines()[-1])
        self.assertEqual(self.lines()[-1].split("Cancel")[0].strip(), "")

    def test_no_file_named_says_so_and_offers_only_cancel(self):
        self.picker = open_file.Picker([], self.root)
        lines = self.lines()
        self.assertIn(catalog_text("named.none"), lines[2])
        self.assertTrue(lines[-1].rstrip().endswith("Cancel"))
        self.assertNotIn("Open", lines[-1])
        self.assertEqual(self.press("\r"), None)

    def test_a_file_name_cannot_send_terminal_codes(self):
        name = "\x1b]52;c;ZWNobyBoaQ==\x07app.py"
        with open(self.path(name), "w") as f:
            f.write("x\n")
        self.picker = open_file.Picker([open_file.Found(self.path(name), 1)], self.root)
        shown = open_file.screen(self.picker, 10, 60)
        self.assertNotIn("\x1b]", shown)
        self.assertIn("?]52;c;ZWNobyBoaQ==?app.py:1", shown)


class Open(Root):
    def test_the_file_shows_at_its_line_in_the_preview_tab_laid_out_as_the_panes_and_files_on_it(self):
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state)
        opened, brought = [], []

        class Herdr:
            def call(self, *args):
                if args[:2] == ("pane", "get"):
                    return {"pane": {"pane_id": "w1:p1", "workspace_id": "w1", "tab_id": "w1:t1"}}
                if args[:2] == ("pane", "list"):
                    return {"panes": [{"pane_id": "w1:p1", "tab_id": "w1:t1", "label": "claude"},
                                      {"pane_id": "w1:p2", "tab_id": "w1:t1", "label": "sidebar"}]}
                return {}

        def open_preview(herdr, workspace, root, spec, state_dir, lay_out=None, here=None):
            opened.append((workspace, root, spec["title"], spec["line"], state_dir, here))
            lay_out("w1:t5")
        set_attrs(self, open_file.preview, open_preview=open_preview)
        set_attrs(self, open_file.conversations_pane, bring=lambda call, tab, kinds, state_dir: brought.append(
            (tab, set(kinds), state_dir)))
        open_file.open_found(Herdr(), open_file.Found(self.path("src/web/page.tsx"), 12), self.root, "w1:p1", state)
        self.assertEqual(opened, [("w1", self.root, os.path.join("src", "web", "page.tsx"), 12, state, "w1:t1")])
        self.assertEqual(brought, [("w1:t5", {"sidebar"}, state)])
        with open(open_file.preview.seed_file(state, "w1:t5")) as f:
            seed = json.load(f)
        self.assertEqual(seed, {"view": "files", "selected": self.path("src/web/page.tsx"),
                                "expanded": [self.path("src"), self.path("src/web")]})


FAKE_HERDR = r'''#!/usr/bin/python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps(args) + "\n")
if args[:2] == ["pane", "read"]:
    print("⏺ Update(README.md)\n  ⎿  README.md changed; the call is in src/app.py:42")
    sys.exit(0)
answers = {("pane", "get"): {"pane": {"pane_id": "w1:p1", "workspace_id": "w1", "tab_id": "w1:t1"}},
           ("pane", "list"): {"panes": [{"pane_id": "w1:p1", "tab_id": "w1:t1", "label": "claude"}]},
           ("tab", "list"): {"tabs": []},
           ("tab", "create"): {"tab": {"tab_id": "w1:t5"}, "root_pane": {"pane_id": "w1:p9"}}}
print(json.dumps({"result": answers.get(tuple(args[:2]), {})}))
'''


class Popup(Root):
    """The popup in a terminal, herdr a stand-in: it reads the focused pane, lists what it names, and Enter opens the
    newest at its line in a new preview tab."""

    def test_enter_opens_the_newest_file_named_at_its_line(self):
        home = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home)
        fake, log = os.path.join(home, "herdr"), os.path.join(home, "calls.jsonl")
        with open(fake, "w") as f:
            f.write(FAKE_HERDR)
        os.chmod(fake, 0o755)
        env = {"HOME": home, "PATH": "/usr/bin:/bin", "TERM": "xterm-256color", "HERDR_BIN_PATH": fake,
               "FAKE_LOG": log, "HERDR_ACTIVE_PANE_ID": "w1:p1", "HERDR_ACTIVE_PANE_CWD": self.root,
               "PYTHONDONTWRITEBYTECODE": "1"}
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        proc = subprocess.Popen(["/usr/bin/python3", "-B", open_file.__file__], stdin=slave, stdout=slave,
                                stderr=slave, env=env, start_new_session=True)
        os.close(slave)
        out, sent, deadline = b"", False, time.monotonic() + 30
        while time.monotonic() < deadline and proc.poll() is None:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    out += os.read(master, 65536)
                except OSError:
                    break
            if not sent and b"README.md" in out:              # both rows drawn, the newest chosen
                time.sleep(0.3)
                os.write(master, b"\r")
                sent = True
        proc.wait(10)
        os.close(master)
        self.assertTrue(sent, out.decode("utf-8", "replace"))
        with open(log) as f:
            calls = [json.loads(one) for one in f]
        self.assertIn(["pane", "read", "w1:p1", "--source", "recent-unwrapped", "--lines", str(open_file.LINES)],
                      calls)
        created = next(call for call in calls if call[:2] == ["tab", "create"])
        self.assertEqual(created[2:7], ["--workspace", "w1", "--cwd", self.root, "--label"])
        state = os.path.join(home, ".local", "state", "herdr", "plugins", "herdr-fold.sidebar")
        with open(open_file.preview.spec_file(state, "w1")) as f:
            spec = json.load(f)
        self.assertEqual((spec["title"], spec["line"]), (os.path.join("src", "app.py"), 42))
        with open(open_file.preview.seed_file(state, "w1:t5")) as f:
            self.assertEqual(json.load(f)["selected"], self.path("src/app.py"))
        self.assertIn(["pane", "rename", "w1:p9", "preview"], calls)


if __name__ == "__main__":
    unittest.main()
