"""Tests for the commit message writer (core/commit_message.py: the sidebar's, Cmd+Shift+C's and the Herdr app mod's):
fallback models, a detailed body, nothing private or from secret-like files, tool-less AIs run outside the pane."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import PACKAGE, set_attrs, set_env, stubs, trap

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import commit_message as cm  # noqa: E402

GOOD = "feat: add a and b\n\n- Add a.txt\n- Add b.txt"
SHORT = "feat: add files"
# a fake AI: answers its n-th call with the n-th line of $ANSWERS ("|" for a line break), Codex-style into the file
# after -o, Claude-style on stdout; logs its arguments, the memory switches and HERDR_PANE_ID; an empty answer fails
FAKE = """#!/bin/sh
n=$(cat "$LOG.count" 2>/dev/null || echo 0); n=$((n + 1)); echo $n > "$LOG.count"
for a in "$@"; do printf '[%s]' "$(printf '%s' "$a" | tr '\\n' ' ')"; done >> "$LOG"
printf ' NO_CLAUDE_MD=%s' "${CLAUDE_CODE_DISABLE_CLAUDE_MDS:-0}" >> "$LOG"
printf ' NO_MEMORY=%s' "${CLAUDE_CODE_DISABLE_AUTO_MEMORY:-0}" >> "$LOG"
echo " PANE=${HERDR_PANE_ID:-none}" >> "$LOG"
answer=$(sed -n "${n}p" "$ANSWERS" | tr '|' '\\n')
out=; prev=; for a in "$@"; do [ "$prev" = -o ] && out=$a; prev=$a; done
if [ -n "$out" ]; then printf '%s\\n' "$answer" > "$out"; else printf '%s\\n' "$answer"; fi
[ -n "$answer" ]
"""


class Writer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.bin = stubs(os.path.join(self.tmp, "bin"), {"claude": FAKE, "codex": FAKE})
        self.log, self.answers = os.path.join(self.tmp, "log"), os.path.join(self.tmp, "answers")
        set_env(self, LOG=self.log, ANSWERS=self.answers, HERDR_PANE_ID="w1:p1", HERDR_COMMIT_AI=None)
        self.req = cm.Request(diff="+a\n+b\n", files=["a.txt", "b.txt"], subjects="", rules=None, rules_from=None)

    def answers_are(self, *answers):
        with open(self.answers, "w") as f:
            f.write("".join(answer.replace("\n", "|") + "\n" for answer in answers))
        if os.path.exists(self.log + ".count"):
            os.remove(self.log + ".count")

    def which(self, name):
        return os.path.join(self.bin, name)

    def calls(self):
        with open(self.log) as f:
            return f.read().splitlines()

    def write(self, order=None):
        return cm.write(self.req, order=order, which=self.which)

    def test_a_detailed_message_is_taken(self):
        self.answers_are(GOOD)
        suggestion = self.write()
        self.assertEqual((suggestion.message, suggestion.backend), (GOOD, "claude"))

    def test_a_squashed_message_is_asked_for_again_once(self):
        self.answers_are(SHORT, GOOD)
        self.assertEqual(self.write().message, GOOD)
        self.assertEqual(len(self.calls()), 2)
        self.assertIn("too short", self.calls()[1])

    def test_still_short_then_the_other_ai(self):
        self.answers_are(SHORT, SHORT, GOOD)
        suggestion = self.write()
        self.assertEqual((suggestion.message, suggestion.backend), (GOOD, "codex"))
        self.assertIn(cm.Problem("claude", "short"), suggestion.problems)

    def test_small_models_and_codex_falls_back_to_its_own(self):
        self.answers_are("", GOOD)                                      # the small model fails, Codex's own works
        self.write(order=["codex"])
        first, second = self.calls()
        self.assertIn("[-m][gpt-6-luna]", first)
        self.assertIn('[-c][model_reasoning_effort="low"]', first)
        self.assertNotIn("[-m]", second)
        self.answers_are(GOOD)
        self.write(order=["claude"])
        self.assertIn("[--model][haiku]", self.calls()[-1])

    def test_claude_runs_without_tools_or_mcp_servers(self):
        self.answers_are(GOOD)
        self.write(order=["claude"])
        self.assertIn("[--tools][]", self.calls()[0])
        self.assertIn("[--strict-mcp-config]", self.calls()[0])

    def test_claude_has_none_of_the_users_instructions_memories_or_hooks(self):
        """A diff can carry instructions: Claude must hold nothing private it could copy into the message."""
        self.answers_are(GOOD)
        self.write(order=["claude"])
        self.assertIn("[--setting-sources][]", self.calls()[0])
        self.assertIn("NO_CLAUDE_MD=1 NO_MEMORY=1", self.calls()[0])

    def test_codex_has_no_tool_to_read_or_send_anything(self):
        """A diff can carry instructions: Codex, its own model too, runs with no shell, no image reading, no apps,
        plugins or browser, no web search, no MCP servers and no memories."""
        self.answers_are("", GOOD)
        self.write(order=["codex"])
        for call in self.calls():
            for feature in ("shell_tool", "view_image", "apps", "plugins", "browser_use", "in_app_browser",
                            "computer_use", "memories"):
                self.assertIn(f"[--disable][{feature}]", call)
            self.assertIn('[-c][web_search="disabled"]', call)
            self.assertIn("[-c][mcp_servers={}]", call)

    def test_the_agents_do_not_run_as_the_pane(self):
        self.answers_are(SHORT, GOOD)
        self.write()
        self.assertTrue(all(call.endswith("PANE=none") for call in self.calls()))

    def test_something_private_the_changes_do_not_hold_goes_to_the_other_ai(self):
        self.answers_are("feat: add a\n\n- Add a.txt for someone@mail.example\n- Add b.txt", GOOD)
        suggestion = self.write()
        self.assertEqual(suggestion.message, GOOD)
        self.assertIn(cm.Problem("claude", "foreign", "email"), suggestion.problems)

    def test_one_file_may_have_a_subject_only(self):
        self.answers_are("fix: correct a typo")
        self.req = cm.Request("+x\n", ["a.txt"], "", None, None)
        self.assertEqual(self.write().message, "fix: correct a typo")

    def test_nothing_works_and_nothing_crashes(self):
        self.answers_are("", "", "", "")
        suggestion = self.write()
        self.assertIsNone(suggestion.message)
        self.assertEqual({p.backend for p in suggestion.problems}, {"claude", "codex"})
        missing = cm.write(self.req, which=lambda name: None)
        self.assertEqual(missing.problems, [cm.Problem("claude", "missing"), cm.Problem("codex", "missing")])

    def test_only_the_chosen_ai(self):
        set_env(self, HERDR_COMMIT_AI="codex")
        self.answers_are(GOOD)
        self.assertEqual(self.write().backend, "codex")


class Rules(unittest.TestCase):
    def test_the_message_shape(self):
        self.assertTrue(cm.well_formed(GOOD, 2))
        self.assertFalse(cm.well_formed(SHORT, 2))
        self.assertTrue(cm.well_formed(SHORT, 1))
        self.assertFalse(cm.well_formed("feat: " + "x" * 80 + "\n\n- a", 2))

    def test_a_message_keeps_no_control_characters(self):
        # a diff can carry escape codes and ask the model to repeat them: none reaches the window or the commit
        message = cm.clean("feat: \x1b]52;c;ZXZpbA==\x07greet\r\n\n- One\x1b[2J\x9b2J\x7f\n- Two\tcolumns")
        self.assertEqual([ch for ch in message if not ch.isprintable() and ch not in "\n\t"], [])
        self.assertTrue(message.startswith("feat: ") and "- Two\tcolumns" in message)

    def test_private_text_only_when_the_changes_hold_it_too(self):
        self.assertEqual(cm.foreign("- Add dev@example.com as the contact", "+contact: dev@example.com"), [])
        self.assertEqual(cm.foreign("- Fix /Us" + "ers/someone/app and 192.0.2.10", "+x"), ["home", "ip"])

    def test_a_private_name_or_a_tailnet_only_when_the_changes_hold_it_too(self):
        # this machine's names and its owner's (Codex reads ~/.codex/AGENTS.md, which may hold them), a tailnet's
        set_attrs(self, cm, own_names=lambda: {cm.fold("Kovács Ilka"), "ana"})
        self.assertEqual(cm.foreign("- Thank kovacs ilka for the review", "+x"), ["name"])
        self.assertEqual(cm.foreign("- Credit Kovács Ilka", "+author: Kovács Ilka"), [])
        self.assertEqual(cm.foreign("- Add the banana icon", "+x"), [])                 # a short word, whole only
        self.assertEqual(cm.foreign("- Point it at box.tail0000.ts.net", "+x"), ["tailnet"])


class Context(unittest.TestCase):
    def test_a_repositorys_config_cannot_make_git_read_the_sidebars_terminal(self):
        # [include] path = /dev/stdin in a downloaded folder: git would read the sidebar's keys, for good
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull)
        subprocess.run(["git", "-C", root, "init", "-q"], check=True)
        subprocess.run(["git", "-C", root, "config", "include.path", "/dev/stdin"], check=True)
        code = (f"import sys; sys.path.insert(0, {os.path.join(PACKAGE, 'core')!r}); "
                f"import commit_message; print(repr(commit_message.git({root!r}, 'status', '--short')))")
        proc = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True)                   # its input kept open
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            self.fail("git waited on the input")
        finally:
            proc.stdin.close()
        self.assertEqual(proc.stdout.read().strip(), "''")
        proc.stdout.close()

    def test_only_what_is_staged_and_never_an_ignored_file(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull)
        git = ["git", "-C", root, "-c", "user.name=dev", "-c", "user.email=dev@example.com"]
        subprocess.run(git + ["init", "-q"], check=True)
        for name, text in ((".gitignore", "notes.local\n"), ("notes.local", "private\n"), ("a.txt", "a\n"),
                           ("b.txt", "b\n")):
            with open(os.path.join(root, name), "w") as f:
                f.write(text)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["rm", "-q", "--cached", "--", "b.txt"], check=True)
        req = cm.request(root)
        self.assertEqual(sorted(req.files), [".gitignore", "a.txt"])
        self.assertNotIn("+private", req.diff)
        self.assertNotIn("b.txt", req.diff)

    def test_a_staged_file_named_like_a_secret_is_named_but_not_read(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull)
        git = ["git", "-C", root, "-c", "user.name=dev", "-c", "user.email=dev@example.com"]
        subprocess.run(git + ["init", "-q"], check=True)
        os.makedirs(os.path.join(root, "deploy"))
        for name, text in (("deploy/.env", "TOKEN=hunter2\n"), ("server.key", "PRIVATE\n"), ("a.txt", "a\n")):
            with open(os.path.join(root, name), "w") as f:
                f.write(text)
        subprocess.run(git + ["add", "-A"], check=True)
        req = cm.request(os.path.join(root, "deploy"))                    # from a folder inside, as a pane may be
        self.assertEqual(sorted(req.files), ["a.txt", "deploy/.env", "server.key"])
        self.assertIn("+a", req.diff)
        self.assertNotIn("hunter2", req.diff)
        self.assertNotIn("PRIVATE", req.diff)
        self.assertIn("deploy/.env, server.key", req.diff)                 # the AI is told why they show no change

    def test_the_users_diff_settings_do_not_change_what_the_ai_reads(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull)
        external = os.path.join(root, "external.sh")
        with open(external, "w") as f:
            f.write("#!/bin/sh\necho EXTERNAL\n")
        os.chmod(external, 0o755)
        git = ["git", "-C", root, "-c", "user.name=dev", "-c", "user.email=dev@example.com"]
        subprocess.run(git + ["init", "-q"], check=True)
        for key, value in (("color.ui", "always"), ("diff.external", external)):
            subprocess.run(git + ["config", key, value], check=True)
        with open(os.path.join(root, "a.txt"), "w") as f:
            f.write("a\n")
        subprocess.run(git + ["add", "a.txt"], check=True)
        diff = cm.request(root).diff
        self.assertIn("+a", diff)
        self.assertNotIn("EXTERNAL", diff)
        self.assertNotIn("\x1b[", diff)


    def test_a_downloaded_folders_programs_do_not_run_while_the_message_is_written(self):
        """What the AI reads is gathered from git: a folder's own fsmonitor and text conversion never run then."""
        root, programs = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        self.addCleanup(shutil.rmtree, programs)
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull)
        git = ["git", "-C", root, "-c", "user.name=dev", "-c", "user.email=dev@example.com"]
        subprocess.run(git + ["init", "-q"], check=True)
        for name, text in ((".gitattributes", "* diff=conv\n"), ("a.txt", "a\n")):
            with open(os.path.join(root, name), "w") as f:
                f.write(text)
        subprocess.run(git + ["add", "-A"], check=True)
        marks = [trap(root, key, programs) for key in ("core.fsmonitor", "diff.conv.textconv")]
        self.assertIn("+a", cm.request(root).diff)
        self.assertEqual([os.path.basename(m) for m in marks if os.path.exists(m)], [])


class CommandLine(unittest.TestCase):
    """The writer for herdr-fold's Herdr app mod: `python3 commit_message.py REPO` answers in JSON, on the machine the
    repository is on."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home, self.repo = os.path.join(self.tmp, "home"), os.path.join(self.tmp, "app")
        self.bin = stubs(os.path.join(self.tmp, "bin"), {"claude": FAKE})
        self.answers = os.path.join(self.tmp, "answers")
        os.makedirs(self.home)
        os.makedirs(self.repo)
        git = ["git", "-C", self.repo, "-c", "user.name=dev", "-c", "user.email=dev@example.com"]
        subprocess.run(git + ["init", "-q"], check=True, env={"GIT_CONFIG_GLOBAL": os.devnull, "PATH": "/usr/bin:/bin"})
        for name in ("a.txt", "b.txt", ".env"):
            with open(os.path.join(self.repo, name), "w") as f:
                f.write(name + "\n")
        subprocess.run(git + ["add", "-A"], check=True, env={"GIT_CONFIG_GLOBAL": os.devnull, "PATH": "/usr/bin:/bin"})

    def answer(self, path, *answers):
        with open(self.answers, "w") as f:
            f.write("\n".join(answers) + "\n")
        out = subprocess.run([sys.executable, "-B", cm.__file__, self.repo], capture_output=True, text=True, env={
            "HOME": self.home, "PATH": f"{path}:/usr/bin:/bin", "GIT_CONFIG_GLOBAL": os.devnull,
            "LOG": os.path.join(self.tmp, "log"), "ANSWERS": self.answers}, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_the_message_its_writer_and_the_files_named_like_secrets(self):
        result = self.answer(self.bin, GOOD.replace("\n", "|"))
        self.assertEqual((result["message"], result["backend"], result["problems"]), (GOOD, "claude", []))
        self.assertEqual(sorted(result["files"]), [".env", "a.txt", "b.txt"])
        self.assertEqual(result["secret_looking"], [".env"])

    def test_the_issue_linked_in_the_sidebar_closes_with_it(self):
        state = os.path.join(self.home, ".local", "state", "herdr", "plugins", "herdr-fold.sidebar")
        os.makedirs(state)
        with open(os.path.join(state, "settings.json"), "w") as f:
            json.dump({"linked": {self.repo: [42, "Login fails"]}}, f)
        self.assertTrue(self.answer(self.bin, GOOD.replace("\n", "|"))["message"].endswith("\n\nFixes #42"))

    def test_without_an_ai_it_says_why(self):
        result = self.answer(os.path.join(self.tmp, "nothing"))
        self.assertIsNone(result["message"])
        self.assertEqual([(p["backend"], p["kind"]) for p in result["problems"]], [("claude", "missing"),
                                                                                   ("codex", "missing")])
        self.assertEqual(result["note"], "claude is not installed; codex is not installed")

    def test_the_problems_in_words(self):
        self.assertEqual(cm.explain([cm.Problem("claude", "failed", "rate limited"), cm.Problem("codex", "short")]),
                         "claude failed: rate limited; codex wrote too short a message, twice")


class Fixes(unittest.TestCase):
    """The line that closes an issue on GitHub, shared by the sidebar and the commit window."""

    def test_a_message_that_closes_the_issue_already(self):
        self.assertTrue(cm.fixes("fix: login\n\nCloses #42", 42))
        self.assertTrue(cm.fixes("fix: login\n\nresolves: #42", 42))
        self.assertFalse(cm.fixes("fix: login, see #42", 42))
        self.assertFalse(cm.fixes("fix: login\n\nFixes #420", 42))

    def test_the_line_goes_at_the_end_once(self):
        self.assertEqual(cm.with_fixes("feat: login\n\n- one\n", 42), "feat: login\n\n- one\n\nFixes #42")
        self.assertEqual(cm.with_fixes("feat: login\n\nFixes #42", 42), "feat: login\n\nFixes #42")
        self.assertEqual(cm.with_fixes("feat: login", None), "feat: login")

    def test_the_issue_linked_in_the_sidebar(self):
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state)
        self.assertIsNone(cm.linked_issue("/srv/app", state))                 # no settings yet
        with open(os.path.join(state, "settings.json"), "w") as f:
            f.write('{"linked": {"/srv/app": [42, "Login fails"], "/srv/other": "broken"}}')
        self.assertEqual(cm.linked_issue("/srv/app", state), (42, "Login fails"))
        self.assertIsNone(cm.linked_issue("/srv/other", state))
        self.assertIsNone(cm.linked_issue("/srv/none", state))

if __name__ == "__main__":
    unittest.main()
