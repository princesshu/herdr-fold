"""What one conversation cost, for the graph's This conversation in both clients: its agent and each sub-agent type
with its model, turns, tokens, share and inspector lines, from tokens.py's index at prices.py's prices, and Claude's
own count beside it. Only read. Usage (in JSON): costs.py AGENT SESSION [--agents=JSON] [--surface=# --text=#]."""
import json
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import prices  # noqa: E402
import statefile  # noqa: E402
import tokens  # noqa: E402
from jsonl import obj, open_regular, parse  # noqa: E402
from prices import money, short  # noqa: E402

AGENTS = ("claude", "codex")
API_KEY = "API key"             # the agents' list's word for an agent on an API key: its cost is spent
COUNT = b'"type":"cost-state"'  # a line of Claude's own count of a conversation; the newest one is its whole
BACK = 8 << 20                  # bytes read at a time from a session's end, looking for that line
LINE = 64 << 20                 # bytes of one line kept while looking: a longer one is no count
PROMPT = ("input", "write_5m", "write_1h", "read")      # the kinds a prompt is made of
EVER = 1 << 62                  # past every hour


def millions(count):
    """COUNT tokens as an inspector's value: 0.79M, a small one as it is (short()'s), none as 0."""
    return f"{count / 1e6:.2f}M" if count >= 10_000 else short(count)


def percent(share):
    return f"{int(share * 100 + 0.5)}%"


def counted(path):
    """Claude's own count of the conversation in the session file PATH in dollars, its newest cost-state line's (read
    from the file's end); None where it has none, or one that is no amount."""
    try:
        with open_regular(path, "rb") as f:
            end, kept = f.seek(0, os.SEEK_END), b""
            while end > 0 and len(kept) <= LINE:
                start = max(0, end - BACK)
                f.seek(start)
                data = f.read(end - start) + kept
                place, cut = data.rfind(COUNT), data.find(b"\n")
                first = data.rfind(b"\n", 0, place) + 1 if place >= 0 else 0
                if place >= 0 and (first or not start):
                    stop = data.find(b"\n", place)
                    total = parse(data[first:stop if stop >= 0 else len(data)]).get("totalCostUSD")
                    return total if prices.number(total) else None
                # its line starts further back: all of it kept; none here: the first line, cut where it was read
                kept, end = data if place >= 0 or cut < 0 else data[:cut + 1], start
    except OSError:
        pass
    return None


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


def said(one, whole, kind, sub, seen, theme):
    """An agent's sums ONE as the graph says them (SUB: a sub-agent's), beside the conversation's WHOLE; KIND: "API
    value" or "spent"; SEEN the conversation's models in order, THEME a card and its text (the models' colors)."""
    model, cost = one["models"][0], one["cost"]
    share = cost / whole["cost"] if cost is not None and whole["cost"] else \
        one["tokens"] / whole["tokens"] if whole["tokens"] else 1.0
    prompt, written = sum(one[kind] for kind in PROMPT), one["write_5m"] + one["write_1h"]
    text = "no price" if cost is None else money(cost, True)
    turns = "sub-agent" if sub else f"{one['turns']} turn{'s' * (one['turns'] != 1)}"
    lines = [["Model", ", ".join(prices.model_name(each) for each in one["models"]), None],
             ["Input", millions(one["input"]), None],
             ["Cache write", millions(written),
              f"1 hour {millions(one['write_1h'])} · 5 min {millions(one['write_5m'])}" if written else None],
             ["Cache read", millions(one["read"]), f"{percent(one['read'] / prompt)} of its input" if one["read"]
              else None],
             ["Output", millions(one["output"]), None], ["Share", f"{percent(share)} of this conversation", None]]
    return {"cost": cost, "text": text, "title": text if cost is None else f"{text} {kind}",
            "model": {"id": model, "name": prices.model_name(model),
                      "color": prices.model_color(model, seen, *(theme or (None, None)))},
            "turns": one["turns"], "tokens": one["tokens"], "share": share,
            "sub": f"{prices.model_name(model)} · {turns} · {short(one['tokens'])} tokens", "lines": lines}


def costs(state, agent, path, agents=None, table=None, theme=None):
    """What the conversation in AGENT's session file PATH cost, from STATE's index (tokens.index()'s, brought up to
    date by the caller): {"session", "kind", "text", "tokens", "agent": said()'s, "subs": {type: said()'s}}; None with
    no message yet. AGENTS: the agents' list (a plan "API key": spent); TABLE: prices.prices()'s; THEME: said()'s."""
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
    whole = summed(rows, models)
    own = said(summed([row for row in rows if row["sub"] is None], models), whole, kind, False, seen, theme)
    subs = {sub: said(summed([row for row in rows if row["sub"] == sub], models), whole, kind, True, seen, theme)
            for sub in dict.fromkeys(row["sub"] for row in rows if row["sub"] is not None)}
    count = counted(path) if agent == "claude" and whole["cost"] is not None else None
    if count is not None:
        apart = round(count * 100) - round(whole["cost"] * 100)
        note = "the same" if not apart else f"{money(abs(apart) / 100, True)} {'more' if apart > 0 else 'less'}"
        own["lines"].append(["Claude's count", money(count, True), note + ", sub-agents included" * bool(subs)])
    prompt = sum(whole[kind] for kind in PROMPT)
    text = "no price" if whole["cost"] is None else money(whole["cost"], True)
    return {"session": session, "kind": kind, "text": text,
            "tokens": short(whole["tokens"]), "agent": own, "subs": subs,
            "line": f"{short(whole['tokens'])} tokens" + (f" · {percent(whole['read'] / prompt)} from cache"
                                                          if whole["read"] else "")}


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
