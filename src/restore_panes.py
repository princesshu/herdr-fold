"""Restores herdr-fold's started agents after herdr restarts (herdr resumes only agents with conversations), only in an
empty shell and never in HOME_SPACE, where the main conversation runs; the ~ workspace is named HOME_SPACE. Without
--startup the dock's columns come back too (the sidebar's panes.py; at herdr's start its own [[startup]] does it)."""
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herdrlib import (AGENTS, HOME_SPACE, PLUGIN_STATE, agents, herdr, machines, panes,  # noqa: E402
                      sidebar_command)
from i18n import line, t  # noqa: E402


def started(role):
    """What restore.done says was started in a pane of ROLE: the column, the sidebar or an agent."""
    if role == "column":
        return t("restore.column_added")
    return t("restore.sidebar_started") if role == "sidebar" else t("restore.agent_started")


def told(where):
    """How each move on WHERE shows, the dock's (panes.restore_all's SAY) and this script's: its line in the catalog,
    SAY(mark, what, workspace, *details)."""
    texts = {
        "sidebar_back": lambda label: t("restore.sidebar_back", where, label),
        "sidebar_back_failed": lambda label, err: t("restore.sidebar_back_failed", where, label, err),
        "terminal_added": lambda label: t("restore.terminal_added", where, label),
        "terminal_failed": lambda label, err: t("restore.terminal_failed", where, label, err),
        "column_next_to": lambda label, name: t("restore.column_next_to", where, label, name or t("restore.the_agent")),
        "column_failed": lambda label, err: t("restore.column_failed", where, label, err),
        "column_gone": lambda label: t("restore.column_gone", where, label),
        "done": lambda label, role: t("restore.done", where, label, role, started(role)),
        "start_failed": lambda label, role, err: t("restore.start_failed", where, label, role, err),
    }
    return lambda mark, what, label, *details: print(line(mark, texts[what](label, *details)))


def named(h, ws, label):
    """The workspace herdr names after the home folder (~) is called HOME_SPACE. Returns the workspace's name."""
    if label == "~":
        h("workspace", "rename", ws, HOME_SPACE, check=False)
        label = HOME_SPACE
    return label


def restore(machine=None, startup=False):
    h = (lambda *a, **k: herdr("--machine", machine, *a, **k)) if machine else herdr
    say = told(machine or t("restore.this_machine"))
    workspaces = [(w["workspace_id"], named(h, w["workspace_id"], w["label"]))
                  for w in h("workspace", "list").get("workspaces", [])]
    if not startup:
        panes.restore_all(h, PLUGIN_STATE, sidebar_command, machine or "", say=say)

    def look():
        started = {a["pane_id"]: a for a in agents(h) if a.get("name") and a.get("agent") in AGENTS}
        return [(pane, (label, started[pane["pane_id"]])) for ws, label in workspaces if label != HOME_SPACE
                for pane in h("pane", "list", "--workspace", ws, check=False).get("panes", [])
                if pane["pane_id"] in started]

    def act(pane, what):
        label, agent = what
        kind = agent["agent"]
        try:
            h("agent", "start", agent["name"], "--kind", kind, "--pane", pane["pane_id"], "--timeout", "60000")
            say("ok", "done", label, kind)
        except RuntimeError as err:
            say("warn", "start_failed", label, kind, err)

    panes.when_steady(h, startup, look, act)


def main():
    args = sys.argv[1:]
    if args == ["--startup"]:
        restore(startup=True)
    elif args[:1] == ["--machine"] and len(args) == 2:
        restore(args[1])
    elif args in ([], ["--all"]):
        restore()
        if args:
            for m in machines():
                if m.get("enabled"):
                    restore(m["label"])
    else:
        sys.exit(t("restore.usage"))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as err:
        sys.exit(line("fail", str(err)))
