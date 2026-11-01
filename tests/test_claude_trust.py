"""Tests for claude_trust.py: `list` names the untrusted git roots of herdr's Claude panes, `trust` marks them in
~/.claude.json and changes nothing else; never home, /, a folder above home or one outside git. Fake herdr, temp HOME.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from support import catalog_text, set_env


SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "claude_trust.py")


class ClaudeTrust(unittest.TestCase):
    def setUp(self):
        self.home = os.path.realpath(tempfile.mkdtemp())
        self.repo = os.path.join(self.home, "Documents", "repo")
        self.sub = os.path.join(self.repo, "src")              # a Claude started inside the repo: its root counts
        self.trusted = os.path.join(self.home, "Documents", "trusted")
        self.plain = os.path.join(self.home, "Downloads")       # not a git repo: never offered
        for d in (self.sub, self.trusted, self.plain):
            os.makedirs(d)
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.config = {"numStartups": 7, "projects": {self.trusted: {"hasTrustDialogAccepted": True, "x": 1},
                                                      "/": {"hasTrustDialogAccepted": True}}}
        with open(os.path.join(self.home, ".claude.json"), "w") as f:
            json.dump(self.config, f)
        agents = [{"pane_id": "w1:p1", "agent": "claude", "cwd": self.sub},
                  {"pane_id": "w2:p1", "agent": "claude", "cwd": self.trusted},
                  {"pane_id": "w3:p1", "agent": "claude", "cwd": self.plain},
                  {"pane_id": "w4:p1", "agent": "codex", "cwd": self.home},   # not Claude: not its business
                  {"pane_id": "w5:p1", "agent": "claude", "cwd": self.home},   # home, and above it: never
                  {"pane_id": "w6:p1", "agent": "claude", "cwd": os.path.dirname(self.home)}]
        self.herdr = os.path.join(self.home, "herdr")
        self.agents = agents
        self.write_herdr()

    def write_herdr(self):
        with open(self.herdr, "w") as f:
            f.write("#!/bin/sh\ncat <<'JSON'\n" + json.dumps({"result": {"agents": self.agents}}) + "\nJSON\n")
        os.chmod(self.herdr, 0o755)

    def add_pane(self, cwd):
        self.agents.append({"pane_id": f"w{len(self.agents) + 1}:p1", "agent": "claude", "cwd": cwd})
        self.write_herdr()

    def tearDown(self):
        shutil.rmtree(self.home)

    def run_script(self, command, folders=()):
        return subprocess.run(["/usr/bin/python3", SCRIPT, command], capture_output=True, text=True, timeout=30,
                              input="".join(f + "\n" for f in folders),
                              env={"HOME": self.home, "HERDR_BIN_PATH": self.herdr, "PATH": "/usr/bin:/bin"})

    def test_lists_the_untrusted_git_roots_of_claude_panes(self):
        self.assertEqual(self.run_script("list").stdout.splitlines(), [self.repo])

    def test_trust_marks_them_and_keeps_everything_else(self):
        self.assertEqual(self.run_script("trust", [self.repo]).returncode, 0)
        with open(os.path.join(self.home, ".claude.json")) as f:
            config = json.load(f)
        self.assertEqual(config["numStartups"], 7)
        self.assertEqual(config["projects"][self.trusted], {"hasTrustDialogAccepted": True, "x": 1})
        self.assertTrue(config["projects"][self.repo]["hasTrustDialogAccepted"])
        self.assertEqual(self.run_script("list").stdout, "")

    def test_only_the_folders_shown_are_trusted(self):
        # one that became untrusted while the question was open is not among them: it is left for the next time
        other = os.path.join(self.home, "Documents", "other")
        subprocess.run(["git", "init", "-q", other], check=True)
        self.add_pane(other)
        self.assertEqual(self.run_script("trust", [other]).returncode, 0)
        with open(os.path.join(self.home, ".claude.json")) as f:
            projects = json.load(f)["projects"]
        self.assertTrue(projects[other]["hasTrustDialogAccepted"])
        self.assertNotIn(self.repo, projects)

    def test_a_folder_outside_a_git_repo_is_never_trusted(self):
        # a trusted one would vouch for every folder under it that is not in a git repo, a downloaded one too
        self.assertEqual(self.run_script("trust", [self.plain]).returncode, 0)
        with open(os.path.join(self.home, ".claude.json")) as f:
            self.assertNotIn(self.plain, json.load(f)["projects"])

    def test_home_and_the_folders_above_it_are_never_trusted(self):
        # Claude keeps the home folder's trust for one session only; outside a git repo it counts a trusted parent,
        # so a trusted home (or /) would vouch for every folder under it, a downloaded one too
        wide = [self.home, os.path.dirname(self.home), os.sep]
        self.assertEqual(self.run_script("trust", wide).returncode, 0)
        with open(os.path.join(self.home, ".claude.json")) as f:
            projects = json.load(f)["projects"]
        self.assertNotIn(self.home, projects)
        self.assertNotIn(os.path.dirname(self.home), projects)
        self.assertEqual(projects["/"], {"hasTrustDialogAccepted": True})      # theirs, left as it was

    def test_the_project_is_the_nearest_folder_with_a_git_folder(self):
        # as Claude finds it: a downloaded .git/config pointing its work tree elsewhere does not move the project
        subprocess.run(["git", "-C", self.repo, "config", "core.worktree", self.home], check=True)
        self.assertEqual(self.run_script("list").stdout.splitlines(), [self.repo])

    def test_an_unreadable_config_is_never_overwritten(self):
        path = os.path.join(self.home, ".claude.json")
        with open(path, "w") as f:
            f.write('{"numStartups": 7, "projects": {')          # half-written by a running Claude
        done = self.run_script("trust", [self.repo])
        self.assertEqual(done.returncode, 1)
        self.assertEqual(done.stdout.strip(), catalog_text("trust.unreadable", "~/.claude.json"))
        with open(path) as f:
            self.assertEqual(f.read(), '{"numStartups": 7, "projects": {')

    def test_a_config_changed_while_trusting_is_left_alone(self):
        set_env(self, HOME=self.home)
        spec = importlib.util.spec_from_file_location("claude_trust", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        path = os.path.join(self.home, ".claude.json")
        original = module.load

        def load_then_claude_writes(*args, **kwargs):
            config = original(*args, **kwargs)
            with open(path, "w") as f:                            # Claude saves meanwhile
                json.dump({"numStartups": 8, "projects": {}, "padding": "x" * 50}, f)
            return config
        module.load = load_then_claude_writes
        with self.assertRaises(module.TrustError):
            module.trust([self.repo])
        with open(path) as f:
            self.assertEqual(json.load(f)["numStartups"], 8)
        self.assertEqual([n for n in os.listdir(self.home) if n.startswith(".claude.json.")], [])

    def test_nothing_to_do_without_herdr(self):
        os.remove(self.herdr)
        done = self.run_script("list")
        self.assertEqual((done.returncode, done.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
