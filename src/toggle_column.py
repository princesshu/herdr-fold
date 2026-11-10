"""Hide and show the right-hand column on the active tab (Cmd+Shift+E) by zooming the agent pane, not closing panes, so
the terminal's programs keep running and sizes come back. A sidebar or terminal closed by hand is brought back instead.
herdr runs it with a minimal PATH, so the herdr binary comes from HERDR_BIN_PATH."""
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herdrlib import PLUGIN_STATE, agent_pane_ids, herdr, panes, sidebar_command  # noqa: E402
from i18n import t  # noqa: E402


def main():
    tab = os.environ.get("HERDR_ACTIVE_TAB_ID") or os.environ.get("HERDR_TAB_ID")
    if not tab:
        sys.exit(t("common.not_in_herdr"))
    lay = next(l for l in herdr("api", "snapshot")["snapshot"]["layouts"] if l["tab_id"] == tab)
    tab_panes = [p for p in herdr("pane", "list", "--workspace", tab.split(":")[0])["panes"] if p["tab_id"] == tab]
    gone = {"sidebar", "terminal"} - {p.get("label") for p in tab_panes}
    if lay.get("zoomed"):
        # back: unzoom the zoomed pane (the agent, or whatever the user zoomed)
        herdr("pane", "zoom", lay["focused_pane_id"], "--toggle")
        if not gone:
            return
    if gone:                                    # closed by hand: back in the tab
        panes.bring(herdr, tab, gone, PLUGIN_STATE, sidebar_command)
        return
    agents, ids = agent_pane_ids(tab_panes), {p["pane_id"] for p in tab_panes}
    shown = [p for p in lay["panes"] if p["pane_id"] in ids]
    agent = next((p for p in shown if p["pane_id"] in agents), None) \
        or max(shown, key=lambda p: p["rect"]["width"] * p["rect"]["height"])
    herdr("pane", "zoom", agent["pane_id"], "--toggle")


if __name__ == "__main__":
    main()
