"""The sidebar's Agent view: what an agent starts with in the folder, in core's words (layers(), section(), report's
months), in cells as the mockups' TUI panes: the head, its line and start-up rule, Usage, the sections, the chosen row's
properties and its form (agent_form.py), a connector's form; and the graph as a tree (graph.py's). It only asks."""
import time

import usage
import widgets
from agent_form import REMOVE_KEY, Form
from agent_layers import NOT_APPROVED, SAID_AS
from agent_setup import READ
from agent_state import HERE
from connectors import BRANDS
from icons import glyphs
from screen import INSET, SPINNER, Style, after, truncate, width
from vt import Key, Mouse
from widgets import MENU_WIDEST, Action, Keyed, Menu, Popup, TextInput, wrap

FOLDED = ("subagents", "rules", "skills", "permissions")     # folded till opened: Connectors, the problems' home, open
FIRST = 5                     # rows a section shows before "N more": its problems and used ones always
TAG = 12                      # cells a tag takes at most (a plugin's name may be long)
NAME_LEAST = 8                # cells a section's names keep at least: below that its tags go, its states stay
UNDER = 2                     # cells what lies under a row (its properties, a reset, a conflict) stands in from it
TEXT_ROWS, ERROR_ROWS = 3, 2  # rows of a chosen row's text (a rule's first lines) and of its error
# the actions core offers, and a sign-in's own (core's connecting()); Claude's own command on Claude's rows alone.
# A connector's Turn off and Turn on are its form's switch
WORKS = ("open", "retry", "connect", "sign-out", "reopen", "cancel", "graph")
CLAUDES = ("retry",)
ASKS = {"retry": "retry_server", "connect": "connect_server", "sign-out": "sign_out_server",
        "reopen": "reopen_sign_in", "cancel": "cancel_sign_in"}          # what an action asks the family for
ADD_KEY, USAGE_KEY, GRAPH_KEY, RUNS_KEY = "a", "U", "g", "r"   # the form, the Usage and Runs views, the graph
UNDO_KEY = "u"                # the foot line's Undo, while it shows
WAITS = SAID_AS[NOT_APPROVED][0]     # a project server's state before it is approved: its form is core's two words
EDITED = ("claude", "codex")  # the agents whose harness core changes (harness.py)
RULES = "permissions"         # the section a rule is added in: `a` on it, its head's +
PLUS = "+"
OWN_FILE = ("mode", "approval", "sandbox", "permission:", "conflict:")     # rows whose form names their file
PLUGIN = "Plugin"             # where a plugin's subagent is from (core's origin()): it turns off with its plugin
# More's lines while this view shows (connectors.html's ⋯ menu), a key at the right of those it has
OPEN_USAGE, SHOW_GRAPH, REFRESH = Keyed("Open Usage", USAGE_KEY), Keyed("Show graph", GRAPH_KEY), "Refresh"
OPEN_RUNS = Keyed("Open Runs", RUNS_KEY)
WAYS = {"claude-ai": "Add from claude.ai…", "url": Keyed("Add by URL…", ADD_KEY)}
USAGE_BUTTON = {"id": "usage", "label": "Open Usage"}   # a Usage row's one action
CONNECTORS = "connectors"     # the section a connector is added in
BRAND = 2                     # cells a connector's brand takes before its name: its glyph or letter, and a space
MARKS = {"bad": ("✕", "deleted"), "warn": ("●", "modified"), "ok": ("●", "added")}     # the one mark column
STATE_ROLE = {"bad": "deleted", "warn": "modified", "ok": "muted", "busy": "accent", "off": "muted",
              "muted": "muted", "allow": "added", "ask": "modified", "deny": "deleted"}
PART_ROLE = {"rules": "accent", "skills": "done", "connectors": "account"}     # the start-up rule's parts, swatches
RULE, SWATCH = "━", "■"
USAGE = "usage"               # Usage's id among the sections folded and opened: the first one, core's own rows
BAR = 5                       # cells of a limit's bar, as usage-agents.html's TUI pane
LEVEL_ROLE = {"ok": "added", "warn": "modified", "bad": "deleted"}      # a level, the status line's colors
RANK = {"ok": 1, "warn": 2, "bad": 3}  # how near its end a level stands: another agent's yellow or red one is told
OPENS = "↗"                   # the Usage head's way to the Usage view
MONTH = "month"               # the report's period the API-key agents' months are read with (any period has them)
ROOT = "agent"                # the agent's own node in core's graph (graph.py's AGENT)
BRANCHES = (("in", lambda node: node["column"] == "in"), ("uses", lambda node: node["column"] == "uses"),
            ("subagents", lambda node: node["parent"] == ROOT))        # the tree's branches, agent-graph.html's
GATE_ROLE = {"allow": "ok", "ask": "warn", "deny": "bad"}              # a gate's verb in its tone's color, else dim
TITLE, TAGGED = 28, 18        # cells a node's name and its tag keep in the tree's columns
TREE = 80                     # cells a tree's line is kept to: the path wraps, an edge's gates go under
LOADING = "Loading setup…"
LOADING_AGENTS = "Loading agents…"
SERVER = "connector:"         # a server's row id: this, then its name (what Claude checks again)
OWN_AGENT = "subagent:"       # a subagent's row id: this, then its source and name; Claude's own folded in BUILT_IN
BUILT_IN = "subagent:built-in"
CONFLICT = "conflict:"        # a conflict's row id: its sentence under it, in yellow
HOOK = "hook:"                # a hook's row id, under Permissions' Hooks group
HEAD = ("head", None)         # the head's item: Enter opens the agents' list
MODEL = ("model", None)       # the head's line: the model and the effort a chat starts with, its form under it
OFFER_WORDS = {"page": "Open its page ↗"}                # the TUI's, as the plan's; else core's


def agent_choices(agents, current):
    """The agents' list's lines in core's words (each of AGENTS' "listed"): the installed in its order, at the right
    its plan's word, or sign in where it must; then the others under their own head; a check on the CURRENT one."""
    found = [{"kind": "install" if one["listed"]["dim"] else "agent", "key": one["key"], "name": one["name"],
              "check": one["key"] == current, "group": one["listed"]["group"], "right": one["listed"]["word"] or "",
              "role": "modified" if one["listed"]["tone"] == "warn" else "muted"} for one in agents or ()]
    return sorted(found, key=lambda one: one["kind"] == "install")


class AgentMenu(Menu):
    """The agents' list as agent-picker.html's TUI pane: each group's head dim (a rule over the second), then a choice
    a row: a ✓ (CHECK, the glyph) on the one shown, its name (dim: not installed), a word at the right in its color;
    with no choice, NOTE under core's first head."""

    def __init__(self, choices, check, note=""):
        super().__init__(choices)
        self.check, self.note = check, note

    def lines(self):
        """What it draws under its frame, in order: (None, a head's words), (None, None) a rule, (N, choice N)."""
        found, group = [], None
        for n, one in enumerate(self.choices):
            if one["group"] != group:
                found += [(None, None)] * bool(found) + [(None, one["group"])]
                group = one["group"]
            found.append((n, one))
        return found or [(None, HERE), (None, self.note)]

    def width(self):
        rows = [2 + width(one["name"]) + (2 + width(one["right"]) if one["right"] else 0) for one in self.choices]
        return max(MENU_WIDEST, max(rows + [width(words) for n, words in self.lines() if n is None and words]) + 4)

    def height(self):
        return len(self.lines()) + 2

    def handle(self, key):
        if not self.choices:
            return "cancel" if key.name in ("enter", "esc") else None
        return super().handle(key)

    def draw(self, canvas, y, x, cells):
        frame, inner = Style(fg="accent", bg="panel"), cells - 2
        canvas.put(y, x, "┌" + "─" * inner + "┐", frame)
        lines = self.lines()
        for row, (n, one) in enumerate(lines, 1):
            canvas.put(y + row, x, "│" + " " * inner + "│", frame)
            if n is None:
                said = one or "─" * (inner - 2)    # a group's head, or the rule over the second one
                canvas.put(y + row, x + 2, truncate(said, inner - 2), Style(fg="muted", bg="panel"))
                continue
            lit = n == self.index
            bg = "button" if lit else "hover" if n == self.hover else "panel"
            words = Style(fg="button_text", bg=bg, bold=True) if lit else Style(fg="text", bg=bg)
            canvas.put(y + row, x + 1, " " * inner, words)
            if one.get("check"):
                canvas.put(y + row, x + 2, self.check, words if lit else Style(fg="accent", bg=bg))
            right = truncate(one["right"], max(0, inner - 6))
            if one["role"] == "muted" and inner - 6 - width(right) < width(one["name"]):
                right = ""                    # no room for both: a plan's word goes before the name is cut
            room = inner - 5 - (width(right) + 1 if right else 0)
            name = Style(fg="muted", bg=bg) if one["kind"] == "install" and not lit else words
            canvas.put(y + row, x + 4, truncate(one["name"], max(1, room)), name)
            if right:
                canvas.put(y + row, x + cells - 2 - width(right), right,
                           words if lit else Style(fg=one["role"], bg=bg))
            canvas.region(y + row, x + 1, x + cells - 1, f"menu:{n}")
        canvas.put(y + len(lines) + 1, x, "└" + "─" * inner + "┘", frame)
        return self.height()


def grey(bg):
    """The faint text's role on a row lit by BG (the selection's or the hover's): muted_row, readable there."""
    return "muted_row" if bg else "muted"


def bar(used):
    """A limit's bar, BAR cells filled by USED percent: never empty with some used, full only with all of it."""
    filled = BAR if used >= 100 else min(BAR - 1, max(1 if used > 0 else 0, round(used * BAR / 100)))
    return "▰" * filled + "▱" * (BAR - filled)


def usage_rows(rows, report, agents, current):
    """Usage's ROWS (core's section()) with each agent on an API key a row of its month instead (REPORT's months, its
    plan's word as AGENTS tell it): the CURRENT agent's first, the others after the plans."""
    months = {one["agent"]: one for one in (report or {}).get("months") or ()}
    plans = {one["key"]: one.get("plan") for one in agents or ()}
    found = [row for row in rows if row["key"] not in months]
    for key, month in months.items():
        found.insert(0 if key == current else len(found), {"key": key, "name": month["name"], "plan": plans.get(key),
                                                           "month": month})
    return found


def figures(row, bars=True, short=False):
    """ROW's figures at its line's end, [(words, role)]: a plan's windows, each its bar (with BARS) and percent in its
    level's color ("5h ▰▰▰▱▱ 64%  wk ▰▱▱▱▱ 16%"; SHORT: the tighter alone); an API key's month spent in its level's
    color, of its budget (SHORT: the spent alone). [] for none."""
    month = row.get("month")
    if month:
        words = month["words"]
        return [(words["spent"], LEVEL_ROLE.get(month["level"], "text"))] + (
            [(f" {words['of']}", "muted")] if words["of"] and not short else [])
    found = []
    for one in [row["tight"]] if short and row["tight"] else [one for one in (row["five"], row["week"]) if one]:
        role = LEVEL_ROLE.get(one["level"], "muted")
        found += [("  ", "muted")] * bool(found) + [(f"{one['label']} ", "muted")]
        found += [(bar(one["used"] or 0) + " ", role)] * bars + [(one["text"], role)]
    return found


def standing(row):
    """How near its end ROW stands, to compare: its month's or its tighter window's level, then the share used."""
    month, tight = row.get("month"), row.get("tight")
    if month:
        return RANK.get(month["level"], 0), 100 * month["today"] / month["budget"] if month["budget"] else 0
    return (RANK[tight["level"]], tight["used"]) if tight else (0, 0)


def headline(rows, current):
    """The row whose figure Usage's head shows folded: the CURRENT agent's, or another's that is yellow or red and
    stands worse; None with neither."""
    mine = next((row for row in rows if row["key"] == current and figures(row)), None)
    worst = max((row for row in rows if row is not mine and standing(row)[0] >= RANK["warn"]), key=standing,
                default=None)
    return worst if worst and (mine is None or standing(worst) > standing(mine)) else mine


def usage_lines(row, twelve):
    """A Usage row's properties: each window's reset and the reading's age, label and value from core's words
    ("5h", "resets 14:46"; "Read", "3 min ago"), hours as TWELVE says."""
    said = [usage.reset_said(one["resets"], twelve) for one in (row.get("five"), row.get("week")) if one]
    return [words.split(" ", 1) + [None] for words in said + [row.get("age") or ""] if words]


def gates_said(edge):
    """EDGE's gates in brackets as a tree's parts, each verb in its tone's color: [ask, allow pytest, hook]."""
    found = []
    for one in (edge or {}).get("gates") or ():
        found += [(", " if found else "[", "dim"), (one["text"], GATE_ROLE.get(one["tone"], "dim"))]
    return found + [("]", "dim")] if found else []


def tree_rows(graph, run=False, twelve=False, cells=TREE):
    """Core's GRAPH as a tree's rows, each [(words, role)]: the agent with its line and chips, what goes in, what it
    uses (each edge's gates in brackets, under it where there is no room) and its subagents, in columns; RUN: what the
    chat ran instead (ran_rows()). TWELVE: hours with AM and PM."""
    if run:
        return ran_rows(graph, twelve, cells)
    agent = next(node for node in graph["nodes"] if node["id"] == ROOT)
    edges = {(one["from"], one["to"]): one for one in graph["edges"]}
    rows = [[(agent["title"], "bold")] + [(f"  {agent['sub']}", "dim")] * bool(agent["sub"])
            + [(f"  [{chip}]", "dim") for chip in agent["chips"]]]
    branches = [(name, nodes) for name, nodes in ((name, [node for node in graph["nodes"] if mine(node)])
                                                  for name, mine in BRANCHES) if nodes]
    shown = [node for _, nodes in branches for node in nodes]
    title = min(TITLE, max(width(node["title"]) for node in shown)) if shown else 0
    tagged = min(TAGGED, max(width(node["tag"] or "") for node in shown)) if shown else 0
    lead = 2 + title + 2 + (tagged + 2 if tagged else 0)        # where a node's words start
    for name, nodes in branches:
        rows.append([(name, "dim")])
        for node in nodes:
            tone = "dim" if node["dim"] else {"bad": "bad", "warn": "warn"}.get(node["state"], "dim")
            name_, tag = truncate(node["title"], title), truncate(node["tag"] or "", tagged)
            row = [(f"  {name_}" + " " * (title - width(name_) + 2), "dim" if node["dim"] else None)]
            row += [(tag + " " * (tagged - width(tag) + 2), "dim")] if tagged else []
            row += [(node["sub"], tone)] if node["sub"] else []
            gate = gates_said(edges.get((ROOT, node["id"])) or edges.get((node["id"], ROOT)))
            if gate and node["sub"] and lead + width(node["sub"]) + 1 + sum(width(words) for words, _ in gate) > cells:
                rows.append(row)
                row = [(" " * lead, None)]
            elif gate and node["sub"]:
                row.append((" ", None))
            rows.append(row + gate)
    return rows


def clock_said(seconds, twelve):
    """SECONDS since 1970 as this machine's time of day, 1:36 PM or 13:36 (TWELVE: with AM and PM); "" for none."""
    if not seconds:
        return ""
    at = time.localtime(seconds)
    return f"{at.tm_hour % 12 or 12}:{at.tm_min:02d} {'AM' if at.tm_hour < 12 else 'PM'}" if twelve \
        else f"{at.tm_hour:02d}:{at.tm_min:02d}"


def ran_rows(graph, twelve, cells):
    """What the chat ran (tree_rows()'s rows): the agent, the numbered path in order of first use, wrapped at CELLS;
    each agent that ran with its properties as aligned label and value rows, its model said on its own line alone;
    each tool's calls in a column."""
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
        lines = [["Cost", shown["state"]["text"], None]] * bool(shown.get("state")) + [
            line for line in shown["lines"] if line[0] != "Model"]
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
    return row["mark"] in ("bad", "warn")


def stated(row):
    """What ROW says in the states' column: its state, but a hook's "hook" (the Hooks group's head says it); a
    subagent of one's own its model and tools, muted (both clients' drawings put them there). None for neither."""
    if row["id"].startswith(HOOK):
        return None
    if row["state"]:
        return row["state"]
    own = row["id"].startswith(OWN_AGENT) and row["id"] != BUILT_IN
    return {"text": row["note"], "tone": "muted"} if own and row["note"] else None


def parts_of(section):
    """SECTION's own rows and its groups' (Permissions' Hooks), each a part with an id and its rows."""
    return [section] + section["groups"]


def doable(row, agent="claude", filed=False):
    """ROW's actions this client can do, Claude's own commands only for AGENT Claude; FILED: its form names its file,
    which opens there."""
    return [one for one in row["properties"]["actions"] if one["id"] in WORKS
            and (agent == "claude" or one["id"] not in CLAUDES) and not (filed and one["id"] == "open")]


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
    return {**row, "state": connect["state"], "mark": None, "dim": False, "properties": {
        **row["properties"], "state": connect["state"], "lines": [], "text": None, "error": None, "tip": None,
        "words": connect["words"], "actions": actions}}


def said(row):
    """ROW's property lines as they lie under it: a line saying only what the row shows (its name, state or tag: where
    a rule or a plugin's skill is from) left out, and a third column naming its tag again."""
    tag, lines = row["tag"], row["properties"]["lines"]
    if not tag:                                     # a conflict: both rules, each with where it is
        return lines
    shown = {row["name"], tag, (row["state"] or {}).get("text")}
    return [[name, value, None if right == tag else right] for name, value, right in lines if value not in shown]


class Layers:
    def __init__(self, icons=True, folded=FOLDED):
        self.icons = icons
        self.folded = set(folded)             # the sections folded, kept in settings.json
        self.more = set()                     # the sections and groups opened past their "N more"
        self.answer = None                    # the family's last read: None until the first one
        self.chosen = None                    # the chosen item's key: ("section", id), ("row", id), ("more", id)
        self.top, self.follow = 0, True       # the first line shown under the head; whether it follows the chosen
        self.checking, self.frame = set(), SPINNER[0]     # the servers Claude checks again, their marks' spin
        self.hover = self.menu = self.canvas = None
        self.cut = {}                         # a row cut short in the last draw: its words whole, for its tip
        self.looking = None                   # a not-installed agent picked in the list: how it is installed, shown
        self.head_y = 0                       # the head's row as last drawn: its list opens under it
        self.signing = set()                  # the servers their agent signs in to now (the family's)
        self.form = None                      # "Add by URL": {"name", "url": fields, "scope", "at": the keys', "error"}
        self.wanted = None                    # a row to choose once it is read: a server added a moment ago
        self.costs = None                     # core's report for the API-key agents' months (the family's read)
        self.edit = None                      # the chosen item's form (agent_form.py's), or a rule's being added
        self.saving = None                    # the foot's words for the save asked of the family
        self.foot = None                      # the last save: {"words", "label", "undo": core's edits back, "of"}

    @property
    def editing(self):
        """Whether the keys are a form's: the dock's own (1-6, q) wait."""
        return bool(self.form) or bool(self.edit and self.edit.entered)

    # --- what it shows

    def set(self, answer):
        """ANSWER (the family's read: core's layers() with the agent and folder, or "missing"), the chosen item kept
        where it still is, else the one in its place."""
        keys = [key for key, _ in self.items()]
        place = keys.index(self.chosen) if self.chosen in keys else None
        self.answer = answer
        if self.foot and self.foot["of"] != (answer.get("agent"), answer.get("folder")):
            self.foot = None                  # another agent's or folder's: its Undo is not this one's
        if self.looking and (self.agent_of(self.looking) or {}).get("installed", True):
            self.looking = None                # installed meanwhile, or no longer told
        if not self.adds():                   # another agent's, or no setup: nothing to add to
            self.form = None
        keys = [key for key, _ in self.items()]
        if self.wanted in keys:
            self.chosen, self.wanted, self.follow = self.wanted, None, True
        if self.chosen not in keys:               # the one in its place; a new view: the first under its head
            under = next((key for key in keys if key not in (HEAD, MODEL)), HEAD)
            self.chosen = (under if place is None else keys[min(place, len(keys) - 1)]) if keys else None
        self.reopen()

    def agent(self):
        return (self.answer or {}).get("agent")

    def doable(self, row):
        form = self.edit if self.edit and self.edit.key == ("row", row["id"]) else None
        return doable(row, self.agent(), row["id"].startswith(OWN_FILE) and bool(form and not form.locked()))

    # --- the chosen item's form (core's plan, which the family asks for)

    def request(self, key):
        """Core's request for the form the item KEY opens (the interface's table: the head's line, a row, the Hooks
        group), or None for an item with none."""
        if not key or self.standing() or self.agent() not in EDITED:
            return None
        kind, name = key
        head = self.answer["head"]
        if key == MODEL:
            return {"action": "model", **({"runs": head["runs"]} if head.get("runs") else {})} if head.get(
                "line") else None
        if kind == "group":
            return {"action": name}
        row = next((row for section in self.sections() for part in parts_of(section) for row in part["rows"]
                    if kind == "row" and row["id"] == name), None)
        if not row:
            return None
        part, _, rest = name.partition(":")
        if part in ("permission", "conflict"):
            behavior, _, rule = rest.partition(":")
            return {"action": "conflict", "behavior": behavior, "rule": rule} if part == "conflict" else {
                "action": "rule", "was": {"rule": rule, "behavior": behavior, "layer": row["tag"]}}
        if part == "connector":
            sizes = {"starts": head.get("starts"), "tokens": row["tokens"]}
            return {"action": part, "name": rest, **{key: size for key, size in sizes.items() if size is not None}}
        if name == BUILT_IN:
            return {"action": "subagent", "name": row["names"][0]} if row.get("names") else None
        if part == "subagent" and any(line[2] == PLUGIN for line in row["properties"]["lines"][:1]):
            return None
        return {"action": part, **({"name": row["name"]} if rest else {})} if part in (
            "mode", "approval", "sandbox", "skill", "subagent") else None

    def reopen(self):
        """The chosen item's form as it opens, core's plan for it awaited (the one shown stays till then); one the
        keys are in stays while its item is the chosen one."""
        form, asked = self.edit, self.request(self.chosen)
        if form and form.entered and form.key == self.chosen:
            return
        row = self.chosen_row() or {}
        parts = (row.get("state") or {}).get("text") == WAITS
        if form and asked and (form.key, form.base, form.parts) == (self.chosen, asked, parts):
            form.waits = True
        else:
            self.edit = Form(self.chosen, asked, row.get("names") or (), (row.get("name"), row.get("note")),
                             parts) if asked else None

    def asks(self):
        """The request the form waits for core's plan of (the family plans it before a draw), or None."""
        return self.edit.asked if self.edit and self.edit.waits else None

    def planned(self, asked, plan):
        if self.edit:
            self.edit.planned(asked, plan)

    def open_rule(self):
        """The form a rule is added with, under Permissions' head, the section open and in view."""
        key = ("section", RULES)
        self.folded.discard(RULES)
        self.chosen, self.follow, self.menu, self.form = key, True, None, None
        self.edit = Form(key, {"action": "rule"})
        self.edit.entered = True

    def edited(self, action):
        """What the form asked for, on its way to the family: a save keeps the foot's words; Claude's own command
        with no Claude in the tab says what it waits for (core's words); a rule's form left is gone."""
        form = self.edit
        if action and action.name == "save_harness":
            self.saving = {"words": form.saved(), "label": form.plan["undo"]}
        if action and action.name == "turn_server" and not self.claude():
            action = Action("say", (self.answer["connect"]["needs"]["turn-on"],))
        if not form.entered and form.key[0] == "section":
            self.edit = None
        return action

    def saved(self, said, undone=False):
        """Core's answer to a save (apply()'s). Made: the form as it opens again, the foot line with its Undo (none
        after an Undo). Refused: core's words in the form."""
        kept, self.saving, form = self.saving, None, self.edit
        if not said["applied"]:
            if form and not undone:
                form.error = said["error"]
            return
        self.foot = {**kept, "undo": said["undo"], "of": (self.agent(), self.answer.get("folder"))} \
            if kept and not undone else None
        if form and form.key[0] == "section":
            self.edit = None
        elif form:
            form.leave()

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
        """The agent on the head: the not-installed one looked at, else the answer's."""
        return self.agent_of(self.looking or (self.answer or {}).get("agent"))

    def standing(self):
        """What stands in the setup's place (core's standing()): the looked-at agent's, else the answer's; None."""
        return (self.agent_of(self.looking) or {}).get("empty") if self.looking else (self.answer or {}).get("empty")

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
        return [one["text"] for one in ((self.answer or {}).get("head") or {}).get("problems") or []]

    def tone(self):
        """The worst problem's tone, for the row's and the rail's dot: "bad" over "warn", else None."""
        tones = {one["tone"] for one in ((self.answer or {}).get("head") or {}).get("problems") or []}
        return "bad" if "bad" in tones else "warn" if "warn" in tones else None

    def shown(self, part):
        """PART's rows shown (a section's or a group's) and how many wait under "N more": its first FIRST, its
        problems and used ones too; every one where "1 more" would take the line the one row it hides needs."""
        rows = part["rows"]
        if part["id"] in self.more or len(rows) <= FIRST:
            return rows, 0
        kept = [row for n, row in enumerate(rows) if n < FIRST or row["mark"]]
        return (kept, len(rows) - len(kept)) if len(rows) - len(kept) > 1 else (rows, 0)

    def usage(self):
        """Usage as core words it (usage.py's section()) and its rows, an agent each (an API key's its month, from
        the report), the agent in use first; (None, []) where the answer tells none."""
        found = (self.answer or {}).get("usage")
        if not found:
            return None, []
        return found, usage_rows(found["rows"], self.costs, self.answer.get("agents"), self.agent())

    def items(self):
        """The items the keys walk, in order: [(key, (section, row or None))]: the head, Usage's head and its agents,
        then the sections' or, with no setup to show, what can be done instead."""
        if self.answer is None:
            return []
        found, standing = [(HEAD, (None, None))], self.standing()
        if standing:
            return found + [(("offer", one["id"]), (None, None)) for one in standing["actions"]]
        found += [(MODEL, (None, None))] if self.request(MODEL) else []
        usage_, rows = self.usage()
        if usage_:
            found.append((("section", USAGE), (None, None)))
            found += [(("usage", row["key"]), (None, None)) for row in rows] if USAGE not in self.folded else []
        for section in self.sections():
            found.append((("section", section["id"]), (section, None)))
            if section["id"] in self.folded:
                continue
            for part in parts_of(section):
                rows, more = self.shown(part)
                found += [(("group", part["id"]), (section, None))] if part is not section else []
                found += [(("row", row["id"]), (section, row)) for row in rows]
                found += [(("more", part["id"]), (section, None))] if more else []
        return found

    def chosen_row(self):
        return next((row for key, (_, row) in self.items() if key == self.chosen and key[0] == "row"), None)

    def chosen_usage(self):
        return next((row for row in self.usage()[1] if self.chosen == ("usage", row["key"])), None)

    def actions(self):
        """The chosen item's buttons: a row's actions this client does, a Usage row's Open Usage."""
        if self.chosen_usage():
            return [USAGE_BUTTON]
        row = self.chosen_row()
        return self.doable(row) if row else []

    # --- the lines it draws

    def lines(self, cells):
        """Every line under the head, in order: [(kind, its item's key or None, what it draws)]."""
        column = self.column([row for one in self.sections() for part in parts_of(one) for row in part["rows"]],
                             cells, self.columns()["name"])
        error = self.answer.get("error")
        found = self.form_lines(MODEL, cells) + ([("error", None, (error["text"], error["tip"]))] if error else [])
        usage_, rows = self.usage()
        if usage_:
            found.append(("section", ("section", USAGE), {"id": USAGE, "title": usage_["title"], "count": None,
                                                          "rows": rows, "groups": []}))
        if usage_ and USAGE not in self.folded:
            for row in rows:
                key = ("usage", row["key"])
                found.append(("usage", key, row))
                pace = (row.get("month") or {}).get("pace_line")
                found += [("pace", key, (pace, row["month"]["level"]))] if pace else []
                if key == self.chosen:
                    found += [(kind, key, what) for kind, what in self.usage_properties(
                        row, cells - INSET - self.under_x(key))]
                elif row.get("reset"):
                    found.append(("words", key, usage.reset_said(row["reset"], self.answer.get("twelve"))))
            found += [] if rows else [("none", None, usage_["none"])]
        for section in self.sections():
            key = ("section", section["id"])
            found.append(("section", key, section))
            if self.form and section["id"] == CONNECTORS:
                found += [("form", key, part) for part in self.form_parts()]
            found += self.form_lines(key, cells)
            if section["id"] in self.folded:
                continue
            for part in parts_of(section):
                rows, more = self.shown(part)
                if part is not section:
                    found += [("group", ("group", part["id"]), part)] + self.form_lines(("group", part["id"]), cells)
                for row in rows:
                    key = ("row", row["id"])
                    found.append(("row", key, (row, column)))
                    if row["id"].startswith(CONFLICT) and row["note"]:
                        found.append(("warning", key, row["note"]))
                    if key == self.chosen:
                        found += [(kind, key, what) for kind, what in self.properties(
                            row, cells - INSET - self.under_x(key))]
                if more:
                    found.append(("more", ("more", part["id"]), f"{more} more"))
        return found

    def columns(self):
        """The columns a line starts at: a section's chevron, its title (a row's mark under it), a row's name."""
        title = INSET + 1 + len(after(self.icons))
        return {"chevron": INSET, "title": title, "name": title + 2}

    def name_x(self, key):
        """Where the item KEY's name starts: a connector's past its brand."""
        return self.columns()["name"] + (BRAND if server_of(key) is not None else 0)

    def under_x(self, key):
        """Where what lies under the item KEY starts: UNDER cells in from its name (the head's line: from the side);
        a rule's form at the names' column."""
        return INSET + UNDER if key == MODEL else self.name_x(key) + (0 if key[0] == "section" else UNDER)

    def form_lines(self, key, cells):
        """The form's lines where it lies under the item KEY, which is not a row (a row's are among its properties)."""
        if not self.edit or self.edit.key != key or key != self.chosen:
            return []
        return [("edit", key, line) for line in self.edit.lines(cells - INSET - self.under_x(key), self.claude())]

    @staticmethod
    def column(rows, cells, name):
        """Where ROWS, every section's, folded or not, end their states and how wide their tags are, the same for
        each, so nothing moves as one opens: (state end, tag cells); no tags where names from column NAME would keep
        fewer than NAME_LEAST cells."""
        edge = cells - INSET
        tags = max([min(TAG, width(row["tag"])) for row in rows if row["tag"]] or [0])
        states = max([width(row["state"]["text"]) for row in rows if row["state"]] or [0])
        if tags and edge - tags - 2 - states - 2 - name < NAME_LEAST:
            tags = 0
        return edge - tags - (2 if tags else 0), tags

    def properties(self, row, room):
        """ROW's properties as lines ROOM cells wide: label and value in aligned columns (a third at the right), none
        the row says already (said()), its error (the files it names its tip), its text, its form as it opens, its
        buttons; with the keys in its form, the form alone."""
        form = self.edit if self.edit and self.edit.key == ("row", row["id"]) else None
        edit = [("edit", line) for line in form.lines(room, self.claude())] if form else []
        if form and form.entered:
            return edit
        props, lines = row["properties"], said(row)
        widest = max([width(line[0]) for line in lines] or [0])
        found = [("property", (line, widest)) for line in lines]
        found += [("words", props["words"])] if props.get("words") else []
        if props["error"]:
            found += [("error", (props["error"][start:end].rstrip(), props["tip"]))
                      for start, end in wrap(props["error"], max(1, room))[:ERROR_ROWS]]
        if props["text"]:
            found += [("text", props["text"][start:end].rstrip())
                      for start, end in wrap(props["text"], max(1, room))[:TEXT_ROWS]]
        return found + edit + ([("buttons", self.doable(row))] if self.doable(row) else [])

    def usage_properties(self, row, room):
        """A Usage row's properties: its windows' resets and its reading's age (usage_lines()), or why its limits are
        not told (core's words, ROOM cells wide), then Open Usage."""
        lines, why = usage_lines(row, self.answer.get("twelve")), (row.get("untold") or {}).get("why") or ""
        widest = max([width(line[0]) for line in lines] or [0])
        return [("property", (line, widest)) for line in lines] + [
            ("text", why[start:end].rstrip()) for start, end in wrap(why, max(1, room)) if why] + [
            ("buttons", [USAGE_BUTTON])]

    # --- drawing

    def draw(self, canvas, top, height, roomy):
        """The head from row TOP (its rows head()'s), then the lines from self.top in the rows left, the chosen item's
        lines in view while it follows the keys; its menu over them."""
        self.canvas, self.cut, cells = canvas, {}, canvas.width
        if self.answer is None:
            canvas.put(top, INSET, truncate(LOADING, cells - 2 * INSET), Style(fg="muted"))
            return
        self.head_y = top
        taken = self.head(canvas, top)
        standing = self.standing()
        if standing:
            self.says(canvas, top + taken, top + height, standing)
        else:
            lines, rows = self.lines(cells), max(1, height - taken - bool(self.foot))
            self.scroll(lines, rows)
            for n, (kind, key, what) in enumerate(lines[self.top:self.top + rows]):
                self.line(canvas, top + taken + n, kind, key, what)
            if self.foot and height > taken + 1:
                self.foot_line(canvas, top + height - 1)
        if self.menu:
            popup = self.menu
            popup.menu.draw(canvas, *popup.menu.at(popup.y, popup.x, cells, top, top + height, INSET))

    def foot_line(self, canvas, y):
        """The last save in core's words, dim, and its Undo after its key at the right."""
        end, label = canvas.width - INSET, self.foot["label"]
        x = end - width(label) - 2
        canvas.put(y, INSET, truncate(self.foot["words"], max(1, x - INSET - 2)), Style(fg="muted"))
        canvas.put(y, x, UNDO_KEY, Style(fg="muted"))
        canvas.put(y, x + 2, label, Style(fg="text" if self.hover == ("undo", None) else "subtext"))
        canvas.region(y, x, end, ("undo", None))

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
        """The agent's name bold, "in <folder>" dim and ⌄ (Enter or a press opens the agents' list), its problems at the
        right in their colors, a click choosing its row; where a setup shows, core's line dim and the start-up rule
        (rule()), else a blank row. The rows it takes."""
        cells, head, agent = canvas.width, self.answer["head"], self.agent_of(self.looking)
        name = agent["name"] if agent else head["name"]
        standing = self.standing()
        problems = [] if standing else head.get("problems") or []
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
            at = canvas.put(y, at + 1, truncate(head["where"], end - at - 1), Style(fg=grey(bg), bg=bg))
        if end - at > 1 + width(more):
            canvas.put(y, at + 1, more, Style(fg=grey(bg), bg=bg))
        if standing or "bar" not in self.answer:
            return 2
        line = 1 if head["line"] else 0
        if line:
            bg = "selection" if self.chosen == MODEL else "hover" if self.hover == MODEL else None
            if bg:
                canvas.band(y + 1, bg)
            if self.request(MODEL):
                canvas.region(y + 1, 0, cells, ("layer", MODEL))
            canvas.put(y + 1, INSET, truncate(head["line"], cells - 2 * INSET), Style(fg=grey(bg), bg=bg))
        self.rule(canvas, y + 1 + line, cells - 2 * INSET)
        return 2 + line

    def rule(self, canvas, y, cells):
        """What loads at start (core's bar) as a rule CELLS wide: each part's share of it in its color, a part with
        any share a cell at least; nothing where nothing loads."""
        parts = [one for one in self.answer["bar"] if one["share"]]
        sizes = [max(1, round(one["share"] * cells)) for one in parts]
        if sizes:
            sizes[sizes.index(max(sizes))] += cells - sum(sizes)
        x = INSET
        for size, one in zip(sizes, parts):
            x = canvas.put(y, x, RULE * size, Style(fg=PART_ROLE[one["part"]]))

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
        lit = kind in ("section", "row", "more", "usage", "group")
        bg = ("selection" if key == self.chosen else "hover" if key == self.hover else None) if lit else None
        if bg:
            canvas.band(y, bg)
        if lit:
            canvas.region(y, 0, cells, ("layer", key))
        if kind == "section":
            self.section(canvas, y, what, bg)
        elif kind == "row":
            self.row(canvas, y, key, *what, bg)
        elif kind == "usage":
            self.usage_line(canvas, y, what, bg)
        elif kind in ("more", "none", "group"):
            words = f"{what['title']} {what['count']}" if kind == "group" else what
            canvas.put(y, x["name"], truncate(words, cells - INSET - x["name"]), Style(fg=grey(bg), bg=bg))
            if kind == "group" and what.get("state"):       # every hook off here
                self.right(canvas, y, cells - INSET, [(what["state"]["text"], "muted")], bg)
        elif kind == "edit":
            self.edit.draw(canvas, y, self.under_x(key), what, self.hover)
        elif kind == "error":
            at = INSET if key is None else self.under_x(key)
            words = truncate(what[0], cells - INSET - at)
            canvas.put(y, at, words, Style(fg="deleted"))
            if what[1]:                                 # the files it named: its tip
                canvas.region(y, at, at + width(words), ("tip", what[1]))
        elif kind == "pace":
            (pace, level), at = what, self.under_x(key)
            words = pace["text"] if width(pace["text"]) <= cells - INSET - at else pace["narrow"]
            canvas.put(y, at, truncate(words, cells - INSET - at), Style(fg=LEVEL_ROLE.get(level, "muted")))
        elif kind in ("warning", "text", "words"):
            role = {"warning": "modified", "text": "muted", "words": "muted"}[kind]
            canvas.put(y, self.under_x(key), truncate(what, cells - INSET - self.under_x(key)), Style(fg=role))
        elif kind == "form":
            self.form_line(canvas, y, what)
        elif kind == "property":
            self.property(canvas, y, *what, self.under_x(key))
        elif kind == "buttons":
            self.buttons(canvas, y, what, self.under_x(key))

    def section(self, canvas, y, what, bg):
        """A section's head: its chevron dim (none on an empty one), its title bold and count; at the right Usage's ↗
        (folded, the figure that matters first: headline()'s), Permissions' summary in its tones' colors, else the
        start-up rule's swatch before what it loads always."""
        cells, x, faint = canvas.width, self.columns(), grey(bg)
        if what["id"] == USAGE or what["rows"] or what["groups"]:       # Usage's line says when it has none
            mark = widgets.TURNS.mark(self.icons, ("agent", what["id"]), what["id"] not in self.folded)
            canvas.put(y, x["chevron"], mark, Style(fg=faint, bg=bg))
        at = canvas.put(y, x["title"], truncate(what["title"], cells - INSET - x["title"]), Style(fg="text", bg=bg,
                                                                                                    bold=True))
        if what["count"] is not None and at + 1 + width(str(what["count"])) <= cells - INSET:
            at = canvas.put(y, at + 1, str(what["count"]), Style(fg=faint, bg=bg))
        end, room = cells - INSET, cells - INSET - at - 2
        if what["id"] == USAGE:
            row = headline(what["rows"], self.agent()) if USAGE in self.folded else None
            parts = [(f"{row['name']} ", "muted")] + figures(row, bars=False, short=True) if row else []
            parts = parts + [("  ", "muted"), (OPENS, "muted")] if parts else [(OPENS, "muted")]
            if sum(width(words) for words, _ in parts) > room:
                parts = [(OPENS, "muted")]
        elif what["summary"]:
            parts = [part for n, one in enumerate(what["summary"])
                     for part in [("  ", "muted")] * bool(n) + [(one["text"], STATE_ROLE[one["tone"]])]]
        else:
            parts = [(SWATCH, PART_ROLE[what["swatch"]]), (f" {what['cost']}", "muted")] if what["cost"] else []
        if what["id"] == RULES and self.agent() == "claude":       # a rule added from its head
            end -= width(PLUS) + 2
            room -= width(PLUS) + 2
            canvas.put(y, end + 2, PLUS, Style(fg="text" if self.hover == ("add", None) else faint, bg=bg))
            canvas.region(y, end + 1, cells, ("add", None))
        if sum(width(words) for words, _ in parts) <= room:
            self.right(canvas, y, end, parts, bg)
            if what["id"] == USAGE:
                canvas.region(y, end - width(OPENS), end, ("opens", None))

    def row(self, canvas, y, key, row, column, bg):
        """A row: its mark under its section's title (one being checked or signing in spins there), its name (dim
        where it does not run here; a connector's after its brand) and note, what it states and its tag in the view's
        columns."""
        cells, x, faint = canvas.width, self.columns(), grey(bg)
        state_end, tags = column
        state = stated(row)
        if server_of(key) in self.checking or (state or {}).get("tone") == "busy":
            canvas.put(y, x["title"], self.frame, Style(fg="accent", bg=bg))
        elif row["mark"] in MARKS:
            glyph, role = MARKS[row["mark"]]
            canvas.put(y, x["title"], glyph, Style(fg=role, bg=bg))
        if tags and row["tag"]:
            words = truncate(row["tag"], tags)
            canvas.put(y, cells - INSET - width(words), words, Style(fg=faint, bg=bg))
        name_x = self.name_x(key)
        if row["icon"] == "plug":                       # its brand between its mark and its name
            glyph, role = brand_cell(row, self.icons)
            canvas.put(y, x["name"], glyph, Style(fg=role, bg=bg))
        room = state_end - name_x                       # a tag's column keeps its two cells of air before it
        noted = state is not None and state is not row["state"]                   # its note in its state's column
        note = "" if noted or row["id"].startswith(CONFLICT) else row["note"] or ""    # or under it, or after its name
        least = 5 if noted else 1                       # a note there gives way to the name: what it is, first
        roomy = room - width(row["name"]) - 2 if noted else room - 3
        if state and roomy >= least:
            words = truncate(state["text"], roomy)
            role = STATE_ROLE.get(state["tone"], "muted")
            canvas.put(y, state_end - width(words), words, Style(fg=faint if role == "muted" else role, bg=bg))
            room -= width(words) + 2
        whole = row["name"] + (f" {note}" if note else "")
        if width(whole) > room:
            self.cut[key] = whole
        at = canvas.put(y, name_x, truncate(row["name"], max(1, room)), Style(fg=faint if row["dim"] else "text",
                                                                              bg=bg))
        if note and room - (at - name_x) > 2:
            canvas.put(y, at + 1, truncate(note, room - (at - name_x) - 1), Style(fg=faint, bg=bg))

    def usage_line(self, canvas, y, row, bg):
        """An agent of Usage: its name bold, its plan's word dim, at the right its figures (figures()): the bars go
        first where all do not fit, then the looser window, an API key's budget; with no reading, core's words."""
        x, end = self.columns()["name"], canvas.width - INSET
        at = canvas.put(y, x, truncate(row["name"], max(1, end - x)), Style(fg="text", bold=True, bg=bg))
        if row["plan"] and end - at > 1 + width(row["plan"]):
            at = canvas.put(y, at + 1, row["plan"], Style(fg=grey(bg), bg=bg))
        untold = [(row["untold"]["text"], "muted")] if row.get("untold") else []
        parts = next((one for one in (figures(row), figures(row, bars=False), figures(row, bars=False, short=True))
                      if sum(width(words) for words, _ in one) <= end - at - 2), []) or untold
        self.right(canvas, y, end, parts, bg)

    @staticmethod
    def right(canvas, y, end, parts, bg=None):
        """PARTS ([(words, role)]) drawn in their roles, ending at column END; muted ones readable on a lit row."""
        x = end - sum(width(words) for words, _ in parts)
        for words, role in parts:
            x = canvas.put(y, x, words, Style(fg=grey(bg) if role == "muted" else role, bg=bg))

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
        """The chosen item's buttons from column X as blocks, a cell of air round each label, two cells apart: Connect
        lit as the accent's button; lit under the mouse."""
        end = canvas.width - INSET
        for n, one in enumerate(actions):
            words = truncate(one["label"], max(1, end - x - 2))
            if x + width(words) + 2 > end:
                break
            pointed = self.hover == ("action", n)
            bg = "button" if one["id"] == "connect" else "hover" if pointed else "input"
            canvas.chip(y, x, width(words) + 2, bg)
            canvas.put(y, x + 1, words, Style(fg="button_text", bg=bg, bold=True) if bg == "button" else Style(
                fg="text" if pointed else "subtext", bg=bg))
            canvas.region(y, x, x + width(words) + 2, ("action", n))
            x += width(words) + 4

    # --- More's lines, the form a connector is added with under Connectors' head

    def menu_lines(self):
        """What More lists first while this view shows (connectors.html's ⋯ menu): the Usage and Runs views and the
        graph, the ways to add a connector, a read of the setup; none where no setup shows."""
        if not self.shows():
            return []
        ways = [WAYS[way["id"]] for way in (self.adds() or {}).get("menu", ()) if way["id"] in WAYS]
        return [OPEN_USAGE] * bool(self.usage()[0]) + [OPEN_RUNS] + [SHOW_GRAPH] * self.graphs() + ways + [REFRESH]

    def menu_pick(self, choice):
        """More's line CHOICE done: the Usage view, the graph, claude.ai's page in the browser, the form opened, the
        setup read again."""
        if choice == OPEN_USAGE:
            return Action("open_usage", ())
        if choice == OPEN_RUNS:
            return Action("open_runs", ())
        if choice == SHOW_GRAPH:
            return Action("show_graph", ())
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
        self.chosen, self.follow, self.menu, self.edit = ("section", CONNECTORS), True, None, None

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
        """A row cut short: its name and note whole; an error: the files it named."""
        if isinstance(target, tuple) and target[0] == "layer":
            return self.cut.get(target[1])
        return target[1] if isinstance(target, tuple) and target[0] == "tip" else None

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
        if self.edit and self.edit.entered:
            return self.edited(self.edit.handle(event))
        keys = [key for key, _ in self.items()]
        if not keys:
            return None
        at = keys.index(self.chosen) if self.chosen in keys else 0
        name, kind = event.name, (self.chosen or (None,))[0]
        typed = event.char if name == "char" and not (event.ctrl or event.alt) else None
        if name in ("up", "down", "pageup", "pagedown", "home", "end"):
            step = {"up": -1, "down": 1, "pageup": -10, "pagedown": 10, "home": -len(keys), "end": len(keys)}[name]
            self.choose(keys[max(0, min(len(keys) - 1, at + step))])
        elif name == "right" and kind == "section":
            if self.chosen[1] in self.folded:
                return self.fold(self.chosen[1])
            if at + 1 < len(keys) and keys[at + 1][0] != "section":
                self.choose(keys[at + 1])
        elif name == "left" and kind == "section":
            return None if self.chosen[1] in self.folded else self.fold(self.chosen[1])
        elif name == "left" and kind in ("row", "more", "usage", "group"):
            self.choose(next(key for key in reversed(keys[:at]) if key[0] == "section"))
        elif name == "right" and self.edit:
            self.edit.enter()
        elif name == "enter":
            return self.activate()
        elif typed == ADD_KEY and self.agent() == "claude" and (dict(self.items())[self.chosen][0] or {}).get(
                "id") == RULES:
            self.open_rule()
        elif typed == ADD_KEY and self.adds():
            self.open_form()
        elif typed == REMOVE_KEY and self.edit and (self.edit.plan or {}).get("remove"):
            self.edit.entered = True
            self.edit.remove()
        elif typed == UNDO_KEY and self.foot:
            return Action("undo_harness", (self.foot["undo"],))
        elif name == "esc":
            self.foot = None
        elif typed == USAGE_KEY and self.usage()[0]:
            return Action("open_usage", ())
        elif typed == RUNS_KEY and self.shows():
            return Action("open_runs", ())
        elif typed == GRAPH_KEY and self.graphs():
            return Action("show_graph", ())
        return None

    def shows(self):
        """Whether the agent's setup shows: read, and not where it stands in its place (not installed, signed out)."""
        return bool(self.answer) and not self.standing() and bool(self.answer.get("sections"))

    def graphs(self):
        """Whether the agent shown has a graph to show: one whose setup shows, of those graph.py draws (READ)."""
        return self.shows() and self.agent() in READ

    def choose(self, key):
        self.chosen, self.follow, self.menu = key, True, None
        self.reopen()

    def fold(self, section):
        """SECTION folded or opened, its chevron turning; the sections folded kept (settings.json). An empty one has
        nothing to fold."""
        found = next((one for one in self.sections() if one["id"] == section), None)
        if found is not None and not (found["rows"] or found["groups"]):
            return None
        widgets.TURNS.turn(("agent", section))
        self.folded ^= {section}
        self.more.discard(section)
        self.follow = True
        return Action("remember_agent_folded", (sorted(self.folded),))

    def activate(self):
        """Enter: a section folded or opened (Usage's too); "N more" opened in place, its first new row chosen; the
        chosen item's first action this client can do, else the keys into its form."""
        kind, name = self.chosen or (None, None)
        if kind == "head":
            return self.open_list()
        if kind == "offer":
            return self.offer(name)
        if kind == "section":
            return self.fold(name)
        if kind == "more":
            part = next(part for section in self.sections() for part in parts_of(section) if part["id"] == name)
            before = {row["id"] for row in self.shown(part)[0]}
            self.more.add(name)
            self.choose(("row", next(row["id"] for row in part["rows"] if row["id"] not in before)))
            return None
        does = self.actions()
        if not does and self.edit:
            self.edit.enter()
        return self.act(does[0]) if does else None

    def act(self, one):
        """What action ONE asks the family for: a file opened, the Usage view, the graph, the agent's own command on
        its server."""
        kind = one["id"]
        if kind == "open":
            return Action("open_setup", (one["path"],))
        if kind == "usage":
            return Action("open_usage", ())
        if kind == "graph":
            return Action("show_graph", ())
        return Action(ASKS[kind], (one["server"],))

    def pick(self, words):
        popup, self.menu = self.menu, None
        if isinstance(popup.menu, AgentMenu):
            return self.picked(words)
        return next((self.act(one) for one in self.actions() if one["label"] == words), None)

    def open_list(self):
        """The agents' list under the head (agent_choices()): a check on the one shown, the looked-at one first."""
        choices = agent_choices((self.answer or {}).get("agents"), self.looking or self.answer.get("agent"))
        menu = AgentMenu(choices, glyphs(self.icons)["check"], LOADING_AGENTS)
        menu.index = next((n for n, one in enumerate(choices) if one["check"]), 0)
        self.menu = Popup(menu, "agents", self.head_y + 1, INSET)

    def picked(self, choice):
        """CHOICE made in the agents' list: an agent, the whole view its own (the app keeps it); one not installed,
        looked at alone: how it is installed in the setup's place."""
        self.looking = choice["key"] if choice["kind"] == "install" else None
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
                target if isinstance(target, tuple) and target[0] in ("action", "form", "edit", "add", "undo") \
                else None
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
            does = self.actions()
            return self.act(does[key]) if key < len(does) else None
        if kind == "opens":
            return Action("open_usage", ())
        if kind == "edit":
            return self.edited(self.edit.press(key)) if self.edit else None
        if kind == "add":
            return self.open_rule()
        if kind == "undo":
            return Action("undo_harness", (self.foot["undo"],)) if self.foot else None
        if kind != "layer":
            return None
        self.choose(key)
        if event.button == 2 and key[0] in ("row", "usage"):     # what can be done on it, there
            does = self.actions()
            self.menu = Popup(Menu([one["label"] for one in does]), None, event.y, event.x) if does else None
            return None
        return self.activate() if event.button == 0 and key[0] in ("section", "more", "head", "offer") else None

    # --- what a new version needs

    def kept(self):
        return {"chosen": list(self.chosen) if self.chosen else None, "more": sorted(self.more)}

    def take(self, kept):
        chosen = kept.get("chosen")
        if isinstance(chosen, list) and len(chosen) == 2 and all(isinstance(part, str) for part in chosen):
            self.chosen = tuple(chosen)
        self.more.update(name for name in kept.get("more") or () if isinstance(name, str))
