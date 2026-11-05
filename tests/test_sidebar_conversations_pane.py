"""Tests for conversations_pane.py: where the Conversations column goes (right before the right column, in every tab
that has one), its width, collapsing to a rail and back, and the archived conversations. herdr is a recorder."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from support import SRC, set_env, stubs

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import conversations  # noqa: E402
import conversations_pane as pane  # noqa: E402
import panels  # noqa: E402


class Herdr:
    """Two tabs, each an agent and the right column (sidebar above terminal), the Conversations column in the tabs
    `with_column`. Panes: t1 agent p1, sidebar p2, terminal p3, Conversations p8; t2 p4, p5, p7, p6. New panes are
    new1, new2…, listed once named; `refused` panes herdr will not close."""

    def __init__(self, with_column=("w1:t2",), current="w1:t2", terminal=True, refused=()):
        self.calls, self.split, self.current, self.refused = [], 0, current, refused
        self.new_in = {}                                                    # a new pane → its tab
        self.panes = []
        for tab, agent, side, term, mine in (("w1:t1", "p1", "p2", "p3", "p8"), ("w1:t2", "p4", "p5", "p7", "p6")):
            self.panes += [{"pane_id": f"w1:{agent}", "tab_id": tab, "label": "claude"},
                           {"pane_id": f"w1:{side}", "tab_id": tab, "label": "sidebar", "cwd": f"/repo/{tab[-1]}"}]
            if terminal:
                self.panes.append({"pane_id": f"w1:{term}", "tab_id": tab, "label": "terminal"})
            if tab in with_column:
                self.panes.append({"pane_id": f"w1:{mine}", "tab_id": tab, "label": "conversations"})

    def tab_of(self, pane):
        return next((p["tab_id"] for p in self.panes if p["pane_id"] == pane), None) or self.new_in.get(pane)

    def __call__(self, *args):
        self.calls.append(" ".join(args))
        if args[:2] == ("pane", "list"):
            return {"panes": self.panes}
        if args[:2] == ("pane", "current"):
            return {"pane": {"tab_id": self.current}}
        if args[:2] == ("pane", "close") and args[2] in self.refused:
            raise RuntimeError("pane is busy")
        if args[:2] == ("pane", "neighbor"):                        # below a sidebar: its terminal
            below = [p["pane_id"] for p in self.panes
                     if p["tab_id"] == self.tab_of(args[3]) and p["label"] == "terminal"]
            return {"neighbor": {"neighbor_pane_id": below[0]}} if below else {}
        if args[:2] == ("pane", "layout"):                          # agent 0-99, Conversations 100-129, column 130-159
            x = {"conversations": 100, "sidebar": 130, "terminal": 130}
            height = {"sidebar": 24, "terminal": 18}
            shown = [{"pane_id": p["pane_id"], "rect": {"x": x.get(p["label"], 0), "y": 0, "height": height.get(
                p["label"], 42), "width": 30 if p["label"] in x else 100}}
                     for p in self.panes if p["tab_id"] == self.tab_of(args[3])]
            return {"layout": {"panes": shown}}
        if args[:2] == ("pane", "rename") and args[2] in self.new_in:
            self.panes.append({"pane_id": args[2], "tab_id": self.new_in[args[2]], "label": args[3]})
        if args[:2] == ("pane", "split"):
            self.split += 1
            self.new_in[f"new{self.split}"] = self.tab_of(args[3])
            return {"pane": {"pane_id": f"new{self.split}", "tab_id": self.new_in[f"new{self.split}"]}}
        return {}

    def changes(self):
        return [call for call in self.calls
                if not call.startswith(("pane list", "pane neighbor", "pane current", "pane layout"))]


class Place(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)

    def write(self, data, name=conversations.SETTINGS):
        with open(os.path.join(self.state, name), "w") as f:
            json.dump(data, f)

    def test_open_until_collapsed_and_the_choice_kept_with_the_width(self):
        self.assertFalse(pane.is_collapsed(self.state))
        self.write({"ratio": 0.65})
        pane.collapse(self.state, True)
        self.assertTrue(pane.is_collapsed(self.state))
        with open(os.path.join(self.state, conversations.SETTINGS)) as f:
            self.assertEqual(json.load(f), {"ratio": 0.65, "collapsed": True})

    def test_archived_ones_are_kept_with_the_rest(self):
        self.write({"ratio": 0.65, "collapsed": True})
        conversations.archive(self.state, {"claude:s1", "claude:s2"})
        conversations.archive(self.state, {"codex:c1"})
        conversations.archive(self.state, {"claude:s1", "claude:s2"}, False)
        self.assertEqual(conversations.archived(self.state), {"codex:c1"})
        self.assertEqual(conversations.setting(self.state),
                         {"ratio": 0.65, "collapsed": True, "archived": ["codex:c1"]})
        self.assertFalse(pane.shows_archived(self.state))
        conversations.keep(self.state, show_archived=True)
        self.assertTrue(pane.shows_archived(self.state))

    def test_the_panes_reopening_a_conversation_are_kept_with_the_rest(self):
        self.write({"collapsed": True, "resumed": ["of another shape"]})
        self.assertEqual(pane.resumed(self.state), {})
        pane.resume(self.state, "w1:p9", "s2")
        pane.resume(self.state, "w2:p3", "c1")
        self.assertEqual(pane.resumed(self.state), {"w1:p9": "s2", "w2:p3": "c1"})
        self.assertTrue(pane.is_collapsed(self.state))

    def test_a_tab_built_here_gets_it_with_the_right_column_off_it_as_wide_as_the_others(self):
        herdr = Herdr()
        self.assertEqual(pane.build(herdr, "w1:p1", "/repo/app", self.state), "new2")
        self.assertEqual(herdr.calls, [
            "pane split --pane w1:p1 --direction right --ratio 0.525 --cwd /repo/app --no-focus",   # 75% x 70%
            "pane split --pane new1 --direction right --ratio 0.4737 --cwd /repo/app --no-focus",   # the two share it
            "pane split --pane new2 --direction down --ratio 0.5 --cwd /repo/app --no-focus",
            "pane rename new2 sidebar", "pane rename new3 terminal", "pane rename new1 conversations",
            f"pane run new2 {pane.sidebar_command()}", f"pane run new1 {pane.command()}"])
        self.write({"ratio": 0.8}, "column.json")                     # dragged: the right column 20%,
        self.write({"ratio": 0.6})                                    # the agent 60% of what is before it
        herdr = Herdr()
        pane.build(herdr, "w1:p1", None, self.state, run="launcher --conversations", sidebar_run="launcher")
        self.assertEqual([call.split(" --ratio ")[1].split()[0] for call in herdr.calls if "right" in call],
                         ["0.48", "0.6154"])
        self.assertEqual(herdr.calls[-2:], ["pane run new2 launcher", "pane run new1 launcher --conversations"])

    def test_beside_the_terminal_with_the_sidebar_started_again_above_it(self):
        herdr = Herdr()
        self.assertEqual(pane.insert(herdr, "w1:p2", "/repo/1", self.state), "new1")
        self.assertEqual(herdr.changes(), [
            "pane close w1:p2",
            "pane split --pane w1:p3 --direction right --ratio 0.4737 --cwd /repo/1 --no-focus",
            "pane swap --source-pane w1:p3 --target-pane new1",                 # the column first, on the left
            "pane rename new1 conversations", f"pane run new1 {pane.command()}",
            "pane split --pane w1:p3 --direction down --ratio 0.5714 --cwd /repo/1 --no-focus",   # as tall as it was
            "pane swap --source-pane w1:p3 --target-pane new2",                 # the sidebar on top again
            "pane rename new2 sidebar", f"pane run new2 {pane.sidebar_command()}"])

    def test_without_a_terminal_beside_the_sidebar_itself(self):
        herdr = Herdr(terminal=False)
        pane.insert(herdr, "w1:p2", "/repo/1", self.state)
        self.assertEqual(herdr.changes()[:2], ["pane split --pane w1:p2 --direction right --ratio 0.4737 --cwd /repo/1 "
                                               "--no-focus", "pane swap --source-pane w1:p2 --target-pane new1"])
        self.assertFalse(any(call.startswith("pane close") for call in herdr.calls))

    def test_every_tab_with_a_right_column_gets_it_beside_that_once(self):
        herdr = Herdr()
        self.assertEqual(pane.ensure(herdr, self.state), 1)
        self.assertEqual(herdr.changes()[0], "pane close w1:p2")               # the first tab's sidebar, to start again
        self.assertEqual(pane.ensure(Herdr(with_column=("w1:t1", "w1:t2")), self.state), 0)

    def test_a_tab_running_another_sidebar_or_refusing_a_step_is_left_alone(self):
        herdr = Herdr()
        self.assertEqual(pane.ensure(herdr, self.state, keep={"w1:p2"}), 0)
        herdr = Herdr(refused=("w1:p2",))
        self.assertEqual(pane.ensure(herdr, self.state), 0)
        self.assertFalse(any(call.startswith("pane split") for call in herdr.calls))

    def test_the_toggle_collapses_it_everywhere_then_opens_it_again(self):
        herdr = Herdr()                                                      # the key pressed where it is
        self.assertTrue(pane.toggle(herdr, self.state))
        self.assertEqual(herdr.changes(), [])                                # every pane narrows itself
        self.assertTrue(pane.is_collapsed(self.state))
        self.assertFalse(pane.toggle(Herdr(), self.state))
        self.assertFalse(pane.is_collapsed(self.state))

    def test_the_toggle_brings_it_back_open_where_it_was_closed_by_hand(self):
        pane.collapse(self.state, True)
        herdr = Herdr(current="w1:t1")                                       # this tab's column closed by hand
        self.assertFalse(pane.toggle(herdr, self.state))
        self.assertIn("pane rename new1 conversations", herdr.calls)
        self.assertFalse(pane.is_collapsed(self.state))

    def test_one_closed_by_hand_stays_closed_and_the_key_brings_it_back(self):
        panels.note(self.state, {"w1:t1": {"sidebar", "terminal", "conversations"}})   # t1 had it: closed by hand
        self.assertEqual(pane.ensure(Herdr(), self.state), 0)
        herdr = Herdr(current="w1:t1")
        self.assertFalse(pane.toggle(herdr, self.state))                    # Cmd+Shift+H there: back
        self.assertIn("pane rename new1 conversations", herdr.calls)

    def test_find_gives_the_keys_to_the_tabs_column_with_an_empty_filter(self):
        herdr, focused = Herdr(), []
        self.assertEqual(pane.find(herdr, self.state, focused.append), "w1:p6")
        self.assertEqual(herdr.changes(), ["pane send-keys w1:p6 esc"])      # Esc: the filter empty
        self.assertEqual(focused, ["w1:p6"])

    def test_find_opens_a_collapsed_column_everywhere(self):
        pane.collapse(self.state, True)
        pane.find(Herdr(), self.state, lambda found: None)
        self.assertFalse(pane.is_collapsed(self.state))

    def test_find_brings_back_a_column_closed_by_hand(self):
        panels.note(self.state, {"w1:t1": {"sidebar", "terminal", "conversations"}})
        herdr, focused = Herdr(current="w1:t1"), []
        self.assertEqual(pane.find(herdr, self.state, focused.append), "new1")
        self.assertIn("pane rename new1 conversations", herdr.calls)
        self.assertEqual(focused, ["new1"])

    def test_find_in_a_tab_without_a_right_column_goes_to_the_workspaces_main_tab(self):
        herdr, focused = Herdr(with_column=("w1:t1", "w1:t2"), current="w1:t3"), []    # w1:t3: a preview tab
        self.assertEqual(pane.find(herdr, self.state, focused.append), "w1:p8")
        self.assertEqual(focused, ["w1:p8"])

    def test_restore_panels_brings_back_every_pane_closed_in_the_tab_and_shows_the_column(self):
        herdr = Herdr(with_column=(), current="w1:t1", terminal=False)    # t1: the terminal and the column closed
        snapshot = {"snapshot": {"layouts": [{"tab_id": "w1:t1", "zoomed": True, "focused_pane_id": "w1:p1"}]}}
        call = lambda *args: snapshot if args[:2] == ("api", "snapshot") else herdr(*args)   # noqa: E731
        self.assertEqual(pane.restore(call, self.state), {"terminal", "conversations"})
        self.assertEqual(herdr.calls[1], "pane zoom w1:p1 --toggle")          # the column hidden: shown first
        self.assertIn("pane rename new1 terminal", herdr.calls)
        self.assertIn("pane rename new2 conversations", herdr.calls)

    def closed_tip(self):
        """The tip herdr shows when t1's terminal is closed by hand."""
        panels.note(self.state, {"w1:t1": {"sidebar", "terminal"}})
        herdr = Herdr(with_column=("w1:t2",))
        for listed in herdr.panes:
            listed["workspace_id"] = "w1"
        herdr.panes = [p for p in herdr.panes if p["label"] != "terminal" or p["tab_id"] != "w1:t1"]
        pane.tell(herdr, self.state, "w1", lambda _: None)
        return [call for call in herdr.calls if call.startswith("notification show")]

    def test_the_tip_names_the_key_only_where_herdr_has_it(self):
        # herdr-fold binds Restore panels to Cmd+Shift+O in herdr's config; the sidebar installed alone has the menus
        home = os.path.join(self.state, "home")
        set_env(self, HOME=home)
        self.assertEqual(self.closed_tip(), ["notification show Closed panels stay closed in their tab --body "
                                             "Restore panels in the ⋯ or right-click menu brings them back"])
        os.makedirs(os.path.join(home, ".config", "herdr"))
        with open(os.path.join(home, ".config", "herdr", "config.toml"), "w") as f:
            f.write('command = "/usr/bin/python3 ~/.config/herdr-fold/plugins/sidebar/conversations_pane.py'
                    ' --restore"\n')
        os.remove(os.path.join(self.state, "conversations.json"))             # told once: shown again here
        self.assertEqual(self.closed_tip(), ["notification show Closed panels stay closed in their tab --body "
                                             "Cmd+Shift+O brings them back"])

    def test_the_first_pane_closed_by_hand_brings_a_tip_once(self):
        set_env(self, HOME=os.path.join(self.state, "home"))
        panels.note(self.state, {"w1:t1": {"sidebar", "terminal"}, "w1:t2": {"sidebar", "terminal", "conversations"}})
        herdr, waited = Herdr(with_column=("w1:t2",)), []
        for listed in herdr.panes:
            listed["workspace_id"] = "w1"
        self.assertFalse(pane.tell(herdr, self.state, "w1", waited.append))        # a pane not of the plugin's
        herdr.panes = [p for p in herdr.panes if p["label"] != "terminal" or p["tab_id"] != "w1:t1"]   # t1's terminal
        self.assertTrue(pane.tell(herdr, self.state, "w1", waited.append))
        self.assertEqual(waited, [pane.SETTLE, pane.SETTLE])        # looked at once the plugin's own moves are done
        tip = [call for call in herdr.calls if call.startswith("notification show")]
        self.assertEqual(len(tip), 1)
        self.assertFalse(pane.tell(herdr, self.state, "w1", waited.append))         # never again
        self.assertEqual(len(waited), 2)

    def test_a_menu_brings_panes_back_in_a_process_that_outlives_its_pane(self):
        # bringing the Conversations column back closes the sidebar on the way: a thread in the sidebar's process
        # would end with it, half done (the sidebar gone, the column not there)
        with mock.patch.object(pane.subprocess, "Popen") as started:
            pane.bring_apart("w1:t1", {"terminal", "conversations"})
        args, kwargs = started.call_args
        self.assertEqual(args[0][2:], [os.path.abspath(pane.__file__), "--bring", "w1:t1", "conversations", "terminal"])
        self.assertTrue(kwargs.get("start_new_session"))                    # its own session: no hangup from the pane
        self.assertEqual({kwargs[k] for k in ("stdin", "stdout", "stderr")}, {pane.subprocess.DEVNULL})

    def test_bring_from_the_command_line_goes_to_the_end(self):
        # what bring_apart() starts: the Conversations column back in a tab with its sidebar over a terminal
        bin_dir, log = os.path.join(self.state, "bin"), os.path.join(self.state, "herdr.log")
        panes = json.dumps({"result": {"panes": [
            {"pane_id": "w1:p1", "tab_id": "w1:t1", "label": "claude"},
            {"pane_id": "w1:p2", "tab_id": "w1:t1", "label": "sidebar", "cwd": "/repo"},
            {"pane_id": "w1:p3", "tab_id": "w1:t1", "label": "terminal"}]}})
        below = json.dumps({"result": {"neighbor": {"neighbor_pane_id": "w1:p3"}}})
        made = json.dumps({"result": {"pane": {"pane_id": "w1:p9", "tab_id": "w1:t1"}}})
        shown = json.dumps({"result": {"layout": {"panes": [{"pane_id": "w1:p2", "rect": {"height": 21}},
                                                            {"pane_id": "w1:p3", "rect": {"height": 21}}]}}})
        stubs(bin_dir, {"herdr": "#!/bin/sh\n"
                                 f"printf '%s\\n' \"$*\" >> '{log}'\n"
                                 'case "$1 $2" in\n'
                                 f"  'pane list') echo '{panes}' ;;\n"
                                 f"  'pane neighbor') echo '{below}' ;;\n"
                                 f"  'pane split') echo '{made}' ;;\n"
                                 f"  'pane layout') echo '{shown}' ;;\n"
                                 "  *) echo '{\"result\": {}}' ;;\n"
                                 "esac\n"})
        done = subprocess.run([sys.executable, pane.__file__, "--bring", "w1:t1", "conversations"], timeout=30,
                              env={"PATH": "/usr/bin:/bin", "HERDR_BIN_PATH": os.path.join(bin_dir, "herdr"),
                                   "HERDR_PLUGIN_STATE_DIR": self.state, "HOME": self.state}, capture_output=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(log) as f:
            calls = f.read().splitlines()
        self.assertIn("pane close w1:p2", calls)                          # the sidebar, to start again above
        self.assertIn("pane rename w1:p9 conversations", calls)
        self.assertEqual(calls[-2], "pane rename w1:p9 sidebar")           # and the sidebar back on top, running
        self.assertTrue(calls[-1].startswith("pane run w1:p9 "), calls[-1])

    def test_a_tab_built_here_is_noted_as_having_every_pane(self):
        pane.build(Herdr(), "w1:p1", "/repo/app", self.state)
        self.assertEqual(panels.had(self.state, "w1:t1"), set(panels.KINDS))

    def test_restore_panels_brings_back_what_the_tab_lacks(self):
        herdr = Herdr(terminal=False)                                        # t1: an agent and the sidebar only
        self.assertEqual(pane.bring(herdr, "w1:t1", {"terminal", "conversations"}, self.state),
                         {"terminal", "conversations"})
        self.assertIn("pane rename new1 terminal", herdr.calls)
        self.assertIn("pane rename new2 conversations", herdr.calls)
        self.assertEqual(panels.had(self.state, "w1:t1"), {"terminal", "conversations"})

    def test_the_right_column_back_beside_the_conversations_column(self):
        herdr = Herdr(with_column=("w1:t1", "w1:t2"))
        herdr.panes = [p for p in herdr.panes if p["tab_id"] != "w1:t1" or p["label"] in ("claude", "conversations")]
        self.assertEqual(pane.bring(herdr, "w1:t1", {"sidebar", "terminal"}, self.state), {"sidebar", "terminal"})
        self.assertTrue(herdr.changes()[0].startswith("pane split --pane w1:p8 --direction right --ratio 0.4737"))

    def test_a_tab_with_none_of_them_gets_the_whole_layout(self):
        herdr = Herdr(with_column=())
        herdr.panes = [p for p in herdr.panes if p["tab_id"] != "w1:t1" or p["label"] == "claude"]
        self.assertEqual(pane.bring(herdr, "w1:t1", set(panels.KINDS), self.state), set(panels.KINDS))
        self.assertTrue(herdr.changes()[0].startswith("pane split --pane w1:p1 --direction right --ratio 0.525"))

    def test_its_commands_run_this_plugin_with_this_python(self):
        self.assertTrue(pane.command(windows=False).endswith("/sidebar.py --conversations"))
        self.assertTrue(pane.command(windows=True).startswith("& '"))
        self.assertTrue(pane.command(windows=True).endswith("sidebar.py' --conversations"))
        self.assertTrue(pane.sidebar_command(windows=False).endswith("/sidebar.py"))
        self.assertTrue(pane.sidebar_command(windows=True).endswith("sidebar.py'"))

    def test_its_commands_name_no_account(self):
        # typed into a pane's shell, the line stays in its history: a path from the home folder goes as ~ ($HOME)
        self.assertNotIn(os.path.expanduser("~") + os.sep, pane.command(windows=False))
        mac, windows = "/Us" + "ers/dev", "C:\\Us" + "ers\\dev"
        self.assertEqual(pane.typed(mac + "/.config/x y/sidebar.py", windows=False, home=mac),
                         "~/'.config/x y/sidebar.py'")
        self.assertEqual(pane.typed("/usr/bin/python3", windows=False, home=mac), "/usr/bin/python3")
        self.assertEqual(pane.typed(windows + "\\a$b`c\\s.py", windows=True, home=windows), '"$HOME\\a`$b``c\\s.py"')
        self.assertEqual(pane.typed("D:\\py\\python.exe", windows=True, home=windows), "'D:\\py\\python.exe'")
        here = os.path.expanduser("~/.a b/c")
        out = subprocess.run(["/bin/sh", "-c", "printf %s " + pane.typed(here, windows=False)], capture_output=True,
                             text=True).stdout
        self.assertEqual(out, here)                                                 # the shell finds it again

    def test_a_folders_name_is_never_typed_into_a_pane(self):
        # herdr types a pane's command into its shell: control characters in a folder's name (a downloaded
        # repository's) would edit that line and run what follows, quotes or not; the folder goes as --cwd only
        herdr = Herdr(current="w1:t1")
        folder = "/repo/a\x15touch owned\r"
        for p in herdr.panes:
            if p.get("cwd"):
                p["cwd"] = folder
        panels.note(self.state, {"w1:t1": {"sidebar", "terminal", "conversations"}})
        pane.bring(herdr, "w1:t1", {"conversations"}, self.state)
        typed = [call for call in herdr.calls if call.startswith("pane run")]
        self.assertTrue(typed)
        self.assertEqual([call for call in typed if "repo" in call or "owned" in call], [])
        self.assertIn(f"--cwd {folder}", " ".join(c for c in herdr.calls if c.startswith("pane split")))


if __name__ == "__main__":
    unittest.main()
