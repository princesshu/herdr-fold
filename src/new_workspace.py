"""The folder picker for a new workspace, opened by the tab-layout plugin after herdr's "new" button: herdr alone would
reuse the active workspace's folder. herdr_layout.py builds the chosen folder's workspace (or it jumps to an existing
one), and the empty one is closed."""
import os
import shutil
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herdr_layout import LayoutError, build  # noqa: E402
from herdrlib import AGENTS, agent_pane_ids, free_label, herdr  # noqa: E402
from i18n import line, t  # noqa: E402
from projects import elsewhere, repositories, start  # noqa: E402
from tui import getkey, printable, wait_and_exit  # noqa: E402

HOME = os.path.expanduser("~")
BOLD, GRAY, INVERT, RESET = "\x1b[1m", "\x1b[90m", "\x1b[7m", "\x1b[0m"


def subfolders(path):
    """The folder's subfolders; hidden ones go at the end of the list (shown in gray)."""
    try:
        names = [e.name for e in os.scandir(path) if e.is_dir()]
    except OSError:
        return []
    return sorted(names, key=lambda n: (n.startswith("."), n.lower()))


def listing(folder, filt, top, others):
    """The rows of FOLDER: in the start folder (TOP) the repositories found elsewhere (OTHERS, full paths) first, then
    the folder itself (.) and its subfolders; typing keeps those whose shown name has it (the folder itself goes)."""
    rows = (others if folder == top else []) + [".", *subfolders(folder)]
    return [row for row in rows if row != "." and filt.lower() in shown(row).lower()] if filt else rows


def shown(name):
    """A row's name as it shows: a full path under the home folder as ~/…"""
    return "~" + name[len(HOME):] if os.path.isabs(name) and (name + "/").startswith(HOME + "/") else name


def start_on(target, first, others):
    """Where the picker starts: on folder TARGET (the sidebar's Add Workspace), chosen in its parent; else in FIRST."""
    if target and os.path.isdir(target):
        folder, name = os.path.split(target.rstrip(os.sep))
        rows = listing(folder, "", first, others)
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


def close_placeholder(ws):
    """The empty workspace created by the "new" button; the last workspace is never closed."""
    if ws and len(herdr("workspace", "list")["workspaces"]) > 1:
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
    toggle_width = len(" │ ".join(f" {a} " for a in AGENTS))
    title = printable(folder.replace(HOME, "~", 1))
    rows = [f"{BOLD}{title}{RESET}" + " " * max(1, width - len(title) - toggle_width) + toggle,
            f"{filt}▏" if filt else ""]
    for n in range(top, min(len(names), top + height)):
        name = names[n]
        path = folder if name == "." else os.path.join(folder, name)
        tags = " ".join(tag for tag, on in (("git", is_repo(path)), ("open", path in opened)) if on)
        color = INVERT if n == chosen else GRAY if name.startswith(".") and name != "." else ""
        rows.append(f"{color} {printable(shown(name))[:48]:48} {GRAY if n != chosen else ''}{tags:8} {RESET}")
    rows += ["", GRAY + t("picker.keys") + RESET]
    return "\x1b[2J\x1b[H" + "\n".join(rows)


def main():
    placeholder = os.environ.get("HERDR_NEW_WORKSPACE")
    repos = repositories()
    first = start(repos)
    others = elsewhere(repos, first)
    folder, chosen = start_on(os.environ.get("HERDR_NEW_WORKSPACE_FOLDER"), first, others)
    opened = set(open_workspaces())
    agent, filt, top = AGENTS[0], "", 0
    while True:
        names = listing(folder, filt, first, others)
        height = max(3, os.get_terminal_size().lines - 6)
        chosen = min(chosen, max(len(names) - 1, 0))
        top = min(max(top, chosen - height + 1), chosen)
        print(screen(folder, names, chosen, top, filt, agent, opened, height, shutil.get_terminal_size().columns),
              end="", flush=True)
        key = getkey()
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
                rows = listing(folder, "", first, others)
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
            close_placeholder(placeholder)
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
