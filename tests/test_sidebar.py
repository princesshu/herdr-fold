"""Tests for the sidebar app (src/plugins/sidebar/sidebar.py) and its herdr actions (actions.py) in a temporary repo
with a stand-in herdr: views, search, previews, live updates, settings and a hanging AI with a stand-in terminal;
in a real pty, q or Ctrl+C gives the terminal back at once."""
import json
import os
import pty
import re
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from unittest import mock

from support import (SRC, AppScreen, FakeHerdrSocket, FakeTerminal, at_once, end_child, end_jobs, logged, set_env,
                     stubs, text)

PLUGIN = os.path.join(SRC, "plugins", "sidebar")
sys.path.insert(0, PLUGIN)
import actions  # noqa: E402
import changes_panel  # noqa: E402
import column  # noqa: E402
import commit_message  # noqa: E402
import loop  # noqa: E402
import panels  # noqa: E402
import preview  # noqa: E402
import screen  # noqa: E402
import sidebar  # noqa: E402
from conversations import Conversation  # noqa: E402
from git import Status  # noqa: E402
from icons import glyphs  # noqa: E402
from vt import Focus, Key, Mouse, Resize  # noqa: E402
from widgets import Action  # noqa: E402

FAKE_HERDR = """#!/bin/sh
printf '%s\\n' "$*" >> "$HERDR_LOG"
case "$1 $2" in
  "tab list") echo '{"result": {"tabs": []}}' ;;
  "tab create") echo '{"result": {"tab": {"tab_id": "w1:t3"}, "root_pane": {"pane_id": "w1:p9"}}}' ;;
  "pane list") echo '{"result": {"panes": [{"pane_id": "w1:p1", "tab_id": "w1:t1", "label": "agent"},'\\
                    '{"pane_id": "w1:p2", "tab_id": "w1:t1", "label": "sidebar"},'\\
                    '{"pane_id": "w1:p5", "tab_id": "w1:t2", "label": "sidebar"}]}}' ;;
  "pane get") echo '{"result": {"pane": {"pane_id": "w1:p2", "tab_id": "w1:t1"}}}' ;;
  "agent list") echo '{"result": {"agents": [{"pane_id": "w1:p7", "tab_id": "w1:t2", "agent": "codex"},'\\
                     '{"pane_id": "w1:p1", "tab_id": "w1:t1", "agent": "claude"}]}}' ;;
  "tab close"|"pane run"|"pane rename"|"pane send-keys"|"pane send-text"|"agent focus") echo '{"result": {}}' ;;
  *) echo "no such command" >&2; exit 2 ;;
esac
"""
HANGING_AI = "#!/bin/sh\nsleep 30\n"
# the GitHub CLI: its arguments to $GH_LOG; issue list answers with $GH_ISSUES, by default one issue; anything else
# with nothing
FAKE_GH = """#!/bin/sh
printf '%s\\n' "$*" >> "$GH_LOG"
case "$1 $2" in
  "issue list") if [ -n "$GH_ISSUES" ]; then printf '%s' "$GH_ISSUES"; exit 0; fi
                printf '%s' '[{"number": 42, "title": "Login fails on Safari", "state": "OPEN", "labels": [],'\\
                            ' "assignees": [], "updatedAt": "2026-10-22T10:00:00Z",'\\
                            ' "url": "https://github.com/acme/app/issues/42"}]' ;;
esac
"""
# gh's answer once a second issue is made on GitHub
TWO_ISSUES = json.dumps([{"number": number, "title": title, "state": "OPEN", "labels": [], "assignees": [],
                          "updatedAt": updated, "url": f"https://github.com/acme/app/issues/{number}"}
                         for number, title, updated in ((43, "Search skips hidden files", "2026-10-23T09:00:00Z"),
                                                        (42, "Login fails on Safari", "2026-10-22T10:00:00Z"))])
SLOW_AI = "#!/bin/sh\nsleep 1.5\nprintf 'feat: from the ai\\n'\n"


ROW = sidebar.stack.ROW       # the tab row's


def keys(text):
    return [Key("char", ch) for ch in text]


class Repo(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.root, self.state = os.path.join(tmp, "project"), os.path.join(tmp, "state")
        self.log = os.path.join(tmp, "herdr.log")
        self.bin = stubs(os.path.join(tmp, "bin"), {"herdr": FAKE_HERDR, "claude": HANGING_AI})
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="dev", GIT_AUTHOR_EMAIL="dev@example.com",
                GIT_COMMITTER_NAME="dev", GIT_COMMITTER_EMAIL="dev@example.com", HERDR_LOG=self.log,
                HERDR_WORKSPACE_ID="w1", HERDR_BIN_PATH=os.path.join(self.bin, "herdr"), HERDR_COMMIT_AI="claude",
                PATH=self.bin + os.pathsep + os.environ["PATH"], HERDR_PLUGIN_STATE_DIR=self.state,
                HOME=os.path.join(tmp, "home"))                # never the user's conversations or commit rules
        os.makedirs(os.path.join(self.root, "src"))
        for rel, body in (("a.txt", "a needle here\n"), ("src/b.py", "print('b')\n"), (".hidden", "x\n")):
            self.write(rel, body)
        git = ["git", "-C", self.root]
        subprocess.run(git + ["init", "-q", "-b", "main"], check=True)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "init"], check=True)
        self.write("a.txt", "a needle here\nand more\n")
        self.write("new.txt", "new\n")

    def write(self, rel, body):
        with open(os.path.join(self.root, rel), "w") as f:
            f.write(body)


class Harness(AppScreen, Repo):
    """The app on its own thread with the stand-in terminal, and ways to wait for what it shows."""

    def start(self, cols=column.FEWEST, rows=45):
        term = FakeTerminal(cols, rows)
        self.run_app(sidebar.App(self.root, term, preview.Herdr(), self.state), term)

    def row(self, part):
        return next((line for line in self.screen().splitlines() if part in line), "")

    def body(self, screen):
        """SCREEN under the tab row: the panel shown."""
        return "\n".join(screen.split("\n")[sidebar.stack.TOP:])


class Running(Harness):
    def setUp(self):
        super().setUp()
        self.start()

    def test_it_starts_on_the_files(self):
        self.until(lambda s: "project" in s and "a.txt" in s)
        self.assertNotIn(".hidden", self.screen())
        self.until(lambda s: self.row("a.txt").rstrip().endswith("M"))   # the temporary folder is behind a symlink

    def test_the_tab_row_names_the_panels_in_their_groups_the_shown_one_in_the_accent(self):
        self.until(lambda s: "project" in s and "Changes 2" in s)              # a.txt changed, new.txt new
        canvas, row = self.app.canvas, text(self.app.canvas, sidebar.stack.ROW)
        self.assertEqual(row[:36], " Chats     Files  Search   Changes 2")
        self.assertEqual(row[36:].split(), ["»", "⋯"])                         # the dock's own, at the row's end
        look = [canvas.rows[sidebar.stack.ROW][row.index(part)][1] for part in ("Chats", "Files", "Search", "2")]
        self.assertEqual([(style.fg, style.bold) for style in look],
                         [("muted", False), ("accent", True), ("muted", False), ("modified", False)])
        self.assertNotIn("badge", {style.bg for _, style in canvas.rows[-1]})

    def test_a_blank_row_above_and_below_the_tab_row_then_the_panel_full_height(self):
        self.until(lambda s: "project" in s)
        rows = self.screen().split("\n")
        self.assertEqual([rows[0].strip(), rows[2].strip()], ["", ""])
        self.assertIn("project", rows[sidebar.stack.TOP])                        # Files' folder, its tree under it
        self.assertNotEqual(rows[sidebar.stack.TOP + 1].strip(), "")
        self.assertEqual(self.app.body, (sidebar.stack.TOP, 45 - sidebar.stack.TOP))

    def test_a_tab_under_the_mouse_lights_up_and_a_click_shows_its_panel(self):
        self.until(lambda s: "project" in s and "Changes 2" in s)
        x = text(self.app.canvas, sidebar.stack.ROW).index("Changes")
        self.assertEqual(self.app.canvas.rows[sidebar.stack.ROW][x][1].fg, "muted")
        self.term.type(Mouse("move", x, sidebar.stack.ROW, 3))
        self.until(lambda s: self.app.canvas.rows[sidebar.stack.ROW][x][1].fg == "text")
        self.term.type(Mouse("press", x, sidebar.stack.ROW, 0))
        self.until(lambda s: self.app.shown() == "changes" and "new.txt" in self.body(s))
        self.assertEqual(self.app.canvas.rows[sidebar.stack.ROW][x][1], screen.Style(fg="accent", bold=True))
        with open(os.path.join(self.state, "dock.json")) as f:
            self.assertEqual(json.load(f)[os.path.realpath(self.root)], {"shown": "changes"})
        self.stop()
        self.start()                                                      # the folder keeps it
        self.until(lambda s: "new.txt" in self.body(s) and self.app.shown() == "changes")

    def test_each_panel_has_its_number_key_in_the_rows_order(self):
        self.until(lambda s: "a.txt" in s)
        for key, panel in (("4", "changes"), ("2", "files"), ("1", "conversations")):
            self.term.type(Key("char", key))
            self.until(lambda s: self.app.shown() == panel)
        self.term.type(Key("char", "2"))                                  # Chats' filter takes every character
        self.until(lambda s: self.app.views["conversations"].typed == "2")
        self.term.type(Key("f9"), Key("char", "3"))
        self.until(lambda s: self.app.shown() == "search")

    def test_a_panels_controls_are_tall_where_the_pane_has_the_rows(self):
        self.stop()
        for rows in (18, 19):                                             # the panel 15 rows high, then 16
            with self.subTest(rows=rows):
                self.start(rows=rows)
                self.term.type(Key("f10"))
                self.until(lambda s: self.app.shown() == "search" and "Search" in s)
                field = any(ch == "▄" and style.fg == "input" for row in self.app.canvas.rows for ch, style in row)
                self.assertEqual(field, rows - sidebar.stack.TOP >= screen.ROOMY)
                self.stop()

    def test_a_key_reaches_the_panel_shown_only(self):
        self.until(lambda s: "a.txt" in s)
        self.term.type(Key("f11"), Key("char", "."))                         # Changes has the keys: Files' hidden stay
        time.sleep(0.3)
        self.assertFalse(self.app.settings["hidden"])
        self.term.type(Key("f9"), Key("char", "."))
        self.until(lambda s: ".hidden" in s)

    def test_a_name_in_use_is_a_line_not_a_crash(self):
        self.until(lambda s: "src" in s)
        self.term.type(Key("char", "n"), *keys("b.py"), Key("enter"))       # src is chosen, src/b.py is there
        self.until(lambda s: "already there: b.py" in s)
        self.assertTrue(self.thread.is_alive())

    def test_a_message_typed_while_the_ai_writes_is_kept_and_commits(self):
        with open(os.path.join(self.bin, "claude"), "w") as f:
            f.write(SLOW_AI)
        subprocess.run(["git", "-C", self.root, "add", "a.txt"], check=True)
        self.term.type(Key("char", "4"))
        self.until(lambda s: "Staged changes" in s)
        self.term.type(Key("char", "A"))
        self.until(lambda s: "Claude is writing the message" in s)
        self.term.type(Key("char", "c"), *keys("fix: mine"), Key("esc"), Key("enter"))
        self.until(lambda s: "suggest" not in self.app.running and "commit" not in self.app.running, timeout=8)
        time.sleep(0.3)                                                     # the frame after the answers
        log = subprocess.run(["git", "-C", self.root, "log", "--format=%s"], capture_output=True, text=True).stdout
        self.assertEqual(log.split("\n")[0], "fix: mine")
        self.assertNotIn("from the ai", self.screen())

    def test_an_untracked_file_previews_as_the_file(self):
        self.term.type(Key("char", "4"))
        self.until(lambda s: "new.txt" in self.body(s))
        rows = self.screen().splitlines()
        y = next(i for i, row in enumerate(rows) if i >= sidebar.stack.TOP and "new.txt" in row)
        self.term.type(Mouse("press", rows[y].index("new.txt"), y, 0))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not any(line.startswith("pane run") for line in logged(self.log)):
            time.sleep(0.05)
        create = next(line for line in logged(self.log) if line.startswith("tab create"))
        with open(create.split("HERDR_FOLD_SPEC_FILE=")[1].split()[0]) as f:
            spec = json.load(f)
        self.assertTrue(json.dumps(spec).count("new.txt"))
        self.assertFalse(any("diff" in argv for argv in spec["pipeline"]))

    def test_search_after_a_pause(self):
        self.term.type(Key("char", "3"), *keys("needle"))
        self.until(lambda s: "1 result in 1 file" in s and "a needle here" in s)

    def test_search_covers_the_folder_or_file_you_chose_in_files(self):
        # the first row is chosen by itself and narrows nothing (test_search_after_a_pause)
        self.until(lambda s: "src" in s)
        self.term.type(Key("down"), Key("up"), Key("char", "3"), *keys("needle"))     # src, chosen by you
        self.until(lambda s: "in src" in s and "No results found" in s)
        self.term.type(Key("f9"), Key("down"), Key("f10"))                            # a.txt: that file alone
        self.until(lambda s: "in a.txt" in s and "1 result in 1 file" in s)
        self.term.type(Key("f9"), Key("down"), Key("f10"))                            # new.txt
        self.until(lambda s: "in new.txt" in s and "No results found" in s)
        self.term.type(Key("f9"), Key("up"), Key("up"), Key("f10"))
        self.until(lambda s: "in src" in s and "No results found" in s)
        self.term.type(Key("esc"))                                                    # the text and the folder
        self.until(lambda s: "in src" not in s and "needle" not in s)

    def test_the_changes_view_shows_the_changes(self):
        self.term.type(Key("char", "4"))
        self.until(lambda s: "Changes" in s and "new.txt" in s and "a.txt" in s)
        self.until(lambda s: "init" in s)                                   # the graph

    def test_a_click_opens_the_preview_tab(self):
        self.until(lambda s: "a.txt" in s)
        rows = self.screen().splitlines()
        y = next(i for i, row in enumerate(rows) if "a.txt" in row)
        self.term.type(Mouse("press", rows[y].index("a.txt"), y, 0))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not any(line.startswith("pane run") for line in logged(self.log)):
            time.sleep(0.05)
        calls = logged(self.log)
        root = os.path.realpath(self.root)
        create = next(line for line in calls if line.startswith("tab create"))
        self.assertTrue(create.startswith(f"tab create --workspace w1 --cwd {root} --label preview: a.txt --env "),
                        create)
        self.assertIn("pager.py", create)                                     # in the tab's environment
        self.assertIn('pane run w1:p9 "$HERDR_FOLD_PYTHON" -B "$HERDR_FOLD_PAGER" && exit', calls)

    def test_a_new_file_shows_up_on_its_own(self):
        self.until(lambda s: "a.txt" in s)
        self.write("later.txt", "x\n")
        self.until(lambda s: "later.txt" in s, timeout=2.5)

    def test_a_hanging_ai_does_not_hang_the_view(self):
        with mock.patch.dict(commit_message.TIMEOUTS, {"claude": 1.5, "codex": 1.5}):
            self.term.type(Key("char", "4"))
            self.until(lambda s: "a.txt" in self.body(s) and "new.txt" in self.body(s))   # the status read
            self.term.type(Key("char", "A"))                                 # nothing staged: it all goes in
            self.until(lambda s: "is writing the message" in s)
            self.term.type(Key("char", "2"))
            self.until(lambda s: "project" in s, timeout=1.0)                # the view answers meanwhile
            self.until(lambda s: "claude failed" in s, timeout=15)          # however busy the machine

    def test_a_commit_with_nothing_staged_takes_every_change(self):
        self.term.type(Key("char", "4"))
        self.until(lambda s: "a.txt" in self.body(s) and "new.txt" in self.body(s))
        self.term.type(*keys("feat: all of it"), Key("enter", alt=True))
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and "feat: all of it" not in subprocess.run(
                ["git", "-C", self.root, "log", "-1", "--format=%s"], capture_output=True, text=True).stdout:
            time.sleep(0.1)
        shown = subprocess.run(["git", "-C", self.root, "show", "--name-only", "--format=%s", "HEAD"],
                               capture_output=True, text=True).stdout.split()
        self.assertEqual(shown[:4], ["feat:", "all", "of", "it"])
        self.assertEqual(sorted(shown[4:]), ["a.txt", "new.txt"])

    def test_the_hidden_files_setting_is_kept(self):
        self.until(lambda s: "a.txt" in s)
        self.term.type(Key("char", "."))
        self.until(lambda s: ".hidden" in s)
        self.stop()
        with open(os.path.join(self.state, "settings.json")) as f:
            self.assertTrue(json.load(f)["hidden"])
        self.start()
        self.until(lambda s: ".hidden" in s)

    def test_a_new_theme_shows_without_a_restart(self):
        self.until(lambda s: "a.txt" in s)
        os.makedirs(self.state, exist_ok=True)
        with open(os.path.join(self.state, "colors.json"), "w") as f:
            json.dump({"accent": "#123456"}, f)
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline and self.app.renderer.theme.colors.get("accent") != "#123456":
            time.sleep(0.05)
        self.assertEqual(self.app.renderer.theme.colors.get("accent"), "#123456")

    def test_f9_to_f11_switch_even_while_typing(self):
        self.term.type(Key("char", "3"), *keys("q1"))
        self.until(lambda s: "q1" in s)                                      # q and 1 went into the field
        self.term.type(Key("f11"))
        self.until(lambda s: self.app.shown() == "changes")
        self.term.type(Key("f9"))
        self.until(lambda s: self.app.showing("files"))

    def test_q_quits_on_the_files(self):
        self.until(lambda s: "a.txt" in s)
        self.term.type(Key("char", "q"))
        self.thread.join(3)
        self.assertFalse(self.thread.is_alive())


class Tips(Harness):
    """A control shown by an icon alone tells what it does once the mouse rests on it."""

    def setUp(self):
        Repo.setUp(self)
        self.start()

    def region(self, match):
        """Where the first region whose target MATCH accepts is, once it is drawn."""
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            found = next(((x0, y) for y, x0, _, target in list(self.app.canvas.regions) if match(target)), None)
            if found:
                return found
            time.sleep(0.05)
        self.fail(f"no such region:\n{self.screen()}")

    def test_an_icons_tip_shows_once_the_mouse_rests_on_it_and_a_key_hides_it(self):
        self.term.type(Key("char", "4"))
        self.until(lambda s: "a.txt" in s)
        self.term.type(Mouse("move", *self.region(lambda target: target == "suggest")))
        self.until(lambda s: " Write message " in s, timeout=3)
        self.term.type(Key("char", "x", ctrl=True))
        self.until(lambda s: "Write message" not in s)

    def test_a_files_icons_tell_what_they_do(self):
        self.term.type(Key("char", "4"))
        self.until(lambda s: "a.txt" in s)
        self.term.type(Mouse("move", *self.changed_row("a.txt")))
        self.term.type(Mouse("move", *self.region(lambda target: isinstance(target, tuple) and target[0] == "stage")))
        self.until(lambda s: " Stage " in s, timeout=3)

    def changed_row(self, name):
        """Where the Changes row of the file NAME starts, once it is drawn."""
        self.until(lambda s: name in self.body(s))
        y = next(y for y, line in enumerate(self.screen().splitlines()) if y >= sidebar.stack.TOP and name in line)
        return next((x0, ry) for ry, x0, _, target in list(self.app.canvas.regions)
                    if ry == y and isinstance(target, tuple) and target[0] == "row")

    def test_a_changed_files_tip_is_its_whole_path_in_the_repository(self):
        self.write("src/b.py", "print('b, changed')\n")
        self.term.type(Key("char", "4"))
        self.term.type(Mouse("move", *self.changed_row("b.py")))
        self.until(lambda s: " src/b.py " in s, timeout=3)

    def test_a_name_files_cuts_short_shows_whole_under_the_mouse(self):
        name = "documents/the-release-checklist-for-every-version.md"      # its name cut in its row, whole in a tip
        os.makedirs(os.path.join(self.root, "documents"))
        self.write(name, "x\n")
        self.term.type(Key("char", "2"))
        self.until(lambda s: "documents" in s)
        self.term.type(Mouse("press", *self.region(lambda target: isinstance(target, tuple) and target[0] == "row"
                                                   and "documents" in self.row_text(target))))
        self.until(lambda s: "the-release" in s)
        self.term.type(Mouse("move", *self.region(lambda target: isinstance(target, tuple) and target[0] == "row"
                                                  and "the-release" in self.row_text(target))))
        self.until(lambda s: " documents/" in s and " the-release-checklist-for-every-version.md " in s, timeout=3)

    def row_text(self, target):
        """The text of the row TARGET's region is on."""
        y = next(ry for ry, _x0, _x1, at in list(self.app.canvas.regions) if at == target)
        return self.screen().splitlines()[y]

    def test_a_path_wider_than_the_pane_shows_whole_broken_after_its_slashes(self):
        rel = "src/a-rather-long-folder-name/and-another-one/the-file.txt"
        os.makedirs(os.path.join(self.root, os.path.dirname(rel)))
        self.write(rel, "x\n")
        subprocess.run(["git", "-C", self.root, "add", rel], check=True)
        subprocess.run(["git", "-C", self.root, "commit", "-q", "-m", "deep"], check=True)
        self.write(rel, "x, changed\n")
        self.term.type(Key("char", "4"))
        self.term.type(Mouse("move", *self.changed_row("the-file.txt")))
        self.until(lambda s: " src/a-rather-long-folder-name/and-another-one/ " in s
                   and " the-file.txt " in s, timeout=3)


class Message(Harness):
    """The commit message's field takes the mouse and the keys a text field does: a drag or Shift selects, and
    Backspace takes the selection whole."""

    def setUp(self):
        Repo.setUp(self)
        self.start()

    def typed(self, text):
        """TEXT typed as the message, once Changes shows: where its first line starts in the field."""
        self.term.type(Key("char", "4"))
        self.until(lambda s: "a.txt" in self.body(s))
        self.term.type(*keys(text))
        first, last = text.split("\n")[0], text.split("\n")[-1]
        self.until(lambda s: first in s and last in s)
        y = next(y for y, line in enumerate(self.screen().splitlines()) if first in line)
        return self.screen().splitlines()[y].index(first), y

    def test_a_message_dragged_over_goes_whole_with_backspace(self):
        x, y = self.typed("fix: a typo")
        end = x + len("fix: a typo")
        self.term.type(Mouse("press", x, y, 0), Mouse("move", end, y, 0), Mouse("release", end, y, 0))
        self.term.type(Key("backspace"))
        self.until(lambda s: "fix: a typo" not in s and "Commit message" in s)

    def test_cmd_a_in_the_message_selects_it_all_for_backspace(self):
        self.typed("feat: a whole\n\nmessage")
        self.term.type(Key("f8"), Key("backspace"))                 # F8: what herdr sends the sidebar for Cmd + A
        self.until(lambda s: "whole" not in s and "Commit message" in s)

    def test_shift_home_selects_and_typing_puts_the_new_message_in_its_place(self):
        self.typed("fix: a typo")
        self.term.type(Key("home", shift=True), *keys("feat: a word"))
        self.until(lambda s: "feat: a word" in s and "typo" not in s)


class PreviewTab(Harness):
    """A file, a diff, a commit or an issue opened from the sidebar shows in the workspace's preview tab, laid out as
    the sidebar's own tab (its panes of the plugin's), whose new sidebar comes back to where this one was."""

    def test_the_preview_tab_gets_this_tabs_panes_and_its_sidebar_this_ones_place(self):
        set_env(self, HERDR_PANE_ID="w1:p2")                                # FAKE_HERDR: in w1:t1, with no terminal
        with mock.patch.object(sidebar.panes, "bring") as bring:
            self.start()
            self.term.type(Key("f11"), Key("char", "c"), *keys("feat: half"), Key("esc"), Key("f10"), *keys("needle"))
            self.until(lambda s: "a needle here" in s)
            self.term.type(Key("tab"), Key("down"), Key("enter"))                  # its hit
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not any(line.startswith("pane run") for line in logged(self.log)):
                time.sleep(0.05)
        self.assertEqual(bring.call_args.args[1:3], ("w1:t3", {"sidebar"}))
        with open(os.path.join(self.state, "seed-w1-t3.json")) as f:
            seed = json.load(f)
        self.assertEqual((seed["show"], seed["query"]), ("search", "needle"))
        self.assertNotIn("message", seed)                       # a message half written stays this sidebar's

    def test_a_new_preview_tabs_sidebar_comes_back_where_the_one_that_opened_it_was(self):
        os.makedirs(self.state)
        seed = os.path.join(self.state, "seed-w1-t1.json")
        with open(seed, "w") as f:
            json.dump({"show": "search", "query": "needle", "chosen": True,
                       "selected": os.path.realpath(os.path.join(self.root, "src"))}, f)
        set_env(self, HERDR_PANE_ID="w1:p2")                                # FAKE_HERDR: its tab is w1:t1
        self.start()
        self.until(lambda s: "in src" in s and "No results found" in s)
        self.assertFalse(os.path.exists(seed))


class IssuesTab(Harness):
    """The Issues view: there only for a repository on GitHub, its issues from gh, an issue previewed, handed to the
    agent and linked to the next commit."""

    def setUp(self):
        super().setUp()
        self.gh_log = os.path.join(os.path.dirname(self.log), "gh.log")
        stubs(self.bin, {"gh": FAKE_GH, "claude": "#!/bin/sh\nprintf 'feat: fix the login on Safari\\n'\n"})
        set_env(self, GH_LOG=self.gh_log, HERDR_PANE_ID="w1:p2")

    def start(self, cols=column.NARROWEST, rows=45):
        super().start(cols, rows)

    def on_github(self):
        subprocess.run(["git", "-C", self.root, "remote", "add", "origin", "git@github.com:acme/app.git"], check=True)

    def gh_calls(self):
        try:
            with open(self.gh_log) as f:
                return f.read().splitlines()
        except OSError:
            return []

    def tabs(self):
        """The panels named on the tab row: Issues among them only on GitHub."""
        return text(self.app.canvas, sidebar.stack.ROW).split()[:-2]               # but » and ⋯

    def test_a_repository_not_on_github_has_no_issues_tab(self):
        self.start()
        self.until(lambda s: "project" in s and "Changes" in s)
        self.assertEqual([name for name in self.tabs() if not name.isdigit()], ["Chats", "Files", "Search", "Changes"])
        self.term.type(Key("f12"), Key("char", "5"))
        time.sleep(0.3)
        self.assertEqual((self.app.shown(), self.app.showing("issues")), ("files", False))
        self.assertEqual(self.gh_calls(), [])

    def test_a_repository_on_github_shows_its_issues(self):
        self.on_github()
        self.start()
        self.until(lambda s: "project" in s and "Issues" in self.tabs())
        self.term.type(Key("f12"))
        self.until(lambda s: "#42 Login fails on Safari" in s)
        self.assertTrue(any(call.startswith("issue list -R acme/app") for call in self.gh_calls()))

    def test_the_issues_are_asked_for_again_in_the_background(self):
        # a list with issues in it: one made elsewhere (on GitHub, in another tab) is there when the view is shown
        # again, as in an editor's list
        self.on_github()
        listed = lambda: [issue.number for issue in self.app.views["issues"].listing.issues]  # noqa: E731
        with mock.patch.object(changes_panel, "STALE", 0.3):
            self.start()
            self.until(lambda s: "project" in s and "Issues" in self.tabs())
            self.term.type(Key("f12"))
            self.until(lambda s: "#42 Login fails on Safari" in s)
            self.term.type(Key("f9"))
            set_env(self, GH_ISSUES=TWO_ISSUES)                 # the second issue, made on GitHub
            self.until(lambda s: listed() == [43, 42])
            self.assertEqual(self.app.shown(), "files")
            self.stop()                                         # its last question done while it is still this quick

    def test_never_looked_at_they_are_never_asked_for(self):
        # a repository whose issues were never shown here (a stranger's clone): gh is not run for its remote
        self.on_github()
        with mock.patch.object(changes_panel, "STALE", 0.3):
            self.start()
            self.until(lambda s: "project" in s and "Issues" in self.tabs())
            time.sleep(1.5)
            self.assertEqual([call for call in self.gh_calls() if call.startswith("issue")], [])

    def test_an_empty_list_is_asked_for_only_on_screen(self):
        # a repository with no issues: gh runs while the view is shown, never behind it; the first one made shows up,
        # and from then on the list is kept fresh behind it too
        self.on_github()
        set_env(self, GH_ISSUES="[]")
        lists = lambda: len([call for call in self.gh_calls() if call.startswith("issue list")])  # noqa: E731
        with mock.patch.object(changes_panel, "STALE", 0.3):
            self.start()
            self.until(lambda s: "project" in s and "Issues" in self.tabs())
            self.term.type(Key("f12"))
            self.until(lambda s: "No open issues" in s)
            self.until(lambda s: lists() >= 2)                  # on screen: asked again
            self.term.type(Key("f11"))                          # Changes in its place: Issues off the screen
            self.until(lambda s: not self.app.showing("issues") and self.app.views["issues"].asked is None)
            asked = lists()
            time.sleep(2.5)                                     # two polls behind it
            self.assertEqual(lists(), asked)
            set_env(self, GH_ISSUES=None)                       # the first issue, made on GitHub
            self.term.type(Key("f12"))
            self.until(lambda s: "#42 Login fails on Safari" in s)
            self.term.type(Key("f11"))
            asked = lists()
            self.until(lambda s: lists() >= asked + 2)
            self.stop()

    def test_the_sidebars_of_one_repository_share_one_question(self):
        # another tab's sidebar takes the answer this one got less than a minute ago; R asks GitHub itself
        self.on_github()
        lists = lambda: len([call for call in self.gh_calls() if call.startswith("issue list")])  # noqa: E731
        self.start()
        self.until(lambda s: "project" in s and "Issues" in self.tabs())
        self.term.type(Key("f12"))
        self.until(lambda s: "#42 Login fails on Safari" in s and lists() == 1)
        other = sidebar.App(self.root, FakeTerminal(), preview.Herdr(), self.state)
        other.github = "acme/app"
        other.work["issues"].fresh_issues(changes_panel.STALE)
        for thread in threading.enumerate():
            if thread.name.startswith("sidebar-") and thread is not threading.current_thread():
                thread.join(5)
        other.collect()
        self.assertEqual(lists(), 1)
        self.assertEqual([issue.number for issue in other.views["issues"].listing.issues], [42])
        self.term.type(Key("char", "R"))
        self.until(lambda s: lists() == 2)

    def test_started_on_the_issues_it_asks_for_them(self):
        # herdr started again with the Issues last chosen: they come without a click
        self.on_github()
        os.makedirs(self.state)
        with open(os.path.join(self.state, "dock.json"), "w") as f:
            json.dump({os.path.realpath(self.root): {"shown": "issues"}}, f)
        self.start()
        self.until(lambda s: "#42 Login fails on Safari" in s)

    def test_after_an_update_the_issues_come_back_on_their_own(self):
        self.on_github()
        old = sidebar.App(self.root, FakeTerminal(), preview.Herdr(), self.state)
        old.show("issues")                                  # kept for the folder, as a click keeps it
        old.hand_over()                                     # its token is what the new version inherits
        self.addCleanup(os.environ.pop, loop.RESUME_ENV, None)
        self.start()
        self.until(lambda s: "#42 Login fails on Safari" in s)

    def test_every_tab_and_the_docks_controls_fit_whole_at_the_narrowest(self):
        self.on_github()
        self.start(cols=column.NARROWEST)
        self.until(lambda s: "project" in s and "Issues" in self.tabs())
        self.assertEqual(text(self.app.canvas, sidebar.stack.ROW).split(),
                         ["Chats", "Files", "Search", "Changes", "2", "Issues", "»", "⋯"])

    def test_enter_previews_the_issue(self):
        self.on_github()
        self.start()
        self.term.type(Key("f12"))
        self.until(lambda s: "#42 Login" in s)
        self.term.type(Key("enter"))
        self.until(lambda s: any("--label preview: #42 Login fails on Safa… --env " in call
                                 for call in logged(self.log)))

    def test_an_issue_handed_to_the_agent_is_linked_to_the_next_commit(self):
        self.on_github()
        self.start()
        self.term.type(Key("f12"))
        self.until(lambda s: "#42 Login" in s)
        self.term.type(Key("char", "t"))                                 # to the agent
        self.until(lambda s: "agent focus w1:p1" in logged(self.log))
        sent = next(call for call in logged(self.log) if call.startswith("pane send-text"))
        self.assertTrue(sent.startswith("pane send-text w1:p1 Work on GitHub issue #42 of acme/app: read it with "
                                        "`gh issue view 42 -R acme/app --comments`"), sent)
        subprocess.run(["git", "-C", self.root, "add", "a.txt"], check=True)
        self.term.type(Key("f11"))
        self.until(lambda s: "Fixes #42" in s and "Staged changes" in s)   # A writes only once a.txt shows as staged
        self.term.type(Key("char", "A"))
        self.until(lambda s: self.app.views["changes"].field.text == "feat: fix the login on Safari\n\nFixes #42",
                   timeout=20)                                       # git and the AI's stand-in: slow under load
        self.term.type(Key("esc"), Key("enter"))
        self.until(lambda s: "Fixes #42" not in s and not (self.app.status and self.app.status.staged))
        log = subprocess.run(["git", "-C", self.root, "log", "-1", "--format=%B"], capture_output=True, text=True)
        self.assertIn("Fixes #42", log.stdout)
        with open(os.path.join(self.state, "settings.json")) as f:
            self.assertEqual(json.load(f)["linked"], {})

    def linked_in_settings(self, issue):
        top = subprocess.run(["git", "-C", self.root, "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True).stdout.strip()
        os.makedirs(self.state, exist_ok=True)
        with open(os.path.join(self.state, "settings.json"), "w") as f:
            json.dump({"linked": {top: issue} if issue else {}}, f)

    def test_a_commit_made_elsewhere_that_fixes_the_issue_unlinks_it(self):
        # the commit window, a terminal or the agent: once the latest commit closes the issue, its line goes
        self.on_github()
        self.linked_in_settings([42, "Login fails on Safari"])
        self.start()
        self.term.type(Key("f11"))
        self.until(lambda s: "Fixes #42" in s)
        subprocess.run(["git", "-C", self.root, "add", "a.txt"], check=True)
        subprocess.run(["git", "-C", self.root, "commit", "-q", "-m", "fix: login on Safari\n\nFixes #42"], check=True)
        self.until(lambda s: "Fixes #42" not in s, timeout=20)
        with open(os.path.join(self.state, "settings.json")) as f:
            self.assertEqual(json.load(f)["linked"], {})

    def test_an_issue_linked_in_another_sidebar_shows_here_too(self):
        # every tab has a sidebar of its own: the link one of them makes reaches the others with their next status
        self.on_github()
        self.start()
        self.term.type(Key("f11"))
        self.until(lambda s: "Changes" in s)
        self.linked_in_settings([42, "Login fails on Safari"])
        with open(os.path.join(self.root, "a.txt"), "a") as f:
            f.write("more\n")
        self.until(lambda s: "Fixes #42" in s, timeout=20)

    def test_a_setting_saved_here_keeps_a_link_another_client_made(self):
        # the Herdr app mod links through core/commit_message.py's link() between this sidebar's own saves
        self.on_github()
        self.start()
        self.term.type(Key("f11"))
        self.until(lambda s: "Changes" in s)
        self.linked_in_settings([42, "Login fails on Safari"])
        self.term.type(Key("f9"), Key("char", "."))                      # hidden files shown: the settings saved
        self.until(lambda s: ".hidden" in s)
        with open(os.path.join(self.state, "settings.json")) as f:
            settings = json.load(f)
        self.assertEqual((settings["hidden"], list(settings["linked"].values())),
                         (True, [[42, "Login fails on Safari"]]))

    def test_x_closes_an_issue_after_a_question(self):
        self.on_github()
        self.start()
        self.term.type(Key("f12"))
        self.until(lambda s: "#42 Login" in s)
        self.term.type(Key("char", "x"))
        self.until(lambda s: "Close #42?" in s)
        self.term.type(Key("char", "y"))
        self.until(lambda s: "issue close 42 -R acme/app" in self.gh_calls())
        self.until(lambda s: len([c for c in self.gh_calls() if c.startswith("issue list")]) >= 2)


class ColumnWidth(Harness):
    """The column dragged wider in one tab: every other tab's column gets that width at once, and it is remembered."""

    def test_a_resize_sets_every_other_tabs_column(self):
        sock = tempfile.mkdtemp(dir="/tmp")                 # a socket's name has room for 104 bytes
        self.addCleanup(shutil.rmtree, sock)

        def tab(n, ratio):
            return {"type": "split", "direction": "right", "ratio": ratio,
                    "first": {"type": "pane", "pane_id": f"w{n}:p1", "label": "claude"},
                    "second": {"type": "pane", "pane_id": f"w{n}:p2", "label": "sidebar"}}

        fake = FakeHerdrSocket(os.path.join(sock, "h.sock"), {"w1:t1": (tab(1, 0.6), False),
                                                              "w2:t1": (tab(2, 0.75), False)})
        self.addCleanup(fake.server.close)
        set_env(self, HERDR_SOCKET_PATH=os.path.join(sock, "h.sock"), HERDR_PANE_ID="w1:p2")
        self.start()
        self.until(lambda s: "project" in s)
        self.term.type(Resize(40, 30))
        self.until(lambda s: ("layout.set_split_ratio", {"tab_id": "w2:t1", "path": [], "ratio": 0.6}) in fake.calls)
        with open(os.path.join(self.state, "column.json")) as f:
            self.assertEqual(json.load(f)["ratio"], 0.6)


class NotYetARepository(Harness):
    def setUp(self):
        Repo.setUp(self)
        shutil.rmtree(os.path.join(self.root, ".git"))
        self.start()

    def test_it_works_once_the_folder_becomes_one(self):
        self.term.type(Key("char", "4"))
        self.until(lambda s: "Not a git repository" in s)
        subprocess.run(["git", "-C", self.root, "init", "-q", "-b", "main"], check=True)
        # the whole list first: a row coming in later would move the first change from under the keys
        self.until(lambda s: all(name in s for name in (".hidden", "a.txt", "new.txt", "b.py")), timeout=4)
        self.term.type(Key("down"), Key("down"), Key("enter"))                # the first change, staged
        self.until(lambda s: "Staged changes" in s, timeout=15)               # a new status, paced by git's own time


class ChosenInFiles(Harness):
    """A workspace that is no repository itself, a repository near and one deep below it: Changes shows the repository
    of the folder chosen in Files (as Search searches there), its message, commit and marks with it."""

    def setUp(self):
        Repo.setUp(self)
        shutil.rmtree(os.path.join(self.root, ".git"))
        self.app_repo, self.lib = (self.repository(rel) for rel in ("work/app", "deep/a/b/c/lib"))
        self.start()

    def repository(self, rel):
        path = os.path.join(self.root, rel)
        name = os.path.basename(rel)
        os.makedirs(path)
        with open(os.path.join(path, name + ".txt"), "w") as f:
            f.write("one\n")
        git = ["git", "-C", path]
        subprocess.run(git + ["init", "-q", "-b", "main"], check=True)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "init"], check=True)
        with open(os.path.join(path, name + ".txt"), "w") as f:
            f.write("two\n")
        return path

    def choose_lib(self):
        """In Files: from deep, the first row, to a, b, c and lib, each opened on the way."""
        self.until(lambda s: "deep" in s)
        self.term.type(*[key for _ in range(4) for key in (Key("right"), Key("down"))])
        self.until(lambda s: "lib" in s)

    def test_without_a_folder_chosen_it_is_no_repository(self):
        self.term.type(Key("char", "4"))
        self.until(lambda s: "Not a git repository" in s)

    def test_the_repository_of_the_folder_chosen_in_files_shows(self):
        self.choose_lib()
        self.term.type(Key("char", "4"))
        self.until(lambda s: "lib.txt" in s and "lib" in self.row("⎇"), timeout=10)     # the repository row
        self.assertNotIn("app.txt", self.screen())

    def test_its_commit_goes_into_that_repository(self):
        self.choose_lib()
        self.term.type(Key("char", "4"))
        self.until(lambda s: "lib.txt" in s, timeout=10)
        self.term.type(Key("down"), Key("down"), Key("enter"))                   # lib.txt staged
        self.until(lambda s: "Staged changes" in s, timeout=15)
        self.term.type(Key("esc"), Key("up"), *keys("feat: in lib"), Key("enter", alt=True))
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and "feat: in lib" not in subprocess.run(
                ["git", "-C", self.lib, "log", "-1", "--format=%s"], capture_output=True, text=True).stdout:
            time.sleep(0.1)
        self.assertEqual(subprocess.run(["git", "-C", self.lib, "log", "-1", "--format=%s"], capture_output=True,
                                        text=True).stdout.strip(), "feat: in lib")
        self.assertEqual(subprocess.run(["git", "-C", self.app_repo, "log", "-1", "--format=%s"],
                                        capture_output=True, text=True).stdout.strip(), "init")

    def test_files_marks_that_repositorys_changes(self):
        self.choose_lib()
        self.until(lambda s: self.row("lib.txt").rstrip().endswith("M") if "lib.txt" in s else
                   self.row("lib").rstrip().endswith("●"), timeout=10)


class PaneMenu(unittest.TestCase):
    """The ⋯ at the tab row's end, or a right click on the row: the panels with a ✓ while shown, each of the tab's
    other panes closed or shown back, About's lines."""

    class Herdr:
        def call(self, *args):
            return {"panes": [{"pane_id": "w1:p1", "tab_id": "w1:t1", "label": "claude"},
                              {"pane_id": "w1:p2", "tab_id": "w1:t1", "label": "sidebar"}]} if args[:2] == (
                "pane", "list") else {}

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_env(self, HERDR_PANE_ID="w1:p2", HOME=self.tmp)
        self.addCleanup(end_jobs)                       # before the folders go: a job of the dock's writes there
        self.brought = []
        self.app = sidebar.App(self.tmp, FakeTerminal(45, 30), self.Herdr(), os.path.join(self.tmp, "state"))

    PANELS = ["✓ Chats", "✓ Files", "✓ Search", "✓ Changes", None]       # Issues: on GitHub only
    PAST = 35                 # a cell of the tab row past its tabs, before » (45 cells: Changes ends at 34)

    def test_it_offers_the_other_panes_and_brings_the_one_chosen(self):
        self.app.draw()
        self.app.handle(Mouse("press", self.PAST, ROW, 2))              # the tab row, past its tabs
        self.assertEqual(self.app.menu[0].choices, self.PANELS + ["Show terminal", "Restore panels"])
        with mock.patch.object(sidebar.panes, "bring",
                               lambda call, tab, kinds, state_dir: self.brought.append((tab, set(kinds)))):
            self.pick("Show terminal")
            end_jobs()
        self.assertEqual(self.brought, [("w1:t1", {"terminal"})])
        self.assertIsNone(self.app.menu)

    def menu_rows(self):
        """The menu's choices, as drawn."""
        self.app.draw()
        rows = ["".join(ch for ch, _ in row) for row in self.app.canvas.rows]
        return [m.group(1).strip() for m in (re.search(r"│([^│]+)│", row) for row in rows) if m]

    def pick(self, choice, app=None):
        """CHOICE clicked in the ⋯'s menu, opened first if it is not."""
        app = app or self.app
        if not app.menu:
            app.draw()
            app.handle(Mouse("press", self.PAST, ROW, 2))
        app.draw()
        rows = ["".join(ch for ch, _ in row) for row in app.canvas.rows]
        y = next(n for n, row in enumerate(rows) if re.search(r"│" + re.escape(choice) + r" *│", row))
        app.handle(Mouse("press", rows[y].index(choice), y, 0))

    def test_a_panel_unchecked_leaves_the_tab_row_and_comes_back_checked(self):
        # as Adobe's Window menu: every panel the dock has, a ✓ on the ones shown
        self.pick("✓ Search")
        self.assertEqual(self.app.tabs(), ["conversations", "files", "changes"])
        self.app.draw()
        self.assertEqual(text(self.app.canvas, ROW).split()[:-2], ["Chats", "Files", "Changes"])
        with open(os.path.join(self.tmp, "state", "settings.json")) as f:
            self.assertEqual(json.load(f)["hidden_panels"], ["search"])
        self.pick("  Search")
        self.assertIn("search", self.app.tabs())

    def test_a_group_left_without_a_panel_leaves_no_gap(self):
        self.pick("✓ Chats")
        self.app.draw()
        self.assertTrue(text(self.app.canvas, ROW).startswith(" Files  Search   Changes"))

    def test_a_hidden_panel_stays_hidden_in_every_tab(self):
        self.pick("✓ Changes")
        other = sidebar.App(self.tmp, FakeTerminal(45, 30), self.Herdr(), os.path.join(self.tmp, "state"))
        self.assertNotIn("changes", other.tabs())                          # a tab's sidebar started later
        self.pick("  Changes", other)
        self.app.next_poll = 0
        self.app.tick()                                                    # one already running: at its next look
        self.assertIn("changes", self.app.tabs())

    def test_the_last_panel_shown_stays(self):
        for choice in ("✓ Chats", "✓ Files", "✓ Search"):
            self.pick(choice)
        self.pick("✓ Changes")
        self.assertEqual(self.app.tabs(), ["changes"])
        self.assertEqual((self.app.note, self.app.shown()), ("One panel stays shown", "changes"))

    def test_two_tabs_hiding_panels_at_once_keep_both(self):
        other = sidebar.App(self.tmp, FakeTerminal(45, 30), self.Herdr(), os.path.join(self.tmp, "state"))
        self.pick("✓ Search")
        self.pick("✓ Changes", other)                                     # before its next look: Search still there
        with open(os.path.join(self.tmp, "state", "settings.json")) as f:
            self.assertEqual(sorted(json.load(f)["hidden_panels"]), ["changes", "search"])

    def test_the_last_panel_shown_stays_whatever_another_tab_hid(self):
        other = sidebar.App(self.tmp, FakeTerminal(45, 30), self.Herdr(), os.path.join(self.tmp, "state"))
        for choice in ("✓ Chats", "✓ Files", "✓ Search"):
            self.pick(choice)
        self.pick("✓ Changes", other)
        self.assertEqual(other.note, "One panel stays shown")
        with open(os.path.join(self.tmp, "state", "settings.json")) as f:
            self.assertEqual(sorted(json.load(f)["hidden_panels"]), ["conversations", "files", "search"])

    def test_every_panel_hidden_by_another_tab_leaves_the_first_shown(self):
        # a tab on GitHub hid every panel but Issues, which this folder, on no GitHub, does not have
        os.makedirs(os.path.join(self.tmp, "state"), exist_ok=True)
        with open(os.path.join(self.tmp, "state", "settings.json"), "w") as f:
            json.dump({"hidden_panels": ["conversations", "files", "search", "changes"]}, f)
        self.app.next_poll = 0
        self.app.tick()
        self.assertEqual(self.app.tabs(), ["conversations"])
        self.app.handle(Key("char", "x"))
        self.app.draw()
        self.assertEqual(text(self.app.canvas, ROW).split(), ["Chats", "»", "⋯"])
        self.assertEqual(self.app.views["conversations"].typed, "x")                # the keys go to it

    def test_a_key_for_a_hidden_panel_shows_it_again(self):
        self.pick("✓ Search")
        self.app.handle(Key("f10"))                                       # its key, as a click on its ✓
        self.assertTrue(self.app.showing("search"))
        with open(os.path.join(self.tmp, "state", "settings.json")) as f:
            self.assertEqual(json.load(f)["hidden_panels"], [])

    def test_the_dots_at_the_tab_rows_right_end_open_it(self):
        self.app.draw()
        dots = text(self.app.canvas, ROW).index("⋯")
        self.app.handle(Mouse("press", dots, ROW, 0))                       # a left click
        self.assertEqual(self.menu_rows(), [row for row in self.PANELS if row] + ["Show terminal", "Restore panels"])
        rows = ["".join(ch for ch, _ in row) for row in self.app.canvas.rows]
        top = next(y for y, row in enumerate(rows) if "┌" in row)
        self.assertEqual(top, ROW + 1)                                     # right under the ⋯ (one row high)
        self.assertEqual(rows[top].rindex("┐"), dots + 2)                   # its right edge with the ⋯'s

    def installed(self, version="0.3.0"):
        """herdr-fold installed here, this VERSION, in a home of the test's own."""
        set_env(self, HOME=self.tmp)
        folder = os.path.join(self.tmp, ".local", "state", "herdr-fold")
        os.makedirs(folder)
        with open(os.path.join(folder, "version"), "w") as f:
            f.write(f"{version}\n")
        return folder

    def test_it_names_herdr_folds_version_and_switches_the_update_check(self):
        folder = self.installed()
        set_env(self, HERDR_FOLD_NO_UPDATE_CHECK=None)
        self.app.update = sidebar.update.check(ask=lambda: "0.3.0")
        self.app.draw()
        self.app.handle(Mouse("press", self.PAST, ROW, 2))
        self.assertEqual(self.app.menu[0].choices[-3:], [None, "herdr-fold 0.3.0", "✓ Check for Updates"])
        self.pick("✓ Check for Updates")
        end_jobs()
        self.app.collect()
        with open(os.path.join(folder, "update.json")) as f:
            self.assertIs(json.load(f)["on"], False)
        self.assertFalse(self.app.update["on"])

    def test_a_newer_version_is_told_once_and_shown_until_updated(self):
        self.installed()
        calls = []
        self.app.herdr = mock.Mock(call=lambda *args: calls.append(args) or {})
        found = {"version": "0.3.0", "latest": "0.4.0", "newer": True, "on": True, "told": None}
        self.app.got_update(found)
        end_jobs()
        self.app.collect()
        self.assertEqual([c[:3] for c in calls], [("notification", "show", "herdr-fold 0.4.0 is out")])
        self.assertEqual(sidebar.update.check(ask=lambda: None)["told"], "0.4.0")
        self.app.got_update({**found, "told": "0.4.0"})                     # another sidebar's: not told again
        end_jobs()
        self.app.collect()
        self.assertEqual(len(calls), 1)
        self.app.draw()
        last = "".join(ch for ch, _ in self.app.canvas.rows[-1])
        self.assertIn("herdr-fold 0.4.0 is out", last)
        with mock.patch.object(sidebar.media, "open_in_browser", return_value=True) as opened:
            self.app.handle(Mouse("press", 5, self.app.canvas.height - 1, 0))
        opened.assert_called_once_with(sidebar.update.RELEASES)

    def test_a_click_in_another_pane_closes_every_menu(self):
        # herdr tells the pane it lost the keys (focus reporting): no menu stays open behind
        self.app.draw()
        self.app.handle(Mouse("press", self.PAST, ROW, 2))
        self.assertIsNotNone(self.app.menu)
        self.app.handle(Focus(False))
        self.assertIsNone(self.app.menu)
        files = self.app.views["files"]
        files.open_menu(None, 5, 5)
        self.app.handle(Focus(True))                                        # back in the pane: nothing closes
        self.assertIsNotNone(files.menu)
        self.app.handle(Focus(False))
        self.assertIsNone(files.menu)

    def test_a_click_on_the_tab_row_closes_the_views_menu(self):
        self.app.draw()
        files = self.app.views["files"]
        files.open_menu(None, 5, 5)
        self.app.handle(Mouse("press", self.PAST, ROW, 2))              # the pane's own menu instead
        self.assertIsNone(files.menu)
        self.assertIsNotNone(self.app.menu)
        self.app.handle(Key("esc"))
        files.open_menu(None, 5, 5)
        search = next(x for x in range(45) if self.app.canvas.hit(x, ROW) == "tab:search")
        self.app.handle(Mouse("press", search, ROW, 0))                  # another panel: the menu not kept behind
        self.assertTrue(self.app.showing("search"))
        self.assertIsNone(files.menu)

    def test_a_right_click_on_a_tab_opens_it_and_leaves_the_panel_shown(self):
        self.app.draw()
        search = next(x for x in range(45) if self.app.canvas.hit(x, ROW) == "tab:search")
        self.app.handle(Mouse("press", search, ROW, 2))
        self.assertIsNotNone(self.app.menu)
        self.assertTrue(self.app.showing("files"))

    def test_each_other_pane_closes_from_it_the_sidebar_itself_not(self):
        panes = self.Herdr().call("pane", "list")["panes"] + [
            {"pane_id": "w1:p3", "tab_id": "w1:t1", "label": "terminal"}]
        calls = []

        def call(*args):
            calls.append(args)
            return {"panes": panes} if args[:2] == ("pane", "list") else {}
        self.app.herdr = mock.Mock(call=call)
        self.app.draw()
        self.app.handle(Mouse("press", self.PAST, ROW, 2))
        self.assertEqual(self.menu_rows()[-1], "Close terminal")                           # not itself
        self.assertNotIn("Close sidebar", self.menu_rows())
        self.pick("Close terminal")
        deadline = time.monotonic() + 5
        while ("pane", "close", "w1:p3") not in calls and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertIn(("pane", "close", "w1:p3"), calls)                    # as closed by hand: it stays closed
        self.assertIsNone(self.app.menu)


class Dock(unittest.TestCase):
    """The dock's tab row: the panel shown and where a key goes, what two sidebars on one folder keep, a handover and a
    seed's panel, a note, the column's room."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_env(self, HERDR_PANE_ID="w1:p2", HOME=self.tmp)
        self.addCleanup(end_jobs)                       # before the folders go: a job of the dock's writes there
        self.state = os.path.join(self.tmp, "state")
        self.app = self.sidebar()

    def sidebar(self, rows=30):
        return sidebar.App(self.tmp, FakeTerminal(column.FEWEST, rows), PaneMenu.Herdr(), self.state)

    def test_it_starts_on_files_whose_keys_work_at_once(self):
        # Chats' filter would take every character: n, . and q are Files' own at once
        self.assertEqual((self.app.shown(), self.app.keyed()), ("files", "files"))
        self.app.handle(Key("char", "."))
        self.assertTrue(self.app.settings["hidden"])

    def test_the_tab_row_shows_chats_dot_while_one_waits_and_changes_count(self):
        waiting = Conversation("claude", "c1", "Fix the page", self.tmp, 0.0, "blocked", "w1:p1")
        self.app.work["conversations"].view.items = [waiting]
        self.app.status = Status(staged=["a.py"], changes=["b.py", "c.py"])
        self.app.draw()
        row = text(self.app.canvas, ROW)
        self.assertEqual(row[:37], " Chats ●   Files  Search   Changes 3 ")
        self.assertEqual([self.app.canvas.rows[ROW][row.index(mark)][1].fg for mark in ("●", "3")], ["modified"] * 2)
        self.app.work["conversations"].view.items = [replace(waiting, state="working")]
        self.app.draw()
        self.assertEqual(text(self.app.canvas, ROW)[:37], " Chats     Files  Search   Changes 3 ")

    def test_i_in_files_switches_every_panels_icons(self):
        # the keys start in Files; its view asks for the icons, which the dock keeps for every panel
        self.app.draw()
        self.app.handle(Key("char", "i"))
        self.assertFalse(self.app.settings["icons"])
        self.assertFalse(self.app.views["changes"].icons)

    def test_a_panel_hidden_in_the_menu_shown_gives_way_to_the_first_one_left(self):
        self.app.show("search")
        self.app.hide("search", True)
        self.assertEqual(self.app.shown(), "files")
        self.app.hide("files", True)
        self.assertEqual(self.app.shown(), "conversations")
        self.app.hide("search", False)                                    # back: shown again, as the folder keeps it
        self.assertEqual(self.app.shown(), "search")

    def test_two_sidebars_on_one_folder_each_show_what_they_chose(self):
        other = self.sidebar()                                            # a preview tab's, on the same folder
        self.app.show("changes")
        other.show("search")
        self.assertEqual(sidebar.stack.state(self.state, os.path.realpath(self.tmp)), {"shown": "search"})
        self.assertEqual((self.app.shown(), other.shown()), ("changes", "search"))

    def test_a_note_goes_by_itself_an_error_stays(self):
        now = [100.0]
        app = sidebar.App(self.tmp, FakeTerminal(45, 30), PaneMenu.Herdr(), self.state, clock=lambda: now[0])
        app.note = "Archived"
        app.tick()
        self.assertIn(100.0 + sidebar.NOTE, app.deadlines())                # the loop wakes up for it
        now[0] += sidebar.NOTE
        app.tick()
        self.assertIsNone(app.note)
        app.error = "settings not saved: disk full"
        now[0] += 60
        app.tick()
        self.assertEqual(app.error, "settings not saved: disk full")       # until a key or a click

    def test_two_tabs_changing_settings_at_once_keep_both(self):
        other = self.sidebar()
        at_once(sidebar.statefile, lambda: other.save(icons=False), lambda: self.app.hide("search", True))
        self.assertEqual({key: sidebar.load_settings(os.path.join(self.state, "settings.json"))[key]
                          for key in ("icons", "hidden_panels")}, {"icons": False, "hidden_panels": ["search"]})

    def test_the_columns_room_is_the_tab_rows_and_follows_the_last_change(self):
        # two panels hidden in a row: the room the first asked for never lands after the second's
        calls, first = [], threading.Event()
        real = sidebar.column.need

        def need(state_dir, tab, cells, tabs):
            calls.append(cells)
            if len(calls) == 1:
                first.wait(2)                                              # the first one slow
            real(state_dir, tab, cells, tabs)

        with mock.patch.object(sidebar.column, "need", need):
            self.app.hide("search", True)
            self.app.hide("conversations", True)
            first.set()
            for _ in range(3):
                end_jobs()
                self.app.collect()
        self.assertEqual(sidebar.column.kept(self.state)["least"]["w1:t1"], sidebar.narrowest(self.app.tabs()))
        self.assertEqual(sidebar.narrowest(self.app.tabs()), len(" Files   Changes 999   »   ⋯   "))
        self.assertEqual(sidebar.narrowest(list(sidebar.PANELS)), column.NARROWEST)

    def test_the_conversations_are_read_less_often_while_off_screen(self):
        now, reads = [100.0], []
        app = sidebar.App(self.tmp, FakeTerminal(45, 30), PaneMenu.Herdr(), self.state, clock=lambda: now[0])
        family = app.work["conversations"]
        family.read, family.got = (lambda: reads.append(now[0])), (lambda seen: None)
        for at in (100.0, 101.5, 110.5):                                   # behind Files: every AWAY seconds
            now[0] = at
            app.tick()
            end_jobs()
            app.collect()
        app.show("conversations")
        now[0] = 111.6                                                     # on screen: every POLL seconds
        app.tick()
        end_jobs()
        self.assertEqual(reads, [100.0, 110.5, 111.6])

    def test_issues_key_off_github_leaves_them_hidden_in_every_tab(self):
        self.app.save(hidden_panels=["issues"])                            # hidden in a tab on GitHub
        self.app.handle(Key("f12"))                                        # no Issues here: nothing to show
        self.assertEqual(self.app.settings["hidden_panels"], ["issues"])

    def test_a_handover_keeps_this_sidebars_own_tab(self):
        # another sidebar on the folder chose another tab since: the new version comes back as this one was
        self.app.show("changes")
        other = self.sidebar()
        other.show("search")
        new = self.sidebar()
        new.take(self.app.left())
        self.assertEqual(new.shown(), "changes")

    def test_a_seed_shows_a_panel_hidden_in_the_menu_again(self):
        # Cmd+Shift+R in a tab whose sidebar was closed by hand: the new one comes on Conversations (actions.find)
        self.app.hide("conversations", True)
        self.app.take({"show": "conversations"})
        self.assertTrue(self.app.showing("conversations"))
        self.assertNotIn("conversations", self.app.settings["hidden_panels"])


def column_tab(n, ratio=0.75):
    """A tab as herdr-fold lays it out: the agent, the right column of the sidebar above a terminal; panes wN:p1…3."""
    def pane(pane_id, label):
        return {"type": "pane", "pane_id": pane_id, "label": label}
    return {"type": "split", "direction": "right", "ratio": ratio, "first": pane(f"w{n}:p1", "claude"),
            "second": {"type": "split", "direction": "down", "ratio": 0.5, "first": pane(f"w{n}:p2", "sidebar"),
                       "second": pane(f"w{n}:p3", "terminal")}}


class Rail(unittest.TestCase):
    """The dock folded to its rail by the tab row's », in every tab: each panel's icon over its name, a press opening
    the panel beside the rail, « opening the dock again; every tab's column and terminal with it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir="/tmp")                 # a socket's name has room for 104 bytes
        self.addCleanup(shutil.rmtree, self.tmp)
        sock = os.path.join(self.tmp, "h.sock")
        set_env(self, HERDR_PANE_ID="w1:p2", HOME=self.tmp, HERDR_SOCKET_PATH=sock)
        self.fake = FakeHerdrSocket(sock, {"w1:t1": (column_tab(1), False), "w2:t1": (column_tab(2), False)})
        self.addCleanup(self.fake.server.close)
        self.addCleanup(end_jobs)                       # before the folders go: a job of the dock's writes there
        self.state = os.path.join(self.tmp, "state")
        self.app = self.sidebar()

    def sidebar(self):
        return sidebar.App(self.tmp, FakeTerminal(45, 30), mock.Mock(call=self.fake.cli), self.state)

    def settle(self, app=None):
        """The dock's jobs done and answered, one asked again meanwhile too."""
        for _ in range(3):
            end_jobs()
            (app or self.app).collect()

    def press(self, target):
        """A click on what answers to TARGET as last drawn."""
        self.app.draw()
        y, x = next((y, x0) for y, x0, _x1, found in reversed(self.app.canvas.regions) if found == target)
        self.app.handle(Mouse("press", x, y, 0))
        self.settle()

    def folded(self):
        """The dock folded to its rail, the pane as narrow as herdr then makes it: 9 cells inside its frame."""
        self.press("to_rail")
        self.app.term.cols = 9

    def rows(self):
        self.app.draw()
        return [text(self.app.canvas, y).rstrip() for y in range(self.app.canvas.height)]

    def ratio(self, tab="w1:t1"):
        return self.fake.tabs[tab][0]["ratio"]

    def test_the_rail_draws_each_panel_its_name_under_its_icon(self):
        marks = glyphs(True)
        self.app.hide("search", True)                                      # hidden in the ⋯: left out
        waiting = Conversation("claude", "c1", "Fix the page", self.tmp, 0.0, "blocked", "w1:p1")
        self.app.work["conversations"].view.items = [waiting]
        self.app.status = Status(staged=["a.py"], changes=["b.py"])
        self.folded()
        self.assertEqual(self.rows()[:10], [" «", f"    {marks['ai']} ●", "  Chats", "", f"    {marks['files']}",
                                            "  Files", "", f"    {marks['git']} 2", " Changes", ""])
        canvas = self.app.canvas
        self.assertEqual([canvas.rows[1][6][1].fg, canvas.rows[7][6][1].fg], ["modified", "modified"])
        self.assertEqual([canvas.rows[1][4][1].fg, canvas.rows[2][2][1].fg], ["subtext", "muted"])
        self.app.work["conversations"].view.items = [replace(waiting, state="working")]
        self.assertEqual(self.rows()[1], f"    {marks['ai']}")                 # none waits: no dot

    def test_a_press_opens_its_panel_beside_the_rail_and_lights_it(self):
        self.folded()
        self.press("icon:changes")
        # the column as wide as its tab row (49 cells and the frame, over the default quarter of 200 cells) and the
        # rail's 9 cells besides
        self.assertIn(("layout.set_split_ratio", {"tab_id": "w1:t1", "path": [], "ratio": 0.7}), self.fake.calls)
        self.assertEqual(self.ratio("w2:t1"), 0.9)                          # another tab's stays the rail
        self.app.term.cols = 58                                             # as herdr then makes it
        rows, canvas, edge = self.rows(), self.app.canvas, 58 - 9
        self.assertEqual(rows[0][:edge].strip(), "")                        # no tab row: the lit icon names it
        self.assertEqual((self.app.body, self.app.panel_at(1, 0), self.app.panel_at(1, edge)), ((1, 29), "changes",
                                                                                                None))
        self.assertEqual((rows[0][edge + 1], canvas.hit(edge + 1, 0), rows[0].strip()[-1]), ("«", "to_dock", "⋯"))
        self.assertEqual((rows[9][edge], canvas.rows[9][edge + 4][1].fg), ("▌", "accent"))       # Changes lit
        self.assertEqual(canvas.rows[10][edge + 1][1], screen.Style(fg="accent", bold=True))
        self.assertEqual(self.app.keyed(), "changes")

    def test_the_lit_icon_or_esc_folds_it_back(self):
        self.folded()
        self.press("icon:changes")
        self.press("icon:changes")                                          # the lit one again
        self.assertEqual((self.app.beside, self.ratio()), (False, 0.9))     # the rail's width again
        self.press("icon:files")
        files = self.app.views["files"]
        files.open_menu(None, 5, 5)
        self.app.handle(Key("esc"))                                         # its menu first
        self.assertEqual((files.menu, self.app.beside, self.app.shown()), (None, True, "files"))
        self.app.handle(Key("esc"))
        self.settle()
        self.assertEqual((self.app.beside, self.ratio()), (False, 0.9))

    def test_the_tab_rows_double_chevron_folds_every_tabs_dock_and_the_rails_opens_it(self):
        self.app.draw()
        self.assertEqual((text(self.app.canvas, ROW)[45 - 8], self.app.canvas.hit(45 - 8, ROW)), ("»", "to_rail"))
        self.app.point("to_rail", 37, ROW)
        self.assertEqual(self.app.tip[1], "Collapse to icons")
        self.folded()
        self.assertTrue(sidebar.column.railed(self.state))
        for n in (1, 2):                                                    # each tab's terminal under its agent
            self.assertEqual((self.ratio(f"w{n}:t1"), self.fake.tabs[f"w{n}:t1"][0]["first"]["second"]["pane_id"]),
                             (0.9, f"w{n}:p3"))
        self.assertEqual((self.rows()[0], self.app.canvas.hit(1, 0)), (" «", "to_dock"))
        self.app.point("to_dock", 1, 0)
        self.assertEqual(self.app.tip[1], "Expand panels")
        self.press("to_dock")
        self.assertFalse(sidebar.column.railed(self.state))
        # each column as wide as before, but for the room its tab row takes: 49 cells and the frame of 200
        self.assertEqual(self.fake.tabs, {"w1:t1": [column_tab(1, 0.745), False], "w2:t1": [column_tab(2, 0.745),
                                                                                             False]})

    def test_another_tabs_sidebar_follows_at_its_next_look(self):
        other = self.sidebar()
        self.folded()
        other.next_poll = 0
        other.tick()
        self.assertTrue(other.railed)

    def test_on_the_rail_a_panels_key_opens_it_beside_the_rail(self):
        self.folded()
        self.assertEqual([panel for panel in self.app.panels() if self.app.showing(panel)], [])
        self.app.handle(Key("f10"))
        self.settle()
        self.assertEqual((self.app.beside, self.app.shown()), (True, "search"))
        self.assertEqual([panel for panel in self.app.panels() if self.app.showing(panel)], ["search"])

    def test_a_sidebar_started_on_the_rail_sets_its_tab(self):
        # a new tab's, a preview tab's: its column the rail, its terminal under its agent; another tab's left as is
        sidebar.column.keep(self.state, {"rail": True})
        new = self.sidebar()
        new.resume()
        self.settle(new)
        self.assertEqual((self.ratio(), self.fake.tabs["w1:t1"][0]["first"]["second"]["pane_id"]), (0.9, "w1:p3"))
        self.assertEqual(self.fake.tabs["w2:t1"], [column_tab(2), False])

    def test_a_rail_never_widens_for_the_tab_row(self):
        self.folded()
        self.app.need(sidebar.column.NARROWEST)
        self.assertEqual(self.ratio(), 0.9)

    def test_the_menus_show_terminal_on_the_rail_brings_it_under_the_agent(self):
        self.folded()
        self.press("icon:changes")
        self.app.term.cols = 58                                             # the ⋯ beside the rail
        root = self.fake.tabs["w1:t1"][0]
        root["first"] = root["first"]["first"]                              # the terminal closed by hand
        self.press("panels")
        self.press(f"menu:{self.app.menu[0].choices.index('Show terminal')}")
        self.assertEqual([root["first"]["first"]["pane_id"], root["first"]["second"]["label"], root["second"]["label"]],
                         ["w1:p1", "terminal", "sidebar"])

    def test_a_tab_whose_agent_was_zoomed_catches_up_once_shown(self):
        self.fake.tabs["w2:t1"][1] = True                                   # its column off screen: left as it was
        self.folded()
        self.assertEqual((self.fake.tabs["w2:t1"][0], sidebar.column.kept(self.state)["owed"]),
                         (column_tab(2), ["w2:p2"]))
        set_env(self, HERDR_PANE_ID="w2:p2")
        other = self.sidebar()                                              # that tab's own sidebar
        other.next_poll = 0
        other.tick()
        self.settle(other)
        self.assertEqual(self.fake.tabs["w2:t1"][0], column_tab(2))         # still zoomed
        self.assertLessEqual(other.next_poll - time.monotonic(), 1.0)       # looked at again soon
        self.fake.tabs["w2:t1"][1] = False                                  # shown again
        other.next_poll = 0
        other.tick()
        self.settle(other)
        self.assertEqual((self.ratio("w2:t1"), self.fake.tabs["w2:t1"][0]["first"]["second"]["pane_id"]),
                         (0.9, "w2:p3"))
        self.assertEqual(sidebar.column.kept(self.state)["owed"], [])

    def test_a_panel_opened_beside_the_rail_comes_back_after_a_handover(self):
        self.folded()
        self.press("icon:changes")
        new = self.sidebar()
        new.take(self.app.left())
        self.settle(new)
        self.assertEqual((new.beside, new.shown()), (True, "changes"))

    def test_folded_alone_the_tab_shown_is_kept_for_the_dock_opened_again(self):
        self.app.show("search")
        self.folded()
        self.assertEqual(self.app.left().get("show"), None)                 # a handover stays on the rail alone
        self.press("to_dock")
        self.app.term.cols = 45
        self.app.draw()
        self.assertEqual((self.app.shown(), text(self.app.canvas, ROW).split()[:2]), ("search", ["Chats", "Files"]))
        self.assertEqual(self.app.canvas.rows[ROW][text(self.app.canvas, ROW).index("Search")][1].fg, "accent")


class Ticks:
    """For a test that moves the sidebar's clock (self.now) and loop (self.app) on."""

    def later(self):
        """Five seconds on, the jobs started meanwhile answered first, as the loop collects them before each tick."""
        end_jobs()
        self.app.collect()
        self.now += 5
        self.app.tick()


class NewVersion(Ticks, unittest.TestCase):
    """An update puts a new version of the sidebar's code in place: the running one hands over to it once the files are
    still and nothing would be cut short, and the new one comes back where the old one was."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root, self.code = os.path.join(self.tmp, "project"), os.path.join(self.tmp, "code")
        self.state = os.path.join(self.tmp, "state")
        set_env(self, HOME=os.path.join(self.tmp, "home"))
        os.makedirs(os.path.join(self.root, "src"))
        os.makedirs(self.code)
        for path in (os.path.join(self.root, "src", "app.py"), os.path.join(self.code, "a.py"),
                     os.path.join(self.code, "b.py")):
            with open(path, "w") as f:
                f.write("x = 1\n")
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull)
        self.addCleanup(os.environ.pop, loop.RESUME_ENV, None)
        self.addCleanup(end_jobs)                       # the first cleanup: its ticks start jobs
        self.now = 1000.0
        self.app = self.make()

    def handovers(self):
        return sorted(name for name in os.listdir(self.state) if name.startswith("resume"))

    def make(self):
        return sidebar.App(self.root, FakeTerminal(), preview.Herdr("/usr/bin/false"), self.state,
                           clock=lambda: self.now, code=self.code)

    def update(self, name="a.py"):
        path = os.path.join(self.code, name)
        with open(path, "a") as f:
            f.write("y = 2\n")
        mtime = os.stat(path).st_mtime_ns + 1_000_000_000                  # newer, however coarse the file system
        os.utime(path, ns=(mtime, mtime))

    def test_the_changes_views_place_is_handed_over(self):
        self.app.views["changes"].focus = "graph"
        self.assertEqual(self.app.left()["changes"]["focus"], "graph")

    def test_a_folded_section_stays_folded_in_the_next_one(self):
        self.app.act(Action("remember_folded", (["graph"],)), "changes")
        self.assertEqual(self.make().views["changes"].folded, {"graph"})

    def test_it_hands_over_once_the_new_version_is_still(self):
        self.update()
        self.later()                                       # seen: more files may still be on their way
        self.assertFalse(self.app.quit)
        self.update("b.py")
        self.later()                                       # one more came: it waits again
        self.assertFalse(self.app.quit)
        self.later()
        self.assertTrue(self.app.quit and self.app.restart)

    def test_it_waits_for_work_a_restart_would_cut_short(self):
        self.update()
        self.later()
        self.app.running.add("commit")
        self.later()
        self.assertFalse(self.app.quit)
        self.app.running.discard("commit")
        self.later()
        self.assertTrue(self.app.restart)

    def test_every_job_holds_it_one_only_asked_again_too(self):
        # a status or a search would only be asked again, but the program it runs would be left behind in this
        # process, never waited for: a zombie of the new version
        for job in ("status", "search", "issues", "column"):
            self.app.running = {job}
            self.assertTrue(self.app.busy(), job)
        self.app.running = set()
        self.assertFalse(self.app.busy())

    @unittest.skipIf(os.name == "nt", "no zombies on Windows")
    def test_the_new_one_waits_for_the_programs_the_old_one_left(self):
        # the same process after the handover (exec): a program the old version ran and left is the new one's child
        pid = os.fork()
        if pid == 0:
            os._exit(0)
        deadline = time.monotonic() + 5
        while not subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True,
                                 text=True).stdout.startswith("Z") and time.monotonic() < deadline:
            time.sleep(0.01)                                                # ended, not waited for: a zombie
        sidebar.reap()
        with self.assertRaises(ChildProcessError):
            os.waitpid(pid, os.WNOHANG)                                     # gone

    def test_an_open_menu_does_not_hold_it(self):
        # a menu opens again with a click; a question or a name half typed would be lost, so those wait
        self.app.views["files"].open_menu(None, 5, 5)
        self.app.views["changes"].menu = sidebar.Menu(["a"])
        self.app.views["issues"].open_filters()
        self.update()
        self.later()
        self.later()
        self.assertTrue(self.app.restart)

    def test_a_question_on_screen_holds_it(self):
        self.app.views["files"].confirm = object()                          # e.g. Move to the Trash?
        self.update()
        self.later()
        self.later()
        self.assertFalse(self.app.quit)
        self.app.views["files"].confirm = None
        self.later()
        self.assertTrue(self.app.restart)

    def test_its_code_gone_it_ends_leaving_nothing_behind(self):
        # uninstalled under a running sidebar: a handover would bring back the state folder just removed, with the
        # project's paths, a half written message and the issues in it
        for name in os.listdir(self.code):
            os.remove(os.path.join(self.code, name))
        os.rmdir(self.code)
        self.later()
        self.later()
        self.assertTrue(self.app.quit)
        self.assertFalse(self.app.restart)
        self.assertFalse(os.path.isdir(self.state) and self.handovers())

    def test_unchanged_code_never_restarts_it(self):
        for _ in range(5):
            self.later()
        self.assertFalse(self.app.quit)

    def test_the_new_one_comes_back_where_this_one_was(self):
        src = os.path.join(self.app.root, "src")                           # the real path (/var is a link here)
        self.app.work["files"].tree.toggle(src)
        self.app.views["files"].select(src)
        self.app.views["changes"].set_message("feat: half written")
        find = self.app.views["search"]
        find.field.insert("needle")
        find.switches["case"] = True
        self.app.views["files"].moved = True                                 # src, chosen by you
        self.app.show("search")
        self.update()
        self.later()
        self.later()
        self.assertTrue(self.app.restart)
        new = self.make()
        new.resume()
        self.assertEqual((new.shown(), new.showing("search")), ("search", True))
        self.assertEqual(new.views["changes"].field.text, "feat: half written")
        self.assertEqual((new.views["search"].field.text, new.views["search"].switches["case"],
                          new.views["search"].place), ("needle", True, "src"))
        self.assertIn(src, new.work["files"].tree.expanded)
        self.assertEqual(new.views["files"].list.selected().path, src)
        self.assertEqual(self.handovers(), [])

    def test_the_tree_comes_back_scrolled_as_it_was(self):
        # the row chosen stays where it was on screen, not moved up to the top as a list one row high would put it
        for n in range(30):
            with open(os.path.join(self.root, f"f{n:02}.txt"), "w") as f:
                f.write("x\n")
        old = self.make()
        old.views["files"].list.resize(10)
        old.views["files"].select(os.path.join(old.root, "f12.txt"))
        top = old.views["files"].list.top
        old.hand_over()
        new = self.make()
        new.resume()
        new.views["files"].list.resize(10)                                  # its first draw, as tall as the old one
        self.assertEqual((new.views["files"].list.top, new.views["files"].list.selected().name), (top, "f12.txt"))

    def test_a_folder_away_from_the_first_row_narrows_the_search_after_an_update(self):
        # only you move the choice off the first row: after an update the folder chosen still narrows the search
        os.makedirs(os.path.join(self.root, "tools"))
        old = self.make()
        old.views["files"].select(os.path.join(old.root, "tools"))
        old.hand_over()
        new = self.make()
        new.resume()
        new.show("search")
        self.assertEqual(new.views["search"].place, "tools")

    def test_a_link_chosen_in_files_is_no_place_to_search(self):
        # a downloaded folder's link may lead out of it: the search stays on the whole folder
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside)
        os.symlink(outside, os.path.join(self.root, "zlink"))
        app = self.make()
        app.views["files"].select(os.path.join(app.root, "zlink"))
        app.views["files"].moved = True
        self.assertEqual(app.views["files"].list.selected().name, "zlink")
        self.assertEqual(app.work["files"].chosen_place(), "")

    def test_each_sidebar_gets_its_own_handover_back(self):
        # an update restarts every pane's sidebar at once, all with one state folder: none takes up another's
        other = self.make()
        self.app.views["changes"].set_message("feat: this pane's")
        other.views["changes"].set_message("fix: the other pane's")
        self.app.hand_over()
        mine = os.environ[loop.RESUME_ENV]                               # what its new version inherits
        other.hand_over()
        theirs = os.environ[loop.RESUME_ENV]
        for token, message in ((theirs, "fix: the other pane's"), (mine, "feat: this pane's")):
            os.environ[loop.RESUME_ENV] = token
            new = self.make()
            new.resume()
            self.assertEqual(new.views["changes"].field.text, message)
            self.assertNotIn(loop.RESUME_ENV, os.environ)               # nothing it starts inherits it
        self.assertEqual(self.handovers(), [])

    def test_a_fresh_start_takes_up_no_handover(self):
        # a sidebar started anew, not by an update, leaves another pane's handover to that pane
        self.app.views["changes"].set_message("feat: another pane's")
        self.app.hand_over()
        left = self.handovers()
        os.environ.pop(loop.RESUME_ENV)
        new = self.make()
        new.resume()
        self.assertEqual(new.views["changes"].field.text, "")
        self.assertEqual((len(left), self.handovers()), (1, left))

    def test_a_handover_a_closed_pane_left_behind_is_forgotten(self):
        self.app.hand_over()
        os.environ.pop(loop.RESUME_ENV)
        [fresh] = self.handovers()
        self.app.hand_over()
        os.environ.pop(loop.RESUME_ENV)
        [stale] = [name for name in self.handovers() if name != fresh]
        hour_ago = time.time() - loop.STALE - 1
        os.utime(os.path.join(self.state, stale), (hour_ago, hour_ago))
        self.make().resume()
        self.assertEqual(self.handovers(), [fresh])            # one coming this moment is another pane's: left

    def test_what_a_preview_tab_closed_otherwise_than_by_q_showed_goes_after_an_hour(self):
        # q deletes it; Cmd+W, or herdr started again, leave it: it names the last file previewed
        os.makedirs(self.state, exist_ok=True)
        old, fresh = (os.path.join(self.state, f"preview-w{n}.json") for n in (1, 2))
        issues = os.path.join(self.state, "issues-0123456789abcdef.json")      # a repository's issues, as last asked
        for path in (old, fresh, issues):
            with open(path, "w") as f:
                f.write("{}")
        hour_ago = time.time() - loop.STALE - 1
        os.utime(old, (hour_ago, hour_ago))
        os.utime(issues, (hour_ago, hour_ago))
        self.make().resume()
        self.assertEqual([os.path.exists(path) for path in (old, fresh, issues)], [False, True, False])

    def test_the_new_version_starts_in_the_same_pane(self):
        script = os.path.join(PLUGIN, "sidebar.py")
        with mock.patch.object(sidebar.os, "execv") as execv:
            sidebar.restart(["sidebar.py", "/some/folder"], windows=False)
        execv.assert_called_once_with(sys.executable, [sys.executable, "-B", script, "/some/folder"])
        # Windows' exec starts a new process and ends this one, which would give the pane's shell back meanwhile
        with mock.patch.object(sidebar.subprocess, "call", return_value=0) as call, self.assertRaises(SystemExit):
            sidebar.restart(["sidebar.py", "/some/folder"], windows=True)
        call.assert_called_once_with([sys.executable, "-B", script, "/some/folder"])


class FollowsItsFolder(Ticks, unittest.TestCase):
    """Its folder renamed or moved while it runs: it comes back on the folder's new place, where it was (a renamed
    folder keeps its identity); a deleted one leaves it as it is."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root, self.state = os.path.join(self.tmp, "old-name"), os.path.join(self.tmp, "state")
        os.makedirs(os.path.join(self.root, "src"))
        with open(os.path.join(self.root, "src", "app.py"), "w") as f:
            f.write("x = 1\n")
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull, HOME=os.path.join(self.tmp, "home"))
        self.addCleanup(os.environ.pop, loop.RESUME_ENV, None)
        self.addCleanup(os.chdir, os.getcwd())
        self.addCleanup(end_jobs)                       # the first cleanup: its ticks start jobs
        self.now = 1000.0
        self.app = sidebar.App(self.root, FakeTerminal(), preview.Herdr("/usr/bin/false"), self.state,
                               clock=lambda: self.now)

    def test_a_renamed_folder_brings_it_back_on_the_new_name_where_it_was(self):
        self.app.work["files"].tree.expanded.add(os.path.join(self.app.root, "src"))
        new = os.path.join(os.path.realpath(self.tmp), "new-name")
        os.rename(self.root, new)
        self.later()
        self.assertTrue(self.app.quit and self.app.restart)
        self.assertEqual(self.app.moved, new)
        with open(os.path.join(self.state, f"resume-{os.environ[loop.RESUME_ENV]}.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["expanded"], [os.path.join(new, "src")])

    def test_a_folder_moved_away_is_found_through_its_own_working_folder(self):
        os.chdir(os.path.join(self.root, "src"))           # where sidebar.sh starts it: the pane's folder
        os.makedirs(os.path.join(self.tmp, "elsewhere"))
        new = os.path.join(os.path.realpath(self.tmp), "elsewhere", "new-name")
        os.rename(self.root, new)
        self.later()
        self.assertEqual(self.app.moved, new)

    def test_a_deleted_folder_leaves_it_as_it_is(self):
        os.makedirs(os.path.join(self.tmp, "new-name"))     # made first: it cannot take the deleted one's identity
        shutil.rmtree(self.root)
        self.later()
        self.assertFalse(self.app.quit)
        self.assertIsNone(self.app.moved)

    def test_it_starts_again_on_the_new_folder(self):
        app = mock.Mock(moved="/work/new-name")
        app.run.return_value = True
        with mock.patch.object(sidebar, "App", return_value=app), mock.patch("keys_unix.UnixTerminal"), \
                mock.patch.object(sidebar, "restart") as restart:
            sidebar.main(["sidebar.py", "/work/old-name"])
        restart.assert_called_once_with(["sidebar.py", "/work/new-name"])


class NewWorkspace(unittest.TestCase):
    """New Workspace on a folder, once herdr-fold's Workspaces plugin is there: its folder picker opens on that folder,
    with the Claude / Codex toggle, as herdr's new button opens it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = os.path.join(self.tmp, "project")
        os.makedirs(os.path.join(self.root, "src"))
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull, HOME=os.path.join(self.tmp, "home"))
        self.calls = []

    def make(self, plugins):
        test = self

        class Herdr:
            def call(self, *args):
                test.calls.append(args)
                if args[:2] == ("plugin", "list"):
                    if plugins is None:
                        raise RuntimeError("no herdr")
                    return {"plugins": [{"plugin_id": plugin} for plugin in plugins]}
                return {}
        self.app = sidebar.App(self.root, FakeTerminal(), Herdr(), os.path.join(self.tmp, "state"))
        self.app.resume()                                       # what run() does first, the terminal taken
        self.settle()
        return self.app

    def settle(self):
        for thread in threading.enumerate():
            if thread.name.startswith("sidebar-"):
                thread.join(5)
        self.app.collect()

    def test_it_is_offered_once_herdr_folds_workspaces_plugin_is_there(self):
        self.assertTrue(self.make(["herdr-fold.sidebar", "herdr-fold.workspaces"]).views["files"].opens_workspace)
        self.assertFalse(self.make(["herdr-fold.sidebar", "herdr-fold.tab-layout"]).views["files"].opens_workspace)
        app = self.make(None)                                   # herdr not answering: nothing offered, no error shown
        self.assertFalse(app.views["files"].opens_workspace)
        self.assertIsNone(app.error)

    def test_it_opens_the_folder_picker_on_the_folder(self):
        app = self.make(["herdr-fold.workspaces"])
        folder = os.path.join(app.root, "src")
        app.act(Action("new_workspace", (folder,)), "files")
        self.settle()
        self.assertIn(("plugin", "pane", "open", "--plugin", "herdr-fold.workspaces", "--entrypoint", "new-workspace",
                       "--focus", "--env", f"HERDR_NEW_WORKSPACE_FOLDER={folder}"), self.calls)


class Terminal(Repo):
    def run_sidebar(self, *keys_):
        """sidebar.py in a pty; once it shows its folder, KEYS are typed half a second apart (a key given as (KEY,
        TEXT): once TEXT shows). What it shows is read all along (a full pty would stop it writing)."""
        pid, fd = pty.fork()
        if pid == 0:
            os.execv(sys.executable, [sys.executable, os.path.join(PLUGIN, "sidebar.py"), self.root])
        out = b""

        def read(seconds, until=None):
            nonlocal out
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline and not (until and until in out):
                if select.select([fd], [], [], 0.1)[0]:
                    try:
                        chunk = os.read(fd, 65536)
                    except OSError:
                        return
                    if not chunk:
                        return
                    out += chunk

        read(10, until=b"project")
        for key in keys_:
            key, until = key if isinstance(key, tuple) else (key, None)
            os.write(fd, key)
            if until:
                read(10, until=until.encode())
            else:
                read(0.5)
        read(3)
        ended = end_child(pid, fd, grace=10, read=read) is not None   # on a busy machine its threads end later
        return out.decode("utf-8", "replace"), ended

    def test_q_and_ctrl_c_give_the_terminal_back(self):
        for key in (b"q", b"\x03"):
            out, ended = self.run_sidebar(key)
            self.assertTrue(ended, out[-500:])
            self.assertIn("project", out)
            self.assertIn("\x1b[?1049l", out[out.index("project"):])

    def test_an_update_restarts_it_in_the_same_pane(self):
        # a copy of the sidebar runs; an update rewrites one of its files: the same process, the new code, the view
        # it was on drawn again, and Ctrl+C (q would be typed into the search) still gives the terminal back
        code = os.path.join(os.path.dirname(self.state), "code")
        shutil.copytree(PLUGIN, code, ignore=shutil.ignore_patterns("__pycache__"))
        pid, fd = pty.fork()
        if pid == 0:
            os.execv(sys.executable, [sys.executable, "-B", os.path.join(code, "sidebar.py"), self.root])
        out = bytearray()

        def read(seconds, until=None, start=0):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline and (until is None or until not in out[start:]):
                if select.select([fd], [], [], 0.1)[0]:
                    try:
                        out.extend(os.read(fd, 65536))
                    except OSError:
                        return

        try:
            read(10, b"project")
            os.write(fd, b"3")                                             # the search view, to come back to
            read(5, b"Aa")
            updated = len(out)
            with open(os.path.join(code, "watch.py"), "a") as f:
                f.write("\n# a new version\n")
            later = os.stat(os.path.join(code, "watch.py")).st_mtime_ns + 1_000_000_000
            os.utime(os.path.join(code, "watch.py"), ns=(later, later))
            read(20, b"\x1b[?1049h", updated)                              # the new one takes the screen
            restarted = out.find(b"\x1b[?1049h", updated)
            self.assertGreater(restarted, 0, bytes(out[-300:]))
            self.assertIn(b"\x1b[?1049l", out[updated:restarted])              # the old one gave it back first
            read(10, b"Aa", restarted)
            self.assertIn(b"Aa", out[restarted:])                             # its view handed over through the exec
            os.write(fd, b"\x03")
        finally:
            status = end_child(pid, fd, grace=5, read=read)
        self.assertEqual(status, 0)

    def test_quitting_does_not_wait_for_a_hanging_ai(self):
        subprocess.run(["git", "-C", self.root, "add", "a.txt"], check=True)
        out, ended = self.run_sidebar((b"4", "⎇"), b"A", b"q")                # A once Changes has the status
        self.assertIn("is writing the message", out)
        self.assertTrue(ended, out[-500:])


class Actions(Repo):
    def action(self, name, **env):
        return subprocess.run([sys.executable, os.path.join(PLUGIN, "actions.py"), name], capture_output=True,
                              text=True, env=dict(os.environ, **env))

    def test_show_git_sends_its_key_to_the_tabs_sidebar(self):
        out = self.action("show-git", HERDR_ACTIVE_TAB_ID="w1:t1")
        self.assertEqual(out.returncode, 0, out.stderr)
        with open(self.log) as f:
            self.assertIn("pane send-keys w1:p2 f11", f.read().splitlines())

    def test_show_issues_sends_f12(self):
        out = self.action("show-issues", HERDR_ACTIVE_TAB_ID="w1:t1")
        self.assertEqual(out.returncode, 0, out.stderr)
        with open(self.log) as f:
            self.assertIn("pane send-keys w1:p2 f12", f.read().splitlines())

    def test_select_all_goes_to_the_sidebar_only_when_it_has_the_keys(self):
        # as herdr runs a plugin action from a key: the focused pane in HERDR_PANE_ID, its tab in HERDR_TAB_ID
        out = self.action("select-all", HERDR_TAB_ID="w1:t1", HERDR_PANE_ID="w1:p2")
        self.assertEqual(out.returncode, 0, out.stderr)
        with open(self.log) as f:
            self.assertIn("pane send-keys w1:p2 f8", f.read().splitlines())
        os.remove(self.log)
        out = self.action("select-all", HERDR_TAB_ID="w1:t1", HERDR_PANE_ID="w1:p1")                  # the agent's
        self.assertEqual((out.returncode, out.stderr), (0, ""))
        self.assertFalse(any("send-keys" in line for line in logged(self.log)))

    def test_every_key_an_action_sends_is_one_the_sidebar_takes(self):
        taken = set(sidebar.VIEW_KEYS) | {sidebar.FIND, "f8"}                 # F8: Cmd + A in a field
        self.assertEqual(sorted(key for key in actions.KEYS.values() if key not in taken), [])

    def test_no_sidebar_in_the_tab_says_so(self):
        out = self.action("show-files", HERDR_ACTIVE_TAB_ID="w1:t9")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("no sidebar", out.stderr)

    class Herdr:
        """A workspace whose tabs t1 and t2 have a sidebar (p2, p5), t1 its terminal (p3); new panes new1, new2…"""

        def __init__(self):
            self.calls, self.made = [], 0
            self.listed = [{"pane_id": "w1:p2", "tab_id": "w1:t1", "label": "sidebar"},
                           {"pane_id": "w1:p3", "tab_id": "w1:t1", "label": "terminal"},
                           {"pane_id": "w1:p5", "tab_id": "w1:t2", "label": "sidebar"}]

        def call(self, *args):
            self.calls.append(args)
            if args[:2] == ("pane", "list"):
                return {"panes": self.listed}
            if args[:2] == ("pane", "split"):
                self.made += 1
                return {"pane": {"pane_id": f"new{self.made}"}}
            if args[:2] == ("pane", "rename") and args[2].startswith("new"):
                self.listed.append({"pane_id": args[2], "tab_id": "w1:t1", "label": args[3]})
            return {}

    def find(self, herdr, tab):
        focused = []
        return actions.find(herdr.call, tab, list(herdr.listed), self.state, focused.append), focused

    def test_find_gives_the_tabs_sidebar_f7_and_the_keys(self):
        herdr = self.Herdr()
        self.assertEqual(self.find(herdr, "w1:t2"), ("w1:p5", ["w1:p5"]))
        self.assertEqual(herdr.calls, [("pane", "send-keys", "w1:p5", sidebar.FIND)])

    def test_find_in_a_tab_without_a_sidebar_goes_to_the_workspaces_first(self):
        herdr = self.Herdr()                                                # w1:t4: the user's own shell tab
        self.assertEqual(self.find(herdr, "w1:t4"), ("w1:p2", ["w1:p2"]))
        self.assertEqual(herdr.calls, [("pane", "send-keys", "w1:p2", sidebar.FIND)])

    def test_find_brings_back_a_sidebar_closed_by_hand_on_its_conversations(self):
        panels.note(self.state, {"w1:t1": {"sidebar", "terminal"}})
        herdr = self.Herdr()
        herdr.listed.pop(0)                                                 # t1's sidebar closed by hand
        self.assertEqual(self.find(herdr, "w1:t1"), ("new1", ["new1"]))
        self.assertIn(("pane", "rename", "new1", "sidebar"), herdr.calls)
        self.assertNotIn(("pane", "send-keys", "new1", sidebar.FIND), herdr.calls)   # not started yet: its seed
        with open(preview.seed_file(self.state, "w1:t1")) as f:
            self.assertEqual(json.load(f), {"show": "conversations"})

    def test_a_seed_shows_conversations_with_the_keys(self):
        app = sidebar.App(self.root, FakeTerminal(45, 30), preview.Herdr(), self.state)
        app.take({"show": "conversations"})
        self.assertEqual(app.keyed(), "conversations")


if __name__ == "__main__":
    unittest.main()
