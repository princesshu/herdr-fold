"""Tests for restore_panes.py (fake herdr): it starts again only agents named by `herdr agent start` (a pane's own name
does not count), names the home folder's workspace home, and without --startup brings back the dock's columns through
the sidebar's panes.py, its moves told in the catalog's lines."""
import contextlib
import importlib.util
import io
import os
import shutil
import tempfile
import unittest

from support import catalog_text, set_attrs

import herdrlib
import panels  # noqa: E402  (the sidebar plugin's, on the path herdrlib gives)
import panes  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "restore_panes.py")


def load():
    spec = importlib.util.spec_from_file_location("restore_panes", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Restore(unittest.TestCase):
    def setUp(self):
        # a plugin state of its own: the default widths
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)
        set_attrs(self, herdrlib, PLUGIN_STATE=self.state)
        set_attrs(self, panes, POLL=0)

    def restore(self, found, agents=None, cwd=None, startup=False, space="app", machine=None, failing=()):
        """FOUND: (tab, label, foreground programs, comma-separated) per pane of workspace w1, all in folder CWD;
        AGENTS: {pane: name or None}, the agents herdr reports (a name: one herdr-fold started); SPACE: the
        workspace's name; FAILING: the calls herdr refuses. herdr's calls as MACHINE's got them; output: self.out."""
        module, calls, agents = load(), [], agents or {}
        listed = [{"pane_id": f"w1:p{n}", "tab_id": tab, "label": label, **({"cwd": cwd} if cwd else {})}
                  for n, (tab, label, _) in enumerate(found, 1)]
        programs = {f"w1:p{n}": program for n, (_, _, program) in enumerate(found, 1)}

        def herdr(*args, **_):
            self.assertEqual(args[:2], ("--machine", machine) if machine else args[:2])
            args = args[2:] if machine else args
            calls.append(args)
            if args[:2] in failing:
                raise RuntimeError("no room")
            if args[:2] == ("workspace", "list"):
                return {"workspaces": [{"workspace_id": "w1", "label": space}]}
            if args[:2] == ("pane", "list"):
                return {"panes": listed}
            if args[:2] == ("agent", "list"):
                return {"agents": [{"pane_id": p, "agent": "claude", **({"name": n} if n else {})}
                                   for p, n in agents.items()]}
            if args[:2] == ("pane", "process-info"):
                return {"process_info": {"foreground_processes": [{"name": n} for n in programs[args[3]].split(",")]}}
            if args[:2] == ("pane", "split"):
                return {"pane": {"pane_id": f"new{len(calls)}"}}
            return {}
        module.herdr = herdr
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            module.restore(machine, startup)
        self.out = out.getvalue()
        return calls

    def splits_of(self, calls):
        """Where the right columns were built: beside a pane of the tab."""
        return [c[3] for c in calls if c[:2] == ("pane", "split") and "right" in c and not c[3].startswith("new")]

    def changes(self, calls):
        return [c for c in calls if c[:2] not in (("workspace", "list"), ("pane", "list"), ("agent", "list"),
                                                  ("pane", "process-info"), ("pane", "get"))]

    def renames(self, calls):
        return [c for c in calls if c[:2] == ("workspace", "rename")]

    def test_the_home_folders_space_is_called_home(self):
        # herdr names it after the folder, ~; no tilde, and never the user's name
        for startup in (False, True):
            calls = self.restore([("w1:t1", "", "zsh"), ("w1:t2", "", "zsh")], space="~", startup=startup)
            self.assertEqual(self.renames(calls), [("workspace", "rename", "w1", "home")], startup)

    def test_a_workspaces_name_shows_without_its_escape_codes(self):
        # a workspace named elsewhere (a connected machine's herdr) may hold codes that set the title or the clipboard
        self.restore([("w1:t1", "sidebar", "zsh")], space="app\x1b]2;owned\x07")
        self.assertIn("app?]2;owned?", self.out)
        self.assertNotIn("\x1b", self.out)
        self.assertNotIn("\x07", self.out)

    def test_a_users_own_claude_pane_is_not_restarted(self):
        calls = self.restore([("w1:t1", "claude", "zsh"), ("w1:t2", "", "zsh")])
        self.assertEqual(self.changes(calls), [])

    def test_a_started_agent_pane_starts_its_agent_again(self):
        for startup in (False, True):
            calls = self.restore([("w1:t1", "claude", "zsh"), ("w1:t1", "sidebar", "Python"),
                                  ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app-claude"}, startup=startup)
            self.assertEqual([c[:7] for c in calls if c[:2] == ("agent", "start")],
                             [("agent", "start", "app-claude", "--kind", "claude", "--pane", "w1:p1")], startup)
            self.assertIn(catalog_text("restore.done", "this machine", "app", "claude",
                                       catalog_text("restore.agent_started")), self.out)

    def test_a_running_agent_is_left_as_it_is(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python"),
                              ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app-claude"})
        self.assertEqual(self.changes(calls), [])
        self.assertEqual(self.out, "")

    def test_what_could_not_be_done_is_told(self):
        self.restore([("w1:t1", "claude", "zsh"), ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app"},
                     failing={("pane", "split"), ("agent", "start")})
        self.assertIn(catalog_text("restore.sidebar_back_failed", "this machine", "app", "no room"), self.out)
        self.assertIn(catalog_text("restore.start_failed", "this machine", "app", "claude", "no room"), self.out)

    def test_no_agent_is_started_again_in_the_home_folders_space(self):
        # the main conversation runs there: herdr names that space ~, and the restore renames it home first
        for space in ("~", "home"):
            calls = self.restore([("w1:t1", "claude", "zsh"), ("w1:t1", "sidebar", "Python"),
                                  ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "home-claude"}, space=space)
            self.assertEqual([c for c in calls if c[:2] == ("agent", "start")], [], space)

    def test_the_columns_come_back_through_the_dock(self):
        # the installer's run: the dock's moves (panes.restore_all), each in the catalog's line
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t2", "", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual(self.splits_of(calls), ["w1:p1"])
        self.assertIn(catalog_text("restore.column_next_to", "this machine", "app", "claude"), self.out)
        calls = self.restore([("w1:t1", "", "zsh")])
        self.assertEqual(self.splits_of(calls), ["w1:p1"])
        self.assertIn(catalog_text("restore.done", "this machine", "app", "column",
                                   catalog_text("restore.column_added")), self.out)

    def test_a_machines_columns_come_back_with_its_own_launcher_under_its_name(self):
        # machines.sh's run, through that machine's herdr: a Windows folder there gets the PowerShell launcher
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "terminal", "pwsh")], agents={"w1:p1": "app"},
                             cwd="C:\\Users\\dev\\app", machine="mini")
        self.assertEqual([c[3] for c in calls if c[:2] == ("pane", "run")], [herdrlib.WINDOWS_SIDEBAR_COMMAND])
        self.assertIn(catalog_text("restore.sidebar_back", "mini", "app"), self.out)
        self.assertEqual(list(panels.load(self.state)), ["mini/w1:t1"])               # its tabs kept apart

    def test_at_herdrs_start_the_columns_are_left_to_the_dock(self):
        # the sidebar's own [[startup]] brings them back (panes.py --startup)
        for found, agents in (([("w1:t1", "", "zsh")], None),
                              ([("w1:t1", "claude", "claude"), ("w1:t1", "terminal", "zsh")], {"w1:p1": "app"})):
            calls = self.restore(found, agents=agents, startup=True)
            self.assertEqual(self.changes(calls), [], found)


if __name__ == "__main__":
    unittest.main()
