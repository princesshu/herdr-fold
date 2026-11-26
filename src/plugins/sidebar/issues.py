"""The sidebar's Issues view, laid out and keyed as GitHub's own issue list, its switch showing its pull requests
instead (pulls.py). Open issues by priority (GitHub's Priority field, else a priority label, a severity label or a
word), each one's type an icon before its number; its filters filters.py's. gh runs in the app's jobs."""
import time
from dataclasses import replace

from filters import Filtered, Filters, counted
from github import (ISSUE_GROUPS, LEVELS, ME, STATES, TYPES, Query, ago, issue_facets, issue_search, kind,
                    matches, priority, rank, ranked, shown_labels)
from icons import glyphs
from pulls import Pulls
from screen import BAND, PAD, PLAIN, SPIN, SPINNER, Canvas, Style, truncate, width
from vt import Key, Mouse
from widgets import TYPED, Action, Confirm, Heading, ListView, Menu, Popup, Row, TextInput

KEYS = {"t": "issue_to_agent", "b": "issue_web", "r": "issue_comment", "o": "preview_issue", "enter": "preview_issue"}
HOVER = ("agent", "web")                  # the buttons an issue shows on hover, in this order
# a priority's traffic-light color role, by its rank (core/github.py's LEVELS)
PRIORITY_ROLE = ("deleted", "deleted", "modified", "added")
NO_PRIORITY = "guide"         # an issue with none: a quiet bar all the same, "not sorted yet", never a gap
TEXT = 3                      # an issue's number: its priority's bar, a cell of air and the margin before it
SLOT = 2                      # a type's icon and a cell of air before the number, where any issue listed has one
BOARDS = {"issues": "Issues", "pulls": "Pull requests"}      # its two lists, the switch's; p switches them
SETS = {"priority": ("Priority", "No priority"), "type": ("Type", "No type")}     # the right click's chained menus


def look(group, value, icons):
    """How a filter's VALUE reads in GROUP (filters.py's Filters): a priority's dot in its color, a type's icon."""
    if group == "level":
        return LEVELS[value], ("●", PRIORITY_ROLE[value]), None
    if group == "type":
        return value, (glyphs(True)[value], "muted") if icons and value in TYPES else None, None
    return value, None, None


def valid(group, value):
    """Whether a kept VALUE can be one of GROUP's."""
    if group in ME:
        return value is True
    return type(value) is int and 0 <= value < len(LEVELS) if group == "level" else isinstance(value, str) and value


class Issues(Filtered):
    SEARCH = staticmethod(issue_search)

    def __init__(self, icons=True, now=time.time):
        self.icons, self.now = icons, now
        self.query, self.filters = Query(), Filters(ISSUE_GROUPS, look)     # asked of GitHub; the filters narrow
        self.asked = self.listing = self.answered = None    # the query on its way, the answer shown and its query
        self.field, self.searching = TextInput(placeholder="Filter issues"), False     # the keys go to the field
        self.list = ListView()
        self.hover = self.pointed = self.confirm = self.doomed = self.canvas = self.menu = None
        self.kind = None              # the menu open: "filters", "issue" (a right click's) or ("set", what, issue)
        self.items = []               # the facets the filters' menu counts: the latest answer's
        self.totals = None            # the repository's open and closed issues, as last told (both sides' counts)
        self.top, self.height, self.drop = 0, 1, (0, 0)
        self.board, self.pulls = "issues", Pulls(icons, now)

    @property
    def editing(self):
        """Whether the view holds the keys: the search field, a menu, a question (the app's own keys wait)."""
        if self.board == "pulls":
            return self.pulls.editing
        return self.searching or self.menu is not None or self.confirm is not None

    def kept(self):
        """What a new version of the sidebar comes back to: the filters, the list shown, its pull requests' filters."""
        return {"state": self.query.state, "chosen": self.filters.kept(), "board": self.board,
                "pulls": self.pulls.kept()}

    def take(self, kept):
        """The filters a version before this one kept (anything not as kept() writes it is left out); one before the
        groups kept Assigned to me and Created by me as flags, one priority (level) and one label: each is its group's
        value now."""
        if not isinstance(kept, dict):
            return
        self.query = Query(kept.get("state") if kept.get("state") in STATES else "open")
        chosen = kept.get("chosen")
        if not isinstance(chosen, dict):
            chosen = {"assigned": [kept.get("assigned")], "authored": [kept.get("authored")],
                      "level": [kept.get("level")], "label": [kept.get("label")]}
        self.filters.take(chosen, valid)
        self.board = kept.get("board") if kept.get("board") in BOARDS else "issues"
        self.pulls.take(kept.get("pulls"))

    # --- asking and answers

    def ask(self, query=None):
        """The issues of QUERY (the current one by default), asked for again; another query's no longer shown meanwhile
        (the first issue's row says so), the same query's staying where they are (its search's too)."""
        self.query = query or self.query
        if self.answered is None or replace(self.answered, search="") != replace(self.query, search=""):
            self.listing = None
            self.rebuild()
        self.asked = self.query
        return Action("load_issues", (self.query,))

    def show(self, listing, query):
        """The answer for QUERY; one for a query no longer chosen is dropped. Returns the ask its search wants now (a
        full list with types or labels on), or None."""
        if query != self.query:
            return None
        self.asked, self.listing, self.answered = None, listing, query
        self.totals = listing.totals or self.totals
        self.rebuild()
        self.items = [issue_facets(issue, listing.me) for issue in listing.issues]
        self.refresh_menu()
        return None if listing.error else self.follow()

    def rebuild(self):
        """The issues shown: the answer's (its search's, once that is the one asked) the filters keep that match what
        is typed; the open ones by priority, gh's order (the latest change first) within one, and for the closed
        ones."""
        listing = self.listing
        searched = listing and listing.narrowed is not None and self.answered == self.query
        found = (listing.narrowed if searched else listing.issues) if listing else ()
        if self.query.state == "open":
            found = ranked(found)
        words, chosen = self.field.text.lower().split(), self.list.selected()
        me = listing.me if listing else ""
        self.list.set([issue for issue in found if matches(issue, words)
                       and self.filters.narrows(issue_facets(issue, me))])
        if chosen is not None:                 # the same issue stays chosen however the list changed around it
            self.list.index = next((n for n, issue in enumerate(self.list.items) if issue.number == chosen.number),
                                   self.list.index)
            self.list.keep_visible()

    def slotted(self):
        """Whether the rows keep a type's icon slot: any issue listed has a type with an icon (the numbers in one
        column); none, and the rows are as a list without types."""
        listing = self.listing
        issues = (listing.issues + (listing.narrowed or ())) if listing else ()
        return self.icons and any(kind(issue)[0] in TYPES for issue in issues)

    # --- drawing

    def draw(self, canvas, top, height, roomy):
        """The view from row TOP, HEIGHT rows: the switch, Issues or Pull requests, then the list it shows."""
        self.canvas, x = canvas, 1
        for name, label in BOARDS.items():              # a choice of two, never the accent: Open's is the screen's
            chosen = name == self.board
            end = canvas.put(top, x, f" {label} ", Style(fg="text" if chosen else "muted", bold=chosen,
                                                         bg="selection" if chosen else None))
            canvas.region(top, x, end, ("board", name))
            x = end + 1
        if self.board == "pulls":
            return self.pulls.draw(canvas, top + 1, height - 1, roomy)
        return self.draw_issues(canvas, top + 1, height - 1, roomy)

    def switch(self, board):
        """BOARD's list shown; its pull requests asked for the first time."""
        self.board = board
        return self.pulls.ask() if board == "pulls" and self.pulls.listing is None and not self.pulls.asked else None

    def draw_issues(self, canvas, top, height, roomy):
        """The issues from row TOP, HEIGHT rows: the filter field with its funnel (tall in a ROOMY pane), what is on as
        chips under it, Open and Closed and the refresh button, then the issues, or on the first one's row what is
        asked or found."""
        self.top, self.height, cells = top, height, canvas.width
        row, taken = canvas.control(top, 1, cells - 2, 1, "input", roomy)
        for y in range(top, top + taken):
            canvas.region(y, 1, cells - 1, "input")
        self.drop = (top + taken, cells - 1)            # the filters menu: under the field, its right edge with it
        funnel = cells - 3                              # a cell of air after it, as the field's words have two before
        self.filters.funnel(canvas, row, funnel, self.icons, self.pointed == "filters" or self.kind == "filters")
        self.field.draw(canvas, row, 3, max(1, funnel - 4), 1, Style(bg="input"), focused=self.searching)
        y = top + taken
        if self.filters.on():                           # in a low pane its first row where the blank one stood
            y += self.filters.draw_chips(canvas, y, self.icons, self.pointed)
        elif not roomy:
            y += 1
        self.states(canvas, y, cells)
        self.refresh(canvas, y, cells)
        y += 2
        line = self.line()
        if line:                                        # on the first issue's row: nothing moves after
            text, role = line
            canvas.put(y, PAD, truncate(text, cells - 2 * PAD), Style(fg=role))
        items = max(1, (top + height - y) // 2)
        if self.list.height != items:
            self.list.resize(items)
        slot = self.slotted()
        for at in range(self.list.height):
            index = self.list.at(at)
            if index is None:
                break
            self.row(canvas, y + 2 * at, index, slot)
        if self.menu:
            popup = self.menu
            popup.menu.draw(canvas, *popup.menu.at(popup.y, popup.x, cells, top, top + height, PAD))
        if self.confirm:
            self.draw_confirm(canvas)

    def states(self, canvas, y, cells):
        """Open and Closed, as GitHub's list has them, each with the repository's count (the word alone till it is
        known): the chosen one filled, one under the mouse lit; a cell of air each side of its words."""
        x = 1
        for name, label in STATES.items():
            label = counted(label, self.totals, name)
            chosen, pointed = name == self.query.state, self.pointed == ("state", name)
            if chosen or pointed:
                canvas.chip(y, x, width(label) + 2, "button" if chosen else "hover")
            style = (Style(fg="button_text", bg="button", bold=True) if chosen
                     else Style(fg="text", bg="hover") if pointed else Style(fg="muted"))
            end = canvas.put(y, x + 1, truncate(label, max(1, cells - x - 2)), style)
            canvas.region(y, x, end + 1, ("state", name))
            x = end + 2

    def refresh(self, canvas, y, cells):
        """The refresh button at the right end of row Y, as Files' header has one: a spinner in its cell while gh runs
        over the issues shown (the first ask says so on the list's first row), lit under the mouse."""
        x = cells - 2
        running = self.asked and self.list.items
        mark = SPINNER[int(self.now() / SPIN) % len(SPINNER)] if running else glyphs(self.icons)["refresh"]
        canvas.put(y, x, mark, Style(fg="text" if self.pointed == "refresh" else "muted"))
        canvas.region(y, x, x + 2, "refresh")

    def tip(self, target):
        """The refresh button's tip while gh runs; None: the sidebar's own."""
        if self.board == "pulls":
            return self.pulls.tip(target)
        return "Loading issues…" if target == "refresh" and self.asked else None

    def line(self):
        """What the list's first row says while there is no issue to show, and its color role: asking, a failure, or
        nothing found."""
        if self.list.items:
            return None
        if self.asked:
            return "Loading issues…", "muted"
        if self.listing is None:
            return None
        if self.listing.error:
            return self.listing.error, "deleted"
        filtered = self.filters.on() or self.field.text.strip()
        return ("No issues match" if filtered else f"No {self.query.state} issues"), "muted"

    def row(self, canvas, y, index, slot):
        """An issue's two rows on its highlight (BAND in from each side): its priority's bar at the highlight's edge,
        its type's icon in the SLOT (where the list keeps one), its number in its priority's color and its title; the
        hover buttons at its end. A closed one's marks all muted."""
        issue, cells = self.list.items[index], canvas.width
        hovered = index == self.hover
        bg = "selection" if index == self.list.index else ("hover" if hovered else None)
        for r in (y, y + 1):
            if r < canvas.height:
                canvas.band(r, bg)
                canvas.region(r, 0, cells, ("issue", index))
        end = cells - 1 - BAND
        if hovered:
            end = self.buttons(canvas, y, end, index, bg)
        level, _ = priority(issue)
        closed = issue.state == "CLOSED"
        ranked = level < len(PRIORITY_ROLE)
        for r in (y, y + 1):
            if r < canvas.height:
                bar = "muted" if closed else PRIORITY_ROLE[level] if ranked else NO_PRIORITY
                canvas.put(r, 1, "▌", Style(fg=bar, bg=bg))
        x = TEXT
        if slot:
            typed = kind(issue)[0]
            if typed in TYPES:
                canvas.put(y, x, glyphs(True)[typed], Style(fg="muted", bg=bg))
            x += SLOT
        number, color = f"#{issue.number}", PRIORITY_ROLE[level] if ranked else "text"
        x = canvas.put(y, x, number, Style(fg="muted" if closed else color, bg=bg, bold=True))
        canvas.put(y, x + 1, truncate(issue.title, max(1, end - x - 2)), Style(fg="text", bg=bg))
        if y + 1 < canvas.height:
            self.details(canvas, y + 1, x + 1, issue, bg)

    def details(self, canvas, y, x, issue, bg):
        """Under its title, two cells apart: its priority in its color, its type's word where no icon says it (icons
        off, an organization's own type), the labels and the assignee, cut to fit; how long ago it changed, always,
        a cell inside the highlight's end."""
        when = ago(issue.updated, self.now())
        stop = canvas.width - 1 - BAND - width(when)
        if when:
            canvas.put(y, stop, when, Style(fg="muted", bg=bg))
        level, first = priority(issue)
        typed = kind(issue)[0]
        people = issue.assignees and "@" + issue.assignees[0] + (f" +{len(issue.assignees) - 1}"
                                                                    if len(issue.assignees) > 1 else "")
        parts = [(first, "muted" if issue.state == "CLOSED" else PRIORITY_ROLE[level]) if first else None,
                 (typed, "muted") if typed and not (self.icons and typed in TYPES) else None,
                 (", ".join(shown_labels(issue)), "muted"), (people, "muted")]
        for text, role in (part for part in parts if part and part[0]):
            if stop - x - 1 <= 1:
                break
            x = canvas.put(y, x, truncate(text, stop - x - 1), Style(fg=role, bg=bg)) + 2

    def buttons(self, canvas, y, end, index, bg):
        """The hover buttons before column END; returns the first column they take."""
        x = end - 2 * len(HOVER)
        for i, kind_ in enumerate(HOVER):
            canvas.put(y, x + 2 * i, glyphs(self.icons)[kind_], Style(fg="text", bg=bg))
            canvas.region(y, x + 2 * i, x + 2 * i + 2, (kind_, index))
        return x

    def draw_confirm(self, canvas):
        cells = canvas.width
        rows = self.confirm.draw(Canvas(cells, self.height), 0, 0, cells)
        y = max(self.top + 2, self.top + self.height - rows - 1)
        for row in range(y, self.top + self.height):
            canvas.put(row, 0, " " * cells, PLAIN)
        canvas.put(y, BAND, "─" * (cells - 2 * BAND), Style(fg="muted"))    # as wide as a row's highlight
        self.confirm.draw(canvas, y + 1, 0, cells)

    # --- events

    def handle(self, event):
        target = self.canvas.hit(event.x, event.y) if isinstance(event, Mouse) and self.canvas else None
        if isinstance(event, Mouse) and event.kind == "press" and isinstance(target, tuple) and target[0] == "board":
            return self.switch(target[1])
        if isinstance(event, Key) and event.name == "char" and event.char == "p" and not self.editing and \
                not (event.ctrl or event.alt):
            return self.switch("issues" if self.board == "pulls" else "pulls")
        if self.board == "pulls":
            return self.pulls.handle(event)
        if isinstance(event, Mouse):
            return self.mouse(event)
        if not isinstance(event, Key):
            return None
        if self.confirm:
            return self.answer(self.confirm.handle(event))
        if self.menu:
            choice = self.menu.menu.handle(event)
            if choice is TYPED:
                self.refresh_menu()
                return None
            if choice == "cancel":
                self.close_menu()
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
            return self.ask(replace(self.query, state=state, search="")) if state != self.query.state else None
        elif name in ("/", "s"):
            self.searching = True
        elif name in ("a", "u", "l"):
            self.open_filters({"a": "assigned", "u": "authored", "l": "label"}[name])
        elif name == "c":
            return Action("new_issue", ())
        elif name == "R":
            return self.ask()
        else:
            return self.on_issue(name, self.list.selected())
        return None

    def type(self, event):
        """A key in the search field: Enter or ↓ back to the list, what is typed kept; Esc clears it and goes back;
        Backspace in an empty field takes the last chip off."""
        if event.name in ("enter", "down", "tab", "esc"):
            self.searching = False
            if event.name == "esc" and self.field.text:
                self.field.clear()
                self.rebuild()
            return None
        if event.name == "backspace" and not self.field.text:
            return self.backspace()
        before = self.field.text
        self.field.handle(event)
        if self.field.text != before:
            self.list.index = 0
            self.rebuild()
        return None

    # --- the menus

    def close_menu(self):
        """Its menus closed, its pull requests' too, as a click outside them closes them: the pane lost the keys."""
        Filtered.close_menu(self)
        self.pulls.close_menu()

    def pick(self, choice):
        """CHOICE of a menu: a filter turned on or off (the menu stays), what to do with the issue the menu was opened
        on, or its priority or type set."""
        popup = self.menu
        if self.kind == "filters":
            action = popup.on[next(n for n, one in enumerate(popup.menu.choices) if one is choice)]
            return self.turn(action) if action else None
        if isinstance(self.kind, tuple):
            action = popup.on[next(n for n, one in enumerate(popup.menu.choices) if one is choice)]
            if not action:
                return None
            _, what, issue = self.kind
            self.close_menu()
            return self.set_value(issue, what, *action)
        self.close_menu()
        what, value = popup.on[choice]
        if what in SETS:
            self.set_menu(what, value, popup)
            return None
        return self.on_issue(what, value)

    def set_menu(self, what, issue, popup):
        """The right click's Priority… or Type… (WHAT): a second menu in the first one's place, its head the issue's
        number with what it sets, then none of them and the options, a check on the one it has."""
        y, x, _ = popup.menu.at(popup.y, popup.x, self.canvas.width, self.top, self.top + self.height, PAD)
        settable, (name, none) = self.listing.settable, SETS[what]
        current = issue.priority if what == "priority" else issue.issue_type
        options = settable["options"] if what == "priority" else settable["types"]
        level = lambda words: rank(words) if what == "priority" else None          # noqa: E731
        nothing = Row(none, on=not current, mark=("●", NO_PRIORITY)) if what == "priority" else \
            Row(none, on=not current, wide=True)                      # no priority: the bar's own grey dot
        choices = [Heading(f"#{issue.number} · {name}", head=True), None, nothing]
        choices += [Row(words, on=current == words, mark=("●", PRIORITY_ROLE[level(words)])
                        if level(words) is not None else None) for _, words in options]
        actions = [None, None, (None, none.lower())] + [(key, words) for key, words in options]
        menu = Menu(choices)
        menu.index = next((n for n, choice in enumerate(choices) if isinstance(choice, Row) and choice.on), 2)
        self.menu, self.kind = Popup(menu, actions, y, x), ("set", what, issue)

    def set_value(self, issue, what, value, words):
        """ISSUE's priority or type (WHAT) set to VALUE (an option's or a type's id; None: none; WORDS its name): its
        row as set at once, then asked of GitHub (a failure asks the list again)."""
        field = self.listing.settable["field"] if what == "priority" else ""
        shown = words if value else ""
        changed = replace(issue, **({"priority": shown} if what == "priority" else {"issue_type": shown}))
        def swap(rows):
            return None if rows is None else tuple(changed if one.number == issue.number else one for one in rows)
        self.listing = replace(self.listing, issues=swap(self.listing.issues), narrowed=swap(self.listing.narrowed))
        self.rebuild()
        return Action("issue_set", (changed, what, value, words, field))

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
        """The right click's menu on ISSUE: everything the keys do with it, Assign to me, and Priority… and Type…
        where the organization has the field or types and the user a role that sets them."""
        verb = "Reopen" if issue.state == "CLOSED" else "Close"
        settable = (self.listing.settable if self.listing else None) or {}
        picks = {"Open": ("o", issue), "Open in the browser": ("b", issue), "To the agent": ("t", issue),
                 "Reply": ("r", issue), "Assign to me": ("assign", issue)}
        if settable.get("options"):
            picks["Priority…"] = ("priority", issue)
        if settable.get("types"):
            picks["Type…"] = ("type", issue)
        picks[f"{verb}…"] = ("x", issue)
        self.menu, self.kind = Popup(Menu(picks), picks, y, x), "issue"

    def answer(self, yes):
        if yes is None:
            return None
        issue, self.confirm, self.doomed = self.doomed, None, None
        return Action("issue_change", (issue, "reopen" if issue.state == "CLOSED" else "close")) if yes else None

    def mouse(self, event):
        target = self.canvas.hit(event.x, event.y) if self.canvas else None
        if event.kind == "move":
            self.hover = target[1] if isinstance(target, tuple) and target[0] in ("issue", *HOVER) else None
            self.pointed = target if target in ("filters", "refresh", "clear") or isinstance(target, tuple) and \
                target[0] in ("state", "chip") else None
            if self.menu:
                self.menu.menu.point(target)
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
            if str(target).startswith("menu:"):
                return self.pick(self.menu.menu.choices[int(target[5:])])
            self.close_menu()
            return None
        self.searching = target == "input" and event.button == 0
        if target == "filters" and event.button == 0:
            self.open_filters()
        elif target == "clear" and event.button == 0:
            return self.clear()
        elif isinstance(target, tuple) and target[0] == "chip" and event.button == 0:
            return self.drop_chip(target[1])
        elif target == "refresh" and event.button == 0:
            return None if self.asked else self.ask()
        elif isinstance(target, tuple) and target[0] == "state" and event.button == 0:
            return self.ask(replace(self.query, state=target[1], search="")) if target[1] != self.query.state else None
        elif isinstance(target, tuple) and target[0] in ("issue", *HOVER):
            kind_, index = target
            self.list.index = index
            issue = self.list.selected()
            if event.button == 2:
                self.issue_menu(issue, event.y, event.x)
            elif event.button == 0:
                return Action({"agent": "issue_to_agent", "web": "issue_web"}.get(kind_, "preview_issue"), (issue,))
        return None
