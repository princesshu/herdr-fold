"""Tests for column.py's widths through a stand-in herdr socket: the columns in a tab's layout, the share a dragged pane
keeps (not while zoomed), set on every tab to the cell."""
import json
import os
import shutil
import sys
import tempfile
import unittest

from support import SRC, FakeHerdrSocket, at_once, set_attrs, set_env

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import column  # noqa: E402
import sidebar  # noqa: E402
from column import Columns  # noqa: E402


def pane(pane_id, label):
    return {"type": "pane", "pane_id": pane_id, "label": label}


def split(direction, ratio, first, second):
    return {"type": "split", "direction": direction, "ratio": ratio, "first": first, "second": second}


def right_column(n):
    return split("down", 0.5, pane(f"w{n}:p2", "sidebar"), pane(f"w{n}:p3", "terminal"))


def tab(n, ratio=0.75):
    """An agent on the left, the right column: the sidebar above the terminal; panes wN:p1…3."""
    return split("right", ratio, pane(f"w{n}:p1", "claude"), right_column(n))


class Column(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir="/tmp")             # a short path: a socket's name has room for 104 bytes
        self.addCleanup(shutil.rmtree, self.tmp)
        self.state = os.path.join(self.tmp, "state")
        self.sock = os.path.join(self.tmp, "h.sock")
        set_env(self, HERDR_SOCKET_PATH=self.sock)
        set_attrs(self, column, SETTLE=0)

    def herdr(self, root=None, zoomed=False, **more):
        """herdr with the tab w1:t1 (ROOT, TAB by default) and the tabs MORE {tab_id: root}."""
        tabs = {"w1:t1": (root or tab(1), zoomed), **{name: (other, False) for name, other in more.items()}}
        self.fake = FakeHerdrSocket(self.sock, tabs)
        self.addCleanup(self.fake.server.close)
        return self.fake

    def write_saved(self, ratio):
        os.makedirs(self.state, exist_ok=True)
        with open(os.path.join(self.state, column.FILE), "w") as f:
            json.dump({"ratio": ratio}, f)

    def sets(self):
        return [(params["tab_id"], params["path"], params["ratio"])
                for method, params in self.fake.calls if method == "layout.set_split_ratio"]

    def test_two_jobs_keeping_at_once_lose_neither(self):
        # the dock's need job and the loop's column job write column.json on threads of their own
        at_once(column.statefile, lambda: column.need(self.state, "w1:t1", 30, {"w1:t1"}),
                lambda: column.remember(self.state, 0.6))
        self.assertEqual(column.kept(self.state), {"least": {"w1:t1": 30}, "ratio": 0.6})

    def test_the_columns_in_a_tab(self):
        self.assertEqual(column.columns({"tab_id": "w1:t1", "root": tab(1)}), Columns("w1:t1", [], 0.75, 0.25))
        nested = split("down", 0.6, tab(1), pane("w1:p9", "below"))            # the whole thing above another pane
        self.assertEqual(column.columns({"root": nested}).outer, [False])
        self.assertIsNone(column.columns({"root": pane("w1:p2", "preview")}))  # no right column

    def test_a_dragged_right_column_is_remembered_and_set_in_every_other_tab(self):
        self.herdr(tab(1, 0.6), **{"w2:t1": tab(2, 0.5), "w3:t1": tab(3, 0.6), "w4:t1": pane("w4:p1", "preview")})
        self.assertEqual(column.drag(self.state, "w1:p2", 78), 1)               # w3 is that wide already
        self.assertEqual(column.saved(self.state), 0.6)
        self.assertEqual(self.sets(), [("w2:t1", [], 0.6)])
        self.assertEqual(column.drag(self.state, "w1:p2", 78), 0)               # nothing new: nothing set

    def test_the_right_column_keeps_room_for_the_widest_head(self):
        self.assertEqual(column.NARROWEST, sidebar.narrowest(sidebar.PANELS))  # every panel's tab, the ⋯
        self.assertEqual(column.FEWEST, sidebar.narrowest(["files", "search", "changes"]))
        column.need(self.state, "w1:t1", column.NARROWEST, {"w1:t1"})
        self.herdr(tab(1, 0.9))                                             # dragged to 20 cells, 18 inside
        column.drag(self.state, "w1:p2", 18)
        self.assertEqual(self.sets(), [("w1:t1", [], 0.845)])               # 31: 29 inside, the frame 2
        self.assertEqual(column.saved(self.state), 0.845)

    def test_each_tab_keeps_room_for_its_own_sidebars_heads(self):
        column.need(self.state, "w9:t1", 23, {"w9:t1"})                     # a tab closed since: forgotten below
        column.need(self.state, "w1:t1", 23, {"w1:t1", "w3:t1"})            # no Issues here
        column.need(self.state, "w3:t1", 29, {"w1:t1", "w3:t1"})            # Issues there: the widest head
        self.assertEqual((column.least(self.state, "w1:t1"), column.least(self.state, "w3:t1")), (23, 29))
        self.assertEqual(column.least(self.state, "w5:t1"), column.FEWEST)  # not said yet: the fewest
        self.assertIsNone((column.kept(self.state).get("least") or {}).get("w9:t1"))
        self.herdr(tab(1, 0.9), **{"w3:t1": tab(3, 0.6)})                   # dragged to 18 inside
        column.drag(self.state, "w1:p2", 18)
        # this one to its own 23 (25 with the frame), the other one following but not under its 29 (31)
        self.assertEqual(self.sets(), [("w1:t1", [], 0.875), ("w3:t1", [], 0.845)])

    def test_widths_still_moving_are_not_taken(self):
        self.herdr()
        shares = iter([0.4, 0.35])                                           # the right column still moving
        set_attrs(self, column, read=lambda pane: Columns("w1:t1", [], 0.6, next(shares), 200))
        self.assertIsNone(column.settled("w1:p2"))

    def test_a_new_tab_takes_the_columns_of_the_tab_it_came_from(self):
        """A preview tab gets its columns to the cell before anything in them starts: nothing moves once they draw."""
        self.herdr(tab(1, 0.55), **{"w2:t1": tab(2, 0.7)})
        self.assertTrue(column.copy("w1:p2", "w2:p2"))
        self.assertEqual(column.cells(column.read("w2:p2")), column.cells(column.read("w1:p2")))
        self.assertFalse(column.copy("w1:p2", "w2:p2"))                    # as wide already: nothing set

    def test_a_width_is_set_to_the_cell(self):
        self.herdr(tab(1, 0.5))                                             # 200 cells: 100, 100
        self.assertEqual(column.read("w1:p2").cells, 200)
        column.arrange(column.read("w1:p2"), right=0.1776)
        widths = {r["pane_id"]: r["rect"]["width"] for r in self.fake.answer("pane.layout", {"pane_id": "w1:p2"})[
            "layout"]["panes"]}
        self.assertEqual((widths["w1:p1"], widths["w1:p2"]), (164, 36))

    def test_nothing_is_remembered_while_the_agent_is_zoomed_or_for_an_odd_share(self):
        self.herdr(zoomed=True)
        self.assertEqual(column.drag(self.state, "w1:p2", 50), 0)
        self.fake.tabs["w1:t1"] = [tab(1, 0.2), False]                      # the agent squeezed to a fifth
        self.assertEqual(column.drag(self.state, "w1:p2", 160), 0)
        self.assertIsNone(column.saved(self.state))

    def test_a_remembered_share_keeps_whatever_else_its_file_holds(self):
        os.makedirs(self.state)
        column.need(self.state, "w1:t1", 23, {"w1:t1"})
        self.assertTrue(column.remember(self.state, 0.6))
        with open(os.path.join(self.state, column.FILE)) as f:
            self.assertEqual(json.load(f), {"least": {"w1:t1": 23}, "ratio": 0.6})

    def test_without_a_herdr_or_a_remembered_width_nothing_happens(self):
        self.assertIsNone(column.read("w1:p2"))                                # no herdr listening
        self.assertEqual(column.drag(self.state, "w1:p2", 50), 0)
        self.write_saved("wide")
        self.assertIsNone(column.saved(self.state))


if __name__ == "__main__":
    unittest.main()
