"""Tests for herdr-fold's Herdr app mod (app/): its logic under Node, the mod as the app itself loads it (herdr-app
check, on a copy), and the folder the app and its marketplace expect. Without Node or the app a part is skipped, as the
PowerShell tests are without PowerShell."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from support import PACKAGE

MOD = os.path.join(PACKAGE, "app", "mods", "herdr-fold")
HERDR_APP = shutil.which("herdr-app") or os.path.expanduser("~/.local/bin/herdr-app")


class Logic(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "no Node")
    def test_the_mods_logic_passes_its_node_tests(self):
        out = subprocess.run(["node", "--test", os.path.join("app", "tests")], cwd=PACKAGE, capture_output=True,
                             text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stdout[-2000:] + out.stderr[-2000:])


class Shape(unittest.TestCase):
    def test_the_folder_holds_what_the_app_loads(self):
        with open(os.path.join(MOD, "mod.json"), encoding="utf-8") as f:
            self.assertIn(json.load(f).get("place"), ("right", "left", "top", "bottom", "none"))
        self.assertTrue(os.path.isfile(os.path.join(MOD, "main.js")))

    def test_every_script_has_its_types_checked(self):
        # the app loads JavaScript only; // @ts-check has an editor (and tsc) check it against the app's own types
        for root, _dirs, files in os.walk(os.path.join(PACKAGE, "app")):
            for name in files:
                if name.endswith(".js"):
                    with self.subTest(name), open(os.path.join(root, name), encoding="utf-8") as f:
                        self.assertEqual(f.readline().strip(), "// @ts-check")


class App(unittest.TestCase):
    @unittest.skipUnless(os.access(HERDR_APP, os.X_OK), "no Herdr app")
    def test_the_app_loads_the_mod(self):
        # on a copy in a home of its own: the check writes its editor files beside the mod, and nothing of the user's
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        copy = os.path.join(home, "mods", "herdr-fold")
        shutil.copytree(MOD, copy)
        env = {"HOME": home, "PATH": "/usr/bin:/bin", "HERDR_APP_HOME": home, "HERDR_TELEMETRY": "0",
               "DO_NOT_TRACK": "1"}
        out = subprocess.run([HERDR_APP, "check", copy], env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
