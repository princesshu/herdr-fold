"""The command the Herdr app mod runs for an agent's graph (graph.py's), a module of its own: the helper carries
graph.py without its comments and docstrings, as every module a command imports, and keeps room to grow. Usage (in
JSON): graph_cli.py claude|codex FOLDER [SESSION] [--costs=JSON]."""
import json
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
from agent_setup import READ, conversation, rollout  # noqa: E402
from graph import graph  # noqa: E402


def main(argv):
    """herdr-fold's Herdr app mod runs this on the space's machine, answering in JSON: AGENT FOLDER [SESSION],
    graph()'s (SESSION a file, for Claude an id too, else the folder's newest conversation; --costs: costs.py's)."""
    options = dict(arg[2:].split("=", 1) for arg in argv[1:] if arg.startswith("--") and "=" in arg)
    args, home = [arg for arg in argv[1:] if not arg.startswith("--")], os.path.expanduser("~")
    try:
        costs = json.loads(options["costs"]) if "costs" in options else None
    except ValueError:
        args = []
    if len(args) not in (2, 3) or args[0] not in READ:
        print("usage: graph_cli.py claude|codex FOLDER [SESSION] [--costs=JSON]", file=sys.stderr)
        return 2
    agent, folder, session = args[0], args[1], args[2] if len(args) == 3 else None
    session = conversation(folder, session, home) if agent == "claude" else \
        session if session and os.path.isfile(session) else rollout(folder, home)
    print(json.dumps(graph(agent, folder, home, session, costs)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
