"""The plugin's panes in every tab with a right column (the sidebar above a terminal, which the dock's rail puts under
the agent): --restore brings back the tab's panes closed by hand, --closed shows the closed-pane tip once, --new-tab
lays out a new tab, --startup brings them back. Usage: python3 panes.py --restore | --closed | --new-tab | --startup"""
import json
import os
import re
import shlex
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import column  # noqa: E402
import panels  # noqa: E402
from conversations import KEPT, change, keep, setting, state_folder  # noqa: E402
from preview import Herdr, quote_powershell  # noqa: E402

SETTLE = 2.0                  # seconds a pane the plugin closes itself on the way takes to be back
SIDEBAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sidebar.py")
NEW_TAB = 1.5                 # seconds a new tab is left to whatever made it: a builder names its pane or runs in it
# Workspaces' name for the "new" button's workspace while its folder is chosen: the picker builds the chosen folder's
# workspace and closes this one
PLACEHOLDER = "new"
AGENTS = ("claude", "codex")  # the agents herdr-fold starts (`herdr agent start NAME`), each beside a right column
# The shells a pane can run with nothing else in its foreground (Unix and Windows)
SHELLS = {"zsh", "bash", "sh", "dash", "fish", "ksh", "nu", "pwsh", "powershell", "cmd"}
# At startup herdr is still running its own `claude --resume` commands (those without a conversation exit after a few
# seconds): a pane is decided about only once its state is the same over this many consecutive checks (every POLL s).
STEADY, POLL, STARTUP_LIMIT = 3, 2, 120


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


def program_names(processes):
    """The plain names of a pane's foreground programs: no folder, no .exe, no login dash, lowercase."""
    return [re.sub(r"(?i)\.exe$", "", p["name"].replace("\\", "/").split("/")[-1]).lstrip("-").lower()
            for p in processes]


def only_shells(processes):
    """True if nothing but a shell runs in the pane's foreground (Unix: -zsh; Windows: pwsh.exe / cmd.exe)."""
    names = program_names(processes)
    return bool(names) and all(n in SHELLS for n in names)


def on_windows(cwd=None):
    """Whether a pane in folder CWD is on a Windows machine: this machine itself, or a connected machine's C:\\… style
    folder."""
    return os.name == "nt" or bool(re.match(r"^[A-Za-z]:[\\/]", cwd or ""))


def asked(call, *args):
    """herdr's answer to ARGS, {} if it gives none (an error)."""
    try:
        return call(*args)
    except RuntimeError:
        return {}


def state_of(call, pane):
    """"shell", the names of the foreground programs, or None if the pane has not started yet."""
    info = asked(call, "pane", "process-info", "--pane", pane["pane_id"])
    processes = (info.get("process_info") or {}).get("foreground_processes") or []
    names = program_names(processes)
    return ("shell" if only_shells(processes) else ",".join(names)) if names else None


def resumed(state_dir):
    """{pane: the conversation id reopened in it}, kept until herdr knows the pane's session."""
    return reopened(setting(state_dir))


def reopened(kept):
    """resumed() in what conversations.json KEPT."""
    found = kept.get("resumed")
    return {pane: id for pane, id in found.items() if isinstance(id, str)} if isinstance(found, dict) else {}


def resume(state_dir, pane, id):
    """PANE noted as reopening the conversation ID."""
    change(state_dir, lambda kept: {**kept, "resumed": {**reopened(kept), pane: id}})


def build(call, pane, cwd, state_dir, sidebar_run=None, scope=""):
    """The right column right of PANE, as wide as in the other tabs: the sidebar above a terminal (on the dock's rail,
    the rail, the terminal under PANE), noted as the tab's (panels.py: SCOPE, a machine's name, or this one); the
    sidebar's pane id. SIDEBAR_RUN: its command (else this plugin's)."""
    run = sidebar_run or sidebar_command()
    if column.railed(state_dir) and not scope:                  # the sidebar then sets the rail's width to the cell
        side = panels.show_rail(call, pane, cwd, run, column.SPLIT[1])
    else:
        side = panels.show_column(call, pane, cwd, run, column.saved(state_dir) or column.RIGHT)
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
    rail = bool(others) and not scope and column.railed(state_dir)        # the terminal under the agent, then
    brought = set()
    if not side and not term and wanted and others:
        side = build(call, others[0], cwd, state_dir, run, scope)
        brought |= set(panels.KINDS)
    if "sidebar" in wanted and not side and term:
        side = rail_beside(call, others[0], cwd, run) if rail and not held(term) else panels.show_sidebar(
            call, term, cwd, run)
        brought.add("sidebar")
    if "terminal" in wanted and side and "terminal" not in brought and not term:
        panels.show_terminal(call, others[0] if rail else side, cwd)
        brought.add("terminal")
    panels.note(state_dir, {tab: brought}, scope)
    return brought


def held(pane):
    """Whether PANE, the terminal, stands in a right column, as the open dock has it; not when herdr cannot say."""
    found = column.layout(pane)
    return bool(found) and column.columns(found, "terminal") is not None


def rail_beside(call, agent, cwd, run):
    """The sidebar back as the dock's rail right of AGENT, the terminal set under the agent before the sidebar runs:
    nothing moves while it starts. Its pane id."""
    side = panels.split(call, agent, "right", column.SPLIT[1], cwd)
    call("pane", "rename", side, "sidebar")
    place_terminal(call, side, True)
    call("pane", "run", side, run)
    return side


def place_terminal(call, pane, rail):
    """The terminal of PANE's tab (PANE: its sidebar) under the agent while the dock is a RAIL, else back under the
    sidebar, as many rows tall: through a new tab, as herdr moves no pane inside its own; its program runs on, its pane
    id kept. Whether it moved; RuntimeError when herdr refused."""
    found = column.layout(pane)
    tab = column.columns(found) if found else None
    root = (found or {}).get("root") or {}
    path = column.find(root, "terminal")
    if tab is None or not path or path[:len(tab.outer) + 1] == tab.outer + [not rail]:
        return False                                # none, or where it goes already: the agent's side, or the column
    parent = column.at(root, path[:-1])
    ratio = float(parent.get("ratio", 0.5)) if parent.get("direction") == "down" else 0.5
    tall = 1 - ratio if path[-1] else ratio                         # its share of the rows
    beside = column.at(root, tab.outer + [False]) if rail else column.at(root, column.find(root, column.SIDEBAR))
    terminal = column.at(root, path).get("pane_id")
    moved = call("pane", "move", terminal, "--new-tab", "--no-focus")
    terminal = ((moved.get("move_result") or {}).get("pane") or {}).get("pane_id") or terminal
    call("pane", "move", terminal, "--tab", tab.tab, "--target-pane", column.panes(beside)[0], "--split", "down",
         "--ratio", f"{1 - tall:.4g}", "--no-focus")
    return True


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


def picking(call, workspace):
    """Whether WORKSPACE is the "new" button's with Workspaces' folder picker open: named PLACEHOLDER, one tab, one
    pane."""
    info = next((w for w in call("workspace", "list").get("workspaces") or [] if w.get("workspace_id") == workspace),
                None)
    return bool(info) and info.get("label") == PLACEHOLDER and info.get("tab_count") == info.get("pane_count") == 1


def new_tab(call, event, state_dir, wait=time.sleep):
    """herdr's tab.created (EVENT): a new tab still one unnamed pane running only a shell after NEW_TAB s (no builder's
    or preview tab) gets the right column, on every system, but for the "new" button's workspace while Workspaces'
    picker is open in it. The sidebar's pane id, or None."""
    tab = ((event.get("data") or {}).get("tab") or {}).get("tab_id")
    if not tab:
        return None
    workspace = tab.split(":")[0]
    wait(NEW_TAB)
    found = [p for p in call("pane", "list", "--workspace", workspace).get("panes") or [] if p.get("tab_id") == tab]
    if len(found) != 1 or found[0].get("label") or state_of(call, found[0]) != "shell" or picking(call, workspace):
        return None
    return build(call, found[0]["pane_id"], found[0].get("cwd") or os.path.expanduser("~"), state_dir)


def when_steady(call, starting, look, act):
    """ACT(pane, what) once on each (pane, what) LOOK() lists that runs only a shell; at herdr's start (STARTING) only
    once its state has stayed the same over STEADY looks, POLL s apart, for at most STARTUP_LIMIT s. LOOK runs each
    round."""
    seen, done = {}, set()
    deadline = time.time() + (STARTUP_LIMIT if starting else 0)
    while True:
        waiting = False
        for pane, what in look():
            if pane["pane_id"] in done:
                continue
            state = state_of(call, pane)
            if starting and state == "shell" and pane.get("agent_session"):
                state = "resuming"                                  # herdr may still resume the conversation in it
            history = seen.setdefault(pane["pane_id"], [])
            history.append(state)
            if starting and (state in (None, "resuming") or history[-STEADY:] != [state] * STEADY):
                waiting = True
                continue
            done.add(pane["pane_id"])
            if state == "shell":                                    # running already: left as it is
                act(pane, what)
        if not waiting or time.time() > deadline:
            return
        time.sleep(POLL)


def old_column(call, pane):
    """Whether PANE, named "conversations", is an older install's column: Python's (sidebar.py --conversations), the
    shell it left, or not started yet; never an agent's pane named so by hand."""
    state = state_of(call, pane)
    return state in (None, "shell") or all(name.startswith("python") for name in state.split(","))


def gone(call, workspaces, state_dir, local, say):
    """An install from before: each tab's Conversations column closed, its list in the sidebar now; on this machine
    (LOCAL: herdr's socket is this one's) the right column, which took its room, as wide as remembered again, and
    what the column kept (its width, its fold) gone from conversations.json."""
    right = 1 - (column.saved(state_dir) or column.RIGHT)          # before a sidebar takes the new width as chosen
    if local and set(setting(state_dir)) - set(KEPT):
        keep(state_dir)
    for ws, label in workspaces:
        found = asked(call, "pane", "list", "--workspace", ws).get("panes") or []
        old = {p["pane_id"]: p["tab_id"] for p in found if p.get("label") == "conversations" and old_column(call, p)}
        for pane in old:
            asked(call, "pane", "close", pane)
        if not old:
            continue
        say("ok", "column_gone", label)
        for pane in found if local else ():
            tab = column.read(pane["pane_id"]) if pane.get("label") == "sidebar" and pane["tab_id"] in old.values() \
                else None
            if tab:
                column.arrange(tab, right=right)


def restore_all(call, state_dir, sidebar_run=None, scope="", starting=False, say=lambda *told: None):
    """Every tab's right column back at herdr's start (STARTING), or for restore_panes.py (SCOPE: a connected machine,
    through its CALL): what a tab never lost by hand, a lone started agent's, herdr's first shell's, an empty sidebar.
    SAY(mark, what, workspace, *details) tells each move; SIDEBAR_RUN as in bring()."""
    run = sidebar_run or (lambda cwd: sidebar_command())
    workspaces = [(w["workspace_id"], w.get("label") or "") for w in call("workspace", "list").get("workspaces") or []]
    gone(call, workspaces, state_dir, not scope, say)
    columned = set()

    def look():
        """The tabs' missing panes back; the panes to start the sidebar or the whole column in, once steady."""
        started = {a["pane_id"] for a in asked(call, "agent", "list").get("agents") or []
                   if a.get("name") and a.get("agent") in AGENTS}
        listed = {ws: asked(call, "pane", "list", "--workspace", ws).get("panes") or [] for ws, _ in workspaces}
        fresh = sum(map(len, listed.values())) == 1               # herdr's very first workspace, nothing else yet
        decide = []
        for ws, label in workspaces:
            found = listed[ws]
            alone = {p["pane_id"] for p in found if sum(q["tab_id"] == p["tab_id"] for q in found) == 1}
            with_terminal = {p["tab_id"] for p in found if p.get("label") == "terminal"}
            with_sidebar = {p["tab_id"] for p in found if p.get("label") == "sidebar"}
            for pane in found:
                name, cwd, tab = pane.get("label") or "", pane.get("cwd"), pane["tab_id"]
                had = panels.had(state_dir, tab, scope)             # what the tab has had: closed by hand stays
                # a column whose sidebar was never there gets one above the terminal; the terminal keeps what runs
                # in it (split below it, then swapped)
                if name == "terminal" and tab not in with_sidebar and "sidebar" not in had:
                    with_sidebar.add(tab)
                    try:
                        panels.show_sidebar(call, pane["pane_id"], cwd, run(cwd))
                        say("ok", "sidebar_back", label)
                    except (RuntimeError, KeyError) as err:
                        say("warn", "sidebar_back_failed", label, err)
                if name == "sidebar" and tab not in with_terminal and "terminal" not in had:
                    with_terminal.add(tab)
                    try:
                        panels.show_terminal(call, pane["pane_id"], cwd)
                        say("ok", "terminal_added", label)
                    except (RuntimeError, KeyError) as err:
                        say("warn", "terminal_failed", label, err)
                # a started agent alone in its tab, running or not, gets the column, unless it was closed by hand
                if pane["pane_id"] in alone and pane["pane_id"] in started and pane["pane_id"] not in columned \
                        and not had:
                    columned.add(pane["pane_id"])
                    try:
                        build(call, pane["pane_id"], cwd, state_dir, run(cwd), scope)
                        say("ok", "column_next_to", label, name)
                    except RuntimeError as err:
                        say("warn", "column_failed", label, err)
                role = None if pane["pane_id"] in started else "column" if fresh and not name else name
                # herdr on Windows names only the shell for a program that is not an agent: the sidebar may be
                # running there, so nothing is typed into it but at herdr's start (every pane a fresh shell then)
                if role == "column" or role == "sidebar" and (starting or not on_windows(cwd)):
                    decide.append((pane, (label, role)))
        return decide

    def act(pane, what):
        label, role = what
        cwd = pane.get("cwd")
        try:
            if role == "column":
                build(call, pane["pane_id"], cwd, state_dir, run(cwd), scope)
            else:
                call("pane", "run", pane["pane_id"], run(cwd))
            say("ok", "done", label, role)
        except RuntimeError as err:
            say("warn", "start_failed", label, role, err)

    when_steady(call, starting, look, act)
    # what each tab has now, kept: a pane closed by hand from here on stays closed
    now = [pane for ws, _ in workspaces for pane in asked(call, "pane", "list", "--workspace", ws).get("panes") or []]
    panels.note(state_dir, panels.present(now), scope, {p["tab_id"] for p in now})


if __name__ == "__main__":
    if sys.argv[1:] not in (["--restore"], ["--closed"], ["--new-tab"], ["--startup"]):
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)
    try:
        if sys.argv[1] == "--closed":                       # herdr runs it in the closed pane's workspace
            tell(Herdr().call, state_folder(), os.environ.get("HERDR_WORKSPACE_ID"))
        elif sys.argv[1] == "--new-tab":                    # herdr's tab.created, the event in the environment
            new_tab(Herdr().call, json.loads(os.environ.get("HERDR_PLUGIN_EVENT_JSON") or "{}"), state_folder())
        elif sys.argv[1] == "--startup":                    # herdr's [[startup]], the session restored
            restore_all(Herdr().call, state_folder(), starting=True)
        else:
            restore(Herdr().call, state_folder())
    except (RuntimeError, OSError, ValueError) as err:
        print(f"Panels: {err}", file=sys.stderr)
        sys.exit(1)
