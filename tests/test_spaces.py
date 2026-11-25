"""Tests for the Spaces plugin (spaces.py) with fake herdr calls: the new button's workspace and its folder
picker, a workspace whose folder is gone or renamed, a folder holding a repository, home staying the first workspace,
and a workspace herdr ended with its last tab made again."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import set_attrs, set_env

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "plugins", "spaces"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import spaces  # noqa: E402


def manifest_events(on):
    """(platforms, command) of each of the manifest's [[events]] on herdr's event ON."""
    with open(os.path.join(os.path.dirname(os.path.abspath(spaces.__file__)), "herdr-plugin.toml"),
              encoding="utf-8") as f:
        manifest = f.read()
    return re.findall(rf'\[\[events\]\]\non = "{re.escape(on)}"\nplatforms = (\[.*\])\ncommand = (\[.*\])', manifest)


class NewTab(unittest.TestCase):
    """The new button's workspace gets the folder picker; any other new tab, and every one on Windows, gets nothing
    from Spaces."""

    def setUp(self):
        self.calls = []

        def herdr(*args, **kwargs):
            self.calls.append(args)
            return {}
        set_attrs(self, spaces, herdr=herdr, new_workspace=lambda ws: True)
        set_attrs(self, spaces.time, sleep=lambda s: None)
        set_attrs(self, os, name="posix")
        set_env(self, HERDR_PLUGIN_EVENT=None, HERDR_PLUGIN_STATE_DIR=None,
                HERDR_PLUGIN_EVENT_JSON=json.dumps({"data": {"tab": {"tab_id": "w2:t1"}}}))

    def test_the_new_buttons_workspace_is_called_new_while_its_folder_is_chosen(self):
        # herdr names it after the folder it inherits: ~, or the active workspace's own name a second time
        spaces.main()
        opened = next(n for n, call in enumerate(self.calls) if call[:3] == ("plugin", "pane", "open"))
        self.assertIn(("workspace", "rename", "w2", "new"), self.calls[:opened])
        self.assertEqual(self.calls[opened][:7], ("plugin", "pane", "open", "--plugin", "herdr-fold.spaces",
                                                  "--entrypoint", "new-workspace"))

    def test_the_picker_is_told_the_workspace_it_was_opened_from(self):
        # Esc goes back there: herdr alone would show a neighbour of the closed one
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state)
        with open(os.path.join(state, spaces.FOCUS), "w") as f:
            json.dump({"now": "w2", "before": "w1"}, f)                     # the new one already in front
        set_env(self, HERDR_PLUGIN_STATE_DIR=state)
        spaces.main()
        opened = next(call for call in self.calls if call[:3] == ("plugin", "pane", "open"))
        self.assertIn("HERDR_CAME_FROM=w1", opened)

    def test_any_other_new_tab_gets_nothing_from_it(self):
        # its column is the dock's (the sidebar's panes.py --new-tab)
        set_attrs(self, spaces, new_workspace=lambda ws: False)
        spaces.main()
        self.assertEqual(self.calls, [])

    def test_a_new_tab_on_windows_gets_nothing_from_it(self):
        # no folder picker there: its key handling is Unix-only
        os.name = "nt"
        spaces.main()
        self.assertEqual(self.calls, [])

    def test_the_manifest_runs_it_on_a_new_tab_on_macos_and_linux_only(self):
        self.assertEqual(manifest_events("tab.created"),
                         [('["macos", "linux"]', '["/usr/bin/python3", "spaces.py"]')])


class Leftovers(unittest.TestCase):
    def test_the_new_buttons_empty_workspace_left_behind_goes_never_one_in_use(self):
        # its picker closed from outside, or left before it finished: an empty "new" not in front is closed
        workspaces = [{"workspace_id": "w1", "label": "lumen-api", "focused": True},
                      {"workspace_id": "w2", "label": spaces.PLACEHOLDER},
                      {"workspace_id": "w3", "label": spaces.PLACEHOLDER, "focused": True},           # its picker on
                      {"workspace_id": "w4", "label": spaces.PLACEHOLDER},                            # an agent in it
                      {"workspace_id": "w5", "label": spaces.PLACEHOLDER}]                            # worked in
        panes = [{"workspace_id": "w1"}, {"workspace_id": "w2"}, {"workspace_id": "w3"},
                 {"workspace_id": "w4", "agent": "claude"}, {"workspace_id": "w5"}, {"workspace_id": "w5"}]
        self.assertEqual(spaces.leftovers(workspaces, panes), ["w2"])


class SpacesFollowTheirFolder(unittest.TestCase):
    """A workspace named after its folder takes the folder's new name when the folder is renamed while herdr runs
    (its panes' folders follow it there); a name you gave it stays."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.repos = os.path.join(self.tmp, "repos")
        os.makedirs(os.path.join(self.repos, "old-name", "src"))

    def path(self, *parts):
        return os.path.join(self.repos, *parts)

    def follow(self, labels, cwds, known, held=()):
        listed = [{"workspace_id": ws, "label": label} for ws, label in labels.items()]
        panes = [{"workspace_id": ws, "cwd": cwd} for ws, cwd in cwds]
        return spaces.follow_folders(listed, panes, known, held=lambda path: path in held)

    def known_before_the_rename(self):
        renames, known = self.follow({"w1": "old-name"}, [("w1", self.path("old-name"))], {})
        self.assertEqual(renames, [])
        self.assertEqual(known["w1"]["label"], "old-name")
        return known

    def test_a_renamed_folder_renames_its_workspace(self):
        known = self.known_before_the_rename()
        os.rename(self.path("old-name"), self.path("new-name"))
        renames, known = self.follow({"w1": "old-name"}, [("w1", self.path("new-name"))], known)
        self.assertEqual(renames, [("w1", "old-name", "new-name")])
        self.assertEqual(known["w1"]["label"], "new-name")
        self.assertEqual(self.follow({"w1": "new-name"}, [("w1", self.path("new-name"))], known)[0], [])

    def test_a_pane_in_a_subfolder_finds_the_renamed_folder(self):
        known = self.known_before_the_rename()
        os.rename(self.path("old-name"), self.path("new-name"))
        renames, _ = self.follow({"w1": "old-name"}, [("w1", self.path("new-name", "src"))], known)
        self.assertEqual(renames, [("w1", "old-name", "new-name")])

    def test_a_name_you_gave_the_workspace_stays(self):
        known = self.known_before_the_rename()
        os.rename(self.path("old-name"), self.path("new-name"))
        renames, known = self.follow({"w1": "Frontend"}, [("w1", self.path("new-name"))], known)
        self.assertEqual((renames, known), ([], {}))
        self.assertEqual(self.follow({"w1": "Frontend"}, [("w1", self.path("new-name"))], known), ([], {}))

    def test_a_pane_gone_to_another_folder_renames_nothing(self):
        known = self.known_before_the_rename()
        os.makedirs(self.path("other"))
        self.assertEqual(self.follow({"w1": "old-name"}, [("w1", self.path("other"))], known)[0], [])

    def test_a_deleted_folder_renames_nothing(self):
        known = self.known_before_the_rename()
        os.makedirs(self.path("new-name"))                    # made first: it cannot take the deleted one's identity
        os.rmdir(self.path("old-name", "src"))
        os.rmdir(self.path("old-name"))
        self.assertEqual(self.follow({"w1": "old-name"}, [("w1", self.path("new-name"))], known)[0], [])

    def test_the_new_name_avoids_another_workspaces(self):
        known = self.known_before_the_rename()
        os.rename(self.path("old-name"), self.path("new-name"))
        renames, _ = self.follow({"w1": "old-name", "w2": "new-name"}, [("w1", self.path("new-name"))], known)
        self.assertEqual(renames, [("w1", "old-name", "repos-new-name")])

    def test_a_folder_renamed_before_it_was_followed_is_known_by_the_chats_it_held(self):
        # the folder named as the workspace, beside where its panes are now, is gone and once held chats
        os.rename(self.path("old-name"), self.path("new-name"))
        renames, known = self.follow({"w1": "old-name"}, [("w1", self.path("new-name", "src"))], {},
                                     held={self.path("old-name")})
        self.assertEqual(renames, [("w1", "old-name", "new-name")])
        self.assertEqual(known["w1"]["folder"], self.path("new-name"))

    def test_a_name_no_folder_ever_had_stays(self):
        # e.g. app on the folder app-web: never a folder of that name, so a name given by hand
        os.rename(self.path("old-name"), self.path("old-name-com"))
        self.assertEqual(self.follow({"w1": "old-name"}, [("w1", self.path("old-name-com"))], {}), ([], {}))

    def test_a_pane_in_a_subfolder_keeps_the_workspace_on_its_folder(self):
        renames, known = self.follow({"w1": "old-name"}, [("w1", self.path("old-name", "src"))], {})
        self.assertEqual(renames, [])
        self.assertEqual(known["w1"]["folder"], self.path("old-name"))

    def test_a_closed_workspace_is_forgotten(self):
        known = self.known_before_the_rename()
        self.assertEqual(self.follow({}, [], known), ([], {}))


class DeletedFolders(unittest.TestCase):
    """A space whose folder is gone says deleted beside its branch (the theme's Space rows show its $folder token):
    herdr keeps naming a deleted folder as its panes' folder, while a renamed one's panes follow it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.here = os.path.join(self.tmp, "here")
        os.makedirs(self.here)
        self.gone = os.path.join(self.tmp, "gone")

    def test_a_space_is_deleted_when_none_of_its_panes_folders_is_there(self):
        panes = [{"workspace_id": "w1", "cwd": self.gone}, {"workspace_id": "w1", "cwd": self.gone + "/src"},
                 {"workspace_id": "w2", "cwd": self.gone}, {"workspace_id": "w2", "cwd": self.here},
                 {"workspace_id": "w3"}]
        self.assertEqual(spaces.gone(panes), {"w1"})

    def calls_for(self, cwd, tokens):
        calls = []

        def herdr(*args, **kwargs):
            calls.append(args)
            if args[:2] == ("workspace", "list"):
                return {"workspaces": [{"workspace_id": "w1", "label": "app", "tokens": tokens}]}
            if args[:2] == ("pane", "list"):
                return {"panes": [{"pane_id": "w1:p1", "workspace_id": "w1", "cwd": cwd}]}
            return {}
        set_attrs(self, spaces, herdr=herdr)
        set_env(self, HERDR_PLUGIN_STATE_DIR=os.path.join(self.tmp, "state"), HERDR_PLUGIN_EVENT="pane.focused")
        spaces.main()
        return [call for call in calls if call[:2] == ("workspace", "report-metadata")]

    def test_it_is_said_once_and_taken_back_when_the_folder_is_there_again(self):
        self.assertEqual(self.calls_for(self.gone, {}), [("workspace", "report-metadata", "w1", "--source",
                                                          "herdr-fold.spaces", "--token", "folder=deleted")])
        self.assertEqual(self.calls_for(self.gone, {"folder": "deleted"}), [])          # said already
        self.assertEqual(self.calls_for(self.here, {"folder": "deleted"}), [("workspace", "report-metadata", "w1",
                                                                             "--source", "herdr-fold.spaces",
                                                                             "--clear-token", "folder")])
        self.assertEqual(self.calls_for(self.here, {}), [])


class FollowOnFocus(unittest.TestCase):
    """On a pane's focus the plugin renames the workspace and its main tab (the one named as the workspace), never
    another tab, and keeps what it knows in its state folder."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.folder = os.path.join(self.tmp, "old-name")
        os.makedirs(self.folder)
        self.cwd, self.calls = self.folder, []

        def herdr(*args, **kwargs):
            self.calls.append(args)
            if args[:2] == ("workspace", "list"):
                return {"workspaces": [{"workspace_id": "w1", "label": "old-name"}]}
            if args[:2] == ("pane", "list"):
                return {"panes": [{"pane_id": "w1:p1", "workspace_id": "w1", "tab_id": "w1:t1", "cwd": self.cwd}]}
            if args[:2] == ("tab", "list"):
                return {"tabs": [{"tab_id": "w1:t1", "label": "old-name"}, {"tab_id": "w1:t2", "label": "Fix login"}]}
            return {}
        set_attrs(self, spaces, herdr=herdr)
        set_env(self, HERDR_PLUGIN_STATE_DIR=os.path.join(self.tmp, "state"), HERDR_PLUGIN_EVENT="pane.focused")

    def test_the_workspace_and_its_main_tab_take_the_folders_new_name(self):
        spaces.main()
        self.assertFalse(any(call[1] == "rename" for call in self.calls))
        self.cwd = os.path.join(self.tmp, "new-name")
        os.rename(self.folder, self.cwd)
        spaces.main()
        renamed = [call for call in self.calls if call[1] == "rename"]
        self.assertEqual(renamed, [("workspace", "rename", "w1", "new-name"), ("tab", "rename", "w1:t1", "new-name")])

    def test_a_space_herdr_named_after_a_root_or_home_takes_herdr_folds_word_with_its_main_tab(self):
        # herdr names one as its path (/, C:\) or ~; a name given by hand stays
        labels = {"w2": "~", "w1": "/", "w3": "C:\\", "w4": "root", "w5": "lab"}

        def herdr(*args, **kwargs):
            self.calls.append(args)
            if args[:2] == ("workspace", "list"):
                return {"workspaces": [{"workspace_id": ws, "label": label} for ws, label in labels.items()]}
            if args[:2] == ("tab", "list"):
                ws = args[args.index("--workspace") + 1]
                return {"tabs": [{"tab_id": f"{ws}:t1", "label": labels[ws]}, {"tab_id": f"{ws}:t2", "label": "logs"}]}
            return {}
        set_attrs(self, spaces, herdr=herdr, request=lambda method, params: self.calls.append((method,)) or {})
        spaces.main()
        self.assertEqual([call for call in self.calls if call[1:2] == ("rename",)],
                         [("workspace", "rename", "w2", "home"), ("tab", "rename", "w2:t1", "home"),
                          ("workspace", "rename", "w1", "root"), ("tab", "rename", "w1:t1", "root"),
                          ("workspace", "rename", "w3", "C:"), ("tab", "rename", "w3:t1", "C:")])

    def test_the_workspace_in_front_and_the_one_before_are_kept(self):
        focused = ["w1"]

        def herdr(*args, **kwargs):
            if args[:2] == ("workspace", "list"):
                return {"workspaces": [{"workspace_id": ws, "label": ws, "focused": ws == focused[0]}
                                       for ws in ("w1", "w2")]}
            return {}
        set_attrs(self, spaces, herdr=herdr)
        for front in ("w1", "w2", "w2"):                                    # the same one again changes nothing
            focused[0] = front
            spaces.main()
        with open(os.path.join(self.tmp, "state", spaces.FOCUS)) as f:
            self.assertEqual(json.load(f), {"now": "w2", "before": "w1"})

    def test_without_herdrs_state_folder_it_keeps_its_own(self):
        set_env(self, HERDR_PLUGIN_STATE_DIR=None, HOME=self.tmp)
        spaces.main()
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, ".local", "state", "herdr", "plugins",
                                                    "herdr-fold.spaces", spaces.SPACES)))

    def test_the_manifest_runs_it_on_a_panes_focus_on_macos_and_linux(self):
        # Windows does not let a folder in use be renamed
        self.assertEqual(manifest_events("pane.focused"),
                         [('["macos", "linux"]', '["/usr/bin/python3", "spaces.py"]')])


class HomeStays(unittest.TestCase):
    """herdr ends a workspace with its last tab: the home folder's is made again when none is left, on a workspace's
    close and on a pane's focus, so home is always a row in Spaces; and it is moved first whenever it is not, so it is
    always the first row."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(os.path.join(self.home, "work"))
        self.calls, self.spaces, self.panes = [], [], []

        def herdr(*args, **kwargs):
            self.calls.append(args)
            if args[:2] == ("workspace", "list"):
                return {"workspaces": self.spaces} if self.spaces is not None else {}
            if args[:2] == ("pane", "list"):
                return {"panes": self.panes}
            if args[:2] == ("workspace", "create"):
                return {"tab": {"tab_id": "w9:t1"}}
            return {}

        def request(method, params):                    # herdr's socket API: its command line moves no workspace
            self.moves.append((method, params))
            return {}
        self.moves = []
        set_attrs(self, spaces, herdr=herdr, request=request)
        set_env(self, HERDR_PLUGIN_STATE_DIR=os.path.join(self.tmp, "state"), HERDR_PLUGIN_EVENT="workspace.closed",
                HOME=self.home)

    def space(self, ws, label, cwd):
        self.spaces.append({"workspace_id": ws, "label": label})
        self.panes.append({"pane_id": f"{ws}:p1", "workspace_id": ws, "tab_id": f"{ws}:t1", "cwd": cwd})

    def made(self):
        return [call for call in self.calls if call[:2] in (("workspace", "create"), ("tab", "rename"))]

    def test_with_no_workspace_at_home_one_is_made_behind_the_one_in_front_named_as_its_main_tab(self):
        self.space("w1", "work", os.path.join(self.home, "work"))
        spaces.main()
        self.assertEqual(self.made(), [("workspace", "create", "--cwd", self.home, "--label", "home", "--no-focus"),
                                       ("tab", "rename", "w9:t1", "home")])

    def test_the_last_workspace_closed_leaves_home(self):
        spaces.main()
        self.assertEqual(self.made()[0][:4], ("workspace", "create", "--cwd", self.home))

    def test_a_workspace_at_home_is_enough_whatever_its_name(self):
        for label, cwd in (("home", os.path.join(self.home, "work")), ("~", None), ("scratch", self.home)):
            self.spaces, self.panes = [], []
            self.space("w1", label, cwd)
            spaces.main()
        self.assertEqual(self.made(), [])

    def test_only_a_workspaces_first_pane_says_where_it_is(self):
        self.space("w1", "work", os.path.join(self.home, "work"))
        self.panes.append({"pane_id": "w1:p2", "workspace_id": "w1", "tab_id": "w1:t1", "cwd": self.home})
        spaces.main()
        self.assertEqual(len(self.made()), 2)

    def test_herdr_not_answering_makes_nothing(self):
        self.spaces = None
        spaces.main()
        self.assertEqual(self.made(), [])

    def test_a_panes_focus_looks_too(self):
        set_env(self, HERDR_PLUGIN_EVENT="pane.focused")
        self.space("w1", "work", os.path.join(self.home, "work"))
        spaces.main()
        self.assertEqual(self.made()[0], ("workspace", "create", "--cwd", self.home, "--label", "home", "--no-focus"))

    def test_the_manifest_runs_it_on_a_workspaces_close_on_macos_and_linux(self):
        self.assertEqual(manifest_events("workspace.closed"),
                         [('["macos", "linux"]', '["/usr/bin/python3", "spaces.py"]')])

    def test_home_below_another_workspace_goes_first_whenever_the_list_changes(self):
        for event in ("workspace.closed", "workspace.created", "workspace.moved", "workspace.reordered"):
            with self.subTest(event=event):
                set_env(self, HERDR_PLUGIN_EVENT=event)
                self.spaces, self.panes, self.moves = [], [], []
                self.space("w1", "work", os.path.join(self.home, "work"))
                self.space("w2", "home", self.home)
                spaces.main()
                self.assertEqual(self.moves, [("workspace.move", {"workspace_id": "w2", "insert_index": 0})])
                self.assertEqual(self.made(), [])

    def test_home_already_first_is_left_alone(self):
        # its own move comes back as herdr's workspace.moved: nothing more is asked, so it ends there
        set_env(self, HERDR_PLUGIN_EVENT="workspace.moved")
        self.space("w2", "home", self.home)
        self.space("w1", "work", os.path.join(self.home, "work"))
        spaces.main()
        self.assertEqual(self.moves, [])

    def test_home_made_again_goes_first(self):
        self.space("w1", "work", os.path.join(self.home, "work"))
        spaces.main()
        self.assertEqual(self.moves, [("workspace.move", {"workspace_id": "w9", "insert_index": 0})])

    def test_home_made_as_the_only_workspace_is_first_already(self):
        spaces.main()
        self.assertEqual(len(self.made()), 2)
        self.assertEqual(self.moves, [])

    def test_the_workspace_named_home_goes_first_not_another_one_in_the_home_folder(self):
        self.space("w1", "work", os.path.join(self.home, "work"))
        self.space("w2", "scratch", self.home)
        self.space("w3", "home", self.home)
        spaces.main()
        self.assertEqual(self.moves, [("workspace.move", {"workspace_id": "w3", "insert_index": 0})])

    def test_a_panes_focus_puts_home_first_too(self):
        # herdr's start restores the workspaces in their order with no event of the list's
        set_env(self, HERDR_PLUGIN_EVENT="pane.focused")
        self.space("w1", "work", os.path.join(self.home, "work"))
        self.space("w2", "~", self.home)
        spaces.main()
        self.assertEqual(self.moves, [("workspace.move", {"workspace_id": "w2", "insert_index": 0})])
        self.spaces.reverse()
        self.moves.clear()
        spaces.main()
        self.assertEqual(self.moves, [])

    def test_the_manifest_runs_it_when_the_list_of_workspaces_changes(self):
        for event in ("workspace.created", "workspace.moved", "workspace.reordered"):
            self.assertEqual(manifest_events(event),
                             [('["macos", "linux"]', '["/usr/bin/python3", "spaces.py"]')], event)


class LastTabClosed(unittest.TestCase):
    """herdr ends a workspace with its last tab (workspace.closed with the workspace, and tab.closed); closed on
    purpose it sends workspace.closed alone. Only the first is made again: in its place, with its name and folder."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home = os.path.join(self.tmp, "home")
        self.work, self.api = os.path.join(self.home, "work"), os.path.join(self.home, "api")
        os.makedirs(self.work)
        os.makedirs(self.api)
        self.calls, self.moves, self.spaces, self.panes = [], [], [], []

        def herdr(*args, **kwargs):
            self.calls.append(args)
            if args[:2] == ("workspace", "list"):
                return {"workspaces": self.spaces} if self.spaces is not None else {}
            if args[:2] == ("pane", "list"):
                return {"panes": self.panes}
            if args[:2] == ("workspace", "create"):
                self.space("w9", args[5], args[3])      # made last, as herdr does
                return {"tab": {"tab_id": "w9:t1"}}
            return {}

        def request(method, params):
            self.moves.append((method, params))
            return {}
        set_attrs(self, spaces, herdr=herdr, request=request)
        set_attrs(self, spaces.time, sleep=lambda s: None)
        set_env(self, HERDR_PLUGIN_STATE_DIR=os.path.join(self.tmp, "state"), HOME=self.home)
        self.space("w1", "home", self.home)
        self.space("w2", "work", self.work)
        self.space("w3", "api", self.api)
        self.event("workspace.created")                 # the list as it was, seen once

    def space(self, ws, label, cwd):
        self.spaces.append({"workspace_id": ws, "label": label})
        self.panes.append({"pane_id": f"{ws}:p1", "workspace_id": ws, "tab_id": f"{ws}:t1", "cwd": cwd})

    def event(self, name, **data):
        set_env(self, HERDR_PLUGIN_EVENT=name, HERDR_PLUGIN_EVENT_JSON=json.dumps(
            {"event": name.replace(".", "_"), "data": {"type": name.replace(".", "_"), **data}}))
        spaces.main()

    def gone(self, ws):
        """herdr's list without WS, and what herdr says of WS as it closes."""
        number = next(n for n, space in enumerate(self.spaces, 1) if space["workspace_id"] == ws)
        said = {**self.spaces[number - 1], "number": number, "focused": False}
        self.spaces = [space for space in self.spaces if space["workspace_id"] != ws]
        self.panes = [pane for pane in self.panes if pane["workspace_id"] != ws]
        return said

    def workspace_closed(self, said):
        self.event("workspace.closed", workspace_id=said["workspace_id"], workspace=said)

    def tab_closed(self, ws):
        self.event("tab.closed", tab_id=f"{ws}:t1", workspace_id=ws)

    def made(self):
        return [call for call in self.calls if call[:2] in (("workspace", "create"), ("tab", "rename"))]

    def focused(self):
        return [call for call in self.calls if call[:2] == ("workspace", "focus")]

    def test_a_workspace_closed_with_its_last_tab_is_made_again_in_its_place(self):
        said = self.gone("w2")
        self.workspace_closed(said)
        self.tab_closed("w2")
        self.assertEqual(self.made(), [("workspace", "create", "--cwd", self.work, "--label", "work", "--no-focus"),
                                       ("tab", "rename", "w9:t1", "work")])
        self.assertEqual(self.moves, [("workspace.move", {"workspace_id": "w9", "insert_index": 1})])
        self.assertEqual(self.focused(), [])

    def test_herdrs_two_events_come_in_either_order(self):
        said = self.gone("w2")
        self.tab_closed("w2")
        self.assertEqual(self.made(), [])
        self.workspace_closed(said)
        self.assertEqual(self.made()[0], ("workspace", "create", "--cwd", self.work, "--label", "work", "--no-focus"))
        self.assertEqual(len(self.made()), 2)

    def test_it_is_made_once(self):
        said = self.gone("w2")
        self.workspace_closed(said)
        self.tab_closed("w2")
        self.event("workspace.created")                 # herdr's event of the one made
        self.event("workspace.moved")
        self.assertEqual(len(self.made()), 2)

    def test_a_workspace_closed_on_purpose_stays_closed(self):
        self.workspace_closed(self.gone("w2"))
        self.event("workspace.moved")
        self.assertEqual(self.made(), [])

    def test_a_tab_closed_beside_another_one_makes_nothing(self):
        self.event("tab.closed", tab_id="w2:t2", workspace_id="w2")
        self.workspace_closed(self.gone("w2"))          # and closed on purpose later it stays closed
        self.assertEqual(self.made(), [])

    def test_a_workspace_whose_last_pane_moved_away_stays_closed(self):
        # herdr sends both events then too, the workspace's close without the workspace
        self.gone("w2")
        self.event("workspace.closed", workspace_id="w2")
        self.tab_closed("w2")
        self.assertEqual(self.made(), [])

    def test_the_one_in_front_is_in_front_again(self):
        said = {**self.gone("w2"), "focused": True}
        self.workspace_closed(said)
        self.tab_closed("w2")
        self.assertEqual(self.focused(), [("workspace", "focus", "w9")])
        self.assertLess(self.calls.index(("tab", "rename", "w9:t1", "work")),
                        self.calls.index(("workspace", "focus", "w9")))

    def test_the_last_one_in_the_list_needs_no_move(self):
        said = self.gone("w3")
        self.workspace_closed(said)
        self.tab_closed("w3")
        self.assertEqual(self.made()[0][:5], ("workspace", "create", "--cwd", self.api, "--label"))
        self.assertEqual(self.moves, [])

    def test_a_workspace_seen_on_a_panes_focus_only_is_made_again_too(self):
        self.space("w4", "late", self.work)
        self.event("pane.focused", pane_id="w1:p1", workspace_id="w1")
        said = self.gone("w4")
        self.workspace_closed(said)
        self.tab_closed("w4")
        self.assertEqual(self.made()[0], ("workspace", "create", "--cwd", self.work, "--label", "late", "--no-focus"))

    def test_a_workspace_whose_folder_is_gone_stays_closed(self):
        said = self.gone("w2")
        os.rmdir(self.work)
        self.workspace_closed(said)
        self.tab_closed("w2")
        self.assertEqual(self.made(), [])

    def test_home_is_made_again_once_and_in_front_when_it_was(self):
        said = {**self.gone("w1"), "focused": True}
        self.workspace_closed(said)
        self.tab_closed("w1")
        self.assertEqual(self.made(), [("workspace", "create", "--cwd", self.home, "--label", "home", "--no-focus"),
                                       ("tab", "rename", "w9:t1", "home")])
        self.assertEqual(self.focused(), [("workspace", "focus", "w9")])

    def test_the_one_made_again_gets_no_folder_picker(self):
        said = {**self.gone("w2"), "focused": True}
        self.workspace_closed(said)
        self.tab_closed("w2")
        set_attrs(self, spaces, new_workspace=lambda ws: True)          # in front with a single pane
        self.event("tab.created", tab={"tab_id": "w9:t1"})
        self.assertEqual([call for call in self.calls if call[:3] == ("plugin", "pane", "open")], [])
        self.event("tab.created", tab={"tab_id": "w8:t1"})                 # the "new" button's still does
        self.assertEqual(len([call for call in self.calls if call[:3] == ("plugin", "pane", "open")]), 1)

    def test_events_a_minute_apart_are_not_one_close(self):
        said = self.gone("w2")
        self.workspace_closed(said)
        now = spaces.time.time()
        set_attrs(self, spaces.time, time=lambda: now + 61)
        self.tab_closed("w2")
        self.assertEqual(self.made(), [])

    def test_herdr_not_answering_makes_nothing(self):
        said = self.gone("w2")
        self.workspace_closed(said)
        self.spaces = None
        self.tab_closed("w2")
        self.assertEqual(self.made(), [])

    def test_the_manifest_runs_it_on_a_tabs_close_on_macos_and_linux(self):
        self.assertEqual(manifest_events("tab.closed"),
                         [('["macos", "linux"]', '["/usr/bin/python3", "spaces.py"]')])


class RepositoryInside(unittest.TestCase):
    """A workspace whose folder is not a repository but holds one shows that one's name ($repo, after herdr's own
    branch and git status) and under it its branch and how far it is from its upstream ($repo_branch): herdr shows a
    branch only for a folder in a repository, and one thing never gets two signals."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.folder = os.path.join(self.tmp, "archive")
        os.makedirs(self.folder)
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="dev", GIT_AUTHOR_EMAIL="dev@example.com",
                GIT_COMMITTER_NAME="dev", GIT_COMMITTER_EMAIL="dev@example.com", HOME=os.path.join(self.tmp, "home"),
                HERDR_PLUGIN_STATE_DIR=os.path.join(self.tmp, "state"), HERDR_PLUGIN_EVENT="pane.focused")
        self.tokens, self.reports, self.panes, self.commits = {}, [], [], 0

        def herdr(*args, **kwargs):
            if args[:2] == ("workspace", "list"):
                return {"workspaces": [{"workspace_id": "w1", "label": "archive", "focused": True,
                                        "active_tab_id": "w1:t1", "tokens": dict(self.tokens)}]}
            if args[:2] == ("pane", "list"):
                return {"panes": [dict(pane, workspace_id="w1", tab_id="w1:t1") for pane in self.panes]}
            if args[:2] == ("workspace", "report-metadata"):                # as herdr: a patch of the tokens
                self.reports.append(args[2:])
                if "--token" in args:
                    name, value = args[args.index("--token") + 1].split("=", 1)
                    self.tokens[name] = value
                else:
                    self.tokens.pop(args[args.index("--clear-token") + 1], None)
            return {}
        set_attrs(self, spaces, herdr=herdr)

    def git(self, path, *args):
        subprocess.run(["git", "-C", path, *args], check=True, capture_output=True)

    def commit(self, path):
        self.commits += 1                                   # a message of its own: never the same commit twice
        self.git(path, "commit", "-q", "--allow-empty", "-m", f"change {self.commits}")

    def repo(self, name, branch="main", upstream=True):
        """A repository NAME in the workspace's folder with a commit on BRANCH, pushed to a bare remote it tracks."""
        path = os.path.join(self.folder, name)
        os.makedirs(path)
        self.git(path, "init", "-q", "-b", branch)
        self.commit(path)
        if upstream:
            remote = os.path.join(self.tmp, "remotes", name.replace(os.sep, "-") + ".git")
            os.makedirs(remote)
            self.git(remote, "init", "-q", "--bare")
            self.git(path, "remote", "add", "origin", remote)
            self.git(path, "push", "-q", "-u", "origin", branch)
        return path

    def focus(self, *cwds, active=None):
        """The repo tokens' reports of a pane's focus, the workspace's panes in CWDS (the first one's folder is the
        workspace's, as herdr takes it), the one at ACTIVE focused."""
        self.panes = [{"pane_id": f"w1:p{n}", "cwd": cwd, "focused": n == active} for n, cwd in enumerate(cwds)]
        self.reports.clear()
        spaces.main()
        return [report[3:] for report in self.reports if report[-1].split("=")[0] in spaces.REPO_TOKENS]

    def test_a_folder_holding_one_repository_shows_its_name_branch_and_how_far_it_is_from_its_upstream(self):
        app = self.repo("app")
        self.commit(app)
        self.git(app, "push", "-q")
        self.git(app, "reset", "-q", "--hard", "HEAD~1")                    # one to pull
        self.commit(app)                                                    # one to push
        self.assertEqual(self.focus(self.folder), [("--token", "repo=app"), ("--token", "repo_branch=main ↑1 ↓1")])
        self.assertEqual(self.focus(self.folder), [])                       # said already

    def test_a_repository_without_a_stamp_is_read_again_on_each_look(self):
        # past refs_stamp's cap there is no stamp to keep a read by: git is asked each time
        app = self.repo("app", upstream=False)
        set_attrs(self, spaces.git, refs_stamp=lambda root: None)
        self.assertEqual(self.focus(self.folder), [("--token", "repo=app"), ("--token", "repo_branch=main")])
        self.git(app, "checkout", "-q", "-b", "other")
        self.assertEqual(self.focus(self.folder), [("--token", "repo_branch=other")])

    def test_a_repository_without_an_upstream_shows_no_arrows(self):
        self.repo(os.path.join("code", "app"), branch="trunk", upstream=False)      # two folders down
        self.assertEqual(self.focus(self.folder), [("--token", "repo=app"), ("--token", "repo_branch=trunk")])

    def test_a_repository_level_with_its_upstream_shows_no_arrows(self):
        # as herdr's git status: nothing when there is nothing to push or pull
        self.repo("app")
        self.assertEqual(self.focus(self.folder), [("--token", "repo=app"), ("--token", "repo_branch=main")])

    def test_the_repositorys_name_is_not_said_where_it_is_the_spaces_own(self):
        # the space is named archive: its branch stands under its name alone, as a repository's own space's
        self.repo("Archive", branch="trunk", upstream=False)
        self.assertEqual(self.focus(self.folder), [("--token", "repo_branch=trunk")])

    def test_a_detached_head_shows_the_repositorys_name_alone(self):
        # herdr's own row shows no branch for one
        app = self.repo("app", upstream=False)
        self.git(app, "checkout", "-q", "--detach")
        self.assertEqual(self.focus(self.folder), [("--token", "repo=app")])

    def test_the_active_panes_repository_wins_and_stays_when_the_pane_leaves_it(self):
        self.repo("one")
        two = self.repo("two", branch="dev")
        os.makedirs(os.path.join(two, "src"))
        self.assertEqual(self.focus(self.folder), [])                       # two, and no pane was ever in one
        self.assertEqual(self.focus(self.folder, os.path.join(two, "src"), active=1),
                         [("--token", "repo=two"), ("--token", "repo_branch=dev")])
        self.assertEqual(self.focus(self.folder, self.folder, active=1), [])          # the one it was last in
        self.assertEqual(self.tokens, {"repo": "two", "repo_branch": "dev"})

    def test_a_folder_that_is_itself_a_repository_gets_no_token(self):
        # herdr's own branch shows there, for a folder below a repository's top too
        app = self.repo("app")
        vendor = self.repo(os.path.join("app", "vendor"))
        os.makedirs(os.path.join(app, "docs"))
        self.assertEqual(self.focus(app, vendor, active=1), [])
        self.assertEqual(self.focus(os.path.join(app, "docs"), vendor, active=1), [])
        self.assertEqual(self.tokens, {})

    def test_the_tokens_are_cleared_when_they_no_longer_apply(self):
        app = self.repo("app", upstream=False)
        clear = [("--clear-token", "repo"), ("--clear-token", "repo_branch")]
        self.assertEqual(self.focus(self.folder), [("--token", "repo=app"), ("--token", "repo_branch=main")])
        self.assertEqual(self.focus(app), clear)                # the workspace's folder in it: herdr's own shows it
        self.assertEqual(self.focus(self.folder), [("--token", "repo=app"), ("--token", "repo_branch=main")])
        shutil.rmtree(app)
        self.assertEqual(self.focus(self.folder), clear)
        self.assertEqual(self.tokens, {})

    def test_the_home_folder_is_never_searched(self):
        # it holds every repository of the user's (and macOS asks before its private folders are looked into)
        home = os.environ["HOME"]
        subprocess.run(["git", "init", "-q", "-b", "main", os.path.join(home, "app")], check=True, capture_output=True)
        self.assertEqual(self.focus(home), [])

    def test_the_search_is_core_gits_in_its_own_copy(self):
        # one source for both clients (the Herdr app mod's Spaces list runs core/git.py too); its own copy, as
        # herdrlib's sidebar modules bring the sidebar's
        self.assertEqual(spaces.git.__file__,
                         os.path.join(os.path.dirname(os.path.abspath(spaces.__file__)), "git.py"))

    def test_git_runs_only_when_the_repository_changed(self):
        app = self.repo("app")
        calls, real = [], spaces.git.run
        set_attrs(self, spaces.git, run=lambda *args, **kwargs: calls.append(args) or real(*args, **kwargs))
        self.focus(self.folder)
        asked = len(calls)
        self.assertGreater(asked, 0)
        self.focus(self.folder)
        self.assertEqual(len(calls), asked)
        self.commit(app)
        self.assertEqual(self.focus(self.folder), [("--token", "repo_branch=main ↑1")])
        self.assertGreater(len(calls), asked)


if __name__ == "__main__":
    unittest.main()
