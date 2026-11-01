"""Search the Claude conversation (Cmd+F): in the focused Claude pane, opens the transcript view (Ctrl+O) and its
search (/); other panes are left alone. herdr runs it with a bare PATH: herdrlib takes herdr from HERDR_BIN_PATH."""
import os
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herdrlib import agents, herdr  # noqa: E402


def main():
    pane = os.environ.get("HERDR_ACTIVE_PANE_ID")
    if not pane or not any(a["pane_id"] == pane and a.get("agent") == "claude" for a in agents()):
        return
    herdr("pane", "send-keys", pane, "ctrl+o", check=False)
    time.sleep(0.2)                         # Claude switches to the transcript view; only then does it understand /
    herdr("pane", "send-text", pane, "/", check=False)


if __name__ == "__main__":
    main()
