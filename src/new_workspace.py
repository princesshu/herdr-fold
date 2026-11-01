"""The folder picker for a new workspace, opened by the tab-layout plugin after herdr's "new" button: herdr alone would
reuse the active workspace's folder. herdr_layout.py builds the chosen folder's workspace (or it jumps to an existing
one), and the empty one is closed."""
import os
import shutil
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herdr_layout import LayoutError, build  # noqa: E402
from herdrlib import AGENTS, agent_pane_ids, free_label, herdr  # noqa: E402
from i18n import line, t  # noqa: E402
from projects import repositories, start  # noqa: E402
from tui import GRAY, INVERT, RESET, button_at, buttons, clicked, getkey, mouse, printable, wait_and_exit  # noqa: E402

HOME = os.path.expanduser("~")
BOLD = "\x1b[1m"
FIRST_ROW = 3              # the folders' first row on screen, under the title and the filter
DOUBLE = 0.4               # seconds within which a second click on a row opens it


def subfolders(path):
    """The folder's subfolders; hidden ones go at the end of the list (shown in gray)."""
    try:
        names = [e.name for e in os.scandir(path) if e.is_dir()]
    except OSError:
        return []
    return sorted(names, key=lambda n: (n.startswith("."), n.lower()))


def listing(folder, filt):
    """The rows of FOLDER: the folder itself (.) and its subfolders; typing keeps those that have it (the folder itself
    goes)."""
    rows = [".", *subfolders(folder)]
    return [row for row in rows if row != "." and filt.lower() in row.lower()] if filt else rows


def title_of(folder):
    return printable(folder.replace(HOME, "~", 1))


def toggle_start(title, width):
    """The toggle's first column (0-based) on the title row: at its right end, a cell from the title at least."""
    return len(title) + max(1, width - len(title) - len(" │ ".join(f" {a} " for a in AGENTS)))


def picker_buttons(width):
    """The last row: the keys a click cannot show, then Cancel and Open (Enter's)."""
    return buttons([t("common.cancel"), t("picker.open")], width, t("picker.keys"))


def hit(column, row, title, width, top, shown):
    """What a click at COLUMN, ROW (1-based) is on: ("agent", name) in the toggle, ("row", n) on one of the SHOWN folder
    rows (the first being row TOP of the list), ("button", "cancel" or "open") on the last row, else None."""
    if row == FIRST_ROW + shown + 1:
        label = button_at(column, picker_buttons(width)[1])
        return label and ("button", "open" if label == t("picker.open") else "cancel")
    if row == 1:
        x, start = column - 1 - toggle_start(title, width), 0
        for agent in AGENTS:
            if start <= x < start + len(agent) + 2:
                return ("agent", agent)
            start += len(agent) + 2 + len(" │ ")
        return None
    return ("row", top + row - FIRST_ROW) if FIRST_ROW <= row < FIRST_ROW + shown else None


def clicking(event, chosen, agent, last, now, title, width, top, shown):
    """A mouse EVENT (tui.clicked()): a click chooses a folder row, the same one again within DOUBLE seconds opens it
    (LAST: the time and row of the click before), the toggle chooses the agent, a button opens or cancels, the wheel
    moves. Returns (chosen, agent, last, "open", "cancel" or None)."""
    button, column, row, pressed = event
    if button in (64, 65):
        return (max(chosen - 1, 0) if button == 64 else chosen + 1), agent, last, None
    target = hit(column, row, title, width, top, shown) if button == 0 and pressed else None
    if target is None:
        return chosen, agent, last, None
    if target[0] == "agent":
        return chosen, target[1], None, None
    if target[0] == "button":
        return chosen, agent, None, target[1]
    if last and last[1] == target[1] and now - last[0] <= DOUBLE:
        return target[1], agent, None, "open"
    return target[1], agent, (now, target[1]), None


def start_on(target, first):
    """Where the picker starts: on folder TARGET (the sidebar's New Workspace), chosen in its parent; else in FIRST."""
    if target and os.path.isdir(target):
        folder, name = os.path.split(target.rstrip(os.sep))
        rows = listing(folder, "")
        if name in rows:
            return folder, rows.index(name)
    return first, 0


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


def screen(folder, names, chosen, top, filt, agent, opened, height, width):
    """The picker: the folder as the title with the agent toggle on its right, what you type to filter by (only then),
    the folders, and the keys that are not obvious."""
    toggle = " │ ".join(f"{INVERT} {a} {RESET}" if a == agent else f" {a} " for a in AGENTS)
    title = title_of(folder)
    rows = [f"{BOLD}{title}{RESET}" + " " * (toggle_start(title, width) - len(title)) + toggle,
            f"{filt}▏" if filt else ""]
    for n in range(top, min(len(names), top + height)):
        name = names[n]
        path = folder if name == "." else os.path.join(folder, name)
        tags = " ".join(tag for tag, on in (("git", is_repo(path)), ("open", path in opened)) if on)
        color = INVERT if n == chosen else GRAY if name.startswith(".") and name != "." else ""
        rows.append(f"{color} {printable(name)[:48]:48} {GRAY if n != chosen else ''}{tags:8} {RESET}")
    rows += ["", picker_buttons(width)[0]]
    return "\x1b[2J\x1b[H" + "\n".join(rows)


def main():
    placeholder = os.environ.get("HERDR_NEW_WORKSPACE")
    first = start(repositories())
    folder, chosen = start_on(os.environ.get("HERDR_NEW_WORKSPACE_FOLDER"), first)
    opened = set(open_workspaces())
    agent, filt, top, last = AGENTS[0], "", 0, None
    mouse(True)
    while True:
        names = listing(folder, filt)
        height, width = max(3, os.get_terminal_size().lines - 6), shutil.get_terminal_size().columns
        chosen = min(chosen, max(len(names) - 1, 0))
        top = min(max(top, chosen - height + 1), chosen)
        print(screen(folder, names, chosen, top, filt, agent, opened, height, width), end="", flush=True)
        key = getkey()
        event = clicked(key)
        if event:
            shown = max(0, min(len(names), top + height) - top)
            chosen, agent, last, action = clicking(event, chosen, agent, last, time.monotonic(), title_of(folder),
                                                   width, top, shown)
            if action == "open" and names:
                name = names[chosen]
                return open_folder(folder if name == "." else os.path.join(folder, name), agent, placeholder)
            if action == "cancel":
                close_placeholder(placeholder, back=True)
                return
            continue
        name = names[chosen] if names else None
        if key == "\x1b[A":
            chosen = max(chosen - 1, 0)
        elif key == "\x1b[B":
            chosen += 1
        elif key == "\x1b[5~":
            chosen = max(chosen - height, 0)
        elif key == "\x1b[6~":
            chosen += height
        elif key == "\x1b[C" and name and name != ".":
            folder, filt, chosen, top = os.path.join(folder, name), "", 0, 0
        elif key == "\x1b[D" or (key in ("\x7f", "\x08") and not filt):
            parent = os.path.dirname(folder)
            if parent != folder:                  # the list lands on the folder it came from
                came_from, folder, filt, top = os.path.basename(folder), parent, "", 0
                rows = listing(folder, "")
                chosen = rows.index(came_from) if came_from in rows else 0
        elif key in ("\x7f", "\x08"):
            filt, chosen = filt[:-1], 0
        elif key == "\t":
            agent = AGENTS[(AGENTS.index(agent) + 1) % len(AGENTS)]
        elif key in ("\r", "\n") and name:
            return open_folder(folder if name == "." else os.path.join(folder, name), agent, placeholder)
        elif key == "\x1b" and filt:
            filt, chosen = "", 0
        elif key in ("\x1b", "\x03"):
            close_placeholder(placeholder, back=True)
            return
        elif len(key) == 1 and key.isprintable():
            filt, chosen, top = filt + key, 0, 0


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except RuntimeError as err:
        print(line("fail", str(err)))
        wait_and_exit(1)
