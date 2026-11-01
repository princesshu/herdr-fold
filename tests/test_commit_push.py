"""Tests for commit_push.py (Cmd+Shift+C): the writer's problems in the catalog's words, a crashing worker reported,
secret-like files (staged ones too) named before the commit, folder and remote names shown without escape codes.
"""
import contextlib
import importlib.util
import io
import json
import os
import pty
import re
import select
import shutil
import subprocess
import tempfile
import time
import unittest

from support import catalog_text, set_env, stubs

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "commit_push.py")


def load():
    spec = importlib.util.spec_from_file_location("commit_push", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CommitPush(unittest.TestCase):
    def setUp(self):
        self.module = load()

    def test_problems_are_worded_from_the_catalog(self):
        cm = self.module.commit_message
        self.assertEqual(self.module.describe(cm.Problem("claude", "missing")),
                         "claude: " + catalog_text("commit.problem_missing"))
        self.assertEqual(self.module.describe(cm.Problem("codex", "foreign", "secret,email")),
                         "codex: " + catalog_text("commit.problem_foreign", catalog_text("commit.foreign_secret") + ", "
                                                  + catalog_text("commit.foreign_email")))

    def test_a_crashing_worker_reaches_the_caller(self):
        with self.assertRaises(ZeroDivisionError):
            self.module.with_spinner("working", lambda: 1 / 0)

    def test_a_secret_inside_a_new_folder_is_listed_and_named(self):
        repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, repo)
        # this machine's global git settings (an excludes file that hides .env) must not change the answer
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull)
        subprocess.run(["git", "init", "-q", repo], check=True)
        os.makedirs(os.path.join(repo, "deploy"))
        with open(os.path.join(repo, "deploy", ".env"), "w") as f:
            f.write("TOKEN=x\n")
        lines = self.module.status_lines(repo)
        self.assertIn("?? deploy/.env", lines)
        self.assertEqual(self.module.sensitive(lines), ["deploy/.env"])

    def test_the_full_list_is_shown_before_committing_everything(self):
        lines = [f"?? file{n}.txt" for n in range(30)]
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.module.show_files("Changes:", lines, full=True)
        self.assertIn("file29.txt", out.getvalue())
        self.assertNotIn("more", out.getvalue())

    def test_a_file_lines_up_the_same_from_either_git_list(self):
        self.assertEqual(self.module.file_row("M\tapp.py"), "M  app.py")
        self.assertEqual(self.module.file_row("R100\told.py\tnew.py"), "R  old.py → new.py")
        self.assertEqual(self.module.file_row(" M app.py"), " M app.py")

    def test_secret_looking_files_are_named(self):
        lines = ["?? .env", " M app.py", "?? config/prod.pem", "?? id_ed25519", "?? notes/credentials.json",
                 "R  old.txt -> keys/server.key", "?? src/environment.ts", "A\tdeploy/.env.prod",
                 "R100\tkeys.txt\tkeys/client.p12", "M\tsrc/app.py"]
        self.assertEqual(self.module.sensitive(lines),
                         [".env", "config/prod.pem", "id_ed25519", "notes/credentials.json", "keys/server.key",
                          "deploy/.env.prod", "keys/client.p12"])


# a stand-in Claude: one detailed message, whatever it is asked
CLAUDE = """#!/bin/sh
cat > /dev/null
printf 'feat: greet by name\\n\\n- Take the name to greet as an argument\\n- Return the greeting instead\\n'
"""


class Popup(unittest.TestCase):
    """The window itself, in a terminal: a repository with a staged change and a local remote, a stand-in Claude."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        remote, self.repo = os.path.join(self.tmp, "remote.git"), os.path.join(self.tmp, "demo")
        fakes = stubs(os.path.join(self.tmp, "bin"), {"claude": CLAUDE})
        self.env = {"HOME": self.tmp, "PATH": f"{fakes}:/usr/bin:/bin", "TERM": "xterm-256color",
                    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_NAME": "dev", "GIT_AUTHOR_EMAIL": "dev@example.com",
                    "GIT_COMMITTER_NAME": "dev", "GIT_COMMITTER_EMAIL": "dev@example.com",
                    "HERDR_ACTIVE_PANE_CWD": self.repo, "HERDR_COMMIT_AI": "claude", "PYTHONDONTWRITEBYTECODE": "1"}
        run = lambda *args, cwd=None: subprocess.run(["git", *args], cwd=cwd, env=self.env, check=True,  # noqa: E731
                                                     capture_output=True)
        run("init", "-q", "--bare", "-b", "main", remote)
        os.makedirs(self.repo)
        for args in (["init", "-q", "-b", "main"], ["commit", "-q", "--allow-empty", "-m", "start"],
                     ["remote", "add", "origin", remote], ["push", "-q", "-u", "origin", "main"]):
            run(*args, cwd=self.repo)
        with open(os.path.join(self.repo, "app.py"), "w") as f:
            f.write("print('hi')\n")
        run("add", "app.py", cwd=self.repo)

    def screen(self, answer=None, at="commit.secrets_ask"):
        """What the window shows once its message is accepted with Enter (and a failure is closed with a key): one line
        per row, as the terminal draws. ANSWER (bytes) is typed at the question AT (a catalog key)."""
        master, slave = pty.openpty()
        proc = subprocess.Popen(["/usr/bin/python3", "-B", SCRIPT], stdin=slave, stdout=slave, stderr=slave,
                                env=self.env, start_new_session=True)
        os.close(slave)
        out, sent, closed, deadline = b"", False, False, time.monotonic() + 60
        any_key = catalog_text("lib.press_any_key").encode()
        question = catalog_text(at).encode()
        while time.monotonic() < deadline and proc.poll() is None:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    out += os.read(master, 65536)
                except OSError:
                    break
            if answer is not None and question in out:
                time.sleep(0.3)
                os.write(master, answer)
                answer = None
            if not sent and b"greet by name" in out:
                time.sleep(0.3)
                os.write(master, b"\r")
                sent = True
            if not closed and any_key in out:
                os.write(master, b"q")
                closed = True
        proc.wait(10)
        os.close(master)
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", out.decode("utf-8", "replace")).replace("\r\n", "\n")
        return [line.split("\r")[-1].rstrip() for line in text.split("\n")]

    def test_the_window_is_spaced_and_lined_up(self):
        rows = self.screen()
        self.assertIn("  A  app.py", rows)                                  # a space, not a tab, after the letter
        self.assertFalse([row for row in rows if "\t" in row])
        message = next(i for i, row in enumerate(rows) if row.startswith("Message ("))
        self.assertEqual(rows[message - 1], "")
        done = next(i for i, row in enumerate(rows) if catalog_text("commit.done", "") in row)
        self.assertEqual(rows[done - 1], "")


    def test_a_folders_name_shows_without_its_escape_codes(self):
        # a downloaded repository's folder may be named with escape codes that set the title or the clipboard
        named = os.path.join(self.tmp, "demo\x1b]2;owned\x07")
        os.rename(self.repo, named)
        self.env["HERDR_ACTIVE_PANE_CWD"] = named
        shown = "\n".join(self.screen())
        self.assertNotIn("\x1b]", shown)
        self.assertNotIn("\x07", shown)

    def test_what_the_remote_says_shows_without_its_escape_codes(self):
        # a remote's hook may answer a push with escape codes that set the title or the clipboard; git passes them on
        hook = os.path.join(self.tmp, "remote.git", "hooks", "pre-receive")
        with open(hook, "w") as f:
            f.write("#!/bin/sh\nprintf '\\033]2;owned\\007 not here\\n' >&2\nexit 1\n")
        os.chmod(hook, 0o755)
        shown = "\n".join(self.screen())
        self.assertIn("not here", shown)
        self.assertNotIn("\x1b]", shown)
        self.assertNotIn("\x07", shown)
        self.assertNotIn(catalog_text("commit.pull_first"), shown)          # declined by a hook, not behind

    def stage(self, name, text):
        with open(os.path.join(self.repo, name), "w") as f:
            f.write(text)
        subprocess.run(["git", "-C", self.repo, "add", name], env=self.env, check=True)

    def committed(self):
        return subprocess.run(["git", "-C", self.repo, "show", "--name-only", "--format=", "HEAD"], env=self.env,
                              capture_output=True, text=True).stdout.split()

    def test_a_staged_secret_is_named_and_committed_only_when_confirmed(self):
        self.stage(".env", "TOKEN=x\n")
        rows = self.screen(answer=b"q")
        warned = next(i for i, row in enumerate(rows) if catalog_text("commit.secrets") in row)
        self.assertEqual(rows[warned + 1], "  .env")
        self.assertEqual(self.committed(), [])                              # canceled: nothing committed
        self.screen(answer=b"\r")
        self.assertEqual(sorted(self.committed()), [".env", "app.py"])

    def test_a_staged_secret_is_named_with_the_changes_not_staged(self):
        self.stage(".env", "TOKEN=x\n")
        with open(os.path.join(self.repo, "README.md"), "w") as f:
            f.write("demo\n")
        rows = self.screen(answer=b"q", at="commit.include_ask")
        warned = next(i for i, row in enumerate(rows) if catalog_text("commit.secrets") in row)
        self.assertEqual(rows[warned + 1:warned + 3], ["  .env", ""])     # README.md is no secret
        self.assertEqual(self.committed(), [])

    def test_the_message_closes_the_issue_linked_in_the_sidebar(self):
        top = subprocess.run(["git", "-C", self.repo, "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                             env=self.env).stdout.strip()
        state = os.path.join(self.tmp, ".local", "state", "herdr", "plugins", "herdr-fold.sidebar")
        os.makedirs(state)
        with open(os.path.join(state, "settings.json"), "w") as f:
            json.dump({"linked": {top: [7, "The greeting is rude"]}}, f)
        rows = self.screen()
        self.assertIn("  Fixes #7", rows)                                    # shown before Enter commits it
        log = subprocess.run(["git", "-C", self.repo, "log", "-1", "--format=%B"], capture_output=True, text=True,
                             env=self.env)
        self.assertTrue(log.stdout.rstrip().endswith("Fixes #7"), log.stdout)

if __name__ == "__main__":
    unittest.main()
