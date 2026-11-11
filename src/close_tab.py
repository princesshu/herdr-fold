"""Close the active tab (Cmd+W). A workspace's main tab never closes, so Claude cannot stop by accident; a tab with a
Claude/Codex conversation asks first, through this script again (`--confirm`) in the Workspaces plugin's popup."""
import os
import shutil
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herdrlib import agents, has_conversation, herdr  # noqa: E402
from i18n import t  # noqa: E402
from tui import MARGIN, button_at, buttons, clicked, getkey, mouse, printable  # noqa: E402


def conversations(tab):
    """The agents on TAB that hold a conversation."""
    return [a for a in agents(herdr) if a.get("tab_id") == tab and has_conversation(a)]


def close(tab):
    if (herdr("tab", "get", tab, check=False).get("tab") or {}).get("number") == 1:
        herdr("notification", "show", t("close.main_stays"), "--body", t("close.main_stays_body"), "--sound", "none",
              check=False)
    elif conversations(tab):
        herdr("plugin", "pane", "open", "--plugin", "herdr-fold.workspaces", "--entrypoint", "close-confirm", "--focus",
              "--env", f"HERDR_CLOSE_TAB={tab}", check=False)
    else:
        herdr("tab", "close", tab, check=False)


def confirm(tab):
    label = (herdr("tab", "get", tab, check=False).get("tab") or {}).get("label") or tab
    pad = " " * MARGIN
    lines = [pad + "\x1b[1m" + t("close.ask", printable(label)) + "\x1b[22m", ""]
    lines += [f"{pad}  {printable(agent.get('terminal_title_stripped') or agent.get('agent'))}"
              for agent in conversations(tab)]
    lines += ["", pad + "  " + t("close.stays_saved"), ""]
    row, spans = buttons([t("common.cancel"), t("close.close")], shutil.get_terminal_size().columns)
    print("\x1b[2J\x1b[H" + "\n".join(lines + [row]), end="", flush=True)
    mouse(True)
    while True:
        key = getkey()
        event = clicked(key)
        choice = button_at(event[1], spans) if event and event[0] == 0 and event[3] and event[2] == len(lines) + 1 \
            else None
        if key in ("\r", "\n") or choice == t("close.close"):
            herdr("tab", "close", tab, check=False)
            return
        if key in ("\x1b", "q", "\x03") or choice == t("common.cancel"):
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
