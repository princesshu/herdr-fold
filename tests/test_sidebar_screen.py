"""Tests for the sidebar's colors and drawing (theme.py, screen.py): cutting with "…", wide characters, names that are
not UTF-8, repainting only changed rows, and colors from the terminal's palette or the theme file."""
import json
import os
import shutil
import sys
import tempfile
import unittest

from support import SRC

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
from screen import Canvas, Renderer, Style, centered, truncate, width  # noqa: E402
from theme import Theme  # noqa: E402


def empty_folder(test):
    folder = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, folder)
    return folder


class Text(unittest.TestCase):
    def test_width_counts_wide_characters_twice(self):
        self.assertEqual(width("abc"), 3)
        self.assertEqual(width("日本"), 4)
        self.assertEqual(width("\ue5ff x"), 3)                       # a Nerd Font icon is one cell

    def test_truncate_keeps_the_width(self):
        self.assertEqual(truncate("components/Hero.tsx", 10), "component…")
        self.assertEqual(width(truncate("日本語のファイル名", 7)), 7)
        self.assertEqual(width(truncate("日本語のファイル名", 6)), 6)
        self.assertEqual(truncate("short", 10), "short")

    def test_nothing_spills_past_the_edge_of_a_narrow_pane(self):
        canvas = Canvas(24, 2)
        canvas.put(0, 20, "a long file name.txt", Style())
        canvas.put(1, 23, "日本", Style())                           # a wide character that does not fit is left out
        self.assertEqual([len(row) for row in canvas.rows], [24, 24])
        self.assertEqual(canvas.rows[1][23][0], " ")

    def test_half_a_wide_character_overwritten_leaves_no_half_behind(self):
        canvas = Canvas(6, 1)
        canvas.put(0, 0, "日本語", Style())
        canvas.put(0, 1, "x", Style())                                # the right half of 日
        canvas.put(0, 4, "y", Style())                                # the left half of 語
        line = "".join(ch for ch, _ in canvas.rows[0])
        self.assertEqual(line, " x本y ")
        self.assertEqual(width(line), 6)

    def test_a_name_that_is_not_utf8_is_drawn(self):
        canvas = Canvas(8, 1)
        canvas.put(0, 0, "caf\udce9.txt", Style())                    # what scandir gives for b"caf\xe9.txt"
        line = Renderer(Theme()).line(canvas.rows[0])
        self.assertIn("caf\ufffd.txt", line)
        line.encode("utf-8")


class Shapes(unittest.TestCase):
    """The controls' shapes, square: a tall one has a half row of edge above and below its content (block characters
    the terminal draws to the cell's edges), a one-row one is a filled row; a button's icon in its middle cell."""

    def cells(self, canvas, y):
        return [(ch, style.fg, style.bg) for ch, style in canvas.rows[y]]

    def test_a_shape_is_square_with_a_half_row_above_and_below(self):
        canvas = Canvas(8, 4)
        canvas.shape(0, 1, 6, 2, "button")
        self.assertEqual("".join(ch for ch, _, _ in self.cells(canvas, 0)), " ▄▄▄▄▄▄ ")
        self.assertEqual({fg for ch, fg, _ in self.cells(canvas, 0) if ch.strip()}, {"button"})
        self.assertEqual([bg for _, _, bg in self.cells(canvas, 1)][1:7], ["button"] * 6)
        self.assertEqual([bg for _, _, bg in self.cells(canvas, 2)][1:7], ["button"] * 6)
        self.assertEqual("".join(ch for ch, _, _ in self.cells(canvas, 3)), " ▀▀▀▀▀▀ ")

    def test_a_one_row_control_is_a_filled_row(self):
        canvas = Canvas(6, 1)
        canvas.chip(0, 0, 5, "badge")
        self.assertEqual([(ch, bg) for ch, _, bg in self.cells(canvas, 0)][:5], [(" ", "badge")] * 5)

    def test_a_one_row_control_on_a_background_has_half_cells_at_its_ends(self):
        # half a cell of air round its content: block characters the terminal draws to the cell's middle
        canvas = Canvas(6, 1)
        canvas.chip(0, 1, 4, "button", under="input")
        self.assertEqual(self.cells(canvas, 0)[1:5], [("▐", "button", "input"), (" ", None, "button"),
                                                      (" ", None, "button"), ("▌", "button", "input")])

    def test_a_buttons_icon_sits_in_its_middle_cell(self):
        # the buttons' icons, codicons or plain marks, start in the middle cell
        self.assertEqual(centered(10, 5), 12)
        self.assertEqual(centered(10, 7), 13)


class Frames(unittest.TestCase):
    def setUp(self):
        self.theme = Theme.load(empty_folder(self))

    def test_only_changed_rows_are_repainted(self):
        renderer = Renderer(self.theme)
        canvas = Canvas(20, 3)
        canvas.put(0, 0, "one", Style())
        canvas.put(1, 0, "two", Style())
        first = renderer.frame(canvas)
        canvas = Canvas(20, 3)
        canvas.put(0, 0, "one", Style())
        canvas.put(1, 0, "TWO", Style())
        second = renderer.frame(canvas)
        self.assertIn("one", first)
        self.assertNotIn("one", second)
        self.assertIn("TWO", second)
        self.assertIn("\x1b[2;1H", second)                         # row 2, column 1

    def test_the_terminals_own_cursor_shows_where_a_field_takes_the_keys(self):
        renderer = Renderer(self.theme)
        canvas = Canvas(20, 3)
        canvas.cursor = (1, 4)
        self.assertTrue(renderer.frame(canvas).endswith("\x1b[2;5H\x1b[5 q\x1b[?25h"))   # a blinking bar there
        moved = Canvas(20, 3)
        moved.cursor = (1, 5)
        self.assertEqual(renderer.frame(moved), "\x1b[2;6H\x1b[5 q\x1b[?25h")             # only the cursor moved
        self.assertEqual(renderer.frame(Canvas(20, 3)), "\x1b[?25l")                        # no field takes the keys
        self.assertEqual(renderer.frame(Canvas(20, 3)), "")

    def test_a_new_size_repaints_everything(self):
        renderer = Renderer(self.theme)
        canvas = Canvas(20, 2)
        canvas.put(0, 0, "same", Style())
        renderer.frame(canvas)
        wider = Canvas(30, 2)
        wider.put(0, 0, "same", Style())
        self.assertIn("same", renderer.frame(wider))

    def test_regions_answer_clicks(self):
        canvas = Canvas(20, 3)
        canvas.region(1, 2, 8, "open README.md")
        self.assertEqual(canvas.hit(5, 1), "open README.md")
        self.assertIsNone(canvas.hit(9, 1))


class Colors(unittest.TestCase):
    def test_without_a_theme_file_the_terminals_palette(self):
        self.assertIn("33", Theme.load(empty_folder(self)).sgr(Style(fg="modified")))

    def test_without_a_theme_file_no_light_box_on_a_dark_terminal(self):
        # a machine without the theme's colors: on a dark terminal the palette's 47 is a light gray box, and the
        # status bar's text and a count's black vanish on it
        codes = set(Theme.load(empty_folder(self)).sgr(Style(fg="badge_text", bg="badge"))[2:-1].split(";"))
        self.assertEqual(codes & {"47", "107", "30"}, set())

    def test_without_a_theme_file_a_background_drawn_as_a_half_block_keeps_its_color(self):
        # a half block takes a background's color as its foreground: the palette's matching foreground code
        theme = Theme.load(empty_folder(self))
        self.assertEqual(theme.sgr(Style(fg="button", bg="input")), "\x1b[35;100m")
        self.assertEqual(theme.sgr(Style(fg="input")), "\x1b[90m")

    def test_the_theme_file_gives_exact_colors(self):
        folder = empty_folder(self)
        with open(os.path.join(folder, "colors.json"), "w") as f:
            json.dump({"modified": "#f9e2af"}, f)
        self.assertIn("38;2;249;226;175", Theme.load(folder).sgr(Style(fg="modified")))

    def test_a_damaged_theme_file_falls_back_to_the_palette(self):
        folder = empty_folder(self)
        with open(os.path.join(folder, "colors.json"), "w") as f:
            f.write("{ not json")
        self.assertIn("33", Theme.load(folder).sgr(Style(fg="modified")))


if __name__ == "__main__":
    unittest.main()
