"""The sidebar's pull requests: the Issues view's other list (issues.py switches to it), laid out and filtered as its
issues (checks, number, title, review; branch, author, age), and the form that opens one in Changes (scm.py), its title
and body written by the agent. The views only ask: gh runs in the app's jobs."""
import time
from dataclasses import replace

from filters import Filtered, Filters, counted
from github import ME, PULL_GROUPS, PULL_STATES, Query, ago, checks_mark, checks_said, pull_facets, pull_search, \
    review_state
from icons import glyphs
from screen import PAD, SPIN, SPINNER, Style, truncate, width
from vt import Key, Mouse
from widgets import TYPED, Action, ListView, Popup, TextInput

KEYS = {"t": "pull_to_agent", "b": "pull_web", "o": "preview_pull", "enter": "preview_pull"}
HOVER = ("agent", "web")                  # the buttons a pull request shows on hover, in this order
MARKS = {"passed": ("✓", "added"), "running": ("●", "modified"), "failed": ("✕", "deleted")}     # the checks'
# a review's state (core/github.py's review_state) as one word and its color role
REVIEW = {"draft": ("Draft", "muted"), "yours": ("your review", "modified"), "changes": ("changes", "deleted"),
          "approved": ("approved", "added"), "merged": ("merged", "muted"), "closed": ("closed", "muted")}
TEXT = 3                      # a pull request's number: its checks' mark, a cell of air and the margin before it
BAND = 1                      # a row's highlight a cell in from each side, as an issue's
# the Review group's values in the filters' menu: its words and their role, as the rows' (REVIEW) in full
REVIEWS = {"draft": ("Draft", None), "yours": ("Your review", "modified"), "approved": ("Approved", "added"),
           "changes": ("Changes requested", "deleted")}
CHECKS = {"passed": "Passing", "running": "Running", "failed": "Failing"}      # the Checks group's, with MARKS
FIELDS = ("into", "title", "body", "as", "create")      # the form's parts, in Tab's order
BODY_ROWS = 4                 # the body's rows at least, as the app's


def mark(canvas, y, x, pull, bg=None):
    """PULL's checks' mark at column X of row Y: ✓ green, ● yellow while they run, ✕ red, none without checks."""
    glyph, role = MARKS.get(checks_mark(pull.checks), ("", None))
    if glyph:
        canvas.put(y, x, glyph, Style(fg=role, bg=bg))


def review_word(pull):
    """PULL's review state as (its word, its role), or None."""
    return REVIEW.get(review_state(pull))


def look(group, value, icons):
    """How a filter's VALUE reads in GROUP (filters.py's Filters): a review's word in its row's color, the checks'
    mark."""
    if group == "review":
        return REVIEWS[value][0], None, REVIEWS[value][1]
    if group == "checks":
        return CHECKS[value], MARKS[value], None
    return value, None, None


def valid(group, value):
    """Whether a kept VALUE can be one of GROUP's."""
    if group in ME:
        return value is True
    return value in (REVIEWS if group == "review" else CHECKS) if group in ("review", "checks") \
        else isinstance(value, str) and bool(value)


class Pulls(Filtered):
    ROWS, SEARCH = "pulls", staticmethod(pull_search)

    def __init__(self, icons=True, now=time.time):
        self.icons, self.now = icons, now
        self.query, self.filters = Query(), Filters(PULL_GROUPS, look)
        self.asked = self.listing = self.answered = None    # the query on its way, the answer shown and its query
        self.field, self.searching = TextInput(placeholder="Filter pull requests"), False
        self.list = ListView()
        self.hover = self.pointed = self.canvas = self.menu = self.kind = None     # its menu: the filters'
        self.items, self.drop = [], (0, 0)          # the facets its menu counts: the latest answer's; where it opens
        self.totals = None                          # the repository's open and closed ones, as last told

    @property
    def state(self):
        return self.query.state

    @property
    def editing(self):
        """Whether the view holds the keys: the filter field, its menu (the app's own keys wait)."""
        return self.searching or self.menu is not None

    def kept(self):
        return {"state": self.query.state, "chosen": self.filters.kept()}

    def take(self, kept):
        """The filters kept() wrote (a version before this one kept none)."""
        if not isinstance(kept, dict):
            return
        self.query = Query(kept.get("state") if kept.get("state") in PULL_STATES else "open")
        self.filters.take(kept.get("chosen"), valid)

    def ask(self, query=None):
        """The pull requests of QUERY (the current one by default) asked for again; another query's no longer shown
        meanwhile, the same query's staying where they are (its search's too)."""
        self.query = query or self.query
        if self.answered is None or replace(self.answered, search="") != replace(self.query, search=""):
            self.listing = None
            self.rebuild()
        self.asked = self.query
        return Action("load_pulls", (self.query,))

    def show(self, listing, query):
        """The answer (core/github.py's Pulls) for QUERY; one for a query no longer chosen is dropped. Returns the ask
        its search wants now, or None."""
        if query != self.query:
            return None
        self.asked, self.listing, self.answered = None, listing, query
        self.totals = listing.totals or self.totals
        self.rebuild()
        self.items = [pull_facets(pull, listing.me) for pull in listing.pulls]
        self.refresh_menu()
        return None if listing.error else self.follow()

    def rebuild(self):
        words, chosen = self.field.text.lower().split(), self.list.selected()
        listing = self.listing
        searched = listing and listing.narrowed is not None and self.answered == self.query
        found = (listing.narrowed if searched else listing.pulls) if listing else ()
        me = listing.me if listing else ""
        self.list.set([pull for pull in found if all(word in self.said(pull) for word in words)
                       and self.filters.narrows(pull_facets(pull, me))])
        if chosen is not None:
            self.list.index = next((n for n, pull in enumerate(self.list.items) if pull.number == chosen.number),
                                   self.list.index)
            self.list.keep_visible()

    def said(self, pull):
        """What the filter finds PULL by: its number, title, branch and author, lowercase."""
        return " ".join((f"#{pull.number}", pull.title, pull.branch, "@" + self.author(pull))).lower()

    def author(self, pull):
        return "you" if self.listing and self.listing.me and pull.author == self.listing.me else pull.author

    # --- drawing

    def draw(self, canvas, top, height, roomy):
        """The view from row TOP, HEIGHT rows: the filter field with its funnel and +, what is on as chips under it,
        Open and Closed and the refresh button, then the pull requests, or on the first one's row what is asked or
        found."""
        self.canvas, cells = canvas, canvas.width
        row, taken = canvas.control(top, 1, cells - 2, 1, "input", roomy)
        for y in range(top, top + taken):
            canvas.region(y, 1, cells - 4, "input")
        self.drop = (top + taken, cells - 1)
        funnel = cells - 5                              # its cell of air, then + and its own, as Issues' funnel
        self.filters.funnel(canvas, row, funnel, self.icons, self.pointed == "filters" or self.menu is not None)
        canvas.put(row, cells - 3, "+", Style(fg="text" if self.pointed == "new" else "muted", bg="input"))
        canvas.region(row, cells - 4, cells - 1, "new")
        self.field.draw(canvas, row, 3, max(1, funnel - 4), 1, Style(bg="input"), focused=self.searching)
        y = top + taken
        if self.filters.on():
            y += self.filters.draw_chips(canvas, y, self.icons, self.pointed)
        elif not roomy:
            y += 1
        x = 1
        for name, label in PULL_STATES.items():           # Open and Closed with their counts, as Issues has them
            label = counted(label, self.totals, name)
            chosen, pointed = name == self.state, self.pointed == ("state", name)
            if chosen or pointed:
                canvas.chip(y, x, width(label) + 2, "button" if chosen else "hover")
            style = (Style(fg="button_text", bg="button", bold=True) if chosen
                     else Style(fg="text", bg="hover") if pointed else Style(fg="muted"))
            end = canvas.put(y, x + 1, truncate(label, max(1, cells - x - 2)), style)
            canvas.region(y, x, end + 1, ("state", name))
            x = end + 2
        running = self.asked and self.list.items
        spin = SPINNER[int(self.now() / SPIN) % len(SPINNER)] if running else glyphs(self.icons)["refresh"]
        canvas.put(y, cells - 2, spin, Style(fg="text" if self.pointed == "refresh" else "muted"))
        canvas.region(y, cells - 2, cells, "refresh")
        y += 2
        line = self.line()
        if line:
            canvas.put(y, PAD, truncate(line[0], cells - 2 * PAD), Style(fg=line[1]))
        items = max(1, (top + height - y) // 2)
        if self.list.height != items:
            self.list.resize(items)
        for at in range(self.list.height):
            index = self.list.at(at)
            if index is None:
                break
            self.row(canvas, y + 2 * at, index)
        if self.menu:
            self.menu.menu.draw(canvas, *self.menu.menu.at(self.menu.y, self.menu.x, cells, top, top + height, PAD))

    def line(self):
        """What the list's first row says while there is no pull request to show, and its role."""
        if self.list.items:
            return None
        if self.asked:
            return "Loading pull requests…", "muted"
        if self.listing is None:
            return None
        if self.listing.error:
            return self.listing.error, "deleted"
        filtered = self.filters.on() or self.field.text.strip()
        return ("No pull requests match" if filtered else f"No {self.state} pull requests"), "muted"

    def tip(self, target):
        return "Loading pull requests…" if target == "refresh" and self.asked else \
            "New pull request: in Changes" if target == "new" else None

    def row(self, canvas, y, index):
        """A pull request's two rows on its highlight (BAND in from each side): its checks' mark at the highlight's
        edge, its number and title, its review's state at the end; its branch, author, age and (unless they passed)
        checks under them; the hover buttons on its first row; each a cell inside the highlight's end."""
        pull, cells = self.list.items[index], canvas.width
        hovered = index == self.hover
        bg = "selection" if index == self.list.index else ("hover" if hovered else None)
        for r in (y, y + 1):
            if r < canvas.height:
                canvas.band(r, bg, BAND)
                canvas.region(r, 0, cells, ("pull", index))
        end = cells - 1 - BAND
        if hovered:
            end -= 2 * len(HOVER)
            for i, kind in enumerate(HOVER):
                canvas.put(y, end + 2 * i, glyphs(self.icons)[kind], Style(fg="text", bg=bg))
                canvas.region(y, end + 2 * i, end + 2 * i + 2, (kind, index))
        else:
            word = review_word(pull)
            if word:
                end -= width(word[0])
                canvas.put(y, end, word[0], Style(fg=word[1], bg=bg))
        mark(canvas, y, 1, pull, bg)
        x = canvas.put(y, TEXT, f"#{pull.number}", Style(fg="muted", bg=bg))
        canvas.put(y, x + 1, truncate(pull.title, max(1, end - x - 2)), Style(fg="text", bg=bg))
        if y + 1 < canvas.height:
            under = [pull.branch, self.author(pull), ago(pull.updated, self.now()),
                     "" if checks_mark(pull.checks) == "passed" else checks_said(pull.checks)]
            canvas.put(y + 1, TEXT, truncate(" · ".join(part for part in under if part), cells - TEXT - 1 - BAND),
                       Style(fg="muted", bg=bg))

    # --- events

    def handle(self, event):
        if isinstance(event, Mouse):
            return self.mouse(event)
        if not isinstance(event, Key):
            return None
        if self.menu:
            choice = self.menu.menu.handle(event)
            if choice is TYPED:
                self.refresh_menu()
            elif choice == "cancel":
                self.close_menu()
            elif choice is not None:
                return self.pick(choice)
            return None
        if self.searching:
            return self.type(event)
        name = event.char if event.name == "char" and not (event.ctrl or event.alt) else event.name
        if name in ("up", "down"):
            self.list.move(1 if name == "down" else -1)
        elif name in ("pageup", "pagedown"):
            self.list.page(1 if name == "pagedown" else -1)
        elif name in ("home", "end"):
            self.list.move(len(self.list.items) * (1 if name == "end" else -1))
        elif name in ("left", "right"):
            state = "closed" if name == "right" else "open"
            return self.ask(replace(self.query, state=state, search="")) if state != self.state else None
        elif name in ("/", "s"):
            self.searching = True
        elif name in ("a", "u", "l"):
            self.open_filters({"a": "assigned", "u": "authored", "l": "label"}[name])
        elif name == "c":
            return Action("new_pull", ())
        elif name == "R":
            return self.ask()
        elif name in KEYS and self.list.selected() is not None:
            return Action(KEYS[name], (self.list.selected(),))
        return None

    def type(self, event):
        """A key in the filter field: Enter or ↓ back to the list, what is typed kept; Esc clears it and goes back;
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

    def pick(self, choice):
        """CHOICE of its filters menu: a filter turned on or off, the menu staying open."""
        action = self.menu.on[next(n for n, one in enumerate(self.menu.menu.choices) if one is choice)]
        return self.turn(action) if action else None

    def mouse(self, event):
        target = self.canvas.hit(event.x, event.y) if self.canvas else None
        if event.kind == "move":
            self.hover = target[1] if isinstance(target, tuple) and target[0] in ("pull", *HOVER) else None
            self.pointed = target if target in ("refresh", "new", "filters", "clear") or isinstance(target, tuple) \
                and target[0] in ("state", "chip") else None
            if self.menu:
                self.menu.menu.point(target)
        elif event.kind in ("wheel_up", "wheel_down"):
            self.list.scroll(3 if event.kind == "wheel_down" else -3)
        elif event.kind == "press" and self.menu:
            if str(target).startswith("menu:"):
                return self.pick(self.menu.menu.choices[int(target[5:])])
            self.close_menu()
        elif event.kind == "press" and event.button == 0:
            self.searching = target == "input"
            if target == "refresh":
                return None if self.asked else self.ask()
            if target == "new":
                return Action("new_pull", ())
            if target == "filters":
                return self.open_filters()
            if target == "clear":
                return self.clear()
            if isinstance(target, tuple) and target[0] == "chip":
                return self.drop_chip(target[1])
            if isinstance(target, tuple) and target[0] == "state":
                return self.ask(replace(self.query, state=target[1], search="")) if target[1] != self.state else None
            if isinstance(target, tuple) and target[0] in ("pull", *HOVER):
                self.list.index = target[1]
                kind = {"agent": "pull_to_agent", "web": "pull_web"}.get(target[0], "preview_pull")
                return Action(kind, (self.list.selected(),))
        return None


class PullForm:
    """A new pull request of BRANCH into one of BASES (the default first), as GitHub's own form: Into, Title, Body,
    Draft or Ready, and one button; Tab the next part, ← → choose, Esc gives it up."""

    def __init__(self, branch, bases, icons=True):
        self.branch, self.bases, self.base, self.icons = branch, list(bases), bases[0], icons
        self.title, self.body = TextInput(placeholder="Title"), TextInput(multiline=True, placeholder="Body")
        self.draft, self.focus, self.commits = True, "title", 0
        self.note = None              # (what wrote it or why nothing was, its role)
        self.writing = None           # while ✦ writes: who writes it, its spinner's frame first
        self.canvas = None

    def fill(self, answer):
        """The writer's ANSWER (core/commit_message.py's pull): the title and the body, what wrote them."""
        if answer.get("title"):
            self.title.clear()
            self.title.insert(answer["title"])
        self.body.clear()
        self.body.insert(answer.get("body") or "")
        self.title.cursor = self.body.cursor = 0              # both shown from their start
        self.commits = answer.get("commits") or 0
        by = "Codex" if answer.get("backend") == "codex" else "Claude"
        self.note = (f"{by} wrote it from {self.commits} commit{'' if self.commits == 1 else 's'}", "muted") \
            if answer.get("title") else (answer.get("note") or "No title written", "deleted")

    @property
    def label(self):
        return "Create draft" if self.draft else "Create pull request"

    def draw(self, canvas, top, roomy):
        """The form from row TOP; returns the row under it."""
        self.canvas, cells = canvas, canvas.width
        field = lambda part: Style(bg="input") if self.focus != part else Style(bg="hover")   # noqa: E731
        canvas.put(top, 1, "New pull request", Style(fg="text", bold=True))
        y = top + 1
        x = canvas.put(y, 1, "Into ", Style(fg="muted"))
        into = f"‹ {self.base} ›"
        x = canvas.put(y, x, into, Style(fg="text", bg="hover" if self.focus == "into" else "input"))
        canvas.region(y, 1, x, "into")
        canvas.put(y, x + 1, truncate(f"from {self.branch}", max(1, cells - x - 2)), Style(fg="muted"))
        y += 1
        canvas.put(y, 1, "Title", Style(fg="muted"))
        canvas.put(y, 7, " " * (cells - 8), field("title"))
        canvas.region(y, 7, cells - 1, "title")
        self.title.draw(canvas, y, 8, cells - 10, 1, field("title"), focused=self.focus == "title")
        y += 1
        rows = max(BODY_ROWS, min(8, len(self.body.lines(cells - 10))))
        canvas.put(y, 1, "Body", Style(fg="muted"))
        for r in range(rows):
            canvas.put(y + r, 7, " " * (cells - 8), field("body"))
            canvas.region(y + r, 7, cells - 1, "body")
        self.body.draw(canvas, y, 8, cells - 10, rows, field("body"), focused=self.focus == "body")
        y += rows + 1
        x = canvas.put(y, 1, "As    ", Style(fg="muted"))
        for draft, text in ((True, "Draft"), (False, "Ready for review")):
            chosen = self.draft == draft
            end = canvas.put(y, x, f" {text} ", Style(fg="text" if chosen else "muted", bold=chosen,
                                                     bg="hover" if chosen and self.focus == "as" else
                                                     "selection" if chosen else None))
            canvas.region(y, x, end, ("as", draft))
            x = end + 1
        y += 1
        note, role = (self.writing, "muted") if self.writing else self.note or ("", "muted")
        x = canvas.put(y, 1, truncate(note, max(1, cells - 12)), Style(fg=role))
        if not self.writing:
            end = canvas.put(y, x + 1, f"{glyphs(self.icons)['ai']} again", Style(fg="muted"))
            canvas.region(y, x + 1, end, "again")
        y += 1
        lit = bool(self.title.text.strip()) and not self.writing
        x = max(1, cells - 1 - width(f" {self.label} "))           # the one button at the row's right end
        if x > 4:
            canvas.put(y, 1, truncate("Esc cancels · Tab the next", x - 3), Style(fg="dim"))
        end = canvas.put(y, x, f" {self.label} ", Style(fg="button_text" if lit else "muted",
                                                       bg="button" if lit else "input", bold=True))
        canvas.region(y, x, end, "create")
        return y + 2

    def handle(self, event):
        """A key or a press: an Action (write again, open, give up), or None."""
        if isinstance(event, Mouse):
            if event.kind != "press" or event.button != 0 or not self.canvas:
                return None
            target = self.canvas.hit(event.x, event.y)
            if isinstance(target, tuple) and target[0] == "as":
                self.draft, self.focus = target[1], "as"
            elif target == "again":
                return self.again()
            elif target == "create":
                return self.create()
            elif target in FIELDS:
                self.focus = target
            return None
        if not isinstance(event, Key):
            return None
        if event.name == "esc":
            return Action("pull_cancel", ())
        if event.name == "tab":
            step = -1 if event.shift else 1
            self.focus = FIELDS[(FIELDS.index(self.focus) + step) % len(FIELDS)]
        elif self.focus in ("title", "body"):
            field = self.title if self.focus == "title" else self.body
            if event.name == "enter" and self.focus == "title":
                self.focus = "body"
            elif not field.handle(event) and event.name == "down" and self.focus == "title":
                self.focus = "body"
        elif self.focus == "into" and event.name in ("left", "right") and len(self.bases) > 1:
            self.base = self.bases[(self.bases.index(self.base) + (1 if event.name == "right" else -1))
                                   % len(self.bases)]
            return self.again()
        elif self.focus == "as" and event.name in ("left", "right"):
            self.draft = event.name == "left"
        elif self.focus == "create" and event.name == "enter":
            return self.create()
        elif self.focus == "create" and event.name == "char" and event.char == "A":
            return self.again()
        return None

    def again(self):
        return None if self.writing else Action("write_pull", (self.base,))

    def create(self):
        title = self.title.text.strip()
        if not title or self.writing:
            return None
        return Action("open_pull", (self.base, self.branch, title, self.body.text, self.draft))
