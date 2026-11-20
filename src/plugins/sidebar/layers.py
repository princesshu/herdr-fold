"""The sidebar's Agent view: what an agent starts with in the folder, in core's words (agent_setup.py's layers(),
usage.py's section(), report.py's costs), in cells as the mockups' TUI panes: the head and its agents' list, Usage,
the sections, the chosen row's properties, a connector's form; and the graph as a tree (graph.py's). It only asks."""
import time

import report as told
import widgets
from connectors import BRANDS
from icons import glyphs
from prices import money
from screen import INSET, SPINNER, Style, after, truncate, width
from vt import Key, Mouse
from widgets import MENU_WIDEST, Action, Menu, Popup, TextInput, wrap

FOLDED = ("rules", "permissions", "skills", "agents")    # folded till opened: Connectors, the problems' home, open
FIRST = 5                     # rows a section shows before "N more": its problems and used ones always
TAG = 12                      # cells a tag takes at most (a plugin's name may be long)
NAME_LEAST = 8                # cells a section's names keep at least: below that its tags go, its states stay
TEXT_ROWS, ERROR_ROWS = 3, 2  # rows of a chosen row's text (a rule's first lines) and of its error
# the actions core offers, and a sign-in's own (core's connecting()); Claude's own commands on Claude's rows alone
WORKS = ("open", "retry", "connect", "turn-off", "turn-on", "sign-out", "reopen", "cancel")
CLAUDES = ("retry", "turn-off", "turn-on")
OWN_WORDS = {"turn-off": "Turn off here", "turn-on": "Turn on here"}     # the TUI's, as connectors.html's TUI pane
# Claude's /mcp command is typed into the tab's Claude: with none there, the button says what it waits for
NEEDS = {"turn-off": "Start Claude in this tab to turn it off here", "turn-on": "Start Claude in this tab to turn it "
         "on here"}
ASKS = {"retry": "retry_server", "connect": "connect_server", "sign-out": "sign_out_server",
        "reopen": "reopen_sign_in", "cancel": "cancel_sign_in"}          # what an action asks the family for
WAYS = {"claude-ai": "Add from claude.ai", "url": "Add by URL"}          # More's lines, as connectors.html's ⋯ menu
REFRESH = "Refresh"
ADD_KEY = "a"                 # the form from the keys (More's "Add by URL")
CONNECTORS = "connectors"     # the section a connector is added in
BRAND = 2                     # cells a connector's brand takes before its name: its glyph or letter, and a space
# a state's tone as a mark (a connector's, a conflict's) and as the color of its word; a tag's tone as its color
MARKS = {"bad": ("✕", "deleted"), "warn": ("●", "modified"), "ok": ("●", "added"), "busy": ("◐", "accent"),
         "off": ("○", "muted")}
USED = MARKS["ok"]            # what the open conversation used (a skill, a sub-agent, a connector): the app's green dot
STATE_ROLE = {"bad": "deleted", "warn": "modified", "ok": "subtext", "busy": "accent", "off": "muted",
              "allow": "added", "ask": "modified", "deny": "deleted"}
TAG_ROLE = {"personal": "accent", "project": "done", "plugin": "conflict", "account": "account", "muted": "muted"}
USAGE = "usage"               # Usage's id among the sections folded and opened: the first one, core's own rows
FOLDS = ("▸", "▾")            # an agent's block in Usage folded and open, as usage-agents.html's TUI pane
BAR = 7                       # cells of a limit's bar, as usage.html's TUI pane
LEVEL_ROLE = {"ok": "added", "warn": "modified", "bad": "deleted"}      # a percent's level, the status line's colors
RANK = {"ok": 1, "warn": 2, "bad": 3}  # how near its end a level stands: another agent's yellow or red one is told
PERIODS = ("7d", "30d", "month")       # what Usage's head steps through: core's periods but today
PERIOD_KEY = "p"              # the next period from the keys
OPEN_USAGE = "Open Usage"     # the Usage head's own line in its right-click menu, as the Herdr app's
PER_DAY = "per day"
SPARK = " ▁▂▃▄▅▆▇█"           # a day's cost in eighths of the costliest day's
PROJECTS = 5                  # projects Usage lists, the costliest first: all of them are the Usage view's
PROJECT, COST = 16, 10        # cells a project's name keeps before its commits go, and a cost's column (~$1,234.56)
READING = "Reading the conversations…"
SHOW_GRAPH, GRAPH_KEY = "Show graph", "g"     # the head's own line in its right-click menu, and its key
ROOT = "agent"                # the agent's own node in core's graph (graph.py's AGENT)
BRANCHES = (("in", lambda node: node["column"] == "in"), ("uses", lambda node: node["column"] == "uses"),
            ("sub-agents", lambda node: node["parent"] == ROOT))        # the tree's branches, agent-chat-design's
TITLE, TAGGED = 28, 18        # cells a node's name and its tag keep in the tree's columns
TREE = 80                     # cells the path that ran is wrapped at: a preview tab's lines are not
LOADING = "Loading setup…"
LOADING_AGENTS = "Loading agents…"
SERVER = "connector:"         # a server's row id: this, then its name (what Claude checks again)
HEAD = ("head", None)         # the head's item: Enter opens the agents' list
AGENTS, ADD = "Agents on this Mac", "Add an agent"       # the lists' heads, as connectors.html's
ADD_LINE = "Add an agent…"
NONE_TO_ADD = "Every agent herdr-fold knows is installed"
OFFER_WORDS = {"page": "Open its page ↗"}                # the TUI's, as the plan's; else core's


def agent_choices(agents, current):
    """The agents' list's lines: AGENTS (core's, each with its standing) installed, in its order, a check on the
    CURRENT one, at the right its plan's word, or sign in where it must; then Add an agent…. None told: none."""
    found = [{"kind": "agent", "key": one["key"], "name": one["name"], "check": one["key"] == current,
              "right": "sign in" if one["signed_in"] is False else one["plan"] or "",
              "role": "modified" if one["signed_in"] is False else "muted"}
             for one in agents or () if one["installed"]]
    return found + [{"kind": "add", "name": ADD_LINE, "right": "", "role": "muted"}] if agents else []


def add_choices(agents):
    """Add an agent…'s lines: AGENTS not installed, in core's order."""
    return [{"kind": "install", "key": one["key"], "name": one["name"], "right": "", "role": "muted"}
            for one in agents or () if not one["installed"]]


class AgentMenu(Menu):
    """The agents' list as connectors.html's TUI pane: its TITLE dim, then a choice a row: a ✓ (CHECK, the glyph) on
    the one in use, its name, a word at the right in its color; with no choice, NOTE in their place."""

    def __init__(self, title, choices, check, note=""):
        super().__init__(choices)
        self.title, self.check, self.note = title, check, note

    def width(self):
        rows = [2 + width(one["name"]) + (2 + width(one["right"]) if one["right"] else 0) for one in self.choices]
        return max(MENU_WIDEST, max(rows + [width(self.title), width(self.note)]) + 4)

    def height(self):
        return max(1, len(self.choices)) + 3

    def handle(self, key):
        if not self.choices:
            return "cancel" if key.name in ("enter", "esc") else None
        return super().handle(key)

    def draw(self, canvas, y, x, cells):
        frame, inner = Style(fg="accent", bg="panel"), cells - 2
        canvas.put(y, x, "┌" + "─" * inner + "┐", frame)
        lines = [(None, self.title)] + ([(n, one) for n, one in enumerate(self.choices)] or [(None, self.note)])
        for row, (n, one) in enumerate(lines, 1):
            canvas.put(y + row, x, "│" + " " * inner + "│", frame)
            if n is None:
                canvas.put(y + row, x + 2, truncate(one, inner - 2), Style(fg="muted", bg="panel"))
                continue
            lit = n == self.index
            bg = "button" if lit else "hover" if n == self.hover else "panel"
            words = Style(fg="button_text", bg=bg, bold=True) if lit else Style(fg="text", bg=bg)
            canvas.put(y + row, x + 1, " " * inner, words)
            if one.get("check"):
                canvas.put(y + row, x + 2, self.check, words if lit else Style(fg="accent", bg=bg))
            right = truncate(one["right"], max(0, inner - 6))
            room = inner - 5 - (width(right) + 1 if right else 0)
            name = Style(fg="muted", bg=bg) if one["kind"] == "add" and not lit else words
            canvas.put(y + row, x + 4, truncate(one["name"], max(1, room)), name)
            if right:
                canvas.put(y + row, x + cells - 2 - width(right), right,
                           words if lit else Style(fg=one["role"], bg=bg))
            canvas.region(y + row, x + 1, x + cells - 1, f"menu:{n}")
        canvas.put(y + len(lines) + 1, x, "└" + "─" * inner + "┘", frame)
        return self.height()


def bar(used):
    """A limit's bar, BAR cells filled by USED percent: never empty with some used, full only with all of it."""
    filled = BAR if used >= 100 else min(BAR - 1, max(1 if used > 0 else 0, round(used * BAR / 100)))
    return "▰" * filled + "▱" * (BAR - filled)


def period_said(period, now=None):
    """PERIOD's words on Usage's head and the Usage view's chip: core's 7 days and 30 days, the month as Nov."""
    return told.PERIODS[period][1] or told.MONTHS[time.localtime(now).tm_mon - 1][:3]


def commits_said(one):
    """ONE's commits (a project's, a conversation's: core's counted()) in words: 5 commits, about 2 commits, 1 commit,
    none yet, – where they are not known."""
    count = one.get("commits")
    return f"{one['commits_text']} commit{'s' * (count != 1)}" if count else one["commits_text"]


def days_said(daily):
    """The days DAILY (the report's) spans: Nov 3 – 9, Oct 28 – Nov 3, Nov 9 for one."""
    first, last = daily[0]["label"], daily[-1]["label"]
    if first == last:
        return first
    return f"{first} – {last.split()[-1] if first.split()[0] == last.split()[0] else last}"


def day_color(day):
    """The color of the model DAY cost the most in, None for a day with no cost."""
    return max(day["models"], key=lambda one: one["cost"])["color"] if day["models"] else None


def spark(daily, cells):
    """DAILY's last CELLS days as [(eighth block, its color)]: each day's cost by the costliest day's, a day with any
    cost never empty, in the color of the model it cost the most in."""
    days = daily[-max(1, cells):]
    top = max([day["total"] for day in days] + [0])
    return [(SPARK[max(1, round(8 * day["total"] / top))] if day["total"] > 0 else SPARK[0], day_color(day))
            for day in days]


def agent_costs(report):
    """What each agent cost in REPORT, as Usage's lines say it: {agent: {"figure", "unit", "of", "level", "used",
    "month"}}: on a plan the period's API value; on an API key core's words for its month's spent, its budget, its
    level and share, and the month's line (its share, its pace, whether over). One with no price to tell: none."""
    found = {}
    for cell in report["summary"]:
        agent = cell.get("agent")
        month = next((one for one in report["months"] if one["agent"] == agent), None)
        if agent is None or not month and cell["value"] is None:
            continue
        if not month:
            found[agent] = {"figure": cell["text"], "unit": cell["unit"], "of": "", "level": None, "used": None,
                            "month": None}
            continue
        words, used = month["words"], 100 * month["today"] / month["budget"] if month["budget"] else None
        found[agent] = {"figure": words["spent"], "unit": words["of"] or "spent", "of": words["of"],
                        "level": month["level"], "used": used,
                        "month": {"label": month["label"][:3], "used": used, "pace": words["pace"],
                                  "over": month["over"]}}
    return found


def cost_rows(rows, report, agents, current=None):
    """Usage's ROWS (core's section()) each with what its agent cost (agent_costs()), and a row for each agent that
    cost something and has no limits (one on an API key), named as AGENTS tell it: after them, or the CURRENT first."""
    costs = agent_costs(report)
    found = [{**row, "cost": costs.get(row["key"])} for row in rows]
    known = {one["key"]: one for one in agents or ()}
    for key in (key for key in costs if not any(row["key"] == key for row in rows)):
        one = known.get(key, {})
        made = {"key": key, "name": one.get("name") or key.capitalize(), "plan": one.get("plan"), "five": None,
                "week": None, "tight": None, "resets": None, "age": None, "current": key == current,
                "cost": costs[key]}
        found.insert(0 if key == current else len(found), made)
    return found


def figures(row, short=False):
    """ROW's figures at its folded line's end, [(words, role)]: on a plan both windows ("5h 72%  wk 16%"; SHORT: the
    tighter alone), on an API key its month's spent of its budget (SHORT: the spent), else what it cost; [] for none.
    A figure wears its level's color, the only sign."""
    found = []
    windows = [row["tight"]] if short and row.get("tight") else [one for one in (row["five"], row["week"]) if one]
    for one in windows:
        found += [("  ", "muted")] * bool(found)
        found += [(f"{one['label']} ", "muted"), (one["text"], LEVEL_ROLE[one["level"]])]
    cost = row.get("cost")
    if found or not cost:
        return found
    word = "" if short else cost["of"] if cost["month"] else cost["unit"]
    return [(cost["figure"], LEVEL_ROLE.get(cost["level"], "text"))] + ([(f" {word}", "muted")] if word else [])


def tightest(row):
    """ROW's one figure for Usage's head folded: a plan's tighter window, an API key's month of its budget."""
    return figures(row, short=True) if row.get("tight") else figures(row)


def standing(row):
    """How near its end ROW stands, to compare: its tighter window's or its month's level, then the share used."""
    if row.get("tight"):
        return RANK[row["tight"]["level"]], row["tight"]["used"]
    cost = row.get("cost") or {}
    return RANK.get(cost.get("level"), 0), cost.get("used") or 0


def headline(rows, current):
    """The row whose figure Usage's head shows folded: the CURRENT agent's, or another's that is yellow or red and
    stands worse; None with neither."""
    mine = next((row for row in rows if row["key"] == current and tightest(row)), None)
    worst = max((row for row in rows if row is not mine and standing(row)[0] >= RANK["warn"]), key=standing,
                default=None)
    return worst if worst and (mine is None or standing(worst) > standing(mine)) else mine


def gates_said(edge):
    """EDGE's gates in brackets, as the tree says them: [ask · pytest allowed, deny git push]; "" with none."""
    return f"[{', '.join(one['text'] for one in edge['gates'])}]" if edge and edge["gates"] else ""


def tree_rows(graph, run=False, twelve=False, cells=TREE):
    """Core's GRAPH (graph.py's) as a tree's rows, each [(words, role)], role None, "bold", "dim", "bad", "warn" or
    "accent": the agent with its line and chips, then what goes in, what it uses (each edge's gates in brackets) and
    its sub-agents; RUN: what the conversation ran instead (ran_rows()). TWELVE: hours with AM and PM."""
    if run:
        return ran_rows(graph, twelve, cells)
    agent = next(node for node in graph["nodes"] if node["id"] == ROOT)
    edges = {(one["from"], one["to"]): one for one in graph["edges"]}
    rows = [[(agent["title"], "bold")] + [(f"  {agent['sub']}", "dim")] * bool(agent["sub"])
            + [(f"  [{chip}]", None) for chip in agent["chips"]]]
    branches = [(name, [node for node in graph["nodes"] if mine(node)]) for name, mine in BRANCHES]
    branches = [(name, nodes) for name, nodes in branches if nodes]
    for n, (name, nodes) in enumerate(branches):
        last = n == len(branches) - 1
        rows.append([("└ " if last else "├ ", "dim"), (name, "dim")])
        title = min(TITLE, max(width(node["title"]) for node in nodes))
        tagged = min(TAGGED, max(width((node["tag"] or {}).get("text", "")) for node in nodes))
        for at, node in enumerate(nodes):
            tone = "dim" if node["dim"] else {"bad": "bad", "warn": "warn"}.get(node["state"])
            tag = truncate((node["tag"] or {}).get("text", ""), tagged)
            gate = gates_said(edges.get((ROOT, node["id"])) or edges.get((node["id"], ROOT)))
            name_ = truncate(node["title"], title)
            row = [(("  " if last else "│ ") + ("└ " if at == len(nodes) - 1 else "├ "), "dim"),
                   (name_ + " " * (title - width(name_) + 2), "dim" if node["dim"] else None)]
            row += [(tag + " " * (tagged - width(tag) + 2), "dim")] if tagged else []
            row += [(node["sub"] or "", tone or "dim")] + [(f"  {gate}", None)] * bool(gate)
            rows.append(row)
    return rows


def clock_said(seconds, twelve):
    """SECONDS since 1970 as this machine's time of day, 1:36 PM or 13:36 (TWELVE: with AM and PM); "" for none."""
    if not seconds:
        return ""
    at = time.localtime(seconds)
    return f"{at.tm_hour % 12 or 12}:{at.tm_min:02d} {'AM' if at.tm_hour < 12 else 'PM'}" if twelve \
        else f"{at.tm_hour:02d}:{at.tm_min:02d}"


def ran_rows(graph, twelve, cells):
    """What the conversation ran (tree_rows()'s rows): the agent, the numbered path in order of first use, wrapped at
    CELLS; each agent that ran with its properties as aligned label and value rows; each tool's calls in a column."""
    nodes = {node["id"]: node for node in graph["nodes"]}
    agent = nodes[ROOT]
    rows = [[(agent["title"], "bold")] + [(f"  {(agent['run'] or {}).get('sub') or ''}".rstrip(), "dim")]]
    line, used = [], 0
    for n, key in enumerate(graph["path"], 1):
        title = nodes[key]["title"]
        size = width(str(n)) + 1 + width(title)
        if line and used + 3 + size > cells:            # the next line, two cells in
            rows.append(line + [(" →", "dim")])
            line, used = [("  ", None)], 2
        elif line:
            line.append((" → ", "dim"))
            used += 3
        line += [(str(n), "accent"), (f" {title}", None)]
        used += size
    rows += [line] if line else []
    for node in (node for node in graph["nodes"] if node["kind"] in ("agent", "sub") and node["run"]["ran"]):
        shown = node["run"]["properties"]
        if not shown:
            continue
        said = clock_said(node["run"]["started"], twelve)
        lines = [["Cost", shown["state"]["text"], None]] * bool(shown.get("state")) + shown["lines"]
        label = max([width(one[0]) for one in lines] or [0])
        rows += [[], [(node["title"], "bold")] + [(f"  {node['run']['sub']}", "dim")] * (node is not agent
                                                                                    and bool(node["run"]["sub"]))]
        for name, words, note in lines:                 # a value's note right after it, dim, as the Herdr app's
            rows.append([(f"  {name}" + " " * (label - width(name) + 2), "dim"), (words.replace("{time}", said), None)]
                        + [(f"  {note}", "dim")] * bool(note))
    called = [node for node in graph["nodes"] if node["kind"] in ("tool", "connector") and node["run"]["calls"]]
    if called:
        title = max(width(node["title"]) for node in called)
        calls = max(width(node["run"]["calls"]) for node in called)
        rows += [[], [("uses", "dim")]]
        rows += [[(f"  {node['title']}" + " " * (title - width(node["title"]) + 2), None),
                  (node["run"]["calls"].rjust(calls), "dim")] for node in called]
    return rows


def tree(graph, run=False, twelve=False, cells=TREE):
    """Core's GRAPH as a tree's lines of text (tree_rows()'s, their roles left out)."""
    return ["".join(words for words, _ in row).rstrip() for row in tree_rows(graph, run, twelve, cells)]


def problem(row):
    """Whether ROW is a problem: failed, to sign in, a conflict."""
    return row["warn"] or (row["state"] or {}).get("tone") in ("bad", "warn")


def doable(row, agent="claude"):
    """ROW's actions this client can do, Claude's own commands only for AGENT Claude."""
    return [one for one in row["properties"]["actions"] if one["id"] in WORKS
            and (agent == "claude" or one["id"] not in CLAUDES)]


def server_of(key):
    """The server a row's item KEY stands for, or None: a connector's row alone has one."""
    return key[1][len(SERVER):] if key and key[0] == "row" and key[1].startswith(SERVER) else None


def brand_cell(row, icons):
    """A connector's brand in one cell and its color (connectors.py's BRANDS): its glyph in the font's icons (ICONS),
    else its letter; one of no known brand its name's letter, dim."""
    brand = BRANDS.get(row.get("brand") or "")
    if not brand:
        return (row["name"].strip()[:1] or "?").upper(), "muted"
    return (brand["glyph"] if icons and brand["glyph"] else brand["name"][0]), brand["color"]


def signing_row(row, connect):
    """ROW while its agent signs in to its server, in core's words (CONNECT, connecting()'s): its state, and for its
    properties what to do meanwhile and the two things to press."""
    server = row["id"][len(SERVER):]
    actions = [{**one, "path": None, "server": server, "primary": not n} for n, one in enumerate(connect["actions"])]
    return {**row, "state": connect["state"], "dim": False, "properties": {
        **row["properties"], "state": connect["state"], "lines": [], "text": None, "error": None,
        "words": connect["words"], "actions": actions}}


def label(action):
    """ACTION's words on its button and in the menu: the TUI's own where it has them, else core's."""
    return OWN_WORDS.get(action["id"], action["label"])


def said(row):
    """ROW's property lines as they lie under it: a line saying only what the row shows (its name, state or tag: where
    a rule or a plugin's skill is from) left out, and a third column naming its tag again."""
    tag, lines = (row["tag"] or {}).get("text"), row["properties"]["lines"]
    if not tag:                                     # a conflict: both rules, each with where it is
        return lines
    shown = {row["name"], tag, (row["state"] or {}).get("text")}
    return [[name, value, None if right == tag else right] for name, value, right in lines if value not in shown]


class Layers:
    def __init__(self, icons=True, folded=FOLDED):
        self.icons = icons
        self.folded = set(folded)             # the sections folded, kept in settings.json
        self.more = set()                     # the sections opened past their "N more"
        self.answer = None                    # the family's last read: None until the first one
        self.chosen = None                    # the chosen item's key: ("section", id), ("row", id), ("more", id)
        self.top, self.follow = 0, True       # the first line shown under the head; whether it follows the chosen
        self.checking, self.frame = set(), SPINNER[0]     # the servers Claude checks again, their marks' spin
        self.hover = self.menu = self.canvas = None
        self.cut = {}                         # a row cut short in the last draw: its words whole, for its tip
        self.adding = None                    # an agent picked under Add an agent…: how it is installed, shown
        self.head_y = 0                       # the head's row as last drawn: its list opens under it
        self.signing = set()                  # the servers their agent signs in to now (the family's)
        self.form = None                      # "Add by URL": {"name", "url": fields, "scope", "at": the keys', "error"}
        self.wanted = None                    # a row to choose once it is read: a server added a moment ago
        self.period = PERIODS[0]              # the period Usage's costs are of
        self.costs = None                     # core's report for it (the family's read): None until the first one
        self.reading = False                  # whether conversations are still being read for it
        self.opened = {}                      # Usage's blocks turned here, {agent: open}, till core's answer tells it

    @property
    def editing(self):
        """Whether the keys are a field's (the form's): the dock's own (1-6, q) wait."""
        return bool(self.form)

    # --- what it shows

    def set(self, answer):
        """ANSWER (the family's read: core's layers() with the agent and folder, or "missing"), the chosen item kept
        where it still is, else the one in its place."""
        keys = [key for key, _ in self.items()]
        place = keys.index(self.chosen) if self.chosen in keys else 1         # a new view: under its head
        self.answer = answer
        told = ((answer or {}).get("usage") or {}).get("open") or {}
        self.opened = {agent: on for agent, on in self.opened.items() if told.get(agent) != on}
        if self.adding and (self.agent_of(self.adding) or {}).get("installed", True):
            self.adding = None                # installed meanwhile, or no longer told
        if not self.adds():                   # another agent's, or no setup: nothing to add to
            self.form = None
        keys = [key for key, _ in self.items()]
        if self.wanted in keys:
            self.chosen, self.wanted, self.follow = self.wanted, None, True
        if self.chosen not in keys:
            self.chosen = keys[min(place, len(keys) - 1)] if keys else None

    def agent(self):
        return (self.answer or {}).get("agent")

    def doable(self, row):
        return doable(row, self.agent())

    def claude(self):
        """Whether a Claude runs in this tab: where its /mcp command is typed."""
        return bool((self.answer or {}).get("claude"))

    def adds(self):
        """Core's words for adding a connector (connecting()'s "add"), None where no setup shows."""
        return None if self.standing() else ((self.answer or {}).get("connect") or {}).get("add")

    def label_of(self, server):
        """The name SERVER's row shows (Box for claude.ai Box), else its own."""
        return next((row["name"] for section in self.sections() for row in section["rows"]
                     if row["id"] == SERVER + server), server)

    def agent_of(self, key):
        """The agent KEY as core tells it (the answer's "agents"), or None."""
        return next((one for one in (self.answer or {}).get("agents") or () if one["key"] == key), None)

    def shown_agent(self):
        """The agent on the head: the one looked at under Add an agent…, else the answer's."""
        return self.agent_of(self.adding or (self.answer or {}).get("agent"))

    def standing(self):
        """What stands in the setup's place (core's standing()): the looked-at agent's, else the answer's; None."""
        return (self.agent_of(self.adding) or {}).get("empty") if self.adding else (self.answer or {}).get("empty")

    def sections(self):
        """Core's sections, a connector whose agent signs in now saying so in core's words."""
        found, connect = (self.answer or {}).get("sections") or [], (self.answer or {}).get("connect")
        if not connect or not self.signing:
            return found
        return [section if section["id"] != CONNECTORS else {**section, "rows": [
            signing_row(row, connect) if server_of(("row", row["id"])) in self.signing else row
            for row in section["rows"]]} for section in found]

    def problems(self):
        """The head's problems in words ("1 failed"), the worst first."""
        return [one["text"] for one in ((self.answer or {}).get("health") or {}).get("problems") or []]

    def tone(self):
        """The worst problem's tone, for the row's and the rail's dot: "bad" over "warn", else None."""
        tones = {one["tone"] for one in ((self.answer or {}).get("health") or {}).get("problems") or []}
        return "bad" if "bad" in tones else "warn" if "warn" in tones else None

    def shown(self, section):
        """SECTION's rows shown and how many wait under "N more": its first FIRST, its problems and used ones too;
        every one where "1 more" would take the line the one row it hides needs."""
        rows = section["rows"]
        if section["id"] in self.more or len(rows) <= FIRST:
            return rows, 0
        kept = [row for n, row in enumerate(rows) if n < FIRST or problem(row) or row["used"]]
        return (kept, len(rows) - len(kept)) if len(rows) - len(kept) > 1 else (rows, 0)

    def usage(self):
        """Usage as core words it (usage.py's section()) and its rows, an agent each (an API key's from the report,
        the agent in use first); (None, []) where the answer tells none."""
        found = (self.answer or {}).get("usage")
        if not found:
            return None, []
        rows = found["rows"]
        if self.costs:
            rows = cost_rows(rows, self.costs, self.answer.get("agents"), self.agent())
        return found, rows

    def opens(self, agent):
        """Whether AGENT's block in Usage is open: as turned here till core tells it, else as core keeps it for both
        clients (the agent in use's alone by default)."""
        if agent in self.opened:
            return self.opened[agent]
        return (((self.answer or {}).get("usage") or {}).get("open") or {}).get(agent, agent == self.agent())

    def items(self):
        """The items the keys walk, in order: [(key, (section, row or None))]: the head, Usage's head (its rows have
        nothing to do), then the sections' or, with no setup to show, what can be done instead."""
        if self.answer is None:
            return []
        found, standing = [(HEAD, (None, None))], self.standing()
        if standing:
            return found + [(("offer", one["id"]), (None, None)) for one in standing["actions"]]
        usage, rows = self.usage()
        if usage:
            found.append((("section", USAGE), (None, None)))
            found += [(("usage", row["key"]), (None, None)) for row in rows] if USAGE not in self.folded else []
        for section in self.sections():
            found.append((("section", section["id"]), (section, None)))
            if section["id"] in self.folded:
                continue
            rows, more = self.shown(section)
            found += [(("row", row["id"]), (section, row)) for row in rows]
            found += [(("more", section["id"]), (section, None))] if more else []
        return found

    def chosen_row(self):
        return next((row for key, (_, row) in self.items() if key == self.chosen and key[0] == "row"), None)

    # --- the lines it draws

    def lines(self, cells):
        """Every line under the head, in order: [(kind, its item's key or None, what it draws)]."""
        x = self.columns()
        found, column = [], self.column([row for one in self.sections() for row in one["rows"]], cells, x["name"])
        usage, rows = self.usage()
        if usage:
            found.append(("section", ("section", USAGE), {"id": USAGE, "title": usage["title"], "count": None,
                                                          "rows": rows}))
        if usage and USAGE not in self.folded:
            for row in rows:
                found.append(("agent", ("usage", row["key"]), row))
                if self.opens(row["key"]):
                    found += [("meters", None, row)] if row["five"] or row["week"] or "cost" not in row else []
                    found += [("month", None, row)] if (row.get("cost") or {}).get("month") else []
            found += [] if rows else [("none", None, usage["none"])]
            found += self.cost_lines(cells)
        for section in self.sections():
            key = ("section", section["id"])
            found.append(("section", key, section))
            if self.form and section["id"] == CONNECTORS:
                found += [("form", key, part) for part in self.form_parts()]
            if section["id"] in self.folded:
                continue
            rows, more = self.shown(section)
            if not rows:
                found.append(("none", None, f"No {section['title'].lower()}"))
            for row in rows:
                key = ("row", row["id"])
                found.append(("row", key, (row, column)))
                if row["warn"] and row["note"]:
                    found.append(("warning", key, row["note"]))
                if key == self.chosen:
                    found += [(kind, key, what) for kind, what in self.properties(
                        row, cells - INSET - self.name_x(key))]
            if more:
                found.append(("more", ("more", section["id"]), f"{more} more"))
        return found

    def cost_lines(self, cells):
        """Usage's lines under its agents in CELLS, from the report: its days as one row of blocks, its projects (the
        first PROJECTS; their commits where every name keeps its place), the cache's share and the prices' day, or,
        while conversations are still read, that; with nothing used, core's words for it."""
        report = self.costs
        if not report:
            return []
        if report["none"]:
            return [("none", None, READING if self.reading else report["none"])]
        found = []
        if any(day["total"] for day in report["daily"]):
            found += [("gap", None, None), ("none", None, PER_DAY), ("spark", None, report["daily"])]
        projects = report["projects"][:PROJECTS]
        said = max([width(commits_said(one)) for one in projects] or [0])
        named = max([min(PROJECT, width(one["name"])) for one in projects] or [0])
        if cells - INSET - self.columns()["name"] - said - 2 - COST - 2 < named:
            said = 0
        found += [("gap", None, None)] + [("project", None, (one, said)) for one in projects] if projects else []
        cache = next((cell["line"] for cell in report["summary"] if cell["key"] == "Tokens"), "")
        foot = [cache] * bool(cache) + [f"prices {report['prices_as_of'].split(',')[0]}"]
        return found + [("gap", None, None), ("none", None, READING if self.reading else " · ".join(foot))]

    def columns(self):
        """The columns a line starts at: a section's chevron, its title (a row's mark under it), a row's name."""
        title = INSET + 1 + len(after(self.icons))
        return {"chevron": INSET, "title": title, "name": title + 2}

    def name_x(self, key):
        """Where the item KEY's name and what lies under it start: a connector's past its brand."""
        return self.columns()["name"] + (BRAND if server_of(key) is not None else 0)

    @staticmethod
    def column(rows, cells, name):
        """Where ROWS, every section's, folded or not, end their states and how wide their tags are, the same for
        each, so nothing moves as one opens: (state end, tag cells); no tags where names from column NAME would keep
        fewer than NAME_LEAST cells."""
        edge = cells - INSET
        tags = max([min(TAG, width(row["tag"]["text"])) for row in rows if row["tag"]] or [0])
        states = max([width(row["state"]["text"]) for row in rows if row["state"]] or [0])
        if tags and edge - tags - 2 - states - 2 - name < NAME_LEAST:
            tags = 0
        return edge - tags - (2 if tags else 0), tags

    def properties(self, row, room):
        """ROW's properties as lines ROOM cells wide: label and value in aligned columns (a third at the right), none
        the row says already (said()), its error, its text, its buttons."""
        props, lines = row["properties"], said(row)
        widest = max([width(line[0]) for line in lines] or [0])
        found = [("property", (line, widest)) for line in lines]
        found += [("words", props["words"])] if props.get("words") else []
        for kind, text, most in (("error", props["error"], ERROR_ROWS), ("text", props["text"], TEXT_ROWS)):
            if text:
                found += [(kind, text[start:end].rstrip()) for start, end in wrap(text, max(1, room))[:most]]
        return found + ([("buttons", self.doable(row))] if self.doable(row) else [])

    # --- drawing

    def draw(self, canvas, top, height, roomy):
        """The head on row TOP, a blank row, then the lines from self.top in HEIGHT - 2 rows, the chosen item's lines
        in view while it follows the keys; its menu over them."""
        self.canvas, self.cut, cells = canvas, {}, canvas.width
        if self.answer is None:
            canvas.put(top, INSET, truncate(LOADING, cells - 2 * INSET), Style(fg="muted"))
            return
        self.head_y = top
        self.head(canvas, top)
        standing = self.standing()
        if standing:
            self.says(canvas, top + 2, top + height, standing)
        else:
            lines, rows = self.lines(cells), max(1, height - 2)
            self.scroll(lines, rows)
            for n, (kind, key, what) in enumerate(lines[self.top:self.top + rows]):
                self.line(canvas, top + 2 + n, kind, key, what)
        if self.menu:
            popup = self.menu
            popup.menu.draw(canvas, *popup.menu.at(popup.y, popup.x, cells, top, top + height, INSET))

    def scroll(self, lines, rows):
        """self.top: the chosen item's lines in view after a key moved it (its first line kept), else where the wheel
        left it; never past the last line."""
        mine = [n for n, (_, key, _) in enumerate(lines) if key == self.chosen]
        if self.follow and mine:
            first, last = mine[0], mine[-1]
            if first < self.top:
                self.top = first
            elif last >= self.top + rows:
                self.top = min(first, last - rows + 1)
            self.follow = False
        self.top = max(0, min(self.top, len(lines) - rows))

    def head(self, canvas, y):
        """The agent's name bold, "in <folder>" dim and ⌄ (a press or Enter opens the agents' list under it), its
        problems at the right in their colors, each choosing its row on a click."""
        cells, head, agent = canvas.width, self.answer["head"], self.agent_of(self.adding)
        name = agent["name"] if agent else head["name"]
        problems = [] if self.standing() else ((self.answer.get("health") or {}).get("problems")) or []
        bg = "selection" if self.chosen == HEAD else "hover" if self.hover == HEAD else None
        if bg:
            canvas.band(y, bg)
        x = cells - INSET
        name_room = x - INSET - (sum(width(one["text"]) + 2 for one in problems))
        if name_room < width(name):                         # no room for both: the name
            problems = []
        canvas.region(y, 0, cells, ("layer", HEAD))
        for one in reversed(problems):
            x -= width(one["text"])
            canvas.put(y, x, one["text"], Style(fg=STATE_ROLE[one["tone"]], bg=bg))
            canvas.region(y, x, x + width(one["text"]), ("problem", one["row"]))
            x -= 2
        end = x if problems else cells - INSET
        at = canvas.put(y, INSET, truncate(name, end - INSET), Style(fg="text", bg=bg, bold=True))
        more = glyphs(self.icons)["more"]
        if end - at > 2:
            at = canvas.put(y, at + 1, truncate(head["where"], end - at - 1), Style(fg="muted", bg=bg))
        if end - at > 1 + width(more):
            canvas.put(y, at + 1, more, Style(fg="muted", bg=bg))

    def says(self, canvas, y, bottom, standing):
        """What stands in the setup's place from row Y on (core's standing()): its title bold, its words, its install
        line, what can be done as buttons (the chosen one lit), its last line dim."""
        cells = canvas.width
        room = max(1, cells - 2 * INSET)
        lines = [("title", standing["title"])] + [("words", standing["words"][start:end].rstrip())
                                                  for start, end in wrap(standing["words"], room)]
        lines += [("gap", ""), ("command", standing["command"])] if standing["command"] else []
        lines += [("gap", ""), ("offers", standing["actions"])] if standing["actions"] else []
        lines += [("gap", ""), ("foot", standing["foot"])] if standing["foot"] else []
        styles = {"title": Style(fg="text", bold=True), "words": Style(fg="subtext"), "command": Style(fg="text"),
                  "foot": Style(fg="muted")}
        for row, (kind, what) in enumerate(lines[:max(0, bottom - y)], y):
            if kind == "offers":
                self.offers(canvas, row, what)
            elif kind != "gap":
                canvas.put(row, INSET, truncate(what, room), styles[kind])

    def offers(self, canvas, y, actions):
        """What can be done instead of a setup, as the properties' buttons: the chosen one lit as a menu's line."""
        x, end = INSET, canvas.width - INSET
        for one in actions:
            key, words = ("offer", one["id"]), OFFER_WORDS.get(one["id"], one["label"])
            words = truncate(words, max(1, end - x - 2))
            if x + width(words) + 2 > end:
                break
            bg = "button" if key == self.chosen else "hover" if key == self.hover else "input"
            canvas.chip(y, x, width(words) + 2, bg)
            canvas.put(y, x + 1, words, Style(fg="button_text", bg=bg, bold=True) if key == self.chosen
                       else Style(fg="text" if key == self.hover else "subtext", bg=bg))
            canvas.region(y, x, x + width(words) + 2, ("layer", key))
            x += width(words) + 4

    def line(self, canvas, y, kind, key, what):
        cells, x = canvas.width, self.columns()
        lit = kind in ("section", "row", "more", "agent")
        bg = ("selection" if key == self.chosen else "hover" if key == self.hover else None) if lit else None
        if bg:
            canvas.band(y, bg)
        if lit:
            canvas.region(y, 0, cells, ("layer", key))
        if kind == "section":
            mark = widgets.TURNS.mark(self.icons, ("agent", what["id"]), what["id"] not in self.folded)
            canvas.put(y, x["chevron"], mark, Style(fg="muted", bg=bg))
            count = "" if what["count"] is None else str(what["count"])
            canvas.put(y, cells - INSET - width(count), count, Style(fg="subtext", bg=bg))
            if what["id"] == USAGE and USAGE in self.folded:    # folded: one figure in the period's place
                count = self.headline(canvas, y, what["rows"], cells - INSET - x["title"] - 7, bg)
            elif what["id"] == USAGE:             # its period in the count's place: a press steps it
                count = truncate(period_said(self.period), max(0, cells - INSET - x["title"] - 7))
                canvas.put(y, cells - INSET - width(count), count, Style(fg="muted", bg=bg))
                canvas.region(y, cells - INSET - width(count), cells - INSET, ("period", None))
            canvas.put(y, x["title"], truncate(what["title"], cells - INSET - width(count) - 1 - x["title"]),
                       Style(fg="text", bg=bg, bold=True))
        elif kind == "row":
            self.row(canvas, y, key, *what, bg)
        elif kind in ("more", "none"):
            canvas.put(y, x["name"], truncate(what, cells - INSET - x["name"]), Style(fg="muted", bg=bg))
        elif kind in ("warning", "error", "text", "words"):
            role = {"warning": "modified", "error": "deleted", "text": "muted", "words": "subtext"}[kind]
            canvas.put(y, self.name_x(key), truncate(what, cells - INSET - self.name_x(key)), Style(fg=role))
        elif kind == "form":
            self.form_line(canvas, y, what)
        elif kind == "agent":
            self.agent_line(canvas, y, what, bg)
        elif kind == "meters":
            self.meters(canvas, y, what)
        elif kind == "month":
            self.month(canvas, y, what["cost"]["month"])
        elif kind == "spark":
            self.spark(canvas, y, what)
        elif kind == "project":
            self.project(canvas, y, *what)
        elif kind == "property":
            self.property(canvas, y, *what, self.name_x(key))
        elif kind == "buttons":
            self.buttons(canvas, y, what, self.name_x(key))

    def row(self, canvas, y, key, row, column, bg):
        """A row: its mark under its section's title (a connector's state, a conflict's, else USED's dot), its name
        (dim where it does not run here; a connector's after its brand) and note, its state and its tag in the view's
        columns."""
        cells, x = canvas.width, self.columns()
        state_end, tags = column
        tone = "warn" if row["warn"] else (row["state"] or {}).get("tone")
        if row["id"].startswith(SERVER) and row["id"][len(SERVER):] in self.checking:
            canvas.put(y, x["title"], self.frame, Style(fg="accent", bg=bg))       # Claude checking it again
        elif (row["icon"] == "plug" or row["warn"]) and tone in MARKS:
            glyph, role = MARKS[tone]
            canvas.put(y, x["title"], glyph, Style(fg=role, bg=bg))
        elif row["used"]:                               # the open conversation used it: the app's dot
            canvas.put(y, x["title"], USED[0], Style(fg=USED[1], bg=bg))
        if tags and row["tag"]:
            words = truncate(row["tag"]["text"], tags)
            canvas.put(y, cells - INSET - width(words), words, Style(fg=TAG_ROLE.get(row["tag"]["tone"], "muted"),
                                                                     bg=bg))
        name_x = self.name_x(key)
        if row["icon"] == "plug":                       # its brand between its mark and its name
            glyph, role = brand_cell(row, self.icons)
            canvas.put(y, x["name"], glyph, Style(fg=role, bg=bg))
        room = state_end - name_x                       # a tag's column keeps its two cells of air before it
        if row["state"]:
            words = truncate(row["state"]["text"], max(1, room - 3))
            canvas.put(y, state_end - width(words), words, Style(fg=STATE_ROLE.get(row["state"]["tone"], "muted"),
                                                                 bg=bg))
            room -= width(words) + 2
        note = "" if row["warn"] else row["note"] or ""
        whole = row["name"] + (f" {note}" if note else "")
        if width(whole) > room:
            self.cut[key] = whole
        at = canvas.put(y, name_x, truncate(row["name"], max(1, room)), Style(fg="muted" if row["dim"] else "text",
                                                                              bg=bg))
        if note and room - (at - name_x) > 2:
            canvas.put(y, at + 1, truncate(note, room - (at - name_x) - 1), Style(fg="muted", bg=bg))

    def agent_line(self, canvas, y, row, bg=None):
        """An agent of Usage: its block's chevron, its name bold, its plan's word dim; open, at the right what it cost
        where the report tells it, else, dim, its reading's age and its reset (both where they fit two cells off);
        folded, its figures (figures()), the tighter alone where both do not fit."""
        x, end = self.columns(), canvas.width - INSET
        opened = self.opens(row["key"])
        canvas.put(y, x["title"], FOLDS[opened], Style(fg="muted", bg=bg))
        at = canvas.put(y, x["name"], truncate(row["name"], max(1, end - x["name"])), Style(fg="text", bold=True,
                                                                                            bg=bg))
        if row["plan"] and end - at > 1 + width(row["plan"]):
            at = canvas.put(y, at + 1, row["plan"], Style(fg="muted", bg=bg))
        if not opened:
            parts = next((one for one in (figures(row), figures(row, short=True))
                          if one and sum(width(words) for words, _ in one) <= end - at - 2), [])
            self.right(canvas, y, end, parts, bg)
            return
        cost = row.get("cost")
        if cost:                              # what it cost: its figure, and the figure's word where both fit
            for figure, unit in ((cost["figure"], cost["unit"]), (cost["figure"], "")):
                if width(figure) + (1 + width(unit) if unit else 0) <= end - at - 2:
                    canvas.put(y, end - width(unit), unit, Style(fg="muted", bg=bg))
                    canvas.put(y, end - width(unit) - (1 if unit else 0) - width(figure), figure, Style(fg="text",
                                                                                                        bg=bg))
                    break
            return
        self.when(canvas, y, row, at, bg)

    def headline(self, canvas, y, rows, room, bg):
        """Usage's head folded: at its right the figure of headline()'s agent after its name, dim, where ROOM cells
        take it (else the figure alone); the words drawn ("" for none)."""
        row = headline(rows, self.agent())
        if not row:
            return ""
        for parts in ([(f"{row['name']} ", "muted")] + tightest(row), tightest(row)):
            words = "".join(words for words, _ in parts)
            if width(words) <= room:
                self.right(canvas, y, canvas.width - INSET, parts, bg)
                return words
        return ""

    @staticmethod
    def right(canvas, y, end, parts, bg=None):
        """PARTS ([(words, role)]) drawn in their roles, ending at column END."""
        x = end - sum(width(words) for words, _ in parts)
        for words, role in parts:
            x = canvas.put(y, x, words, Style(fg=role, bg=bg))

    @staticmethod
    def when(canvas, y, row, at, bg=None):
        """ROW's reading's age and its window's reset at the line's right, dim, two cells past column AT at least."""
        end = canvas.width - INSET
        said = [words for words in (row["age"], (row["resets"] or {}).get("said")) if words]
        for words in ("  ".join(said), *said[:1]):
            if words and width(words) <= end - at - 2:
                canvas.put(y, end - width(words), words, Style(fg="muted", bg=bg))
                break

    def meters(self, canvas, y, row):
        """An agent's limits under its name: "5h" and "wk" dim, each with its bar and percent in its level's color,
        each in its own column (one past its reset leaves its place empty); a narrow pane drops the bars. Where its
        name's line says what it cost, its age and reset stand after them."""
        x, end = self.columns()["name"], canvas.width - INSET
        bars = end - x >= 2 * (3 + BAR + 4) + 2
        if row.get("cost"):
            self.when(canvas, y, row, x + 2 * (3 + BAR + 4 if bars else 7) + 2)
        for one in (row["five"], row["week"]):
            if one:
                role = Style(fg=LEVEL_ROLE.get(one["level"], "muted"))
                at = canvas.put(y, x, one["label"], Style(fg="muted"))
                if bars:
                    at = canvas.put(y, at + 1, bar(one["used"]), role)
                canvas.put(y, at, one["text"].rjust(4 if bars else 5), role)
            x += (3 + BAR + 4 if bars else 7) + 2

    def month(self, canvas, y, month):
        """An API-key agent's month under its name: its name dim, its spent as a bar of its budget (with one, where
        the bars fit), the pace it is on; bar and pace yellow once over."""
        x, end = self.columns()["name"], canvas.width - INSET
        role = Style(fg="modified") if month["over"] else None
        at = canvas.put(y, x, month["label"], Style(fg="muted"))
        if month["used"] is not None and end - x >= 2 * (3 + BAR + 4) + 2:
            at = canvas.put(y, at + 1, bar(month["used"]), role or Style(fg="added"))
        canvas.put(y, at + 2, truncate(month["pace"], max(0, end - at - 2)), role or Style(fg="muted"))

    def spark(self, canvas, y, daily):
        """The report's days as one row of blocks, each in its costliest model's color, then the days they span."""
        x, end = self.columns()["name"], canvas.width - INSET
        shown = daily
        while len(shown) > 1 and len(shown) > end - x - 2 - width(days_said(shown)):   # the days named are the ones
            shown = shown[1:]                                                           # drawn: the last that fit
        said = days_said(shown)
        for block, color in spark(shown, len(shown)):
            x = canvas.put(y, x, block, Style(fg=color))
        canvas.put(y, x + 2, said, Style(fg="muted"))

    def project(self, canvas, y, one, said):
        """A project: its name, its cost, and its conversations' commits dim in a column SAID cells wide (0: none)."""
        x, end = self.columns()["name"], canvas.width - INSET
        cost = "no price" if one["cost"] is None else money(one["cost"], True)
        if said:
            canvas.put(y, end - said, commits_said(one), Style(fg="muted"))
            end -= said + 2
        canvas.put(y, end - width(cost), cost, Style(fg="text" if one["cost"] is not None else "muted"))
        canvas.put(y, x, truncate(one["name"], max(1, end - width(cost) - 2 - x)), Style(fg="text"))

    def property(self, canvas, y, line, widest, x):
        """A property from column X: its label dim, its value from the labels' column (WIDEST cells and two) on, a
        third column at the right, dim."""
        cells = canvas.width
        name, value, right = line
        end = cells - INSET
        if right:
            canvas.put(y, end - width(right), right, Style(fg="muted"))
            end -= width(right) + 2
        canvas.put(y, x, name, Style(fg="muted"))
        canvas.put(y, x + widest + 2, truncate(value, max(1, end - x - widest - 2)), Style(fg="text"))

    def buttons(self, canvas, y, actions, x):
        """The chosen row's buttons from column X as blocks, a cell of air round each label, two cells apart: Connect
        lit as the accent's button, one that waits for a Claude dim; lit under the mouse."""
        end = canvas.width - INSET
        for n, one in enumerate(actions):
            words = truncate(label(one), max(1, end - x - 2))
            if x + width(words) + 2 > end:
                break
            pointed, waits = self.hover == ("action", n), one["id"] in NEEDS and not self.claude()
            bg = "button" if one["id"] == "connect" else "hover" if pointed else "input"
            canvas.chip(y, x, width(words) + 2, bg)
            canvas.put(y, x + 1, words, Style(fg="button_text", bg=bg, bold=True) if bg == "button" else Style(
                fg="muted" if waits else "text" if pointed else "subtext", bg=bg))
            canvas.region(y, x, x + width(words) + 2, ("action", n))
            x += width(words) + 4

    # --- a connector added: More's lines, the form under Connectors' head

    def menu_lines(self):
        """What More lists first while this view shows (connectors.html's ⋯ menu): the ways to add a connector, and a
        read of the setup; none where no setup shows."""
        add = self.adds()
        return [WAYS[way["id"]] for way in add["menu"] if way["id"] in WAYS] + [REFRESH] if add else []

    def menu_pick(self, choice):
        """More's line CHOICE done: claude.ai's page in the browser, the form opened, the setup read again."""
        if choice == REFRESH:
            return Action("refresh_agent", ())
        way = next((way for way in (self.adds() or {}).get("menu", ()) if WAYS.get(way["id"]) == choice), None)
        if way and way["url"]:
            return Action("open_url", (way["url"],))
        if way:
            self.open_form()
        return None

    def open_form(self):
        """The form under Connectors' head, the section open and in view, the keys in Name."""
        scopes = self.adds()["scopes"]
        self.form = {"name": TextInput(), "url": TextInput(), "scope": scopes[0]["id"] if scopes else None,
                     "at": "name", "error": None}
        self.folded.discard(CONNECTORS)
        self.chosen, self.follow, self.menu = ("section", CONNECTORS), True, None

    def form_stops(self):
        """What the form's keys step through, in order."""
        return ["name", "url"] + (["scope"] if self.adds()["scopes"] else []) + ["add", "cancel"]

    def form_parts(self):
        return ["title", "name", "url"] + (["scope"] if self.adds()["scopes"] else []) + (
            ["error"] if self.form["error"] else []) + ["buttons", "gap"]

    def refuse(self, error):
        """Why the form was not taken ({"field", "error"}: core's check, or the agent's own words), the keys back in
        the field refused."""
        if self.form:
            self.form["error"] = error
            self.form["at"] = error["field"] if error["field"] in ("name", "url") else self.form["at"]

    def form_line(self, canvas, y, part):
        """A line of the form (connectors.html's Hozzáadás pane): its title, a field after its label, Claude's two
        scopes as chips (the chosen one lit), why it was refused, Add and connect lit and Cancel. The terminal's
        cursor stands where the keys are."""
        add, form, x, end = self.adds(), self.form, self.columns()["title"], canvas.width - INSET
        at, value = form["at"], x + max(width(name) for name in add["fields"].values()) + 2
        if part == "title":
            canvas.put(y, x, truncate(add["title"], end - x), Style(fg="text", bold=True))
        elif part in ("name", "url"):
            canvas.put(y, x, add["fields"][part], Style(fg="muted"))
            form[part].draw(canvas, y, value, max(1, end - value), 1, Style(fg="text", bg="input"), at == part)
            canvas.region(y, value, end, ("form", part))
        elif part == "scope":
            canvas.put(y, x, add["fields"]["scope"], Style(fg="text" if at == "scope" else "muted"))
            for one in add["scopes"]:
                lit, words = one["id"] == form["scope"], truncate(one["label"], max(1, end - value - 2))
                if lit:
                    canvas.chip(y, value, width(words) + 2, "button")
                canvas.put(y, value + 1, words, Style(fg="button_text", bg="button", bold=True) if lit
                           else Style(fg="subtext"))
                canvas.region(y, value, value + width(words) + 2, ("scope", one["id"]))
                if lit and at == "scope":
                    canvas.cursor = (y, value + 1)
                value += width(words) + 4
        elif part == "error":
            canvas.put(y, x, truncate(form["error"]["error"], end - x), Style(fg="deleted"))
        elif part == "buttons":
            for key, words in (("add", add["submit"]), ("cancel", add["cancel"])):
                bg = "button" if key == "add" else "hover" if at == key or self.hover == ("form", key) else "input"
                canvas.chip(y, x, width(words) + 2, bg)
                canvas.put(y, x + 1, words, Style(fg="button_text", bg=bg, bold=True) if key == "add"
                           else Style(fg="text" if bg == "hover" else "subtext", bg=bg))
                canvas.region(y, x, x + width(words) + 2, ("form", key))
                if at == key:
                    canvas.cursor = (y, x + 1)
                x += width(words) + 4

    def form_key(self, event):
        """A key in the form: Tab and ↓ step on, Shift+Tab and ↑ back; a field takes what is typed; ← → or Space
        choose the scope; Enter adds (on Cancel: leaves); Esc leaves."""
        form, stops, name = self.form, self.form_stops(), event.name
        at = form["at"]
        if name == "esc" or (name == "enter" and at == "cancel"):
            self.form = None
        elif name in ("tab", "down", "backtab", "up"):
            form["at"] = stops[(stops.index(at) + (1 if name in ("tab", "down") else -1)) % len(stops)]
        elif name == "enter":
            return self.submit()
        elif at in ("name", "url"):
            if form[at].handle(event) and (form["error"] or {}).get("field") == at:
                form["error"] = None              # typed over: no longer what was refused
        elif at == "scope" and (name in ("left", "right") or (name == "char" and event.char == " ")):
            ids = [one["id"] for one in self.adds()["scopes"]]
            form["scope"] = ids[(ids.index(form["scope"]) + (-1 if name == "left" else 1)) % len(ids)]
        return None

    def submit(self):
        form = self.form
        return Action("add_connector", (form["name"].text, form["url"].text, form["scope"]))

    def form_press(self, kind, key):
        """A press in the form: the keys in a field, a scope chosen, its buttons done."""
        if kind == "scope":
            self.form.update(scope=key, at="scope")
        elif key == "cancel":
            self.form = None
        elif key == "add":
            return self.submit()
        else:
            self.form["at"] = key
        return None

    def tip(self, target):
        """A row cut short: its name and note whole."""
        if isinstance(target, tuple) and target[0] == "layer":
            return self.cut.get(target[1])
        return None

    # --- keys and the mouse

    def handle(self, event):
        if isinstance(event, Mouse):
            return self.mouse(event)
        if not isinstance(event, Key) or self.answer is None:
            return None
        if self.menu:
            choice = self.menu.menu.handle(event)
            if choice == "cancel":
                self.menu = None
            return self.pick(choice) if choice not in (None, "cancel") else None
        if self.form:
            return self.form_key(event)
        keys = [key for key, _ in self.items()]
        if not keys:
            return None
        at = keys.index(self.chosen) if self.chosen in keys else 0
        name = event.name
        if name in ("up", "down", "pageup", "pagedown", "home", "end"):
            step = {"up": -1, "down": 1, "pageup": -10, "pagedown": 10, "home": -len(keys), "end": len(keys)}[name]
            self.choose(keys[max(0, min(len(keys) - 1, at + step))])
        elif name in ("right", "left") and self.chosen and self.chosen[0] == "usage":
            if self.opens(self.chosen[1]) == (name == "left"):      # → opens a folded one, ← folds an open one
                return self.turn(self.chosen[1])
            if name == "left":
                self.choose(("section", USAGE))
        elif name == "right" and self.chosen and self.chosen[0] == "section":
            if self.chosen[1] in self.folded:
                return self.fold(self.chosen[1])
            if at + 1 < len(keys) and keys[at + 1][0] != "section":
                self.choose(keys[at + 1])
        elif name == "left" and self.chosen and self.chosen[0] in ("section", "row", "more"):
            if self.chosen[0] == "section":
                return None if self.chosen[1] in self.folded else self.fold(self.chosen[1])
            self.choose(next(key for key in reversed(keys[:at]) if key[0] == "section"))
        elif name == "enter":
            return self.activate()
        elif name == "char" and event.char == ADD_KEY and not (event.ctrl or event.alt) and self.adds():
            self.open_form()
        elif name == "char" and event.char == PERIOD_KEY and not (event.ctrl or event.alt) and self.usage()[0]:
            return self.step_period()
        elif name == "char" and event.char == GRAPH_KEY and not (event.ctrl or event.alt) and self.graphs():
            return Action("show_graph", ())
        return None

    def graphs(self):
        """Whether the agent shown has a graph to show: one whose setup is read."""
        return bool(self.answer) and not self.standing() and bool(self.answer.get("sections"))

    def step_period(self):
        """Usage's next period (PERIODS', round): its head says it at once, its costs are asked for."""
        self.period = PERIODS[(PERIODS.index(self.period) + 1) % len(PERIODS)]
        return Action("usage_period", (self.period,))

    def choose(self, key):
        self.chosen, self.follow, self.menu = key, True, None

    def turn(self, agent):
        """AGENT's block in Usage opened or folded, at once; core keeps it for both clients (the family asks)."""
        self.opened[agent] = not self.opens(agent)
        self.follow = True
        return Action("usage_open", (agent, self.opened[agent]))

    def fold(self, section):
        """SECTION folded or opened, its chevron turning; the sections folded kept (settings.json)."""
        widgets.TURNS.turn(("agent", section))
        self.folded ^= {section}
        self.more.discard(section)
        self.follow = True
        return Action("remember_agent_folded", (sorted(self.folded),))

    def activate(self):
        """Enter: a section folded or opened (Usage's: its view), an agent's block in it; "N more" opened in place, its
        first new row chosen; a row's first action this client can do."""
        kind, name = self.chosen or (None, None)
        if kind == "head":
            return self.open_list()
        if kind == "offer":
            return self.offer(name)
        if kind == "section" and name == USAGE:         # its home: the Usage view
            return Action("open_usage", (self.period,))
        if kind == "section":
            return self.fold(name)
        if kind == "usage":
            return self.turn(name)
        if kind == "more":
            section = next(s for s in self.sections() if s["id"] == name)
            before = {row["id"] for row in self.shown(section)[0]}
            self.more.add(name)
            self.choose(("row", next(row["id"] for row in section["rows"] if row["id"] not in before)))
            return None
        row = self.chosen_row()
        return self.act(self.doable(row)[0]) if row and self.doable(row) else None

    def act(self, one):
        """What action ONE asks the family for: a file opened, the agent's own command on its server; Claude's /mcp
        with no Claude in the tab: what it waits for, said."""
        kind = one["id"]
        if kind == "open":
            return Action("open_setup", (one["path"],))
        if kind in NEEDS:
            return Action("turn_server", (one["server"], kind == "turn-on")) if self.claude() \
                else Action("say", (NEEDS[kind],))
        return Action(ASKS[kind], (one["server"],))

    def pick(self, words):
        popup, self.menu = self.menu, None
        if isinstance(popup.menu, AgentMenu):
            return self.picked(words)
        if popup.on == USAGE:
            return Action("open_usage", (self.period,))
        if popup.on == SHOW_GRAPH:
            return Action("show_graph", ())
        return next((self.act(one) for one in self.doable(popup.on) if label(one) == words), None)

    def open_list(self, add=False):
        """The agents' list under the head: the installed ones and Add an agent…, or (ADD) the ones to add."""
        agents, check = (self.answer or {}).get("agents"), glyphs(self.icons)["check"]
        menu = AgentMenu(ADD, add_choices(agents), check, NONE_TO_ADD) if add else AgentMenu(
            AGENTS, agent_choices(agents, None if self.adding else self.answer.get("agent")), check, LOADING_AGENTS)
        self.menu = Popup(menu, "agents", self.head_y + 1, INSET)

    def picked(self, choice):
        """CHOICE made in the agents' list: an agent, the whole view its own (the app keeps it); Add an agent…, its
        list; an agent to add, how it is installed in the setup's place."""
        if choice["kind"] == "add":
            return self.open_list(add=True)
        self.adding = choice["key"] if choice["kind"] == "install" else None
        if choice["kind"] == "agent":
            return Action("choose_agent", (choice["key"],))
        self.choose(next((key for key, _ in self.items() if key[0] == "offer"), HEAD))
        return None

    def offer(self, name):
        """What stands in a setup's place done: its agent's own sign-in, its install line copied, its page opened."""
        agent, standing = self.shown_agent(), self.standing()
        if not agent or not standing:
            return None
        return {"sign-in": Action("sign_in", (agent["key"],)), "copy": Action("copy_text", (standing["command"],)),
                "page": Action("open_url", (agent["page"],))}.get(name)

    def close_menu(self):
        self.menu = None

    def mouse(self, event):
        target = self.canvas.hit(event.x, event.y) if self.canvas else None
        if event.kind == "move":
            self.hover = target[1] if isinstance(target, tuple) and target[0] == "layer" else \
                target if isinstance(target, tuple) and target[0] in ("action", "form") else None
            if self.menu:
                self.menu.menu.point(target)
        elif event.kind in ("wheel_up", "wheel_down"):
            self.top = max(0, self.top + (3 if event.kind == "wheel_down" else -3))
            self.follow = False
        elif event.kind == "press":
            return self.press(target, event)
        return None

    def press(self, target, event):
        if self.menu:
            menu, self.menu = self.menu, None
            if str(target).startswith("menu:"):
                self.menu = menu
                return self.pick(menu.menu.choices[int(target[5:])])
            return None
        if not isinstance(target, tuple):
            return None
        kind, key = target
        if kind in ("form", "scope"):
            return self.form_press(kind, key) if self.form else None
        if kind == "problem":                           # its row chosen, its section opened
            section = next((s["id"] for s in self.sections() if any(row["id"] == key for row in s["rows"])), None)
            self.choose(("row", key))
            return self.fold(section) if section in self.folded else None
        if kind == "action":
            row = self.chosen_row()
            return self.act(self.doable(row)[key]) if row and key < len(self.doable(row)) else None
        if kind == "period":
            self.choose(("section", USAGE))
            return self.step_period()
        self.choose(key)
        if key == HEAD and event.button == 2:           # the head's own menu: its graph
            self.menu = Popup(Menu([SHOW_GRAPH]), SHOW_GRAPH, event.y, event.x) if self.graphs() else None
            return None
        if key == ("section", USAGE):                   # a press folds it as the others; its view from the menu
            self.menu = Popup(Menu([OPEN_USAGE]), USAGE, event.y, event.x) if event.button == 2 else None
            return self.fold(USAGE) if event.button == 0 else None
        if event.button == 2 and key[0] == "row":
            row, does = self.chosen_row(), self.doable(self.chosen_row())
            self.menu = Popup(Menu([label(one) for one in does]), row, event.y, event.x) if does else None
            return None
        return self.activate() if event.button == 0 and key[0] in ("section", "more", "head", "offer", "usage") \
            else None

    # --- what a new version needs

    def kept(self):
        return {"chosen": list(self.chosen) if self.chosen else None, "more": sorted(self.more),
                "period": self.period}

    def take(self, kept):
        chosen = kept.get("chosen")
        if isinstance(chosen, list) and len(chosen) == 2 and all(isinstance(part, str) for part in chosen):
            self.chosen = tuple(chosen)
        self.more.update(name for name in kept.get("more") or () if isinstance(name, str))
        self.period = kept["period"] if kept.get("period") in PERIODS else self.period
