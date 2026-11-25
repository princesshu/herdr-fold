"""What Claude or Codex starts with in a folder, for a chat and the Agent panel: model, effort, rules and imports,
skills, mode, sandbox, permissions, hooks, subagents, MCP servers, the newest chat's first turn, what a chat used. Only
read, every command theirs; a wrong setting counts as none. The agents: agent_state.py; the panel: agent_layers.py."""
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
import words  # noqa: E402
from connectors import brand  # noqa: E402
from jsonl import claude_project_dir, newest_first, obj, open_regular, parse  # noqa: E402
from locate import dot_git, find, repo_top, tool_env  # noqa: E402

CHARS_PER_TOKEN = 4             # the tokens a file costs, estimated: Claude's own count is not at hand
LARGEST = 1 << 20               # bytes of a rules file read: more is not a rule anyone keeps
CONFIG_LARGEST = 16 << 20       # bytes of ~/.claude.json read: it keeps every project's settings, it grows
GLOBAL, PROJECT, LOCAL, MANAGED, BUILT_IN = "Global", "Project", "Local", "Managed", "Built-in"
CLAUDE = "Claude"               # the source of Claude's own subagents
HERDR_FOLD = "herdr-fold"       # the source of the hook herdr-fold's chats pass Claude with --settings
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
LISTING = "agent_listing_delta"         # a session's line telling the subagents it added and removed
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
GENERAL = "general-purpose"     # the subagent Claude starts for an Agent call that names none
# the session lines that tell the MCP servers' state: their tools, their instructions, a compaction starting both over
TOLD = (b'"deferred_tools_delta"', b'"mcp_instructions_delta"', b'"compact_boundary"')
# the agents herdr-fold knows, in its order (agent_state.py's HOW: each one's program, sign-in and install)
KNOWN = {"claude": {"name": "Claude"}, "codex": {"name": "Codex"}, "gemini": {"name": "Gemini CLI"}}
# a mode in the chat's words
MODE_WORDS = {"default": "Manual", "manual": "Manual", "acceptEdits": "Edit automatically", "plan": "Plan",
              "auto": "Auto", "dontAsk": "Don't ask", "bypassPermissions": "Bypass permissions"}
# Codex's approval policy and sandbox in words
APPROVALS = {"untrusted": "Ask unless trusted", "on-request": "Ask on request", "on-failure": "Ask on failure",
             "never": "Never ask"}
SANDBOXES = {"read-only": "Read only", "workspace-write": "Workspace write", "danger-full-access": "Full access"}
# an effort in words: Claude's (effortLevel, CLAUDE_CODE_EFFORT_LEVEL) and Codex's (model_reasoning_effort)
EFFORTS = {"minimal": "Minimal", "low": "Low", "medium": "Medium", "high": "High", "xhigh": "Extra high", "max": "Max"}
# config.toml's lines read: a table's head, a key with a plain value (a string, true or false, a list on one line)
TOML_TABLE = re.compile(r"\s*\[([^\[\]]+)\]\s*(?:#.*)?")
TOML_VALUE = re.compile(r"""\s*([\w-]+)\s*=\s*("[^"\\]*"|'[^']*'|true|false|\[[^\]]*\])\s*(?:#.*)?""")
TOML_STRING = re.compile(r""""([^"\\]*)"|'([^']*)'""")
GATES = ("PreToolUse", "PermissionRequest")             # the hooks that decide a call, the others watch
CONTEXT = ("SessionStart", "UserPromptSubmit")          # the hooks whose output Claude reads as context
READ_ONLY = ("Read", "Grep", "Glob", "LS", "WebFetch", "WebSearch")     # a subagent with these alone reads only
WEB_DOMAIN = re.compile(r"WebFetch\(domain:([^()\s]+)\)")    # an allow rule whose host Claude's sandbox reaches too
IMPORT = re.compile(r"(?:^|\s)@([^\s`]+)")      # an @import in a rules file, outside its code
DEPTH = 5                       # imports Claude follows from one file, one into the next
CHAT = re.compile(r"[0-9a-f-]{36}")     # a session one of herdr-fold's chats may have started
ASK_TIMEOUT = 10                # seconds an agent may take to tell whether it is signed in, or to list its servers
ROLLOUTS = 200                  # Codex's newest chats looked through for the folder's
FIRST_LINE = 1 << 20            # bytes of a Codex chat's first line read
# Codex's rules' decisions as Claude's behaviors: it takes the most restrictive rule that matches, as Claude does
DECISIONS = {"allow": "allow", "prompt": "ask", "forbidden": "deny"}
CODEX_KINDS = {"stdio": "stdio", "streamable_http": "http"}      # `codex mcp list`'s transports as a row names them
OFF = "off"                     # a Codex server turned off: in its own configuration, everywhere
NOT_PLAIN = object()            # a rule's value Codex works out itself (a name, an expression): not read
AGENT_OFF = re.compile(r"Agent\(([\w.:-]{1,80})\)")     # the deny rule that turns one subagent off
EFFORT_ENV = "CLAUDE_CODE_EFFORT_LEVEL"


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


def rule(path, scope, home, via=None, paths=None, depth=0):
    """The rule in PATH ({path, scope, tokens, paths, via}: paths the globs it is read for, [] for always; VIA the file
    that imports it, with its PATHS), then each file it imports (@path outside its code: from its own folder, ~/ from
    HOME) as one more, DEPTH files deep at most; [] where PATH cannot be read."""
    text = read_text(path)
    if text is None:
        return []
    told = front_matter(text).get("paths", [])
    told = [told] if isinstance(told, str) and told else told if isinstance(told, list) else []
    found = [{"path": path, "scope": scope, "tokens": tokens(text), "paths": told if paths is None else paths,
              "via": via}]
    code = re.sub(r"`[^`\n]*`", "", re.sub(r"```.*?(```|$)", "", text, flags=re.S))
    for name in IMPORT.findall(code) if depth < DEPTH else ():
        name = os.path.join(home, name[2:]) if name.startswith("~/") else os.path.join(os.path.dirname(path), name)
        found += rule(os.path.normpath(name), scope, home, path, found[0]["paths"], depth + 1)
    return found


def ancestors(folder):
    """FOLDER and the folders above it, the highest first, up to and not including / (Claude reads each one's)."""
    found, here = [], os.path.abspath(folder)
    while os.path.dirname(here) != here:
        found.append(here)
        here = os.path.dirname(here)
    return found[::-1]


def rule_places(folder, home):
    """Where Claude looks for rules in FOLDER, in its order, each with its scope: the user's own (Global), each folder's
    from the highest down (Project; AGENTS.md too, read by Codex and by whoever imports it), the folder's .claude/rules,
    then CLAUDE.local.md (Local)."""
    personal = os.path.join(home, ".claude")
    places = [(os.path.join(personal, "CLAUDE.md"), GLOBAL)]
    places += [(path, GLOBAL) for path in sorted(glob.glob(os.path.join(personal, "rules", "**", "*.md"),
                                                             recursive=True))]
    for here in ancestors(folder):
        places += [(os.path.join(here, "CLAUDE.md"), PROJECT), (os.path.join(here, ".claude", "CLAUDE.md"), PROJECT),
                   (os.path.join(here, "AGENTS.md"), PROJECT)]
    places += [(path, PROJECT) for path in sorted(glob.glob(os.path.join(folder, ".claude", "rules", "**", "*.md"),
                                                            recursive=True))]
    return places + [(os.path.join(here, "CLAUDE.local.md"), LOCAL) for here in ancestors(folder)]


def rules(folder, home):
    """The rules Claude reads in FOLDER, in its order (rule_places()'s), each followed by the files it imports; each
    file once."""
    found, seen = [], set()
    for path, scope in rule_places(folder, home):
        for one in rule(path, scope, home):
            if os.path.realpath(one["path"]) not in seen:
                seen.add(os.path.realpath(one["path"]))
                found.append(one)
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
    """Claude's settings files for FOLDER with their scopes, each over the one before: the user's, the project's, the
    local ones, then the organization's (managed-settings.json, then its drop-in folder's by name)."""
    return [(os.path.join(home, ".claude", "settings.json"), GLOBAL),
            (os.path.join(folder, ".claude", "settings.json"), PROJECT),
            (os.path.join(folder, ".claude", "settings.local.json"), LOCAL),
            (os.path.join(MANAGED_DIR, "managed-settings.json"), MANAGED)] + \
        [(path, MANAGED) for path in sorted(glob.glob(os.path.join(MANAGED_DIR, "managed-settings.d", "*.json")))]


def setting(folder, home, key, env):
    """What Claude starts with in FOLDER for the settings KEY (its names, one in the next): ENV as the last settings
    file's env sets it, else as this environment does, else the last settings file's KEY (the organization's over
    every other); None for none."""
    files = [read_json(path) for path, _ in settings(folder, home)][::-1]
    found = [obj(one.get("env")).get(env) for one in files] + [os.environ.get(env)]
    for one in files:
        for name in key:
            one = obj(one).get(name)
        found.append(one)
    return next((one for one in found if isinstance(one, str) and one.strip()), None)


def effort_told(folder, home, model):
    """The effort Claude starts MODEL with in FOLDER (setting()'s, EFFORT_ENV over the files): the one kept under
    MODEL's own id where it takes one of its own (words.own_effort()), else the settings' one effortLevel."""
    own = words.own_effort(model)
    return setting(folder, home, ("modelSettings", own, "effortLevel") if own else ("effortLevel",), EFFORT_ENV)


def turned_off(folder, home):
    """What Claude's settings files turn off in FOLDER, the keys the Agent panel's forms write (harness.py): {"skills"
    (skillOverrides: "off"), "agents" (a deny rule, Agent(name)), "servers" (deniedMcpServers): the names; "hooks":
    whether a file has disableAllHooks}."""
    found = {"skills": [], "agents": [], "servers": [], "hooks": False}
    for path, _ in settings(folder, home):
        table = read_json(path)
        found["skills"] += [name for name, value in obj(table.get("skillOverrides")).items() if value == "off"]
        found["agents"] += [one.group(1) for one in map(AGENT_OFF.fullmatch, strings(permission_table(path).get(
            "deny"))) if one]
        found["servers"] += strings([obj(one).get("serverName") for one in table.get("deniedMcpServers") or []
                                     if isinstance(table.get("deniedMcpServers"), list)])
        found["hooks"] = found["hooks"] or table.get("disableAllHooks") is True
    return found


def sandbox(folder, home):
    """Claude's Bash sandbox in FOLDER: {on, hosts, scope, path} of the last settings file that turns it on or off
    (sandbox.enabled); HOSTS the domains its commands reach unasked, each file's network.allowedDomains and
    WebFetch(domain:…) allow rules, as Claude merges them. None where no file turns it on or off."""
    found, hosts = None, []
    for path, scope in settings(folder, home):
        table = read_json(path)
        box = obj(table.get("sandbox"))
        found = {"on": box["enabled"], "scope": scope, "path": path} if isinstance(box.get("enabled"), bool) \
            else found
        hosts += strings(obj(box.get("network")).get("allowedDomains"))
        hosts += [one.group(1) for one in map(WEB_DOMAIN.fullmatch, strings(permission_table(path).get("allow")))
                  if one]
    return found and {**found, "hosts": list(dict.fromkeys(hosts))}


def permission_table(path):
    found = read_json(path).get("permissions")
    return found if isinstance(found, dict) else {}


def mode_told(folder, home):
    """The mode Claude starts in for FOLDER unasked (permissions.defaultMode) and who tells it: {mode, scope, path} of
    the last settings file that names one of Claude's modes, the organization's over every other; None where none."""
    found = None
    for path, scope in settings(folder, home):
        mode = permission_table(path).get("defaultMode")
        found = {"mode": mode, "scope": scope, "path": path} if isinstance(mode, str) and mode in MODES else found
    return found


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
    found, seen = [], set()
    for path, scope in sorted(settings(folder, home), key=lambda one: one[1] != MANAGED):
        table = permission_table(path)
        for behavior in BEHAVIORS:
            listed = table.get(behavior)
            for text in (rule_text(value) for value in (listed if isinstance(listed, list) else [])):
                if text and (text, behavior) not in seen:
                    seen.add((text, behavior))
                    found.append({"rule": text, "behavior": behavior, "scope": scope, "path": path})
    counts = {behavior: sum(one["behavior"] == behavior for one in found) for behavior in BEHAVIORS}
    mode = (mode_told(folder, home) or {}).get("mode")
    return {**counts, "mode": mode, "rules": found, "conflicts": conflicts(found)}


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
    for path, scope in settings(folder, home):
        plugins = read_json(path).get("enabledPlugins") if scope != MANAGED else None
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
            found.append((name.split("@")[0], GLOBAL if mine[0].get("scope", "user") == "user" else PROJECT,
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
    """The skills Claude can use in FOLDER: the user's own (Global), the project's, then the enabled plugins'."""
    return skills_in(((os.path.join(home, ".claude", "skills"), GLOBAL),
                      (os.path.join(folder, ".claude", "skills"), PROJECT))) + plugin_skills(folder, home)


def agent(path, scope, source):
    """The subagent PATH defines ({name, description, model, tools, scope, source, path}), or None where Claude would
    not load it: its front matter's name (not "-…", no ":") and description are a must. Model None: Claude's default
    for a subagent; tools []: none listed, every tool its own."""
    text = read_text(path)
    meta = front_matter(text) if text is not None else {}
    name, description, model = meta.get("name"), meta.get("description"), meta.get("model")
    if not (isinstance(name, str) and name and name[0] != "-" and ":" not in name and isinstance(description, str)
            and description):
        return None
    return {"name": name, "description": description, "model": model if isinstance(model, str) and model else None,
            "tools": tool_list(meta.get("tools")), "scope": scope, "source": source, "path": path}


def tool_list(value):
    """A subagent's tools as its front matter lists them: `Read, Grep`, `["Read", "Grep"]` or `- Read` lines."""
    if isinstance(value, str):
        value = value.strip()
        value = (value[1:-1] if value[:1] == "[" and value[-1:] == "]" else value).split(",")
    return [unquote(one) for one in value if isinstance(one, str) and unquote(one)] if isinstance(value, list) else []


def built_in_agents(session):
    """Claude's own subagents as the session file SESSION's listings leave them (each adds and removes; one marked
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
    """The subagents Claude can start in FOLDER: the user's own (Global), the project's, each enabled plugin's (its
    name as source; Claude calls it plugin:name), then Claude's own as SESSION (a session file's path) lists them. As
    in Claude, a project's agent hides the user's of its name, either a built-in one."""
    found = []
    for base, scope in ((os.path.join(home, ".claude", "agents"), GLOBAL),
                        (os.path.join(folder, ".claude", "agents"), PROJECT)):
        found += [agent(path, scope, scope) for path in sorted(glob.glob(os.path.join(base, "*.md")))]
    for name, scope, root in plugins(folder, home):
        found += [agent(path, scope, name) for path in sorted(glob.glob(os.path.join(root, "agents", "*.md")))]
    found = [one for one in found if one] + built_in_agents(session)
    rank = {CLAUDE: 0, GLOBAL: 1, PROJECT: 2}         # a plugin's agent, named plugin:name, hides none of these
    key = lambda one: one["name"] if one["source"] in rank else f"{one['source']}:{one['name']}"     # noqa: E731
    starts = {}
    for one in found:
        if key(one) not in starts or rank.get(one["source"], 0) >= rank.get(starts[key(one)]["source"], 0):
            starts[key(one)] = one
    return [one for one in found if starts[key(one)] is one]


# --- hooks, the newest chat

def hooked(table, scope, source, path):
    """The hooks in TABLE ({event: [{matcher, hooks: [{type, command}]}]}, from the file PATH): {event, matcher, name
    (its command's script, else its program; a prompt's type), command, kind (gate, context or watch), scope, source,
    path}."""
    found = []
    for event, groups in obj(table).items():
        for group in groups if isinstance(event, str) and isinstance(groups, list) else []:
            matcher = obj(group).get("matcher")
            for one in map(obj, obj(group).get("hooks") if isinstance(obj(group).get("hooks"), list) else []):
                command = clean(one.get("command"), None) if one.get("type", "command") == "command" else None
                try:
                    said = shlex.split(command or "")
                except ValueError:
                    said = (command or "").split()
                name = os.path.basename(next((word for word in said if "/" in word), said[0] if said else "")) \
                    if one.get("type", "command") == "command" else clean(one.get("type"))
                if name:
                    found.append({"event": event, "matcher": clean(matcher) if isinstance(matcher, str) else None,
                                  "name": clean(name, LINE), "command": command,
                                  "kind": "gate" if event in GATES else "context" if event in CONTEXT else "watch",
                                  "scope": scope, "source": source, "path": path})
    return found


def hooks(folder, home, session=None, stopped=False):
    """Every hook Claude runs in FOLDER: each settings file's in its order, each enabled plugin's (hooks/hooks.json, or
    what its plugin.json names), herdr-fold's own where SESSION is one of its chats. None with disableAllHooks, but
    for STOPPED (those it stops); the organization's alone with its allowManagedHooksOnly."""
    files = [(path, scope, read_json(path)) for path, scope in settings(folder, home)]
    if not stopped and any(table.get("disableAllHooks") is True for _, _, table in files):
        return []
    managed_only = any(table.get("allowManagedHooksOnly") is True for _, scope, table in files if scope == MANAGED)
    found = [one for path, scope, table in files if scope == MANAGED or not managed_only
             for one in hooked(table.get("hooks"), scope, scope, path)]
    for name, scope, root in [] if managed_only else plugins(folder, home):
        manifest = os.path.join(root, ".claude-plugin", "plugin.json")
        named = read_json(manifest).get("hooks")
        places = [os.path.join(root, "hooks", "hooks.json")] + \
            ([os.path.normpath(os.path.join(root, named))] if isinstance(named, str) else [])
        found += [one for path in places for one in hooked(read_json(path).get("hooks"), scope, name, path)]
        found += hooked(obj(named).get("hooks"), scope, name, manifest)
    if chat_status(session, home) is not None:
        found.append({"event": "PermissionRequest", "matcher": "*", "name": HERDR_FOLD, "command": None,
                      "kind": "gate", "scope": HERDR_FOLD, "source": HERDR_FOLD, "path": None})
    return found


def chat_status(session, home):
    """What herdr-fold keeps of the status line of its chat in the session file SESSION ({model, effort, window, …}),
    or None where SESSION is none of its chats."""
    key = os.path.basename(session or "")[:-len(".jsonl")]
    path = os.path.join(home, ".local", "state", HERDR_FOLD, "chat", key, "status.json")
    return read_json(path) if CHAT.fullmatch(key) and os.path.isfile(path) else None


def first_turn(agent, path):
    """What AGENT's first answer in the chat file PATH started from: {"tokens": its prompt, the cache's reads and
    writes in it, "model", "window" and "effort": the ones Codex tells}, each None where not told (no answer yet, no
    file)."""
    model = effort = None
    none = {"tokens": None, "model": None, "window": None, "effort": None}
    try:
        with open_regular(path, "rb") as f:
            for raw in f:
                entry = parse(raw) if b'"usage"' in raw or b'"token_count"' in raw or b'"turn_context"' in raw else {}
                told = obj(entry.get("payload"))
                if agent == "codex" and entry.get("type") == "turn_context":
                    model = told.get("model") if isinstance(told.get("model"), str) else model
                    effort = told.get("effort") if told.get("effort") in EFFORTS else effort
                info = obj(told.get("info")) if agent == "codex" and told.get("type") == "token_count" else {}
                if info:
                    window = info.get("model_context_window")
                    return {"tokens": tokens_in(obj(info.get("last_token_usage")), ("input_tokens",)), "model": model,
                            "window": window if type(window) is int and window > 0 else None, "effort": effort}
                message = obj(entry.get("message"))
                if agent == "claude" and entry.get("type") == "assistant" and entry.get("isSidechain") is not True \
                        and isinstance(message.get("usage"), dict) and message.get("model") != "<synthetic>":
                    return {"tokens": tokens_in(message["usage"], ("input_tokens", "cache_creation_input_tokens",
                                                                   "cache_read_input_tokens")),
                            "model": message.get("model") if isinstance(message.get("model"), str) else None,
                            "window": None, "effort": None}
    except (OSError, TypeError):
        return none
    return {**none, "model": model, "effort": effort}


def tokens_in(usage, keys):
    return sum(usage[key] for key in keys if type(usage.get(key)) is int and usage[key] > 0)


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
    for found in [entry] + [read_json(path) for path, _ in settings(folder, home)]:
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
        listed(config.get("mcpServers"), GLOBAL, GLOBAL, config_path) + list(connected) + \
        plugin_servers(folder, home)


def server_rows(folder, home, calls, denied=()):
    """Claude's MCP servers in FOLDER, in its /mcp order (the project's, the local ones, the user's, claude.ai's, the
    plugins'; the organization's alone where it has any), their state as the newest session tells it (a connector's
    anywhere; off here for one of DENIED), and their CALLS in the open chat ({a server's tool key: calls}, use()'s)."""
    config = read_json(os.path.join(home, ".claude.json"), CONFIG_LARGEST)
    entry = obj(obj(config.get("projects")).get(project_key(folder)))
    project, read = mcpjson(folder, home, entry), {}
    here = telling(glob.glob(os.path.join(claude_project_dir(folder, home), "*.jsonl")), read)
    anywhere = telling(glob.glob(os.path.join(home, ".claude", "projects", "*", "*.jsonl")), read)
    found = defined(folder, home, config, connectors(config, (here, anywhere)))
    keys = {tool_key(one["name"]) for one in found}
    off = set(strings(entry.get("disabledMcpServers"))) | set(denied)
    told_by = {False: (here, owned(here, keys)), True: (anywhere, owned(anywhere, keys))}
    for one in found:
        said, lines = told_by[one["kind"] == CLAUDE_AI]         # a connector is the account's: as told anywhere
        one.update(state(one, said, lines.get(tool_key(one["name"]), []), off, project),
                   used=calls.get(tool_key(one["name"]), 0))
    return found


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
    """What Claude starts with in FOLDER for HOME's user: model, effort, rules, skills, permissions, sandbox, hooks,
    "stopped" (the hooks disableAllHooks stops), agents, servers, "off" (turned_off(): a skill's and a subagent's own
    "off" too), use, "start" (the newest chat's first turn) and "unread"; SESSION the open chat's file."""
    used = use(session)
    newest = (newest_first(glob.glob(os.path.join(glob.escape(claude_project_dir(folder, home)), "*.jsonl"))) or
              [None])[0]
    status, start = chat_status(newest, home) or {}, first_turn("claude", newest)
    start.update(window=status["window"] if type(status.get("window")) is int else None,
                 model=start["model"] or clean(status.get("model"), LINE),
                 effort=status.get("effort") if status.get("effort") in EFFORTS else None)
    model, off = setting(folder, home, ("model",), "ANTHROPIC_MODEL"), turned_off(folder, home)
    effort = effort_told(folder, home, model or start["model"])
    files = [path for path, _ in settings(folder, home)] + [path for path, _ in rule_places(folder, home)] + \
        [os.path.join(home, ".claude.json"), os.path.join(folder, ".mcp.json")]
    return {"model": model, "effort": effort if effort in EFFORTS else None, "rules": rules(folder, home),
            "skills": [{**one, "off": not plugged(one) and one["name"] in off["skills"]}
                       for one in skills(folder, home)],
            "permissions": permissions(folder, home), "sandbox": sandbox(folder, home),
            "hooks": hooks(folder, home, session),
            "stopped": hooks(folder, home, session, True) if off["hooks"] else [],
            "agents": [{**one, "off": not plugged(one) and one["name"] in off["agents"]}
                       for one in agents(folder, home, session)],
            "servers": server_rows(folder, home, used["servers"], off["servers"]), "off": off,
            "use": used, "start": start, "unread": unread(files)}


def unread(paths):
    """Those of PATHS that are there but cannot be read, each once."""
    return [path for path in dict.fromkeys(paths) if os.path.lexists(path) and not os.access(path, os.R_OK)]


# --- Codex's setup, in the rows Claude's take

def codex_home(home):
    """Codex's own folder: CODEX_HOME, as Codex takes it, else HOME's .codex."""
    return os.environ.get("CODEX_HOME") or os.path.join(home, ".codex")


def toml_values(path):
    """A config.toml's plain values (a string, true or false, a list of strings on one line), its tables' nested by
    their heads: {"model": …, "sandbox_workspace_write": {"network_access": …}}."""
    found = table = {}
    for line in (read_text(path) or "").split("\n"):
        head, pair = TOML_TABLE.fullmatch(line), TOML_VALUE.fullmatch(line)
        if head:
            table = found.setdefault(head.group(1).strip(), {})
        elif pair:
            raw = pair.group(2)
            table[pair.group(1)] = raw == "true" if raw in ("true", "false") else raw[1:-1] if raw[0] in "\"'" \
                else [a or b for a, b in TOML_STRING.findall(raw)]
    return found


def codex_trusted(folder, home):
    """Whether Codex trusts FOLDER, or a folder above it in its repository: trust_level "trusted" under that folder's
    [projects."<path>"] (or '<path>') in its home's config."""
    tables = toml_values(os.path.join(codex_home(home), "config.toml"))
    return any(obj(tables.get(head)).get("trust_level") == "trusted" for here in project_folders(folder)
               for head in (f"projects.{json.dumps(here, ensure_ascii=False)}", f"projects.'{here}'"))


def codex_files(home, folder=None):
    """Codex's config files with their scopes, each over the one before: its home's (Global; its values left out
    where it names a profile, whose own are not read), then for a FOLDER Codex trusts each .codex/config.toml from
    its repository's top down to it (Project): [(path, scope, toml_values()'s)]."""
    path = os.path.join(codex_home(home), "config.toml")
    found = [(path, GLOBAL, {} if "profile" in toml_values(path) else toml_values(path))]
    for here in project_folders(folder) if folder and codex_trusted(folder, home) else []:
        found.append((os.path.join(here, ".codex", "config.toml"), PROJECT,
                      toml_values(os.path.join(here, ".codex", "config.toml"))))
    return found


def codex_config(home, folder=None):
    """What Codex's config files (codex_files()'s) set together: a later file's value over an earlier one's."""
    found = {}
    for _, _, values in codex_files(home, folder):
        found.update(values)
    return found


def codex_told(home, folder, key):
    """Which of Codex's config files sets its top-level KEY for FOLDER, the last that does: {scope, path}, or None."""
    return next(({"scope": scope, "path": path} for path, scope, values in codex_files(home, folder)[::-1]
                 if key in values), None)


def codex_sandbox(folder, home, config):
    """Codex's sandbox as its CONFIG (codex_config()'s) sets it: {mode, writes (FOLDER's name, /tmp and its writable
    roots, in workspace-write), network, scope, path}; None where it sets none."""
    mode, told = config.get("sandbox_mode"), obj(config.get("sandbox_workspace_write"))
    if mode not in SANDBOXES:
        return None
    writes = [os.path.basename(os.path.abspath(folder))] + ["/tmp"] * (told.get("exclude_slash_tmp") is not True) + \
        strings(told.get("writable_roots")) if mode == "workspace-write" else []
    return {"mode": mode, "writes": writes, "network": told.get("network_access") is True,
            **codex_told(home, folder, "sandbox_mode")}


READ = ("claude", "codex")      # the agents whose setup setup() reads


def project_folders(folder):
    """FOLDER and the folders above it up to its repository's top, the top first (FOLDER alone outside one)."""
    folder = os.path.abspath(folder)
    top = repo_top(folder) or folder
    return [here for here in ancestors(folder) if here == top or here.startswith(top.rstrip(os.sep) + os.sep)]


def codex_rules(folder, home):
    """The rules Codex reads in FOLDER, in its order: its home's (Global), then each folder's from the repository's
    top down to FOLDER (Project); in each, AGENTS.override.md, else AGENTS.md, the first that holds anything."""
    found = []
    for here, scope in [(codex_home(home), GLOBAL)] + [(here, PROJECT) for here in project_folders(folder)]:
        for path in (os.path.join(here, "AGENTS.override.md"), os.path.join(here, "AGENTS.md")):
            text = read_text(path)
            if text and text.strip():
                found.append({"path": path, "scope": scope, "tokens": tokens(text), "paths": [], "via": None})
                break
    return found


def codex_skills(folder, home):
    """The skills Codex can use in FOLDER: its home's and the user's .agents ones (Global; Codex's own, .system,
    left out), then each folder's .agents/skills from the repository's top down to FOLDER (Project)."""
    return skills_in([(os.path.join(codex_home(home), "skills"), GLOBAL),
                      (os.path.join(home, ".agents", "skills"), GLOBAL)] +
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


def codex_permissions(home, folder=None):
    """Codex's prefix rules ($CODEX_HOME/rules/*.rules, by name) in permissions()'s shape: the pattern's words as the
    rule, prompt as ask, forbidden as deny; a rule wider than another hides it (Codex's most restrictive wins); "mode"
    its approval policy as codex_config() reads it for FOLDER, or None, "told" the file that sets it (codex_told())."""
    found, seen, patterns = [], set(), {}
    for path in sorted(glob.glob(os.path.join(codex_home(home), "rules", "*.rules"))):
        for pattern, behavior in prefix_rules(path):
            text = pattern_text(pattern)
            patterns[text] = pattern
            if (text, behavior) not in seen:
                seen.add((text, behavior))
                found.append({"rule": text, "behavior": behavior, "scope": GLOBAL, "path": path})
    counts = {behavior: sum(one["behavior"] == behavior for one in found) for behavior in BEHAVIORS}
    mode = codex_config(home, folder).get("approval_policy")
    return {**counts, "mode": mode, "told": codex_told(home, folder, "approval_policy"), "rules": found,
            "conflicts": conflicts(found, lambda wide, narrow: len(
        patterns[wide]) <= len(patterns[narrow]) and all(set(alts) >= set(their) for alts, their in zip(
            patterns[wide], patterns[narrow])))}


def codex_servers(binary, folder, home):
    """Codex's MCP servers as its own list gives them (`codex mcp list --json` in FOLDER: its configuration, nothing
    checked), in its order: on, off or sign in; None where it gives no list. Env, headers, a URL's query never kept."""
    try:
        code, out, _ = run([binary, "mcp", "list", "--json"], folder)
        listed = json.loads(out) if code == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError, RecursionError):
        return None
    if not isinstance(listed, list):
        return None
    found, path = [], os.path.join(codex_home(home), "config.toml")
    for entry in listed:
        transport = obj(obj(entry).get("transport"))
        kind = CODEX_KINDS.get(transport.get("type")) if isinstance(transport.get("type"), str) else None
        one = kind and server(entry.get("name"), {"type": kind, **{key: transport.get(key) for key in (
            "command", "args", "url")}}, GLOBAL, GLOBAL, path)
        if one:
            one["state"] = OFF if entry.get("enabled") is False else \
                SIGN_IN if entry.get("auth_status") == "not_logged_in" else ON
            if entry.get("auth_status") == "o_auth":    # in through Codex's own OAuth: it signs out
                one["signed"] = True
            found.append(one)
    return found


def codex_setup(folder, home):
    """What Codex starts with in FOLDER for the user whose home is HOME, in the rows Claude's take: {"model", "effort",
    "rules", "skills", "permissions", "sandbox", "hooks" (its hooks.json's), "agents": [] (it names none of its own),
    "servers" ("unlisted": it gave no list), "use": none, "start" (its first turn), "unread"}; None: not here."""
    binary = find("codex")
    if not binary:
        return None
    config, own, servers = codex_config(home, folder), codex_home(home), codex_servers(binary, folder, home)
    effort, hooks_file = config.get("model_reasoning_effort"), os.path.join(own, "hooks.json")
    return {"model": config.get("model") if isinstance(config.get("model"), str) else None,
            "effort": effort if effort in EFFORTS else None, "rules": codex_rules(folder, home),
            "skills": codex_skills(folder, home), "permissions": codex_permissions(home, folder),
            "sandbox": codex_sandbox(folder, home, config),
            "hooks": hooked(read_json(hooks_file).get("hooks"), GLOBAL, GLOBAL, hooks_file),
            "agents": [], "servers": servers or [], "unlisted": servers is None, "use": {},
            "start": first_turn("codex", rollout(folder, home)),
            "unread": unread([os.path.join(own, name) for name in ("config.toml", "hooks.json", "AGENTS.md")])}


def rollout(folder, home):
    """Codex's newest chat started in FOLDER (its own, no helper's), or None."""
    place = os.path.join(glob.escape(codex_home(home)), "sessions", "*", "*", "*", "rollout-*.jsonl")
    for path in newest_first(glob.glob(place))[:ROLLOUTS]:
        try:
            with open_regular(path, "rb") as f:
                meta = obj(parse(f.readline(FIRST_LINE)).get("payload"))
        except OSError:
            continue
        if meta.get("cwd") == folder and "subagent" not in obj(meta.get("source")):
            return path
    return None


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


# --- what the readers of a setup share: a file as it is named, a plugin's row, the open conversation

LINE = 120                      # characters of a line shown: a rule's, a model's name, a hook's
SESSION_ID = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]*")      # a chat's id, as the app tells it: never a path


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


def main(argv):
    """The Herdr app mod runs this on the space's machine, answering in JSON: claude FOLDER [SESSION] and codex FOLDER
    (setup()'s). The Agent panel's layers: agent_layers.py."""
    if argv[1:2] == ["claude"] and len(argv) in (3, 4) or argv[1:2] == ["codex"] and len(argv) == 3:
        print(json.dumps(setup(argv[1], argv[2], os.path.expanduser("~"), argv[3] if len(argv) == 4 else None)))
        return 0
    print("usage: agent_setup.py claude FOLDER [SESSION] | codex FOLDER", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
