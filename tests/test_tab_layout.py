"""Tests for the tab-layout plugin (tab_layout.py) with fake herdr calls: a new tab gets the column on Windows too,
Windows has no folder picker, the new button's workspace is called new while its folder is chosen, and a workspace
follows its renamed folder."""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

from support import set_attrs

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "plugins", "tab-layout"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import tab_layout  # noqa: E402


class NewTabOnWindows(unittest.TestCase):
    def setUp(self):
        self.calls, self.columns = [], []
        self.saved = (tab_layout.herdr, tab_layout.add_column, tab_layout.new_workspace, tab_layout.time.sleep, os.name)

        def herdr(*args, **kwargs):
            self.calls.append(args)
            if args[:2] == ("pane", "list"):
                return {"panes": [{"pane_id": "w2:p1", "tab_id": "w2:t1", "label": None, "cwd": "C:\\Users\\dev\\app"}]}
            if args[:2] == ("pane", "process-info"):
                return {"process_info": {"foreground_processes": [{"name": "pwsh.exe"}]}}
            return {}
        tab_layout.herdr = herdr
        tab_layout.add_column = lambda pane, cwd, *rest: self.columns.append((pane, cwd))
        tab_layout.new_workspace = lambda ws: True
        tab_layout.time.sleep = lambda s: None
        os.environ["HERDR_PLUGIN_EVENT_JSON"] = json.dumps({"data": {"tab": {"tab_id": "w2:t1"}}})

    def tearDown(self):
        tab_layout.herdr, tab_layout.add_column, tab_layout.new_workspace, tab_layout.time.sleep, os.name = self.saved
        del os.environ["HERDR_PLUGIN_EVENT_JSON"]

    def test_windows_new_workspace_gets_the_column_instead_of_the_folder_picker(self):
        os.name = "nt"
        tab_layout.main()
        self.assertFalse(any(call[:2] == ("plugin", "pane") for call in self.calls))
        self.assertEqual(self.columns, [("w2:p1", "C:\\Users\\dev\\app")])

    def test_the_new_buttons_workspace_is_called_new_while_its_folder_is_chosen(self):
        # herdr names it after the folder it inherits: ~, or the active workspace's own name a second time
        os.name = "posix"
        tab_layout.main()
        opened = next(n for n, call in enumerate(self.calls) if call[:3] == ("plugin", "pane", "open"))
        self.assertIn(("workspace", "rename", "w2", "new"), self.calls[:opened])


class SpacesFollowTheirFolder(unittest.TestCase):
    """A workspace named after its folder takes the folder's new name when the folder is renamed while herdr runs
    (its panes' folders follow it there); a name you gave it stays."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.repos = os.path.join(self.tmp, "repos")
        os.makedirs(os.path.join(self.repos, "old-name", "src"))

    def path(self, *parts):
        return os.path.join(self.repos, *parts)

    def follow(self, labels, cwds, known):
        workspaces = [{"workspace_id": ws, "label": label} for ws, label in labels.items()]
        panes = [{"workspace_id": ws, "cwd": cwd} for ws, cwd in cwds]
        return tab_layout.follow_folders(workspaces, panes, known)

    def known_before_the_rename(self):
        renames, known = self.follow({"w1": "old-name"}, [("w1", self.path("old-name"))], {})
        self.assertEqual(renames, [])
        self.assertEqual(known["w1"]["label"], "old-name")
        return known

    def test_a_renamed_folder_renames_its_workspace(self):
        known = self.known_before_the_rename()
        os.rename(self.path("old-name"), self.path("new-name"))
        renames, known = self.follow({"w1": "old-name"}, [("w1", self.path("new-name"))], known)
        self.assertEqual(renames, [("w1", "old-name", "new-name")])
        self.assertEqual(known["w1"]["label"], "new-name")
        self.assertEqual(self.follow({"w1": "new-name"}, [("w1", self.path("new-name"))], known)[0], [])

    def test_a_pane_in_a_subfolder_finds_the_renamed_folder(self):
        known = self.known_before_the_rename()
        os.rename(self.path("old-name"), self.path("new-name"))
        renames, _ = self.follow({"w1": "old-name"}, [("w1", self.path("new-name", "src"))], known)
        self.assertEqual(renames, [("w1", "old-name", "new-name")])

    def test_a_name_you_gave_the_workspace_stays(self):
        known = self.known_before_the_rename()
        os.rename(self.path("old-name"), self.path("new-name"))
        renames, known = self.follow({"w1": "Frontend"}, [("w1", self.path("new-name"))], known)
        self.assertEqual((renames, known), ([], {}))
        self.assertEqual(self.follow({"w1": "Frontend"}, [("w1", self.path("new-name"))], known), ([], {}))

    def test_a_pane_gone_to_another_folder_renames_nothing(self):
        known = self.known_before_the_rename()
        os.makedirs(self.path("other"))
        self.assertEqual(self.follow({"w1": "old-name"}, [("w1", self.path("other"))], known)[0], [])

    def test_a_deleted_folder_renames_nothing(self):
        known = self.known_before_the_rename()
        os.makedirs(self.path("new-name"))                    # made first: it cannot take the deleted one's identity
        os.rmdir(self.path("old-name", "src"))
        os.rmdir(self.path("old-name"))
        self.assertEqual(self.follow({"w1": "old-name"}, [("w1", self.path("new-name"))], known)[0], [])

    def test_the_new_name_avoids_another_workspaces(self):
        known = self.known_before_the_rename()
        os.rename(self.path("old-name"), self.path("new-name"))
        renames, _ = self.follow({"w1": "old-name", "w2": "new-name"}, [("w1", self.path("new-name"))], known)
        self.assertEqual(renames, [("w1", "old-name", "repos-new-name")])

    def test_a_closed_workspace_is_forgotten(self):
        known = self.known_before_the_rename()
        self.assertEqual(self.follow({}, [], known), ([], {}))


class FollowOnFocus(unittest.TestCase):
    """On a pane's focus the plugin renames the workspace and its main tab (the one named as the workspace), never
    another tab, and keeps what it knows in its state folder."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.folder = os.path.join(self.tmp, "old-name")
        os.makedirs(self.folder)
        self.cwd, self.calls = self.folder, []

        def herdr(*args, **kwargs):
            self.calls.append(args)
            if args[:2] == ("workspace", "list"):
                return {"workspaces": [{"workspace_id": "w1", "label": "old-name"}]}
            if args[:2] == ("pane", "list"):
                return {"panes": [{"pane_id": "w1:p1", "workspace_id": "w1", "tab_id": "w1:t1", "cwd": self.cwd}]}
            if args[:2] == ("tab", "list"):
                return {"tabs": [{"tab_id": "w1:t1", "label": "old-name"}, {"tab_id": "w1:t2", "label": "Fix login"}]}
            return {}
        set_attrs(self, tab_layout, herdr=herdr)
        os.environ["HERDR_PLUGIN_STATE_DIR"] = os.path.join(self.tmp, "state")
        os.environ["HERDR_PLUGIN_EVENT"] = "pane.focused"
        self.addCleanup(os.environ.pop, "HERDR_PLUGIN_STATE_DIR")
        self.addCleanup(os.environ.pop, "HERDR_PLUGIN_EVENT")

    def test_the_workspace_and_its_main_tab_take_the_folders_new_name(self):
        tab_layout.main()
        self.assertFalse(any(call[1] == "rename" for call in self.calls))
        self.cwd = os.path.join(self.tmp, "new-name")
        os.rename(self.folder, self.cwd)
        tab_layout.main()
        renamed = [call for call in self.calls if call[1] == "rename"]
        self.assertEqual(renamed, [("workspace", "rename", "w1", "new-name"), ("tab", "rename", "w1:t1", "new-name")])

    def test_the_manifest_runs_it_on_a_panes_focus_on_macos_and_linux(self):
        # Windows does not let a folder in use be renamed
        with open(os.path.join(os.path.dirname(os.path.abspath(tab_layout.__file__)), "herdr-plugin.toml"),
                  encoding="utf-8") as f:
            manifest = f.read()
        events = re.findall(r'\[\[events\]\]\non = "pane\.focused"\nplatforms = (\[.*\])\ncommand = (\[.*\])', manifest)
        self.assertEqual(events, [('["macos", "linux"]', '["/usr/bin/python3", "tab_layout.py"]')])


if __name__ == "__main__":
    unittest.main()
