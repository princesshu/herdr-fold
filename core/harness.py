"""An agent's harness changed from the Agent panel, in both clients' words: a form's change planned (its choices, its
layers, the lines it takes out and puts in, when it applies, what overrides it, why it is refused), then made by
harness_edit.py in the agent's own settings file. Usage (in JSON): harness.py plan|apply AGENT FOLDER JSON."""
import contextlib
import json
import os
import re
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import agent_setup as setup  # noqa: E402
import words  # noqa: E402
from connectors import toggle  # noqa: E402
from harness_edit import (CLAUDE_EFFORTS, CODEX_EFFORTS, EFFORT_KEY, ENABLED_KEY, GLOBAL, HOST, HOSTS_KEY,  # noqa: E402
                          LAYERS, LOCAL, MANAGED, MODE_IDS, MODE_KEY, MODEL, POLICIES, PROJECT, Refused, apply, changed,
                          place, plain, same, toml_find, value_at)
from locate import repo_top  # noqa: E402
from model_windows import WINDOWS  # noqa: E402

ORDER = (GLOBAL, PROJECT, LOCAL, MANAGED)       # a later layer's value over an earlier one's
# the modes offered, in the chat's words (Bypass: the form's short one)
MODES = {mode: "Bypass" if mode == "bypassPermissions" else setup.MODE_WORDS[mode] for mode in MODE_IDS}
NAMED_UNDER = ("skillOverrides", "modelSettings")       # the keys that hold an entry a name: a skill's, a model's
GLOBAL_MODES = ("auto", "bypassPermissions")    # Claude ignores these in a project's and a local file
APPROVALS = {**{policy: setup.APPROVALS[policy] for policy in POLICIES}, "granular": "Granular"}
AGENT_NAME = re.compile(r"[\w.:-]{1,80}")       # a subagent's name, as a deny rule's Agent(name) takes it
# when a change applies, and why one is not offered
NOW, NEXT = "Applies now", "From the next session"
ORG = "Set by your organization"
GLOBAL_ONLY = "Auto and Bypass permissions work only in Global"
NOT_RULE = "Not a rule Claude takes"
CODEX_RULES = "Codex keeps its rules in a file of their own: change it there"
IN_GIT = "In git: your team gets it with your next commit"
OWN_HOOK = "Also stops herdr-fold's own hook: decisions go back to Claude's terminal"
MACHINE = "Mac" if sys.platform == "darwin" else "computer"


def told(agent, folder, home, key):
    """Each layer's value at KEY, the weakest first and the organization's last: {scope: value}, a layer that sets
    none left out (Codex's: a plain string alone)."""
    found = {}
    if agent == "codex":
        for layer in LAYERS["codex"]:
            with contextlib.suppress(Refused):
                mine = toml_find(setup.read_text(place(agent, layer, folder, home)) or "", *key)[0]
                found.update({layer: mine["plain"].group(2)} if mine else {})
        return found
    for path, scope in setup.settings(folder, home):
        value = value_at(setup.read_json(path), key)
        found.update({scope: value} if value is not None else {})
    return found


def layer_of(agent, asked, found, default):
    """The layer a change is saved in: the one ASKED for, else the strongest written one in FOUND (told()'s), else
    DEFAULT; ValueError for one never written."""
    layer = asked.get("layer") or max((scope for scope in found if scope in LAYERS[agent]), key=ORDER.index,
                                      default=default)
    if layer not in LAYERS[agent]:
        raise ValueError("not a layer herdr-fold writes")
    return layer


def put_value(found, layer, key, value):
    """The edits that set KEY to VALUE in LAYER (FOUND: told()'s; none for no VALUE, or where it holds it), and a
    sentence for each stronger layer that sets another."""
    if value is None:
        return [], []
    edits = [] if same(found.get(layer), value) else [{"layer": layer, "key": list(key), "before": found.get(layer),
                                                       "after": value}]
    return edits, [f"{scope} sets {json.dumps(theirs)}: it wins in this folder" for scope, theirs in found.items()
                   if ORDER.index(scope) > ORDER.index(layer) and not same(theirs, value)]


def field(key, label, kind, value, **more):
    return {"id": key, "label": label, "kind": kind, "value": value, **more}


def choices(labels, off=None):
    return [{"id": key, "label": label, "off": (off or {}).get(key)} for key, label in labels.items()]


def changes(agent, folder, home, edits):
    """EDITS as the lines a form shows, by file in their order: [{path, lines: [["-", what goes], ["+", what
    comes]]}]."""
    found = {}
    for edit in edits:
        path, key = setup.shown(place(agent, edit["layer"], folder, home), folder, home), edit["key"]
        listed, said = "before" not in edit, lambda value: json.dumps(value, ensure_ascii=False)
        for sign, value in (("-", edit.get("remove") if listed else edit["before"]),
                            ("+", edit.get("add") if listed else edit["after"])):
            if value is not None:
                for name in key[:0:-1] if key[0] in NAMED_UNDER and not listed else ():
                    value = {name: value}           # a name's own entry: shown from the key that holds them all
                text = f'{key[-1]} = "{value}"' if agent == "codex" else f"{key[-1]} {said(value)}" if listed else \
                    f'"{key[0] if key[0] in NAMED_UNDER else key[-1]}": {said(value)}'
                found.setdefault(path, {"path": path, "lines": []})["lines"].append([sign, text])
    return list(found.values())


def planned(agent, folder, home, fields, layer=None, among=None, edits=(), when=None, submit="Save", **said):
    """A plan both clients draw: FIELDS, the layers (AMONG, else the agent's) with LAYER chosen, none without one;
    EDITS tried on the files as they are: their lines, WHEN they apply and the button, or the error."""
    plan = {"fields": fields, "saved": "Saved in", "layers": [], "changes": [], "when": None, "warns": [], "ask": None,
            "submit": None, "cancel": "Cancel", "remove": None, "error": None, "edits": [], "done": None,
            "undo": "Undo", "say": [], "now": None, "more": None, **said}
    plan["layers"] = [{"id": one, "label": one, "path": setup.shown(place(agent, one, folder, home), folder, home),
                       "chosen": one == layer} for one in among or LAYERS[agent] if layer]
    if edits and not plan["error"]:
        try:
            changed(agent, folder, home, list(edits))
        except Refused as why:
            plan["error"] = str(why)
        else:
            plan.update(edits=list(edits), changes=changes(agent, folder, home, edits), when=when, submit=submit)
    return plan


def last(found):
    return list(found.values())[-1] if found else None


def profile(folder, home, layer):
    """What stands between Codex and LAYER's file, a sentence each: a profile its Global file names over Global, a
    Project file read only once Codex trusts FOLDER."""
    name = told("codex", folder, home, ("profile",)).get(GLOBAL)
    return [f"Profile {name} wins over Global, not over Project"] * bool(name and layer == GLOBAL) + [
        f"Codex reads it once it trusts {os.path.basename(folder)}"] * (
            layer == PROJECT and not setup.codex_trusted(folder, home))


def mode(agent, folder, home, asked):
    """Claude's mode (permissions.defaultMode): {"value": a MODES id}."""
    found = told(agent, folder, home, MODE_KEY)
    layer, value = layer_of(agent, asked, found, PROJECT), asked.get("value")
    off = {one: GLOBAL_ONLY for one in GLOBAL_MODES if layer != GLOBAL}
    if value is not None and value not in MODES:
        raise ValueError("not a mode")
    edits, warns = put_value(found, layer, MODE_KEY, None if value in off else value)
    return planned(agent, folder, home, [field("value", "Mode", "choice", value or found.get(layer) or last(found),
                                               choices=choices(MODES, off), hint=GLOBAL_ONLY if off else None)],
                   layer, edits=edits, when=NEXT, warns=warns, error=off.get(value))


def model(agent, folder, home, asked):
    """The model and the effort a chat starts with: {"model": an alias or an id, "effort", "runs": the head's, the
    model in use where no file names one}. Claude's effort is kept where that model reads it: under its own id in
    modelSettings (words.own_effort()), else effortLevel. "say": what a running Claude chat is told to switch now."""
    codex, wanted, runs = agent == "codex", [asked.get("model"), asked.get("effort")], asked.get("runs")
    models, efforts = told(agent, folder, home, ("model",)), CODEX_EFFORTS if codex else CLAUDE_EFFORTS
    if any(one is not None and not plain(one, MODEL) for one in (wanted[0], runs)) or wanted[1] not in (None, *efforts):
        raise ValueError("not a model or an effort")
    own = None if codex else words.own_effort(wanted[0] or last(models) or runs)
    keys = (("model",), ("model_reasoning_effort",) if codex else ("modelSettings", own, "effortLevel") if own
            else EFFORT_KEY)
    found = [models, told(agent, folder, home, keys[1])]
    layer = layer_of(agent, asked, {**found[0], **found[1]}, GLOBAL if codex else PROJECT)
    made = [put_value(one, layer, key, value) for one, key, value in zip(found, keys, wanted)]
    edits, warns = made[0][0] + made[1][0], made[0][1] + made[1][1]
    say = [f"/{word} {edit['after']}" for word, (their, _) in zip(("model", "effort"), made) for edit in their]
    files = [setup.obj(setup.read_json(path).get("env")) for path, _ in setup.settings(folder, home)]
    warns += [f"{env} is set: it wins over every file" for env in ("ANTHROPIC_MODEL", setup.EFFORT_ENV)
              if not codex and (os.environ.get(env) or any(one.get(env) for one in files))]
    shown = [value or one.get(layer) or last(one) for value, one in zip(wanted, found)]
    ids = sorted((one for one in WINDOWS if "codex" in one), reverse=True) if codex else list(words.FAMILIES)
    ids += [one for one in shown[:1] if isinstance(one, str) and one not in ids]
    return planned(agent, folder, home, [
        field("model", "Model", "choice", shown[0], choices=choices({one: words.model_name(one) for one in ids})),
        field("effort", "Effort", "choice", shown[1], choices=choices({one: setup.EFFORTS[one] for one in efforts}))],
        layer, edits=edits, when=NEXT, warns=warns + (profile(folder, home, layer) if codex else []),
        say=[] if codex else say, now="Switch this chat now" if say and not codex else None)


def choice(folder, home, asked, key, label, labels, off, warn):
    """One of Codex's settings of a few values: {"value": one of LABELS}; OFF, WARN: {value: why not, a sentence}."""
    found = told("codex", folder, home, key)
    layer, value = layer_of("codex", asked, found, GLOBAL), asked.get("value")
    if value is not None and value not in labels:
        raise ValueError("not a value")
    edits, warns = put_value(found, layer, key, None if value in off else value)
    return planned("codex", folder, home, [field("value", label, "choice", value or found.get(layer) or last(found),
                                                 choices=choices(labels, off))], layer, edits=edits, when=NEXT,
                   warns=warns + [warn[one] for one in warn if one == value] + profile(folder, home, layer),
                   error=off.get(value))


def approval(agent, folder, home, asked):
    """Codex's approval policy: {"value": on-request or never}; a table of its own (granular) is the file's."""
    return choice(folder, home, asked, ("approval_policy",), "Approval", APPROVALS,
                  {"granular": "Granular is set in the file"}, {})


def sandbox(agent, folder, home, asked):
    """Codex's sandbox mode: {"value"}. Claude's Bash sandbox: {"on", "add": a host, "remove": one of the layer's
    own}; the "add" field's "items" every layer's hosts (one an allow rule gives: its "rule")."""
    if agent == "codex":
        return choice(folder, home, asked, ("sandbox_mode",), "Sandbox", setup.SANDBOXES, {}, {
            "danger-full-access": f"No sandbox: commands can change any file on this {MACHINE} and reach the network"})
    found = told(agent, folder, home, ENABLED_KEY)
    layer, on, add = layer_of(agent, asked, found, PROJECT), asked.get("on"), asked.get("add")
    gone = asked.get("remove")
    hosts = []
    for path, scope in setup.settings(folder, home):
        hosts += [{"host": host, "layer": scope, "rule": None}
                  for host in setup.strings(value_at(setup.read_json(path), HOSTS_KEY))]
        hosts += [{"host": one.group(1), "layer": scope, "rule": one.group()} for one in map(
            setup.WEB_DOMAIN.fullmatch, setup.strings(setup.permission_table(path).get("allow"))) if one]
    own = [one["host"] for one in hosts if one["layer"] == layer and not one["rule"]]
    if on is not None and type(on) is not bool or gone is not None and gone not in own:
        raise ValueError("not a sandbox's change")
    edits, warns = put_value(found, layer, ENABLED_KEY, on)
    add, error = add.strip() if isinstance(add, str) else "", None
    if add:
        there = next((one["layer"] for one in hosts if one["host"] == add and not one["rule"]), None)
        error = "Not a host's name" if not plain(add, HOST) else f"Already in {there}" if there else None
        edits += [] if error else [{"layer": layer, "key": list(HOSTS_KEY), "add": add}]
    edits += [{"layer": layer, "key": list(HOSTS_KEY), "remove": gone}] if gone is not None else []
    others = [scope for scope in dict.fromkeys(one["layer"] for one in hosts) if scope != layer]
    return planned(agent, folder, home, [
        field("on", "Bash sandbox", "switch", last(found) is True if on is None else on),
        field("add", "Hosts", "text", add, items=hosts)], layer, edits=edits, warns=warns, error=error,
        when=NOW + (f" · adds to {' and '.join(others)}'s hosts" if add and others else ""),
        more={"label": "More options", "path": place(agent, layer, folder, home)})


def rule(agent, folder, home, asked):
    """A rule of Claude's added ({"rule", "behavior"}), changed or moved ("was": {rule, behavior, layer} too), or
    removed ("was", "remove": true; "ask" the question, "done" the line after)."""
    was, text, gone = asked.get("was"), asked.get("rule"), asked.get("remove") is True
    if agent == "codex":
        return planned(agent, folder, home, [], error=CODEX_RULES)
    if was is not None and not (isinstance(was, dict) and was.get("behavior") in setup.BEHAVIORS
                                and was.get("layer") in ORDER and isinstance(was.get("rule"), str)) or gone and not was:
        raise ValueError("not a rule's change")
    layer = (was or {}).get("layer", PROJECT) if gone or not asked.get("layer") else asked["layer"]
    behavior = asked.get("behavior") or (was or {}).get("behavior", "allow")
    fields = [field("rule", "Rule", "text", (was or {}).get("rule", "") if text is None else text),
              field("behavior", "Behavior", "choice", behavior, choices=choices({one: one for one in setup.BEHAVIORS}))]
    if was and was["layer"] == MANAGED:
        return planned(agent, folder, home, fields, error=ORG)
    if layer not in LAYERS[agent] or behavior not in setup.BEHAVIORS:
        raise ValueError("not a rule's change")
    tables = {scope: setup.permission_table(path) for path, scope in setup.settings(folder, home)
              if scope in LAYERS[agent]}
    key, said = ["permissions", behavior], {"remove": "Remove" if was else None}
    old = {"layer": was["layer"], "key": ["permissions", was["behavior"]], "remove": was["rule"]} if was else None
    if was and was["rule"] not in setup.strings(tables[was["layer"]].get(was["behavior"])):
        return planned(agent, folder, home, fields, layer, error=f"No longer in {was['layer']}", **said)
    if gone:
        return planned(agent, folder, home, fields, layer, edits=[old], when=NOW, submit="Remove",
                       ask=f"Remove from {layer}?", done=f"Removed {was['rule']} from {layer}",
                       warns=[IN_GIT] * (layer == PROJECT and bool(repo_top(folder))), **said)
    new = setup.rule_text(was["rule"] if was and text is None else text)
    if not new or old == {"layer": layer, "key": key, "remove": new}:
        return planned(agent, folder, home, fields, layer, error=NOT_RULE if text and not new else None, **said)
    if new in setup.strings(tables[layer].get(behavior)):
        return planned(agent, folder, home, fields, layer, error=f"Already in {layer}", **said)
    edits = [{**old, "add": new}] if old and (old["layer"], old["key"]) == (layer, key) else \
        [old] * bool(old) + [{"layer": layer, "key": key, "add": new}]
    mine = {"rule": new, "behavior": behavior, "scope": layer, "path": None}
    rules = [one for one in setup.permissions(folder, home)["rules"] if not was or (
        one["rule"], one["behavior"], one["scope"]) != (was["rule"], was["behavior"], was["layer"])] + [mine]
    return planned(agent, folder, home, fields, layer, edits=edits, when=NOW, submit="Save" if was else "Add", warns=[
        f"{one['behavior']} {one['rule']} in {one['scope']} hides it: this rule would never apply"
        for one in setup.conflicts(rules) if one["hides"] is mine], **said)


def conflict(agent, folder, home, asked):
    """A rule Claude never reaches ({"behavior", "rule"}) let through one "way": the rule hiding it removed, or
    narrowed to "to" (it must match less than before, and the hidden one no more)."""
    if agent == "codex":
        return planned(agent, folder, home, [], error=CODEX_RULES)
    found = next((one for one in setup.permissions(folder, home)["conflicts"] if (
        one["hides"]["behavior"], one["hides"]["rule"]) == (asked.get("behavior"), asked.get("rule"))), None)
    way, to = asked.get("way"), asked.get("to")
    if way not in (None, "remove", "narrow"):
        raise ValueError("not a way out of a conflict")
    if not found:
        return planned(agent, folder, home, [], error="No longer hidden")
    hider, hidden, locked = found["rule"], found["hides"], found["scope"] == MANAGED
    ways = {"remove": f"Remove the {found['behavior']} in {found['scope']}",
            "narrow": f"Narrow the {found['behavior']}"}
    fields = [field("way", found["text"], "choice", way,
                    choices=choices(ways, dict.fromkeys(ways, ORG) if locked else {}))]
    fields += [field("to", "Rule", "text", hider if to is None else to)] if way == "narrow" else []
    edit, new = {"layer": found["scope"], "key": ["permissions", found["behavior"]], "remove": hider}, None
    if way == "narrow" and to and not locked:
        new = setup.rule_text(to)
        error = NOT_RULE if not new else f"Not narrower than {hider}" if new == hider or not setup.covers(hider, new) \
            else f"Still hides {hidden['behavior']} {hidden['rule']}" if setup.covers(new, hidden["rule"]) else None
        if error:
            return planned(agent, folder, home, fields, error=error)
    return planned(agent, folder, home, fields, edits=[{**edit, **({"add": new} if new else {})}] * bool(
        not locked and (new or way == "remove")), when=NOW, error=ORG if locked else None)


def turned(folder, home, key, item=None):
    """The layers whose settings file turns a thing off, the weakest first: ITEM in the list at KEY, else KEY set
    (a skill's override to "off", any other to true)."""
    found = []
    for path, scope in setup.settings(folder, home):
        value = value_at(setup.read_json(path), key)
        if item in value if isinstance(value, list) and item is not None else \
                item is None and value == ("off" if key[0] == "skillOverrides" else True):
            found.append(scope)
    return list(dict.fromkeys(found))


def switch(agent, folder, home, asked, key, item, when, layers=(PROJECT, LOCAL), also=(), turn=None, on=None,
           label=None, short="On here", **said):
    """A thing of Claude's off in FOLDER by one entry (turned()'s), on again with it out wherever it is: {"on",
    "layer"}. ALSO: edits made with turning it on; TURN: the two buttons' words; ON: whether it is on now."""
    here, off, wanted = os.path.basename(folder), turned(folder, home, key, item), asked.get("on")
    layer, value = asked.get("layer") or LOCAL, "off" if key[0] == "skillOverrides" else True
    if wanted is not None and type(wanted) is not bool or layer not in layers:
        raise ValueError("not a switch's change")
    made = {"key": list(key), **({"add": item} if item is not None else {"before": None, "after": value})}
    back = {"key": list(key), **({"remove": item} if item is not None else {"before": value, "after": None})}
    edits = [{"layer": layer, **made}] * (layer not in off) if wanted is False else \
        [{"layer": scope, **back} for scope in off] + list(also) if wanted else []
    locked = bool(wanted) and MANAGED in off
    fields = [field("on", label or f"On in {here}", "switch", (not off if on is None else on) if wanted is None
                    else wanted, short=short, turn=turn or {"on": f"Turn on in {here}", "off": f"Turn off in {here}"})]
    return planned(agent, folder, home, fields, None if wanted else layer, layers, edits=[] if locked else edits,
                   when=when, error=ORG if locked else None, **said)


def skill(agent, folder, home, asked):
    """A skill of the user's or the project's off in FOLDER (skillOverrides, as Claude's /skills writes it): {"name",
    "on", "layer"}; a plugin's turns off with its plugin."""
    name, found = asked.get("name"), setup.skills(folder, home)
    if not plain(name):
        raise ValueError("not a skill's name")
    if any(one["name"] == name for one in found) and all(setup.plugged(one) for one in found if one["name"] == name):
        return planned(agent, folder, home, [], error="Turns off with its plugin")
    return switch(agent, folder, home, asked, ["skillOverrides", name], None, NEXT)


def subagent(agent, folder, home, asked):
    """A subagent off in FOLDER (a deny rule, Agent(name)): {"name", "on"}."""
    if not plain(asked.get("name"), AGENT_NAME):
        raise ValueError("not a subagent's name")
    return switch(agent, folder, home, asked, ["permissions", "deny"], f"Agent({asked['name']})", NEXT)


def hooks(agent, folder, home, asked):
    """Every hook off in one settings file's reach (disableAllHooks: Claude has no switch for one hook): {"on"}."""
    here = os.path.basename(folder)
    return switch(agent, folder, home, asked, ["disableAllHooks"], None, NOW, LAYERS[agent],
                  label=f"All hooks in {here}", short="All hooks here", warns=[OWN_HOOK] * (asked.get("on") is False))


def connector(agent, folder, home, asked):
    """A server off in FOLDER ({"name", "on", "layer"}): the project's .mcp.json's by disabledMcpjsonServers (on:
    approved too), any other by deniedMcpServers; "say" where Claude's own state turns it off. {"starts", "tokens"}
    (the head's, the row's) make "when" tell what new chats start at."""
    name, wanted, here = asked.get("name"), asked.get("on"), os.path.basename(folder)
    if not plain(name):
        raise ValueError("not a server's name")
    config = setup.read_json(os.path.join(home, ".claude.json"), setup.CONFIG_LARGEST)
    entry = setup.obj(setup.obj(config.get("projects")).get(setup.project_key(folder)))
    row = next((one for one in setup.defined(folder, home, config) if one["name"] == name), None)
    path, every, approved, refused = setup.mcpjson(folder, home, entry)
    if row and row["scope"] == MANAGED:
        return planned(agent, folder, home, [], error=ORG)
    project = bool(row) and row["path"] == path
    waits = project and not (every or name in approved)
    kept = name in setup.strings(entry.get("disabledMcpServers")) + setup.strings(entry.get("disabledMcpjsonServers"))
    starts, tokens = asked.get("starts"), asked.get("tokens")
    less = f" · new chats start at ~{words.tokens(starts - tokens)}" if wanted is False and type(starts) is int \
        and type(tokens) is int and 0 < tokens <= starts else ""
    say = []
    with contextlib.suppress(ValueError):
        say = [toggle(name, True)] * bool(wanted and kept)
    return switch(agent, folder, home, asked, *((["disabledMcpjsonServers"], name) if project else (
        ["deniedMcpServers"], {"serverName": name})), NEXT + less, say=say, on=None if not waits else False,
        also=[{"layer": asked.get("layer") or LOCAL, "key": ["enabledMcpjsonServers"], "add": name}] * waits,
        turn={"on": f"Approve in {here}", "off": "Keep off"} if waits and name not in refused else None)


# a form's action, its plan and the agents it is for (a Codex rule's answers why it is not changed here)
PLANS = {"mode": (mode, ("claude",)), "model": (model, ("claude", "codex")), "sandbox": (sandbox, ("claude", "codex")),
         "approval": (approval, ("codex",)), "rule": (rule, ("claude", "codex")),
         "conflict": (conflict, ("claude", "codex")), "skill": (skill, ("claude",)),
         "subagent": (subagent, ("claude",)), "connector": (connector, ("claude",)), "hooks": (hooks, ("claude",))}


def plan(agent, folder, home, asked):
    """AGENT's form for ASKED ({"action": PLANS' key, "layer", the action's own; the action alone: as it opens) in
    FOLDER, with the edits harness_edit.py makes of it; nothing written. ValueError for a request no form makes."""
    made, agents = PLANS.get(asked.get("action") if isinstance(asked, dict) else None, (None, ()))
    if agent not in agents or not isinstance(folder, str) or not os.path.isabs(folder):
        raise ValueError("not a change herdr-fold plans")
    return made(agent, os.path.normpath(folder), home, asked)


def main(argv):
    """Both clients run this on the space's machine, answering in JSON: plan AGENT FOLDER REQUEST (plan()'s), apply
    AGENT FOLDER EDITS (harness_edit.py's apply()); a request or an edit no form makes is the usage."""
    try:
        if argv[1:2] not in (["plan"], ["apply"]) or len(argv) != 5:
            raise ValueError("not a command")
        made = (plan if argv[1] == "plan" else apply)(argv[2], argv[3], os.path.expanduser("~"), json.loads(argv[4]))
    except ValueError:
        print("usage: harness.py plan AGENT FOLDER REQUEST | apply AGENT FOLDER EDITS", file=sys.stderr)
        return 2
    print(json.dumps(made))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
