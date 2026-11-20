"""Tests for tui.py, the small windows' key handling: the terminal's cursor is hidden while a window reads keys (it
draws its own caret, so none is left after its last line) and comes back when the window ends."""
import os
import pty
import re
import select
import subprocess
import sys
import time
import unittest

from support import SRC, end_child

# a window that reads one key, then ends; one that takes the mouse too, and shows what it read
WINDOW = f"import sys; sys.path.insert(0, {SRC!r}); import tui; tui.getkey()"
MOUSE_WINDOW = f"import sys; sys.path.insert(0, {SRC!r}); import tui; tui.mouse(True); print(repr(tui.getkey()))"
HIDE, SHOW = b"\x1b[?25l", b"\x1b[?25h"
MOUSE_ON, MOUSE_OFF = b"\x1b[?1000h\x1b[?1006h", b"\x1b[?1006l\x1b[?1000l"


def read_until(fd, done):
    shown, end = b"", time.monotonic() + 5
    while time.monotonic() < end and not done(shown):
        if select.select([fd], [], [], 0.1)[0]:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            shown += chunk
    return shown


class Cursor(unittest.TestCase):
    def test_hidden_while_the_keys_are_read_and_back_at_the_end(self):
        pid, fd = pty.fork()
        if pid == 0:
            os.execv(sys.executable, [sys.executable, "-B", "-c", WINDOW])
        try:
            shown = read_until(fd, lambda out: HIDE in out)
            os.write(fd, b"x")
            shown += read_until(fd, lambda out: SHOW in out)
        finally:
            end_child(pid, fd)
        self.assertTrue(HIDE in shown and shown.index(HIDE) < shown.rindex(SHOW), shown)

    def test_a_click_is_one_key_and_the_mouse_is_given_back_at_the_end(self):
        pid, fd = pty.fork()
        if pid == 0:
            os.execv(sys.executable, [sys.executable, "-B", "-c", MOUSE_WINDOW])
        try:
            shown = read_until(fd, lambda out: MOUSE_ON in out)
            os.write(fd, b"\x1b[<0;12;5M")
            shown += read_until(fd, lambda out: MOUSE_OFF in out)
        finally:
            end_child(pid, fd)
        self.assertIn(b"'\\x1b[<0;12;5M'", shown)
        self.assertLess(shown.index(MOUSE_ON), shown.rindex(MOUSE_OFF))

    def test_a_mouse_report_is_its_button_place_and_whether_pressed(self):
        import tui
        self.assertEqual(tui.clicked("\x1b[<0;12;5M"), (0, 12, 5, True))
        self.assertEqual(tui.clicked("\x1b[<65;3;9m"), (65, 3, 9, False))
        self.assertIsNone(tui.clicked("\x1b[B"))
        self.assertIsNone(tui.clicked("a"))

    def test_the_buttons_sit_at_the_rows_right_end_a_cell_from_each_side_the_default_one_inverted(self):
        # herdr's popup keeps a blank column inside its right edge: that one is the right side's cell
        import tui
        row, spans = tui.buttons(["Cancel", "Open"], 40, "Tab agent")
        plain = re.sub(r"\x1b\[[0-9;]*m", "", row)
        self.assertEqual(len(plain), 40)
        self.assertTrue(plain.startswith(" Tab agent") and plain.endswith(" Cancel    Open "), plain)
        self.assertIn(tui.INVERT + " Open " + tui.RESET, row)                 # Enter's, the last one
        self.assertNotIn(tui.INVERT + " Cancel ", row)
        self.assertEqual(spans, [(25, 32, "Cancel"), (35, 40, "Open")])
        self.assertEqual([tui.button_at(column, spans) for column in (24, 25, 32, 33, 35, 40, 41)],
                         [None, "Cancel", "Cancel", None, "Open", "Open", None])

    def test_nothing_written_where_the_output_is_no_terminal(self):
        typed, keys = os.openpty()                            # the keys come from a terminal, the output goes to a pipe
        self.addCleanup(os.close, typed)
        self.addCleanup(os.close, keys)
        os.write(typed, b"x")
        done = subprocess.run([sys.executable, "-B", "-c", WINDOW], stdin=keys, capture_output=True, timeout=10)
        self.assertEqual((done.returncode, done.stdout), (0, b""))


class CloseButtons(unittest.TestCase):
    """Every popup's close button at its top right, at its edge (herdr's blank column is the cell of air there): air,
    the close glyph, air, as the sidebar's icons alone, lit under the mouse, its tip after a moment; a click closes."""

    def setUp(self):
        sys.path.insert(0, SRC)
        import tui
        self.now = [100.0]
        self.button = tui.CloseButton("x", {"glyph": "90", "lit": "39", "hover": "100", "tip": "39;45"},
                                      clock=lambda: self.now[0])

    def test_it_sits_at_the_top_right_a_cell_from_the_edge(self):
        self.assertEqual(self.button.span(40), (38, 40))
        self.assertEqual(self.button.overlay(40), "\x1b7\x1b[1;38H\x1b[90m x \x1b[0m\x1b8")      # as about.html

    def test_the_mouse_lights_it_and_its_tip_comes_after_a_moment(self):
        self.assertEqual(self.button.take("\x1b[<35;38;1M", 40), "kept")              # a move onto it
        self.assertEqual(self.button.overlay(40), "\x1b7\x1b[1;38H\x1b[39;100m x \x1b[0m\x1b8")
        self.assertEqual(self.button.wait(), 0.5)
        self.now[0] += 0.5
        self.assertEqual(self.button.take(None, 40), "kept")                            # the wait ran out
        self.assertIn("\x1b[2;28H\x1b[39;45m Close (Esc) \x1b[0m", self.button.overlay(40))   # under it, at its edge
        self.assertIsNone(self.button.wait())
        self.assertEqual(self.button.take("\x1b[<35;10;5M", 40), "redraw")            # off it: what the tip hid
        self.assertEqual(self.button.take("\x1b[<35;38;1M", 40), "kept")
        self.assertEqual(self.button.take("\x1b[<35;11;5M", 40), "kept")              # off before its tip
        self.assertEqual(self.button.take("\x1b[<35;12;5M", 40), "kept")              # any other move: no redraw

    def test_a_click_on_it_closes_and_any_other_key_is_the_popups(self):
        self.assertEqual(self.button.take("\x1b[<0;39;1M", 40), "close")
        for key in ("\x1b[<0;37;1M", "\x1b[<0;38;2M", "\x1b", "\r", "a"):
            with self.subTest(key=key):
                self.assertIsNone(self.button.take(key, 40))

    def test_the_mouse_moves_are_asked_for_with_the_clicks(self):
        code = (f"import sys; sys.path.insert(0, {SRC!r}); import tui; tui.sys.stdout.isatty = lambda: True; "
                "tui.mouse(True, moves=True); tui.mouse(False)")
        out = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True).stdout
        self.assertEqual(out, "\x1b[?1000h\x1b[?1003h\x1b[?1006h\x1b[?1006l\x1b[?1003l\x1b[?1000l")

    def test_a_popup_reads_its_keys_through_it(self):
        # the button's own (a move, its tip) handled on the way, a click on it CLOSED: the popup's cancel
        sys.path.insert(0, SRC)
        import contextlib
        import io
        import tui
        keys, drawn = ["\x1b[<35;38;1M", None, "\x1b[<35;5;5M", "a", "\x1b[<0;38;1M"], []
        with contextlib.redirect_stdout(io.StringIO()) as out:
            first = tui.read_key(self.button, 40, lambda: drawn.append(1), read=lambda timeout: keys.pop(0))
            second = tui.read_key(self.button, 40, lambda: drawn.append(1), read=lambda timeout: keys.pop(0))
        self.assertEqual((first, second, drawn), ("a", tui.CLOSED, [1]))    # drawn again once: when its tip went
        self.assertIn("Close (Esc)", out.getvalue())

    def test_a_popups_last_wait_gives_the_mouse_back_first(self):
        # "press any key" after the work: a mouse move is no key there
        code = (f"import sys; sys.path.insert(0, {SRC!r}); import tui; tui.sys.stdout.isatty = lambda: True; "
                "tui.getkey = lambda *a: 'x'; tui.mouse(True, moves=True)\ntry:\n    tui.wait_and_exit()\n"
                "except SystemExit:\n    pass")
        out = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True).stdout
        self.assertLess(out.index("\x1b[?1003l"), out.index("\n"))
