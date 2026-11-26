"""What OpenCode starts with in a folder, in the rows Claude's and Codex's setups take: the instructions it reads, its
model and its MCP servers (V2's config: the user's own as `opencode debug config` lists them in the home folder, a
project's read as text, never run). Only read; a module of its own, so the graph's and harness's helpers skip it."""
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
# a project's own config files, in a folder from the repository's top down (its plugins are code: read, never loaded)
PROJECT_FILES = ("opencode.json", "opencode.jsonc", os.path.join(".opencode", "opencode.json"),
                 os.path.join(".opencode", "opencode.jsonc"))
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


def documents(binary, home):
    """The user's own config files as `opencode debug config` lists them, run in HOME (a private server, never its
    background service): never in a project, whose config may load its plugins. (path, what it sets); None: no list."""
    try:
        code, out, _ = agent_setup.run([binary, "debug", "config", "--standalone"], home)
        listed = json.loads(out) if code == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError, RecursionError):
        return None
    if not isinstance(listed, list):
        return None
    return [(one["path"], obj(one.get("info"))) for one in map(obj, listed)
            if one.get("type") == "document" and isinstance(one.get("path"), str) and os.path.isabs(one["path"])]


def jsonc(text):
    """TEXT, a .json or .jsonc config, as JSON reads it: its // and /* */ comments and trailing commas left out, its
    strings kept as written. ValueError where it is no JSON then."""
    out, at, end = [], 0, len(text)
    while at < end:
        if text[at] == '"':                             # a string whole, its escapes with it
            close = at + 1
            while close < end and text[close] != '"':
                close += 2 if text[close] == "\\" else 1
            out.append(text[at:close + 1])
            at = close + 1
        elif text.startswith("//", at):
            at = text.find("\n", at) if "\n" in text[at:] else end
        elif text.startswith("/*", at):
            at = text.find("*/", at + 2) + 2 if "*/" in text[at + 2:] else end
        elif text[at] == "," and text[at + 1:].lstrip()[:1] in ("}", "]"):
            at += 1                                     # a trailing comma
        else:
            out.append(text[at])
            at += 1
    return json.loads("".join(out))


def project_documents(folder, home):
    """FOLDER's project config files read as text, never run: each folder's opencode.json(c) and .opencode's, from the
    repository's top (else FOLDER) down to FOLDER, as OpenCode merges them: (path, what it sets, its model decoded)."""
    folder = os.path.abspath(folder)
    if folder == os.path.abspath(home):
        return []
    top, found = repo_top(folder) or folder, []
    for here in (here for here in ancestors(folder) if here == top or inside(here, top)):
        for path in (os.path.join(here, name) for name in PROJECT_FILES):
            text = read_text(path)
            try:
                info = obj(jsonc(text)) if text is not None else None
            except (ValueError, RecursionError):
                info = None
            if info is not None:
                model = info.get("model")                 # "provider/model", as `debug config` decodes it
                if isinstance(model, str) and "/" in model:
                    provider, _, name = model.partition("/")
                    info = {**info, "model": {"providerID": provider, "model": name}}
                found.append((path, info))
    return found


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
    own, places = documents(binary, home), rule_paths(folder, home)
    found = (own or []) + project_documents(folder, home)        # a project's, even where the user's list fails
    texts = [(path, where, read_text(path)) for path, where in places]
    picked = next((obj(info["model"]) for _, info in reversed(found) if obj(info.get("model")).get("model")), {})
    model, variant = picked.get("model"), picked.get("variant")
    return {"model": model if isinstance(model, str) else None, "effort": variant if variant in EFFORTS else None,
            "skills": [], "rules": [{"path": path, "scope": where, "tokens": tokens(text), "paths": [], "via": None}
                      for path, where, text in texts if text is not None],
            "permissions": None, "sandbox": None, "hooks": [], "agents": [], "servers": servers(found, home),
            "unlisted": own is None, "use": {}, "unread": unread([path for path, _ in places]),
            "start": dict.fromkeys(("tokens", "model", "window", "effort"))}
