"""The machines' graph in both clients' words, from core/networks.py's look: this Mac, the networks, the machines on
them and those behind another, each edge the way it goes, each node's properties the Machines view's rows (one source
for both). Only shapes what it is given. Usage (in JSON): machine_graph.py LOOK|- WORDS [--runs=JSON] [--kept=JSON]."""
import json
import re
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
from icons import NETWORKS  # noqa: E402

MOST = 256                    # the machines, and a network's names to add, one look gives at most
ROUTES = 8                    # a machine's routes, at most
SPACES = 10 ** 4              # the spaces one machine's runs count, at most
AGENTS_MOST = 64              # the agents one machine's runs name, at most
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")                     # a machine's name, core/machines.py's
HOST = re.compile(r"(?!-)[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})*")    # a host name or an IPv4 address
IP6 = re.compile(r"[0-9A-Fa-f:.]{2,45}")
USER = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{0,31}")
KEY = re.compile(r"SHA256:[A-Za-z0-9+/]{1,64}")                           # a host key's fingerprint
WHY = re.compile(r"machines\.why_[a-z_]{1,40}")                           # a ladder's sentence, by its catalog key
WORD = re.compile(r"[a-z_]{1,32}")                                        # an agent's name or state, herdr's
CONTROLS = re.compile(r"[\x00-\x1f\x7f-\x9f]")
STATES = ("on", "off", "signed_out", "expired", "approval", "no_management")      # a network client's, core's
WITH_CLIENT = ("tailscale", "netbird", "zerotier")      # the networks whose client on this Mac has a state
OSES, PATHS = ("linux", "macos", "windows"), ("direct", "relayed")
LOOKS_AROUND = ("linux", "macos")                       # ./machines.sh through reads these (Windows comes later)
AGENTS = {"claude": "Claude", "codex": "Codex", "opencode": "OpenCode", "copilot": "Copilot"}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
OFFLINE = ("machines.why_offline", "machines.why_offline_unseen")         # sentences that say when it was seen

THIS_MAC, OTHER, BETWEEN = "This Mac", "Other", " › "
BY_ADDRESS = "none yet: add one by its address"          # ZeroTier and WireGuard name no machine to offer
CONNECTED, NOT_CONNECTED, AWAY, WAITING = "connected", "not connected", "unreachable", "waiting"
IN_USE, STANDBY = "in use", "standby"
ACTIONS = {"status": "Status", "again": "Set up again", "remove": "Remove", "through": "Look around from here…",
           "check": "Check again", "copy": "Copy command"}
MAC = "mac"                   # this Mac's node
COLUMNS = ["mac", "networks", "machines", "through"]
WORDS = {"columns": {"mac": THIS_MAC, "networks": "Networks", "machines": "Machines", "through": "Through"},
         "legend": [["always", "direct"], ["demand", "relayed"], ["standby", "standby route"], ["failed", "away"]]}
USAGE = "usage: machine_graph.py LOOK WORDS [--runs=JSON] [--kept=JSON] (LOOK -: read from its input)"
LOOK_MOST = 1 << 22           # bytes of a look read from its input: 256 machines' take some hundred KB


# --- what it is given, checked

def clean(value, most=300):
    """VALUE a network or a machine said, safe to show: its control characters dropped, cut at MOST."""
    return CONTROLS.sub("", str(value))[:most]


def name_ok(value):
    return isinstance(value, str) and bool(NAME.fullmatch(value))


def address_ok(value):
    return isinstance(value, str) and len(value) <= 253 and bool(HOST.fullmatch(value) or IP6.fullmatch(value))


def listed(value, most=MOST):
    return value[:most] if isinstance(value, list) else []


def kind_of(word):
    """A network's word (core/icons.py's NETWORKS, in the routes' order), through for one behind another; else None."""
    return word if isinstance(word, str) and (word in NETWORKS or word == "through") else None


def checked_why(said, depth=0):
    """A ladder's sentence (core/networks.py's why()), checked: its catalog key, its arguments cleaned, what to do and
    what caused it (three deep at most); None for anything else."""
    if not isinstance(said, dict) or depth > 3 or not (isinstance(said.get("key"), str) and WHY.fullmatch(said["key"])):
        return None
    args = lambda values: [clean(one) for one in listed(values, 8)]          # noqa: E731
    action = said.get("action")
    todo = {"key": action["key"], "args": args(action.get("args")),
            "command": clean(action["command"]) if isinstance(action.get("command"), str) else None} \
        if isinstance(action, dict) and isinstance(action.get("key"), str) and WHY.fullmatch(action["key"]) else None
    return {"key": said["key"], "args": args(said.get("args")), "action": todo,
            "then": checked_why(said.get("then"), depth + 1)}


def checked_routes(routes):
    found = []
    for one in (one for one in listed(routes, ROUTES) if isinstance(one, dict) and address_ok(one.get("address"))):
        network = kind_of(one.get("network"))
        found.append({"network": network, "address": one["address"],
                      "user": one["user"] if isinstance(one.get("user"), str) and USER.fullmatch(one["user"]) else None,
                      "through": one["through"] if network == "through" and name_ok(one.get("through")) else None})
    return found


def number(value, most):
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= most else None


def seen(said):
    """What core/networks.py's here answered (SAID), checked as everything a network or a machine says is: a name, an
    address, a user, a key, a network and a state of their shapes, a sentence by its catalog key with its arguments
    cleaned, each list capped; anything else dropped."""
    said = said if isinstance(said, dict) else {}
    machines, names = [], set()
    for one in (one for one in listed(said.get("machines")) if isinstance(one, dict)):
        if not name_ok(one.get("name")) or one["name"] in names:
            continue
        names.add(one["name"])
        network, figures = kind_of(one.get("network")), one.get("figures") if isinstance(one.get("figures"), dict) \
            else {}
        machines.append({"name": one["name"], "os": one["os"] if one.get("os") in OSES else "", "network": network,
                         "through": one["through"] if network == "through" and name_ok(one.get("through")) else None,
                         "key": one["key"] if isinstance(one.get("key"), str) and KEY.fullmatch(one["key"]) else None,
                         "why": checked_why(one.get("why")), "routes": checked_routes(one.get("routes")),
                         "figures": {"path": figures.get("path") if figures.get("path") in PATHS else None,
                                     "login_ms": number(figures.get("login_ms"), 10 ** 6),
                                     "seen": number(figures.get("seen"), 10 ** 11)}})
    told = said.get("networks") if isinstance(said.get("networks"), dict) else {}
    networks = {}
    for kind in (kind for kind in NETWORKS if isinstance(told.get(kind), dict)):
        one = told[kind]
        networks[kind] = {"installed": one.get("installed") is True if "installed" in one else None,
                          "state": one.get("state") if one.get("state") in STATES else None,
                          "why": checked_why(one.get("why")),
                          "offered": list(dict.fromkeys(name for name in listed(one.get("offered")) if name_ok(name)))}
    return {"checked": number(said.get("checked"), 10 ** 11), "machines": machines, "networks": networks}


def checked_runs(value):
    """What runs on each machine as a client tells it ({name: {"spaces", "agents": [[agent, state]]}}), checked: a name
    of its shape, a count within herdr's, each agent and its state a plain word; anything else dropped."""
    found = {}
    for name, one in list(value.items())[:MOST] if isinstance(value, dict) else ():
        spaces = number(one.get("spaces"), SPACES) if isinstance(one, dict) else None
        if name_ok(name) and spaces is not None:
            agents = listed(one.get("agents"), AGENTS_MOST)
            found[name] = {"spaces": spaces, "agents": [pair for pair in agents if isinstance(pair, list) and len(
                pair) == 2 and all(isinstance(word, str) and WORD.fullmatch(word) for word in pair)]}
    return found


def checked_kept(value):
    """The machines herdr keeps ({label: enabled}), checked; None where it is not of that shape (herdr told nothing)."""
    if not isinstance(value, dict):
        return None
    return {name: one for name, one in list(value.items())[:MOST] if name_ok(name) and isinstance(one, bool)}


# --- how it is said (the Machines view's words, the graph's too)

def grouped(found):
    """FOUND's machines (seen()'s) as the app groups them: the networks in the routes' order, a machine under the route
    it is reached by, one behind another under its jump host (by name; jump hosts that go round nest none), those no
    network tells last; an empty network where it offers machines to add or names none (added by address)."""
    machines = {one["name"]: one for one in found["machines"]}

    def parent(one):
        up = one["through"]
        return up if one["network"] == "through" and up in machines and up != one["name"] else None

    def nests(one):
        passed, up = {one["name"]}, parent(one)
        while up:
            if up in passed:
                return False
            passed.add(up)
            up = parent(machines[up])
        return parent(one) is not None

    top, behind = [], {}
    for one in sorted(machines.values(), key=lambda one: one["name"].casefold()):
        (behind.setdefault(one["through"], []) if nests(one) else top).append(one)

    def under(one):
        """The network a machine on top stands under: its own, else the one of the jump host it goes through."""
        if one["network"] in NETWORKS:
            return one["network"]
        jump = machines.get(one["through"]) if one["network"] == "through" else None
        return jump["network"] if jump and jump["network"] in NETWORKS else None

    def flat(one, depth=0):
        return [(one, depth)] + [found for below in behind.get(one["name"], []) for found in flat(below, depth + 1)]

    groups = []
    for kind in NETWORKS:
        net, mine = found["networks"].get(kind) or {}, [one for one in top if under(one) == kind]
        offered = net.get("offered", []) if net.get("state") == "on" and not mine else []
        bare = not mine and net.get("installed") and (kind == "wireguard" or net.get("state") == "on") \
            and kind in ("zerotier", "wireguard")
        if mine or offered or bare:
            groups.append({"network": kind, "net": net, "offered": offered,
                           "machines": [found for one in mine for found in flat(one)]})
    rest = [one for one in top if under(one) is None]
    if rest:
        groups.append({"network": None, "net": {}, "offered": [], "machines": [found for one in rest
                                                                             for found in flat(one)]})
    return groups


def state_words(network, net, t):
    """How a network says NET's state while it is not on, (words, tone): off or not installed muted, one to act on
    warn (the app's words and tones); None while on, and for a network with no client of its own."""
    if network not in WITH_CLIENT:
        return None
    if net.get("installed") is False:
        return t("machines.state_missing"), "muted"
    return {"off": (t("machines.state_off"), "muted"),
            "signed_out": (t("machines.state_signed_out"), "warn"),
            "expired": (t("machines.state_expired"), "warn"),
            "approval": (t("machines.state_approval"), "warn"),
            "no_management": (t("machines.state_no_management"), "warn")}.get(net.get("state"))


def to_add(count, t):
    return t("machines.to_add_one", count) if count == 1 else t("machines.to_add", count)


def counted(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def why_lines(why, t):
    """WHY as machines.sh says it, a line each [[words, tone]]: the sentence warn, then what caused it or what to do,
    each one's own after it, a command in the text's tone after its words."""
    lines, follow = [[[t(why["key"], *why["args"]), "warn"]]], why["then"] or why["action"]
    while follow:
        if follow.get("command"):
            lines.append([[t(follow["key"], *follow["args"], "\0").split("\0")[0], "muted"],
                          [follow["command"], "text"]])
        else:
            lines.append([[t(follow["key"], *follow["args"]), "muted"]])
        follow = follow.get("then") or follow.get("action")
    return lines


def first_command(why):
    """The first command WHY's sentences give to run (Start it: netbird up); None for none."""
    follow = why and (why["then"] or why["action"])
    while follow:
        if follow.get("command"):
            return follow["command"]
        follow = follow.get("then") or follow.get("action")
    return None


def waiting(runs):
    return any(status == "blocked" for _, status in (runs or {}).get("agents", ()))


def way_words(figures):
    """The way to a machine as its network tells it (direct, relayed) and the time a login or the network measured."""
    return " ".join(filter(None, [figures["path"], None if figures["login_ms"] is None
                                  else f"{figures['login_ms']} ms"]))


def right_words(one, runs):
    """What a machine's row says at its right, (words, tone): unreachable while away, waiting while an agent there
    waits on you, else the way to it."""
    if one["why"]:
        return AWAY, "muted"
    if waiting(runs):
        return WAITING, "warn"
    return way_words(one["figures"]), "muted"


def runs_parts(runs):
    """What runs on a machine [[words, tone]]: its spaces, then each agent working or waiting on you."""
    count = runs["spaces"]
    parts = [[counted(count, "space"), "text"]]
    for agent, status in runs["agents"]:
        if agent in AGENTS and status in ("blocked", "working"):
            parts += [[", ", "text"], [f"{AGENTS[agent]} {'waiting' if status == 'blocked' else 'working'}",
                                       "warn" if status == "blocked" else "text"]]
    return parts


def path_words(one, machines, t):
    """The way to a machine behind another: This Mac › Tailscale › lumen-api › build-01."""
    chain, up = [one["name"]], one
    while up["network"] == "through" and up["through"] in machines and up["through"] not in chain:
        up = machines[up["through"]]
        chain.insert(0, up["name"])
    return BETWEEN.join([THIS_MAC] + ([t(f"machines.network_{up['network']}")] if up["network"] in NETWORKS else [])
                        + chain)


def short_key(key):
    """A fingerprint cut to what tells it apart at a glance: SHA256:Qm9vZ0x1…a7Fk."""
    body = key[len("SHA256:"):]
    return f"SHA256:{body[:8]}…{body[-4:]}" if len(body) > 13 else key


def seen_words(when, now, local=time.localtime):
    """When a machine was seen last: today 8:02, else Nov 26 8:02 (this Mac's time)."""
    then, today = local(when), local(now)
    clock = f"{then.tm_hour}:{then.tm_min:02d}"
    if (then.tm_year, then.tm_yday) == (today.tm_year, today.tm_yday):
        return f"today {clock}"
    return f"{MONTHS[then.tm_mon - 1]} {then.tm_mday} {clock}"


def actions(made):
    """MADE ([(id, label)]) as a node's actions, graph.py's shape, the first one primary."""
    return [{"id": kind, "label": label, "path": None, "server": None, "primary": not n}
            for n, (kind, label) in enumerate(made)]


def machine_actions(one):
    """What a machine's properties offer: away, looking again and its sentence's command; else Status, Set up again,
    Remove, and Look around from here on a machine that can look around."""
    if one["why"]:
        return actions([("check", ACTIONS["check"])] + [("copy", ACTIONS["copy"])] * bool(first_command(one["why"])))
    return actions([(kind, ACTIONS[kind]) for kind in ("status", "again", "remove")]
                   + [("through", ACTIONS["through"])] * (one["os"] in LOOKS_AROUND))


def properties(title, state=None, lines=(), why=(), command=None, made=()):
    """A node's properties: its title and state ({text, tone}), why it is away and the first command to run, its
    lines [label, [[words, tone]], what it says at its right, a route's network mark or None], its actions."""
    return {"title": title, "state": state, "why": list(why), "command": command, "lines": list(lines), "text": None,
            "error": None, "tip": None, "actions": list(made)}


def route_line(one, route, n, t):
    """One of a machine's routes: its address (through which machine), the one in use first, the others standby."""
    parts = [[route["address"], "text"]]
    if route["through"]:
        parts += [["  ", "text"], [t("machines.network_through", route["through"]), "muted"]]
    ms = one["figures"]["login_ms"]
    right = [[STANDBY, "muted"]] if n else [[IN_USE, "text"]] + [["  ", "text"], [f"{ms} ms", "muted"]] * (
        ms is not None)
    return ["" if n else "Routes", parts, right, route["network"] or ""]


def machine_properties(one, found, t, runs=None, kept=None, now=None):
    """Machine ONE's properties as the Machines view lists them under its list and the graph's inspector shows them
    (FOUND: seen()'s; RUNS, KEPT: what runs, herdr's machines): why it is away, its address or routes, user, network,
    the way behind another, key, when seen, what runs; its actions."""
    machines, name, why = {other["name"]: other for other in found["machines"]}, one["name"], one["why"]
    state = {"text": AWAY, "tone": "muted"} if why else {"text": CONNECTED, "tone": "ok"} if (kept or {}).get(name) \
        else {"text": NOT_CONNECTED, "tone": "muted"} if kept is not None else None
    lines, routes = [], one["routes"]
    first = (routes or [{}])[0]

    def line(label, words):
        lines.append([label, [[words, "text"]], [], None])

    if len(routes) > 1:
        lines += [route_line(one, route, n, t) for n, route in enumerate(routes)]
    elif first.get("address"):
        line("Address", first["address"])
    if first.get("user"):
        line("User", first["user"])
    if len(routes) <= 1 and (one["network"] in NETWORKS or one["through"]):
        line("Network", t("machines.network_through", one["through"]) if one["network"] == "through"
             else t(f"machines.network_{one['network']}"))
    if one["network"] == "through" and one["through"]:
        line("Path", path_words(one, machines, t))
    if one["key"]:
        line("Key", short_key(one["key"]))
    if one["figures"]["seen"] and (why or {}).get("key") not in OFFLINE:
        line("Last seen", seen_words(one["figures"]["seen"], time.time() if now is None else now))
    there = (runs or {}).get(name)
    if there and not why:
        lines.append(["Runs", runs_parts(there), [], None])
    return properties(name, state, lines, why_lines(why, t) if why else [], first_command(why), machine_actions(one))


def network_properties(title, said, net, names, offered, t, checked, now):
    """A network's properties: its state, why it is not on and what to do, its machines, when that was checked; looking
    again and the command, else its machines to add (a count, as its row in the list)."""
    why = net.get("why")
    lines = [["Machines", [[", ".join(names), "text"]], [], None]] * bool(names)
    lines += [["Checked", [[seen_words(checked, now), "text"]], [], None]] * bool(why and checked)
    made = [("check", ACTIONS["check"])] + [("copy", ACTIONS["copy"])] * bool(first_command(why)) if why else \
        [("add", to_add(len(offered), t))] if offered else []
    return properties(title, {"text": said[0], "tone": said[1]} if said else None, lines,
                      why_lines(why, t) if why else [], first_command(why), actions(made))


# --- the graph

def node(key, column, kind, title, parts=(), icon=None, tag=None, state=None, dim=False, parent=None, network=None,
         props=None):
    """A node in core/graph.py's shape: SUB its PARTS' words ([[words, tone]], kept for their tones), NETWORK the mark
    of a network's node, PROPS its properties (properties()'s)."""
    parts = [list(one) for one in parts]
    return {"id": key, "column": column, "kind": kind, "title": title, "icon": icon, "brand": None, "tag": tag,
            "sub": "".join(words for words, _ in parts) or None, "parts": parts, "state": state, "dim": dim,
            "chips": [], "parent": parent, "network": network, "properties": props or properties(title), "run": None}


def edge(start, end, style, label=None):
    """An edge in core/graph.py's shape, LABEL what it says on its way (direct 22 ms) or None."""
    return {"from": start, "to": end, "style": style, "gates": [], "run": None, "label": label}


def network_id(kind):
    return f"network:{kind or 'other'}"


def machine_id(name):
    return f"machine:{name}"


def graph(found, t, runs=None, kept=None, now=None):
    """FOUND (seen()'s) as the machines' graph: this Mac, each network with machines, some to add or a standby route
    (Other: none tells), each machine (behind another in Through), an edge by each route. T: the catalog's words; RUNS
    what runs on each machine; KEPT the machines herdr keeps (None: not told)."""
    now, runs = time.time() if now is None else now, runs or {}
    machines, groups = {one["name"]: one for one in found["machines"]}, grouped(found)
    by_kind = {group["network"]: group for group in groups}
    standby = {route["network"] for one in found["machines"] for route in one["routes"][1:]}
    kinds = [kind for kind in NETWORKS if kind in by_kind or kind in standby] + [None] * (None in by_kind)
    said = f"{counted(len([kind for kind in kinds if kind]), 'network')}, {counted(len(machines), 'machine')}"
    nodes, edges, failing = [node(MAC, "mac", "mac", THIS_MAC, [[said, "text"]], icon="monitor")], [], set()
    for kind in kinds:
        group = by_kind.get(kind) or {"net": found["networks"].get(kind) or {}, "offered": [], "machines": []}
        state, names = state_words(kind, group["net"], t), [one["name"] for one, _ in group["machines"]]
        sub = counted(len(names), "machine") if names else to_add(len(group["offered"]), t) if group["offered"] \
            else BY_ADDRESS if kind in by_kind else None
        title = t(f"machines.network_{kind}") if kind else OTHER
        nodes.append(node(network_id(kind), "networks", "network", title, [[sub, "muted"]] * bool(sub),
                          tag=state and state[0], state="warn" if state and state[1] == "warn" else None,
                          dim=bool(state) and state[1] == "muted", parent=MAC, network=kind,
                          props=network_properties(title, state, group["net"], names, group["offered"], t,
                                                   found.get("checked"), now)))
        edges.append(edge(MAC, network_id(kind), "failed" if state else "always"))
        failing.update([network_id(kind)] * bool(state))
    # this Mac to a network failed while it is not on; a network (a jump host) to a machine by its route in use, direct
    # always, relayed demand, away failed, its label the way and the time measured; its other routes standby, no label
    for group in groups:
        for one, depth in group["machines"]:
            name, why, there = one["name"], one["why"], runs.get(one["name"])
            jump = one["through"] if one["network"] == "through" and one["through"] in machines \
                and one["through"] != name else None
            parts = [[AWAY, "bad"]] if why else runs_parts(there) if there else [[NOT_CONNECTED, "muted"]] * (
                kept is not None and not kept.get(name))
            nodes.append(node(machine_id(name), "through" if depth else "machines", "machine", name, parts,
                              icon="server", tag=one["os"] or None,
                              state="bad" if why else "warn" if waiting(there) else None,
                              dim=network_id(group["network"]) in failing,
                              parent=machine_id(jump) if depth else network_id(group["network"]),
                              props=machine_properties(one, found, t, runs, kept, now)))
            style = "failed" if why else "demand" if one["figures"]["path"] == "relayed" else "always"
            edges.append(edge(machine_id(jump) if jump else network_id(group["network"]), machine_id(name), style,
                              None if why else way_words(one["figures"]) or None))
    drawn = {(one["from"], one["to"]) for one in edges}
    for group in groups:
        for one, _ in group["machines"]:
            for route in one["routes"][1:]:
                start = network_id(route["network"]) if route["network"] in NETWORKS else machine_id(route["through"]) \
                    if route["through"] in machines and route["through"] != one["name"] else None
                if start and (start, machine_id(one["name"])) not in drawn:
                    drawn.add((start, machine_id(one["name"])))
                    edges.append(edge(start, machine_id(one["name"]), "standby"))
    return {"columns": COLUMNS, "words": WORDS, "checked": found.get("checked"), "nodes": nodes, "edges": edges}


# --- the app's command

def catalog(words):
    """A t() over WORDS (the catalog's texts by key, the app's MACHINE_WORDS): %s takes the next argument, %% is a
    percent sign, \\n a new line, as src/i18n.py fills them; a key it was not given says nothing."""
    texts = {key: text for key, text in words.items() if isinstance(key, str) and isinstance(text, str)}

    def t(key, *args):
        values = iter(args)
        return re.sub(r"%s|%%|\\n", lambda found: str(next(values, "")) if found.group() == "%s"
                      else "%" if found.group() == "%%" else "\n", texts.get(key, ""))
    return t


def main(argv):
    """The Herdr app mod runs this on this Mac, answering in JSON: graph()'s of LOOK (core/networks.py's here, its JSON;
    -: piped in, LOOK_MOST at most) in WORDS (the catalog's machines.* texts), --runs and --kept as checked_runs() and
    checked_kept() take them."""
    options = dict(arg[2:].split("=", 1) for arg in argv[1:] if arg.startswith("--") and "=" in arg)
    args = [arg for arg in argv[1:] if not arg.startswith("--")]
    if args[:1] == ["-"]:
        given = sys.stdin.read(LOOK_MOST + 1)
        args[0] = given if len(given) <= LOOK_MOST else ""
    try:
        look, words = [json.loads(one) for one in args] if len(args) == 2 else (None, None)
        runs, kept = [json.loads(options[key]) if key in options else None for key in ("runs", "kept")]
    except (ValueError, RecursionError):
        look = words = None
    if not isinstance(look, dict) or not isinstance(words, dict):
        print(USAGE, file=sys.stderr)
        return 2
    print(json.dumps(graph(seen(look), catalog(words), checked_runs(runs), checked_kept(kept))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
