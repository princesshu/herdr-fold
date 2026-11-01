"""Tests for the sidebar's search view (src/plugins/sidebar/find.py): the field and its switches, a search 150 ms after
typing stops, the hits by file, the limit, errors, stale answers dropped, previews, and nothing past 24 columns."""
import os
import sys
import unittest

from support import SRC

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
from find import DELAY, Find  # noqa: E402
from screen import Canvas  # noqa: E402
from search import Hit, Query, Result  # noqa: E402
from vt import Key, Mouse  # noqa: E402
from widgets import Action  # noqa: E402

ROOT = os.path.join(os.sep, "repo")
LONG = "a/very/deep/folder/with-a-long-file-name.py"


def content(canvas, y):
    """Row Y's text without the trailing blanks."""
    return text(canvas, y).rstrip()


def text(canvas, y):
    return "".join(ch for ch, _ in canvas.rows[y])


def three():
    return Result(hits=[Hit("src/app.py", 3, "    def foo(self):", [(8, 11)]), Hit("src/app.py", 9, "foo()", [(0, 3)]),
                        Hit("README.md", 1, "Use foo here", [(4, 7)])], total=3, files=2)


class View(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.view = Find(ROOT, clock=lambda: self.now)

    def type(self, chars):
        for ch in chars:
            self.view.handle(Key("char", ch))

    def answer(self, result, query=Query("foo")):
        self.type(query.text)
        self.view.handle(Key("enter"))
        self.view.show(result, query)

    def draw(self, width=45, height=12, roomy=False):
        self.canvas = Canvas(width, height)
        self.view.draw(self.canvas, 0, height, roomy)
        return self.canvas

    def row_of(self, part):
        return next(y for y in range(self.canvas.height) if part in text(self.canvas, y))

    def click(self, part):
        y = self.row_of(part)
        return self.view.handle(Mouse("press", text(self.canvas, y).index(part), y, 0))

    def test_a_roomy_pane_gives_the_field_three_rows_with_its_switches_inside(self):
        self.answer(three())
        self.draw(height=30, roomy=True)
        self.assertEqual([y for y in range(6) if self.canvas.rows[y][2][1].bg == "input"], [1])
        self.assertEqual((text(self.canvas, 0)[1], text(self.canvas, 2)[1]), ("▄", "▀"))   # square, half rows
        for label in ("Aa", "ab", ".*"):
            self.assertIn(label, text(self.canvas, 1))
        self.assertEqual(self.row_of("3 results"), 3)                       # right under the field's edge

    def test_a_nerd_font_icon_keeps_a_cell_of_air_before_the_name_and_the_hits_line_up(self):
        self.answer(three())
        self.draw()
        line = text(self.canvas, self.row_of("app.py"))
        name = line.index("app.py")
        self.assertEqual((line[name - 2:name], line[name - 3] != " "), ("  ", True))
        hit = text(self.canvas, self.row_of("def foo"))
        self.assertEqual(len(hit) - len(hit.lstrip()), name)                # the hit starts under the name

    def test_the_hits_stand_apart_from_the_summary(self):
        self.answer(three())
        self.draw()
        summary = self.row_of("3 results")
        self.assertEqual(text(self.canvas, summary + 1).strip(), "")
        self.assertEqual(self.row_of("app.py"), summary + 2)

    def test_typing_asks_after_a_pause(self):
        self.assertLessEqual(DELAY, 0.15)                                   # short enough to feel instant
        self.type("fo")
        self.now += DELAY * 0.7
        self.type("o")
        self.now += DELAY * 0.7
        self.assertIsNone(self.view.tick(self.now))
        self.assertAlmostEqual(self.view.deadline(), self.now + DELAY * 0.3)
        self.now += DELAY * 0.31
        self.assertEqual(self.view.tick(self.now), Action("search", (Query("foo"), "")))
        self.assertIsNone(self.view.tick(self.now + 1))
        self.assertIsNone(self.view.deadline())
        self.draw()
        self.assertIn("Searching", text(self.canvas, 2))

    def test_enter_asks_at_once(self):
        self.type("foo")
        self.assertEqual(self.view.handle(Key("enter")), Action("search", (Query("foo"), "")))
        self.assertIsNone(self.view.tick(self.now + 1))

    def test_the_switches_ask_again(self):
        self.answer(three())
        self.draw()
        self.assertTrue(content(self.canvas, 0).rstrip().endswith(".*"))
        self.assertEqual(self.click("Aa"), Action("search", (Query("foo", case=True), "")))
        self.assertEqual(self.view.handle(Key("char", "r", alt=True)),
                         Action("search", (Query("foo", case=True, regex=True), "")))
        self.draw()
        x = text(self.canvas, 0).index(".*")
        on = self.canvas.rows[0][x][1]
        self.assertEqual((on.fg, on.bg), ("button_text", "button"))                # a switch that is on is filled

    def test_a_switch_under_the_mouse_gets_a_hover_background(self):
        self.answer(three())
        self.draw()
        x = text(self.canvas, 0).index("ab")
        self.view.handle(Mouse("move", x, 0, 3))
        self.draw()
        self.assertEqual({self.canvas.rows[0][x + d][1].bg for d in (0, 1)}, {"hover"})          # its chip,
        ends = [self.canvas.rows[0][x + d] for d in (-1, 2)]                                  # half a cell round it
        self.assertEqual([(ch, style.fg, style.bg) for ch, style in ends],
                         [("▐", "hover", "input"), ("▌", "hover", "input")])
        self.assertEqual(self.canvas.rows[0][text(self.canvas, 0).index("Aa")][1].bg, "input")  # the others stay
        self.click("ab")                                                                        # on: filled
        self.draw()
        self.assertEqual(self.canvas.rows[0][x][1].bg, "button")
        self.view.handle(Mouse("move", 2, 8, 3))                                               # the mouse leaves
        self.view.handle(Key("char", "w", alt=True))
        self.draw()
        self.assertEqual(self.canvas.rows[0][x][1].bg, "input")

    def test_the_summary_and_the_hits_by_file(self):
        self.answer(three())
        canvas = self.draw()
        self.assertEqual(text(canvas, 2).strip(), "3 results in 2 files")      # a row below the field
        app = self.row_of("app.py")
        self.assertIn("src", text(canvas, app))
        self.assertTrue(content(canvas, app).endswith("2"))
        self.assertEqual(self.row_of("def foo(self):"), app + 1)
        y = self.row_of("def foo(self):")
        x = text(canvas, y).index("foo")
        self.assertEqual((canvas.rows[y][x][1].fg, canvas.rows[y][x][1].bold), ("accent", True))
        self.assertEqual(canvas.rows[y][x - 2][1].fg, "text")
        self.assertTrue(content(canvas, self.row_of("README.md")).endswith("1"))
        badge = canvas.rows[app][len(content(canvas, app)) - 1][1]
        self.assertEqual((badge.fg, badge.bg), ("badge_text", "badge"))

    def test_singular_none_cut_and_error(self):
        self.answer(Result(hits=[Hit("a.py", 1, "foo", [(0, 3)])], total=1, files=1))
        self.assertEqual(text(self.draw(), 2).strip(), "1 result in 1 file")
        self.view.show(Result(), Query("foo"))
        self.assertEqual(text(self.draw(), 2).strip(), "No results found")
        many = [Hit(f"f{i % 40}.txt", i, "foo", [(0, 3)]) for i in range(2000)]
        self.view.show(Result(hits=many, total=5321, files=60), Query("foo"))
        self.assertEqual(text(self.draw(), 2).strip(), "2000 of 5321 results shown")
        self.view.show(Result(error="invalid regex: missing ), unterminated subpattern"), Query("foo"))
        canvas = self.draw()
        self.assertIn("invalid regex", text(canvas, 2))
        self.assertEqual(canvas.rows[2][2][1].fg, "deleted")

    def test_typing_on_narrows_the_hits_at_once(self):
        # optimistic: the hits the longer text still matches stay, marked anew, before the search answers
        self.answer(three())
        self.type("(")
        canvas = self.draw()
        self.assertEqual(text(canvas, 2).strip(), "Searching…")
        self.assertFalse(any("Use foo here" in text(canvas, y) for y in range(12)))
        y = self.row_of("def foo(self):")
        line = text(canvas, y)
        marked = "".join(ch for ch, style in canvas.rows[y] if style.fg == "accent")
        self.assertEqual(marked, "foo(", line)
        self.view.show(three(), Query("foo"))                               # the shorter text's answer: stale
        self.assertEqual(text(self.draw(), 2).strip(), "Searching…")
        self.now += DELAY
        self.assertEqual(self.view.tick(self.now), Action("search", (Query("foo("), "")))

    def test_whole_word_regex_or_a_shorter_text_keep_the_hits_until_the_answer(self):
        # those can match lines the last answer had not: nothing is guessed
        for switch, keys in (("word", "("), ("regex", "("), (None, "\x7f")):
            self.setUp()
            if switch:
                self.view.switches[switch] = True
            self.answer(three(), Query("foo", **({switch: True} if switch else {})))
            if keys == "\x7f":
                self.view.handle(Key("backspace"))
            else:
                self.type(keys)
            canvas = self.draw()
            self.assertEqual(text(canvas, 2).strip(), "Searching…", switch)
            self.row_of("Use foo here")

    def test_a_stale_answer_is_dropped(self):
        self.answer(three())
        self.view.show(Result(), Query("fo"))
        self.assertEqual(text(self.draw(), 2).strip(), "3 results in 2 files")

    def test_a_folder_narrows_the_search_and_says_so(self):
        # the folder chosen in Files: above the field, in bold, before anything is typed too
        self.assertIsNone(self.view.within("src/lib"))
        canvas = self.draw()
        self.assertEqual(content(canvas, 0), " in src/lib")
        self.assertIn("Aa", text(canvas, 1))                                  # the field right under it
        name = text(canvas, 0).index("src/lib")
        self.assertEqual({(canvas.rows[0][x][1].bold, canvas.rows[0][x][1].bg) for x in range(name, name + 7)},
                         {(True, None)})
        self.type("foo")
        self.assertEqual(self.view.handle(Key("enter")), Action("search", (Query("foo"), "src/lib")))
        self.view.show(Result(), Query("foo"))                              # an answer for the whole root: stale
        self.view.show(three(), Query("foo"), "src/lib")
        canvas = self.draw()
        self.assertEqual((self.row_of("in src/lib"), self.row_of("3 results")), (0, 3))
        self.assertEqual(self.row_of("app.py"), 5)
        self.assertEqual(self.view.within("src"), Action("search", (Query("foo"), "src")))   # another: asked again
        self.assertEqual(canvas.rows[0][1][1].fg, "muted")

    def test_one_cross_in_the_field_clears_the_text_and_the_folder(self):
        self.assertNotIn("×", text(self.draw(), 0))                          # nothing to clear
        self.view.within("src")
        self.assertIn("×", text(self.draw(), 1))                             # a folder alone has it too
        self.answer(three())
        canvas = self.draw()
        field = text(canvas, 1)
        self.assertLess(field.index("×"), field.index("Aa"))                  # in the field, before the switches
        self.assertEqual(canvas.rows[1][field.index("×")][1].bg, "input")
        self.assertEqual([y for y in range(canvas.height) if "×" in text(canvas, y)], [1])    # the only one
        self.assertIsNone(self.view.handle(Mouse("press", field.index("×"), 1, 0)))
        self.assertEqual((self.view.field.text, self.view.result, self.view.place), ("", None, ""))
        canvas = self.draw()
        self.assertNotIn("×", text(canvas, 0))
        self.assertFalse(any("in src" in text(canvas, y) for y in range(canvas.height)))

    def test_esc_clears_the_text_and_the_folder_too(self):
        self.view.within("src")
        self.answer(three())
        self.assertIsNone(self.view.handle(Key("esc")))
        self.assertEqual((self.view.field.text, self.view.result, self.view.place), ("", None, ""))

    def test_enter_or_a_click_previews_the_hit(self):
        self.answer(three())
        self.draw()
        self.assertTrue(self.view.editing)
        self.view.handle(Key("down"))
        self.assertFalse(self.view.editing)
        self.view.handle(Key("down"))
        self.assertEqual(self.view.handle(Key("enter")), Action("preview_file", (os.path.join(ROOT, "src/app.py"), 3)))
        self.draw()
        self.assertEqual(self.click("Use foo here"), Action("preview_file", (os.path.join(ROOT, "README.md"), 1)))

    def test_a_file_row_folds_its_hits(self):
        self.answer(three())
        self.view.handle(Key("down"))
        self.assertIsNone(self.view.handle(Key("enter")))
        self.draw()
        self.assertFalse(any("def foo" in text(self.canvas, y) for y in range(12)))
        self.click("app.py")
        self.draw()
        self.row_of("def foo")

    def test_typing_in_the_hits_goes_back_to_the_field(self):
        self.answer(three())
        self.view.handle(Key("down"))
        self.type("d")
        self.assertTrue(self.view.editing)
        self.draw()
        self.assertIn("food", text(self.canvas, 0))
        self.view.handle(Key("esc"))
        self.draw()
        self.assertNotIn("food", text(self.canvas, 0))
        self.assertEqual(text(self.canvas, 2).strip(), "")

    def test_tab_leaves_the_field_even_without_hits(self):
        self.type("x")
        self.view.handle(Key("tab"))
        self.assertFalse(self.view.editing)                       # the app's 1 2 3 4 and q work again
        self.view.handle(Key("tab"))
        self.assertTrue(self.view.editing)
        self.assertEqual(self.view.field.text, "x")

    def test_a_switch_on_has_half_a_cell_of_air_each_side_in_the_narrowest_sidebar(self):
        # 33 columns: herdr-fold's sidebar is never narrower (its view buttons); a half block at each end
        self.answer(three())
        for name in self.view.switches:
            self.view.switches[name] = True
        canvas = self.draw(width=33)
        for label in ("Aa", "ab", ".*"):
            x = text(canvas, 0).index(label)
            self.assertEqual([canvas.rows[0][x + d][1].bg for d in (0, 1)], ["button"] * 2, label)
            self.assertEqual([(canvas.rows[0][x + d][0], canvas.rows[0][x + d][1].fg) for d in (-1, 2)],
                             [("▐", "button"), ("▌", "button")], label)
        self.assertIn("▐Aa▌▐ab▌▐.*▌", text(canvas, 0))                    # side by side: their halves the air between
        self.assertGreaterEqual(text(canvas, 0).index("Aa") - text(canvas, 0).index("foo"), 8)  # room to type

    def test_nothing_runs_past_the_edge_at_24_columns(self):
        self.answer(Result(hits=[Hit(LONG, 7, "x = foo + " + "y" * 60 + " + foo", [(4, 7), (75, 78)])],
                           total=1, files=1))
        canvas = self.draw(width=24)
        y = self.row_of("with-")
        self.assertIn("…", text(canvas, y))
        self.assertTrue(content(canvas, y).endswith("1"))
        self.assertTrue(content(canvas, 0).endswith("Aa ab .*"))           # the switches close together
        self.assertGreaterEqual(text(canvas, 0).index("Aa") - text(canvas, 0).index("foo"), 8)  # room to type
        self.assertIn("foo", text(canvas, y + 1))


if __name__ == "__main__":
    unittest.main()
