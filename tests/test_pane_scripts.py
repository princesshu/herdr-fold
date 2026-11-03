"""Tests for the small pane scripts: pane-env.sh, claude_search.py (Cmd+F) and sidebar.sh / sidebar.ps1, with fakes in
a temporary HOME.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from support import PWSH, stubs

HERDR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


class PaneEnv(unittest.TestCase):
    def source(self, times):
        home = tempfile.mkdtemp()
        script = os.path.join(HERDR_DIR, "pane-env.sh")
        body = "; ".join([f". {script}"] * times) + '; echo "$CLAUDE_CODE_NO_FLICKER"; echo "$PATH"'
        out = subprocess.run(["/bin/sh", "-c", body], env={"HOME": home, "PATH": "/usr/bin:/bin"},
                             capture_output=True, text=True).stdout.split("\n")
        shutil.rmtree(home)
        return home, out[0], out[1]

    def test_claude_starts_fullscreen(self):
        _, flicker, _ = self.source(1)
        self.assertEqual(flicker, "1")

    def test_herdr_pbcopy_comes_first_once(self):
        home, _, path = self.source(2)
        self.assertEqual(path, f"{home}/.config/herdr-fold/bin:/usr/bin:/bin")


class ClaudeSearch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.log = os.path.join(self.tmp, "calls")
        agents = {"result": {"agents": [{"pane_id": "w1:p1", "agent": "claude"},
                                        {"pane_id": "w1:p4", "agent": "codex"}]}}
        self.stub = os.path.join(self.tmp, "herdr")
        with open(self.stub, "w") as f:
            f.write(f"#!/bin/sh\necho \"$*\" >> {self.log}\n"
                    f"[ \"$1 $2\" = \"agent list\" ] && echo '{json.dumps(agents)}'\nexit 0\n")
        os.chmod(self.stub, 0o755)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_search(self, pane):
        subprocess.run(["/usr/bin/python3", os.path.join(HERDR_DIR, "claude_search.py")], timeout=10,
                       env={"HERDR_BIN_PATH": self.stub, "HERDR_ACTIVE_PANE_ID": pane, "PATH": "/usr/bin:/bin"})
        with open(self.log) as f:
            return [line.strip() for line in f if not line.startswith("agent list")]

    def test_opens_the_search_in_a_claude_pane(self):
        self.assertEqual(self.run_search("w1:p1"), ["pane send-keys w1:p1 ctrl+o", "pane send-text w1:p1 /"])

    def test_does_nothing_in_other_panes(self):
        self.assertEqual(self.run_search("w1:p2"), [])
        self.assertEqual(self.run_search("w1:p4"), [])


FAKE_SIDEBAR = "import sys\nprint('FOLDER=' + sys.argv[1])\nprint('CACHE=' + str(sys.dont_write_bytecode))\n"


class Launcher:
    """A sidebar launcher starts the plugin's sidebar.py in the folder it is given (the pane's by default), without
    leaving Python caches next to the plugin."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home = os.path.join(self.tmp, "home")
        plugin = os.path.join(self.home, ".config", "herdr-fold", "plugins", "sidebar")
        os.makedirs(plugin)
        with open(os.path.join(plugin, "sidebar.py"), "w") as f:
            f.write(FAKE_SIDEBAR)
        self.folder = os.path.join(self.tmp, "project")
        os.makedirs(self.folder)

    def test_starts_the_sidebar_in_the_folder_it_is_given(self):
        out = self.launch(self.folder)
        self.assertIn("FOLDER=" + self.folder, out)
        self.assertIn("CACHE=True", out)

    def test_defaults_to_the_panes_folder(self):
        self.assertIn("FOLDER=" + os.path.realpath(self.folder), self.launch(None, cwd=self.folder))


class SidebarLauncher(Launcher, unittest.TestCase):
    def launch(self, folder, cwd=None, script=None, path="/usr/bin:/bin"):
        argv = ["/bin/bash", script or os.path.join(HERDR_DIR, "sidebar.sh")] + ([folder] if folder else [])
        done = subprocess.run(argv, env={"HOME": self.home, "PATH": path}, cwd=cwd or self.tmp,
                              capture_output=True, text=True, timeout=30)
        return done.stdout + done.stderr

    def without_the_system_python(self):
        """The launcher as on a machine without /usr/bin/python3 (a Linux without it, say): a copy that looks for it
        at a path that does not exist."""
        with open(os.path.join(HERDR_DIR, "sidebar.sh")) as f:
            source = f.read()
        self.assertIn("py=/usr/bin/python3", source)
        script = os.path.join(self.tmp, "sidebar.sh")
        with open(script, "w") as f:
            f.write(source.replace("py=/usr/bin/python3", f"py={self.tmp}/none/python3"))
        return script

    def test_a_python3_on_the_path_stands_in_for_the_system_one(self):
        bin_dir = stubs(os.path.join(self.tmp, "bin"), {"python3": '#!/bin/sh\nexec /usr/bin/python3 "$@"\n'})
        out = self.launch(self.folder, script=self.without_the_system_python(), path=f"{bin_dir}:/bin")
        self.assertIn("FOLDER=" + self.folder, out)

    def test_says_what_is_missing_without_python3(self):
        out = self.launch(self.folder, script=self.without_the_system_python(), path="/bin")
        self.assertIn("The sidebar needs Python 3.9 or newer (python3).", out)
        self.assertNotIn("FOLDER=", out)


@unittest.skipUnless(PWSH, "no PowerShell (pwsh) on this machine")
class WindowsSidebarLauncher(Launcher, unittest.TestCase):
    def setUp(self):
        super().setUp()
        # the launcher sits in ~/.config/herdr-fold, next to plugins/: it finds the plugin from its own folder
        for name in ("sidebar.ps1", "python.ps1"):                         # as the machine gets them
            shutil.copy(os.path.join(HERDR_DIR, name), os.path.join(self.home, ".config", "herdr-fold"))
        self.bin = stubs(os.path.join(self.tmp, "bin"), {"python": '#!/bin/sh\nexec /usr/bin/python3 "$@"\n'})

    def launch(self, folder, cwd=None, path=None, local_app_data=None):
        script = os.path.join(self.home, ".config", "herdr-fold", "sidebar.ps1")
        argv = [PWSH, "-NoProfile", "-File", script] + ([folder] if folder else [])
        env = {"HOME": self.home, "PATH": path or f"{self.bin}:/usr/bin:/bin",
               **({"LOCALAPPDATA": local_app_data} if local_app_data else {})}
        done = subprocess.run(argv, env=env, cwd=cwd or self.tmp, capture_output=True, text=True, timeout=60)
        return done.stdout + done.stderr

    def test_the_store_alias_is_passed_over_for_the_real_python(self):
        # Windows' "python" in WindowsApps only offers the Store; a python.org install for the user is the real one
        store = stubs(os.path.join(self.tmp, "WindowsApps"), {"python": "#!/bin/sh\necho STORE\n"})
        local = os.path.join(self.tmp, "AppData", "Local")
        stubs(os.path.join(local, "Programs", "Python", "Python312"),
              {"python.exe": '#!/bin/sh\nexec /usr/bin/python3 "$@"\n'})
        out = self.launch(self.folder, path=f"{store}:/bin", local_app_data=local)
        self.assertIn("FOLDER=" + self.folder, out)
        self.assertNotIn("STORE", out)

    def test_says_what_is_missing_without_python(self):
        self.assertIn("The sidebar needs Python 3.9 or newer", self.launch(self.folder, path="/bin"))


@unittest.skipUnless(PWSH, "no PowerShell (pwsh) on this machine")
class WindowsPython(unittest.TestCase):
    """python.ps1: the real Python's path on a Windows machine, which its sidebar, prepare script and the Herdr app mod
    take; the Store's alias in WindowsApps is passed over."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.local = os.path.join(self.tmp, "AppData", "Local")

    def find(self, path):
        done = subprocess.run([PWSH, "-NoProfile", "-File", os.path.join(HERDR_DIR, "python.ps1")], capture_output=True,
                              text=True, timeout=60, env={"PATH": path, "LOCALAPPDATA": self.local, "HOME": self.tmp})
        return done.returncode, done.stdout.strip()

    def test_the_python_on_the_path_unless_it_is_the_stores_alias(self):
        real = stubs(os.path.join(self.tmp, "Python"), {"python": "#!/bin/sh\n"})
        self.assertEqual(self.find(f"{real}:/bin"), (0, os.path.join(real, "python")))
        store = stubs(os.path.join(self.tmp, "WindowsApps"), {"python": "#!/bin/sh\n"})
        installed = stubs(os.path.join(self.local, "Programs", "Python", "Python312"), {"python.exe": "#!/bin/sh\n"})
        self.assertEqual(self.find(f"{store}:/bin"), (0, os.path.join(installed, "python.exe")))

    def test_nothing_without_a_python(self):
        self.assertEqual(self.find("/bin"), (1, ""))


if __name__ == "__main__":
    unittest.main()
