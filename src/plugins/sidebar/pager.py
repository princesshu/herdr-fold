"""The sidebar's pager: a file or a pipeline's output in color, with less's keys; q or Esc closes the preview tab. It
runs the pipeline itself so the keyboard stays the terminal's, and lets only colors through (no cursor moves, titles or
clipboard). Usage: HERDR_FOLD_SPEC_FILE=PATH pager.py (preview.py writes the spec there, and each new one)."""
import json
import os
import re
import signal
import stat
import subprocess
import sys
import threading

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from preview import Herdr  # noqa: E402
from screen import char_width  # noqa: E402
from vt import Key, Mouse  # noqa: E402

# any escape sequence: CSI, OSC (ended by BEL or ST, or by the line), DCS SOS PM APC (ended by ST), or ESC and one more
ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)?|[PX^_][^\x1b]*(?:\x1b\\)?|.?)", re.S)
SGR = re.compile(r"\x1b\[[0-9;:]*m")
CONTROL = {chr(c) for c in [*range(32), *range(0x7f, 0xa0)]}
LIMIT = 8_000_000             # bytes read at most: a huge file or an endless command does not stall the pager
CONTEXT = 3                   # lines shown above the line the pager opens at, or a search hit
WATCH = 0.3                   # seconds between looks at the spec's file: a new spec there is shown
WAIT = 30                     # seconds a pipeline may run (gh asking GitHub, a program that never ends): then stopped


def stop(proc):
    """PROC and whatever it started (its own session): a child of it may hold the output open."""
    try:
        if os.name == "nt":
            proc.kill()
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass


def read(spec):
    """At most LIMIT + 1 bytes: the pipeline's output (its errors too), what it gave within WAIT, or the file's, a plain
    file only (a pipe or a device may never end). A string is a failure. The pipeline's programs have no terminal to
    open (a repository's config could name /dev/tty for git to read the keys from)."""
    if not spec.get("pipeline"):
        try:
            fd = os.open(spec["file"], os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
        except OSError as err:
            return str(err)
        with os.fdopen(fd, "rb") as f:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                return "not a plain file: a pipe or a device is not shown"
            return f.read(LIMIT + 1)
    procs, env = [], dict(os.environ, **(spec.get("env") or {}))
    timer = threading.Timer(WAIT, lambda: [stop(proc) for proc in procs])
    try:
        for argv in spec["pipeline"]:
            stdin = procs[-1].stdout if procs else subprocess.DEVNULL
            procs.append(subprocess.Popen(argv, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                          env=env, start_new_session=True))
            if stdin is not subprocess.DEVNULL:
                stdin.close()                       # the next command owns it now
        timer.start()
        return procs[-1].stdout.read(LIMIT + 1)
    except OSError as err:
        return f"cannot run {argv[0]}: {err}"
    finally:
        timer.cancel()
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            proc.stdout.close()


def load(spec):
    """The lines to show — a line is what ends in a newline, as editors and git count, so the line a search found is
    the line shown; a cut ends with an ellipsis line."""
    data = read(spec)
    if isinstance(data, str):
        return [data]
    if not spec.get("pipeline") and b"\0" in data[:8192]:
        return ["binary file"]
    cut = len(data) > LIMIT
    if cut:
        data = data[:data.rfind(b"\n", 0, LIMIT) + 1]
    lines = [line.rstrip("\r") for line in data.decode("utf-8", "replace").expandtabs(4).split("\n")]
    if len(lines) > 1 and lines[-1] == "":
        lines.pop()
    return lines + ["…"] if cut else lines


def plain(line):
    return "".join(ch for ch in ESCAPE.sub("", line) if ch not in CONTROL)


def shown(sgr):
    """SGR without 8, conceal: a file could hide a line from the preview with it. A color's own numbers (38;5;8, the
    r;g;b of 38;2) stay; nothing is left of one that only concealed."""
    params, kept, i = sgr[2:-1].split(";"), [], 0
    while i < len(params):
        size = 1
        if params[i] in ("38", "48", "58") and i + 1 < len(params):     # a color, its numbers after it
            size += {"5": 2, "2": 4}.get(params[i + 1], 1)
        part, i = params[i:i + size], i + size
        head = part[0].split(":")[0]
        if not (size == 1 and head.isdigit() and int(head) == 8):
            kept += part
    return f"\x1b[{';'.join(kept)}m" if kept else ""


def visible(line, cells):
    """LINE cut to CELLS columns: its colors kept, every other escape sequence and control character dropped."""
    out, used, pos = [], 0, 0
    while pos < len(line):
        m = ESCAPE.match(line, pos)
        if m:
            if SGR.fullmatch(m.group(0)):
                out.append(shown(m.group(0)))
            pos = m.end()
            continue
        ch = line[pos]
        pos += 1
        if ch in CONTROL:
            continue
        w = char_width(ch)
        if used + w > cells:
            break
        out.append(ch)
        used += w
    return "".join(out)


class Pager:
    def __init__(self, lines, title, line=None):
        self.lines, self.title = lines, title
        self.top = max(0, (line or 1) - 1 - CONTEXT)
        self.height = 24
        self.query = self.typing = self.hit = self.note = None

    def status(self):
        if self.typing is not None:
            return "/" + self.typing
        if self.note:
            return self.note
        return f"{self.title}  {self.top + 1}-{min(len(self.lines), self.top + self.height)}/{len(self.lines)}"

    def draw(self, term):
        cells, height = term.size()
        self.height = max(1, height - 1)
        self.top = max(0, min(self.top, len(self.lines) - self.height))
        out = []
        for row in range(self.height):
            index = self.top + row
            text = visible(self.lines[index], cells) if index < len(self.lines) else "\x1b[2m~"
            out.append(f"\x1b[{row + 1};1H\x1b[0m{text}\x1b[0m\x1b[K")
        out.append(f"\x1b[{height};1H\x1b[0;7m{visible(' ' + self.status(), cells)}\x1b[K\x1b[0m")
        term.write("".join(out))
        term.flush()

    def find(self, start, step):
        """Bring the first line after START (before it, for step -1) that holds the query into view."""
        needle = self.query.lower()
        for offset in range(1, len(self.lines) + 1):
            index = (start + offset * step) % len(self.lines)
            if needle in plain(self.lines[index]).lower():
                self.hit, self.top = index, max(0, index - CONTEXT)
                return
        self.note = f"not found: {self.query}"

    def handle(self, event):
        """React to EVENT; False when the pager should end."""
        if isinstance(event, Mouse):
            if event.kind in ("wheel_up", "wheel_down"):
                self.top = max(0, self.top + (3 if event.kind == "wheel_down" else -3))
            return True
        if not isinstance(event, Key):
            return True
        self.note = None
        if self.typing is not None:
            if event.name == "enter":
                self.query, self.typing = self.typing or self.query, None   # an empty search repeats the last one
                if self.query:
                    self.find(self.top - 1, 1)
            elif event.name == "esc":
                self.typing = None
            elif event.name == "backspace":
                self.typing = self.typing[:-1]
            elif event.name in ("char", "paste") and not event.ctrl:
                self.typing += event.char
            return True
        key = event.char if event.name == "char" else event.name
        if key in ("q", "esc") or (event.name == "char" and event.ctrl and event.char == "c"):
            return False
        moves = {"down": 1, "j": 1, "enter": 1, "up": -1, "k": -1, "pagedown": self.height, " ": self.height,
                 "f": self.height, "pageup": -self.height, "b": -self.height}
        if key in moves:
            self.top = max(0, self.top + moves[key])
        elif key in ("g", "home"):
            self.top = 0
        elif key in ("G", "end"):
            self.top = max(0, len(self.lines) - self.height)
        elif key == "/":
            self.typing = ""
        elif key in ("n", "N") and self.query:
            self.find(self.top + CONTEXT if self.hit is None else self.hit, 1 if key == "n" else -1)
        return True


def stamp(path):
    """What tells a spec written to PATH from the one before (written whole, in a new file put in place)."""
    try:
        info = os.stat(path)
    except OSError:
        return None
    return info.st_mtime_ns, info.st_size, info.st_ino


def spec_at(path):
    """The spec in PATH, or None."""
    try:
        with open(path, encoding="utf-8") as f:
            spec = json.load(f)
    except (OSError, ValueError):
        return None
    return spec if isinstance(spec, dict) else None


def close(path):
    """q: the preview tab closes (the panes beside it with it), and what it showed is forgotten."""
    try:
        os.remove(path)
    except OSError:
        pass
    tab = os.environ.get("HERDR_TAB_ID")
    if tab:
        try:
            Herdr().call("tab", "close", tab)
        except RuntimeError:
            pass                                    # the pane closes with its shell then


def main():
    path = os.environ["HERDR_FOLD_SPEC_FILE"]
    seen, spec = stamp(path), spec_at(path)
    if spec is None:
        print(f"nothing to show: {path}")
        return 1
    pager = Pager(load(spec), spec.get("title") or "", spec.get("line"))
    if os.name == "nt":
        from keys_windows import WindowsTerminal as Terminal
    else:
        from keys_unix import UnixTerminal as Terminal
    with Terminal() as term:
        drawn = None
        while True:
            if stamp(path) not in (seen, None):     # the next preview, written by a sidebar
                seen, spec = stamp(path), spec_at(path)
                if spec is not None:
                    pager, drawn = Pager(load(spec), spec.get("title") or "", spec.get("line")), None
            state = (pager, pager.top, pager.typing, pager.note, term.size())
            if state != drawn:                      # a mouse move changes nothing: no redraw
                pager.draw(term)
                drawn = (pager, pager.top, pager.typing, pager.note, term.size())
            if not all(pager.handle(event) for event in term.read(WATCH)):
                break
    close(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
