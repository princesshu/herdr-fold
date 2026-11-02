"""The whole remote way on the lab's machine: install.sh in a home of its own connects it to herdr (the TUI) and to the
Herdr app's core as the installer does, the mod's own code commits and pushes there, and uninstall.sh takes the app's
part off again. Run by python3 lab/lab.py test; nothing of the person's own (herdr, the app, ~/.ssh) is used."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.dirname(LAB)
sys.path.insert(0, LAB)
sys.path.insert(0, os.path.join(PACKAGE, "tests"))
import lab  # noqa: E402
from support import copy_package, run_in_terminal, stubs  # noqa: E402

# stand-ins on this Mac: no GitHub sign-in, browser, Tailscale network or Codex; a Claude that answers one message
FAKES = {"gh": "#!/bin/sh\nexit 1\n", "open": "#!/bin/sh\nexit 0\n", "defaults": "#!/bin/sh\nexit 1\n",
         "tailscale": "#!/bin/sh\nexit 1\n", "codex": None, "pgrep": "#!/bin/sh\nexit 1\n",
         "claude": "#!/bin/sh\ncat >/dev/null\nprintf 'feat: a change\\n'\n"}


def herdr_app():
    return shutil.which("herdr-app") or os.path.expanduser("~/.local/bin/herdr-app")


class WholeWay(unittest.TestCase):
    def setUp(self):
        self.lab = lab.Lab()
        # in the lab's own folder: a socket's path must stay within the 104 bytes macOS gives it
        self.tmp = tempfile.mkdtemp(prefix="demo-", dir=self.lab.home)
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(os.path.join(self.home, ".config", "herdr-fold"))
        with open(os.path.join(self.home, ".config", "herdr-fold", "machines.txt"), "w") as f:
            f.write("lab | lab | linux\n")
        fakes = stubs(os.path.join(self.tmp, "fakes"), FAKES)
        # herdr runs ssh through the login shell, whose /etc/zprofile puts the system's ssh first: the home's own
        # .zprofile, read after it, puts the lab's (which reads only the lab's settings) back in front
        with open(os.path.join(self.home, ".zprofile"), "w") as f:
            f.write(f'export PATH="{self.lab.bin}:{fakes}:$PATH"\n')
        path = [self.lab.bin, fakes, "/opt/homebrew/bin", os.path.dirname(herdr_app()), "/usr/bin", "/bin",
                "/usr/sbin", "/sbin"]
        # the core's socket goes under XDG_RUNTIME_DIR: the demo's own folder keeps it short, the home's would not
        self.env = {"HOME": self.home, "PATH": ":".join(path), "SHELL": "/bin/zsh", "TERM": "xterm-256color",
                    "LANG": "en_US.UTF-8", "XDG_RUNTIME_DIR": self.tmp, "HERDR_FOLD_YES": "1",
                    "HERDR_FOLD_NO_BREW": "1", "HERDR_TELEMETRY": "0", "DO_NOT_TRACK": "1",
                    "HC_SESSION": "herdr-fold-lab"}
        self.package = copy_package(os.path.join(self.tmp, "package"))
        self.server = subprocess.Popen(["herdr", "server"], env=self.env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self.stop)
        self.wait_for(lambda: self.run_here("herdr", "status", "server").returncode == 0, "the demo herdr")

    def stop(self):
        """The demo's servers stopped, its own herdr by its own PID if it does not go."""
        self.run_here("herdr", "server", "stop")
        self.run_here("herdr-core", "server", "stop")
        try:
            self.server.wait(10)
        except subprocess.TimeoutExpired:
            self.server.kill()
            self.server.wait()

    def run_here(self, *argv):
        return subprocess.run(argv, env=self.env, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=600)

    def wait_for(self, condition, what, seconds=60):
        deadline = time.monotonic() + seconds
        while not condition():
            if time.monotonic() >= deadline:
                self.fail(f"{what} did not come up")
            time.sleep(0.5)

    def on_machine(self, command, stdin=None):
        """COMMAND on the lab's machine, as dev."""
        out = subprocess.run([os.path.join(self.lab.bin, "ssh"), "lab", command], input=stdin, capture_output=True,
                             text=True, timeout=600)
        self.assertEqual(out.returncode, 0, out.stdout[-2000:] + out.stderr[-2000:])
        return out.stdout

    def core(self, module, *args):
        """core/MODULE run on the machine as the mod runs it: python3 -I, its source given, not installed there."""
        with open(os.path.join(PACKAGE, "core", module), encoding="utf-8") as f:
            source = f.read()
        return json.loads(self.on_machine("python3 -I - " + " ".join(args), stdin=source))

    def test_the_whole_way(self):
        shown, ended = run_in_terminal(["/bin/bash", os.path.join(self.package, "install.sh")], self.env,
                                       lambda line: "y" if "install" in line.lower() else "", timeout=1500)
        self.assertTrue(ended, shown[-3000:])
        state = os.path.join(self.home, ".local", "state", "herdr-fold")
        with self.subTest("the TUI has the machine, and the machine its part"):
            listed = json.loads(self.run_here("herdr", "machine", "list", "--json").stdout or "[]")
            self.assertIn("lab", [machine.get("label") for machine in listed], shown[-3000:])
            self.on_machine("test -x ~/.config/herdr-fold/sidebar.sh && python3 --version && git --version")
        with self.subTest("the Herdr app has herdr-fold and the machine"):
            self.assertTrue(os.path.isfile(os.path.join(self.home, ".config", "herdr-app", "mods", "herdr-fold",
                                                        "main.js")), shown[-3000:])
            self.assertIn("lab", self.run_here("herdr-core", "machine", "ls", "--json").stdout)
            with open(os.path.join(state, "app-machines.txt")) as f:
                self.assertEqual(f.read().split(), ["lab"])
        with self.subTest("the mod's code commits and pushes on the machine, a secret asked about first"):
            self.on_machine("git init -q --bare -b main origin.git && git init -q -b main app && cd app && "
                            "git config user.name dev && git config user.email dev@example.com && echo one > a.txt "
                            "&& git add -A && git commit -q -m init && git remote add origin ../origin.git && "
                            "git push -q -u origin main && echo two > a.txt && echo TOKEN=1 > .env")
            self.assertEqual(self.core("git.py", "stage", "app"), {"ok": True, "advice": None})
            self.assertEqual(self.core("commit_message.py", "secrets", "app"), {"secret_looking": [".env"]})
            written = self.core("commit_message.py", "write", "app")["message"]       # the machine's stand-in Claude
            self.assertTrue(written.startswith("feat: change the lab files"), written)
            self.assertEqual(self.core("git.py", "commit", "app", "'feat: change the lab files'"),
                             {"ok": True, "advice": None})
            self.assertEqual(self.core("git.py", "sync", "app"), {"ok": True, "advice": None})
            pushed = self.on_machine("git -C origin.git log -1 --format=%s").strip()
            self.assertEqual(pushed, "feat: change the lab files")
        with self.subTest("uninstall.sh takes the app's part off"):
            out = self.run_here("/bin/bash", os.path.join(self.package, "uninstall.sh"))
            self.assertEqual(out.returncode, 0, out.stdout[-2000:] + out.stderr[-2000:])
            self.assertFalse(os.path.exists(os.path.join(self.home, ".config", "herdr-app", "mods", "herdr-fold")))
            self.assertNotIn("lab", self.run_here("herdr-core", "machine", "ls", "--json").stdout)


if __name__ == "__main__":
    unittest.main()
