"""The plugin's panes in a tab: the sidebar above a terminal (the right column). What a tab has had is kept in
panels.json, so a pane closed by hand stays closed until the user brings it back; one it never had may be put in. A
connected machine's tabs are kept apart under its name (SCOPE)."""
import os

import statefile

FILE = "panels.json"
KINDS = ("sidebar", "terminal")               # as on screen: top to bottom
RESTORE = "Restore panels"


def menu(present):
    """The sidebar's own menu's lines for a tab with the PRESENT kinds: each other pane, by its name in herdr, closed or
    shown back, in screen order; Restore panels while any is closed."""
    lines = [f"{'Close' if kind in present else 'Show'} {kind}" for kind in KINDS if kind != "sidebar"]
    return lines + ([RESTORE] if set(KINDS) - set(present) else [])


def chosen(line, present):
    """What a menu LINE asks for in a tab with the PRESENT kinds: ("close", kind), ("show", {kinds}), or None (not a
    panes' line)."""
    if line == RESTORE:
        return "show", set(KINDS) - set(present)
    what, _, name = line.partition(" ")
    kind = name if name in KINDS else None
    if what == "Close" and kind:
        return "close", kind
    return ("show", {kind}) if what == "Show" and kind else None


def close(call, tab, kind):
    """TAB's pane of KIND closed, as by hand (it stays closed, panels.json)."""
    pane = next((p["pane_id"] for p in call("pane", "list").get("panes") or []
                 if p.get("tab_id") == tab and p.get("label") == kind), None)
    if pane:
        call("pane", "close", pane)


def key(tab, scope=""):
    return f"{scope}/{tab}" if scope else tab


def load(state_dir):
    return loaded(statefile.read(os.path.join(state_dir, FILE)))


def loaded(kept):
    """{tab: the kinds it has had} in what FILE KEPT."""
    return {name: set(kinds) & set(KINDS) for name, kinds in kept.items() if isinstance(kinds, list)}


def had(state_dir, tab, scope=""):
    """The kinds TAB has had."""
    return load(state_dir).get(key(tab, scope), set())


def note(state_dir, present, scope="", tabs=None):
    """PRESENT ({tab: kinds it has now}) added to what each tab has had; with TABS (every tab there is in SCOPE now),
    the tabs gone forgotten; on what FILE holds then (statefile.update: every tab's sidebar writes it)."""
    def noted(found):
        kept = loaded(found)
        for tab, kinds in present.items():
            known = {kind for kind in kinds if kind in KINDS}
            if known:
                kept.setdefault(key(tab, scope), set()).update(known)
        if tabs is not None:
            alive = {key(tab, scope) for tab in tabs}
            kept = {name: kinds for name, kinds in kept.items()
                    if name in alive or (name.split("/", 1)[0] if "/" in name else "") != scope}
        return {name: sorted(kinds) for name, kinds in sorted(kept.items())}

    try:
        statefile.update(os.path.join(state_dir, FILE), noted)
    except OSError:
        pass


def present(panes):
    """{tab: the plugin's kinds it has} of PANES (herdr's pane list)."""
    found = {}
    for pane in panes:
        found.setdefault(pane["tab_id"], set())
        if pane.get("label") in KINDS:
            found[pane["tab_id"]].add(pane["label"])
    return found


def closed(state_dir, tab, kinds, scope=""):
    """Of the KINDS TAB has now, the ones it has had but lacks: closed by hand, left closed."""
    return had(state_dir, tab, scope) - set(kinds)


def split(call, pane, direction, ratio, cwd):
    where = ["--cwd", cwd] if cwd else []
    return call("pane", "split", "--pane", pane, "--direction", direction, "--ratio", f"{ratio:.4g}", *where,
                "--no-focus")["pane"]["pane_id"]


def show_sidebar(call, terminal, cwd, run, height=0.5):
    """The sidebar back above TERMINAL (split below it, then swapped: the terminal keeps what runs in it), HEIGHT of
    the column; its pane id. RUN: its command."""
    side = split(call, terminal, "down", height, cwd)
    call("pane", "swap", "--source-pane", side, "--target-pane", terminal)
    call("pane", "rename", side, "sidebar")
    call("pane", "run", side, run)
    return side


def show_terminal(call, above, cwd):
    """A terminal back under ABOVE (the sidebar; on the dock's rail, the agent); its pane id."""
    term = split(call, above, "down", 0.5, cwd)
    call("pane", "rename", term, "terminal")
    return term


def show_rail(call, beside, cwd, run, share):
    """The right column as the dock's rail, right of BESIDE (the agent), SHARE of the split BESIDE's, and a terminal
    under BESIDE; the sidebar's pane id. RUN: the sidebar's command."""
    side = split(call, beside, "right", share, cwd)
    show_terminal(call, beside, cwd)
    call("pane", "rename", side, "sidebar")
    call("pane", "run", side, run)
    return side


def show_column(call, beside, cwd, run, share):
    """The right column back, right of BESIDE (the agent): the sidebar above a terminal, SHARE of the split BESIDE's;
    the sidebar's pane id. RUN: the sidebar's command."""
    side = split(call, beside, "right", share, cwd)
    show_terminal(call, side, cwd)
    call("pane", "rename", side, "sidebar")
    call("pane", "run", side, run)
    return side
