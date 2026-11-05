"""Tests for conversations_app.py with a stand-in terminal and a fake herdr: going to, reopening and naming
conversations, and the column's width (a rail when collapsed, MIN_OPEN, COLLAPSE_BELOW) kept beside the right column."""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

from support import SRC, AppScreen, FakeHerdrSocket, FakeTerminal, jsonl, logged, set_attrs, set_env, stubs

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import column  # noqa: E402
import conversations  # noqa: E402
import preview  # noqa: E402
import conversations_pane  # noqa: E402
from conversation_list import RAIL  # noqa: E402
import conversations_app  # noqa: E402
from conversations_app import ConversationsApp  # noqa: E402
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
  "pane split") echo '{"result": {"pane": {"pane_id": "w1:p10"}}}' ;;
  *) echo '{"result": {}}' ;;
esac
"""
LOOKS = ("agent list", "workspace list", "pane list")                # the app's look every second


class Column(AppScreen, unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.home, self.log, self.state = os.path.join(tmp, "home"), os.path.join(tmp, "herdr.log"), os.path.join(
            tmp, "state")
        fakes = stubs(os.path.join(tmp, "bin"), {"herdr": FAKE_HERDR})
        set_env(self, HOME=self.home, HERDR_LOG=self.log, HERDR_WORKSPACE_ID="w1",
                HERDR_BIN_PATH=os.path.join(fakes, "herdr"))
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

    def start(self):
        self.term = FakeTerminal(40, 24)
        self.app = ConversationsApp(self.term, preview.Herdr(), self.state)
        thread = threading.Thread(target=self.app.run, daemon=True)
        thread.start()

        def stop():
            self.term.type(Key("char", "c", ctrl=True))
            thread.join(5)
        self.addCleanup(stop)
        self.until(lambda s: "Price list" in s)

    def calls_after(self, first):
        """The herdr calls from the first one starting FIRST on, waited for until the tab or workspace is focused; the
        LOOKS left out."""
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            calls = [call for call in logged(self.log) if not call.startswith(LOOKS)]
            starts = [n for n, call in enumerate(calls) if call.startswith(first)]
            if starts and any(call.startswith("tab focus") for call in calls[starts[0]:]):
                return calls[starts[0]:]
            time.sleep(0.05)
        self.fail(f"no {first} call: {logged(self.log)}")

    def test_the_spaces_in_their_order_their_conversations_under_them(self):
        self.start()
        rows = self.screen().splitlines()
        shown = [row.strip() for row in rows[rows.index(next(r for r in rows if "Filter" in r)) + 2:] if row.strip()]
        self.assertEqual((shown[0].split()[1], shown[0][-1]), ("app", "▾"), shown)   # 1 app, this pane's: open
        self.assertTrue(shown[1].startswith("├─ ● Fix the login"), shown)
        self.assertTrue(shown[2].startswith("└─ · Price list"), shown)
        self.assertEqual(shown[3].split(), ["○", "docs", "0", "▸"], shown)   # 2 docs: an idle agent, nothing else
        self.assertNotIn("Old notes", self.screen())                        # /elsewhere: no workspace has it

    def test_a_running_one_is_gone_to(self):
        self.start()
        self.term.type(Key("down"), Key("enter"))
        deadline = time.monotonic() + 5
        while "agent focus w1:p1" not in logged(self.log) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertIn("agent focus w1:p1", logged(self.log))

    def test_the_conversation_of_the_active_tab_leads_though_another_was_written_to_later(self):
        self.claude("s2", "/repo/app", "Price list", time.time())             # reopened and closed a moment ago
        self.start()
        self.until(lambda s: s.index("Fix the login") < s.index("Price list"))

    def test_a_right_click_comes_to_it_not_to_herdrs_pane_menu(self):
        set_env(self, HERDR_PANE_ID="w1:p4")                     # herdr's own menu would offer Close pane
        self.start()
        deadline = time.monotonic() + 5
        while "pane input w1:p4 --right-click pane" not in logged(self.log) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertIn("pane input w1:p4 --right-click pane", logged(self.log))

    def test_a_note_goes_by_itself_or_on_a_click_an_error_stays(self):
        now = [100.0]
        app = ConversationsApp(FakeTerminal(40, 24), preview.Herdr(), self.state, clock=lambda: now[0])
        app.say("Archived")
        now[0] += conversations_app.NOTE
        app.tick()
        self.assertIsNone(app.note)                                          # by itself
        app.say("Archived")
        app.handle(Mouse("press", 1, 1, 0))
        self.assertIsNone(app.note)                                          # on a click
        app.error = "its file is gone"
        now[0] += conversations_app.NOTE
        app.tick()
        self.assertEqual(app.error, "its file is gone")

    def test_copy_conversation_puts_the_whole_conversation_on_the_clipboard(self):
        path = os.path.join(self.home, ".claude", "projects", "-repo-app", "s2.jsonl")
        with open(path, "a") as f:
            f.write(jsonl({"type": "assistant", "message": {"content": [{"type": "text", "text": "**Done.**"}]}}))
        app, copied = ConversationsApp(FakeTerminal(40, 24), preview.Herdr(), self.state), []
        app.clipboard = lambda text: copied.append(text) or True
        set_attrs(self, sys.modules["richtext"], copy_rich=lambda markdown, plain: copied.append("formatted"))
        item = conversations.Conversation("claude", "s2", "Price list", "/repo/app", 0)
        self.assertIsNone(app.copy(item))
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
        self.term.type(Key("down"), Key("down"), Key("char", " "), Key("down", shift=True))  # Price list, Draft notes
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
        self.assertEqual(conversations_app.own_tab(herdr(alone, 2), "w1:p1"), "w1:t2")
        self.assertIsNone(conversations_app.own_tab(herdr(alone, 1), "w1:p1"))      # the main tab: the workspace's
        self.assertIsNone(conversations_app.own_tab(herdr(shared, 2), "w1:p1"))
        self.assertIsNone(conversations_app.own_tab(herdr(alone, 2), "w1:p9"))      # no agent there any more

    def test_a_tab_is_named_as_the_sessions_list_names_it(self):
        for name in ("Price list", "Colors of fruits and vegetables in spring", "x" * conversations_app.TAB_NAME):
            self.assertEqual(conversations_app.tab_name(name), sessions.tab_name(name))

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
        conversations_pane.keep(self.state, show_archived=True)               # Show archived in another tab
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
            if args[:2] == ("pane", "split"):
                return {"pane": {"pane_id": "w1:p10", "tab_id": "w1:t3"}}
            return {}

    def reopen(self, item):
        herdr = self.Recorder()
        app = ConversationsApp(FakeTerminal(40, 24), herdr, self.state)
        app.folders = {"/repo/app": "w1"}
        app.reopen(item)
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

    def test_a_new_version_waits_for_every_job(self):
        # its look every second runs herdr: handed over meanwhile, that program would stay a zombie of the new one
        app = ConversationsApp(FakeTerminal(40, 24), self.Recorder(), self.state)
        for job in ("read", "width", "copy"):
            app.running = {job}
            self.assertTrue(app.busy(), job)
        app.running = set()
        self.assertFalse(app.busy())

    def test_a_new_version_takes_over_between_two_looks(self):
        # a look every second: the handover comes before the next one starts, never with one running
        code = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, code)
        path = os.path.join(code, "a.py")
        with open(path, "w") as f:
            f.write("x = 1\n")
        now = [1000.0]
        app = ConversationsApp(FakeTerminal(40, 24), self.Recorder(), self.state, clock=lambda: now[0], code=code)
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
        self.assertEqual(app.running, set())                               # no look of its own left running

    def test_a_click_in_another_pane_closes_its_menu(self):
        app = ConversationsApp(FakeTerminal(40, 24), self.Recorder(), self.state)
        closed = []
        set_attrs(self, app.view, close_menu=lambda: closed.append(True))
        app.handle(Focus(True))
        app.handle(Focus(False))
        self.assertEqual(closed, [True])

    def test_an_id_that_could_be_an_option_reopens_nothing(self):
        for bad in ("-x", "a b", "s2\x07"):
            with self.assertRaises(RuntimeError):
                self.reopen(conversations.Conversation("claude", bad, "Price list", "/repo/app", 0))

    def choose(self, row, choice):
        """CHOICE of the right click's menu on the row that shows ROW."""
        y = next(n for n, shown in enumerate(self.screen().splitlines()) if row in shown)
        self.term.type(Mouse("press", 5, y, 2))
        self.until(lambda s: any(f"│{choice} " in line for line in s.splitlines()[y + 1:]))
        at = next(n for n, line in enumerate(self.screen().splitlines()) if n > y and f"│{choice} " in line)
        self.term.type(Mouse("press", 7, at, 0))

    def test_a_closed_one_reopens_in_a_new_tab_of_its_workspace_with_the_right_column(self):
        noted = []
        set_attrs(self, conversations_pane, resume=lambda state_dir, pane, id: noted.append((pane, id)))
        self.start()
        self.term.type(Key("down"), Key("down"), Key("enter"))
        calls = self.calls_after("tab create")
        self.assertEqual(calls, [
            "tab create --workspace w1 --cwd /repo/app --label Price list --no-focus",
            "pane rename w1:p9 claude",
            # the Conversations column off the agent, the right column off it (the fake names every new pane w1:p10)
            "pane split --pane w1:p9 --direction right --ratio 0.525 --cwd /repo/app --no-focus",
            "pane split --pane w1:p10 --direction right --ratio 0.4737 --cwd /repo/app --no-focus",
            "pane split --pane w1:p10 --direction down --ratio 0.5 --cwd /repo/app --no-focus",
            "pane rename w1:p10 sidebar",
            "pane rename w1:p10 terminal",
            "pane rename w1:p10 conversations",
            f"pane run w1:p10 {conversations_pane.sidebar_command()}",
            f"pane run w1:p10 {conversations_pane.command()}",
            "agent start claude-s2 --kind claude --pane w1:p9 --timeout 60000 -- --resume s2",
            "tab focus w1:t3"])
        self.assertEqual(noted, [("w1:p9", "s2")])                 # its row marked before herdr knows the session

    def test_a_reopened_ones_pane_is_forgotten_once_herdr_knows_its_session(self):
        conversations_pane.resume(self.state, "w1:p1", "s1")                # herdr knows w1:p1's session
        conversations_pane.resume(self.state, "w1:p7", "s2")                # no agent there any more
        self.start()
        deadline = time.monotonic() + 5
        while conversations_pane.resumed(self.state) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(conversations_pane.resumed(self.state), {})


class Width(unittest.TestCase):
    """200 cells: the agent 100, this column 50 (w1:p4), the right column 50."""

    def setUp(self):
        tmp = tempfile.mkdtemp(dir="/tmp")                  # a short path: a socket's name has room for 104 bytes
        self.addCleanup(shutil.rmtree, tmp)
        self.state = os.path.join(tmp, "state")
        os.makedirs(self.state)
        node = {"type": "split", "direction": "right", "ratio": 0.5,
                "first": {"type": "pane", "pane_id": "w1:p1", "label": "claude"},
                "second": {"type": "split", "direction": "right", "ratio": 0.5,
                           "first": {"type": "pane", "pane_id": "w1:p4", "label": "conversations"},
                           "second": {"type": "pane", "pane_id": "w1:p2", "label": "sidebar"}}}
        self.fake = FakeHerdrSocket(os.path.join(tmp, "h.sock"), {"w1:t1": (node, False)})
        self.addCleanup(self.fake.server.close)
        set_env(self, HERDR_SOCKET_PATH=os.path.join(tmp, "h.sock"))
        set_attrs(self, column, SETTLE=0)
        self.term = FakeTerminal(50, 24)
        self.app = ConversationsApp(self.term, preview.Herdr(), self.state)

    def sets(self):
        return [(params["path"], params["ratio"]) for method, params in self.fake.calls
                if method == "layout.set_split_ratio"]

    def remember(self, ratio):
        with open(os.path.join(self.state, conversations.SETTINGS), "w") as f:
            json.dump({"ratio": ratio}, f)

    def test_collapsed_a_rail_the_agent_taking_the_room_the_right_column_kept(self):
        self.app.view.collapsed = True
        self.app.place("w1:p4")
        conversations = RAIL / 200
        inner = conversations / (conversations + 0.25)
        self.assertEqual(self.sets(), [([], round(1 - 0.25 / (1 - inner), 4)), ([True], round(inner, 4))])

    def test_collapsed_the_rail_has_its_cells_inside_herdrs_frame(self):
        self.app.view.collapsed = True
        self.term.cols = 48                                 # herdr's frame takes a cell each side of the 50
        self.app.place("w1:p4")
        self.assertEqual(self.sets(), [([], 0.705), ([True], round((RAIL + 2) / (RAIL + 2 + 50), 4))])

    def test_the_frame_is_measured_once_not_mid_drag(self):
        self.app.view.collapsed = True
        self.term.cols = 48                                 # herdr's frame: a cell each side
        self.app.place("w1:p4")
        self.term.cols = 47                                 # a terminal a step behind herdr while a border moves
        self.assertEqual(self.app.target(column.read("w1:p4"), "w1:p4")[1:], (RAIL + 2, 2))

    def test_open_at_the_width_remembered(self):
        self.app.view.collapsed = False
        self.remember(0.6)                                  # the agent 60% of the 150 cells before the right column
        self.app.place("w1:p4")
        self.assertEqual(self.sets(), [([], 0.45), ([True], 0.5455)])

    def test_opened_from_a_rail_never_as_squeezed_as_it_was(self):
        self.app.view.collapsed = False
        self.remember(0.85)                                 # 22.5 cells: the agent's 70% instead, 45 cells
        self.app.place("w1:p4", opening=True)
        self.assertEqual(self.sets(), [([], 0.525), ([True], 0.4737)])

    def layout(self, outer, inner):
        """The agent's split and the one this column shares with the right column, as the user left them."""
        self.fake.tabs["w1:t1"][0]["ratio"] = outer
        self.fake.tabs["w1:t1"][0]["second"]["ratio"] = inner
        self.term.cols = round(200 * (1 - outer) * inner)        # this pane's cells (no frame here)

    def saved(self, name):
        with open(os.path.join(self.state, name)) as f:
            return json.load(f).get("ratio")

    def test_a_window_resized_keeps_every_columns_share_and_saves_nothing(self):
        # Ghostty opening again: its window grows or shrinks in steps, herdr gives every column its share of it; no
        # border was dragged, so no column takes another's room, none collapses, and no width is kept for the tabs
        self.app.view.collapsed, self.app.placed, self.app.last = False, True, (100, 50, 50)
        for width in (120, 260, 200):
            self.fake.width = width
            self.term.cols = round(width * 0.25)
            self.assertIsNone(self.app.drag("w1:p4"), width)
            self.assertEqual(column.cells(column.read("w1:p4")), (width // 2, width // 4, width // 4), width)
        self.assertEqual([name for name in ("column.json", conversations.SETTINGS)
                          if os.path.exists(os.path.join(self.state, name))], [])

    def test_open_the_agents_border_moves_only_this_column(self):
        self.app.view.collapsed, self.app.placed, self.app.last = False, True, (90, 60, 50)
        self.layout(0.4, 0.5)                                    # dragged: the agent 80, the two others 60 each
        self.assertIsNone(self.app.drag("w1:p4"))
        self.assertEqual(self.sets(), [([True], 0.5833)])        # this column 70, the right column 50 as it was
        self.assertEqual((self.saved("column.json"), self.saved(conversations.SETTINGS)), (0.75, 0.5333))

    def test_open_the_right_columns_border_widens_it_this_column_moving_with_it(self):
        self.app.view.collapsed, self.app.placed, self.app.last = False, True, (90, 60, 50)
        self.layout(0.45, 0.4545)                                # dragged into this column: it 50, the right one 60
        self.assertIsNone(self.app.drag("w1:p4"))
        self.assertEqual(self.sets(), [([], 0.4), ([True], 0.5)])   # this column 60 again, the agent 80
        self.assertEqual((self.saved("column.json"), self.saved(conversations.SETTINGS)), (0.7, 0.5714))

    def test_the_right_column_keeps_room_for_the_sidebars_buttons(self):
        self.app.view.collapsed, self.app.placed, self.app.last = False, True, (90, 60, 50)
        self.layout(0.45, 0.8182)                                # the sidebar dragged to 20 cells
        self.assertIsNone(self.app.drag("w1:p4"))
        self.assertEqual(self.sets(), [([], 0.535), ([True], round(60 / 93, 4))])   # 33: its sidebar has not said
        column.need(self.state, "w1:t1", column.NARROWEST, {"w1:t1"})        # Issues there too: 39
        self.fake.calls.clear()
        self.app.last = (90, 60, 50)
        self.layout(0.45, 0.8182)
        self.assertIsNone(self.app.drag("w1:p4"))
        self.assertEqual(self.sets(), [([], 0.505), ([True], round(60 / 99, 4))])   # 39, this column 60 beside it

    def test_collapsed_either_border_widens_the_right_column_the_rail_moving_with_it(self):
        self.app.view.collapsed, self.app.placed, self.app.last = True, True, (143, 7, 50)
        self.layout(0.7, 0.2)                                    # the agent's border: the agent 140, the rest 60
        self.assertIsNone(self.app.drag("w1:p4"))
        self.assertEqual(self.sets(), [([True], round(RAIL / 60, 4))])   # the rail 7, the right column 53
        self.assertEqual(self.saved("column.json"), 0.735)
        self.fake.calls.clear()
        self.app.last = (143, 7, 50)
        self.layout(0.715, 0.0702)                               # the rail's own border: it 4, the right column 53
        self.assertIsNone(self.app.drag("w1:p4"))
        self.assertEqual(self.sets(), [([], 0.7), ([True], round(RAIL / 60, 4))])   # the rail 7 again, moved left

    def test_squeezed_below_its_opening_width_it_stays_open_for_every_tab(self):
        self.app.view.collapsed, self.app.placed, self.app.last = False, True, (90, 60, 50)
        self.layout(0.65, 0.2857)                                # the agent 130: this column 20
        self.assertIsNone(self.app.drag("w1:p4"))
        self.assertEqual(self.saved(conversations.SETTINGS), 0.8667)
        self.app.place("w1:p4")                                  # started again: as it was left
        self.assertEqual(column.cells(column.read("w1:p4")), (130, 20, 50))

    def test_dragged_narrower_than_half_its_opening_width_it_collapses_in_every_tab(self):
        self.app.view.collapsed, self.app.placed, self.app.last = False, True, (90, 60, 50)
        self.layout(0.7, 0.1667)                                 # the agent 140: this column 10
        self.assertEqual(self.app.drag("w1:p4"), "collapse")
        self.app.dragged("collapse")
        self.assertTrue(self.app.view.collapsed)
        self.assertTrue(conversations_pane.is_collapsed(self.state))

    def test_nothing_is_taken_out_of_sight_or_before_it_is_placed(self):
        self.app.view.collapsed, self.app.placed, self.app.last = False, True, (90, 60, 50)
        self.layout(0.4, 0.5)
        set_attrs(self, column, visible=lambda tab: False)       # another tab on screen: this one set from it
        self.assertIsNone(self.app.drag("w1:p4"))
        self.assertEqual(self.sets(), [])
        set_attrs(self, column, visible=lambda tab: True)
        self.app.placed = False                                  # its own width still coming
        self.assertIsNone(self.app.drag("w1:p4"))
        self.assertEqual(self.sets(), [])
        self.assertFalse(os.path.exists(os.path.join(self.state, "column.json")))


if __name__ == "__main__":
    unittest.main()
