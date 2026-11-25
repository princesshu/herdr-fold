"""The sidebar: Files, Search, Changes, on GitHub Issues, and Agent in one pane, one at a time under a row of buttons,
its ✦ opening the Chats list over them. One process: the screen and keys on the main thread, slow commands on threads
that wake the loop, so the view never waits. Usage: python3 sidebar.py [FOLDER] (in the home folder: ~/Documents)"""
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, replace

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
from agent_panel import Agent  # noqa: E402
from changes_panel import Changes  # noqa: E402
from chat_list import STATE_MARK, STATE_ROLE  # noqa: E402
from chats_panel import Chats                  # noqa: E402
from files_panel import Files  # noqa: E402
from loop import CODE, Loop  # noqa: E402
from dock import GROUPS, PANELS  # noqa: E402
from layers import FOLDED, STATE_ROLE as LAYER_ROLE  # noqa: E402
from screen import GIT_ROLE, INSET, MARGIN, ROOMY, Canvas, Style, short_count, truncate, width  # noqa: E402
from tree import git_marks  # noqa: E402
from vt import Focus, Key, Mouse, Resize  # noqa: E402
from widgets import Menu, wrap  # noqa: E402
import watch  # noqa: E402

# 1 to 5 in the row's order; F9 to F12 are what herdr's actions send (actions.py), as F7 to find a chat
VIEW_KEYS = {"1": "files", "2": "search", "3": "changes", "4": "issues", "5": "agent", "f9": "files", "f10": "search",
             "f11": "changes", "f12": "issues"}
TERMINAL_KEY = "6"            # on the rail, the tab's terminal raised or lowered: the digit after the views' keys
FIND = "f7"
DOCK_KEY = "f6"               # the dock folded or opened again, in every tab (herdr's action: Cmd + Option + B)
CHATS = "chats"       # the ✦'s: its list opens over the sidebar (on the rail, the dock opened), no view of the row
AGENT = "agent"       # the Agent view: a dot by its icon while its setup has a problem
DOT = STATE_MARK["blocked"]   # a count by an icon in the row and on the rail: there is something; its number in the tip
VIEWS = tuple(panel for panel in PANELS if panel != CHATS)
START = "files"               # the view a folder starts on
# linked: the issue each repository's next commit fixes, {repository: [number, title]}
# agent: the one herdr-fold started last (panes.py's last_agent); agent_folded: the Agent view's sections folded
DEFAULTS = {"hidden": True, "icons": True, "commit_mode": "commit", "linked": {}, "folded": [], "hidden_panels": [],
            "agent": "claude", "agent_folded": list(FOLDED), "agent_chosen": {}}
UPDATES = 3600.0              # seconds between two looks at update.json (GitHub itself is asked once a day at most)
SETTINGS = "Settings…"        # More's last line: herdr's popup (settings.py), at its About while a newer version is out
WHATS_NEW = "What's new: More › Settings › About"     # an update's notification says where its changes are
FAMILIES = (Chats, Files, Changes, Agent)         # the panel families the dock hosts
FOLD_DOCK, OPEN_DOCK = "»", "«"   # at the row's end: » folds the dock to its rail, « on the rail opens it again
LOOK = 1.0                    # seconds between two looks at FOLLOWED's stamps: an idle tab's too, whatever its poll
# the state folder's files another tab's sidebar, Settings or the theme setter writes, and what takes each here
FOLLOWED = (("settings.json", "follow_settings"), ("colors.json", "follow_theme"), (column.FILE, "follow_dock"))
                              # (the icons, the views) is here within it, at any pace of the poll; read once changed
NOTE = 4.0                    # seconds a note ("Archived", "Renamed") stays on the last row; an error stays till a key
UNFOLD = 3                    # the cells past the rail's width a drag widens it by to open the dock, more than a nudge
FOLD_REST = 0.8               # seconds the open column stays under its row's least before the dock folds: let go there
TIP_DELAY = 0.5               # seconds the mouse rests on a control shown by an icon before it says what it does
# what each such control does, by its target (a row's buttons by their kind)
TIPS = {"suggest": "Write message", "mode": "Commit mode", "sync": "Sync",
        "to_rail": "Collapse to icons", "to_dock": "Expand panels", "unlink": "Unlink issue",
        "new_file": "New file", "new_folder": "New folder", "refresh": "Refresh",
        "collapse": "Collapse all", "case": "Match case", "word": "Whole word", "regex": "Regular expression",
        "clear": "Clear", "stage": "Stage", "unstage": "Unstage", "discard": "Discard changes", "diff": "Show diff",
        "agent": "To agent", "web": "Open in browser", "remote": "More actions", "terminal": "Terminal"}


def grouped(panels):
    """GROUPS with the panels of PANELS there, a group without any left out."""
    return [(group, [panel for panel in members if panel in panels]) for group, members in GROUPS
            if any(panel in panels for panel in members)]


def narrowest(views):
    """The cells the row takes with the ✦ and the VIEWS shown, its icons alone: what the column keeps to at least
    (column.need())."""
    return stack.cells(grouped([CHATS, *views]), names=False)


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
        self.seen, self.next_look = {"colors.json": self.colors}, 0.0     # each of FOLLOWED's stamp when last read
        self.settings = load_settings(self.saw("settings.json"))
        self.repo = git.top(self.root)                  # None outside a repository; checked again by each status
        self.own = self.repo                            # the folder's own repository; without one, the chosen's
        self.looked = None                              # the folder chosen in Files the last status was asked for
        self.head = None                                # the latest commit seen: a newer one may close the linked issue
        self.github = git.github_name(self.repo) if self.repo else None     # OWNER/NAME on GitHub, or None
        self.status = None
        self.families = [family(self) for family in FAMILIES]
        self.work = {panel: family for family in self.families for panel in family.PANELS}    # each panel's family
        self.views = {panel: view for family in self.families for panel, view in family.views.items()}
        self.dock = stack.state(state_dir, self.root)    # the view shown in this folder
        self.saw(column.FILE)
        self.railed = column.railed(state_dir)            # the dock folded to its rail, in every tab (column.json)
        self.chats = False                                # the Chats list open, with the keys
        self.box = None                                   # the list's place, as last drawn: (top, left, bottom, right)
        self.named = True                                 # the row's names under its icons, as last drawn
        self.owed = False                                 # this tab left as it was by a fold (its agent zoomed)
        self.body = None                                  # the panel's rows, as last drawn: (top, rows)
        self.reach = 0                                    # the cells the panel takes, as last drawn: none on the rail
        self.watcher = watch.Watcher(self.work["files"].tree.expanded_dirs, git.git_dir(self.root), clock)
        self.pointed = None                               # under the mouse: a button, the ⋯, », a rail's icon
        self.terminal = None                              # on the rail, the tab's terminal: (share, under the agent)
        self.split = None                                 # the agent's share this sidebar last set or saw
        self.dots = (0, None, 0)                          # where the ⋯'s menu opens: open_menu()'s arguments
        self.needs = None                                 # the cells this tab's row was said to take
        self.menu = None                                  # the pane's own menu: (Menu, its row, its column, its tab)
        self.tip = None                         # the control under the mouse: (target, tip, x, y, when due, drawn)
        self.noted = (None, 0.0)                          # the note on the last row, and when it came
        self.update, self.next_update = None, 0.0         # update.check()'s answer, and when to look again

    def stop(self):
        for family in self.families:
            family.stop()

    def panels(self):
        """The views it can show here: its families', Issues only for a repository on GitHub."""
        return [panel for panel in VIEWS if panel in self.views and (panel != "issues" or self.github)]

    def row(self):
        """The views on the row: the ones not hidden in the ⋯'s Panels; the first, when another tab hid every one this
        one can show (all but Issues, on GitHub there, here not)."""
        hidden = self.settings["hidden_panels"]
        return [panel for panel in self.panels() if panel not in hidden] or self.panels()[:1]

    def hide(self, panel, hidden):
        """View PANEL hidden (HIDDEN) or shown again, in every tab, on what settings.json holds then (another tab's
        sidebar may hide one at the same moment); never the last one shown, nor a name no view has."""
        last = []

        def change(settings):
            others = [name for name in settings["hidden_panels"] if name != panel and name in VIEWS]
            if hidden and not [name for name in self.panels() if name not in others + [panel]]:
                last.append(panel)
                return settings
            return {**settings, "hidden_panels": others + [panel] if hidden else others}

        self.save(change)
        if last:
            self.note = "One panel stays shown"
        self.fit()

    def fit(self):
        """The cells the row takes now, said to the column when they changed (column.need()); once more when they
        change while that runs, so the last change lands last."""
        if narrowest(self.row()) != self.needs:
            self.needs = narrowest(self.row())
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
        """The row's groups (the rail's too): the ✦ and the views shown, a group without any left out."""
        return grouped([CHATS, *self.row()])

    def shown(self):
        """The view shown: the one kept for this folder while it is on the row here (hidden, or Issues off GitHub, it
        comes back with its button), else Files, else the row's first."""
        views, kept = self.row(), self.dock["shown"]
        return kept if kept in views else START if START in views else views[0]

    def showing(self, panel):
        """Whether PANEL is on screen: the Chats list while open; a view while it is the one shown and the dock
        open (under the list too, back as it was once that closes)."""
        if panel == CHATS:
            return self.chats
        return panel == self.shown() and not self.railed

    def keyed(self):
        """The panel with the keys: the Chats list while open, else the view shown while it is on screen; None
        on the rail."""
        shown = self.shown()
        return CHATS if self.chats else shown if self.showing(shown) else None

    def keep_dock(self, shown):
        """SHOWN the view this sidebar shows, and kept for its folder (dock.json: another sidebar on this folder, a
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
            # else that of the folder chosen in Files, else the one inside the folder, as the Spaces row names it
            repo = own or (git.top(place) if place != root else None) or git.repo_inside(root)
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
        if now >= self.next_look:
            self.next_look = now + LOOK
            shown = self.look() or shown
        if now >= self.next_poll:
            shown = self.follow(now) or shown             # a new version first, before this poll starts a job
            if self.quit:
                return shown
            self.moved = self.moved or moved_to(self.root, self.identity)
            if self.moved:                                # on again where the folder went, once nothing is cut short
                if not self.busy():
                    self.hand_over()
                return shown
            shown = self.follow_settings() or shown
            shown = self.follow_dock() or shown
            if self.railed:                               # its terminal closed, opened or dragged by hand meanwhile
                self.read_terminal()
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

    def saw(self, name):
        """The state folder's file NAME's path, its stamp kept as seen: the caller reads it next."""
        path = os.path.join(self.state_dir, name)
        self.seen[name] = watch.stamp(path)
        return path

    def look(self):
        """One stat of each of FOLLOWED: one whose stamp changed since it was read is taken here by its follower, which
        reads it. Whether anything shown changed; nothing is looked at once the folder moved."""
        if self.moved:
            return False
        changed = [follow for name, follow in FOLLOWED
                   if watch.stamp(os.path.join(self.state_dir, name)) != self.seen.get(name)]
        return any([getattr(self, follow)() for follow in changed])

    def follow_theme(self):
        self.saw("colors.json")
        return super().follow_theme()

    def follow_settings(self):
        """What another tab's sidebar or Settings chose (settings.json) taken here: the views hidden or shown again
        in a ⋯, the icons chosen in Settings or by an i in Files; whether anything shown changed."""
        shown = False
        kept = load_settings(self.saw("settings.json"))
        if kept["hidden_panels"] != self.settings["hidden_panels"]:
            self.settings["hidden_panels"], shown = kept["hidden_panels"], True
            self.fit()
        if kept["icons"] != self.settings["icons"]:
            self.settings["icons"], shown = kept["icons"], True
            self.wear_icons(kept["icons"])
        return shown

    def busy(self):
        """Whether a restart would cut something short: any job but the update check (no program of its own, asked
        again by the new version), or a name being typed or a question on screen. A menu does not hold it: the new
        version comes back without it, as a click elsewhere closes it."""
        held = [hold for family in self.families for hold in family.holds()]
        return bool(self.running - {"update"}) or any(held)

    def left(self):
        shown = self.shown()
        left = {"show": CHATS} if self.chats else {"show": shown} if self.showing(shown) else {}     # none: the rail
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
        self.reshape()                          # its tab's column as chosen (a restart, a new tab), or the rail

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
        show = left.get("show")
        if show == CHATS:                               # the list open, or actions.find's seed
            self.open_chats()
        elif show in self.panels():                     # hidden in the ⋯'s Panels: shown again
            self.show(show)
        for family in self.families:
            family.take(left)

    def deadlines(self):
        tip = self.tip[4] if self.tip and self.tip[4] > self.clock() else self.next_poll
        note = [self.noted[1] + NOTE] if self.note else []
        return [self.next_poll, self.next_look, tip] + note + [due for family in self.families
                                                               for due in family.deadlines()]

    def point(self, target, x, y):
        """The mouse on TARGET at X, Y: a control shown by an icon says what it does once the mouse rests on it, a
        changed file its path, a name Files cuts short its path whole."""
        tip = TIPS.get(target[0] if isinstance(target, tuple) else target)
        kind, _, panel = str(target).partition(":")
        if kind == "icon" or (kind == "button" or target == "panels") and not self.named:    # an icon alone: its name
            tip = stack.MORE if target == "panels" else PANELS[panel]["name"]
        count = self.counts().get(panel) if kind in ("button", "icon") else None
        if count:                                                     # a dot by its icon: how many
            tip = f"{PANELS[panel]['name']} · {short_count(count)}{' waiting' if panel == CHATS else ''}"
        problems = self.views[AGENT].problems() if kind in ("button", "icon") and panel == AGENT else []
        if problems:                                                  # the Agent view's dot: its problems
            tip = f"{PANELS[AGENT]['name']} · {', '.join(problems)}"
        if target == "panels" and (self.update or {}).get("newer"):      # More's: which version is out
            tip = f"{stack.MORE} · herdr-fold {self.update['latest']} is out"
        if target == "terminal" and not (self.terminal and self.terminal[1]):
            tip = "No terminal in this tab"
        if tip and (kind == "button" or target in ("to_rail", "panels")):                  # the row's
            y = (stack.NAMES if self.named else stack.ROW) + 1
        elif tip and self.on_rail(target):              # under its block's ▀ row, on its icon's column
            y = stack.ROW + 1 if target == "to_dock" else stack.floor(y, stack.ROW + 2)
            x = stack.rail_column(self.canvas.width if self.canvas else self.term.size()[0])
        view = self.views.get(self.panel_at(y, x))
        if hasattr(view, "tip"):                        # a view's own first: a path, a name cut short, what runs
            tip = view.tip(target) or tip
        if not tip:
            self.tip = None
        elif not self.tip or self.tip[0] != target:
            self.tip = (target, tip, x, y, self.clock() + TIP_DELAY, False)

    def on_rail(self, target):
        """Whether TARGET is the rail's: an icon, «, the terminal's."""
        return self.railed and (str(target).startswith("icon:") or target in ("to_dock", "terminal"))

    def draw_tip(self, canvas):
        """The tip under the mouse (above it where the rows below are too few), whole inside the content's inset (the
        rail: the pane, edge to edge), a cell of air round it where its words have room, once it is due; one too
        wide for a row goes on in the next (a path after a /, a count's dot with its count)."""
        target, tip, x, y, due, _ = self.tip
        if self.clock() < due:
            return
        self.tip = (target, tip, x, y, due, True)
        inset = 0 if self.railed else INSET
        room = max(1, canvas.width - 2 * inset)
        air = int(max(width(word) for word in re.split("[ /]", tip)) + 2 <= room)
        glued = tip.replace(" · ", " ·\u00a0")                              # "Changes · 2" breaks before its dot
        lines = [glued[start:end].rstrip().replace("\u00a0", " ")
                 for start, end in wrap(glued, max(1, room - 2 * air), breaks=" /")]
        cells = max(width(line) for line in lines) + 2 * air
        top = y + 1 if y + len(lines) < canvas.height else max(0, y - len(lines))
        start = x - (cells - 1) // 2 if self.on_rail(target) else x       # a rail's: its middle on the icon's column
        left = max(inset, min(start, canvas.width - inset - cells))
        for row, line in enumerate(lines):
            label = truncate(" " * air + line + " " * air, room)
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
            self.pointed = None                   # what was under the mouse moved with the pane: lit at its next move
            self.follow_dock()                    # folded or opened in another tab, which set this one's width
            self.resized()
            return
        if isinstance(event, Focus):
            if not event.gained:                  # a click in another pane: no menu, nor the list, stays open behind
                self.menu = None
                for view in self.views.values():
                    view.close_menu()
                self.close_chats()
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
                self.close_chats()
                self.show(VIEW_KEYS[name])
                return
            if name == FIND:
                self.open_chats(find=True)
                return
            if name == DOCK_KEY:                  # as » or «, the list closing on the way
                self.close_chats()
                self.fold_dock(not self.railed)
                return
            if name == TERMINAL_KEY and self.railed and not editing:   # the rail's terminal
                self.raise_terminal()
                return
            if name == "q" and not editing:
                self.quit = True
                return
            if name == "esc" and self.chats and not self.engaged(panel):
                self.close_chats()
                return
            if panel:
                self.act(self.views[panel].handle(event), panel)
            return
        target = self.canvas.hit(event.x, event.y) if self.canvas else None
        if event.kind == "move":                    # the row, the rail and More's menu light what is under it
            lit = target in ("panels", "to_rail", "to_dock", "terminal") or str(target).startswith(("icon:", "button:"))
            self.pointed = target if lit else None
            if self.menu:
                self.menu[0].point(target)
        if self.chats and not self.chats_mouse(event, target):     # else closed by one of the dock's own controls,
            return                                                  # which acts too
        if event.kind == "move":
            self.point(target, event.x, event.y)
            if self.menu and str(target).startswith("menu:"):       # over More's menu, not the view under it
                return
        elif event.kind == "press":
            self.error = self.note = None
            if self.railed and event.button == 2:
                return                                # the rail: no room for a menu
            own = target in ("row", "sync", "panels", "to_rail", "to_dock") or str(target).startswith("button:")
            if own:                                   # outside the views: their menus close, as a click in one does
                for view in self.views.values():
                    view.close_menu()
            if target == "panels" and event.button != 2:                  # the ⋯: its menu right under it
                self.open_menu(*self.dots)
                return
            if target in ("to_rail", "to_dock") and event.button != 2:
                self.fold_dock(target == "to_rail")
                return
            if target == "terminal":
                self.raise_terminal()
                return
            if own and event.button == 2:             # a right click on the row: there
                self.open_menu(event.y, event.x)
                return
            kind, _, name = str(target).partition(":")
            if kind in ("icon", "button"):           # a rail's icon as the row's button: on the rail, the dock opened
                self.open_chats() if name == CHATS else self.show(name)
                return
            if target == "sync":
                self.work["changes"].do_sync()
                return
        panel = self.panel_at(event.y, event.x)
        if panel:                                       # in the view's own cells, from its first
            self.act(self.views[panel].handle(replace(event, x=event.x - MARGIN)), panel)

    def chats_mouse(self, event, target):
        """The mouse while the Chats list is open: a press outside it closes it, on one of the dock's own controls
        (True) to do that one's too, as Adobe switches a flyout; the star's only closes it, More's opens its menu over
        it (the list's own lines first). Inside, the list has it."""
        top, left, bottom, right = self.box or (0, 0, -1, -1)       # not drawn yet: all of the pane outside it
        if event.kind == "press" and target == "panels":
            return True
        if event.kind == "press" and not (top <= event.y <= bottom and left <= event.x <= right):
            self.error = self.note = None
            own = event.button != 2 and target != "button:" + CHATS and (
                target == "to_rail" or str(target).startswith("button:"))
            self.close_chats()
            return own
        if top <= event.y <= bottom and left <= event.x <= right:
            inside = replace(event, x=event.x - left - MARGIN, y=event.y - top)
            self.act(self.views[CHATS].handle(inside), CHATS)
        return False

    def act(self, action, panel=None):
        """ACTION done by its PANEL's family where that has it, else by the dock (the icons, a URL opened)."""
        if action is not None:
            name = "do_" + action.name
            getattr(self.work[panel] if hasattr(self.work.get(panel), name) else self, name)(*action.args)

    def panel_at(self, y, x=0):
        """The view drawn at row Y and column X; None on the row, under the view or on the rail."""
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
        """On the job's thread: PANE resized. Dragged (a share not the one last seen): the open dock kept that wide,
        under its row's least "fold" once let go; the rail more than UNFOLD cells wider "open" (dragged()). Else
        (herdr's sidebar folded, a window resized) back to its cells at once."""
        tab = column.read(pane)
        if tab and (self.split is None or abs(tab.left - self.split) > column.TOLERANCE):
            tab = column.settled(pane)                   # dragged: where it was let go, not on the way
        if not tab or not tab.cells:
            return 0
        dragged = self.split is None or abs(tab.left - self.split) > column.TOLERANCE
        inside = self.term.size()[0]
        least = column.least(self.state_dir, tab.tab) + column.frame(tab, pane, inside)
        if dragged and not self.railed:
            if self.split is not None and tab.left > self.split and column.cells(tab)[1] < least:   # under its row
                return "fold" if column.rested(pane, tab, FOLD_REST) else 0
            moved = column.drag(self.state_dir, pane, inside, tab)
            self.split = (column.read(pane) or tab).left                    # as it stands now, set back or not
            return moved
        right = column.width(self.state_dir, tab, self.railed)
        if dragged and self.railed and column.cells(tab)[1] - round(right * tab.cells) > UNFOLD:
            return "open"
        column.arrange(tab, right=right)
        self.split = round(column.share(1 - right), 4)
        return 0

    def dragged(self, answer):
        """The rail dragged open or the open dock under its row's least (drag()): the dock opened or folded in every tab
        as « or » would, the open width kept; whether it was."""
        if answer in ("open", "fold") and self.railed == (answer == "open"):
            self.fold_dock(answer == "fold")
            return True
        return False

    # --- the pane's own menu: each of the tab's other panes closed or shown back

    def open_menu(self, y, x, right=None):
        """The ⋯ menu at Y, X (with RIGHT, its right edge there instead): the views, each with a ✓ while shown, as
        Adobe's Window menu; each of the tab's other panes closed or shown back (panels.menu()); Settings…."""
        pane = os.environ.get("HERDR_PANE_ID")
        try:
            listed = self.herdr.call("pane", "list").get("panes") or []
        except RuntimeError:
            listed = []
        tab = next((p["tab_id"] for p in listed if p.get("pane_id") == pane), None)
        present = {p.get("label") for p in listed if p.get("tab_id") == tab} & set(panels.KINDS)
        shown = self.row()
        lines = [f"{'✓' if panel in shown else ' '} {PANELS[panel]['name']}" for panel in self.panels()]
        own = self.own_lines()                          # the panel with the keys: its own lines first
        lines = own + [None] + lines if own else lines
        for part in (panels.menu(present) if tab else [], [SETTINGS] if os.name != "nt" else []):  # herdr's popup
            lines += [None] + part if part else []
        menu = Menu(lines)
        self.menu = (menu, y, x if right is None else right - menu.width(), tab, present)

    def own_lines(self):
        """What the panel with the keys lists in More before the views: the Agent view its Usage view, graph and ways
        to add a connector, the Chats list Show archived."""
        view = self.views.get(self.keyed())
        return view.menu_lines() if hasattr(view, "menu_lines") else []

    def got_update(self, found):
        """The update check's answer, for More's dot while a newer version is out; after an update, Updated to
        herdr-fold X said once, for every tab's sidebar and the app (a herdr notification)."""
        self.update = found
        version = found["updated"]
        if version:
            self.job("seen", lambda: update.seen(version) and self.herdr.call(
                "notification", "show", f"Updated to herdr-fold {version}", "--body", WHATS_NEW, "--sound", "none"))

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
        if choice in self.own_lines():
            self.act(self.views[self.keyed()].menu_pick(choice), self.keyed())
            return None
        panel = next((name for name in self.panels() if choice[2:] == PANELS[name]["name"]), None)
        if panel:                                       # a view's ✓: hidden, or shown again
            self.hide(panel, choice.startswith("✓"))
            return None
        if choice == SETTINGS:
            self.job("settings", lambda: self.herdr.call("plugin", "pane", "open", "--plugin", "herdr-fold.sidebar",
                                                         "--entrypoint", "settings", "--focus"))
            return None
        what, kinds = panels.chosen(choice, present) or (None, None)
        if what == "close":
            self.job("panels", lambda: panels.close(self.herdr.call, tab, kinds))
        elif what == "show":
            self.job("panels", lambda: panes.bring(self.herdr.call, tab, kinds, self.state_dir))
        return None

    def show(self, panel):
        """View PANEL shown (hidden in the ⋯'s Panels: shown again; on the rail, the dock opened as « does), with the
        keys; what it needs as it comes (came()); one it cannot show here (Issues off GitHub) left as it is."""
        if panel not in self.panels():
            return
        if panel in self.settings["hidden_panels"]:
            self.hide(panel, False)
        if panel not in self.row():
            return
        coming = not self.showing(panel)
        if self.dock["shown"] != panel:                 # kept for the folder, the dock folded or not
            self.keep_dock(panel)
        if self.railed:
            self.fold_dock(False)
        if coming or panel == "issues":             # Issues shown already: asked again once their answer is old
            self.came(panel)

    def came(self, panel):
        """What PANEL needs once it comes on screen (its family's came()): Changes its Graph, Search the place chosen
        in Files, Issues their list."""
        self.work[panel].came(panel)

    def open_chats(self, find=False):
        """The Chats list open over the sidebar, with the keys (on the rail, the dock opened as « does); FIND: its
        filter emptied (Cmd+Shift+R). Any other menu closes."""
        self.menu = None
        for view in self.views.values():
            view.close_menu()
        if find:
            self.work[CHATS].find()
        if self.railed:
            self.fold_dock(False)
        self.chats = True

    def close_chats(self):
        """The list closed (ChatList.shut()); the keys back with the view shown."""
        if not self.chats:
            return
        self.chats = False
        self.views[CHATS].shut()

    # --- the dock folded to its rail: the same in every tab, as the column's width

    def fold_dock(self, rail):
        """The dock folded to its RAIL, or opened again, in every tab: kept in column.json first (another tab's sidebar
        takes it at its next look), then each tab's column and terminal set (shape())."""
        self.railed = rail
        if not column.keep(self.state_dir, {"rail": rail}):
            self.error = "settings not saved"
        self.reshape(every=True)

    def engaged(self, panel):
        """Whether PANEL has what Esc closes before the list: a menu, a name typed, a question."""
        return bool(panel) and bool(getattr(self.views[panel], "menu", None) or any(self.work[panel].holds()))

    def follow_dock(self):
        """The dock a rail, or open, as another tab's sidebar left it (column.json), and this tab set once shown when
        that left it as it was (its agent zoomed: "owed"); whether the dock changed."""
        self.saw(column.FILE)
        kept = column.kept(self.state_dir)
        railed, changed = kept.get("rail") is True, (kept.get("rail") is True) != self.railed
        if changed:                             # the list too: the column is the other tab's now
            self.close_chats()
            self.railed = railed
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
        rail = self.railed
        self.job("dock", lambda: self.shape(rail, every), self.reshaped)

    def reshaped(self, failed):
        if failed:
            self.error = failed
        if self.railed:
            self.read_terminal()
        every = "dock-every" in self.again
        if every or "dock" in self.again:
            self.again -= {"dock", "dock-every"}
            self.reshape(every)

    def shape(self, rail, every):
        """On the job's thread: this tab's column (EVERY: every tab's, this one first) as wide as the dock takes, its
        terminal under the agent on the RAIL, else under the sidebar (moved before a column narrows, after it widens);
        a tab whose agent is zoomed left to its own sidebar (column.owe()). What failed, or None."""
        here = os.environ.get("HERDR_PANE_ID")
        if not here:
            return None
        failed, done, skipped = None, [], []
        sidebars, kept = column.sidebars() if every else {}, panes.kept_terminal(self.state_dir)
        for pane in [here] + [other for other in sidebars.values() if other != here]:
            tab = column.read(pane)
            if not tab or not tab.cells:
                skipped += [pane] if column.hidden(pane) else []        # its own sidebar sets it once shown
                continue
            try:
                found = panes.terminal(pane) if rail and pane == here else None
                if found and not found[1]:                              # its height in the right column: raised so
                    kept = panes.keep_terminal(self.state_dir, share=found[0])
                low = kept["share"] if kept["raised"] else panes.COLLAPSED     # under the agent: raised, or its least
                moved = rail and panes.place_terminal(self.herdr.call, pane, True, low)
                if moved:
                    tab = column.read(pane) or tab                      # the column's place in the tree may move
                right = column.width(self.state_dir, tab, rail)
                column.arrange(tab, right=right)
                self.split = round(column.share(1 - right), 4) if pane == here else self.split
                if not rail:
                    moved = panes.place_terminal(self.herdr.call, pane, False, kept["share"])
                if moved:                                               # a shell's prompt drawn again from the top
                    panes.clear_shell(self.herdr.call, pane)
                done.append(pane)
            except RuntimeError as err:
                failed = f"terminal not moved: {err}"
        column.owe(self.state_dir, done, skipped, set(sidebars.values()) if every else None)
        return failed

    # --- the tab's terminal under the agent, on the rail

    def terminal_up(self):
        """Whether this tab's terminal stands raised under the agent (the rail's icon lit): more than its least rows."""
        return bool(self.terminal and self.terminal[1] and self.terminal[0] > panes.COLLAPSED + 0.01)

    def read_terminal(self, share=None):
        """This tab's terminal set to SHARE of the rows under the agent (None: as it is), then read (self.terminal), on
        the job's thread."""
        pane = os.environ.get("HERDR_PANE_ID")
        if not pane or "terminal" in self.running:
            return

        def work():
            if share is not None and panes.size_terminal(pane, share):
                panes.clear_shell(self.herdr.call, pane)               # a shell's prompt drawn again from the top
            return panes.terminal(pane)

        self.job("terminal", work, self.got_terminal)

    def got_terminal(self, found):
        self.terminal = found

    def raise_terminal(self):
        """The rail's terminal icon pressed (or 5): this tab's terminal raised under the agent as tall as it was in the
        right column, or down to its least rows, the choice kept for the next fold; nothing without one."""
        if self.terminal and self.terminal[1]:
            kept = panes.keep_terminal(self.state_dir, raised=not self.terminal_up())
            self.read_terminal(kept["share"] if kept["raised"] else panes.COLLAPSED)

    def count(self):
        """Changes' count: the changes staged and not, beside its icon in the row and on the rail."""
        return len(self.status.staged) + len(self.status.changes) if self.status else 0

    def counts(self):
        """{panel: its count}: the ✦'s, the chats waiting for an answer; Changes', the changes."""
        return {CHATS: self.work[CHATS].waiting(), "changes": self.count()}

    def marks(self):
        """The dots by the icons, in the row and on the rail (the count or the words in the tip): the chats waiting and
        the changes in their colors; Agent's while its setup has a problem, the worst one's (red over yellow); More's,
        in the accent, while a newer herdr-fold is out (Settings' About says how to get it)."""
        roles = {CHATS: STATE_ROLE["blocked"], "changes": GIT_ROLE["M"]}
        marks = {panel: (DOT, roles[panel]) for panel, count in self.counts().items() if count}
        tone = self.work[AGENT].tone()
        marks.update({AGENT: (DOT, LAYER_ROLE[tone])} if tone else {})
        return {**marks, "panels": (DOT, "accent")} if (self.update or {}).get("newer") else marks

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

    def open_file(self, path, line=None, root=None, name=None):
        """PATH where it is worked on: text in the user's editor, in a tab of its own named NAME (else for its path,
        from ROOT) at LINE; a picture, a page, a binary file or one past the limit in the preview tab. Files and the
        preview see what it saved on disk."""
        root, workspace = root or self.root, os.environ.get("HERDR_WORKSPACE_ID")
        text = bool(workspace) and preview.editable(path)
        argv = text and preview.editor(line)
        if not argv:
            if text:
                self.note = "No editor found: set $EDITOR"
            return self.open_preview(preview.file_spec(root, path, line), root)

        def work():
            pane, _ = preview.open_editor(self.herdr, workspace, root, path, argv, name)
            return preview.gone_at_once(self.herdr, pane)

        def then(outside):
            if outside:
                self.note = f"Opened in {os.path.basename(argv[0])}, outside herdr"
        self.job("edit", work, then)

    def open_tab(self, label, argv, then=None):
        """ARGV with the keyboard in a tab of its own (gh's prompts for a new issue or a comment, an agent's own
        sign-in); THEN gets its (pane, tab), None where none could open."""
        workspace = os.environ.get("HERDR_WORKSPACE_ID")
        if not workspace:
            self.error = "It opens in a herdr tab: run the sidebar in herdr"
            if then:
                then(None)
            return
        launch = preview.interactive(argv)
        self.job("tab", lambda: preview.open_tab(self.herdr, workspace, self.repo or self.root, label, launch), then)

    def do_open_url(self, url):
        self.note = "Opened in the browser" if media.open_in_browser(url) else "No browser to open it in"

    def do_icons(self, on):
        self.wear_icons(on)
        self.save(icons=on)

    def wear_icons(self, on):
        """Every view with Nerd Font icons (ON) or plain marks; the row and the rail read the settings' own."""
        for view in self.views.values():
            view.icons = on

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
        self.reach, self.body, self.box = 0 if self.railed else cells, None, None
        if not self.railed:
            self.named = stack.named(self.groups(), cells)          # too narrow: the icons alone, a row less
            top = stack.TOP if self.named else stack.TOP - 1
            self.draw_panel(canvas, top)
            self.draw_row(canvas)
            if self.chats:                              # in the view's place, under the blank row
                self.draw_chats(canvas, top)
        else:                                           # « on the row's icons' line as », the icons under it
            self.dock_head(canvas, stack.ROW, True)
            # across the whole pane: herdr keeps a tenth of the tab at least
            stack.rail(canvas, stack.ROW + 2, rows - stack.ROW - 2, self.groups(), self.marks(), self.settings["icons"],
                       self.pointed, terminal=self.terminal_up())
        if self.menu:
            menu, y, x = self.menu[:3]
            menu.draw(canvas, *menu.at(y, x, cells, 0, rows, INSET))
        elif self.tip:
            self.draw_tip(canvas)
        self.canvas = canvas
        self.term.write(self.renderer.frame(canvas))
        self.term.flush()

    def draw_panel(self, canvas, top):
        """The view shown on CANVAS from row TOP down, what went wrong or a note over its last row."""
        cells, rows = canvas.width, canvas.height
        line = self.error or self.note
        self.body, full = (top, max(0, rows - top - bool(line))), max(0, rows - top)
        for family in self.families:
            family.drawing()
        if full:                                        # every row its own, the line over the last: nothing moves
            view = Canvas(max(1, cells - 2 * MARGIN), rows)          # its highlight edge to edge, its content a cell in
            self.views[self.shown()].draw(view, top, full, full >= ROOMY)          # tall where it has the rows
            canvas.paste(view, 0, MARGIN)
        if line:
            canvas.put(rows - 1, 0, " " * cells)
            canvas.put(rows - 1, INSET, truncate(line, cells - 2 * INSET),
                       Style(fg="deleted" if self.error else "muted"))

    def draw_row(self, canvas):
        """The row (stack.button_row()): the ✦, the views' buttons and More, each icon over its name, a blank row above
        and below; » at the right end of the icons' line. A right click on it opens More's menu there."""
        for y in (stack.ROW, stack.NAMES):
            canvas.backdrop(y, 0, canvas.width, "row")
        more = stack.button_row(canvas, stack.ROW, self.groups(), None if self.chats else self.shown(),
                                self.marks(), CHATS if self.chats else None, self.pointed, self.settings["icons"])
        self.dots = (stack.NAMES + 1 if self.named else stack.ROW + 1, more, None)      # its menu under More
        self.dock_head(canvas, stack.ROW, False)

    def dock_head(self, canvas, y, rail):
        """The dock's own button on row Y, a block of an icon alone as the row's: » that folds the dock to its rail at
        the row's right end, or (RAIL) « that opens it again over the rail's icons; lit under the mouse as they are,
        its half rows its own."""
        target, cells = "to_dock" if rail else "to_rail", canvas.width
        x = stack.rail_column(cells) if rail else stack.corner(cells) + stack.ICON_BUTTON // 2
        first, end = stack.block(x, cells)
        canvas.put(y, x, OPEN_DOCK if rail else FOLD_DOCK, Style(fg="text" if self.pointed == target else "subtext"))
        if self.pointed == target:
            stack.hover(canvas, (y,), first, end)
        for row in (y - 1, y + 1, y):
            canvas.region(row, 0 if rail else first, cells if rail else end, target)

    def draw_chats(self, canvas, top):
        """The Chats list in the view's place, from row TOP to the view's last, edge to edge on the views' own
        background (no frame, no second shade), in the views' margins: its filter, its rows, its menu."""
        first, rows = self.body
        bottom, cells = first + rows - 1, canvas.width
        if bottom - top < 1:                              # no room for it: the keys still go to it
            return
        inside = Canvas(max(1, cells - 2 * MARGIN), bottom - top + 1)
        for y in range(top, bottom + 1):
            canvas.put(y, 0, " " * cells)
        self.views[CHATS].draw(inside, 0, inside.height, rows >= ROOMY)
        canvas.paste(inside, top, MARGIN)
        self.box = (top, 0, bottom, cells - 1)


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
