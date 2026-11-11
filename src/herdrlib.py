"""Shared herdr helpers: the herdr CLI, the agents and machines it reports, the right-hand column (pane names in
lowercase). herdr runs commands with a minimal PATH: herdr comes from HERDR_BIN_PATH."""
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins", "sidebar"))   # the column's place
import panes  # noqa: E402
from panes import AGENTS, on_windows  # noqa: E402  (the dock's own: the agents herdr-fold starts, a folder's system)

HERDR = os.environ.get("HERDR_BIN_PATH") or shutil.which("herdr") or next(
    (p for p in ("/opt/homebrew/bin/herdr", "/usr/local/bin/herdr") if os.path.exists(p)), "herdr")
# the sidebar plugin's state: the right column's width as last dragged, what each tab has had
PLUGIN_STATE = os.path.join(os.path.expanduser("~"), ".local", "state", "herdr", "plugins", "herdr-fold.sidebar")
SIDEBAR_COMMAND = "bash ~/.config/herdr-fold/sidebar.sh"
# On Windows the pane's shell is PowerShell: it expands $HOME; the ExecutionPolicy is bypassed for this call only
WINDOWS_SIDEBAR_COMMAND = ('powershell -NoProfile -ExecutionPolicy Bypass '
                           '-File "$HOME\\.config\\herdr-fold\\sidebar.ps1"')


def herdr(*args, check=True):
    """The result part of herdr's JSON reply; with check=False, an empty dict on error."""
    out = subprocess.run([HERDR, *args], capture_output=True, text=True)
    if out.returncode != 0:
        if check:
            raise RuntimeError((out.stderr or out.stdout).strip())
        return {}
    if not out.stdout.strip():
        return {}
    data = json.loads(out.stdout)
    return data.get("result", {}) if isinstance(data, dict) else data       # `machine list --json` is a plain list


def agent_pane_ids(panes):
    """The agent panes: those where herdr sees Claude or Codex running, or that are still named "claude" / "codex"
    (e.g. after a restart, while still empty). A pane renamed after its session thus stays an agent pane."""
    running = {a["pane_id"] for a in agents() if a.get("agent") in AGENTS}
    return {p["pane_id"] for p in panes if p["pane_id"] in running or p.get("label") in AGENTS}


def sidebar_command(cwd=None):
    """The sidebar launch command for the pane's shell: the PowerShell launcher on Windows, elsewhere the bash one."""
    return WINDOWS_SIDEBAR_COMMAND if on_windows(cwd) else SIDEBAR_COMMAND


def add_column(pane_id, cwd, h=herdr, machine=None):
    """Adds the right column (sidebar over terminal) right of the pane, as wide as last dragged; noted as the tab's,
    under MACHINE's name on a connected one. `h`: the herdr caller (`herdr --machine <machine>` there, see
    restore_panes.py); `cwd` None: herdr inherits the pane's folder."""
    panes.build(h, pane_id, cwd, PLUGIN_STATE, sidebar_command(cwd), machine or "")


# A workspace's name for its folder, and its main tab's (the workspace's first tab is named as the workspace)
HOME_SPACE = "home"


def space_name(path, home=None, sep="/"):
    """The name of a workspace on folder PATH: its last part; HOME_SPACE for the home folder HOME (never ~ or the user's
    name); a root (/, C:\\) as it is."""
    if home and path.rstrip(sep) == home.rstrip(sep):
        return HOME_SPACE
    return path.rstrip(sep).split(sep)[-1] or path


def space_labels(path, home=None):
    """The names a workspace on folder PATH may get, in order: its own, then with its parent folder's, then numbered."""
    base = space_name(path, home)
    return [base, f"{os.path.basename(os.path.dirname(path))}-{base}"] + [f"{base}-{n}" for n in range(2, 100)]


def free_label(path, taken, home=None):
    return next(label for label in space_labels(path, home) if label not in taken)


def agent_name(label, role):
    """A name herdr accepts for the agent of a pane labeled LABEL: lowercase letters, digits, - and _, at most 32,
    starting with a letter (else ROLE- goes in front)."""
    name = re.sub(r"[^a-z0-9_-]", "-", label.lower()).strip("-")[:32]
    return name if name[:1].isalpha() else f"{role}-{name}"[:32]


def agents(h=herdr):
    """The agents herdr reports (none if herdr does not answer)."""
    return h("agent", "list", check=False).get("agents", [])


def has_conversation(agent):
    """True if the agent holds a conversation (the sessions-view plugin's has_session marker)."""
    return "has_session" in (agent.get("tokens") or {})


def machines(h=herdr):
    """The remote machines connected in herdr: [{"label", "id", "target", "enabled", …}]."""
    found = h("machine", "list", "--json", check=False)
    return found if isinstance(found, list) else []
