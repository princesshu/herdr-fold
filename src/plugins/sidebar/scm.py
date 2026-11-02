"""The sidebar's Changes view: the commit message with ✦, the Commit button and its mode menu, the issue the commit
fixes, the repositories below a workspace that is none itself, Staged Changes, Changes and the Graph. A staged file
named like a secret's is committed only after a question. Every git command comes back as an Action for the app."""
import os
from dataclasses import dataclass

from commit_message import secret_looking
from git import Change, Commit
from screen import GIT_LETTER, GIT_ROLE, PLAIN, Canvas, Style, after, centered, glyphs, icon, truncate, width
from vt import Key, Mouse
from widgets import Action, Confirm, ListView, Menu, TextInput

MODES = {"commit": "Commit", "push": "Commit & Push", "sync": "Commit & Sync"}
MESSAGE_ROWS = 6              # the message field grows with its text up to this many rows
SIDE = 5                      # the cells of the AI's button beside the message, and of the mode's under it


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
class Repo:
    """A repository below a workspace that is none itself: the chosen one's changes show under the list."""
    path: str
    name: str
    folder: str               # where it is, from the workspace's folder
    branch: str
    sync: str                 # ↻ 1↓ 2↑, or empty without an upstream
    count: int                # its changes, staged or not
    active: bool


@dataclass(frozen=True)
class Gap:
    """The empty row above a section that follows another: drawn blank, never chosen."""


GAP = Gap()


class Scm:
    def __init__(self, mode="commit", icons=True):
        self.mode = mode if mode in MODES else "commit"
        self.icons = icons
        self.field = TextInput(multiline=True, placeholder="Commit message")
        self.list = ListView(1)
        self.focus, self.folded = "button", set()
        self.keyed = False            # the keys moved last (not the mouse): the button then shows that it has the focus
        self.working = self.notice = self.menu = self.confirm = self.then = None     # then: the Action of the yes
        self.status, self.hover, self.canvas, self.top, self.height = None, None, None, 0, 1
        self.shown = None             # what the rows were built from: a mouse move must not rebuild 50 000 of them
        self.linked = None            # (number, title) of the issue the next commit fixes

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

    def sync(self, status, graph, repos=()):
        """The list's rows, built again only from a new status, graph or REPOS or a section folded; the chosen one
        stays chosen when it is still there."""
        folded = frozenset(self.folded)
        if self.shown and self.shown[0] is status and self.shown[1] is graph and self.shown[2:] == (folded, repos):
            return
        self.shown = (status, graph, folded, repos)
        items = []
        if repos:
            items.append(Section("repos", "Repositories", len(repos)))
            items += [] if "repos" in self.folded else list(repos)
        if status.staged:
            items.append(Section("staged", "Staged changes", len(status.staged)))
            items += [] if "staged" in self.folded else [Entry(change, True) for change in status.staged]
        items.append(Section("changes", "Changes", len(status.changes)))
        items += [] if "changes" in self.folded else [Entry(change, False) for change in status.changes]
        items.append(Section("graph", "Graph"))
        items += [] if "graph" in self.folded else list(graph)
        items = [row for i, item in enumerate(items)
                 for row in ((GAP, item) if i and isinstance(item, Section) else (item,))]
        if items != self.list.items:
            chosen = self.list.selected()
            self.list.set(items)
            if chosen in items:
                self.list.index = items.index(chosen)
                self.list.keep_visible()
            self.off_the_gap(1)

    def paths(self, item):
        if isinstance(item, Entry):
            return (item.change.path,)
        changes = self.status.staged if item.kind == "staged" else self.status.changes
        return tuple(change.path for change in changes)

    # --- drawing

    def draw(self, canvas, top, height, status, graph, roomy, repos=()):
        """The view from row TOP, HEIGHT rows, REPOS on top of it; its field and buttons tall in a ROOMY pane, chips in
        a low one."""
        self.canvas, self.top, self.height, self.status = canvas, top, height, status
        cells = canvas.width
        if status is None:
            return
        if status.error:
            line = "Not a git repository" if "not a git repository" in status.error.lower() else status.error
            canvas.put(top, 1, truncate(line, cells - 2), Style(fg="muted"))
            return
        self.sync(status, graph, repos)
        side = cells - SIDE - 1                           # the AI's and the mode's buttons, a cell in from the edge
        main = side - 2                                   # the message and the commit button: a cell of air before
        inner = main - 4                                  # the text, two cells in from the shape's ends
        rows = min(MESSAGE_ROWS, len(self.field.lines(inner))) if self.field.text else 1
        text_row, taken = canvas.control(top, 1, main, rows, "input", roomy)
        for y in range(top, top + taken):
            canvas.region(y, 1, 1 + main, "input")
        self.field.draw(canvas, text_row, 3, inner, rows, Style(bg="input"), focused=self.focus == "message")
        self.side(canvas, top, rows, roomy)
        below = top + taken + (0 if roomy else 1)        # the edges are the air between them in a roomy pane
        tall = self.button(canvas, below, roomy)
        y = below + tall - 1
        lines = []
        if self.linked:
            lines.append((f"Fixes #{self.linked[0]} {self.linked[1]}", "accent"))
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
        if self.list.height != top + height - first:
            self.list.resize(top + height - first)
        for row in range(self.list.height):
            index = self.list.at(row)
            if index is None:
                break
            self.row(canvas, first + row, index)
        if self.menu:
            wide = min(cells, self.menu.width())
            self.menu.draw(canvas, below + tall, max(0, cells - 1 - wide), wide)
        if self.confirm:
            self.draw_confirm(canvas)

    def side(self, canvas, top, rows, roomy):
        """The AI's own button beside the message, as tall as it, its star in the middle."""
        x = canvas.width - SIDE - 1
        row, taken = canvas.control(top, x, SIDE, rows, "selection", roomy)
        for y in range(top, top + taken):
            canvas.region(y, x, x + SIDE, "suggest")
        canvas.put(row + (rows - 1) // 2, centered(x, SIDE), glyphs(self.icons)["ai"],
                   Style(fg="muted" if self.working else "accent", bg="selection", bold=True))

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
        focused = self.focus == "button" and self.keyed    # the keys brought it here: the label lit the other way
        canvas.put(row, 1 + max(0, (main - width(label)) // 2), label,
                   Style(fg="button", bg="button_text", bold=True) if focused else fill)
        canvas.put(row, centered(side, SIDE), marks["more"], fill)
        return taken

    def row(self, canvas, y, index):
        item, cells = self.list.items[index], canvas.width
        if isinstance(item, Gap):
            return
        chosen = index == self.list.index and self.focus == "list"
        hovered = index == self.hover
        bg = "selection" if chosen else ("hover" if hovered else None)
        canvas.band(y, bg)
        canvas.region(y, 0, cells, ("row", index))
        if isinstance(item, Section):
            self.section(canvas, y, index, item, bg, hovered)
        elif isinstance(item, Entry):
            self.entry(canvas, y, index, item, bg, hovered)
        elif isinstance(item, Repo):
            self.repo_row(canvas, y, item, bg)
        else:
            self.commit_row(canvas, y, item, bg)

    def icons_at(self, canvas, y, end, index, kinds, bg):
        """The hover icons KINDS ending before column END; returns the first column they take."""
        x = end - 2 * len(kinds)
        for i, kind in enumerate(kinds):
            canvas.put(y, x + 2 * i, glyphs(self.icons)[kind], Style(fg="text", bg=bg))
            canvas.region(y, x + 2 * i, x + 2 * i + 2, (kind, index))
        return x

    def section(self, canvas, y, index, item, bg, hovered):
        cells = canvas.width
        mark = glyphs(self.icons)["closed" if item.kind in self.folded else "open"]
        x = canvas.put(y, 1, mark + after(self.icons), Style(fg="muted", bg=bg))
        end = cells - 1
        if item.count is not None:
            end = self.count_chip(canvas, y, end, item.count)
        kinds = {"staged": ("unstage",), "changes": ("discard", "stage")}.get(item.kind, ())
        if hovered and kinds and item.count:
            end = self.icons_at(canvas, y, end - 1, index, kinds, bg)
        canvas.put(y, x, truncate(item.title, end - x - 1), Style(fg="text", bg=bg, bold=True))

    def count_chip(self, canvas, y, end, count):
        """COUNT on a chip ending before column END; returns the column the chip starts at."""
        text = str(count)
        end -= width(text) + 2
        canvas.chip(y, end, width(text) + 2, "badge")
        canvas.put(y, end + 1, text, Style(fg="badge_text", bg="badge"))
        return end

    def entry(self, canvas, y, index, item, bg, hovered):
        change, cells = item.change, canvas.width
        x = 2 + len(after(self.icons))                    # under the section's name
        folder, name = os.path.split(change.path.rstrip("/"))          # a nested repository is "inner/"
        if self.icons:
            x = canvas.put(y, x, icon(name) + after(True), Style(fg="muted", bg=bg))
        canvas.put(y, cells - 2, GIT_LETTER.get(change.code, change.code), Style(fg=GIT_ROLE[change.code], bg=bg))
        end = cells - 3
        if hovered:
            kinds = ("diff", "unstage") if item.staged else ("diff", "discard", "stage")
            end = self.icons_at(canvas, y, end, index, kinds, bg) - 1
        x = canvas.put(y, x, truncate(name, end - x), Style(fg="text", bg=bg, strike=change.code == "D"))
        detail = "tracked, but ignored" if change.ignored else folder
        if detail and end - x - 1 > 1:
            canvas.put(y, x + 1, truncate(detail, end - x - 1), Style(fg="muted", bg=bg))

    def repo_row(self, canvas, y, repo, bg):
        """The chosen one marked and bold, then its branch and sync, its changes on a chip; where it is, dim."""
        end = self.count_chip(canvas, y, canvas.width - 1, repo.count) if repo.count else canvas.width - 1
        x = canvas.put(y, 2 + len(after(self.icons)), "● " if repo.active else "○ ",
                       Style(fg="accent" if repo.active else "muted", bg=bg))
        parts = ((repo.name, "text", repo.active), (f"{repo.branch} {repo.sync}".strip(), "accent", False),
                 (repo.folder, "muted", False))
        for part, role, bold in parts:
            room = end - 1 - x
            if part and room > 1:
                x = canvas.put(y, x, truncate(part, room), Style(fg=role, bg=bg, bold=bold)) + 1

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
            self.keyed = self.keyed and event.kind not in ("press", "release")
            return self.mouse(event)
        if not isinstance(event, Key):
            return None
        self.keyed = True
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
        if isinstance(self.list.selected(), Gap):
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
            self.menu = Menu(MODES.values())
        else:
            return self.common_key(event)
        return None

    def list_key(self, event):
        name, item = event.name, self.list.selected()
        if (name == "up" and self.list.index == 0) or name == "esc":
            self.focus = "button"
        elif name in ("up", "down"):
            self.list.move(1 if name == "down" else -1)
            self.off_the_gap(1 if name == "down" else -1)
        elif name in ("pageup", "pagedown"):
            self.list.page(1 if name == "pagedown" else -1)
            self.off_the_gap(1 if name == "pagedown" else -1)
        elif name in ("home", "end"):
            self.list.move(len(self.list.items) * (1 if name == "end" else -1))
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
        if event.kind == "move":
            self.hover = target[1] if isinstance(target, tuple) else None
        elif event.kind in ("wheel_up", "wheel_down"):
            self.list.scroll(3 if event.kind == "wheel_down" else -3)
        elif event.kind == "press" and event.button == 0:
            return self.press(target)
        return None

    def press(self, target):
        if self.confirm:
            return self.answer(target == "confirm:yes") if target in ("confirm:yes", "confirm:no") else None
        if self.menu:
            if str(target).startswith("menu:"):
                return self.choose(list(MODES.values())[int(target[5:])])
            self.menu = None
            return None
        self.notice = None
        if target == "input":
            self.focus = "message"
        elif target == "suggest":
            return self.suggest()
        elif target == "commit":
            self.focus = "button"
            return self.commit()
        elif target == "mode":
            self.menu = Menu(MODES.values())
        elif target == "unlink":
            return Action("unlink", ())
        elif isinstance(target, tuple):
            kind, index = target
            item = self.list.items[index]
            if kind == "row":
                self.focus, self.list.index = "list", index
                return self.activate(item) if isinstance(item, (Section, Repo)) else self.preview(item)
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
        action = Action("commit", (message, self.mode))
        names = [os.path.basename(change.path) for change in self.status.staged if secret_looking(change.path)]
        if not names:
            return action
        shown = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
        question = (f"{shown} looks like a secret. Commit it anyway?" if len(names) == 1 else
                    f"{shown} look like secrets. Commit them anyway?")
        self.confirm, self.then = Confirm(question, "Commit"), action
        return None

    def suggest(self):
        return None if self.working else Action("suggest")

    def close_menu(self):
        """Its menu closed, as a click outside it closes it: the pane lost the keys, or its header was clicked."""
        self.menu = None

    def choose(self, label):
        if label is None:
            return None
        self.menu = None
        mode = next((mode for mode, text in MODES.items() if text == label), None)
        if mode is None:
            return None
        self.mode = mode
        return Action("remember_mode", (mode,))

    def activate(self, item):
        if isinstance(item, Section):
            self.folded.symmetric_difference_update({item.kind})
            return None
        if isinstance(item, Entry):
            return Action("unstage" if item.staged else "stage", (self.paths(item),))
        if isinstance(item, Repo):
            return Action("choose_repo", (item.path,))
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
