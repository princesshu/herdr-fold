"""New tab: a workspace from herdr's "new" button gets the folder picker (new_workspace.py) instead of the inherited
folder, unless it is a git worktree's; any other new tab gets the right-hand column. Only an empty new tab is touched
(one unnamed shell pane after 1.5 s), which skips the workspace builder's tabs and the sidebar's preview tab."""
import json
import os
import subprocess
import sys
import time

# herdrlib.py is two folders up, where the plugin is installed (and in the package): never another copy on the machine
sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
from herdrlib import add_column, herdr, only_shells  # noqa: E402

# the "new" button's workspace while its folder is chosen: herdr names it after the folder it inherits (~, or the
# active workspace's own name a second time); the picker builds the chosen folder's and closes this one
PLACEHOLDER = "new"


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


def main():
    event = json.loads(os.environ.get("HERDR_PLUGIN_EVENT_JSON") or "{}")
    tab = ((event.get("data") or {}).get("tab") or {}).get("tab_id")
    if not tab:
        return
    ws = tab.split(":")[0]
    time.sleep(0.3)                              # the "new" button brings it to the front after creating it
    if os.name != "nt" and new_workspace(ws):        # no folder picker on Windows (its key handling is Unix-only)
        herdr("workspace", "rename", ws, PLACEHOLDER, check=False)    # a name it keeps does not stop the picker
        herdr("plugin", "pane", "open", "--plugin", "herdr-fold.tab-layout", "--entrypoint", "new-workspace", "--focus",
              "--env", f"HERDR_NEW_WORKSPACE={ws}")
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
