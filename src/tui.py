"""Shared helpers for the herdr popup scripts (commit_push.py, close_tab.py, new_workspace.py, add_machine.py,
themes/picker.py): reading keys, finding programs, showing names from elsewhere.
herdr launches the popup with a minimal PATH, so these helpers also look for programs in the usual places."""
import atexit
import glob
import os
import re
import select
import shutil
import sys
import termios
import tty

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from i18n import t  # noqa: E402


_saved_mode = None
_pending = b""            # a byte read after Esc that does not belong to it
_mouse = False            # clicks and the wheel reported to the window
MOUSE_REPORT = re.compile(r"\x1b\[<(\d+);(\d+);(\d+)([Mm])")
GRAY, INVERT, RESET = "\x1b[90m", "\x1b[7m", "\x1b[0m"
GAP = 2                   # cells between two buttons
MARGIN = 1                # cells kept clear at a window's left and right edge


def printable(text):
    """TEXT for the screen: a control character becomes ? — a folder name or a title from elsewhere (a downloaded
    repository's) may hold escape codes, which would write the clipboard or the window title."""
    return "".join(ch if ch.isprintable() else "?" for ch in text)


def cursor(shown):
    """The terminal's cursor shown or hidden, where the output is a terminal (a pipe gets no control codes)."""
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[?25h" if shown else "\x1b[?25l")
        sys.stdout.flush()


def mouse(on):
    """Clicks and the wheel reported as keys (getkey() reads each as one, clicked() tells what it is), where the output
    is a terminal; given back when the window ends."""
    global _mouse
    if sys.stdout.isatty() and on != _mouse:
        sys.stdout.write("\x1b[?1000h\x1b[?1006h" if on else "\x1b[?1006l\x1b[?1000l")
        sys.stdout.flush()
        _mouse = on
        if on:
            atexit.register(mouse, False)


def clicked(key):
    """A mouse report among the keys: (button, column, row, pressed), 1-based; None for any other key. Button 0 is the
    left one, 64 and 65 the wheel up and down."""
    found = MOUSE_REPORT.fullmatch(key)
    return (int(found[1]), int(found[2]), int(found[3]), found[4] == "M") if found else None


def buttons(labels, width, left=""):
    """A row with LEFT, faint, at its start and the button LABELS at its end, MARGIN cells from each edge, the last one
    the default (inverted: Enter presses it); and where each button is, for button_at(): (first column, last, label)."""
    cells = [f" {label} " for label in labels]
    column = start = max(MARGIN + len(left) + GAP + 1,
                         width - MARGIN - sum(map(len, cells)) - GAP * (len(cells) - 1) + 1)
    spans = []
    for label, cell in zip(labels, cells):
        spans.append((column, column + len(cell) - 1, label))
        column += len(cell) + GAP
    shown = [(INVERT + cell + RESET) if n == len(cells) - 1 else cell for n, cell in enumerate(cells)]
    return (" " * MARGIN + f"{GRAY}{left}{RESET}" + " " * (start - 1 - MARGIN - len(left)) + (" " * GAP).join(shown)
            + " " * MARGIN), spans


def button_at(column, spans):
    return next((label for first, last, label in spans if first <= column <= last), None)


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
