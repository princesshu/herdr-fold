"""Restores herdr-fold's panes after herdr restarts (the layout survives; herdr resumes only agents with conversations):
its started agents (not in HOME_SPACE, where the main conversation runs) and columns, only in an empty shell, never by
pane name alone. A pane closed by hand stays closed; herdr's first shell, made before plugins start, gets the column."""
import os
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herdrlib import (AGENTS, HOME_SPACE, PLUGIN_STATE, SHELLS, add_column, agents,  # noqa: E402
                      conversations_command, conversations_pane, herdr, machines, on_windows, program_names,
                      sidebar_command)
from i18n import line, t  # noqa: E402
import panels  # noqa: E402  (the sidebar plugin's, on the path herdrlib gives)

# At startup herdr is still running its own `claude --resume` commands (those without a conversation exit after a few
# seconds): a pane is decided about only once its state is the same over this many consecutive checks (every POLL s).
STEADY, POLL, STARTUP_LIMIT = 3, 2, 120


def state_of(h, pane):
    """"shell", the names of the foreground programs, or None if the pane has not started yet."""
    info = h("pane", "process-info", "--pane", pane["pane_id"], check=False)
    names = program_names((info.get("process_info") or {}).get("foreground_processes") or [])
    if not names:
        return None
    return "shell" if all(n in SHELLS for n in names) else ",".join(names)


def start(h, pane, role, name, machine=None):
    if role == "column":
        add_column(pane["pane_id"], pane.get("cwd"), h, machine)
        return t("restore.column_added")
    if role == "sidebar":
        h("pane", "run", pane["pane_id"], sidebar_command(pane.get("cwd")))
        return t("restore.sidebar_started")
    if role == "conversations":
        h("pane", "run", pane["pane_id"], conversations_command(pane.get("cwd")))
        return t("restore.sidebar_started")
    h("agent", "start", name, "--kind", role, "--pane", pane["pane_id"], "--timeout", "60000")
    return t("restore.agent_started")


def named(h, ws, label):
    """The workspace herdr names after the home folder (~) is called HOME_SPACE. Returns the workspace's name."""
    if label == "~":
        h("workspace", "rename", ws, HOME_SPACE, check=False)
        label = HOME_SPACE
    return label


def restore(machine=None, startup=False):
    h = (lambda *a, **k: herdr("--machine", machine, *a, **k)) if machine else herdr
    where, scope = machine or t("restore.this_machine"), machine or ""
    workspaces = [(w["workspace_id"], named(h, w["workspace_id"], w["label"]))
                  for w in h("workspace", "list").get("workspaces", [])]
    seen, done, columned, foreign = {}, set(), set(), set()
    deadline = time.time() + (STARTUP_LIMIT if startup else 0)
    while True:
        waiting = False
        started = {a["pane_id"]: a for a in agents(h) if a.get("name") and a.get("agent") in AGENTS}
        listed = {ws: h("pane", "list", "--workspace", ws, check=False).get("panes", []) for ws, _ in workspaces}
        fresh = sum(map(len, listed.values())) == 1       # herdr's very first workspace, nothing else yet
        for ws, label in workspaces:
            panes = listed[ws]
            alone = {p["pane_id"] for p in panes if sum(q["tab_id"] == p["tab_id"] for q in panes) == 1}
            with_terminal = {p["tab_id"] for p in panes if p.get("label") == "terminal"}
            with_sidebar = {p["tab_id"] for p in panes if p.get("label") == "sidebar"}
            for pane in panes:
                name = pane.get("label") or ""
                had = panels.had(PLUGIN_STATE, pane["tab_id"], scope)     # what the tab has had: closed by hand stays
                # a column whose sidebar was never there gets one above the terminal; the terminal keeps what runs
                # in it (split below it, then swapped)
                if name == "terminal" and pane["tab_id"] not in with_sidebar and "sidebar" not in had:
                    with_sidebar.add(pane["tab_id"])
                    try:
                        panels.show_sidebar(h, pane["pane_id"], pane.get("cwd"), sidebar_command(pane.get("cwd")))
                        print(line("ok", t("restore.sidebar_back", where, label)))
                    except (RuntimeError, KeyError) as err:
                        print(line("warn", t("restore.sidebar_back_failed", where, label, err)))
                # a column whose terminal was never there gets one under the sidebar
                if name == "sidebar" and pane["tab_id"] not in with_terminal and "terminal" not in had:
                    with_terminal.add(pane["tab_id"])
                    try:
                        panels.show_terminal(h, pane["pane_id"], pane.get("cwd"))
                        print(line("ok", t("restore.terminal_added", where, label)))
                    except (RuntimeError, KeyError) as err:
                        print(line("warn", t("restore.terminal_failed", where, label, err)))
                # a started agent alone in its tab — running or not — gets the right-hand column next to it, unless its
                # columns were closed by hand
                if pane["pane_id"] in alone and pane["pane_id"] not in columned and pane["pane_id"] in started \
                        and not had:
                    columned.add(pane["pane_id"])
                    try:
                        add_column(pane["pane_id"], pane.get("cwd"), h, machine)
                        print(line("ok", t("restore.column_next_to", where, label, name or t("restore.the_agent"))))
                    except RuntimeError as err:
                        print(line("warn", t("restore.column_failed", where, label, err)))
                if pane["pane_id"] in started:
                    role = started[pane["pane_id"]]["agent"]
                elif fresh and not name and pane["pane_id"] not in columned:
                    role = "column"
                else:
                    role = name
                restarted = role in AGENTS and label != HOME_SPACE and pane["pane_id"] in started
                if pane["pane_id"] in done or not (role in ("sidebar", "conversations", "column") or restarted):
                    continue
                state = state_of(h, pane)
                if role == "sidebar" and state not in (None, "shell") and \
                        not any(program.startswith("python") for program in state.split(",")):
                    foreign.add(pane["pane_id"])           # another program in the sidebar's place: left as it is
                column_program = role in ("sidebar", "conversations")
                if state == "shell" and column_program and not startup and on_windows(pane.get("cwd")):
                    # herdr on Windows names only the shell for a program that is not an agent: the sidebar may be
                    # running there, so nothing is typed into it (when herdr starts, every pane is a fresh shell)
                    continue
                if startup and state == "shell" and pane.get("agent_session"):
                    state = "resuming"             # herdr may still resume the conversation in it
                history = seen.setdefault(pane["pane_id"], [])
                history.append(state)
                if startup and (state in (None, "resuming") or history[-STEADY:] != [state] * STEADY):
                    waiting = True
                    continue
                done.add(pane["pane_id"])
                if state != "shell":                           # running already: left as it is, without a line
                    continue
                try:
                    name = started.get(pane["pane_id"], {}).get("name")
                    print(line("ok", t("restore.done", where, label, role, start(h, pane, role, name, machine))))
                except RuntimeError as err:
                    print(line("warn", t("restore.start_failed", where, label, role, err)))
        if not waiting or time.time() > deadline:
            # every tab with a right column, the Conversations column beside it
            added = conversations_pane.ensure(h, PLUGIN_STATE, conversations_command, sidebar_command, foreign, scope)
            if added:
                print(line("ok", t("restore.conversations_added", where, added)))
            # what each tab has now, kept: a pane closed by hand from here on stays closed
            now = [pane for ws, _ in workspaces
                   for pane in h("pane", "list", "--workspace", ws, check=False).get("panes", [])]
            panels.note(PLUGIN_STATE, panels.present(now), scope, {p["tab_id"] for p in now})
            return
        time.sleep(POLL)


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
