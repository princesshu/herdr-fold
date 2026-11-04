"""The folder picker for a new workspace, opened by the tab-layout plugin after herdr's "new" button: herdr alone would
reuse the active workspace's folder. herdr_layout.py builds the chosen folder's workspace (or it jumps to an existing
one), and the empty one is closed."""
import collections
import os
import shutil
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herdr_layout import LayoutError, build  # noqa: E402
from herdrlib import AGENTS, PLUGIN_STATE, agent_pane_ids, free_label, herdr  # noqa: E402
from i18n import line, t  # noqa: E402
from projects import repositories, start  # noqa: E402
from icons import glyphs, icon  # noqa: E402  the sidebar's, on the path herdrlib gives
from screen import after, icons_on  # noqa: E402  the sidebar's, on the path herdrlib gives
from tui import (GRAY, INVERT, MARGIN, RESET, button_at, buttons, clicked, getkey, mouse, printable,  # noqa: E402
                 wait_and_exit)

HOME = os.path.expanduser("~")
BOLD = "\x1b[1m"
FIRST_ROW = 3              # the tree's first row on screen, under the title and the filter
DOUBLE = 0.4               # seconds within which a second click on a row opens it
NAME_CELLS = 48            # a row's cells before its tags, fewer in a narrower window (a wrapped row moves the clicks)
TAGS_CELLS = 8             # "git open"

Row = collections.namedtuple("Row", "path name depth open")


def subfolders(path):
    """The folder's subfolders; hidden ones go at the end of the list (shown in gray)."""
    try:
        names = [e.name for e in os.scandir(path) if e.is_dir()]
    except OSError:
        return []
    return sorted(names, key=lambda n: (n.startswith("."), n.lower()))


def tree(root, opened, filt):
    """ROOT on top, open, and each open folder's subfolders under it (OPENED: the open ones), as the sidebar's Files
    view shows a folder; typing keeps the rows whose name has it (ROOT goes)."""
    rows = [Row(root, "~" if root == HOME else os.path.basename(root.rstrip(os.sep)) or root, 0, True)]

    def under(folder, depth):
        for name in subfolders(folder):
            path = os.path.join(folder, name)
            rows.append(Row(path, name, depth, path in opened))
            if path in opened:
                under(path, depth + 1)
    under(root, 1)
    return [row for row in rows[1:] if filt.lower() in row.name.lower()] if filt else rows


def indent(depth):
    """What goes before a row's mark: the top one none, the ones under it a step in, deeper ones Files' guide lines."""
    return "" if not depth else "  " + "│ " * (depth - 1)


def title_of(folder):
    return printable(folder.replace(HOME, "~", 1))


def toggle_start(title, width):
    """The toggle's first column (0-based) on the title row: at its right end, MARGIN from the edge, a cell from the
    title at least."""
    return MARGIN + len(title) + max(1, width - 2 * MARGIN - len(title) - len(" │ ".join(f" {a} " for a in AGENTS)))


def picker_buttons(width):
    """The last row: the keys a click cannot show, then Cancel and Open (Enter's)."""
    return buttons([t("common.cancel"), t("common.open")], width, t("picker.keys"))


class Picker:
    """The tree in the picker and what the keys and the mouse do with it, as in the sidebar's Files view: → opens a
    folder or steps into an open one, ← closes one or steps to its parent, and on the top row goes up a folder."""

    def __init__(self, root, target=None):
        self.root, self.opened, self.filt, self.agent = root, set(), "", AGENTS[0]
        self.chosen = self.top = 0
        self.last = None                          # the click before: its time and row (a second one there opens)
        if target and os.path.isdir(target):      # the sidebar's New Workspace: on that folder, in its parent
            self.root = os.path.dirname(target.rstrip(os.sep)) or target
            self.choose(target)

    def rows(self):
        return tree(self.root, self.opened, self.filt)

    def choose(self, path):
        self.chosen = next((n for n, row in enumerate(self.rows()) if row.path == path), 0)

    def chosen_path(self):
        rows = self.rows()
        return rows[min(self.chosen, len(rows) - 1)].path if rows else None

    def fit(self, height):
        """The rows on screen, HEIGHT at most, the chosen one among them."""
        rows = self.rows()
        self.chosen = min(self.chosen, max(len(rows) - 1, 0))
        self.top = min(max(self.top, self.chosen - height + 1), self.chosen)
        return rows[self.top:self.top + height]

    def press(self, key, height):
        """KEY's effect; "open", "cancel" or None."""
        rows = self.rows()
        row = rows[self.chosen] if self.chosen < len(rows) else None
        if key == "\x1b[A":
            self.chosen = max(self.chosen - 1, 0)
        elif key == "\x1b[B":
            self.chosen += 1
        elif key in ("\x1b[5~", "\x1b[6~"):
            self.chosen = max(self.chosen + (height if key == "\x1b[6~" else -height), 0)
        elif key == "\x1b[C" and row:
            self.open_or_enter(rows, row)
        elif key == "\x1b[D" or (key in ("\x7f", "\x08") and not self.filt):
            self.close_or_up(rows, row)
        elif key in ("\x7f", "\x08"):
            self.filt, self.chosen = self.filt[:-1], 0
        elif key == "\t":
            self.agent = AGENTS[(AGENTS.index(self.agent) + 1) % len(AGENTS)]
        elif key in ("\r", "\n") and row:
            return "open"
        elif key == "\x1b" and self.filt:
            self.filt, self.chosen = "", 0
        elif key in ("\x1b", "\x03"):
            return "cancel"
        elif len(key) == 1 and key.isprintable():
            self.filt, self.chosen, self.top = self.filt + key, 0, 0
        return None

    def open_or_enter(self, rows, row):
        if not row.open:
            self.opened.add(row.path)
        elif self.chosen + 1 < len(rows) and rows[self.chosen + 1].depth > row.depth:
            self.chosen += 1

    def close_or_up(self, rows, row):
        if row is None:
            return
        if row.depth and row.open:
            self.opened.discard(row.path)
        elif row.depth:
            self.chosen = next((n for n in range(self.chosen - 1, -1, -1) if rows[n].depth < row.depth), self.chosen)
        elif os.path.dirname(self.root) != self.root:    # the top row: up a folder, this one open and chosen
            below, self.root, self.top = self.root, os.path.dirname(self.root), 0
            self.opened.add(below)
            self.choose(below)

    def click(self, event, now, width, height):
        """A mouse EVENT (tui.clicked()): a click chooses a row, the same one again within DOUBLE seconds opens it, a
        click on its mark opens or closes it, the toggle chooses the agent, a button opens or cancels, the wheel moves.
        "open", "cancel" or None."""
        button, column, at, pressed = event
        if button in (64, 65):
            self.chosen = max(self.chosen - 1, 0) if button == 64 else self.chosen + 1
            return None
        if button != 0 or not pressed:
            return None
        shown = self.fit(height)
        if at == 1:
            x, start = column - 1 - toggle_start(title_of(self.root), width), 0
            for agent in AGENTS:
                if start <= x < start + len(agent) + 2:
                    self.agent = agent
                start += len(agent) + 2 + len(" │ ")
            return None
        if at == FIRST_ROW + len(shown) + 1:
            label = button_at(column, picker_buttons(width)[1])
            return label and ("open" if label == t("common.open") else "cancel")
        if not FIRST_ROW <= at < FIRST_ROW + len(shown):
            return None
        row, self.chosen = shown[at - FIRST_ROW], self.top + at - FIRST_ROW
        mark = 2 + len(indent(row.depth))
        if row.depth and mark <= column <= mark + 1:
            self.opened.symmetric_difference_update({row.path})
            self.last = None
        elif self.last and self.last[1] == self.chosen and now - self.last[0] <= DOUBLE:
            self.last = None
            return "open"
        else:
            self.last = (now, self.chosen)
        return None


def open_workspaces():
    """folder → workspace, based on the folder of each workspace's agent pane."""
    panes = herdr("pane", "list")["panes"]
    agents = agent_pane_ids(panes)
    return {p["cwd"]: p["workspace_id"] for p in panes if p["pane_id"] in agents and p.get("cwd")}


def is_repo(path):
    return os.path.exists(os.path.join(path, ".git"))


def close_placeholder(ws, back=False):
    """The empty workspace created by the "new" button; the last workspace is never closed. BACK (Esc): the one in
    front before it first, as herdr alone would show a neighbour of the closed one."""
    if ws and len(herdr("workspace", "list")["workspaces"]) > 1:
        came = os.environ.get("HERDR_CAME_FROM")
        if back and came and came != ws:
            herdr("workspace", "focus", came, check=False)
        herdr("workspace", "close", ws, check=False)


def open_folder(path, agent, placeholder):
    ws = open_workspaces().get(path)
    if not ws:
        workspaces = herdr("workspace", "list")["workspaces"]
        label = printable(free_label(path, {w["label"] for w in workspaces if w["workspace_id"] != placeholder}, HOME))
        print("\n" + t("picker.setting_up", label, agent))
        try:
            print("\n".join(build(None, agent, path, label)))
        except (LayoutError, RuntimeError) as err:
            print(line("fail", str(err)))
            wait_and_exit(1)
        ws = next((w["workspace_id"] for w in herdr("workspace", "list")["workspaces"] if w["label"] == label), None)
        if not ws:
            wait_and_exit(1)
    herdr("workspace", "focus", ws)
    close_placeholder(placeholder)


def screen(picker, opened, height, width):
    """The picker: the folder as the title with the agent toggle on its right, what you type to filter by (only then),
    the tree, and the keys that are not obvious with Cancel and Open."""
    rows, icons = picker.fit(height), icons_on(PLUGIN_STATE)
    cells = max(1, min(NAME_CELLS, width - TAGS_CELLS - 3))
    toggle = " │ ".join(f"{INVERT} {a} {RESET}" if a == picker.agent else f" {a} " for a in AGENTS)
    title = title_of(picker.root)
    lines = [" " * MARGIN + f"{BOLD}{title}{RESET}" + " " * (toggle_start(title, width) - MARGIN - len(title)) + toggle
             + " " * MARGIN, " " * MARGIN + f"{picker.filt}▏" if picker.filt else ""]
    for n, row in enumerate(rows, picker.top):
        mark = glyphs(icons)["open" if row.open else "closed"] + after(icons)
        folder = icon(row.name, True, row.open) + after(True) if icons else ""
        cell = indent(row.depth) + mark + folder + printable(row.name)
        tags = " ".join(tag for tag, on in (("git", is_repo(row.path)), ("open", row.path in opened)) if on)
        color = INVERT if n == picker.chosen else GRAY if row.depth and row.name.startswith(".") else ""
        lines.append(f"{color} {cell[:cells]:{cells}} {GRAY if n != picker.chosen else ''}{tags:{TAGS_CELLS}} {RESET}")
    lines += ["", picker_buttons(width)[0]]
    return "\x1b[2J\x1b[H" + "\n".join(lines)


def main():
    placeholder = os.environ.get("HERDR_NEW_WORKSPACE")
    picker = Picker(start(repositories()), os.environ.get("HERDR_NEW_WORKSPACE_FOLDER"))
    opened = set(open_workspaces())
    mouse(True)
    while True:
        height, width = max(3, os.get_terminal_size().lines - 6), shutil.get_terminal_size().columns
        print(screen(picker, opened, height, width), end="", flush=True)
        key = getkey()
        event = clicked(key)
        action = picker.click(event, time.monotonic(), width, height) if event else picker.press(key, height)
        if action == "open" and picker.chosen_path():
            return open_folder(picker.chosen_path(), picker.agent, placeholder)
        if action == "cancel":
            close_placeholder(placeholder, back=True)
            return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except RuntimeError as err:
        print(line("fail", str(err)))
        wait_and_exit(1)
