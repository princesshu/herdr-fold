"""The sidebar's herdr actions: the active tab's pane named "sidebar" gets the view's key — F9 Files, F10 Search,
F11 Changes, F12 Issues (keys no text field takes, so a search being typed does not swallow them).
Usage: actions.py show-files|show-search|show-git|show-issues"""
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from preview import Herdr  # noqa: E402

KEYS = {"show-files": "f9", "show-search": "f10", "show-git": "f11", "show-issues": "f12"}


def main(argv):
    if len(argv) != 2 or argv[1] not in KEYS:
        sys.exit("usage: actions.py " + "|".join(KEYS))
    tab = os.environ.get("HERDR_ACTIVE_TAB_ID") or os.environ.get("HERDR_TAB_ID")
    if not tab:
        sys.exit("not in herdr")
    herdr = Herdr()
    try:
        panes = herdr.call("pane", "list", "--workspace", tab.split(":")[0]).get("panes", [])
        pane = next((p["pane_id"] for p in panes if p.get("tab_id") == tab and p.get("label") == "sidebar"), None)
        if pane is None:
            sys.exit("no sidebar in this tab")
        herdr.call("pane", "send-keys", pane, KEYS[argv[1]])
    except RuntimeError as err:
        sys.exit(f"herdr: {err}")


if __name__ == "__main__":
    main(sys.argv)
