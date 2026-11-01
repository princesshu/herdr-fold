"""New tab: a workspace from herdr's "new" button gets the folder picker (new_workspace.py), unless a git worktree's;
any other new tab gets the right-hand column, only while empty (one unnamed shell pane after 1.5 s: no builder's or
preview tab). On a pane's focus, a workspace named after its folder takes the folder's new name."""
import json
import os
import re
import subprocess
import sys
import tempfile
import time

# herdrlib.py is two folders up, where the plugin is installed (and in the package): never another copy on the machine
sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
from herdrlib import add_column, free_label, herdr, only_shells, space_labels  # noqa: E402

# the "new" button's workspace while its folder is chosen: herdr names it after the folder it inherits (~, or the
# active workspace's own name a second time); the picker builds the chosen folder's and closes this one
PLACEHOLDER = "new"
# in the state folder: each followed workspace's name, folder and the folder's identity (a renamed folder keeps it);
# the workspace in front and the one before it (Esc in the folder picker goes back there)
SPACES, FOCUS = "spaces.json", "focus.json"


def linked_worktree(path):
    out = subprocess.run(["git", "-C", path, "rev-parse", "--git-dir", "--git-common-dir"], capture_output=True,
                         text=True)
    dirs = [os.path.realpath(os.path.join(path, d)) for d in out.stdout.split()]
    return out.returncode == 0 and len(dirs) == 2 and dirs[0] != dirs[1]


def new_workspace(ws):
    """The "new" button's workspace: in front, with a single tab and pane, and not a git worktree's. The button always
    opens next to the existing ones: if this is the only workspace (e.g. on the very first start), it is not from the
    button."""
    workspaces = herdr("workspace", "list")["workspaces"]
    info = next((w for w in workspaces if w["workspace_id"] == ws), None)
    if len(workspaces) < 2 or not info or not info["focused"] or info["tab_count"] != 1 or info["pane_count"] != 1:
        return False
    cwd = herdr("pane", "list", "--workspace", ws)["panes"][0].get("cwd")
    return not (cwd and linked_worktree(cwd))


def identity(path):
    try:
        found = os.stat(path)
    except OSError:
        return None
    return [found.st_dev, found.st_ino]


def folders_up(path):
    while True:
        yield path
        parent = os.path.dirname(path)
        if parent == path:
            return
        path = parent


def folders_of(panes):
    """Each workspace's panes' folders."""
    cwds = {}
    for pane in panes:
        if pane.get("cwd"):
            cwds.setdefault(pane["workspace_id"], []).append(pane["cwd"])
    return cwds


def renamed_from(label, places, held):
    """The folder among PLACES that was named LABEL before it was followed: a folder of that name beside it is gone,
    and it HELD conversations."""
    if not label or os.sep in label:
        return None
    return next((up for up in places if os.path.dirname(up) != up
                 and not os.path.lexists(os.path.join(os.path.dirname(up), label))
                 and held(os.path.join(os.path.dirname(up), label))), None)


def follow_folders(workspaces, panes, known, home=None, held=lambda path: False):
    """The renames (workspace, old name, new name) for each workspace whose folder was renamed (its panes' folders went
    with it), and what is known after them. Followed: a workspace named as its folder, or as a folder beside it that is
    gone and HELD conversations (renamed before); a name given by hand ends it."""
    labels = {w["workspace_id"]: w.get("label") or "" for w in workspaces}
    cwds = folders_of(panes)
    renames, now = [], {}
    for ws, label in labels.items():
        mine, seen = cwds.get(ws, []), known.get(ws)
        if seen is None:
            places = [up for cwd in mine for up in folders_up(cwd) if identity(up)]
            folder = next((up for up in places if label in space_labels(up, home)), None)
            if folder:
                now[ws] = {"label": label, "folder": folder, "id": identity(folder)}
                continue
            folder = renamed_from(label, places, held)
            if folder is None:
                continue
            seen = {"label": label, "folder": os.path.join(os.path.dirname(folder), label), "id": identity(folder)}
        if label != seen["label"]:
            continue
        moved = None if os.path.isdir(seen["folder"]) else next(
            (up for cwd in mine for up in folders_up(cwd) if identity(up) == seen["id"]), None)
        if moved is None:                               # still there, deleted, or no pane in it now
            now[ws] = seen
            continue
        new = free_label(moved, {other for key, other in labels.items() if key != ws}, home)
        if new != label:
            renames.append((ws, label, new))
        now[ws] = {"label": new, "folder": moved, "id": seen["id"]}
    return renames, now


def gone(panes):
    """The workspaces whose panes' folders are all gone: herdr keeps naming a deleted folder as a pane's, while a
    renamed one's panes follow it."""
    return {ws for ws, mine in folders_of(panes).items() if not any(os.path.isdir(cwd) for cwd in mine)}


def held_conversations(path, home):
    """Whether Claude kept conversations for folder PATH: under ~/.claude/projects, the path with every character but
    letters and digits as -."""
    return os.path.isdir(os.path.join(home, ".claude", "projects", re.sub(r"[^A-Za-z0-9]", "-", path)))


def load(name):
    state = os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.join(
        os.path.expanduser("~"), ".local", "state", "herdr", "plugins", "herdr-fold.tab-layout")
    try:
        with open(os.path.join(state, name), encoding="utf-8") as f:
            found = json.load(f)
    except (OSError, ValueError):
        found = {}
    return state, found if isinstance(found, dict) else {}


def save(state, name, value):
    os.makedirs(state, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=state, prefix=f".{name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(value, f)
    os.replace(temporary, os.path.join(state, name))


def came_from(placeholder):
    """The workspace that was in front before PLACEHOLDER, the "new" button's (in front by now, or about to be)."""
    _, focus = load(FOCUS)
    return focus.get("before") if focus.get("now") == placeholder else focus.get("now")


def on_focus():
    """The workspace in front kept, with the one before it; a workspace whose folder is gone said deleted; each
    followed one whose folder was renamed takes its new name, and so does its main tab (named as it)."""
    workspaces = herdr("workspace", "list", check=False).get("workspaces")
    if not workspaces:                                  # herdr not answering: what is known stays
        return
    state, focus = load(FOCUS)
    front = next((w["workspace_id"] for w in workspaces if w.get("focused")), None)
    if front and focus.get("now") != front:
        save(state, FOCUS, {"now": front, "before": focus.get("now")})
    panes = herdr("pane", "list", check=False).get("panes") or []
    deleted = gone(panes)
    for space in workspaces:                            # the theme's Space rows show $folder beside the branch
        said = (space.get("tokens") or {}).get("folder") == "deleted"
        if (space["workspace_id"] in deleted) != said:
            herdr("workspace", "report-metadata", space["workspace_id"], "--source", "herdr-fold.tab-layout",
                  *(["--clear-token", "folder"] if said else ["--token", "folder=deleted"]), check=False)
    state, known = load(SPACES)
    home = os.path.expanduser("~")
    renames, now = follow_folders(workspaces, panes, known, home, lambda path: held_conversations(path, home))
    for ws, old, new in renames:
        herdr("workspace", "rename", ws, new, check=False)
        for tab in herdr("tab", "list", "--workspace", ws, check=False).get("tabs") or []:
            if tab.get("label") == old:
                herdr("tab", "rename", tab["tab_id"], new, check=False)
    if now != known:
        save(state, SPACES, now)


def main():
    if os.environ.get("HERDR_PLUGIN_EVENT") == "pane.focused":
        on_focus()
        return
    event = json.loads(os.environ.get("HERDR_PLUGIN_EVENT_JSON") or "{}")
    tab = ((event.get("data") or {}).get("tab") or {}).get("tab_id")
    if not tab:
        return
    ws = tab.split(":")[0]
    time.sleep(0.3)                              # the "new" button brings it to the front after creating it
    if os.name != "nt" and new_workspace(ws):        # no folder picker on Windows (its key handling is Unix-only)
        herdr("workspace", "rename", ws, PLACEHOLDER, check=False)    # a name it keeps does not stop the picker
        came = came_from(ws)
        herdr("plugin", "pane", "open", "--plugin", "herdr-fold.tab-layout", "--entrypoint", "new-workspace", "--focus",
              "--env", f"HERDR_NEW_WORKSPACE={ws}", *(["--env", f"HERDR_CAME_FROM={came}"] if came else []))
        return
    time.sleep(1.2)
    panes = [p for p in herdr("pane", "list", "--workspace", ws)["panes"] if p["tab_id"] == tab]
    if len(panes) != 1 or panes[0].get("label"):
        return
    pane = panes[0]
    if not only_shells(
            herdr("pane", "process-info", "--pane", pane["pane_id"])["process_info"]["foreground_processes"]):
        return
    add_column(pane["pane_id"], pane.get("cwd") or os.path.expanduser("~"))


if __name__ == "__main__":
    main()
