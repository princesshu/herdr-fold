#!/usr/bin/env python3
"""A machine's side of herdr-fold on a GitHub Linux or Windows runner, as machines.sh runs it there over SSH: the
payload it sends, the prepare script, the Herdr app mod's core through a commit and a push, and the prepare script
taking herdr-fold off again. Only on GitHub's own runners: it changes the runner's home (on Windows its PATH too)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.dirname(LAB)
sys.path.insert(0, LAB)
import lab  # noqa: E402
import walk  # noqa: E402

WINDOWS = os.name == "nt"
BASH = r"C:\Program Files\Git\bin\bash.exe" if WINDOWS else "/bin/bash"     # Git's, not WSL's, on Windows
HOME = os.path.expanduser("~")
BIN = os.path.join(HOME, ".local", "bin")                  # where Claude Code's installer puts it
STAND_IN = ("ci", "claude.cmd") if WINDOWS else ("linux", "claude")


class MachineSide(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()        # its cleanup takes git's read-only objects on Windows too
        self.addCleanup(work.cleanup)
        self.work = work.name
        self.env = dict(os.environ, HERDR_FOLD_LANG="en", PATH=BIN + os.pathsep + os.environ["PATH"])

    def run_here(self, argv, stdin=None, cwd=None, env=None):
        out = subprocess.run(argv, input=stdin, cwd=cwd or self.work, env=env or self.env, capture_output=True,
                             encoding="utf-8", errors="replace", timeout=1200)
        self.assertEqual(out.returncode, 0, out.stdout[-3000:] + out.stderr[-3000:])
        return out.stdout

    def shell(self, command):
        return self.run_here([BASH, "-c", command])

    def python(self, args, stdin):
        return self.run_here([sys.executable, *args], stdin)

    def own_core(self, args):
        """hc ARGS through this machine's own core, as the Mac's has them run here: its code and what it printed."""
        out = subprocess.run([self.hc, *args], cwd=self.work, env=self.env, capture_output=True, encoding="utf-8",
                             errors="replace", timeout=600)
        return out.returncode, out.stdout, out.stderr

    def prepare(self, mode=""):
        """machines.sh's payload in ~/.herdr-fold and its prepare script run there, as over SSH: the files it lists."""
        script = "prepare-windows.ps1" if WINDOWS else "prepare-unix.sh"
        stage = os.path.join(HOME, ".herdr-fold")
        self.run_here([BASH, "-c", '. ./machines.sh; stage_payload "$1" "$2" "$3"', "machines.sh",
                       stage.replace("\\", "/"), script, mode], cwd=PACKAGE)
        with open(os.path.join(stage, "files.list")) as f:
            listed = f.read().split()
        if WINDOWS:
            argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(stage, script),
                    "en", *(["-Remove"] if mode else [])]
        else:
            argv = [BASH, os.path.join(stage, script), *(["--remove"] if mode else [])]
        # a session of its own, as over SSH: not the module path of the PowerShell 7 this job's step runs in
        fresh = {key: value for key, value in self.env.items() if key.upper() != "PSMODULEPATH"}
        print(self.run_here(argv, cwd=HOME, env=fresh))
        return listed

    def test_a_machine_is_prepared_commits_and_pushes_and_is_taken_off(self):
        listed = self.prepare()
        with self.subTest("every file listed for it is in place"):
            self.assertTrue(listed)
            self.assertEqual([rel for rel in listed if not os.path.isfile(os.path.join(HOME, rel))], [])
        with self.subTest("the mod's core commits and pushes there, a secret asked about first"):
            os.makedirs(BIN, exist_ok=True)
            stand_in = os.path.join(BIN, STAND_IN[1])
            shutil.copy(os.path.join(LAB, *STAND_IN), stand_in)
            os.chmod(stand_in, 0o755)
            walk.commit_and_push(self, self.shell, self.python)
        with self.subTest("the mod's star writes in the background through the machine's core, outliving its exec"):
            self.hc = shutil.which("herdr-core")
            self.assertTrue(self.hc, "no herdr-core on this runner")
            self.addCleanup(subprocess.run, [self.hc, "server", "stop"], capture_output=True, timeout=60)
            shell = self.run_here([self.hc, "exec", "echo %OS%"])          # how the mod tells a Windows machine
            self.assertEqual("Windows_NT" in shell, WINDOWS, shell)
            binary = self.run_here(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                    os.path.join(HOME, ".config", "herdr-fold", "python.ps1")]).strip() \
                if WINDOWS else "python3"
            walk.write_in_the_background(self, self.own_core, self.shell, os.path.join(self.work, "app"), binary)
        with self.subTest("the prepare script takes herdr-fold off"):
            self.prepare("remove")
            self.assertEqual([rel for rel in listed if os.path.exists(os.path.join(HOME, rel))], [])


if __name__ == "__main__":
    if not lab.on_githubs_runner():
        print("machine_side.py runs only on a GitHub-hosted runner: it changes the runner's home", file=sys.stderr)
        sys.exit(1)
    sys.stdout.reconfigure(encoding="utf-8")         # the prepare script's ✓ and ! in the job's log, Windows too
    unittest.main()
