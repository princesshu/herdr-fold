# Generated from core/agent_setup.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""What Claude or Codex starts with in a folder, for a chat's Context panel, / menu and mode chip and the Agent panel:
rules, skills, mode, permissions with their conflicts, sub-agents, MCP servers with their state, what a chat used. Only
read, nothing of theirs written, every command theirs. A wrong setting counts as none. The agents: agent_state.py."""
import ast
import glob
import json
import os
import re
import shlex
import signal
import stat
import subprocess
import sys
import unicodedata
import urllib.parse

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
from connectors import CLAUDE_AI as CLAUDE_PAGE, brand, logout  # noqa: E402
from jsonl import claude_project_dir, newest_first, obj, open_regular, parse  # noqa: E402
from locate import dot_git, find, repo_top, tool_env  # noqa: E402

CHARS_PER_TOKEN = 4             # the tokens a file costs, estimated: Claude's own count is not at hand
LARGEST = 1 << 20               # bytes of a rules file read: more is not a rule anyone keeps
CONFIG_LARGEST = 16 << 20       # bytes of ~/.claude.json read: it keeps every project's settings, it grows
PERSONAL, PROJECT, LOCAL, MANAGED, BUILT_IN = "Personal", "Project", "Local", "Managed", "Built-in"
CLAUDE = "Claude"               # the source of Claude's own sub-agents
# the modes Claude's permissions.defaultMode may name: claude 2.1.325's --permission-mode, and default (Manual's)
MODES = ("default", "manual", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions")
# the organization's settings, over every other: managed-settings.json, then managed-settings.d/*.json by name
MANAGED_DIR = "/Library/Application Support/ClaudeCode" if sys.platform == "darwin" else "/etc/claude-code"
BEHAVIORS = ("allow", "ask", "deny")
# Claude checks deny, then ask, then allow, the first rule that matches deciding: what each behavior's rule never
# reaches past, in that order
HIDDEN_BY = {"allow": ("deny", "ask"), "ask": ("deny",)}
RULE = re.compile(r"([^\s()]+)(?:\((.+)\))?", re.S)          # Tool or Tool(content), as Claude takes a rule
PATH_TOOLS = ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit")    # a rule's * stays in one folder, ** crosses
LISTING = "agent_listing_delta"         # a session's line telling the sub-agents it added and removed
LISTED = re.compile(r"(.*) \(Tools: ([^()]*)\)", re.S)       # a listing's line after its name: words, then tools
TOOL = re.compile(r"[A-Za-z][\w:.-]*")  # a tool's name in a listing's line ("All tools except …" lists none)
# an MCP server's transport as a row names it, by its config's type (none: a command); another type Claude refuses
KINDS = {None: "stdio", "stdio": "stdio", "http": "http", "streamable-http": "http", "sse": "sse", "sse-ide": "sse",
         "ws": "ws", "ws-ide": "ws"}
ACCOUNT, CLAUDE_AI = "Account", "claude.ai"     # a claude.ai connector's scope and source: the account's
CONNECTOR = "claude.ai "        # how Claude names a claude.ai connector: "claude.ai Box"
ON, FAILED, SIGN_IN, OFF_HERE, NOT_CHECKED = "on", "failed", "sign in", "off here", "not checked"
# Claude still connecting a server when it wrote the line; a project's .mcp.json server waiting for its yes
PENDING, NOT_APPROVED = "pending", "not approved"
LOOKED = 10                     # the newest session files looked in for one that tells the servers' state
ERROR = 200                     # characters of an error a row keeps
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")     # a terminal's escape sequence, in a text shown as text
LINE_NAME = re.compile(r"[^\s:]+")      # the tool a deferred tools line names, at its start
GENERAL = "general-purpose"     # the sub-agent Claude starts for an Agent call that names none
# the session lines that tell the MCP servers' state: their tools, their instructions, a compaction starting both over
TOLD = (b'"deferred_tools_delta"', b'"mcp_instructions_delta"', b'"compact_boundary"')
# the agents herdr-fold knows, in its order (agent_state.py's HOW: each one's program, sign-in and install)
KNOWN = {"claude": {"name": "Claude"}, "codex": {"name": "Codex"}, "gemini": {"name": "Gemini CLI"}}
# Codex's approval policy in words, the graph's line's and the Agent panel's Permissions'
# a mode in the chat's words
MODE_WORDS = {"default": "Manual", "manual": "Manual", "acceptEdits": "Edit automatically", "plan": "Plan",
              "auto": "Auto", "dontAsk": "Don't ask", "bypassPermissions": "Bypass permissions"}
APPROVALS = {"untrusted": "Ask unless trusted", "on-request": "Ask on request", "on-failure": "Ask on failure",
             "never": "Never ask"}
# what codex_config() reads at config.toml's top level
CODEX_WORD = re.compile(r"""^(profile|model_reasoning_effort|approval_policy)\s*=\s*["']([\w-]+)["']""", re.M)
ASK_TIMEOUT = 10                # seconds an agent may take to tell whether it is signed in, or to list its servers
# Codex's rules' decisions as Claude's behaviors: it takes the most restrictive rule that matches, as Claude does
DECISIONS = {"allow": "allow", "prompt": "ask", "forbidden": "deny"}
CODEX_KINDS = {"stdio": "stdio", "streamable_http": "http"}      # `codex mcp list`'s transports as a row names them
OFF = "off"                     # a Codex server turned off: in its own configuration, everywhere
NOT_PLAIN = object()            # a rule's value Codex works out itself (a name, an expression): not read


def read_text(path, largest=LARGEST):
    """PATH's text (its first LARGEST bytes), or None where it is not a regular file or cannot be read (a pipe would
    hold the reader)."""
    try:
        if not stat.S_ISREG(os.stat(path).st_mode):
            return None
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(largest)
    except OSError:
        return None


def front_matter(text):
    """The YAML front matter's keys at the top of TEXT, the few shapes a rule or a skill uses: `key: value` (quoted or
    not), a block (`key: >` or `key: |`, its indented lines) and a list (`key:` then `- item` lines)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    found, key, block, joiner = {}, None, None, " "
    for line in lines[1:]:
        item, indented = line.strip(), line[:1] in (" ", "\t")
        if item == "---":
            break
        if key and block is not None and (indented or not item):
            if item:
                block.append(item)
                found[key] = joiner.join(block)
            continue
        if key and item.startswith("- ") and found[key] in ("", []) or key and isinstance(found[key], list) \
                and item.startswith("- "):
            found[key] = (found[key] or []) + [unquote(item[2:])]
            continue
        if not item or item.startswith("#") or indented:
            continue        # a blank line, a comment, or a deeper shape this does not read
        name, colon, value = line.partition(":")
        if not colon or not name.strip():
            key = None
            continue
        key, value = name.strip(), value.strip()
        block, joiner = ([], " " if value[:1] == ">" else "\n") if value[:1] in (">", "|") else (None, " ")
        found[key] = "" if block is not None else unquote(value)
    return found


def unquote(value):
    value = value.strip()
    if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def tokens(text):
    return round(len(text) / CHARS_PER_TOKEN)


def rule(path, scope):
    """The rule in PATH ({path, scope, tokens, paths}: paths the globs it is read for, [] for always), or None."""
    text = read_text(path)
    if text is None:
        return None
    paths = front_matter(text).get("paths", [])
    return {"path": path, "scope": scope, "tokens": tokens(text),
            "paths": [paths] if isinstance(paths, str) and paths else paths if isinstance(paths, list) else []}


def ancestors(folder):
    """FOLDER and the folders above it, the highest first, up to and not including / (Claude reads each one's)."""
    found, here = [], os.path.abspath(folder)
    while os.path.dirname(here) != here:
        found.append(here)
        here = os.path.dirname(here)
    return found[::-1]


def rules(folder, home):
    """The rules Claude reads in FOLDER, in its order: the user's own (Personal), each folder's from the highest down
    (Project; AGENTS.md too, read by Codex and by whoever imports it), the folder's .claude/rules, then CLAUDE.local.md
    (Local); each file once."""
    personal = os.path.join(home, ".claude")
    places = [(os.path.join(personal, "CLAUDE.md"), PERSONAL)]
    places += [(path, PERSONAL) for path in sorted(glob.glob(os.path.join(personal, "rules", "**", "*.md"),
                                                             recursive=True))]
    for here in ancestors(folder):
        places += [(os.path.join(here, "CLAUDE.md"), PROJECT), (os.path.join(here, ".claude", "CLAUDE.md"), PROJECT),
                   (os.path.join(here, "AGENTS.md"), PROJECT)]
    places += [(path, PROJECT) for path in sorted(glob.glob(os.path.join(folder, ".claude", "rules", "**", "*.md"),
                                                            recursive=True))]
    places += [(os.path.join(here, "CLAUDE.local.md"), LOCAL) for here in ancestors(folder)]
    found, seen = [], set()
    for path, scope in places:
        real = os.path.realpath(path)
        if real in seen:
            continue
        seen.add(real)
        item = rule(path, scope)
        if item:
            found.append(item)
    return found


def skill(path, scope, source):
    """The skill whose SKILL.md is PATH ({name, description, scope, source, path, tokens}), or None: its name and
    description from its front matter, else its folder's name and none. Tokens: what its name and description cost,
    the part Claude keeps in view."""
    text = read_text(path)
    if text is None:
        return None
    meta = front_matter(text)
    name = meta.get("name") if isinstance(meta.get("name"), str) and meta.get("name") else \
        os.path.basename(os.path.dirname(path))
    description = meta.get("description") if isinstance(meta.get("description"), str) else ""
    return {"name": name, "description": description, "scope": scope, "source": source, "path": path,
            "tokens": tokens(name + description)}


def read_json(path, largest=LARGEST):
    try:
        found = json.loads(read_text(path, largest) or "null")
    except (ValueError, RecursionError):
        return {}
    return found if isinstance(found, dict) else {}


def settings(folder, home):
    """Claude's settings files for FOLDER, each over the one before: the user's, the project's, the local ones."""
    return (os.path.join(home, ".claude", "settings.json"), os.path.join(folder, ".claude", "settings.json"),
            os.path.join(folder, ".claude", "settings.local.json"))


def managed_settings():
    """The organization's settings files, as Claude reads them: managed-settings.json, then its drop-in folder's."""
    return [os.path.join(MANAGED_DIR, "managed-settings.json")] + \
        sorted(glob.glob(os.path.join(MANAGED_DIR, "managed-settings.d", "*.json")))


def permission_table(path):
    found = read_json(path).get("permissions")
    return found if isinstance(found, dict) else {}


def mode_told(folder, home):
    """The mode Claude starts in for FOLDER unasked (permissions.defaultMode) and who tells it: {mode, scope, path} of
    the last settings file that names one of Claude's modes, the organization's over every other; None where none."""
    user, project, local = settings(folder, home)
    found = None
    places = [(user, PERSONAL), (project, PROJECT), (local, LOCAL)] + [(path, MANAGED) for path in managed_settings()]
    for path, scope in places:
        mode = permission_table(path).get("defaultMode")
        found = {"mode": mode, "scope": scope, "path": path} if isinstance(mode, str) and mode in MODES else found
    return found


def default_mode(folder, home):
    return (mode_told(folder, home) or {}).get("mode")


def rule_text(value):
    """VALUE as a permission rule Claude takes (Tool or Tool(content), trimmed), else None; one holding a control
    character is left out too."""
    if not isinstance(value, str) or any(ord(ch) < 32 or ord(ch) == 127 for ch in value.strip()):
        return None
    return value.strip() if RULE.fullmatch(value.strip()) else None


def permissions(folder, home):
    """Claude's permission rules for FOLDER: {allow, ask, deny: how many, mode, rules: [{rule, behavior, scope, path}],
    conflicts}. Each settings file in Claude's order (the organization's, the user's, the project's, the local ones);
    a rule listed again with its behavior is counted once, where it first is."""
    user, project, local = settings(folder, home)
    places = [(path, MANAGED) for path in managed_settings()] + [(user, PERSONAL), (project, PROJECT), (local, LOCAL)]
    found, seen = [], set()
    for path, scope in places:
        table = permission_table(path)
        for behavior in BEHAVIORS:
            listed = table.get(behavior)
            for text in (rule_text(value) for value in (listed if isinstance(listed, list) else [])):
                if text and (text, behavior) not in seen:
                    seen.add((text, behavior))
                    found.append({"rule": text, "behavior": behavior, "scope": scope, "path": path})
    counts = {behavior: sum(one["behavior"] == behavior for one in found) for behavior in BEHAVIORS}
    return {**counts, "mode": default_mode(folder, home), "rules": found, "conflicts": conflicts(found)}


def conflicts(rules, covering=None):
    """The rules among RULES the agent never reaches: for each, the first rule that does instead (a deny before an ask)
    with the hidden one and a sentence: {rule, behavior, scope, path, hides: {…}, text}. COVERING: covers()'s kind."""
    found, covering = [], covering or covers
    for hidden in rules:
        hider = next((one for behavior in HIDDEN_BY.get(hidden["behavior"], ()) for one in rules
                      if one["behavior"] == behavior and covering(one["rule"], hidden["rule"])), None)
        if hider:
            found.append({**hider, "hides": hidden,
                          "text": f"{hider['behavior']} in {hider['scope']} hides {hidden['behavior']} in "
                                  f"{hidden['scope']}"})
    return found


def covers(wide, narrow):
    """Whether the rule WIDE matches whatever NARROW does: the same rule; a bare tool every use of it (an MCP server's
    name each of its tools, a * in a name what it matches); else the same tool, NARROW's words in WIDE's pattern."""
    wide_tool, wide_words = RULE.fullmatch(wide).groups()
    tool, words = RULE.fullmatch(narrow).groups()
    if wide == narrow:
        return True
    if wide_words is None:
        return bool(pattern(wide_tool, False).fullmatch(tool)) or \
            wide_tool.startswith("mcp__") and wide_tool.count("__") == 1 and tool.startswith(wide_tool + "__")
    return words is not None and tool == wide_tool and bool(pattern(wide_words, tool in PATH_TOOLS).fullmatch(words))


def pattern(words, path):
    """A rule's WORDS as Claude matches them: * any text (in a PATH one folder's, ** any), \\* a star; a single
    trailing " *" (a legacy ":*" too) matching the words before it alone as well."""
    words = words[:-2] + " *" if words.endswith(":*") else words
    one = r"(?:[^/*]|(?<!\*)\*(?!\*))*" if path else ".*"      # a path's * never takes a narrower rule's **
    parts = re.findall(r"\\[*\\]|\*\*|\*|[^*\\]+|\\", words)
    optional = parts[-1:] == ["*"] and len(parts) > 1 and parts[-2].endswith(" ") \
        and sum(part in ("*", "**") for part in parts) == 1
    if optional:
        parts = parts[:-2] + [parts[-2][:-1]]
    found = "".join(re.escape(part[1]) if len(part) == 2 and part[0] == "\\" else ".*" if part == "**" else
                    one if part == "*" else re.escape(part) for part in parts)
    return re.compile(found + (f"(?: {one})?" if optional else ""), re.S)


def enabled_plugins(folder, home):
    """The plugins turned on for FOLDER (`name@marketplace`), the user's settings first, the project's over them,
    the local ones last."""
    turned = {}
    for path in settings(folder, home):
        plugins = read_json(path).get("enabledPlugins")
        if isinstance(plugins, dict):
            turned.update({name: on for name, on in plugins.items() if isinstance(on, bool)})
    return [name for name, on in turned.items() if on]


def plugins(folder, home):
    """Each enabled plugin installed for FOLDER, by its name: (its name without the marketplace, its scope, its
    installed copy's folder)."""
    installed = read_json(os.path.join(home, ".claude", "plugins", "installed_plugins.json")).get("plugins")
    installed = installed if isinstance(installed, dict) else {}
    found = []
    for name in sorted(enabled_plugins(folder, home)):
        copies = [one for one in installed.get(name) or [] if isinstance(one, dict)
                  and isinstance(one.get("installPath"), str)]
        mine = [one for one in copies if one.get("projectPath") in (None, os.path.abspath(folder))]
        if mine:
            found.append((name.split("@")[0], PERSONAL if mine[0].get("scope", "user") == "user" else PROJECT,
                          mine[0]["installPath"]))
    return found


def plugin_skills(folder, home):
    """Each enabled plugin's skills (its installed copy's skills/*/SKILL.md), the plugin's name as their source."""
    found = []
    for name, scope, root in plugins(folder, home):
        for path in sorted(glob.glob(os.path.join(root, "skills", "*", "SKILL.md"))):
            item = skill(path, scope, name)
            if item:
                found.append(item)
    return found


def skills_in(places):
    """The skills in each of PLACES ((a folder of skills, the scope it gives them), each folder once): its
    <skill>/SKILL.md files."""
    found, seen = [], set()
    for base, scope in places:
        if os.path.realpath(base) not in seen:
            seen.add(os.path.realpath(base))
            found += [item for item in (skill(path, scope, scope) for path in sorted(
                glob.glob(os.path.join(base, "*", "SKILL.md")))) if item]
    return found


def skills(folder, home):
    """The skills Claude can use in FOLDER: the user's own (Personal), the project's, then the enabled plugins'."""
    return skills_in(((os.path.join(home, ".claude", "skills"), PERSONAL),
                      (os.path.join(folder, ".claude", "skills"), PROJECT))) + plugin_skills(folder, home)


def agent(path, scope, source):
    """The sub-agent PATH defines ({name, description, model, tools, scope, source, path}), or None where Claude would
    not load it: its front matter's name (not "-…", no ":") and description are a must. Model None: Claude's default
    for a sub-agent; tools []: none listed, every tool its own."""
    text = read_text(path)
    meta = front_matter(text) if text is not None else {}
    name, description, model = meta.get("name"), meta.get("description"), meta.get("model")
    if not (isinstance(name, str) and name and name[0] != "-" and ":" not in name and isinstance(description, str)
            and description):
        return None
    return {"name": name, "description": description, "model": model if isinstance(model, str) and model else None,
            "tools": tool_list(meta.get("tools")), "scope": scope, "source": source, "path": path}


def tool_list(value):
    """A sub-agent's tools as its front matter lists them: `Read, Grep`, `["Read", "Grep"]` or `- Read` lines."""
    if isinstance(value, str):
        value = value.strip()
        value = (value[1:-1] if value[:1] == "[" and value[-1:] == "]" else value).split(",")
    return [unquote(one) for one in value if isinstance(one, str) and unquote(one)] if isinstance(value, list) else []


def built_in_agents(session):
    """Claude's own sub-agents as the session file SESSION's listings leave them (each adds and removes; one marked
    initial, a compacted conversation's, starts over): its words and tools from the listing's line."""
    listed = {}
    for listing in attachments(session, LISTING) if session else ():
        added, lines = listing.get("addedTypes"), listing.get("addedLines")
        lines = dict(zip(added, lines)) if isinstance(added, list) and isinstance(lines, list) else {}
        listed = {} if listing.get("isInitial") is True else listed
        for name in listing.get("builtInTypes") if isinstance(listing.get("builtInTypes"), list) else []:
            if isinstance(name, str) and name:
                line = lines.get(name) if isinstance(lines.get(name), str) else ""
                listed[name] = line[len(f"- {name}: "):] if line.startswith(f"- {name}: ") else ""
        for name in listing.get("removedTypes") if isinstance(listing.get("removedTypes"), list) else []:
            if isinstance(name, str):
                listed.pop(name, None)
    found = []
    for name, words in listed.items():
        parts = LISTED.fullmatch(words)
        tools = [one.strip() for one in parts.group(2).split(",")] if parts else []
        found.append({"name": name, "description": parts.group(1) if parts else words, "model": None,
                      "tools": tools if all(TOOL.fullmatch(one) for one in tools) else [], "scope": BUILT_IN,
                      "source": CLAUDE, "path": None})
    return found


def attachments(session, kind):
    """The attachments of KIND in the session file SESSION, in its order; an unreadable file has none."""
    marker = f'"{kind}"'.encode()
    try:
        with open_regular(session, "rb") as f:
            for raw in f:
                found = obj(parse(raw.decode("utf-8", "replace")).get("attachment")) if marker in raw else {}
                if found.get("type") == kind:
                    yield found
    except OSError:
        return


def agents(folder, home, session=None):
    """The sub-agents Claude can start in FOLDER: the user's own (Personal), the project's, each enabled plugin's (its
    name as source; Claude calls it plugin:name), then Claude's own as SESSION (a session file's path) lists them. As
    in Claude, a project's agent hides the user's of its name, either a built-in one."""
    found = []
    for base, scope in ((os.path.join(home, ".claude", "agents"), PERSONAL),
                        (os.path.join(folder, ".claude", "agents"), PROJECT)):
        found += [agent(path, scope, scope) for path in sorted(glob.glob(os.path.join(base, "*.md")))]
    for name, scope, root in plugins(folder, home):
        found += [agent(path, scope, name) for path in sorted(glob.glob(os.path.join(root, "agents", "*.md")))]
    found = [one for one in found if one] + built_in_agents(session)
    rank = {CLAUDE: 0, PERSONAL: 1, PROJECT: 2}         # a plugin's agent, named plugin:name, hides none of these
    key = lambda one: one["name"] if one["source"] in rank else f"{one['source']}:{one['name']}"     # noqa: E731
    starts = {}
    for one in found:
        if key(one) not in starts or rank.get(one["source"], 0) >= rank.get(starts[key(one)]["source"], 0):
            starts[key(one)] = one
    return [one for one in found if starts[key(one)] is one]


# --- the MCP servers

def strings(value):
    """VALUE's strings, where it is a list; else none."""
    return [one for one in value if isinstance(one, str)] if isinstance(value, list) else []


def controlled(text):
    return any(unicodedata.category(ch) == "Cc" for ch in text)


def clean(text, limit=ERROR):
    """TEXT as a row shows it, as text: escape sequences and control characters out (a line break as a space), at most
    LIMIT characters (None: all); None for none."""
    if not isinstance(text, str):
        return None
    text = "".join(" " if ch in "\n\r\t" else ch for ch in ANSI.sub("", text)
                   if ch in "\n\r\t" or unicodedata.category(ch) != "Cc").strip()
    return (text[:limit - 1] + "…" if limit and len(text) > limit else text) or None


def address(url):
    """URL's host and path, as a row shows it: no scheme, user, password, query or fragment."""
    try:
        parts = urllib.parse.urlsplit(clean(url, None) or "")
    except ValueError:
        return None
    return (parts.netloc.rpartition("@")[2] + parts.path.rstrip("/")) or None


def tool_key(name):
    """A server's NAME as its tools carry it (mcp__<this>__<tool>): every character but a letter, digit, _ or - as _."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)


def row(name, label, kind, scope, source, path, runs=None, url=None):
    """A server's row, its state not checked yet; a known service's brand (connectors.py's) by its label or URL."""
    return {"name": name, "label": label, "kind": kind, "scope": scope, "source": source, "path": path, "runs": runs,
            "url": url, "brand": brand(label, url), "state": NOT_CHECKED, "tools": None, "tokens": None, "error": None,
            "used": 0}


def server(name, config, scope, source, path, label=None):
    """The row of the server NAME as CONFIG (its entry in the file PATH) defines it, or None where Claude would not
    take it: a stdio one runs a command, the others have a URL. Its env and header values, a URL's query never kept."""
    config = obj(config)
    kind = config.get("type")
    kind = KINDS.get(kind) if isinstance(kind, str) or kind is None else "stdio"    # a wrong type as none
    command, url = config.get("command"), config.get("url")
    if not isinstance(name, str) or not name or controlled(name) or not kind or \
            not (isinstance(command, str) and command if kind == "stdio" else isinstance(url, str) and url):
        return None
    if kind != "stdio":
        return row(name, label or name, kind, scope, source, path, url=address(url))
    words = [clean(one, None) or "" for one in [command] + strings(config.get("args"))]
    return row(name, label or name, kind, scope, source, path, runs=" ".join(
        shlex.quote(one) if not one or any(ch.isspace() for ch in one) else one for one in words))


def listed(table, scope, source, path, prefix=""):
    """The servers TABLE ({name: config}, from the file PATH) defines, by name: PREFIX before each one's name."""
    found = [server(prefix + name, config, scope, source, path, name if prefix else None)
             for name, config in sorted(obj(table).items(), key=lambda pair: pair[0].casefold())]
    return [one for one in found if one]


def project_key(folder):
    """The folder Claude keeps FOLDER's project settings under (~/.claude.json's projects): its repository's top, a
    worktree's main checkout's, else FOLDER itself."""
    folder = os.path.abspath(folder)
    top = repo_top(folder)
    if not top:
        return folder
    worktrees = os.path.dirname(os.path.normpath(dot_git(top)))         # a worktree's: <main>/.git/worktrees/<name>
    if os.path.basename(worktrees) == "worktrees" and os.path.basename(os.path.dirname(worktrees)) == ".git":
        return os.path.dirname(os.path.dirname(worktrees))
    return top


def plugin_servers(folder, home):
    """Each enabled plugin's servers (plugin:<plugin>:<server>): its .mcp.json's, then those its plugin.json names
    (inline, or the files it points to); a file's servers under mcpServers, or the file itself is the table."""
    found = []
    for name, scope, root in plugins(folder, home):
        manifest = os.path.join(root, ".claude-plugin", "plugin.json")
        named = read_json(manifest).get("mcpServers")
        files = [os.path.join(root, ".mcp.json")] + [os.path.normpath(os.path.join(root, one)) for one in (
            [named] if isinstance(named, str) else strings(named))]
        tables = [(path, read_json(path)) for path in files] + ([(manifest, {"mcpServers": named})]
                                                                 if isinstance(named, dict) else [])
        seen = set()
        for path, table in tables:
            table = table["mcpServers"] if isinstance(table.get("mcpServers"), dict) else table
            for one in listed(table, scope, name, path, f"plugin:{name}:"):
                if one["name"] not in seen:
                    seen.add(one["name"])
                    found.append(one)
    return sorted(found, key=lambda one: one["name"].casefold())


def told(session):
    """What the session file SESSION's lines last said of the MCP servers, or None where none says: {"tools": {tool: its
    line}, "blocks": {server: its instructions}, "failed": {server: error}, "sign_in", "pending": {server}}. A compacted
    conversation lists its tools and instructions again; a list said again replaces the one before."""
    found, said = {"tools": {}, "blocks": {}, "failed": {}, "sign_in": set(), "pending": set()}, False
    try:
        with open_regular(session, "rb") as f:
            for raw in f:
                if not any(marker in raw for marker in TOLD):
                    continue
                entry = parse(raw)
                if entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
                    found.update(tools={}, blocks={})
                delta = obj(entry.get("attachment")) if entry.get("isSidechain") is not True else {}
                if delta.get("type") == "deferred_tools_delta":
                    said = True
                    tools(found, delta)
                elif delta.get("type") == "mcp_instructions_delta":
                    instructions(found, delta)
    except OSError:
        return None
    return found if said else None


def tools(found, delta):
    """FOUND (told()'s) with the deferred tools DELTA: its tools removed, then added, each with its line; the servers'
    lists it holds replacing the ones before (a failed one with its error, as text)."""
    lines = {LINE_NAME.match(line).group(): line for line in strings(delta.get("addedLines")) if LINE_NAME.match(line)}
    for name in strings(delta.get("removedNames")):
        found["tools"].pop(name, None)
    found["tools"].update({name: lines.get(name, name) for name in strings(delta.get("addedNames"))})
    if isinstance(delta.get("failedMcpServers"), list):
        found["failed"] = {one["name"]: clean(one.get("error")) for one in delta["failedMcpServers"]
                           if isinstance(one, dict) and isinstance(one.get("name"), str)}
    for key, field in (("sign_in", "needsAuthMcpServers"), ("pending", "pendingMcpServers")):
        if isinstance(delta.get(field), list):
            found[key] = set(strings(delta[field]))


def instructions(found, delta):
    """FOUND (told()'s) with the instructions DELTA: its servers' blocks removed, then added."""
    for name in strings(delta.get("removedNames")):
        found["blocks"].pop(name, None)
    names, blocks = delta.get("addedNames"), delta.get("addedBlocks")
    if isinstance(names, list) and isinstance(blocks, list):
        found["blocks"].update({name: block for name, block in zip(names, blocks)
                                if isinstance(name, str) and isinstance(block, str)})


def telling(paths, read):
    """The state the first of PATHS (the newest first, LOOKED of them) tells, else None; READ: the files read so far."""
    for path in newest_first(paths)[:LOOKED]:
        if path not in read:
            read[path] = told(path)
        if read[path] is not None:
            return read[path]
    return None


def mcpjson(folder, home, entry):
    """How Claude takes the servers of FOLDER's .mcp.json: (its path, all approved, the names approved, the names
    refused), from the settings files and the project's ENTRY in ~/.claude.json (where an older Claude kept them)."""
    every, approved, refused = False, set(), set()
    for found in [entry] + [read_json(path) for path in list(settings(folder, home)) + managed_settings()]:
        every = every or found.get("enableAllProjectMcpServers") is True
        approved |= set(strings(found.get("enabledMcpjsonServers")))
        refused |= set(strings(found.get("disabledMcpjsonServers")))
    return os.path.join(folder, ".mcp.json"), every, approved, refused


def state(one, said, lines, off, project):
    """The state of the row ONE, its tools, tokens and error, as SAID (told()'s, or None) has it with its tool LINES;
    OFF the names turned off in this project, PROJECT how its .mcp.json is taken (mcpjson()'s)."""
    name, block = one["name"], (said or {}).get("blocks", {}).get(one["name"])
    path, every, approved, refused = project
    if name in off or one["path"] == path and name in refused:
        return {"state": OFF_HERE}
    if one["path"] == path and not (every or name in approved):
        return {"state": NOT_APPROVED}
    if said is None:
        return {}
    if name in said["failed"]:
        return {"state": FAILED, "error": said["failed"][name]}
    if name in said["sign_in"]:
        return {"state": SIGN_IN}
    if name in said["pending"]:
        return {"state": PENDING}
    if lines or block:
        return {"state": ON, "tools": len(lines) or None,
                "tokens": tokens("\n".join(lines + [block] if block else lines))}
    return {}


def owned(said, keys):
    """Each server's tool lines in SAID (told()'s, or None), by its tool key among KEYS: a tool goes to the longest
    key its name starts with."""
    found, longest = {}, sorted(keys, key=len, reverse=True)
    for tool, line in (said or {}).get("tools", {}).items():
        owner = next((key for key in longest if tool.startswith(f"mcp__{key}__")), None)
        if owner:
            found.setdefault(owner, []).append(line)
    return found


def connectors(config, told_by):
    """The account's claude.ai connectors, by name: those Claude ever connected (CONFIG, ~/.claude.json's) and those
    the sessions' lines TOLD_BY (told()'s) name."""
    names = set(strings(config.get("claudeAiMcpEverConnected")))
    for said in told_by:
        if said:
            names |= set(said["failed"]) | said["sign_in"] | said["pending"] | set(said["blocks"])
    return [row(name, name[len(CONNECTOR):], CLAUDE_AI, ACCOUNT, CLAUDE_AI, None)
            for name in sorted(names, key=str.casefold)
            if name.startswith(CONNECTOR) and name[len(CONNECTOR):].strip() and not controlled(name)]


def defined(folder, home, config, connected=()):
    """The servers Claude takes in FOLDER, in its /mcp order, unchecked: the organization's alone where it has any,
    else the project's, the local ones, the user's (CONFIG: ~/.claude.json's), the CONNECTED ones, the plugins'."""
    config_path, managed = os.path.join(home, ".claude.json"), os.path.join(MANAGED_DIR, "managed-mcp.json")
    entry, project = obj(obj(config.get("projects")).get(project_key(folder))), os.path.join(folder, ".mcp.json")
    return listed(read_json(managed).get("mcpServers"), MANAGED, MANAGED, managed) or \
        listed(read_json(project).get("mcpServers"), PROJECT, PROJECT, project) + \
        listed(entry.get("mcpServers"), LOCAL, LOCAL, config_path) + \
        listed(config.get("mcpServers"), PERSONAL, PERSONAL, config_path) + list(connected) + \
        plugin_servers(folder, home)


def server_rows(folder, home, calls):
    """servers()'s rows, CALLS the open conversation's ({a server's tool key: calls}, use()'s)."""
    config = read_json(os.path.join(home, ".claude.json"), CONFIG_LARGEST)
    entry = obj(obj(config.get("projects")).get(project_key(folder)))
    project, read = mcpjson(folder, home, entry), {}
    here = telling(glob.glob(os.path.join(claude_project_dir(folder, home), "*.jsonl")), read)
    anywhere = telling(glob.glob(os.path.join(home, ".claude", "projects", "*", "*.jsonl")), read)
    found = defined(folder, home, config, connectors(config, (here, anywhere)))
    keys = {tool_key(one["name"]) for one in found}
    off = set(strings(entry.get("disabledMcpServers")))
    told_by = {False: (here, owned(here, keys)), True: (anywhere, owned(anywhere, keys))}
    for one in found:
        said, lines = told_by[one["kind"] == CLAUDE_AI]         # a connector is the account's: as told anywhere
        one.update(state(one, said, lines.get(tool_key(one["name"]), []), off, project),
                   used=calls.get(tool_key(one["name"]), 0))
    return found


def servers(folder, home, session=None):
    """Claude's MCP servers in FOLDER, in its /mcp order (the project's, the local ones, the user's, claude.ai's, the
    plugins', each by name; the organization's alone where it has any), their state as the newest session tells it (a
    connector's anywhere), and their calls in SESSION, the open conversation's file."""
    return server_rows(folder, home, use(session)["servers"])


def use(session):
    """What the conversation in the session file SESSION used: {"skills": {name: when it was last called (ISO)},
    "servers": {a server's tool key: calls}, "agents": {type: calls}}; a call once (Claude writes a message again)."""
    found, seen = {"skills": {}, "servers": {}, "agents": {}}, set()
    if not session:
        return found
    try:
        with open_regular(session, "rb") as f:
            for raw in f:
                entry = parse(raw) if b'"tool_use"' in raw else {}
                content = obj(entry.get("message")).get("content") if entry.get("type") == "assistant" else None
                for block in content if isinstance(content, list) else []:
                    key = block.get("id") if isinstance(block, dict) and isinstance(block.get("id"), str) else None
                    if not isinstance(block, dict) or block.get("type") != "tool_use" or key and key in seen:
                        continue
                    seen.add(key)
                    called(found, block.get("name"), obj(block.get("input")), entry.get("timestamp"))
    except OSError:
        pass
    return found


def called(found, name, given, when):
    """FOUND (use()'s) with one call of the tool NAME, its input GIVEN, made WHEN."""
    skill, kind = given.get("skill"), given.get("subagent_type")
    if name == "Skill" and isinstance(skill, str) and skill:
        times = [one for one in (found["skills"].get(skill), when) if isinstance(one, str)]
        found["skills"][skill] = max(times) if times else None
    elif name in ("Agent", "Task"):
        kind = kind if isinstance(kind, str) and kind else GENERAL
        found["agents"][kind] = found["agents"].get(kind, 0) + 1
    elif isinstance(name, str) and name.startswith("mcp__"):
        key = name[len("mcp__"):].partition("__")[0]
        found["servers"][key] = found["servers"].get(key, 0) + 1


def run(argv, cwd=None, timeout=None, read=True):
    """ARGV run as one argv in CWD (nothing to read, its own process group): (exit code, out, error), the output None
    where READ is false (never read). OSError where it cannot start; subprocess.TimeoutExpired where it gives no
    answer in TIMEOUT seconds (ASK_TIMEOUT's), stopped with what it started (a server it was connecting to)."""
    kept, timeout = subprocess.PIPE if read else subprocess.DEVNULL, ASK_TIMEOUT if timeout is None else timeout
    proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=kept, stderr=kept, env=tool_env(argv[0]),
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:                                    # Windows has no process group: the program alone (the TUI's copy)
            if hasattr(os, "killpg"):
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except OSError:
            pass
        proc.communicate()
        raise
    return proc.returncode, out, err


def claude_setup(folder, home, session=None):
    """What Claude starts with in FOLDER for the user whose home is HOME: {"rules", "skills", "default_mode" (its mode
    or None), "permissions", "agents", "servers", "use"}; SESSION the open conversation's file, for Claude's own
    sub-agents and what the conversation used."""
    used = use(session)
    return {"rules": rules(folder, home), "skills": skills(folder, home), "default_mode": default_mode(folder, home),
            "permissions": permissions(folder, home), "agents": agents(folder, home, session),
            "servers": server_rows(folder, home, used["servers"]), "use": used}


# --- Codex's setup, in the rows Claude's take

def codex_home(home):
    """Codex's own folder: CODEX_HOME, as Codex takes it, else HOME's .codex."""
    return os.environ.get("CODEX_HOME") or os.path.join(home, ".codex")


def codex_config(home):
    """Codex's config.toml's top-level effort and approval policy, by their keys; none where it names a profile."""
    said = dict(CODEX_WORD.findall(("\n" + (read_text(os.path.join(codex_home(home), "config.toml")) or ""))
                                   .split("\n[")[0]))
    return {} if "profile" in said else said


READ = ("claude", "codex")      # the agents whose setup setup() reads


def project_folders(folder):
    """FOLDER and the folders above it up to its repository's top, the top first (FOLDER alone outside one)."""
    folder = os.path.abspath(folder)
    top = repo_top(folder) or folder
    return [here for here in ancestors(folder) if here == top or here.startswith(top.rstrip(os.sep) + os.sep)]


def codex_rules(folder, home):
    """The rules Codex reads in FOLDER, in its order: its home's (Personal), then each folder's from the repository's
    top down to FOLDER (Project); in each, AGENTS.override.md, else AGENTS.md, the first that holds anything."""
    found = []
    for here, scope in [(codex_home(home), PERSONAL)] + [(here, PROJECT) for here in project_folders(folder)]:
        for path in (os.path.join(here, "AGENTS.override.md"), os.path.join(here, "AGENTS.md")):
            text = read_text(path)
            if text and text.strip():
                found.append({"path": path, "scope": scope, "tokens": tokens(text), "paths": []})
                break
    return found


def codex_skills(folder, home):
    """The skills Codex can use in FOLDER: its home's and the user's .agents ones (Personal; Codex's own, .system,
    left out), then each folder's .agents/skills from the repository's top down to FOLDER (Project)."""
    return skills_in([(os.path.join(codex_home(home), "skills"), PERSONAL),
                      (os.path.join(home, ".agents", "skills"), PERSONAL)] +
                     [(os.path.join(here, ".agents", "skills"), PROJECT) for here in project_folders(folder)])


def prefix_rules(path):
    """The prefix rules of the Codex rules file PATH (Starlark, read as Python reads its own: nothing run), in order:
    (pattern, behavior), the pattern a tuple of each word's alternatives; one Codex refuses, or one not plain, out."""
    try:
        tree = ast.parse(read_text(path) or "")
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return []
    found = []
    for node in tree.body:
        call = node.value if isinstance(node, ast.Expr) else None
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != "prefix_rule" \
                or call.args:
            continue
        given = {}
        for keyword in call.keywords:
            try:
                given[keyword.arg] = ast.literal_eval(keyword.value)
            except (ValueError, TypeError, SyntaxError, RecursionError, MemoryError):
                given[keyword.arg] = NOT_PLAIN
        decision = given.get("decision")
        words = [[one] if isinstance(one, str) else one for one in given.get("pattern") or ()] \
            if isinstance(given.get("pattern"), list) else []
        if words and decision in (None, *DECISIONS) and all(
                isinstance(one, list) and one and all(isinstance(word, str) and word and not controlled(word)
                                                      for word in one) for one in words):
            found.append((tuple(tuple(one) for one in words), DECISIONS[decision or "allow"]))
    return found


def pattern_text(pattern):
    """A prefix rule's PATTERN as the panel shows it: its words (one with a space quoted), alternatives as {a,b}."""
    def word(text):
        return shlex.quote(text) if any(ch.isspace() for ch in text) else text
    return " ".join(word(one[0]) if len(one) == 1 else "{" + ",".join(word(alt) for alt in one) + "}"
                    for one in pattern)


def codex_permissions(home):
    """Codex's prefix rules ($CODEX_HOME/rules/*.rules, by name) in permissions()'s shape: the pattern's words as the
    rule, prompt as ask, forbidden as deny; a rule wider than another hides it (Codex's most restrictive wins); "mode"
    its approval policy as codex_config() reads it, or None."""
    found, seen, patterns = [], set(), {}
    for path in sorted(glob.glob(os.path.join(codex_home(home), "rules", "*.rules"))):
        for pattern, behavior in prefix_rules(path):
            text = pattern_text(pattern)
            patterns[text] = pattern
            if (text, behavior) not in seen:
                seen.add((text, behavior))
                found.append({"rule": text, "behavior": behavior, "scope": PERSONAL, "path": path})
    counts = {behavior: sum(one["behavior"] == behavior for one in found) for behavior in BEHAVIORS}
    mode = codex_config(home).get("approval_policy")
    return {**counts, "mode": mode, "rules": found, "conflicts": conflicts(found, lambda wide, narrow: len(
        patterns[wide]) <= len(patterns[narrow]) and all(set(alts) >= set(their) for alts, their in zip(
            patterns[wide], patterns[narrow])))}


def codex_servers(binary, folder, home):
    """Codex's MCP servers as its own list gives them (`codex mcp list --json` in FOLDER: its configuration, nothing
    checked), in its order: on, off or sign in; none where it gives none. Env, headers, a URL's query never kept."""
    try:
        code, out, _ = run([binary, "mcp", "list", "--json"], folder)
    except (OSError, subprocess.TimeoutExpired):
        return []
    try:
        listed = json.loads(out) if code == 0 else []
    except (ValueError, RecursionError):
        return []
    found, path = [], os.path.join(codex_home(home), "config.toml")
    for entry in listed if isinstance(listed, list) else []:
        transport = obj(obj(entry).get("transport"))
        kind = CODEX_KINDS.get(transport.get("type")) if isinstance(transport.get("type"), str) else None
        one = kind and server(entry.get("name"), {"type": kind, **{key: transport.get(key) for key in (
            "command", "args", "url")}}, PERSONAL, PERSONAL, path)
        if one:
            one["state"] = OFF if entry.get("enabled") is False else \
                SIGN_IN if entry.get("auth_status") == "not_logged_in" else ON
            if entry.get("auth_status") == "o_auth":    # in through Codex's own OAuth: it signs out
                one["signed"] = True
            found.append(one)
    return found


def codex_setup(folder, home):
    """What Codex starts with in FOLDER for the user whose home is HOME, in the rows Claude's take: {"rules", "skills",
    "permissions", "agents": [] (Codex names none of its own here), "servers"}; None where Codex is not here."""
    binary = find("codex")
    if not binary:
        return None
    return {"rules": codex_rules(folder, home), "skills": codex_skills(folder, home),
            "permissions": codex_permissions(home), "agents": [], "servers": codex_servers(binary, folder, home)}


def setup(agent, folder, home, session=None):
    """AGENT's setup in FOLDER (claude_setup()'s or codex_setup()'s; None for Codex where it is not here), each rule and
    server marked with the agents that read it: both where the other one, when here, reads it too (a rule by its file,
    a server by its URL or its command line). SESSION: Claude's open conversation's file."""
    if agent not in READ:
        raise ValueError(f"not an agent with a setup: {agent!r}")
    own = claude_setup(folder, home, session) if agent == "claude" else codex_setup(folder, home)
    if own is None:
        return None
    binary = find("codex" if agent == "claude" else "claude")
    if not binary:
        files, places = [], []
    elif agent == "claude":
        files, places = codex_rules(folder, home), codex_servers(binary, folder, home)
    else:
        files = rules(folder, home)
        places = defined(folder, home, read_json(os.path.join(home, ".claude.json"), CONFIG_LARGEST))
    files = {os.path.realpath(one["path"]) for one in files}
    places = {one["url"] or one["runs"] for one in places} - {None}
    for one in own["rules"]:
        one["agents"] = ["claude", "codex"] if os.path.realpath(one["path"]) in files else [agent]
    for one in own["servers"]:
        one["agents"] = ["claude", "codex"] if (one["url"] or one["runs"]) in places else [agent]
    return own


# --- the Agent panel's layers: the sections, rows, words and properties both clients draw

SECTIONS = (("rules", "Rules"), ("permissions", "Permissions"), ("skills", "Skills"), ("connectors", "Connectors"),
            ("agents", "Agents"))
GRAPHED = ("rules", "skills", "connectors", "agents")      # the sections whose rows the graph draws as nodes
TONES = {PERSONAL: "personal", PROJECT: "project", CLAUDE_AI: "account"}    # a tag's color: a plugin's, else muted
# a server's state in its row's word and tone; a dim row's server does not run here
SAID_AS = {ON: ("on", "ok"), FAILED: ("failed", "bad"), SIGN_IN: ("sign in", "warn"), PENDING: ("connecting", "busy"),
           NOT_APPROVED: ("not approved", "off"), OFF_HERE: ("off here", "off"), OFF: ("off", "off"),
           NOT_CHECKED: ("not checked", "off")}
DIM = (NOT_APPROVED, OFF_HERE, OFF)
PROBLEMS = ((FAILED, "failed", "bad"), (SIGN_IN, "sign in", "warn"))    # first in their section, a chip each
FIRST_LINES = 3                 # lines of a rule its properties show
LINE = 120                      # characters of a rule's line shown
NAMED = 2                       # sub-agents a folded section names before "N more"
SESSION_ID = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]*")      # a conversation's id, as the app tells it: never a path


def kilo(tokens, whole=False):
    """TOKENS as a cost reads: thousands with one decimal ("6.1k", "<0.1k"), WHOLE from ten thousand ("22k")."""
    tenths = int(tokens / 100 + 0.5)
    if whole and tenths >= 100:
        return f"{int(tokens / 1000 + 0.5)}k"
    return "0k" if not tokens else f"{tenths / 10:.1f}k" if tenths else "<0.1k"


def inside(path, base):
    return os.path.abspath(path).startswith(os.path.abspath(base).rstrip(os.sep) + os.sep)


def shown(path, folder, home):
    """PATH as the properties name it: from FOLDER in it, from ~ in HOME, from FOLDER above it ("../CLAUDE.md")."""
    if inside(path, folder):
        return os.path.relpath(path, folder)
    if inside(path, home):
        return "~/" + os.path.relpath(path, home)
    return os.path.relpath(path, folder) if inside(folder, os.path.dirname(path)) else path


def plugged(one):
    """Whether the reader's row ONE is an enabled plugin's (its source the plugin's name)."""
    return one.get("source", one["scope"]) not in (one["scope"], CLAUDE, CLAUDE_AI)


def tag(one):
    """The tag of the reader's row ONE: a plugin's name, claude.ai, else its scope; in its tone."""
    text = one["source"] if plugged(one) or one.get("source") == CLAUDE_AI else one["scope"]
    return {"text": text, "tone": "plugin" if plugged(one) else TONES.get(text, "muted")}


def origin(one, folder, home):
    """Where ONE comes from, a properties line: a plugin by its name, claude.ai and Claude's own, else its file."""
    if plugged(one):
        return ["From", one["source"], "Plugin"]
    return ["From", one["source"] if one.get("source") in (CLAUDE_AI, CLAUDE) else shown(one["path"], folder, home),
            one["scope"]]


def used_line(calls):
    return [["Used", ("once" if calls == 1 else f"{calls} times") + " in this conversation", None]] if calls else []


def act(kind, label, path=None, server=None):
    return {"id": kind, "label": label, "path": path, "server": server, "primary": False}


def opened(paths, folder, home):
    """Open for each of PATHS (once each), by the file's name; by where it is where two share a name."""
    paths = list(dict.fromkeys(paths))
    names = [os.path.basename(path) for path in paths]
    return [act("open", "Open " + (shown(path, folder, home) if names.count(name) > 1 else name), path)
            for path, name in zip(paths, names)]


def properties(title, state=None, lines=(), text=None, error=None, actions=()):
    """A row's properties: its title and state, label and value lines (a third column at the right, or None), a text
    and an error shown as they are, its actions, the first one primary."""
    actions = [{**one, "primary": not n} for n, one in enumerate(actions)]
    return {"title": title, "state": state, "lines": [list(one) for one in lines], "text": text, "error": error,
            "actions": actions}


def layer(key, icon, name, props, note=None, mark=None, state=None, tokens=None, used=False, agents=(), dim=False,
          warn=False, known=None):
    """A row of the panel: KEY its id, MARK its tag, KNOWN a connector's brand; its cost in words beside its TOKENS."""
    return {"id": key, "icon": icon, "name": name, "note": note, "tag": mark, "state": state, "brand": known,
            "tokens": tokens,
            "cost": None if tokens is None else kilo(tokens), "used": used, "agents": list(agents), "dim": dim,
            "warn": warn, "properties": props}


def first_lines(path):
    """The first FIRST_LINES lines of the file PATH, past its front matter and blank lines, as text, each cut."""
    lines = (read_text(path) or "").split("\n")
    if lines[0].strip() == "---":
        lines = lines[next((n for n, line in enumerate(lines[1:], 1) if line.strip() == "---"), 0) + 1:]
    return "\n".join([line for line in (clean(one, LINE) for one in lines) if line][:FIRST_LINES]) or None


def rule_rows(setup, agent, folder, home):
    """The rules, in the agent's order: one above FOLDER by its way there ("../CLAUDE.md"); a path-scoped one dim."""
    rows = []
    for one in setup["rules"]:
        path, paths = one["path"], one["paths"]
        name = os.path.basename(path) if one["scope"] == PERSONAL or inside(path, folder) else \
            os.path.relpath(path, folder)
        lines = [origin(one, folder, home)] + ([["Paths", ", ".join(paths), None]] if paths else [])
        spoken = ", ".join(paths[:-1]) + " or " + paths[-1] if len(paths) > 1 else "".join(paths)
        rows.append(layer("rule:" + path, "file", name, properties(name, lines=lines, text=first_lines(path),
                                                                     actions=opened([path], folder, home)),
                          note=f"when {spoken} is read" if paths else None, mark=tag(one), tokens=one["tokens"],
                          agents=one.get("agents", [agent]), dim=bool(paths)))
    return rows


def permission_rows(setup, agent, folder, home):
    """First what the agent starts with, where a file tells it (Claude's mode, Codex's approval policy: its words the
    note, read and never set here); then each conflict, in place of the rule it hides (the sentence its note, both
    rules its lines), then every other rule with its behavior."""
    table, rows = setup["permissions"], []
    told = {"scope": PERSONAL, "path": os.path.join(codex_home(home), "config.toml")}
    told = (told if table["mode"] in APPROVALS else None) if agent == "codex" else mode_told(folder, home)
    if told:
        name, word = ("Approval", APPROVALS[table["mode"]]) if agent == "codex" else ("Mode", MODE_WORDS[told["mode"]])
        rows.append(layer(name.lower(), "shield", name, properties(
            name, lines=[origin(told, folder, home)], actions=opened([told["path"]], folder, home)),
            note=word, mark=tag(told), agents=[agent]))
    hidden = {(one["hides"]["behavior"], one["hides"]["rule"]) for one in table["conflicts"]}
    for one in table["conflicts"]:
        hides = one["hides"]
        lines = [[hides["behavior"].capitalize(), hides["rule"], hides["scope"]],
                 [one["behavior"].capitalize(), one["rule"], one["scope"]]]
        rows.append(layer(f"conflict:{hides['behavior']}:{hides['rule']}", "shield", hides["rule"], properties(
            hides["rule"], lines=lines, actions=opened([one["path"], hides["path"]], folder, home)), note=one["text"],
            agents=[agent], warn=True))
    for one in table["rules"]:
        if (one["behavior"], one["rule"]) not in hidden:
            state = {"text": one["behavior"], "tone": one["behavior"]}
            rows.append(layer(f"permission:{one['behavior']}:{one['rule']}", "shield", one["rule"], properties(
                one["rule"], state, [origin(one, folder, home)], actions=opened([one["path"]], folder, home)),
                mark=tag(one), state=state, agents=[agent]))
    return rows


def skill_rows(setup, agent, folder, home):
    """The skills, each with its description; a dot on those the open conversation used (a plugin's as plugin:name)."""
    used, rows = obj(setup.get("use")).get("skills", {}), []
    for one in setup["skills"]:
        called = f"{one['source']}:{one['name']}" if plugged(one) else one["name"]
        lines = [origin(one, folder, home)] + ([["Used", "in this conversation", None]] if called in used else [])
        rows.append(layer("skill:" + one["path"], "skill", one["name"], properties(
            one["name"], lines=lines, text=clean(one["description"], None),
            actions=opened([one["path"]], folder, home)), mark=tag(one), tokens=one["tokens"], used=called in used,
            agents=[agent]))
    return rows


def agent_rows(setup, agent, folder, home):
    """The sub-agents, each with its model (its row's word) and tools, and how often the open conversation ran it."""
    used, rows = obj(setup.get("use")).get("agents", {}), []
    for one in setup["agents"]:
        calls = used.get(f"{one['source']}:{one['name']}" if plugged(one) else one["name"], 0)
        state = {"text": one["model"], "tone": "ok"} if one["model"] else None
        lines = [origin(one, folder, home)] + ([["Model", one["model"], None]] if one["model"] else []) + \
            ([["Tools", ", ".join(one["tools"]), None]] if one["tools"] else []) + used_line(calls)
        rows.append(layer(f"agent:{one['source']}:{one['name']}", "bot", one["name"], properties(
            one["name"], state, lines, clean(one["description"], None),
            actions=opened([one["path"]] if one["path"] else [], folder, home)),
            mark=tag(one), state=state, used=bool(calls), agents=[agent]))
    return rows


def server_actions(one, agent, folder, home):
    """What a server's state allows: Claude's own commands (Retry, Turn off or on here, Sign out) on Claude's alone;
    Connect; its file where it is edited (a project's .mcp.json, the organization's, Codex's configuration)."""
    state, name, here = one["state"], one["name"], os.path.basename(os.path.abspath(folder))
    files = opened([one["path"]], folder, home) if one["path"] and (agent == "codex" or one["source"] in (
        PROJECT, MANAGED)) else []
    off = act("turn-off", f"Turn off in {here}", server=name)
    if state == SIGN_IN:
        return [act("connect", "Connect", server=name)] + ([off] if agent == "claude" else files)
    if agent == "codex" and state == ON and one.get("signed"):
        return [act("sign-out", "Sign out", server=name)] + files
    if agent != "claude" or state == NOT_APPROVED:
        return files
    if state == ON:
        return [off] + ([act("sign-out", "Sign out", server=name)] if one["kind"] == CLAUDE_AI else files)
    if state == OFF_HERE:
        return [act("turn-on", f"Turn on in {here}", server=name)] + files
    return [act("retry", "Retry", server=name)] + files       # failed, connecting, not checked


def signs_out(one, agent):
    """Where a Claude server with an address that is on is signed out, a properties line: Claude's own command, for
    you to run (herdr-fold has no button for it; a claude.ai connector has its own). None for any other."""
    if agent != "claude" or one["state"] != ON or not one["url"] or one["kind"] == CLAUDE_AI:
        return []
    try:
        return [["Sign out", shlex.join(logout(agent, one["name"])), None]]
    except ValueError:
        return []


def connector_rows(setup, agent, folder, home):
    """The servers, failed ones first, then those to sign in, then in the agent's own order: their state in words
    ("32 tools" for one on that told its tools), what each runs or its address, its error, its actions."""
    rank, rows = {state: n for n, (state, _, _) in enumerate(PROBLEMS)}, []
    for one in sorted(setup["servers"], key=lambda one: rank.get(one["state"], len(rank))):
        word, tone = SAID_AS[one["state"]]
        word = f"{one['tools']} tool{'s' * (one['tools'] != 1)}" if one["state"] == ON and one["tools"] else word
        state = {"text": word, "tone": tone}
        lines = [origin(one, folder, home)] + [[label, one[key], None] for label, key in (("Runs", "runs"), (
            "URL", "url")) if one[key]] + signs_out(one, agent) + used_line(one["used"])
        rows.append(layer("connector:" + one["name"], "plug", one["label"], properties(
            one["label"], state, lines, error=one["error"], actions=server_actions(one, agent, folder, home)),
            mark=tag(one), state=state, tokens=one["tokens"], used=bool(one["used"]),
            agents=one.get("agents", [agent]), dim=one["state"] in DIM, known=one["brand"]))
    return rows


def connecting(agent, folder):
    """What a sign-in and the add form say in both clients: a row's state while its agent signs in in a terminal and
    what can be done then; why Claude's Turn off or on waits for a chat; the form's words, Claude's two ways to add
    and its two scopes (this folder's, every folder's), Codex's one (by its address, for every folder)."""
    here, claude = os.path.basename(os.path.abspath(folder)), agent == "claude"
    return {"state": {"text": "signing in", "tone": "busy"}, "words": "Finish in your browser",
            "actions": [{"id": "reopen", "label": "Open the page again"}, {"id": "cancel", "label": "Cancel"}],
            "needs": {f"turn-{way}": f"Start a chat in {here} to turn it {way}" for way in ("off", "on")},
            "add": {"tip": "Add a connector", "title": "Add a connector",
                    "menu": ([{"id": "claude-ai", "label": "From claude.ai…", "url": CLAUDE_PAGE}] if claude else [])
                    + [{"id": "url", "label": "By URL…", "url": None}],
                    "fields": {"name": "Name", "url": "URL", "scope": "For"},
                    "scopes": [{"id": "local", "label": here}, {"id": "user", "label": "All projects"}] if claude
                    else [], "submit": "Add and connect", "cancel": "Cancel"}}


def health(setup):
    """What loads at start (the rules read always, every skill's listing, the servers' tools and instructions) and
    the problems as chips, each leading to its first row."""
    parts = (("rules", sum(one["tokens"] for one in setup["rules"] if not one["paths"])),
             ("skills", sum(one["tokens"] for one in setup["skills"])),
             ("connectors", sum(one["tokens"] or 0 for one in setup["servers"])))
    loaded, problems = sum(tokens for _, tokens in parts), []
    for state, word, tone in PROBLEMS:
        found = [one["name"] for one in setup["servers"] if one["state"] == state]
        problems += [{"text": f"{len(found)} {word}", "tone": tone, "row": "connector:" + found[0]}] if found else []
    return {"loaded": loaded, "text": f"{kilo(loaded, whole=True)} loaded at start",
            "bar": [{"part": part, "tokens": tokens} for part, tokens in parts], "problems": problems}


def summary(key, setup, rows):
    """What a section's head says beside its count: the permissions by behavior (one with none left out), the
    sub-agents by name."""
    if key == "permissions":
        return [{"text": f"{setup['permissions'][one]} {one}", "tone": one} for one in BEHAVIORS
                if setup["permissions"][one]]
    if key == "agents":
        names = [row["name"] for row in rows]
        names = names if len(names) <= NAMED + 1 else names[:NAMED] + [f"{len(names) - NAMED} more"]
        return [{"text": ", ".join(names), "tone": "ok"}]
    return []


def layers(setup, agent, folder, home):
    """AGENT's SETUP (setup()'s) in FOLDER as the Agent panel draws it, in both clients' words: the head, the health,
    the sections in order with their counts, costs and rows, each row's properties (a row the graph draws ends with
    Show graph); a section with no rows left out but Connectors (where one is added). HOME: where ~ is."""
    made = {"rules": rule_rows, "permissions": permission_rows, "skills": skill_rows, "connectors": connector_rows,
            "agents": agent_rows}
    sections = []
    for key, title in SECTIONS:
        rows = made[key](setup, agent, folder, home)
        for shown in (row["properties"]["actions"] for row in rows if key in GRAPHED):
            shown.append({**act("graph", "Show graph"), "primary": not shown})
        costs = [row["tokens"] for row in rows if row["tokens"] is not None]
        if rows or key == "connectors":
            sections.append({"id": key, "title": title, "count": len(rows), "tokens": sum(costs) if costs else None,
                             "cost": kilo(sum(costs)) if costs else None, "summary": summary(key, setup, rows),
                             "rows": rows})
    return {"head": {"name": KNOWN[agent]["name"], "where": f"in {os.path.basename(os.path.abspath(folder))}"},
            "health": health(setup), "sections": sections, "connect": connecting(agent, folder)}


def conversation(folder, session, home):
    """Claude's file of the open conversation in FOLDER: SESSION where it is a file, its file there where it is a
    conversation's id (never a path), else the folder's newest; None where the folder has none."""
    if session and os.path.isfile(session):
        return session
    place = claude_project_dir(folder, home)
    named = os.path.join(place, f"{session}.jsonl") if session and SESSION_ID.fullmatch(session) else None
    if named and os.path.isfile(named):
        return named
    return (newest_first(glob.glob(os.path.join(glob.escape(place), "*.jsonl"))) or [None])[0]


def checked_over(servers, checked):
    """SERVERS with Claude's own looks over them (CHECKED: {name: {"base", "state", "error"}}, agent_state.py's
    check()'s, kept by the app): each shown while its server's state is still the one it had then (BASE)."""
    for one in servers:
        said = obj(obj(checked).get(one["name"]))
        if said.get("state") in SAID_AS and said.get("base") == one["state"]:
            one.update(state=said["state"], error=clean(said.get("error")))
    return servers


def main(argv):
    """The Herdr app mod runs this on the space's machine, answering in JSON: claude FOLDER [SESSION] and codex FOLDER
    (setup()'s), layers AGENT FOLDER [SESSION] (the Agent panel's, "states" each server's own; SESSION a file or an id,
    else the newest; Claude's may end with --checked JSON)."""
    home, checked = os.path.expanduser("~"), {}
    if argv[1:3] == ["layers", "claude"] and argv[-2:-1] == ["--checked"] and len(argv) in (6, 7):
        try:
            argv, checked = argv[:-2], json.loads(argv[-1])
        except ValueError:
            argv = argv[:1]                         # not JSON: the usage
    if argv[1:2] == ["claude"] and len(argv) in (3, 4) or argv[1:2] == ["codex"] and len(argv) == 3:
        print(json.dumps(setup(argv[1], argv[2], home, argv[3] if len(argv) == 4 else None)))
        return 0
    if argv[1:3] == ["layers", "claude"] and len(argv) in (4, 5) or argv[1:3] == ["layers", "codex"] and len(argv) == 4:
        session = conversation(argv[3], argv[4] if len(argv) == 5 else None, home) if argv[2] == "claude" else None
        found = setup(argv[2], argv[3], home, session)
        states = {one["name"]: one["state"] for one in found["servers"]} if found else {}
        if found:
            checked_over(found["servers"], checked)
        print(json.dumps(found and {"agent": argv[2], "folder": argv[3], "states": states,
                                    **layers(found, argv[2], argv[3], home)}))
        return 0
    print("usage: agent_setup.py claude FOLDER [SESSION] | codex FOLDER | layers claude FOLDER [SESSION] "
          "[--checked JSON] | layers codex FOLDER", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
