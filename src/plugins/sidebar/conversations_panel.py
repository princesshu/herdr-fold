"""The Conversations panel's work in the dock (conversation_list.py draws it): its list read again every second, a
running conversation focused, a closed one reopened in a new tab of its workspace, one archived, renamed or copied;
done through the sidebar that hosts it (its jobs, herdr, its note)."""
import base64
import os
import re
import sys
from dataclasses import replace

import conversations
import panes
import preview
import richtext
from conversation_list import ConversationList
from fileops import system_clipboard

POLL = 1.0                    # seconds between two looks at the conversations
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


class Conversations:
    """The list (VIEW) and what it asks for, done through HOST: the sidebar."""

    def __init__(self, host):
        self.host, self.view = host, ConversationList()
        self.next_read = 0.0
        self.here = os.environ.get("HERDR_WORKSPACE_ID")
        self.folders = {}                     # a folder a workspace's pane is in → that workspace
        self.clipboard = system_clipboard(sys.platform)

    def tick(self, now):
        """The list read again every POLL seconds; the archived ones shown or hidden in another tab: here too. Whether
        anything shown changed."""
        if now < self.next_read:
            return False
        self.next_read = now + POLL
        if "read" not in self.host.running:
            self.host.job("read", self.read, self.got)
        archived = conversations.setting(self.host.state_dir).get("show_archived") is True
        if archived == self.view.show_archived:
            return False
        self.view.show_archived = archived
        self.view.rebuild()
        return True

    def read(self):
        """On the job's thread: the conversations, the workspaces in the Spaces list's order with their states, each
        folder's workspace, the archived ones and the agents' panes in each workspace's active tab."""
        state, call = self.host.state_dir, self.host.herdr.call
        reopened = panes.resumed(state)
        try:
            agents = call("agent", "list").get("agents") or []
            spaces = sorted(call("workspace", "list").get("workspaces") or [], key=lambda space: space.get("number", 0))
            found = call("pane", "list").get("panes") or []
        except RuntimeError:
            agents, spaces, found = [], [], []
        else:                                   # a reopened one's pane: forgotten once herdr knows its session
            untold = {agent.get("pane_id") for agent in agents if not (agent.get("agent_session") or {}).get("value")}
            if set(reopened) - untold:
                reopened = {pane: id for pane, id in reopened.items() if pane in untold}
                conversations.keep(state, resumed=reopened)
        names = {space["workspace_id"]: space.get("label") or space["workspace_id"] for space in spaces}
        folders = {}
        for pane in found:
            if pane.get("cwd") and pane.get("workspace_id") in names:
                folders.setdefault(pane["cwd"], pane["workspace_id"])
        active = {space.get("active_tab_id") for space in spaces}
        return {"found": conversations.local(state, agents, reopened), "names": names, "folders": folders,
                "order": [names[s["workspace_id"]] for s in spaces],
                "front": {agent.get("pane_id") for agent in agents if agent.get("tab_id") in active},
                "states": {names[s["workspace_id"]]: s.get("agent_status") for s in spaces},
                "archived": conversations.archived(state)}

    def got(self, seen):
        names, self.folders = seen["names"], seen["folders"]
        view = self.view
        view.archived, view.front, view.states, view.icons = (seen["archived"], seen["front"], seen["states"],
                                                              self.host.settings["icons"])
        view.set(seen["found"], seen["order"], lambda folder: names.get(self.folders.get(folder)), names.get(self.here))

    def find(self):
        """Cmd+Shift+R here: the filter empty and the keys in it (the dock shows the panel)."""
        self.view.field.clear()
        self.view.rebuild()

    def left(self):
        return {"typed": self.view.typed, "opened": sorted(self.view.opened), "closed": sorted(self.view.closed)}

    def take(self, left):
        if isinstance(left.get("typed"), str):
            self.view.field.insert(left["typed"])
        self.view.opened.update(name for name in left.get("opened") or () if isinstance(name, str))
        self.view.closed.update(name for name in left.get("closed") or () if isinstance(name, str))

    # --- what the list asks for

    def do_copy(self, item):
        self.host.job("copy", lambda: self.copy(item), self.copied)

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
            self.host.term.write("\x1b]52;c;" + base64.b64encode(text.encode("utf-8")).decode("ascii") + "\x07")
        self.host.note = "Conversation copied"

    def do_archive(self, *items):
        self.file(items, True)
        self.host.note = "Archived" if len(items) == 1 else f"{len(items)} archived"

    def do_unarchive(self, *items):
        self.file(items, False)
        self.host.note = "Back in the list"

    def do_rename(self, item, name):
        """ITEM named NAME by hand, as herdr's Rename pane names one: AI Sessions keeps it and shows it too, a
        running one's pane takes it, and so does its tab if it has the tab to itself."""
        name = preview.label(name)
        self.host.job("rename", lambda: self.rename(item, name), lambda _: self.renamed(item, name))

    def rename(self, item, name):
        conversations.name_session(item.id, name)
        if item.pane:
            call = self.host.herdr.call
            call("pane", "rename", item.pane, name)
            tab = own_tab(call, item.pane)
            if tab:
                call("tab", "rename", tab, tab_name(name))

    def renamed(self, item, name):
        """At once in the list, before its next read."""
        key = self.view.key(("item", item))
        self.view.items = [replace(one, title=name) if self.view.key(("item", one)) == key else one
                           for one in self.view.items]
        self.view.rebuild()
        self.host.note = "Renamed"

    def do_show_archived(self, shown):
        """The archived conversations in sight (SHOWN) or out of it, in every tab."""
        conversations.keep(self.host.state_dir, show_archived=shown)
        self.view.show_archived = shown
        self.view.rebuild()

    def file(self, items, off):
        """ITEMS off the list (OFF) or back on it, in every tab; their files as they were."""
        keys = {self.view.archive_key(item) for item in items}
        conversations.archive(self.host.state_dir, keys, off)
        self.view.archived = (self.view.archived | keys) if off else (self.view.archived - keys)
        self.view.rebuild()

    def do_open(self, item):
        if item.pane:
            self.host.job("go", lambda: self.host.herdr.call("agent", "focus", item.pane))
        else:
            self.host.job("reopen", lambda: self.reopen(item))

    def reopen(self, item):
        """A new tab with ITEM in the workspace of its folder: the agent resuming it on the left, the right column
        beside it."""
        if not SESSION.fullmatch(item.id):     # from a file's content: never an option, a space or a control code
            raise RuntimeError("not a conversation's id")
        workspace = self.folders.get(item.folder)
        if not workspace:                       # its workspace closed since the list was read
            raise RuntimeError("its workspace is gone")
        call, state = self.host.herdr.call, self.host.state_dir
        made = call("tab", "create", "--workspace", workspace, "--cwd", item.folder, "--label", tab_name(item.title),
                    "--no-focus")
        pane = made["root_pane"]["pane_id"]
        call("pane", "rename", pane, item.agent)       # named, so the new-tab plugin leaves it alone
        panes.build(call, pane, item.folder, state)    # the right column, as elsewhere
        resume = ["--resume", item.id] if item.agent == "claude" else ["resume", item.id]
        panes.resume(state, pane, item.id)             # its row marked before herdr knows the session
        call("agent", "start", f"{item.agent}-{item.id[:8]}", "--kind", item.agent, "--pane", pane, "--timeout",
             "60000", "--", *resume)
        if conversations.manual_names().get(item.id) == item.title:   # a name given in herdr goes back on its pane
            call("pane", "rename", pane, preview.label(item.title))
        call("tab", "focus", made["tab"]["tab_id"])
