"""The sidebar's Changes view: the repository row (VS Code's Repositories), the message with ✦, Commit and its modes,
the issue the commit fixes, Staged Changes, Changes and the Graph. A staged file named like a secret is committed only
after a question. The view only asks: every git command comes back as an Action for the app."""
import os
from dataclasses import dataclass

import widgets
from commit_message import secret_looking
from git import Change, Commit, taken
from icons import GIT_LETTER, glyphs, icon
from screen import GIT_ROLE, PLAIN, Canvas, Style, after, centered, truncate, width
from vt import Key, Mouse
from widgets import Action, Confirm, ListView, Menu, TextInput

MODES = {"commit": "Commit", "push": "Commit & Push", "sync": "Commit & Sync"}
REMOTE = {"Pull": "pull", "Push": "push"}       # the repository row's ⋯, with Open on GitHub for a repository there
MESSAGE_ROWS = 7              # the message field grows with its text up to this many rows (odd: see draw())
SIDE = 5                      # the cells of the AI's button beside the message, and of the mode's under it
BRANCH_LEAST = 4              # the cells the repository row's branch needs at least: ⎇, a letter and …


@dataclass(frozen=True)
class Section:
    kind: str                 # staged, changes or graph
    title: str
    count: int = None


@dataclass(frozen=True)
class Entry:
    change: Change
    staged: bool


@dataclass(frozen=True)
class Gap:
    """The empty row above a section that follows another: drawn blank, never chosen."""


GAP = Gap()


class Scm:
    def __init__(self, mode="commit", icons=True, folded=()):
        self.mode = mode if mode in MODES else "commit"
        self.icons = icons
        self.field = TextInput(multiline=True, placeholder="Commit message")
        self.list = ListView()                       # the changes
        self.graph_list = ListView()                 # the Graph, at the view's bottom
        self.focus = "button"                          # message, button, list or graph
        self.folded = set(folded) & {"repositories", "staged", "changes", "graph"}   # the sections closed, kept
        self.repo = self.github = None            # the repository's folder and its name on GitHub, the app's
        self.selecting = False        # the left button went down in the message and is held: a drag selects
        self.working = self.notice = self.menu = self.confirm = self.then = None     # then: the Action of the yes
        self.writing = None           # while ✦ writes: who writes the message, its spinner's frame first
        self.menu_at = None           # the row the repository's ⋯ opened its menu under (None: the mode's)
        self.status, self.hover, self.canvas, self.top, self.height = None, None, None, 0, 1
        self.shown = None             # what the rows were built from: a mouse move must not rebuild 50 000 of them
        self.linked = None            # (number, title) of the issue the next commit fixes
        self.wanted = None            # where the version before this one was (kept()), once the rows are there

    @property
    def editing(self):
        """Whether the view holds the keys — the message, a menu or a question (the app's own keys wait)."""
        return self.focus == "message" or self.menu is not None or self.confirm is not None

    def set_message(self, text):
        self.field.clear()
        self.field.insert(text or "")
        self.notice = None

    def busy(self, text):
        """A line saying what runs (None: nothing); meanwhile ✦ asks for no second message."""
        self.working = text

    # --- what is shown

    def sync(self, status, graph):
        """The list's rows, built again only from a new status or graph or a section folded; the chosen one stays
        chosen when it is still there."""
        folded = frozenset(self.folded)
        if self.shown and self.shown[0] is status and self.shown[1] is graph and self.shown[2] == folded:
            return
        self.shown = (status, graph, folded)
        items = []
        if status.staged:
            items.append(Section("staged", "Staged changes", len(status.staged)))
            items += [] if "staged" in self.folded else [Entry(change, True) for change in status.staged]
        items.append(Section("changes", "Changes", len(status.changes)))
        items += [] if "changes" in self.folded else [Entry(change, False) for change in status.changes]
        items = [row for i, item in enumerate(items)
                 for row in ((GAP, item) if i and isinstance(item, Section) else (item,))]
        refill(self.list, items)
        self.off_the_gap(1)
        refill(self.graph_list, [Section("graph", "Graph")] + ([] if "graph" in self.folded else list(graph)))
        if self.wanted:
            for rows, name in ((self.list, "list"), (self.graph_list, "graph")):
                found = next((i for i, item in enumerate(rows.items) if key_of(item) == self.wanted.get(name)), None)
                if found is not None:
                    rows.index = found
                    rows.keep_visible()
            if self.wanted.get("focus") in ("message", "button", "list", "graph"):
                self.focus = self.wanted["focus"]
            self.wanted = None

    def kept(self):
        """Where the view is, for the next version: the focus, and the chosen row of the changes and of the Graph."""
        return {"focus": self.focus, "list": key_of(self.list.selected()), "graph": key_of(self.graph_list.selected())}

    def take(self, kept):
        self.wanted = kept if isinstance(kept, dict) else None

    def paths(self, item):
        if isinstance(item, Entry):
            return (item.change.path,)
        changes = self.status.staged if item.kind == "staged" else self.status.changes
        return tuple(change.path for change in changes)

    # --- drawing

    def draw(self, canvas, top, height, status, graph, roomy):
        """The view from row TOP, HEIGHT rows; its field and buttons tall in a ROOMY pane, chips in a low one."""
        self.canvas, self.top, self.height, self.status = canvas, top, height, status
        cells = canvas.width
        if status is None:
            return
        if status.error:
            line = "Not a git repository" if "not a git repository" in status.error.lower() else status.error
            canvas.put(top, 1, truncate(line, cells - 2), Style(fg="muted"))
            return
        self.sync(status, graph)
        below_repository = self.repository(canvas, top, status, roomy)
        top, height = below_repository, height - (below_repository - top)       # the rest of the view under it
        side = cells - SIDE - 1                           # the AI's and the mode's buttons, a cell in from the edge
        main = side - 2                                   # the message and the commit button: a cell of air before
        inner = main - 4                                  # the text, two cells in from the shape's ends
        rows = min(MESSAGE_ROWS, len(self.field.lines(inner))) if self.field.text else 1
        rows += 1 - rows % 2                              # an odd number: the star beside them has a middle row
        text_row, taken = canvas.control(top, 1, main, rows, "input", roomy)
        for y in range(top, top + taken):
            canvas.region(y, 1, 1 + main, "input")
        self.field.placeholder = self.writing or "Commit message"         # an empty field says who writes in it
        self.field.draw(canvas, text_row, 3, inner, rows, Style(bg="input"), focused=self.focus == "message")
        self.side(canvas, top, rows, roomy)
        below = top + taken + (0 if roomy else 1)        # the edges are the air between them in a roomy pane
        tall = self.button(canvas, below, roomy)
        y = below + tall - 1
        lines = []
        if self.linked:
            lines.append((f"Fixes #{self.linked[0]} {self.linked[1]}", "accent"))
        if self.writing and self.field.text:                  # the field holds a message: who writes says it here
            lines.append((self.writing, "muted"))
        if self.working or self.notice:
            lines.append((self.working or self.notice, "muted" if self.working else "deleted"))
        if status.branch is None:
            lines.append(("detached HEAD", "modified"))
        for line, role in lines:
            y += 1
            if self.linked and line.startswith(f"Fixes #{self.linked[0]} "):
                canvas.put(y, 1, truncate(line, cells - 5), Style(fg=role))
                canvas.put(y, cells - 2, "×", Style(fg="muted"))
                canvas.region(y, cells - 3, cells, "unlink")
                continue
            canvas.put(y, 1, truncate(line, cells - 2), Style(fg=role))
        first = y + (1 if roomy and not lines else 2)    # the button's lower edge, or an empty row, of air
        # the changes take what they need, the Graph the rest at the bottom, a third of the room at least
        room, history = top + height - first, self.graph_list.items
        least = len(history) if len(history) <= 1 else min(len(history), max(3, room // 3))
        above = min(len(self.list.items), max(1, room - least - 1))
        below = max(0, min(len(history), room - above - 1))
        parts = ((self.list, first, above, False), (self.graph_list, top + height - below, below, True))
        for rows, y0, shown, graph in parts:
            if shown and rows.height != shown:
                rows.resize(shown)
            for row in range(shown):
                index = rows.at(row)
                if index is None:
                    break
                self.row(canvas, y0 + row, index, graph)
        if self.menu:
            wide = min(cells, self.menu.width())
            self.menu.draw(canvas, below + tall if self.menu_at is None else self.menu_at, max(0, cells - 1 - wide),
                           wide)
        if self.confirm:
            self.draw_confirm(canvas)

    def repository(self, canvas, y, status, roomy):
        """On top, as VS Code's Repositories: its heading (its chevron folds it), then the repository's name, ⎇ its
        branch (* with changes), ↻ the sync (when it is behind or ahead) and ⋯ pull, push or its page on GitHub.
        Returns the row the message starts on: right under them in a ROOMY pane (its edge their air), else one below."""
        cells, marks = canvas.width, glyphs(self.icons)
        if not self.repo:
            return y
        folded = "repositories" in self.folded
        mark = widgets.TURNS.mark(self.icons, ("section", "repositories"), not folded)
        x = canvas.put(y, 1, mark + after(self.icons), Style(fg="muted"))
        canvas.put(y, x, "Repositories", Style(fg="text", bold=True))
        canvas.region(y, 0, cells, "repositories")
        air = 1 if roomy else 2
        if folded:
            return y + air
        y += 1
        end = cells - 2
        canvas.put(y, end, "⋯", Style(fg="muted"))
        canvas.region(y, end - 1, cells, "remote")
        counts = f" {status.behind}↓ {status.ahead}↑" if status.upstream and (status.behind or status.ahead) else ""
        sync = marks["refresh"] + counts
        end -= width(sync) + 2
        canvas.put(y, end, sync, Style(fg="accent" if self.working else "muted"))
        canvas.region(y, end - 1, end + width(sync) + 1, "sync")
        x = 2 + len(after(self.icons))                    # under the heading's name, as a change's row
        x = canvas.put(y, x, marks["repo"] + after(self.icons), Style(fg="muted"))
        name = os.path.basename(self.repo.rstrip(os.sep))
        room = end - 2 - (x + width(name) + 1)            # the branch's: what the name leaves before the sync
        if room >= BRANCH_LEAST:
            branch = truncate(f"⎇ {status.branch or 'detached'}{'*' if status.staged or status.changes else ''}", room)
            end -= width(branch) + 2
            canvas.put(y, end, branch, Style(fg="muted"))
        canvas.put(y, x, truncate(name, max(1, end - x - 1)), Style(fg="text"))
        return y + air

    def side(self, canvas, top, rows, roomy):
        """The AI's own button beside the message, as tall as it, its star in the middle."""
        x = canvas.width - SIDE - 1
        row, taken = canvas.control(top, x, SIDE, rows, "selection", roomy)
        for y in range(top, top + taken):
            canvas.region(y, x, x + SIDE, "suggest")
        canvas.put(row + (rows - 1) // 2, centered(x, SIDE), glyphs(self.icons)["ai"],
                   Style(fg="muted" if self.working or self.writing else "accent", bg="selection", bold=True))

    def button(self, canvas, y, roomy):
        """The commit button in the message's shape and width, its label in the middle; under the AI's button, the
        mode's own. Returns the rows they take."""
        cells, marks = canvas.width, glyphs(self.icons)
        side = cells - SIDE - 1
        main = side - 2
        row, taken = canvas.control(y, 1, main, 1, "button", roomy)
        canvas.control(y, side, SIDE, 1, "button", roomy)
        for r in range(y, y + taken):
            canvas.region(r, 1, 1 + main, "commit")
            canvas.region(r, side, side + SIDE, "mode")
        fill = Style(fg="button_text", bg="button", bold=True)
        label = truncate(f" {marks['check']} {MODES[self.mode]} ", main - 4)
        canvas.put(row, 1 + max(0, (main - width(label)) // 2), label, fill)
        canvas.put(row, centered(side, SIDE), marks["more"], fill)
        return taken

    def row(self, canvas, y, index, graph=False):
        """Row INDEX of the changes, or of the GRAPH."""
        rows, cells = self.graph_list if graph else self.list, canvas.width
        item = rows.items[index]
        if isinstance(item, Gap):
            return
        chosen = index == rows.index and self.focus == ("graph" if graph else "list")
        hovered = self.hover == (("graph", index) if graph else index)
        bg = "selection" if chosen else ("hover" if hovered else None)
        canvas.band(y, bg)
        canvas.region(y, 0, cells, ("graph" if graph else "row", index))
        if isinstance(item, Section):
            self.section(canvas, y, index, item, bg, hovered)
        elif isinstance(item, Entry):
            self.entry(canvas, y, index, item, bg, hovered)
        else:
            self.commit_row(canvas, y, item, bg)

    def tip(self, target):
        """A changed file's whole path in its repository, for the mouse resting on its row (as GitHub Desktop's)."""
        if isinstance(target, tuple) and target[0] == "row" and 0 <= target[1] < len(self.list.items):
            item = self.list.items[target[1]]
            return item.change.path if isinstance(item, Entry) else None
        return None

    def icons_at(self, canvas, y, end, index, kinds, bg):
        """The hover icons KINDS ending before column END; returns the first column they take."""
        x = end - 2 * len(kinds)
        for i, kind in enumerate(kinds):
            canvas.put(y, x + 2 * i, glyphs(self.icons)[kind], Style(fg="text", bg=bg))
            canvas.region(y, x + 2 * i, x + 2 * i + 2, (kind, index))
        return x

    def section(self, canvas, y, index, item, bg, hovered):
        cells = canvas.width
        mark = widgets.TURNS.mark(self.icons, ("section", item.kind), item.kind not in self.folded)
        x = canvas.put(y, 1, mark + after(self.icons), Style(fg="muted", bg=bg))
        end = cells - 1
        if item.count is not None:                       # the count on a chip
            count = str(item.count)
            end -= width(count) + 2
            canvas.chip(y, end, width(count) + 2, "badge")
            canvas.put(y, end + 1, count, Style(fg="badge_text", bg="badge"))
        kinds = {"staged": ("unstage",), "changes": ("discard", "stage")}.get(item.kind, ())
        if hovered and kinds and item.count:
            end = self.icons_at(canvas, y, end - 1, index, kinds, bg)
        canvas.put(y, x, truncate(item.title, end - x - 1), Style(fg="text", bg=bg, bold=True))

    def entry(self, canvas, y, index, item, bg, hovered):
        change, cells = item.change, canvas.width
        x = 2 + len(after(self.icons))                    # under the section's name
        folder, name = os.path.split(change.path.rstrip("/"))          # a nested repository is "inner/"
        if self.icons:
            x = canvas.put(y, x, icon(name) + after(True), Style(fg="muted", bg=bg))
        letter = cells - 3                                # under the last digit of its section's count
        canvas.put(y, letter, GIT_LETTER.get(change.code, change.code), Style(fg=GIT_ROLE[change.code], bg=bg))
        end = letter
        if hovered:
            kinds = ("diff", "unstage") if item.staged else ("diff", "discard", "stage")
            end = self.icons_at(canvas, y, end, index, kinds, bg) - 1
        x = canvas.put(y, x, truncate(name, end - x), Style(fg="text", bg=bg, strike=change.code == "D"))
        if folder and end - x - 1 > 1:
            canvas.put(y, x + 1, truncate(folder, end - x - 1), Style(fg="muted", bg=bg))

    def commit_row(self, canvas, y, commit, bg):
        cells = canvas.width
        x = canvas.put(y, 2 + len(after(self.icons)), "◉ " if commit.head else "○ ",   # in the files' column
                       Style(fg="accent" if commit.head else "muted", bg=bg))
        for part, role in ((commit.subject, "text"), (" ".join(commit.refs), "accent"), (commit.author, "muted")):
            room = cells - 1 - x
            if part and room > 1:
                x = canvas.put(y, x, truncate(part, room), Style(fg=role, bg=bg)) + 1

    def draw_confirm(self, canvas):
        cells = canvas.width
        rows = self.confirm.draw(Canvas(cells, self.height), 0, 0, cells)
        y = max(self.top + 1, self.top + self.height - rows - 1)
        for row in range(y, self.top + self.height):
            canvas.put(row, 0, " " * cells, PLAIN)
        canvas.put(y, 0, "─" * cells, Style(fg="muted"))
        self.confirm.draw(canvas, y + 1, 0, cells)

    # --- events

    def handle(self, event):
        if self.status is None or self.status.error:
            return None
        if isinstance(event, Mouse):
            return self.mouse(event)
        if not isinstance(event, Key):
            return None
        if self.confirm:
            return self.answer(self.confirm.handle(event))
        if self.menu:
            return self.choose(self.menu.handle(event))
        self.notice = None
        if event.name == "enter" and event.alt:
            return self.commit()
        if self.focus == "message":
            if event.name in ("esc", "tab"):
                self.focus = "button"
            elif not self.field.handle(event) and event.name == "down":
                self.focus = "button"
            return None
        return self.button_key(event) if self.focus == "button" else self.list_key(event)

    def off_the_gap(self, step):
        """A move that ends on the empty row above a section goes on to the section (a gap is never first or last)."""
        if self.focus != "graph" and isinstance(self.list.selected(), Gap):
            self.list.move(step)

    def button_key(self, event):
        name = event.name
        if name == "enter":
            return self.commit()
        if name == "down" and self.list.items:
            self.focus = "list"
        elif name == "up":
            self.focus = "message"
        elif name == "right":
            self.menu, self.menu_at = Menu(MODES.values()), None
        else:
            return self.common_key(event)
        return None

    def list_key(self, event):
        """The changes' keys, or the Graph's: up from the top of the Graph and down from the last change cross over."""
        name, graph = event.name, self.focus == "graph"
        rows = self.graph_list if graph else self.list
        item = rows.selected()
        if name == "esc" or (name == "up" and rows.index == 0 and not graph):
            self.focus = "button"
        elif name == "up" and rows.index == 0:
            self.focus, self.list.index = "list", len(self.list.items) - 1
            self.list.keep_visible()
        elif name == "down" and rows.index == len(rows.items) - 1 and not graph and self.graph_list.items:
            self.focus, self.graph_list.index = "graph", 0
            self.graph_list.keep_visible()
        elif name in ("up", "down"):
            rows.move(1 if name == "down" else -1)
            self.off_the_gap(1 if name == "down" else -1)
        elif name in ("pageup", "pagedown"):
            rows.page(1 if name == "pagedown" else -1)
            self.off_the_gap(1 if name == "pagedown" else -1)
        elif name in ("home", "end"):
            rows.move(len(rows.items) * (1 if name == "end" else -1))
        elif name == "enter":
            return self.activate(item)
        elif name == "char" and event.char == " ":
            return self.preview(item)
        elif name == "char" and event.char == "d":
            self.ask_discard(item)
        else:
            return self.common_key(event)
        return None

    def common_key(self, event):
        """The keys of the button and the list alike: A, S, c, and typing, which goes to the message."""
        if event.name == "char" and not (event.ctrl or event.alt):
            if event.char == "A":
                return self.suggest()
            if event.char == "S":
                return Action("sync")
            self.focus = "message"
            if event.char != "c":
                self.field.handle(event)
        elif event.name == "paste":
            self.focus = "message"
            self.field.handle(event)
        return None

    def mouse(self, event):
        target = self.canvas.hit(event.x, event.y) if self.canvas else None
        if event.kind == "move" and self.selecting and event.button == 0:
            self.field.drag(event.x, event.y)
        elif event.kind == "move":
            self.hover = (target if target[0] == "graph" else target[1]) if isinstance(target, tuple) else None
        elif event.kind in ("wheel_up", "wheel_down"):     # the message under the mouse or being selected, else a list
            step = 3 if event.kind == "wheel_down" else -3
            if target == "input" or self.selecting:
                self.field.scroll(step)
            else:
                (self.graph_list if isinstance(target, tuple) and target[0] == "graph" else self.list).scroll(step)
        elif event.kind == "press" and event.button == 0:
            return self.press(target, event)
        elif event.kind == "release":
            self.selecting = False
        return None

    def press(self, target, event):
        if self.confirm:
            return self.answer(target == "confirm:yes") if target in ("confirm:yes", "confirm:no") else None
        if self.menu:
            if str(target).startswith("menu:"):
                return self.choose(self.menu.choices[int(target[5:])])
            self.menu = None
            return None
        self.notice = None
        if target == "input":                             # the cursor where it is pressed, a drag selecting on
            self.focus, self.selecting = "message", True
            self.field.press(event.x, event.y)
        elif target == "suggest":
            return self.suggest()
        elif target == "commit":
            self.focus = "button"
            return self.commit()
        elif target == "mode":
            self.menu, self.menu_at = Menu(MODES.values()), None
        elif target == "remote":
            self.menu = Menu([*REMOTE, *(["Open on GitHub"] if self.github else [])])
            self.menu_at = event.y + 1
        elif target == "repositories":
            self.folded.symmetric_difference_update({"repositories"})
            widgets.TURNS.turn(("section", "repositories"))
            return Action("remember_folded", (sorted(self.folded),))
        elif target == "unlink":
            return Action("unlink", ())
        elif isinstance(target, tuple) and target[0] == "graph":
            self.focus, self.graph_list.index = "graph", target[1]
            item = self.graph_list.items[target[1]]
            return self.activate(item) if isinstance(item, Section) else self.preview(item)
        elif isinstance(target, tuple):
            kind, index = target
            item = self.list.items[index]
            if kind == "row":
                self.focus, self.list.index = "list", index
                return self.preview(item) if not isinstance(item, Section) else self.activate(item)
            if kind in ("stage", "unstage"):
                return Action(kind, (self.paths(item),))
            if kind == "discard":
                self.ask_discard(item)
            elif kind == "diff":
                return self.preview(item)
        return None

    # --- what the keys and the mouse do

    def commit(self):
        message = self.field.text.strip()
        if not message:
            self.notice = "The message is empty"
            return None
        # with nothing staged, every change shown: exactly those, so one come since is never committed unasked
        paths = () if self.status.staged else tuple(taken(self.status.changes))
        action = Action("commit", (message, self.mode, paths))
        going = [change.path for change in self.status.staged] or paths
        names = [os.path.basename(path) for path in going if secret_looking(path)]
        if not names:
            return action
        shown = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
        question = (f"{shown} looks like a secret. Commit it anyway?" if len(names) == 1 else
                    f"{shown} look like secrets. Commit them anyway?")
        self.confirm, self.then = Confirm(question, "Commit"), action
        return None

    def suggest(self):
        return None if self.working or self.writing else Action("suggest")

    def close_menu(self):
        """Its menu closed, as a click outside it closes it: the pane lost the keys, or its header was clicked."""
        self.menu = None

    def choose(self, label):
        if label is None:
            return None
        self.menu = None
        if label in REMOTE:
            return Action("sync", (REMOTE[label],))
        if label == "Open on GitHub":
            return Action("repo_web", ())
        mode = next((mode for mode, text in MODES.items() if text == label), None)
        if mode is None:
            return None
        self.mode = mode
        return Action("remember_mode", (mode,))

    def activate(self, item):
        if isinstance(item, Section):
            self.folded.symmetric_difference_update({item.kind})
            widgets.TURNS.turn(("section", item.kind))
            return Action("remember_folded", (sorted(self.folded),))
        if isinstance(item, Entry):
            return Action("unstage" if item.staged else "stage", (self.paths(item),))
        return self.preview(item)

    def preview(self, item):
        if isinstance(item, Entry):
            return Action("preview_diff", (item.change.path, item.staged))
        if isinstance(item, Commit):
            return Action("preview_commit", (item.hash,))
        return None

    def ask_discard(self, item):
        if isinstance(item, Entry) and not item.staged:
            name = os.path.basename(item.change.path.rstrip("/"))
            if item.change.code == "?":
                self.confirm = Confirm(f"Move {name} to the Trash?", "Move")
            else:
                self.confirm = Confirm(f"Discard changes in {name}? This cannot be undone.", "Discard")
        elif isinstance(item, Section) and item.kind == "changes" and item.count:
            self.confirm = Confirm(f"Discard all {item.count} changes? This cannot be undone.", "Discard")
        else:
            return
        self.then = Action("discard", (self.paths(item),))

    def answer(self, yes):
        if yes is None:
            return None
        then, self.confirm, self.then = self.then, None, None
        return then if yes else None


def refill(rows, items):
    """ROWS (a ListView) with ITEMS, the chosen one still chosen when it is still there."""
    if items != rows.items:
        chosen = rows.selected()
        rows.set(items)
        if chosen in items:
            rows.index = items.index(chosen)
            rows.keep_visible()


def key_of(item):
    """ITEM as the next version finds it again: a file by its path and side, a section by its kind, a commit by hash."""
    if isinstance(item, Entry):
        return ["entry", item.change.path, item.staged]
    if isinstance(item, Section):
        return ["section", item.kind]
    if isinstance(item, Commit):
        return ["commit", item.hash]
    return None
