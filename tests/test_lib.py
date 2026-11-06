"""Tests for lib/'s shell helpers: status lines (a mark column, color only on a terminal without NO_COLOR, summarize,
HERDR_FOLD_VERBOSE=1), the questions (in a pty; ask() in the language's letters) and the SSH Host * block.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from support import ANSI, PACKAGE, catalog_text, run_in_terminal

import i18n

LIB = os.path.join(PACKAGE, "lib", "common.sh")
REMOTE = "  -- apps (Linux-x86_64)\\n  [✓] git\\n  [✓] python3\\n  [!] starship not installed: no network\\n" \
         "  [✓] ~/.config/herdr-fold/sidebar.sh\\n  [-] codex not on this machine\\n" \
         "  [+] overwritten old files: ~/.local/state/herdr-fold/1\\n"


def sh(script, **env):
    return subprocess.run(["/bin/bash", "-c", f'. "{LIB}"; {script}'], capture_output=True, text=True, timeout=30,
                          env={"PATH": "/usr/bin:/bin", **env}).stdout


def in_terminal(script, answer=None, lib=LIB, keep_colors=False, **env):
    """bash -c '. lib/common.sh; SCRIPT' in a real terminal; answer(line) answers its questions."""
    shown, _ = run_in_terminal(["/bin/bash", "-c", f'. "{lib}"; {script}'],
                               {"PATH": "/usr/bin:/bin", "TERM": "xterm", **env}, answer or (lambda line: None),
                               timeout=20, idle=0.2, keep_colors=keep_colors)
    return shown


def ask(default, answer, lib=LIB, lang="en"):
    """ask() in a real terminal: Enter, or ANSWER and Enter, at its question."""
    return in_terminal(f'if ask "Go ahead?" {default}; then echo ANSWER=yes; else echo ANSWER=no; fi',
                       lambda line: answer if "Go ahead?" in line else None, lib=lib, HERDR_FOLD_LANG=lang)


class Parts(unittest.TestCase):
    """What each part gets (files.txt's, the Brewfile's own column): the Herdr app alone the shared files and programs,
    the TUI all of them."""

    def listed(self, function, *parts):
        return sh(f'DOT="{PACKAGE}"; {function} {" ".join(parts)}').splitlines()

    def test_the_app_alone_gets_the_shared_files(self):
        shared = {line.split("|")[1] for line in self.listed("package_files", "app")}
        self.assertIn(".config/herdr-fold/statusline.py", shared)
        self.assertIn(".config/herdr-fold/themes/apply.py", shared)
        self.assertNotIn(".config/ghostty/config", shared)
        self.assertEqual([rel for rel in shared if "/plugins/" in rel], [])
        self.assertEqual(self.listed("package_files", "tui"), self.listed("package_files"))

    def test_the_app_alone_gets_gh_and_ripgrep(self):
        self.assertEqual(self.listed("brew_lines", "app"), ["brew gh", "brew ripgrep"])
        self.assertIn("cask ghostty", self.listed("brew_lines", "tui", "app"))


class Summarize(unittest.TestCase):
    """The lines a remote machine prints come back through summarize: what needs attention keeps its own line, the done
    ones and the section headers fold into one line for the step."""

    def test_a_failed_step_is_not_summed_up_as_done(self):
        out = sh('printf "  [✓] git\\n" | summarize "apps and settings" 1')
        self.assertEqual(out, "  [!] apps and settings\n")

    def test_keeps_what_needs_attention_and_sums_up_the_rest(self):
        out = sh(f'printf "{REMOTE}" | summarize "apps and settings"')
        self.assertEqual(out, "  [!] starship not installed: no network\n"
                              "  [-] codex not on this machine\n"
                              "  [+] overwritten old files: ~/.local/state/herdr-fold/1\n"
                              "  [✓] apps and settings\n")

    def test_a_stop_on_the_machine_keeps_its_line_and_is_counted(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        count = os.path.join(tmp, "warnings")
        out = sh('printf "  [✗] no space left\\n" | summarize "apps and settings" 1', HERDR_FOLD_WARNINGS=count)
        self.assertIn("  [✗] no space left\n", out)
        with open(count) as f:
            self.assertEqual(len(f.read().splitlines()), 2)                 # the stop and the failed step

    def test_verbose_shows_every_line(self):
        out = sh(f'printf "{REMOTE}" | summarize "apps and settings"', HERDR_FOLD_VERBOSE="1")
        self.assertIn("  [✓] git", out)
        self.assertIn("  -- apps (Linux-x86_64)", out)
        self.assertIn("  [✓] apps and settings", out)


class Marks(unittest.TestCase):
    """Every status line: a bracketed mark in one column, the text after it; the notes line up under the text."""

    def test_every_mark_outside_a_terminal(self):
        out = sh('ok done; have there; warn careful; fail stopped; skip later; saved kept; note more')
        self.assertEqual(out, "  [✓] done\n  [✓] there\n  [!] careful\n  [✗] stopped\n  [-] later\n"
                              "  [+] kept\n      more\n")

    def test_in_a_terminal_the_bracket_is_dim_and_the_mark_colored(self):
        out = in_terminal('ok done; warn careful; fail stopped', keep_colors=True)
        self.assertIn("\x1b[32m✓", out)
        self.assertIn("\x1b[33m!", out)
        self.assertIn("\x1b[31m✗", out)
        self.assertIn("\x1b[2m[", out)
        self.assertIn("  [✓] done\n  [!] careful\n  [✗] stopped", ANSI.sub("", out))

    def test_no_color_turns_the_colors_off(self):
        self.assertNotIn("\x1b[", in_terminal('ok done', keep_colors=True, NO_COLOR="1").replace("\x1b[K", ""))

    def test_a_step_heading_has_no_codes_outside_a_terminal_or_with_no_color(self):
        self.assertEqual(sh('step "2/8 Apps"'), "\n== 2/8 Apps\n")
        plain = in_terminal('step "2/8 Apps"', keep_colors=True, NO_COLOR="1").replace("\x1b[K", "")
        self.assertNotIn("\x1b[", plain)
        self.assertIn("\x1b[1m== 2/8 Apps", in_terminal('step "2/8 Apps"', keep_colors=True))

    def test_fail_is_counted_like_a_warning(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        count = os.path.join(tmp, "warnings")
        sh('fail stopped; warn careful; ok fine', HERDR_FOLD_WARNINGS=count)
        with open(count) as f:
            self.assertEqual(f.read().splitlines(), ["stopped", "careful"])

    def test_a_python_line_shows_no_control_character_but_its_line_breaks_and_tabs(self):
        # a name from elsewhere (a machine's workspace, a remote's answer) may hold codes that set the title
        self.assertEqual(i18n.line("ok", "a\x1b]2;x\x07b\x9b\n\tc"), "  [✓] a?]2;x?b?\n\tc")

    def test_a_shell_line_shows_no_control_character_but_its_tabs(self):
        # what ssh or a remote machine says, a machine's name: codes that set the title or move the cursor show as ?
        evil = r"a\033]2;x\007b\r\tc"
        for helper in ("ok", "have", "warn", "fail", "skip", "saved", "note", "section"):
            out = sh(f'{helper} "$(printf "{evil}")"')
            self.assertNotIn("\x1b", out, helper)
            self.assertNotIn("\x07", out, helper)
            self.assertNotIn("\r", out, helper)
            self.assertTrue(out.rstrip("\n").endswith("a?]2;x?b?\tc"), (helper, out))
        out = sh(f'printf "  [✗] {evil}\\n  [+] {evil}\\nplain {evil}\\n" | summarize step')
        self.assertNotIn("\x1b", out)
        self.assertEqual(out.count("a?]2;x?b?\tc"), 3)

    def test_a_shell_line_shows_no_c1_control_but_keeps_its_letters(self):
        # a C1 control in UTF-8 (U+009B is CSI) works as an escape in some terminals; é, ©, a no-break space stay
        out = sh(r'ok "$(printf "a\302\23331mb \303\251\302\251\302\240.")"', LANG="en_US.UTF-8")
        self.assertEqual(out, "  [✓] a?31mb é©\u00a0.\n")

    def test_python_lines_match_the_installer_lines(self):
        for kind in ("ok", "have", "warn", "fail", "skip", "saved"):
            self.assertEqual(i18n.line(kind, "text") + "\n", sh(f"{kind} text"), kind)


class Ask(unittest.TestCase):
    def test_default_yes_shows_only_y_in_capitals(self):
        out = ask("y", "")
        self.assertIn("Go ahead? [Y/n] ", out)
        self.assertIn("ANSWER=yes", out)

    def test_default_no_shows_only_n_in_capitals(self):
        out = ask("n", "")
        self.assertIn("Go ahead? [y/N] ", out)
        self.assertIn("ANSWER=no", out)

    def test_y_means_yes(self):
        self.assertIn("ANSWER=yes", ask("n", "y"))

    def test_n_means_no(self):
        self.assertIn("ANSWER=no", ask("y", "n"))

    def test_yes_in_capitals_means_yes(self):
        self.assertIn("ANSWER=yes", ask("n", "YES"))


class QuestionsLineUp(unittest.TestCase):
    """Every question starts two columns in, as the status lines do; the catalog's texts bring no indent."""

    def lines(self, out, text):
        return [line for line in out.splitlines() if text in line]

    def test_ask_prompt_and_the_waits_start_two_columns_in(self):
        shown = {"Go ahead?": ask("y", ""),
                 "Name": in_terminal('prompt "Name" x >/dev/null', lambda line: "" if "Name" in line else None),
                 "Press Enter": in_terminal("wait_for_start", lambda line: "" if "Press Enter" in line else None),
                 "Press any key": in_terminal("wait_for_key", lambda line: "x" if "Press any key" in line else None)}
        for text, out in shown.items():
            self.assertEqual([line[:2 + len(text)] for line in self.lines(out, text)], ["  " + text], text)

    def test_no_question_in_the_catalog_brings_its_own_indent(self):
        used = set()
        for rel in ("install.sh", "machines.sh", "uninstall.sh", "lib/common.sh"):
            with open(os.path.join(PACKAGE, rel), encoding="utf-8") as f:
                used |= set(re.findall(r'\b(?:ask|prompt|wanted [\w.-]+) "\$\(t ([a-z0-9_.]+)', f.read()))
        used |= {"lib.press_enter_to_start", "lib.press_any_key"}
        self.assertEqual(sorted(key for key in used if catalog_text(key).startswith(" ")), [])


class RemoveMarked(unittest.TestCase):
    """A folder goes only with its mark in it, checked where nothing can swap it in after the check."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.dir = os.path.join(self.tmp, "kept")

    def remove(self):
        return sh(f'remove_marked "{self.dir}" .mark && echo GONE || echo KEPT').strip()

    def touch(self, folder, name):
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, name), "w"):
            pass

    def test_a_marked_folder_goes(self):
        self.touch(self.dir, ".mark")
        self.assertEqual(self.remove(), "GONE")
        self.assertEqual(os.listdir(self.tmp), [])

    def test_a_folder_without_the_mark_stays_where_it_was(self):
        self.touch(self.dir, "mine")
        self.assertEqual(self.remove(), "KEPT")
        self.assertEqual(os.listdir(self.tmp), ["kept"])
        self.assertEqual(os.listdir(self.dir), ["mine"])

    def test_a_link_to_a_marked_folder_stays(self):
        target = os.path.join(self.tmp, "elsewhere")
        self.touch(target, ".mark")
        os.symlink(target, self.dir)
        self.assertEqual(self.remove(), "KEPT")
        self.assertTrue(os.path.islink(self.dir))
        self.assertTrue(os.path.isfile(os.path.join(target, ".mark")))


class Progress(unittest.TestCase):
    def test_an_item_shows_in_the_mark_column(self):
        out = in_terminal("progress .config/x; progress_clear")
        self.assertIn("  […] .config/x", re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", out))


class AskInAnotherLanguage(unittest.TestCase):
    """The letters and the answers that mean yes come from the language file — here a made-up one: [J/n], j / ja."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        shutil.copytree(os.path.join(PACKAGE, "lib"), os.path.join(self.tmp, "lib"))    # its texts: ../src/lang
        os.makedirs(os.path.join(self.tmp, "src", "lang"))
        with open(os.path.join(self.tmp, "src", "lang", "xx.txt"), "w", encoding="utf-8") as f:
            f.write("lib.ask_default_yes = [J/n]\nlib.ask_default_no = [j/N]\nlib.yes_answers = j ja\n")
        self.lib = os.path.join(self.tmp, "lib", "common.sh")

    def test_prompt_shows_the_languages_letters(self):
        out = ask("y", "", self.lib, "xx")
        self.assertIn("Go ahead? [J/n] ", out)
        self.assertIn("ANSWER=yes", out)

    def test_the_languages_answers_mean_yes(self):
        self.assertIn("ANSWER=yes", ask("n", "j", self.lib, "xx"))
        self.assertIn("ANSWER=yes", ask("n", "Ja", self.lib, "xx"))

    def test_other_answers_mean_no(self):
        self.assertIn("ANSWER=no", ask("y", "n", self.lib, "xx"))
        self.assertIn("ANSWER=no", ask("y", "y", self.lib, "xx"))     # the English letter is not this language's yes


class WaitForStart(unittest.TestCase):
    """The installer's first line: Enter starts it, any other key ends it before anything changed. Not a yes/no
    question, so the first [Y/n] or [y/N] is a real decision's."""

    def start(self, key, **env):
        return in_terminal("if wait_for_start; then echo STARTED; else echo CANCELED; fi",
                           lambda line: key if "Press Enter to start" in line else None, **env)

    def test_enter_starts(self):
        out = self.start("")
        self.assertIn("Press Enter to start, any other key to cancel.", out)
        self.assertIn("STARTED", out)

    def test_any_other_key_cancels(self):
        for key in ("n", "y", " "):
            self.assertIn("CANCELED", self.start(key), repr(key))

    def test_no_wait_without_questions(self):
        out = self.start("", HERDR_FOLD_YES="1")
        self.assertNotIn("Press Enter", out)
        self.assertIn("STARTED", out)


class WaitForKey(unittest.TestCase):
    """The installer's last line: however it was started (a double-click in Finder opens it in Terminal or Ghostty,
    which close the window as soon as it ends), it waits for a key so the result can be read."""

    def test_waits_for_a_key_in_a_terminal(self):
        out = in_terminal("wait_for_key; echo GONE", lambda line: "x" if "Press any key" in line else None)
        self.assertIn("Press any key to exit.", out)
        self.assertIn("GONE", out)

    def test_no_wait_without_questions(self):
        out = in_terminal("wait_for_key; echo GONE", HERDR_FOLD_YES="1")
        self.assertNotIn("Press any key", out)
        self.assertIn("GONE", out)


class SshKey(unittest.TestCase):
    """The SSH key the installer makes: its comment names no one. The public key goes into every machine's
    authorized_keys and shows on screen; user@host would name the account and the Mac."""

    def test_the_keys_comment_names_no_one(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        bin_dir = os.path.join(home, "bin")
        os.makedirs(bin_dir)
        for name, body in (("ssh-keygen", 'echo "$@" > "$HOME/keygen-args"; touch "$HOME/.ssh/id_ed25519.pub"\n'),
                           ("ssh-add", "exit 0\n")):
            with open(os.path.join(bin_dir, name), "w") as f:
                f.write("#!/bin/sh\n" + body)
            os.chmod(os.path.join(bin_dir, name), 0o755)
        in_terminal("make_ssh_key", lambda line: "", HOME=home, PATH=f"{bin_dir}:/usr/bin:/bin")
        with open(os.path.join(home, "keygen-args")) as f:
            args = f.read().split()
        self.assertEqual(args[args.index("-C") + 1], "herdr-fold")


class SshConfig(unittest.TestCase):
    """The Host * block written with a new SSH key (lib/common.sh): once, and readable by any OpenSSH — Homebrew's does
    not know UseKeychain, so IgnoreUnknown comes first."""

    def test_the_block_works_with_any_openssh_and_is_written_once(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        for _ in range(2):
            sh("ssh_config_block", HOME=home)
        with open(os.path.join(home, ".ssh", "config")) as f:
            text = f.read()
        self.assertEqual(text.count("Host *"), 1)
        self.assertLess(text.index("IgnoreUnknown UseKeychain"), text.index("UseKeychain yes"))


class MarkedBlock(unittest.TestCase):
    """The marked block in a shell's settings file (lib/files.sh): the new text is made beside the file first, so a
    write cut short there (a full disk, here a file size limit) leaves the file as it was, and a file that then cannot
    take it keeps its text, the new one named beside it; a linked file stays a link, its target written."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        self.rc = os.path.join(self.home, ".zshrc")
        self.theirs = "".join(f"alias a{n}='echo {n}'\n" for n in range(200))          # some 4 KB of their own

    def write(self, path, text):
        with open(path, "w") as f:
            f.write(text)

    def read(self, path):
        with open(path) as f:
            return f.read()

    def test_a_write_cut_short_leaves_the_file_whole(self):
        self.write(self.rc, self.theirs)
        for call in ('marked_block "$HOME/.zshrc" "the block"', 'remove_marked_block "$HOME/.zshrc"'):
            if call.startswith("remove"):
                sh('marked_block "$HOME/.zshrc" "the block"', HOME=self.home)
                before = self.read(self.rc)
            else:
                before = self.theirs
            sh(f"ulimit -f 2; {call}", HOME=self.home)                              # 2 KB: less than the file
            self.assertEqual(self.read(self.rc), before, call)
            self.assertEqual(sorted(os.listdir(self.home)), [".zshrc"], call)       # no temporary file left

    def test_a_file_that_cannot_take_the_new_text_keeps_its_own_and_the_new_one_is_named(self):
        self.write(self.rc, self.theirs)
        os.chmod(self.rc, 0o444)
        out = sh('marked_block "$HOME/.zshrc" "the block"', HOME=self.home)
        self.assertEqual(self.read(self.rc), self.theirs)
        copies = [name for name in os.listdir(self.home) if name != ".zshrc"]
        self.assertEqual(len(copies), 1, out)
        self.assertEqual(self.read(os.path.join(self.home, copies[0])),
                         self.theirs + "\n# >>> herdr-fold >>>\nthe block\n# <<< herdr-fold <<<\n")
        self.assertIn(catalog_text("files.not_written", "~/.zshrc", "~/" + copies[0]), out)

    def test_a_linked_file_stays_a_link(self):
        target = os.path.join(self.home, "dotfiles-zshrc")
        self.write(target, self.theirs)
        os.symlink(target, self.rc)
        sh('marked_block "$HOME/.zshrc" "the block"', HOME=self.home)
        self.assertTrue(os.path.islink(self.rc))
        self.assertIn("the block", self.read(target))
        sh('remove_marked_block "$HOME/.zshrc"', HOME=self.home)
        self.assertTrue(os.path.islink(self.rc))
        self.assertEqual(self.read(target), self.theirs)


if __name__ == "__main__":
    unittest.main()
