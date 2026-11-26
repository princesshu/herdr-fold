"""herdr-fold's Runs view in the TUI (the Agent view's More opens it over the tab, r), as runs.html's TUI frames: core's
runs (runs.py) a row each under its day, the chosen one's properties under it, New run's form over the list. ↑ ↓ step,
Enter opens a run or presses its button (← → pick one), n New run, o opens a file it made, Esc closes."""
import os
import shlex
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_state  # noqa: E402
import media  # noqa: E402
import preview  # noqa: E402
import runs  # noqa: E402
from icons import glyphs  # noqa: E402
from loop import Loop  # noqa: E402
from screen import CONTENT, INSET, SPIN, SPINNER, Canvas, Style, icons_on, truncate, width  # noqa: E402
from settings import CLOSE_CELLS  # noqa: E402
from usage_view import Row  # noqa: E402
from vt import Focus, Key, Mouse  # noqa: E402
from widgets import TextInput, wrap  # noqa: E402

POLL, QUICK = 30.0, 5.0       # seconds between two reads while open; while a run works
AGENTS = (None, "claude", "codex")
NAMES = {None: "All agents", **runs.NAMES}
LOADING, FAILED = "Loading runs…", "Couldn't read the runs"
NONE = "No runs yet: n starts one in the background"
KEYS = "n New run · o opens a file · Esc closes"
FORM_KEYS = "Esc cancels · Tab the next"
LABEL = 8                     # cells of a property's label (Ran as, Folder, Prompt…)
AGENT, TIME, MADE, COST = 6, 5, 10, 6         # cells of a row's columns after its name
LEAST = 12                    # cells a run's name keeps: past it the agent's and the time's columns go
PROMPT_ROWS = 3               # rows of the form's prompt
# the form's stops in order, Tab's: each a choice (← → change it) but the prompt and Start
STOPS = ("agent", "prompt", "where", "env", "when", "start")
LABELS = {"agent": "Agent", "prompt": "Prompt", "where": "Where", "env": "Env", "when": "When"}
WHERE = (("here", "This Mac"), ("cloud", "Cloud"))
WHEN = (("now", "Now"), ("schedule", "On a schedule"))
MARKS = {"failed": ("✕", "deleted"), "blocked": ("●", "modified")}


def form_note(form, into):
    """The words under New run's choices: what starts where (the app's runs.js formNote)."""
    if form["agent"] == "claude" and form["when"] == "schedule":
        return "Claude keeps schedules in the cloud. A new chat opens with /schedule and your words; Claude asks the " \
               "rest there. Its runs are not listed here."
    if form["agent"] == "codex" and form["when"] == "schedule":
        return "Codex schedules only in its own app."
    if form["agent"] == "claude":
        return "Runs on this Mac in the background; Attach shows it as it works, Stop ends it."
    return f"Codex makes a diff in the cloud; Apply brings it into {into}" if form["where"] == "cloud" else \
        "Runs on this Mac with codex exec, on its own; it shows here as it works."


def actions(run, into):
    """The buttons RUN's properties offer, [(id, label)], as the app's runActions."""
    live, cloud = run["state"] in runs.LIVE, run["kind"] == "cloud"
    return ([("attach", "Attach"), ("stop", "Stop")] if run["kind"] == "background" and live else []) \
        + ([("chat", "Open as chat"), ("again", "Run again")] if not cloud and not live else []) \
        + ([("diff", "Show diff")] if cloud and run["state"] in ("ready", "applied") else []) \
        + ([("apply", f"Apply to {into}")] if cloud and run["state"] == "ready" else []) \
        + ([("again", "Run again")] if cloud and run["state"] == "failed" else []) \
        + ([("pr", f"Open PR #{run['pr']['number']}")] if run.get("pr") else []) \
        + ([("web", "Open on the web")] if cloud and run.get("url") else []) \
        + ([("remove", "Remove")] if run["kind"] == "background" and not live else [])


class RunsView(Loop):
    def __init__(self, terminal, herdr, state_dir, clock=time.monotonic, folder=None, home=None):
        super().__init__(terminal, herdr, state_dir, clock)
        self.folder = folder or os.getcwd()          # the tab's: a new run's
        self.into = os.path.basename(self.folder.rstrip(os.sep))
        self.home = home or os.path.expanduser("~")
        self.icons = icons_on(state_dir)
        self.answer = self.agents = None   # core's runs, and the agents' list (their plans), as last read
        self.failed = None                 # why the last read gave nothing
        self.read_at, self.fresh = None, False
        self.agent = None                  # the agent it is narrowed to: None for every one
        self.cursor = 0                    # the run the keys are on, in the list's order
        self.chosen = None                 # the run whose properties show, by its key
        self.button = 0                    # the chosen run's button the keys are on
        self.form = None                   # New run's: {"agent", "where", "when", "env", "at", "note", "busy"}
        self.prompt = TextInput(multiline=True, placeholder="What the agent should do")
        self.said = None                   # what an action did, or why it did not: (words, failed)
        self.pointed = None
        self.top, self.height, self.count = 0, 1, 0
        self.field_at = None               # the form's prompt's first line, as last drawn
        self.ask()

    # --- reading

    def ask(self, fresh=False):
        """The runs read on a job's thread (FRESH: the agents asked again, after an action); once more when asked while
        that runs."""
        self.read_at, self.fresh = self.clock(), self.fresh or fresh
        if "runs" in self.running:
            self.again.add("runs")
            return
        home, agents, asked = self.home, self.agents, self.fresh
        self.fresh = False

        def work():
            told = agents or agent_state.machine_agents(home)
            return {"runs": runs.runs(told, asked), "agents": told}

        self.job("runs", work, self.got)

    def got(self, found):
        if found:
            self.answer, self.agents, self.failed = found["runs"], found["agents"], None
        if "runs" in self.again:
            self.again.discard("runs")
            self.ask()

    def collect(self):
        """A read that failed says so in the list's place; an action's failure on its line."""
        answered = super().collect()
        if self.error:
            if self.answer is None:
                self.failed = self.error
            else:
                self.said = (self.error, True)
            self.error = None
        return answered

    def shown(self):
        return [one for one in (self.answer or {}).get("runs", ()) if not self.agent or one["agent"] == self.agent]

    # --- what it does

    def handle(self, event):
        if isinstance(event, Focus):
            self.quit = self.quit or not event.gained
        elif isinstance(event, Key):
            self.key(event)
        elif isinstance(event, Mouse):
            target = self.canvas.hit(event.x, event.y) if self.canvas else None
            if event.kind == "move":
                self.pointed = target
            elif event.kind in ("wheel_up", "wheel_down"):
                self.scroll(3 if event.kind == "wheel_down" else -3)
            elif event.kind == "press" and event.button == 0 and target:
                self.press(target)

    def key(self, key):
        if self.form:
            return self.form_key(key)
        name = key.char if key.name == "char" and not (key.ctrl or key.alt) else key.name
        listed, run = self.shown(), self.chosen_run()
        if name == "esc" and run:
            self.chosen = None
        elif name in ("esc", "q") or (key.name == "char" and key.ctrl and key.char == "c"):
            self.quit = True
        elif name in ("up", "down") and listed:
            self.cursor = max(0, min(len(listed) - 1, self.cursor + (1 if name == "down" else -1)))
            self.chosen = None if self.chosen != listed[self.cursor]["key"] else self.chosen
        elif name in ("left", "right") and run:
            self.button = max(0, min(len(actions(run, self.into)) - 1, self.button + (1 if name == "right" else -1)))
        elif name == "enter" and run and actions(run, self.into):
            self.act(actions(run, self.into)[self.button][0], run)
        elif name == "enter" and listed:
            self.choose(listed[min(self.cursor, len(listed) - 1)]["key"])
        elif name == "tab":
            self.agent = AGENTS[(AGENTS.index(self.agent) + 1) % len(AGENTS)]
            self.cursor, self.chosen = 0, None
        elif name == "n":
            self.open_form()
        elif name == "o" and run and run["files"]:
            self.open_file((run["media"][0]["path"] if run["media"] else run["files"][0]))
        elif name in ("pageup", "pagedown"):
            self.scroll(self.height if name == "pagedown" else -self.height)
        return None

    def chosen_run(self):
        return next((one for one in self.shown() if one["key"] == self.chosen), None)

    def choose(self, key):
        """Run KEY's properties shown under its row (again: put away), its first button the keys'."""
        self.chosen, self.button, self.said = (None if key == self.chosen else key), 0, None
        listed = [one["key"] for one in self.shown()]
        self.cursor = listed.index(key) if key in listed else self.cursor

    def scroll(self, rows):
        self.top = max(0, min(self.top + rows, self.count - self.height))

    def press(self, target):
        kind, value = target if isinstance(target, tuple) else (target, None)
        if kind == "close":
            self.quit = True
        elif kind == "agent":
            self.agent, self.cursor, self.chosen = value, 0, None
        elif kind == "row":
            self.choose(value)
        elif kind == "button" and self.chosen_run():
            self.act(value, self.chosen_run())
        elif kind == "form" and self.form:
            self.form_press(*value)

    def open_file(self, path):
        self.said = ("Opened", False) if media.open_in_browser(path) else ("Nothing here opens it", True)

    def in_tab(self, folder, name, argv):
        """ARGV run in a new tab of this workspace, in FOLDER, shown: Attach, a chat, a diff, a schedule's chat."""
        workspace = os.environ.get("HERDR_WORKSPACE_ID")
        if not workspace:
            raise RuntimeError("A run opens in a herdr tab: open Runs in herdr")
        made = self.herdr.call("tab", "create", "--workspace", workspace, "--cwd", folder, "--label",
                               preview.label(name)[:40], "--no-focus")
        self.herdr.call("pane", "run", made["root_pane"]["pane_id"], shlex.join(argv))
        self.herdr.call("tab", "focus", made["tab"]["tab_id"])

    def act(self, what, run):
        """WHAT done to RUN from its properties, on a job's thread: its agent's own command, a tab opened for what
        shows in a terminal, the browser; what happened said under the buttons."""
        if what in ("web", "pr"):
            url = run["pr"]["url"] if what == "pr" else run["url"]
            self.said = ("Opened in the browser", False) if media.open_in_browser(url) else ("No browser", True)
            return
        if what == "again":
            self.form = {"agent": run["agent"], "where": "cloud" if run["kind"] == "cloud" else "here",
                         "when": "now", "env": run.get("env_id"), "at": "start", "note": None, "busy": False}
            self.prompt.clear()
            self.prompt.insert(run["prompt"])
            return self.start(run["folder"] or self.folder)
        if f"act-{run['key']}" in self.running:
            return
        folder, title = run["folder"] or self.folder, run["title"]

        def work():
            if what == "attach":
                self.in_tab(folder, title, ["claude", "attach", run["id"]])
                return {"ok": True, "said": "Attached in a new tab"}
            if what == "diff":
                self.in_tab(self.folder, title, ["codex", "cloud", "diff", run["id"]])
                return {"ok": True, "said": "Its diff is in a new tab"}
            if what == "chat":
                done = runs.act("remove", run["id"]) if run["kind"] == "background" else {"ok": True}
                if not done["ok"]:
                    return done
                self.in_tab(folder, title, ["claude", "--resume", run["session"]] if run["agent"] == "claude"
                            else ["codex", "resume", run["session"]])
                return {"ok": True, "said": "Opened as a chat" + (": it is in Chats now" * (run["kind"] ==
                                                                                           "background"))}
            return runs.act(what, run["id"], self.folder if what == "apply" else None)

        def then(done):
            self.said = (done["said"], not done["ok"])
            self.ask(fresh=True)

        self.said = None
        self.job(f"act-{run['key']}", work, then)

    # --- New run

    def open_form(self):
        envs = (self.answer or {}).get("envs") or []
        self.form = {"agent": "claude", "where": "here", "when": "now", "env": envs[0]["id"] if envs else None,
                     "at": "prompt", "note": None, "busy": False}
        self.prompt.clear()
        self.chosen = None

    def stops(self):
        form = self.form
        return [stop for stop in STOPS if (stop != "where" or form["agent"] == "codex")
                and (stop != "env" or form["agent"] == "codex" and form["where"] == "cloud")]

    def ready(self):
        form = self.form
        return bool(self.prompt.text.strip()) and not form["busy"] and not (
            form["agent"] == "codex" and form["where"] == "cloud" and not form["env"])

    def choices(self, stop):
        """The choices at STOP, [(value, label, usable)]."""
        form, envs = self.form, (self.answer or {}).get("envs") or []
        if stop == "agent":
            return [(key, name, True) for key, name in runs.NAMES.items()]
        if stop == "where":
            return [(key, name, key == "here" or bool(envs)) for key, name in WHERE]
        if stop == "env":
            return [(one["id"], one["label"], True) for one in envs]
        return [(key, name, key == "now" or form["agent"] == "claude") for key, name in WHEN]

    def pick(self, stop, value):
        """VALUE chosen at STOP, where it can be; Codex's schedule never (its app's)."""
        if not any(key == value and usable for key, _, usable in self.choices(stop)):
            return
        self.form[stop] = value
        self.form["note"] = None
        if self.form["agent"] == "codex" and self.form["when"] == "schedule":
            self.form["when"] = "now"

    def form_key(self, key):
        """Tab and Shift+Tab step through the stops, ← → change a choice, the prompt takes what is typed; Enter starts
        (or opens Claude's schedule chat); Esc cancels."""
        form, stops = self.form, self.stops()
        at = form["at"] if form["at"] in stops else "prompt"
        if key.name == "esc":
            self.form = None
        elif key.name in ("tab", "backtab"):
            form["at"] = stops[(stops.index(at) + (1 if key.name == "tab" else -1)) % len(stops)]
        elif key.name == "enter":
            self.start(self.folder)
        elif at == "prompt":
            if self.prompt.handle(key):
                form["note"] = None
        elif key.name in ("left", "right") and at != "start":
            values = [value for value, _, usable in self.choices(at) if usable]
            if values:
                now = values.index(form[at]) if form[at] in values else 0
                self.pick(at, values[(now + (1 if key.name == "right" else -1)) % len(values)])
        return None

    def form_press(self, stop, value=None):
        if stop == "start":
            self.start(self.folder)
        elif stop == "cancel":
            self.form = None
        elif stop == "prompt":
            self.form["at"] = "prompt"
        else:
            self.form["at"] = stop
            self.pick(stop, value)

    def start(self, folder):
        """The form's run started on a job's thread, or Claude's schedule's chat opened with /schedule and the words
        typed; what happened said, a failure in the agent's words under the form."""
        form, prompt = self.form, self.prompt.text.strip()
        if not self.ready():
            return
        schedule = form["agent"] == "claude" and form["when"] == "schedule"
        form["busy"] = True

        def work():
            if schedule:
                self.in_tab(folder, prompt.splitlines()[0], ["claude", f"/schedule {prompt}"])
                return {"ok": True, "said": "Opened a chat with /schedule"}
            return runs.start(form["agent"], form["where"], folder, prompt, form["env"])

        def then(done):
            form["busy"] = False
            if not done["ok"]:
                form["note"] = done["said"]
                return
            self.form, self.said = None, (done["said"], False)
            self.ask(fresh=True)

        self.job("start", work, then)

    # --- the loop's

    def tick(self):
        now, live = self.clock(), (self.answer or {}).get("working")
        if not self.form and now >= self.read_at + (QUICK if live else POLL):
            self.ask()
        return self.answer is None and not self.failed or bool(live) or "start" in self.running

    def deadlines(self):
        spin = [self.clock() + SPIN] if self.answer is None and not self.failed or (self.answer or {}).get(
            "working") or "start" in self.running else []
        return spin + [self.read_at + (QUICK if (self.answer or {}).get("working") else POLL)]

    # --- drawing

    def draw(self):
        cells, rows = self.term.size()
        canvas = Canvas(cells, rows)
        head = self.chips(canvas)
        lines = (self.form_lines(cells) + [Row()] if self.form else []) + self.lines(cells)
        keys = FORM_KEYS if self.form else KEYS
        feet = [keys[start:stop].rstrip() for start, stop in wrap(keys, max(1, cells - 2 * INSET))]
        self.count, self.height = len(lines), max(1, rows - head - 1 - len(feet))
        at = next((n for n, line in enumerate(lines) if getattr(line, "chosen", False)), None)
        if at is not None and not (self.top <= at < self.top + self.height):
            self.top = at
        self.scroll(0)
        for n, line in enumerate(lines[self.top:self.top + self.height]):
            if getattr(line, "band", None):
                canvas.band(head + 1 + n, line.band)
            line.draw(canvas, head + 1 + n)
        for n, words in enumerate(feet):
            canvas.put(rows - len(feet) + n, INSET, words, Style(fg="muted"))
        if self.form and self.form["at"] == "prompt" and self.field_at is not None:
            y = head + 1 + self.field_at - self.top
            if 0 <= y - head - 1 < self.height:
                self.prompt.draw(canvas, y, INSET + LABEL, max(8, cells - 2 * INSET - LABEL), PROMPT_ROWS,
                                 Style(fg="text", bg="input"), True)
        self.canvas = canvas
        self.term.write(self.renderer.frame(canvas))
        self.term.flush()

    def chips(self, canvas):
        """The agents' chips, the close button at the right; the rows they take."""
        corner, lit = canvas.width - CLOSE_CELLS, self.pointed == "close"
        canvas.put(0, corner, f" {glyphs(self.icons)['close']} ", Style(fg="text" if lit else "subtext",
                                                                        bg="hover" if lit else None))
        canvas.region(0, corner, canvas.width, "close")
        x = INSET
        for agent in AGENTS:
            words, chosen = NAMES[agent], agent == self.agent
            if chosen:
                canvas.chip(0, x, width(words) + 2, "hover")
            canvas.put(0, x + 1, words, Style(fg="text", bg="hover", bold=True) if chosen else Style(
                fg="text" if self.pointed == ("agent", agent) else "subtext"))
            canvas.region(0, x, x + width(words) + 2, ("agent", agent))
            x += width(words) + 3
        return 1

    @staticmethod
    def said_row(cells, words, failed, x=INSET):
        row = Row()
        row.put(x, truncate(words, cells - x - INSET), Style(fg="deleted" if failed else "muted"))
        return row

    def lines(self, cells):
        """The runs under their days' names, the chosen one's properties under its row, the foot's sentence; before
        an answer, what stands in its place."""
        found, end = self.answer, cells - CONTENT        # a run's words a cell inside its highlight's end
        if found is None:
            if self.failed:
                return [self.said_row(cells, f"{FAILED}: {self.failed}", True)]
            return [self.said_row(cells, f"{SPINNER[int(self.clock() / SPIN) % len(SPINNER)]} {LOADING}", False)]
        listed, lines, group = self.shown(), [], None
        self.cursor = min(self.cursor, max(0, len(listed) - 1))
        if not listed:
            lines.append(self.said_row(cells, NONE if not found["runs"] else "No runs of this agent", False))
        for n, run in enumerate(listed):
            if run["group"] != group:
                group = run["group"]
                lines.append(Row())
                lines[-1].put(INSET, group, Style(fg="muted", bold=True))
            lines.append(self.row(run, end, n == self.cursor))
            if run["key"] == self.chosen:
                lines += self.properties(run, cells)
        if self.said and not self.chosen_run() and not self.form:
            lines.append(self.said_row(cells, *self.said))
        lines.append(Row())
        for words in [found["scheduled"], *found["notes"]]:
            for start, stop in wrap(words, max(1, cells - 2 * INSET)):
                lines.append(Row())
                lines[-1].put(INSET, words[start:stop].rstrip(), Style(fg="muted" if words == found["scheduled"]
                                                                        else "deleted"))
        return lines

    def row(self, run, end, cursor):
        """RUN's row on its highlight, its words on it too and a cell inside it each side (END: the column after their
        last): its mark (a spinner while it works), its name, then its agent, time, what it made and its cost in
        columns from the right (the agent's and the time's go where the name would keep too few cells)."""
        row = Row()
        row.chosen = run["key"] == self.chosen
        pointed = cursor or self.pointed == ("row", run["key"])
        row.band = bg = "selection" if row.chosen else "hover" if pointed else None
        faint = "muted_row" if bg else "muted"           # readable on the highlight, as every list's
        mark, role = MARKS.get(run["state"], (SPINNER[int(self.clock() / SPIN) % len(SPINNER)], "accent")
                                if run["state"] == "running" else (" ", "muted"))
        row.put(CONTENT, mark, Style(fg=faint if role == "muted" else role, bg=bg))
        columns = [(run["name"], AGENT), (run["time"], TIME), (run["made"] or "–", MADE), (run["cost"], COST)]
        while len(columns) > 2 and end - sum(size + 1 for _, size in columns) - CONTENT - 2 < LEAST:
            columns.pop(0)
        x = end
        for words, size in reversed(columns):
            failed = words == "failed"
            row.right(x, truncate(words, size), Style(fg="deleted" if failed else faint, bg=bg))
            x -= size + 1
        row.put(CONTENT + 2, truncate(run["title"], max(1, x - CONTENT - 2)), Style(fg="text", bg=bg))
        row.regions.append((0, end + CONTENT, ("row", run["key"])))
        return row

    def properties(self, run, cells):
        """RUN's properties under its row, as the app's: how it ran, where and when, its prompt, what it does now or
        made, its cost; its buttons, the one the keys are on lit; what was done."""
        x, room, lines = CONTENT + 2, max(8, cells - 2 * CONTENT - 2 - LABEL), []      # its words end as the row's

        def line(label, words, role="text"):
            for n, (start, stop) in enumerate(wrap(words, room) or [(0, 0)]):
                lines.append(Row())
                if not n:
                    lines[-1].put(x, label, Style(fg="muted"))
                lines[-1].put(x + LABEL, words[start:stop].rstrip(), Style(fg=role))

        short = [path[len(run["folder"]) + 1:] if run["folder"] and path.startswith(run["folder"] + os.sep) else path
                 for path in run["files"]]
        line("Ran as", run["ran_as"])
        line("Env" if run["kind"] == "cloud" else "Folder", " · ".join(filter(None, [run["place"],
                                                                                    f"{run['day']} {run['time']}",
                                                                                    run["took"]])))
        line("Prompt", run["prompt"])
        if run["now"]:
            line("Now", run["now"])
        if run.get("diff"):
            line("Diff", f"{run['diff']} · {run['said']}")
        elif short:
            for n, path in enumerate(short[:6]):
                line(("So far" if run["state"] in runs.LIVE else "Made") if not n else "", path)
        line("Cost", run["cost_line"])
        row, at = Row(), x
        for n, (id, label) in enumerate(actions(run, self.into)):
            lit = n == self.button or self.pointed == ("button", id)
            row.put(at, f" {label} ", Style(fg="text" if lit else "subtext", bg="hover" if lit else "input"))
            row.regions.append((at, at + width(label) + 2, ("button", id)))
            at += width(label) + 3
        lines.append(row)
        if self.said:
            lines.append(self.said_row(cells, *self.said, x=x))
        return lines

    def form_lines(self, cells):
        """New run's form, as the app's: the agent, the folder, the prompt, where and when it runs (Codex's schedule
        muted), what that does; Start lit once it can, the one accent."""
        form, x, room = self.form, INSET, max(8, cells - 2 * INSET - LABEL)
        lines = [Row()]
        lines[0].put(x, "New run", Style(fg="text", bold=True))
        for stop in self.stops()[:-1]:                  # Start, the last stop, ends the form
            lit, label = form["at"] == stop, LABELS[stop]
            if stop == "prompt":
                lines.append(Row())
                lines[-1].put(x, "Folder", Style(fg="muted"))
                lines[-1].put(x + LABEL, truncate(self.into, room))
                self.field_at = len(lines)              # draw() paints the field here while it has the keys
                shown = [self.prompt.text[a:b].rstrip() for a, b in wrap(self.prompt.text, room)] \
                    or [self.prompt.placeholder]
                for n in range(PROMPT_ROWS):
                    part = Row()
                    if not n:
                        part.put(x, label, Style(fg="text" if lit else "muted"))
                    if not lit:
                        part.put(x + LABEL, truncate(shown[n] if n < len(shown) else "", room).ljust(room), Style(
                            fg="text" if self.prompt.text else "muted", bg="input"))
                    part.regions.append((x + LABEL, x + LABEL + room, ("form", ("prompt",))))
                    lines.append(part)
                continue
            row, at = Row(), x + LABEL
            row.put(x, label, Style(fg="text" if lit else "muted"))
            for value, words, usable in self.choices(stop):
                chosen = form[stop] == value
                row.put(at, f" {words} ", Style(fg="text", bg="hover", bold=True) if chosen else Style(
                    fg="subtext" if usable else "muted"))
                if usable:
                    row.regions.append((at, at + width(words) + 2, ("form", (stop, value))))
                at += width(words) + 3
            lines.append(row)
        for words, role in ((form_note(form, self.into), "muted"), (form["note"] or "", "deleted")):
            for start, stop in wrap(words, max(1, room)) if words else ():
                lines.append(Row())
                lines[-1].put(x + LABEL, words[start:stop].rstrip(), Style(fg=role))
        words = "Starting…" if form["busy"] else "Open in a chat" if form["agent"] == "claude" \
            and form["when"] == "schedule" else "Start"
        lines.append(Row())
        lines[-1].put(x, f" {words} ", Style(fg="button_text", bg="button", bold=True) if self.ready() or form["busy"]
                      else Style(fg="muted", bg="input"))
        lines[-1].regions.append((x, x + width(words) + 2, ("form", ("start",))))
        return lines

def main():
    state = os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.join(
        os.path.expanduser("~"), ".local", "state", "herdr", "plugins", "herdr-fold.sidebar")
    if os.name == "nt":
        from keys_windows import WindowsTerminal as Terminal
    else:
        from keys_unix import UnixTerminal as Terminal
    RunsView(Terminal(), preview.Herdr(), state).run()


if __name__ == "__main__":
    main()
