"""Shared helpers for the herdr popup scripts (commit_push.py, close_tab.py, new_workspace.py, add_machine.py,
themes/picker.py, open_file.py): reading keys, the close button, finding programs, showing names from elsewhere.
herdr launches the popup with a minimal PATH, so these helpers also look for programs in the usual places."""
import atexit
import glob
import os
import re
import select
import shutil
import sys
import termios
import time
import tty

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from i18n import t  # noqa: E402


_saved_mode = None
_pending = b""            # a byte read after Esc that does not belong to it
_mouse = False            # clicks and the wheel reported to the window
MOUSE_REPORT = re.compile(r"\x1b\[<(\d+);(\d+);(\d+)([Mm])")
GRAY, INVERT, RESET = "\x1b[90m", "\x1b[7m", "\x1b[0m"
GAP = 2                   # cells between two buttons
MARGIN = 1                # cells kept clear at a window's left edge
RIGHT = 0                 # and at its right one: herdr's popup keeps a blank column of its own there, as About has it
CLOSE_TIP, TIP_DELAY = "Close (Esc)", 0.5       # the close button's tip, once the mouse rests on it that long
MOVE = 32                 # a mouse report's flag for a move (the moves asked for: mouse(True, moves=True))
CLOSED = "close"          # read_key()'s answer for a click on the close button: the popup's cancel, whatever typed
CLOSE_ROOM = 4            # what the close button takes of its row: its three cells and one of air before them


def printable(text):
    """TEXT for the screen: a control character becomes ? — a folder name or a title from elsewhere (a downloaded
    repository's) may hold escape codes, which would write the clipboard or the window title."""
    return "".join(ch if ch.isprintable() else "?" for ch in text)


def cursor(shown):
    """The terminal's cursor shown or hidden, where the output is a terminal (a pipe gets no control codes)."""
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[?25h" if shown else "\x1b[?25l")
        sys.stdout.flush()


def mouse(on, moves=False):
    """Clicks and the wheel reported as keys (getkey() reads each as one, clicked() tells what it is), and with MOVES
    the mouse's moves (a close button lit under it), where the output is a terminal; given back when the window ends."""
    global _mouse
    if sys.stdout.isatty() and bool(on) != bool(_mouse):
        codes = ("1000", "1003", "1006") if (moves if on else _mouse == "moves") else ("1000", "1006")
        sys.stdout.write("".join(f"\x1b[?{code}h" for code in codes) if on else
                         "".join(f"\x1b[?{code}l" for code in reversed(codes)))
        sys.stdout.flush()
        _mouse = ("moves" if moves else True) if on else False
        if on:
            atexit.register(mouse, False)


def clicked(key):
    """A mouse report among the keys: (button, column, row, pressed), 1-based; None for any other key. Button 0 is the
    left one, 64 and 65 the wheel up and down."""
    found = MOUSE_REPORT.fullmatch(key)
    return (int(found[1]), int(found[2]), int(found[3]), found[4] == "M") if found else None


def buttons(labels, width, left=""):
    """A row with LEFT, faint, at its start and the button LABELS at its end, MARGIN and RIGHT in, the last one
    the default (inverted: Enter presses it); and where each button is, for button_at(): (first column, last, label)."""
    cells = [f" {label} " for label in labels]
    column = start = max(MARGIN + len(left) + GAP + 1,
                         width - RIGHT - sum(map(len, cells)) - GAP * (len(cells) - 1) + 1)
    spans = []
    for label, cell in zip(labels, cells):
        spans.append((column, column + len(cell) - 1, label))
        column += len(cell) + GAP
    shown = [(INVERT + cell + RESET) if n == len(cells) - 1 else cell for n, cell in enumerate(cells)]
    return (" " * MARGIN + f"{GRAY}{left}{RESET}" + " " * (start - 1 - MARGIN - len(left)) + (" " * GAP).join(shown)
            + " " * RIGHT), spans


def button_at(column, spans):
    return next((label for first, last, label in spans if first <= column <= last), None)


class CloseButton:
    """The popup's close button on its first row, RIGHT in from its right edge: air, the close glyph, air, as the
    sidebar's icons alone (about.html's color), the hover color under the mouse (the tinted line alone: no row above
    it) and its tip after TIP_DELAY. COLORS: SGR codes for the glyph, the glyph lit, the hover and the tip."""

    def __init__(self, glyph, colors, clock=time.monotonic):
        self.glyph, self.colors, self.clock = glyph, colors, clock
        self.over, self.tip = None, False          # since when the mouse rests on it; its tip drawn

    def span(self, width):
        """Its first and last column (from 1) in a popup WIDTH cells wide."""
        return width - RIGHT - 2, width - RIGHT

    def wait(self):
        """Seconds until its tip is due (getkey()'s timeout), None while none is coming."""
        return None if self.over is None or self.tip else max(0.0, self.over + TIP_DELAY - self.clock())

    def take(self, key, width):
        """KEY (getkey()'s, None when its wait ran out) as the button takes it: "close" for a click on it; "kept" for
        a mouse move or its tip coming (drawn again with overlay(), nothing else); "redraw" when its tip goes."""
        if key is None:
            self.tip = self.over is not None
            return "kept" if self.tip else None
        found = clicked(key)
        if not found:
            return None
        button, column, row, pressed = found
        first, last = self.span(width)
        on = row == 1 and first <= column <= last
        if button & MOVE:
            covered = self.tip and not on
            if on != (self.over is not None):
                self.over, self.tip = (self.clock() if on else None), False
            return "redraw" if covered else "kept"
        return "close" if on and button == 0 and pressed else None

    def overlay(self, width):
        """Its cells as drawn now, the cursor kept where it was: the block, lit while the mouse is on it, its tip under
        it at its right edge once due, a cell of air round its words as the sidebar's tips."""
        first, last = self.span(width)
        look = f"{self.colors['lit']};{self.colors['hover']}" if self.over is not None else self.colors["glyph"]
        out = f"\x1b7\x1b[1;{first}H\x1b[{look}m {self.glyph} \x1b[0m"
        if self.tip:
            words = f" {CLOSE_TIP} "
            out += f"\x1b[2;{max(1, last - len(words) + 1)}H\x1b[{self.colors['tip']}m{words}\x1b[0m"
        return out + "\x1b8"


def read_key(close, width, redraw, timeout=None, read=None):
    """The next key the popup acts on (None: its own TIMEOUT ran out): CLOSE's own handled on the way (a move, its tip;
    REDRAW() draws the popup again where the tip was), a click on it CLOSED."""
    read, end = read or getkey, None if timeout is None else time.monotonic() + timeout
    while True:
        waits = [w for w in (close.wait(), None if end is None else max(0.0, end - time.monotonic())) if w is not None]
        key = read(min(waits) if waits else None)
        if key is None and end is not None and time.monotonic() >= end:
            return None
        taken = close.take(key, width)
        if taken == "close":
            return CLOSED
        if taken == "redraw":
            redraw()
        elif taken == "kept":
            sys.stdout.write(close.overlay(width))
            sys.stdout.flush()
        elif key is not None:
            return key


def close_button():
    """The close button as the sidebar draws its own: its glyph (Codicons' close, or × with its icons off) and its
    theme's colors (herdr-fold's theme setter writes them; else the terminal's own)."""
    import herdrlib                                       # the sidebar's modules on the path
    from icons import glyphs
    from screen import icons_on
    from theme import Theme
    theme = Theme.load(herdrlib.PLUGIN_STATE)
    text = theme.color("text", "fg")
    colors = {"glyph": theme.color("subtext", "fg"), "lit": text, "hover": theme.color("hover", "bg"),
              "tip": f"{text};{theme.color('selection', 'bg')}"}
    return CloseButton(glyphs(icons_on(herdrlib.PLUGIN_STATE))["close"], colors)


def restore_terminal():
    global _saved_mode
    if _saved_mode is not None:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, _saved_mode)
        _saved_mode = None
        cursor(True)


def _key_mode():
    """Cbreak mode until the script ends (keys one by one, no echo; output and Ctrl+C as usual), not switched back after
    each key, so keystrokes in between are not lost. Hides the cursor: a window draws its own caret, or none."""
    global _saved_mode
    if _saved_mode is None:
        fd = sys.stdin.fileno()
        _saved_mode = termios.tcgetattr(fd)
        tty.setcbreak(fd, termios.TCSANOW)
        cursor(False)
        atexit.register(restore_terminal)


def getkey(timeout=None):
    """One key; arrows and the like as escape sequences (e.g. "\\x1b[D"), a plain Esc on its own, Enter as "\\n";
    None when none comes in TIMEOUT seconds. Reads straight from the file descriptor: sys.stdin's buffering would hide
    the rest of a sequence from select()."""
    global _pending
    _key_mode()
    fd = sys.stdin.fileno()
    if timeout is not None and not _pending and not select.select([fd], [], [], timeout)[0]:
        return None
    data, _pending = (_pending, b"") if _pending else (os.read(fd, 1), b"")
    if data == b"\x1b" and select.select([fd], [], [], 0.05)[0]:
        data += os.read(fd, 1)                 # ESC [ … (CSI) or ESC O x (SS3); only the sequence's own bytes
        if data[1:] not in (b"[", b"O"):       # plain Esc followed by another key: that one belongs to the next call
            _pending, data = data[1:], b"\x1b"
        elif data == b"\x1b[":
            while not (0x40 <= data[-1] <= 0x7E and len(data) > 2):
                data += os.read(fd, 1)
        elif data == b"\x1bO":
            data += os.read(fd, 1)
    elif data and data[0] >= 0xC0:              # multi-byte UTF-8 character (e.g. accented)
        need = 1 if data[0] < 0xE0 else 2 if data[0] < 0xF0 else 3
        while len(data) < need + 1:
            data += os.read(fd, need + 1 - len(data))
    key = data.decode("utf-8", "replace")
    # "application mode" arrows (ESC O A…) are the same as the usual ones (ESC [ A…)
    return "\x1b[" + key[2:] if key.startswith("\x1bO") and len(key) == 3 else key


def read_line(prompt):
    """Read a whole line (in the usual, echoing mode)."""
    restore_terminal()
    return input(prompt)


def wait_and_exit(code=0):
    mouse(False)                                      # a mouse move is no key here
    print("\n" + t("lib.press_any_key"))
    getkey()
    sys.exit(code)


def search_path():
    home = os.path.expanduser("~")
    extra = [os.path.join(home, ".local", "bin"), "/opt/homebrew/bin", "/usr/local/bin",
             os.path.join(home, ".bun", "bin"), os.path.join(home, ".npm-global", "bin")]
    extra += sorted(glob.glob(os.path.join(home, ".nvm", "versions", "node", "*", "bin")), reverse=True)
    return os.pathsep.join([os.environ.get("PATH", ""), *extra])


def find(name):
    return shutil.which(name, path=search_path())
