"""Shared herdr helpers: the herdr CLI, the agents and machines it reports, the right-hand column with the Conversations
column before it (pane names in lowercase). herdr runs commands with a minimal PATH: herdr comes from HERDR_BIN_PATH."""
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins", "sidebar"))   # the column's place
import conversations_pane  # noqa: E402

HERDR = os.environ.get("HERDR_BIN_PATH") or shutil.which("herdr") or next(
    (p for p in ("/opt/homebrew/bin/herdr", "/usr/local/bin/herdr") if os.path.exists(p)), "herdr")
AGENTS = ("claude", "codex")
# The shells a pane can run with nothing else in its foreground (Unix and Windows)
SHELLS = {"zsh", "bash", "sh", "dash", "fish", "ksh", "nu", "pwsh", "powershell", "cmd"}
# the sidebar plugin's state: the columns' widths as last dragged, whether the Conversations column is collapsed
PLUGIN_STATE = os.path.join(os.path.expanduser("~"), ".local", "state", "herdr", "plugins", "herdr-fold.sidebar")
SIDEBAR_COMMAND = "bash ~/.config/herdr-fold/sidebar.sh"
CONVERSATIONS_COMMAND = SIDEBAR_COMMAND + " --conversations"
# On Windows the pane's shell is PowerShell: it expands $HOME; the ExecutionPolicy is bypassed for this call only
WINDOWS_SIDEBAR_COMMAND = ('powershell -NoProfile -ExecutionPolicy Bypass '
                           '-File "$HOME\\.config\\herdr-fold\\sidebar.ps1"')
WINDOWS_CONVERSATIONS_COMMAND = WINDOWS_SIDEBAR_COMMAND + " -Conversations"


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


def on_windows(cwd=None):
    """Whether a pane in folder CWD is on a Windows machine: this machine itself, or a connected machine's C:\\… style
    folder."""
    return os.name == "nt" or bool(re.match(r"^[A-Za-z]:[\\/]", cwd or ""))


def sidebar_command(cwd=None):
    """The sidebar launch command for the pane's shell: the PowerShell launcher on Windows, elsewhere the bash one."""
    return WINDOWS_SIDEBAR_COMMAND if on_windows(cwd) else SIDEBAR_COMMAND


def conversations_command(cwd=None):
    """The Conversations column's launch command (the sidebar's launcher, its column switch)."""
    return WINDOWS_CONVERSATIONS_COMMAND if on_windows(cwd) else CONVERSATIONS_COMMAND


def add_column(pane_id, cwd, h=herdr, machine=None):
    """Adds the Conversations column, then the right column (sidebar over terminal), right of the pane, as wide as last
    dragged; noted as the tab's, under MACHINE's name on a connected one. `h`: the herdr caller (`herdr --machine
    <machine>` there, see restore_panes.py); `cwd` None: herdr inherits the pane's folder."""
    conversations_pane.build(h, pane_id, cwd, PLUGIN_STATE, conversations_command(cwd), sidebar_command(cwd),
                             machine or "")


def program_names(processes):
    """The plain names of a pane's foreground programs: no folder, no .exe, no login dash, lowercase."""
    return [re.sub(r"(?i)\.exe$", "", p["name"].replace("\\", "/").split("/")[-1]).lstrip("-").lower()
            for p in processes]


def only_shells(processes):
    """True if nothing but a shell runs in the pane's foreground (Unix: -zsh; Windows: pwsh.exe / cmd.exe)."""
    names = program_names(processes)
    return bool(names) and all(n in SHELLS for n in names)


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
