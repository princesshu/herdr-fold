"""Tests for install.sh's and uninstall.sh's Herdr app part, in a temporary HOME (herdr, herdr-app, gh are stubs):
with the app on the Mac, one question puts herdr-fold's mod, layout and keys into it; without it nothing is asked."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from support import catalog_text, copy_package, from_homebrew, run_in_terminal, stubs
from test_install_cleanup import DEFAULTS_STUB, GH_STUB, STUB

# the app's command line: logs each call; running (status answers) only with STUB_APP_RUNNING, on STUB_APP_LAYOUT
APP = """#!/bin/sh
echo "herdr-app $*" >> "$STUB_APP_LOG"
case "$1" in
  status) [ -n "$STUB_APP_RUNNING" ] || exit 1; printf '{"layout": "%s"}\\n' "${STUB_APP_LAYOUT:-main}" ;;
esac
exit 0
"""


class InstallApp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        self.pkg = copy_package(os.path.join(self.tmp, "pkg"))
        self.fakes = stubs(os.path.join(self.tmp, "stubs"), {"herdr": STUB, "gh": GH_STUB, "defaults": DEFAULTS_STUB,
                                                             "brew": None, "open": None, "claude": None, "codex": None,
                                                             "pgrep": None})
        from_homebrew(self.fakes)
        plugins = os.path.join(self.tmp, "plugins.json")
        with open(plugins, "w") as f:
            json.dump({"result": {"plugins": []}}, f)
        self.app_log = os.path.join(self.tmp, "app-calls")
        self.app_home = os.path.join(self.home, ".config", "herdr-app")
        self.env = {"HOME": self.home, "PATH": f"{self.fakes}:/usr/bin:/bin:/usr/sbin:/sbin", "HERDR_FOLD_YES": "1",
                    "HERDR_FOLD_NO_BREW": "1", "HERDR_FOLD_NO_MACHINES": "1", "TERM": "dumb", "GH_STUB_STATE": "out",
                    "GH_STUB_LOG": os.path.join(self.tmp, "gh-calls"), "STUB_PLUGINS": plugins,
                    "STUB_HERDR_LOG": os.path.join(self.tmp, "herdr-calls"), "STUB_APP_LOG": self.app_log}

    def with_app(self, running=False, layout="main"):
        stubs(self.fakes, {"herdr-app": APP})
        if running:
            self.env.update(STUB_APP_RUNNING="1", STUB_APP_LAYOUT=layout)

    def run_script(self, name):
        done = subprocess.run(["bash", os.path.join(self.pkg, name)], env=self.env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=300)
        self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-2000:])
        return done.stdout

    def app_calls(self):
        if not os.path.exists(self.app_log):
            return []
        with open(self.app_log) as f:
            return f.read().splitlines()

    def recorded(self):
        with open(os.path.join(self.home, ".local", "state", "herdr-fold", "plugins.txt")) as f:
            return f.read().splitlines()

    def in_app(self, rel):
        return os.path.exists(os.path.join(self.app_home, rel))

    def test_without_the_app_nothing_is_asked_or_put(self):
        self.run_script("install.sh")
        self.assertFalse(os.path.exists(self.app_home))
        self.assertEqual([line for line in self.recorded() if "herdr-fold.app" in line], [])

    def test_with_the_app_the_question_is_asked(self):
        self.with_app()
        env = {k: v for k, v in self.env.items() if k != "HERDR_FOLD_YES"}
        shown, _ = run_in_terminal(["/bin/bash", os.path.join(self.pkg, "install.sh")], env, lambda line: "",
                                   timeout=240)
        self.assertIn(catalog_text("install.app_ask"), shown)

    def test_with_the_app_it_is_set_up(self):
        self.with_app()
        out = self.run_script("install.sh")
        self.assertTrue(self.in_app("mods/herdr-fold/main.js"))
        self.assertTrue(self.in_app("layouts/herdr-fold.json"))
        with open(os.path.join(self.app_home, "keys.json")) as f:
            self.assertIn("layout:herdr-fold", json.load(f))
        self.assertIn("herdr-fold.app", self.recorded())
        self.assertIn(f"herdr-app check {self.app_home}/mods/herdr-fold", self.app_calls())
        self.assertIn(catalog_text("install.app_done"), out)
        self.assertFalse([call for call in self.app_calls() if "layout.switch" in call])

    def test_a_running_app_shows_the_layout(self):
        self.with_app(running=True)
        out = self.run_script("install.sh")
        self.assertIn("herdr-app do layout.switch --name herdr-fold", self.app_calls())
        self.assertIn(catalog_text("install.app_layout"), out)

    def test_an_earlier_no_stays(self):
        self.with_app()
        state = os.path.join(self.home, ".local", "state", "herdr-fold")
        os.makedirs(state)
        with open(os.path.join(state, "plugins.txt"), "w") as f:
            f.write("declined:herdr-fold.app\n")
        self.run_script("install.sh")
        self.assertFalse(self.in_app("mods/herdr-fold"))
        self.assertIn("declined:herdr-fold.app", self.recorded())

    def test_uninstall_takes_the_app_part_off(self):
        self.with_app(running=True, layout="herdr-fold")
        self.run_script("install.sh")
        out = self.run_script("uninstall.sh")
        self.assertFalse(self.in_app("mods/herdr-fold"))
        self.assertFalse(self.in_app("layouts/herdr-fold.json"))
        with open(os.path.join(self.app_home, "keys.json")) as f:
            self.assertNotIn("layout:herdr-fold", json.load(f))
        self.assertIn("herdr-app do layout.switch --name main", self.app_calls())
        self.assertIn(catalog_text("uninstall.app_off"), out)

    def test_uninstall_takes_the_machines_it_added_off_the_app(self):
        self.with_app()
        hc_log = os.path.join(self.tmp, "hc-calls")
        stubs(self.fakes, {"herdr-core": f'#!/bin/sh\necho "hc $*" >> {hc_log}\n'})
        self.run_script("install.sh")
        record = os.path.join(self.home, ".local", "state", "herdr-fold", "app-machines.txt")
        with open(record, "w") as f:
            f.write("box\nalpha\n")
        self.run_script("uninstall.sh")
        with open(hc_log) as f:
            self.assertEqual(f.read().splitlines(), ["hc machine rm box", "hc machine rm alpha"])
        self.assertFalse(os.path.exists(record))


if __name__ == "__main__":
    unittest.main()
