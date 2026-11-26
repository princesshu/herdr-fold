# Generated from core/opencode_setup.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""What OpenCode starts with in a folder, in the rows Claude's and Codex's setups take: the instructions it reads, its
model and its MCP servers from the config files its own `opencode debug config` lists (V2's). Only read; a module of its
own, so the helpers that read Claude and Codex alone (the graph's, the harness's) do not carry it."""
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import agent_setup  # noqa: E402  (its find and run by the module: what a test stands in for)
from agent_setup import (EFFORTS, GLOBAL, LOCAL, MANAGED, NOT_CHECKED, OFF, PROJECT, ancestors, inside,  # noqa: E402
                         read_text, repo_top, server, strings, tokens, unread)
from jsonl import obj  # noqa: E402

SYSTEM = "/Library/Application Support/opencode" if sys.platform == "darwin" else "/etc/opencode"   # the machine's
KINDS = {"local": "stdio", "remote": "http"}    # its servers' types as a row names them
# the switches that keep OpenCode from reading CLAUDE.md, as its docs name them (the second skips .claude skills too)
NO_CLAUDE = ("OPENCODE_DISABLE_CLAUDE_CODE_PROMPT", "OPENCODE_DISABLE_CLAUDE_CODE")


def config_home(home):
    """OpenCode's own config folder: under XDG_CONFIG_HOME, as OpenCode takes it, else HOME's .config."""
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config"), "opencode")


def rule_paths(folder, home):
    """The instructions OpenCode reads in FOLDER, in its order, with their scopes: its config folder's AGENTS.md, else
    ~/.claude/CLAUDE.md (Global); then each folder's AGENTS.md, else its CLAUDE.md, from FOLDER up to the home folder
    (outside it, the repository's top), the nearest first (Project)."""
    claude = not any(os.environ.get(name, "").lower() in ("1", "true") for name in NO_CLAUDE)
    names = ("AGENTS.md", "CLAUDE.md") if claude else ("AGENTS.md",)
    own = [os.path.join(config_home(home), "AGENTS.md")] + [os.path.join(home, ".claude", "CLAUDE.md")] * claude
    found = [(path, GLOBAL) for path in own if os.path.isfile(path)][:1]
    folder, home = os.path.abspath(folder), os.path.abspath(home)
    stop = home if folder == home or inside(folder, home) else repo_top(folder) or folder
    for here in reversed(ancestors(folder)):
        found += [(path, PROJECT) for path in (os.path.join(here, name) for name in names) if os.path.isfile(path)][:1]
        if here == stop:
            break
    return list(dict.fromkeys(found))


def documents(binary, folder):
    """OpenCode's config files for FOLDER as its own `opencode debug config` lists them (a private server's, never its
    background service), in its order: (path, what it sets); one with no file of its own left out. None: no list."""
    try:
        code, out, _ = agent_setup.run([binary, "debug", "config", "--standalone"], folder)
        listed = json.loads(out) if code == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError, RecursionError):
        return None
    if not isinstance(listed, list):
        return None
    return [(one["path"], obj(one.get("info"))) for one in map(obj, listed)
            if one.get("type") == "document" and isinstance(one.get("path"), str) and os.path.isabs(one["path"])]


def scope(path, home):
    """Where the config file PATH stands: in OpenCode's config folder Global (a project's own under it, Local), in the
    machine's Managed, else Project."""
    own = config_home(home)
    if inside(path, own):
        return LOCAL if inside(path, os.path.join(own, "project")) else GLOBAL
    return MANAGED if inside(path, SYSTEM) else PROJECT


def servers(found, home):
    """The MCP servers the config files FOUND (documents()'s) define, a later file's over an earlier one's, by name: off
    where its config says so, else not checked (`opencode mcp list` named none of them where it was tried)."""
    rows = {}
    for path, info in found:
        for name, config in obj(obj(info.get("mcp")).get("servers")).items():
            config, where = obj(config), scope(path, home)
            command = strings(config.get("command"))
            one = server(name, {"type": KINDS.get(config.get("type"), "none"), "command": command[0] if command else
                                None, "args": command[1:], "url": config.get("url")}, where, where, path)
            if one:
                rows[name] = {**one, "state": OFF if config.get("disabled") is True else NOT_CHECKED}
    return [rows[name] for name in sorted(rows, key=str.casefold)]


def setup(folder, home):
    """What OpenCode starts with in FOLDER for the user whose home is HOME, in the rows Claude's take: {"model" (its id,
    its provider's apart), "effort" (its variant, where that is one), "rules", "servers" ("unlisted": no list),
    "unread"}, the rest empty: nothing of it read; None: not here."""
    binary = agent_setup.find("opencode")
    if not binary:
        return None
    found, places = documents(binary, folder), rule_paths(folder, home)
    texts = [(path, where, read_text(path)) for path, where in places]
    picked = next((obj(info["model"]) for _, info in reversed(found or []) if obj(info.get("model")).get("model")), {})
    model, variant = picked.get("model"), picked.get("variant")
    return {"model": model if isinstance(model, str) else None, "effort": variant if variant in EFFORTS else None,
            "skills": [], "rules": [{"path": path, "scope": where, "tokens": tokens(text), "paths": [], "via": None}
                      for path, where, text in texts if text is not None],
            "permissions": None, "sandbox": None, "hooks": [], "agents": [], "servers": servers(found or [], home),
            "unlisted": found is None, "use": {}, "unread": unread([path for path, _ in places]),
            "start": dict.fromkeys(("tokens", "model", "window", "effort"))}
