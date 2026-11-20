# Generated from core/graph.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""An agent's graph in a folder, in both clients' words: what goes in (rules, skills), the agent with its sub-agents,
what they use (tools, connectors), each edge with its gate; and what a conversation ran, in order, with costs.py's
figures laid in. Only read. Usage (in JSON): graph.py claude|codex FOLDER [SESSION] [--costs=JSON]."""
import calendar
import collections
import glob
import json
import os
import re
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import agent_setup as setup     # noqa: E402
from jsonl import newest_first, obj, open_regular, parse  # noqa: E402

WORDS = {"columns": {"in": "In", "agents": "Agents", "uses": "Uses"},
         "views": {"wiring": "Wiring", "run": "This conversation"},
         "legend": [["always", "always"], ["demand", "on demand"], ["ran", "ran here"], ["failed", "failed"]]}
AGENT = "agent"                 # the agent's own node
USE = b'"type":"tool_use"'      # in a line of Claude's that holds a call (a result quoting one has it escaped)
UNUSED = "connector · not used"
FILES = ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit")         # one node: the files' tools
SHELL = ("exec", "shell", "local_shell", "exec_command", "shell_command")       # Codex's names for its shell
STARTS = ("Agent", "Task")      # a sub-agent's call (Task: its name before Claude Code 2.1)
NO_TYPE = "agent"               # a sub-agent whose file tells no type, as tokens.py names it
# a mode in the chat's words, and what it lets through unasked: every tool, the files' tools, or none
LETS = {"acceptEdits": ("files",), "auto": None, "bypassPermissions": None}
MODES = {mode: (word, LETS.get(mode, ())) for mode, word in setup.MODE_WORDS.items()}
EFFORTS = {"xhigh": "Extra high"}
READS, EDITS = ("Read", "Grep", "Glob"), ("Edit", "Write", "MultiEdit", "NotebookEdit")
NAME = 40                       # characters of a name or an error a node shows
SAID = 32                       # characters of a skill's description in its line
NAMED = 2                       # exceptions a gate names before their count
FOLD = 4                        # the project's own skills, and sub-agents, each a node; more and others' fold
LISTED = 20                     # lines a folded node's properties list
LOOKED = 200                    # Codex's newest chats looked through for the folder's
FIRST = 1 << 20                 # bytes of a Codex chat's first line read
RESULT = re.compile(rb'"(?:tool_use_id|call_id)":\s*"([^"\\]+)"')
CHAT = re.compile(r"[0-9a-f-]{36}")     # a session a herdr-fold chat may have started
STAMP = re.compile(r"(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)")
RANK = {setup.FAILED: 2, setup.SIGN_IN: 1, setup.PENDING: 1}            # the servers that run first, then these
STYLE = {setup.ON: "always", setup.SIGN_IN: "waiting", setup.PENDING: "waiting", setup.FAILED: "failed"}


def times(count):
    return "once" if count == 1 else f"{count} times"


def calls_said(count):
    return f"{count} call{'s' * (count != 1)}"


# --- a conversation's calls

def reach(claude, name, given):
    """What a call of the tool NAME with its input GIVEN reaches: (skill, sub, server or tool; its name)."""
    kind = given.get("subagent_type")
    if claude and name == "Skill" and isinstance(given.get("skill"), str):
        return "skill", given["skill"]
    if claude and name in STARTS:
        return "sub", kind if isinstance(kind, str) and kind else setup.GENERAL
    if name.startswith("mcp__"):
        return "server", name[len("mcp__"):].partition("__")[0]
    return "tool", "files" if claude and name in FILES else "shell" if not claude and name in SHELL else name


def claude_calls(path):
    """The session file PATH's tool calls in order ({at, name, id, to, message}), the ids answered, and the mode it
    was last in; a call once (Claude writes a message again). OSError when it cannot be read."""
    calls, done, seen, mode = [], set(), set(), None
    with open_regular(path, "rb") as f:
        for n, raw in enumerate(f):
            if b'"tool_use_id"' in raw:
                done.update(RESULT.findall(raw))
            if USE in raw:
                entry = parse(raw)
                message = obj(entry.get("message")) if entry.get("type") == "assistant" else {}
                for block in message.get("content") if isinstance(message.get("content"), list) else []:
                    key = obj(block).get("id")
                    if obj(block).get("type") == "tool_use" and isinstance(block.get("name"), str) and key not in seen:
                        seen.update([key] if isinstance(key, str) else ())
                        calls.append({"at": entry.get("timestamp"), "name": block["name"], "id": key,
                                      "to": reach(True, block["name"], obj(block.get("input"))),
                                      "message": message.get("id") or n})
            elif b'"permission-mode"' in raw:
                mode = parse(raw).get("permissionMode") or mode
    return calls, {one.decode("utf-8", "replace") for one in done}, mode


def codex_calls(path):
    """The Codex chat PATH's tool calls in order, the ids answered, its approval policy, session and effort."""
    calls, done, policy, session, effort = [], set(), None, None, None
    with open_regular(path, "rb") as f:
        for n, raw in enumerate(f):
            if b'_output"' in raw and b'"call_id"' in raw:
                done.update(RESULT.findall(raw)[:1])
            elif b'"call_id"' in raw or b'"turn_context"' in raw or not n:
                entry = parse(raw)
                told = obj(entry.get("payload"))
                if entry.get("type") == "turn_context":
                    policy = told.get("approval_policy") or policy
                    effort = told.get("effort") or effort
                elif entry.get("type") == "session_meta":
                    session = told.get("id") if isinstance(told.get("id"), str) else None
                elif isinstance(told.get("name"), str) and isinstance(told.get("call_id"), str):
                    calls.append({"at": entry.get("timestamp"), "name": told["name"], "id": told["call_id"],
                                  "to": reach(False, told["name"], {}), "message": told["call_id"]})
    return calls, {one.decode("utf-8", "replace") for one in done}, policy, session, effort


def running(calls, done, by=None, over=False):
    """CALLS, BY's (a sub-agent's type), with "open" on those that run now: unanswered, in the last message that
    called (OVER: none can)."""
    last = calls[-1]["message"] if calls else None
    return [{**one, "by": by, "open": not over and one["id"] not in done and one["message"] == last} for one in calls]


def read(agent, path):
    """What the conversation in AGENT's file PATH ran: {"session", "mode", "calls": the agent's and its sub-agents' in
    time's order, "subs": each sub-agent file's type}; None for no file."""
    try:
        if agent == "codex":
            calls, done, mode, session, effort = codex_calls(path)
            return {"session": session, "mode": mode, "effort": effort, "calls": running(calls, done), "subs": []}
        calls, done, mode = claude_calls(path)
    except (OSError, TypeError):
        return None
    found, subs = running(calls, done), []
    for meta in sorted(glob.glob(os.path.join(glob.escape(path[:-len(".jsonl")]), "subagents", "agent-*.meta.json"))):
        told = setup.read_json(meta)
        try:
            calls, done, _ = claude_calls(meta[:-len(".meta.json")] + ".jsonl")
        except OSError:
            continue
        kind = told.get("agentType")
        subs.append(kind if isinstance(kind, str) and kind else NO_TYPE)
        found += running(calls, done, subs[-1], told.get("finished") is True)
    found.sort(key=lambda one: one["at"] if isinstance(one["at"], str) else "")
    return {"session": os.path.basename(path)[:-len(".jsonl")], "mode": mode, "calls": found, "subs": subs}


def rollout(folder, home):
    """Codex's newest chat started in FOLDER (its own, no helper's), or None."""
    place = os.path.join(glob.escape(setup.codex_home(home)), "sessions", "*", "*", "*", "rollout-*.jsonl")
    for path in newest_first(glob.glob(place))[:LOOKED]:
        try:
            with open_regular(path, "rb") as f:
                meta = obj(parse(f.readline(FIRST)).get("payload"))
        except OSError:
            continue
        if meta.get("cwd") == folder and "subagent" not in obj(meta.get("source")):
            return path
    return None


# --- gates

def short(words):
    """A rule's WORDS as a gate names them: "git push *" as git push."""
    return re.sub(r"(:\*|\s*\*+)$", "", words).strip() or words


def gates(table, names, base, hook=False, server=None, lone=True):
    """The gates on the edge to a tool, and the rules met as properties lines: BASE (allow, ask, deny, auto or None)
    unless a bare rule of TABLE (permissions()'s) sets it, the other rules its exceptions (NAMED of them named), the
    HOOK where it asks. NAMES: the tools (None: Codex's, every rule); SERVER: a connector's tool key; LONE: one tool."""
    hidden = {(one["hides"]["behavior"], one["hides"]["rule"]) for one in table["conflicts"]}
    found, lines, bare = {behavior: [] for behavior in setup.BEHAVIORS}, [], set()
    for one in table["rules"]:
        tool, words = (None, one["rule"]) if names is None else setup.RULE.fullmatch(one["rule"]).groups()
        whole = f"mcp__{server}"
        if (one["behavior"], one["rule"]) in hidden or not (
                tool in (whole, whole + "__*") or tool.startswith(whole + "__") if server
                else names is None or tool in names):
            continue
        lines.append([one["behavior"].capitalize(), one["rule"], one["scope"]])
        if words is None and (tool in (whole, whole + "__*") if server else lone):
            bare.add(one["behavior"])
        else:
            found[one["behavior"]].append(tool if words is None else short(words) if lone else f"{tool} {short(words)}")
    base = next((behavior for behavior in ("deny", "ask", "allow") if behavior in bare), base)

    def said(behavior):
        some = found[behavior]
        return f"{len(some)} tool{'s' * (len(some) != 1)}" if server else \
            ", ".join(some[:NAMED]) + (f" +{len(some) - NAMED}" if len(some) > NAMED else "")
    made = []
    if base in ("ask", None) and found["allow"]:
        made.append({"text": ("ask · " if base else "") + f"{said('allow')} allowed", "tone": base or "allow"})
    elif base:
        made.append({"text": base, "tone": "allow" if base == "auto" else base})
    made += [{"text": f"{behavior} {said(behavior)}", "tone": behavior} for behavior in ("ask", "deny")
             if found[behavior] and base not in (behavior, "deny")]
    asks = base == "ask" or found["ask"] and base != "deny"
    return made + [{"text": "hook", "tone": "hook"}] * bool(hook and asks), lines


# --- the graph

def show(row=None):
    """Show in Agent, a node's way to the Agent panel: on ROW (the row's id there, its node's too), or the agent's."""
    return {**setup.act("agent", "Show in Agent"), "row": row}


def node(key, column, kind, title, sub=None, row=None, icon=None, lines=(), then=None, acts=(), **more):
    """A node: ROW the Agent panel's row it is drawn from (its tag, brand, properties), else LINES its properties'
    (ACTS their actions); THEN what This conversation says of it: (its line, True where it ran unasked or its tag)."""
    row = row or {}
    return {"id": key, "column": column, "kind": kind, "title": title, "icon": icon or row.get("icon"),
            "brand": row.get("brand"), "tag": row.get("tag"), "sub": sub, "state": None, "dim": False, "chips": [],
            "parent": AGENT if kind in ("sub", "subs") else None,
            "properties": row.get("properties") or setup.properties(title, lines=lines, actions=acts), "run": None,
            "then": then or (sub, None), **more}


def edge(start, end, style, found=()):
    return {"from": start, "to": end, "style": style, "gates": list(found), "run": None}


def tools_said(tools, servers):
    """A sub-agent's TOOLS in a few words: reads, edits, runs, then the SERVERS ({tool key: its row}) it reaches."""
    words = [word for word, names in (("reads", READS), ("edits", EDITS), ("runs", ("Bash",)))
             if any(tool in names for tool in tools)]
    keys = dict.fromkeys(reach(True, tool, {})[1] for tool in tools if tool.startswith("mcp__"))
    return ", ".join(words + [servers[key]["label"] if key in servers else key for key in keys]) or "every tool"


def called_as(one):
    return f"{one['source']}:{one['name']}" if setup.plugged(one) else one["name"]


def epoch(stamp):
    found = STAMP.match(stamp) if isinstance(stamp, str) else None
    try:
        return calendar.timegm(tuple(int(part) for part in found.groups())) if found else None
    except (ValueError, OverflowError):
        return None


def graph(agent, folder, home, session=None, costs=None):
    """AGENT's graph in FOLDER (HOME: where ~ is): {"agent", "name", "folder", "session", "run": whether a conversation
    is read, "words", "nodes", "edges", "path": the nodes that ran, in order}; None where the agent is not here.
    SESSION: the conversation's file; COSTS: costs.py's answer for it. A node's and an edge's "run": None with none."""
    claude = agent == "claude"
    own = setup.setup(agent, folder, home, session if claude else None)
    if own is None:
        return None
    ran = read(agent, session) if session else None
    costs, calls, name = obj(costs) if ran else {}, ran["calls"] if ran else [], setup.KNOWN[agent]["name"]
    rows = {row["id"]: row for section in setup.layers(own, agent, folder, home)["sections"]
            for row in section["rows"]}
    for row in rows.values():                   # a node is where Show graph leads: its own leads back to its row
        kept = [one for one in row["properties"]["actions"] if one["id"] != "graph"]
        row["properties"]["actions"] = kept + [{**show(row["id"]), "primary": not kept}]
    used, nodes, edges, ids = collections.Counter(one["to"] for one in calls), [], [], {}
    used.update(("sub", kind) for kind in (ran["subs"] if ran else ()))

    def add(key, made, style=None, inward=False, found=()):
        """MADE among the nodes, as what a call's KEY reaches, with its edge of STYLE from the agent (INWARD: to it)."""
        ids[key] = made["id"]
        nodes.append(made)
        if style:
            edges.append(edge(*((made["id"], AGENT) if inward else (AGENT, made["id"])), style, found))

    def some(kind, items, make, key, word):
        """ITEMS each a node (MAKE's) where it ran or is the project's own (FOLD of those), the rest as one node."""
        rest, shown = [], 0
        for one in items:
            mine = one["scope"] == setup.PROJECT and not setup.plugged(one)
            if (kind, called_as(one)) in used or mine and shown < FOLD:
                shown += (kind, called_as(one)) not in used
                make(one)
            else:
                rest.append(one)
        if len(rest) > 1:
            lines = [[one["name"], setup.tag(one)["text"], None] for one in rest[:LISTED]]
            lines += [["", f"{len(rest) - LISTED} more", None]] * (len(rest) > LISTED)
            cost = [setup.kilo(sum(one["tokens"] for one in rest))] if kind == "skill" else []
            add((key, None), node(key, "in" if cost else "agents", kind + "s", f"{len(rest)} more {word}",
                                  " · ".join(["on demand"] + cost), icon="skill" if cost else "bot", lines=lines),
                "demand", bool(cost))
        for one in rest[:len(rest) == 1]:
            make(one)

    # in: the rules, the skills
    for one in own["rules"]:
        row, paths = rows["rule:" + one["path"]], one["paths"]
        then = (f"read with {', '.join(paths)} · {row['cost']}", None) if paths else (
            f"always · {row['cost']} tokens", True)
        add(("rule", row["id"]), node(row["id"], "in", "rule", row["name"], row["note"] or f"always · {row['cost']}",
                                      row, then=then), "demand" if paths else "always", True)

    def skill(one):
        row, words, count = rows["skill:" + one["path"]], setup.clean(one["description"], SAID), used[
            ("skill", called_as(one))]
        add(("skill", called_as(one)), node(
            row["id"], "in", "skill", row["name"], "skill · " + words if words else "skill", row,
            then=(f"skill · used {times(count)} · {row['cost']}", None) if count else None), "demand", True)
    some("skill", own["skills"], skill, "skills:more", "skills")

    # agents: the agent, its sub-agents
    session_id = ran["session"] if ran else None
    status = os.path.join(home, ".local", "state", "herdr-fold", "chat", session_id or "", "status.json")
    hooked = claude and bool(CHAT.fullmatch(session_id or "")) and os.path.isfile(status)
    chat = setup.read_json(status) if hooked else {}
    mode = ran["mode"] if ran and ran["mode"] in MODES else own.get("default_mode") or "default"
    starts = {} if claude else setup.codex_config(home)
    policy = None if claude else (ran or {}).get("mode") or own["permissions"]["mode"]
    effort = chat.get("effort") if claude else (ran or {}).get("effort") or starts.get("model_reasoning_effort")
    effort = setup.clean(effort, NAME)
    effort = effort and EFFORTS.get(effort, effort.capitalize())
    lines = [[label, value, None] for label, value in (
        ("Model", setup.clean(chat.get("model"), NAME) or obj(obj(costs.get("agent")).get("model")).get("name")),
        ("Effort", effort), ("Mode", MODES[mode][0] if claude else None),
        ("Approval", setup.APPROVALS.get(str(policy)))) if value]
    add((AGENT, None), node(AGENT, "agents", "agent", name, " · ".join(line[1] for line in lines) or None, icon=agent,
                            lines=lines + [["Hook", "PermissionRequest", "herdr-fold"]] * hooked, acts=[show()]))
    nodes[-1].update(tag={"text": "this conversation", "tone": "muted"} if ran else None,
                     chips=["PermissionRequest → herdr-fold"] * hooked)
    servers = {setup.tool_key(one["name"]): one for one in own["servers"]}

    def sub(one):
        row = rows[f"agent:{one['source']}:{one['name']}"]
        words = ["sub-agent"] + [(one["model"] or "").capitalize()] * (one["model"] not in (None, "inherit")) + \
            [tools_said(one["tools"], servers)]
        add(("sub", called_as(one)), node(row["id"], "agents", "sub", row["name"], " · ".join(words), row), "demand")
        for key in dict.fromkeys(reach(True, tool, {})[1] for tool in one["tools"] if tool.startswith("mcp__")):
            if servers.get(key, {}).get("state") in STYLE:
                edges.append(edge(row["id"], "connector:" + servers[key]["name"], STYLE[servers[key]["state"]]))
    some("sub", own["agents"], sub, "agents:more", "sub-agents")

    # uses: the built-in tools, the connectors
    table, lets = own["permissions"], MODES[mode][1]
    asks = ("allow" if policy == "never" else "ask" if policy else None) if not claude else \
        "deny" if mode == "dontAsk" else "auto" if mode == "auto" else "allow" if lets is None else "ask"

    def tool(key, title=None, names=None, base=None, icon="wrench"):
        title, names = title or setup.clean(key, NAME) or "tool", names or (key,)
        found, lines = gates(table, names if claude else None, base, hooked, lone=len(names) == 1 or not claude) \
            if claude or names == SHELL else ([], [])
        lines = [["Kind", "built-in", None]] + [["Tools", ", ".join(names), None]] * (len(names) > 1 and claude) + lines
        add(("tool", key), node("tool:" + (title if names == (key,) else key), "uses", "tool", title, "built-in",
                                icon=icon, lines=lines), "always", found=found)
    if claude:
        tool("files", "Read · Edit · Write", FILES, "allow" if lets else asks, "file")
        tool("Bash", base=asks, icon="terminal")
    else:
        tool("shell", "Shell", SHELL, asks, "terminal")
    for one in sorted(own["servers"], key=lambda one: (one["state"] in setup.DIM) * 3 or RANK.get(one["state"], 0)):
        row, state, cost = rows["connector:" + one["name"]], one["state"], one["tokens"] and setup.kilo(one["tokens"])
        word, tone = setup.SAID_AS[state]
        said = "needs sign-in" if state == setup.SIGN_IN else word if state in setup.DIM or state == setup.PENDING \
            else " · ".join(["failed"] + [setup.clean(one["error"], NAME)] * bool(one["error"])) \
            if state == setup.FAILED else " · ".join(
                ["MCP"] + [f"{one['tools']} tools"] * bool(one["tools"])
                + [cost or word] * bool(cost or not one["tools"]))
        style = None if state in setup.DIM else STYLE.get(state, "demand")
        add(("server", setup.tool_key(one["name"])), node(
            row["id"], "uses", "connector", row["name"], said, row, dim=not style,
            state=tone if tone in ("bad", "warn") else "warn" if state == setup.PENDING else None,
            then=(f"connector · {cost} tokens in context" if cost else UNUSED,
                  {"text": word, "tone": tone} if tone in ("bad", "warn") else None)),
            style, found=gates(table, (), asks, hooked, setup.tool_key(one["name"]))[0]
            if style in ("always", "demand") and claude else ())
    edges.sort(key=lambda one: AGENT not in (one["from"], one["to"]))       # a sub-agent's own after the agent's

    made = {"agent": agent, "name": name, "folder": folder, "session": session_id, "run": bool(ran), "words": WORDS,
            "nodes": nodes, "edges": edges, "path": []}
    if ran:
        run(made, ran, costs, ids, add, tool, effort)
    for one in nodes:
        del one["then"]
    return made


def run(made, read, costs, ids, add, tool, effort):
    """MADE (graph()'s) with what READ (read()'s) laid in: each node's and edge's "run", a node for what ran unlisted,
    the path; COSTS on the agent and its sub-agents. IDS: a node's id by what a call reaches; ADD, TOOL make one."""
    nodes, edges, name = made["nodes"], made["edges"], made["name"]
    by_id, lines, names = {}, {}, {}

    def keep():
        """Each node and edge made since, with its run: a rule read always ran, its edge too."""
        for one in nodes:
            if one["run"] is None:
                said, extra = one["then"]
                one["run"] = {"ran": extra is True or one["id"] == AGENT, "order": None, "sub": said,
                              "tag": extra if isinstance(extra, dict) else None, "calls": None, "count": 0,
                              "cost": None, "model": None, "share": None, "started": None, "properties": None}
                by_id[one["id"]] = one
        for one in edges:
            if one["run"] is None:
                loaded = one["style"] == "always" and one["to"] == AGENT and by_id[one["from"]]["run"]["ran"]
                one["run"] = {"ran": loaded, "running": False, "calls": 0}
                lines[(one["from"], one["to"])] = one

    def reached(key):
        """The id of the node a call's KEY reaches, made where the setup lists none."""
        kind, word = key[0], setup.clean(key[1], NAME) or key[0]
        if key not in ids:
            column, made, sub, icon = {"skill": ("in", "skill", "skill", "skill"), "tool": (None,) * 4,
                                       "sub": ("agents", "sub", "sub-agent", "bot"),
                                       "server": ("uses", "connector", "MCP", "plug")}[kind]
            if kind == "tool":
                tool(key[1])
            else:
                add(key, node(f"{kind}:run:{word}", column, made, word, sub, icon=icon),
                    None if kind == "server" else "demand", kind == "skill")
            keep()
        return ids[key]
    keep()
    for kind in read["subs"]:
        start = reached(("sub", kind))
        by_id[start]["run"]["ran"] = lines[(AGENT, start)]["run"]["ran"] = True
    for one in read["calls"]:
        start, key = reached(("sub", one["by"])) if one["by"] else AGENT, reached(one["to"])
        ends = (key, start) if one["to"][0] == "skill" else (start, key)
        if ends not in lines:
            edges.append(edge(*ends, "always"))
            keep()
        went, there = lines[ends]["run"], by_id[key]["run"]
        went.update(ran=True, running=went["running"] or one["open"], calls=went["calls"] + 1)
        if not there["order"]:
            made["path"].append(key)
            there.update(ran=True, order=len(made["path"]), started=epoch(one["at"]))
        there["count"] += 1
        word = setup.clean(one["name"].rpartition("__")[2], NAME) or "tool"
        names.setdefault(key, collections.Counter())[word] += 1

    kinds = {node_id: key[1] for key, node_id in ids.items() if key[0] == "sub"}
    for one in nodes:
        ran, kind, count, shown = one["run"], one["kind"], one["run"]["count"], one["properties"]
        cost = obj(costs.get("agent") if kind == "agent" else obj(costs.get("subs")).get(kinds.get(one["id"])))
        model = obj(cost.get("model"))
        if kind in ("tool", "connector") and count:
            ran["calls"] = calls_said(count)
            ran["sub"] = "connector" if ran["sub"] == UNUSED else ran["sub"]
            split = [[word, str(n), None] for word, n in names[one["id"]].items()]
            if kind == "tool":
                ran["properties"] = setup.properties(one["title"], lines=[["Calls", str(count), None]] + split * (
                    [line[0] for line in split] != [one["title"]]))
        elif kind == "sub" and not ran["ran"]:
            ran["sub"] = "not run in this conversation"
        elif kind == "sub":
            ran["sub"] = cost.get("sub") or f"sub-agent · ran {times(max(count, 1))}"
            told = [["Model", model["name"], None] if line[0] == "Model" and model else line
                    for line in shown["lines"] if line[0] != "Used"]
            has = any(line[0] == "Model" for line in told)
            told += [["Started", f"by {name} at {{time}}, step {ran['order']}", None]] * bool(ran["order"])
            told += [line for line in cost.get("lines") or [] if line[0] != "Model" or not has]
            ran["properties"] = {**shown, "lines": told,
                                 "state": {"text": cost["title"], "tone": "ok"} if cost.get("title") else None}
        elif kind == "agent" and cost:
            ran["sub"] = cost.get("sub") or ran["sub"]
            told = [[line[0], f"{line[1]} · {effort}", line[2]] if line[0] == "Model" and effort else line
                    for line in cost.get("lines") or []]
            ran["properties"] = setup.properties(name, {"text": cost.get("title"), "tone": "ok"}, told, actions=[
                {**setup.act("usage", "Open in Usage"), "session": made["session"]}, show()])
        if cost and ran["ran"]:
            ran.update(cost=cost.get("text"), share=cost.get("share"),
                       model={"name": model.get("name"), "color": model.get("color")} if model else None)


def main(argv):
    """herdr-fold's Herdr app mod runs this on the space's machine, answering in JSON: AGENT FOLDER [SESSION],
    graph()'s (SESSION a file, for Claude an id too, else the folder's newest conversation; --costs: costs.py's)."""
    options = dict(arg[2:].split("=", 1) for arg in argv[1:] if arg.startswith("--") and "=" in arg)
    args, home = [arg for arg in argv[1:] if not arg.startswith("--")], os.path.expanduser("~")
    try:
        costs = json.loads(options["costs"]) if "costs" in options else None
    except ValueError:
        args = []
    if len(args) not in (2, 3) or args[0] not in setup.READ:
        print("usage: graph.py claude|codex FOLDER [SESSION] [--costs=JSON]", file=sys.stderr)
        return 2
    agent, folder, session = args[0], args[1], args[2] if len(args) == 3 else None
    session = setup.conversation(folder, session, home) if agent == "claude" else \
        session if session and os.path.isfile(session) else rollout(folder, home)
    print(json.dumps(graph(agent, folder, home, session, costs)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
