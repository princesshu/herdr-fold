"""The Cmd keys an editor takes: herdr runs this with the key (KEYS) in the focused pane. An editor in front there gets
its own key for it, or nothing (EDITORS); elsewhere the key does what it did: Claude's search, the sidebar field's whole
text, the tab closed, a key passed on. herdr runs it with a bare PATH: herdrlib takes herdr from HERDR_BIN_PATH."""
import os
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from close_tab import close  # noqa: E402
from herdrlib import agents, herdr  # noqa: E402
from i18n import t  # noqa: E402

KEYS = ("a", "c", "x", "z", "shift+z", "s", "f", "w")   # Cmd + A, C, X, Z, Shift + Z, S, F and W
# each editor's own select all, copy, cut, undo, redo, save, find and quit, by the program in front; macOS's nano is
# pico, which has no undo; vim's keys depend on its mode, so it gets none
EDITORS = {"micro": {"a": "ctrl+a", "c": "ctrl+c", "x": "ctrl+x", "z": "ctrl+z", "shift+z": "ctrl+y", "s": "ctrl+s",
                     "f": "ctrl+f", "w": "ctrl+q"},
           "nano": {"z": "alt+u", "shift+z": "alt+e", "s": "ctrl+s", "f": "ctrl+w", "w": "ctrl+x"},
           "pico": {"s": "ctrl+o", "f": "ctrl+w", "w": "ctrl+x"},
           "vi": {}, "vim": {}, "nvim": {}}
PASSED = ("c", "x", "s")      # outside an editor these go on to the pane as they came, as herdr passed them before


def editor_in(pane):
    """The editor in front in PANE, by the name herdr gives its process: the program's own (macOS's nano is pico)."""
    running = herdr("pane", "process-info", "--pane", pane, check=False).get("process_info") or {}
    names = [os.path.basename(str(p.get("name", ""))).lower() for p in running.get("foreground_processes") or []
             if isinstance(p, dict)]
    return next((name for name in names if name in EDITORS), None)


def main(key):
    pane = os.environ.get("HERDR_ACTIVE_PANE_ID")
    if not pane:
        return
    editor = editor_in(pane)
    if editor:
        if EDITORS[editor].get(key):
            herdr("pane", "send-keys", pane, EDITORS[editor][key], check=False)
    elif key == "f":
        if any(a["pane_id"] == pane and a.get("agent") == "claude" for a in agents()):
            herdr("pane", "send-keys", pane, "ctrl+o", check=False)
            time.sleep(0.2)                 # Claude switches to the transcript view; only then does it understand /
            herdr("pane", "send-text", pane, "/", check=False)
    elif key == "a":
        if (herdr("pane", "get", pane, check=False).get("pane") or {}).get("label") == "sidebar":
            herdr("pane", "send-keys", pane, "f8", check=False)        # the sidebar's field that has the keys
    elif key == "w":
        if os.environ.get("HERDR_ACTIVE_TAB_ID"):
            close(os.environ["HERDR_ACTIVE_TAB_ID"])
    elif key in PASSED:
        herdr("pane", "send-keys", pane, "super+" + key, check=False)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in KEYS:
        sys.exit(t("cmd_keys.usage", "|".join(KEYS)))
    main(sys.argv[1])
