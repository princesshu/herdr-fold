"""The sidebar's pager: a file or a pipeline's output in color, with less's keys, or an image or a PDF drawn; q or Esc
closes the preview tab. It runs the pipeline itself so the keys stay the terminal's, and lets only colors through (no
cursor moves, titles or clipboard). Usage: HERDR_FOLD_SPEC_FILE=PATH pager.py (preview.py writes each spec there)."""
import base64
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import git  # noqa: E402
import media  # noqa: E402
from preview import Herdr  # noqa: E402
from screen import char_width, width  # noqa: E402
from vt import Key, Mouse  # noqa: E402

# any escape sequence: CSI, OSC (ended by BEL or ST, or by the line), DCS SOS PM APC (ended by ST), or ESC and one more
ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)?|[PX^_][^\x1b]*(?:\x1b\\)?|.?)", re.S)
SGR = re.compile(r"\x1b\[[0-9;:]*m")
CONTROL = {chr(c) for c in [*range(32), *range(0x7f, 0xa0)]}
LIMIT = 8_000_000             # bytes read at most: a huge file or an endless command does not stall the pager
CONTEXT = 3                   # lines shown above the line the pager opens at, or a search hit
WATCH = 0.3                   # seconds between looks at the spec's file: a new spec there is shown
SIDE = 10                     # an SVG's or a page's code and picture: the least columns a side keeps (rows: a third)
VIEWS = ("code", "split", "picture")   # an SVG's or a page's views, in its status row's order; c turns to the next
CLOSE = "Close Preview"                     # a right click's menu: the tab closed
MENU = "48;5;237;38;5;252"    # its colors: a background of its own, which a picture lies under
BELOW = -1073741825           # a picture's z in the Kitty graphics protocol: under a cell with a background of its own
WAIT = 30                     # seconds a pipeline may run (gh asking GitHub, a program that never ends): then stopped
PICTURE = 4271                # the picture's id in the Kitty graphics protocol: one at a time
CELL, CELL_PX = 2.1, 16       # a cell's height by its width, and its width in pixels, where the terminal says neither
GAP = 1                       # rows between two of a PDF's pages


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


KEY_HINT = re.compile(r"  \S: [^:]*$")    # a status row's last key hint, left out where the row has no room for it
CHOSEN = "\x1b[27;1;30;45m"  # a status row's chosen control: dark bold letters on the accent, as a sidebar button's
FAINT = "\x1b[100m"          # a control's key letter: in the row's reverse, the palette's gray
TURN = {False: ("\ueb57", "Stacked"), True: ("\ueb56", "Side by Side")}   # the turn's glyph and word: where it goes
NAME = 8                     # cells a status row keeps for its file's name before the turn's word gives way


def browse(path):
    """The right click's item that opens PATH as o does: in the browser, or in Preview (media.opener())."""
    return f"Open in {media.opener(path)}"


def browse_hint(path):
    """o's part of a status row, for PATH."""
    return f"  o: open in {media.opener(path).lower()}"


def bar(status, cells, lead=""):
    """STATUS as the pane's last row, CELLS wide, after LEAD (its controls, kept whole): its key hints left out, the
    last first, then its end cut short; spaces fill it out, as a terminal clears the rest without the row's colors."""
    room = cells - width(plain(lead))
    hint = KEY_HINT.search(status)
    while hint and width(" " + status) > room:
        status = status[:hint.start()]
        hint = KEY_HINT.search(status)
    status = " " + status
    if width(status) > room:
        status = visible(status, room - 1) + "…" if room > 1 else ""
    status = visible(status, room)
    return lead + status + " " * (room - width(status))


def controls(groups, cells):
    """A status row's controls in CELLS: GROUPS of a key and its items (label, short label, chosen, action), the chosen
    one in the accent; the short labels where the long ones leave the file's name under NAME cells. Gives them as
    written, and each item's cells and action for a click."""
    for short in (False, True):
        out, spans, at = [], [], 0
        for key, items in groups:
            out.append(f" {FAINT}{key}\x1b[49m")
            at += 2
            for label, brief, chosen, action in items:
                text = f" {brief if short else label} "
                out.append(f"{CHOSEN}{text}\x1b[0;7m" if chosen else text)
                spans.append((at, at + width(text), action))
                at += width(text)
        if cells - at - 1 >= NAME:
            break
    return "".join(out), spans


def turn(stacking):
    """The status row's turn, after v: its glyph and word say where it goes."""
    glyph, word = TURN[stacking]
    return "v", [(f"{glyph} {word}", glyph, False, "turn")]


def clicked(event, row, spans):
    """The action of the status row's control EVENT presses (ROW: that row, SPANS: its controls' cells); else None."""
    if isinstance(event, Mouse) and event.kind == "press" and event.button == 0 and event.y == row:
        return next((action for first, last, action in spans if first <= event.x < last), None)
    return None


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
    def __init__(self, lines, title, line=None, opens=None):
        self.lines, self.title, self.opens = lines, title, opens      # opens: a page o opens in the browser
        self.top = max(0, (line or 1) - 1 - CONTEXT)
        self.height = 24
        self.query = self.typing = self.hit = self.note = None
        self.lead = ""                                                # its status row's controls (PictureAndCode's)

    def shown(self):
        return self.top, self.typing, self.note

    def status(self):
        if self.typing is not None:
            return "/" + self.typing
        if self.note:
            return self.note
        hint = browse_hint(self.opens) if self.opens else ""
        return f"{self.title}  {self.top + 1}-{min(len(self.lines), self.top + self.height)}/{len(self.lines)}{hint}"

    def choices(self):
        """A right click's menu: the page in the browser where o opens it, and the tab closed."""
        return ([(browse(self.opens), None)] if self.opens else []) + [(CLOSE, None)]

    def choose(self, choice):
        """CHOICE of the menu done; False when the pager should end."""
        if self.opens and choice == browse(self.opens):
            self.note = None if media.open_in_browser(self.opens) else "No browser to open it in"
        return choice != CLOSE

    def rows(self, cells, rows):
        """The lines in view, ROWS of them cut to CELLS: each one's text, for its row."""
        self.height = max(1, rows)
        self.top = max(0, min(self.top, len(self.lines) - self.height))
        return [visible(self.lines[index], cells) if index < len(self.lines) else ""
                for index in range(self.top, self.top + self.height)]

    def draw(self, term):
        cells, height = term.size()
        out = [f"\x1b[{row + 1};1H\x1b[0m{text}\x1b[0m\x1b[K" for row, text in enumerate(self.rows(cells, height - 1))]
        out.append(f"\x1b[{height};1H\x1b[0;7m{bar(self.status(), cells, self.lead)}\x1b[0m")
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
        elif key == "o" and self.opens:
            self.note = None if media.open_in_browser(self.opens) else "No browser to open it in"
        return True


def cell(term):
    """A cell of TERM in pixels, (width, height): as the terminal says (herdr gives a pane's size in pixels), else the
    guess."""
    pixels, (columns, rows) = getattr(term, "pixels", lambda: None)(), term.size()
    return (pixels[0] / columns, pixels[1] / rows) if pixels else (CELL_PX, CELL_PX * CELL)


def fit(columns, rows, width, height, size=None):
    """Where a WIDTH x HEIGHT picture goes in COLUMNS x ROWS cells of SIZE (cell's): never past its own size, its
    aspect kept, centered. (row, column, its columns, its rows): both given, the terminal works neither out."""
    cw, ch = size or (CELL_PX, CELL_PX * CELL)
    scale = min(1, columns * cw / width, rows * ch / height)
    wide, tall = min(columns, max(1, round(width * scale / cw))), min(rows, max(1, round(height * scale / ch)))
    return (rows - tall) // 2, (columns - wide) // 2, wide, tall


def kitty(data, columns, rows, crop=None, image=PICTURE):
    """DATA (a PNG) as the Kitty graphics protocol's escapes, image IMAGE placed at the cursor COLUMNS wide, ROWS high
    or both, its part CROP (x, y, w, h in its pixels) alone; in chunks of 4096, q=2: the terminal answers nothing."""
    text = base64.b64encode(data).decode("ascii")
    chunks = [text[n:n + 4096] for n in range(0, len(text), 4096)] or [""]
    place = "".join(f"{key}={value}," for key, value in (("c", columns), ("r", rows)) if value)
    place += ("x={},y={},w={},h={},".format(*crop) if crop else "") + f"z={BELOW},"
    return "".join(f"\x1b_G{f'a=T,f=100,i={image},q=2,{place}' if n == 0 else ''}m={int(n < len(chunks) - 1)};"
                   f"{chunk}\x1b\\" for n, chunk in enumerate(chunks))


def gone(image=PICTURE):
    """Image IMAGE taken off the pane, its data with it."""
    return f"\x1b_Ga=d,d=I,i={image},q=2\x1b\\"


GONE = gone()


def opening(term, columns, height, what):
    """The pane cleared, saying WHAT opens: its first draw compiles a helper, a few seconds the first time."""
    term.write(f"\x1b[0m\x1b[2J\x1b[{height};1H\x1b[0;7m{visible(f' Opening the {what}…', columns)}\x1b[K\x1b[0m")
    term.flush()


def width_px(columns, cw=CELL_PX):
    """The pixels a picture COLUMNS wide (cells CW pixels wide) is made with."""
    return min(2400, max(480, round(columns * cw)))


class Picture:
    """An image, an SVG or a page drawn in the pane, fitted and centered: o opening it in the browser, q or Esc closing
    the tab. Its PNG is made in a folder of its own, gone at close()."""

    def __init__(self, path, title, image=PICTURE):
        self.path, self.title, self.note, self.image = path, title, None, image      # IMAGE: its id, one of two
        self.work = tempfile.mkdtemp(prefix="herdr-fold-picture.")
        self.opens, self.lead = media.browsable(), ""
        self.drawn = media.kind_of(path) in ("svg", "html")      # WebKit draws it, sharp at any width
        self.ready = not self.drawn                              # its helper compiled at its first draw
        self.cell = (CELL_PX, CELL_PX * CELL)                    # the pane's, as its terminal says at each draw

    def shown(self):
        return self.note

    def status(self):
        if self.note:
            return self.note
        return f"{self.title}{browse_hint(self.path) if self.opens else ''}"

    def png(self, columns, rows):
        """The picture as a PNG with the pixels COLUMNS x ROWS cells show: its longer side, the pane's height for a
        tall one."""
        width, high = width_px(columns, self.cell[0]), round(rows * self.cell[1])
        if self.drawn:                               # a page as a browser of the room's size shows it
            return media.drawn_png(self.path, width, self.work, high)
        return media.as_png(self.path, self.work, min(2400, max(width, high)))

    def draw(self, term):
        columns, height = term.size()
        self.prepare(term, columns, height)
        self.cell = cell(term)
        out = [self.taken(), "\x1b[0m\x1b[2J", self.place(columns, max(1, height - 1))]
        out.append(f"\x1b[{height};1H\x1b[0;7m{bar(self.status(), columns, self.lead)}\x1b[0m")
        term.write("".join(out))
        term.flush()

    def taken(self):
        """What takes the picture off the pane."""
        return gone(self.image)

    def prepare(self, term, columns, height):
        """The first draw's wait, said in the pane: the helper that draws an SVG or a page compiled."""
        if not self.ready:
            opening(term, columns, height, "picture")
            media.helper("page-shot")
            self.ready = True

    def place(self, columns, rows, left=0, made_for=None, top=0):
        """The picture fitted to COLUMNS x ROWS cells from column LEFT and row TOP, as escapes, its PNG made for
        MADE_FOR (columns, rows) when given (a side, dragged: made once); "" where it cannot be shown."""
        made = self.png(*(made_for or (columns, rows)))
        shape = media.size(made) if made else None
        if not shape:
            self.note = self.note or f"{self.title}: cannot be shown here{browse_hint(self.path) if self.opens else ''}"
            return ""
        row, column, wide, tall = fit(columns, rows, *shape, self.cell)
        with open(made, "rb") as f:
            return f"\x1b[{top + row + 1};{left + column + 1}H" + kitty(f.read(), wide, tall, image=self.image)

    def handle(self, event):
        """React to EVENT; False when the pager should end."""
        if not isinstance(event, Key):
            return True
        self.note = None
        key = event.char if event.name == "char" else event.name
        if key in ("q", "esc") or (event.name == "char" and event.ctrl and event.char == "c"):
            return False
        if key == "o" and self.opens:
            self.note = None if media.open_in_browser(self.path) else "No browser to open it in"
        return True

    def choices(self):
        return [(browse(self.path), None)] * bool(self.opens) + [(CLOSE, None)]

    def choose(self, choice):
        if self.opens and choice == browse(self.path):
            self.note = None if media.open_in_browser(self.path) else "No browser to open it in"
        return choice != CLOSE

    def close(self, term):
        """The picture taken off the pane (one already gone, a closed tab's: nothing to say) and its files away."""
        try:
            term.write(self.taken())
            term.flush()
        except OSError:
            pass
        shutil.rmtree(self.work, ignore_errors=True)


def layout(sizes, columns, ratio=CELL):
    """Where a PDF's pages (SIZES, each width and height) go COLUMNS wide, one under another a GAP apart, in cells RATIO
    times as high as wide: each one's first row and rows, and the rows they all take."""
    places, top = [], 0
    for wide, tall in sizes:
        rows = max(1, round(tall / wide * columns / ratio))
        places.append((top, rows))
        top += rows + GAP
    return places, max(0, top - GAP)


class Pdf(Picture):
    """A PDF's pages one under another, as wide as the pane and a row apart, scrolled by the wheel and the pager's
    moves; o opens it in the browser, q or Esc closes the tab. Each page is made a PNG as it comes into view."""

    def __init__(self, path, title):
        super().__init__(path, title)
        self.top, self.rows, self.sizes, self.places, self.total, self.placed = 0, 1, None, [], 0, 0
        self.ready = False                                       # its pages measured at its first draw

    def shown(self):
        return self.top, self.note

    def page(self):
        """The page at the middle of the pane, from 0."""
        middle = self.top + self.rows // 2
        return max([n for n, (first, _) in enumerate(self.places) if first <= middle] or [0])

    def status(self):
        if self.note:
            return self.note
        count = len(self.sizes) if self.sizes else "?"            # no helper: the first page alone, through sips
        return f"{self.title}  page {self.page() + 1} of {count}{browse_hint(self.path) if self.opens else ''}"

    def prepare(self, term, columns, height):
        """The first draw's wait, said in the pane: each page's size asked for (the helper compiled the first time)."""
        if not self.ready:
            opening(term, columns, height, "PDF")
            self.sizes, self.ready = media.pages(self.path), True

    def taken(self):
        return "".join(gone(PICTURE + n) for n in range(self.placed))

    def place(self, columns, rows, left=0):
        """The pages in view, COLUMNS wide less a column of air each side, ROWS high, as escapes: a page cut by the
        pane's edge shows its part in view."""
        wide, self.rows = max(1, columns - 2), rows
        width, ratio = width_px(wide, self.cell[0]), self.cell[1] / self.cell[0]
        first = None if self.sizes else media.page_png(self.path, 0, width, self.work)
        self.places, self.total = layout(self.sizes or ([media.size(first)] if first else []), wide, ratio)
        self.top = max(0, min(self.top, self.total - rows))
        out, self.placed = [], 0
        for n, (start, tall) in enumerate(self.places):
            seen, end = max(start, self.top), min(start + tall, self.top + rows)
            made = media.page_png(self.path, n, width, self.work) if seen < end else None
            shape = media.size(made) if made else None
            if not shape:
                continue
            above, below = round((seen - start) / tall * shape[1]), round((end - start) / tall * shape[1])
            with open(made, "rb") as f:
                out.append(f"\x1b[{seen - self.top + 1};{left + 2}H" + kitty(
                    f.read(), wide, end - seen, (0, above, shape[0], max(1, below - above)), PICTURE + self.placed))
            self.placed += 1
        if not self.places:
            self.note = self.note or f"{self.title}: cannot be shown here{browse_hint(self.path) if self.opens else ''}"
        return "".join(out)

    def handle(self, event):
        """React to EVENT; False when the pager should end."""
        if isinstance(event, Mouse):
            if event.kind in ("wheel_up", "wheel_down"):
                self.scroll(3 if event.kind == "wheel_down" else -3)
            return True
        if not isinstance(event, Key):
            return True
        key = event.char if event.name == "char" else event.name
        screen = max(1, self.rows - 1)
        moves = {"down": 1, "j": 1, "enter": 1, "up": -1, "k": -1, "pagedown": screen, " ": screen, "f": screen,
                 "pageup": -screen, "b": -screen, "g": -self.total, "home": -self.total, "G": self.total,
                 "end": self.total}
        if key in moves:
            self.note = None
            self.scroll(moves[key])
            return True
        return super().handle(event)

    def scroll(self, rows):
        self.top = max(0, min(self.total - self.rows, self.top + rows))


class PictureAndCode:
    """An SVG or a page, as VS Code's preview to the side: its code left and its picture right, or above and below where
    the pane is taller than wide (v, the status row's turn or the right click's menu turns them), the divider dragged,
    the picture fitted to its part; the status row's Code, Split and Picture, c or the menu choose what is shown."""

    def __init__(self, spec):
        title = spec.get("title") or ""
        self.picture, self.code = Picture(spec["picture"], title), Pager(load(spec), title, None, spec.get("open"))
        self.view, self.share, self.dragging, self.side = "split", 0.5, False, None
        self.stacked = None                          # chosen: code above the picture, or not; None: by the pane's shape
        self.size, self.stacking = (0, 0), False     # the pane's cells and its way, as last drawn
        self.row, self.spans = None, []              # the status row and its controls' cells, as last drawn

    def views(self):
        """The one shown alone, or the code beside the picture (its status)."""
        return self.picture if self.view == "picture" else self.code

    def switch(self, columns):
        """The status row's controls in COLUMNS, for the view drawn: the views after c; in Split, the turn after v."""
        groups = [("c", [(view.title(), view.title(), view == self.view, view) for view in VIEWS])]
        lead, self.spans = controls(groups + ([turn(self.stacking)] if self.view == "split" else []), columns)
        self.code.lead = self.picture.lead = lead

    def following(self):
        return VIEWS[(VIEWS.index(self.view) + 1) % len(VIEWS)]

    def shown(self):
        return self.view, self.share, self.stacked, self.views().shown()

    def status(self):
        return self.views().status()

    def divider(self, cells, least=SIDE):
        """The divider's column (or row, stacked) in CELLS: SHARE of them, each side LEAST at least."""
        return max(min(least, cells // 2), min(cells - least - 1, round(cells * self.share)))

    def draw(self, term):
        columns, height = term.size()
        rows = self.row = height - 1
        if self.view != "split":
            self.switch(columns)
            if self.view == "code":
                term.write(GONE)                     # the picture taken off for the lines
            return self.views().draw(term)
        self.picture.prepare(term, columns, height)
        size = self.picture.cell = cell(term)
        self.size, self.stacking = (columns, rows), self.stacked if self.stacked is not None \
            else columns * size[0] < rows * size[1]
        self.switch(columns)
        out = [GONE, "\x1b[0m\x1b[2J"]
        if self.stacking:
            at = self.divider(rows, max(1, rows // 3))
            for row, text in enumerate(self.code.rows(columns, at)):
                out.append(f"\x1b[{row + 1};1H\x1b[0m{text}\x1b[0m")
            out.append(f"\x1b[{at + 1};1H\x1b[2m{'─' * columns}\x1b[0m")
            box, left, top = (columns, rows - at - 1), 0, at + 1
        else:
            at = self.divider(columns)
            for row, text in enumerate(self.code.rows(at, rows)):
                out.append(f"\x1b[{row + 1};1H\x1b[0m{text}\x1b[0m")
            out += [f"\x1b[{row + 1};{at + 1}H\x1b[2m│\x1b[0m" for row in range(rows)]
            box, left, top = (columns - at - 1, rows), at + 1, 0
        if not self.dragging or self.side is None:   # made for its part once let go: fitted meanwhile, as made
            self.side = box
        out.append(self.picture.place(*box, left, self.side, top))
        out.append(f"\x1b[{height};1H\x1b[0;7m{bar(self.status(), columns, self.code.lead)}\x1b[0m")
        term.write("".join(out))
        term.flush()
        return None

    def handle(self, event):
        action = clicked(event, self.row, self.spans)
        if action == "turn":
            self.stacked = not self.stacking
            return True
        if action:
            self.view = action
            return True
        if isinstance(event, Mouse) and self.view == "split" and event.kind in ("press", "move", "release"):
            columns, rows = self.size
            at, cells = (event.y, rows) if self.stacking else (event.x, columns)
            least = max(1, rows // 3) if self.stacking else SIDE
            if event.kind == "press" and event.button == 0 and at == self.divider(cells, least):
                self.dragging = True
                return True
            if self.dragging:
                if event.kind == "move" and event.button == 0:
                    self.share = at / max(1, cells)
                self.dragging = event.kind != "release"
                return True
        if isinstance(event, Key) and event.name == "char" and event.char in ("c", "v") and not event.ctrl \
                and self.code.typing is None:                # typed into a search, it is a letter
            if event.char == "c":
                self.view = self.following()
            else:
                self.stacked = not self.stacking
            return True
        return self.views().handle(event)

    def choices(self):
        return [(view.title(), view == self.view) for view in VIEWS] + [
            ("Side by Side", not self.stacking), ("Stacked", self.stacking)] + self.picture.choices()

    def choose(self, choice):
        if choice.lower() in VIEWS:
            self.view = choice.lower()
            return True
        if choice in ("Side by Side", "Stacked"):
            self.stacked = choice == "Stacked"
            self.stacking = self.stacked
            return True
        return self.picture.choose(choice)

    def close(self, term):
        self.picture.close(term)


SIDES = {False: ("Index", "Working Tree"), True: ("HEAD", "Index")}    # a change's before and after, staged or not


class PictureChange:
    """A changed picture as VS Code's image diff: its before and after side by side, or one above the other where the
    pane is taller than wide (v, the status row's turn or the right click turns them), each under its caption; a new
    one's after alone, a deleted one's before alone. git's copies of it live in a folder of its own, gone at close()."""

    def __init__(self, spec):
        change, self.title = spec["change"], spec.get("title") or ""
        root, path, staged = change["root"], change["path"], change["staged"]
        self.work = tempfile.mkdtemp(prefix="herdr-fold-change.")
        found, here = [], os.path.join(root, path)
        for n, (label, at) in enumerate(zip(SIDES[staged], ("HEAD", "") if staged else ("", None))):
            out = os.path.join(self.work, f"{n}{os.path.splitext(path)[1]}")      # its extension kept: its kind
            if at is None:
                found.append((here if os.path.isfile(here) else None, label))
            else:
                found.append((out if git.committed(root, path, out, at) else None, label))
        self.sides = [(Picture(shown, self.title, PICTURE + n), label) for n, (shown, label) in enumerate(found)
                      if shown]
        self.stacked, self.stacking = None, False    # chosen: one above the other, or not; None: by the pane's shape
        self.row, self.spans = None, []              # the status row and its turn's cells, as last drawn

    def shown(self):
        return self.stacked, tuple(side.note for side, _ in self.sides)

    def status(self):
        note = next((side.note for side, _ in self.sides if side.note), None)
        return note or (self.title if self.sides else f"{self.title}: nothing to show")

    def draw(self, term):
        columns, height = term.size()
        rows, size = height - 1, cell(term)
        self.row, self.stacking = rows, self.stacked if self.stacked is not None else columns * size[0] < rows * size[1]
        lead, self.spans = controls([turn(self.stacking)], columns) if len(self.sides) == 2 else ("", [])
        out = [gone(PICTURE), gone(PICTURE + 1), "\x1b[0m\x1b[2J"]
        if len(self.sides) == 2 and self.stacking:
            at = rows // 2
            out.append(f"\x1b[{at + 1};1H\x1b[2m{'─' * columns}\x1b[0m")
            parts = [(0, 0, columns, at), (0, at + 1, columns, rows - at - 1)]
        elif len(self.sides) == 2:
            at = columns // 2
            out += [f"\x1b[{row + 1};{at + 1}H\x1b[2m│\x1b[0m" for row in range(rows)]
            parts = [(0, 0, at, rows), (at + 1, 0, columns - at - 1, rows)]
        else:
            parts = [(0, 0, columns, rows)]
        for (side, label), (left, top, wide, tall) in zip(self.sides, parts):
            side.cell, shape = size, media.pixels(side.path)
            caption = f"{label} · {shape[0]} × {shape[1]}" if shape else label
            out.append(f"\x1b[{top + 1};{left + 2}H\x1b[2m{visible(caption, max(1, wide - 2))}\x1b[0m")
            out.append(side.place(wide, max(1, tall - 1), left, None, top + 1))
        out.append(f"\x1b[{height};1H\x1b[0;7m{bar(self.status(), columns, lead)}\x1b[0m")
        term.write("".join(out))
        term.flush()
        return None

    def handle(self, event):
        """React to EVENT; False when the pager should end."""
        if clicked(event, self.row, self.spans) == "turn":
            self.stacked = not self.stacking
        if not isinstance(event, Key):
            return True
        key = event.char if event.name == "char" else event.name
        if key in ("q", "esc") or (event.name == "char" and event.ctrl and event.char == "c"):
            return False
        if key == "v" and not event.ctrl and len(self.sides) == 2:
            self.stacked = not self.stacking
        return True

    def choices(self):
        two = len(self.sides) == 2
        return [("Side by Side", not self.stacking), ("Stacked", self.stacking)] * two + [(CLOSE, None)]

    def choose(self, choice):
        if choice in ("Side by Side", "Stacked"):
            self.stacked = self.stacking = choice == "Stacked"
        return choice != CLOSE

    def close(self, term):
        for side, _ in self.sides:
            side.close(term)
        shutil.rmtree(self.work, ignore_errors=True)


class Popup:
    """A right click's menu, at the pointer and inside the pane: CHOICES a row each, (label, whether it is the one on,
    None: no check), Enter or a click picking one, Esc or a click outside dropping it."""

    def __init__(self, choices, y, x, columns, rows):
        self.choices, self.index = choices, 0
        self.checks = any(on is not None for _, on in choices)
        self.wide = max(width(label) for label, _ in choices) + (6 if self.checks else 4)
        self.top = max(0, min(y, rows - 3 - len(choices)))
        self.left = max(0, min(x, columns - self.wide))

    def draw(self):
        """The menu as escapes: a box over the pane (a background of its own, over a picture), the chosen row lit."""
        rows = ["┌" + "─" * (self.wide - 2) + "┐"]
        for n, (label, on) in enumerate(self.choices):
            mark = ("✓ " if on else "  ") if self.checks else ""
            text = f" {mark}{label}".ljust(self.wide - 2)
            rows.append(f"│\x1b[{'7' if n == self.index else '27'}m{text}\x1b[27m│")
        rows.append("└" + "─" * (self.wide - 2) + "┘")
        return "".join(f"\x1b[{self.top + n + 1};{self.left + 1}H\x1b[0;{MENU}m{row}\x1b[0m"
                       for n, row in enumerate(rows))

    def handle(self, event):
        """EVENT on the menu: the choice's label, "" when it is dropped, None while it stays."""
        if isinstance(event, Key):
            if event.name in ("up", "down"):
                self.index = (self.index + (1 if event.name == "down" else -1)) % len(self.choices)
            elif event.name == "enter":
                return self.choices[self.index][0]
            elif event.name == "esc" or event.name == "char" and event.char == "q":
                return ""
            return None
        if not isinstance(event, Mouse) or event.kind not in ("press", "move"):
            return None
        row = event.y - self.top - 1
        inside = 0 <= row < len(self.choices) and self.left <= event.x < self.left + self.wide
        if event.kind == "move":
            self.index = row if inside else self.index
            return None
        return self.choices[row][0] if inside else ""


def viewer(spec):
    """SPEC's view: a changed picture's before and after, an SVG or a page as its code and its picture, an image or a
    PDF drawn, else the pager over its lines."""
    if spec.get("change"):
        return PictureChange(spec)
    if spec.get("picture") and media.kind_of(spec["picture"]) in ("svg", "html"):
        return PictureAndCode(spec)
    if spec.get("picture") and media.kind_of(spec["picture"]) == "pdf":
        return Pdf(spec["picture"], spec.get("title") or "")
    if spec.get("picture"):
        return Picture(spec["picture"], spec.get("title") or "")
    return Pager(load(spec), spec.get("title") or "", spec.get("line"), spec.get("open"))


def redraw(view, term, drawn):
    """VIEW drawn again where it or the pane's size changed since DRAWN; what it is drawn for now. The size is the one
    before it draws: a pane resized while a picture is made (a moment) is drawn again at the next look."""
    size = term.size()
    if (view, view.shown(), size) != drawn:
        view.draw(term)
        drawn = (view, view.shown(), size)
    return drawn


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


def forget(path, seen):
    """What the pager showed forgotten (its spec at PATH, as SEEN), not the next one a sidebar wrote there meanwhile."""
    if stamp(path) == seen:
        try:
            os.remove(path)
        except OSError:
            pass


def close():
    """q: the preview tab closes, the panes beside it with it."""
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
    pager = viewer(spec)
    if os.name == "nt":
        from keys_windows import WindowsTerminal as Terminal
    else:
        from keys_unix import UnixTerminal as Terminal
    for name in ("SIGHUP", "SIGTERM"):                # a closed tab's pane ends so: the picture's files go too
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lambda *_: sys.exit(0))
    with Terminal() as term:
        drawn, menu, going = None, None, True
        try:
            while going:
                if stamp(path) not in (seen, None):     # the next preview, written by a sidebar
                    seen, spec = stamp(path), spec_at(path)
                    if spec is not None:
                        if isinstance(pager, (Picture, PictureAndCode)):
                            pager.close(term)
                        pager, drawn, menu = viewer(spec), None, None
                drawn = redraw(pager, term, drawn)      # a mouse move changes nothing: no redraw
                if menu:
                    term.write(menu.draw())
                    term.flush()
                for event in term.read(WATCH):
                    if menu:                            # the right click's menu takes every event while it is open
                        chosen = menu.handle(event)
                        if chosen is not None:
                            menu, drawn = None, None     # its box goes with a draw anew
                            going = not chosen or pager.choose(chosen)
                    elif isinstance(event, Mouse) and event.kind == "press" and event.button == 2:
                        menu = Popup(pager.choices(), event.y, event.x, *term.size())
                    else:
                        going = pager.handle(event)
                    if not going:
                        break
        finally:
            if isinstance(pager, (Picture, PictureAndCode)):
                pager.close(term)
            forget(path, seen)                          # q, or the tab closed otherwise (a hang-up)
    close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
