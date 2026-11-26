"""Tests for column.py's widths through a stand-in herdr socket: the columns in a tab's layout, the share a dragged pane
keeps (not while zoomed), set on every tab to the cell; the dock folded to its rail in every tab, its terminal under
the agent."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from support import SRC, FakeHerdrSocket, FakeTerminal, at_once, end_jobs, set_attrs, set_env

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import column  # noqa: E402
import panes  # noqa: E402
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

    def write_saved(self, cells, key="open"):
        os.makedirs(self.state, exist_ok=True)
        with open(os.path.join(self.state, column.FILE), "w") as f:
            json.dump({key: cells}, f)

    def sets(self):
        return [(params["tab_id"], params["path"], params["ratio"])
                for method, params in self.fake.calls if method == "layout.set_split_ratio"]

    def test_two_jobs_keeping_at_once_lose_neither(self):
        # the dock's need job and the loop's column job write column.json on threads of their own
        at_once(column.statefile, lambda: column.need(self.state, "w1:t1", 30, {"w1:t1"}),
                lambda: column.remember(self.state, 80))
        self.assertEqual(column.kept(self.state), {"least": {"w1:t1": 30}, "open": 80})

    def test_a_refusal_is_herdrs_own_sentence(self):
        busy = {"error": {"code": "ui_busy", "message": "a popup pane is already open"}, "id": "pane.open"}
        self.assertEqual(column.refusal(busy), "A popup pane is already open")
        self.assertEqual(column.refusal(json.dumps(busy)), "A popup pane is already open")
        self.assertEqual(column.refusal({"error": "no  such\npane"}), "No such pane")
        for none in ({"result": {}}, {"error": {"code": "ui_busy"}}, {"error": {"message": 3}}, "{not json", "plain",
                     "[1]", None, 7):
            self.assertIsNone(column.refusal(none))
        # the socket's error answer raises with it
        self.herdr()
        with mock.patch.object(column, "read_line", lambda read: json.dumps(busy).encode() + b"\n"):
            with self.assertRaises(OSError) as failed:
                column.call("pane.list", {})
        self.assertEqual(str(failed.exception), "A popup pane is already open")

    def test_the_columns_in_a_tab(self):
        self.assertEqual(column.columns({"tab_id": "w1:t1", "root": tab(1)}), Columns("w1:t1", [], 0.75, 0.25))
        nested = split("down", 0.6, tab(1), pane("w1:p9", "below"))            # the whole thing above another pane
        self.assertEqual(column.columns({"root": nested}).outer, [False])
        self.assertIsNone(column.columns({"root": pane("w1:p2", "preview")}))  # no right column

    def test_a_dragged_right_column_is_remembered_and_set_in_every_other_tab(self):
        self.herdr(tab(1, 0.55), **{"w2:t1": tab(2, 0.5), "w3:t1": tab(3, 0.55), "w4:t1": pane("w4:p1", "preview")})
        self.assertEqual(column.drag(self.state, "w1:p2", 88), 1)               # w3 is that wide already
        self.assertEqual(column.chosen(self.state), 90)                         # its cells, frame and all
        self.assertEqual(self.sets(), [("w2:t1", [], 0.55)])
        self.assertEqual(column.drag(self.state, "w1:p2", 88), 0)               # nothing new: nothing set

    def test_a_column_a_hair_short_of_every_name_snaps_up_to_them_and_a_cell(self):
        # names a cell or three short of fitting are shown: the column snaps up to them and SLACK, so herdr's rounding
        # of the split never hides them; further off, or in a window with no room for them, it stays as it is
        wide, narrow = Columns("w1:t1", [], 0.6, 0.4, 200), Columns("w1:t1", [], 0.6, 0.4, 110)
        named = column.IDEAL + column.FRAME + column.SLACK
        self.assertEqual((column.SLACK, column.SNAP, named), (1, 3, 83))
        for saved, shown in ((78, 78), (79, 83), (82, 83), (83, 83), (84, 84)):
            self.write_saved(saved)
            self.assertEqual(column.width(self.state, wide), shown / 200, saved)
        self.write_saved(80)
        self.assertEqual(column.width(self.state, narrow), column.most(110) / 110)     # 77: no room for the names
        self.herdr(tab(1, 0.6))                                                 # let go at 80 cells: up to 83
        column.drag(self.state, "w1:p2", 78)
        self.assertEqual((self.sets()[0], column.chosen(self.state)), (("w1:t1", [], 0.585), 83))

    def test_the_right_column_keeps_room_for_the_row(self):
        # the row's seven buttons (Agent among them) a cell apart, »'s block, a cell in from each side: their names
        # where the column first opens, their icons alone at its least; each the row's own cells, never a number apart
        self.assertEqual(column.NARROWEST, sidebar.narrowest(sidebar.PANELS))  # every view's button, the ⋯ and »
        self.assertEqual(column.FEWEST, sidebar.narrowest(["files", "search", "changes", "agent"]))
        self.assertEqual(column.IDEAL, sidebar.stack.cells(sidebar.grouped(sidebar.PANELS)))
        without = sidebar.grouped(["files", "search", "changes", "agent", "chats"])
        self.assertEqual((column.IDEAL, sidebar.stack.cells(without)), (80, 69))   # every name; without Issues
        self.assertEqual((column.NARROWEST, column.FEWEST), (49, 43))           # its icons alone
        column.need(self.state, "w1:t1", column.NARROWEST, {"w1:t1"})
        self.herdr(tab(1, 0.9))                                             # dragged to 20 cells, 18 inside
        column.drag(self.state, "w1:p2", 18)
        self.assertEqual(self.sets(), [("w1:t1", [], 0.745)])               # 51: 49 inside, the frame 2
        self.assertEqual(column.chosen(self.state), 51)

    def test_each_tab_keeps_room_for_its_own_sidebars_row(self):
        column.need(self.state, "w9:t1", 23, {"w9:t1"})                     # a tab closed since: forgotten below
        column.need(self.state, "w1:t1", 23, {"w1:t1", "w3:t1"})            # no Issues here
        column.need(self.state, "w3:t1", 29, {"w1:t1", "w3:t1"})            # Issues there: the wider row
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

    def test_a_drag_paused_on_its_way_has_not_rested(self):
        self.herdr(tab(1, 0.8))
        here = column.read("w1:p2")
        self.assertTrue(column.rested("w1:p2", here, 0))

        def drag_on(_seconds):
            self.fake.tabs["w1:t1"][0]["ratio"] = 0.7
        self.assertFalse(column.rested("w1:p2", here, 1, wait=drag_on))

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

    def test_nothing_is_remembered_while_the_agent_is_zoomed_or_in_a_tab_too_small(self):
        self.herdr(zoomed=True)
        self.assertEqual(column.drag(self.state, "w1:p2", 50), 0)
        self.fake.tabs["w1:t1"], self.fake.width = [tab(1, 0.2), False], 60     # the row leaves the agent under a 30 %
        self.assertEqual(column.drag(self.state, "w1:p2", 46), 0)
        self.assertIsNone(column.chosen(self.state))

    def test_a_column_dragged_past_the_agents_room_comes_back_to_it_and_is_kept_in_every_tab(self):
        # the agent keeps LIMITS[0] of the tab as the row keeps its least: dragged wider, the column comes back to the
        # most it may take, remembered and set in every tab as any drag; a narrower window opens it no wider either,
        # but never under its row
        self.herdr(tab(1, 0.2), **{"w2:t1": tab(2, 0.6)})                   # dragged to 160 of 200 cells
        self.assertEqual(column.drag(self.state, "w1:p2", 158), 1)
        self.assertEqual((self.sets(), column.chosen(self.state)), ([("w1:t1", [], 0.3), ("w2:t1", [], 0.3)], 140))
        for cells, right in ((300, 140), (150, 105), (60, column.FEWEST + column.FRAME)):
            with self.subTest(cells=cells):
                self.assertEqual(column.width(self.state, Columns("w1:t1", [], 0.5, 0.5, cells)), right / cells)

    def test_another_tabs_width_kept_over_its_own_row_is_no_drag(self):
        # a tab whose row takes more (Issues there) set to its least by another tab's drag: its own sidebar takes that
        # as nothing new, so the narrower width stays everyone else's
        column.need(self.state, "w1:t1", 49, {"w1:t1", "w2:t1"})
        column.need(self.state, "w2:t1", 43, {"w1:t1", "w2:t1"})
        column.remember(self.state, 45)                                     # w2 dragged to its least
        self.herdr(tab(1, 0.745), **{"w2:t1": tab(2, 0.775)})               # w1 at its own 51 for it
        self.assertEqual(column.drag(self.state, "w1:p2", 49), 0)
        self.assertEqual((column.chosen(self.state), self.sets()), (45, []))

    def test_a_remembered_width_keeps_whatever_else_its_file_holds(self):
        os.makedirs(self.state)
        column.need(self.state, "w1:t1", 23, {"w1:t1"})
        self.assertTrue(column.remember(self.state, 60))
        with open(os.path.join(self.state, column.FILE)) as f:
            self.assertEqual(json.load(f), {"least": {"w1:t1": 23}, "open": 60})

    def test_it_opens_at_the_rows_ideal_width_then_as_wide_as_dragged_in_cells_in_any_window(self):
        # first: every name of the row and the frame; then the cells chosen, a wider window or not
        wide, wider = Columns("w1:t1", [], 0.75, 0.25, 200), Columns("w1:t1", [], 0.75, 0.25, 300)
        self.assertEqual(column.width(self.state, wide), (column.IDEAL + column.FRAME + column.SLACK) / 200)
        self.write_saved(90)
        self.assertEqual((column.width(self.state, wide), column.width(self.state, wider)), (90 / 200, 90 / 300))

    def test_a_new_tabs_column_is_split_off_as_wide_as_chosen(self):
        self.assertEqual(column.split_share(self.state, "w1:p1"), column.RIGHT)     # no herdr to measure the tab
        self.herdr(pane("w1:p1", "claude"))                                 # the new tab: its shell alone, 200 cells
        self.assertEqual(column.split_share(self.state, "w1:p1"),
                         1 - (column.IDEAL + column.FRAME + column.SLACK) / 200)
        self.write_saved(60)
        self.assertEqual(column.split_share(self.state, "w1:p1"), 0.7)

    def test_folding_keeps_the_open_width(self):
        # folded, every tab's column the rail, as narrow as herdr lets one be; opened, as wide as last chosen again
        self.write_saved(90)
        fake = self.herdr(tab(1, 0.55), **{"w2:t1": tab(2, 0.55)})
        set_env(self, HERDR_PANE_ID="w1:p2", HOME=self.tmp)
        self.addCleanup(end_jobs)
        app = sidebar.App(self.tmp, FakeTerminal(45, 30), mock.Mock(call=fake.cli), self.state)

        def done():
            for _ in range(3):
                end_jobs()
                app.collect()

        app.fold_dock(True)
        done()
        self.assertEqual(sorted(self.sets()), [("w1:t1", [], 0.895), ("w2:t1", [], 0.895)])    # 20 and a cell: odd
        self.assertEqual((column.chosen(self.state), column.railed(self.state)), (90, True))
        fake.tabs["w1:t1"][0]["ratio"] = 0.885                               # the rail nudged 2 cells wider
        app.drag("w1:p2")
        self.assertEqual((fake.tabs["w1:t1"][0]["ratio"], column.chosen(self.state)), (0.895, 90))
        fake.width = 300                                                     # the window wider: the share kept
        app.drag("w1:p2")
        self.assertEqual((column.cells(column.read("w1:p2"))[1], column.railed(self.state)), (31, True))  # odd
        fake.width = 200
        app.fold_dock(False)
        done()
        self.assertEqual([fake.tabs[name][0]["ratio"] for name in ("w1:t1", "w2:t1")], [0.55, 0.55])
        self.assertFalse(column.railed(self.state))

    def test_a_window_resized_keeps_the_open_columns_cells(self):
        # herdr keeps each split's share as the window changes: the sidebar sets its column back to the cells chosen,
        # remembering nothing, so a narrow window and back leaves it as it was; a drag after it is still taken
        self.write_saved(90)
        fake = self.herdr(tab(1, 0.55), **{"w2:t1": tab(2, 0.55)})
        set_env(self, HERDR_PANE_ID="w1:p2", HOME=self.tmp)
        self.addCleanup(end_jobs)
        app = sidebar.App(self.tmp, FakeTerminal(88, 30), mock.Mock(call=fake.cli), self.state)
        app.reshape()
        for _ in range(3):
            end_jobs()
            app.collect()
        widths = []
        for cells in (120, 100, 200):
            fake.width = cells                                               # the window resized: the share kept
            app.drag("w1:p2")
            widths.append(column.cells(column.read("w1:p2"))[1])
        self.assertEqual((widths, column.chosen(self.state)), ([84, 70, 90], 90))   # the agent keeps 30 of the window
        self.assertEqual(fake.tabs["w2:t1"][0]["ratio"], 0.55)               # its own sidebar sets that tab
        fake.tabs["w1:t1"][0]["ratio"] = 0.55                                # then dragged to 90 cells
        app.drag("w1:p2")
        self.assertEqual((column.chosen(self.state), fake.tabs["w2:t1"][0]["ratio"]), (90, 0.55))

    def test_alone_the_rail_takes_an_odd_width_inside_the_frame(self):
        # RAIL cells, or the tenth of the tab herdr keeps at least where that is more, a cell more where that would be
        # even: each icon on the rail's very middle
        self.herdr()
        for cells in (120, 130, 155, 160, 200, 201, 333, 400):
            with self.subTest(cells=cells):
                self.fake.tabs["w1:t1"], self.fake.width = [tab(1), False], cells
                here = column.read("w1:p2")
                column.arrange(here, right=column.width(self.state, here, rail=True))
                inside = column.cells(column.read("w1:p2"))[1] - column.FRAME
                fewest = max(column.RAIL, cells - int(cells * column.SPLIT[1] + 0.5) - column.FRAME)
                self.assertEqual(inside, fewest + 1 - fewest % 2)

    def test_the_terminal_moves_under_the_agent_on_the_rail_and_back(self):
        # herdr moves no pane inside its own tab: through a new one, which goes by itself; it keeps its rows
        def side(sidebar_share):
            return split("down", sidebar_share, pane("w1:p2", "sidebar"), pane("w1:p3", "terminal"))

        fake = self.herdr(split("right", 0.75, pane("w1:p1", "claude"), side(0.7)))
        self.assertTrue(panes.place_terminal(fake.cli, "w1:p2", True))
        under = split("right", 0.75, split("down", 0.7, pane("w1:p1", "claude"), pane("w1:p3", "terminal")),
                      pane("w1:p2", "sidebar"))
        self.assertEqual(fake.tabs, {"w1:t1": [under, False]})                  # its pane id kept, no tab left over
        self.assertEqual(fake.moves, [("pane", "move", "w1:p3", "--new-tab", "--no-focus"),
                                      ("pane", "move", "w1:p3", "--tab", "w1:t1", "--target-pane", "w1:p1", "--split",
                                       "down", "--ratio", "0.7", "--no-focus")])
        self.assertFalse(panes.place_terminal(fake.cli, "w1:p2", True))         # there already: nothing moves
        self.assertTrue(panes.place_terminal(fake.cli, "w1:p2", False))
        self.assertEqual(fake.tabs, {"w1:t1": [split("right", 0.75, pane("w1:p1", "claude"), side(0.7)), False]})
        self.assertEqual(fake.moves[-1][3:9], ("--tab", "w1:t1", "--target-pane", "w1:p2", "--split", "down"))
        self.assertEqual(len(fake.moves), 4)

    def test_without_a_herdr_or_a_remembered_width_nothing_happens(self):
        self.assertIsNone(column.read("w1:p2"))                                # no herdr listening
        self.assertEqual(column.drag(self.state, "w1:p2", 50), 0)
        self.write_saved("wide")
        self.assertIsNone(column.chosen(self.state))


if __name__ == "__main__":
    unittest.main()
