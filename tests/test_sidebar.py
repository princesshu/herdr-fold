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
from unittest import mock

from support import SRC, AppScreen, FakeHerdrSocket, FakeTerminal, end_child, end_jobs, logged, set_env, stubs

PLUGIN = os.path.join(SRC, "plugins", "sidebar")
sys.path.insert(0, PLUGIN)
import actions  # noqa: E402
import column  # noqa: E402
import commit_message  # noqa: E402
import loop  # noqa: E402
import panels  # noqa: E402
import preview  # noqa: E402
import screen  # noqa: E402
import sidebar  # noqa: E402
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

    def start(self, cols=45, rows=45):
        term = FakeTerminal(cols, rows)
        self.run_app(sidebar.App(self.root, term, preview.Herdr(), self.state), term)

    def row(self, part):
        return next((line for line in self.screen().splitlines() if part in line), "")

    def work(self, screen):
        """SCREEN from the Work group's head down: Changes or Issues, apart from Files above it."""
        top = self.app.slices.get("work", (len(screen), 0))[0]
        return "\n".join(screen.split("\n")[top:])


class Running(Harness):
    def setUp(self):
        super().setUp()
        self.start()

    def test_it_starts_on_the_files(self):
        self.until(lambda s: "project" in s and "a.txt" in s)
        self.assertNotIn(".hidden", self.screen())
        self.until(lambda s: self.row("a.txt").rstrip().endswith("M"))   # the temporary folder is behind a symlink

    def test_each_group_heads_its_tabs_the_shown_one_in_the_accent(self):
        self.until(lambda s: "project" in s and "Changes 2" in s)              # a.txt changed, new.txt new
        canvas, project, work = self.app.canvas, self.app.slices["project"][0], self.app.slices["work"][0]
        chats, files, changes = ("".join(ch for ch, _ in canvas.rows[y]) for y in (0, project, work))
        self.assertEqual((chats[3:16], files[3:16], changes[3:12]), ("Conversations", "Files  Search", "Changes 2"))
        styles = [canvas.rows[project][3][1], canvas.rows[project][10][1], canvas.rows[work][3][1],
                  canvas.rows[work][11][1]]
        self.assertEqual([(style.fg, style.bold) for style in styles],
                         [("accent", True), ("muted", False), ("accent", True), ("modified", False)])
        self.assertEqual(self.app.slices, {"conversations": (0, 15), "project": (15, 15), "work": (30, 15)})
        self.assertEqual(chats.rstrip()[-3:].strip(), "⋯")                    # the pane's own menu, at the first head
        self.assertNotIn("badge", {style.bg for _, style in canvas.rows[-1]})

    def test_the_heads_fit_whole_at_the_narrowest_and_a_tab_under_the_mouse_lights_up(self):
        self.until(lambda s: "project" in s)
        narrow = sidebar.App(self.root, FakeTerminal(sidebar.narrowest(self.app.tabs()), 30), preview.Herdr(),
                             self.state)                                 # as narrow as it goes
        narrow.draw()
        self.assertIn("Files  Search", "".join(ch for ch, _ in narrow.canvas.rows[narrow.slices["project"][0]]))
        head = self.app.slices["project"][0]
        self.assertEqual(self.app.canvas.rows[head][10][1].fg, "muted")
        self.term.type(Mouse("move", 10, head, 3))
        self.until(lambda s: self.app.canvas.rows[head][10][1].fg == "text")

    def test_a_panels_controls_are_tall_where_its_group_has_the_rows(self):
        self.stop()
        for rows in (45, 60):                                             # 15 rows a group, then 20
            with self.subTest(rows=rows):
                self.start(rows=rows)
                self.term.type(Key("f10"))
                self.until(lambda s: self.app.focus == "project" and "Search" in s)
                field = any(ch == "▄" and style.fg == "input" for row in self.app.canvas.rows for ch, style in row)
                self.assertEqual(field, self.app.slices["project"][1] - 1 >= screen.ROOMY)
                self.stop()

    def test_the_folder_name_and_its_tree_follow_the_head_without_a_gap(self):
        self.until(lambda s: "project" in s)
        rows, head = self.screen().split("\n"), self.app.slices["project"][0]
        self.assertIn("project", rows[head + 1])
        self.assertNotEqual(rows[head + 2].strip(), "")                          # the tree's first entry

    def test_a_click_gives_its_group_the_keys(self):
        self.until(lambda s: "project" in s)
        self.assertEqual(self.app.focus, "project")
        self.term.type(Mouse("press", 4, self.app.slices["work"][0] + 3, 0), Mouse("release", 4,
                       self.app.slices["work"][0] + 3, 0))
        self.until(lambda s: self.app.focus == "work")

    def test_a_key_reaches_the_group_with_the_keys_only(self):
        self.until(lambda s: "a.txt" in s)
        self.term.type(Key("f11"), Key("char", "."))                         # Changes has the keys: Files' hidden stay
        time.sleep(0.3)
        self.assertNotIn(".hidden", self.screen())
        self.term.type(Key("f9"), Key("char", "."))
        self.until(lambda s: ".hidden" in s)

    def test_a_group_folds_to_its_head_and_stays_so(self):
        self.until(lambda s: "project" in s)
        work = self.app.slices["work"][0]
        self.term.type(Mouse("press", 1, work, 0))
        self.until(lambda s: self.app.slices["work"] == (44, 1))
        with open(os.path.join(self.state, "dock.json")) as f:
            self.assertEqual(json.load(f)[os.path.realpath(self.root)]["folded"], ["work"])
        self.stop()
        self.start()
        self.until(lambda s: self.app.slices.get("work") == (44, 1))

    def test_a_head_held_and_dragged_moves_the_edge(self):
        self.until(lambda s: "project" in s)
        work = self.app.slices["work"][0]
        self.term.type(Mouse("press", 30, work, 0), Mouse("move", 30, work - 4, 0), Mouse("release", 30, work - 4, 0))
        self.until(lambda s: self.app.slices["work"] == (26, 19))
        with open(os.path.join(self.state, "dock.json")) as f:
            self.assertIn("weights", json.load(f)[os.path.realpath(self.root)])

    def test_a_name_in_use_is_a_line_not_a_crash(self):
        self.until(lambda s: "src" in s)
        self.term.type(Key("char", "n"), *keys("b.py"), Key("enter"))       # src is chosen, src/b.py is there
        self.until(lambda s: "already there: b.py" in s)
        self.assertTrue(self.thread.is_alive())

    def test_a_message_typed_while_the_ai_writes_is_kept_and_commits(self):
        with open(os.path.join(self.bin, "claude"), "w") as f:
            f.write(SLOW_AI)
        subprocess.run(["git", "-C", self.root, "add", "a.txt"], check=True)
        self.term.type(Key("char", "3"))
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
        self.term.type(Key("char", "3"))
        self.until(lambda s: "new.txt" in self.work(s))
        rows, work = self.screen().splitlines(), self.app.slices["work"][0]
        y = next(i for i, row in enumerate(rows) if i > work and "new.txt" in row)
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
        self.term.type(Key("char", "2"), *keys("needle"))
        self.until(lambda s: "1 result in 1 file" in s and "a needle here" in s)

    def test_search_covers_the_folder_or_file_you_chose_in_files(self):
        # the first row is chosen by itself and narrows nothing (test_search_after_a_pause)
        self.until(lambda s: "src" in s)
        self.term.type(Key("down"), Key("up"), Key("char", "2"), *keys("needle"))     # src, chosen by you
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
        self.term.type(Key("char", "3"))
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
            self.term.type(Key("char", "3"))
            self.until(lambda s: "a.txt" in self.work(s) and "new.txt" in self.work(s))   # the status read
            self.term.type(Key("char", "A"))                                 # nothing staged: it all goes in
            self.until(lambda s: "is writing the message" in s)
            self.term.type(Key("char", "1"))
            self.until(lambda s: "project" in s, timeout=1.0)                # the view answers meanwhile
            self.until(lambda s: "claude failed" in s, timeout=15)          # however busy the machine

    def test_a_commit_with_nothing_staged_takes_every_change(self):
        self.term.type(Key("char", "3"))
        self.until(lambda s: "a.txt" in self.work(s) and "new.txt" in self.work(s))
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
        self.term.type(Key("char", "2"), *keys("q1"))
        self.until(lambda s: "q1" in s)                                      # q and 1 went into the field
        self.term.type(Key("f11"))
        self.until(lambda s: self.app.focus == "work")
        self.term.type(Key("f9"))
        self.until(lambda s: self.app.focus == "project" and self.app.showing("files"))

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
        self.term.type(Key("char", "3"))
        self.until(lambda s: "a.txt" in s)
        self.term.type(Mouse("move", *self.region(lambda target: target == "suggest")))
        self.until(lambda s: " Write message " in s, timeout=3)
        self.term.type(Key("char", "x", ctrl=True))
        self.until(lambda s: "Write message" not in s)

    def test_a_files_icons_tell_what_they_do(self):
        self.term.type(Key("char", "3"))
        self.until(lambda s: "a.txt" in s)
        self.term.type(Mouse("move", *self.changed_row("a.txt")))
        self.term.type(Mouse("move", *self.region(lambda target: isinstance(target, tuple) and target[0] == "stage")))
        self.until(lambda s: " Stage " in s, timeout=3)

    def changed_row(self, name):
        """Where the Changes row of the file NAME starts, once it is drawn."""
        self.until(lambda s: name in self.work(s))
        work = self.app.slices["work"][0]
        y = next(y for y, line in enumerate(self.screen().splitlines()) if y > work and name in line)
        return next((x0, ry) for ry, x0, _, target in list(self.app.canvas.regions)
                    if ry == y and isinstance(target, tuple) and target[0] == "row")

    def test_a_changed_files_tip_is_its_whole_path_in_the_repository(self):
        self.write("src/b.py", "print('b, changed')\n")
        self.term.type(Key("char", "3"))
        self.term.type(Mouse("move", *self.changed_row("b.py")))
        self.until(lambda s: " src/b.py " in s, timeout=3)

    def test_a_name_files_cuts_short_shows_whole_under_the_mouse(self):
        name = "docs/the-release-checklist-for-every-version.md"           # its name cut in its row, whole in a tip
        os.makedirs(os.path.join(self.root, "docs"))
        self.write(name, "x\n")
        self.term.type(Key("char", "1"))
        self.until(lambda s: "docs" in s)
        self.term.type(Mouse("press", *self.region(lambda target: isinstance(target, tuple) and target[0] == "row"
                                                   and "docs" in self.row_text(target))))
        self.until(lambda s: "the-release" in s)
        self.term.type(Mouse("move", *self.region(lambda target: isinstance(target, tuple) and target[0] == "row"
                                                  and "the-release" in self.row_text(target))))
        self.until(lambda s: " docs/" in s and " the-release-checklist-for-every-version.md " in s, timeout=3)

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
        self.term.type(Key("char", "3"))
        self.term.type(Mouse("move", *self.changed_row("the-file.txt")))
        self.until(lambda s: " src/a-rather-long-folder-name/" in s
                   and " and-another-one/the-file.txt " in s, timeout=3)


class Message(Harness):
    """The commit message's field takes the mouse and the keys a text field does: a drag or Shift selects, and
    Backspace takes the selection whole."""

    def setUp(self):
        Repo.setUp(self)
        self.start()

    def typed(self, text):
        """TEXT typed as the message, once Changes shows: where its first line starts in the field."""
        self.term.type(Key("char", "3"))
        self.until(lambda s: "a.txt" in self.work(s))
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

    def on_github(self):
        subprocess.run(["git", "-C", self.root, "remote", "add", "origin", "git@github.com:acme/app.git"], check=True)

    def gh_calls(self):
        try:
            with open(self.gh_log) as f:
                return f.read().splitlines()
        except OSError:
            return []

    def tabs(self):
        """The panels' tabs on the heads: Issues among them only on GitHub."""
        heads = [self.screen().split("\n")[top] for top, _rows in self.app.slices.values()]
        return sum(PANEL in head for head in heads for PANEL in ("Files", "Search", "Changes", "Issues"))

    def test_a_repository_not_on_github_has_no_issues_tab(self):
        self.start()
        self.until(lambda s: "project" in s)
        self.assertEqual(self.tabs(), 3)
        self.term.type(Key("f12"), Key("char", "4"))
        time.sleep(0.3)
        self.assertEqual((self.app.focus, self.app.showing("issues")), ("project", False))
        self.assertEqual(self.gh_calls(), [])

    def test_a_repository_on_github_shows_its_issues(self):
        self.on_github()
        self.start()
        self.until(lambda s: "project" in s and self.tabs() == 4)
        self.term.type(Key("f12"))
        self.until(lambda s: "#42 Login fails on Safari" in s)
        self.assertTrue(any(call.startswith("issue list -R acme/app") for call in self.gh_calls()))

    def test_the_issues_are_asked_for_again_in_the_background(self):
        # a list with issues in it: one made elsewhere (on GitHub, in another tab) is there when the view is shown
        # again, as in an editor's list
        self.on_github()
        listed = lambda: [issue.number for issue in self.app.views["issues"].listing.issues]  # noqa: E731
        with mock.patch.object(sidebar, "STALE", 0.3):
            self.start()
            self.until(lambda s: "project" in s and self.tabs() == 4)
            self.term.type(Key("f12"))
            self.until(lambda s: "#42 Login fails on Safari" in s)
            self.term.type(Key("f9"))
            set_env(self, GH_ISSUES=TWO_ISSUES)                 # the second issue, made on GitHub
            self.until(lambda s: listed() == [43, 42])
            self.assertEqual(self.app.focus, "project")
            self.stop()                                         # its last question done while it is still this quick

    def test_never_looked_at_they_are_never_asked_for(self):
        # a repository whose issues were never shown here (a stranger's clone): gh is not run for its remote
        self.on_github()
        with mock.patch.object(sidebar, "STALE", 0.3):
            self.start()
            self.until(lambda s: "project" in s and self.tabs() == 4)
            time.sleep(1.5)
            self.assertEqual([call for call in self.gh_calls() if call.startswith("issue")], [])

    def test_an_empty_list_is_asked_for_only_on_screen(self):
        # a repository with no issues: gh runs while the view is shown, never behind it; the first one made shows up,
        # and from then on the list is kept fresh behind it too
        self.on_github()
        set_env(self, GH_ISSUES="[]")
        lists = lambda: len([call for call in self.gh_calls() if call.startswith("issue list")])  # noqa: E731
        with mock.patch.object(sidebar, "STALE", 0.3):
            self.start()
            self.until(lambda s: "project" in s and self.tabs() == 4)
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
        self.until(lambda s: "project" in s and self.tabs() == 4)
        self.term.type(Key("f12"))
        self.until(lambda s: "#42 Login fails on Safari" in s and lists() == 1)
        other = sidebar.App(self.root, FakeTerminal(), preview.Herdr(), self.state)
        other.github = "acme/app"
        other.fresh_issues(sidebar.STALE)
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
            json.dump({os.path.realpath(self.root): {"shown": {"work": "issues"}}}, f)
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

    def test_four_tabs_and_the_dots_fit_at_the_narrowest_never_shrunk(self):
        self.on_github()
        self.start(cols=column.NARROWEST)
        self.until(lambda s: "project" in s and self.tabs() == 4)
        rows = self.screen().split("\n")
        self.assertTrue(rows[0].rstrip().endswith("⋯"))
        self.assertIn("Issues", rows[self.app.slices["work"][0]])

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
        self.term.type(Key("char", "3"))
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
        self.term.type(Key("char", "3"))
        self.until(lambda s: "Not a git repository" in s)

    def test_the_repository_of_the_folder_chosen_in_files_shows(self):
        self.choose_lib()
        self.term.type(Key("char", "3"))
        self.until(lambda s: "lib.txt" in s and "lib" in self.row("⎇"), timeout=10)     # the repository row
        self.assertNotIn("app.txt", self.screen())

    def test_its_commit_goes_into_that_repository(self):
        self.choose_lib()
        self.term.type(Key("char", "3"))
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
    """A right click on the sidebar's header or status bar: its own menu, each of the tab's other panes closed or shown
    back."""

    class Herdr:
        def call(self, *args):
            return {"panes": [{"pane_id": "w1:p1", "tab_id": "w1:t1", "label": "claude"},
                              {"pane_id": "w1:p2", "tab_id": "w1:t1", "label": "sidebar"}]} if args[:2] == (
                "pane", "list") else {}

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_env(self, HERDR_PANE_ID="w1:p2", HOME=self.tmp)
        self.brought = []
        self.app = sidebar.App(self.tmp, FakeTerminal(45, 30), self.Herdr(), os.path.join(self.tmp, "state"))

    def test_it_offers_the_other_panes_and_brings_the_one_chosen(self):
        self.app.draw()
        self.app.handle(Mouse("press", 40, 0, 2))                        # the header, past the view buttons
        self.assertEqual(self.app.menu[0].choices, ["Show terminal", "Restore panels"])
        self.app.draw()
        with mock.patch.object(sidebar.panes, "bring",
                               lambda call, tab, kinds, state_dir: self.brought.append((tab, set(kinds)))):
            self.app.handle(Key("enter"))
            end_jobs()
        self.assertEqual(self.brought, [("w1:t1", {"terminal"})])
        self.assertIsNone(self.app.menu)

    def menu_rows(self):
        """The menu's choices, as drawn."""
        self.app.draw()
        rows = ["".join(ch for ch, _ in row) for row in self.app.canvas.rows]
        return [m.group(1).strip() for m in (re.search(r"│([^│]+)│", row) for row in rows) if m]

    def test_the_dots_at_the_headers_right_edge_open_it(self):
        self.app.draw()
        dots = "".join(ch for ch, _ in self.app.canvas.rows[0]).index("⋯")
        self.app.handle(Mouse("press", dots, 0, 0))                         # a left click
        self.assertEqual(self.menu_rows(), ["Show terminal", "Restore panels"])
        rows = ["".join(ch for ch, _ in row) for row in self.app.canvas.rows]
        top = next(y for y, row in enumerate(rows) if "┌" in row)
        self.assertEqual(top, 1)                                           # right under the ⋯ (one row high)
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
        self.app.handle(Mouse("press", 40, 0, 2))
        self.assertEqual(self.app.menu[0].choices[-2:], ["herdr-fold 0.3.0", "✓ Check for Updates"])
        self.app.handle(Key("up"))
        self.app.handle(Key("enter"))
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
        self.app.handle(Mouse("press", 40, 0, 2))
        self.assertIsNotNone(self.app.menu)
        self.app.handle(Focus(False))
        self.assertIsNone(self.app.menu)
        files = self.app.views["files"]
        files.open_menu(None, 5, 5)
        self.app.handle(Focus(True))                                        # back in the pane: nothing closes
        self.assertIsNotNone(files.menu)
        self.app.handle(Focus(False))
        self.assertIsNone(files.menu)

    def test_a_click_on_the_header_closes_the_views_menu(self):
        self.app.draw()
        files = self.app.views["files"]
        files.open_menu(None, 5, 5)
        self.app.handle(Mouse("press", 40, 0, 2))                        # the pane's own menu instead
        self.assertIsNone(files.menu)
        self.assertIsNotNone(self.app.menu)
        self.app.handle(Key("esc"))
        files.open_menu(None, 5, 5)
        head = self.app.slices["project"][0]
        search = next(x for x in range(45) if self.app.canvas.hit(x, head) == "tab:search")
        self.app.handle(Mouse("press", search, head, 0))                 # another panel: the menu not kept behind
        self.assertTrue(self.app.showing("search"))
        self.assertIsNone(files.menu)

    def test_a_right_click_on_a_tab_opens_it_and_leaves_the_panel_shown(self):
        self.app.draw()
        self.app.handle(Mouse("press", 10, self.app.slices["project"][0], 2))   # Search's tab
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
        self.app.handle(Mouse("press", 40, 0, 2))
        self.assertEqual(self.menu_rows(), ["Close terminal"])                             # not itself
        self.app.handle(Key("enter"))
        deadline = time.monotonic() + 5
        while ("pane", "close", "w1:p3") not in calls and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertIn(("pane", "close", "w1:p3"), calls)                    # as closed by hand: it stays closed
        self.assertIsNone(self.app.menu)


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
        self.app.act(Action("remember_folded", (["graph"],)))
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
        self.app.tree.toggle(src)
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
        self.assertEqual((new.focus, new.showing("search")), ("project", True))
        self.assertEqual(new.views["changes"].field.text, "feat: half written")
        self.assertEqual((new.views["search"].field.text, new.views["search"].switches["case"],
                          new.views["search"].place), ("needle", True, "src"))
        self.assertIn(src, new.tree.expanded)
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
        self.assertEqual(app.chosen_place(), "")

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
        self.app.tree.expanded.add(os.path.join(self.app.root, "src"))
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
    """New Workspace on a folder, once herdr-fold's tab layout is there: its folder picker opens on that folder, with
    the Claude / Codex toggle, as herdr's new button opens it."""

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

    def test_it_is_offered_once_herdr_folds_tab_layout_is_there(self):
        self.assertTrue(self.make(["herdr-fold.sidebar", "herdr-fold.tab-layout"]).views["files"].opens_workspace)
        self.assertFalse(self.make(["herdr-fold.sidebar"]).views["files"].opens_workspace)
        app = self.make(None)                                   # herdr not answering: nothing offered, no error shown
        self.assertFalse(app.views["files"].opens_workspace)
        self.assertIsNone(app.error)

    def test_it_opens_the_folder_picker_on_the_folder(self):
        app = self.make(["herdr-fold.tab-layout"])
        folder = os.path.join(app.root, "src")
        app.act(Action("new_workspace", (folder,)))
        self.settle()
        self.assertIn(("plugin", "pane", "open", "--plugin", "herdr-fold.tab-layout", "--entrypoint", "new-workspace",
                       "--focus", "--env", f"HERDR_NEW_WORKSPACE_FOLDER={folder}"), self.calls)


class Terminal(Repo):
    def run_sidebar(self, *keys_):
        """sidebar.py in a pty; once it shows the branch, KEYS are typed half a second apart. What it shows is read
        all along (a full pty would stop it writing)."""
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

        read(10, until="⎇".encode())
        for key in keys_:
            os.write(fd, key)
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
            read(10, "⎇".encode())
            os.write(fd, b"2")                                             # the search view, to come back to
            read(5, b"Search")
            updated = len(out)
            with open(os.path.join(code, "watch.py"), "a") as f:
                f.write("\n# a new version\n")
            later = os.stat(os.path.join(code, "watch.py")).st_mtime_ns + 1_000_000_000
            os.utime(os.path.join(code, "watch.py"), ns=(later, later))
            read(20, b"\x1b[?1049h", updated)                              # the new one takes the screen
            restarted = out.find(b"\x1b[?1049h", updated)
            self.assertGreater(restarted, 0, bytes(out[-300:]))
            self.assertIn(b"\x1b[?1049l", out[updated:restarted])              # the old one gave it back first
            read(10, "⎇".encode(), restarted)
            self.assertIn(b"Search", out[restarted:])                         # its view handed over through the exec
            os.write(fd, b"\x03")
        finally:
            status = end_child(pid, fd, grace=5, read=read)
        self.assertEqual(status, 0)

    def test_quitting_does_not_wait_for_a_hanging_ai(self):
        subprocess.run(["git", "-C", self.root, "add", "a.txt"], check=True)
        out, ended = self.run_sidebar(b"3", b"A", b"q")
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
        self.assertEqual(app.focus, "conversations")


if __name__ == "__main__":
    unittest.main()
