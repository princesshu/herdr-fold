"""The sidebar's controls: a list that keeps its selection in view, a text field (one line, or several for the commit
message), a drop-down menu and a confirmation. Plus Action, what a view asks the app to do: the views stay free of
side effects, so they are tested without a terminal."""
import time
from dataclasses import dataclass

from screen import PLAIN, Style, char_width, truncate, width

DOUBLE_CLICK = 0.4            # seconds: a click on the same place sooner than this after one is a double (or triple)


@dataclass(frozen=True)
class Action:
    name: str
    args: tuple = ()


class ListView:
    def __init__(self, height):
        self.height = max(1, height)
        self.items, self.index, self.top = [], 0, 0

    def set(self, items):
        self.items = list(items)
        self.index = min(self.index, max(0, len(self.items) - 1))
        self.fit()

    def resize(self, height):
        self.height = max(1, height)
        self.fit()

    def fit(self):
        """No empty rows below the end while items are hidden above, and the selection in view."""
        self.top = min(self.top, max(0, len(self.items) - self.height))
        self.keep_visible()

    def selected(self):
        return self.items[self.index] if self.items else None

    def move(self, delta):
        if self.items:
            self.index = max(0, min(len(self.items) - 1, self.index + delta))
            self.keep_visible()

    def page(self, delta):
        self.move(delta * self.height)

    def scroll(self, delta):
        """The wheel: the view moves, the selection stays."""
        self.top = max(0, min(max(0, len(self.items) - self.height), self.top + delta))

    def keep_visible(self):
        if self.index < self.top:
            self.top = self.index
        elif self.index >= self.top + self.height:
            self.top = self.index - self.height + 1

    def at(self, row):
        """The item index shown on ROW of the view, or None."""
        index = self.top + row
        return index if 0 <= row < self.height and index < len(self.items) else None


class TextInput:
    def __init__(self, multiline=False, placeholder=""):
        self.multiline, self.placeholder = multiline, placeholder
        self.text, self.cursor = "", 0
        self.anchor = None            # the selection's other end (the cursor is the one that moves), or None
        self.top = 0                  # the first row shown: a text taller than the field shows from here
        self.place = None             # where it was last drawn, for a click: (row, column, cells, rows)
        self.clicks = (None, 0, 0)    # the last click: when, at which index, how many in a row

    def clear(self):
        self.text, self.cursor, self.top, self.anchor = "", 0, 0, None

    def span(self):
        """The selection's (start, end), or None."""
        if self.anchor is None or self.anchor == self.cursor:
            return None
        return min(self.anchor, self.cursor), max(self.anchor, self.cursor)

    def selected(self):
        span = self.span()
        return self.text[span[0]:span[1]] if span else ""

    def cut(self):
        """The selection taken out of the text; whether there was one."""
        span, self.anchor = self.span(), None
        if span:
            self.text, self.cursor = self.text[:span[0]] + self.text[span[1]:], span[0]
        return bool(span)

    def insert(self, text):
        self.cut()
        self.text = self.text[:self.cursor] + text + self.text[self.cursor:]
        self.cursor += len(text)

    def line_start(self):
        return self.text.rfind("\n", 0, self.cursor) + 1

    def line_end(self):
        end = self.text.find("\n", self.cursor)
        return len(self.text) if end < 0 else end

    def word_start(self):
        """Where the word before the cursor starts, the spaces between them taken with it."""
        i = self.cursor
        while i and self.text[i - 1].isspace():
            i -= 1
        while i and not self.text[i - 1].isspace():
            i -= 1
        return i

    def word_at(self, i):
        """(start, end) of the word at index I (letters, digits and _), or of the one character there."""
        i = min(i, len(self.text) - 1)
        if i < 0:
            return 0, 0
        def is_word(ch):
            return ch.isalnum() or ch == "_"
        if not is_word(self.text[i]):
            return i, i + 1
        start, end = i, i + 1
        while start and is_word(self.text[start - 1]):
            start -= 1
        while end < len(self.text) and is_word(self.text[end]):
            end += 1
        return start, end

    def handle(self, key):
        """Edit by KEY; False if the key is not the field's (the view handles it)."""
        name = key.name
        if name in ("left", "right", "home", "end", "up", "down") or (name == "char" and key.ctrl and key.char in "ae"):
            return self.move(key)
        if name == "char" and key.ctrl:
            if key.char != "u":
                return False
            if not self.cut():
                start = self.line_start()
                self.text, self.cursor = self.text[:start] + self.text[self.cursor:], start
        elif name == "char" and not key.alt:
            self.insert(key.char)
        elif name == "paste":
            self.insert(key.char if self.multiline else key.char.replace("\r\n", " ").replace("\n", " "))
        elif name == "enter" and self.multiline:
            self.insert("\n")
        elif name == "f8":                     # what herdr sends a sidebar that has the keys for Cmd + A (actions.py)
            self.anchor, self.cursor = 0, len(self.text)
        elif name in ("backspace", "delete"):
            if self.cut():
                pass
            elif name == "backspace" and key.alt:                     # Option + Backspace: the word before
                start = self.word_start()
                self.text, self.cursor = self.text[:start] + self.text[self.cursor:], start
            elif name == "backspace" and self.cursor:
                self.text, self.cursor = self.text[:self.cursor - 1] + self.text[self.cursor:], self.cursor - 1
            elif name == "delete" and self.cursor < len(self.text):
                self.text = self.text[:self.cursor] + self.text[self.cursor + 1:]
        else:
            return False
        return True

    def move(self, key):
        """A cursor key (Ctrl + A and E too): with Shift the selection follows the cursor; without, Left or Right
        leaves a selection at that side, any other drops it."""
        span = self.span()
        if key.shift:
            self.anchor = self.cursor if self.anchor is None else self.anchor
        elif span and key.name in ("left", "right"):
            self.cursor, self.anchor = span[0] if key.name == "left" else span[1], None
            return True
        else:
            self.anchor = None
        name = {"a": "home", "e": "end"}[key.char] if key.name == "char" else key.name
        if name == "left":
            self.cursor = max(0, self.cursor - 1)
        elif name == "right":
            self.cursor = min(len(self.text), self.cursor + 1)
        elif name == "home":
            self.cursor = self.line_start()
        elif name == "end":
            self.cursor = self.line_end()
        elif self.multiline:
            column = self.cursor - self.line_start()
            if name == "up" and self.line_start() > 0:
                start = self.text.rfind("\n", 0, self.line_start() - 1) + 1
                self.cursor = min(start + column, self.line_start() - 1)
            elif name == "down" and self.line_end() < len(self.text):
                start = self.line_end() + 1
                end = self.text.find("\n", start)
                self.cursor = min(start + column, len(self.text) if end < 0 else end)
            else:
                return False
        else:
            return False
        return True

    def index_at(self, x, y):
        """The text's index at column X, row Y of the canvas where the field was last drawn: past a row's text its end,
        above or below the field its nearest row."""
        if not self.place or not self.text:
            return len(self.text)
        row0, column0, cells, rows = self.place
        spans = wrap(self.text, cells)
        row = self.top + min(max(y - row0, 0), rows - 1)
        if row >= len(spans):
            return len(self.text)
        start, end = spans[row]
        i, used = start, 0
        while i < end and used + char_width(self.text[i]) <= x - column0:
            used += char_width(self.text[i])
            i += 1
        soft_break = row + 1 < len(spans) and spans[row + 1][0] == end
        return i - 1 if soft_break and i == end else i       # the break's end shows on the next row

    def press(self, x, y, now=None):
        """A click at column X, row Y: the cursor there, where a drag selects from; a second one there soon after
        selects its word, a third the whole text."""
        now = time.monotonic() if now is None else now
        at = self.index_at(x, y)
        last, where, count = self.clicks
        count = count + 1 if last is not None and now - last <= DOUBLE_CLICK and where == at else 1
        self.clicks = (now, at, count)
        if count == 1:
            self.anchor = self.cursor = at
        elif count == 2:
            self.anchor, self.cursor = self.word_at(at)
        else:
            self.anchor, self.cursor = 0, len(self.text)

    def drag(self, x, y):
        """The mouse dragged to column X, row Y: the selection from where it was pressed to there."""
        self.anchor = self.cursor if self.anchor is None else self.anchor
        self.cursor = self.index_at(x, y)

    def lines(self, cells):
        """The text wrapped to CELLS wide rows (an empty field is one empty row)."""
        return [self.text[start:end] for start, end in wrap(self.text, cells)]

    def cursor_cell(self, cells):
        """(row, column) of the cursor in lines(CELLS): at a row's soft break it stands at the start of the next row."""
        rows = wrap(self.text, cells)
        for row, (start, end) in enumerate(rows):
            soft_break = row + 1 < len(rows) and rows[row + 1][0] == end
            if start <= self.cursor < end or (self.cursor == end and not soft_break):
                return row, width(self.text[start:self.cursor])
        return len(rows) - 1, 0

    def draw(self, canvas, y, x, cells, height, style=Style(bg="input"), focused=False):
        """Paint the field (or its placeholder) in HEIGHT rows, its selection lit; when FOCUSED, its cursor's place goes
        to the canvas, for the terminal's own cursor. Returns the rows used."""
        self.place = (y, x, cells, height)
        spans = wrap(self.text, cells)
        rows = [self.text[start:end] for start, end in spans] if self.text else [self.placeholder]
        row, column = self.cursor_cell(cells)
        if focused:                   # the rows at the cursor show, wherever it is; otherwise they stay where they were
            self.top = min(self.top, row) if row < self.top + height else row - height + 1
        self.top = max(0, min(self.top, len(rows) - height))
        shown, span = rows[self.top:self.top + height], self.span()
        for i in range(height):
            canvas.put(y + i, x, " " * cells, style)
        for i, text in enumerate(shown):
            text_style = style if self.text else Style(fg="muted", bg=style.bg)
            canvas.put(y + i, x, truncate(text.rstrip(" "), cells), text_style)   # the break's spaces lie past the edge
            start, end = spans[self.top + i]
            a, b = (max(start, span[0]), min(end, span[1])) if span else (0, 0)       # the row's part of it
            if a < b:
                before = width(self.text[start:a])
                canvas.put(y + i, x + before, truncate(self.text[a:b].rstrip(" "), cells - before),
                           Style(fg=style.fg, bg="selection"))
        if focused and self.top <= row < self.top + height:
            canvas.cursor = (y + row - self.top, x + min(column, cells - 1))
        canvas.region(y, x, x + cells, "input")
        return max(1, min(height, len(shown)))


def wrap(text, cells, breaks=" "):
    """TEXT's rows CELLS wide, as (start, end) index pairs: each of its lines starts a row, a row breaks after the last
    of BREAKS that fits (spaces at a break stay at its end, past the edge), a word wider than a row inside it."""
    rows, start = [], 0
    for logical in text.split("\n"):
        end = start + len(logical)
        row, used, after_space, i = start, 0, None, start
        while i < end:
            ch = text[i]
            if ch != " " and used + char_width(ch) > cells and i > row:
                row_end = after_space if after_space is not None and after_space > row else i
                rows.append((row, row_end))
                row, after_space = row_end, None
                used = width(text[row:i])
                continue
            used += char_width(ch)
            if ch in breaks:
                after_space = i + 1
            i += 1
        rows.append((row, end))
        start = end + 1
    return rows


MENU_WIDEST = 14              # a menu's cells at least, as herdr's own


class Menu:
    """A choice a row: ↑ ↓ and Enter, or a click; drawn as herdr's own menus: a frame in the accent on the panel's
    background, the chosen row lit in the accent."""

    def __init__(self, choices):
        self.choices, self.index = list(choices), 0

    def width(self):
        """The cells it takes, as herdr's own: its widest choice and four more (the frame, two of air)."""
        return max(MENU_WIDEST, max(width(choice) for choice in self.choices) + 4)

    def height(self):
        return len(self.choices) + 2

    def at(self, y, x, cells, top, bottom):
        """Where it goes for a click at Y, X, as herdr's own: its corner there, moved in as far as it must to stay
        between rows TOP and BOTTOM in a pane CELLS wide; (y, x, its width)."""
        wide = min(cells, self.width())
        return max(top, min(y, bottom - self.height())), max(0, min(x, cells - wide)), wide

    def handle(self, key):
        if key.name in ("up", "down"):
            self.index = (self.index + (1 if key.name == "down" else -1)) % len(self.choices)
        elif key.name == "enter":
            return self.choices[self.index]
        elif key.name == "esc":
            return "cancel"
        return None

    def draw(self, canvas, y, x, cells):
        frame = Style(fg="accent", bg="panel")
        canvas.put(y, x, "┌" + "─" * (cells - 2) + "┐", frame)
        for i, choice in enumerate(self.choices, 1):
            style = (Style(fg="button_text", bg="button", bold=True) if i - 1 == self.index
                     else Style(fg="text", bg="panel"))
            canvas.put(y + i, x, "│", frame)
            canvas.put(y + i, x + 1, truncate(choice, cells - 2).ljust(cells - 2), style)
            canvas.put(y + i, x + cells - 1, "│", frame)
            canvas.region(y + i, x + 1, x + cells - 1, f"menu:{i - 1}")
        canvas.put(y + len(self.choices) + 1, x, "└" + "─" * (cells - 2) + "┘", frame)
        return self.height()


class Confirm:
    """A question with a yes button and Cancel; Enter presses the chosen one, which is Cancel until Tab or ← →
    chooses the other."""

    def __init__(self, question, yes):
        self.question, self.yes, self.choice = question, yes, "no"

    def handle(self, key):
        if key.name in ("tab", "backtab", "left", "right"):
            self.choice = "yes" if self.choice == "no" else "no"
        elif key.name == "enter":
            return self.choice == "yes"
        elif key.name == "char" and key.char in ("y", "Y"):
            return True
        elif key.name == "esc" or (key.name == "char" and key.char in ("n", "N")):
            return False
        return None

    def draw(self, canvas, y, x, cells):
        words, row = self.question.split(), 0
        line = ""
        for word in words:
            if line and width(line) + 1 + width(word) > cells - 2:
                canvas.put(y + row, x + 1, line, PLAIN)
                row, line = row + 1, word
            else:
                line = f"{line} {word}".strip()
        canvas.put(y + row, x + 1, truncate(line, cells - 2), PLAIN)
        row += 2
        col = x + 1
        for name, label in (("yes", self.yes), ("no", "Cancel")):
            chosen = self.choice == name
            style = Style(fg="button_text", bg="button", bold=True) if chosen else Style(bg="input")
            text = f" {label} "
            end = canvas.put(y + row, col, text, style)
            canvas.region(y + row, col, end, f"confirm:{name}")
            col = end + 1
        return row + 1
