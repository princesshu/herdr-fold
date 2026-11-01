"""Tests for tui.py, the small windows' key handling: the terminal's cursor is hidden while a window reads keys (it
draws its own caret, so none is left after its last line) and comes back when the window ends."""
import os
import pty
import select
import subprocess
import sys
import time
import unittest

from support import SRC

# a window that reads one key, then ends
WINDOW = f"import sys; sys.path.insert(0, {SRC!r}); import tui; tui.getkey()"
HIDE, SHOW = b"\x1b[?25l", b"\x1b[?25h"


def read_until(fd, done, timeout=5.0):
    shown, end = b"", time.monotonic() + timeout
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

    def test_nothing_written_where_the_output_is_no_terminal(self):
        typed, keys = os.openpty()                            # the keys come from a terminal, the output goes to a pipe
        self.addCleanup(os.close, typed)
        self.addCleanup(os.close, keys)
        os.write(typed, b"x")
        done = subprocess.run([sys.executable, "-B", "-c", WINDOW], stdin=keys, capture_output=True, timeout=10)
        self.assertEqual((done.returncode, done.stdout), (0, b""))
