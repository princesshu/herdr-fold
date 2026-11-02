"""The sidebar's controls: a list that keeps its selection in view, a text field (one line, or several for the commit
message), a drop-down menu and a confirmation. Plus Action, what a view asks the app to do: the views stay free of
side effects, so they are tested without a terminal."""
from dataclasses import dataclass

from screen import PLAIN, Style, char_width, truncate, width


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
        self.top = 0                  # the first row shown: a text taller than the field shows from here

    def clear(self):
        self.text, self.cursor, self.top = "", 0, 0

    def insert(self, text):
        self.text = self.text[:self.cursor] + text + self.text[self.cursor:]
        self.cursor += len(text)

    def line_start(self):
        return self.text.rfind("\n", 0, self.cursor) + 1

    def line_end(self):
        end = self.text.find("\n", self.cursor)
        return len(self.text) if end < 0 else end

    def handle(self, key):
        """Edit by KEY; False if the key is not the field's (the view handles it)."""
        name = key.name
        if name == "char" and key.ctrl:
            if key.char == "a":
                self.cursor = self.line_start()
            elif key.char == "e":
                self.cursor = self.line_end()
            elif key.char == "u":
                start = self.line_start()
                self.text, self.cursor = self.text[:start] + self.text[self.cursor:], start
            else:
                return False
        elif name == "char" and not key.alt:
            self.insert(key.char)
        elif name == "paste":
            self.insert(key.char if self.multiline else key.char.replace("\r\n", " ").replace("\n", " "))
        elif name == "enter" and self.multiline:
            self.insert("\n")
        elif name == "backspace" and self.cursor:
            self.text, self.cursor = self.text[:self.cursor - 1] + self.text[self.cursor:], self.cursor - 1
        elif name == "delete" and self.cursor < len(self.text):
            self.text = self.text[:self.cursor] + self.text[self.cursor + 1:]
        elif name == "left":
            self.cursor = max(0, self.cursor - 1)
        elif name == "right":
            self.cursor = min(len(self.text), self.cursor + 1)
        elif name == "home":
            self.cursor = self.line_start()
        elif name == "end":
            self.cursor = self.line_end()
        elif name in ("up", "down") and self.multiline:
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
        elif name not in ("backspace", "delete"):
            return False
        return True

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
        """Paint the field (or its placeholder) in HEIGHT rows; when FOCUSED, its cursor's place goes to the canvas, for
        the terminal's own cursor. Returns the rows used."""
        rows = self.lines(cells) if self.text else [self.placeholder]
        row, column = self.cursor_cell(cells)
        if focused:                   # the rows at the cursor show, wherever it is; otherwise they stay where they were
            self.top = min(self.top, row) if row < self.top + height else row - height + 1
        self.top = max(0, min(self.top, len(rows) - height))
        shown = rows[self.top:self.top + height]
        for i in range(height):
            canvas.put(y + i, x, " " * cells, style)
        for i, text in enumerate(shown):
            text_style = style if self.text else Style(fg="muted", bg=style.bg)
            canvas.put(y + i, x, truncate(text.rstrip(" "), cells), text_style)   # the break's spaces lie past the edge
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
