"""The whole remote way on the lab's machine: install.sh connects it to herdr (the TUI) and the Herdr app's core, where
the mod commits and pushes; the sidebar draws there; uninstall.sh takes each part off. Each part alone and an update
from the last release, in homes of their own. Run by python3 lab/lab.py test; nothing of the person's own is used."""
import json
import os
import shlex
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
sys.path.insert(0, os.path.join(PACKAGE, "lib"))
import herdr_app as app_setup  # noqa: E402  (herdr_app() below is the app's command line)
import lab  # noqa: E402
import walk  # noqa: E402
from support import copy_package, run_in_terminal, stubs  # noqa: E402

# what of herdr-fold's a home keeps after the last part goes: the machine list (written by its person), and the lab's
# own core session
KEPT = (".config/herdr-fold", ".config/herdr-fold/machines.txt")
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
        system = {"Linux": "linux", "Darwin": "macos"}[self.on_machine("uname -s").strip()]
        with open(os.path.join(self.home, ".config", "herdr-fold", "machines.txt"), "w") as f:
            f.write(f"lab | lab | {system}\n")
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

    def in_the_app_window(self, root):
        """The demo's Herdr app on this screen, a space on the machine at ROOT: the mod's star, Commit and Sync, by the
        app's own commands; what the window lists while the message is written, in the log."""
        app, said = herdr_app(), os.path.join(self.tmp, "app.log")
        self.seen_before(app)
        with open(said, "w") as log:                        # the app's own lines, for a failure to show
            window = subprocess.Popen([app], env=self.env, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        self.addCleanup(self.quit, window)
        self.wait_for(lambda: self.run_here(app, "status").returncode == 0, "the Herdr app", 120)
        self.on_machine("cd app && echo four > a.txt")
        # the right panel shown at herdr-fold, as mod.open does from a hidden one (again it would hide it): a hidden
        # copy gets no commands
        for args in (["space.new", "--machine", "lab", "--folder", root], ["layout.switch", "--name", "herdr-fold"],
                     ["layout.select", "--stack", "fold-panel-body", "--child", "changes"],
                     ["layout.show", "--id", "fold-panel"]):
            out = self.run_here(app, "do", *args)
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        deadline, asked, listed = time.monotonic() + 180, 0.0, False
        while not self.on_machine("git -C app log -1 --format=%s").startswith(walk.MESSAGE) or \
                "four" not in self.on_machine("git -C app show --format= HEAD -- a.txt"):
            if time.monotonic() > deadline:
                self.fail("the mod's commit did not come\n" + self.app_failed(app, said))
            if time.monotonic() - asked > 20:       # before the mod has its repository, or while it works, it drops it
                self.run_here(app, "do", "herdr-fold.write")
                asked = time.monotonic()
            self.run_here(app, "do", "herdr-fold.commit")         # nothing to commit while the message is written
            time.sleep(2)
            if not listed:
                print("\nthe window while the message is written:\n" + self.run_here(app, "ls").stdout,
                      file=sys.stderr)
                listed = True
        self.run_here(app, "do", "herdr-fold.sync")
        self.wait_for(lambda: self.on_machine("git -C app rev-parse HEAD") ==
                      self.on_machine("git -C origin.git rev-parse main"), "the mod's push", 60)
        # drawn too, not only obeyed, Search as well: the window's status names any error a mod's code ran into
        self.assertEqual(self.run_here(app, "do", "herdr-fold.search").returncode, 0)
        time.sleep(3)
        status = self.run_here(app, "status").stdout
        print("\nthe window's status:\n" + status, file=sys.stderr)
        broken = [line for line in status.splitlines() if "herdr-fold" in line and
                  any(word in line.lower() for word in ("error", "panic", "exception", "failed"))]
        self.assertEqual(broken, [], self.app_failed(app, said))
        # the tab's own terminal under the panel, on the space's machine, as the TUI's right column has it there
        app_home = os.path.join(self.home, ".config", "herdr-app")
        self.wait_for(lambda: any(a.startswith("lab/") for a in app_setup.tab_terminals(app_home)),
                      "the tab's terminal on the machine", 60)
        address = next(a for a in app_setup.tab_terminals(app_home) if a.startswith("lab/"))
        got = self.run_here("herdr-core", "get", "--json", address)
        self.assertEqual(json.loads(got.stdout or "{}").get("state"), "live", got.stdout + got.stderr)

    def seen_before(self, app):
        """The demo's app as one that ran this version before: no welcome, no What's New over the mod's panel (the
        app's own bench script starts it past the welcome the same way)."""
        home = os.path.join(self.home, ".config", "herdr-app")
        for name, value in (("shared.json", {"frame.welcomed": True}),
                            ("update-notes.json", {"last_run": self.run_here(app, "--version").stdout.split()[-1]})):
            path, kept = os.path.join(home, name), {}
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    kept = json.load(f)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(dict(kept, **value), f)

    def app_failed(self, app, said):
        """What shows why the mod did not get on: the window's status and its own lines, the core's terminals, the job
        folders on the machine; a picture of the window where the runner keeps one (LAB_ARTIFACTS)."""
        kept = os.environ.get("LAB_ARTIFACTS")
        if kept:
            os.makedirs(kept, exist_ok=True)
            self.run_here(app, "shot", os.path.join(kept, "app-window.png"))
        jobs = self.on_machine("python3 -c 'import os, tempfile; d = tempfile.gettempdir(); "
                               "print(sorted(n for n in os.listdir(d) if n.startswith(\"herdr-fold.\")))'")
        with open(said, errors="replace") as f:
            lines = f.read()[-3000:]
        terminals = self.run_here("herdr-core", "ls", "--all", "--json").stdout
        return "\n".join([self.run_here(app, "status").stdout, terminals, "job folders on the machine: " + jobs, lines])

    def quit(self, window):
        """The demo's app quits, its own PID ended if it does not."""
        self.run_here(herdr_app(), "do", "app.quit")
        try:
            window.wait(30)
        except subprocess.TimeoutExpired:
            window.kill()
            window.wait()

    def run_here(self, *argv, **switches):
        return subprocess.run(argv, env={**self.env, **switches}, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=600)

    def script(self, name, package=None, **switches):
        """The package's install.sh or uninstall.sh run with SWITCHES (HERDR_FOLD_PARTS…), every answer the default."""
        out = self.run_here("/bin/bash", os.path.join(package or self.package, name), **switches)
        self.assertEqual(out.returncode, 0, out.stdout[-3000:] + out.stderr[-2000:])
        return out.stdout

    def left(self):
        """What of herdr-fold's the home holds, but KEPT: a path naming herdr-fold, the lab's core session aside."""
        found = []
        for folder, dirs, files in os.walk(self.home):
            for name in dirs + files:
                rel = os.path.relpath(os.path.join(folder, name), self.home)
                if "herdr-fold" in rel and "herdr-fold-lab" not in rel and rel not in KEPT:
                    found.append(rel)
        return sorted(found)

    def at(self, rel):
        return os.path.exists(os.path.join(self.home, rel))

    def herdr_plugins(self):
        listed = json.loads(self.run_here("herdr", "plugin", "list", "--json").stdout or "{}")
        return [plugin.get("plugin_id") for plugin in listed.get("result", {}).get("plugins", [])]

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

    def on_python(self, args, stdin):
        return self.on_machine("python3 " + " ".join(map(shlex.quote, args)), stdin)

    def app_core(self, args):
        """hc ARGS through the demo's app core, as the mod has it run them: its code and what it printed."""
        out = self.run_here("herdr-core", *args)
        return out.returncode, out.stdout, out.stderr

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
            walk.commit_and_push(self, self.on_machine, self.on_python)
        root = self.on_machine("pwd").strip() + "/app"
        with self.subTest("the mod's star writes in the background through the app's core, outliving its exec"):
            walk.write_in_the_background(self, self.app_core, self.on_machine, root, "python3", on="lab")
        with self.subTest("the TUI's sidebar draws on the machine, in a workspace herdr-fold lays out there"):
            out = self.run_here("python3", os.path.join(self.home, ".config", "herdr-fold", "herdr_layout.py"),
                                "--machine", "lab", root)
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            panes = json.loads(self.run_here("herdr", "--machine", "lab", "pane", "list").stdout)["result"]["panes"]
            # the new workspace's (the installer laid out one in the machine's home before)
            sidebar = next(pane["pane_id"] for pane in panes if pane.get("label") == "sidebar" and pane["cwd"] == root)
            deadline, shown = time.monotonic() + 60, ""
            while "a.txt" not in shown and time.monotonic() < deadline:     # Files: the repository read there
                read = self.run_here("herdr", "--machine", "lab", "pane", "read", sidebar)
                shown = read.stdout + read.stderr
                time.sleep(1)
            self.assertIn("a.txt", shown, shown[-3000:])
        with self.subTest("the Herdr app's window: its mod writes, commits and syncs a change on the machine"):
            if not lab.on_githubs_runner():
                self.skipTest("the app's window opens on a GitHub runner only, never on this Mac's screen")
            self.in_the_app_window(root)
        with self.subTest("uninstall.sh takes the TUI's part off, the app keeps its own and the machine"):
            self.script("uninstall.sh", HERDR_FOLD_PARTS="tui")
            self.assertFalse(self.at(".config/ghostty/config"))
            self.assertNotIn("herdr-fold.sidebar", self.herdr_plugins())
            self.assertTrue(self.at(".config/herdr-app/mods/herdr-fold/main.js"))
            self.assertIn("lab", self.run_here("herdr-core", "machine", "ls", "--json").stdout)
        with self.subTest("then the app's, and nothing of herdr-fold's is left but the machine list"):
            self.script("uninstall.sh", HERDR_FOLD_PARTS="app")
            self.assertNotIn("lab", self.run_here("herdr-core", "machine", "ls", "--json").stdout)
            self.assertEqual(self.left(), [])

    def test_the_tui_alone(self):
        """herdr's TUI alone: Ghostty's and herdr's settings, herdr-fold's plugins, nothing in the Herdr app."""
        self.script("install.sh", HERDR_FOLD_PARTS="tui", HERDR_FOLD_NO_MACHINES="1")
        self.assertTrue(self.at(".config/ghostty/config"))
        self.assertIn("herdr-fold.sidebar", self.herdr_plugins())
        self.assertFalse(self.at(".config/herdr-app/mods/herdr-fold"))
        self.script("uninstall.sh")
        self.assertEqual(self.left(), [])

    def test_the_app_alone(self):
        """The Herdr app alone: its mod, layout and keys, nothing of the TUI's, no herdr plugin."""
        self.script("install.sh", HERDR_FOLD_PARTS="app", HERDR_FOLD_NO_MACHINES="1")
        self.assertTrue(self.at(".config/herdr-app/mods/herdr-fold/main.js"))
        self.assertFalse(self.at(".config/ghostty/config") or self.at(".config/herdr/config.toml"))
        self.assertFalse([plugin for plugin in self.herdr_plugins() if plugin.startswith("herdr-fold")])
        self.script("uninstall.sh")
        self.assertEqual(self.left(), [])

    def test_an_update_from_the_last_release(self):
        """The last release (main) installed as its own installer does, then this version over it as a person
        updates (Enter to every question): nothing left that this version does not put there, nothing after it goes."""
        released = os.path.join(self.tmp, "released")
        os.makedirs(released)
        ref = "origin/main"
        known = subprocess.run(["git", "-C", PACKAGE, "rev-parse", "--verify", "--quiet", ref], capture_output=True)
        if known.returncode:
            # a runner's checkout has this branch alone, and only its last commit: a fetch there makes no clone shallow
            fetched = subprocess.run(["git", "-C", PACKAGE, "fetch", "--depth", "1", "origin", "main"],
                                     capture_output=True, text=True, timeout=300)
            self.assertEqual(fetched.returncode, 0, fetched.stderr)
            ref = "FETCH_HEAD"
        archive = subprocess.run(["git", "-C", PACKAGE, "archive", ref], capture_output=True, timeout=300)
        self.assertEqual(archive.returncode, 0, archive.stderr)
        subprocess.run(["tar", "-x", "-C", released], input=archive.stdout, check=True)
        self.script("install.sh", released, HERDR_FOLD_NO_MACHINES="1")
        env = {key: value for key, value in self.env.items() if key != "HERDR_FOLD_YES"}
        shown, ended = run_in_terminal(["/bin/bash", os.path.join(self.package, "install.sh")],
                                       {**env, "HERDR_FOLD_NO_MACHINES": "1"}, lambda line: "", timeout=1500)
        self.assertTrue(ended, shown[-3000:])
        with open(os.path.join(self.home, ".local", "state", "herdr-fold", "installed.txt")) as f:
            recorded = set(f.read().split())
        fold = os.path.join(self.home, ".config", "herdr-fold")
        own = {"machines.txt", "statusline.json", "setup-folder", "private-words.txt"}       # this Mac's, not files
        stale = [rel for rel in (os.path.relpath(os.path.join(folder, name), self.home)
                                 for folder, _dirs, files in os.walk(fold) for name in files)
                 if rel not in recorded and os.path.basename(rel) not in own and "__pycache__" not in rel]
        self.assertEqual(stale, [], shown[-3000:])
        self.script("uninstall.sh")
        self.assertEqual(self.left(), [])


if __name__ == "__main__":
    unittest.main()
