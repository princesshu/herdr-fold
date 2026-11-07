"""Tests for install.sh's and uninstall.sh's Herdr app part, in a temporary HOME (herdr, herdr-app, gh are stubs):
with the app on the Mac, one question puts herdr-fold's mod, layout and keys into it; without it nothing is asked."""
import json
import os
import unittest

from support import AppInstall, catalog_text, run_in_terminal, stubs


class InstallApp(AppInstall, unittest.TestCase):
    def test_without_the_app_nothing_is_asked_or_put(self):
        self.run_script("install.sh")
        self.assertFalse(os.path.exists(self.app_home))
        self.assertEqual([line for line in self.recorded() if "herdr-fold.app" in line], [])

    def test_an_update_of_the_tui_alone_asks_once_about_the_app_found(self):
        """The TUI installed, then the Herdr app on this Mac: the update asks about it once (how v0.2.0's users meet
        it), not the first question."""
        self.run_script("install.sh")
        self.with_app()
        env = {k: v for k, v in self.env.items() if k != "HERDR_FOLD_YES"}
        shown, _ = run_in_terminal(["/bin/bash", os.path.join(self.pkg, "install.sh")], env, lambda line: "",
                                   timeout=240)
        self.assertIn(catalog_text("install.app_ask"), shown)
        self.assertNotIn(catalog_text("install.parts_ask"), shown)

    def test_with_the_app_it_is_set_up(self):
        self.with_app()
        out = self.run_script("install.sh")
        self.assertTrue(self.in_app("mods/herdr-fold/main.js"))           # what it puts there: test_lib_herdr_app
        self.assertIn("herdr-fold.app", self.recorded())
        self.assertIn(f"herdr-app check {self.app_home}/mods/herdr-fold", self.app_calls())
        self.assertIn(catalog_text("install.app_done"), out)
        self.assertFalse([call for call in self.app_calls() if "layout.switch" in call])

    def test_the_check_leaves_no_editor_file_in_the_mod(self):
        """herdr-app check writes an editor's types and settings beside the mod it checks: none stays there."""
        self.with_app()
        self.run_script("install.sh")
        left = [name for name in ("gpui-kit.d.ts", "herdr.d.ts", "jsconfig.json")
                if os.path.exists(os.path.join(self.app_home, "mods", "herdr-fold", name))]
        self.assertEqual(left, [])

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
        self.assertFalse(self.in_app("mods/herdr-fold"))                   # what it takes off: test_lib_herdr_app
        self.assertIn("herdr-app do layout.switch --name main", self.app_calls())
        self.assertIn(catalog_text("uninstall.app_off"), out)

    def in_bundle(self):
        """The app's command line where the app puts it: a link into Herdr.app; returns the bundle."""
        bundle = os.path.join(self.tmp, "Applications", "Herdr.app")
        os.makedirs(os.path.join(bundle, "Contents", "MacOS"))
        os.replace(os.path.join(self.fakes, "herdr-app"), os.path.join(bundle, "Contents", "MacOS", "Herdr"))
        os.symlink(os.path.join(bundle, "Contents", "MacOS", "Herdr"), os.path.join(self.fakes, "herdr-app"))
        return os.path.realpath(bundle)

    def with_settings(self):
        with open(os.path.join(self.app_home, "shared.json"), "w") as f:
            json.dump({"herdr-fold.view": "changes", "frame.welcomed": True}, f)

    def settings(self):
        with open(os.path.join(self.app_home, "shared.json")) as f:
            return json.load(f)

    def test_uninstall_closes_a_running_app_for_herdr_folds_settings_and_opens_it_again(self):
        """A running app holds the mods' shared values and writes them all back: closed meanwhile, as its terminals
        run on in its core, and opened again behind the uninstaller."""
        self.with_app(running=True, layout="herdr-fold")
        bundle = self.in_bundle()
        self.run_script("install.sh")
        self.with_settings()
        opened = os.path.join(self.tmp, "opened")
        stubs(self.fakes, {"open": f'#!/bin/sh\necho "$*" >> {opened}\n'})
        out = self.run_script("uninstall.sh")
        self.assertIn("herdr-app do app.quit", self.app_calls())
        self.assertIn(catalog_text("uninstall.app_closing"), out)
        self.assertEqual(self.settings(), {"frame.welcomed": True})
        with open(opened) as f:
            self.assertEqual(f.read().splitlines(), [f"-g {bundle}"])

    def test_an_app_that_does_not_open_again_is_named(self):
        self.with_app(running=True)
        self.in_bundle()
        self.run_script("install.sh")
        out = self.run_script("uninstall.sh")                           # the open stub fails
        self.assertIn(catalog_text("uninstall.app_not_reopened"), out)

    def test_an_app_that_does_not_close_keeps_the_settings_and_says_where(self):
        self.with_app(running=True)
        self.env["STUB_APP_STAYS"] = "1"
        self.run_script("install.sh")
        self.with_settings()
        out = self.run_script("uninstall.sh")
        self.assertEqual(self.settings(), {"herdr-fold.view": "changes", "frame.welcomed": True})
        self.assertIn(catalog_text("uninstall.app_still_open", "~/.config/herdr-app/shared.json"), out)

    def test_a_closed_app_stays_closed(self):
        self.with_app()
        self.run_script("install.sh")
        self.with_settings()
        self.run_script("uninstall.sh")
        self.assertEqual(self.settings(), {"frame.welcomed": True})
        self.assertFalse([call for call in self.app_calls() if "app.quit" in call])

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
