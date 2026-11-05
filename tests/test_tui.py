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

from support import SRC

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
            os.waitpid(pid, 0)
            os.close(fd)
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
            os.waitpid(pid, 0)
            os.close(fd)
        self.assertIn(b"'\\x1b[<0;12;5M'", shown)
        self.assertLess(shown.index(MOUSE_ON), shown.rindex(MOUSE_OFF))

    def test_a_mouse_report_is_its_button_place_and_whether_pressed(self):
        import tui
        self.assertEqual(tui.clicked("\x1b[<0;12;5M"), (0, 12, 5, True))
        self.assertEqual(tui.clicked("\x1b[<65;3;9m"), (65, 3, 9, False))
        self.assertIsNone(tui.clicked("\x1b[B"))
        self.assertIsNone(tui.clicked("a"))

    def test_the_buttons_sit_at_the_rows_right_end_a_cell_from_each_edge_the_default_one_inverted(self):
        import tui
        row, spans = tui.buttons(["Cancel", "Open"], 40, "Tab agent")
        plain = re.sub(r"\x1b\[[0-9;]*m", "", row)
        self.assertEqual(len(plain), 40)
        self.assertTrue(plain.startswith(" Tab agent") and plain.endswith(" Cancel    Open  "), plain)
        self.assertIn(tui.INVERT + " Open " + tui.RESET, row)                 # Enter's, the last one
        self.assertNotIn(tui.INVERT + " Cancel ", row)
        self.assertEqual(spans, [(24, 31, "Cancel"), (34, 39, "Open")])
        self.assertEqual([tui.button_at(column, spans) for column in (23, 24, 31, 32, 34, 39, 40)],
                         [None, "Cancel", "Cancel", None, "Open", "Open", None])

    def test_nothing_written_where_the_output_is_no_terminal(self):
        typed, keys = os.openpty()                            # the keys come from a terminal, the output goes to a pipe
        self.addCleanup(os.close, typed)
        self.addCleanup(os.close, keys)
        os.write(typed, b"x")
        done = subprocess.run([sys.executable, "-B", "-c", WINDOW], stdin=keys, capture_output=True, timeout=10)
        self.assertEqual((done.returncode, done.stdout), (0, b""))
