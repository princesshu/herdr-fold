"""Tests for the dock's layout (src/plugins/sidebar/stack.py): the row of buttons of one size, each icon over its short
name, in its groups with their counts, its cells whatever the width, what each folder keeps (the view shown), and the
dock folded to its rail."""
import itertools
import json
import os
import shutil
import sys
import tempfile
import unittest

from support import SRC, at_once, text

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import column as sidebar_column  # noqa: E402
import stack  # noqa: E402
from dock import PANELS  # noqa: E402
from icons import glyphs  # noqa: E402
from screen import COUNT as ROOM, INSET, MARGIN, Canvas, Style, short_count  # noqa: E402

GROUPS = [("project", ["files", "search"]), ("work", ["changes", "issues"]), ("chats", ["chats"])]
WAITING, CHANGED = ("●", "deleted"), ("●", "modified")         # the dots: chats waiting, Changes' changes
NERD = glyphs(True)
# at its cells (70): buttons a cell in from the pane's side, a cell between two, each name in the very middle of its
# own: 9 cells for an odd name, 10 for an even one
NAMES = "   Files     Search    Changes    Issues     Chats      More"
SPANS = {"files": (1, 10), "search": (11, 21), "changes": (22, 31), "issues": (32, 42), "chats": (43, 52),
         "panels": (53, 63)}
ICONS = set(NERD.values()) | {"⋯"}   # a row's icons, More's ⋯ among them


HALF = Style(fg="hover")                # a half row of the hover color on the views' own background


def halves(canvas, y, mark):
    """The columns of row Y drawn as half rows MARK in the hover color."""
    return [x for x, (ch, style) in enumerate(canvas.rows[y]) if ch == mark and style == HALF]


def icon_columns(canvas, y=1):
    """The columns of the icons on row Y."""
    return [x for x, (ch, _) in enumerate(canvas.rows[y]) if ch in ICONS]


class Count(unittest.TestCase):
    def test_a_count_takes_four_cells_at_most_its_unit_lowercase(self):
        # up to 999 as it is; under ten of a unit one decimal, floored, none for .0; from ten on, whole
        cases = {999: "999", 1000: "1k", 1234: "1.2k", 9999: "9.9k", 18432: "18k", 111000: "111k", 999999: "999k",
                 1300000: "1.3m", 12000000: "12m", 10 ** 10: "999m"}
        self.assertEqual({n: short_count(n) for n in cases}, cases)
        self.assertEqual(max(len(short_count(n)) for n in range(0, 2 * 10 ** 6, 997)), ROOM)


class Row(unittest.TestCase):
    """The buttons on two rows a cell in from the pane's sides, a cell between two, as the first version's tabs: its
    icon over its short name in its middle, else its icon alone in 5 cells; its dot beside the icon inside it."""

    def row(self, cells=70, chosen="files", marks=None, groups=GROUPS, opened=None, pointed=None, icons=True):
        """The row on rows 1 and 2 of a canvas with the blank rows round it (0 and 3)."""
        canvas = Canvas(cells, 4)
        stack.button_row(canvas, 1, groups, chosen, marks or {}, opened, pointed, icons)
        return canvas

    def look(self, canvas, y, part):
        return canvas.rows[y][text(canvas, y).index(part)][1]

    def lit(self, canvas):
        """The cells in the hover background: {(row, column)}."""
        return {(y, x) for y, row in enumerate(canvas.rows) for x, (_, style) in enumerate(row) if style.bg == "hover"}

    def blocks(self, canvas, panels=SPANS):
        """Each button's cells on its icon's row, as the mouse finds them."""
        return [sorted(x for x in range(canvas.width) if canvas.hit(x, 1) == ("panels" if panel == "panels"
                                                                             else f"button:{panel}"))
                for panel in panels]

    def test_each_name_stands_in_the_very_middle_of_its_button_its_icon_over_it(self):
        # as much air left of a name as right of it; its icon on its middle cell, or an even one's left middle (a
        # glyph of one cell cannot stand over an even name's very middle)
        canvas = self.row(marks={"chats": WAITING, "changes": CHANGED})
        self.assertEqual(text(canvas, 2).rstrip(), NAMES)
        self.assertEqual(text(canvas, 1).rstrip(), f"     {NERD['files']}         {NERD['search']}          "
                                                   f"{NERD['git']} ●       {NERD['issues']}          "
                                                   f"{NERD['ai']} ●       {'⋯'}")
        self.assertEqual(self.blocks(canvas), [list(range(*span)) for span in SPANS.values()])
        icons = icon_columns(canvas)
        for n, (panel, (first, end)) in enumerate(SPANS.items()):
            name = NAMES.split()[n]
            at = text(canvas, 2).index(name)
            self.assertEqual((at - first, end - first), (end - at - len(name), 9 + (len(name) + 1) % 2), name)
            self.assertEqual(icons[n], at + (len(name) - 1) // 2, name)
        self.assertEqual([canvas.hit(x, 2) for x in (0, 10, 21, 63)], [None] * 4)    # the edge, between two, after

    def test_a_dot_stands_right_of_its_icon_inside_its_button_its_color_its_counts_and_moves_nothing(self):
        for cells in (70, 43):                                    # names, and the icons alone
            bare = self.row(cells)
            for marks in ({"changes": CHANGED}, {"chats": WAITING}, {"changes": CHANGED, "chats": WAITING}):
                with self.subTest(cells=cells, marks=marks):
                    canvas = self.row(cells, marks=marks)
                    self.assertEqual((icon_columns(canvas), text(canvas, 2)), (icon_columns(bare), text(bare, 2)))
                    blocks = dict(zip(SPANS, self.blocks(canvas)))
                    for panel, (dot, role) in marks.items():     # a cell of air after its icon, then the dot
                        icon = icon_columns(canvas)[list(SPANS).index(panel)]
                        self.assertEqual((text(canvas, 1)[icon + 1:icon + 3], canvas.rows[1][icon + 2][1]),
                                         (" " + dot, Style(fg=role)))
                        self.assertLessEqual(icon + 2, blocks[panel][-1])

    def test_its_names_from_its_ideal_width_its_icons_alone_down_to_its_least(self):
        # names: 9 or 10 cells each, a cell between two, else the icons alone in 5 cells each, the first version's
        # tabs; a cell in from the pane's side, then a cell of air and »'s block of an icon alone a cell in from the
        # other: the column first opens at the names, never narrower than the icons
        without = [GROUPS[0], ("work", ["changes"]), GROUPS[2]]
        self.assertEqual((stack.BUTTON, stack.ICON_BUTTON, stack.GAP), (7 + 2 * 1, 5, 1))
        self.assertEqual([stack.cells(groups, names) for groups in (GROUPS, without) for names in (True, False)],
                         [70, 43, 59, 37])
        self.assertEqual((stack.named(GROUPS, 70), stack.named(GROUPS, 69)), (True, False))
        for cells, names in ((70, True), (43, False)):            # the last button a cell of air before »'s block
            self.assertEqual(stack.laid(GROUPS, cells)[-1][2] + stack.GAP, stack.corner(cells), names)
        self.assertEqual([stack.corner(cells) for cells in (70, 43)], [64, 37])     # a cell of air after it

    def test_at_its_least_its_icons_alone_as_the_first_versions_tabs(self):
        # 5 cells each a cell in from the pane's side, a cell between two, the icon on the middle cell, a dot last
        canvas = self.row(43, marks={"chats": WAITING, "changes": CHANGED})
        self.assertEqual(text(canvas, 1).rstrip(), f"   {NERD['files']}     {NERD['search']}     {NERD['git']} ●   "
                                                   f"{NERD['issues']}     {NERD['ai']} ●   {'⋯'}")
        self.assertEqual(text(canvas, 2).strip(), "")                   # no names: the tip names one
        blocks = self.blocks(canvas)
        self.assertEqual(blocks, [list(range(x, x + 5)) for x in (1, 7, 13, 19, 25, 31)])
        self.assertEqual(icon_columns(canvas), [x + 2 for x in (1, 7, 13, 19, 25, 31)])     # the very middle

    def test_at_every_width_the_row_starts_at_the_panes_side_a_cell_between_two(self):
        # from the widest down to the least: names from 70 cells, else the icons alone, the same at every width
        # (what is left is at the right); each name in its block's middle
        marks = {"chats": WAITING, "changes": CHANGED}
        names_row, icons_row = self.row(70, marks=marks), self.row(43, marks=marks)
        for cells in range(100, 42, -1):
            with self.subTest(cells=cells):
                canvas, like = self.row(cells, marks=marks), names_row if cells >= 70 else icons_row
                self.assertEqual([text(canvas, y)[:like.width].rstrip() for y in (1, 2)],
                                 [text(like, y).rstrip() for y in (1, 2)])
                self.assertEqual(self.blocks(canvas), self.blocks(like))
                self.assertEqual(text(canvas, 1)[like.width:].strip(), "")

    def test_the_chosen_one_is_in_the_accent_its_name_bold_the_one_under_the_mouse_lit(self):
        canvas = self.row(chosen="changes", marks={"chats": WAITING, "changes": CHANGED}, pointed="button:search")
        icons = {name: self.look(canvas, 1, NERD[glyph]) for name, glyph in (("Chats", "ai"), ("Files", "files"),
                                                                              ("Search", "search"), ("Changes", "git"))}
        names = {name: self.look(canvas, 2, name) for name in icons}
        self.assertEqual(icons, {"Chats": Style(fg="subtext"), "Files": Style(fg="subtext"),
                                 "Search": Style(fg="text", bg="hover"), "Changes": Style(fg="accent")})
        self.assertEqual(names, {"Chats": Style(fg="muted"), "Files": Style(fg="muted"),
                                 "Search": Style(fg="text", bg="hover"), "Changes": Style(fg="accent", bold=True)})
        line = text(canvas, 1)
        self.assertEqual([canvas.rows[1][x][1] for x, ch in enumerate(line) if ch == "●"],
                         [Style(fg="modified"), Style(fg="deleted")])               # Changes' dot, then Chats'

    def test_the_star_with_its_list_open_is_in_the_accent_beside_the_chosen_one(self):
        canvas = self.row(opened="chats")
        self.assertEqual([self.look(canvas, 1, NERD["ai"]), self.look(canvas, 2, "Chats")],
                         [Style(fg="accent"), Style(fg="accent")])            # open, not chosen: never bold
        self.assertEqual(self.look(canvas, 2, "Files"), Style(fg="accent", bold=True))

    def test_the_button_under_the_mouse_is_lit_all_of_it(self):
        # its cells, as the first version's tall control: half a row of the hover color above (▄), its lines on it,
        # half a row below (▀), on the blank rows round the row, the last one's too (» is on the icons' line); the
        # chosen one keeps the accent; with the mouse elsewhere those rows are blank again
        marks = {"chats": WAITING, "changes": CHANGED}
        for cells, groups, names in ((70, GROUPS, True), (59, [GROUPS[0], ("work", ["changes"]), GROUPS[2]], True),
                                     (43, GROUPS, False)):
            bare, lines = self.row(cells, marks=marks, groups=groups), (1, 2) if names else (1,)
            self.assertEqual((self.lit(bare), halves(bare, 0, "▄"), halves(bare, lines[-1] + 1, "▀")), (set(), [], []))
            buttons = [panel for _group, panels in groups for panel in panels] + ["panels"]
            for panel, block in zip(buttons, self.blocks(bare, buttons)):
                with self.subTest(cells=cells, button=panel):
                    target = "panels" if panel == "panels" else f"button:{panel}"
                    canvas = self.row(cells, marks=marks, groups=groups, pointed=target)
                    self.assertEqual(self.lit(canvas), {(y, x) for y in lines for x in block})
                    self.assertTrue(0 < block[0] and block[-1] < cells - 1)          # never on the frame
                    self.assertEqual((halves(canvas, 0, "▄"), halves(canvas, lines[-1] + 1, "▀")), (block, block))
                    self.assertEqual([text(canvas, y) for y in lines], [text(bare, y) for y in lines])
        canvas = self.row(marks=marks, pointed="button:files")
        self.assertEqual(self.look(canvas, 2, "Files"), Style(fg="accent", bg="hover", bold=True))
        self.assertEqual(self.look(self.row(marks=marks, pointed="button:changes"), 1, "●"),
                         Style(fg="modified", bg="hover"))

    def test_without_a_nerd_font_the_icons_are_plain_marks(self):
        canvas = self.row(marks={"chats": WAITING, "changes": CHANGED}, icons=False)
        self.assertEqual(text(canvas, 1).rstrip(), "     ▤         ⌕          ⎇ ●       #          ✦ ●       ⋯")
        self.assertEqual(text(canvas, 2).rstrip(), NAMES)

    def test_a_group_left_without_a_view_leaves_no_gap(self):
        canvas = self.row(groups=[("work", ["changes"]), ("chats", ["chats"])], chosen="changes")
        self.assertEqual(text(canvas, 2).rstrip(), "  Changes    Chats      More")


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


    def test_an_older_versions_id_is_read_as_chats_and_written_so(self):
        with open(os.path.join(self.state, stack.FILE), "w", encoding="utf-8") as f:
            json.dump({self.one: {"shown": "conversations"}, self.two: {"shown": "files"}}, f)
        self.assertEqual(stack.state(self.state, self.one), {"shown": "chats"})
        stack.keep(self.state, self.two, "search")
        self.assertEqual(self.kept(), {self.one: {"shown": "chats"}, self.two: {"shown": "search"}})


ORDER = ["files", "search", "changes", "issues", "chats"]          # GROUPS' panels, as the rail stacks them
SIDES = ((sidebar_column.RAIL, 0), (13, 0), (19, 0), (30, 30 - sidebar_column.RAIL))   # (cells, the rail's column)


def painted(canvas):
    """The cells the hover paints: its background and its half rows."""
    return {(y, x) for y, row in enumerate(canvas.rows) for x, (ch, style) in enumerate(row)
            if style.bg == "hover" or style == HALF}


class Rail(unittest.TestCase):
    """The dock folded to its rail: the row's icons alone stacked, each a block of three rows (its own half rows round
    its icon), on the middle of its five cells (the App's own: test_sidebar.py, Rail)."""

    def test_every_item_is_its_icon_on_five_cells_three_rows_apart(self):
        # the row's icon alone on its block's middle cell, no name, a dot on the last; its own half rows, the next
        # block right under (half a row of air between two lit ones, as the row's cell); the hover paints the block,
        # all of it answers; the ones with no room left out from the end, never the lit one
        dots = {"changes": CHANGED, "chats": WAITING}
        self.assertEqual(sidebar_column.RAIL, stack.ICON_BUTTON + 2 * MARGIN)
        for (cells, left), rows, lit in itertools.product(SIDES, (15, 16, 9, 6, 3, 2), (None, "chats", "files")):
            fit = rows // 3
            shown = ORDER[:fit] if lit is None or lit in ORDER[:fit] or not fit else ORDER[:fit - 1] + [lit]
            middle = left + (cells - left) // 2
            block = list(range(middle - 2, middle + 3))
            with self.subTest(cells=cells, left=left, rows=rows, lit=lit):
                canvas = Canvas(cells, rows)
                stack.rail(canvas, 0, rows, lit, GROUPS, dots, left=left)
                self.assertEqual([(y, x) for y, row in enumerate(canvas.rows) for x, (ch, _) in enumerate(row)
                                  if ch in ICONS], [(1 + 3 * n, middle) for n in range(len(shown))])
                self.assertEqual([text(canvas, 1 + 3 * n)[middle + 1:].rstrip() for n in range(len(shown))],
                                 [f" {dots[panel][0]}" if panel in dots else "" for panel in shown])
                self.assertEqual("".join(text(canvas, 1 + 3 * n)[:middle] for n in range(len(shown))).strip(), "")
                blank = [y for y in range(rows) if y % 3 != 1 or y >= 3 * len(shown)]    # all but the icons' lines
                self.assertEqual([text(canvas, y).strip() for y in blank], [""] * len(blank))
                for n, panel in enumerate(shown):
                    canvas, top = Canvas(cells, rows), 3 * n
                    stack.rail(canvas, 0, rows, lit, GROUPS, dots, left=left, pointed=f"icon:{panel}")
                    self.assertEqual(painted(canvas), {(y, x) for y in range(top, top + 3) for x in block})
                    self.assertEqual((halves(canvas, top, "▄"), halves(canvas, top + 2, "▀")), (block, block))
                    self.assertEqual(canvas.rows[top + 1][middle][1].fg, "accent" if panel == lit else "text")
                    self.assertEqual([canvas.hit(middle, y) for y in range(top, top + 3)], [f"icon:{panel}"] * 3)

    def test_two_neighbours_keep_their_own_half_rows(self):
        # the one above's ▀ and the one below's ▄ on rows of their own: lighting one leaves the other's rows blank
        for n in range(1, len(ORDER)):
            seen = {}
            for pointed in (None, ORDER[n - 1], ORDER[n]):
                canvas = Canvas(sidebar_column.RAIL, 15)
                stack.rail(canvas, 0, 15, None, GROUPS, pointed=pointed and f"icon:{pointed}")
                seen[pointed] = (text(canvas, 3 * n - 1), text(canvas, 3 * n))
            with self.subTest(between=ORDER[n - 1:n + 1]):
                self.assertEqual(seen, {None: (" " * 5, " " * 5), ORDER[n - 1]: ("▀" * 5, " " * 5),
                                        ORDER[n]: (" " * 5, "▄" * 5)})

    def test_the_tabs_terminal_comes_after_the_views_lit_while_raised(self):
        # its own block, as theirs; the accent while it stands raised under the agent, as a view opened beside
        for raised in (False, True):
            canvas = Canvas(sidebar_column.RAIL, 21)
            stack.rail(canvas, 0, 21, None, GROUPS, terminal=raised, more=True, pointed="terminal")
            with self.subTest(raised=raised):
                self.assertEqual([text(canvas, y).strip() for y in (16, 19)], [NERD["terminal"], "⋯"])
                self.assertEqual((canvas.rows[16][2][1].fg, canvas.hit(2, 15), canvas.hit(2, 17)),
                                 ("accent" if raised else "text", "terminal", "terminal"))
                self.assertEqual(painted(canvas), {(y, x) for y in range(15, 18) for x in range(5)})

    def test_beside_a_view_the_more_button_comes_last_as_one_of_them(self):
        # the pane's own menu, ⋯ as the row's More, in a block of its own after the views'; its line returned
        canvas = Canvas(sidebar_column.RAIL, 18)
        line = stack.rail(canvas, 0, 18, None, GROUPS, more=True, pointed="panels")
        self.assertEqual((line, text(canvas, 16).rstrip(), canvas.hit(2, 15), canvas.hit(2, 17)),
                         (16, "  ⋯", "panels", "panels"))
        self.assertEqual(painted(canvas), {(y, x) for y in range(15, 18) for x in range(5)})
        self.assertIsNone(stack.rail(Canvas(sidebar_column.RAIL, 18), 0, 18, None, GROUPS))

    def test_the_lit_one_is_in_the_accent_as_the_rows_chosen_button(self):
        # no bar of its own: the row marks its chosen button by the accent alone
        canvas = Canvas(sidebar_column.RAIL, 15)
        stack.rail(canvas, 0, 15, "changes", GROUPS, {"changes": CHANGED}, pointed="icon:changes")
        self.assertEqual(painted(canvas), {(y, x) for y in range(6, 9) for x in range(0, 5)})
        self.assertEqual((canvas.rows[7][2][1], text(canvas, 7).rstrip()),
                         (Style(fg="accent", bg="hover"), f"  {NERD['git']} ●"))
        canvas = Canvas(sidebar_column.RAIL, 15)
        stack.rail(canvas, 0, 15, "changes", GROUPS)
        self.assertEqual([canvas.rows[y][2][1].fg for y in (1, 4, 7, 10, 13)],
                         ["subtext", "subtext", "accent", "subtext", "subtext"])
        self.assertNotIn("▌", "".join(text(canvas, y) for y in range(15)))

    def test_on_its_own_cells_every_item_has_as_much_air_left_as_right(self):
        # from the rail's sides: its icon on the very middle, its block as much each side inside the margins; a dot (on
        # the block's last cell) moves nothing
        dots = {"changes": CHANGED, "chats": WAITING}
        for (cells, left), lit, marks, (n, panel) in itertools.product(SIDES, (None, "changes"), ({}, dots),
                                                                       enumerate(ORDER)):
            with self.subTest(cells=cells, left=left, lit=lit, dots=bool(marks), panel=panel):
                canvas, y, last = Canvas(cells, 15), 1 + 3 * n, cells - 1
                stack.rail(canvas, 0, 15, lit, GROUPS, marks, left=left, pointed=f"icon:{panel}")
                icons = {x for row in canvas.rows for x, (ch, _) in enumerate(row) if ch in ICONS}
                self.assertEqual({x - left for x in icons}, {last - x for x in icons})
                lit_cells = sorted({x for _, x in painted(canvas)})
                self.assertEqual((lit_cells[0] - left, last - lit_cells[-1]),
                                 (MARGIN + (cells - left - sidebar_column.RAIL) // 2,) * 2)
                if panel in marks:
                    self.assertEqual(text(canvas, y).index("●"), lit_cells[-1])     # inside it, its last cell

    def test_it_stands_at_the_right_edge_the_panel_opened_beside_it_lit(self):
        left = 30 - sidebar_column.RAIL
        canvas = Canvas(30, 17)
        stack.rail(canvas, 1, 16, "changes", GROUPS, icons=False, left=left)
        marks = glyphs(False)
        icon = left + sidebar_column.RAIL // 2          # the middle of its content
        self.assertEqual([text(canvas, y)[left:].rstrip() for y in (2, 5, 8, 11, 14)],
                         [f"  {marks[glyph]}" for glyph in ("files", "search", "git", "issues", "ai")])
        self.assertEqual([canvas.rows[y][icon][1].fg for y in (2, 5, 8, 11, 14)],
                         ["subtext", "subtext", "accent", "subtext", "subtext"])
        self.assertEqual([text(canvas, y).strip() for y in range(17) if y % 3 != 2], [""] * 12)
        self.assertEqual("".join(text(canvas, y)[:left] for y in range(17)).strip(), "")


if __name__ == "__main__":
    unittest.main()
