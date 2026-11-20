"""herdr-fold's Usage view in the TUI (the Agent view's Usage head opens it over the tab), as usage.html's TUI usage
pane: core's report (report.py) in cells: the period's and the agents' chips, the summary, each day by model, a month
against its budget (Enter edits the budget), the projects, conversations and models. ↑ ↓ scroll, Esc closes."""
import os
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_state  # noqa: E402
import commits  # noqa: E402
import preview  # noqa: E402
import report  # noqa: E402
import statefile  # noqa: E402
import tokens  # noqa: E402
import usage  # noqa: E402
from icons import glyphs  # noqa: E402
from layers import PERIODS, READING, SPARK, commits_said, day_color, period_said  # noqa: E402
from loop import Loop  # noqa: E402
from prices import money, short  # noqa: E402
from screen import INSET, SPIN, SPINNER, Canvas, Style, icons_on, truncate, width  # noqa: E402
from settings import CLOSE_CELLS, CLOSE_TIP, TIP_DELAY  # noqa: E402
from vt import Focus, Key, Mouse  # noqa: E402
from widgets import TextInput, wrap  # noqa: E402

PERIOD_ENV = "HERDR_FOLD_USAGE_PERIOD"        # the period it opens on, as the Agent view's Usage had it
POLL = 60.0                   # seconds between two reads while open
AGENTS = (None, *usage.AGENTS)                # the agents' chips: every one, then each
ALL = "All agents"
LOADING, FAILED = "Loading usage…", "Couldn't read the usage"
CHART = 5                     # rows of a day's column, an eighth of a row its least step
MONTH = 24                    # cells of a month's bar: its budget, or its pace where that is more
PACE = "│"                    # where the month's pace ends, on its bar
DAY_STEPS = (1, 2, 5, 10, 15)  # days between two of a month's named days: the smallest that fits
SWATCH = "■"                  # a model's color before its name
NAME, SPACE, AGENT = 20, 14, 20               # cells a project's name, a conversation's space, a model's agent keep
WIDE = 90                     # cells from which the tables show every column
BUDGET, PER_MONTH = "Monthly budget", "a month"     # the budget's form, as the Herdr app's
SAVE, CANCEL = "Save", "Cancel"
AMOUNT = 12                   # cells of a budget's field
HEADS = {"conversations": ("space", "turns", "tokens", "cache", "cost", "commits"),
         "models": ("agent", "input", "write", "read", "output", "cost")}       # the tables' columns, on their heads
TEXTS = ("space", "agent")    # the columns of names, left-aligned: every other is a figure


def figures(period, agents, theme, home, agent=None, state=None):
    """On a job's thread: what the agents cost in PERIOD (AGENT's alone), {"report": core's, "left": the bytes of
    conversations still to read}: the token and commit indexes each brought on by one look (core bounds it), then the
    report from them; AGENTS the agents' list (their plans), THEME the pane's ground and text (the models' colors)."""
    state = state or statefile.folder()
    left = tokens.index(state, home)["left"] + commits.index(state, home)["left"]
    return {"report": report.report(state, home, period, agent, agents=agents, theme=theme), "left": left}


def chart(daily, rows=CHART):
    """DAILY (the report's) as columns of ROWS cells, the lowest first, each (block, its color, the color over it):
    a day's models stacked in the legend's order, the costliest day ROWS high, a day with any cost never empty."""
    top, units, found = max([day["total"] for day in daily] + [0]), rows * 8, []
    for day in daily:
        spans, sum_, before = [], 0.0, 0
        for one in day["models"]:
            sum_ += one["cost"]
            upto = round(units * sum_ / top) if top else 0
            if upto > before:
                spans.append((before, upto, one["color"]))
                before = upto
        if day["total"] > 0 and not spans:
            spans = [(0, 1, day_color(day))]
        column, whole = [], spans[-1][1] if spans else 0
        for n in range(rows):
            low, high = 8 * n, min(whole, 8 * n + 8)
            inside = [(max(a, low), min(b, high), color) for a, b, color in spans if a < high and b > low]
            if not inside:
                column.append((" ", None, None))
            elif len(inside) == 1:
                column.append((SPARK[high - low], inside[0][2], None))
            elif high - low == 8:                       # two models meet in a whole cell: the upper one its ground
                column.append((SPARK[inside[0][1] - low], inside[0][2], inside[1][2]))
            else:                                       # in the column's top cell: the larger part's color
                column.append((SPARK[high - low], max(inside, key=lambda one: one[1] - one[0])[2], None))
        found.append(column)
    return found


def day_labels(daily, pitch):
    """The days' numbers under their columns PITCH cells apart, [(column, number)], as the app's axisLabels: the last
    day, the first and each month's 1st always; between them a month's days at the smallest of DAY_STEPS that fits
    (1 3 5, 1 5 10 15); each a cell clear of the next, the one named first giving way last."""
    numbers = [day["label"].split()[-1] for day in daily]
    clear = max([len(number) for number in numbers] + [1]) + 1
    step = next((step for step in DAY_STEPS if step * pitch >= clear), None)
    ends = {len(numbers) - 1: 0, 0: 1}
    ranked = sorted(range(len(numbers)), key=lambda n: (ends.get(n, 2 if numbers[n] == "1" else 3), n))
    found = {}
    for n in ranked:
        if n not in ends and numbers[n] != "1" and not (step and numbers[n].isdigit()
                                                        and int(numbers[n]) % step == (step == 2)):
            continue
        if all((n - other) * pitch > len(numbers[other]) if other < n else (other - n) * pitch > len(numbers[n])
               for other in found):
            found[n] = (n * pitch, numbers[n])
    return [found[n] for n in sorted(found)]


def pace_bar(month, cells=MONTH):
    """A month against its budget in CELLS: (the cells spent, the cells the budget takes, the cell its pace ends in),
    the whole the budget, or the pace where that is more."""
    scale = max(month["budget"], month["pace"], month["today"])
    spent = min(cells, max(1 if month["today"] > 0 else 0, round(cells * month["today"] / scale)))
    return spent, max(1, round(cells * month["budget"] / scale)), min(cells - 1, int(cells * month["pace"] / scale))


class Row:
    """A line of the view: what it puts where, what answers a press there."""

    def __init__(self):
        self.parts, self.regions, self.field = [], [], None

    def put(self, x, words, style=Style(fg="text")):
        self.parts.append((x, words, style))
        return x + width(words)

    def right(self, end, words, style=Style(fg="text")):
        self.parts.append((end - width(words), words, style))
        return end - width(words)

    def draw(self, canvas, y):
        for x, words, style in self.parts:
            canvas.put(y, x, words, style)
        for x0, x1, target in self.regions:
            canvas.region(y, x0, x1, target)
        if self.field:
            field, x, focused = self.field
            field.draw(canvas, y, x, AMOUNT, 1, Style(fg="text", bg="input"), focused)


class UsageView(Loop):
    def __init__(self, terminal, herdr, state_dir, clock=time.monotonic, period=None, home=None, state=None):
        super().__init__(terminal, herdr, state_dir, clock)
        self.period = period if period in PERIODS else PERIODS[0]
        self.agent = None                 # the agent it is narrowed to: None for every one
        self.home, self.state = home or os.path.expanduser("~"), state or statefile.folder()
        self.icons = icons_on(state_dir)
        self.report = self.agents = None  # core's report and agents' list, as last read
        self.budgets = {}                 # each agent's budget, as core keeps it
        self.reading = False              # conversations still being read
        self.failed = None                # why the last read gave nothing
        self.read_at = None
        self.top = 0                      # the first line shown under the chips
        self.form = None                  # the budget's form: {"fields": {agent: TextInput}, "at", "error"}
        self.pointed = None
        self.over, self.tip = None, False      # since when the mouse rests on the close button; its tip drawn
        self.height, self.count = 1, 0    # the body's rows and its lines, as last drawn
        self.ask()

    # --- reading

    def ask(self):
        """The report read on a job's thread (the agents told once, kept by core); once more when asked while that
        runs, so the last choice lands last."""
        self.read_at = self.clock()
        if "report" in self.running:
            self.again.add("report")
            return
        period, agent, home, state, agents = self.period, self.agent, self.home, self.state, self.agents
        colors = self.renderer.theme.colors            # button_text is the pane's own ground (the theme setter's)
        theme = (colors.get("button_text"), colors.get("text"))

        def work():
            told = agents or agent_state.machine_agents(home)
            return {**figures(period, told, theme, home, agent, state), "agents": told,
                    "budgets": report.budget(state), "asked": (period, agent)}

        self.job("report", work, self.got)

    def got(self, found):
        again = "report" in self.again
        self.again.discard("report")
        if found and found["asked"] == (self.period, self.agent):
            self.report, self.agents, self.budgets = found["report"], found["agents"], found["budgets"]
            self.reading, self.failed = bool(found["left"]), None
        if again or found and found["left"]:
            self.ask()

    def collect(self):
        """A read that failed says so in the report's place (the loop's error line is the sidebar's)."""
        answered = super().collect()
        if self.error:
            self.failed, self.error = self.error, None
        return answered

    def keyed(self):
        """The agents a budget can be set for: the ones on an API key, as the agents' list tells them."""
        return [one for one in self.agents or () if one.get("plan") == report.API_KEY and one["key"] in usage.AGENTS]

    # --- what it does

    def handle(self, event):
        if isinstance(event, Focus):
            self.quit = self.quit or not event.gained    # a click outside: the pane clicked has the keys now
        elif isinstance(event, Key):
            self.key(event)
        elif isinstance(event, Mouse):
            target = self.canvas.hit(event.x, event.y) if self.canvas else None
            if event.kind == "move":
                if (target == "close") != (self.pointed == "close"):
                    self.over, self.tip = (self.clock() if target == "close" else None), False
                self.pointed = target
            elif event.kind in ("wheel_up", "wheel_down"):
                self.scroll(3 if event.kind == "wheel_down" else -3)
            elif event.kind == "press" and event.button == 0 and target:
                self.press(target)

    def key(self, key):
        if self.form:
            return self.form_key(key)
        name = key.char if key.name == "char" and not (key.ctrl or key.alt) else key.name
        if name in ("esc", "q") or (key.name == "char" and key.ctrl and key.char == "c"):
            self.quit = True
        elif name in ("tab", "backtab"):
            step = -1 if name == "backtab" else 1
            self.choose(period=PERIODS[(PERIODS.index(self.period) + step) % len(PERIODS)])
        elif name == "a":
            self.choose(agent=AGENTS[(AGENTS.index(self.agent) + 1) % len(AGENTS)])
        elif name in ("up", "down", "pageup", "pagedown", "home", "end"):
            self.scroll({"up": -1, "down": 1, "pageup": -self.height, "pagedown": self.height,
                         "home": -self.count, "end": self.count}[name])
        elif name == "enter" and self.keyed():
            self.open_form()
        return None

    def choose(self, **chosen):
        """Another period or agent: its report read, from its top."""
        for name, value in chosen.items():
            setattr(self, name, value)
        self.top = 0
        self.ask()

    def scroll(self, rows):
        self.top = max(0, min(self.top + rows, self.count - self.height))

    def press(self, target):
        if target == "close":
            self.quit = True
        elif target == "budget":
            self.open_form()
        elif isinstance(target, tuple) and target[0] == "period" and target[1] != self.period:
            self.choose(period=target[1])
        elif isinstance(target, tuple) and target[0] == "agent" and target[1] != self.agent:
            self.choose(agent=target[1])
        elif isinstance(target, tuple) and target[0] == "form" and self.form:
            if target[1] == "save":
                self.save()
            elif target[1] == "cancel":
                self.form = None
            else:
                self.form["at"] = target[1]

    # --- the budget (kept in herdr-fold's own state: nothing of an agent's is written)

    def open_form(self):
        """The budget's form in the month's place: a field for each agent on an API key, with what core keeps."""
        fields = {}
        for one in self.keyed():
            kept, fields[one["key"]] = self.budgets.get(one["key"]), TextInput()
            fields[one["key"]].insert("" if not kept else str(kept) if kept == int(kept) else f"{kept:.2f}")
        if fields:
            self.form = {"fields": fields, "at": next(iter(fields)), "error": None, "shown": False}

    def form_key(self, key):
        """A key in the form: Tab and ↓ step on, Shift+Tab and ↑ back; a field takes what is typed; Enter saves (on
        Cancel: leaves); Esc leaves."""
        form, at = self.form, self.form["at"]
        stops = [*form["fields"], "save", "cancel"]
        if key.name == "esc" or (key.name == "enter" and at == "cancel"):
            self.form = None
        elif key.name in ("tab", "down", "backtab", "up"):
            form["at"] = stops[(stops.index(at) + (1 if key.name in ("tab", "down") else -1)) % len(stops)]
        elif key.name == "enter":
            self.save()
        elif at in form["fields"] and form["fields"][at].handle(key):
            form["error"] = None
        return None

    def save(self):
        """The form's amounts kept by core (an empty field: no budget); one that is no amount said under them."""
        typed = {agent: field.text.strip() for agent, field in self.form["fields"].items()}
        names = {one["key"]: one["name"] for one in self.keyed()}
        for agent, text in typed.items():
            if text and not report.AMOUNT.fullmatch(text):
                self.form.update(error=f"{names.get(agent, agent)}'s is not an amount", at=agent)
                return
        try:
            for agent, text in typed.items():
                self.budgets = report.set_budget(self.state, agent, text)
        except (OSError, ValueError) as err:
            self.form["error"] = str(err) if isinstance(err, OSError) else f"{names.get(agent, agent)}'s is not an " \
                "amount"
            return
        self.form = None
        self.ask()

    # --- the loop's

    def tick(self):
        """The report read again when due; the spinner's next frame, the close button's tip come due."""
        now = self.clock()
        if now >= self.read_at + POLL and not self.form:
            self.ask()
        due = self.over is not None and not self.tip and now >= self.over + TIP_DELAY
        self.tip = self.tip or due
        return self.report is None or self.reading or due

    def deadlines(self):
        tip = [self.over + TIP_DELAY] if self.over is not None and not self.tip else []
        spin = [self.clock() + SPIN] if self.report is None and not self.failed or self.reading else []
        return tip + spin + [self.read_at + POLL]

    # --- drawing

    def draw(self):
        cells, rows = self.term.size()
        canvas = Canvas(cells, rows)
        head = self.chips(canvas)
        lines = self.lines(cells)
        self.count, self.height = len(lines), max(1, rows - head - 1)
        at = next((n for n, line in enumerate(lines) if line.field), None)
        if self.form and at is not None and not self.form["shown"]:     # the form just opened: all of it in view
            last = at + len(self.form["fields"]) + 1
            self.top = at - 1 if at - 1 < self.top else max(self.top, last + 1 - self.height)
            self.form["shown"] = True
        self.scroll(0)
        for n, line in enumerate(lines[self.top:self.top + self.height]):
            line.draw(canvas, head + 1 + n)
        if self.tip:                                  # under the button at its right edge, as the sidebar's tips
            words = f" {CLOSE_TIP} "
            canvas.put(1, cells - len(words), words, Style(fg="text", bg="selection"))
        self.canvas = canvas
        self.term.write(self.renderer.frame(canvas))
        self.term.flush()

    def chip(self, canvas, y, x, words, target, lit):
        """A chip at X: the chosen one on the accent, the one under the mouse on the hover's. Its end."""
        bg = "button" if lit else "hover" if self.pointed == target else None
        if bg:
            canvas.chip(y, x, width(words) + 2, bg)
        canvas.put(y, x + 1, words, Style(fg="button_text", bg=bg, bold=True) if lit else Style(
            fg="text" if bg else "subtext", bg=bg))
        canvas.region(y, x, x + width(words) + 2, target)
        return x + width(words) + 2

    def chips(self, canvas):
        """The periods' chips, then the agents' (under them where one row has no room for both), the close button at
        the right; the rows they take."""
        cells, corner = canvas.width, canvas.width - CLOSE_CELLS
        lit = self.pointed == "close"
        canvas.put(0, corner, f" {glyphs(self.icons)['close']} ", Style(fg="text" if lit else "subtext",
                                                                        bg="hover" if lit else None))
        canvas.region(0, corner, cells, "close")
        x = INSET
        for period in PERIODS:
            x = self.chip(canvas, 0, x, period_said(period), ("period", period), period == self.period) + 1
        told = {one["id"]: one["label"] for one in (self.report or {}).get("filters", {}).get("agents", ())}
        names = [(agent, told.get(agent) or (usage.NAMES[agent] if agent else ALL)) for agent in AGENTS]
        y = 0 if x + 2 + sum(width(name) + 3 for _, name in names) - 1 <= corner else 1
        x = x + 2 if y == 0 else INSET
        for agent, name in names:
            x = self.chip(canvas, y, x, name, ("agent", agent), agent == self.agent) + 1
        return y + 1

    def lines(self, cells):
        """Every line under the chips, in the report's order; before a report, what stands in its place."""
        found = self.report
        if found is None or found["none"]:
            row = Row()
            if self.failed:
                row.put(INSET, truncate(f"{FAILED}: {self.failed}", cells - 2 * INSET), Style(fg="deleted"))
            elif found is None or self.reading:
                frame = SPINNER[int(self.clock() / SPIN) % len(SPINNER)]
                row.put(INSET, f"{frame} {LOADING if found is None else READING}", Style(fg="muted"))
            else:
                row.put(INSET, found["none"], Style(fg="muted"))
            return [row] + ([Row()] + self.budget_form(cells) if self.form else [])
        end, words = cells - INSET, found["words"]
        lines = self.summary(found, end)
        if any(day["total"] for day in found["daily"]):
            lines += [Row()] + self.per_day(found, end)
        for month in found["months"]:
            lines += [Row()] + self.month(found, month, end)
        if self.form and not found["months"]:
            lines += [Row()] + self.budget_form(cells)
        if found["projects"]:
            lines += [Row(), self.title(end, words["projects"], words["projects_note"])] + self.projects(found, end)
        lines += [Row()] + self.conversations(found, end, cells >= WIDE)
        lines += [Row()] + self.models(found, end, cells >= WIDE)
        lines.append(Row())
        for start, stop in wrap(words["foot"], max(1, end - INSET)):
            lines.append(Row())
            lines[-1].put(INSET, words["foot"][start:stop].rstrip(), Style(fg="muted"))
        if self.reading:
            frame = SPINNER[int(self.clock() / SPIN) % len(SPINNER)]
            lines.append(Row())
            lines[-1].put(INSET, f"{frame} {READING}", Style(fg="muted"))
        return lines

    @staticmethod
    def title(end, words, note="", role="muted"):
        """A block's head: its name bold, a few words about it dim at the right."""
        row = Row()
        at = row.put(INSET, words, Style(fg="text", bold=True))
        if note and end - at - 2 > 0:
            row.right(end, truncate(note, end - at - 2), Style(fg=role))
        return row

    def summary(self, found, end):
        """The summary as aligned rows: a cell's key left, its figure and unit from one column, its line dim under."""
        cells_, lines = found["summary"], []
        value = INSET + min(max(width(cell["key"]) for cell in cells_), max(8, end - INSET - 20)) + 2
        for cell in cells_:
            row = Row()
            row.put(INSET, truncate(cell["key"], value - INSET - 2), Style(fg="subtext"))
            at = row.put(value, cell["text"], Style(fg="text", bold=True))
            if cell.get("unit") and cell.get("value") is not None:
                row.put(at + 1, cell["unit"], Style(fg="muted"))
            lines.append(row)
            if cell.get("line"):
                lines.append(Row())
                lines[-1].put(INSET + 2, truncate(cell["line"], end - INSET - 2),
                              Style(fg="modified" if cell.get("over") else "muted"))
        return lines

    def per_day(self, found, end):
        """Per day, by model: the costliest day at the right of its head, CHART rows of stacked blocks a day, the
        days' numbers under them, the legend (each model's share) wrapped under those."""
        top = found["top"]
        lines = [self.title(end, found["words"]["daily"], f"top {money(top['total'], True)}, {top['label']}" if top
                            else "")]
        room = end - INSET - 2
        pitch = 2 if 2 * len(found["daily"]) - 1 <= room else 1
        daily = found["daily"][-room:]
        columns = chart(daily)
        for n in reversed(range(CHART)):
            row = Row()
            for at, column in enumerate(columns):
                block, color, over = column[n]
                if block != " ":
                    row.put(INSET + 2 + at * pitch, block, Style(fg=color, bg=over))
            lines.append(row)
        row = Row()
        for at, number in day_labels(daily, pitch):
            row.put(INSET + 2 + at, number, Style(fg="muted"))
        lines.append(row)
        row, x = Row(), INSET
        for one in found["legend"]:
            said = f"{one['name']} {one['share']}%"
            if x > INSET and x + 2 + width(said) > end:
                lines.append(row)
                row, x = Row(), INSET
            row.put(x, SWATCH, Style(fg=one["color"]))
            x = row.put(x + 2, said, Style(fg="subtext")) + 2
        return lines + [row]

    def month(self, found, month, end):
        """A month against its budget: its bar with the pace's mark, core's words for it (yellow once over), and
        Budget…, which opens its form under them; with no budget, the words alone."""
        head = found["words"]["month"] if month["budget"] else month["label"]
        lines, row, x = [self.title(end, head, month["key"])], Row(), INSET
        over = Style(fg="modified") if month["over"] else None
        if month["budget"]:
            room = end - x - 2 - width(month["line"])           # the bar gives way to its words, to half its cells
            cells = room if MONTH // 2 <= room < MONTH else MONTH
            spent, whole, pace = pace_bar(month, cells)
            for n in range(cells):
                block = PACE if n == pace and n >= spent else "▰" if n < spent else "▱" if n < whole else " "
                row.put(x + n, block, Style(fg="text") if block == PACE else over or Style(fg="added"))
            x += cells + 2
        if width(month["line"]) > end - x:              # a narrow pane: its words under its bar
            lines.append(row)
            row, x = Row(), INSET
        row.put(x, truncate(month["line"], end - x), over or Style(fg="subtext"))
        lines.append(row)
        if self.form:                                   # in Budget…'s place, under the first month alone
            return lines + (self.budget_form(end + INSET) if month is found["months"][0] else [])
        said, row = found["words"]["budget"], Row()
        bg = "hover" if self.pointed == "budget" else "input"
        row.put(INSET, f" {said} ", Style(fg="text" if bg == "hover" else "subtext", bg=bg))
        row.regions.append((INSET, INSET + width(said) + 2, "budget"))
        return lines + [row]

    def budget_form(self, cells):
        """The budget's form, as the Herdr app's: its title, each agent's field ("Codex  $ 50  a month"), why it was
        not taken, Save lit and Cancel."""
        form, at, names = self.form, self.form["at"], {one["key"]: one["name"] for one in self.keyed()}
        lines, label = [Row()], INSET + max([width(name) for name in names.values()] or [0]) + 2
        lines[0].put(INSET, BUDGET, Style(fg="text", bold=True))
        for agent, field in form["fields"].items():
            row = Row()
            row.put(INSET, names.get(agent, agent), Style(fg="text" if at == agent else "subtext"))
            row.put(label, "$", Style(fg="muted"))
            row.field = (field, label + 2, at == agent)
            row.put(label + 2 + AMOUNT + 1, PER_MONTH, Style(fg="muted"))
            row.regions.append((label, label + 2 + AMOUNT, ("form", agent)))
            lines.append(row)
        if form["error"]:
            lines.append(Row())
            lines[-1].put(INSET, truncate(form["error"], cells - 2 * INSET), Style(fg="deleted"))
        row, x = Row(), INSET
        for key, words in (("save", SAVE), ("cancel", CANCEL)):
            lit = key == "save"
            bg = "button" if lit else "hover" if at == key or self.pointed == ("form", key) else "input"
            row.put(x, f" {words} ", Style(fg="button_text", bg=bg, bold=True) if lit else Style(
                fg="text" if bg == "hover" else "subtext", bg=bg))
            row.regions.append((x, x + width(words) + 2, ("form", key)))
            x += width(words) + 3
        return lines + [row]

    def projects(self, found, end):
        """By project, in aligned columns: a name, a bar by the costliest one's cost (MONTH cells at most), the cost,
        its conversations' commits dim; in a narrow pane the commits go, then the bars."""
        projects = found["projects"]
        name = min(NAME, max(width(one["name"]) for one in projects))
        said = max(width(commits_said(one)) for one in projects)
        cost = max(width(self.cost(one)) for one in projects)
        if end - INSET - name - 2 - cost - 2 - said < 4:        # no room for both: the commits go
            said = 0
        most = max([one["cost"] or 0 for one in projects])
        room = min(MONTH, end - (said + 2 if said else 0) - cost - 2 - (INSET + name + 2))
        bars, lines = (room + 2 if room >= 4 else 0), []
        for one in projects:
            row, x = Row(), INSET + name + 2
            row.put(INSET, truncate(one["name"], name))
            if bars and one["cost"] and most:
                row.put(x, "▰" * max(1, round(room * one["cost"] / most)), Style(fg="muted"))
            row.right(x + bars + cost, self.cost(one), Style(fg="text" if one["cost"] is not None else "muted"))
            if said:
                row.put(x + bars + cost + 2, commits_said(one), Style(fg="muted"))
            lines.append(row)
        return lines

    def cost(self, one):
        return self.report["words"]["no_price"] if one["cost"] is None else money(one["cost"])

    @staticmethod
    def table(end, head, rows, least):
        """A table's lines: its HEAD's name bold and, dim, its columns' names over them; each of ROWS its first cell
        (parts, kept LEAST cells at least) left, the others in their columns two cells apart, figures right-aligned,
        names (TEXTS) left."""
        widths = [max([width(name)] + [width(row[1][n][0]) for row in rows]) for n, name in enumerate(head[1])]
        while widths and end - INSET - sum(size + 2 for size in widths) < least:      # the first columns go first
            widths, head, rows = widths[1:], (head[0], head[1][1:]), [(row[0], row[1][1:]) for row in rows]
        first, x = Row(), end
        for size, name in reversed(list(zip(widths, head[1]))):
            first.put(x - size, name, Style(fg="muted")) if name in TEXTS else first.right(x, name, Style(fg="muted"))
            x -= size + 2
        first.put(INSET, truncate(head[0], max(1, x - INSET)), Style(fg="text", bold=True))
        lines = [first]
        for parts, cells_ in rows:
            row, at = Row(), end
            for size, name, (words, role) in reversed(list(zip(widths, head[1], cells_))):
                row.put(at - size, words, Style(fg=role)) if name in TEXTS else row.right(at, words, Style(fg=role))
                at -= size + 2
            left = INSET
            for words, style in parts:
                words = truncate(words, max(0, at - left))
                left = row.put(left, words, style) + 1
            lines.append(row)
        return lines

    def conversations(self, found, end, wide):
        """Conversations, the most first: its title, cost and commits; in a wide pane its space, turns, tokens and
        the cache's share too."""
        words, rows = found["words"], []
        for one in found["conversations"]:
            cost = (self.cost(one), "text" if one["cost"] is not None else "muted")
            made = (one["commits_text"], "text" if one["commits"] else "muted")
            more = [(truncate(one["space"], SPACE), "subtext"), (str(one["turns"]), "subtext"),
                    (short(one["tokens"]), "subtext"), ("–" if one["cache"] is None else f"{one['cache']}%", "subtext")]
            rows.append(([(one["title"], Style(fg="text"))], (more if wide else []) + [cost, made]))
        head = (words["conversations"], HEADS["conversations"] if wide else HEADS["conversations"][-2:])
        lines = self.table(end, head, rows, 12)
        if found["more"]:
            lines.append(Row())
            lines[-1].put(INSET, f"+{found['more']} more", Style(fg="muted"))
        return lines

    def models(self, found, end, wide):
        """Models: each one's color and name, its tokens by kind, its cost; in a wide pane its agent too."""
        def count(n):
            return (short(n) if n else "–", "subtext")
        rows = [([(SWATCH, Style(fg=one["color"])), (one["name"], Style(fg="text"))],
                 ([(truncate(one["agent"], AGENT), "subtext")] if wide else [])
                 + [count(one[kind]) for kind in ("input", "write", "read", "output")]
                 + [(one["text"], "text" if one["cost"] is not None else "muted")]) for one in found["models"]]
        head = (found["words"]["models"], HEADS["models"] if wide else HEADS["models"][1:])
        return self.table(end, head, rows, 12)


def main():
    state = os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.join(
        os.path.expanduser("~"), ".local", "state", "herdr", "plugins", "herdr-fold.sidebar")
    if os.name == "nt":
        from keys_windows import WindowsTerminal as Terminal
    else:
        from keys_unix import UnixTerminal as Terminal
    UsageView(Terminal(), preview.Herdr(), state, period=os.environ.get(PERIOD_ENV)).run()


if __name__ == "__main__":
    main()
