"""Tests for herdr_layout.py: a folder's workspace (agent left, sidebar over terminal right) on this machine or a
connected one (its folder checked over SSH with remote.sh, faked). herdr is a fake that records the calls.
"""
import os
import shutil
import tempfile
import unittest

from support import set_attrs, set_env

import herdr_layout
import herdrlib


class Layout(unittest.TestCase):
    def setUp(self):
        self.calls, self.labels, self.agent_fails = [], [], False
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)
        self.state = os.path.join(self.folder, "plugin-state")              # the default widths
        set_attrs(self, herdrlib, PLUGIN_STATE=self.state)
        n = iter(range(2, 99))

        def herdr(*args, check=True):
            self.calls.append(args)
            cmd = [a for a in args if not (a == "--machine" or a == "box")][:2]
            if cmd == ["workspace", "list"]:
                return {"workspaces": [{"label": label} for label in self.labels]}
            if cmd == ["workspace", "create"]:
                return {"workspace": {"workspace_id": "w9"}, "tab": {"tab_id": "w9:t1"},
                        "root_pane": {"pane_id": "w9:p1"}}
            if cmd == ["pane", "split"]:
                return {"pane": {"pane_id": f"w9:p{next(n)}"}}
            if cmd == ["agent", "start"] and self.agent_fails:
                raise RuntimeError("the agent did not start")
            return {}
        set_attrs(self, herdr_layout, herdr=herdr,
                  machines=lambda h=None: [{"label": "box", "target": "root@box.example"}],
                  remote=lambda fn, *args: {"remote_os": "windows", "remote_path": "C:\\projects\\app",
                                            "remote_is_dir": ""}.get(fn, ""))
        set_env(self, HERDR_ENV="1")

    def named(self, *prefix):
        return [c for c in self.calls if c[:len(prefix)] == prefix]

    def test_a_local_workspace_gets_the_agent_and_the_column(self):
        lines = herdr_layout.build(None, "claude", self.folder, "My App")
        create = self.named("workspace", "create")[0]
        self.assertEqual(create[create.index("--cwd") + 1], os.path.realpath(self.folder))
        self.assertIn(("pane", "rename", "w9:p1", "claude"), self.calls)
        self.assertIn(("tab", "rename", "w9:t1", "My App"), self.calls)            # the main tab: the workspace's name
        self.assertEqual({c[3] for c in self.named("pane", "rename")}, {"claude", "sidebar", "terminal",
                                                                   "conversations"})
        start = self.named("agent", "start")[0]
        self.assertEqual(start[2], "my-app")
        self.assertTrue(lines[-1].endswith("is ready (w9)"), lines)

    def test_the_conversations_column_goes_before_the_right_column(self):
        herdr_layout.build(None, "claude", self.folder, "My App")
        # the Conversations column split off the agent's pane, then the right column off it: the two share a split
        rights = [c for c in self.named("pane", "split") if "right" in c]
        self.assertEqual([(c[3], c[c.index("--ratio") + 1]) for c in rights], [("w9:p1", "0.525"), ("w9:p2", "0.4737")])
        self.assertIn(("pane", "rename", "w9:p2", "conversations"), self.calls)
        self.assertIn(("pane", "run", "w9:p2", "bash ~/.config/herdr-fold/sidebar.sh --conversations"), self.calls)
        self.assertIn(("pane", "rename", "w9:p3", "sidebar"), self.calls)

    def test_the_home_folders_workspace_is_called_home(self):
        set_attrs(self, herdr_layout, HOME=os.path.realpath(self.folder))
        herdr_layout.build(None, "claude", self.folder)
        create = self.named("workspace", "create")[0]
        self.assertEqual(create[create.index("--label") + 1], "home")
        self.assertIn(("tab", "rename", "w9:t1", "home"), self.calls)

    def test_a_new_column_takes_the_width_last_chosen(self):
        # the sidebar remembers the share before its column when it is dragged (column.json in its state folder);
        # the agent takes 70% of that until the Conversations column is dragged
        os.makedirs(self.state)
        saved = os.path.join(self.state, "column.json")
        for content, ratio in ((None, "0.525"), ('{"ratio": 0.62}', "0.434"), ("{oops", "0.525"),
                               ('{"ratio": 0.99}', "0.525")):
            if content is not None:
                with open(saved, "w") as f:
                    f.write(content)
            self.calls.clear()
            herdrlib.add_column("w9:p1", None, h=herdr_layout.herdr)
            right = next(c for c in self.calls if c[:2] == ("pane", "split") and "right" in c)
            self.assertEqual(right[right.index("--ratio") + 1], ratio, content)

    def test_an_existing_workspace_is_not_made_twice(self):
        self.labels = ["My App"]
        lines = herdr_layout.build(None, "claude", self.folder, "My App")
        self.assertEqual(self.named("workspace", "create"), [])
        self.assertIn("[-]", lines[0])

    def test_outside_a_herdr_pane_nothing_happens(self):
        os.environ.pop("HERDR_ENV")
        with self.assertRaises(herdr_layout.LayoutError):
            herdr_layout.build(None, "claude", self.folder, "x")
        self.assertEqual(self.calls, [])

    def test_a_missing_folder_is_refused(self):
        with self.assertRaises(herdr_layout.LayoutError):
            herdr_layout.build(None, "claude", os.path.join(self.folder, "nope"), "x")

    def test_a_remote_windows_folder_gets_the_powershell_sidebar(self):
        herdr_layout.build("box", "codex", "~\\projects\\app", "app")
        self.assertTrue(all(c[:2] == ("--machine", "box") for c in self.calls))
        run = [c for c in self.calls if c[2:4] == ("pane", "run")][0]
        self.assertIn("sidebar.ps1", run[-1])

    def test_an_unknown_machine_is_refused(self):
        with self.assertRaises(herdr_layout.LayoutError):
            herdr_layout.build("nowhere", "claude", "/srv/app", "app")

    def test_an_agent_that_does_not_start_is_said(self):
        self.agent_fails = True
        lines = herdr_layout.build(None, "claude", self.folder, "My App")
        self.assertTrue(any("[!]" in line for line in lines), lines)
        self.assertTrue(lines[-1].endswith("is ready (w9)"))


if __name__ == "__main__":
    unittest.main()
