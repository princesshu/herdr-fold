"""New tab: a workspace from herdr's "new" button gets the folder picker (new_workspace.py), unless a git worktree's;
any other new tab is left alone (its column is the dock's). On a pane's focus: the workspace in front noted, one whose
folder is gone said deleted, one holding a repository shown its branch, one named after its folder renamed with it."""
# On a workspace's close and a pane's focus the home folder's workspace is made again when none is left, and whenever
# the list of workspaces changes it is moved first when it is not (put_home). A workspace herdr ended with its last
# tab is made again in its place; one closed on purpose stays closed (spaces_changed)
import contextlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time

# herdrlib.py is two folders up, where the plugin is installed (and in the package): never another copy on the machine
sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..")))
from herdrlib import HOME_SPACE, free_label, herdr, request, space_labels  # noqa: E402

# its own copy of core/git.py (tools/build.py's), by its path: herdrlib's sidebar modules bring the sidebar's as git
SPEC = importlib.util.spec_from_file_location("workspaces_git", os.path.join(HERE, "git.py"))
git = sys.modules[SPEC.name] = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(git)

# the "new" button's workspace while its folder is chosen: herdr names it after the folder it inherits (~, or the
# active workspace's own name a second time); the picker builds the chosen folder's and closes this one
PLACEHOLDER = "new"
# in the state folder: each followed workspace's name, folder and the folder's identity (a renamed folder keeps it);
# the workspace in front and the one before it (Esc in the folder picker goes back there), with the repository each
# workspace's pane was last in and each repository's branch as last read
SPACES, FOCUS = "spaces.json", "focus.json"
# and CLOSED: each workspace's folder (herdr's close names none); what herdr said of each one that just closed, "tab"
# when its tab's close came too; the ones made again (no folder picker for them)
CLOSED = "closed.json"
# herdr's events of the list of workspaces: after each the home folder's is looked for and put first (put_home)
LISTED = ("workspace.closed", "workspace.created", "workspace.moved", "workspace.reordered")
# herdr ends a workspace with its last tab: workspace.closed with the workspace, and LAST_TAB for the same workspace
# (0.9.5; from its tab menu and key after "Close workspace?", from `herdr tab close` unasked). A workspace closed on
# purpose sends workspace.closed alone, one whose last pane moved away both, the first without the workspace
LAST_TAB = "tab.closed"
# the two events come together: what one left is the other's for RECENT seconds
RECENT = 60
# git gets GIT_WAIT seconds for a repository's branch (on each pane's focus); herdr keeps a token's first VALUE
# characters
GIT_WAIT, VALUE = 2, 80


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
    and it HELD chats."""
    if not label or os.sep in label:
        return None
    return next((up for up in places if os.path.dirname(up) != up
                 and not os.path.lexists(os.path.join(os.path.dirname(up), label))
                 and held(os.path.join(os.path.dirname(up), label))), None)


def follow_folders(workspaces, panes, known, home=None, held=lambda path: False):
    """The renames (workspace, old name, new name) for each workspace whose folder was renamed (its panes' folders went
    with it), and what is known after them. Followed: a workspace named as its folder, or as a folder beside it that is
    gone and HELD chats (renamed before); a name given by hand ends it."""
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


def held_chats(path, home):
    """Whether Claude kept chats for folder PATH: under ~/.claude/projects, the path with every character but
    letters and digits as -."""
    return os.path.isdir(os.path.join(home, ".claude", "projects", re.sub(r"[^A-Za-z0-9]", "-", path)))


def branch_row(root):
    """ROOT's branch and how far it is from its upstream, as herdr's Spaces row writes its own: "main ↑2 ↓1", the
    branch alone without an upstream or with nothing to push or pull; None on a detached HEAD (herdr shows none)."""
    branch, ahead, behind = git.tracking(root, GIT_WAIT)
    if not branch:
        return None
    status = " ".join(([f"↑{ahead}"] if ahead else []) + ([f"↓{behind}"] if behind else []))
    return f"{branch[:VALUE - len(status) - 1]} {status}" if status else branch[:VALUE]


def repo_rows(workspaces, panes, kept, home):
    """Each workspace's repo token where its folder is in no repository (else herdr's row shows its own): the branch row
    of the one inside core/git.py's repo_inside picks by its active pane and the one a pane was last in; and what is
    kept after it: {"repos": workspace → repository, "branches": repository → its stamp and row}."""
    last, read = kept.get("repos") or {}, kept.get("branches") or {}
    rows, repos, branches = {}, {}, {}
    for space in workspaces:
        ws = space["workspace_id"]
        mine = [pane for pane in panes if pane.get("workspace_id") == ws and pane.get("cwd")]
        if not mine:
            continue
        active = next((pane["cwd"] for pane in mine if pane.get("focused")
                       and pane.get("tab_id") == space.get("active_tab_id", pane.get("tab_id"))), None)
        # herdr's folder for it: its first pane's (first tab's root)
        repo = git.repo_inside(mine[0]["cwd"], active, last.get(ws), home)
        if repo is None:
            continue
        if repo in (active and git.repo_top(active), last.get(ws)):
            repos[ws] = repo
        if repo not in branches:
            stamp = git.refs_stamp(repo)
            seen = read.get(repo) or {}
            fresh = stamp is not None and seen.get("stamp") == stamp           # no stamp (past its cap): read again
            branches[repo] = seen if fresh else {"stamp": stamp, "row": branch_row(repo)}
        rows[ws] = branches[repo]["row"]
    return rows, {"repos": repos, "branches": branches}


def same_folder(one, other):
    return bool(one and other) and os.path.realpath(one) == os.path.realpath(other)


def first_folders(panes):
    """Each workspace's folder as herdr has it: its first pane's."""
    first = {}
    for pane in panes:
        first.setdefault(pane.get("workspace_id"), pane.get("cwd"))
    return first


def home_space(workspaces, panes, home):
    """The home folder's workspace: the one named HOME_SPACE (or ~, herdr's own name for it), else the first whose
    first pane (herdr's folder for a workspace) is in HOME; None when there is none."""
    first = first_folders(panes)
    named = [w for w in workspaces if w.get("label") in (HOME_SPACE, "~")]
    there = [w for w in workspaces if same_folder(first.get(w["workspace_id"]), home)]
    return next(iter(named + there), None)


def home_kept(workspaces, panes, home):
    """Whether the home folder's workspace is there and the first one."""
    found = home_space(workspaces, panes, home)
    return found is not None and found is workspaces[0]


@contextlib.contextmanager
def locked():
    """One at a time: herdr's events of one close come together, each in a process of its own."""
    import fcntl                                        # Unix only, as the events that come here
    state, _ = load(FOCUS)
    os.makedirs(state, exist_ok=True)
    with open(os.path.join(state, "home.lock"), "w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def put_home(workspaces, panes, home):
    """The home folder's workspace made again when none is left: named HOME_SPACE as its main tab, behind the one in
    front, a shell in it (the sidebar's new-tab hook gives it the right column); and moved first when it is not, the
    one in front staying there. Its id (None when it could not be made)."""
    # herdr's event of the move comes here again and finds it first, so it ends there
    found = (home_space(workspaces, panes, home) or {}).get("workspace_id")
    if home_kept(workspaces, panes, home):
        return found
    if not found:
        made = herdr("workspace", "create", "--cwd", home, "--label", HOME_SPACE, "--no-focus", check=False)
        tab = (made.get("tab") or {}).get("tab_id")
        if tab:
            herdr("tab", "rename", tab, HOME_SPACE, check=False)
            found = tab.split(":")[0]
    if found and workspaces:                            # herdr's socket API (no command moves one); alone it is first
        request("workspace.move", {"workspace_id": found, "insert_index": 0})
    return found


def panes_listed():
    return herdr("pane", "list", check=False).get("panes") or []


def note_spaces(kept, workspaces, panes, name=None, data=None):
    """KEPT (CLOSED's) after herdr's event NAME with DATA: each listed workspace's folder; a workspace no longer
    listed keeps its folder in its note, with what herdr said as it closed (its name, its place, in front or not) and
    "tab" once its tab's close came; notes and made ones older than RECENT seconds dropped."""
    folders, closed, made = (kept.setdefault(key, {}) for key in ("folders", "closed", "made"))
    now, listed = time.time(), {space["workspace_id"] for space in workspaces}
    for ws, folder in first_folders(panes).items():
        if ws in listed and folder:
            folders[ws] = folder
    for ws in [ws for ws in folders if ws not in listed]:
        closed.setdefault(ws, {"at": now})["folder"] = folders.pop(ws)
    for group in (closed, made):
        for ws in [ws for ws, seen in group.items() if now - seen["at"] > RECENT]:
            del group[ws]
    ws, space = (data or {}).get("workspace_id"), (data or {}).get("workspace")
    if not ws or ws in listed:                          # a tab closed beside another one
        return
    if name == LAST_TAB:
        closed.setdefault(ws, {"at": now})["tab"] = True
    elif name == "workspace.closed" and space and space.get("label"):
        closed.setdefault(ws, {"at": now}).update(label=space["label"], index=(space.get("number") or 1) - 1,
                                                  front=bool(space.get("focused")))


def make_again(note, count, home_id):
    """The workspace herdr ended with its last tab made again as NOTE has it, among COUNT others: its name (its main
    tab's too), its folder, its place in the list, in front when it was. Home's is put_home's (HOME_ID); one whose
    folder is gone stays closed. The id of the one made, None for none."""
    # a shell in it: the sidebar's new-tab hook gives it the right column; herdr went to a neighbour meanwhile
    made = None
    if note["label"] in (HOME_SPACE, "~"):
        ws = home_id
    elif not os.path.isdir(note["folder"]):
        return None
    else:
        tab = (herdr("workspace", "create", "--cwd", note["folder"], "--label", note["label"], "--no-focus",
                     check=False).get("tab") or {}).get("tab_id")
        if not tab:
            return None
        herdr("tab", "rename", tab, note["label"], check=False)
        ws = made = tab.split(":")[0]
        if note["index"] < count:                       # made last: the last one closed is in its place already
            request("workspace.move", {"workspace_id": ws, "insert_index": note["index"]})
    if ws and note["front"]:
        herdr("workspace", "focus", ws, check=False)
    return made


def spaces_changed(name=None, data=None, home=None):
    """After herdr's event NAME (with DATA) of the list of workspaces or of a tab's close: home kept (put_home), and
    the workspace herdr ended with its last tab made again, once both of herdr's events of it came (in any order)."""
    # herdr's events of the one made come here again and find no note of it, so it ends there
    home = home or os.path.expanduser("~")
    with locked():
        workspaces = herdr("workspace", "list", check=False).get("workspaces")
        if workspaces is None:                          # herdr not answering (stopping): nothing made
            return
        panes = panes_listed()
        state, kept = load(CLOSED)
        before = json.dumps(kept, sort_keys=True)
        note_spaces(kept, workspaces, panes, name, data)
        home_id = put_home(workspaces, panes, home)
        ws = (data or {}).get("workspace_id")
        note = kept["closed"].get(ws) or {}
        if all(key in note for key in ("folder", "label", "tab")):
            del kept["closed"][ws]
            made = make_again(note, len(workspaces), home_id)
            if made:
                kept["made"][made] = {"at": time.time()}
        if json.dumps(kept, sort_keys=True) != before:
            save(state, CLOSED, kept)


def made_again(ws):
    """Whether workspace WS is one spaces_changed made (read once it is done with it)."""
    import fcntl
    state, _ = load(CLOSED)
    try:
        with open(os.path.join(state, "home.lock"), encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            return ws in (load(CLOSED)[1].get("made") or {})
    except OSError:                                     # nothing was ever made
        return False


def load(name):
    state = os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.join(
        os.path.expanduser("~"), ".local", "state", "herdr", "plugins", "herdr-fold.workspaces")
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
    """The workspace in front kept, with the one before it; a workspace whose folder is gone said deleted, one whose
    folder holds a repository given that one's branch row; each followed one whose folder was renamed takes its new
    name, and so does its main tab (named as it)."""
    workspaces = herdr("workspace", "list", check=False).get("workspaces")
    if not workspaces:                                  # herdr not answering: what is known stays
        return
    state, focus = load(FOCUS)
    kept = dict(focus)
    front = next((w["workspace_id"] for w in workspaces if w.get("focused")), None)
    if front and focus.get("now") != front:
        kept.update(now=front, before=focus.get("now"))
    panes = panes_listed()
    home = os.path.expanduser("~")
    spaces_changed(home=home)                           # home kept, each workspace's folder noted for its close
    rows, repos = repo_rows(workspaces, panes, focus, home)
    for key, value in repos.items():
        if value:
            kept[key] = value
        else:
            kept.pop(key, None)
    if kept != focus:
        save(state, FOCUS, kept)
    deleted = gone(panes)
    for space in workspaces:                            # the theme's Space rows show $repo and $folder by the branch
        tokens = space.get("tokens") or {}
        said = tokens.get("folder") == "deleted"
        if (space["workspace_id"] in deleted) != said:
            herdr("workspace", "report-metadata", space["workspace_id"], "--source", "herdr-fold.workspaces",
                  *(["--clear-token", "folder"] if said else ["--token", "folder=deleted"]), check=False)
        row = rows.get(space["workspace_id"])
        if row != tokens.get("repo"):
            herdr("workspace", "report-metadata", space["workspace_id"], "--source", "herdr-fold.workspaces",
                  *(["--token", f"repo={row}"] if row else ["--clear-token", "repo"]), check=False)
    state, known = load(SPACES)
    renames, now = follow_folders(workspaces, panes, known, home, lambda path: held_chats(path, home))
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
    if os.environ.get("HERDR_PLUGIN_EVENT") in LISTED + (LAST_TAB,):
        spaces_changed(os.environ["HERDR_PLUGIN_EVENT"], event.get("data"))
        return
    tab = ((event.get("data") or {}).get("tab") or {}).get("tab_id")
    if not tab or os.name == "nt":               # no folder picker on Windows (its key handling is Unix-only)
        return
    ws = tab.split(":")[0]
    time.sleep(0.3)                              # the "new" button brings it to the front after creating it
    if made_again(ws) or not new_workspace(ws):
        return
    herdr("workspace", "rename", ws, PLACEHOLDER, check=False)        # a name it keeps does not stop the picker
    came = came_from(ws)
    herdr("plugin", "pane", "open", "--plugin", "herdr-fold.workspaces", "--entrypoint", "new-workspace", "--focus",
          "--env", f"HERDR_NEW_WORKSPACE={ws}", *(["--env", f"HERDR_CAME_FROM={came}"] if came else []))


if __name__ == "__main__":
    main()
