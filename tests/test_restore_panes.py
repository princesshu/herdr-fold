"""Tests for restore_panes.py (fake herdr): it touches only herdr-fold's panes, agents named by `herdr agent start` (a
pane's own name does not count) and its sidebar/terminal column, and rebuilds missing columns and their programs.
"""
import contextlib
import importlib.util
import io
import os
import shutil
import tempfile
import unittest

from support import catalog_text, set_attrs

import herdrlib
import panels

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

    def restore(self, panes, agents=None, cwd=None, startup=False, refused=(), space="app"):
        """panes: (tab, label, foreground programs, comma-separated) per pane of workspace w1, all in folder CWD;
        agents: {pane: name or None} — the agents herdr reports (a name: one herdr-fold started); refused: the panes
        herdr will not close; space: the workspace's name. Returns the herdr calls; what it printed is in self.out."""
        module, calls, agents = load(), [], agents or {}
        listed = [{"pane_id": f"w1:p{n}", "tab_id": tab, "label": label, **({"cwd": cwd} if cwd else {})}
                  for n, (tab, label, _) in enumerate(panes, 1)]
        programs = {f"w1:p{n}": program for n, (_, _, program) in enumerate(panes, 1)}

        def herdr(*args, check=True):
            calls.append(args)
            if args[:2] == ("pane", "close") and args[2] in refused:
                if check:
                    raise RuntimeError("pane is busy")
                return {}
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
            if args[:2] == ("pane", "neighbor"):                        # below a tab's sidebar: its terminal
                tab = next(p["tab_id"] for p in listed if p["pane_id"] == args[3])
                below = [p["pane_id"] for p in listed if p["tab_id"] == tab and p["label"] == "terminal"]
                return {"neighbor": {"neighbor_pane_id": below[0]}} if below else {}
            if args[:2] == ("pane", "layout"):                          # agent 0-99, conversations 100-129, column
                tab = next(p["tab_id"] for p in listed if p["pane_id"] == args[3])
                x = {"conversations": 100, "sidebar": 130, "terminal": 130}
                shown = [{"pane_id": p["pane_id"], "rect": {"x": x.get(p["label"], 0), "y": 0, "height": 20,
                                                             "width": 30 if p["label"] in x else 100}}
                         for p in listed if p["tab_id"] == tab]
                return {"layout": {"panes": shown}}
            return {}
        module.herdr, module.POLL = herdr, 0
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            module.restore(startup=startup)
        self.out = out.getvalue()
        return calls

    def splits_of(self, calls):
        """Where the columns were built, beside a pane of the tab (not where the Conversations column was put beside a
        right column: that one is swapped to the left)."""
        swapped = {c[5] for c in calls if c[:2] == ("pane", "swap")}
        return [c[3] for n, c in enumerate(calls, 1)
                if c[:2] == ("pane", "split") and "right" in c and not c[3].startswith("new")
                and f"new{n}" not in swapped]

    def changes(self, calls):
        return [c for c in calls if c[:2] not in (("workspace", "list"), ("pane", "list"), ("agent", "list"),
                                                  ("pane", "process-info"), ("tab", "list"), ("pane", "layout"),
                                                  ("pane", "neighbor"))]

    def renames(self, calls):
        return [c for c in calls if c[:2] == ("workspace", "rename")]

    def test_the_home_folders_space_is_called_home(self):
        # herdr names it after the folder, ~; no tilde, and never the user's name
        calls = self.restore([("w1:t1", "", "zsh"), ("w1:t2", "", "zsh")], space="~")
        self.assertEqual(self.renames(calls), [("workspace", "rename", "w1", "home")])

    def test_a_workspaces_name_shows_without_its_escape_codes(self):
        # a workspace named elsewhere (a connected machine's herdr) may hold codes that set the title or the clipboard
        self.restore([("w1:t1", "sidebar", "zsh")], space="app\x1b]2;owned\x07")
        self.assertIn("app?]2;owned?", self.out)
        self.assertNotIn("\x1b", self.out)
        self.assertNotIn("\x07", self.out)

    def test_a_started_agent_alone_in_its_tab_gets_the_column(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t2", "", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual(self.splits_of(calls), ["w1:p1"])

    def test_a_started_agent_by_herdrs_record_not_by_the_pane_name(self):
        calls = self.restore([("w1:t1", "Colors of fruits", "claude"), ("w1:t2", "", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual(self.splits_of(calls), ["w1:p1"])

    def test_a_users_own_agent_alone_gets_no_column(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t2", "", "zsh")], agents={"w1:p1": None})
        self.assertEqual(self.changes(calls), [])

    def test_a_users_own_claude_pane_is_not_restarted(self):
        calls = self.restore([("w1:t1", "claude", "zsh"), ("w1:t2", "", "zsh")])
        self.assertEqual(self.changes(calls), [])

    def test_a_started_agent_pane_starts_its_agent_again(self):
        calls = self.restore([("w1:t1", "claude", "zsh"), ("w1:t1", "sidebar", "Python"),
                              ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app-claude"})
        self.assertEqual([c[:7] for c in calls if c[:2] == ("agent", "start")],
                         [("agent", "start", "app-claude", "--kind", "claude", "--pane", "w1:p1")])

    def test_no_agent_is_started_again_in_the_home_folders_space(self):
        # the main conversation runs there: herdr names that space ~, and the restore renames it home first
        for space in ("~", "home"):
            calls = self.restore([("w1:t1", "claude", "zsh"), ("w1:t1", "sidebar", "Python"),
                                  ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "home-claude"}, space=space)
            self.assertEqual([c for c in calls if c[:2] == ("agent", "start")], [], space)

    def test_the_conversations_column_gets_its_program_back(self):
        calls = self.restore([("w1:t1", "claude", "zsh"), ("w1:t1", "conversations", "zsh"),
                              ("w1:t1", "sidebar", "Python"), ("w1:t1", "terminal", "zsh")])
        self.assertIn(("pane", "run", "w1:p2", "bash ~/.config/herdr-fold/sidebar.sh --conversations"), calls)

    def test_every_tab_with_a_right_column_gets_the_conversations_column(self):
        panes = [("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python"), ("w1:t1", "terminal", "zsh"),
                 ("w1:t2", "claude", "claude"), ("w1:t2", "conversations", "Python"), ("w1:t2", "sidebar", "Python"),
                 ("w1:t2", "terminal", "zsh")]
        calls = self.restore(panes)
        # only the tab without it: beside the terminal (swapped to its left), the sidebar started again above that
        self.assertEqual([c[2:] for c in calls if c[:2] in (("pane", "close"), ("pane", "swap"))
                          or c[:2] == ("pane", "split")],
                         [("w1:p2",), ("--pane", "w1:p3", "--direction", "right", "--ratio", "0.4737", "--no-focus"),
                          ("--source-pane", "w1:p3", "--target-pane", f"new{self.n_of(calls, 'right')}"),
                          ("--pane", "w1:p3", "--direction", "down", "--ratio", "0.5", "--no-focus"),
                          ("--source-pane", "w1:p3", "--target-pane", f"new{self.n_of(calls, 'down')}")])
        self.assertIn(("pane", "run", f"new{self.n_of(calls, 'down')}", "bash ~/.config/herdr-fold/sidebar.sh"),
                      calls)
        self.assertIn(catalog_text("restore.conversations_added", "this machine", 1), self.out)

    def test_a_sidebar_running_another_program_keeps_its_tab_as_it_is(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "herdr-sidebar"),
                              ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual([c for c in calls if c[:2] in (("pane", "close"), ("pane", "split"))], [])

    @staticmethod
    def n_of(calls, direction):
        """The number in the name of the pane the first split in DIRECTION made (the fake names it new<n>)."""
        return next(n for n, c in enumerate(calls, 1) if c[:2] == ("pane", "split") and direction in c)

    def test_a_fresh_herdrs_only_shell_gets_the_column(self):
        # herdr makes its very first workspace before the plugins start, so the new-tab event never reaches it
        self.assertEqual(self.splits_of(self.restore([("w1:t1", "", "zsh")])), ["w1:p1"])

    def test_a_users_own_shell_tabs_get_no_column(self):
        self.assertEqual(self.changes(self.restore([("w1:t1", "", "zsh"), ("w1:t2", "", "zsh")])), [])

    def test_a_tab_with_its_column_is_left_alone(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python"),
                              ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual(self.splits_of(calls), [])

    def test_a_pane_already_running_gets_no_line(self):
        # nothing was done to it, and what program runs there is none of the user's business
        self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "conversations", "Python"),
                      ("w1:t1", "sidebar", "Python"), ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual(self.out, "")

    def test_a_lone_other_program_is_left_alone(self):
        # e.g. the sidebar's file preview tab
        self.assertEqual(self.splits_of(self.restore([("w1:t2", "", "less")])), [])

    def test_a_missing_terminal_is_added_under_the_sidebar(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python"),
                              ("w1:t1", "conversations", "Python")], agents={"w1:p1": "app"})
        splits = [c for c in calls if c[:2] == ("pane", "split")]
        self.assertEqual([(c[3], c[5]) for c in splits], [("w1:p2", "down")])
        self.assertIn("terminal", [c[3] for c in calls if c[:2] == ("pane", "rename")])

    def test_a_terminal_whose_sidebar_is_gone_gets_it_back_above(self):
        # e.g. closed by hand: the terminal keeps what runs in it, a new sidebar goes on top
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app"})
        split = [c for c in calls if c[:2] == ("pane", "split")]
        self.assertEqual([(c[3], "down" in c) for c in split], [("w1:p2", True)])
        new = f"new{calls.index(split[0]) + 1}"
        self.assertIn(("pane", "swap", "--source-pane", new, "--target-pane", "w1:p2"), calls)
        self.assertIn(("pane", "rename", new, "sidebar"), calls)
        self.assertEqual([c[2] for c in calls if c[:2] == ("pane", "run")], [new])

    def closed_by_hand(self):
        """The tab w1:t1 has had every pane: one missing now was closed by hand."""
        panels.note(self.state, {"w1:t1": set(panels.KINDS)})

    def test_a_sidebar_closed_by_hand_stays_closed(self):
        self.closed_by_hand()
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "conversations", "Python"),
                              ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual(self.sidebars_made(calls), [])

    def test_a_terminal_closed_by_hand_stays_closed(self):
        self.closed_by_hand()
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python"),
                              ("w1:t1", "conversations", "Python")], agents={"w1:p1": "app"})
        self.assertNotIn("terminal", [c[3] for c in calls if c[:2] == ("pane", "rename")])

    def test_an_agent_whose_panes_were_all_closed_by_hand_gets_none_back(self):
        self.closed_by_hand()
        self.assertEqual(self.splits_of(self.restore([("w1:t1", "claude", "claude")], agents={"w1:p1": "app"})), [])

    def test_what_each_tab_has_is_kept(self):
        self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python"), ("w1:t1", "terminal", "zsh"),
                      ("w1:t1", "conversations", "Python")], agents={"w1:p1": "app"})
        self.assertEqual(panels.had(self.state, "w1:t1"), set(panels.KINDS))

    def sidebars_made(self, calls):
        """The new sidebar panes: split off, then named "sidebar"."""
        return [c[2] for c in calls if c[:2] == ("pane", "rename") and c[3] == "sidebar" and c[2].startswith("new")]

    def test_a_sidebar_on_windows_is_not_typed_into(self):
        # herdr on Windows names only the shell for a program that is not an agent: the sidebar may be running
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "pwsh"),
                              ("w1:t1", "terminal", "pwsh"), ("w1:t1", "conversations", "pwsh")],
                             agents={"w1:p1": "app"}, cwd="C:\\Users\\dev\\app")
        self.assertEqual([c for c in calls if c[:2] == ("pane", "run")], [])

    def test_a_sidebar_on_windows_starts_when_herdr_starts(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "pwsh"),
                              ("w1:t1", "terminal", "pwsh"), ("w1:t1", "conversations", "pwsh")],
                             agents={"w1:p1": "app"}, cwd="C:\\Users\\dev\\app", startup=True)
        self.assertEqual([c[2] for c in calls if c[:2] == ("pane", "run")], ["w1:p2", "w1:p4"])

if __name__ == "__main__":
    unittest.main()
