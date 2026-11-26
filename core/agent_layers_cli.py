"""The command the Herdr app mod runs for the Agent panel's layers (agent_layers.py's, with Claude's own looks over
its servers), a module of its own: graph.py's helper, which draws from those layers, does not carry it. Usage (in
JSON): agent_layers_cli.py claude FOLDER [SESSION] [--checked JSON] | codex FOLDER | opencode FOLDER."""
import json
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
from agent_layers import SAID_AS, layers  # noqa: E402
from agent_setup import clean, conversation, setup  # noqa: E402
from jsonl import obj  # noqa: E402
import opencode_setup  # noqa: E402


def checked_over(servers, checked):
    """SERVERS with Claude's own looks over them (CHECKED: {name: {"base", "state", "error"}}, agent_state.py's
    check()'s, kept by the app): each shown while its server's state is still the one it had then (BASE)."""
    for one in servers:
        said = obj(obj(checked).get(one["name"]))
        if said.get("state") in SAID_AS and said.get("base") == one["state"]:
            one.update(state=said["state"], error=clean(said.get("error")))
    return servers


def main(argv):
    """The Herdr app mod runs this on the space's machine, answering in JSON: claude FOLDER [SESSION], codex FOLDER and
    opencode FOLDER (the Agent panel's layers, "states" each server's own; SESSION a file or an id, else the newest;
    Claude's may end with --checked JSON)."""
    home, checked = os.path.expanduser("~"), {}
    if argv[1:2] == ["claude"] and argv[-2:-1] == ["--checked"] and len(argv) in (5, 6):
        try:
            argv, checked = argv[:-2], json.loads(argv[-1])
        except ValueError:
            argv = argv[:1]                         # not JSON: the usage
    if argv[1:2] == ["claude"] and len(argv) in (3, 4) or argv[1:2] in (["codex"], ["opencode"]) and len(argv) == 3:
        session = conversation(argv[2], argv[3] if len(argv) == 4 else None, home) if argv[1] == "claude" else None
        found = opencode_setup.setup(argv[2], home) if argv[1] == "opencode" else setup(argv[1], argv[2], home, session)
        states = {one["name"]: one["state"] for one in found["servers"]} if found else {}
        if found:
            checked_over(found["servers"], checked)
        print(json.dumps(found and {"agent": argv[1], "folder": argv[2], "states": states,
                                    **layers(found, argv[1], argv[2], home)}))
        return 0
    print("usage: agent_layers_cli.py claude FOLDER [SESSION] [--checked JSON] | codex FOLDER | opencode FOLDER",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
