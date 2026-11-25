"""Tests for the sidebar's Chats list (chats_panel.py, chat_list.py) with a stand-in
terminal and a fake herdr: the list the ✦ opens over the sidebar; going to, reopening, archiving, naming, copying
one."""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from support import SRC, AppScreen, FakeTerminal, end_jobs, jsonl, logged, set_attrs, set_env, stubs

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import chats          # noqa: E402
import chats_panel          # noqa: E402
import fileops  # noqa: E402
import panes  # noqa: E402
import plan  # noqa: E402
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

    def start(self, chats=True):
        """The sidebar running, its chats read; with CHATS their list open (F7), else on Files, as it starts."""
        term = FakeTerminal(40, 40)
        self.run_app(sidebar.App(self.root, term, preview.Herdr(), self.state), term)
        if chats:
            self.term.type(Key(sidebar.FIND))
            self.until(lambda s: "Price list" in s)
        else:
            self.until(lambda s: "Price list" in [item.title for item in self.app.views["chats"].items or []])

    def listed(self):
        """The list's rows under its filter, as shown."""
        top, left, bottom, right = self.app.box
        lines = [line[left:right + 1] for line in self.screen().splitlines()[top + 1:bottom + 1]]
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
        self.until(lambda s: any(f"│ {choice} " in line for line in s.splitlines()[y + 1:]))
        at = next(n for n, line in enumerate(self.screen().splitlines()) if n > y and f"│ {choice} " in line)
        self.term.type(Mouse("press", 7, at, 0))

    def test_it_lists_the_spaces_with_chats_in_their_order_their_chats_under_them(self):
        self.start()
        self.assertEqual(self.app.box[0], self.app.body[0])              # in the view's place, under the blank row
        shown = self.listed()
        self.assertEqual(shown[0].split(), [glyphs(True)["open"], "app", "2"], shown)       # this pane's
        self.assertTrue(shown[1].startswith("● Fix the login"), shown)
        self.assertTrue(shown[2].startswith("· Price list"), shown)
        self.assertEqual(len(shown), 3, shown)                              # docs has no chat: not listed
        self.assertNotIn("Old notes", self.screen())                        # /elsewhere: no workspace has it

    def test_a_running_one_is_gone_to(self):
        self.start(chats=False)
        self.assertEqual(self.app.keyed(), "files")                         # the keys start with Files
        self.term.type(Key(sidebar.FIND), Key("down"), Key("enter"))
        deadline = time.monotonic() + 5
        while "agent focus w1:p1" not in logged(self.log) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertIn("agent focus w1:p1", logged(self.log))

    def test_the_chat_of_the_active_tab_leads_though_another_was_written_to_later(self):
        self.claude("s2", "/repo/app", "Price list", time.time())             # reopened and closed a moment ago
        self.start()
        self.until(lambda s: s.index("Fix the login") < s.index("Price list"))

    def test_find_opens_the_list_empties_its_filter_and_gives_it_the_keys(self):
        self.start()
        self.term.type(Key("f9"))                                             # closed: Files shown, with the keys
        self.until(lambda s: self.app.keyed() == "files" and "Price list" not in s)
        self.app.views["chats"].field.insert("zzz")
        self.term.type(Key(sidebar.FIND))
        self.until(lambda s: self.app.keyed() == "chats" and "Price list" in s)
        self.assertEqual(self.app.views["chats"].typed, "")

    def test_copy_chat_puts_the_whole_chat_on_the_clipboard(self):
        path = os.path.join(self.home, ".claude", "projects", "-repo-app", "s2.jsonl")
        with open(path, "a") as f:
            f.write(jsonl({"type": "assistant", "message": {"content": [{"type": "text", "text": "**Done.**"}]}}))
        work, copied = self.make().work["chats"], []
        work.clipboard = lambda text: copied.append(text) or True
        set_attrs(self, sys.modules["richtext"], copy_rich=lambda markdown, plain: copied.append("formatted"))
        item = chats.Chat("claude", "s2", "Price list", "/repo/app", 0)
        self.assertIsNone(work.copy(item))
        self.assertEqual(copied[0], "# Price list\n\n**You**\n\nPrice list\n\n**Claude**\n\n**Done.**\n")
        self.assertEqual(copied[1:], ["formatted"] if sys.platform == "darwin" else [])

    def test_the_chosen_chats_plan_is_read_on_and_its_approved_plan_opens_in_the_preview(self):
        path = os.path.join(self.home, ".claude", "projects", "-repo-app", "s2.jsonl")
        task = {"type": "tool_use", "id": "k1", "name": "TaskCreate", "input": {"subject": "Keep the page in range"}}
        with open(path, "a") as f:
            f.write(jsonl({"type": "assistant", "message": {"content": [task]}}) + jsonl({
                "type": "user", "toolUseResult": {"plan": "1. Keep the page in range", "isAgent": False,
                                                  "filePath": "/Users/dev/.claude/plans/calm-red-fox.md"},
                "message": {"content": [{"type": "tool_result", "tool_use_id": "p1", "content": "Approved."}]}}))
        app = self.make()
        work, item = app.work["chats"], chats.Chat("claude", "s2", "Price list", "/repo/app", 0)
        work.got_plan(work.read_plan(item))
        self.assertIsNone(work.view.plan[1])                         # asked for, not numbered yet: no list
        with open(path, "a") as f:
            f.write(jsonl({"type": "user", "message": {"content": [{
                "type": "tool_result", "tool_use_id": "k1", "content": "Task #1 created successfully"}]}}))
        with mock.patch.object(plan, "lines", wraps=plan.lines) as read:
            work.got_plan(work.read_plan(item))
        self.assertGreater(read.call_args.args[2], 0)                # on from where the last read stopped
        self.assertEqual((work.view.plan[0], work.view.plan[1]["count"]), ("claude:s2", "0 of 1 done"))
        shown = []
        app.open_preview = lambda spec, cwd: shown.append((spec["title"], spec.get("file") or spec["pipeline"][0][-1]))
        work.show_plan(work.plan_file(item))
        kept = os.path.join(self.state, "plans", "s2", "plan.md")
        self.assertEqual(shown, [("plan · Price list", kept)])
        with open(kept, encoding="utf-8") as f:
            self.assertEqual(f.read(), "1. Keep the page in range\n")
        with self.assertRaises(RuntimeError):
            work.plan_file(chats.Chat("claude", "s1", "Fix the login", "/repo/app", 0))

    def test_archive_takes_a_closed_one_off_the_list_in_every_tab_and_back(self):
        self.start()
        self.choose("Price list", "Archive")
        self.until(lambda s: s.count("Price list") == 1 and 'Archived "Price list"' in s)    # the foot's alone
        self.assertEqual(chats.archived(self.state), {"claude:s2"})
        with open(os.path.join(self.home, ".claude", "projects", "-repo-app", "s2.jsonl"), encoding="utf-8") as f:
            self.assertIn("Price list", f.read())                  # its file as it was: resumable as before
        self.term.type(*[Key("char", ch) for ch in "archived"])
        self.until(lambda s: any(line.rstrip().endswith("archived") for line in s.splitlines() if "Price" in line))
        self.choose("Price list", "Unarchive")
        self.until(lambda s: "Back in the list" in s)
        self.assertEqual(chats.archived(self.state), set())

    def trash(self):
        """The system's Trash stood in for by a folder outside the home (Linux's own is under the temporary home)."""
        trashed = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, trashed)
        set_env(self, XDG_DATA_HOME=None)
        stand_in = lambda path: shutil.move(path, trashed)                     # noqa: E731
        set_attrs(self, fileops, mac_trash=stand_in, windows_recycle=stand_in)
        return os.path.join(self.home, ".claude", "projects", "-repo-app", "s2.jsonl")

    def test_delete_moves_a_closed_ones_file_to_the_trash_once_asked(self):
        path = self.trash()
        chats.archive(self.state, {"claude:s2"})
        self.start(chats=False)
        self.term.type(Key(sidebar.FIND), *[Key("char", ch) for ch in "price"])    # an archived one: found by typing
        self.until(lambda s: "Price list" in s)
        self.choose("Price list", "Delete…")
        self.until(lambda s: "Move the chat “Price list” to" in s)
        self.assertTrue(os.path.isfile(path))                      # asked first: nothing has left
        self.term.type(Key("char", "y"))
        self.until(lambda s: "Price list" not in s and "Moved to the Trash" in s)
        self.assertFalse(os.path.exists(path))
        self.assertEqual(chats.archived(self.state), set())
        self.assertTrue(os.path.isfile(os.path.join(os.path.dirname(path), "s1.jsonl")))

    def test_a_trash_that_refuses_brings_the_row_back_and_says_why(self):
        path = self.trash()

        def refuse(*_, **__):
            raise fileops.Refused("the Trash is full")
        set_attrs(self, fileops, trash_chat=refuse)
        self.start()
        self.choose("Price list", "Delete…")
        self.until(lambda s: "Move the chat “Price list” to" in s)
        self.term.type(Key("char", "y"))
        self.until(lambda s: "The Trash is full" in s)
        self.until(lambda s: "Price list" in s)
        self.assertTrue(os.path.isfile(path))

    def test_the_delete_key_on_a_running_one_says_it_is_not_deleted(self):
        self.trash()
        self.start()
        self.term.type(Key("down"), Key("delete"))                 # app's first chat: Fix the login, running
        self.until(lambda s: "A running chat is not deleted" in s)
        self.assertNotIn("Move the chat", self.screen())
        self.assertTrue(os.path.isfile(os.path.join(self.home, ".claude", "projects", "-repo-app", "s1.jsonl")))

    def test_the_marked_ones_are_archived_together(self):
        self.claude("s4", "/repo/app", "Draft notes", time.time() - 7200)
        self.start()
        self.until(lambda s: "Draft notes" in s)
        self.term.type(Key(sidebar.FIND), Key("down"), Key("down"), Key("char", " "),
                       Key("down", shift=True))                              # Price list, Draft notes
        y = next(n for n, shown in enumerate(self.screen().splitlines()) if "Draft notes" in shown)
        self.term.type(Mouse("press", 12, y, 2))
        self.until(lambda s: "Archive 2 chats" in s.splitlines()[y + 1])
        self.term.type(Mouse("press", 14, y + 1, 0))
        self.until(lambda s: "Price list" not in s and "Draft notes" not in s and "Archived 2 chats" in s)
        self.assertEqual(chats.archived(self.state), {"claude:s2", "claude:s4"})

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

    def test_own_tab_is_the_tab_a_chat_has_to_itself(self):
        def herdr(agents, number):
            return lambda *args: ({"agents": agents} if args[:2] == ("agent", "list")
                                  else {"tab": {"tab_id": args[2], "number": number}})
        alone = [{"pane_id": "w1:p1", "tab_id": "w1:t2"}, {"pane_id": "w1:p5", "tab_id": "w1:t3"}]
        shared = alone + [{"pane_id": "w1:p6", "tab_id": "w1:t2"}]
        self.assertEqual(chats_panel.own_tab(herdr(alone, 2), "w1:p1"), "w1:t2")
        self.assertIsNone(chats_panel.own_tab(herdr(alone, 1), "w1:p1"))              # the main tab: the workspace's
        self.assertIsNone(chats_panel.own_tab(herdr(shared, 2), "w1:p1"))
        self.assertIsNone(chats_panel.own_tab(herdr(alone, 2), "w1:p9"))              # no agent there any more

    def test_a_tab_is_named_as_the_sessions_list_names_it(self):
        for name in ("Price list", "Colors of fruits and vegetables in spring", "x" * chats_panel.TAB_NAME):
            self.assertEqual(chats_panel.tab_name(name), sessions.tab_name(name))

    def test_rename_names_a_closed_one(self):
        self.start()
        self.choose("Price list", "Rename")
        self.term.type(*[Key("char", ch) for ch in " 2027"], Key("enter"))
        self.until(lambda s: "Price list 2027" in s)
        self.assertEqual(self.names(), {"s2": {"name": "Price list 2027", "given": False}})
        self.assertEqual([call for call in logged(self.log) if call.startswith("pane rename")], [])

    def test_show_archived_in_one_tab_shows_them_in_every_tab(self):
        self.start()
        chats.archive(self.state, {"claude:s2"})                         # archived in another tab
        self.until(lambda s: "Fix the login" in s and "Price list" not in s)
        chats.keep(self.state, show_archived=True)                        # Show archived in another tab
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
        work = self.make(herdr).work["chats"]
        work.folders = {"/repo/app": "w1"}
        work.reopen(item)
        return herdr.calls

    def test_a_reopened_chats_title_is_a_clean_label(self):
        # a title comes from a transcript: an escape code in it, or a leading dash herdr's command line takes for an
        # option, never reaches the tab's label or the pane's name
        set_attrs(self, chats, manual_names=lambda: {"s2": "\x1b]52;c;ZXZpbA==\x07-rf list"})
        title = "\x1b]52;c;ZXZpbA==\x07-rf list"
        calls = self.reopen(chats.Chat("claude", "s2", title, "/repo/app", 0))
        create = next(c for c in calls if c[:2] == ("tab", "create"))
        names = [c[3] for c in calls if c[:2] == ("pane", "rename")]
        for label in [create[create.index("--label") + 1]] + names:
            self.assertTrue(label.isprintable() and not label.startswith("-"), label)

    def test_an_id_that_could_be_an_option_reopens_nothing(self):
        for bad in ("-x", "a b", "s2\x07"):
            with self.assertRaises(RuntimeError):
                self.reopen(chats.Chat("claude", bad, "Price list", "/repo/app", 0))

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

    def test_a_second_enter_while_it_reopens_opens_no_second_tab(self):
        app = self.make()
        family = app.work["chats"]
        item = chats.Chat("claude", "s2", "Price list", "/repo/app", 0)
        family.folders = {"/repo/app": "w1"}
        family.do_open(item)
        family.do_open(item)                                    # before the first is done
        end_jobs()
        self.assertEqual(sum(line.startswith("tab create") for line in logged(self.log)), 1)

    def test_a_pane_reopened_while_the_list_is_read_stays_noted(self):
        # the read forgets the panes herdr knows the session of; one a reopen notes meanwhile is not among them
        panes.resume(self.state, "w1:p1", "s1")                # herdr knows w1:p1's session
        state = self.state

        class Reopening(preview.Herdr):
            def call(self, *args):
                if args[:2] == ("agent", "list"):
                    panes.resume(state, "w1:p9", "s2")         # a reopen job's, while the read waits for herdr
                return super().call(*args)

        self.make(Reopening()).work["chats"].read()
        self.assertEqual(panes.resumed(self.state), {"w1:p9": "s2"})

    def test_a_click_in_another_pane_closes_its_menu(self):
        app = self.make(self.Recorder())
        closed = []
        set_attrs(self, app.views["chats"], close_menu=lambda: closed.append(True))
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
