"""Builds a herdr workspace for a folder, here or on a connected machine: one tab named as the workspace, the agent on
the left, the right-hand column (herdrlib.add_column) beside it. new_workspace.py uses it; by hand, see USAGE below
(<machine> from `herdr machine list`; its folder is checked over SSH with remote.sh's helpers)."""
import os
import subprocess
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from herdrlib import add_column, agent_name, herdr, machines, space_name  # noqa: E402
from i18n import line, t  # noqa: E402

HOME = os.path.realpath(os.path.expanduser("~"))
USAGE = "Usage: herdr_layout.py [--machine <machine>] [--agent claude|codex] <folder> [name]"


class LayoutError(Exception):
    """The workspace cannot be made (the reason is the message); nothing was created."""


def remote(function, *args):
    """A helper of remote.sh (remote_os, remote_path, remote_is_dir …) run with ARGS: its output, or None if it
    failed."""
    done = subprocess.run(["bash", "-c", '. "$0"; "$@"', os.path.join(HERE, "remote.sh"), function, *args],
                          capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else None


def place(machine, folder):
    """(herdr caller, the folder as the machine sees it, its path separator) — or LayoutError."""
    if not machine:
        if os.environ.get("HERDR_ENV") != "1":
            raise LayoutError(t("common.not_in_herdr"))
        path = os.path.realpath(os.path.expanduser(folder))
        if not os.path.isdir(path):
            raise LayoutError(t("layout.no_folder", folder))
        return herdr, path, "/"
    target = next((m.get("target") for m in machines() if m.get("label") == machine), None)
    if not target:
        raise LayoutError(t("layout.no_machine", machine))
    os_name = remote("remote_os", target)
    if not os_name:
        raise LayoutError(t("layout.unreachable", machine, target))
    path = remote("remote_path", target, os_name, folder) or folder
    if remote("remote_is_dir", target, os_name, path) is None:
        raise LayoutError(t("layout.no_folder_on", machine, path))
    return (lambda *args, **kw: herdr("--machine", machine, *args, **kw)), path, "\\" if os_name == "windows" else "/"


def build(machine, agent, folder, label=None):
    """Makes the workspace; returns its status lines. LayoutError: nothing was made."""
    h, path, sep = place(machine, folder)
    home = HOME if not machine else path if folder.rstrip("/\\") == "~" else None     # a machine's: given as ~
    label = label or space_name(path, home, sep)
    if any(w.get("label") == label for w in h("workspace", "list").get("workspaces", [])):
        return [line("skip", t("layout.exists", label))]
    made = h("workspace", "create", "--cwd", path, "--label", label, "--no-focus")
    main = made["root_pane"]["pane_id"]
    h("pane", "rename", main, agent)            # named, so no new-tab hook lays it out as an empty tab
    h("tab", "rename", made["tab"]["tab_id"], label)              # the main tab, named as the workspace
    add_column(main, path, h, machine)
    lines = []
    try:
        h("agent", "start", agent_name(label, agent), "--kind", agent, "--pane", main, "--timeout", "60000")
        lines.append(line("ok", t("layout.agent", agent, agent_name(label, agent))))
    except RuntimeError:
        lines.append(line("warn", t("layout.agent_asks", agent, agent)))
    workspace = made["workspace"]["workspace_id"]
    lines.append(line("ok", t("layout.ready_on", label, machine, workspace) if machine
                      else t("layout.ready", label, workspace)))
    return lines


def main(args):
    machine, agent = None, "claude"
    while args[:1] in (["--machine"], ["--agent"]) and len(args) > 1:
        if args[0] == "--machine":
            machine = args[1]
        else:
            agent = args[1]
        args = args[2:]
    if agent not in ("claude", "codex") or not 1 <= len(args) <= 2:
        sys.exit(USAGE)
    try:
        print("\n".join(build(machine, agent, *args)))
    except LayoutError as err:
        sys.exit(line("fail", str(err)))


if __name__ == "__main__":
    main(sys.argv[1:])
