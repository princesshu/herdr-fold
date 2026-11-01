"""The sidebar's terminal on macOS and Linux: raw mode, the alternate screen, mouse, paste and focus reporting, switched
on while it runs and back off afterwards. Keys arrive as events through the shared decoder (vt.py); another thread
wakes the loop with wake(), and a window size change arrives as a Resize event."""
import os
import select
import shutil
import signal
import sys
import termios
import tty

from vt import PASTE_START, Decoder, Resize

# alternate screen, hidden cursor, mouse clicks + any movement + SGR coordinates, bracketed paste, focus reports
ON = "\x1b[?1049h\x1b[?25l\x1b[?1000h\x1b[?1003h\x1b[?1006h\x1b[?2004h\x1b[?1004h"
OFF = "\x1b[?1004l\x1b[?2004l\x1b[?1006l\x1b[?1003l\x1b[?1000l\x1b[0 q\x1b[?25h\x1b[?1049l"
ESC_WAIT = 0.05               # how long an Esc waits for the rest of its sequence


class UnixTerminal:
    def __init__(self, stdin_fd=0, stdout=None):
        self.fd = stdin_fd
        self.out = stdout or sys.stdout
        self.decoder = Decoder()
        self.saved = None
        self.resized = False
        self.old_winch = None
        self.wake_r = self.wake_w = None

    def __enter__(self):
        self.wake_r, self.wake_w = os.pipe()
        self.saved = termios.tcgetattr(self.fd)
        tty.setraw(self.fd, termios.TCSANOW)
        self.old_winch = signal.signal(signal.SIGWINCH, self._winch)
        self.write(ON)
        self.flush()
        return self

    def __exit__(self, *exc):
        self.write(OFF)
        self.flush()
        termios.tcsetattr(self.fd, termios.TCSANOW, self.saved)
        signal.signal(signal.SIGWINCH, self.old_winch)
        os.close(self.wake_r)
        os.close(self.wake_w)

    def _winch(self, signum, frame):
        self.resized = True
        self.wake()

    def wake(self):
        """Return a waiting read() at once (safe from any thread)."""
        try:
            os.write(self.wake_w, b"x")
        except OSError:
            pass

    def size(self):
        """Columns and lines; 80×24 for a window that reports none (Python 3.9 passes a 0×0 size on)."""
        columns, lines = shutil.get_terminal_size((80, 24))
        return columns or 80, lines or 24

    def read(self, timeout):
        """The events that arrive within TIMEOUT seconds (fewer, or none, if woken)."""
        events = []
        ready = select.select([self.fd, self.wake_r], [], [], timeout)[0]
        if self.wake_r in ready:
            os.read(self.wake_r, 4096)
        if self.fd in ready:
            events += self.decoder.feed(os.read(self.fd, 65536))
            if self.decoder.pending and not self.decoder.pending.startswith(PASTE_START):
                if select.select([self.fd], [], [], ESC_WAIT)[0]:
                    events += self.decoder.feed(os.read(self.fd, 65536))
                if self.decoder.pending:
                    events += self.decoder.flush()
        if self.resized:
            self.resized = False
            events.append(Resize(*self.size()))
        return events

    def write(self, text):
        self.out.write(text)

    def flush(self):
        self.out.flush()
