"""Close the active tab (Cmd+W). A workspace's main tab never closes, so Claude cannot stop by accident; a tab with a
Claude/Codex conversation asks first, through this script again (`--confirm`) in the tab-layout plugin's popup."""
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herdrlib import agents, has_conversation, herdr  # noqa: E402
from i18n import t  # noqa: E402
from tui import getkey, printable  # noqa: E402


def conversations(tab):
    """The agents on TAB that hold a conversation."""
    return [a for a in agents(herdr) if a.get("tab_id") == tab and has_conversation(a)]


def close(tab):
    if (herdr("tab", "get", tab, check=False).get("tab") or {}).get("number") == 1:
        herdr("notification", "show", t("close.main_stays"), "--body", t("close.main_stays_body"), "--sound", "none",
              check=False)
    elif conversations(tab):
        herdr("plugin", "pane", "open", "--plugin", "herdr-fold.tab-layout", "--entrypoint", "close-confirm", "--focus",
              "--env", f"HERDR_CLOSE_TAB={tab}", check=False)
    else:
        herdr("tab", "close", tab, check=False)


def confirm(tab):
    label = (herdr("tab", "get", tab, check=False).get("tab") or {}).get("label") or tab
    print("\x1b[2J\x1b[H\x1b[1m" + t("close.ask", printable(label)) + "\x1b[22m\n")
    for agent in conversations(tab):
        print(f"  {printable(agent.get('terminal_title_stripped') or agent.get('agent'))}")
    print("\n  " + t("close.stays_saved"), end="", flush=True)
    while True:
        key = getkey()
        if key in ("\r", "\n"):
            herdr("tab", "close", tab, check=False)
            return
        if key in ("\x1b", "q", "\x03"):
            return


def main(args):
    if args == ["--confirm"]:
        tab = os.environ.get("HERDR_CLOSE_TAB")
        if tab:
            confirm(tab)
        return
    tab = os.environ.get("HERDR_ACTIVE_TAB_ID")
    if tab:
        close(tab)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit(130)
