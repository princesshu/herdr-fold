"""Add a remote machine (Ctrl+B, Shift+M; New space's Add machine…): herdr has only `herdr machine add`, no button.
The sidebar plugin's popup, framed as Settings: the package's ./machines.sh new (setup-folder names its folder) in a
terminal of its own under the close button, which, Esc or Ctrl+C end it at any question; --open opens the popup."""
import contextlib
import fcntl
import os
import pty
import select
import signal
import struct
import sys
import termios
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from herdrlib import herdr  # noqa: E402
from i18n import t  # noqa: E402
from tui import clicked, close_button, getkey, key_mode, mouse, search_path, wait_and_exit  # noqa: E402

RECORD = os.path.join(HERE, "setup-folder")
PANE = ("plugin", "pane", "open", "--plugin", "herdr-fold.sidebar", "--entrypoint", "add-machine", "--focus")
TOP = 2                                 # rows over its terminal: the close button's, its tip's
WAIT = 5                                # seconds it waits for another popup to go
CANCELLED = 130


def open_popup(after=None):
    """The popup opened over the space in front, as Settings opens; once process AFTER (a popup of its own: herdr keeps
    one at a time) has ended, asked again while herdr says it is busy, for a few seconds."""
    end = time.monotonic() + WAIT
    while after and time.monotonic() < end:
        try:
            os.kill(after, 0)
        except OSError:
            break
        time.sleep(0.05)
    while True:
        try:
            return herdr(*PANE)
        except RuntimeError as err:
            if "ui_busy" not in str(err) or time.monotonic() > end:
                return None
            time.sleep(0.1)


def run(argv, env):
    """ARGV in a terminal of its own under the close button's rows: what it writes shown, what is typed passed on; the
    button's click, Esc or Ctrl+C end it and all it started. Its exit status (CANCELLED when ended so)."""
    pid, fd = pty.fork()
    if pid == 0:
        os.execve(argv[0], argv, env)
    out, close = sys.stdout, close_button()

    def fit(*_):                                    # its rows, the scroll region under the button's, the button drawn
        rows, cols = os.get_terminal_size()
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", max(1, rows - TOP), cols, 0, 0))
        out.write(f"\x1b[2J\x1b[{TOP + 1};{rows}r\x1b[{TOP + 1};1H" + close.overlay(cols))
        out.flush()

    fit()
    signal.signal(signal.SIGWINCH, fit)
    key_mode()                                      # keys one by one from the start: Esc alone reaches it at once
    mouse(True, moves=True)
    cancelled = False
    try:
        while True:
            ready = select.select([fd, sys.stdin.fileno()], [], [], close.wait())[0]
            if fd in ready:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    chunk = b""
                if not chunk:
                    break
                os.write(out.fileno(), chunk)
            key = getkey(0) if sys.stdin.fileno() in ready else None
            taken = close.take(key, os.get_terminal_size().columns) if key or not ready else None
            if taken == "close" or key == "\x1b":
                cancelled = True
                break
            if key is not None and not taken and not clicked(key):
                os.write(fd, key.encode())
            if taken or fd in ready:                # the button kept over what it writes
                gone = "\x1b7\x1b[2;1H\x1b[2K\x1b8" if taken == "redraw" else ""      # its tip's row blank again
                out.write(gone + close.overlay(os.get_terminal_size().columns))
                out.flush()
    except KeyboardInterrupt:
        cancelled = True
    if cancelled:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pid, signal.SIGTERM)          # machines.sh and the ssh it runs
    os.close(fd)
    status = os.waitpid(pid, 0)[1]
    return CANCELLED if cancelled else os.waitstatus_to_exitcode(status)


def main():
    if sys.argv[1:2] == ["--open"]:                 # --open [PID]: after that process's popup has gone
        return open_popup(int(sys.argv[2]) if sys.argv[2:] else None)
    try:
        with open(RECORD, encoding="utf-8") as f:
            folder = f.read().strip()
    except OSError:
        folder = ""
    script = os.path.join(folder, "machines.sh") if folder else ""
    if script and os.path.isfile(script):
        # herdr starts the window with a bare-bones PATH: machines.sh calls herdr, ssh and the Homebrew tools by name
        herdr_bin = os.environ.get("HERDR_BIN_PATH")
        path = os.pathsep.join(([os.path.dirname(herdr_bin)] if herdr_bin else []) + [search_path()])
        sys.exit(run(["/bin/bash", script, "new"], dict(os.environ, PATH=path)))
    print(t("add_machine.no_package", folder or t("add_machine.no_record")))
    wait_and_exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(CANCELLED)
