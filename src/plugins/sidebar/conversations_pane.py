"""The Conversations column's pane in every tab with a right column: --toggle collapses or opens it, --restore brings
back the tab's panes closed by hand, --closed shows the closed-pane tip once, --find opens it here with the keys.
Usage: python3 conversations_pane.py --toggle | --restore | --closed | --find | --bring TAB KIND…"""
import json
import os
import shlex
import subprocess
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import column  # noqa: E402
import panels  # noqa: E402
import statefile  # noqa: E402
from conversations import state_folder  # noqa: E402
from preview import Herdr, quote_powershell  # noqa: E402

FILE = "conversations.json"
NAME = column.CONVERSATIONS
RATIO = 0.7                   # the agent's share of what is before the right column until the column is dragged
MIN_OPEN = 32                 # the cells it opens to at least, from a rail
COLLAPSE_BELOW = 16           # the fewest cells it stays open at: dragged narrower, it collapses
TOLD = "told_closed"          # kept: the tip on a pane closed by hand was shown
SETTLE = 2.0                  # seconds a pane the plugin closes itself on the way (a column moved) takes to be back
SIDEBAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sidebar.py")


def typed(path, windows=os.name == "nt", home=os.path.expanduser("~")):
    """PATH as typed into a pane's shell, quoted: from the home folder as ~ ($HOME in PowerShell), so the line, kept in
    the shell's history, names no account."""
    sep = "\\" if windows else "/"
    inside = path.startswith(home.rstrip(sep) + sep)
    rest = path[len(home.rstrip(sep)) + 1:]
    if windows:
        if inside:                                  # in double quotes PowerShell fills in $HOME: ` " $ escaped
            return '"$HOME\\' + rest.replace("`", "``").replace('"', '`"').replace("$", "`$") + '"'
        return quote_powershell(path)
    return "~/" + shlex.quote(rest) if inside else shlex.quote(path)


def command(windows=os.name == "nt"):
    """This plugin's Conversations, with this Python (-B: no caches beside the plugin)."""
    if windows:
        return f"& {typed(sys.executable, True)} -B {typed(SIDEBAR, True)} --conversations"
    return f"{typed(sys.executable, False)} -B {typed(SIDEBAR, False)} --conversations"


def sidebar_command(windows=os.name == "nt"):
    """This plugin's sidebar, with this Python, on its pane's own folder: herdr types a pane's command into its shell,
    so a folder's name (a downloaded repository's, control characters and all) never goes there, only --cwd."""
    if windows:
        return f"& {typed(sys.executable, True)} -B {typed(SIDEBAR, True)}"
    return f"{typed(sys.executable, False)} -B {typed(SIDEBAR, False)}"


def setting(state_dir):
    try:
        with open(os.path.join(state_dir, FILE), encoding="utf-8") as f:
            kept = json.load(f)
    except (OSError, ValueError):
        return {}
    return kept if isinstance(kept, dict) else {}


def is_collapsed(state_dir):
    return setting(state_dir).get("collapsed") is True


def shows_archived(state_dir):
    return setting(state_dir).get("show_archived") is True


def keep(state_dir, **values):
    """VALUES kept in FILE, whatever else it keeps staying."""
    try:
        statefile.write(os.path.join(state_dir, FILE), {**setting(state_dir), **values})
    except OSError:
        pass


def collapse(state_dir, collapsed):
    """COLLAPSED kept for every tab's column."""
    keep(state_dir, collapsed=collapsed)


def archived(state_dir):
    """The conversations taken off the list, as "<agent>:<id>"."""
    kept = setting(state_dir).get("archived")
    return {key for key in kept if isinstance(key, str)} if isinstance(kept, list) else set()


def archive(state_dir, keys, off=True):
    """The conversations KEYS ("<agent>:<id>") off the list (OFF), or back on it; their files stay as they are."""
    keep(state_dir, archived=sorted(archived(state_dir) | keys if off else archived(state_dir) - keys))


def resumed(state_dir):
    """{pane: the conversation id reopened in it}, kept until herdr knows the pane's session."""
    kept = setting(state_dir).get("resumed")
    return {pane: id for pane, id in kept.items() if isinstance(id, str)} if isinstance(kept, dict) else {}


def resume(state_dir, pane, id):
    """PANE noted as reopening the conversation ID."""
    keep(state_dir, resumed={**resumed(state_dir), pane: id})


def build(call, pane, cwd, state_dir, run=None, sidebar_run=None, scope=""):
    """Both columns right of PANE, as wide as in the other tabs: this one, then the right column (the sidebar above a
    terminal), noted as the tab's (panels.py: SCOPE, a machine's name, or this one); the sidebar's pane id. RUN,
    SIDEBAR_RUN: the panes' commands (else this plugin's)."""
    where = ["--cwd", cwd] if cwd else []
    before = column.saved(state_dir) or column.RIGHT              # the share before the right column
    agent = column.saved(state_dir, FILE) or RATIO
    mine = before * (1 - agent)
    made = call("pane", "split", "--pane", pane, "--direction", "right", "--ratio", f"{before * agent:.4g}", *where,
                "--no-focus")["pane"]
    new = made["pane_id"]
    side = call("pane", "split", "--pane", new, "--direction", "right", "--ratio", f"{mine / (mine + 1 - before):.4g}",
                *where, "--no-focus")["pane"]["pane_id"]
    term = call("pane", "split", "--pane", side, "--direction", "down", "--ratio", "0.5", *where,
                "--no-focus")["pane"]["pane_id"]
    call("pane", "rename", side, column.SIDEBAR)
    call("pane", "rename", term, "terminal")
    call("pane", "rename", new, NAME)
    call("pane", "run", side, sidebar_run or sidebar_command())
    call("pane", "run", new, run or command())
    if made.get("tab_id"):
        panels.note(state_dir, {made["tab_id"]: set(panels.KINDS)}, scope)
    return side


def insert(call, sidebar, cwd, state_dir, run=None, sidebar_run=None, scope=""):
    """The column right before the right column whose top is SIDEBAR: beside the terminal under it, the sidebar
    started again above that (a pane can only be split, so the column cannot be put beside both at once); beside the
    sidebar itself without a terminal; noted as the tab's. Its widths: the column sets them once it runs."""
    where = ["--cwd", cwd] if cwd else []
    below = (call("pane", "neighbor", "--pane", sidebar, "--direction", "down").get("neighbor") or {})
    below = below.get("neighbor_pane_id")
    height = 0.5
    if below:
        shown = {p["pane_id"]: p["rect"] for p in call("pane", "layout", "--pane", sidebar)["layout"]["panes"]}
        if sidebar in shown and below in shown:
            height = shown[sidebar]["height"] / max(1, shown[sidebar]["height"] + shown[below]["height"])
        call("pane", "close", sidebar)
    anchor = below or sidebar
    agent = column.saved(state_dir, FILE) or RATIO
    before = column.saved(state_dir) or column.RIGHT
    mine = before * (1 - agent)
    made = call("pane", "split", "--pane", anchor, "--direction", "right", "--ratio",
                f"{mine / (mine + 1 - before):.4g}", *where, "--no-focus")["pane"]
    new = made["pane_id"]
    call("pane", "swap", "--source-pane", anchor, "--target-pane", new)          # the column first, on the left
    call("pane", "rename", new, NAME)
    call("pane", "run", new, run or command())
    if below:
        side = call("pane", "split", "--pane", below, "--direction", "down", "--ratio", f"{height:.4g}", *where,
                    "--no-focus")["pane"]["pane_id"]
        call("pane", "swap", "--source-pane", below, "--target-pane", side)      # the sidebar on top again
        call("pane", "rename", side, column.SIDEBAR)
        call("pane", "run", side, sidebar_run or sidebar_command())
    if made.get("tab_id"):
        panels.note(state_dir, {made["tab_id"]: {NAME}}, scope)
    return new


def places(call):
    """{tab: [its sidebar, its folder, its Conversations pane or None]} for every tab that has a right column."""
    panes = call("pane", "list").get("panes") or []
    found = {p["tab_id"]: [p["pane_id"], p.get("cwd"), None] for p in panes if p.get("label") == column.SIDEBAR}
    for pane in panes:
        if pane.get("label") == NAME and pane.get("tab_id") in found:
            found[pane["tab_id"]][2] = pane["pane_id"]
    return found


def ensure(call, state_dir, run=None, sidebar_run=None, keep=(), scope=""):
    """The column in every tab that has a right column but not it yet (one closed by hand stays closed); how many got
    it. RUN, SIDEBAR_RUN: the panes' commands for a folder, else this plugin's; KEEP: sidebar panes running another
    program, whose tabs are left alone, as is a tab herdr refuses a step in. SCOPE: a machine's name, or this one."""
    added = 0
    for tab, (sidebar, cwd, present) in places(call).items():
        if sidebar in keep or present or NAME in panels.had(state_dir, tab, scope):
            continue
        try:
            insert(call, sidebar, cwd, state_dir, run(cwd) if run else None,
                   sidebar_run(cwd) if sidebar_run else None, scope)
        except (RuntimeError, KeyError):
            continue
        added += 1
    return added


def bring(call, tab, kinds, state_dir, run=None, sidebar_run=None, scope=""):
    """The KINDS (panels.KINDS) TAB lacks, back in it and noted as the tab's: the whole layout where none is left, else
    each in its place. RUN, SIDEBAR_RUN: the panes' commands for a folder (else this plugin's). Which came back."""
    panes = [p for p in call("pane", "list").get("panes") or [] if p.get("tab_id") == tab]
    mine = {p["label"]: p["pane_id"] for p in panes if p.get("label") in panels.KINDS}
    others = [p["pane_id"] for p in panes if p.get("label") not in panels.KINDS]
    cwd = next((p.get("cwd") for p in panes if p.get("cwd")), None)
    runs = (run(cwd) if run else command(),
            sidebar_run(cwd) if sidebar_run else sidebar_command())
    wanted = set(kinds) - set(mine)
    side, term, conv = (mine.get(kind) for kind in panels.KINDS)
    if wanted >= {"sidebar", "terminal", NAME} and not mine and others:
        build(call, others[0], cwd, state_dir, *runs, scope)
        return wanted
    brought = set()
    if not side and not term and wanted & {"sidebar", "terminal"} and (conv or others):
        before = column.saved(state_dir) or column.RIGHT
        agent = column.saved(state_dir, FILE) or RATIO
        share = before * (1 - agent) / (before * (1 - agent) + 1 - before) if conv else before
        side = panels.show_column(call, conv or others[0], cwd, runs[1], share)
        brought |= {"sidebar", "terminal"}
    if "sidebar" in wanted and not side and term:
        side = panels.show_sidebar(call, term, cwd, runs[1])
        brought.add("sidebar")
    if "terminal" in wanted and side and "terminal" not in brought and not term:
        panels.show_terminal(call, side, cwd)
        brought.add("terminal")
    if NAME in wanted and not conv and side:
        insert(call, side, cwd, state_dir, *runs, scope)
        brought.add(NAME)
    panels.note(state_dir, {tab: brought}, scope)
    return brought


def bring_apart(tab, kinds):
    """bring() for TAB's KINDS in a process of its own, apart from the pane that asks (a menu's): bringing the
    Conversations column back closes the sidebar and starts it again above the terminal, and the work must not end
    with the sidebar's process."""
    apart = ({"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
             else {"start_new_session": True})
    subprocess.Popen([sys.executable, "-B", os.path.abspath(__file__), "--bring", tab, *sorted(kinds)],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **apart)


def toggle(call, state_dir, run=None, sidebar_run=None):
    """Collapsed in every tab, or open again; a column closed by hand in the tab the key is pressed in comes back
    there, open. Whether it is collapsed now."""
    found = places(call)
    here = (call("pane", "current").get("pane") or {}).get("tab_id")
    if here in found and not found[here][2]:
        bring(call, here, {NAME}, state_dir, run, sidebar_run)
        collapse(state_dir, False)
        return False
    collapse(state_dir, not is_collapsed(state_dir))
    return is_collapsed(state_dir)


def restore(call, state_dir, run=None, sidebar_run=None):
    """Restore panels: every pane of the plugin's (panels.KINDS) the tab the key is pressed in lacks, back, and the tab
    shown whole (Cmd+Shift+E hides the right column by zooming the agent). Which came back."""
    here = (call("pane", "current").get("pane") or {}).get("tab_id")
    if not here:
        return set()
    layouts = call("api", "snapshot").get("snapshot", {}).get("layouts") or []
    shown = next((tab for tab in layouts if tab.get("tab_id") == here), {})
    if shown.get("zoomed"):
        call("pane", "zoom", shown["focused_pane_id"], "--toggle")
    return bring(call, here, panels.KINDS, state_dir, run, sidebar_run)


def find(call, state_dir, focus, run=None, sidebar_run=None):
    """Cmd+Shift+R: the column of the tab the key is pressed in (else the workspace's main tab's) given the keys, its
    filter empty; opened in every tab where collapsed, back where closed by hand. FOCUS(pane) gives the keys (herdr's
    command line focuses only by direction). The pane, or None in a workspace without a right column."""
    found = places(call)
    tab = (call("pane", "current").get("pane") or {}).get("tab_id")
    if tab not in found:                                    # herdr's tab ids start with their workspace's
        tab = next((other for other in found if other.split(":")[0] == str(tab).split(":")[0]), None)
    if tab is None:
        return None
    mine = found[tab][2]
    if mine:
        call("pane", "send-keys", mine, "esc")              # one brought back starts with an empty filter anyway
    else:
        bring(call, tab, {NAME}, state_dir, run, sidebar_run)
        mine = places(call).get(tab, [None, None, None])[2]
    collapse(state_dir, False)
    if mine:
        focus(mine)
    return mine


def restore_hint():
    """How closed panels come back: herdr-fold's key (Cmd+Shift+O) where herdr's config binds Restore panels to one, or
    the menus that always have it (the sidebar's ⋯, a right click) where the sidebar is installed alone."""
    try:
        with open(os.path.expanduser("~/.config/herdr/config.toml"), encoding="utf-8") as f:
            bound = "conversations_pane.py --restore" in f.read()
    except OSError:
        bound = False
    return "Cmd+Shift+O brings them back" if bound else "Restore panels in the ⋯ or right-click menu brings them back"


def tell(call, state_dir, workspace, wait=time.sleep):
    """A pane closed in WORKSPACE (herdr's pane.closed): the first time a tab there lacks one of the plugin's panes it
    has had, closed by hand, herdr says how they come back; never again. Whether it said so."""
    if setting(state_dir).get(TOLD) or not workspace:
        return False
    wait(SETTLE)
    tabs = {}
    for pane in call("pane", "list").get("panes") or []:
        if pane.get("workspace_id") == workspace:
            tabs.setdefault(pane["tab_id"], set()).add(pane.get("label"))
    if not any(panels.closed(state_dir, tab, labels) for tab, labels in tabs.items()):
        return False
    call("notification", "show", "Closed panels stay closed in their tab", "--body", restore_hint())
    keep(state_dir, **{TOLD: True})
    return True


if __name__ == "__main__":
    if sys.argv[1:] not in (["--toggle"], ["--restore"], ["--closed"], ["--find"]) and not (
            sys.argv[1:2] == ["--bring"] and len(sys.argv) > 3 and set(sys.argv[3:]) <= set(panels.KINDS)):
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)
    try:
        if sys.argv[1] == "--closed":                       # herdr runs it in the closed pane's workspace
            tell(Herdr().call, state_folder(), os.environ.get("HERDR_WORKSPACE_ID"))
        elif sys.argv[1] == "--find":
            find(Herdr().call, state_folder(), lambda mine: column.call("pane.focus", {"pane_id": mine}))
        elif sys.argv[1] == "--bring":
            bring(Herdr().call, sys.argv[2], set(sys.argv[3:]), state_folder())
        else:
            (toggle if sys.argv[1] == "--toggle" else restore)(Herdr().call, state_folder())
    except (RuntimeError, OSError) as err:
        print(f"Conversations: {err}", file=sys.stderr)
        sys.exit(1)
