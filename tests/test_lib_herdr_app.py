"""Tests for lib/herdr_app.py, which sets up herdr-fold in the Herdr app for install.sh: the mod, the layout and the
keys go into the app's home and come off again, and nothing of the person's own is changed."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from support import PACKAGE, set_env

sys.path.insert(0, os.path.join(PACKAGE, "lib"))
import herdr_app  # noqa: E402

MOD = os.path.join(PACKAGE, "app", "mods", "herdr-fold")


def read(path):
    with open(path, "rb") as f:
        return f.read()


def keys(home):
    with open(os.path.join(home, "keys.json"), encoding="utf-8") as f:
        return json.load(f)


def shared(home):
    with open(os.path.join(home, "shared.json"), encoding="utf-8") as f:
        return json.load(f)


class Install(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.home, self.state = os.path.join(tmp, "app"), os.path.join(tmp, "state")
        os.makedirs(self.home)

    def write(self, rel, text):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def test_install_puts_the_mod_the_layout_and_the_keys(self):
        self.assertEqual(herdr_app.install(PACKAGE, self.home, self.state), 0)
        for root, _dirs, files in os.walk(MOD):
            for rel in (os.path.relpath(os.path.join(root, name), MOD) for name in files):
                self.assertEqual(read(os.path.join(self.home, "mods", "herdr-fold", rel)), read(os.path.join(MOD, rel)))
        themes = os.path.join(PACKAGE, "app", "themes")
        for rel in [("layouts", "herdr-fold.json")] + [("themes", name) for name in os.listdir(themes)]:
            self.assertEqual(read(os.path.join(self.home, *rel)), read(os.path.join(PACKAGE, "app", *rel)))
        with open(os.path.join(PACKAGE, "app", "keys.json"), encoding="utf-8") as f:
            self.assertEqual(keys(self.home), json.load(f))

    def layout_theme(self):
        with open(os.path.join(self.home, "layouts", "herdr-fold.json"), encoding="utf-8") as f:
            return json.load(f)["theme"]

    def test_the_layout_takes_the_theme_chosen(self):
        self.assertEqual(herdr_app.install(PACKAGE, self.home, self.state, theme="nord"), 0)
        self.assertEqual(self.layout_theme(), "herdr-fold-nord")
        herdr_app.install(PACKAGE, self.home, self.state, theme="9")                 # by its number, as asked
        self.assertEqual(self.layout_theme(), "herdr-fold-dracula")

    def test_an_update_keeps_the_theme_in_the_layout(self):
        herdr_app.install(PACKAGE, self.home, self.state, theme="nord")
        herdr_app.install(PACKAGE, self.home, self.state)
        self.assertEqual(self.layout_theme(), "herdr-fold-nord")

    def test_an_earlier_copy_is_replaced_whole(self):
        self.write("mods/herdr-fold/mod.json", '{ "place": "none", "title": "herdr-fold" }\n')
        self.write("mods/herdr-fold/old.js", "// an earlier version's\n")
        herdr_app.install(PACKAGE, self.home, self.state)
        self.assertEqual(sorted(os.listdir(os.path.join(self.home, "mods", "herdr-fold"))), sorted(os.listdir(MOD)))

    def test_a_folder_of_that_name_not_herdr_folds_stays(self):
        self.write("mods/herdr-fold/main.js", "// someone's own\n")
        out = subprocess.run([sys.executable, "-I", herdr_app.__file__, "install", PACKAGE], capture_output=True,
                             env={"HERDR_APP_HOME": self.home, "HOME": self.home, "PATH": "/usr/bin:/bin"})
        self.assertEqual(out.returncode, 4)
        self.assertEqual(os.listdir(os.path.join(self.home, "mods", "herdr-fold")), ["main.js"])
        self.assertFalse(os.path.exists(os.path.join(self.home, "layouts", "herdr-fold.json")))

    def test_the_persons_other_keys_stay(self):
        self.write("keys.json", json.dumps({"global": {"cmd-t": "tab.new"}, "layout:herdr-fold": {"cmd-k": "x.y"}}))
        herdr_app.install(PACKAGE, self.home, self.state)
        installed = keys(self.home)
        self.assertEqual(installed["global"], {"cmd-t": "tab.new"})
        self.assertEqual(installed["layout:herdr-fold"]["cmd-k"], "x.y")
        self.assertEqual(installed["layout:herdr-fold"]["cmd-shift-g"], "herdr-fold.changes")
        herdr_app.uninstall(PACKAGE, self.home, self.state)
        self.assertEqual(keys(self.home), {"global": {"cmd-t": "tab.new"}, "layout:herdr-fold": {"cmd-k": "x.y"}})

    def test_an_emptied_section_goes(self):
        herdr_app.install(PACKAGE, self.home, self.state)
        herdr_app.uninstall(PACKAGE, self.home, self.state)
        self.assertEqual(keys(self.home), {})

    def test_unreadable_keys_are_left_alone(self):
        self.write("keys.json", "{")
        self.assertEqual(herdr_app.install(PACKAGE, self.home, self.state), 3)
        self.assertEqual(read(os.path.join(self.home, "keys.json")), b"{")
        self.assertTrue(os.path.isfile(os.path.join(self.home, "mods", "herdr-fold", "main.js")))
        self.assertTrue(os.path.isfile(os.path.join(self.home, "layouts", "herdr-fold.json")))

    def test_uninstall_takes_off_what_install_put(self):
        self.write("mods/other/main.js", "// another mod\n")
        self.write("layouts/mine.json", "{}\n")
        self.write("themes/mine.json", "{}\n")
        herdr_app.install(PACKAGE, self.home, self.state)
        self.write("herdr-fold-pictures/0123456789ab.png", "a picture the preview tab drew")
        self.write("data/herdr-fold/store.json", "{}\n")                    # the app's data of each mod it ran
        self.write("data/other/store.json", "{}\n")
        self.write("layouts/.state/herdr-fold.json", "{}\n")                # the app's state of each layout shown
        self.write("layouts/.state/mine.json", "{}\n")
        herdr_app.uninstall(PACKAGE, self.home, self.state)
        self.assertEqual(sorted(os.listdir(os.path.join(self.home, "mods"))), ["other"])
        self.assertFalse(os.path.exists(os.path.join(self.home, "herdr-fold-pictures")))
        self.assertEqual(os.listdir(os.path.join(self.home, "data")), ["other"])
        self.assertEqual(os.listdir(os.path.join(self.home, "layouts", ".state")), ["mine.json"])
        self.assertEqual(sorted(os.listdir(os.path.join(self.home, "layouts"))), [".state", "mine.json"])
        self.assertEqual(os.listdir(os.path.join(self.home, "themes")), ["mine.json"])

    def test_uninstall_takes_the_apps_storage_of_the_mod_off(self):
        set_env(self, HOME=self.home)
        herdr_app.install(PACKAGE, self.home, self.state)
        mod = herdr_app.storage(os.path.join(self.home, "mods", "herdr-fold"))
        other = os.path.join(os.path.dirname(mod), "other-0123456789abcdef")
        for made in (mod, other):
            os.makedirs(made)
        herdr_app.uninstall(PACKAGE, self.home, self.state)
        self.assertEqual(os.listdir(os.path.dirname(mod)), ["other-0123456789abcdef"])

    def test_the_storage_is_named_by_the_real_path(self):
        # test_app.py checks the name against the folder the app itself makes
        set_env(self, HOME=self.home)
        linked = os.path.join(self.home, "linked")
        os.symlink(self.home, linked)
        named = herdr_app.storage(os.path.join(self.home, "mod"))
        self.assertEqual(herdr_app.storage(os.path.join(linked, "mod")), named)
        self.assertEqual(os.path.dirname(named),
                         os.path.join(self.home, "Library", "Application Support", "gpui-shell", "apps"))
        self.assertRegex(os.path.basename(named), r"^mod-[0-9a-f]{16}$")

    def test_the_apps_own_shared_values_stay_as_they_are(self):
        text = json.dumps({"workspace.panels": []})
        self.write("shared.json", text)
        herdr_app.uninstall(PACKAGE, self.home, self.state)
        self.assertEqual(read(os.path.join(self.home, "shared.json")), text.encode())

    def test_a_theme_an_earlier_version_brought_goes(self):
        self.write("themes/herdr-fold-gone.json", "{}\n")
        self.write("themes/mine.json", "{}\n")
        os.makedirs(self.state)
        with open(os.path.join(self.state, "app-themes.json"), "w", encoding="utf-8") as f:
            json.dump(["themes/herdr-fold-gone.json"], f)                    # as that version recorded it
        herdr_app.install(PACKAGE, self.home, self.state)
        self.assertEqual(sorted(os.listdir(os.path.join(self.home, "themes"))),
                         sorted(os.listdir(os.path.join(PACKAGE, "app", "themes")) + ["mine.json"]))
        herdr_app.uninstall(PACKAGE, self.home, self.state)
        self.assertEqual(os.listdir(os.path.join(self.home, "themes")), ["mine.json"])

    def test_a_persons_own_theme_named_like_herdr_folds_stays(self):
        self.write("themes/herdr-fold-nord-mine.json", "{}\n")                # a copy made to change it
        herdr_app.install(PACKAGE, self.home, self.state)
        herdr_app.install(PACKAGE, self.home, self.state)                     # an update
        self.assertTrue(os.path.isfile(os.path.join(self.home, "themes", "herdr-fold-nord-mine.json")))
        herdr_app.uninstall(PACKAGE, self.home, self.state)
        self.assertEqual(os.listdir(os.path.join(self.home, "themes")), ["herdr-fold-nord-mine.json"])

    def test_install_records_the_keys_it_put(self):
        herdr_app.install(PACKAGE, self.home, self.state)
        with open(os.path.join(self.state, "app-keys.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), keys(self.home))
        herdr_app.uninstall(PACKAGE, self.home, self.state)
        self.assertFalse(os.path.exists(os.path.join(self.state, "app-keys.json")))

    def test_a_key_an_earlier_version_put_goes_one_rebound_since_stays(self):
        earlier = {"layout:herdr-fold": {"cmd-shift-x": "herdr-fold.gone", "cmd-shift-y": "herdr-fold.gone-too"},
                   "global": {"cmd-shift-z": "herdr-fold.moved"}}
        os.makedirs(self.state)
        with open(os.path.join(self.state, "app-keys.json"), "w", encoding="utf-8") as f:
            json.dump(earlier, f)
        self.write("keys.json", json.dumps({**earlier, "layout:herdr-fold": {
            "cmd-shift-x": "herdr-fold.gone", "cmd-shift-y": "x.mine", "cmd-k": "herdr-fold.issues"}}))
        herdr_app.install(PACKAGE, self.home, self.state)
        installed = keys(self.home)
        self.assertNotIn("global", installed)
        self.assertNotIn("cmd-shift-x", installed["layout:herdr-fold"])
        self.assertEqual(installed["layout:herdr-fold"]["cmd-shift-y"], "x.mine")
        self.assertEqual(installed["layout:herdr-fold"]["cmd-k"], "herdr-fold.issues")

    def test_uninstall_takes_an_earlier_versions_keys_off(self):
        herdr_app.install(PACKAGE, self.home, self.state)
        earlier = {"layout:herdr-fold": {"cmd-shift-x": "herdr-fold.gone"}}
        with open(os.path.join(self.state, "app-keys.json"), "w", encoding="utf-8") as f:
            json.dump(earlier, f)
        self.write("keys.json", json.dumps(herdr_app.merge_keys(keys(self.home), earlier)))
        herdr_app.uninstall(PACKAGE, self.home, self.state)
        self.assertEqual(keys(self.home), {})

    def test_shared_values_the_mod_no_longer_names_go(self):
        self.write("shared.json", json.dumps({"herdr-fold.graph_folded": True, "herdr-fold.view": "changes",
                                              "herdr-fold.panel-width": 420, "sidebar.width": 268}))
        herdr_app.install(PACKAGE, self.home, self.state)
        self.assertEqual(shared(self.home), {"herdr-fold.panel-width": 420, "sidebar.width": 268})

    def test_uninstall_takes_herdr_folds_shared_values_off(self):
        self.write("shared.json", json.dumps({"herdr-fold.view": "changes", "herdr-fold.waits": {},
                                              "frame.welcomed": True}))
        herdr_app.uninstall(PACKAGE, self.home, self.state)
        self.assertEqual(shared(self.home), {"frame.welcomed": True})

    def test_a_running_apps_shared_values_are_left_to_it(self):
        """A running app holds them and writes them all back on its next change: a file written meanwhile is lost."""
        text = json.dumps({"herdr-fold.graph_folded": True, "herdr-fold.view": "changes"})
        self.write("shared.json", text)
        herdr_app.install(PACKAGE, self.home, self.state, app_running=True)
        herdr_app.uninstall(PACKAGE, self.home, self.state, app_running=True)
        self.assertEqual(read(os.path.join(self.home, "shared.json")), text.encode())

    def old_state(self):
        """The app's state of the layout as the one panel stack left it: Changes chosen in it, the panel dragged."""
        state = {"nodes": {"fold-panel-body": {"active": "changes"}, "fold-panel": {"size": {"px": 420}},
                           "fold-terminals": {"active": "fold-terminal-t1"}}, "file": {"id": "root"}}
        self.write("layouts/.state/herdr-fold.json", json.dumps(state))
        return state

    def test_an_update_prunes_the_apps_state_of_the_layout(self):
        self.old_state()
        herdr_app.install(PACKAGE, self.home, self.state)
        with open(os.path.join(self.home, "layouts", ".state", "herdr-fold.json"), encoding="utf-8") as f:
            self.assertEqual(sorted(json.load(f)["nodes"]), ["fold-panel", "fold-terminals"])

    def test_an_update_brings_a_group_saved_folded_back_at_the_folded_height_of_now(self):
        # an earlier version folded a group to 34 px; this one's folded group is 50 (its head 36, PAD 12, its frame)
        self.write("layouts/.state/herdr-fold.json", json.dumps({"nodes": {"fold-project": {"size": {"px": 34}},
                                                                           "fold-project-body": {"hidden": True}}}))
        herdr_app.install(PACKAGE, self.home, self.state)
        with open(os.path.join(self.home, "layouts", ".state", "herdr-fold.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["nodes"]["fold-project"], {"size": {"px": 50}})

    def test_a_running_apps_state_of_the_layout_is_left_to_it(self):
        text = json.dumps(self.old_state())
        herdr_app.install(PACKAGE, self.home, self.state, app_running=True)
        self.assertEqual(read(os.path.join(self.home, "layouts", ".state", "herdr-fold.json")), text.encode())

    def test_a_folder_named_like_a_theme_is_left_alone(self):
        os.makedirs(os.path.join(self.home, "themes", "herdr-fold-mine.json"))
        self.assertEqual(herdr_app.install(PACKAGE, self.home, self.state), 0)
        herdr_app.uninstall(PACKAGE, self.home, self.state)
        self.assertEqual(os.listdir(os.path.join(self.home, "themes")), ["herdr-fold-mine.json"])

    def test_the_record_is_its_owners_only(self):
        herdr_app.install(PACKAGE, self.home, self.state)
        self.assertEqual(os.stat(self.state).st_mode & 0o777, 0o700)

    def test_the_app_home_follows_herdr_app_home(self):
        set_env(self, HERDR_APP_HOME=self.home)
        self.assertEqual(herdr_app.app_home(), self.home)
        out = subprocess.run([sys.executable, "-I", herdr_app.__file__, "install", PACKAGE], capture_output=True,
                             env={"HERDR_APP_HOME": self.home, "HOME": self.home, "PATH": "/usr/bin:/bin"})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.home, "mods", "herdr-fold", "main.js")))


def with_tab_terminals(home, *addresses):
    """The layout in HOME with terminals in its fold-terminals stack, as the mod puts the tabs' there."""
    path = os.path.join(home, "layouts", "herdr-fold.json")
    with open(path, encoding="utf-8") as f:
        layout = json.load(f)
    stack, = [n for n in herdr_app.nodes(layout) if n.get("id") == "fold-terminals"]
    stack["children"] += [{"id": f"fold-terminal-tb{i}", "type": "block", "content": {"terminal": address}}
                          for i, address in enumerate(addresses)]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(layout, f)


class State(unittest.TestCase):
    def test_the_layout_state_loses_the_nodes_the_layout_has_no_more(self):
        """The old layout's state (its one panel stack on Search, Changes' block): the stack gone, so the new groups'
        stacks, which it never had, open on their own tabs; what is still there keeps its clicks."""
        with open(os.path.join(PACKAGE, "app", "layouts", "herdr-fold.json"), encoding="utf-8") as f:
            layout = json.load(f)
        old = {"nodes": {"fold-panel-body": {"active": "search"}, "changes": {"hidden": False},
                         "fold-panel": {"size": {"px": 420}}, "gone": {"hidden": True}}, "file": {"id": "root"}}
        pruned = herdr_app.prune_state(old, layout)
        self.assertEqual(pruned, {"nodes": {"changes": {"hidden": False}, "fold-panel": {"size": {"px": 420}}},
                                  "file": {"id": "root"}})
        self.assertFalse({"fold-project-body", "fold-work-body"} & set(pruned["nodes"]))
        self.assertEqual(herdr_app.prune_state(["not", "a", "state"], layout), ["not", "a", "state"])

    def test_a_group_saved_folded_takes_the_folded_height_of_now(self):
        """A group folded is its head, PAD under it and its frame (logic.js's FOLDED_GROUP): one saved folded at another
        height takes that one; one saved open, or folded with no size of its own, keeps what it had."""
        with open(os.path.join(PACKAGE, "app", "layouts", "herdr-fold.json"), encoding="utf-8") as f:
            layout = json.load(f)
        old = {"nodes": {"fold-project": {"size": {"px": 34}}, "fold-project-body": {"hidden": True},
                         "fold-work": {"size": {"px": 300}}, "fold-work-body": {"active": "issues"}}}
        pruned = herdr_app.prune_state(old, layout, 12)["nodes"]
        self.assertEqual([pruned["fold-project"], pruned["fold-work"]], [{"size": {"px": 50}}, {"size": {"px": 300}}])
        folded = {"nodes": {"fold-work-body": {"hidden": True}}}
        self.assertEqual(herdr_app.prune_state(folded, layout, 12), folded)
        self.assertEqual(herdr_app.prune_state(old, layout)["nodes"]["fold-project"], {"size": {"px": 34}})  # no PAD
        self.assertEqual(herdr_app.card_pad(os.path.join(PACKAGE, "app")), 12)       # logic.js's


class Terminals(unittest.TestCase):
    """The terminals the mod started for tabs, on this computer and on other machines, end with herdr-fold."""

    def test_the_tabs_terminals_the_layout_names_end(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        herdr_app.install(PACKAGE, home, os.path.join(home, "state"))
        self.assertEqual(herdr_app.tab_terminals(home), [])
        with_tab_terminals(home, "t2", "lab/t5")
        self.assertEqual(herdr_app.tab_terminals(home), ["t2", "lab/t5"])
        hc, log = os.path.join(home, "herdr-core"), os.path.join(home, "killed")
        with open(hc, "w") as f:
            f.write(f'#!/bin/sh\necho "$*" >> {log}\n')
        os.chmod(hc, 0o755)
        herdr_app.end_terminals(hc, home)
        self.assertEqual(read(log), b"kill -- t2\nkill -- lab/t5\n")

    def test_no_layout_no_terminals(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        self.assertEqual(herdr_app.tab_terminals(home), [])


class Running(unittest.TestCase):
    def test_an_app_that_does_not_answer_is_taken_for_running_and_not_closed(self):
        """It may still hold herdr-fold's values and write them back: they are left to it."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        app = os.path.join(tmp, "herdr-app")
        with open(app, "w") as f:
            f.write("#!/bin/sh\nexec sleep 5\n")
        os.chmod(app, 0o755)
        with mock.patch.object(herdr_app, "ANSWER", 0.2), mock.patch.object(herdr_app, "CLOSING", 1):
            self.assertTrue(herdr_app.running(app))
            self.assertFalse(herdr_app.close(app))


class Found(unittest.TestCase):
    def test_the_app_is_found_by_its_command_line(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        binary = os.path.join(home, ".local", "bin", "herdr-app")
        os.makedirs(os.path.dirname(binary))
        env = {"HOME": home, "PATH": "/usr/bin:/bin"}
        out = subprocess.run([sys.executable, "-I", herdr_app.__file__, "cli"], capture_output=True, text=True, env=env)
        self.assertEqual((out.returncode, out.stdout), (1, ""))
        with open(binary, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(binary, 0o755)
        out = subprocess.run([sys.executable, "-I", herdr_app.__file__, "cli"], capture_output=True, text=True, env=env)
        self.assertEqual((out.returncode, out.stdout.strip()), (0, binary))


if __name__ == "__main__":
    unittest.main()
