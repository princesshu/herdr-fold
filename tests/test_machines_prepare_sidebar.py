"""Tests for ./machines.sh prepare's sidebar on an emulated machine (a temp folder, ssh runs here, herdr faked): files
arrive, a herdr-sidebar of its own is named and left alone, nothing is downloaded. Windows needs pwsh on PATH or PWSH.
"""
import os
import shutil
import subprocess
import tempfile
import unittest

from support import FAILING_SCP, FAKE_PYTHON, FAKE_SSH, PWSH, catalog_text, copy_package, stubs

FAKE_HERDR = """#!/bin/sh
printf '%s\\n' "herdr $*" >> "$STUB_HERDR_LOG"
case "$*" in
  *"plugin uninstall "*" "*) echo "usage: herdr plugin uninstall <plugin_id|owner/repo[/subdir...]>" >&2; exit 2 ;;
  "machine list --json") echo '[{"label": "box", "id": "m1", "target": "box"}]' ;;
  *"plugin list"*) [ -n "$STUB_NO_SIDEBAR" ] || echo "- herdr-sidebar (herdr-sidebar) enabled" ;;
  *"workspace list"*) echo '{"result":{"workspaces":[{"workspace_id":"w1","label":"app"}]}}' ;;
  *"pane list"*) echo '{"result":{"panes":[{"pane_id":"w1:p1","tab_id":"w1:t1","label":"sidebar"},
    {"pane_id":"w1:p2","tab_id":"w1:t1","label":"terminal"}]}}' ;;
  *"process-info"*"w1:p1"*) echo '{"result":{"process_info":{"foreground_processes":[{"name":"herdr-sidebar"}]}}}' ;;
  *"process-info"*) echo '{"result":{"process_info":{"foreground_processes":[{"name":"zsh"}]}}}' ;;
esac
exit 0
"""


class RemoteSidebar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.package = os.path.join(self.tmp, "package")
        copy_package(self.package)
        self.profile = os.path.join(self.tmp, "profile")      # the Mac's HOME and the machine's at once
        os.makedirs(os.path.join(self.profile, ".config", "herdr-fold"))
        fakes = stubs(os.path.join(self.tmp, "stubs"), {"ssh": FAKE_SSH, "scp": FAILING_SCP, "python": FAKE_PYTHON,
                                                       "herdr": FAKE_HERDR, **{name: "#!/bin/sh\nexit 0\n"   # present
                                                                               for name in ("starship", "git")}})
        # the machine-side script puts ~/.local/bin and /opt/homebrew/bin first: the fake goes there too, so the real
        # herdr of this Mac is never called
        local_bin = os.path.join(self.profile, ".local", "bin")
        os.makedirs(local_bin)
        shutil.copy(os.path.join(fakes, "herdr"), local_bin)
        self.log = os.path.join(self.tmp, "herdr-calls")
        self.env = {"HOME": self.profile, "USERPROFILE": self.profile, "PROCESSOR_ARCHITECTURE": "AMD64",
                    "LOCALAPPDATA": os.path.join(self.profile, "AppData", "Local"), "PWSH": PWSH or "", "TERM": "dumb",
                    "PATH": f"{fakes}:/usr/bin:/bin", "TMPDIR": self.tmp + "/", "STUB_HERDR_LOG": self.log,
                    "HERDR_FOLD_PLATFORM": "Darwin-arm64"}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def prepare(self, os_name):
        with open(os.path.join(self.profile, ".config", "herdr-fold", "machines.txt"), "w") as f:
            f.write(f"box | box | {os_name}\n")
        done = subprocess.run(["bash", os.path.join(self.package, "machines.sh"), "prepare"], env=self.env,
                              capture_output=True, text=True, timeout=300)
        with open(self.log) as f:
            return f.read().splitlines(), done.stdout + done.stderr

    def test_someones_own_herdr_sidebar_on_a_machine_is_named_and_left_alone(self):
        calls, out = self.prepare("linux")
        self.assertFalse([c for c in calls if "herdr-sidebar" in c and " plugin " in c and "list" not in c], out)
        self.assertIn(catalog_text("machines.herdr_sidebar_too"), out)

    def test_nothing_is_installed_from_the_internet(self):
        self.env["STUB_NO_SIDEBAR"] = "1"
        calls, out = self.prepare("linux")
        self.assertFalse([c for c in calls if c.startswith("herdr plugin install")], out)
        self.assertNotIn("[!] " + catalog_text("machines.finishing"), out)

    def test_the_sidebar_files_reach_the_machine_and_a_dropped_file_goes(self):
        # a machine prepared before: its record lists a file the package no longer has
        old = ".config/herdr-fold/dropped/tool.sh"
        for rel, text in ((old, "#!/bin/sh\n"), (".local/state/herdr-fold/prepared.txt", old + "\n")):
            os.makedirs(os.path.dirname(os.path.join(self.profile, rel)), exist_ok=True)
            with open(os.path.join(self.profile, rel), "w") as f:
                f.write(text)
        _, out = self.prepare("linux")
        folder = os.path.join(self.profile, ".config", "herdr-fold")
        self.assertTrue(os.path.isfile(os.path.join(folder, "plugins", "sidebar", "sidebar.py")), out)
        self.assertFalse(os.path.exists(os.path.join(folder, "dropped")), out)

    def linked(self, calls):
        return [call.split(" plugin link ", 1)[1] for call in calls if " plugin link " in call]

    def test_a_machines_plugins_are_linked_where_it_got_them(self):
        calls, out = self.prepare("linux")
        self.assertEqual([path.replace(self.profile, "~") for path in self.linked(calls)],
                         ["~/.config/herdr-fold/plugins/sessions-view", "~/.config/herdr-fold/plugins/tab-layout"], out)

    @unittest.skipUnless(PWSH, "no PowerShell (pwsh) on this machine")
    def test_a_windows_machines_plugins_are_linked_where_it_got_them(self):
        calls, out = self.prepare("windows")
        self.assertEqual([path.replace(self.profile, "~").replace("\\", "/") for path in self.linked(calls)],
                         ["~/.config/herdr-fold/plugins/sessions-view", "~/.config/herdr-fold/plugins/tab-layout"], out)

    @unittest.skipUnless(PWSH, "no PowerShell (pwsh) on this machine")
    def test_someones_own_herdr_sidebar_on_a_windows_machine_is_named_and_left_alone(self):
        calls, out = self.prepare("windows")
        self.assertFalse([c for c in calls if "herdr-sidebar" in c and " plugin " in c and "list" not in c], out)
        self.assertIn(catalog_text("machines.herdr_sidebar_too"), out)

    @unittest.skipUnless(PWSH, "no PowerShell (pwsh) on this machine")
    def test_nothing_is_installed_from_the_internet_on_windows(self):
        self.env["STUB_NO_SIDEBAR"] = "1"
        calls, out = self.prepare("windows")
        self.assertFalse([c for c in calls if c.startswith("herdr plugin install")], out)
        self.assertNotIn("[!] " + catalog_text("machines.finishing"), out)


if __name__ == "__main__":
    unittest.main()
