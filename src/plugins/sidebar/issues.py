"""The sidebar's Issues view, laid out and keyed as GitHub's own issue list. Open issues with a priority come first, the
most pressing at the top: GitHub's Priority field where the organization has it, else a priority label, a severity
label or a word alone. The view only asks: gh runs in the app's jobs."""
import time
from dataclasses import replace

from github import LEVELS, STATES, Query, ago, matches, priority, ranked
from icons import glyphs
from screen import Canvas, PLAIN, Style, truncate, width
from vt import Key, Mouse
from widgets import Action, Confirm, ListView, Menu, Popup, TextInput

KEYS = {"t": "issue_to_agent", "b": "issue_web", "r": "issue_comment", "o": "preview_issue", "enter": "preview_issue"}
HOVER = ("agent", "web")                  # the buttons an issue shows on hover, in this order
# a priority's traffic-light color role, by its rank (core/github.py's LEVELS)
PRIORITY_ROLE = ("deleted", "deleted", "modified", "added")


class Issues:
    def __init__(self, icons=True, now=time.time):
        self.icons, self.now = icons, now
        self.query, self.level = Query(), None             # asked of GitHub; the priority shown (its rank), or all
        self.asked = self.listing = None
        self.field, self.searching = TextInput(placeholder="Search issues"), False     # the keys go to the field
        self.list = ListView(1)
        self.hover = self.pointed = self.confirm = self.doomed = self.canvas = self.menu = None
        self.top, self.height, self.drop = 0, 1, (0, 0)

    @property
    def editing(self):
        """Whether the view holds the keys: the search field, a menu, a question (the app's own keys wait)."""
        return self.searching or self.menu is not None or self.confirm is not None

    def kept(self):
        """What a new version of the sidebar comes back to: the filters."""
        return {"state": self.query.state, "assigned": self.query.assigned, "authored": self.query.authored,
                "label": self.query.label, "level": self.level}

    def take(self, kept):
        """The filters a version before this one kept (anything not as kept() writes it is left out)."""
        if not isinstance(kept, dict):
            return
        state = kept.get("state") if kept.get("state") in STATES else "open"
        label = kept.get("label") if isinstance(kept.get("label"), str) else ""
        self.query = Query(state, kept.get("assigned") is True, kept.get("authored") is True, label)
        self.level = kept.get("level") if kept.get("level") in range(len(LEVELS)) else None

    # --- asking and answers

    def ask(self, query=None):
        """The issues of QUERY (the current one by default), asked for again."""
        self.query = query or self.query
        self.asked = self.query
        return Action("load_issues", (self.query,))

    def show(self, listing, query):
        """The answer for QUERY; one for a query no longer chosen is dropped."""
        if query != self.query:
            return
        self.asked, self.listing = None, listing
        self.rebuild()

    def rebuild(self):
        """The issues shown: the answer's of the chosen priority that match what is typed; the open ones by priority,
        gh's order (the latest change first) within one, and for the closed ones."""
        found = self.listing.issues if self.listing else ()
        if self.query.state == "open":
            found = ranked(found)
        words, chosen = self.field.text.lower().split(), self.list.selected()
        self.list.set([issue for issue in found if matches(issue, words)
                       and (self.level is None or priority(issue)[0] == self.level)])
        if chosen is not None:                 # the same issue stays chosen however the list changed around it
            self.list.index = next((n for n, issue in enumerate(self.list.items) if issue.number == chosen.number),
                                   self.list.index)
            self.list.keep_visible()

    # --- drawing

    def draw(self, canvas, top, height, roomy):
        """The view from row TOP, HEIGHT rows: the search field with the filters button (tall in a ROOMY pane), Open
        and Closed, a line when there is something to say, then the issues."""
        self.canvas, self.top, self.height, cells = canvas, top, height, canvas.width
        row, taken = canvas.control(top, 1, cells - 2, 1, "input", roomy)
        for y in range(top, top + taken):
            canvas.region(y, 1, cells - 1, "input")
        self.drop = (top + taken, cells - 1)            # the filters menu: under the field, its right edge with it
        x = self.filters(canvas, row, cells - 2)
        self.field.draw(canvas, row, 3, max(1, x - 4), 1, Style(bg="input"), focused=self.searching)
        y = top + taken + (0 if roomy else 1)
        self.states(canvas, y, cells)
        y += 2
        line = self.line()
        if line:
            text, role = line
            canvas.put(y, 1, truncate(text, cells - 2), Style(fg=role))
            y += 2
        items = max(1, (top + height - y) // 2)
        if self.list.height != items:
            self.list.resize(items)
        for at in range(self.list.height):
            index = self.list.at(at)
            if index is None:
                break
            self.row(canvas, y + 2 * at, index)
        if self.menu:
            popup = self.menu
            popup.menu.draw(canvas, *popup.menu.at(popup.y, popup.x, cells, top, top + height))
        if self.confirm:
            self.draw_confirm(canvas)

    def filters(self, canvas, row, end):
        """The filters button, ending before column END in the field: what is on (the priority in its color), or
        Filters; lit under the mouse or while its menu is open. Returns its first column."""
        parts = [(f"● {LEVELS[self.level]}", PRIORITY_ROLE[self.level])] if self.level is not None else []
        q = self.query
        parts += [(word, "text") for word, on in (("me", q.assigned), ("by me", q.authored), (q.label, q.label)) if on]
        parts = parts or [("Filters", "muted")]
        label = " · ".join(text for text, _ in parts) + " ▾"
        cells = min(width(label) + 2, max(4, end // 2))
        x = end - cells
        lit = self.pointed == "filters" or self.menu is not None
        canvas.chip(row, x, cells, "hover" if lit else "input")
        at, bg = x + 1, "hover" if lit else "input"
        for n, (text, role) in enumerate(parts):
            if n:
                at = canvas.put(row, at, " · ", Style(fg="muted", bg=bg))
            at = canvas.put(row, at, truncate(text, max(1, x + cells - 3 - at)), Style(fg=role, bg=bg))
        canvas.put(row, min(at + 1, x + cells - 2), "▾", Style(fg="muted", bg=bg))
        canvas.region(row, x, x + cells, "filters")
        return x

    def states(self, canvas, y, cells):
        """Open and Closed, as GitHub's list has them: the chosen one filled, one under the mouse lit."""
        x = 1
        for name, label in STATES.items():
            chosen, pointed = name == self.query.state, self.pointed == ("state", name)
            if chosen or pointed:
                canvas.chip(y, x, width(label) + 2, "button" if chosen else "hover")
            style = (Style(fg="button_text", bg="button", bold=True) if chosen
                     else Style(fg="text", bg="hover") if pointed else Style(fg="muted"))
            end = canvas.put(y, x + 1, truncate(label, max(1, cells - x - 2)), style)
            canvas.region(y, x, end + 1, ("state", name))
            x = end + 2

    def line(self):
        """What to say above the list, and its color role: asking, a failure, or nothing found."""
        if self.asked:
            return "Loading issues…", "muted"
        if self.listing is None:
            return None
        if self.listing.error:
            return self.listing.error, "deleted"
        if self.list.items:
            return None
        filtered = self.query != Query(self.query.state) or self.level is not None or self.field.text.strip()
        return ("No issues match" if filtered else f"No {self.query.state} issues"), "muted"
    def row(self, canvas, y, index):
        issue, cells = self.list.items[index], canvas.width
        hovered = index == self.hover
        bg = "selection" if index == self.list.index else ("hover" if hovered else None)
        for r in (y, y + 1):
            if r < canvas.height:
                canvas.band(r, bg)
                canvas.region(r, 0, cells, ("issue", index))
        end = cells - 1
        if hovered:
            end = self.buttons(canvas, y, end, index, bg)
        level, _ = priority(issue)
        if level < len(PRIORITY_ROLE):
            for r in (y, y + 1):
                if r < canvas.height:
                    canvas.put(r, 0, "▌", Style(fg=PRIORITY_ROLE[level], bg=bg))
        number, color = f"#{issue.number}", PRIORITY_ROLE[level] if level < len(PRIORITY_ROLE) else "accent"
        x = canvas.put(y, 1, number, Style(fg=color if issue.state != "CLOSED" else "muted", bg=bg, bold=True))
        canvas.put(y, x + 1, truncate(issue.title, max(1, end - x - 2)), Style(fg="text", bg=bg))
        if y + 1 < canvas.height:
            self.details(canvas, y + 1, 1 + width(number) + 1, issue, bg)

    def details(self, canvas, y, x, issue, bg):
        """The labels and the assignee, cut to fit; how long ago it changed, always, at the right edge."""
        when = ago(issue.updated, self.now())
        stop = canvas.width - 1 - width(when)
        if when:
            canvas.put(y, stop, when, Style(fg="muted", bg=bg))
        people = issue.assignees and "@" + issue.assignees[0] + (f" +{len(issue.assignees) - 1}"
                                                                    if len(issue.assignees) > 1 else "")
        level, first = priority(issue)                  # the priority first, in its color
        labels = ", ".join(label for label in issue.labels if label != first)
        if first and stop - x - 1 > 1:
            x = canvas.put(y, x, truncate(first, stop - x - 1), Style(fg=PRIORITY_ROLE[level], bg=bg))
            labels = ", " + labels if labels else ""
        parts = [part for part in (labels, people) if part]
        if parts and stop - x - 1 > 1:
            canvas.put(y, x, truncate("  ".join(parts), stop - x - 1), Style(fg="muted", bg=bg))

    def buttons(self, canvas, y, end, index, bg):
        """The hover buttons before column END; returns the first column they take."""
        x = end - 2 * len(HOVER)
        for i, kind in enumerate(HOVER):
            canvas.put(y, x + 2 * i, glyphs(self.icons)[kind], Style(fg="text", bg=bg))
            canvas.region(y, x + 2 * i, x + 2 * i + 2, (kind, index))
        return x

    def draw_confirm(self, canvas):
        cells = canvas.width
        rows = self.confirm.draw(Canvas(cells, self.height), 0, 0, cells)
        y = max(self.top + 2, self.top + self.height - rows - 1)
        for row in range(y, self.top + self.height):
            canvas.put(row, 0, " " * cells, PLAIN)
        canvas.put(y, 0, "─" * cells, Style(fg="muted"))
        self.confirm.draw(canvas, y + 1, 0, cells)

    # --- events

    def handle(self, event):
        if isinstance(event, Mouse):
            return self.mouse(event)
        if not isinstance(event, Key):
            return None
        if self.confirm:
            return self.answer(self.confirm.handle(event))
        if self.menu:
            choice = self.menu.menu.handle(event)
            if choice == "cancel":
                self.menu = None
            return self.pick(choice) if choice not in (None, "cancel") else None
        if self.searching:
            return self.type(event)
        if event.ctrl and event.char in ("/", "\x7f"):              # Ctrl+/: a terminal sends it as Ctrl+?
            self.searching = True
            return None
        name = event.char if event.name == "char" and not (event.ctrl or event.alt) else event.name
        if name in ("up", "down"):
            self.list.move(1 if name == "down" else -1)
        elif name in ("pageup", "pagedown"):
            self.list.page(1 if name == "pagedown" else -1)
        elif name in ("home", "end"):
            self.list.move(len(self.list.items) * (1 if name == "end" else -1))
        elif name in ("left", "right"):
            state = "closed" if name == "right" else "open"
            return self.ask(replace(self.query, state=state)) if state != self.query.state else None
        elif name in ("/", "s"):
            self.searching = True
        elif name in ("a", "u", "l"):
            self.open_filters({"a": "assignee", "u": "author", "l": "label"}[name])
        elif name == "c":
            return Action("new_issue", ())
        elif name == "R":
            return self.ask()
        else:
            return self.on_issue(name, self.list.selected())
        return None

    def type(self, event):
        """A key in the search field: Enter or ↓ back to the list, what is typed kept; Esc clears it and goes back."""
        if event.name in ("enter", "down", "tab", "esc"):
            self.searching = False
            if event.name == "esc" and self.field.text:
                self.field.clear()
                self.rebuild()
            return None
        before = self.field.text
        self.field.handle(event)
        if self.field.text != before:
            self.list.index = 0
            self.rebuild()
        return None

    def open_filters(self, at=None):
        """The filters menu right under the field its button is in, their right edges in one line, its cursor on the
        part AT (assignee, author, label, priority): each filter, a ✓ on the ones on; the labels those of the issues
        listed, the chosen one too."""
        q, mark = self.query, lambda on: "✓ " if on else "  "
        picks = {mark(q.assigned) + "Assigned to me": ("assignee", None),
                 mark(q.authored) + "Created by me": ("author", None),
                 mark(self.level is None) + "Any priority": ("priority", None)}
        picks.update({mark(self.level == n) + f"● {name}": ("priority", n) for n, name in enumerate(LEVELS)})
        labels = sorted({label for issue in (self.listing.issues if self.listing else ()) for label in issue.labels}
                        | ({q.label} if q.label else set()), key=str.lower)
        picks[mark(not q.label) + "Any label"] = ("label", "")
        picks.update({mark(q.label == label) + label: ("label", label) for label in labels})
        menu = Menu(picks)
        if at:
            menu.index = next(n for n, (part, _) in enumerate(picks.values()) if part == at)
        self.menu = Popup(menu, picks, self.drop[0], self.drop[1] - menu.width())

    def close_menu(self):
        """Its menu closed, as a click outside it closes it: the pane lost the keys, or its header was clicked."""
        self.menu = None

    def pick(self, choice):
        """CHOICE of a menu: a filter turned on or off (asked of GitHub again, but the priority), or what to do with
        the issue the menu was opened on."""
        picks, self.menu = self.menu.on, None
        what, value = picks[choice]
        q = self.query
        if what == "assignee":
            return self.ask(replace(q, assigned=not q.assigned))
        if what == "author":
            return self.ask(replace(q, authored=not q.authored))
        if what == "label":
            return self.ask(replace(q, label=value)) if value != q.label else None
        if what == "priority":
            self.level = value
            self.list.index = 0
            self.rebuild()
            return None
        return self.on_issue(what, value)

    def on_issue(self, name, issue):
        if issue is None:
            return None
        if name in KEYS:
            return Action(KEYS[name], (issue,))
        if name == "assign":                                  # the right click's menu only: GitHub's m is milestones
            return Action("issue_change", (issue, "assign"))
        if name == "x":
            verb = "Reopen" if issue.state == "CLOSED" else "Close"
            self.confirm, self.doomed = Confirm(f"{verb} #{issue.number}?", verb), issue
        return None

    def issue_menu(self, issue, y, x):
        """The right click's menu on ISSUE: everything the keys do with it, and Assign to me."""
        verb = "Reopen" if issue.state == "CLOSED" else "Close"
        picks = {"Open": ("o", issue), "Open in the browser": ("b", issue), "To the agent": ("t", issue),
                 "Reply": ("r", issue), "Assign to me": ("assign", issue), f"{verb}…": ("x", issue)}
        self.menu = Popup(Menu(picks), picks, y, x)

    def answer(self, yes):
        if yes is None:
            return None
        issue, self.confirm, self.doomed = self.doomed, None, None
        return Action("issue_change", (issue, "reopen" if issue.state == "CLOSED" else "close")) if yes else None

    def mouse(self, event):
        target = self.canvas.hit(event.x, event.y) if self.canvas else None
        if event.kind == "move":
            self.hover = target[1] if isinstance(target, tuple) and target[0] in ("issue", *HOVER) else None
            self.pointed = target if target == "filters" or isinstance(target, tuple) and target[0] == "state" \
                else None
        elif event.kind in ("wheel_up", "wheel_down"):
            self.list.scroll(3 if event.kind == "wheel_down" else -3)
        elif event.kind == "press":
            return self.press(event, target)
        return None

    def press(self, event, target):
        if self.confirm:
            if event.button == 0 and target in ("confirm:yes", "confirm:no"):
                return self.answer(target == "confirm:yes")
            return None
        if self.menu:
            popup, self.menu = self.menu, None
            if str(target).startswith("menu:"):
                self.menu = popup
                return self.pick(popup.menu.choices[int(target[5:])])
            return None
        self.searching = target == "input" and event.button == 0
        if target == "filters" and event.button == 0:
            self.open_filters()
        elif isinstance(target, tuple) and target[0] == "state" and event.button == 0:
            return self.ask(replace(self.query, state=target[1])) if target[1] != self.query.state else None
        elif isinstance(target, tuple) and target[0] in ("issue", *HOVER):
            kind, index = target
            self.list.index = index
            issue = self.list.selected()
            if event.button == 2:
                self.issue_menu(issue, event.y, event.x)
            elif event.button == 0:
                return Action({"agent": "issue_to_agent", "web": "issue_web"}.get(kind, "preview_issue"), (issue,))
        return None
