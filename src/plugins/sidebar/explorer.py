"""The sidebar's Files view: the folder as a tree under a header with its buttons, git's letter on each changed file
and a ● on each folder holding changes, what git ignores faint. The view only asks: what changes the disk comes back
as an Action for the app."""
import os
from dataclasses import dataclass

import media
from icons import GIT_LETTER, glyphs, icon
from screen import GIT_ROLE, PLAIN, Canvas, Style, after, truncate
from tree import Node, git_marks
from vt import Key, Mouse
from widgets import Action, Confirm, ListView, Menu, Popup, TextInput

LIST = 1                      # the tree's first row: right under the header
MENU = ("New File", "New Folder", "Rename", "Copy Path", "Move to Trash")


@dataclass
class Naming:
    action: str               # new_file, new_folder or rename
    target: str               # the folder a new entry goes in, or the path renamed
    field: TextInput
    back: str = None          # the path chosen before, chosen again when the naming ends
    node: Node = None         # a new entry's row


class Explorer:
    def __init__(self, tree, icons=True, repo=None):
        self.tree, self.icons = tree, icons
        self.repo = repo or tree.root           # git's paths are relative to the repository's top folder
        self.list = ListView()
        self.status, self.marks, self.folders = None, {}, {}
        self.naming = self.menu = self.confirm = self.doomed = None
        self.hover, self.canvas, self.top, self.height = None, Canvas(0, 0), 0, 1
        self.cut = set()                        # the rows whose name is cut short, as last drawn
        self.pointed = None                               # the header button under the mouse
        self.moved = False                                # whether the chosen row is yours: the first is by itself
        self.opens_workspace = False                      # herdr-fold's folder picker there (the app asks herdr once)

    @property
    def editing(self):
        """Whether the view holds the keys — a name being typed, a menu or a question (the app's own keys wait)."""
        return any(held is not None for held in (self.naming, self.menu, self.confirm))

    # --- what is shown

    def watch(self, status):
        """Git's marks from a STATUS not seen yet (the app hands them over worked out already, with take)."""
        if status is not self.status:
            self.take(status, git_marks(status, self.repo, self.tree.root))

    def take(self, status, marks):
        """A STATUS and its MARKS from git_marks."""
        self.status, (self.marks, self.folders, ignored) = status, marks
        self.tree.set_ignored(ignored)

    def sync(self):
        """The rows from the tree (and a new entry's row while it is named); the selection stays on its path."""
        rows = self.tree.rows()
        if self.naming and self.naming.node:
            folder = self.naming.target
            at = next((i + 1 for i, node in enumerate(rows) if node.path == folder), 0)
            rows.insert(at, self.naming.node)
        if rows != self.list.items:
            chosen = self.list.selected()
            self.list.set(rows)
            if chosen is not None:
                self.choose(lambda node: node is chosen or (chosen.path and node.path == chosen.path))

    def choose(self, match):
        index = next((i for i, node in enumerate(self.list.items) if match(node)), None)
        if index is not None:
            self.list.index = index
            self.list.keep_visible()

    def select(self, path):
        """Choose PATH's row (the app does, for an entry it has just made)."""
        self.sync()
        self.choose(lambda node: node.path == path)

    # --- drawing

    def draw(self, canvas, top, height, status):
        """The view from row TOP, HEIGHT rows: the folder's name, the tree right under it."""
        self.canvas, self.top, self.height, self.cut = canvas, top, height, set()
        self.watch(status)
        self.sync()
        if self.list.height != height - LIST:
            self.list.resize(height - LIST)
        self.header(canvas, top)
        for y in range(top + 1, top + height):
            canvas.region(y, 0, canvas.width, "blank")
        for row in range(self.list.height):
            index = self.list.at(row)
            if index is None:
                break
            self.row(canvas, top + LIST + row, index)
        if self.menu:
            self.draw_menu(canvas)
        if self.confirm:
            self.draw_confirm(canvas)

    def header(self, canvas, y):
        marks = glyphs(self.icons)
        buttons = ("new_file", "new_folder", "refresh", "collapse")
        x = canvas.width - 3 * len(buttons) + 1               # each icon with two columns of room after it
        name = os.path.basename(self.tree.root.rstrip(os.sep)) or self.tree.root
        canvas.put(y, 1, truncate(name, x - 2), Style(fg="text", bold=True))
        for target in buttons:
            canvas.put(y, x, marks[target], Style(fg="text" if target == self.pointed else "muted"))
            canvas.region(y, x, x + 2, target)
            x += 3

    def row(self, canvas, y, index):
        node, width = self.list.items[index], canvas.width
        bg = "selection" if index == self.list.index else ("hover" if index == self.hover else None)
        canvas.band(y, bg)
        canvas.region(y, 0, width, ("row", index))
        x = canvas.put(y, 1, "│ " * node.depth, Style(fg="muted", bg=bg))
        naming = self.naming
        named = naming and (node is naming.node or (naming.action == "rename" and node.path == naming.target))
        if node.path is None and not named:                 # "… N more"
            canvas.put(y, x + 2, truncate(node.name, width - x - 3), Style(fg="muted", bg=bg))
            return
        chevron = glyphs(self.icons)["open" if node.expanded else "closed"] if node.is_dir else " "
        x = canvas.put(y, x, chevron + after(self.icons), Style(fg="muted", bg=bg))
        if self.icons:
            glyph = icon(node.name, node.is_dir, node.expanded)
            x = canvas.put(y, x, glyph + after(True), Style(fg="accent" if node.is_dir else "muted", bg=bg))
        if named:
            naming.field.draw(canvas, y, x, max(1, width - x - 1), 1, Style(bg="input"), focused=True)
            return
        code = (self.folders if node.is_dir else self.marks).get(node.path)
        fg = "ignored" if self.tree.is_ignored(node.path) else GIT_ROLE[code] if code else "text"
        strike = code == "D" and not node.is_dir
        shown = truncate(node.name, width - x - 3)
        canvas.put(y, x, shown, Style(fg=fg, bg=bg, strike=strike))
        if shown != node.name:
            self.cut.add(index)
        if code:
            mark = "●" if node.is_dir else GIT_LETTER.get(code, code)
            canvas.put(y, width - 2, mark, Style(fg=GIT_ROLE[code], bg=bg))

    def tip(self, target):
        """A name cut short in its row, whole (its path in the folder), for the mouse resting on it."""
        if isinstance(target, tuple) and target[0] == "row" and target[1] in self.cut:
            return os.path.relpath(self.list.items[target[1]].path, self.tree.root)
        return None

    def draw_menu(self, canvas):
        popup = self.menu
        popup.menu.draw(canvas, *popup.menu.at(popup.y, popup.x, canvas.width, self.top + LIST,
                                               self.top + self.height))

    def draw_confirm(self, canvas):
        width = canvas.width
        rows = self.confirm.draw(Canvas(width, self.height), 0, 0, width)
        y = max(self.top + LIST, self.top + self.height - rows - 1)
        for row in range(y, self.top + self.height):
            canvas.put(row, 0, " " * width, PLAIN)
        canvas.put(y, 0, "─" * width, Style(fg="muted"))
        self.confirm.draw(canvas, y + 1, 0, width)

    # --- events

    def handle(self, event):
        self.sync()
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
                return self.finish()
            if event.name == "esc":
                self.end_naming()
            else:
                self.naming.field.handle(event)
            return None
        return self.key(event)

    def key(self, event):
        if event.name == "char" and (event.ctrl or event.alt):
            return None
        name, node = event.char if event.name == "char" else event.name, self.list.selected()
        moves = {"up": -1, "k": -1, "down": 1, "j": 1, "home": -len(self.list.items), "g": -len(self.list.items),
                 "end": len(self.list.items), "G": len(self.list.items)}
        if name in moves or name in ("pageup", "pagedown", "right", "l", "left", "h", "enter", " "):
            self.moved = True
        if name in moves:
            self.list.move(moves[name])
        elif name in ("pageup", "pagedown"):
            self.list.page(1 if name == "pagedown" else -1)
        elif name in ("right", "l"):
            self.open_or_enter(node)
        elif name in ("left", "h"):
            self.close_or_up(node)
        elif name in ("enter", " "):
            return self.activate(node)
        elif name in ("n", "N"):
            self.new("new_file" if name == "n" else "new_folder", self.folder(node))
        elif name == "r":
            self.rename(node)
        elif name == "delete":
            self.ask_trash(node)
        elif name == "m" and node is not None:
            self.open_menu(node, self.top + LIST + self.list.index - self.list.top, 2)
        elif name == ".":
            self.tree.set_hidden(not self.tree.show_hidden)
            return Action("show_hidden", (self.tree.show_hidden,))
        elif name == "i":
            self.icons = not self.icons
            return Action("icons", (self.icons,))
        elif name == "R":
            return Action("refresh")
        return None

    def mouse(self, event):
        target = self.canvas.hit(event.x, event.y)
        if event.kind == "move":
            self.hover = target[1] if isinstance(target, tuple) else None
            self.pointed = target if isinstance(target, str) else None
        elif event.kind in ("wheel_up", "wheel_down"):
            self.list.scroll(3 if event.kind == "wheel_down" else -3)
        elif event.kind == "press":
            return self.press(event, target)
        return None

    def press(self, event, target):
        if self.confirm:
            return self.answer(target == "confirm:yes") if target in ("confirm:yes", "confirm:no") else None
        if self.menu:
            if str(target).startswith("menu:"):
                return self.pick(self.menu.menu.choices[int(target[5:])])
            self.menu = None
            return None
        if target == "input":
            return None
        node = self.list.items[target[1]] if isinstance(target, tuple) else None
        if self.naming:
            self.end_naming()
            if node is not None and node.path is None:
                return None
        if node is not None:
            self.choose(lambda row: row is node or (node.path and row.path == node.path))
            self.moved = True
            if event.button == 2:
                self.open_menu(node, event.y, event.x)
                return None
            return self.activate(node) if event.button == 0 else None
        if target == "blank" and event.button == 2:
            self.open_menu(None, event.y, event.x)
        elif target in ("new_file", "new_folder"):
            self.new(target, self.folder(self.list.selected()))
        elif target == "refresh":
            return Action("refresh")
        elif target == "collapse":
            self.tree.collapse_all()
            self.sync()
        return None

    # --- what the keys and the mouse do

    def activate(self, node):
        if node is None or node.path is None:
            return None
        if node.is_dir:
            self.tree.toggle(node.path)
            self.sync()
            return None
        return Action("preview_file", (node.path,))

    def open_or_enter(self, node):
        if node is None or not node.is_dir:
            return
        if not node.expanded:
            self.tree.toggle(node.path)
            self.sync()
        elif self.list.index + 1 < len(self.list.items) and self.list.items[self.list.index + 1].depth > node.depth:
            self.list.move(1)

    def close_or_up(self, node):
        if node is None:
            return
        if node.is_dir and node.expanded:
            self.tree.toggle(node.path)
            self.sync()
            return
        for index in range(self.list.index - 1, -1, -1):
            if self.list.items[index].depth < node.depth:
                self.list.index = index
                self.list.keep_visible()
                return

    def folder(self, node):
        """Where a new entry goes: the chosen folder, the chosen file's folder, or the root."""
        if node is None or node.path is None:
            return self.tree.root
        return node.path if node.is_dir else os.path.dirname(node.path)

    def new(self, action, folder):
        if folder != self.tree.root and folder not in self.tree.expanded:
            self.tree.toggle(folder)
        depth = 0 if folder == self.tree.root else os.path.relpath(folder, self.tree.root).count(os.sep) + 1
        chosen = self.list.selected()
        node = Node(None, "", action == "new_folder", depth)
        self.naming = Naming(action, folder, TextInput(), chosen.path if chosen else None, node)
        self.sync()
        self.choose(lambda row: row is node)

    def rename(self, node):
        if node is None or node.path is None:
            return
        field = TextInput()
        field.insert(node.name)
        self.naming = Naming("rename", node.path, field, node.path)

    def finish(self):
        naming, name = self.naming, self.naming.field.text.strip()
        self.end_naming()
        if not name or (naming.action == "rename" and name == os.path.basename(naming.target)):
            return None
        return Action(naming.action, (naming.target, name))

    def end_naming(self):
        back, self.naming = self.naming.back, None
        self.sync()
        if back:
            self.select(back)

    def ask_trash(self, node):
        if node is not None and node.path is not None:
            self.confirm, self.doomed = Confirm(f"Move {node.name} to the Trash?", "Move"), node.path

    def answer(self, yes):
        if yes is None:
            return None
        doomed, self.confirm, self.doomed = self.doomed, None, None
        return Action("trash", (doomed,)) if yes else None

    def open_menu(self, node, y, x):
        if node is None or node.path is None:
            choices = MENU[:2]
        else:
            choices = (("New Workspace",) if node.is_dir and self.opens_workspace else ()) + MENU
            if not node.is_dir and media.kind_of(node.path) and media.browsable():     # a page, a PDF, an image
                choices = ("Open in Browser",) + choices
        self.menu = Popup(Menu(choices), node, y, x)

    def close_menu(self):
        """Its menu closed, as a click outside it closes it: the pane lost the keys, or its header was clicked."""
        self.menu = None

    def pick(self, choice):
        node = self.menu.on if self.menu else None
        self.menu = None
        if choice in ("New File", "New Folder"):
            self.new("new_file" if choice == "New File" else "new_folder", self.folder(node))
        elif choice == "Rename":
            self.rename(node)
        elif choice == "Copy Path":
            return Action("copy_path", (node.path,))
        elif choice == "Open in Browser":
            return Action("open_browser", (node.path,))
        elif choice == "New Workspace":
            return Action("new_workspace", (node.path,))
        elif choice == "Move to Trash":
            self.ask_trash(node)
        return None
