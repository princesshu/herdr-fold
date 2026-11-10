"""The sidebar: Conversations, Files, Search, Changes and, for a repository on GitHub, Issues in one pane, as groups of
tabs. One process: the screen and keys on the main thread, slow commands on background threads that wake the loop, so
the view never waits. Usage: python3 sidebar.py [FOLDER] (in the home folder: ~/Documents)"""
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
import widgets  # noqa: E402
from widgets import Menu, wrap  # noqa: E402
import watch  # noqa: E402

VIEW_KEYS = {"1": "files", "2": "search", "3": "changes", "4": "issues", "f9": "files", "f10": "search",
             "f11": "changes", "f12": "issues"}
FIND, FOLD = "f7", "f6"       # the keys herdr's actions send (actions.py): find a conversation, fold its group
GROUP_OF = {panel: group for group, panels in GROUPS for panel in panels}
# linked: the issue each repository's next commit fixes, {repository: [number, title]}
DEFAULTS = {"hidden": False, "icons": True, "commit_mode": "commit", "linked": {}, "folded": []}
UPDATES = 3600.0              # seconds between two looks at update.json (GitHub itself is asked once a day at most)
CHECK = "Check for Updates"   # the ⋯ menu's switch, a ✓ while it is on
FAMILIES = (Conversations, Files, Changes)        # the panel families the dock hosts, in its groups' order
MORE = 5                      # the cells of the ⋯ (the pane's own menu) at the first group's head
COUNT = 3                     # the cells a count beside a tab's name takes at most (Changes: 999)
TIP_DELAY = 0.5               # seconds the mouse rests on a control shown by an icon before it says what it does
# what each such control does, by its target (a row's buttons by their kind)
TIPS = {"suggest": "Write message", "mode": "Commit mode", "sync": "Sync", "panels": "Panes",
        "unlink": "Unlink issue",
        "new_file": "New file", "new_folder": "New folder", "refresh": "Refresh",
        "collapse": "Collapse all", "case": "Match case", "word": "Whole word", "regex": "Regular expression",
        "clear": "Clear", "stage": "Stage", "unstage": "Unstage", "discard": "Discard changes", "diff": "Show diff",
        "agent": "To agent", "web": "Open in browser", "remote": "More actions"}


def head_width(panels):
    """The cells a group's head takes with PANELS as its tabs: a cell of edge, the fold and a cell, each tab's name (and
    Changes' count) two apart, a cell, the ⋯ and a cell of edge."""
    names = sum(width(PANELS[panel]["title"]) + (1 + COUNT if panel == "changes" else 0) for panel in panels)
    return 1 + 2 + names + 2 * (len(panels) - 1) + 1 + MORE + 1


def narrowest(panels):
    """The cells the widest group's head takes with PANELS shown: what the column keeps to at least (column.need())."""
    return max(head_width([panel for panel in shown if panel in panels]) for _group, shown in GROUPS)


def load_settings(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}
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
        self.dock = stack.state(state_dir, self.root)    # each group's panel shown, the folded ones, their shares
        self.focus = GROUP_OF["files"]                    # the group with the keys: Files' at first
        self.slices = {}                                  # each group's rows, as last drawn: {group: (top, rows)}
        self.dragging = None                              # a head held: (its group, the row it went down on, weights)
        files = self.work.get("files")
        self.watcher = watch.Watcher(files.tree.expanded_dirs if files else lambda: [self.root],
                                     git.git_dir(self.root), clock)
        self.pointed = None                               # the panel's tab (or the ⋯) under the mouse
        self.dots = (0, None, 0)                          # where the ⋯'s menu opens: open_menu()'s arguments
        self.needs = None                                 # the cells this tab's header was said to take
        self.menu = None                                  # the pane's own menu: (Menu, its row, its column, its tab)
        self.tip = None                         # the control under the mouse: (target, tip, x, y, when due, drawn)
        self.update, self.next_update = None, 0.0         # update.check()'s answer, and when to look again

    def stop(self):
        for family in self.families:
            family.stop()

    def tabs(self):
        """The panels there: its families', Issues only for a repository on GitHub."""
        return [panel for panel in PANELS if panel in self.views and (panel != "issues" or self.github)]

    def groups(self):
        """GROUPS with the panels there, a group without any left out."""
        tabs = self.tabs()
        return [(group, [panel for panel in panels if panel in tabs]) for group, panels in GROUPS
                if any(panel in tabs for panel in panels)]

    def shown(self, group):
        """The panel GROUP shows: the one kept for this folder while it is there, else its first."""
        panels = dict(self.groups()).get(group) or []
        kept = self.dock["shown"].get(group)
        return kept if kept in panels else (panels[0] if panels else None)

    def showing(self, panel):
        """Whether PANEL is on screen: shown in its group, the group open (as last drawn; before that, not folded)."""
        group = GROUP_OF[panel]
        rows = self.slices[group][1] if group in self.slices else None
        opened = rows > stack.HEAD if rows is not None else group not in self.dock["folded"]
        return opened and self.shown(group) == panel

    def keep_dock(self, **changes):
        self.dock.update(changes)
        try:
            stack.keep(self.state_dir, self.root, **self.dock)
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
        if narrowest(self.tabs()) != self.needs:                # Issues came or went: the header's width with it
            self.needs = narrowest(self.tabs())
            self.job("need", lambda cells=self.needs: self.need(cells))
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
            changed = self.watcher.poll()
            folders = [path for path in changed if path != "git"]
            if folders:
                self.reload(folders)
                shown = True
            if self.watcher.status_due(bool(changed), self.showing("changes")) or (
                    self.own is None and self.chosen_folder() != self.looked):    # another folder chosen in Files
                self.refresh()
            self.next_poll = now + self.watcher.interval()
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
        left = {"show": self.shown(self.focus)}
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
        if left.get("show") in self.tabs():
            self.show(left["show"])
        for family in self.families:
            family.take(left)

    def deadlines(self):
        tip = self.tip[4] if self.tip and self.tip[4] > self.clock() else self.next_poll
        return [self.next_poll, tip] + [due for family in self.families for due in family.deadlines()]

    def point(self, target, x, y):
        """The mouse on TARGET at X, Y: a control shown by an icon says what it does once the mouse rests on it, a
        changed file its path, a name Files cuts short its path whole."""
        tip = TIPS.get(target[0] if isinstance(target, tuple) else target)
        view = self.views.get(self.panel_at(y))
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

    def save(self, **changes):
        self.settings.update(changes)
        path = os.path.join(self.state_dir, "settings.json")
        self.settings["linked"] = load_settings(path)["linked"]      # commit_message.link() writes them, the app too
        try:
            statefile.write(path, self.settings, indent=2)
        except OSError as err:
            self.error = f"settings not saved: {err}"

    # --- events

    def handle(self, event):
        self.watcher.touch()
        if not (isinstance(event, Mouse) and event.kind == "move"):
            self.tip = None                               # a key, a click or the wheel: the tip goes
        if isinstance(event, Resize):
            self.renderer.reset()
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
        if isinstance(event, Mouse) and self.dragging and event.kind in ("move", "release"):
            self.drag_head(event)
            return
        if isinstance(event, Key):
            if event.name == "char" and event.ctrl and event.char == "c":
                self.quit = True
                return
            self.error = self.note = None
            view = self.views[self.shown(self.focus) or self.tabs()[0]]
            name = event.char if event.name == "char" and not (event.ctrl or event.alt) else event.name
            if name in VIEW_KEYS and (name.startswith("f") or not view.editing):
                self.show(VIEW_KEYS[name])
                return
            if name == FIND:
                self.show("conversations")
                self.work["conversations"].find()
                return
            if name == FOLD:
                self.fold("conversations")
                return
            if name == "q" and not view.editing:
                self.quit = True
                return
            self.act(view.handle(event), self.shown(self.focus))
            return
        target = self.canvas.hit(event.x, event.y) if self.canvas else None
        if event.kind == "move":
            self.pointed = target[4:] if str(target).startswith("tab:") else target if target == "panels" else None
            self.point(target, event.x, event.y)
        elif event.kind == "press":
            self.error = self.note = None
            head = target in ("pane", "sync", "panels") or str(target).startswith(("head:", "fold:", "tab:"))
            if head:                                  # outside the panels: their menus close, as a click in one does
                for view in self.views.values():
                    view.close_menu()
            if target == "news":                                             # a newer version: its release
                self.do_open_url(update.RELEASES)
                return
            if target == "panels" and event.button != 2:                  # the ⋯: its menu right under it
                self.open_menu(*self.dots)
                return
            if head and event.button == 2:            # a right click on a head or the status bar: there
                self.open_menu(event.y, event.x)
                return
            kind, _, name = str(target).partition(":")
            if kind == "fold":
                self.fold(name)
                return
            if kind == "tab":
                self.show(name)
                return
            if kind == "head":                        # held: the edge above it follows the mouse
                self.dragging = (name, event.y, dict(self.dock["weights"]))
                return
            if target == "sync" and "changes" in self.work:
                self.work["changes"].do_sync()
                return
        panel = self.panel_at(event.y)
        if panel:
            if event.kind == "press":
                self.focus = GROUP_OF[panel]
            self.act(self.views[panel].handle(event), panel)

    def act(self, action, panel=None):
        """ACTION done by its PANEL's own work where it has one (the Conversations list's), else by the sidebar."""
        if action is not None:
            getattr(self.work.get(panel, self), "do_" + action.name)(*action.args)

    def panel_at(self, y):
        """The panel drawn at row Y; None on a head or under the groups."""
        for group, (top, rows) in self.slices.items():
            if top + stack.HEAD <= y < top + rows:
                return self.shown(group)
        return None

    def drag_head(self, event):
        """A head held: the edge above it follows the mouse; kept once it is let go."""
        group, start, weights = self.dragging
        rows = sum(size for _top, size in self.slices.values())
        names = [name for name, _panels in self.groups()]
        self.dock["weights"] = stack.dragged(rows, names, set(self.dock["folded"]), weights, group, event.y - start)
        if event.kind == "release":
            self.dragging = None
            self.keep_dock()

    def need(self, cells):
        """On the job's thread: this tab's right column takes CELLS at least inside its frame (column.need(): the
        widths keep to it, this tab's own); widened at once if it is narrower."""
        pane = os.environ.get("HERDR_PANE_ID")
        if not pane:                                            # not in a herdr pane: no column to keep
            return
        try:
            panes = self.herdr.call("pane", "list").get("panes") or []
        except RuntimeError:
            return
        tab = next((p["tab_id"] for p in panes if p.get("pane_id") == pane), None)
        if not tab:
            return
        column.need(self.state_dir, tab, cells, {p["tab_id"] for p in panes})
        here = column.read(pane)
        if here and here.cells:
            least = cells + column.frame(here, pane, self.term.size()[0])
            if column.cells(here)[1] < least:
                column.arrange(here, right=least / here.cells)

    # --- the pane's own menu: each of the tab's other panes closed or shown back

    def open_menu(self, y, x, right=None):
        """The ⋯ menu at Y, X (with RIGHT, its right edge there instead): each of the tab's other panes closed or shown
        back, Restore panels while any is closed (panels.menu())."""
        pane = os.environ.get("HERDR_PANE_ID")
        try:
            panes = self.herdr.call("pane", "list").get("panes") or []
        except RuntimeError:
            return
        tab = next((p["tab_id"] for p in panes if p.get("pane_id") == pane), None)
        present = {p.get("label") for p in panes if p.get("tab_id") == tab} & set(panels.KINDS)
        if tab:
            menu = Menu(panels.menu(present) + self.about())
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
        """PANEL shown in its group, the group open, and given the keys; what it needs as it comes (came())."""
        if panel not in self.tabs():
            return
        group = GROUP_OF[panel]
        self.focus = group
        if self.shown(group) != panel or group in self.dock["folded"]:
            self.keep_dock(shown={**self.dock["shown"], group: panel},
                           folded=[name for name in self.dock["folded"] if name != group])
            self.came(panel)
        elif panel == "issues":                     # shown already: asked again once its answer is old
            self.came(panel)

    def came(self, panel):
        """What PANEL needs once it comes on screen (its family's came()): Changes its Graph, Search the place chosen
        in Files, Issues their list."""
        self.work[panel].came(panel)

    def fold(self, group):
        """GROUP folded to its head, or open again, its panel coming on screen."""
        opening = group in self.dock["folded"]
        self.keep_dock(folded=[name for name in self.dock["folded"] if name != group] + ([] if opening else [group]))
        widgets.TURNS.turn(("group", group))
        if opening:
            self.came(self.shown(group))

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
        """The folder chosen in Files (its family's), the root without Files: in a folder that is no repository itself,
        Changes shows that one's."""
        files = self.work.get("files")
        return files.chosen_folder() if files else self.root

    def reload(self, folders=None):
        """FOLDERS changed on disk (None: any of them): shown as they are now."""
        for family in self.families:
            family.reload(folders)

    # --- drawing

    def draw(self):
        cells, rows = self.term.size()
        canvas = Canvas(cells, rows)
        news = f"herdr-fold {self.update['latest']} is out: {update.HOW}" if (self.update or {}).get("newer") else None
        line = self.error or self.note or news
        height = max(1, rows - bool(line))              # the groups, what went wrong below them, else a newer version
        groups = self.groups()
        self.slices = stack.heights(height, [group for group, _panels in groups], set(self.dock["folded"]),
                                    self.dock["weights"])
        for family in self.families:
            family.drawing()
        for n, (group, panels) in enumerate(groups):
            top, size = self.slices[group]
            self.group_head(canvas, top, group, panels, size > stack.HEAD, first=n == 0)
            if size > stack.HEAD:                       # its controls tall where its panel has the rows for them
                body = size - stack.HEAD
                self.views[self.shown(group)].draw(canvas, top + stack.HEAD, body, body >= ROOMY)
        if line:
            canvas.put(rows - 1, 0, " " * cells)
            canvas.put(rows - 1, 1, truncate(line, cells - 2),
                       Style(fg="deleted" if self.error else "muted" if self.note else "accent"))
            if line is news:
                canvas.region(rows - 1, 0, cells, "news")
        if self.menu:
            menu, y, x = self.menu[:3]
            menu.draw(canvas, *menu.at(y, x, cells, 0, rows))
        elif self.tip:
            self.draw_tip(canvas)
        self.canvas = canvas
        self.term.write(self.renderer.frame(canvas))
        self.term.flush()

    def group_head(self, canvas, y, group, panels, opened, first):
        """GROUP's head on row Y: its fold, its PANELS as tabs (the shown one bold in the accent, Changes with its
        count), at the FIRST head's right end the ⋯ (the pane's own menu); the rest of it drags the edge above it."""
        canvas.backdrop(y, 0, canvas.width, f"head:{group}")
        canvas.put(y, 1, widgets.TURNS.mark(self.settings["icons"], ("group", group), opened), Style(fg="muted"))
        canvas.region(y, 0, 3, f"fold:{group}")
        right = canvas.width - 2 - MORE if first else canvas.width - 1
        x, shown = 3, self.shown(group)
        for panel in panels:
            lit = "accent" if panel == shown else "text" if panel == self.pointed else "muted"
            end = canvas.put(y, x, truncate(PANELS[panel]["title"], max(0, right - x)),
                             Style(fg=lit, bold=panel == shown))
            count = len(self.status.staged) + len(self.status.changes) if panel == "changes" and self.status else 0
            if count:
                end = canvas.put(y, end + 1, truncate(str(min(count, 10 ** COUNT - 1)), max(0, right - end - 1)),
                                 Style(fg="modified"))
            canvas.region(y, x, end, f"tab:{panel}")
            x = end + 2
        if first:
            more = canvas.width - 1 - MORE
            canvas.control(y, more, MORE, 1, "badge", False)
            canvas.put(y, centered(more, MORE), "⋯", Style(fg="text" if self.pointed == "panels" else "muted",
                                                            bg="badge"))
            canvas.region(y, more, more + MORE, "panels")
            self.dots = (y + 1, None, more + MORE)          # its menu: right under it, its right edge with it

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
        restart([argv[0], app.moved] if getattr(app, "moved", None) else argv)


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
