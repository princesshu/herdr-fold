"""Tests for lib/offer_install.sh, herdr-plugin.toml's hook: on herdr's start or a pane's focus it opens the installer
in a tab of its own, once per package copy; many focus events open one tab, and with nowhere to keep its mark, none.
"""
import ast
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from support import PACKAGE, catalog_text, stubs

OFFER = os.path.join(PACKAGE, "lib", "offer_install.sh")
OPEN = "plugin pane open --plugin herdr-fold --entrypoint install --no-focus"


class Offer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.log = os.path.join(self.tmp, "herdr-calls")
        fake = f'#!/bin/sh\necho "$*" >> "{self.log}"\n'
        self.herdr = os.path.join(stubs(os.path.join(self.tmp, "bin"), {"herdr": fake}), "herdr")
        self.state = os.path.join(self.tmp, "state")

    def copy(self, name):
        """A folder herdr keeps the package in (one per version): its scripts and texts, the package's own."""
        root = os.path.join(self.tmp, "plugins", name)
        os.makedirs(root, exist_ok=True)
        for part in ("lib", "src"):
            if not os.path.exists(os.path.join(root, part)):
                os.symlink(os.path.join(PACKAGE, part), os.path.join(root, part))
        return root

    def env(self, root, state=None):
        return {"PATH": "/usr/bin:/bin", "HERDR_BIN_PATH": self.herdr, "HERDR_PLUGIN_ROOT": root,
                "HERDR_PLUGIN_STATE_DIR": self.state if state is None else state}

    def offer(self, version="a1", state=None):
        done = subprocess.run(["/bin/sh", OFFER], env=self.env(self.copy(version), state), capture_output=True,
                              text=True, timeout=30)
        self.assertEqual((done.returncode, done.stderr), (0, ""))

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as f:
            return f.read().splitlines()

    def marks(self):
        return sorted(name for name in os.listdir(self.state) if name.startswith("offered-"))

    def notified(self):
        return [call for call in self.calls() if call.startswith("notification show ")]

    def test_the_installer_is_offered_once_per_copy(self):
        # in a tab of its own that takes no focus (an Enter typed elsewhere starts nothing), said in a notification
        self.offer()
        self.offer()
        self.assertEqual([call for call in self.calls() if call.startswith("plugin ")], [OPEN])
        self.assertEqual(self.notified(), [f"notification show {catalog_text('offer.ready')} "
                                           f"--body {catalog_text('offer.ready_body')}"])
        self.assertEqual(len(self.marks()), 1)

    def test_herdrs_start_and_a_focus_run_it_as_the_manifest_says(self):
        # the manifest's own command lines, run as herdr runs them: the plugin's root in the environment
        with open(os.path.join(PACKAGE, "herdr-plugin.toml"), encoding="utf-8") as f:
            hooks = re.findall(r'^\[\[(startup|events)\]\]\n(?:on = "pane\.focused"\n)?command = (\[.*\])$', f.read(),
                               re.M)
        self.assertEqual([kind for kind, _ in hooks], ["startup", "events"])
        for n, (_, command) in enumerate(hooks):
            done = subprocess.run(ast.literal_eval(command), env=self.env(self.copy(f"c{n}")), capture_output=True,
                                  text=True, timeout=30)
            self.assertEqual((done.returncode, done.stderr), (0, ""))
        self.assertEqual([call for call in self.calls() if call.startswith("plugin ")], [OPEN, OPEN])  # one a copy

    def test_a_new_copy_is_offered_again_and_the_old_mark_goes(self):
        self.offer("a1")
        first = self.marks()
        self.offer("b2")                                            # herdr plugin update: a new folder
        self.assertEqual([call for call in self.calls() if call.startswith("plugin ")], [OPEN, OPEN])
        self.assertEqual(len(self.marks()), 1)
        self.assertNotEqual(self.marks(), first)

    def test_many_focus_events_at_once_open_one_tab(self):
        runs = [subprocess.Popen(["/bin/sh", OFFER], env=self.env(self.copy("a1")),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for _ in range(20)]
        for run in runs:
            run.wait(timeout=30)
        self.assertEqual([call for call in self.calls() if call.startswith("plugin ")], [OPEN])

    def test_a_tab_that_did_not_open_is_offered_again(self):
        # herdr refused (a client newer than the running server, no workspace yet): the mark goes, the next focus tries
        stubs(os.path.join(self.tmp, "bin"), {"herdr": f'#!/bin/sh\necho "$*" >> "{self.log}"\nexit 1\n'})
        self.offer()
        self.assertEqual(self.marks(), [])
        self.offer()
        self.assertEqual(self.calls(), [OPEN, OPEN])                # and no notification of a tab that is not there

    def test_the_tab_drops_the_switches_that_skip_its_questions(self):
        # a HERDR_FOLD_YES (or CONFIG, STARTED, UPDATE) left in herdr's environment never starts the install unasked
        with open(os.path.join(PACKAGE, "herdr-plugin.toml"), encoding="utf-8") as f:
            pane = f.read().split("[[panes]]", 1)[1]
        command = ast.literal_eval(re.search(r"^command = (\[.*?\])$", pane, re.MULTILINE | re.DOTALL).group(1))
        root = os.path.join(self.tmp, "root")
        stubs(root, {"install.sh": "#!/bin/bash\nenv\n"})
        env = dict(self.env(root), HERDR_FOLD_YES="1", HERDR_FOLD_CONFIG="replace", HERDR_FOLD_STARTED="1",
                   HERDR_FOLD_UPDATE="1", HERDR_FOLD_NO_BREW="1")
        seen = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30).stdout
        skipping = ("HERDR_FOLD_YES", "HERDR_FOLD_CONFIG", "HERDR_FOLD_STARTED", "HERDR_FOLD_UPDATE")
        self.assertEqual([line for line in seen.splitlines() if line.split("=", 1)[0] in skipping], [])
        self.assertIn("HERDR_FOLD_NO_BREW=1", seen)                   # what only does less stays

    def test_without_a_state_folder_nothing_opens(self):
        locked = os.path.join(self.tmp, "locked")
        os.makedirs(locked)
        os.chmod(locked, 0o555)
        self.addCleanup(os.chmod, locked, 0o755)
        self.offer(state="")
        self.offer(state=os.path.join(locked, "state"))
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
