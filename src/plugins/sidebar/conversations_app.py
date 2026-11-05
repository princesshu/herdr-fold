"""The Conversations column (sidebar.py --conversations, in a pane of its own): its list read again every second, a
running conversation focused, a closed one reopened in a new tab of its workspace, and its width set in every tab (a
rail while collapsed). Ctrl+C quits; a new version of the plugin takes over in the same pane, as the sidebar's does."""
import base64
import os
import re
import sys
import time
from dataclasses import replace

import column
import conversations
import conversations_pane
import panels
import preview
import richtext
from conversation_list import RAIL, ConversationList
from fileops import system_clipboard
from loop import CODE, Loop
from screen import ROOMY, Canvas, Style, icons_on, truncate
from vt import Focus, Key, Mouse, Resize

POLL = 1.0                    # seconds between two looks at the conversations
NOTE = 4.0                    # seconds a note ("Archived", …) stays on the bottom row
TAB_NAME = 24                 # characters of a conversation's name on its tab, as AI Sessions puts it there
SESSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]*")     # a conversation's id, as claude --resume and codex resume take


def tab_name(name):
    """NAME as its conversation's tab shows it (sessions-view's tab_name): TAB_NAME characters at most, a longer one cut
    with "…"; a clean label for herdr's command line."""
    name = preview.label(name)
    return name if len(name) <= TAB_NAME else name[:TAB_NAME - 1] + "…"


def own_tab(call, pane):
    """PANE's tab if its conversation has the tab to itself, else None; never a workspace's main tab, which keeps the
    workspace's name."""
    agents = call("agent", "list").get("agents") or []
    tab = next((agent.get("tab_id") for agent in agents if agent.get("pane_id") == pane), None)
    if not tab or sum(agent.get("tab_id") == tab for agent in agents) != 1:
        return None
    return None if (call("tab", "get", tab).get("tab") or {}).get("number") == 1 else tab


class ConversationsApp(Loop):
    def __init__(self, terminal, herdr, state_dir, clock=time.monotonic, code=CODE):
        super().__init__(terminal, herdr, state_dir, clock, code)
        self.view = ConversationList()
        self.view.collapsed = None                # not known yet: the first tick sets it, and the width with it
        self.placed = False                       # this pane at the width it was given (until then a size is its own)
        self.last, self.unsaved = None, False     # the cells this tab was set to last (left, this, right), not kept yet
        self.frame = None                         # herdr's frame round this pane, measured once while nothing moves
        self.here = os.environ.get("HERDR_WORKSPACE_ID")
        self.tab = None                           # this pane's tab
        self.noted = 0.0                          # when the note was put up
        self.folders = {}                     # a folder a workspace's pane is in → that workspace
        self.clipboard = system_clipboard(sys.platform)

    # --- reading

    def tick(self):
        now, shown = self.clock(), False
        if self.note and now - self.noted >= NOTE:         # a note goes by itself; an error stays until a key
            self.note, shown = None, True
        if now >= self.next_poll:
            shown = self.follow(now) or shown             # a new version first, before this look starts a job
            if self.quit:
                return shown
            if "read" not in self.running:
                self.job("read", self.read, self.got)
            collapsed = conversations_pane.is_collapsed(self.state_dir)
            if collapsed != self.view.collapsed:          # collapsed or opened in some tab: here too
                opening = self.view.collapsed is True and not collapsed
                self.view.collapsed, shown = collapsed, True
                self.fit(opening)
            archived = conversations_pane.shows_archived(self.state_dir)
            if archived != self.view.show_archived:      # the archived ones shown or hidden in some tab
                self.view.show_archived, shown = archived, True
                self.view.rebuild()
            self.next_poll = now + POLL
        return shown

    def read(self):
        """On the job's thread: the conversations, the workspaces in the Spaces list's order with their states, each
        folder's workspace, the archived ones, the agents' panes in each workspace's active tab, and this pane's tab
        with the panes it lacks."""
        reopened = conversations_pane.resumed(self.state_dir)
        try:
            agents = self.herdr.call("agent", "list").get("agents") or []
            spaces = sorted(self.herdr.call("workspace", "list").get("workspaces") or [],
                            key=lambda space: space.get("number", 0))
            panes = self.herdr.call("pane", "list").get("panes") or []
        except RuntimeError:
            agents, spaces, panes = [], [], []
        else:                                   # a reopened one's pane: forgotten once herdr knows its session
            untold = {agent.get("pane_id") for agent in agents if not (agent.get("agent_session") or {}).get("value")}
            if set(reopened) - untold:
                reopened = {pane: id for pane, id in reopened.items() if pane in untold}
                conversations.keep(self.state_dir, resumed=reopened)
        names = {space["workspace_id"]: space.get("label") or space["workspace_id"] for space in spaces}
        folders = {}
        for pane in panes:
            if pane.get("cwd") and pane.get("workspace_id") in names:
                folders.setdefault(pane["cwd"], pane["workspace_id"])
        active = {space.get("active_tab_id") for space in spaces}
        front = {agent.get("pane_id") for agent in agents if agent.get("tab_id") in active}
        tab = next((p["tab_id"] for p in panes if p.get("pane_id") == os.environ.get("HERDR_PANE_ID")), None)
        missing = {"sidebar", "terminal"} - {p.get("label") for p in panes if p.get("tab_id") == tab}
        return {"found": conversations.local(self.state_dir, agents, reopened), "names": names, "folders": folders,
                "order": [names[s["workspace_id"]] for s in spaces], "front": front, "tab": tab,
                "states": {names[s["workspace_id"]]: s.get("agent_status") for s in spaces},
                "icons": icons_on(self.state_dir),
                "archived": conversations.archived(self.state_dir), "missing": missing if tab else set()}

    def got(self, seen):
        names, self.folders, self.tab = seen["names"], seen["folders"], seen["tab"]
        self.view.archived, self.view.front, self.view.missing = seen["archived"], seen["front"], seen["missing"]
        self.view.states, self.view.icons = seen["states"], seen["icons"]
        self.view.set(seen["found"], seen["order"], lambda folder: names.get(self.folders.get(folder)),
                      names.get(self.here))

    def left(self):
        return {"typed": self.view.typed, "opened": sorted(self.view.opened), "closed": sorted(self.view.closed)}

    def take(self, left):
        if isinstance(left.get("typed"), str):
            self.view.field.insert(left["typed"])
        self.view.opened.update(name for name in left.get("opened") or () if isinstance(name, str))
        self.view.closed.update(name for name in left.get("closed") or () if isinstance(name, str))

    # --- events

    def handle(self, event):
        if isinstance(event, Resize):
            self.renderer.reset()
            self.resized()
            return
        if isinstance(event, Focus):
            if not event.gained:                  # a click in another pane: its menu does not stay open behind
                self.view.close_menu()
            return
        if isinstance(event, Key):
            if event.name == "char" and event.ctrl and event.char == "c":
                self.quit = True
                return
        if isinstance(event, Key) or isinstance(event, Mouse) and event.kind == "press":
            self.error = self.note = None
        self.act(self.view.handle(event))

    # --- the width

    def fit(self, opening=False):
        """This pane as wide as it should be: a rail of RAIL cells while collapsed, else the width remembered (OPENING
        from a rail at least MIN_OPEN); the agent before it gives or takes the room."""
        pane = os.environ.get("HERDR_PANE_ID")
        if pane:
            self.placed = False
            self.job("width", lambda: self.place(pane, opening), lambda _: setattr(self, "placed", True))

    def target(self, tab, pane, opening=False):
        """(the right column's cells, this pane's, herdr's frame round it) as they should be in TAB now: the right
        column as remembered, at least column.least(); this one a rail while collapsed, else as remembered, at least
        COLLAPSE_BELOW (MIN_OPEN when OPENING from a rail)."""
        whole = tab.cells
        if self.frame is None:                    # mid-drag herdr's cells run ahead of the terminal's: measured once
            self.frame = column.frame(tab, pane, self.term.size()[0])
        frame = self.frame
        right = max(round((1 - (column.saved(self.state_dir) or column.RIGHT)) * whole),
                    column.least(self.state_dir, tab.tab) + frame)
        if self.view.collapsed:
            return right, RAIL + frame, frame
        before = whole - right
        mine = (1 - (column.saved(self.state_dir, conversations.SETTINGS) or conversations_pane.RATIO)) * before
        least = conversations_pane.MIN_OPEN if opening else conversations_pane.COLLAPSE_BELOW
        if mine - frame < least:                                # opened from a rail: never as squeezed as it was
            mine = max((1 - conversations_pane.RATIO) * before, min(least + frame, before / 2))
        return right, round(mine), frame

    def place(self, pane, opening=False):
        """On the job's thread: PANE as fit() says, in the cells herdr has the tab in now."""
        tab = column.read(pane)
        if not tab or tab.inner is None or not tab.cells:
            return False
        right, mine, _ = self.target(tab, pane, opening)
        changed = column.arrange(tab, right=right / tab.cells, conversations=mine / tab.cells)
        self.last = (tab.cells - right - mine, mine, right)
        return changed

    def drag(self, pane):
        """On the job's thread: this tab, the one on screen, was resized by a drag, so its widths are set again (open,
        the agent's border resizes this column, collapsing it below COLLAPSE_BELOW; else the right column takes it) and
        kept once they settle. A whole-window resize is no drag. Returns "collapse" for the main thread, or None."""
        tab = column.read(pane)
        if not tab or tab.inner is None or not tab.cells or not self.placed or self.view.collapsed is None:
            return None
        if not column.visible(tab):                             # out of sight: set by the tab dragged
            return None
        whole, now = tab.cells, column.cells(tab)
        want_right, want_mine, frame = self.target(tab, pane)
        last = self.last or (whole - want_right - want_mine, want_mine, want_right)
        if sum(last) != whole:                                  # the window resized (Ghostty opening), no border
            self.last = now                                     # dragged: every column keeps the share herdr gave it
            return None
        if now != last:
            left, mine, right = now
            if left == last[0]:                                 # the border with the right column
                mine = want_mine if self.view.collapsed else last[1]
            elif self.view.collapsed:                           # the agent's border, the rail moving with it
                mine, right = want_mine, whole - left - want_mine
            else:                                               # the agent's border: this column's own width
                right, mine = last[2], whole - left - last[2]
                if mine - frame < conversations_pane.COLLAPSE_BELOW:
                    return "collapse"
            right = max(right, column.least(self.state_dir, tab.tab) + frame)    # its sidebar's buttons, every one
            column.arrange(tab, right=right / whole, conversations=mine / whole)
            self.last, self.unsaved = (whole - right - mine, mine, right), True
        if self.unsaved and column.settled(pane):              # still: kept, and set in every other tab
            left, mine, right = self.last
            self.unsaved = False
            column.spread(self.state_dir, pane, right=right / whole,
                          agent=None if self.view.collapsed else 1 - mine / (whole - right),
                          file=conversations.SETTINGS)
        return None

    def dragged(self, result):
        if result == "collapse":
            self.turn(True)                       # dragged narrower than it opens: collapsed, in every tab

    def do_collapse(self):
        self.turn(True)

    def do_expand(self):
        self.turn(False)

    def turn(self, collapsed):
        """Collapsed (or opened) in every tab: this pane at once, the others at their next look."""
        conversations_pane.collapse(self.state_dir, collapsed)
        self.view.collapsed = collapsed
        self.fit(opening=not collapsed)

    def do_copy(self, item):
        self.job("copy", lambda: self.copy(item), self.copied)

    def copy(self, item):
        """On the job's thread: ITEM's whole conversation on the clipboard as Markdown, formatted beside it on a Mac;
        the text back when there is no clipboard program (the terminal's own carries it then)."""
        paths = conversations.session_files(item.agent, item.id)
        if not paths:
            raise RuntimeError("its file is gone")
        text = conversations.markdown(item, paths[0])
        if not self.clipboard(text):
            return text
        if sys.platform == "darwin":
            richtext.copy_rich(text, text)
        return None

    def copied(self, text):
        if text is not None:                       # no clipboard program: the terminal's own (OSC 52)
            self.term.write("\x1b]52;c;" + base64.b64encode(text.encode("utf-8")).decode("ascii") + "\x07")
        self.say("Conversation copied")

    def say(self, note):
        self.note, self.noted = note, self.clock()

    def do_archive(self, *items):
        self.file(items, True)
        self.say("Archived" if len(items) == 1 else f"{len(items)} archived")

    def do_unarchive(self, *items):
        self.file(items, False)
        self.say("Back in the list")

    def do_rename(self, item, name):
        """ITEM named NAME by hand, as herdr's Rename pane names one: AI Sessions keeps it and shows it too, a
        running one's pane takes it, and so does its tab if it has the tab to itself."""
        name = preview.label(name)
        self.job("rename", lambda: self.rename(item, name), lambda _: self.renamed(item, name))

    def rename(self, item, name):
        conversations.name_session(item.id, name)
        if item.pane:
            self.herdr.call("pane", "rename", item.pane, name)
            tab = own_tab(self.herdr.call, item.pane)
            if tab:
                self.herdr.call("tab", "rename", tab, tab_name(name))

    def renamed(self, item, name):
        """At once in the list, before its next read."""
        key = self.view.key(("item", item))
        self.view.items = [replace(one, title=name) if self.view.key(("item", one)) == key else one
                           for one in self.view.items]
        self.view.rebuild()
        self.say("Renamed")

    def do_close_panel(self, kind):
        """This tab's pane of KIND (the sidebar, the terminal) closed, as by hand."""
        if self.tab:
            tab = self.tab
            self.job("panels", lambda: panels.close(self.herdr.call, tab, kind))

    def do_show_panels(self, kinds):
        """KINDS (the sidebar, the terminal) back in this pane's tab, closed by hand before: in a process of its own,
        as the sidebar's menu does it."""
        if self.tab:
            conversations_pane.bring_apart(self.tab, kinds)

    def do_show_archived(self, shown):
        """The archived conversations in sight (SHOWN) or out of it, in every tab."""
        conversations.keep(self.state_dir, show_archived=shown)
        self.view.show_archived = shown
        self.view.rebuild()

    def file(self, items, off):
        """ITEMS off the list (OFF) or back on it, in every tab; their files as they were."""
        keys = {self.view.archive_key(item) for item in items}
        conversations.archive(self.state_dir, keys, off)
        self.view.archived = (self.view.archived | keys) if off else (self.view.archived - keys)
        self.view.rebuild()

    def do_open(self, item):
        if item.pane:
            self.job("go", lambda: self.herdr.call("agent", "focus", item.pane))
        else:
            self.job("reopen", lambda: self.reopen(item))

    def reopen(self, item):
        """A new tab with ITEM in the workspace of its folder: the agent resuming it on the left, the right column
        beside it."""
        if not SESSION.fullmatch(item.id):     # from a file's content: never an option, a space or a control code
            raise RuntimeError("not a conversation's id")
        workspace = self.folders.get(item.folder)
        if not workspace:                       # its workspace closed since the list was read
            raise RuntimeError("its workspace is gone")
        made = self.herdr.call("tab", "create", "--workspace", workspace, "--cwd", item.folder, "--label",
                               tab_name(item.title), "--no-focus")
        pane = made["root_pane"]["pane_id"]
        self.herdr.call("pane", "rename", pane, item.agent)       # named, so the new-tab plugin leaves it alone
        conversations_pane.build(self.herdr.call, pane, item.folder, self.state_dir)   # both columns, as elsewhere
        resume = ["--resume", item.id] if item.agent == "claude" else ["resume", item.id]
        conversations_pane.resume(self.state_dir, pane, item.id)     # its row marked before herdr knows the session
        self.herdr.call("agent", "start", f"{item.agent}-{item.id[:8]}", "--kind", item.agent, "--pane", pane,
                        "--timeout", "60000", "--", *resume)
        if conversations.manual_names().get(item.id) == item.title:   # a name given in herdr goes back on its pane
            self.herdr.call("pane", "rename", pane, preview.label(item.title))
        self.herdr.call("tab", "focus", made["tab"]["tab_id"])

    # --- drawing

    def draw(self):
        cells, rows = self.term.size()
        canvas = Canvas(cells, rows)
        line = self.error or self.note
        self.view.draw(canvas, 0, rows - (2 if line else 0), rows >= ROOMY)
        if line:
            canvas.put(rows - 1, 1, truncate(line, cells - 2), Style(fg="deleted" if self.error else "muted"))
        self.canvas = canvas
        self.term.write(self.renderer.frame(canvas))
        self.term.flush()
