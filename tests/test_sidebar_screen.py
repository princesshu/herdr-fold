"""Tests for the sidebar's colors and drawing (theme.py, screen.py): cutting with "…", wide characters, names that are
not UTF-8, repainting only changed rows, colors from the terminal's palette or the theme file, and the air (AIR) every
view keeps between a row's words and the button after them."""
import json
import os
import shutil
import sys
import tempfile
import unittest

from support import SRC, set_attrs, text

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import agent_layers  # noqa: E402
import github  # noqa: E402
import layers  # noqa: E402
import widgets  # noqa: E402
from chat_list import ChatList  # noqa: E402
from chats import Chat  # noqa: E402
from explorer import Explorer  # noqa: E402
from find import Find  # noqa: E402
from git import Change, Status  # noqa: E402
from github import Issue, Listing, Pull, Query  # noqa: E402
from icons import glyphs  # noqa: E402
from issues import Issues  # noqa: E402
from pulls import PullForm, Pulls  # noqa: E402
from scm import Entry, Scm, Section  # noqa: E402
from screen import AIR, Canvas, Renderer, Style, centered, truncate, width  # noqa: E402
from theme import Theme  # noqa: E402
from tree import Tree  # noqa: E402


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


LONG = "A title long enough that it never fits beside the buttons of its row"
NERD = glyphs(True)
NOW = github.parse_time("2026-10-24T12:00:00Z")


def drawn(view, cells, rows=16, roomy=False):
    canvas = Canvas(cells, rows)
    view.draw(canvas, 0, rows, roomy)
    return canvas


def issue_list(labels=()):
    view = Issues(now=lambda: NOW)
    view.ask()
    view.show(Listing((Issue(42, LONG, labels, updated="2026-10-22T10:00:00Z"),)), Query())
    return view


def issue_row(test):
    view = issue_list()
    view.hover = 0
    return drawn(view, 44), "#42", NERD["agent"], True


def issue_states(test):                        # Open and Closed with their counts in a narrow pane: the refresh
    view = issue_list()
    view.totals = {"open": 1234, "closed": 56789}
    return drawn(view, 24), "Open", NERD["refresh"], True


def issue_field(test):                         # the words typed, the funnel at the field's end
    view = issue_list()
    view.field.text = "x" * 80
    return drawn(view, 30), "xxx", NERD["funnel"], False


def pull_list():
    view = Pulls(now=lambda: NOW)
    view.ask()
    view.show(github.Pulls((Pull(58, LONG, "fix/x", "dev", "2026-10-24T11:55:00Z", decision="APPROVED"),), "dev"),
              Query())
    return view


def pull_row(test):
    view = pull_list()
    view.hover = 0
    return drawn(view, 44), "#58", NERD["agent"], True


def pull_field(test):
    view = pull_list()
    view.field.text = "x" * 80
    return drawn(view, 30), "xxx", NERD["funnel"], False


def pull_form(test):                           # what wrote it, then ✦ again
    form = PullForm("fix/x", ["main"], icons=True)
    form.fill({"title": "Title", "body": "Body", "backend": "claude", "commits": 3})
    form.note = ("Claude wrote it from 3 commits and from the branch's name", "muted")
    canvas = Canvas(40, 20)
    form.draw(canvas, 0, False)
    return canvas, "Claude wrote", NERD["ai"], True


def changes(kind, cells, repo="app"):
    """The Changes view CELLS wide, its KIND of row (a Section or an Entry) under the mouse; None: no row."""
    view = Scm(icons=True)
    view.repo = "/work/" + repo
    view.status = Status(branch="main", upstream="origin/main", changes=[Change(f"src/{LONG.replace(' ', '-')}.py",
                                                                                "M")])
    view.graph = []
    drawn(view, cells, 30, True)
    view.hover = next((n for n, item in enumerate(view.list.items) if kind and isinstance(item, kind)), None)
    return drawn(view, cells, 30, True)


def changes_section(test):
    return changes(Section, 22), "Cha", NERD["discard"], True


def changes_entry(test):
    return changes(Entry, 30), "A-title", NERD["diff"], True


def changes_repository(test):                  # a name too long to leave its branch room: the sync's glyph
    return changes(Entry, 30, repo="a-repository-name-far-too-long-for-its-row"), "a-repo", NERD["refresh"], True


def files_header(test):
    root = os.path.join(empty_folder(test), "a-folder-with-a-name-far-too-long")
    os.mkdir(root)
    return drawn(Explorer(Tree(root), icons=True), 30, 6), "a-folder", NERD["new_file"], True


def search_field(test):                        # the words typed, its ×
    view = Find(empty_folder(test), clock=lambda: 0)
    view.field.text = "x" * 80
    return drawn(view, 40, 8), "xxx", "×", False


def chats_plan(test):                          # the done steps' row of a chosen chat's plan: their chevron
    view = ChatList(now=lambda: NOW)
    chat = Chat("claude", "s1", "Login redirect fix", "/repo/shop", NOW - 7200, "working", "w1:p1")
    view.set([chat], ["shop"], {"/repo/shop": "shop"}.get, "shop")
    view.list.index = next(n for n, row in enumerate(view.list.items) if row[1] == chat)
    view.plan = ("claude:s1", {"steps": [{"text": "Keep it", "state": "done", "after": None},
                                         {"text": "Then", "state": "now", "after": None}], "note": None,
                               "done": "12 steps done", "count": "1 of 2 done", "finished": False, "plan": 4})
    return drawn(view, 16, 12), "✓", NERD["closed"], True


def agent(title="Permissions", usage=None):
    """The Agent view 30 cells wide: its head (in a long folder), a section TITLE, Usage's head where USAGE says."""
    view = layers.Layers(icons=True)
    answer = {"agent": "claude", "folder": "/work/x", "error": None, "claude": True, "bar": [],
              "head": {"name": "Claude", "where": "in a-folder-with-a-very-long-name", "line": "", "problems": []},
              "connect": agent_layers.connecting("claude", "/work/x"),
              "sections": [{"id": "permissions", "title": title, "count": None, "tokens": None, "cost": None,
                            "swatch": None, "summary": [], "rows": [], "groups": []}]}
    view.set({**answer, "usage": {"title": usage, "rows": [], "none": "No limits told"}} if usage else answer)
    return drawn(view, 30, 12, True)


def agent_head(test):
    return agent(), "Claude", NERD["more"], True


def agent_rules(test):                         # Permissions' +, a rule added from its head
    return agent("Permissions of every kind there are"), "Permissions", "+", True


def agent_usage(test):                         # Usage's ↗ to its view
    return agent(usage="Usage of every agent on this machine"), "Usage", "↗", True


class Air(unittest.TestCase):
    """AIR blank cells between a row's words, cut with "…" where they run long, and the icon or glyph button after
    them, the buttons shown (a row under the mouse): the words give way, never the buttons."""
    CASES = (issue_row, issue_states, issue_field, pull_row, pull_field, pull_form, changes_section,
             changes_entry, changes_repository, files_header, search_field, chats_plan, agent_head, agent_rules,
             agent_usage)

    def setUp(self):
        set_attrs(self, widgets, TURN=0)                  # each fold at rest at once

    def test_a_rows_words_stand_air_cells_before_the_button_after_them(self):
        for case in self.CASES:
            with self.subTest(case.__name__):
                canvas, word, button, cut = case(self)
                row = next(text(canvas, y) for y in range(canvas.height) if word in text(canvas, y))
                at = row.index(button, row.index(word))
                words = row[:at].rstrip()
                self.assertGreaterEqual(at - len(words), AIR, row)
                if cut:
                    self.assertEqual(words[-1], "…", row)

    def test_a_changes_name_keeps_a_cell_before_gits_letter(self):
        # plain words after them: a cell of air, as a section's title keeps before its count
        canvas = changes(None, 30)
        row = next(line for line in (text(canvas, y) for y in range(30)) if "A-title" in line)
        words = row[:row.index(" M ")].rstrip()
        self.assertEqual(words[-1], "…")
        self.assertGreaterEqual(row.index(" M ") + 1 - len(words), 1)


if __name__ == "__main__":
    unittest.main()
