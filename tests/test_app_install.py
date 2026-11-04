"""Tests for lib/herdr_app.py, which sets up herdr-fold in the Herdr app for install.sh: the mod, the layout and the
keys go into the app's home and come off again, and nothing of the person's own is changed."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

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


class Install(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)

    def write(self, rel, text):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def test_install_puts_the_mod_the_layout_and_the_keys(self):
        self.assertEqual(herdr_app.install(PACKAGE, self.home), 0)
        for name in os.listdir(MOD):
            self.assertEqual(read(os.path.join(self.home, "mods", "herdr-fold", name)), read(os.path.join(MOD, name)))
        for rel in (("layouts", "herdr-fold.json"), ("themes", "herdr-fold.json")):     # the layout in its own theme
            self.assertEqual(read(os.path.join(self.home, *rel)), read(os.path.join(PACKAGE, "app", *rel)))
        with open(os.path.join(PACKAGE, "app", "keys.json"), encoding="utf-8") as f:
            self.assertEqual(keys(self.home), json.load(f))

    def test_an_earlier_copy_is_replaced_whole(self):
        self.write("mods/herdr-fold/mod.json", '{ "place": "none", "title": "herdr-fold" }\n')
        self.write("mods/herdr-fold/old.js", "// an earlier version's\n")
        herdr_app.install(PACKAGE, self.home)
        self.assertEqual(sorted(os.listdir(os.path.join(self.home, "mods", "herdr-fold"))), sorted(os.listdir(MOD)))

    def test_a_folder_of_that_name_not_herdr_folds_stays(self):
        self.write("mods/herdr-fold/main.js", "// someone's own\n")
        out = subprocess.run([sys.executable, "-I", herdr_app.__file__, "install", PACKAGE], capture_output=True,
                             env={"HERDR_APP_HOME": self.home, "PATH": "/usr/bin:/bin"})
        self.assertEqual(out.returncode, 4)
        self.assertEqual(os.listdir(os.path.join(self.home, "mods", "herdr-fold")), ["main.js"])
        self.assertFalse(os.path.exists(os.path.join(self.home, "layouts", "herdr-fold.json")))

    def test_the_persons_other_keys_stay(self):
        self.write("keys.json", json.dumps({"global": {"cmd-t": "tab.new"}, "layout:herdr-fold": {"cmd-k": "x.y"}}))
        herdr_app.install(PACKAGE, self.home)
        installed = keys(self.home)
        self.assertEqual(installed["global"], {"cmd-t": "tab.new"})
        self.assertEqual(installed["layout:herdr-fold"]["cmd-k"], "x.y")
        self.assertEqual(installed["layout:herdr-fold"]["cmd-shift-g"], "mod.open:herdr-fold")
        herdr_app.uninstall(PACKAGE, self.home)
        self.assertEqual(keys(self.home), {"global": {"cmd-t": "tab.new"}, "layout:herdr-fold": {"cmd-k": "x.y"}})

    def test_an_emptied_section_goes(self):
        herdr_app.install(PACKAGE, self.home)
        herdr_app.uninstall(PACKAGE, self.home)
        self.assertEqual(keys(self.home), {})

    def test_unreadable_keys_are_left_alone(self):
        self.write("keys.json", "{")
        self.assertEqual(herdr_app.install(PACKAGE, self.home), 3)
        self.assertEqual(read(os.path.join(self.home, "keys.json")), b"{")
        self.assertTrue(os.path.isfile(os.path.join(self.home, "mods", "herdr-fold", "main.js")))
        self.assertTrue(os.path.isfile(os.path.join(self.home, "layouts", "herdr-fold.json")))

    def test_uninstall_takes_off_what_install_put(self):
        self.write("mods/other/main.js", "// another mod\n")
        self.write("layouts/mine.json", "{}\n")
        self.write("themes/mine.json", "{}\n")
        herdr_app.install(PACKAGE, self.home)
        herdr_app.uninstall(PACKAGE, self.home)
        self.assertEqual(sorted(os.listdir(os.path.join(self.home, "mods"))), ["other"])
        self.assertEqual(os.listdir(os.path.join(self.home, "layouts")), ["mine.json"])
        self.assertEqual(os.listdir(os.path.join(self.home, "themes")), ["mine.json"])

    def test_the_app_home_follows_herdr_app_home(self):
        set_env(self, HERDR_APP_HOME=self.home)
        self.assertEqual(herdr_app.app_home(), self.home)
        out = subprocess.run([sys.executable, "-I", herdr_app.__file__, "install", PACKAGE], capture_output=True,
                             env={"HERDR_APP_HOME": self.home, "PATH": "/usr/bin:/bin"})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.home, "mods", "herdr-fold", "main.js")))


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
