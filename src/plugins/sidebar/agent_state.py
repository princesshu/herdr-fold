# Generated from core/agent_state.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""The agents on this machine, for the Agent panel's list and Usage: which are installed, signed in and on which plan
(each asked with its own command, nothing of its account kept), what stands in the place of a setup that cannot show,
and Claude's own look at an MCP server. Only read. agent_setup.py reads the setups, and finds and runs the programs."""
import glob
import json
import os
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import agent_setup as setup     # noqa: E402
from jsonl import newest_first, obj, open_regular, parse  # noqa: E402

CHECK_TIMEOUT = 25              # seconds `claude mcp get` may take: the app's exec stops a program after 30
# `claude mcp get`'s Status words (after its mark) and the state each says, the first that starts it; else failed
CHECKED = (("Connected · tools fetch failed", setup.FAILED), ("Connected", setup.ON),
           ("Needs authentication", setup.SIGN_IN), ("Pending approval", setup.NOT_APPROVED),
           ("Rejected", setup.OFF_HERE), ("Disabled for this project", setup.OFF_HERE))
SAID = re.compile(r"  (Status|Issue|URL): (.*)")    # its own lines, never a header's or a variable's (indented more)
# each agent's plans by the id it tells, in the panel's words: another id shows no plan, never itself
PLANS = {"claude": {"max": "Max", "pro": "Pro", "team": "Team", "enterprise": "Enterprise"},
         "codex": {"free": "Free", "go": "Go", "plus": "Plus", "pro": "Pro", "prolite": "Pro", "team": "Team",
                   "business": "Business", "enterprise": "Enterprise", "edu": "Edu"}}
# a Codex id the table lacks by the widest family one of its parts names ("self_serve_business_prolite": Business)
FAMILIES = ("enterprise", "business", "team", "edu", "pro", "plus", "go", "free")
API_KEY = "API key"             # the plan's word for an agent on an API key
API_KEYS = ("api_key", "api_key_helper")    # `claude auth status`'s authMethod for an API key, its own or a helper's
# how `codex login status` starts for one on an API key (on stderr; Codex 0.169)
CODEX_API_KEY = b"Logged in using an API key"
KEEP = 60                       # seconds an agent's answer is kept (the panel reads again every 30 s)
KEPT = {}                       # each agent's answer by its program's path: (when, (signed in, plan))
TAIL = 4 << 20                  # bytes from a Codex chat's end looked through for its plan
# each of agent_setup.py's KNOWN: its program, and its own way to sign in (its command, in a terminal tab) and install
HOW = {"claude": {"program": "claude", "login": ["claude", "auth", "login"],
                  "install": "npm install -g @anthropic-ai/claude-code",
                  "page": "https://code.claude.com/docs/en/setup"},
       "codex": {"program": "codex", "login": ["codex", "login"], "install": "npm install -g @openai/codex",
                 "page": "https://developers.openai.com/codex/cli"},
       "opencode": {"program": "opencode", "login": ["opencode", "auth", "login"],
                    "install": "npm install -g @opencode/cli", "page": "https://opencode.ai/docs/"},
       "copilot": {"program": "copilot", "login": ["copilot", "login"], "install": "npm install -g @github/copilot",
                   "page": "https://docs.github.com/copilot/how-tos/copilot-cli"},
       "gemini": {"program": "gemini", "login": ["gemini"], "install": "npm install -g @google/gemini-cli",
                  "page": "https://github.com/google-gemini/gemini-cli"}}
# the head's list in both clients' words: its two groups' heads (beside one signed out: agent_setup.py's sign in)
HERE, ABSENT = "Agents on this Mac", "Not installed"
SIGNS_IN = ("It signs in its own way: Sign in opens it in a terminal tab, and you finish there, or in the browser if "
            "it asks.")
INSTALLS = "It installs its own way: run its command in a terminal, then choose it in the list."


def claude_state(binary):
    """Whether Claude is signed in, and its plan's word (`claude auth status --json`: loggedIn, authMethod and
    subscriptionType read, its e-mail and organization never kept): (signed in, plan), None where it does not tell."""
    try:
        _, out, _ = setup.run([binary, "auth", "status", "--json"])
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    told = parse(out)
    signed = told["loggedIn"] if isinstance(told.get("loggedIn"), bool) else None
    how, plan = told.get("authMethod"), told.get("subscriptionType")
    plan = API_KEY if how in API_KEYS else \
        PLANS["claude"].get(plan) if how == setup.CLAUDE_AI and isinstance(plan, str) else None
    return signed, plan if signed else None


def codex_plan(home):
    """Codex's plan's word as the newest of its LOOKED newest chats that names one tells it (a token count's
    rate_limits.plan_type, in its last TAIL bytes); None where none does (an API key's), or for an id with no word."""
    paths = glob.glob(os.path.join(setup.codex_home(home), "sessions", "*", "*", "*", "rollout-*.jsonl"))
    for path in newest_first(paths)[:setup.LOOKED]:
        try:
            with open_regular(path, "rb") as f:
                f.seek(max(0, os.fstat(f.fileno()).st_size - TAIL))
                lines = f.read().split(b"\n")
        except OSError:
            continue
        for raw in reversed(lines):
            payload = obj(parse(raw).get("payload")) if b'"plan_type"' in raw else {}
            plan = obj(payload.get("rate_limits")).get("plan_type") if payload.get("type") == "token_count" else None
            if isinstance(plan, str):
                parts = re.split(r"[_-]", plan)
                return PLANS["codex"].get(plan) or next((PLANS["codex"][one] for one in FAMILIES if one in parts), None)
    return None


def codex_state(binary, home):
    """Whether Codex is signed in (`codex login status`'s exit code) and its plan's word: "API key" where its words
    start as CODEX_API_KEY (the rest, a masked key, is not looked at), else codex_plan()'s."""
    try:
        code, out, error = setup.run([binary, "login", "status"])
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    on_key = any((part or b"").lstrip().startswith(CODEX_API_KEY) for part in (error, out))
    return code == 0, (API_KEY if on_key else codex_plan(home)) if code == 0 else None


def opencode_state(binary):
    """Whether OpenCode is signed in: True where `opencode auth list --format json` (a private server's, never its
    background service) names an integration, a stored credential or a key in the environment; else None, as its free
    models need neither. No plan told."""
    try:
        code, out, _ = setup.run([binary, "auth", "list", "--format", "json", "--standalone"])
        told = json.loads(out) if code == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError, RecursionError):
        return None, None
    return (True if isinstance(told, list) and told else None), None


def machine_agents(home, which=None, fresh=False):
    """The agents herdr-fold knows, in its order: installed (WHICH finds its program; else the usual places), signed in
    and on which plan (None where it does not tell: Copilot and Gemini CLI never do), how it signs in and is installed.
    An answer is kept KEEP seconds; FRESH asks again (after a sign-in)."""
    found = []
    for key, known in setup.KNOWN.items():
        how = HOW[key]
        binary, state = (which or setup.find)(how["program"]), (None, None)
        if binary and key in ("claude", "codex", "opencode"):
            kept = KEPT.get(binary)
            if fresh or not kept or time.monotonic() - kept[0] >= KEEP:
                kept = KEPT[binary] = (time.monotonic(), claude_state(binary) if key == "claude" else
                                       codex_state(binary, home) if key == "codex" else opencode_state(binary))
            state = kept[1]
        found.append({"key": key, "name": known["name"], "installed": bool(binary), "signed_in": state[0],
                      "plan": state[1], "login": list(how["login"]), "install": how["install"],
                      "page": how["page"]})
    return found


def listed(agent):
    """AGENT's (machine_agents()'s) row in the head's list, in both clients' words: its group (the installed first, the
    others dim under theirs) and the word at its right: sign in where it says it is signed out, else its plan's where
    it tells one."""
    if not agent["installed"]:
        return {"group": ABSENT, "dim": True, "word": None, "tone": None}
    out = agent["signed_in"] is False
    return {"group": HERE, "dim": False, "word": setup.SIGN_IN if out else agent["plan"],
            "tone": "warn" if out else None}


def told(home, fresh=False):
    """machine_agents(), each with its row in the list (listed()) and what stands in its setup's place (standing(),
    "empty"), as both clients take them."""
    return [{**one, "listed": listed(one), "empty": standing(one)} for one in machine_agents(home, fresh=fresh)]


def standing(agent):
    """What the panel says in place of AGENT's (machine_agents()'s) setup, and what can be done: not installed (its
    vendor's line and page) or not signed in (where it tells); None where its setup shows, or none of it is read."""
    name = agent["name"]
    if not agent["installed"]:
        return {"kind": "install", "title": f"{name} is not installed", "words": INSTALLS,
                "command": agent.get("install"), "foot": "herdr-fold runs no installer.",
                "actions": [{"id": "copy", "label": "Copy"}, {"id": "page", "label": "Open its page"}]}
    if agent["signed_in"] is False:
        return {"kind": "sign-in", "title": f"{name} is not signed in", "words": SIGNS_IN, "command": None,
                "foot": "herdr-fold keeps no token.", "actions": [{"id": "sign-in", "label": "Sign in"}]}
    return None


def check(folder, name):
    """Claude's own look at the server NAME in FOLDER (`claude mcp get NAME`, one argv; Claude connects only to what it
    approved): {"state", "error", "url"}, its Status, Issue and URL lines. A name like an option or holding a control
    character is refused (ValueError)."""
    if not isinstance(name, str) or not name or name.startswith("-") or setup.controlled(name):
        raise ValueError("not a server's name")
    binary = setup.find("claude")
    if not binary:
        return {"state": setup.NOT_CHECKED, "error": "claude is not on this machine's PATH", "url": None}
    try:
        _, out, err = setup.run([binary, "mcp", "get", name], folder, CHECK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"state": setup.NOT_CHECKED, "error": f"No answer in {CHECK_TIMEOUT} s", "url": None}
    except OSError as error:
        return {"state": setup.NOT_CHECKED, "error": setup.clean(error.strerror or str(error)), "url": None}
    said = {}
    for line in setup.ANSI.sub("", out.decode("utf-8", "replace")).splitlines():
        found = SAID.fullmatch(line)
        if found and found.group(1) not in said:
            said[found.group(1)] = found.group(2).strip()
    if "Status" not in said:
        last = (err.decode("utf-8", "replace").strip() or out.decode("utf-8", "replace").strip()).splitlines()
        return {"state": setup.NOT_CHECKED, "error": setup.clean(last[-1] if last else "") or "No answer",
                "url": None}
    words = said["Status"]
    words = words.split(" ", 1)[1] if " " in words and not words[0].isalnum() else words     # after its mark
    checked = next((one for start, one in CHECKED if words.startswith(start)), setup.FAILED)
    plain = checked != setup.FAILED or words == "Failed to connect"        # its words say no more than its state
    return {"state": checked, "error": setup.clean(said.get("Issue")) or (None if plain else setup.clean(words)),
            "url": setup.address(said["URL"]) if "URL" in said else None}


def main(argv):
    """The Herdr app mod runs this on the space's machine, answering in JSON: agents (told()'s), check claude FOLDER
    NAME (check()'s)."""
    if argv[1:] == ["agents"]:
        print(json.dumps(told(os.path.expanduser("~"))))
        return 0
    if argv[1:3] == ["check", "claude"] and len(argv) == 5:
        try:
            print(json.dumps(check(argv[3], argv[4])))
            return 0
        except ValueError:
            pass
    print("usage: agent_state.py agents | check claude FOLDER NAME", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
