"""Tests for the sidebar plugin's panels.py: the panes each tab has had (so a pane closed by hand stays closed) and
bringing a pane back. herdr is a recorder."""
import json
import os
import shutil
import sys
import tempfile
import unittest

from support import SRC

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import panels  # noqa: E402


class Herdr:
    def __init__(self):
        self.calls, self.made = [], 0

    def __call__(self, *args):
        self.calls.append(" ".join(args))
        if args[:2] == ("pane", "list"):
            return {"panes": getattr(self, "listed", [])}
        if args[:2] == ("pane", "split"):
            self.made += 1
            return {"pane": {"pane_id": f"new{self.made}"}}
        return {}


class Record(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)

    def test_what_a_tab_has_had_is_kept_and_a_pane_gone_from_it_was_closed(self):
        panels.note(self.state, {"w1:t1": {"sidebar", "terminal"}, "w1:t2": {"claude"}})
        self.assertEqual(panels.had(self.state, "w1:t1"), {"sidebar", "terminal"})
        self.assertEqual(panels.had(self.state, "w1:t2"), set())                # none of the plugin's: nothing kept
        self.assertEqual(panels.closed(self.state, "w1:t1", {"sidebar"}), {"terminal"})

    def test_a_kind_an_older_version_kept_is_not_taken(self):
        # the Conversations column, before it was a panel of the sidebar: never brought back, gone on the next note
        with open(os.path.join(self.state, panels.FILE), "w") as f:
            json.dump({"w1:t1": ["conversations", "sidebar"]}, f)
        self.assertEqual(panels.had(self.state, "w1:t1"), {"sidebar"})
        panels.note(self.state, {"w1:t2": {"terminal"}})
        with open(os.path.join(self.state, panels.FILE)) as f:
            self.assertEqual(json.load(f), {"w1:t1": ["sidebar"], "w1:t2": ["terminal"]})

    def test_a_machines_tabs_are_kept_apart_and_the_tabs_gone_forgotten(self):
        panels.note(self.state, {"w1:t1": {"sidebar"}})
        panels.note(self.state, {"w1:t1": {"terminal"}}, "box")
        self.assertEqual((panels.had(self.state, "w1:t1"), panels.had(self.state, "w1:t1", "box")),
                         ({"sidebar"}, {"terminal"}))
        panels.note(self.state, {}, "box", tabs=set())                          # the machine's tab is gone
        self.assertEqual((panels.had(self.state, "w1:t1"), panels.had(self.state, "w1:t1", "box")),
                         ({"sidebar"}, set()))

    def test_the_kinds_each_tab_has_now(self):
        listed = [{"pane_id": "p1", "tab_id": "t1", "label": "claude"},
                  {"pane_id": "p2", "tab_id": "t1", "label": "sidebar"},
                  {"pane_id": "p3", "tab_id": "t2"}]
        self.assertEqual(panels.present(listed), {"t1": {"sidebar"}, "t2": set()})


class Menu(unittest.TestCase):
    def test_each_other_pane_closed_or_shown_back_in_screen_order(self):
        every = {"sidebar", "terminal"}
        self.assertEqual(panels.menu(every), ["Close terminal"])
        self.assertEqual(panels.menu({"sidebar"}), ["Show terminal", "Restore panels"])
        self.assertEqual(panels.chosen("Close terminal", every), ("close", "terminal"))
        self.assertEqual(panels.chosen("Restore panels", {"sidebar"}), ("show", {"terminal"}))
        self.assertIsNone(panels.chosen("Copy conversation", every))

    def test_a_pane_closes_as_by_hand(self):
        herdr = Herdr()
        herdr.listed = [{"pane_id": "w1:p3", "tab_id": "w1:t1", "label": "terminal"},
                        {"pane_id": "w2:p3", "tab_id": "w2:t1", "label": "terminal"}]
        panels.close(herdr, "w1:t1", "terminal")
        self.assertEqual(herdr.calls[-1], "pane close w1:p3")


class Bring(unittest.TestCase):
    def test_the_sidebar_back_above_the_terminal_which_keeps_running(self):
        herdr = Herdr()
        self.assertEqual(panels.show_sidebar(herdr, "w1:p3", "/repo", "sidebar.sh"), "new1")
        self.assertEqual(herdr.calls, ["pane split --pane w1:p3 --direction down --ratio 0.5 --cwd /repo --no-focus",
                                       "pane swap --source-pane new1 --target-pane w1:p3",
                                       "pane rename new1 sidebar", "pane run new1 sidebar.sh"])

    def test_a_terminal_back_under_the_sidebar(self):
        herdr = Herdr()
        panels.show_terminal(herdr, "w1:p2", None)
        self.assertEqual(herdr.calls, ["pane split --pane w1:p2 --direction down --ratio 0.5 --no-focus",
                                       "pane rename new1 terminal"])

    def test_the_right_column_back_beside_a_pane(self):
        herdr = Herdr()
        self.assertEqual(panels.show_column(herdr, "w1:p4", "/repo", "sidebar.sh", 0.4737), "new1")
        self.assertEqual(herdr.calls[0], "pane split --pane w1:p4 --direction right --ratio 0.4737 --cwd /repo "
                                         "--no-focus")
        self.assertIn("pane rename new2 terminal", herdr.calls)
        self.assertEqual(herdr.calls[-2:], ["pane rename new1 sidebar", "pane run new1 sidebar.sh"])


if __name__ == "__main__":
    unittest.main()
