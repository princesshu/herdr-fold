"""The sidebar: Conversations, Files, Search, Changes and, for a repository on GitHub, Issues in one pane, one at a time
under a row of tabs. One process: the screen and keys on the main thread, slow commands on background threads that wake
the loop, so the view never waits. Usage: python3 sidebar.py [FOLDER] (in the home folder: ~/Documents)"""
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import column  # noqa: E402
import commit_message  # noqa: E402
import panes  # noqa: E402
import git  # noqa: E402
import media  # noqa: E402
import panels  # noqa: E402
import preview  # noqa: E402
import stack  # noqa: E402
import statefile  # noqa: E402
import update  # noqa: E402
from changes_panel import Changes  # noqa: E402
from conversations_panel import Conversations  # noqa: E402
from files_panel import Files  # noqa: E402
from loop import CODE, Loop  # noqa: E402
from dock import GROUPS, PANELS  # noqa: E402
from screen import ROOMY, Canvas, Style, centered, truncate, width  # noqa: E402
from tree import git_marks  # noqa: E402
from vt import Focus, Key, Mouse, Resize  # noqa: E402
from widgets import Menu, wrap  # noqa: E402
import watch  # noqa: E402

# 1 to 5 in the tab row's order; F9 to F12 are what herdr's actions send (actions.py), as F7 to find a conversation
VIEW_KEYS = {"1": "conversations", "2": "files", "3": "search", "4": "changes", "5": "issues", "f9": "files",
             "f10": "search", "f11": "changes", "f12": "issues"}
FIND = "f7"
START = "files"               # the panel a folder starts on: its keys (n . q) work at once, Chats' filter takes them
# linked: the issue each repository's next commit fixes, {repository: [number, title]}
DEFAULTS = {"hidden": False, "icons": True, "commit_mode": "commit", "linked": {}, "folded": [], "hidden_panels": []}
UPDATES = 3600.0              # seconds between two looks at update.json (GitHub itself is asked once a day at most)
CHECK = "Check for Updates"   # the ⋯ menu's switch, a ✓ while it is on
FAMILIES = (Conversations, Files, Changes)        # the panel families the dock hosts, in its groups' order
FOLD_DOCK, OPEN_DOCK = "»", "«"   # at the tab row's end: » folds the dock to its rail, « on the rail opens it again
NOTE = 4.0                    # seconds a note ("Archived", "Renamed") stays on the last row; an error stays till a key
TIP_DELAY = 0.5               # seconds the mouse rests on a control shown by an icon before it says what it does
# what each such control does, by its target (a row's buttons by their kind)
TIPS = {"suggest": "Write message", "mode": "Commit mode", "sync": "Sync", "panels": "More actions",
        "to_rail": "Collapse to icons", "to_dock": "Expand panels", "unlink": "Unlink issue",
        "new_file": "New file", "new_folder": "New folder", "refresh": "Refresh",
        "collapse": "Collapse all", "case": "Match case", "word": "Whole word", "regex": "Regular expression",
        "clear": "Clear", "stage": "Stage", "unstage": "Unstage", "discard": "Discard changes", "diff": "Show diff",
        "agent": "To agent", "web": "Open in browser", "remote": "More actions"}


def grouped(tabs):
    """GROUPS with the panels of TABS there, a group without any left out."""
    return [(group, [panel for panel in members if panel in tabs]) for group, members in GROUPS
            if any(panel in tabs for panel in members)]


def narrowest(tabs):
    """The cells the tab row takes with the panels TABS shown: what the column keeps to at least (column.need())."""
    return stack.cells(grouped(tabs))


def load_settings(path):
    return settings_of(statefile.read(path))


def settings_of(data):
    """DEFAULTS' keys in DATA (settings.json's), each of its own type, else its default."""
    return {key: data[key] if isinstance(data.get(key), type(value)) else value for key, value in DEFAULTS.items()}


def identity(path):
    try:
        found = os.stat(path)
    except OSError:
        return None
    return found.st_dev, found.st_ino


def moved_to(root, known):
    """Where folder ROOT went, renamed or moved (KNOWN: its identity, which goes with it): the working folder went with
    it, or it is beside where it was. None while it is there, and once it is gone."""
    if known is None or os.path.isdir(root):
        return None
    places = []
    try:
        here = os.getcwd()
    except OSError:                                 # the working folder deleted
        here = None
    while here:
        places.append(here)
        up = os.path.dirname(here)
        here = None if up == here else up
    try:
        places += [entry.path for entry in os.scandir(os.path.dirname(root)) if entry.is_dir(follow_symlinks=False)]
    except OSError:
        pass
    return next((os.path.realpath(place) for place in places if identity(place) == known), None)


@dataclass
class Look:
    """The repository's status as the dock's status job found it, for each family to take what it shows."""
    repo: str                 # None outside a repository
    github: str               # OWNER/NAME on GitHub, or None
    status: object            # git.Status
    marks: dict               # the file view's marks (tree.git_marks)
    graph: list               # the recent commits, None when Changes was not shown
    issue: tuple              # the issue the next commit fixes: (number, title), or None


class App(Loop):
    def __init__(self, root, terminal, herdr, state_dir, clock=time.monotonic, code=CODE):
        super().__init__(terminal, herdr, state_dir, clock, code)
        # the real path: git names the repository by it, a symbolic link on the way would hide every git mark
        self.root = os.path.realpath(root)
        self.identity, self.moved = identity(self.root), None    # a renamed or moved folder keeps its identity
        self.settings = load_settings(os.path.join(state_dir, "settings.json"))
        self.repo = git.top(self.root)                  # None outside a repository; checked again by each status
        self.own = self.repo                            # the folder's own repository; without one, the chosen's
        self.looked = None                              # the folder chosen in Files the last status was asked for
        self.head = None                                # the latest commit seen: a newer one may close the linked issue
        self.github = git.github_name(self.repo) if self.repo else None     # OWNER/NAME on GitHub, or None
        self.status = None
        self.families = [family(self) for family in FAMILIES]
        self.work = {panel: family for family in self.families for panel in family.PANELS}    # each panel's family
        self.views = {panel: view for family in self.families for panel, view in family.views.items()}
        self.dock = stack.state(state_dir, self.root)    # the panel shown in this folder
        self.railed = column.railed(state_dir)            # the dock folded to its rail, in every tab (column.json)
        self.beside = False                               # on the rail, the panel shown opened beside it in this tab
        self.owed = False                                 # this tab left as it was by a fold (its agent zoomed)
        self.body = None                                  # the panel's rows, as last drawn: (top, rows)
        self.reach = 0                                    # the cells the panel takes, as last drawn: up to the rail
        self.watcher = watch.Watcher(self.work["files"].tree.expanded_dirs, git.git_dir(self.root), clock)
        self.pointed = None                               # under the mouse: a panel's tab, the ⋯, », an icon
        self.dots = (0, None, 0)                          # where the ⋯'s menu opens: open_menu()'s arguments
        self.needs = None                                 # the cells this tab's tab row was said to take
        self.menu = None                                  # the pane's own menu: (Menu, its row, its column, its tab)
        self.tip = None                         # the control under the mouse: (target, tip, x, y, when due, drawn)
        self.noted = (None, 0.0)                          # the note on the last row, and when it came
        self.update, self.next_update = None, 0.0         # update.check()'s answer, and when to look again

    def stop(self):
        for family in self.families:
            family.stop()

    def panels(self):
        """The panels it can show here: its families', Issues only for a repository on GitHub."""
        return [panel for panel in PANELS if panel in self.views and (panel != "issues" or self.github)]

    def tabs(self):
        """The panels shown: the ones not hidden in the ⋯'s Panels; the first, when another tab hid every one this one
        can show (all but Issues, on GitHub there, here not)."""
        hidden = self.settings["hidden_panels"]
        return [panel for panel in self.panels() if panel not in hidden] or self.panels()[:1]

    def hide(self, panel, hidden):
        """PANEL hidden (HIDDEN) or shown again, in every tab, on what settings.json holds then (another tab's sidebar
        may hide one at the same moment); never the last one shown."""
        last = []

        def change(settings):
            others = [name for name in settings["hidden_panels"] if name != panel]
            if hidden and not [name for name in self.panels() if name not in others + [panel]]:
                last.append(panel)
                return settings
            return {**settings, "hidden_panels": others + [panel] if hidden else others}

        self.save(change)
        if last:
            self.note = "One panel stays shown"
        self.fit()

    def fit(self):
        """The cells the tab row takes now, said to the column when they changed (column.need()); once more when they
        change while that runs, so the last change lands last."""
        if narrowest(self.tabs()) != self.needs:
            self.needs = narrowest(self.tabs())
            self.tell_need()

    def tell_need(self):
        if "need" in self.running:
            self.again.add("need")
            return
        self.job("need", lambda cells=self.needs: self.need(cells), self.told_need)

    def told_need(self, _answer):
        if "need" in self.again:
            self.again.discard("need")
            self.tell_need()

    def groups(self):
        """The tab row's groups: GROUPS with the panels shown, a group without any left out."""
        return grouped(self.tabs())

    def shown(self):
        """The panel shown: the one kept for this folder while it is a tab here (hidden, or Issues off GitHub, it comes
        back with its tab), else Files, else the first tab."""
        tabs, kept = self.tabs(), self.dock["shown"]
        return kept if kept in tabs else START if START in tabs else tabs[0]

    def showing(self, panel):
        """Whether PANEL is on screen: the one shown, the dock open or, on the rail, PANEL opened beside it."""
        return panel == self.shown() and (self.beside or not self.railed)

    def keyed(self):
        """The panel with the keys: the one shown while it is on screen; None on the rail alone."""
        shown = self.shown()
        return shown if self.showing(shown) else None

    def keep_dock(self, shown):
        """SHOWN the panel this sidebar shows, and kept for its folder (dock.json: another sidebar on this folder, a
        preview tab's, writes it too)."""
        self.dock["shown"] = shown
        try:
            stack.keep(self.state_dir, self.root, shown)
        except OSError as err:
            self.error = f"settings not saved: {err}"

    def refresh(self):
        """Ask git for the status (and the graph while Changes shows); once more when asked while running.
        The repository is looked up again each time (git init, or a .git taken away), its name on GitHub with it, and
        the file view's marks are worked out on the job's thread too."""
        if "status" in self.running:
            self.again.add("status")
            return
        root, with_graph, started = self.root, self.showing("changes"), self.clock()
        settings = os.path.join(self.state_dir, "settings.json")
        place = self.looked = self.chosen_folder()
        known, seen = self.repo, self.head                  # the latest commit seen in the repository shown

        def work():
            own = git.top(root)
            repo = own or (git.top(place) if place != root else None)      # else that of the folder chosen in Files
            # not a repository when looked up: so it is shown, even if git init ran meanwhile (the next status has it)
            status = git.status(repo) if repo else git.Status(error=git.status(root).error or "not a git repository")
            graph = git.graph(repo) if repo and with_graph and not status.error else None
            name = git.github_name(repo) if repo else None
            # unlinked once a commit made anywhere (the commit window, a terminal, the agent) closed the issue
            settled = commit_message.settle(repo, seen if repo == known else None, self.state_dir) if repo else \
                (None, None)
            linked = load_settings(settings)["linked"]      # every tab's sidebar and the app mod link: one may be new
            return (repo, name, status, git_marks(status, repo or root, root), graph, started, self.clock(), linked,
                    settled, own)

        self.job("status", work, self.got_status)

    def got_status(self, answer):
        repo, self.github, self.status, marks, graph, started, finished, linked, (issue, head), self.own = answer
        self.fit()                                      # Issues came or went: the tab row's width with it
        if repo != self.repo:
            self.repo = repo
            self.watcher.git_dir = git.git_dir(repo) if repo else None
            self.head = None
        self.settings["linked"] = linked
        self.head = head or self.head
        look = Look(repo, self.github, self.status, marks, graph, issue)
        for family in self.families:
            family.took_status(look)
        self.watcher.status_done(started, finished)
        if "status" in self.again:
            self.again.discard("status")
            self.refresh()

    def tick(self):
        """The poll when due, the paused search and a tip come due; whether anything shown changed."""
        now = self.clock()
        shown = bool(self.tip) and not self.tip[5] and now >= self.tip[4]
        if self.note != self.noted[0]:                    # a new note, from the dock or a family
            self.noted = (self.note, now)
        elif self.note and now >= self.noted[1] + NOTE:   # it goes by itself
            self.note, shown = None, True
        if now >= self.next_update:
            self.next_update = now + UPDATES
            self.job("update", update.check, self.got_update)
        if now >= self.next_poll:
            shown = self.follow(now) or shown             # a new version first, before this poll starts a job
            if self.quit:
                return shown
            self.moved = self.moved or moved_to(self.root, self.identity)
            if self.moved:                                # on again where the folder went, once nothing is cut short
                if not self.busy():
                    self.hand_over()
                return shown
            hidden = load_settings(os.path.join(self.state_dir, "settings.json"))["hidden_panels"]
            if hidden != self.settings["hidden_panels"]:      # hidden or shown again in another tab's ⋯
                self.settings["hidden_panels"], shown = hidden, True
                self.fit()
            shown = self.follow_dock() or shown
            changed = self.watcher.poll()
            folders = [path for path in changed if path != "git"]
            if folders:
                self.reload(folders)
                shown = True
            if self.watcher.status_due(bool(changed), self.showing("changes")) or (
                    self.own is None and self.chosen_folder() != self.looked):    # another folder chosen in Files
                self.refresh()
            self.next_poll = now + (watch.PACES[0] if self.owed else self.watcher.interval())
        for family in self.families:                      # after the handover's turn: never during a look
            shown = family.tick(now) or shown
        return shown

    def busy(self):
        """Whether a restart would cut something short: any job but the update check (no program of its own, asked
        again by the new version), or a name being typed or a question on screen. A menu does not hold it: the new
        version comes back without it, as a click elsewhere closes it."""
        held = [hold for family in self.families for hold in family.holds()]
        return bool(self.running - {"update"}) or any(held)

    def left(self):
        shown = self.shown()
        left = {"show": shown} if self.showing(shown) else {}            # the rail alone stays so
        left["dock"] = self.dock                          # its own view, whatever another sidebar here changed since
        for family in self.families:
            left.update(family.left())
        return left

    def moved_path(self, path):
        """PATH in its folder's new place, once the folder moved."""
        if self.moved and path and (path == self.root or path.startswith(self.root + os.sep)):
            return self.moved + path[len(self.root):]
        return path

    def resume(self):
        """Come back where the version before this one was, or, in a new preview tab, where the sidebar that opened it
        was, or to the view last chosen; the issues asked for when they show, as a click on their view would."""
        super().resume()
        self.seeded()
        for family in self.families:            # a job only once the terminal is taken (its wake needs that)
            family.resume()
        if self.railed:                         # a new tab's or a preview tab's: its column the rail too
            self.reshape()

    def seeded(self):
        """A new preview tab's sidebar: where the sidebar that opened it was, left for its tab (open_preview())."""
        try:
            if not any(name.startswith("seed-") for name in os.listdir(self.state_dir)):
                return
        except OSError:
            return
        tab = preview.this_tab(self.herdr)
        path = preview.seed_file(self.state_dir, tab) if tab else None
        try:
            with open(path, encoding="utf-8") as f:
                left = json.load(f)
            os.remove(path)
        except (OSError, TypeError, ValueError):
            return
        if isinstance(left, dict):
            self.take(left)

    def take(self, left):
        if isinstance(left.get("dock"), dict):
            self.dock = stack.parsed(left["dock"])
        if left.get("show") in self.panels():          # hidden in the ⋯'s Panels: shown again (actions.find's seed)
            self.show(left["show"])
        for family in self.families:
            family.take(left)

    def deadlines(self):
        tip = self.tip[4] if self.tip and self.tip[4] > self.clock() else self.next_poll
        note = [self.noted[1] + NOTE] if self.note else []
        return [self.next_poll, tip] + note + [due for family in self.families for due in family.deadlines()]

    def point(self, target, x, y):
        """The mouse on TARGET at X, Y: a control shown by an icon says what it does once the mouse rests on it, a
        changed file its path, a name Files cuts short its path whole."""
        tip = TIPS.get(target[0] if isinstance(target, tuple) else target)
        view = self.views.get(self.panel_at(y, x))
        if not tip and hasattr(view, "tip"):            # a view's own: a changed file's path, a name cut short
            tip = view.tip(target)
        if not tip:
            self.tip = None
        elif not self.tip or self.tip[0] != target:
            self.tip = (target, tip, x, y, self.clock() + TIP_DELAY, False)

    def draw_tip(self, canvas):
        """The tip under the mouse (above it where the rows below are too few), whole inside the pane, once it is due;
        one too wide for a row goes on in the next (a path after a /)."""
        target, tip, x, y, due, _ = self.tip
        if self.clock() < due:
            return
        self.tip = (target, tip, x, y, due, True)
        lines = [tip[start:end] for start, end in wrap(tip, max(1, canvas.width - 2), breaks=" /")]
        cells = max(width(line) for line in lines) + 2
        top = y + 1 if y + len(lines) < canvas.height else max(0, y - len(lines))
        left = max(0, min(x, canvas.width - cells))
        for row, line in enumerate(lines):
            label = truncate(f" {line} ", canvas.width)
            canvas.put(top + row, left, label + " " * (cells - width(label)), Style(fg="text", bg="selection"))

    # --- settings

    def save(self, change=None, **changes):
        """CHANGES, or CHANGE (given the settings, their new value), made to what settings.json holds then
        (statefile.update): another tab's sidebar and the app write it too."""
        how = change or (lambda settings: {**settings, **changes})
        try:
            self.settings = statefile.update(os.path.join(self.state_dir, "settings.json"),
                                             lambda kept: how(settings_of(kept)), indent=2)
        except OSError as err:
            self.settings = how(self.settings)
            self.error = f"settings not saved: {err}"

    # --- events

    def handle(self, event):
        self.watcher.touch()
        if not (isinstance(event, Mouse) and event.kind == "move"):
            self.tip = None                               # a key, a click or the wheel: the tip goes
        if isinstance(event, Resize):
            self.renderer.reset()
            self.follow_dock()                    # folded or opened in another tab, which set this one's width
            self.resized()
            return
        if isinstance(event, Focus):
            if not event.gained:                  # a click in another pane: no menu stays open behind
                self.menu = None
                for view in self.views.values():
                    view.close_menu()
            return
        if self.menu and isinstance(event, (Key, Mouse)) and (isinstance(event, Key) or event.kind == "press"):
            self.act(self.answer_menu(event))
            return
        if isinstance(event, Key):
            if event.name == "char" and event.ctrl and event.char == "c":
                self.quit = True
                return
            self.error = self.note = None
            panel = self.keyed()
            editing = bool(panel) and self.views[panel].editing
            name = event.char if event.name == "char" and not (event.ctrl or event.alt) else event.name
            if name in VIEW_KEYS and (name.startswith("f") or not editing):
                self.show(VIEW_KEYS[name])
                return
            if name == FIND:
                self.show("conversations")
                self.work["conversations"].find()
                return
            if name == "q" and not editing:
                self.quit = True
                return
            if name == "esc" and self.beside and not self.engaged(panel):
                self.fly(False)
                return
            if panel:
                self.act(self.views[panel].handle(event), panel)
            return
        target = self.canvas.hit(event.x, event.y) if self.canvas else None
        if event.kind == "move":
            lit = target in ("panels", "to_rail", "to_dock") or str(target).startswith("icon:")
            self.pointed = target[4:] if str(target).startswith("tab:") else target if lit else None
            self.point(target, event.x, event.y)
        elif event.kind == "press":
            self.error = self.note = None
            if self.railed and not self.reach and event.button == 2:
                return                                # the rail alone: no room for a menu
            own = target in ("tabs", "sync", "panels", "to_rail", "to_dock") or str(target).startswith("tab:")
            if own:                                   # outside the panels: their menus close, as a click in one does
                for view in self.views.values():
                    view.close_menu()
            if target == "news":                                             # a newer version: its release
                self.do_open_url(update.RELEASES)
                return
            if target == "panels" and event.button != 2:                  # the ⋯: its menu right under it
                self.open_menu(*self.dots)
                return
            if target in ("to_rail", "to_dock") and event.button != 2:
                self.fold_dock(target == "to_rail")
                return
            if own and event.button == 2:             # a right click on the tab row: there
                self.open_menu(event.y, event.x)
                return
            kind, _, name = str(target).partition(":")
            if kind == "icon":
                if event.button != 2:
                    self.press_icon(name)
                return
            if kind == "tab":
                self.show(name)
                return
            if target == "sync":
                self.work["changes"].do_sync()
                return
        panel = self.panel_at(event.y, event.x)
        if panel:
            self.act(self.views[panel].handle(event), panel)

    def act(self, action, panel=None):
        """ACTION done by its PANEL's family where that has it, else by the dock (the icons, a URL opened)."""
        if action is not None:
            name = "do_" + action.name
            getattr(self.work[panel] if hasattr(self.work.get(panel), name) else self, name)(*action.args)

    def panel_at(self, y, x=0):
        """The panel drawn at row Y and column X; None on the tab row, under the panel or on the rail."""
        if x >= self.reach or not self.body:
            return None
        top, rows = self.body
        return self.shown() if top <= y < top + rows else None

    def need(self, cells):
        """On the job's thread: this tab's right column takes CELLS at least inside its frame (column.need(): the
        widths keep to it, this tab's own); widened at once if it is narrower."""
        pane = os.environ.get("HERDR_PANE_ID")
        if not pane:                                            # not in a herdr pane: no column to keep
            return
        try:
            listed = self.herdr.call("pane", "list").get("panes") or []
        except RuntimeError:
            return
        tab = next((p["tab_id"] for p in listed if p.get("pane_id") == pane), None)
        if not tab:
            return
        column.need(self.state_dir, tab, cells, {p["tab_id"] for p in listed})
        here = column.read(pane)
        if here and here.cells and not self.railed:             # the rail keeps to its own width
            least = cells + column.frame(here, pane, self.term.size()[0])
            if column.cells(here)[1] < least:
                column.arrange(here, right=least / here.cells)

    def drag(self, pane):
        """On the job's thread: PANE resized: by hand while the dock is open (Loop.drag()); on the rail, its column set
        back to the rail's width or the rail's and its panel's (a window resized, the rail dragged), nothing kept."""
        if not self.railed:
            return super().drag(pane)
        tab = column.read(pane)
        if tab and tab.cells:
            column.arrange(tab, right=column.width(self.state_dir, tab, True, self.beside))
        return 0

    # --- the pane's own menu: each of the tab's other panes closed or shown back

    def open_menu(self, y, x, right=None):
        """The ⋯ menu at Y, X (with RIGHT, its right edge there instead): the panels, each with a ✓ while shown, as
        Adobe's Window menu; each of the tab's other panes closed or shown back (panels.menu()); About's lines."""
        pane = os.environ.get("HERDR_PANE_ID")
        try:
            listed = self.herdr.call("pane", "list").get("panes") or []
        except RuntimeError:
            listed = []
        tab = next((p["tab_id"] for p in listed if p.get("pane_id") == pane), None)
        present = {p.get("label") for p in listed if p.get("tab_id") == tab} & set(panels.KINDS)
        shown = self.tabs()
        lines = [f"{'✓' if panel in shown else ' '} {PANELS[panel]['name']}" for panel in self.panels()]
        for part in (panels.menu(present) if tab else [], self.about()):
            lines += [None] + part if part else []
        menu = Menu(lines)
        self.menu = (menu, y, x if right is None else right - menu.width(), tab, present)

    def about(self):
        """The ⋯ menu's last lines: herdr-fold's version (a newer one's, once out), its releases opened in the browser,
        and the update check's switch."""
        found = self.update
        if not (found and found["version"]):
            return []                                     # not looked at yet, or never installed here (a remote one)
        named = f"herdr-fold {found['latest']} is out" if found["newer"] else f"herdr-fold {found['version']}"
        return [named, f"{'✓' if found['on'] else ' '} {CHECK}"]

    def got_update(self, found):
        """The update check's answer: a newer version said once, for every sidebar and the app (a herdr notification),
        and on the pane's last row while it is out."""
        self.update = found
        if found["newer"] and found["told"] != found["latest"]:
            latest = found["latest"]
            self.job("told", lambda: (update.told(latest), self.herdr.call(
                "notification", "show", f"herdr-fold {latest} is out", "--body", update.HOW)))

    def answer_menu(self, event):
        menu, y, x, tab, present = self.menu
        if isinstance(event, Key):
            choice = menu.handle(event)
            if choice is None:
                return None
        else:
            target = self.canvas.hit(event.x, event.y) if self.canvas else None
            choice = menu.choices[int(target[5:])] if str(target).startswith("menu:") else "cancel"
        self.menu = None
        panel = next((name for name in self.panels() if choice[2:] == PANELS[name]["name"]), None)
        if panel:                                       # a panel's ✓: hidden, or shown again
            self.hide(panel, choice.startswith("✓"))
            return None
        if choice.startswith("herdr-fold "):
            self.do_open_url(update.RELEASES)
            return None
        if choice.endswith(CHECK):
            on = not (self.update or {}).get("on", True)
            self.job("update", lambda: (update.switch(on), update.check())[1], self.got_update)
            return None
        what, kinds = panels.chosen(choice, present) or (None, None)
        if what == "close":
            self.job("panels", lambda: panels.close(self.herdr.call, tab, kinds))
        elif what == "show":
            self.job("panels", lambda: panes.bring(self.herdr.call, tab, kinds, self.state_dir))
        return None

    def show(self, panel):
        """PANEL shown (hidden in the ⋯'s Panels: shown again; on the rail, beside it), with the keys; what it needs as
        it comes (came()); one it cannot show here (Issues off GitHub) left as it is, in every tab."""
        if panel not in self.panels():
            return
        if panel in self.settings["hidden_panels"]:
            self.hide(panel, False)
        if panel not in self.tabs():
            return
        coming = not self.showing(panel)
        if self.dock["shown"] != panel:                 # kept for the folder, the dock folded or not
            self.keep_dock(panel)
        if self.railed and not self.beside:
            self.fly(True)
        if coming or panel == "issues":             # Issues shown already: asked again once their answer is old
            self.came(panel)

    def came(self, panel):
        """What PANEL needs once it comes on screen (its family's came()): Changes its Graph, Search the place chosen
        in Files, Issues their list."""
        self.work[panel].came(panel)

    # --- the dock folded to its rail: the same in every tab, as the column's width

    def fold_dock(self, rail):
        """The dock folded to its RAIL, or opened again, in every tab: kept in column.json first (another tab's sidebar
        takes it at its next look), then each tab's column and terminal set (shape())."""
        self.railed, self.beside = rail, False
        if not column.keep(self.state_dir, {"rail": rail}):
            self.error = "settings not saved"
        self.reshape(every=True)

    def press_icon(self, panel):
        """PANEL's icon on the rail pressed: PANEL opened beside the rail, the icon lit; the lit one again folds it
        back."""
        if self.showing(panel):
            self.fly(False)
        else:
            self.show(panel)

    def fly(self, beside):
        """On the rail, the panel shown opened BESIDE it, or folded back: this tab's column widened for it, or
        narrowed."""
        self.beside = beside
        self.reshape()

    def engaged(self, panel):
        """Whether PANEL has what Esc closes before the panel beside the rail: a menu, a name typed, a question."""
        return bool(panel) and bool(getattr(self.views[panel], "menu", None) or any(self.work[panel].holds()))

    def follow_dock(self):
        """The dock a rail, or open, as another tab's sidebar left it (column.json), and this tab set once shown when
        that left it as it was (its agent zoomed: "owed"); whether the dock changed."""
        kept = column.kept(self.state_dir)
        railed, changed = kept.get("rail") is True, (kept.get("rail") is True) != self.railed
        if changed:
            self.railed, self.beside = railed, False
        self.owed = os.environ.get("HERDR_PANE_ID") in (kept.get("owed") if isinstance(kept.get("owed"), list) else [])
        if self.owed:
            self.reshape()
        return changed

    def reshape(self, every=False):
        """This tab's column (EVERY: every tab's) as the dock is now (shape()); once more when asked while that runs,
        so the last change lands last."""
        if "dock" in self.running:
            self.again.add("dock-every" if every else "dock")
            return
        rail, beside = self.railed, self.beside
        self.job("dock", lambda: self.shape(rail, beside, every), self.reshaped)

    def reshaped(self, failed):
        if failed:
            self.error = failed
        every = "dock-every" in self.again
        if every or "dock" in self.again:
            self.again -= {"dock", "dock-every"}
            self.reshape(every)

    def shape(self, rail, beside, every):
        """On the job's thread: this tab's column (EVERY: every tab's, this one first) as wide as the dock takes, its
        terminal under the agent on the RAIL, else under the sidebar (moved before a column narrows, after it widens);
        a tab whose agent is zoomed left to its own sidebar (column.owe()). What failed, or None."""
        here = os.environ.get("HERDR_PANE_ID")
        if not here:
            return None
        failed, done, skipped = None, [], []
        sidebars = column.sidebars() if every else {}
        for pane in [here] + [other for other in sidebars.values() if other != here]:
            tab = column.read(pane)
            if not tab or not tab.cells:
                skipped += [pane] if column.hidden(pane) else []        # its own sidebar sets it once shown
                continue
            try:
                if rail and panes.place_terminal(self.herdr.call, pane, True):
                    tab = column.read(pane) or tab                      # the column's place in the tree may move
                column.arrange(tab, right=column.width(self.state_dir, tab, rail, beside and pane == here))
                if not rail:
                    panes.place_terminal(self.herdr.call, pane, False)
                done.append(pane)
            except RuntimeError as err:
                failed = f"terminal not moved: {err}"
        column.owe(self.state_dir, done, skipped, set(sidebars.values()) if every else None)
        return failed

    def count(self):
        """Changes' count: the changes staged and not, on its tab and on its rail icon."""
        return len(self.status.staged) + len(self.status.changes) if self.status else 0

    def marks(self):
        """Each panel's state after its tab's name and on its rail icon: Chats' dot while a conversation waits for an
        answer, Changes' count."""
        found = {"conversations": ("●", "modified")} if self.work["conversations"].waiting() else {}
        if self.count():
            found["changes"] = (str(min(self.count(), 10 ** stack.COUNT - 1)), "modified")
        return found

    # --- what every family asks for: the preview tab, a tab of its own, the browser, the icons

    def open_preview(self, spec, cwd):
        """SPEC in the workspace's preview tab; a new one gets this sidebar's tab's panes of the plugin's, and its
        sidebar this one's place (a message being written stays here)."""
        workspace = os.environ.get("HERDR_WORKSPACE_ID")
        if not workspace:
            self.error = "A preview opens in a herdr tab: run the sidebar in herdr"
            return
        seed = {key: value for key, value in self.left().items() if key != "message"}

        def work():
            here = preview.this_tab(self.herdr)

            def lay_out(tab):
                kinds = panels.present(self.herdr.call("pane", "list").get("panes") or []).get(here)
                statefile.write(preview.seed_file(self.state_dir, tab), seed)
                panes.bring(self.herdr.call, tab, kinds or set(panels.KINDS), self.state_dir)
                made = next((p.get("pane_id") for p in self.herdr.call("pane", "list").get("panes") or []
                             if p.get("tab_id") == tab and p.get("label") == column.SIDEBAR), None)
                if made:                                    # this tab's widths, before anything there draws
                    column.copy(os.environ.get("HERDR_PANE_ID"), made)

            preview.open_preview(self.herdr, workspace, cwd, spec, self.state_dir, lay_out, here)

        self.job("preview", work)

    def open_tab(self, label, argv):
        """ARGV with the keyboard in a tab of its own (gh's prompts for a new issue or a comment)."""
        workspace = os.environ.get("HERDR_WORKSPACE_ID")
        if not workspace:
            self.error = "It opens in a herdr tab: run the sidebar in herdr"
            return
        launch = preview.interactive(argv)
        self.job("tab", lambda: preview.open_tab(self.herdr, workspace, self.repo or self.root, label, launch))

    def do_open_url(self, url):
        self.note = "Opened in the browser" if media.open_in_browser(url) else "No browser to open it in"

    def do_icons(self, on):
        for view in self.views.values():
            view.icons = on
        self.save(icons=on)

    def chosen_folder(self):
        """The folder chosen in Files (its family's): in a folder that is no repository itself, Changes shows that
        one's."""
        return self.work["files"].chosen_folder()

    def reload(self, folders=None):
        """FOLDERS changed on disk (None: any of them): shown as they are now."""
        for family in self.families:
            family.reload(folders)

    # --- drawing

    def draw(self):
        cells, rows = self.term.size()
        canvas = Canvas(cells, rows)
        edge = max(0, cells - column.RAIL)              # the rail's edge, where » and « stand in every state
        # the panel beside the rail once the column is widened for it: as wide as the tab row it had, or FEWEST
        beside = self.railed and self.beside and edge >= min(column.FEWEST, narrowest(self.tabs()))
        self.reach, self.body = edge if beside else 0 if self.railed else cells, None
        if beside:                                      # no tab row: the lit icon names it
            area = Canvas(edge, rows)
            self.draw_panel(area, 1)
            canvas.paste(area)
            self.dock_head(canvas, 0, True)
        elif not self.railed:
            self.draw_panel(canvas, stack.TOP)
            self.draw_tabs(canvas)
        else:
            self.dock_head(canvas, 0, True, more=False)     # no room for the ⋯ on the rail alone
        if self.railed:
            lit = self.shown() if self.beside else None
            stack.rail(canvas, 1, rows - 1, lit, self.groups(), self.marks(), self.settings["icons"], edge,
                       self.pointed)
        if self.menu:
            menu, y, x = self.menu[:3]
            menu.draw(canvas, *menu.at(y, x, cells, 0, rows))
        elif self.tip:
            self.draw_tip(canvas)
        self.canvas = canvas
        self.term.write(self.renderer.frame(canvas))
        self.term.flush()

    def draw_panel(self, canvas, top):
        """The panel shown on CANVAS (the pane's, or its part left of the rail) from row TOP down, what went wrong
        under it, else a newer version."""
        cells, rows = canvas.width, canvas.height
        news = f"herdr-fold {self.update['latest']} is out: {update.HOW}" if (self.update or {}).get("newer") else None
        line = self.error or self.note or news
        self.body = (top, max(0, rows - top - bool(line)))
        for family in self.families:
            family.drawing()
        if self.body[1]:                                # its controls tall where it has the rows for them
            self.views[self.shown()].draw(canvas, top, self.body[1], self.body[1] >= ROOMY)
        if line:
            canvas.put(rows - 1, 0, " " * cells)
            canvas.put(rows - 1, 1, truncate(line, cells - 2),
                       Style(fg="deleted" if self.error else "muted" if self.note else "accent"))
            if line is news:
                canvas.region(rows - 1, 0, cells, "news")

    def draw_tabs(self, canvas):
        """The tab row (stack.tab_row()), a blank row above and below it; at its right end the dock's » and ⋯. A right
        click on it opens the ⋯'s menu there."""
        canvas.backdrop(stack.ROW, 0, canvas.width, "tabs")
        stack.tab_row(canvas, stack.ROW, self.groups(), self.shown(), self.marks(), self.pointed)
        self.dock_head(canvas, stack.ROW, False)

    def dock_head(self, canvas, y, rail, more=True):
        """The dock's own controls at row Y's right end, over the rail's edge: » that folds the dock to its rail (RAIL:
        « that opens it again), and, MORE, the ⋯ (the pane's own menu)."""
        dots, target = canvas.width - 1 - stack.MORE, "to_dock" if rail else "to_rail"
        x = max(1, dots - 2)
        canvas.put(y, x, OPEN_DOCK if rail else FOLD_DOCK, Style(fg="text" if self.pointed == target else "muted"))
        canvas.region(y, x - 1, x + 2, target)
        if more:
            canvas.control(y, dots, stack.MORE, 1, "badge", False)
            canvas.put(y, centered(dots, stack.MORE), "⋯", Style(fg="text" if self.pointed == "panels" else "muted",
                                                                  bg="badge"))
            canvas.region(y, dots, dots + stack.MORE, "panels")
            self.dots = (y + 1, None, dots + stack.MORE)    # its menu: right under it, its right edge with it


def main(argv):
    reap()
    home = os.path.expanduser("~")
    state = os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.join(home, ".local", "state", "herdr", "plugins",
                                                                     "herdr-fold.sidebar")
    if os.name == "nt":
        from keys_windows import WindowsTerminal as Terminal
    else:
        from keys_unix import UnixTerminal as Terminal
    folder = os.path.abspath(argv[1]) if len(argv) > 1 else os.getcwd()
    if folder == home and os.path.isdir(os.path.join(home, "Documents")):
        folder = os.path.join(home, "Documents")   # under home every repository would show at once
    app = App(folder, Terminal(), preview.Herdr(), state)
    if app.run():
        restart([argv[0], app.moved] if app.moved else argv)


def restart(argv, windows=os.name == "nt"):
    """Start the new version in this pane, on the same folder: in place of this process on macOS and Linux; on Windows,
    whose exec starts a new process and ends this one (the pane's shell would take the keys back meanwhile), as a
    child this one waits for."""
    args = [sys.executable, "-B", os.path.abspath(__file__), *argv[1:]]
    if windows:
        sys.exit(subprocess.call(args))
    os.execv(sys.executable, args)


def reap():
    """Wait for the programs an earlier version left in this process as it handed over (restart(): the same process
    on macOS and Linux), each a zombie until then: before this one runs any of its own. Windows keeps none."""
    if os.name == "nt":
        return
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:                   # none left
            return
        if not pid:                                 # the rest still running
            return


if __name__ == "__main__":
    main(sys.argv)
