"""Tests for toggle_column.py (Cmd+Shift+E): the right column hidden by zooming the agent and shown again, or a sidebar
or terminal closed by hand brought back instead. herdr is a recorder."""
import unittest

from support import set_attrs, set_env

import toggle_column


class Toggle(unittest.TestCase):
    def setUp(self):
        self.calls, self.brought, self.zoomed = [], [], False
        self.panes = [{"pane_id": "w1:p1", "tab_id": "w1:t1", "label": "claude"},
                      {"pane_id": "w1:p2", "tab_id": "w1:t1", "label": "sidebar"},
                      {"pane_id": "w1:p3", "tab_id": "w1:t1", "label": "terminal"}]
        set_env(self, HERDR_ACTIVE_TAB_ID="w1:t1")

        def herdr(*args, check=True):
            self.calls.append(args)
            if args[:2] == ("api", "snapshot"):
                rects = {"w1:p1": 100, "w1:p2": 30, "w1:p3": 30}
                return {"snapshot": {"layouts": [{"tab_id": "w1:t1", "zoomed": self.zoomed, "focused_pane_id": "w1:p1",
                                                  "panes": [{"pane_id": p["pane_id"], "rect": {
                                                      "width": rects[p["pane_id"]], "height": 40}}
                                                            for p in self.panes]}]}}
            if args[:2] == ("pane", "list"):
                return {"panes": self.panes}
            return {}
        set_attrs(self, toggle_column, herdr=herdr, agent_pane_ids=lambda panes: {"w1:p1"})
        set_attrs(self, toggle_column.panes,
                  bring=lambda call, tab, kinds, *rest: self.brought.append((tab, set(kinds))))

    def test_the_column_hidden_by_zooming_the_agent_and_shown_again(self):
        toggle_column.main()
        self.assertIn(("pane", "zoom", "w1:p1", "--toggle"), self.calls)
        self.calls.clear()
        self.zoomed = True
        toggle_column.main()
        self.assertEqual([c for c in self.calls if c[:2] == ("pane", "zoom")], [("pane", "zoom", "w1:p1", "--toggle")])
        self.assertEqual(self.brought, [])

    def test_a_sidebar_or_terminal_closed_by_hand_comes_back_instead(self):
        self.panes = self.panes[:1] + self.panes[2:]                        # the sidebar closed
        toggle_column.main()
        self.assertEqual(self.brought, [("w1:t1", {"sidebar"})])
        self.assertEqual([c for c in self.calls if c[:2] == ("pane", "zoom")], [])


if __name__ == "__main__":
    unittest.main()
