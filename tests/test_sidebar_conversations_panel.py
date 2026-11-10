"""Tests for the sidebar's Conversations panel (conversations_panel.py, conversation_list.py) with a stand-in
terminal and a fake herdr: the list in the first group; going to, reopening, archiving, naming, copying one."""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

from support import SRC, AppScreen, FakeTerminal, end_jobs, jsonl, logged, set_attrs, set_env, stubs

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import conversations  # noqa: E402
import conversations_panel  # noqa: E402
import panes  # noqa: E402
import preview  # noqa: E402
import sidebar  # noqa: E402
from icons import glyphs  # noqa: E402
from vt import Focus, Key, Mouse  # noqa: E402

sys.path.insert(0, os.path.join(SRC, "plugins", "sessions-view"))
import sessions  # noqa: E402

FAKE_HERDR = """#!/bin/sh
printf '%s\\n' "$*" >> "$HERDR_LOG"
case "$1 $2" in
  "agent list") echo '{"result": {"agents": [{"pane_id": "w1:p1", "tab_id": "w1:t1", "agent": "claude",
                       "agent_status": "working", "cwd": "/repo/app", "agent_session": {"value": "s1"}}]}}' ;;
  "workspace list") echo '{"result": {"workspaces": [{"workspace_id": "w2", "label": "docs", "number": 2,
                           "agent_status": "idle"}, {"workspace_id": "w1", "label": "app", "number": 1,
                           "active_tab_id": "w1:t1", "agent_status": "working"}]}}' ;;
  "pane list") echo '{"result": {"panes": [{"pane_id": "w1:p1", "workspace_id": "w1", "cwd": "/repo/app"}]}}' ;;
  "tab create") echo '{"result": {"tab": {"tab_id": "w1:t3"}, "root_pane": {"pane_id": "w1:p9"}}}' ;;
  "tab get") echo '{"result": {"tab": {"tab_id": "w1:t1", "number": 2, "label": "2"}}}' ;;
  "pane get") echo '{"result": {"pane": {"pane_id": "w1:p10", "tab_id": "w1:t3"}}}' ;;
  "pane split") echo '{"result": {"pane": {"pane_id": "w1:p10"}}}' ;;
  *) echo '{"result": {}}' ;;
esac
"""
LOOKS = ("agent list", "workspace list", "pane list", "plugin list")    # what the sidebar asks again and again


class Panel(AppScreen, unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.home, self.log, self.state = os.path.join(tmp, "home"), os.path.join(tmp, "herdr.log"), os.path.join(
            tmp, "state")
        self.root = os.path.join(tmp, "project")
        os.makedirs(self.root)
        fakes = stubs(os.path.join(tmp, "bin"), {"herdr": FAKE_HERDR})
        set_env(self, HOME=self.home, HERDR_LOG=self.log, HERDR_WORKSPACE_ID="w1",
                HERDR_BIN_PATH=os.path.join(fakes, "herdr"), GIT_CONFIG_GLOBAL=os.devnull)
        self.addCleanup(end_jobs)                       # the first cleanup: a test's own tick starts jobs too
        now = time.time()
        self.claude("s1", "/repo/app", "Fix the login", now - 60)
        self.claude("s2", "/repo/app", "Price list", now - 3600)
        self.claude("s3", "/elsewhere", "Old notes", now - 86400)

    def claude(self, session, folder, text, changed):
        path = os.path.join(self.home, ".claude", "projects", folder.replace("/", "-"), f"{session}.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(jsonl({"type": "user", "isSidechain": False, "cwd": folder, "message": {"content": text}}))
        os.utime(path, (changed, changed))

    def make(self, herdr=None, **more):
        return sidebar.App(self.root, FakeTerminal(40, 40), herdr or preview.Herdr(), self.state, **more)

    def start(self):
        term = FakeTerminal(40, 40)
        self.run_app(sidebar.App(self.root, term, preview.Herdr(), self.state), term)
        self.until(lambda s: "Price list" in s)

    def listed(self):
        """The Conversations group's rows under its filter, as shown."""
        top, rows = self.app.slices["conversations"]
        lines = self.screen().splitlines()[top:top + rows]
        start = next(n for n, line in enumerate(lines) if "Filter" in line) + 2
        return [line.strip() for line in lines[start:] if line.strip()]

    def calls_after(self, first):
        """The herdr calls from the first one starting FIRST on, waited for until the tab is focused; the LOOKS left
        out."""
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            calls = [call for call in logged(self.log) if not call.startswith(LOOKS)]
            starts = [n for n, call in enumerate(calls) if call.startswith(first)]
            if starts and any(call.startswith("tab focus") for call in calls[starts[0]:]):
                return calls[starts[0]:]
            time.sleep(0.05)
        self.fail(f"no {first} call: {logged(self.log)}")

    def choose(self, row, choice):
        """CHOICE of the right click's menu on the row that shows ROW."""
        y = next(n for n, shown in enumerate(self.screen().splitlines()) if row in shown)
        self.term.type(Mouse("press", 5, y, 2))
        self.until(lambda s: any(f"│{choice} " in line for line in s.splitlines()[y + 1:]))
        at = next(n for n, line in enumerate(self.screen().splitlines()) if n > y and f"│{choice} " in line)
        self.term.type(Mouse("press", 7, at, 0))

    def test_the_first_group_lists_the_spaces_in_their_order_their_conversations_under_them(self):
        self.start()
        self.assertEqual(self.app.slices["conversations"][0], 0)
        shown = self.listed()
        self.assertEqual((shown[0].split()[1], shown[0][-1]), ("app", glyphs(True)["open"]), shown)   # this pane's
        self.assertTrue(shown[1].startswith("├─ ● Fix the login"), shown)
        self.assertTrue(shown[2].startswith("└─ · Price list"), shown)
        self.assertEqual(shown[3].split(), ["○", "docs", "0", glyphs(True)["closed"]], shown)   # an idle agent
        self.assertNotIn("Old notes", self.screen())                        # /elsewhere: no workspace has it

    def test_a_running_one_is_gone_to(self):
        self.start()
        self.assertEqual(self.app.focus, "project")                         # the keys start with Files
        self.term.type(Key(sidebar.FIND), Key("down"), Key("enter"))
        deadline = time.monotonic() + 5
        while "agent focus w1:p1" not in logged(self.log) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertIn("agent focus w1:p1", logged(self.log))

    def test_the_conversation_of_the_active_tab_leads_though_another_was_written_to_later(self):
        self.claude("s2", "/repo/app", "Price list", time.time())             # reopened and closed a moment ago
        self.start()
        self.until(lambda s: s.index("Fix the login") < s.index("Price list"))

    def test_find_opens_the_group_empties_its_filter_and_gives_it_the_keys(self):
        self.start()
        self.term.type(Key("f9"), Mouse("press", 1, 0, 0))                    # Files has the keys, the group folded
        self.until(lambda s: self.app.slices["conversations"][1] == 1 and self.app.focus == "project")
        self.app.views["conversations"].field.insert("zzz")
        self.term.type(Key(sidebar.FIND))
        self.until(lambda s: self.app.focus == "conversations" and "Price list" in s)
        self.assertEqual(self.app.views["conversations"].typed, "")

    def test_fold_shuts_the_group_and_opens_it_again(self):
        self.start()
        self.term.type(Key(sidebar.FOLD))
        self.until(lambda s: self.app.slices["conversations"][1] == 1)
        self.term.type(Key(sidebar.FOLD))
        self.until(lambda s: "Price list" in s)

    def test_copy_conversation_puts_the_whole_conversation_on_the_clipboard(self):
        path = os.path.join(self.home, ".claude", "projects", "-repo-app", "s2.jsonl")
        with open(path, "a") as f:
            f.write(jsonl({"type": "assistant", "message": {"content": [{"type": "text", "text": "**Done.**"}]}}))
        work, copied = self.make().work["conversations"], []
        work.clipboard = lambda text: copied.append(text) or True
        set_attrs(self, sys.modules["richtext"], copy_rich=lambda markdown, plain: copied.append("formatted"))
        item = conversations.Conversation("claude", "s2", "Price list", "/repo/app", 0)
        self.assertIsNone(work.copy(item))
        self.assertEqual(copied[0], "# Price list\n\n**You**\n\nPrice list\n\n**Claude**\n\n**Done.**\n")
        self.assertEqual(copied[1:], ["formatted"] if sys.platform == "darwin" else [])

    def test_archive_takes_a_closed_one_off_the_list_in_every_tab_and_back(self):
        self.start()
        self.choose("Price list", "Archive")
        self.until(lambda s: "Price list" not in s and "Archived" in s)
        self.assertEqual(conversations.archived(self.state), {"claude:s2"})
        with open(os.path.join(self.home, ".claude", "projects", "-repo-app", "s2.jsonl"), encoding="utf-8") as f:
            self.assertIn("Price list", f.read())                  # its file as it was: resumable as before
        self.term.type(*[Key("char", ch) for ch in "archived"])
        self.until(lambda s: "Price list" in s)
        self.choose("Price list", "Unarchive")
        self.until(lambda s: "Back in the list" in s)
        self.assertEqual(conversations.archived(self.state), set())

    def test_the_marked_ones_are_archived_together(self):
        self.claude("s4", "/repo/app", "Draft notes", time.time() - 7200)
        self.start()
        self.until(lambda s: "Draft notes" in s)
        self.term.type(Key(sidebar.FIND), Key("down"), Key("down"), Key("char", " "),
                       Key("down", shift=True))                              # Price list, Draft notes
        y = next(n for n, shown in enumerate(self.screen().splitlines()) if "Draft notes" in shown)
        self.term.type(Mouse("press", 12, y, 2))
        self.until(lambda s: "Archive 2 conversations" in s.splitlines()[y + 1])
        self.term.type(Mouse("press", 14, y + 1, 0))
        self.until(lambda s: "Price list" not in s and "Draft notes" not in s and "2 archived" in s)
        self.assertEqual(conversations.archived(self.state), {"claude:s2", "claude:s4"})

    def names(self):
        with open(os.path.join(self.home, ".local", "state", "herdr", "plugins", "herdr-fold.sessions-view",
                               "names.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_rename_names_a_running_one_and_its_pane(self):
        self.start()
        self.choose("Fix the login", "Rename")
        self.term.type(*[Key("backspace")] * len("login"), *[Key("char", ch) for ch in "signup"], Key("enter"))
        self.until(lambda s: "Fix the signup" in s and "Renamed" in s)
        self.assertIn("pane rename w1:p1 Fix the signup", logged(self.log))       # AI Sessions shows it too
        self.assertIn("tab rename w1:t1 Fix the signup", logged(self.log))        # the tab it has to itself
        self.assertEqual(self.names(), {"s1": {"name": "Fix the signup", "given": False}})

    def test_own_tab_is_the_tab_a_conversation_has_to_itself(self):
        def herdr(agents, number):
            return lambda *args: ({"agents": agents} if args[:2] == ("agent", "list")
                                  else {"tab": {"tab_id": args[2], "number": number}})
        alone = [{"pane_id": "w1:p1", "tab_id": "w1:t2"}, {"pane_id": "w1:p5", "tab_id": "w1:t3"}]
        shared = alone + [{"pane_id": "w1:p6", "tab_id": "w1:t2"}]
        self.assertEqual(conversations_panel.own_tab(herdr(alone, 2), "w1:p1"), "w1:t2")
        self.assertIsNone(conversations_panel.own_tab(herdr(alone, 1), "w1:p1"))      # the main tab: the workspace's
        self.assertIsNone(conversations_panel.own_tab(herdr(shared, 2), "w1:p1"))
        self.assertIsNone(conversations_panel.own_tab(herdr(alone, 2), "w1:p9"))      # no agent there any more

    def test_a_tab_is_named_as_the_sessions_list_names_it(self):
        for name in ("Price list", "Colors of fruits and vegetables in spring", "x" * conversations_panel.TAB_NAME):
            self.assertEqual(conversations_panel.tab_name(name), sessions.tab_name(name))

    def test_rename_names_a_closed_one(self):
        self.start()
        self.choose("Price list", "Rename")
        self.term.type(*[Key("char", ch) for ch in " 2027"], Key("enter"))
        self.until(lambda s: "Price list 2027" in s)
        self.assertEqual(self.names(), {"s2": {"name": "Price list 2027", "given": False}})
        self.assertEqual([call for call in logged(self.log) if call.startswith("pane rename")], [])

    def test_show_archived_in_one_tab_shows_them_in_every_tab(self):
        self.start()
        conversations.archive(self.state, {"claude:s2"})                 # archived in another tab
        self.until(lambda s: "Fix the login" in s and "Price list" not in s)
        conversations.keep(self.state, show_archived=True)                # Show archived in another tab
        self.until(lambda s: "Price list" in s and "archived" in s)
        self.choose("Price list", "Unarchive")
        self.until(lambda s: "Back in the list" in s)

    class Recorder:
        """herdr, answering only what a reopen needs: the new tab, its splits."""
        def __init__(self):
            self.calls = []

        def call(self, *args):
            self.calls.append(args)
            if args[:2] == ("tab", "create"):
                return {"root_pane": {"pane_id": "w1:p9"}, "tab": {"tab_id": "w1:t3"}}
            if args[:2] in (("pane", "split"), ("pane", "get")):
                return {"pane": {"pane_id": "w1:p10", "tab_id": "w1:t3"}}
            return {}

    def reopen(self, item):
        herdr = self.Recorder()
        work = self.make(herdr).work["conversations"]
        work.folders = {"/repo/app": "w1"}
        work.reopen(item)
        return herdr.calls

    def test_a_reopened_conversations_title_is_a_clean_label(self):
        # a title comes from a transcript: an escape code in it, or a leading dash herdr's command line takes for an
        # option, never reaches the tab's label or the pane's name
        set_attrs(self, conversations, manual_names=lambda: {"s2": "\x1b]52;c;ZXZpbA==\x07-rf list"})
        title = "\x1b]52;c;ZXZpbA==\x07-rf list"
        calls = self.reopen(conversations.Conversation("claude", "s2", title, "/repo/app", 0))
        create = next(c for c in calls if c[:2] == ("tab", "create"))
        names = [c[3] for c in calls if c[:2] == ("pane", "rename")]
        for label in [create[create.index("--label") + 1]] + names:
            self.assertTrue(label.isprintable() and not label.startswith("-"), label)

    def test_an_id_that_could_be_an_option_reopens_nothing(self):
        for bad in ("-x", "a b", "s2\x07"):
            with self.assertRaises(RuntimeError):
                self.reopen(conversations.Conversation("claude", bad, "Price list", "/repo/app", 0))

    def test_a_closed_one_reopens_in_a_new_tab_of_its_workspace_with_the_right_column(self):
        noted = []
        set_attrs(self, panes, resume=lambda state_dir, pane, id: noted.append((pane, id)))
        self.start()
        self.term.type(Key(sidebar.FIND), Key("down"), Key("down"), Key("enter"))
        calls = self.calls_after("tab create")
        self.assertEqual(calls, [
            "tab create --workspace w1 --cwd /repo/app --label Price list --no-focus",
            "pane rename w1:p9 claude",
            # the right column off the agent (the fake names every new pane w1:p10)
            "pane split --pane w1:p9 --direction right --ratio 0.75 --cwd /repo/app --no-focus",
            "pane split --pane w1:p10 --direction down --ratio 0.5 --cwd /repo/app --no-focus",
            "pane rename w1:p10 terminal",
            "pane rename w1:p10 sidebar",
            f"pane run w1:p10 {panes.sidebar_command()}",
            "pane get w1:p10",
            "agent start claude-s2 --kind claude --pane w1:p9 --timeout 60000 -- --resume s2",
            "tab focus w1:t3"])
        self.assertEqual(noted, [("w1:p9", "s2")])                 # its row marked before herdr knows the session

    def test_a_reopened_ones_pane_is_forgotten_once_herdr_knows_its_session(self):
        panes.resume(self.state, "w1:p1", "s1")                # herdr knows w1:p1's session
        panes.resume(self.state, "w1:p7", "s2")                # no agent there any more
        self.start()
        deadline = time.monotonic() + 5
        while panes.resumed(self.state) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(panes.resumed(self.state), {})

    def test_a_click_in_another_pane_closes_its_menu(self):
        app = self.make(self.Recorder())
        closed = []
        set_attrs(self, app.views["conversations"], close_menu=lambda: closed.append(True))
        app.handle(Focus(True))
        app.handle(Focus(False))
        self.assertEqual(closed, [True])

    def test_a_new_version_takes_over_between_two_looks(self):
        # a look every second runs herdr: the handover comes before the next one starts, never with one running
        code = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, code)
        path = os.path.join(code, "a.py")
        with open(path, "w") as f:
            f.write("x = 1\n")
        now = [1000.0]
        app = self.make(self.Recorder(), clock=lambda: now[0], code=code)
        with open(path, "a") as f:
            f.write("y = 2\n")
        mtime = os.stat(path).st_mtime_ns + 1_000_000_000                  # newer, however coarse the file system
        os.utime(path, ns=(mtime, mtime))
        for _ in range(4):
            for thread in threading.enumerate():                            # each look answered, as the loop collects
                if thread.name.startswith("sidebar-"):
                    thread.join(5)
            app.collect()
            now[0] += 5
            app.tick()
            if app.quit:
                break
        self.assertTrue(app.restart)
        self.assertNotIn("read", app.running)                              # no look of its own left running


if __name__ == "__main__":
    unittest.main()
