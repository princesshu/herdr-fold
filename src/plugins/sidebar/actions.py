"""The sidebar's herdr actions: the active tab's sidebar gets a key no text field takes (KEYS), F7 (find a
conversation) the keys too; F8, for Cmd + A, only a sidebar that has the keys: its field's text.
Usage: actions.py show-files|show-search|show-git|show-issues|find-conversation|toggle-conversations|select-all"""
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import column  # noqa: E402
import panels  # noqa: E402
import panes  # noqa: E402
import statefile  # noqa: E402
from conversations import state_folder  # noqa: E402
from preview import Herdr, seed_file  # noqa: E402

KEYS = {"show-files": "f9", "show-search": "f10", "show-git": "f11", "show-issues": "f12",
        "find-conversation": "f7", "toggle-conversations": "f6", "select-all": "f8"}


def sidebar_of(listed, tab=None):
    """TAB's sidebar in LISTED (herdr's pane list; TAB None: the first there is), or None."""
    return next((p["pane_id"] for p in listed if p.get("label") == "sidebar" and tab in (None, p.get("tab_id"))), None)


def find(call, tab, listed, state_dir, focus):
    """Cmd+Shift+R: TAB's sidebar (else the workspace's first, LISTED its panes) gets F7 and the keys (FOCUS); one
    closed there by hand comes back on Conversations (its seed: it is not running yet). The pane, or None."""
    pane = sidebar_of(listed, tab)
    if pane is None and "sidebar" in panels.had(state_dir, tab):
        statefile.write(seed_file(state_dir, tab), {"show": "conversations"})
        panes.bring(call, tab, {"sidebar"}, state_dir)
        pane = sidebar_of(call("pane", "list").get("panes") or [], tab)
    else:
        pane = pane or sidebar_of(listed)
        if pane:
            call("pane", "send-keys", pane, KEYS["find-conversation"])
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
        if argv[1] == "select-all":           # any other pane is left alone, as Cmd + A would do nothing there
            focused = os.environ.get("HERDR_ACTIVE_PANE_ID") or os.environ.get("HERDR_PANE_ID")   # a plugin action's
            if any(p.get("pane_id") == focused and p.get("label") == "sidebar" for p in listed):
                herdr.call("pane", "send-keys", focused, KEYS[argv[1]])
            return
        if argv[1] == "find-conversation":    # herdr's command line focuses only by direction
            if not find(herdr.call, tab, listed, state_folder(), lambda pane: column.call("pane.focus",
                                                                                          {"pane_id": pane})):
                sys.exit("no sidebar in this workspace")
            return
        pane = sidebar_of(listed, tab)
        if pane is None:
            sys.exit("no sidebar in this tab")
        herdr.call("pane", "send-keys", pane, KEYS[argv[1]])
    except (RuntimeError, OSError) as err:
        sys.exit(f"herdr: {err}")


if __name__ == "__main__":
    main(sys.argv)
