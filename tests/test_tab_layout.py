"""Tests for the tab-layout plugin (tab_layout.py) with fake herdr calls: a new tab gets the column on Windows too,
Windows has no folder picker, and the new button's workspace is called new while its folder is chosen."""
import json
import os
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
