"""The sidebar's Search view: the place searched, the field with its Aa, ab and .* switches, and the hits by file. A
search is asked 150 ms after typing stops (at once for Enter, a switch or another place), an older answer dropped;
typing on narrows the hits at once. The view only asks: the search and the preview come back as Actions for the app."""
import os
import time
from dataclasses import dataclass

from screen import Style, after, char_width, glyphs, icon, truncate, width
from search import Hit, Query, Result, pattern
from vt import Key, Mouse
from widgets import Action, ListView, TextInput

DELAY = 0.15
SWITCHES = (("case", "Aa", "c"), ("word", "ab", "w"), ("regex", ".*", "r"))


@dataclass(frozen=True)
class File:
    path: str                 # from the root, with "/"
    count: int


def summary(result):
    """The line above the hits, and its color role."""
    if result.error:
        return result.error, "deleted"
    if not result.total:
        return "No results found", "muted"
    if len(result.hits) < result.total:
        return f"{len(result.hits)} of {result.total} results shown", "muted"
    hits, files = result.total, result.files
    return f"{hits} result{'s' * (hits != 1)} in {files} file{'s' * (files != 1)}", "muted"


class Find:
    def __init__(self, root, icons=True, clock=time.monotonic):
        self.root, self.icons, self.clock = root, icons, clock
        self.field = TextInput(placeholder="Search")
        self.switches = {name: False for name, _, _ in SWITCHES}
        self.list = ListView(1)
        self.focus, self.due, self.asked, self.running = "field", None, None, False
        self.result, self.folded, self.hover, self.canvas = None, set(), None, None
        self.answered = None                              # the question the result shown answers
        self.pointed = None                               # the switch under the mouse
        self.place = ""                                   # the folder or file searched, from the root ("": all of it)

    @property
    def editing(self):
        """Whether the keys are the field's (the app's own keys wait)."""
        return self.focus == "field"

    # --- asking and answers

    def query(self):
        return Query(self.field.text, **self.switches)

    def ask(self):
        self.due = None
        if not self.field.text:
            self.clear()
            return None
        self.asked, self.running = (self.query(), self.place), True
        return Action("search", self.asked)

    def within(self, place):
        """Search PLACE, a folder or a file (from the root, with "/"; "" for all of it) from now on: at once, when
        something is typed."""
        if place == self.place:
            return None
        self.place = place
        return self.ask() if self.field.text else None

    def clear(self):
        self.due, self.asked, self.running, self.result, self.answered = None, None, False, None, None
        self.rebuild()

    def reset(self):
        """The field's × or Esc: the text, the hits and the folder or file gone; the next search is everywhere."""
        self.field.clear()
        self.place = ""
        self.clear()

    def tick(self, now):
        """The search, once the typing has paused long enough."""
        return self.ask() if self.due is not None and now >= self.due else None

    def deadline(self):
        return self.due

    def show(self, result, query, place=""):
        if (query, place) != self.asked:
            return
        self.result, self.running, self.folded, self.answered = result, False, set(), self.asked
        self.list.index = self.list.top = 0
        self.rebuild()

    def narrow(self):
        """At once, as the text grows: the hits shown that the new text still matches, marked anew, while its search
        is on the way (an answer for the shorter text is no longer wanted). Only where every line it finds is among
        them: the last answer's text inside the new one, its switches and place the same, no whole word or regex."""
        query, self.asked = self.query(), None
        self.running = bool(query.text)
        last = self.answered
        if not (self.result and not self.result.error and last and last[1] == self.place and query.text
                and not (query.word or query.regex) and last[0] == Query(last[0].text, query.case)):
            return
        before, now = (last[0].text, query.text) if query.case else (last[0].text.lower(), query.text.lower())
        if before == now or before not in now:
            return
        regex, hits = pattern(query), []
        for hit in self.result.hits:
            spans = [m.span() for m in regex.finditer(hit.text) if m.end() > m.start()]
            if spans:
                hits.append(Hit(hit.path, hit.line_no, hit.text, spans))
        self.result = Result(hits, len(hits), len({hit.path for hit in hits}))
        self.answered = (query, self.place)
        self.rebuild()

    def rebuild(self):
        groups = {}
        for hit in self.result.hits if self.result else []:
            groups.setdefault(hit.path, []).append(hit)
        rows = []
        for path, hits in groups.items():
            rows.append(File(path, len(hits)))
            if path not in self.folded:
                rows.extend(hits)
        self.list.set(rows)

    # --- drawing

    def draw(self, canvas, top, height, roomy):
        """The view from row TOP, HEIGHT rows; its field tall in a ROOMY pane, a chip in a low one."""
        self.canvas, cells = canvas, canvas.width
        # a switch: its letters on a chip with half a cell of air each side, the chips side by side; its letters
        # alone, a cell apart, only where the field would keep fewer than 8 cells to type (under 27: herdr-fold's
        # sidebar is never so narrow)
        slot, gap = (4, 0) if cells >= 27 else (2, 1)
        bottom = top + height
        if self.place:                                    # the folder or file searched, above the field, in bold
            x = canvas.put(top, 1, "in ", Style(fg="muted"))
            canvas.put(top, x, truncate(self.place, cells - x - 1), Style(fg="text", bold=True))
            top += 1
        row, taken = canvas.control(top, 1, cells - 2, 1, "input", roomy)
        for y in range(top, top + taken):
            canvas.region(y, 1, cells - 1, "input")
        x = cells - 3 - slot * len(SWITCHES) - gap * (len(SWITCHES) - 1)
        clear = 2 if self.field.text or self.place else 0    # its ×: the text and the place gone
        self.field.draw(canvas, row, 3, max(1, x - 4 - clear), 1, Style(bg="input"), focused=self.editing)
        if clear:
            canvas.put(row, x - 3, "×", Style(fg="text" if self.pointed == "clear" else "muted", bg="input"))
            canvas.region(row, x - 3, x - 2, "clear")
        lit, pad = Style(fg="button_text", bg="button", bold=True), (slot - 2) // 2
        for name, label, _ in SWITCHES:
            on, pointed = self.switches[name], self.pointed == name
            if (on or pointed) and pad:                  # on: filled; under the mouse: lit; a chip where there is room
                canvas.chip(row, x, slot, "button" if on else "hover", under="input")   # half a cell of air each side
            off = Style(fg="text", bg="hover") if pointed else Style(fg="muted", bg="input")
            canvas.put(row, x + pad, label, lit if on else off)
            canvas.region(row, x, x + slot, name)
            x += slot + gap
        y = top + taken + (0 if roomy else 1)             # the field's lower edge, or a row, of air
        if self.running:
            canvas.put(y, 1, truncate("Searching…", cells - 2), Style(fg="muted"))
        elif self.result:
            line, role = summary(self.result)
            canvas.put(y, 1, truncate(line, cells - 2), Style(fg=role))
        first = y + 2                                     # an empty row, then the hits
        if self.list.height != bottom - first:
            self.list.resize(bottom - first)
        for row in range(self.list.height):
            index = self.list.at(row)
            if index is None:
                break
            self.row(canvas, first + row, index)

    def row(self, canvas, y, index):
        item, cells = self.list.items[index], canvas.width
        chosen = index == self.list.index and not self.editing
        bg = "selection" if chosen else ("hover" if index == self.hover else None)
        canvas.band(y, bg)
        canvas.region(y, 0, cells, ("row", index))
        indent = 1 + (1 + len(after(self.icons))) * (1 + self.icons)    # under the name: past the chevron and icon
        if isinstance(item, Hit):
            self.hit(canvas, y, indent, item, bg)
            return
        mark = glyphs(self.icons)["closed" if item.path in self.folded else "open"]
        x = canvas.put(y, 1, mark + after(self.icons), Style(fg="muted", bg=bg))
        folder, name = os.path.split(item.path)
        if self.icons:
            x = canvas.put(y, x, icon(name) + after(True), Style(fg="muted", bg=bg))
        count = str(item.count)
        end = cells - 3 - width(count)                    # the count on a chip at the right edge
        x = canvas.put(y, x, truncate(name, end - x - 1), Style(fg="text", bg=bg))
        if folder and end - x - 2 > 1:
            canvas.put(y, x + 1, truncate(folder, end - x - 2), Style(fg="muted", bg=bg))
        canvas.chip(y, end, width(count) + 2, "badge")
        canvas.put(y, end + 1, count, Style(fg="badge_text", bg="badge"))

    def hit(self, canvas, y, x, hit, bg):
        """The line, from its first non-blank character (from just before the match, when that is out of view), the
        match marked, cut with "…" at the edge."""
        text = hit.text.lstrip()
        shift = len(hit.text) - len(text)
        spans = [(start - shift, end - shift) for start, end in hit.spans if start >= shift]
        cells = canvas.width - 1 - x
        if spans and width(text[:spans[0][1]]) > cells:
            cut = max(0, spans[0][0] - cells // 3)
            text, spans = "…" + text[cut:], [(start - cut + 1, end - cut + 1) for start, end in spans if start >= cut]
        marked = {i for start, end in spans for i in range(start, end)}
        base, match = Style(fg="text", bg=bg), Style(fg="accent", bold=True, bg=bg)
        limit = x + cells - (width(text) > cells)               # a cut line keeps a cell for "…"
        for i, ch in enumerate(text):
            if x + char_width(ch) > limit:
                canvas.put(y, x, "…", base)
                return
            x = canvas.put(y, x, ch, match if i in marked else base)

    # --- events

    def close_menu(self):
        """Nothing to close: the search has no menu (the sidebar closes every view's when the pane loses the keys)."""

    def handle(self, event):
        if isinstance(event, Mouse):
            return self.mouse(event)
        if not isinstance(event, Key):
            return None
        if event.name == "char" and event.alt:
            switch = next((name for name, _, key in SWITCHES if key == event.char.lower()), None)
            return self.flip(switch) if switch else None
        return self.field_key(event) if self.editing else self.hits_key(event)

    def field_key(self, event):
        if event.name == "enter":
            return self.ask()
        if event.name == "tab" or (event.name == "down" and self.list.items):
            self.focus = "hits"
        elif event.name == "esc":
            self.reset()
        else:
            self.edit(event)
        return None

    def hits_key(self, event):
        name = event.name
        if (name == "up" and self.list.index == 0) or name in ("esc", "tab"):
            self.focus = "field"
        elif name in ("up", "down"):
            self.list.move(1 if name == "down" else -1)
        elif name in ("pageup", "pagedown"):
            self.list.page(1 if name == "pagedown" else -1)
        elif name in ("home", "end"):
            self.list.move(len(self.list.items) * (1 if name == "end" else -1))
        elif name == "enter":
            return self.activate(self.list.selected())
        elif name == "paste" or (name == "char" and not event.ctrl):
            self.focus = "field"
            self.edit(event)
        return None

    def edit(self, event):
        before = self.field.text
        self.field.handle(event)
        if self.field.text != before:
            self.due = self.clock() + DELAY
            self.narrow()

    def flip(self, switch):
        self.switches[switch] = not self.switches[switch]
        return self.ask()

    def activate(self, item):
        if isinstance(item, Hit):
            return Action("preview_file", (os.path.join(self.root, *item.path.split("/")), item.line_no))
        if isinstance(item, File):
            self.folded.symmetric_difference_update({item.path})
            self.rebuild()
        return None

    def mouse(self, event):
        target = self.canvas.hit(event.x, event.y) if self.canvas else None
        if event.kind == "move":
            self.hover = target[1] if isinstance(target, tuple) else None
            self.pointed = target if target in self.switches or target == "clear" else None
        elif event.kind in ("wheel_up", "wheel_down"):
            self.list.scroll(3 if event.kind == "wheel_down" else -3)
        elif event.kind == "press" and event.button == 0:
            if target == "input":
                self.focus = "field"
            elif target in self.switches:
                return self.flip(target)
            elif target == "clear":
                self.reset()
            elif isinstance(target, tuple):
                self.focus, self.list.index = "hits", target[1]
                return self.activate(self.list.selected())
        return None
