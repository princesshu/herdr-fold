"""Tests for panes.py: the right column (the sidebar above a terminal) built in a new tab as wide as in the others,
the panes a tab lacks brought back, Restore panels, the tip on a pane closed by hand, the commands typed into a
pane. herdr is a recorder."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import SRC, set_env, stubs

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import conversations  # noqa: E402
import panels  # noqa: E402
import panes  # noqa: E402


class Herdr:
    """Two tabs, each an agent and the right column (sidebar above terminal). Panes: t1 agent p1, sidebar p2,
    terminal p3; t2 p4, p5, p7. New panes are new1, new2…, listed once named."""

    def __init__(self, current="w1:t2", terminal=True):
        self.calls, self.split, self.current = [], 0, current
        self.new_in = {}                                                    # a new pane → its tab
        self.panes = []
        for tab, agent, side, term in (("w1:t1", "p1", "p2", "p3"), ("w1:t2", "p4", "p5", "p7")):
            folder = f"/repo/{tab[-1]}"
            self.panes += [{"pane_id": f"w1:{agent}", "tab_id": tab, "label": "claude", "cwd": folder},
                           {"pane_id": f"w1:{side}", "tab_id": tab, "label": "sidebar", "cwd": folder}]
            if terminal:
                self.panes.append({"pane_id": f"w1:{term}", "tab_id": tab, "label": "terminal", "cwd": folder})

    def only(self, tab, *labels):
        """TAB left with the panes of LABELS only."""
        self.panes = [p for p in self.panes if p["tab_id"] != tab or p["label"] in labels]

    def tab_of(self, pane):
        return next((p["tab_id"] for p in self.panes if p["pane_id"] == pane), None) or self.new_in.get(pane)

    def __call__(self, *args):
        self.calls.append(" ".join(args))
        if args[:2] == ("pane", "list"):
            return {"panes": self.panes}
        if args[:2] == ("pane", "current"):
            return {"pane": {"tab_id": self.current}}
        if args[:2] == ("pane", "get"):
            return {"pane": {"pane_id": args[2], "tab_id": self.tab_of(args[2])}}
        if args[:2] == ("pane", "rename") and args[2] in self.new_in:
            self.panes.append({"pane_id": args[2], "tab_id": self.new_in[args[2]], "label": args[3]})
        if args[:2] == ("pane", "split"):
            self.split += 1
            self.new_in[f"new{self.split}"] = self.tab_of(args[3])
            return {"pane": {"pane_id": f"new{self.split}", "tab_id": self.new_in[f"new{self.split}"]}}
        return {}

    def changes(self):
        return [call for call in self.calls if not call.startswith(("pane list", "pane current", "pane get"))]


class Panes(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)

    def write(self, data, name=conversations.SETTINGS):
        with open(os.path.join(self.state, name), "w") as f:
            json.dump(data, f)

    def test_the_panes_reopening_a_conversation_are_kept_with_the_rest(self):
        self.write({"show_archived": True, "resumed": ["of another shape"]})
        self.assertEqual(panes.resumed(self.state), {})
        panes.resume(self.state, "w1:p9", "s2")
        panes.resume(self.state, "w2:p3", "c1")
        self.assertEqual(panes.resumed(self.state), {"w1:p9": "s2", "w2:p3": "c1"})
        self.assertTrue(conversations.setting(self.state)["show_archived"])

    def test_a_tab_built_here_gets_the_right_column_as_wide_as_the_others(self):
        herdr = Herdr()
        self.assertEqual(panes.build(herdr, "w1:p1", "/repo/app", self.state), "new1")
        self.assertEqual(herdr.changes(), [
            "pane split --pane w1:p1 --direction right --ratio 0.75 --cwd /repo/app --no-focus",
            "pane split --pane new1 --direction down --ratio 0.5 --cwd /repo/app --no-focus",
            "pane rename new2 terminal", "pane rename new1 sidebar", f"pane run new1 {panes.sidebar_command()}"])
        self.write({"ratio": 0.8}, "column.json")                     # dragged: the right column 20%
        herdr = Herdr()
        panes.build(herdr, "w1:p1", None, self.state, sidebar_run="launcher")
        self.assertEqual(herdr.changes()[0], "pane split --pane w1:p1 --direction right --ratio 0.8 --no-focus")
        self.assertEqual(herdr.changes()[-1], "pane run new1 launcher")

    def test_a_tab_built_here_is_noted_as_having_every_pane(self):
        panes.build(Herdr(), "w1:p1", "/repo/app", self.state)
        self.assertEqual(panels.had(self.state, "w1:t1"), set(panels.KINDS))
        panes.build(Herdr(), "w1:p1", "/repo/app", self.state, scope="mini")       # a machine's tabs apart
        self.assertEqual(panels.had(self.state, "w1:t1", "mini"), set(panels.KINDS))

    def test_a_terminal_back_under_the_sidebar(self):
        herdr = Herdr(terminal=False)                                        # t1: an agent and the sidebar only
        self.assertEqual(panes.bring(herdr, "w1:t1", {"terminal"}, self.state), {"terminal"})
        self.assertEqual(herdr.changes(), [
            "pane split --pane w1:p2 --direction down --ratio 0.5 --cwd /repo/1 --no-focus",
            "pane rename new1 terminal"])
        self.assertEqual(panels.had(self.state, "w1:t1"), {"terminal"})

    def test_the_sidebar_back_above_its_terminal(self):
        herdr = Herdr()
        herdr.only("w1:t1", "claude", "terminal")
        self.assertEqual(panes.bring(herdr, "w1:t1", {"sidebar"}, self.state), {"sidebar"})
        self.assertEqual(herdr.changes(), [
            "pane split --pane w1:p3 --direction down --ratio 0.5 --cwd /repo/1 --no-focus",
            "pane swap --source-pane new1 --target-pane w1:p3",              # the terminal keeps what runs in it
            "pane rename new1 sidebar", f"pane run new1 {panes.sidebar_command()}"])

    def test_a_tab_with_neither_gets_the_whole_column(self):
        herdr = Herdr()
        herdr.only("w1:t1", "claude")
        self.assertEqual(panes.bring(herdr, "w1:t1", set(panels.KINDS), self.state), set(panels.KINDS))
        self.assertEqual(herdr.changes()[0],
                         "pane split --pane w1:p1 --direction right --ratio 0.75 --cwd /repo/1 --no-focus")

    def test_one_already_there_is_not_brought_again(self):
        herdr = Herdr()
        self.assertEqual(panes.bring(herdr, "w1:t1", set(panels.KINDS), self.state), set())
        self.assertEqual(herdr.changes(), [])

    def test_restore_panels_brings_back_every_pane_closed_in_the_tab_and_shows_the_column(self):
        herdr = Herdr(current="w1:t1", terminal=False)                       # t1: the terminal closed
        snapshot = {"snapshot": {"layouts": [{"tab_id": "w1:t1", "zoomed": True, "focused_pane_id": "w1:p1"}]}}
        call = lambda *args: snapshot if args[:2] == ("api", "snapshot") else herdr(*args)   # noqa: E731
        self.assertEqual(panes.restore(call, self.state), {"terminal"})
        self.assertEqual(herdr.calls[1], "pane zoom w1:p1 --toggle")          # the column hidden: shown first
        self.assertIn("pane rename new1 terminal", herdr.calls)

    def closed_tip(self):
        """The tip herdr shows when t1's terminal is closed by hand."""
        panels.note(self.state, {"w1:t1": {"sidebar", "terminal"}})
        herdr = Herdr()
        for listed in herdr.panes:
            listed["workspace_id"] = "w1"
        herdr.only("w1:t1", "claude", "sidebar")
        panes.tell(herdr, self.state, "w1", lambda _: None)
        return [call for call in herdr.calls if call.startswith("notification show")]

    def test_the_tip_names_the_key_only_where_herdr_has_it(self):
        # herdr-fold binds Restore panels to Cmd+Shift+O in herdr's config; the sidebar installed alone has the menus
        home = os.path.join(self.state, "home")
        set_env(self, HOME=home)
        self.assertEqual(self.closed_tip(), ["notification show Closed panels stay closed in their tab --body "
                                             "Restore panels in the ⋯ or right-click menu brings them back"])
        os.makedirs(os.path.join(home, ".config", "herdr"))
        with open(os.path.join(home, ".config", "herdr", "config.toml"), "w") as f:
            f.write('type = "plugin_action"\ncommand = "herdr-fold.sidebar.restore-panels"\n')
        os.remove(os.path.join(self.state, conversations.SETTINGS))            # told once: shown again here
        self.assertEqual(self.closed_tip(), ["notification show Closed panels stay closed in their tab --body "
                                             "Cmd+Shift+O brings them back"])

    def test_the_first_pane_closed_by_hand_brings_a_tip_once(self):
        set_env(self, HOME=os.path.join(self.state, "home"))
        panels.note(self.state, {"w1:t1": {"sidebar", "terminal"}, "w1:t2": {"sidebar", "terminal"}})
        herdr, waited = Herdr(), []
        for listed in herdr.panes:
            listed["workspace_id"] = "w1"
        self.assertFalse(panes.tell(herdr, self.state, "w1", waited.append))        # every pane still there
        herdr.only("w1:t1", "claude", "sidebar")                                     # t1's terminal closed
        self.assertTrue(panes.tell(herdr, self.state, "w1", waited.append))
        self.assertEqual(waited, [panes.SETTLE, panes.SETTLE])      # looked at once the plugin's own moves are done
        tip = [call for call in herdr.calls if call.startswith("notification show")]
        self.assertEqual(len(tip), 1)
        self.assertFalse(panes.tell(herdr, self.state, "w1", waited.append))         # never again
        self.assertEqual(len(waited), 2)

    def test_restore_from_the_command_line_builds_the_column(self):
        # herdr's Restore panels action: the tab the key is pressed in, its right column back
        bin_dir, log = os.path.join(self.state, "bin"), os.path.join(self.state, "herdr.log")
        found = json.dumps({"result": {"panes": [{"pane_id": "w1:p1", "tab_id": "w1:t1", "label": "claude",
                                                  "cwd": "/repo"}]}})
        here = json.dumps({"result": {"pane": {"pane_id": "w1:p1", "tab_id": "w1:t1"}}})
        made = json.dumps({"result": {"pane": {"pane_id": "w1:p9", "tab_id": "w1:t1"}}})
        stubs(bin_dir, {"herdr": "#!/bin/sh\n"
                                 f"printf '%s\\n' \"$*\" >> '{log}'\n"
                                 'case "$1 $2" in\n'
                                 f"  'pane list') echo '{found}' ;;\n"
                                 f"  'pane current') echo '{here}' ;;\n"
                                 f"  'pane split') echo '{made}' ;;\n"
                                 "  *) echo '{\"result\": {}}' ;;\n"
                                 "esac\n"})
        done = subprocess.run([sys.executable, panes.__file__, "--restore"], timeout=30,
                              env={"PATH": "/usr/bin:/bin", "HERDR_BIN_PATH": os.path.join(bin_dir, "herdr"),
                                   "HERDR_PLUGIN_STATE_DIR": self.state, "HOME": self.state}, capture_output=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(log) as f:
            calls = f.read().splitlines()
        self.assertIn("pane split --pane w1:p1 --direction right --ratio 0.75 --cwd /repo --no-focus", calls)
        self.assertIn("pane rename w1:p9 sidebar", calls)
        self.assertEqual(panels.had(self.state, "w1:t1"), set(panels.KINDS))
        wrong = subprocess.run([sys.executable, panes.__file__, "--bring"], capture_output=True, text=True)
        self.assertEqual(wrong.returncode, 2)
        self.assertIn("Usage:", wrong.stderr)

    def test_its_command_runs_the_sidebar_with_this_python(self):
        self.assertTrue(panes.sidebar_command(windows=False).endswith("/sidebar.py"))
        self.assertTrue(panes.sidebar_command(windows=True).startswith("& '"))
        self.assertTrue(panes.sidebar_command(windows=True).endswith("sidebar.py'"))

    def test_its_command_names_no_account(self):
        # typed into a pane's shell, the line stays in its history: a path from the home folder goes as ~ ($HOME)
        self.assertNotIn(os.path.expanduser("~") + os.sep, panes.sidebar_command(windows=False))
        mac, windows = "/Us" + "ers/dev", "C:\\Us" + "ers\\dev"
        self.assertEqual(panes.typed(mac + "/.config/x y/sidebar.py", windows=False, home=mac),
                         "~/'.config/x y/sidebar.py'")
        self.assertEqual(panes.typed("/usr/bin/python3", windows=False, home=mac), "/usr/bin/python3")
        self.assertEqual(panes.typed(windows + "\\a$b`c\\s.py", windows=True, home=windows), '"$HOME\\a`$b``c\\s.py"')
        self.assertEqual(panes.typed("D:\\py\\python.exe", windows=True, home=windows), "'D:\\py\\python.exe'")
        here = os.path.expanduser("~/.a b/c")
        out = subprocess.run(["/bin/sh", "-c", "printf %s " + panes.typed(here, windows=False)], capture_output=True,
                             text=True).stdout
        self.assertEqual(out, here)                                                 # the shell finds it again

    def test_a_folders_name_is_never_typed_into_a_pane(self):
        # herdr types a pane's command into its shell: control characters in a folder's name (a downloaded
        # repository's) would edit that line and run what follows, quotes or not; the folder goes as --cwd only
        herdr = Herdr()
        folder = "/repo/a\x15touch owned\r"
        herdr.only("w1:t1", "claude", "terminal")
        for p in herdr.panes:
            p["cwd"] = folder
        panes.bring(herdr, "w1:t1", {"sidebar"}, self.state)
        typed = [call for call in herdr.calls if call.startswith("pane run")]
        self.assertTrue(typed)
        self.assertEqual([call for call in typed if "repo" in call or "owned" in call], [])
        self.assertIn(f"--cwd {folder}", " ".join(c for c in herdr.calls if c.startswith("pane split")))


if __name__ == "__main__":
    unittest.main()
