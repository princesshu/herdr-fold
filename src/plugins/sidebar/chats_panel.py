"""The Chats list's work in the dock (chat_list.py draws it): read every second while open with the chosen chat's plan,
a running chat focused, a closed one reopened in a new tab, one archived, renamed, copied or, once asked, moved to the
Trash, a Claude chat's files restored to a checkpoint; done through its host, the sidebar (jobs, herdr, note)."""
import base64
import os
import re
import sys
from dataclasses import replace

import chats
import checkpoints
import panes
import plan
import preview
import richtext
import usage
from chat_list import ChatList
from family import Family
from fileops import system_clipboard

POLL = 1.0                    # seconds between two looks at the chats
AWAY = 10.0                   # the same while closed: the ✦'s count and reopened panes cleared all the same
TAB_NAME = 24                 # characters of a chat's name on its tab, as AI Sessions puts it there
SESSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]*")     # a chat's id, as claude --resume and codex resume take


def tab_name(name):
    """NAME as its chat's tab shows it (sessions-view's tab_name): TAB_NAME characters at most, a longer one cut
    with "…"; a clean label for herdr's command line."""
    name = preview.label(name)
    return name if len(name) <= TAB_NAME else name[:TAB_NAME - 1] + "…"


def answered(work):
    """WORK's answer (core/checkpoints.py's), or {error} for what stopped it: the view waits on an answer."""
    try:
        return work()
    except (OSError, ValueError) as err:
        return {"error": chats.said(err)}


def own_tab(call, pane):
    """PANE's tab if its chat has the tab to itself, else None; never a workspace's main tab, which keeps the
    workspace's name."""
    agents = call("agent", "list").get("agents") or []
    tab = next((agent.get("tab_id") for agent in agents if agent.get("pane_id") == pane), None)
    if not tab or sum(agent.get("tab_id") == tab for agent in agents) != 1:
        return None
    return None if (call("tab", "get", tab).get("tab") or {}).get("number") == 1 else tab


class Chats(Family):
    """The list (VIEW) and what it asks for, done through HOST: the sidebar."""
    PANELS = ("chats",)

    def __init__(self, host):
        super().__init__(host)
        self.view = ChatList()
        self.views = {"chats": self.view}
        self.read_at = None                   # when the list was last read
        self.here = os.environ.get("HERDR_WORKSPACE_ID")
        self.folders = {}                     # a folder a workspace's pane is in → that workspace
        self.plans = {}                       # the chosen chat's list as last read (plan.read's), by "<agent>:<id>"
        self.clipboard = system_clipboard(sys.platform)

    def tick(self, now):
        """The list read again every POLL seconds, AWAY while it is off screen; the archived ones shown or hidden in
        another tab: here too. Whether anything shown changed."""
        if now < self.next_read():
            return False
        self.read_at = now
        if "read" not in self.host.running:
            self.host.job("read", self.read, self.got)
        chosen = self.view.chosen()
        if chosen and self.host.showing("chats") and "plan" not in self.host.running:
            self.host.job("plan", lambda: self.read_plan(chosen), self.got_plan)
        archived = chats.setting(self.host.state_dir).get("show_archived") is True
        if archived == self.view.show_archived:
            return False
        self.view.show_archived = archived
        self.view.rebuild()
        return True

    def read(self):
        """On the job's thread: the chats, the workspaces in the Spaces list's order, each folder's workspace, the
        archived ones and the agents' panes in each workspace's active tab."""
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
            gone = set(reopened) - untold
            reopened = {pane: id for pane, id in reopened.items() if pane in untold}
            if gone:                            # on what it holds then: a reopen job may have noted one meanwhile
                chats.change(state, lambda kept: {**kept, "resumed": {
                    pane: id for pane, id in panes.reopened(kept).items() if pane not in gone}})
        names = {space["workspace_id"]: space.get("label") or space["workspace_id"] for space in spaces}
        folders = {}
        for pane in found:
            if pane.get("cwd") and pane.get("workspace_id") in names:
                folders.setdefault(pane["cwd"], pane["workspace_id"])
        active = {space.get("active_tab_id") for space in spaces}
        return {"found": chats.local(state, agents, reopened), "names": names, "folders": folders,
                "order": [names[s["workspace_id"]] for s in spaces],
                "front": {agent.get("pane_id") for agent in agents if agent.get("tab_id") in active},
                "archived": chats.archived(state)}

    def got(self, seen):
        names, self.folders = seen["names"], seen["folders"]
        view = self.view
        view.archived, view.front, view.icons = seen["archived"], seen["front"], self.host.settings["icons"]
        view.set(seen["found"], seen["order"], lambda folder: names.get(self.folders.get(folder)), names.get(self.here))
        shown = view.points                     # its checkpoints read again once the chat has changed
        fresh = next((one for one in seen["found"] if shown and (one.agent, one.id) == (shown.item.agent,
                                                                                       shown.item.id)), None)
        if fresh and fresh.time != shown.item.time and not shown.busy and "points" not in self.host.running:
            shown.item = fresh
            self.do_checkpoints(fresh)

    def read_plan(self, item):
        """On the job's thread: ITEM's task list, its file read on from where the last read of it stopped."""
        key, paths = self.view.archive_key(item), chats.own_files(item.agent, item.id)
        return key, plan.read(item.agent, paths[0] if paths else None, self.plans.get(key))

    def got_plan(self, found):
        key, got = found
        self.plans = {key: got}                 # the chosen chat's alone is kept
        self.view.plan = (key, plan.shown(got["state"]))

    def waiting(self):
        """How many chats wait for an answer (herdr's blocked: a question, a permission): the count beside the
        ✦, in the row and on the rail."""
        return sum(item.state == "blocked" for item in self.view.items or ())

    def find(self):
        """Cmd+Shift+R here: the filter empty and the keys in it (the dock opens the list)."""
        self.view.field.clear()
        self.view.rebuild()

    def next_read(self):
        if self.read_at is None:
            return 0.0
        return self.read_at + (POLL if self.host.showing("chats") else AWAY)

    def deadlines(self):
        return [self.next_read()]

    def holds(self):
        return (self.view.naming, self.view.confirm, self.view.points)

    def left(self):
        view = self.view
        return {"chats": {"typed": view.typed, "opened": sorted(view.opened), "closed": sorted(view.closed)}}

    def take(self, left):
        mine = left.get("chats") if isinstance(left.get("chats"), dict) else {}
        if isinstance(mine.get("typed"), str):
            self.view.field.insert(mine["typed"])
        self.view.opened.update(name for name in mine.get("opened") or () if isinstance(name, str))
        self.view.closed.update(name for name in mine.get("closed") or () if isinstance(name, str))

    # --- what the list asks for

    def do_copy(self, item):
        self.host.job("copy", lambda: self.copy(item), self.copied)

    def copy(self, item):
        """On the job's thread: ITEM's whole chat on the clipboard as Markdown, formatted beside it on a Mac;
        the text back when there is no clipboard program (the terminal's own carries it then)."""
        paths = chats.session_files(item.agent, item.id)
        if not paths:
            raise RuntimeError("its file is gone")
        text = chats.markdown(item, paths[0])
        if not self.clipboard(text):
            return text
        if sys.platform == "darwin":
            richtext.copy_rich(text, text)
        return None

    def copied(self, text):
        if text is not None:                       # no clipboard program: the terminal's own (OSC 52)
            self.host.term.write("\x1b]52;c;" + base64.b64encode(text.encode("utf-8")).decode("ascii") + "\x07")
        self.host.note = "Chat copied"

    def do_plan(self, item):
        self.host.job("plan-open", lambda: self.plan_file(item), self.show_plan)

    def plan_file(self, item):
        """On the job's thread: ITEM's approved plan kept as a file in the plugin's state, and the chat's name."""
        if not SESSION.fullmatch(item.id):     # from a file's content: never a path's part with a slash in it
            raise RuntimeError("not a chat's id")
        paths = chats.own_files(item.agent, item.id)
        path = plan.document(paths[0], os.path.join(self.host.state_dir, "plans", item.id)) if paths else None
        if not path:
            raise RuntimeError("its plan is gone")
        return path, item.title

    def show_plan(self, found):
        """The plan in the user's editor, named after its chat."""
        path, title = found
        self.host.open_file(path, None, os.path.dirname(path), f"plan · {preview.label(title)}")

    def do_archive(self, *items):
        self.file(items, True)
        self.host.note = f'Archived "{items[0].title}"' if len(items) == 1 else f"Archived {len(items)} chats"

    def do_unarchive(self, *items):
        self.file(items, False)
        self.host.note = "Back in the list"

    def do_delete(self, item):
        """ITEM's file to the system's Trash, its row gone from the list already (the view's yes)."""
        self.host.job(f"delete-{item.agent}-{item.id}", lambda: self.delete(item), lambda why: self.deleted(item, why))

    def delete(self, item):
        """On the job's thread: herdr asked once more whether it runs, then chats.delete; why not, else None."""
        state = self.host.state_dir
        try:
            agents = self.host.herdr.call("agent", "list").get("agents") or []
            chats.delete(state, item.agent, item.id, agents, panes.resumed(state))
        except (RuntimeError, OSError) as err:          # herdr not answering: it may be running
            return chats.said(err)
        return None

    def deleted(self, item, why):
        """Said on the dock's last row: where it went, or WHY not, its row back then."""
        if why:
            self.view.back(item)
            self.host.error = why
        else:
            self.host.note = "Moved to the Trash"

    def do_no_delete(self, _item):
        self.host.note = "A running chat is not deleted"

    def do_rename(self, item, name):
        """ITEM named NAME by hand, as herdr's Rename pane names one: AI Sessions keeps it and shows it too, a
        running one's pane takes it, and so does its tab if it has the tab to itself."""
        name = preview.label(name)
        self.host.job("rename", lambda: self.rename(item, name), lambda _: self.renamed(item, name))

    def rename(self, item, name):
        chats.name_session(item.id, name)
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

    # --- a Claude chat's checkpoints (checkpoint_list.py), through core/checkpoints.py and Claude's own rewind

    def points_of(self, item):
        """The checkpoints view while it shows ITEM; None once closed or showing another."""
        shown = self.view.points
        return shown if shown and shown.item.id == item.id else None

    def do_checkpoints(self, item):
        shown = self.points_of(item)
        if shown:
            shown.twelve = usage.twelve_hours(os.path.expanduser("~"))
        self.host.job("points", lambda: answered(lambda: checkpoints.listed(item.id)),
                      lambda found: self.got_points(item, found))

    def got_points(self, item, found):
        shown = self.points_of(item)
        if shown and "error" in found:
            shown.told = (found["error"], True)
            shown.set({"points": [], "undo": None})
        elif shown:
            shown.set(found)

    def do_checkpoint_ask(self, item, point):
        """Claude's dry run for POINT, shown under it while it is still the one chosen."""
        def got(asked):
            shown = self.points_of(item)
            if shown and shown.asked == "asking" and (shown.chosen() or {}).get("id") == point["id"]:
                shown.asked = asked
        self.host.job("point-ask", lambda: answered(lambda: checkpoints.ask(item.id, point["id"])), got)

    def do_checkpoint_restore(self, item, point, last):
        """ITEM's files back to POINT (LAST its newest point, the Undo's), what happened said on the view's foot."""
        def done(answer):
            shown = self.points_of(item)
            if shown:
                shown.busy, shown.asked = False, answer if "error" in answer else None
                if "error" not in answer:
                    shown.told = (shown.restored_words(answer["files"], point["id"]), False)
            self.do_checkpoints(item)
        self.host.job("point-restore", lambda: answered(lambda: checkpoints.restore(item.id, point["id"], last)), done)

    def do_checkpoint_undo(self, item):
        def done(answer):
            shown = self.points_of(item)
            if shown:
                files = answer.get("files", 0)
                shown.busy = False
                shown.told = (answer["error"], True) if "error" in answer else (
                    f"Undid the restore: {files} file{'' if files == 1 else 's'} back as they were", False)
            self.do_checkpoints(item)
        self.host.job("point-undo", lambda: answered(lambda: checkpoints.undo(item.id)), done)

    def do_show_archived(self, shown):
        """The archived chats in sight (SHOWN) or out of it, in every tab."""
        chats.keep(self.host.state_dir, show_archived=shown)
        self.view.show_archived = shown
        self.view.rebuild()

    def file(self, items, off):
        """ITEMS off the list (OFF) or back on it, in every tab; their files as they were."""
        keys = {self.view.archive_key(item) for item in items}
        chats.archive(self.host.state_dir, keys, off)
        self.view.archived = (self.view.archived | keys) if off else (self.view.archived - keys)
        self.view.rebuild()

    def do_open(self, item):
        if item.pane:
            self.host.job("go", lambda: self.host.herdr.call("agent", "focus", item.pane))
        elif f"reopen-{item.id}" not in self.host.running:      # a second Enter while it opens: still one tab
            self.host.job(f"reopen-{item.id}", lambda: self.reopen(item))

    def reopen(self, item):
        """A new tab with ITEM in the workspace of its folder: the agent resuming it on the left, the right column
        beside it."""
        if not SESSION.fullmatch(item.id):     # from a file's content: never an option, a space or a control code
            raise RuntimeError("not a chat's id")
        workspace = self.folders.get(item.folder)
        if not workspace:                       # its workspace closed since the list was read
            raise RuntimeError("its space is gone")
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
        if chats.manual_names().get(item.id) == item.title:           # a name given in herdr goes back on its pane
            call("pane", "rename", pane, preview.label(item.title))
        call("tab", "focus", made["tab"]["tab_id"])
