# Generated from core/agent_layers.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""The Agent panel's layers of what agent_setup.py reads, in both clients' words: the head, the bar, the sections with
their rows, each row's properties and actions, what a sign-in and the add form say. Only read; a module of its own, so
a helper that reads a setup alone does not carry it. The command: agent_layers_cli.py."""
import os
import re
import shlex
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import words  # noqa: E402
from agent_setup import (APPROVALS, BEHAVIORS, BUILT_IN, CLAUDE, CLAUDE_AI, EFFORTS, FAILED, GLOBAL,  # noqa: E402
                         HERDR_FOLD, KNOWN, LINE, MANAGED, MODE_WORDS, NOT_APPROVED, NOT_CHECKED, OFF, OFF_HERE, ON,
                         PENDING, PROJECT, READ_ONLY, SANDBOXES, SIGN_IN, clean, inside, mode_told, plugged,
                         read_text, shown)
from connectors import CLAUDE_AI as CLAUDE_PAGE, logout  # noqa: E402
from jsonl import obj  # noqa: E402

# the owner's order (2026-11-20): who works (the subagents), what they read always, then on demand, what they may
# do, what they reach; Usage, the clients' own, before them all in both clients
SECTIONS = (("subagents", "Subagents"), ("rules", "Rules"), ("skills", "Skills"), ("permissions", "Permissions"),
            ("connectors", "Connectors"))
PARTS = ("rules", "skills", "connectors")       # what loads at start, the bar's parts and their sections' swatches
# a server's state in its row's word and tone; a dim row's server does not run here
SAID_AS = {ON: ("on", "ok"), FAILED: ("failed", "bad"), SIGN_IN: ("sign in", "warn"), PENDING: ("connecting", "busy"),
           NOT_APPROVED: ("not approved", "off"), OFF_HERE: ("off here", "off"), OFF: ("off", "off"),
           NOT_CHECKED: ("not checked", "off")}
DIM = (NOT_APPROVED, OFF_HERE, OFF)
NOT_READ = {"text": "not read", "tone": "off"}      # a part that could not be read: said in its place, never left out
OFF_STATE = {"text": SAID_AS[OFF_HERE][0], "tone": SAID_AS[OFF_HERE][1]}    # a skill, a subagent, the hooks: off here
DEFAULT = "Default"             # the tag of what no file sets: the agent's own default
PROBLEMS = ((FAILED, "failed", "bad"), (SIGN_IN, "sign in", "warn"))    # first in their section, a chip each
FIRST_LINES = 3                 # lines of a rule its properties show
NAMED = 3                       # Claude's own subagents their folded row names before "N more"
PATH_IN = re.compile(r"""['"]?((?:~|\.{1,2})?/[^\s'":,;()]+)['"]?""")      # a file named in an error


def tag(one):
    """The tag of the reader's row ONE: a plugin's name, claude.ai, else its scope (Default: what no file sets)."""
    return one["source"] if one["scope"] != DEFAULT and (plugged(one) or one.get("source") == CLAUDE_AI) \
        else one["scope"]


def origin(one, folder, home):
    """Where ONE comes from, a properties line: a plugin by its name, claude.ai and Claude's own, else its file."""
    if plugged(one) and one["scope"] != DEFAULT:
        return ["From", one["source"], "Plugin"]
    return ["From", one["source"] if one.get("source") in (CLAUDE_AI, CLAUDE) or one["scope"] == DEFAULT
            else shown(one["path"], folder, home), None if one["scope"] == DEFAULT else one["scope"]]


def used_line(calls):
    return [["Used", ("once" if calls == 1 else f"{calls} times") + " in this chat", None]] if calls else []


def act(kind, label, path=None, server=None):
    return {"id": kind, "label": label, "path": path, "server": server, "primary": False}


def opened(paths, folder, home):
    """Open for each of PATHS (once each), by the file's name; by where it is where two share a name."""
    paths = list(dict.fromkeys(paths))
    names = [os.path.basename(path) for path in paths]
    return [act("open", "Open " + (shown(path, folder, home) if names.count(name) > 1 else name), path)
            for path, name in zip(paths, names)]


def apart(error):
    """ERROR's words without the files it names, and those files (a properties tip), each None for none: an error
    says what failed and why, never a file name."""
    if not error:
        return None, None
    files = [one for one in PATH_IN.findall(error)]
    said = re.sub(r"\s+([:,.;])", r"\1", re.sub(r"\s{2,}", " ", PATH_IN.sub("", error))).strip(" :,;")
    return said or "failed", ", ".join(files) or None


def properties(title, state=None, lines=(), text=None, error=None, actions=()):
    """A row's properties: its title and state, label and value lines (a third column at the right, or None), a text
    and an error shown as they are (the files the error names its tip), its actions, the first one primary."""
    error, tip = apart(error)
    return {"title": title, "state": state, "lines": [list(one) for one in lines], "text": text, "error": error,
            "tip": tip, "actions": [{**one, "primary": not n} for n, one in enumerate(actions)]}


def layer(key, icon, name, props, note=None, mark=None, place=None, state=None, tokens=None, agents=(), dim=False,
          known=None):
    """A row of the panel: KEY its id, PLACE its tag, MARK its one mark (bad failed, warn sign in or a conflict, ok used
    in this chat), KNOWN a connector's brand; its cost by the number rule beside its TOKENS."""
    return {"id": key, "icon": icon, "name": name, "note": note, "tag": place, "mark": mark, "state": state,
            "brand": known, "tokens": tokens, "cost": None if tokens is None else words.tokens(tokens),
            "agents": list(agents), "dim": dim, "properties": props}


def first_lines(path):
    """The first FIRST_LINES lines of the file PATH, past its front matter and blank lines, as text, each cut."""
    lines = (read_text(path) or "").split("\n")
    if lines[0].strip() == "---":
        lines = lines[next((n for n, line in enumerate(lines[1:], 1) if line.strip() == "---"), 0) + 1:]
    return "\n".join([line for line in (clean(one, LINE) for one in lines) if line][:FIRST_LINES]) or None


def rule_name(path, scope, folder, home):
    """A rule's name: in FOLDER its file's, else its way there ("~/.claude/CLAUDE.md", "../CLAUDE.md"), so a Global
    and a Project CLAUDE.md never read as one file twice."""
    return os.path.basename(path) if inside(path, folder) else "~/" + os.path.relpath(path, home) \
        if scope == GLOBAL and inside(path, home) else os.path.relpath(path, folder)


def rule_rows(setup, agent, folder, home):
    """The rules, in the agent's order: an imported one says by which, a path-scoped one dim with its paths."""
    rows = []
    for one in setup["rules"]:
        path, paths = one["path"], one["paths"]
        name = rule_name(path, one["scope"], folder, home)
        lines = [origin(one, folder, home)] + ([["Paths", ", ".join(paths), None]] if paths else []) + \
            ([["Imported by", shown(one["via"], folder, home), None]] if one["via"] else [])
        spoken = ", ".join(paths[:-1]) + " or " + paths[-1] if len(paths) > 1 else "".join(paths)
        note = f"imported by {rule_name(one['via'], one['scope'], folder, home)}" if one["via"] else \
            f"when {spoken} is read" if paths else None
        rows.append(layer("rule:" + path, "file", name, properties(name, lines=lines, text=first_lines(path),
                                                                     actions=opened([path], folder, home)),
                          note=note, place=tag(one), tokens=one["tokens"], agents=one.get("agents", [agent]),
                          dim=bool(paths)))
    return rows


def hook_key(one):
    """The id of the hook ONE's row, and of its node in the graph."""
    return f"hook:{one['path']}:{one['event']}:{one['matcher']}:{one['name']}"


def hook_rows(setup, agent, folder, home):
    """The hooks, the gates first: each with its event (and matcher), a context one saying so, what it runs; those
    disableAllHooks stops in their place, dim."""
    rows, stopped = [], not setup["hooks"] and setup.get("stopped") or []
    for one in sorted(setup["hooks"] or stopped, key=lambda one: one["kind"] != "gate"):
        on = " · ".join([one["event"]] + [one["matcher"]] * (one["matcher"] not in (None, "", "*")))
        own = one["source"] == HERDR_FOLD
        state = {"text": "hook", "tone": "muted"}
        lines = [["On", on, None], ["From", "this chat's settings", HERDR_FOLD] if own else origin(one, folder, home)]
        rows.append(layer(hook_key(one), "hook", one["name"], properties(
            one["name"], state, lines + [["Runs", one["command"], None]] * bool(one["command"]),
            actions=opened([one["path"]] if one["path"] else [], folder, home)),
            note=f"{one['event']} · adds context" if one["kind"] == "context" else f"on {on}",
            place=tag(one), state=state, agents=[agent], dim=bool(stopped)))
    return rows


def permission_rows(setup, agent, folder, home):
    """First what the agent starts with (Claude's mode, Codex's approval policy: its words the note), then its sandbox,
    each from the file that sets it, else the agent's own default; then each conflict, in place of the rule it hides
    (the sentence its note, both rules its lines), then every other rule with its behavior."""
    table, rows, box, codex = setup["permissions"], [], setup["sandbox"], agent == "codex"
    own = {"scope": DEFAULT, "source": f"{KNOWN[agent]['name']}'s default", "path": None}
    told = (table["told"] if table["mode"] in APPROVALS else None) if codex else mode_told(folder, home)
    name, word = ("Approval", APPROVALS[table["mode"]] if told else own["source"]) if codex else (
        "Mode", MODE_WORDS[told["mode"] if told else "default"])
    rows.append(layer(name.lower(), "shield", name, properties(
        name, lines=[origin(told or own, folder, home)], actions=opened([told["path"]] if told else [], folder, home)),
        note=word, place=tag(told or own), agents=[agent]))
    hosts = len(box.get("hosts", [])) if box else 0
    word = (SANDBOXES[box["mode"]] if box else own["source"]) if codex else "Bash" + (
        f" · {hosts} host{'s' * (hosts != 1)}" if hosts else "") if box and box["on"] else "off"
    more = [] if not box else [["Writes", ", ".join(box["writes"]), None]] * bool(box["writes"]) + [
        ["Network", "on" if box["network"] else "off", None]] if codex else \
        [["Hosts", ", ".join(box["hosts"]), None]] * bool(box["hosts"] and box["on"])
    lines = [origin(box or own, folder, home)] + more
    rows.append(layer("sandbox", "shield", "Sandbox", properties(
        "Sandbox", lines=lines, actions=opened([box["path"]] if box else [], folder, home)), note=word,
        place=tag(box or own), agents=[agent]))
    hidden = {(one["hides"]["behavior"], one["hides"]["rule"]) for one in table["conflicts"]}
    for one in table["conflicts"]:
        hides = one["hides"]
        lines = [[hides["behavior"].capitalize(), hides["rule"], hides["scope"]],
                 [one["behavior"].capitalize(), one["rule"], one["scope"]]]
        rows.append(layer(f"conflict:{hides['behavior']}:{hides['rule']}", "shield", hides["rule"], properties(
            hides["rule"], lines=lines, actions=opened([one["path"], hides["path"]], folder, home)), note=one["text"],
            mark="warn", agents=[agent]))
    for one in table["rules"]:
        if (one["behavior"], one["rule"]) not in hidden:
            state = {"text": one["behavior"], "tone": one["behavior"]}
            rows.append(layer(f"permission:{one['behavior']}:{one['rule']}", "shield", one["rule"], properties(
                one["rule"], state, [origin(one, folder, home)], actions=opened([one["path"]], folder, home)),
                place=tag(one), state=state, agents=[agent]))
    return rows


def skill_rows(setup, agent, folder, home):
    """The skills, each with its description; a mark on those the open chat used (a plugin's as plugin:name); one
    turned off in this folder dim, off here."""
    used, rows = obj(setup.get("use")).get("skills", {}), []
    for one in setup["skills"]:
        called = f"{one['source']}:{one['name']}" if plugged(one) else one["name"]
        lines = [origin(one, folder, home)] + ([["Used", "in this chat", None]] if called in used else [])
        state = OFF_STATE if one.get("off") else None
        rows.append(layer("skill:" + one["path"], "skill", one["name"], properties(
            one["name"], state, lines, clean(one["description"], None), actions=opened([one["path"]], folder, home)),
            mark="ok" if called in used else None, place=tag(one), state=state, tokens=one["tokens"], agents=[agent],
            dim=bool(state)))
    return rows


def subagent_said(one):
    """A subagent's model and tools in a few words: "Opus · 4 tools", "Haiku · read-only"; None for neither told."""
    model, tools = one["model"] not in (None, "inherit") and words.model_name(one["model"]), one["tools"]
    said = ("read-only" if all(tool in READ_ONLY for tool in tools) else f"{len(tools)} tool{'s' * (len(tools) != 1)}"
            ) if tools else None
    return " · ".join(part for part in (model, said) if part) or None


def subagent_row(one, used, agent, folder, home):
    """The row of the subagent ONE (graph.py draws Claude's own each from one too): its model and tools, how often
    the open chat ran it (USED: use()'s by type); one turned off in this folder dim, off here."""
    calls = used.get(f"{one['source']}:{one['name']}" if plugged(one) else one["name"], 0)
    lines = [origin(one, folder, home)] + ([["Model", one["model"], None]] if one["model"] else []) + \
        ([["Tools", ", ".join(one["tools"]), None]] if one["tools"] else []) + used_line(calls)
    state = OFF_STATE if one.get("off") else None
    return layer(f"subagent:{one['source']}:{one['name']}", "bot", one["name"], properties(
        one["name"], state, lines, clean(one["description"], None),
        actions=opened([one["path"]] if one["path"] else [], folder, home)),
        note=subagent_said(one), mark="ok" if calls else None, place=tag(one), state=state, agents=[agent],
        dim=bool(state))


def subagent_rows(setup, agent, folder, home):
    """The subagents: the user's, the project's and the plugins' each a row; Claude's own folded into one, Built-in,
    naming NAMED of them ("names": all of them, "off": those turned off in this folder)."""
    used = obj(setup.get("use")).get("agents", {})
    rows = [subagent_row(one, used, agent, folder, home) for one in setup["agents"] if one["source"] != CLAUDE]
    own = [one for one in setup["agents"] if one["source"] == CLAUDE]
    if own:
        names, ran = [one["name"] for one in own], sum(used.get(one["name"], 0) for one in own)
        lines = [["From", CLAUDE, BUILT_IN]] + [[one["name"], subagent_said(one) or "", OFF_STATE["text"] if one.get(
            "off") else None] for one in own] + used_line(ran)
        rows.append({**layer("subagent:built-in", "bot", ", ".join(names[:NAMED]), properties(BUILT_IN, lines=lines),
                             note=f"{len(names) - NAMED} more" if len(names) > NAMED else None,
                             mark="ok" if ran else None, place=BUILT_IN, agents=[agent]), "names": names,
                     "off": [one["name"] for one in own if one.get("off")]})
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
    ("32 tools" for one on that told its tools), what each runs or its address, its error, its actions. A list the
    agent could not give: one row saying so."""
    if setup.get("unlisted"):
        return [layer("unread:connectors", "plug", f"{KNOWN[agent]['name']}'s servers", properties(
            "Connectors", NOT_READ, text=f"`{agent} mcp list` gave no list, so which servers {KNOWN[agent]['name']} "
            "has is not known here."), state=NOT_READ, agents=[agent], dim=True)]
    rank, rows = {state: n for n, (state, _, _) in enumerate(PROBLEMS)}, []
    for one in sorted(setup["servers"], key=lambda one: rank.get(one["state"], len(rank))):
        word, tone = SAID_AS[one["state"]]
        word = f"{one['tools']} tool{'s' * (one['tools'] != 1)}" if one["state"] == ON and one["tools"] else word
        state = {"text": word, "tone": tone}
        lines = [origin(one, folder, home)] + [[label, one[key], None] for label, key in (("Runs", "runs"), (
            "URL", "url")) if one[key]] + signs_out(one, agent) + used_line(one["used"])
        rows.append(layer("connector:" + one["name"], "plug", one["label"], properties(
            one["label"], state, lines, error=one["error"], actions=server_actions(one, agent, folder, home)),
            mark=tone if tone in ("bad", "warn") else "ok" if one["used"] else None, place=tag(one), state=state,
            tokens=one["tokens"], agents=one.get("agents", [agent]), dim=one["state"] in DIM, known=one["brand"]))
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


def head(setup, agent, folder, parts):
    """The panel's head: the model (an alias as the newest chat ran it; "runs" its id), effort, what it starts with (the
    newest chat's first turn, else PARTS' sum as an estimate) of its model's window (the chat's, else the price
    table's), their line, the problems as chips each leading to its first row."""
    start, told = setup["start"], setup["model"]
    ran, measured = start["model"], start["tokens"] is not None
    model = ran if ran and (not told or words.family(told) == words.family(ran) and not told.startswith(
        ("claude-", "gpt-"))) else told
    window = (start["window"] if model == ran else None) or words.window(
        told if told and told.lower().endswith(words.ONE_M) else model)
    effort = EFFORTS.get(setup["effort"] or start["effort"])
    starts = start["tokens"] if measured else sum(tokens for _, tokens in parts)
    said = f"starts at {'' if measured else '~'}{words.tokens(starts)}" + (
        f" of {words.tokens(window).replace('.0', '')}" if window else "")
    problems = []
    for state, word, tone in PROBLEMS:
        found = [one["name"] for one in setup["servers"] if one["state"] == state]
        problems += [{"text": f"{len(found)} {word}", "tone": tone, "row": "connector:" + found[0]}] if found else []
    return {"name": KNOWN[agent]["name"], "where": f"in {os.path.basename(os.path.abspath(folder))}",
            "model": words.model_name(model) or None, "runs": model or None, "effort": effort, "starts": starts,
            "measured": measured,
            "window": window, "line": " · ".join(part for part in (words.model_name(model), effort, said) if part),
            "problems": problems}


def layers(setup, agent, folder, home):
    """AGENT's SETUP in FOLDER as the Agent panel draws it in both clients' words: the head, the bar (what loads at
    start, each part's share), an unread file's error, the sections in order with their counts, costs, swatches, rows
    and Permissions' Hooks group (an empty one left out but Connectors). HOME: where ~ is."""
    made = {"subagents": subagent_rows, "rules": rule_rows, "skills": skill_rows, "permissions": permission_rows,
            "connectors": connector_rows}
    sections = []
    for key, title in SECTIONS:
        rows = made[key](setup, agent, folder, home)
        hooks = hook_rows(setup, agent, folder, home) if key == "permissions" else []
        groups = [{"id": "hooks", "title": "Hooks", "count": len(hooks), "rows": hooks,
                   "state": None if setup["hooks"] else OFF_STATE}] if hooks else []
        for row in rows + [one for group in groups for one in group["rows"]]:
            if row["id"].split(":")[0] in ("rule", "skill", "connector", "hook") or row["id"].startswith(
                    "subagent:") and row["id"] != "subagent:built-in":
                acts = row["properties"]["actions"]
                acts.append({**act("graph", "Show in graph"), "primary": not acts})
        loads = [row["tokens"] for row in rows if row["tokens"] is not None and not row["dim"]]
        unknown = key == "permissions" or key == "connectors" and setup.get("unlisted")
        count = None if unknown else len(setup["agents"]) if key == "subagents" else \
            sum(not row["dim"] for row in rows) if key == "rules" else len(rows)
        if rows or groups or key == "connectors":
            sections.append({"id": key, "title": title, "count": count, "tokens": sum(loads) if loads else None,
                             "cost": words.tokens(sum(loads)) if loads else None,
                             "swatch": key if key in PARTS else None,
                             "summary": [{"text": f"{setup['permissions'][one]} {one}", "tone": one}
                                         for one in BEHAVIORS if setup["permissions"][one]]
                             if key == "permissions" else [], "rows": rows, "groups": groups})
    parts = [("rules", sum(one["tokens"] for one in setup["rules"] if not one["paths"])),
             ("skills", sum(one["tokens"] for one in setup["skills"] if not one.get("off"))),
             ("connectors", sum(one["tokens"] or 0 for one in setup["servers"]))]
    whole = sum(tokens for _, tokens in parts)
    files = [shown(path, folder, home) for path in setup["unread"]]
    return {"head": head(setup, agent, folder, parts),
            "bar": [{"part": part, "tokens": tokens, "share": tokens / whole if whole else 0}
                    for part, tokens in parts],
            "error": {"text": f"Couldn't read {KNOWN[agent]['name']}'s setup: permission denied",
                      "tip": ", ".join(files)} if files else None,
            "sections": sections, "connect": connecting(agent, folder)}
