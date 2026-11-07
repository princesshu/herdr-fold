"""Tests for the sidebar's controls (src/plugins/sidebar/widgets.py): a list, a text field, a drop-down menu, and a
confirmation whose Enter means the safe answer unless the other button is chosen."""
import os
import sys
import unittest

from support import SRC

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
from screen import Canvas  # noqa: E402
from vt import Key  # noqa: E402
from widgets import Confirm, ListView, Menu, TextInput  # noqa: E402


def typed(field, text):
    for ch in text:
        field.handle(Key("char", ch))


def text(canvas, y):
    return "".join(ch for ch, _ in canvas.rows[y]).rstrip()


class Lists(unittest.TestCase):
    def setUp(self):
        self.view = ListView(10)
        self.view.set(range(100))

    def test_the_selection_stays_in_view(self):
        self.view.move(15)
        self.assertEqual((self.view.index, self.view.top), (15, 6))
        self.view.page(-1)
        self.assertEqual((self.view.index, self.view.top), (5, 5))

    def test_rows_map_to_items(self):
        self.view.move(15)
        self.assertEqual(self.view.at(3), 9)
        self.assertIsNone(self.view.at(10))

    def test_no_running_past_the_ends(self):
        self.view.move(1000)
        self.assertEqual((self.view.index, self.view.top), (99, 90))
        self.view.move(-1000)
        self.assertEqual((self.view.index, self.view.top), (0, 0))

    def test_the_wheel_scrolls_without_moving_the_selection(self):
        self.view.scroll(5)
        self.assertEqual((self.view.index, self.view.top), (0, 5))

    def test_a_taller_view_fills_up_from_the_end(self):
        self.view.move(1000)
        self.view.resize(30)
        self.assertEqual((self.view.index, self.view.top), (99, 70))

    def test_a_shorter_list_keeps_a_valid_selection(self):
        self.view.move(50)
        self.view.set(range(3))
        self.assertEqual((self.view.index, self.view.top), (2, 0))


class Text(unittest.TestCase):
    def test_typing_and_inserting_in_the_middle(self):
        field = TextInput()
        typed(field, "helo")
        field.handle(Key("left"))
        typed(field, "l")
        self.assertEqual((field.text, field.cursor), ("hello", 4))

    def test_backspace_at_the_start_does_nothing_and_ctrl_u_clears(self):
        field = TextInput()
        field.handle(Key("backspace"))
        typed(field, "abc")
        field.handle(Key("char", "u", ctrl=True))
        self.assertEqual(field.text, "")

    def test_enter_starts_a_new_line_only_in_a_multiline_field(self):
        one, many = TextInput(), TextInput(multiline=True)
        for field in (one, many):
            typed(field, "a")
            self.assertEqual(field.handle(Key("enter")), field is many)
            typed(field, "b")
        self.assertEqual((one.text, many.text), ("ab", "a\nb"))

    def test_pasted_text_arrives_in_one_piece(self):
        field = TextInput(multiline=True)
        field.handle(Key("paste", "line one\nline two"))
        self.assertEqual(field.text, "line one\nline two")
        single = TextInput()
        single.handle(Key("paste", "a\nb"))
        self.assertEqual(single.text, "a b")

    def test_a_focused_field_keeps_every_letter_and_leaves_the_cursor_to_the_terminal(self):
        # a cursor drawn as a character would hide the letter under it: the placeholder's first one, or one typed
        field = TextInput(placeholder="Search")
        canvas = Canvas(20, 1)
        field.draw(canvas, 0, 2, 10, 1, focused=True)
        self.assertEqual("".join(ch for ch, _ in canvas.rows[0])[2:8], "Search")
        self.assertEqual(canvas.cursor, (0, 2))
        field.insert("needle")
        field.cursor = 2
        canvas = Canvas(20, 1)
        field.draw(canvas, 0, 2, 10, 1, focused=True)
        self.assertEqual("".join(ch for ch, _ in canvas.rows[0])[2:8], "needle")
        self.assertEqual(canvas.cursor, (0, 4))                             # before the first "e", a bar
        canvas = Canvas(20, 1)
        field.draw(canvas, 0, 2, 10, 1)
        self.assertIsNone(canvas.cursor)

    def test_rows_break_between_words(self):
        # a word goes whole to the next row; the space it breaks at stays at the end of the row before
        field = TextInput(multiline=True)
        field.insert("Return the last page past the end")
        lines = field.lines(25)
        self.assertEqual([line.rstrip() for line in lines], ["Return the last page past", "the end"])
        self.assertEqual("".join(lines), field.text)

    def test_a_row_that_fills_the_field_shows_whole(self):
        # the space a row breaks at lies past the edge: the row's last letter shows, not an ellipsis in its place
        field = TextInput(multiline=True)
        field.insert("Return the last page past the end")
        canvas = Canvas(25, 2)
        field.draw(canvas, 0, 0, 25, 2)
        self.assertEqual([text(canvas, y) for y in range(2)], ["Return the last page past", "the end"])

    def test_a_word_wider_than_the_row_breaks_inside_it(self):
        field = TextInput(multiline=True)
        field.insert("see " + "x" * 30 + " ok")
        self.assertEqual([line.rstrip() for line in field.lines(10)], ["see", "x" * 10, "x" * 10, "x" * 10, "ok"])

    def test_the_cursor_follows_the_rows(self):
        field = TextInput(multiline=True)
        field.insert("Return the last page past the end")
        field.cursor = field.text.index("the end")
        self.assertEqual(field.cursor_cell(25), (1, 0))
        field.cursor = len(field.text)
        self.assertEqual(field.cursor_cell(25), (1, 7))

    def test_a_focused_field_shows_the_rows_around_its_cursor(self):
        # a message taller than the field: the rows at the cursor show, wherever it moves (not always the last ones)
        field = TextInput(multiline=True)
        field.insert("\n".join(f"line {n}" for n in range(8)))
        field.cursor = 0
        canvas = Canvas(10, 3)
        field.draw(canvas, 0, 0, 10, 3, focused=True)
        self.assertEqual([text(canvas, y) for y in range(3)], ["line 0", "line 1", "line 2"])
        self.assertEqual(canvas.cursor, (0, 0))
        field.cursor = len(field.text)
        canvas = Canvas(10, 3)
        field.draw(canvas, 0, 0, 10, 3, focused=True)
        self.assertEqual([text(canvas, y) for y in range(3)], ["line 5", "line 6", "line 7"])
        self.assertEqual(canvas.cursor, (2, 6))

    def test_the_wheel_shows_other_rows_until_the_cursor_moves(self):
        # a message taller than the field: the wheel moves its rows and leaves the cursor; a key brings the cursor back
        field = TextInput(multiline=True)
        field.insert("\n".join(f"line {n}" for n in range(8)))
        field.cursor = 0
        field.draw(Canvas(10, 3), 0, 0, 10, 3, focused=True)
        field.scroll(3)
        canvas = Canvas(10, 3)
        field.draw(canvas, 0, 0, 10, 3, focused=True)
        self.assertEqual((text(canvas, 0), field.cursor), ("line 3", 0))
        field.scroll(20)                                          # never past the last rows
        field.draw(canvas, 0, 0, 10, 3, focused=True)
        self.assertEqual(text(canvas, 0), "line 5")
        field.handle(Key("right"))
        field.draw(canvas, 0, 0, 10, 3, focused=True)
        self.assertEqual(text(canvas, 0), "line 0")

    def test_a_message_put_in_shows_from_its_first_row(self):
        # a suggested message lands with the cursor at its end, but the field shows its subject first
        field = TextInput(multiline=True)
        field.insert("Subject line\n\n" + "\n".join(f"- change {n}" for n in range(6)))
        canvas = Canvas(14, 3)
        field.draw(canvas, 0, 0, 14, 3)
        self.assertEqual(text(canvas, 0), "Subject line")

    def test_shift_and_an_arrow_select_and_backspace_takes_the_selection_whole(self):
        field = TextInput()
        typed(field, "hello world")
        for _ in range(5):
            field.handle(Key("left", shift=True))
        self.assertEqual(field.selected(), "world")
        field.handle(Key("backspace"))
        self.assertEqual((field.text, field.cursor, field.selected()), ("hello ", 6, ""))

    def test_typing_or_pasting_puts_the_new_text_in_the_selections_place(self):
        field = TextInput(multiline=True)
        typed(field, "fix: a typo")
        field.handle(Key("home", shift=True))
        typed(field, "feat")
        self.assertEqual(field.text, "feat")
        field.handle(Key("left", shift=True))
        field.handle(Key("paste", "t: more"))
        self.assertEqual(field.text, "feat: more")

    def test_an_arrow_without_shift_leaves_the_selection_at_its_side(self):
        field = TextInput()
        typed(field, "abcdef")
        field.handle(Key("left", shift=True))
        field.handle(Key("left", shift=True))
        field.handle(Key("left"))
        self.assertEqual((field.cursor, field.selected()), (4, ""))
        field.handle(Key("right", shift=True))
        field.handle(Key("right"))
        self.assertEqual((field.cursor, field.selected()), (5, ""))

    def test_option_backspace_deletes_the_word_before_the_cursor(self):
        field = TextInput()
        typed(field, "feat: add the thing")
        field.handle(Key("backspace", alt=True))
        self.assertEqual(field.text, "feat: add the ")
        field.handle(Key("backspace", alt=True))
        self.assertEqual(field.text, "feat: add ")

    def test_a_click_puts_the_cursor_there_and_a_drag_selects(self):
        field = TextInput(multiline=True)
        field.insert("one two three\nfour")
        field.draw(Canvas(30, 3), 1, 2, 20, 2)                    # at row 1, column 2, 20 cells wide
        field.press(2 + 4, 1, now=10.0)                           # before "two"
        self.assertEqual((field.cursor, field.selected()), (4, ""))
        field.drag(2 + 2, 2)                                      # into "four", on the next row
        self.assertEqual(field.selected(), "two three\nfo")
        field.handle(Key("delete"))
        self.assertEqual(field.text, "one ur")

    def test_a_double_click_selects_a_word_and_a_triple_click_the_whole_text(self):
        field = TextInput(multiline=True)
        field.insert("feat: add the thing\n\n- more")
        field.draw(Canvas(30, 3), 0, 0, 30, 3)
        field.press(11, 0, now=10.0)
        field.press(11, 0, now=10.2)
        self.assertEqual(field.selected(), "the")
        field.press(11, 0, now=10.4)
        self.assertEqual(field.selected(), field.text)
        field.press(11, 0, now=12.0)                              # a while later: one click again
        self.assertEqual(field.selected(), "")

    def test_f8_the_key_cmd_a_sends_selects_the_whole_text(self):
        field = TextInput(multiline=True)
        typed(field, "feat: a\n\n- b")
        field.handle(Key("f8"))
        self.assertEqual(field.selected(), "feat: a\n\n- b")
        field.handle(Key("backspace"))
        self.assertEqual(field.text, "")

    def test_the_selection_shows_lit(self):
        field = TextInput()
        typed(field, "abcdef")
        field.handle(Key("left", shift=True))
        field.handle(Key("left", shift=True))
        canvas = Canvas(10, 1)
        field.draw(canvas, 0, 0, 10, 1, focused=True)
        self.assertEqual([style.bg for _, style in canvas.rows[0][3:7]], ["input", "selection", "selection", "input"])

    def test_long_lines_wrap_and_nothing_is_lost(self):
        field = TextInput(multiline=True)
        field.handle(Key("paste", "x" * 70))
        lines = field.lines(30)
        self.assertEqual([len(line) for line in lines], [30, 30, 10])
        self.assertEqual("".join(lines), field.text)


class Menus(unittest.TestCase):
    def test_a_choice_and_cancel(self):
        menu = Menu(["Commit", "Commit & Push", "Commit & Sync"])
        menu.handle(Key("down"))
        menu.handle(Key("down"))
        self.assertEqual(menu.handle(Key("enter")), "Commit & Sync")
        self.assertEqual(Menu(["a"]).handle(Key("esc")), "cancel")

    def test_it_is_drawn_as_herdrs_own_menus(self):
        menu = Menu(["Open", "Copy conversation"])
        self.assertEqual((menu.width(), Menu(["Open"]).width(), menu.height()), (len("Copy conversation") + 4, 14, 4))
        canvas = Canvas(40, 6)
        menu.draw(canvas, 0, 0, menu.width())
        rows = ["".join(ch for ch, _ in row)[:menu.width()] for row in canvas.rows[:4]]
        self.assertEqual(rows, ["┌" + "─" * 19 + "┐", "│Open" + " " * 15 + "│", "│Copy conversation  │",
                                "└" + "─" * 19 + "┘"])
        self.assertEqual((canvas.rows[0][0][1].fg, canvas.rows[0][0][1].bg), ("accent", "panel"))
        lit, plain = canvas.rows[1][1][1], canvas.rows[2][1][1]
        self.assertEqual(((lit.fg, lit.bg, lit.bold), (plain.fg, plain.bg)),
                         (("button_text", "button", True), ("text", "panel")))      # the chosen row in the accent
        self.assertEqual(menu.at(30, 35, 40, 0, 20), (16, 19, 21))                  # moved in to stay on screen


class Confirmations(unittest.TestCase):
    def test_enter_alone_is_the_safe_answer(self):
        self.assertFalse(Confirm("Discard changes in a.txt?", "Discard").handle(Key("enter")))

    def test_the_other_button_then_enter(self):
        confirm = Confirm("Discard changes in a.txt?", "Discard")
        confirm.handle(Key("tab"))
        self.assertTrue(confirm.handle(Key("enter")))

    def test_y_esc_and_other_keys(self):
        self.assertTrue(Confirm("q", "Discard").handle(Key("char", "y")))
        self.assertFalse(Confirm("q", "Discard").handle(Key("esc")))
        self.assertIsNone(Confirm("q", "Discard").handle(Key("char", "x")))

    def test_its_buttons_answer_clicks(self):
        confirm = Confirm("Discard changes in a.txt?", "Discard")
        canvas = Canvas(30, 6)
        confirm.draw(canvas, 0, 0, 30)
        targets = {target for _, _, _, target in canvas.regions}
        self.assertEqual(targets, {"confirm:yes", "confirm:no"})


if __name__ == "__main__":
    unittest.main()
