"""Tests for the dock's layout (src/plugins/sidebar/stack.py): the tab row, its groups and marks, its cells and a row
too narrow for it, what each folder keeps (the panel shown), and the dock folded to its rail."""
import json
import os
import shutil
import sys
import tempfile
import unittest

from support import SRC, at_once, text

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import stack  # noqa: E402
from icons import glyphs  # noqa: E402
from screen import Canvas, Style  # noqa: E402

GROUPS = [("conversations", ["conversations"]), ("project", ["files", "search"]), ("work", ["changes", "issues"])]
DOT, COUNT = ("●", "modified"), ("8", "modified")          # Chats' waiting dot, Changes' count


class TabRow(unittest.TestCase):
    def row(self, cells, shown="files", marks=None, groups=GROUPS, pointed=None):
        canvas = Canvas(cells, 1)
        stack.tab_row(canvas, 0, groups, shown, marks or {}, pointed)
        return canvas

    def test_the_names_stand_in_their_groups_a_wider_gap_between_two(self):
        canvas = self.row(57, marks={"conversations": DOT, "changes": COUNT})
        self.assertEqual(text(canvas, 0).rstrip(), " Chats ●   Files  Search   Changes 8  Issues")
        self.assertEqual(text(canvas, 0)[57 - stack.CONTROLS:].strip(), "")      # the dock's » and ⋯ go there

    def test_the_shown_tab_is_bold_in_the_accent_the_one_under_the_mouse_lit(self):
        canvas = self.row(57, shown="changes", marks={"conversations": DOT, "changes": COUNT}, pointed="search")
        row = text(canvas, 0)
        look = {name: canvas.rows[0][row.index(name)][1] for name in ("Chats", "Files", "Search", "Changes", "8", "●")}
        self.assertEqual(look, {"Chats": Style(fg="muted"), "Files": Style(fg="muted"), "Search": Style(fg="text"),
                                "Changes": Style(fg="accent", bold=True), "8": Style(fg="modified"),
                                "●": Style(fg="modified")})

    def test_a_click_on_a_name_or_its_mark_shows_its_panel(self):
        canvas = self.row(57, marks={"changes": COUNT})
        row = text(canvas, 0)
        changes = row.index("Changes")
        self.assertEqual({canvas.hit(x, 0) for x in range(changes, changes + len("Changes 8"))}, {"tab:changes"})
        self.assertEqual([canvas.hit(x, 0) for x in (0, changes - 1, row.index("Issues") - 1)], [None] * 3)

    def test_chats_keeps_its_dots_cells_and_the_tabs_after_it_stay_put(self):
        # a conversation starts or stops waiting at any moment: the names after it never move under the mouse
        waiting, not_waiting = (text(self.row(57, marks=marks), 0) for marks in ({"conversations": DOT}, {}))
        self.assertEqual(not_waiting.rstrip(), " Chats     Files  Search   Changes  Issues")
        self.assertEqual(waiting.index("Files"), not_waiting.index("Files"))

    def test_a_group_left_without_a_panel_leaves_no_gap(self):
        canvas = self.row(57, groups=[("project", ["files"]), ("work", ["changes"])])
        self.assertEqual(text(canvas, 0).rstrip(), " Files   Changes")

    def test_its_cells_are_every_name_and_mark_at_their_widest_and_the_controls(self):
        self.assertEqual(stack.cells(GROUPS), 57)
        self.assertEqual(stack.cells(GROUPS[:2] + [("work", ["changes"])]), 49)        # no Issues off GitHub
        widest = {"conversations": DOT, "changes": ("9" * stack.COUNT, "modified")}
        self.assertEqual(text(self.row(57, marks=widest), 0).split(),
                         ["Chats", "●", "Files", "Search", "Changes", "999", "Issues"])

    def test_a_row_too_narrow_leaves_whole_tabs_out_from_its_end_never_the_shown_one(self):
        self.assertEqual(text(self.row(56, marks={"changes": ("999", "modified")}), 0).split(),
                         ["Chats", "Files", "Search", "Changes", "999"])
        self.assertEqual(text(self.row(40, shown="issues"), 0).split(), ["Chats", "Files", "Issues"])
        self.assertEqual(text(self.row(16, shown="search"), 0).strip(), "")       # its name never cut short


class Kept(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)
        self.one, self.two = (os.path.join(self.state, name) for name in ("one", "two"))
        for folder in (self.one, self.two):
            os.mkdir(folder)

    def kept(self):
        with open(os.path.join(self.state, stack.FILE), encoding="utf-8") as f:
            return json.load(f)

    def test_each_folder_keeps_the_panel_it_shows(self):
        stack.keep(self.state, self.one, "issues")
        stack.keep(self.state, self.two, "search")
        self.assertEqual([stack.state(self.state, folder) for folder in (self.one, self.two)],
                         [{"shown": "issues"}, {"shown": "search"}])
        self.assertEqual(stack.state(self.state, os.path.join(self.state, "three")), {"shown": None})

    def test_a_gone_folder_is_forgotten(self):
        stack.keep(self.state, self.one, "changes")
        os.rmdir(self.one)
        stack.keep(self.state, self.two, "files")
        self.assertEqual(self.kept(), {self.two: {"shown": "files"}})

    def test_two_sidebars_changing_at_once_keep_both_changes(self):
        at_once(stack.statefile, lambda: stack.keep(self.state, self.one, "changes"),
                lambda: stack.keep(self.state, self.two, "issues"))
        self.assertEqual(self.kept(), {self.one: {"shown": "changes"}, self.two: {"shown": "issues"}})

    def test_what_it_cannot_read_is_nothing_kept(self):
        with open(os.path.join(self.state, stack.FILE), "w", encoding="utf-8") as f:
            f.write('{"%s": {"shown": [1]}, "%s": "files"}' % (self.one, self.two))
        self.assertEqual([stack.state(self.state, folder) for folder in (self.one, self.two)], [{"shown": None}] * 2)

    def test_an_older_versions_groups_are_read_as_nothing_and_go_at_the_next_write(self):
        # the stacked groups' file: each group's panel, the folded ones and their shares
        older = {"shown": {"work": "issues"}, "folded": ["project"], "weights": {"project": 0.3, "work": 0.7}}
        with open(os.path.join(self.state, stack.FILE), "w", encoding="utf-8") as f:
            json.dump({self.one: older, self.two: older}, f)
        self.assertEqual(stack.state(self.state, self.one), {"shown": None})
        stack.keep(self.state, self.one, "files")
        self.assertEqual(self.kept(), {self.one: {"shown": "files"}})


class Rail(unittest.TestCase):
    """The dock folded to its rail: each panel's icon over its name (the App's own: test_sidebar.py, Rail)."""

    def test_a_panel_the_rows_have_no_room_for_is_left_out(self):
        canvas = Canvas(9, 8)
        stack.rail(canvas, 0, 8, None, GROUPS, icons=False)
        self.assertEqual([canvas.hit(0, y) for y in range(8)], ["icon:conversations"] * 2 + [None]
                         + ["icon:files"] * 2 + ["icon:search"] * 2 + [None])        # Changes' two rows: not one

    def test_it_stands_at_the_right_edge_the_panel_opened_beside_it_lit(self):
        canvas = Canvas(30, 13)
        stack.rail(canvas, 1, 12, "changes", GROUPS, icons=False, left=21)
        marks = glyphs(False)
        self.assertEqual(text(canvas, 9)[21:].rstrip(), f"▌   {marks['git']}")    # a bar at its edge, the icon in
        self.assertEqual(text(canvas, 10)[21:], " Changes ")                        # the middle, its name under it
        self.assertEqual([canvas.rows[9][25][1].fg, canvas.rows[10][22][1]], ["accent", Style(fg="accent", bold=True)])
        self.assertEqual((text(canvas, 11)[25], canvas.rows[11][25][1].fg, canvas.rows[12][22][1].fg),
                         (marks["issues"], "subtext", "muted"))
        self.assertEqual("".join(text(canvas, y)[:21] for y in range(13)).strip(), "")


if __name__ == "__main__":
    unittest.main()
