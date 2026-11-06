"""Tests for tests/support.py's end_child: a program a test runs in a pty ends with the test, never holding up the run
(a step still writing once its output goes unread blocks on the full terminal, and only a closed one lets it go)."""
import os
import pty
import select
import time
import unittest

from support import end_child


def output_until_end(fd):
    out = b""
    while select.select([fd], [], [], 5)[0]:
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
    return out


class EndChild(unittest.TestCase):
    def test_a_child_still_writing_is_ended_and_the_run_goes_on(self):
        pid, fd = pty.fork()
        if pid == 0:
            os.execv("/bin/sh", ["sh", "-c", "while :; do printf xxxxxxxxxxxxxxxx; done"])
        time.sleep(0.5)                                   # its output unread: it fills the terminal and waits
        start = time.monotonic()
        self.assertIsNone(end_child(pid, fd, grace=0.5))
        self.assertLess(time.monotonic() - start, 5)

    def test_an_ended_child_gives_its_exit_code(self):
        pid, fd = pty.fork()
        if pid == 0:
            os.execv("/bin/sh", ["sh", "-c", "echo done; exit 3"])
        self.assertIn(b"done", output_until_end(fd))
        self.assertEqual(end_child(pid, fd), 3)


if __name__ == "__main__":
    unittest.main()
