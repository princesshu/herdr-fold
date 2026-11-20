"""The Chats list the ✦ opens over the sidebar: herdr's workspaces in its Spaces list's order and typography, each a
group of its chats (the active tab's first, then the newest; none outside every workspace), under a filter; closed ones
marked to archive together, one deleted once asked. The view only asks: what it does comes back as an Action."""
import time
from dataclasses import dataclass

import widgets
from github import since
from screen import PAD, PLAIN, Canvas, Style, truncate, width
from vt import Key, Mouse
from widgets import Action, Confirm, ListView, Menu, Popup, TextInput

# herdr's states, as its Spaces list and AI Sessions mark and color them (unknown: its overlay0, the sidebar's
# "ignored"); a closed chat, which herdr has no state for, "·" in the faint guide color
STATE_ROLE = {"blocked": "deleted", "done": "done", "working": "modified", "idle": "added", "unknown": "ignored"}
STATE_MARK = {"blocked": "●", "done": "●", "working": "●", "idle": "○", "unknown": "·"}
MENU = ("Open", "Copy chat", "Rename")
DELETE = "Delete…"            # a closed chat's, asked first: its file to the system's Trash
ASKED = 40                    # characters of a chat's name in that question
BOX, MARKED = "□", "■"        # a closed chat's box, and a marked one's


def printable(text):
    """TEXT as it may show: a control character (a title's escape codes) as ?"""
    return "".join(ch if ch.isprintable() else "?" for ch in text)


def mark(state):
    """STATE's mark and its color, as herdr draws them; no state: a faint dot."""
    return (STATE_MARK[state], STATE_ROLE[state]) if state in STATE_MARK else ("·", "guide")


@dataclass
class Naming:
    item: object              # the chat renamed
    field: TextInput          # its new name, the old one to start with


class ChatList:
    editing = True            # the filter takes every character typed: the app's own keys (1-4, q) wait

    def __init__(self, now=time.time):
        self.now = now
        self.items, self.spaces, self.place, self.here = None, [], None, None      # items None: not read yet
        self.field = TextInput(placeholder="Filter")
        self.opened, self.closed = set(), set()                     # groups opened or closed by hand
        self.archived = set()                                       # "<agent>:<id>" of the chats off the list
        self.show_archived = False                                  # those in sight too (the app sets it)
        self.marked = set()                                         # "<agent>:<id>" of the ones marked to archive
        self.naming = None                                          # a chat's name being edited (Naming)
        self.confirm = self.doomed = None                           # Delete…'s question, and the chat it asks about
        self.gone = set()                                           # "<agent>:<id>" of those on their way to the Trash
        self.front = set()                  # the panes of each workspace's active tab, whose chats lead
        self.states = {}                    # each workspace's state, as herdr's Spaces list has it (the app sets it)
        self.icons = True                   # the sidebar's icons (its settings), or plain marks (the app sets it)
        self.list = ListView()
        self.hover = self.canvas = self.menu = None
        self.top = self.height = 0

    @property
    def typed(self):
        return self.field.text

    def set(self, items, spaces, place, here):
        """ITEMS (the chats), SPACES (the workspaces' names in the Spaces list's order), PLACE (a folder's
        workspace, or None), HERE (the workspace this pane is in). The first time, HERE is the one chosen."""
        first = self.items is None
        self.items, self.spaces, self.place, self.here = items, spaces, place, here
        self.gone &= {self.archive_key(item) for item in items}     # read without it: its file is in the Trash
        self.rebuild()
        if first:
            self.list.index = next((i for i, row in enumerate(self.list.items) if row[1] == here), 0)
            self.list.keep_visible()

    # --- the rows

    def group_of(self, item):
        return self.place(item.folder)

    def matches(self, item):
        """Whether ITEM matches what was typed: its name, its group, its folder, "archived" for an archived one."""
        typed = self.typed.lower()
        parts = (item.title, self.group_of(item) or "", item.folder,
                 "archived" if self.archive_key(item) in self.archived else "")
        return not typed or any(typed in part.lower() for part in parts)

    def is_open(self, name):
        if self.typed or name in self.opened:
            return True
        return name not in self.closed and name == self.here

    @staticmethod
    def archive_key(item):
        return f"{item.agent}:{item.id}"

    @staticmethod
    def markable(row):
        """Whether ROW is a chat that can be marked: a closed one (a running one is never archived)."""
        return bool(row) and row[0] == "item" and not row[1].state

    def mark_row(self, row, on=None):
        """ROW's chat marked (ON), unmarked, or turned over (None); a running one or a group as it is."""
        if self.markable(row):
            key = self.archive_key(row[1])
            if on is None:
                on = key not in self.marked
            (self.marked.add if on else self.marked.discard)(key)

    def bulk(self):
        """The right click's menu on a marked row, while more than one is marked in sight: {choice: (action, the marked
        ones in the list's order)}, to archive the others and to unarchive the archived ones. One running again since it
        was marked is left out."""
        marked = [row[1] for row in self.list.items if self.markable(row) and self.archive_key(row[1]) in self.marked]
        if len(marked) < 2:
            return {}
        choices = {}
        for action, back in (("archive", False), ("unarchive", True)):
            items = [item for item in marked if (self.archive_key(item) in self.archived) == back]
            if items:
                noun = "chat" if len(items) == 1 else "chats"
                choices[f"{action.capitalize()} {len(items)} {noun}"] = (action, items)
        return choices

    def members(self):
        """{workspace: its chats that match what was typed, the one in its active tab first, then the newest},
        in the Spaces list's order; an archived one only while shown or something is typed."""
        groups = {name: [] for name in self.spaces}
        for item in self.items or ():
            if self.archive_key(item) in self.gone:
                continue
            if self.archive_key(item) in self.archived and not (self.typed or self.show_archived):
                continue
            if self.group_of(item) in groups and self.matches(item):
                groups[self.group_of(item)].append(item)
        return {name: sorted(found, key=lambda item: (item.pane not in self.front, -item.time))
                for name, found in groups.items()}

    def rows(self):
        """("group", name, its chats, open) and ("item", chat, last in its group) rows, in the order
        shown: every workspace, one that has nothing typed matches left out."""
        rows = []
        for name, found in self.members().items():
            if self.typed and not found:
                continue
            rows.append(("group", name, found, self.is_open(name)))
            if self.is_open(name):
                rows += [("item", item, n == len(found) - 1) for n, item in enumerate(found)]
        return rows

    def rebuild(self):
        """The rows again, the chosen one kept chosen when it is still there."""
        chosen = self.key(self.list.selected())
        self.list.set(self.rows())
        keys = [self.key(row) for row in self.list.items]
        if chosen in keys:
            self.list.index = keys.index(chosen)
            self.list.keep_visible()

    @staticmethod
    def key(row):
        if row is None:
            return None
        return ("group", row[1]) if row[0] == "group" else ("item", row[1].agent, row[1].id)

    def toggle(self, name):
        widgets.TURNS.turn(("space", name))
        if self.is_open(name):
            self.closed.add(name)
            self.opened.discard(name)
        else:
            self.opened.add(name)
            self.closed.discard(name)
        self.rebuild()

    # --- drawing

    def draw(self, canvas, top, height, roomy):
        """The view from row TOP, HEIGHT rows: the filter, tall in a ROOMY slice as the dock's other fields are, a
        line when there is something to say, the rows."""
        self.canvas, self.top, self.height, cells = canvas, top, height, canvas.width
        for y in range(top, top + height):
            canvas.backdrop(y, 0, cells, "blank")                   # its own menu, under everything else
        field = cells - 2
        row, taken = canvas.control(top, 1, field, 1, "input", roomy)
        for y in range(top, top + taken):
            canvas.region(y, 1, 1 + field, "input")
        self.field.draw(canvas, row, 2, field - 2, 1, Style(bg="input"), focused=True)
        y = top + taken + (0 if roomy else 1)
        line = self.line()
        if line:
            canvas.put(y, 1, truncate(line, cells - 2), Style(fg="muted"))
            y += 2
        rows = max(1, top + height - y)
        if self.list.height != rows:
            self.list.resize(rows)
        for row in range(self.list.height):
            index = self.list.at(row)
            if index is None:
                break
            self.draw_row(canvas, y + row, index)
        if self.menu:
            self.draw_menu(canvas)
        if self.confirm:
            self.draw_confirm(canvas)

    def space_mark(self, name):
        """Workspace NAME's mark and its color, as herdr's Spaces list draws them."""
        return mark(self.states.get(name) or "unknown")

    def line(self):
        if self.items is None:
            return "Loading chats…"
        if self.list.items:
            return None
        return "No chat matches" if self.typed else "No chats"

    def draw_row(self, canvas, y, index):
        """A workspace as herdr's Spaces list has it: its mark, its name (the current one's bold), and at the right
        edge how many it holds and its fold chevron; a chat on herdr's tree lines: its mark, its name (a closed
        one's faint), the agent (fainter still) and how long ago."""
        row, cells = self.list.items[index], canvas.width
        bg = "selection" if index == self.list.index else ("hover" if index == self.hover else None)
        if bg:
            canvas.band(y, bg)
        canvas.region(y, 0, cells, ("row", index))
        if row[0] == "group":
            _, name, found, opened = row
            count = str(len(found))
            canvas.put(y, cells - 2, widgets.TURNS.mark(self.icons, ("space", name), opened), Style(fg="accent", bg=bg))
            canvas.put(y, cells - 3 - width(count), count, Style(fg="muted", bg=bg))
            shown, role = self.space_mark(name)
            canvas.put(y, 1, shown, Style(fg=role, bg=bg))
            here = name == self.here
            canvas.put(y, 3, truncate(printable(name), max(1, cells - 7 - width(count))),
                       Style(fg="text" if here else "subtext", bg=bg, bold=here))
            return
        _, item, last = row
        ago = since(item.time, self.now())
        archived = self.archive_key(item) in self.archived
        faint = "muted" if bg else "guide"            # herdr's own secondary color; on a lit row, still legible
        label = ("archived", "archived") if archived else (item.agent, faint)
        right = [("· ", faint), label, (" · ", faint), (ago, "muted")]
        if width("".join(part for part, _ in right)) > cells // 3:   # narrow: how long ago, or that it is archived
            right = right[:2] if archived else right[3:]
        start = x = cells - 1 - sum(width(part) for part, _ in right)
        for part, role in right:
            x = canvas.put(y, x, part, Style(fg=role, bg=bg))
        canvas.put(y, 1, "  └─ " if last else "  ├─ ", Style(fg="guide", bg=bg))        # inside the margin
        if self.markable(row):                                  # its box, in the tree lines' indent
            canvas.region(y, 0, 3, ("mark", index))
            if self.marked or index == self.hover:
                on = self.archive_key(item) in self.marked
                canvas.put(y, 1, MARKED if on else BOX, Style(fg="accent" if on else "muted", bg=bg))
        shown, role = mark(item.state)
        canvas.put(y, 6, shown, Style(fg=role, bg=bg))
        if self.naming and self.key(("item", self.naming.item)) == self.key(row):
            self.naming.field.draw(canvas, y, 8, max(1, cells - 9), 1, Style(bg="input"), focused=True)
            return
        title = truncate(printable(item.title), max(1, start - 9))
        look = "archived" if archived else "subtext" if item.state else "muted"     # set aside: a shade further back
        canvas.put(y, 8, title, Style(fg=look, bg=bg))

    def draw_menu(self, canvas):
        popup = self.menu
        popup.menu.draw(canvas, *popup.menu.at(popup.y, popup.x, canvas.width, self.top, self.top + self.height, PAD))

    def draw_confirm(self, canvas):
        """Delete…'s question over the list's foot, as the dock's views ask theirs."""
        cells = canvas.width
        rows = self.confirm.draw(Canvas(cells, self.height), 0, 0, cells)
        y = max(self.top, self.top + self.height - rows - 1)
        for row in range(y, self.top + self.height):
            canvas.put(row, 0, " " * cells, PLAIN)
            canvas.region(row, 0, cells, "question")
        canvas.put(y, PAD, "─" * (cells - 2 * PAD), Style(fg="muted"))
        self.confirm.draw(canvas, y + 1, 0, cells)

    def close_menu(self):
        """Its menu closed, as a click outside it closes it: the pane lost the keys."""
        self.menu = None

    def shut(self):
        """The list closed (its lit button, Esc, a click outside it, another pane): its menu, a name being typed, a
        question and the marks go with it; what was typed stays for the next time."""
        self.menu = self.naming = self.confirm = self.doomed = None
        self.marked.clear()

    # --- keys and the mouse

    def handle(self, event):
        if isinstance(event, Mouse):
            return self.mouse(event)
        if not isinstance(event, Key):
            return None
        if self.confirm:
            return self.answer(self.confirm.handle(event))
        if self.menu:
            choice = self.menu.menu.handle(event)
            if choice == "cancel":
                self.menu = None
            return self.pick(choice) if choice not in (None, "cancel") else None
        if self.naming:
            if event.name == "enter":
                return self.named()
            if event.name == "esc":
                self.naming = None
            else:
                self.naming.field.handle(event)
            return None
        name = event.char if event.name == "char" and not (event.ctrl or event.alt) else event.name
        row = self.list.selected()
        if name in ("up", "down"):
            if event.shift:                                     # marking on the way: from here to where it goes
                self.mark_row(row, True)
            self.list.move(1 if name == "down" else -1)
            if event.shift:
                self.mark_row(self.list.selected(), True)
        elif name in ("pageup", "pagedown"):
            self.list.page(1 if name == "pagedown" else -1)
        elif name in ("home", "end"):
            self.list.move(len(self.list.items) * (1 if name == "end" else -1))
        elif name == "left" and row:
            self.close(row)
        elif name == "right" and row and row[0] == "group":
            if row[3]:
                self.list.move(1)
            else:
                self.toggle(row[1])
        elif name == "enter" and row:
            return self.choose(row)
        elif name == " " and not self.typed:
            self.mark_row(row)
        elif name == "delete" and not self.typed:               # the filter empty: nothing of it to delete
            if row and row[0] == "item":
                return self.ask_delete(row[1]) if self.markable(row) else Action("no_delete", (row[1],))
        elif name in ("backspace", "delete") or (event.name == "char" and not (event.ctrl or event.alt)
                                                and event.char.isprintable()):
            self.filter(lambda: self.field.handle(event))
        return None

    def close(self, row):
        """← : a chat's group chosen; an open group closed."""
        if row[0] == "item":
            group = self.group_of(row[1])
            self.list.index = next(i for i, r in enumerate(self.list.items) if r[0] == "group" and r[1] == group)
            self.list.keep_visible()
        elif row[3]:
            self.toggle(row[1])

    def choose(self, row):
        if row[0] == "group":
            self.toggle(row[1])
            return None
        return Action("open", (row[1],))

    def ask_delete(self, item):
        """Delete… asked about ITEM, by its name: nothing leaves before the yes."""
        name = printable(item.title)
        name = name if len(name) <= ASKED else name[:ASKED - 1].rstrip() + "…"
        self.confirm, self.doomed = Confirm(f"Move the chat “{name}” to the Trash?", "Move"), item

    def answer(self, yes):
        """The question answered: on a yes the row leaves at once, the next one in its place, and its file follows."""
        if yes is None:
            return None
        item, self.confirm, self.doomed = self.doomed, None, None
        if not yes:
            return None
        self.gone.add(self.archive_key(item))
        self.marked.discard(self.archive_key(item))
        self.rebuild()
        return Action("delete", (item,))

    def back(self, item):
        """ITEM in the list again: the Trash did not take it."""
        self.gone.discard(self.archive_key(item))
        self.rebuild()

    def named(self):
        """The rename done: the chat and its new name, unless it is empty or the same."""
        item, name = self.naming.item, self.naming.field.text.strip()
        self.naming = None
        return Action("rename", (item, name)) if name and name != item.title else None

    def choices(self, item):
        """The right click's menu for ITEM: Archive for a closed one, Unarchive for an archived one, Delete… for either
        (a running one has neither); for None (anywhere else in the list) Show or Hide archived while any is, else
        nothing."""
        if item is None:
            return (("Hide archived" if self.show_archived else "Show archived"),) if self.archived else ()
        bulk = self.bulk() if self.archive_key(item) in self.marked else {}
        if bulk:
            return tuple(bulk) + ("Unmark all",)
        closed = () if item.state else (DELETE,)
        if self.archive_key(item) in self.archived:
            return MENU + ("Unarchive",) + closed
        return MENU + (("Archive",) if closed else ()) + closed

    def open_menu(self, item, event):
        """ITEM's menu where EVENT clicked; none where it would be empty."""
        choices = self.choices(item)
        self.menu = Popup(Menu(choices), item, event.y, event.x) if choices else None

    def pick(self, choice):
        item, self.menu = self.menu.on, None
        bulk = self.bulk()
        if choice in bulk:
            action, items = bulk[choice]
            self.marked -= {self.archive_key(one) for one in items}
            return Action(action, tuple(items))
        if choice == "Unmark all":
            self.marked.clear()
            return None
        if choice == DELETE:
            self.ask_delete(item)
            return None
        if choice == "Rename":
            self.naming = Naming(item, TextInput())
            self.naming.field.insert(item.title)
            return None
        if choice in ("Show archived", "Hide archived"):
            return Action("show_archived", (choice == "Show archived",))
        actions = {"Open": "open", "Copy chat": "copy", "Archive": "archive", "Unarchive": "unarchive"}
        if actions[choice] in ("archive", "unarchive"):
            self.marked.discard(self.archive_key(item))
        return Action(actions[choice], (item,))

    def filter(self, change):
        before = self.typed
        change()
        if self.typed != before:
            self.list.index = 0
            self.rebuild()

    def mouse(self, event):
        target = self.canvas.hit(event.x, event.y) if self.canvas else None
        index = target[1] if isinstance(target, tuple) and target[0] in ("row", "mark") else None
        if event.kind == "move":
            self.hover = index if index is not None else target
            if self.menu:
                self.menu.menu.point(target)
        elif event.kind in ("wheel_up", "wheel_down"):
            self.list.scroll(3 if event.kind == "wheel_down" else -3)
        elif event.kind == "press":
            if self.confirm:
                return self.answer(target == "confirm:yes") if target in ("confirm:yes", "confirm:no") else None
            if self.naming:                                 # a click in its field leaves it be; elsewhere it ends
                if target != "input":
                    self.naming = None
                return None
            if self.menu:
                menu, self.menu = self.menu, None
                if str(target).startswith("menu:"):
                    self.menu = menu
                    return self.pick(menu.menu.choices[int(target[5:])])
                return None
            if target == "blank" and event.button == 2:
                self.open_menu(None, event)
                return None
            if index is not None:
                self.list.index = index
                row = self.list.items[index]
                if target[0] == "mark" and event.button == 0:
                    self.mark_row(row)
                    return None
                if event.button == 2:
                    self.open_menu(row[1] if row[0] == "item" else None, event)
                    return None
                return self.choose(row) if event.button == 0 else None
        return None
