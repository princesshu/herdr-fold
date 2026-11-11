"""Tests for the Workspaces plugin (workspaces.py) with fake herdr calls: the new button's workspace is called new while
its folder is chosen, Windows has no folder picker, a workspace whose folder is gone says deleted, a workspace
follows its renamed folder, and a folder holding a repository shows that one's branch."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import set_attrs, set_env

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "plugins", "workspaces"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import workspaces  # noqa: E402


def manifest_events(on):
    """(platforms, command) of each of the manifest's [[events]] on herdr's event ON."""
    with open(os.path.join(os.path.dirname(os.path.abspath(workspaces.__file__)), "herdr-plugin.toml"),
              encoding="utf-8") as f:
        manifest = f.read()
    return re.findall(rf'\[\[events\]\]\non = "{re.escape(on)}"\nplatforms = (\[.*\])\ncommand = (\[.*\])', manifest)


class NewTab(unittest.TestCase):
    """The new button's workspace gets the folder picker; any other new tab, and every one on Windows, gets nothing
    from Workspaces."""

    def setUp(self):
        self.calls = []

        def herdr(*args, **kwargs):
            self.calls.append(args)
            return {}
        set_attrs(self, workspaces, herdr=herdr, new_workspace=lambda ws: True)
        set_attrs(self, workspaces.time, sleep=lambda s: None)
        set_attrs(self, os, name="posix")
        set_env(self, HERDR_PLUGIN_EVENT=None, HERDR_PLUGIN_STATE_DIR=None,
                HERDR_PLUGIN_EVENT_JSON=json.dumps({"data": {"tab": {"tab_id": "w2:t1"}}}))

    def test_the_new_buttons_workspace_is_called_new_while_its_folder_is_chosen(self):
        # herdr names it after the folder it inherits: ~, or the active workspace's own name a second time
        workspaces.main()
        opened = next(n for n, call in enumerate(self.calls) if call[:3] == ("plugin", "pane", "open"))
        self.assertIn(("workspace", "rename", "w2", "new"), self.calls[:opened])
        self.assertEqual(self.calls[opened][:7], ("plugin", "pane", "open", "--plugin", "herdr-fold.workspaces",
                                                  "--entrypoint", "new-workspace"))

    def test_the_picker_is_told_the_workspace_it_was_opened_from(self):
        # Esc goes back there: herdr alone would show a neighbour of the closed one
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state)
        with open(os.path.join(state, workspaces.FOCUS), "w") as f:
            json.dump({"now": "w2", "before": "w1"}, f)                     # the new one already in front
        set_env(self, HERDR_PLUGIN_STATE_DIR=state)
        workspaces.main()
        opened = next(call for call in self.calls if call[:3] == ("plugin", "pane", "open"))
        self.assertIn("HERDR_CAME_FROM=w1", opened)

    def test_any_other_new_tab_gets_nothing_from_it(self):
        # its column is the dock's (the sidebar's panes.py --new-tab)
        set_attrs(self, workspaces, new_workspace=lambda ws: False)
        workspaces.main()
        self.assertEqual(self.calls, [])

    def test_a_new_tab_on_windows_gets_nothing_from_it(self):
        # no folder picker there: its key handling is Unix-only
        os.name = "nt"
        workspaces.main()
        self.assertEqual(self.calls, [])

    def test_the_manifest_runs_it_on_a_new_tab_on_macos_and_linux_only(self):
        self.assertEqual(manifest_events("tab.created"),
                         [('["macos", "linux"]', '["/usr/bin/python3", "workspaces.py"]')])


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
        spaces = [{"workspace_id": ws, "label": label} for ws, label in labels.items()]
        panes = [{"workspace_id": ws, "cwd": cwd} for ws, cwd in cwds]
        return workspaces.follow_folders(spaces, panes, known, held=lambda path: path in held)

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

    def test_a_folder_renamed_before_it_was_followed_is_known_by_the_conversations_it_held(self):
        # the folder named as the workspace, beside where its panes are now, is gone and once held conversations
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
        self.assertEqual(workspaces.gone(panes), {"w1"})

    def calls_for(self, cwd, tokens):
        calls = []

        def herdr(*args, **kwargs):
            calls.append(args)
            if args[:2] == ("workspace", "list"):
                return {"workspaces": [{"workspace_id": "w1", "label": "app", "tokens": tokens}]}
            if args[:2] == ("pane", "list"):
                return {"panes": [{"pane_id": "w1:p1", "workspace_id": "w1", "cwd": cwd}]}
            return {}
        set_attrs(self, workspaces, herdr=herdr)
        set_env(self, HERDR_PLUGIN_STATE_DIR=os.path.join(self.tmp, "state"), HERDR_PLUGIN_EVENT="pane.focused")
        workspaces.main()
        return [call for call in calls if call[:2] == ("workspace", "report-metadata")]

    def test_it_is_said_once_and_taken_back_when_the_folder_is_there_again(self):
        self.assertEqual(self.calls_for(self.gone, {}), [("workspace", "report-metadata", "w1", "--source",
                                                          "herdr-fold.workspaces", "--token", "folder=deleted")])
        self.assertEqual(self.calls_for(self.gone, {"folder": "deleted"}), [])          # said already
        self.assertEqual(self.calls_for(self.here, {"folder": "deleted"}), [("workspace", "report-metadata", "w1",
                                                                             "--source", "herdr-fold.workspaces",
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
        set_attrs(self, workspaces, herdr=herdr)
        set_env(self, HERDR_PLUGIN_STATE_DIR=os.path.join(self.tmp, "state"), HERDR_PLUGIN_EVENT="pane.focused")

    def test_the_workspace_and_its_main_tab_take_the_folders_new_name(self):
        workspaces.main()
        self.assertFalse(any(call[1] == "rename" for call in self.calls))
        self.cwd = os.path.join(self.tmp, "new-name")
        os.rename(self.folder, self.cwd)
        workspaces.main()
        renamed = [call for call in self.calls if call[1] == "rename"]
        self.assertEqual(renamed, [("workspace", "rename", "w1", "new-name"), ("tab", "rename", "w1:t1", "new-name")])

    def test_the_workspace_in_front_and_the_one_before_are_kept(self):
        focused = ["w1"]

        def herdr(*args, **kwargs):
            if args[:2] == ("workspace", "list"):
                return {"workspaces": [{"workspace_id": ws, "label": ws, "focused": ws == focused[0]}
                                       for ws in ("w1", "w2")]}
            return {}
        set_attrs(self, workspaces, herdr=herdr)
        for front in ("w1", "w2", "w2"):                                    # the same one again changes nothing
            focused[0] = front
            workspaces.main()
        with open(os.path.join(self.tmp, "state", workspaces.FOCUS)) as f:
            self.assertEqual(json.load(f), {"now": "w2", "before": "w1"})

    def test_without_herdrs_state_folder_it_keeps_its_own(self):
        set_env(self, HERDR_PLUGIN_STATE_DIR=None, HOME=self.tmp)
        workspaces.main()
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, ".local", "state", "herdr", "plugins",
                                                    "herdr-fold.workspaces", workspaces.SPACES)))

    def test_the_manifest_runs_it_on_a_panes_focus_on_macos_and_linux(self):
        # Windows does not let a folder in use be renamed
        self.assertEqual(manifest_events("pane.focused"),
                         [('["macos", "linux"]', '["/usr/bin/python3", "workspaces.py"]')])


class RepositoryInside(unittest.TestCase):
    """A workspace whose folder is not a repository but holds one shows that one's branch and how far it is from its
    upstream ($repo, after herdr's own branch and git status): herdr shows a branch only for a folder in a repository,
    and one thing never gets two signals."""

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
        set_attrs(self, workspaces, herdr=herdr)

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
        """The repo token reports of a pane's focus, the workspace's panes in CWDS (the first one's folder is the
        workspace's, as herdr takes it), the one at ACTIVE focused."""
        self.panes = [{"pane_id": f"w1:p{n}", "cwd": cwd, "focused": n == active} for n, cwd in enumerate(cwds)]
        self.reports.clear()
        workspaces.main()
        return [report[3:] for report in self.reports if report[-1] == "repo" or report[-1].startswith("repo=")]

    def test_a_folder_holding_one_repository_shows_its_branch_and_how_far_it_is_from_its_upstream(self):
        app = self.repo("app")
        self.commit(app)
        self.git(app, "push", "-q")
        self.git(app, "reset", "-q", "--hard", "HEAD~1")                    # one to pull
        self.commit(app)                                                    # one to push
        self.assertEqual(self.focus(self.folder), [("--token", "repo=main ↑1 ↓1")])
        self.assertEqual(self.focus(self.folder), [])                       # said already

    def test_a_repository_without_a_stamp_is_read_again_on_each_look(self):
        # past refs_stamp's cap there is no stamp to keep a read by: git is asked each time
        app = self.repo("app", upstream=False)
        set_attrs(self, workspaces.git, refs_stamp=lambda root: None)
        self.assertEqual(self.focus(self.folder), [("--token", "repo=main")])
        self.git(app, "checkout", "-q", "-b", "other")
        self.assertEqual(self.focus(self.folder), [("--token", "repo=other")])

    def test_a_repository_without_an_upstream_shows_its_branch_alone(self):
        self.repo(os.path.join("code", "app"), branch="trunk", upstream=False)      # two folders down
        self.assertEqual(self.focus(self.folder), [("--token", "repo=trunk")])

    def test_a_repository_level_with_its_upstream_shows_its_branch_alone(self):
        # as herdr's git status: nothing when there is nothing to push or pull
        self.repo("app")
        self.assertEqual(self.focus(self.folder), [("--token", "repo=main")])

    def test_the_active_panes_repository_wins_and_stays_when_the_pane_leaves_it(self):
        self.repo("one")
        two = self.repo("two", branch="dev")
        os.makedirs(os.path.join(two, "src"))
        self.assertEqual(self.focus(self.folder), [])                       # two, and no pane was ever in one
        self.assertEqual(self.focus(self.folder, os.path.join(two, "src"), active=1), [("--token", "repo=dev")])
        self.assertEqual(self.focus(self.folder, self.folder, active=1), [])          # the one it was last in
        self.assertEqual(self.tokens, {"repo": "dev"})

    def test_a_folder_that_is_itself_a_repository_gets_no_token(self):
        # herdr's own branch shows there, for a folder below a repository's top too
        app = self.repo("app")
        vendor = self.repo(os.path.join("app", "vendor"))
        os.makedirs(os.path.join(app, "docs"))
        self.assertEqual(self.focus(app, vendor, active=1), [])
        self.assertEqual(self.focus(os.path.join(app, "docs"), vendor, active=1), [])
        self.assertEqual(self.tokens, {})

    def test_the_token_is_cleared_when_it_no_longer_applies(self):
        app = self.repo("app", upstream=False)
        clear = [("--clear-token", "repo")]
        self.assertEqual(self.focus(self.folder), [("--token", "repo=main")])
        self.assertEqual(self.focus(app), clear)                # the workspace's folder in it: herdr's own shows it
        self.assertEqual(self.focus(self.folder), [("--token", "repo=main")])
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
        self.assertEqual(workspaces.git.__file__,
                         os.path.join(os.path.dirname(os.path.abspath(workspaces.__file__)), "git.py"))

    def test_git_runs_only_when_the_repository_changed(self):
        app = self.repo("app")
        calls, real = [], workspaces.git.run
        set_attrs(self, workspaces.git, run=lambda *args, **kwargs: calls.append(args) or real(*args, **kwargs))
        self.focus(self.folder)
        asked = len(calls)
        self.assertGreater(asked, 0)
        self.focus(self.folder)
        self.assertEqual(len(calls), asked)
        self.commit(app)
        self.assertEqual(self.focus(self.folder), [("--token", "repo=main ↑1")])
        self.assertGreater(len(calls), asked)


if __name__ == "__main__":
    unittest.main()
