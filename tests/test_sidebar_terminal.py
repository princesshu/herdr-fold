"""Tests for the sidebar's terminal on macOS and Linux (src/plugins/sidebar/keys_unix.py) in a real pty: modes switched
on and back off, keys as events, waking the loop from another thread, and 80×24 when no size is reported."""
import os
import pty
import select
import sys
import time
import unittest

from support import SRC

PROGRAM = r"""
import sys, threading, time
sys.path.insert(0, %r)
from keys_unix import UnixTerminal
with UnixTerminal() as term:
    print("SIZE", term.size(), flush=True)
    threading.Timer(0.3, term.wake).start()
    started = time.time()
    term.read(5)
    print("WOKE %%.1f" %% (time.time() - started), flush=True)
    seen = []
    while not any(getattr(e, "char", "") == "q" for e in seen):
        seen += term.read(1)
    print("EVENTS", seen, flush=True)
"""


def run(keys):
    """The program in a pty; KEYS are typed once it is waiting. Returns everything it wrote."""
    pid, fd = pty.fork()
    if pid == 0:
        os.execv(sys.executable, [sys.executable, "-c", PROGRAM % os.path.join(SRC, "plugins", "sidebar")])
    out, deadline = b"", time.time() + 10
    time.sleep(0.6)
    os.write(fd, keys)
    while time.time() < deadline:
        if select.select([fd], [], [], 0.2)[0]:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
    os.waitpid(pid, 0)
    os.close(fd)
    return out.decode("utf-8", "replace")


class Terminal(unittest.TestCase):
    def test_modes_are_switched_on_and_back_off(self):
        out = run(b"q")
        for on in ("\x1b[?1049h", "\x1b[?1006h", "\x1b[?2004h", "\x1b[?1004h"):
            self.assertIn(on, out)
            self.assertIn(on[:-1] + "l", out[out.index(on):])
        self.assertIn("\x1b[0 q\x1b[?25h", out)                          # the terminal's own cursor back as it was

    def test_keys_arrive_as_events(self):
        self.assertIn("Key(name='up'", run(b"\x1b[Aq"))

    def test_another_thread_wakes_the_loop(self):
        out = run(b"q")
        self.assertLess(float(out.split("WOKE ")[1].split()[0]), 1.0)

    def test_a_window_without_a_size_is_80_by_24(self):
        self.assertIn("SIZE (80, 24)", run(b"q"))             # pty.fork makes a 0×0 one


if __name__ == "__main__":
    unittest.main()
