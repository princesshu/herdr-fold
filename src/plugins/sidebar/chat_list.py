"""The Chats list the ✦ opens over the sidebar: herdr's workspaces with chats in its Spaces list's order, each a group
of its chats (the active tab's first, then the newest) under a filter, the chosen one's plan under it, a Claude chat's
checkpoints in its place; closed ones marked to archive together, one deleted once asked. Actions come back."""
import time
from dataclasses import dataclass

import widgets
from agent_setup import KNOWN
from chats import TRASHED
from checkpoint_list import CheckpointList
from screen import AIR, CONTENT, PAD, PLAIN, Canvas, Style, truncate, width
from vt import Key, Mouse
from widgets import Action, Confirm, ListView, Menu, Popup, TextInput, wrap
from words import since

# herdr's states, as its Spaces list and AI Sessions mark and color them (unknown: its overlay0, the sidebar's
# "ignored"); a closed chat, which herdr has no state for, "·" in the faint guide color
STATE_ROLE = {"blocked": "deleted", "done": "done", "working": "modified", "idle": "added", "unknown": "ignored"}
STATE_MARK = {"blocked": "●", "done": "●", "working": "●", "idle": "○", "unknown": "·"}
SHOW, HIDE = "Show archived", "Hide archived"           # the archived ones in sight or not: More's line, the list's
MENU = ("Open", "Copy chat", "Rename")
DELETE = "Delete…"            # a closed chat's of TRASHED, asked first: its file to the system's Trash
CHECKPOINTS = "Checkpoints…"  # a Claude chat's: its prompts to take its files back to, in the list's place
ASKED = 40                    # characters of a chat's name in that question
BOX, MARKED = "□", "■"        # a closed chat's box, and a marked one's
TITLE = CONTENT + 4           # where a chat's name starts, its mark two cells before it (under its space's name)
TITLE_LEAST = 16              # cells a chat's name keeps at least: in fewer the agent's column goes
# the chosen chat's plan under its row (core/plan.py's list): a step's mark and its color, by its state
STEP_MARK = {"done": ("✓", "done"), "now": ("◐", "accent"), "next": ("○", "muted")}
OPEN_PLAN = "Open the plan"   # at the plan's head: the approved plan in your editor
NOTE_ROWS = 2                 # rows of a plan's note (Codex's) at most
AFTER_LEAST = 8               # cells of what a step waits for at least: in fewer it is left out


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
        self.field = TextInput(placeholder="Filter chats")
        self.opened, self.closed = set(), set()                     # groups opened or closed by hand
        self.archived = set()                                       # "<agent>:<id>" of the chats off the list
        self.show_archived = False                                  # those in sight too (the app sets it)
        self.marked = set()                                         # "<agent>:<id>" of the ones marked to archive
        self.naming = None                                          # a chat's name being edited (Naming)
        self.confirm = self.doomed = None                           # Delete…'s question, and the chat it asks about
        self.gone = set()                                           # "<agent>:<id>" of those on their way to the Trash
        self.front = set()                  # the panes of each workspace's active tab, whose chats lead
        self.icons = True                   # the sidebar's icons (its settings), or plain marks (the app sets it)
        self.plan = None                    # ("<agent>:<id>", its list: core/plan.py's shown), as the app read it
        self.done_open = None               # "<agent>:<id>" of the chat whose done steps are listed, each on a line
        self.points = None                  # a Claude chat's checkpoints in the list's place (CheckpointList)
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
        """("group", name, its chats, open) and ("item", chat) rows, in the order shown: every workspace with a chat
        in sight."""
        rows = []
        for name, found in self.members().items():
            if not found:
                continue
            rows.append(("group", name, found, self.is_open(name)))
            if self.is_open(name):
                rows += [("item", item) for item in found]
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

    # --- the chosen chat's plan

    def chosen(self):
        """The chat chosen; None on a group, or with no row."""
        row = self.list.selected()
        return row[1] if row and row[0] == "item" else None

    def planned(self):
        """The chosen chat's list; None while it has none, or the one read is another's."""
        item = self.chosen()
        return self.plan[1] if item and self.plan and self.plan[0] == self.archive_key(item) else None

    def plan_lines(self, cells):
        """The plan's lines under the chosen chat's row, CELLS wide: its head (a finished one's all it says), its note,
        the done steps in one row (listed under it once opened), then the step at work and those to do."""
        plan, room = self.planned(), max(1, cells - TITLE - 2 - CONTENT)
        if not plan:
            return []
        if plan["finished"]:
            return [{"kind": "head", "text": plan["count"]}]
        note = plan["note"] or ""
        lines = [{"kind": "head", "text": ""}]
        lines += [{"kind": "note", "text": note[start:end].strip()}
                  for start, end in wrap(note, room + 2)[:NOTE_ROWS] if note]
        done = [step for step in plan["steps"] if step["state"] == "done"]
        listed = self.done_open == self.plan[0]
        lines += [{"kind": "fold", "text": plan["done"], "open": listed}] if done else []
        lines += [{"kind": "listed", "text": step["text"]} for step in done] if listed else []
        return lines + [{"kind": step["state"], "text": step["text"], "after": step["after"]}
                        for step in plan["steps"] if step["state"] != "done"]

    def list_done(self, on):
        """The chosen chat's done steps listed under their row (ON) or back in it; whether that changed anything."""
        plan = self.planned()
        if not plan or plan["finished"] or not plan["done"] or (self.done_open == self.plan[0]) == on:
            return False
        widgets.TURNS.turn(("plan", self.plan[0]))
        self.done_open = self.plan[0] if on else None
        return True

    def draw_plan(self, canvas, y, line):
        """A line of the plan, under its chat's name: the head with the approved plan's link at its end, a step's mark
        and words, what it waits for at the right where there is room."""
        cells, kind, words = canvas.width, line["kind"], line["text"]
        room = max(1, cells - TITLE - 2 - CONTENT)       # its words end where the rows' do
        canvas.region(y, 0, cells, "plan")
        if kind == "head":
            canvas.put(y, TITLE, "Plan", Style(fg="muted"))
            canvas.put(y, TITLE + 6, truncate(words, max(1, room - 4)), Style(fg="done"))
            start = cells - CONTENT - width(OPEN_PLAN)
            if self.planned()["plan"] is not None and start >= TITLE + 6 + width(words) + 2:
                canvas.put(y, start, OPEN_PLAN, Style(fg="subtext", underline=True))
                canvas.region(y, start, cells - CONTENT, "plan:open")
        elif kind in ("note", "listed"):
            canvas.put(y, TITLE if kind == "note" else TITLE + 2, truncate(words, room + (2 if kind == "note" else 0)),
                       Style(fg="muted"))
        elif kind == "fold":
            canvas.region(y, 0, cells, "plan:done")
            canvas.put(y, TITLE, STEP_MARK["done"][0], Style(fg=STEP_MARK["done"][1]))
            shown = truncate(words, max(1, room - AIR - 2))  # its chevron AIR after them, the cell it spills into
            canvas.put(y, TITLE + 2, shown, Style(fg="muted"))
            canvas.put(y, TITLE + 2 + width(shown) + AIR,
                       widgets.TURNS.mark(self.icons, ("plan", self.plan[0]), line["open"]), Style(fg="muted"))
        else:
            mark, role = STEP_MARK[kind]
            after, most = line["after"] or "", room - TITLE_LEAST - 2
            after = truncate(after, min(most, cells // 3)) if after and most >= AFTER_LEAST else ""
            canvas.put(y, TITLE, mark, Style(fg=role))
            canvas.put(y, TITLE + 2, truncate(words, room - (width(after) + 2 if after else 0)),
                       Style(fg="text" if kind == "now" else "subtext"))
            canvas.put(y, cells - CONTENT - width(after), after, Style(fg="muted"))

    # --- drawing

    def draw(self, canvas, top, height, roomy):
        """The view from row TOP, HEIGHT rows: the filter, tall in a ROOMY slice as the dock's other fields are, a
        line when there is something to say, the rows."""
        if self.points:
            self.points.draw(canvas, top, height)
            return
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
        plan = self.plan_lines(cells)[:rows - 1]                    # under the chosen row, which stays in sight
        if self.list.height != rows - len(plan):
            self.list.resize(rows - len(plan))
        widths = self.columns()
        for row in range(self.list.height):
            index = self.list.at(row)
            if index is None:
                break
            self.draw_row(canvas, y, index, widths)
            y += 1
            for line in plan if index == self.list.index else ():
                self.draw_plan(canvas, y, line)
                y += 1
        if self.menu:
            self.draw_menu(canvas)
        if self.confirm:
            self.draw_confirm(canvas)

    def line(self):
        if self.items is None:
            return "Loading chats…"
        if self.list.items:
            return None
        return "No chat matches" if self.typed else "No chats"

    def columns(self):
        """The cells of the chats' two columns at the right, the agent's and the age's (or "archived"), as wide as
        their widest in sight."""
        items = [row[1] for row in self.list.items if row[0] == "item"]
        return (max([width(KNOWN[item.agent]["name"]) for item in items] or [0]),
                max([width(self.age(item)) for item in items] or [0]))

    def age(self, item):
        """How long ago ITEM was written to, or that it is archived."""
        return "archived" if self.archive_key(item) in self.archived else since(item.time, self.now())

    def draw_row(self, canvas, y, index, widths):
        """A workspace: its fold chevron dim, its name (the current one's bold), how many chats it holds at the right
        edge; a chat under its name: its mark, its name (a closed one's faint), the agent and how long ago in two
        right-aligned muted columns (WIDTHS, columns()'s), the agent's gone where the pane is narrow."""
        row, cells = self.list.items[index], canvas.width
        bg = "selection" if index == self.list.index else ("hover" if index == self.hover else None)
        faint = "muted_row" if bg else "muted"
        if bg:
            canvas.band(y, bg)
        canvas.region(y, 0, cells, ("row", index))
        if row[0] == "group":
            _, name, found, opened = row
            count = str(len(found))
            canvas.put(y, CONTENT, widgets.TURNS.mark(self.icons, ("space", name), opened), Style(fg=faint, bg=bg))
            canvas.put(y, cells - CONTENT - width(count), count, Style(fg=faint, bg=bg))
            here = name == self.here
            canvas.put(y, TITLE - 2, truncate(printable(name), max(1, cells - CONTENT - TITLE - width(count))),
                       Style(fg="text" if here else "subtext", bg=bg, bold=here))
            return
        item = row[1]
        agent, age = widths
        archived = self.archive_key(item) in self.archived
        start = cells - CONTENT - age
        canvas.put(y, cells - CONTENT - width(self.age(item)), self.age(item),
                   Style(fg="archived" if archived else faint, bg=bg))
        if start - agent - 2 - TITLE - 2 >= TITLE_LEAST:        # room for the agent's column too
            start -= agent + 2
            name = KNOWN[item.agent]["name"]
            canvas.put(y, start + agent - width(name), name, Style(fg=faint, bg=bg))
        if self.markable(row):                                  # its box, under the groups' chevrons
            canvas.region(y, 0, CONTENT + 2, ("mark", index))
            if self.marked or index == self.hover:
                on = self.archive_key(item) in self.marked
                canvas.put(y, CONTENT, MARKED if on else BOX, Style(fg="accent" if on else faint, bg=bg))
        shown, role = mark(item.state)
        canvas.put(y, TITLE - 2, shown, Style(fg=faint if bg and role == "guide" else role, bg=bg))
        if self.naming and self.key(("item", self.naming.item)) == self.key(row):
            self.naming.field.draw(canvas, y, TITLE, max(1, cells - TITLE - CONTENT), 1, Style(bg="input"),
                                   focused=True)
            return
        title = truncate(printable(item.title), max(1, start - TITLE - 2))
        look = "archived" if archived else "subtext" if item.state else faint      # set aside: a shade further back
        canvas.put(y, TITLE, title, Style(fg=look, bg=bg))

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
        self.menu = self.naming = self.confirm = self.doomed = self.points = None
        self.marked.clear()

    # --- keys and the mouse

    def handle(self, event):
        if self.points:
            done = self.points.handle(event)
            if done == "back":
                self.points = None
            return None if done == "back" else done
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
            if not self.list_done(False):
                self.close(row)
        elif name == "right" and row and row[0] == "item":
            if not self.list_done(True) and row[1].agent == "claude":
                return self.open_points(row[1])
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
                return self.ask_delete(row[1]) if self.markable(row) and row[1].agent in TRASHED \
                    else Action("no_delete", (row[1],))
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

    def menu_lines(self):
        """What More lists first while the list is open: Show or Hide archived while any is, else nothing."""
        return [HIDE if self.show_archived else SHOW] if self.archived else []

    def menu_pick(self, choice):
        """More's line CHOICE: the archived ones in sight or out of it (the app keeps it, for every tab)."""
        return Action("show_archived", (choice == SHOW,))

    def choices(self, item):
        """The right click's menu for ITEM: Checkpoints… for a Claude chat, Archive for a closed one, Unarchive for an
        archived one, Delete… for either whose file is its own (a running one has neither); for None (elsewhere in the
        list) More's lines."""
        if item is None:
            return tuple(self.menu_lines())
        bulk = self.bulk() if self.archive_key(item) in self.marked else {}
        if bulk:
            return tuple(bulk) + ("Unmark all",)
        delete = () if item.state or item.agent not in TRASHED else (DELETE,)
        mine = MENU + ((CHECKPOINTS,) if item.agent == "claude" else ())
        if self.archive_key(item) in self.archived:
            return mine + ("Unarchive",) + delete
        return mine + (() if item.state else ("Archive",)) + delete

    def open_points(self, item):
        """ITEM's checkpoints in the list's place, read by Chats."""
        self.points = CheckpointList(item)
        return Action("checkpoints", (item,))

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
        if choice == CHECKPOINTS:
            return self.open_points(item)
        if choice == "Rename":
            self.naming = Naming(item, TextInput())
            self.naming.field.insert(item.title)
            return None
        if choice in (SHOW, HIDE):
            return self.menu_pick(choice)
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
            if target in ("plan:done", "plan:open") and event.button == 0:
                if target == "plan:open":
                    return Action("plan", (self.chosen(),))
                self.list_done(self.done_open != self.plan[0])
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
