"""The Files and Search panels' work in the dock (explorer.py and find.py draw them): the folder's tree and the files
made, renamed or moved to the Trash in it, a file in the preview tab, the search and the place chosen in Files it
covers; done through the sidebar that hosts them."""
import base64
import os
import threading

import media
import preview
import search
from explorer import Explorer
from family import Family
from fileops import Ops
from find import Find
from tree import Tree


def picker_there(herdr):
    """Whether herdr-fold's tab layout is there, with the folder picker of herdr's new button: herdr's plugin list."""
    try:
        plugins = herdr.call("plugin", "list", "--json").get("plugins") or []
    except RuntimeError:
        return False
    return any(plugin.get("plugin_id") == "herdr-fold.tab-layout" for plugin in plugins)


class Files(Family):
    PANELS = ("files", "search")

    def __init__(self, host):
        super().__init__(host)
        self.tree = Tree(host.root, show_hidden=host.settings["hidden"])
        icons = host.settings["icons"]
        self.views = {"files": Explorer(self.tree, icons, host.repo), "search": Find(host.root, icons, host.clock)}
        workspace = os.environ.get("HERDR_WORKSPACE_ID")
        self.views["files"].preview = preview.spec_file(host.state_dir, workspace) if workspace else None
        self.ops = Ops(host.root)
        self.searching = None                     # the running search's stop

    def tick(self, now):
        found = self.views["search"].tick(now)
        self.host.act(found, "search")
        return found is not None

    def deadlines(self):
        due = self.views["search"].deadline()
        return [due] if due else []

    def came(self, panel):
        if panel == "search":
            self.host.act(self.views["search"].within(self.chosen_place()), "search")

    def resume(self):
        if os.name != "nt":                     # the folder picker is not on Windows
            self.host.job("picker", lambda: picker_there(self.host.herdr), self.got_picker)

    def reload(self, folders=None):
        self.tree.reload(folders)

    def got_picker(self, there):
        self.views["files"].opens_workspace = there

    def took_status(self, answer):
        self.views["files"].repo = answer.repo or self.host.root
        self.views["files"].take(answer.status, answer.marks)

    def holds(self):
        files = self.views["files"]
        return files.naming, files.confirm

    def left(self):
        find, files, moved = self.views["search"], self.views["files"], self.host.moved_path
        return {"expanded": sorted(map(moved, self.tree.expanded)),
                "selected": moved(getattr(files.list.selected(), "path", None)), "top": files.list.top,
                "chosen": files.moved, "query": find.field.text, "switches": find.switches}

    def take(self, left):
        self.tree.expanded.update(p for p in left.get("expanded") or () if isinstance(p, str) and os.path.isdir(p))
        if isinstance(left.get("selected"), str):
            files = self.views["files"]
            files.select(left["selected"])
            files.moved = left.get("chosen") is True
            if isinstance(left.get("top"), int) and left["top"] >= 0:
                files.list.top = left["top"]      # as it was scrolled, not as a list not yet drawn (one row) puts it
        find = self.views["search"]
        for name, on in (left.get("switches") or {}).items():
            if name in find.switches:
                find.switches[name] = bool(on)
        find.place = self.chosen_place()
        if isinstance(left.get("query"), str) and left["query"]:
            find.field.insert(left["query"])
            self.host.act(find.ask(), "search")

    def stop(self):
        if self.searching:
            self.searching.set()

    def chosen_place(self):
        """The folder or file you chose in Files, for the search (from the root, with "/"), or "" for all of it: only
        the first row, chosen by itself (a row away from it is always yours, before an update too), or a link (it may
        lead out of the folder)."""
        files, root = self.views["files"], self.host.root
        node = files.list.selected()
        if not ((files.moved or files.list.index > 0) and node is not None and node.path) or node.path == root \
                or os.path.islink(node.path):
            return ""
        return os.path.relpath(node.path, root).replace(os.sep, "/")

    def chosen_folder(self):
        """The folder you chose in Files (a file's own folder), the root without a choice: in a folder that is no
        repository itself, Changes shows that one's."""
        path = os.path.normpath(os.path.join(self.host.root, self.chosen_place()))
        return path if os.path.isdir(path) else os.path.dirname(path)

    # --- what the views ask for

    def do_preview_file(self, path, line=None):
        self.host.open_preview(preview.file_spec(self.host.root, path, line), self.host.root)

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
            self.host.error = str(err)
            return
        self.tree.reload([folder])
        self.views["files"].select(path)
        self.host.refresh()

    def do_trash(self, path):
        def then(_):
            self.tree.reload([os.path.dirname(path)])
            self.host.refresh()
        self.host.job("trash", lambda: self.ops.trash(path), then)

    def do_new_workspace(self, folder):
        self.host.job("workspace", lambda: self.host.herdr.call(
            "plugin", "pane", "open", "--plugin", "herdr-fold.tab-layout", "--entrypoint", "new-workspace", "--focus",
            "--env", f"HERDR_NEW_WORKSPACE_FOLDER={folder}"))

    def do_close_preview(self):
        self.host.job("preview", lambda: preview.close_preview(self.host.herdr, os.environ["HERDR_WORKSPACE_ID"]))

    def do_open_browser(self, path):
        self.host.note = "Opened in the browser" if media.open_in_browser(path) else "No browser to open it in"

    def do_copy_path(self, path):
        if not self.ops.copy_path(path):        # no clipboard program: the terminal's own (OSC 52)
            self.host.term.write("\x1b]52;c;" + base64.b64encode(path.encode("utf-8")).decode("ascii") + "\x07")
            self.host.term.flush()
        self.host.note = "Path copied"

    def do_refresh(self):
        self.tree.reload()
        self.host.refresh()

    def do_show_hidden(self, show):
        self.host.save(hidden=show)

    def do_search(self, query, place):
        if self.searching:
            self.searching.set()                # the older search stops; its answer would be dropped anyway
        self.searching = stop = threading.Event()
        self.host.job("search", lambda: search.search(self.host.root, query, cancel=stop, place=place),
                      lambda result: self.views["search"].show(result, query, place))
