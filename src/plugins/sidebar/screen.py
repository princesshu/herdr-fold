"""The sidebar's drawing: a canvas of cells the views paint on (a wide character takes two, never half of one),
clickable regions, a renderer that sends only the rows changed since the last frame, and where the icons go (their
glyphs are core/icons.py's)."""
import json
import os
import unicodedata
from dataclasses import dataclass

ROOMY = 16          # rows a pane needs for tall controls: the tabs' three, twelve for the view, a footer

ELLIPSIS = "…"

# git's change codes' color roles (the letters shown for them are core/icons.py's)
GIT_ROLE = {"M": "modified", "A": "added", "R": "added", "?": "added", "D": "deleted", "U": "conflict"}


@dataclass(frozen=True)
class Style:
    fg: str = None            # a theme role (theme.py), or None for the terminal's default
    bg: str = None
    bold: bool = False
    strike: bool = False
    underline: bool = False


PLAIN = Style()


def char_width(ch):
    """Cells a character takes: 0 for control and combining marks, 1 for a Nerd Font icon (private use), 2 for a
    wide East Asian character, else 1."""
    code = ord(ch)
    if code < 0x20 or 0x7f <= code < 0xa0 or unicodedata.combining(ch):
        return 0
    if 0xe000 <= code <= 0xf8ff or code >= 0xf0000:
        return 1
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def width(text):
    return sum(char_width(ch) for ch in text)


def truncate(text, limit):
    """TEXT in LIMIT cells: as it is if it fits, else cut with "…" (padded to exactly LIMIT if a wide character
    would not fit)."""
    if width(text) <= limit:
        return text
    if limit <= 0:
        return ""
    kept, used = [], 0
    for ch in text:
        w = char_width(ch)
        if used + w > limit - 1:
            break
        kept.append(ch)
        used += w
    return "".join(kept) + ELLIPSIS + " " * (limit - 1 - used)


def after(nerd):
    """The blank after a mark before its text: two cells after a Nerd Font icon (the terminal draws the icon over the
    first one), one after a plain mark."""
    return "  " if nerd else " "


def icons_on(state_dir):
    """Whether the sidebar shows Nerd Font icons (its settings.json in STATE_DIR): unless turned off there."""
    try:
        with open(os.path.join(state_dir, "settings.json"), encoding="utf-8") as f:
            settings = json.load(f)
    except (OSError, ValueError):
        return True
    return not isinstance(settings, dict) or settings.get("icons") is not False


def centered(start, cells):
    """The column of a button's icon in CELLS columns from START, its middle one (an odd number has a very middle): the
    icons there are codicons, which Ghostty draws from that cell's left edge a little wider than it, or plain marks."""
    return start + (cells - 1) // 2


class Canvas:
    def __init__(self, width_, height):
        self.width, self.height = width_, height
        self.cursor = None                    # (row, column) of the field that takes the keys: the terminal's cursor
        self.rows = [[(" ", PLAIN) for _ in range(width_)] for _ in range(height)]
        self.regions = []

    def put(self, y, x, text, style=PLAIN):
        """Paint TEXT at row Y from column X; what does not fit is left out. Returns the next free column."""
        if not 0 <= y < self.height:
            return x
        row = self.rows[y]
        for ch in text:
            if "\ud800" <= ch <= "\udfff":
                ch = "\ufffd"                            # a byte of a name that is not UTF-8
            w = char_width(ch)
            if w == 0:
                continue
            if x < 0 or x + w > self.width:
                break
            for cell in range(x, x + w):
                self.unpair(row, cell)
            row[x] = (ch, style)
            if w == 2:
                row[x + 1] = ("", style)                # the right half of a wide character
            x += w
        return x

    def unpair(self, row, x):
        """Before cell X is painted over: the other half of a wide character there becomes a space."""
        ch, _ = row[x]
        if ch == "" and x > 0:
            row[x - 1] = (" ", row[x - 1][1])
        elif ch and char_width(ch) == 2 and x + 1 < self.width:
            row[x + 1] = (" ", row[x + 1][1])

    def shape(self, y, x, cells, rows, color):
        """A tall control in COLOR, CELLS wide, square: ROWS content rows (Y+1 to Y+ROWS) between a half row of edge
        above (row Y) and below (row Y+ROWS+1), block characters the terminal draws to the cell's edges."""
        edge = Style(fg=color)
        self.put(y, x, "▄" * cells, edge)
        for row in range(y + 1, y + 1 + rows):
            self.put(row, x, " " * cells, Style(bg=color))
        self.put(y + rows + 1, x, "▀" * cells, edge)

    def chip(self, y, x, cells, color, under=None):
        """A one-row control in COLOR, CELLS wide; its content goes between X+1 and X+CELLS-1. On a background UNDER,
        its ends are half cells (block characters the terminal draws to the cell's middle): half a cell of air round
        the content instead of a whole one."""
        self.put(y, x, " " * cells, Style(bg=color))
        if under:
            self.put(y, x, "▐", Style(fg=color, bg=under))
            self.put(y, x + cells - 1, "▌", Style(fg=color, bg=under))

    def band(self, y, bg):
        """Row Y's background as a chosen or hovered row (none: a plain row)."""
        self.put(y, 0, " " * self.width, Style(bg=bg))

    def control(self, y, x, cells, rows, color, roomy):
        """A control's shape: in a roomy pane tall, a half row of edge above and below its ROWS content rows; in a low
        one a chip (plain rows for more than one). Returns its first content row and the rows it takes."""
        if roomy:
            self.shape(y, x, cells, rows, color)
            return y + 1, rows + 2
        if rows == 1:
            self.chip(y, x, cells, color)
        else:
            for row in range(y, y + rows):
                self.put(row, x, " " * cells, Style(bg=color))
        return y, rows

    def region(self, y, x0, x1, target):
        """Columns X0..X1-1 of row Y answer clicks with TARGET (the latest region on top)."""
        self.regions.append((y, x0, x1, target))

    def backdrop(self, y, x0, x1, target):
        """As region(), but under every other one, whenever it is laid."""
        self.regions.insert(0, (y, x0, x1, target))

    def paste(self, part):
        """PART, a canvas as tall and narrower, over this one's left side: its cells, what answers its clicks, its
        cursor."""
        for row, cells in zip(self.rows, part.rows):
            row[:len(cells)] = cells
        self.regions += part.regions
        self.cursor = part.cursor or self.cursor

    def hit(self, x, y):
        for ry, x0, x1, target in reversed(self.regions):
            if ry == y and x0 <= x < x1:
                return target
        return None


UNKNOWN = object()                            # the terminal's cursor before the first frame, or after someone else's


class Renderer:
    def __init__(self, theme):
        self.theme = theme
        self.previous = None
        self.size = None
        self.cursor = UNKNOWN

    def reset(self):
        self.previous, self.cursor = None, UNKNOWN

    def frame(self, canvas):
        """The escape sequences that turn the last frame into CANVAS; then the terminal's own cursor, a blinking bar
        where a field takes the keys (it stands at the left edge of its cell and hides no letter), hidden otherwise."""
        lines = [self.line(row) for row in canvas.rows]
        full = self.previous is None or self.size != (canvas.width, canvas.height)
        out = ["\x1b[0m\x1b[2J"] if full else []
        for y, line in enumerate(lines):
            if full or self.previous[y] != line:
                out.append(f"\x1b[{y + 1};1H{line}\x1b[0m")
        if canvas.cursor != self.cursor or (canvas.cursor and out):      # drawing moves it: put it back
            row, column = canvas.cursor or (0, 0)
            out.append(f"\x1b[{row + 1};{column + 1}H\x1b[5 q\x1b[?25h" if canvas.cursor else "\x1b[?25l")
        self.previous, self.size, self.cursor = lines, (canvas.width, canvas.height), canvas.cursor
        return "".join(out)

    def line(self, row):
        parts, current = [], None
        for ch, style in row:
            if ch == "":
                continue
            if style != current:
                parts.append("\x1b[0m" + self.theme.sgr(style))
                current = style
            parts.append(ch)
        return "".join(parts)
