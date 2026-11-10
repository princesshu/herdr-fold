"""The plugin's panes in every tab with a right column (the sidebar above a terminal): --restore brings back the tab's
panes closed by hand, --closed shows the closed-pane tip once.
Usage: python3 panes.py --restore | --closed"""
import os
import shlex
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import column  # noqa: E402
import panels  # noqa: E402
from conversations import keep, setting, state_folder  # noqa: E402
from preview import Herdr, quote_powershell  # noqa: E402

SETTLE = 2.0                  # seconds a pane the plugin closes itself on the way takes to be back
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


def sidebar_command(windows=os.name == "nt"):
    """This plugin's sidebar, with this Python, on its pane's own folder: herdr types a pane's command into its shell,
    so a folder's name (a downloaded repository's, control characters and all) never goes there, only --cwd."""
    if windows:
        return f"& {typed(sys.executable, True)} -B {typed(SIDEBAR, True)}"
    return f"{typed(sys.executable, False)} -B {typed(SIDEBAR, False)}"


def resumed(state_dir):
    """{pane: the conversation id reopened in it}, kept until herdr knows the pane's session."""
    kept = setting(state_dir).get("resumed")
    return {pane: id for pane, id in kept.items() if isinstance(id, str)} if isinstance(kept, dict) else {}


def resume(state_dir, pane, id):
    """PANE noted as reopening the conversation ID."""
    keep(state_dir, resumed={**resumed(state_dir), pane: id})


def build(call, pane, cwd, state_dir, sidebar_run=None, scope=""):
    """The right column right of PANE, as wide as in the other tabs: the sidebar above a terminal, noted as the tab's
    (panels.py: SCOPE, a machine's name, or this one); the sidebar's pane id. SIDEBAR_RUN: its command (else this
    plugin's)."""
    share = column.saved(state_dir) or column.RIGHT
    side = panels.show_column(call, pane, cwd, sidebar_run or sidebar_command(), share)
    tab = (call("pane", "get", side).get("pane") or {}).get("tab_id")
    if tab:
        panels.note(state_dir, {tab: set(panels.KINDS)}, scope)
    return side


def bring(call, tab, kinds, state_dir, sidebar_run=None, scope=""):
    """The KINDS (panels.KINDS) TAB lacks, back in it and noted as the tab's: the whole column where neither is left,
    else each in its place. SIDEBAR_RUN: the sidebar's command for a folder (else this plugin's). Which came back."""
    found = [p for p in call("pane", "list").get("panes") or [] if p.get("tab_id") == tab]
    mine = {p["label"]: p["pane_id"] for p in found if p.get("label") in panels.KINDS}
    others = [p["pane_id"] for p in found if p.get("label") not in panels.KINDS]
    cwd = next((p.get("cwd") for p in found if p.get("cwd")), None)
    run = sidebar_run(cwd) if sidebar_run else sidebar_command()
    wanted, side, term = set(kinds) - set(mine), mine.get("sidebar"), mine.get("terminal")
    brought = set()
    if not side and not term and wanted and others:
        side = build(call, others[0], cwd, state_dir, run, scope)
        brought |= set(panels.KINDS)
    if "sidebar" in wanted and not side and term:
        side = panels.show_sidebar(call, term, cwd, run)
        brought.add("sidebar")
    if "terminal" in wanted and side and "terminal" not in brought and not term:
        panels.show_terminal(call, side, cwd)
        brought.add("terminal")
    panels.note(state_dir, {tab: brought}, scope)
    return brought


def restore(call, state_dir, sidebar_run=None):
    """Restore panels: every pane of the plugin's (panels.KINDS) the tab the key is pressed in lacks, back, and the tab
    shown whole (Cmd+Shift+E hides the right column by zooming the agent). Which came back."""
    here = (call("pane", "current").get("pane") or {}).get("tab_id")
    if not here:
        return set()
    layouts = call("api", "snapshot").get("snapshot", {}).get("layouts") or []
    shown = next((tab for tab in layouts if tab.get("tab_id") == here), {})
    if shown.get("zoomed"):
        call("pane", "zoom", shown["focused_pane_id"], "--toggle")
    return bring(call, here, panels.KINDS, state_dir, sidebar_run)


def restore_hint():
    """How closed panels come back: herdr-fold's key (Cmd+Shift+O) where herdr's config binds Restore panels to one, or
    the menus that always have it (the sidebar's ⋯, a right click on a head) where the sidebar is installed alone."""
    try:
        with open(os.path.expanduser("~/.config/herdr/config.toml"), encoding="utf-8") as f:
            bound = "herdr-fold.sidebar.restore-panels" in f.read()
    except OSError:
        bound = False
    return "Cmd+Shift+O brings them back" if bound else "Restore panels in the ⋯ or right-click menu brings them back"


def tell(call, state_dir, workspace, wait=time.sleep):
    """A pane closed in WORKSPACE (herdr's pane.closed): the first time a tab there lacks one of the plugin's panes it
    has had, closed by hand, herdr says how they come back; never again. Whether it said so."""
    if setting(state_dir).get("told_closed") or not workspace:
        return False
    wait(SETTLE)
    tabs = {}
    for pane in call("pane", "list").get("panes") or []:
        if pane.get("workspace_id") == workspace:
            tabs.setdefault(pane["tab_id"], set()).add(pane.get("label"))
    if not any(panels.closed(state_dir, tab, labels) for tab, labels in tabs.items()):
        return False
    call("notification", "show", "Closed panels stay closed in their tab", "--body", restore_hint())
    keep(state_dir, told_closed=True)
    return True


if __name__ == "__main__":
    if sys.argv[1:] not in (["--restore"], ["--closed"]):
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)
    try:
        if sys.argv[1] == "--closed":                       # herdr runs it in the closed pane's workspace
            tell(Herdr().call, state_folder(), os.environ.get("HERDR_WORKSPACE_ID"))
        else:
            restore(Herdr().call, state_folder())
    except (RuntimeError, OSError) as err:
        print(f"Panels: {err}", file=sys.stderr)
        sys.exit(1)
