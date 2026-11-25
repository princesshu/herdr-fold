# Generated from core/costs.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""What one chat cost, for the graph's This chat in both clients: its agent and each subagent type with its model,
turns, tokens, share (beside a subagent) and inspector lines, from tokens.py's index at prices.py's prices. Only read.
Usage (in JSON): costs.py AGENT SESSION [--agents=JSON] [--surface=# --text=#]."""
import json
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import prices  # noqa: E402
import statefile  # noqa: E402
import tokens  # noqa: E402
from jsonl import obj  # noqa: E402
from prices import money  # noqa: E402
from words import model_name, percent, tokens as said_tokens  # noqa: E402

AGENTS = ("claude", "codex")
API_KEY = "API key"             # the agents' list's word for an agent on an API key: its cost is spent
PROMPT = ("input", "write_5m", "write_1h", "read")      # the kinds a prompt is made of
EVER = 1 << 62                  # past every hour


def summed(rows, models):
    """ROWS (tokens.rows()'s, one agent's) as one: each kind's tokens, the turns, the models with the most tokens
    first, the cost at MODELS' prices (None where none of them has a price)."""
    sums = {kind: sum(row[kind] for row in rows) for kind in tokens.KINDS}
    by_model, cost = {}, None
    for row in rows:
        by_model[row["model"]] = by_model.get(row["model"], 0) + sum(row[kind] for kind in PROMPT) + row["output"]
        one = prices.cost(row, prices.price_of(row["model"], models))
        cost = cost if one is None else (cost or 0) + one
    return {**sums, "turns": sum(row["messages"] for row in rows), "cost": cost,
            "tokens": sum(sums[kind] for kind in PROMPT) + sums["output"],
            "models": sorted(by_model, key=lambda model: -by_model[model])}


def said(one, whole, kind, sub, seen, theme, shared):
    """An agent's sums ONE as the graph says them (SUB: a subagent's), beside the chat's WHOLE (its share of it where
    SHARED, more than one agent ran); KIND: "API value" or "spent"; SEEN the chat's models in order, THEME a card and
    its text (the models' colors)."""
    model, cost = one["models"][0], one["cost"]
    share = cost / whole["cost"] if cost is not None and whole["cost"] else \
        one["tokens"] / whole["tokens"] if whole["tokens"] else 1.0
    prompt = sum(one[kind] for kind in PROMPT)
    text = "no price" if cost is None else money(cost, True)
    turns = [] if sub else [f"{one['turns']} turn{'s' * (one['turns'] != 1)}"]
    lines = [["Model", ", ".join(model_name(each) for each in one["models"]), None],
             ["Input", said_tokens(one["input"]), None],
             ["Cache write", said_tokens(one["write_5m"] + one["write_1h"]), None],
             ["Cache read", said_tokens(one["read"]), f"{percent(one['read'] / prompt)} of its input" if one["read"]
              else None],
             ["Output", said_tokens(one["output"]), None]]
    lines += [["Share", f"{percent(share)} of this chat", None]] * shared
    return {"cost": cost, "text": text, "title": text if cost is None else f"{text} {kind}",
            "model": {"id": model, "name": model_name(model),
                      "color": prices.model_color(model, seen, *(theme or (None, None)))},
            "turns": one["turns"], "tokens": one["tokens"], "share": share,
            "sub": " · ".join([model_name(model)] + turns + [f"{said_tokens(one['tokens'])} tokens"]), "lines": lines}


def costs(state, agent, path, agents=None, table=None, theme=None):
    """What the chat in AGENT's file PATH cost, from STATE's index: {"session", "kind", "text" (its whole), "tokens",
    "agent": said()'s, "subs": {type: said()'s}, "line"}; None with no message yet. AGENTS: the agents' list (a plan
    "API key": spent); TABLE: prices.prices()'s; THEME: said()'s."""
    try:
        session = os.path.basename(path)[:-len(".jsonl")] if agent == "claude" else tokens.codex_session(path)[0]
    except OSError:
        return None
    files = {one: entry for one, entry in tokens.load(state)["files"].items()
             if entry.get("agent") == agent and entry.get("session") == session}
    rows = sorted(tokens.rows({"files": files}, 0, EVER), key=lambda row: (row["hour"], row["model"]))
    if not [row for row in rows if row["sub"] is None]:
        return None
    models = (table or prices.prices(state))["models"]
    plan = next((obj(one).get("plan") for one in agents if obj(one).get("key") == agent), None) \
        if isinstance(agents, list) else None
    kind, seen = "spent" if plan == API_KEY else "API value", list(dict.fromkeys(row["model"] for row in rows))
    whole, types = summed(rows, models), list(dict.fromkeys(row["sub"] for row in rows if row["sub"] is not None))
    own = said(summed([row for row in rows if row["sub"] is None], models), whole, kind, False, seen, theme,
               bool(types))
    subs = {sub: said(summed([row for row in rows if row["sub"] == sub], models), whole, kind, True, seen, theme,
                      True) for sub in types}
    prompt = sum(whole[kind] for kind in PROMPT)
    text = "no price" if whole["cost"] is None else money(whole["cost"], True)
    return {"session": session, "kind": kind, "text": text, "tokens": said_tokens(whole["tokens"]), "agent": own,
            "subs": subs, "line": f"{said_tokens(whole['tokens'])} tokens" + (
                f" · {percent(whole['read'] / prompt)} from cache" if whole["read"] else "")}


def filed(state, agent, session):
    """The file of AGENT's conversation SESSION (its id) as STATE's index knows it, its newest where it was resumed
    into another; None where it knows none."""
    found = [(entry.get("mtime") or 0, path) for path, entry in tokens.load(state)["files"].items()
             if entry.get("agent") == agent and entry.get("session") == session and entry.get("sub") is None]
    return max(found)[1] if found else None


def main(argv):
    """herdr-fold's Herdr app mod runs this, answering in JSON: AGENT SESSION (its file, or its id), costs()'s after
    the index is brought up to date ("left": the bytes it has yet to read), null with no message yet."""
    options = dict(arg[2:].split("=", 1) for arg in argv[1:] if arg.startswith("--") and "=" in arg)
    args = [arg for arg in argv[1:] if not arg.startswith("--")]
    try:
        agents = json.loads(options["agents"]) if "agents" in options else None
    except ValueError:
        args = []
    if len(args) != 2 or args[0] not in AGENTS:
        print("usage: costs.py claude|codex SESSION [--agents=JSON] [--surface=#hex --text=#hex]",
              file=sys.stderr)
        return 2
    state = statefile.folder()
    left = tokens.index(state)["left"]
    path = args[1] if os.path.isfile(args[1]) else filed(state, *args)
    found = path and costs(state, args[0], path, agents, theme=(options.get("surface"), options.get("text")))
    print(json.dumps(found and {**found, "left": left}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
