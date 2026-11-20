# Generated from core/report.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""What the agents used, for Usage's report in both clients, from tokens.py's index at prices.py's prices: as API
value on a plan (never "spent"), as spent with an API key, by day, model, project and conversation; a month against
its budget (herdr-fold's own BUDGET file), its pace, the chat's notice, the CSV. Usage (in JSON): main()'s."""
import io
import json
import os
import re
import sys
import time
from csv import writer

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import commits  # noqa: E402
import prices  # noqa: E402
import statefile  # noqa: E402
import tokens  # noqa: E402
import usage  # noqa: E402
from prices import money, short  # noqa: E402

PERIODS = {"today": (1, "Today"), "7d": (7, "7 days"), "30d": (30, "30 days"), "month": (0, None)}
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
BUDGET = usage.SETTINGS         # each API-key agent's monthly budget in dollars, and the notices dismissed
LARGEST = 1_000_000             # dollars a month a budget may be: more is a slip of the hand
API_KEY = "API key"             # the agents' list's word for an agent on an API key: its cost is spent
NEAR = 0.8                      # the share of a budget spent from which a chat says so
TITLE = 80                      # characters of a conversation's title kept
MOST = 200                      # conversations listed, the most first
NOTICE = re.compile(r"(claude|codex):\d{4}-(0[1-9]|1[0-2])")           # a notice's key: its agent and month
AMOUNT = re.compile(r"\$?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?")              # a budget as typed: 50, $50, 1,250.50
CHATS = ("herdr", "plugins", "herdr-fold.sidebar", "chat-index.json")  # the chat list's index in the state home
NAMES = ("herdr", "plugins", "herdr-fold.sessions-view", "names.json")  # the names given by hand
HEAD = ("day", "agent", "model", "conversation", "space", "input", "cache_write_5m", "cache_write_1h", "cache_read",
        "output", "reasoning", "searches", "cost", "kind")
COLUMNS = {"conversations": ["Conversation", "Space", "Models", "Turns", "Tokens", "Cache", "Cost", "Commits",
                             "Per commit"],
           "models": ["Model", "Agent", "Input", "Cache write", "Cache read", "Output", "Cost"]}


# --- words

def whole(dollars, about=False):
    """DOLLARS to the nearest one, as a pace and a round budget are said: $46; ABOUT (a pace): ~$46."""
    return f"{prices.ABOUT if about else ''}${int(dollars + 0.5):,}"


def amount(dollars):
    return whole(dollars) if dollars == int(dollars) else money(dollars)


def text(value, limit=TITLE):
    """VALUE as one line of text, LIMIT characters of it: no control character, a new line as a space."""
    value = " ".join(value.split()) if isinstance(value, str) else ""
    return "".join(ch for ch in value if ch.isprintable())[:limit].strip()


# --- days

def midnight(at, days=0, months=0, first=False):
    """This machine's midnight before AT, DAYS days later; FIRST: of its month's first day, MONTHS months later."""
    now = time.localtime(at)
    return int(time.mktime((now.tm_year, now.tm_mon + months, 1 if first else now.tm_mday + days, 0, 0, 0, 0, 0, -1)))


def day(at):
    """AT's day here, as (2026-11-07, Nov 7)."""
    now = time.localtime(at)
    return f"{now.tm_year}-{now.tm_mon:02d}-{now.tm_mday:02d}", f"{MONTHS[now.tm_mon - 1][:3]} {now.tm_mday}"


def bounds(period, now):
    """PERIOD (PERIODS') at NOW as whole days of this machine's, today its last: {"id", "label", "from", "to"} in
    seconds since 1970, "to" not in it. ValueError for another word."""
    if period not in PERIODS:
        raise ValueError(f"not a period: {period!r}")
    days, label = PERIODS[period]
    return {"id": period, "label": label or MONTHS[time.localtime(now).tm_mon - 1],
            "from": midnight(now, 1 - days) if days else midnight(now, first=True), "to": midnight(now, 1)}


def days_of(since, until):
    """Each day's start from SINCE until UNTIL, a 23- or 25-hour one too."""
    found = [since]
    while midnight(found[-1], 1) < until:
        found.append(midnight(found[-1], 1))
    return found


# --- the budget

def kept(state):
    return statefile.read(os.path.join(state, BUDGET))


def sound(dollars):
    return prices.number(dollars) and 0.005 <= dollars <= LARGEST


def budget(state):
    """Each agent's monthly budget in dollars, {agent: dollars}, as kept in STATE; an agent with none is not in it."""
    found = kept(state).get("budgets")
    return {agent: found[agent] for agent in usage.AGENTS if sound(found.get(agent))} if isinstance(found, dict) \
        else {}


def set_budget(state, agent, dollars):
    """AGENT's monthly budget set to DOLLARS (a number, or as typed: 50, $1,250.50), to the cent; None, "" or 0 takes
    it away. The budgets then. ValueError for another agent or what is no amount up to LARGEST."""
    if agent not in usage.AGENTS:
        raise ValueError(f"not an agent: {agent!r}")
    if isinstance(dollars, str) and (not dollars.strip() or AMOUNT.fullmatch(dollars.strip())):
        dollars = float(dollars.strip().lstrip("$").replace(",", "") or 0)
    if dollars is not None and (not prices.number(dollars) or dollars and not sound(dollars)):
        raise ValueError(f"not a budget: {dollars!r}")
    cents = round(dollars, 2) if dollars else None
    cents = int(cents) if cents and cents == int(cents) else cents

    def change(was):
        made = {**budget_of(was), agent: cents}
        return {**was, "budgets": {one: value for one, value in made.items() if value}}
    return statefile.update(os.path.join(state, BUDGET), change)["budgets"]


def budget_of(was):
    found = was.get("budgets")
    return {agent: value for agent, value in found.items() if agent in usage.AGENTS and sound(value)} \
        if isinstance(found, dict) else {}


def dismissed(state):
    """The notices dismissed, by their keys (an agent's newest alone is kept)."""
    found = kept(state).get("dismissed")
    return [key for key in found if isinstance(key, str) and NOTICE.fullmatch(key)] if isinstance(found, list) else []


def dismiss(state, key):
    """The notice KEY (notice()'s: codex:2026-11) dismissed for its month. ValueError for what is no key."""
    if not isinstance(key, str) or not NOTICE.fullmatch(key):
        raise ValueError(f"not a notice: {key!r}")
    agent = key.split(":")[0]
    statefile.update(os.path.join(state, BUDGET), lambda was: {**was, "dismissed": sorted(
        [one for one in dismissed(state) if one.split(":")[0] != agent] + [key])})


def pace(spent, day, days):
    """What a month of DAYS days comes to at SPENT by its DAY-th day (that day counted whole)."""
    return spent / max(day, 1) * days


def notice(month, dismissed, now):
    """The chat's notice for MONTH (report()'s) at NOW, {"key", "agent", "text"}: from NEAR of its budget spent, or
    its pace past it; None for none, for a key among DISMISSED and for a month that is over."""
    if not month or not month.get("budget") or now >= month["to"]:
        return None
    key = f"{month['agent']}:{month['id']}"
    if key in dismissed or month["today"] < NEAR * month["budget"] and month["pace"] <= month["budget"]:
        return None
    return {"key": key, "agent": month["agent"],
            "text": f"{month['name']} has spent {money(month['today'], True)} of {amount(month['budget'])} this "
                    f"month · on pace for {whole(month['pace'], True)} by {month['end']}"}


# --- the report

def signed(agents):
    """AGENTS (the agents' list) as {agent: (its name, its plan's word or None)}; the name its own where not told."""
    told = {one["key"]: one for one in (agents if isinstance(agents, list) else []) if isinstance(one, dict)
            and isinstance(one.get("key"), str)}
    found = {}
    for agent in usage.AGENTS:
        name, plan = told.get(agent, {}).get("name"), told.get(agent, {}).get("plan")
        found[agent] = (text(name) or usage.NAMES[agent],
                        plan if isinstance(plan, str) and usage.PLAN.fullmatch(plan) else None)
    return found


def said_as(agent, told):
    """AGENT with its plan, as a cell's key: Claude · Max plan, Codex · API key, Codex where it is not told."""
    name, plan = told[agent]
    return f"{name} · {plan}" if plan == API_KEY else f"{name} · {plan} plan" if plan else name


def titles(home, chats=None):
    """Each conversation's title by its session, as the chat list has it (its index: a rename, Claude's own title,
    else the first prompt) and a name given by hand over it."""
    state = os.path.join(home, ".local", "state")
    index = statefile.read(chats or os.path.join(state, *CHATS))
    found = {}
    for path, entry in usage.obj(index.get("files")).items():
        entry = usage.obj(entry)
        session = entry.get("id") if "id" in entry else os.path.basename(path)[:-len(".jsonl")]
        title = text(entry.get("custom")) or text(entry.get("ai")) or text(entry.get("prompt"))
        if isinstance(session, str) and title and not entry.get("helper"):
            found[session] = title
    for session, entry in statefile.read(os.path.join(state, *NAMES)).items():
        if isinstance(entry, dict) and not entry.get("given") and text(entry.get("name")):
            found[session] = text(entry["name"])
    return found


def summed(rows):
    """ROWS' sums: each kind of token, the messages, "tokens" (all of them), "cache" (the percent of the prompt read
    from the cache, None with no prompt), "cost" (None where no row has a price) and "unpriced" (a row has none)."""
    found = {kind: sum(row[kind] for row in rows) for kind in tokens.KINDS + ("messages",)}
    prompt = found["input"] + found["write_5m"] + found["write_1h"] + found["read"]
    costs = [row["cost"] for row in rows if row["cost"] is not None]
    return {**found, "tokens": prompt + found["output"], "cache": round(100 * found["read"] / prompt) if prompt
            else None, "cost": sum(costs) if costs else None, "unpriced": len(costs) < len(rows)}


def grouped(rows, key):
    found = {}
    for row in rows:
        found.setdefault(key(row), []).append(row)
    return found


def most_first(groups):
    """GROUPS ({key: rows}) as [(key, rows, sums)], the costliest first, then the one with the most tokens."""
    found = [(key, rows, summed(rows)) for key, rows in groups.items()]
    return sorted(found, key=lambda one: (-(one[2]["cost"] or 0), one[2]["cost"] is None, -one[2]["tokens"],
                                          str(one[0])))


def within(path, folder):
    return folder is None or path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def read(state, until, table, told, theme):
    """Every row of the index in STATE before UNTIL with its cost at TABLE, its model's name and color (on THEME's
    card), its day here and whether its agent's cost is value or spent."""
    rows = sorted(tokens.rows(tokens.load(state), 0, until), key=lambda row: (row["hour"], row["model"]))
    seen, days = list(dict.fromkeys(row["model"] for row in rows)), {}
    colors = {model: prices.model_color(model, seen, *(theme or (None, None))) for model in seen}
    for row in rows:
        if row["hour"] not in days:
            days[row["hour"]] = day(row["hour"])[0]
        row.update(cost=prices.cost(row, prices.price_of(row["model"], table["models"])), day=days[row["hour"]],
                   name=prices.model_name(row["model"]) or row["model"], color=colors[row["model"]],
                   kind="spent" if told.get(row["agent"], ("", None))[1] == API_KEY else "value")
    return rows


def month_of(agent, rows, told, budgets, now):
    """AGENT's calendar month at NOW from its ROWS, against its budget: what was spent by each day's end, today's
    sum, the pace it is on, its words (a line, and its parts for both clients) and its level (yellow once over)."""
    since, until = midnight(now, first=True), midnight(now, months=1, first=True)
    starts = [start for start in days_of(since, until)]
    by_day = grouped([row for row in rows if row["cost"] is not None], lambda row: row["day"])
    spent, sum_ = [], 0
    for n, start in enumerate(start for start in starts if start <= now):
        sum_ += sum(row["cost"] for row in by_day.get(day(start)[0], []))
        spent.append([n + 1, sum_])
    limit, on = budgets.get(agent), pace(sum_, len(spent), len(starts))
    top, over = most_first(grouped(rows, lambda row: row["model"])), bool(limit) and max(on, sum_) > limit
    words = {"spent": money(sum_, True), "of": f"of {amount(limit)}" if limit else "",
             "pace": f"on pace for {whole(on, True)}"}
    return {"agent": agent, "name": told[agent][0], "key": said_as(agent, told), "id": day(since)[0][:7],
            "label": MONTHS[time.localtime(since).tm_mon - 1], "budget": limit, "days": len(starts),
            "day": len(spent), "spent": spent, "today": sum_, "pace": on, "over": over,
            "line": f"{words['spent']} {words['of']} · {words['pace']}" if limit
            else f"{words['spent']} · {words['pace']}",
            "words": words, "level": ("warn" if over else "ok") if limit else None,
            "end": day(until - 43200)[1], "from": since, "to": until, "color": top[0][1][0]["color"] if top else None}


def months_of(rows, told, budgets, now):
    """The month of each agent on an API key among ROWS' (every folder's: a budget is the agent's)."""
    since = midnight(now, first=True)
    mine = grouped([row for row in rows if row["hour"] >= since and row["kind"] == "spent"], lambda row: row["agent"])
    return [month_of(agent, mine[agent], told, budgets, now) for agent in usage.AGENTS if agent in mine]


def cells(rows, told, months, week):
    """The summary row's cells for ROWS: each agent's cost with its plan's or its month's line, then the tokens."""
    found = []
    for agent, mine in grouped(sorted(rows, key=lambda row: usage.AGENTS.index(row["agent"])),
                               lambda row: row["agent"]).items():
        sums, month = summed(mine), next((one for one in months if one["agent"] == agent), None)
        line = f"{month['label']} {month['line']}" if month else ""
        if told[agent][1] and not month:
            line = "no charge on the plan" + (f" · week {week[agent]}% of its limit" if agent in week else "")
        found.append({"key": said_as(agent, told), "agent": agent, "value": sums["cost"],
                      "text": "no price" if sums["cost"] is None else money(sums["cost"], True),
                      "unit": "spent" if mine[0]["kind"] == "spent" else "API value", "line": line,
                      "over": bool(month and month["over"])})
    sums = summed(rows)
    return found + [{"key": "Tokens", "value": sums["tokens"], "text": short(sums["tokens"]),
                     "line": f"{sums['cache']}% read from cache" if sums["cache"] is not None else ""}]


def daily(rows, span):
    """ROWS by day and model for the chart: each day of SPAN with its models' costs in the legend's order, the legend
    (the costliest model first, its share of the whole) and the day that cost the most."""
    known = [row for row in rows if row["cost"] is not None]
    legend = [(name, mine[0], sums["cost"]) for name, mine, sums in most_first(grouped(known, lambda row: row["name"]))]
    whole_, by_day, found = sum(cost for _, _, cost in legend), grouped(known, lambda row: row["day"]), []
    for start in days_of(span["from"], span["to"]):
        iso, label = day(start)
        costs = {name: sum(row["cost"] for row in mine)
                 for name, mine in grouped(by_day.get(iso, []), lambda row: row["name"]).items()}
        found.append({"day": iso, "label": label, "total": sum(costs.values()) if costs else 0,
                      "models": [{"model": first["model"], "name": name, "color": first["color"], "cost": costs[name]}
                                 for name, first, _ in legend if name in costs]})
    top = max(found, key=lambda one: one["total"])
    return found, [{"model": first["model"], "name": name, "color": first["color"], "cost": cost,
                    "share": round(100 * cost / whole_) if whole_ else 0} for name, first, cost in legend], \
        {key: top[key] for key in ("day", "label", "total")} if top["total"] else None


def counted(found):
    """FOUND (several conversations' commits, None for the ones not known) as a figure: the commits, each once, and
    its words: 2, about 2 (some only followed an edit), none yet, – (not known)."""
    known = {one["sha"]: one for mine in found if mine is not None for one in mine}
    if all(mine is None for mine in found):
        return {"commits": None, "about": False, "commits_text": "–"}
    about = any(one["how"] == "after" for one in known.values())
    return {"commits": len(known), "about": about,
            "commits_text": f"{'about ' if about else ''}{len(known)}" if known else "none yet"}


def conversation(key, rows, sums, named, made):
    """One conversation's row: its title, space, models (the costliest first), turns (its own agent's answers),
    tokens, the percent read from the cache, its cost and what a turn cost; its commits (MADE), their lines and
    what one cost."""
    kinds = [sum(one["how"] == how for one in made or ()) for how in ("made", "after")]
    added, removed = (sum(one[key] for one in made) for key in ("added", "removed")) if made is not None \
        else (None, None)
    own = sum(row["messages"] for row in rows if not row["sub"]) or sums["messages"]
    subs = sorted({row["sub"] for row in rows if row["sub"]})
    models = [{"name": name, "color": mine[0]["color"]}
              for name, mine, _ in most_first(grouped(rows, lambda row: row["name"]))]
    per_turn = sums["cost"] / own if sums["cost"] is not None and own else None
    tip = [f"{money(per_turn)} a turn"] if per_turn is not None else []
    return {"session": key[1], "agent": key[0], "folder": rows[0]["folder"],
            "title": named.get(key[1]) or (text(subs[0]) if subs and len(subs) == len({row["sub"] for row in rows})
                                           else "") or "Untitled",
            "space": text(os.path.basename(rows[0]["folder"].rstrip(os.sep))), "models": models, "turns": own,
            "tokens": sums["tokens"], "cache": sums["cache"], "cost": sums["cost"], "kind": rows[0]["kind"],
            "unpriced": sums["unpriced"], "per_turn": per_turn,
            "tip": " · ".join(tip + ([f"{sums['cache']}% read from cache"] if sums["cache"] is not None else [])),
            **counted([made]), "added": added, "removed": removed, "changed": f"+{added} −{removed}" if made else "",
            "per_commit": sums["cost"] / len(made) if made and sums["cost"] is not None else None,
            "commits_tip": f"{kinds[0]} made in the conversation · {kinds[1]} after its edits" if kinds[1] else ""}


def model(key, rows, sums, told):
    return {"model": rows[0]["model"], "name": key[0], "color": rows[0]["color"], "agent": key[1],
            "input": sums["input"], "write": sums["write_5m"] + sums["write_1h"], "write_5m": sums["write_5m"],
            "write_1h": sums["write_1h"], "read": sums["read"], "output": sums["output"],
            "reasoning": sums["reasoning"], "cost": sums["cost"], "kind": rows[0]["kind"],
            "text": "no price" if sums["cost"] is None else money(sums["cost"])}


def label_of(row, told):
    """ROW's agent as the Models table names it: Claude's sub-agents apart."""
    return told[row["agent"]][0] + (" · sub-agents" if row["agent"] == "claude" and row["sub"] else "")


def gathered(state, period, agent, folder, now, agents, table, theme):
    """What report() and csv() both start from: the period, the agents' words, the prices, every agent's rows this
    month and before (AGENT's alone), and the period's in FOLDER."""
    if agent is not None and agent not in usage.AGENTS:
        raise ValueError(f"not an agent: {agent!r}")
    now = int(time.time() if now is None else now)
    span, told = bounds(period, now), signed(agents)
    table = table or prices.prices(state, now)
    rows = [row for row in read(state, span["to"], table, told, theme) if agent in (None, row["agent"])]
    return now, span, told, table, rows, [row for row in rows if row["hour"] >= span["from"]
                                          and within(row["folder"], folder)]


def report(state, home, period, agent=None, folder=None, now=None, agents=None, table=None, theme=None, chats=None):
    """Usage's report for PERIOD (PERIODS') at NOW, AGENT's and FOLDER's alone where given: the summary row, each day
    by model, each API-key agent's month, the projects, conversations, models, and both clients' words. AGENTS: the
    agents' list (its plans); THEME: (card, text) to lift the colors on. ValueError for another period or agent."""
    now, span, told, table, rows, inside = gathered(state, period, agent, folder, now, agents, table, theme)
    months = months_of(rows, told, budget(state), now)
    week = {one["agent"]: one["week"]["used"] for one in usage.limits(home, now) if one["week"]}
    days, legend, top = daily(inside, span)
    named, by_talk = titles(home, chats), grouped(inside, lambda row: (row["agent"], row["session"]))
    index = commits.load(state)
    lines = dict(index["lines"])
    known = commits.found(commits.sessions(index), {session: mine[0]["folder"] for (
        one, session), mine in by_talk.items() if one == "claude"}, span["from"], span["to"], lines)
    if len(lines) > len(index["lines"]):
        commits.keep_lines(state, lines)
    made = {key: known.get(key[1]) if key[0] == "claude" else None for key in by_talk}
    talks = [conversation(key, mine, sums, named, made[key]) for key, mine, sums in most_first(by_talk)]
    whole_, cost = counted(list(made.values())), summed(inside)["cost"]
    as_of = time.strptime(table["as_of"], "%Y-%m-%d")
    as_of = f"{MONTHS[as_of.tm_mon - 1][:3]} {as_of.tm_mday}, {as_of.tm_year}"
    said = span["label"] if period == "month" else span["label"].lower()
    month, kinds = MONTHS[time.localtime(now).tm_mon - 1], {row["kind"] for row in inside}
    both = "value and spent together" if len(kinds) > 1 else "spent" if kinds == {"spent"} else "API value"
    return {
        "period": span, "prices_as_of": as_of,
        "filters": {"periods": [{"id": id, "label": label or month} for id, (_, label) in PERIODS.items()],
                    "agents": [{"id": None, "label": "All agents"}]
                    + [{"id": one, "label": told[one][0]} for one in usage.AGENTS], "spaces": "All spaces"},
        "summary": cells(inside, told, months, week) + [{
            "key": "Commits from these conversations", "value": whole_["commits"], "text": whole_["commits_text"],
            "about": whole_["about"], "line": f"{money(cost / whole_['commits'], True)} each, "
            f"{'spent' if kinds == {'spent'} else 'API value'}" if whole_["commits"] and cost is not None else ""}],
        "none": None if inside else "Nothing used in this period",
        "daily": days, "legend": legend, "top": top, "month": months[0] if months else None, "months": months,
        "projects": [{"folder": key, "name": text(os.path.basename(key.rstrip(os.sep))) or key, "cost": sums["cost"],
                      "tokens": sums["tokens"], **counted([made[row["agent"], row["session"]] for row in mine])}
                     for key, mine, sums in most_first(grouped(inside, lambda row: row["folder"]))],
        "conversations": talks[:MOST], "more": max(0, len(talks) - MOST),
        "models": [model(key, mine, sums, told) for key, mine, sums in most_first(grouped(
            inside, lambda row: (row["name"], label_of(row, told))))],
        "columns": COLUMNS, "csv_name": f"herdr-fold usage {day(span['from'])[0]} to {day(span['to'] - 43200)[0]}.csv",
        "words": {"daily": "Per day, by model", "month": f"{month}, against its budget", "projects": "By project",
                  "projects_note": f"{both} · {said}", "conversations": "Conversations",
                  "conversations_note": f"the most first · {said}", "models": "Models",
                  "models_note": "each message at its own model's prices", "budget": "Budget…",
                  "export": "Export CSV", "none_yet": "none yet", "no_price": "no price",
                  "foot": f"Costs are estimates from the conversations' token counts at list prices (LiteLLM's "
                          f"model cost map, as of {as_of}), not the provider's invoice · a model with no price shows "
                          "its tokens alone"}}


def notices(state, now=None, agents=None, table=None):
    """The chats' notices now: each API-key agent's whose month asks for one and is not dismissed."""
    now, _, told, _, rows, _ = gathered(state, "today", None, None, now, agents, table, None)
    found = (notice(month, dismissed(state), now) for month in months_of(rows, told, budget(state), now))
    return [one for one in found if one]


def csv(state, home, period, agent=None, folder=None, now=None, agents=None, table=None, chats=None):
    """PERIOD's usage as CSV (HEAD's columns): a row for each day, agent, model and conversation, its tokens by kind,
    its cost in dollars (empty with no price) and whether that is value or spent. A title that would start a
    formula in a spreadsheet is written after an apostrophe."""
    _, _, told, _, _, inside = gathered(state, period, agent, folder, now, agents, table, None)
    named, out = titles(home, chats), io.StringIO()
    lines = writer(out)
    lines.writerow(HEAD)
    found = []
    for (iso, agent, name, session), mine in grouped(
            inside, lambda row: (row["day"], row["agent"], row["name"], row["session"])).items():
        sums, title = summed(mine), named.get(session) or "Untitled"
        found.append([iso, told[agent][0], name, "'" + title if title[0] in "=+-@" else title,
                      text(os.path.basename(mine[0]["folder"].rstrip(os.sep))), sums["input"], sums["write_5m"],
                      sums["write_1h"], sums["read"], sums["output"], sums["reasoning"], sums["searches"],
                      "" if sums["cost"] is None else f"{sums['cost']:.6f}", mine[0]["kind"]])
    lines.writerows(sorted(found, key=lambda row: [str(cell) for cell in row[:4]]))
    return out.getvalue()


def main(argv):
    """herdr-fold's Herdr app mod runs this, answering in JSON: report PERIOD [AGENT] [FOLDER] (--agents=JSON the
    agents' list, --surface=#hex --text=#hex the theme's card and text); budget [AGENT DOLLARS]; notice
    [--agents=JSON]; dismiss KEY; csv PERIOD [AGENT] [FOLDER] (as text)."""
    options = dict(arg[2:].split("=", 1) for arg in argv[2:] if arg.startswith("--") and "=" in arg)
    command, args = argv[1] if len(argv) > 1 else "", [arg for arg in argv[2:] if not arg.startswith("--")]
    state, home = statefile.folder(), os.path.expanduser("~")
    try:
        agents = json.loads(options["agents"]) if "agents" in options else None
        asked = {"agent": args[1] if len(args) > 1 and args[1] else None,
                 "folder": args[2] if len(args) > 2 and args[2] else None, "agents": agents}
        if command == "report" and 1 <= len(args) <= 3:
            theme = (options.get("surface"), options.get("text"))
            print(json.dumps(report(state, home, args[0], theme=theme, **asked)))
        elif command == "csv" and 1 <= len(args) <= 3:
            sys.stdout.write(csv(state, home, args[0], **asked))
        elif command == "budget" and len(args) in (0, 2):
            print(json.dumps(set_budget(state, *args) if args else budget(state)))
        elif command == "notice" and not args:
            print(json.dumps({"notices": notices(state, agents=agents)}))
        elif command == "dismiss" and len(args) == 1:
            dismiss(state, args[0])
            print(json.dumps({"ok": True}))
        else:
            raise ValueError("unknown command")
    except (ValueError, RecursionError):
        print("usage: report.py report PERIOD [AGENT] [FOLDER] [--agents=JSON] [--surface=#hex --text=#hex] | "
              "budget [AGENT DOLLARS] | notice [--agents=JSON] | dismiss KEY | csv PERIOD [AGENT] [FOLDER]",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
