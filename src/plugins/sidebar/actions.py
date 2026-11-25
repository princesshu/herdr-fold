"""The sidebar's herdr actions: the tab's sidebar gets a key no field takes (KEYS), F7 (a chat found) with the keys
too, F6 the dock folded or opened.
Usage: actions.py show-files|show-search|show-git|show-issues|toggle-dock|find-chat"""
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import column  # noqa: E402
import panels  # noqa: E402
import panes  # noqa: E402
import statefile  # noqa: E402
from chats import state_folder          # noqa: E402
from preview import Herdr, seed_file  # noqa: E402

KEYS = {"show-files": "f9", "show-search": "f10", "show-git": "f11", "show-issues": "f12",
        "toggle-dock": "f6", "find-chat": "f7"}


def sidebar_of(listed, tab=None):
    """TAB's sidebar in LISTED (herdr's pane list; TAB None: the first there is), or None."""
    return next((p["pane_id"] for p in listed if p.get("label") == "sidebar" and tab in (None, p.get("tab_id"))), None)


def show(call, tab, listed, key):
    """KEY to TAB's sidebar (LISTED: its workspace's panes); on the rail a view's opens the dock there. The pane, or
    None."""
    pane = sidebar_of(listed, tab)
    if pane:
        call("pane", "send-keys", pane, key)
    return pane


def find(call, tab, listed, state_dir, focus):
    """Cmd+Shift+R: TAB's sidebar (else the workspace's first, LISTED its panes) gets F7 and the keys (FOCUS); one
    closed there by hand comes back on Chats (its seed: it is not running yet). The pane, or None."""
    pane = sidebar_of(listed, tab)
    if pane is None and "sidebar" in panels.had(state_dir, tab):
        statefile.write(seed_file(state_dir, tab), {"show": "chats"})
        panes.bring(call, tab, {"sidebar"}, state_dir)
        pane = sidebar_of(call("pane", "list").get("panes") or [], tab)
    else:
        pane = pane or sidebar_of(listed)
        if pane:
            call("pane", "send-keys", pane, KEYS["find-chat"])
    if pane:
        focus(pane)
    return pane


def main(argv):
    if len(argv) != 2 or argv[1] not in KEYS:
        sys.exit("usage: actions.py " + "|".join(KEYS))
    tab = os.environ.get("HERDR_ACTIVE_TAB_ID") or os.environ.get("HERDR_TAB_ID")
    if not tab:
        sys.exit("not in herdr")
    herdr = Herdr()
    try:
        listed = herdr.call("pane", "list", "--workspace", tab.split(":")[0]).get("panes", [])
        def focus(pane):                      # herdr's command line focuses only by direction
            column.call("pane.focus", {"pane_id": pane})

        if argv[1] == "find-chat":
            if not find(herdr.call, tab, listed, state_folder(), focus):
                sys.exit("no sidebar in this space")
            return
        if show(herdr.call, tab, listed, KEYS[argv[1]]) is None:
            sys.exit("no sidebar in this tab")
    except (RuntimeError, OSError) as err:
        sys.exit(f"herdr: {err}")


if __name__ == "__main__":
    main(sys.argv)
