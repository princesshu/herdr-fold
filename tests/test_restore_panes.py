"""Tests for restore_panes.py (fake herdr): it touches only herdr-fold's panes, agents named by `herdr agent start` (a
pane's own name does not count) and its sidebar/terminal column, and rebuilds missing columns and their programs.
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest

from support import FakeHerdrSocket, catalog_text, set_attrs, set_env

import herdrlib
import conversations  # noqa: E402  (the sidebar plugin's, on the path herdrlib gives)
import panels  # noqa: E402

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

    def restore(self, panes, agents=None, cwd=None, startup=False, space="app"):
        """panes: (tab, label, foreground programs, comma-separated) per pane of workspace w1, all in folder CWD;
        agents: {pane: name or None} — the agents herdr reports (a name: one herdr-fold started); space: the
        workspace's name. Returns the herdr calls; what it printed is in self.out."""
        module, calls, agents = load(), [], agents or {}
        listed = [{"pane_id": f"w1:p{n}", "tab_id": tab, "label": label, **({"cwd": cwd} if cwd else {})}
                  for n, (tab, label, _) in enumerate(panes, 1)]
        programs = {f"w1:p{n}": program for n, (_, _, program) in enumerate(panes, 1)}

        def herdr(*args, **_):
            calls.append(args)
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
            if args[:2] == ("pane", "close"):
                listed[:] = [p for p in listed if p["pane_id"] != args[2]]
            return {}
        module.herdr, module.POLL = herdr, 0
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            module.restore(startup=startup)
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

    def test_an_older_installs_conversations_column_goes_its_room_back_to_the_agent(self):
        # before it was a panel of the sidebar, the Conversations column stood between the agent and the right
        # column: closed, its room goes to the right column, set back to the width remembered on this machine
        tmp = tempfile.mkdtemp(dir="/tmp")                  # a short path: a socket's name has room for 104 bytes
        self.addCleanup(shutil.rmtree, tmp)
        set_env(self, HERDR_SOCKET_PATH=os.path.join(tmp, "h.sock"))
        column = {"type": "split", "direction": "down", "ratio": 0.5, "first": {"type": "pane", "pane_id": "w1:p3",
                  "label": "sidebar"}, "second": {"type": "pane", "pane_id": "w1:p4", "label": "terminal"}}
        after = {"type": "split", "direction": "right", "ratio": 0.525, "second": column,     # as herdr leaves it
                 "first": {"type": "pane", "pane_id": "w1:p1", "label": "claude"}}
        fake = FakeHerdrSocket(os.path.join(tmp, "h.sock"), {"w1:t1": (after, False)})
        self.addCleanup(fake.server.close)
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "conversations", "Python"),
                              ("w1:t1", "sidebar", "Python"), ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual(self.changes(calls), [("pane", "close", "w1:p2")])
        self.assertEqual([params for method, params in fake.calls if method == "layout.set_split_ratio"],
                         [{"tab_id": "w1:t1", "path": [], "ratio": 0.75}])
        self.assertIn(catalog_text("restore.column_gone", "this machine", "app"), self.out)

    def test_what_an_older_install_kept_for_its_column_goes(self):
        # the column's width and fold in conversations.json: gone at once, the rest kept; no file made where none was
        conversations.keep(self.state, archived=["claude:s1"])
        with open(os.path.join(self.state, conversations.SETTINGS)) as f:
            kept = {**json.load(f), "ratio": 0.62, "collapsed": True}
        with open(os.path.join(self.state, conversations.SETTINGS), "w") as f:
            json.dump(kept, f)
        self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python"), ("w1:t1", "terminal", "zsh")],
                     agents={"w1:p1": "app"})
        self.assertEqual(conversations.setting(self.state), {"archived": ["claude:s1"]})
        os.remove(os.path.join(self.state, conversations.SETTINGS))
        self.restore([("w1:t1", "claude", "claude")], agents={"w1:p1": "app"})
        self.assertFalse(os.path.exists(os.path.join(self.state, conversations.SETTINGS)))

    def test_a_sidebar_running_another_program_keeps_its_tab_as_it_is(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "herdr-sidebar"),
                              ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual([c for c in calls if c[:2] in (("pane", "close"), ("pane", "split"))], [])

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
        self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python"), ("w1:t1", "terminal", "zsh")],
                     agents={"w1:p1": "app"})
        self.assertEqual(self.out, "")

    def test_a_lone_other_program_is_left_alone(self):
        # e.g. the sidebar's file preview tab
        self.assertEqual(self.splits_of(self.restore([("w1:t2", "", "less")])), [])

    def test_a_missing_terminal_is_added_under_the_sidebar(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python")], agents={"w1:p1": "app"})
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
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual(self.sidebars_made(calls), [])

    def test_a_terminal_closed_by_hand_stays_closed(self):
        self.closed_by_hand()
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python")], agents={"w1:p1": "app"})
        self.assertNotIn("terminal", [c[3] for c in calls if c[:2] == ("pane", "rename")])

    def test_an_agent_whose_panes_were_all_closed_by_hand_gets_none_back(self):
        self.closed_by_hand()
        self.assertEqual(self.splits_of(self.restore([("w1:t1", "claude", "claude")], agents={"w1:p1": "app"})), [])

    def test_what_each_tab_has_is_kept(self):
        self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python"), ("w1:t1", "terminal", "zsh")],
                     agents={"w1:p1": "app"})
        self.assertEqual(panels.had(self.state, "w1:t1"), set(panels.KINDS))

    def sidebars_made(self, calls):
        """The new sidebar panes: split off, then named "sidebar"."""
        return [c[2] for c in calls if c[:2] == ("pane", "rename") and c[3] == "sidebar" and c[2].startswith("new")]

    def test_a_sidebar_on_windows_is_not_typed_into(self):
        # herdr on Windows names only the shell for a program that is not an agent: the sidebar may be running
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "pwsh"),
                              ("w1:t1", "terminal", "pwsh")], agents={"w1:p1": "app"}, cwd="C:\\Users\\dev\\app")
        self.assertEqual([c for c in calls if c[:2] == ("pane", "run")], [])

    def test_a_sidebar_on_windows_starts_when_herdr_starts(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "pwsh"),
                              ("w1:t1", "terminal", "pwsh")], agents={"w1:p1": "app"}, cwd="C:\\Users\\dev\\app",
                             startup=True)
        self.assertEqual([c[2] for c in calls if c[:2] == ("pane", "run")], ["w1:p2"])

if __name__ == "__main__":
    unittest.main()
