# Generated from core/copilot_setup.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""What Copilot CLI starts with in a folder, in the rows Claude's and Codex's setups take: the instructions it reads,
its model and its MCP servers (yours as `copilot mcp list` gives them in the home folder, a project's files read as
text, never run). Only read; a module of its own, so the graph's and harness's helpers skip it."""
import glob
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import agent_setup  # noqa: E402  (its find and run by the module: what a test stands in for)
from agent_setup import (BUILT_IN, EFFORTS, GLOBAL, NOT_CHECKED, OFF, PROJECT, front_matter,  # noqa: E402
                         project_folders, read_text, repo_top, server, strings, tokens, unread)
from jsonl import obj  # noqa: E402
from opencode_setup import jsonc  # noqa: E402

# the instructions a folder holds that Copilot reads in the repository's top, then in the folder below it, and the
# folders of those it reads at any depth there
NAMED = ("AGENTS.md", "CLAUDE.md", os.path.join(".claude", "CLAUDE.md"), "GEMINI.md")
INSTRUCTIONS, RULES = os.path.join(".github", "instructions"), os.path.join(".claude", "rules")
# the settings a repository can override, in its .github/copilot, the later over the earlier (over the user's own)
REPO_SETTINGS = ("settings.json", "settings.local.json")


def copilot_home(home):
    """Copilot's own folder: COPILOT_HOME, as Copilot takes it, else HOME's .copilot."""
    return os.environ.get("COPILOT_HOME") or os.path.join(home, ".copilot")


def matched(folder, under, pattern):
    """The files under FOLDER's UNDER (at any depth) named as PATTERN, in their order."""
    return sorted(glob.glob(os.path.join(glob.escape(os.path.join(folder, under)), "**", pattern), recursive=True))


def rule_paths(folder, home):
    """The instructions Copilot reads in FOLDER, in its order, as `copilot instruction list` gives them: its home's
    copilot-instructions.md and instructions/ (Global); then in the repository's top (else FOLDER) and in FOLDER below
    it: .github/copilot-instructions.md, then NAMED, then .github/instructions/ and .claude/rules/ (Project)."""
    own, folder = copilot_home(home), os.path.abspath(folder)
    places = list(dict.fromkeys([repo_top(folder) or folder, folder]))
    found = [(os.path.join(own, "copilot-instructions.md"), GLOBAL)]
    found += [(path, GLOBAL) for path in matched(own, "instructions", "*.instructions.md")]
    found += [(os.path.join(here, ".github", "copilot-instructions.md"), PROJECT) for here in places]
    found += [(os.path.join(here, name), PROJECT) for here in places for name in NAMED]
    for here in places:
        found += [(path, PROJECT) for path in matched(here, INSTRUCTIONS, "*.instructions.md")]
        found += [(path, PROJECT) for path in matched(here, RULES, "*.md")]
    return found


def applied(path, text):
    """The globs an .instructions.md file is read for (its applyTo, a list or comma-separated); [] for always."""
    told = front_matter(text).get("applyTo") if path.endswith(".instructions.md") else None
    return [one.strip() for one in (told.split(",") if isinstance(told, str) else strings(told)) if one.strip()]


def read(path):
    """PATH's settings, a JSON or JSONC file as Copilot reads it; {} where it is none."""
    text = read_text(path)
    try:
        return obj(jsonc(text)) if text is not None else {}
    except (ValueError, RecursionError):
        return {}


def settings(folder, home):
    """Copilot's settings files for FOLDER, the user's first, then the repository's (its top's .github/copilot), each
    later one over the earlier: (path, what it sets)."""
    top = repo_top(os.path.abspath(folder)) or os.path.abspath(folder)
    paths = [os.path.join(copilot_home(home), "settings.json")] + [os.path.join(top, ".github", "copilot", name)
                                                                     for name in REPO_SETTINGS]
    return [(path, read(path)) for path in paths]


def listed(binary, home):
    """Copilot's own list of its servers, `copilot mcp list --json` run in HOME, never in a project (whose servers are
    read as text): {name: config}; None where it gives no list."""
    try:
        code, out, _ = agent_setup.run([binary, "mcp", "list", "--json"], home)
        found = json.loads(out) if code == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError, RecursionError):
        return None
    return found["mcpServers"] if isinstance(found, dict) and isinstance(found.get("mcpServers"), dict) else None


def entry(config):
    """CONFIG as server() takes it: a "local" server is stdio; one with no type is stdio where it runs a command, else
    http, Copilot's default."""
    kind = config.get("type")
    return {**config, "type": "stdio" if kind == "local" or kind is None and config.get("command") else kind or "http"}


def workspace(folder):
    """The project's servers, read as text from FOLDER up to its repository's top, a nearer file over a farther one:
    each folder's .mcp.json, else its .github/mcp.json. {name: (config, path)}."""
    found = {}
    for here in project_folders(folder):
        path = next((one for one in (os.path.join(here, ".mcp.json"), os.path.join(here, ".github", "mcp.json"))
                     if os.path.isfile(one)), None)
        for name, config in obj(read(path).get("mcpServers") if path else None).items():
            found[name] = (obj(config), path)
    return found


def servers(own, folder, home, off):
    """The servers Copilot starts with in FOLDER, a later source's over an earlier one's by name, as Copilot merges
    them: OWN's (listed()'s) user ones, the project's (workspace()'s), then OWN's plugins' and its built-in ones; off
    where Copilot says or a settings file's disabledMcpServers (OFF) names it, else not checked (none is asked)."""
    user, own, rows = os.path.join(copilot_home(home), "mcp-config.json"), {k: obj(v) for k, v in own.items()}, {}
    for name, config in own.items():
        if config.get("source") == "user":
            rows[name] = server(name, entry(config), GLOBAL, GLOBAL, user), config
    for name, (config, path) in workspace(folder).items():
        rows[name] = server(name, entry(config), PROJECT, PROJECT, path), config
    for name, config in own.items():                    # a plugin's, by its name; one with no plugin left out
        plugin = config.get("sourcePlugin")
        if config.get("source") in ("plugin", "builtin") and isinstance(plugin, str) and plugin:
            scope = BUILT_IN if config["source"] == "builtin" else GLOBAL
            rows[name] = server(name, entry(config), scope, plugin, None), config
    return [{**one, "state": OFF if config.get("enabled") is False or name in off else NOT_CHECKED}
            for name, (one, config) in sorted(rows.items(), key=lambda pair: pair[0].casefold()) if one]


def setup(folder, home):
    """What Copilot starts with in FOLDER for the user whose home is HOME, in the rows Claude's take: {"model", "effort"
    (its settings', the repository's over the user's), "rules" (an .instructions.md file's applyTo its paths),
    "servers" ("unlisted": no list), "unread"}, the rest empty: nothing of it read; None: not here."""
    binary = agent_setup.find("copilot")
    if not binary:
        return None
    places, told, own = rule_paths(folder, home), settings(folder, home), listed(binary, home)
    texts = [(path, where, read_text(path)) for path, where in dict.fromkeys(places)]
    chosen = {key: info[key] for _, info in told for key in ("model", "effortLevel")       # the later file's wins
              if isinstance(info.get(key), str) and info[key]}
    off = {name for _, info in told for name in strings(info.get("disabledMcpServers"))}
    return {"model": chosen.get("model"), "effort": chosen.get("effortLevel") if chosen.get("effortLevel") in EFFORTS
            else None, "skills": [],
            "rules": [{"path": path, "scope": where, "tokens": tokens(text), "paths": applied(path, text), "via": None}
                      for path, where, text in texts if text is not None],
            "permissions": None, "sandbox": None, "hooks": [], "agents": [],
            "servers": servers(own or {}, folder, home, off), "unlisted": own is None, "use": {},
            "unread": unread([path for path, _ in places] + [path for path, _ in told]),
            "start": dict.fromkeys(("tokens", "model", "window", "effort"))}
