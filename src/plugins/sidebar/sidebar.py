"""The sidebar: Files, Search, Changes and, for a repository on GitHub, Issues in one pane. One process: the screen and
keys on the main thread, slow commands on background threads that wake the loop, so the view never waits.
Usage: python3 sidebar.py [FOLDER] (in the home folder: ~/Documents), or --conversations for the Conversations column"""
import base64
import json
import os
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import column  # noqa: E402
import commit_message  # noqa: E402
import conversations_pane  # noqa: E402
import git  # noqa: E402
import github  # noqa: E402
import panels  # noqa: E402
import preview  # noqa: E402
import search  # noqa: E402
import statefile  # noqa: E402
from explorer import Explorer, git_marks  # noqa: E402
from fileops import Ops  # noqa: E402
from find import Find  # noqa: E402
from issues import Issues  # noqa: E402
from loop import CODE, Loop  # noqa: E402
from scm import Scm  # noqa: E402
from screen import ROOMY, Canvas, Style, centered, glyphs, truncate, width  # noqa: E402
from tree import Tree  # noqa: E402
from vt import Focus, Key, Mouse, Resize  # noqa: E402
from widgets import Menu, wrap  # noqa: E402
import watch  # noqa: E402

VIEWS = {"files": "Files", "search": "Search", "git": "Changes", "issues": "Issues"}     # each with its title, a word
VIEW_KEYS = {"1": "files", "2": "search", "3": "git", "4": "issues", "f9": "files", "f10": "search", "f11": "git",
             "f12": "issues"}
# linked: the issue each repository's next commit fixes, {repository: [number, title]}
DEFAULTS = {"hidden": False, "icons": True, "commit_mode": "commit", "view": "files", "linked": {}, "folded": []}
STALE = 60.0                  # seconds: the issues shown or listed here asked for again (a new one shows up)
BUSY = {"commit": "Committing…", "sync": "Syncing…", "suggest": "Writing the message…"}   # the first running shows
EMPTY = git.Status()
TAB = 5                       # the cells of a view's tab: its icon in the middle one
TIP_DELAY = 0.5               # seconds the mouse rests on a control shown by an icon before it says what it does
# what each such control does, by its target (a row's buttons by their kind)
TIPS = {"suggest": "Write the message", "mode": "Commit mode", "sync": "Sync", "panels": "Panes",
        "unlink": "Unlink the issue", "view:files": "Files", "view:search": "Search", "view:git": "Changes",
        "view:issues": "Issues", "new_file": "New file", "new_folder": "New folder", "refresh": "Refresh",
        "collapse": "Collapse all", "case": "Match case", "word": "Whole word", "regex": "Regular expression",
        "clear": "Clear", "stage": "Stage", "unstage": "Unstage", "discard": "Discard changes", "diff": "Show diff",
        "agent": "To the agent", "web": "Open in the browser"}
# the cells between the last view's tab and the ⋯ at least: the shown view's title (a cell of air on each side), the ⋯ a
# group of its own
APART = 1 + max(width(title) for title in VIEWS.values()) + 1


def narrowest(views):
    """The cells the header takes with VIEWS shown: a cell of edge, their tabs, APART, the ⋯ and a cell of edge."""
    return len(views) * (TAB + 1) + APART + TAB + 1


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


def picker_there(herdr):
    """Whether herdr-fold's tab layout is there, with the folder picker of herdr's new button: herdr's plugin list."""
    try:
        plugins = herdr.call("plugin", "list", "--json").get("plugins") or []
    except RuntimeError:
        return False
    return any(plugin.get("plugin_id") == "herdr-fold.tab-layout" for plugin in plugins)


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
        self.tree = Tree(self.root, show_hidden=self.settings["hidden"])
        icons = self.settings["icons"]
        self.views = {"files": Explorer(self.tree, icons, self.repo), "search": Find(self.root, icons, clock),
                      "git": Scm(self.settings["commit_mode"], icons, self.settings["folded"]), "issues": Issues(icons)}
        self.github = github.repo_name(self.repo) if self.repo else None     # OWNER/NAME on GitHub, or None
        self.issues_asked = {}                            # when each query's issues were last asked for
        self.views["git"].linked = self.linked()
        self.view = self.settings["view"] if self.settings["view"] in self.tabs() else "files"
        self.ops = Ops(self.root)
        self.repo_ops = Ops(self.repo) if self.repo else None
        self.watcher = watch.Watcher(self.tree.expanded_dirs, git.git_dir(self.root), clock)
        self.status, self.graph, self.searching = None, [], None
        self.suggesting = None                            # the message as it was when ✦ asked; None: no answer wanted
        self.pointed = None                               # the view tab (or the ⋯) under the mouse
        self.dots = (0, None, 0)                          # where the ⋯'s menu opens: open_menu()'s arguments
        self.needs = None                                 # the cells this tab's header was said to take
        self.menu = None                                  # the pane's own menu: (Menu, its row, its column, its tab)
        self.tip = None                         # the control under the mouse: (target, tip, x, y, when due, drawn)

    def stop(self):
        if self.searching:
            self.searching.set()

    def tabs(self):
        """The views shown: Issues only for a repository on GitHub."""
        return [view for view in VIEWS if view != "issues" or self.github]

    def refresh(self):
        """Ask git for the status (and the graph while Changes shows); once more when asked while running.
        The repository is looked up again each time (git init, or a .git taken away), its name on GitHub with it, and
        the file view's marks are worked out on the job's thread too."""
        if "status" in self.running:
            self.again.add("status")
            return
        root, with_graph, started = self.root, self.view == "git", self.clock()
        settings = os.path.join(self.state_dir, "settings.json")
        place = self.looked = self.chosen_folder()

        def work():
            own = git.top(root)
            repo = own or (git.top(place) if place != root else None)      # else that of the folder chosen in Files
            # not a repository when looked up: so it is shown, even if git init ran meanwhile (the next status has it)
            status = git.status(repo) if repo else git.Status(error=git.status(root).error or "not a git repository")
            graph = git.graph(repo) if repo and with_graph and not status.error else None
            name = github.repo_name(repo) if repo else None
            linked = load_settings(settings)["linked"]           # every tab's sidebar links: another one's may be new
            latest = git.head(repo) if repo and linked.get(repo) else (None, "")
            return (repo, name, status, git_marks(status, repo or root, root), graph, started, self.clock(), linked,
                    latest, own)

        self.job("status", work, self.got_status)

    def got_status(self, answer):
        repo, self.github, self.status, marks, graph, started, finished, linked, (head, message), self.own = answer
        if narrowest(self.tabs()) != self.needs:                # Issues came or went: the header's width with it
            self.needs = narrowest(self.tabs())
            self.job("need", lambda cells=self.needs: self.need(cells))
        if repo != self.repo:
            self.repo, self.repo_ops = repo, Ops(repo) if repo else None
            self.views["files"].repo = repo or self.root
            self.watcher.git_dir = git.git_dir(repo) if repo else None
            self.head = None
        self.settings["linked"] = linked
        issue = self.linked()
        if issue and head and self.head not in (None, head) and commit_message.fixes(message, issue[0]):
            self.do_unlink()  # a commit made anywhere (the commit window, a terminal, the agent) closed it
        else:
            self.views["git"].linked = issue
        self.head = head or self.head
        if self.view not in self.tabs():                # the repository left GitHub (or git)
            self.view = "files"
        self.views["files"].take(self.status, marks)
        if graph is not None:
            self.graph = graph
        self.watcher.status_done(started, finished)
        if "status" in self.again:
            self.again.discard("status")
            self.refresh()

    def tick(self):
        """The poll when due, the paused search and a tip come due; whether anything shown changed."""
        now = self.clock()
        shown = bool(self.tip) and not self.tip[5] and now >= self.tip[4]
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
                self.tree.reload(folders)
                shown = True
            if self.watcher.status_due(bool(changed), self.view == "git") or (
                    self.own is None and self.chosen_folder() != self.looked):    # another folder chosen in Files
                self.refresh()
            listing = self.views["issues"].listing        # asked on screen; behind it only while it lists any
            if self.github and (self.view == "issues" or listing and listing.issues):
                self.fresh_issues(STALE)
            self.next_poll = now + self.watcher.interval()
        search = self.views["search"].tick(now)
        self.act(search)
        return shown or search is not None

    def busy(self):
        """Whether a restart would cut something short: any job (loop.py's busy()), or a name being typed or a
        question on screen. A menu does not hold it: the new version comes back without it, as a click elsewhere
        closes it."""
        files, scm, issues = self.views["files"], self.views["git"], self.views["issues"]
        return super().busy() or any((files.naming, files.confirm, scm.confirm, issues.confirm))

    def left(self):
        find, files = self.views["search"], self.views["files"]
        return {"view": self.view, "expanded": sorted(map(self.moved_path, self.tree.expanded)),
                "selected": self.moved_path(getattr(files.list.selected(), "path", None)), "top": files.list.top,
                "chosen": files.moved,
                "message": self.views["git"].field.text, "changes": self.views["git"].kept(), "query": find.field.text,
                "switches": find.switches,
                "issues": self.views["issues"].kept()}

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
        self.show(self.view)
        if os.name != "nt":                     # the folder picker is not on Windows; a job only once the terminal is
            self.job("picker", lambda: picker_there(self.herdr), self.got_picker)    # taken (its wake needs that)

    def seeded(self):
        """A new preview tab's sidebar: where the sidebar that opened it was, left for its tab (open_preview())."""
        try:
            if not any(name.startswith("seed-") for name in os.listdir(self.state_dir)):
                return
        except OSError:
            return
        tab = self.own_tab()
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
        self.view = left.get("view") if left.get("view") in self.tabs() else self.view
        self.views["issues"].take(left.get("issues"))
        self.tree.expanded.update(p for p in left.get("expanded") or () if isinstance(p, str) and os.path.isdir(p))
        if isinstance(left.get("selected"), str):
            files = self.views["files"]
            files.select(left["selected"])
            files.moved = left.get("chosen") is True
            if isinstance(left.get("top"), int) and left["top"] >= 0:
                files.list.top = left["top"]      # as it was scrolled, not as a list not yet drawn (one row) puts it
        if isinstance(left.get("message"), str) and left["message"]:
            self.views["git"].set_message(left["message"])
        self.views["git"].take(left.get("changes"))
        find = self.views["search"]
        for name, on in (left.get("switches") or {}).items():
            if name in find.switches:
                find.switches[name] = bool(on)
        find.place = self.chosen_place()
        if isinstance(left.get("query"), str) and left["query"]:
            find.field.insert(left["query"])
            self.act(find.ask())

    def deadlines(self):
        tip = self.tip[4] if self.tip and self.tip[4] > self.clock() else self.next_poll
        return [self.next_poll, self.views["search"].deadline() or self.next_poll, tip]

    def point(self, target, x, y):
        """The mouse on TARGET at X, Y: a control shown by an icon says what it does once the mouse rests on it, a
        changed file its path."""
        tip = TIPS.get(target[0] if isinstance(target, tuple) else target)
        if not tip and self.view == "git":
            tip = self.views["git"].tip(target)
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
        try:
            statefile.write(os.path.join(self.state_dir, "settings.json"), self.settings, indent=2)
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
        view = self.views[self.view]
        if self.menu and isinstance(event, (Key, Mouse)) and (isinstance(event, Key) or event.kind == "press"):
            self.act(self.answer_menu(event))
            return
        if isinstance(event, Key):
            if event.name == "char" and event.ctrl and event.char == "c":
                self.quit = True
                return
            self.error = self.note = None
            name = event.char if event.name == "char" and not (event.ctrl or event.alt) else event.name
            if name in VIEW_KEYS and (name.startswith("f") or not view.editing):
                self.show(VIEW_KEYS[name])
                return
            if name == "q" and not view.editing:
                self.quit = True
                return
        elif isinstance(event, Mouse) and event.kind == "move":
            target = self.canvas.hit(event.x, event.y) if self.canvas else None
            self.pointed = target[5:] if str(target).startswith("view:") else target if target == "panels" else None
            self.point(target, event.x, event.y)
        elif isinstance(event, Mouse) and event.kind == "press":
            self.error = self.note = None
            target = self.canvas.hit(event.x, event.y) if self.canvas else None
            header = target in ("pane", "sync", "panels") or str(target).startswith("view:")
            if header:                                # outside the view: its menu closes, as a click in it does
                view.close_menu()
            if target == "panels" and event.button != 2:                  # the ⋯: its menu right under it
                self.open_menu(*self.dots)
                return
            if header and event.button == 2:          # a right click on the header or the status bar: there
                self.open_menu(event.y, event.x)
                return
            if str(target).startswith("view:"):
                self.show(target[5:])
                return
            if target == "sync":
                self.do_sync()
                return
        self.act(view.handle(event))

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
            if column.cells(here)[2] < least:
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
            menu = Menu(panels.menu(present, "sidebar"))
            self.menu = (menu, y, x if right is None else right - menu.width(), tab, present)

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
        what, kinds = panels.chosen(choice, present) or (None, None)
        if what == "close":
            self.job("panels", lambda: panels.close(self.herdr.call, tab, kinds))
        elif what == "show":
            conversations_pane.bring_apart(tab, kinds)              # it may close this pane on the way
        return None

    def show(self, view):
        if view != self.view and view in self.tabs():
            self.view = view
            self.save(view=view)
            if view == "git":
                self.refresh()
            if view == "search":
                self.act(self.views["search"].within(self.chosen_place()))
        if self.view == "issues":
            self.fresh_issues(STALE)

    def fresh_issues(self, after):
        """The issues asked for again when their last answer is older than AFTER seconds and none is on its way: an
        answer another sidebar of the repository got less than STALE seconds ago is taken (one question a minute)."""
        issues = self.views["issues"]
        if self.clock() - self.issues_asked.get(issues.query, float("-inf")) > after and not issues.asked:
            issues.ask()
            self.do_load_issues(issues.query, shared=True)

    # --- what the views ask for

    def do_preview_file(self, path, line=None):
        self.open_preview(preview.file_spec(self.root, path, line), self.root)

    def do_preview_diff(self, path, staged):
        untracked = not staged and any(c.path == path and c.code == "?" for c in (self.status or EMPTY).changes)
        if untracked:                                   # no diff to show: the file itself
            self.open_preview(preview.file_spec(self.repo, os.path.join(self.repo, path), None), self.repo)
        else:
            self.open_preview(preview.diff_spec(self.repo, path, staged), self.repo)

    def do_preview_commit(self, commit):
        self.open_preview(preview.commit_spec(self.repo, commit), self.repo)

    def open_preview(self, spec, cwd):
        """SPEC in the workspace's preview tab; a new one gets this sidebar's tab's panes of the plugin's, and its
        sidebar this one's place (a message being written stays here)."""
        workspace = os.environ.get("HERDR_WORKSPACE_ID")
        if not workspace:
            self.error = "A preview opens in a herdr tab: run the sidebar in herdr"
            return
        seed = {key: value for key, value in self.left().items() if key != "message"}

        def work():
            here = self.own_tab()

            def lay_out(tab):
                kinds = panels.present(self.herdr.call("pane", "list").get("panes") or []).get(here)
                statefile.write(preview.seed_file(self.state_dir, tab), seed)
                conversations_pane.bring(self.herdr.call, tab, kinds or set(panels.KINDS), self.state_dir)

            preview.open_preview(self.herdr, workspace, cwd, spec, self.state_dir, lay_out, here)

        self.job("preview", work)

    def own_tab(self):
        """The tab this sidebar is in (None outside herdr): a call to herdr, for a job's thread."""
        pane = os.environ.get("HERDR_PANE_ID")
        try:
            return self.herdr.call("pane", "get", pane)["pane"]["tab_id"] if pane else None
        except (RuntimeError, KeyError, TypeError):
            return None

    def open_tab(self, label, argv):
        """ARGV with the keyboard in a tab of its own (gh's prompts for a new issue or a comment)."""
        workspace = os.environ.get("HERDR_WORKSPACE_ID")
        if not workspace:
            self.error = "It opens in a herdr tab: run the sidebar in herdr"
            return
        launch = preview.interactive(argv)
        self.job("tab", lambda: preview.open_tab(self.herdr, workspace, self.repo or self.root, label, launch))

    # --- the issues

    def do_load_issues(self, query, shared=False):
        """The issues of QUERY from GitHub, kept for the repository's other sidebars; SHARED: one of them got less
        than STALE seconds ago taken instead (R and a change made here always ask GitHub)."""
        name, state_dir = self.github, self.state_dir
        if not name:
            return

        def work():
            listing = github.kept(state_dir, name, query, STALE) if shared else None
            if listing is None:
                listing = github.issues(name, query)
                github.keep(state_dir, name, query, listing)
            return listing

        def then(listing):
            self.issues_asked[query] = self.clock()
            self.views["issues"].show(listing, query)

        self.job("issues", work, then)

    def do_preview_issue(self, issue):
        self.open_preview(github.view_spec(self.github, issue), self.repo or self.root)

    def do_issue_web(self, issue):
        name = self.github

        def then(error):
            if error:
                self.error = f"{error}: {issue.url}"
        self.job("issue", lambda: github.open_in_browser(name, issue.number), then)

    def do_issue_comment(self, issue):
        self.open_tab(f"issue: #{issue.number}", github.comment_argv(self.github, issue.number))

    def do_new_issue(self):
        self.open_tab("issue: new", github.create_argv(self.github))

    def do_issue_change(self, issue, what):
        name, done = self.github, {"close": "Closed", "reopen": "Reopened", "assign": "Assigned to you:"}[what]

        def then(error):
            self.error = error
            if not error:
                self.note = f"{done} #{issue.number}"
            self.act(self.views["issues"].ask())

        self.job("issue", lambda: github.change(name, issue.number, what), then)

    def do_issue_to_agent(self, issue):
        """The tab's Claude or Codex gets the issue as a prompt, not sent yet, and the focus; the next commit fixes
        it."""
        me = os.environ.get("HERDR_PANE_ID")

        def work():
            tab = self.herdr.call("pane", "get", me).get("pane", {}).get("tab_id") if me else None
            agents = self.herdr.call("agent", "list").get("agents", [])
            target = next((a["pane_id"] for a in agents if a.get("tab_id") == tab and a.get("agent") in
                           ("claude", "codex")), None)
            if target is None:
                return "No Claude or Codex in this tab to hand the issue to"
            self.herdr.call("pane", "send-text", target, github.prompt(self.github, issue))
            self.herdr.call("agent", "focus", target)
            return None

        def then(error):
            self.error = error
            if not error:
                self.link(issue.number, issue.title)

        self.job("agent", work, then)

    def linked(self):
        """The issue this repository's next commit fixes: (number, title), or None."""
        found = self.settings["linked"].get(self.repo) if self.repo else None
        return (int(found[0]), str(found[1])) if isinstance(found, list) and len(found) == 2 else None

    def link(self, number, title):
        linked = {**self.settings["linked"], self.repo: [number, title]}
        self.views["git"].linked = (number, title)
        self.save(linked=linked)

    def do_unlink(self):
        linked = {repo: issue for repo, issue in self.settings["linked"].items() if repo != self.repo}
        self.views["git"].linked = None
        self.save(linked=linked)

    def do_new_file(self, folder, name):
        self.file_op(lambda: self.ops.new_file(folder, name), folder)

    def do_new_folder(self, folder, name):
        self.file_op(lambda: self.ops.new_folder(folder, name), folder)

    def do_rename(self, path, name):
        self.file_op(lambda: self.ops.rename(path, name), os.path.dirname(path))

    def file_op(self, work, folder):
        try:
            path = work()
        except OSError as err:                  # Refused, a name in use, no permission
            self.error = str(err)
            return
        self.tree.reload([folder])
        self.views["files"].select(path)
        self.refresh()

    def do_trash(self, path):
        def then(_):
            self.tree.reload([os.path.dirname(path)])
            self.refresh()
        self.job("trash", lambda: self.ops.trash(path), then)

    def got_picker(self, there):
        self.views["files"].opens_workspace = there

    def do_new_workspace(self, folder):
        self.job("workspace", lambda: self.herdr.call(
            "plugin", "pane", "open", "--plugin", "herdr-fold.tab-layout", "--entrypoint", "new-workspace", "--focus",
            "--env", f"HERDR_NEW_WORKSPACE_FOLDER={folder}"))

    def do_copy_path(self, path):
        if not self.ops.copy_path(path):        # no clipboard program: the terminal's own (OSC 52)
            self.term.write("\x1b]52;c;" + base64.b64encode(path.encode("utf-8")).decode("ascii") + "\x07")
            self.term.flush()
        self.note = "Path copied"

    def do_refresh(self):
        self.tree.reload()
        self.refresh()

    def do_show_hidden(self, show):
        self.save(hidden=show)

    def do_icons(self, on):
        self.views["search"].icons = self.views["git"].icons = self.views["issues"].icons = on
        self.save(icons=on)

    def do_search(self, query, place):
        if self.searching:
            self.searching.set()                # the older search stops; its answer would be dropped anyway
        self.searching = stop = threading.Event()
        self.job("search", lambda: search.search(self.root, query, cancel=stop, place=place),
                 lambda result: self.views["search"].show(result, query, place))

    def chosen_place(self):
        """The folder or file you chose in Files, for the search (from the root, with "/"), or "" for all of it: only
        the first row, chosen by itself (a row away from it is always yours, before an update too), or a link (it may
        lead out of the folder)."""
        files = self.views["files"]
        node = files.list.selected()
        if not ((files.moved or files.list.index > 0) and node is not None and node.path) or node.path == self.root \
                or os.path.islink(node.path):
            return ""
        return os.path.relpath(node.path, self.root).replace(os.sep, "/")

    def chosen_folder(self):
        """The folder you chose in Files (a file's own folder), the root without a choice: in a folder that is no
        repository itself, Changes shows that one's."""
        path = os.path.normpath(os.path.join(self.root, self.chosen_place()))
        return path if os.path.isdir(path) else os.path.dirname(path)

    def git_job(self, kind, work, reload=False):
        def then(error):
            if error:
                self.error = error
            if reload:
                self.tree.reload()
            self.refresh()
        self.job(kind, work, then)

    def do_stage(self, paths):
        self.git_job("git", lambda: git.stage(self.repo, list(paths)))

    def do_unstage(self, paths):
        self.git_job("git", lambda: git.unstage(self.repo, list(paths)))

    def do_discard(self, paths):
        untracked = {change.path for change in (self.status or EMPTY).changes if change.code == "?"}

        def work():
            for path in paths:
                if path in untracked:           # never deleted: an untracked file goes to the Trash
                    self.repo_ops.trash(os.path.join(self.repo, path))
                else:
                    error = git.discard(self.repo, path)
                    if error:
                        return error
            return None

        self.git_job("git", work, reload=True)

    def do_suggest(self):
        """The message written for what a commit takes: the staged changes, or every change, staged first."""
        if "suggest" in self.running:
            return
        status = self.status or EMPTY
        if not (status.staged or status.changes):
            self.error = "Nothing to commit"
            return
        self.suggesting, repo = self.views["git"].field.text, self.repo

        def work():
            git.stage_all(repo)
            return commit_message.write(commit_message.request(repo))

        self.job("suggest", work, self.got_suggestion)

    def got_suggestion(self, suggestion):
        """The written message goes into the field only if nothing happened meanwhile: no commit, no typing."""
        wanted, self.suggesting = self.suggesting, None
        if suggestion.message:
            if wanted is not None and self.views["git"].field.text == wanted:
                linked = self.views["git"].linked
                self.views["git"].set_message(commit_message.with_fixes(suggestion.message, linked and linked[0]))
        else:
            self.error = "No message: " + commit_message.explain(suggestion.problems)
        self.refresh()                                  # what was staged for it

    def do_commit(self, message, mode, paths):
        if "commit" in self.running or "sync" in self.running:
            self.note = "A commit or sync is still running"
            return
        self.suggesting = None                          # a message still being written is for changes now committed

        def work():
            ok, line = git.commit(self.repo, message, paths)
            if not ok:
                return False, line
            if mode in ("push", "sync"):
                ok, line = (git.push if mode == "push" else git.sync)(self.repo)
            return True, None if ok else git.advice(line)

        def then(answer):
            committed, error = answer
            if committed:
                self.views["git"].set_message("")
                linked = self.views["git"].linked
                if linked and commit_message.fixes(message, linked[0]):
                    self.do_unlink()                    # GitHub closes it with the push
            self.error = error
            self.refresh()

        self.job("commit", work, then)

    def do_remember_mode(self, mode):
        self.save(commit_mode=mode)

    def do_remember_folded(self, folded):
        self.save(folded=folded)

    def do_sync(self):
        if not self.repo or "sync" in self.running:
            return

        def work():
            ok, line = git.sync(self.repo)
            return None if ok else git.advice(line)

        self.git_job("sync", work)

    # --- drawing

    def draw(self):
        cells, rows = self.term.size()
        canvas = Canvas(cells, rows)
        roomy = rows >= ROOMY                            # the tabs and the view's controls alike
        top = self.switcher(canvas, roomy)
        line = self.error or self.note
        height = max(2, rows - top - 1 - bool(line))     # the view, the status bar below it
        view = self.views[self.view]
        self.views["git"].busy(next((text for kind, text in BUSY.items() if kind in self.running), None))
        if self.view == "files":
            view.draw(canvas, top, height, self.status or EMPTY)
        elif self.view in ("search", "issues"):
            view.draw(canvas, top, height, roomy)
        else:
            view.draw(canvas, top, height, self.status, self.graph, roomy)
        if line:
            canvas.put(rows - 2, 0, " " * cells)
            canvas.put(rows - 2, 1, truncate(line, cells - 2), Style(fg="deleted" if self.error else "muted"))
        self.status_bar(canvas, rows - 1)
        for y in (*range(top), rows - 1):                  # the header and the status bar: the pane's own menu
            canvas.backdrop(y, 0, cells, "pane")
        if self.menu:
            menu, y, x = self.menu[:3]
            menu.draw(canvas, *menu.at(y, x, cells, 0, rows))
        elif self.tip:
            self.draw_tip(canvas)
        self.canvas = canvas
        self.term.write(self.renderer.frame(canvas))
        self.term.flush()

    def switcher(self, canvas, roomy):
        """The views as tabs, the shown one lit, and the ⋯ (the pane's own menu) apart at the right edge, the shown
        view's title between them; the column is never narrower than all of them (narrowest()). Returns the row the
        view starts at: right under tall tabs, a row of air under one-row ones."""
        nerd, tabs = self.settings["icons"], self.tabs()
        marks, x, cells = glyphs(nerd), 1, TAB
        more = canvas.width - 1 - cells                                      # the ⋯: at the right edge
        row, taken = canvas.control(0, more, cells, 1, "badge", roomy)
        self.dots = (taken, None, more + cells)                 # its menu: right under it, its right edge with it
        lit = "text" if self.pointed == "panels" else "muted"
        canvas.put(row, centered(more, cells), "⋯", Style(fg=lit, bg="badge"))
        for y in range(taken):
            canvas.region(y, more, more + cells, "panels")
        for view in tabs:
            shown = view == self.view
            color = "selection" if shown else "badge"
            row, taken = canvas.control(0, x, cells, 1, color, roomy)
            lit = "accent" if shown else "text" if view == self.pointed else "muted"   # under the mouse: brighter
            canvas.put(row, centered(x, cells), marks[view], Style(fg=lit, bg=color, bold=shown))
            for y in range(taken):
                canvas.region(y, x, x + cells, "view:" + view)
            x += cells + 1
        canvas.put(row, x, truncate(VIEWS[self.view], more - 1 - x), Style(fg="accent", bold=True))   # as herdr's
        return taken + (0 if roomy else 1)

    def status_bar(self, canvas, y):
        status = self.status
        canvas.put(y, 0, " " * canvas.width, Style(bg="badge"))     # the footer: one bar, the branch and its sync
        if not self.repo or status is None or status.error:
            return
        dirty = "*" if status.staged or status.changes else ""
        name = "" if self.own else os.path.basename(self.repo) + " "     # one chosen in Files: which one
        branch = truncate(f"{name}⎇ {status.branch or 'detached'}{dirty}", canvas.width - 13)
        x = canvas.put(y, 1, branch, Style(fg="text", bg="badge"))
        sync = f"↻ {status.behind}↓ {status.ahead}↑" if status.upstream else "↻"
        syncing = "sync" in self.running or "commit" in self.running
        end = canvas.put(y, x + 3, sync, Style(fg="accent" if syncing else "muted", bg="badge"))
        canvas.region(y, x + 2, end + 1, "sync")


def main(argv):
    reap()
    home = os.path.expanduser("~")
    state = os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.join(home, ".local", "state", "herdr", "plugins",
                                                                     "herdr-fold.sidebar")
    if os.name == "nt":
        from keys_windows import WindowsTerminal as Terminal
    else:
        from keys_unix import UnixTerminal as Terminal
    if argv[1:2] == ["--conversations"]:
        from conversations_app import ConversationsApp
        app = ConversationsApp(Terminal(), preview.Herdr(), state)
    else:
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
