"""Tests for install.sh: what an earlier install left but the package dropped goes (or the original comes back), three
dated backups stay, plus the GitHub step, zshrc line, in-herdr warning and AI-session guard. herdr, brew, open faked.
"""
import json
import os
import pathlib
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import unittest

from support import (DEFAULTS_STUB, GH_STUB, HERDR_STUB, PACKAGE, PackageHome, catalog_text, copy_package,
                     from_homebrew, run_in_terminal, stubs)


# herdr-sidebar as herdr lists it: it listens to tab.created too (its --ensure hook)
SIDEBAR = {"plugin_id": "herdr-sidebar", "version": "0.15.0", "events": [{"on": "tab.created"}], "plugin_root": ""}
# someone's own herdr settings: a key of theirs, and herdr-fold's key chord (prefix+f) bound to a command of theirs
THEIR_CONFIG = """# mine
[keys]
next_agent = ["ctrl+n"]

[[keys.command]]
key = "prefix+f"
type = "shell"
command = "my-finder"
description = "my finder"
"""
# a Python that writes its cache next to the module (Homebrew's, Linux's), not into ~/Library/Caches as the Mac's own
IN_PLACE_PYTHON = '#!/bin/sh\nexec /usr/bin/python3 -X pycache_prefix= "$@"\n'


class InstallCleanup(PackageHome, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        self.pkg = copy_package(os.path.join(self.tmp, "pkg"))
        fakes = stubs(os.path.join(self.tmp, "stubs"), {"herdr": HERDR_STUB, "gh": GH_STUB, "defaults": DEFAULTS_STUB,
                                                       "brew": None, "open": None, "claude": None, "codex": None,
                                                       "pgrep": None})                          # Ghostty is not open
        from_homebrew(fakes)
        self.gh_log = os.path.join(self.tmp, "gh-calls")
        self.herdr_log = os.path.join(self.tmp, "herdr-calls")
        self.plugins = os.path.join(self.tmp, "plugins.json")
        self.set_plugins()
        # no Homebrew folder on PATH: the system python3 (3.9, as on a fresh Mac), never a real Homebrew program
        self.env = {"HOME": self.home, "PATH": f"{fakes}:/usr/bin:/bin:/usr/sbin:/sbin",
                    "HERDR_FOLD_YES": "1", "HERDR_FOLD_NO_BREW": "1", "HERDR_FOLD_NO_MACHINES": "1", "TERM": "dumb",
                    "GH_STUB_STATE": "out", "GH_STUB_LOG": self.gh_log,
                    "STUB_HERDR_LOG": self.herdr_log, "STUB_PLUGINS": self.plugins,
                    "STUB_AGENTS": os.path.join(self.tmp, "agents.json")}

    def set_plugins(self, *plugins):
        """What `herdr plugin list --json` says is installed."""
        with open(self.plugins, "w") as f:
            json.dump({"result": {"plugins": list(plugins)}}, f)

    def herdr_calls(self):
        if not os.path.exists(self.herdr_log):
            return []
        with open(self.herdr_log) as f:
            return f.read().splitlines()

    def install(self):
        done = subprocess.run(["bash", os.path.join(self.pkg, "install.sh")], env=self.env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=300)
        self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-2000:])
        return done.stdout

    def install_answering(self, answers, keep_colors=False):
        """install.sh in a terminal (pty), as someone runs it: a question gets the answer whose text it shows, any
        other the default (Enter). Returns what the terminal showed (KEEP_COLORS: with its color codes)."""
        env = {k: v for k, v in self.env.items() if k != "HERDR_FOLD_YES"}
        shown, _ = run_in_terminal(["/bin/bash", os.path.join(self.pkg, "install.sh")], env,
                                   lambda line: next((a for q, a in answers.items() if q in line), ""), timeout=240,
                                   keep_colors=keep_colors)
        return shown

    def drop_from_package(self, rel):
        files = os.path.join(self.pkg, "files.txt")
        with open(files) as f:
            lines = [line for line in f if not line.rstrip().endswith("| " + rel) and f"| {rel}" not in line]
        with open(files, "w") as f:
            f.writelines(lines)

    def lines_of(self, output, step):
        """The lines step STEP (its heading's catalog key) printed, up to the next step's heading."""
        body = output.split("== " + catalog_text(step), 1)[1].split("\n== ", 1)[0]
        return [line.strip() for line in body.splitlines() if line.strip()]

    def herdr_of_its_own(self, folder=None, version="0.9.6"):
        """herdr from its own installer (curl … | sh puts it in ~/.local/bin), or from FOLDER, not from Homebrew."""
        folder = folder or self.path(".local/bin")
        os.remove(os.path.join(self.tmp, "stubs", "herdr"))
        stubs(folder, {"herdr": HERDR_STUB})
        self.env.update(PATH=folder + ":" + self.env["PATH"], STUB_HERDR_VERSION=version)

    def on_the_mac(self, *programs):
        """PROGRAMS on this Mac without Homebrew: a command, Ghostty in /Applications, the font. herdr and gh are
        there from the start."""
        for name in programs:
            if name == "ghostty":
                self.env["STUB_GHOSTTY"] = "/Applications/Ghostty.app"
            elif name.startswith("font-"):
                self.write("Library/Fonts/JetBrainsMonoNerdFont-Regular.ttf", "")
            else:
                stubs(os.path.join(self.tmp, "stubs"), {{"git-delta": "delta", "ripgrep": "rg"}.get(name, name): None})

    def homebrew_run(self, answers=None, herdr="0.9.6", fails=False):
        """Runs the installer with a stand-in brew (FAILS: its install fails). Returns its calls and the output. Each
        call starts with six flags, "1" off and "-" on: analytics, cleanup, hints, list of new programs, auto-update,
        upgrade on install. ANSWERS: run in a terminal with these answers."""
        log = os.path.join(self.tmp, "brew-calls")
        brew = (f'#!/bin/sh\necho "${{HOMEBREW_NO_ANALYTICS:--}}${{HOMEBREW_NO_INSTALL_CLEANUP:--}}'
                f'${{HOMEBREW_NO_ENV_HINTS:--}}${{HOMEBREW_NO_UPDATE_REPORT_NEW:--}}${{HOMEBREW_NO_AUTO_UPDATE:--}}'
                f'${{HOMEBREW_NO_INSTALL_UPGRADE:--}} $*" >> "{log}"\n'
                f'[ "$1" = install ] && exit {1 if fails else 0}\nexit 0\n')
        stubs(os.path.join(self.tmp, "stubs"), {"brew": brew})
        del self.env["HERDR_FOLD_NO_BREW"]
        self.env.setdefault("STUB_HERDR_VERSION", herdr)
        if fails:
            done = subprocess.run(["bash", os.path.join(self.pkg, "install.sh")], env=self.env,
                                  stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
            self.assertNotEqual(done.returncode, 0)
            out = done.stdout
        else:
            out = self.install() if answers is None else self.install_answering(answers)
        if not os.path.exists(log):
            return [], out
        with open(log) as f:
            return f.read().splitlines(), out

    def test_homebrew_does_not_run_when_every_program_is_on_the_mac(self):
        self.on_the_mac("starship", "bat", "git-delta", "ripgrep", "ghostty", "font-jetbrains-mono-nerd-font")
        calls, out = self.homebrew_run()
        self.assertEqual(calls, [])
        self.assertIn(catalog_text("install.apps_there"), out)

    def test_what_is_missing_homebrew_installs_and_nothing_else(self):
        # auto-update stays on: Homebrew needs it to find current versions
        self.on_the_mac("starship", "bat", "git-delta", "ghostty", "font-jetbrains-mono-nerd-font")
        calls, out = self.homebrew_run()
        self.assertEqual(calls, ["1111-1 install ripgrep"])
        self.assertIn(catalog_text("install.apps_missing", "ripgrep"), out)

    def test_a_program_installed_without_homebrew_stays_the_one(self):
        # e.g. Ghostty from its website, ripgrep from cargo
        self.on_the_mac("ghostty", "ripgrep")
        calls, _ = self.homebrew_run()
        self.assertEqual(calls, ["1111-1 install starship bat git-delta",
                                 "1111-1 install --cask font-jetbrains-mono-nerd-font"])

    def test_a_herdr_not_from_homebrew_gets_no_second_one(self):
        self.herdr_of_its_own()
        calls, out = self.homebrew_run()
        self.assertEqual([call for call in calls if " herdr" in call], [])
        self.assertNotIn("Ghostty looks for herdr", out)                      # ~/.local/bin is on its list

    def test_no_leaves_homebrew_alone_and_names_what_to_run(self):
        calls, shown = self.homebrew_run({catalog_text("install.apps_ask").strip(): "n"})
        self.assertEqual(calls, [])
        self.assertIn(catalog_text("install.apps_later", "brew install starship bat git-delta ripgrep && "
                                   "brew install --cask ghostty font-jetbrains-mono-nerd-font"), shown)
        self.assertNotIn("== " + catalog_text("install.step_theme"), shown)

    def test_a_herdr_older_than_herdr_fold_needs_is_upgraded_after_the_same_yes(self):
        self.on_the_mac("starship", "bat", "git-delta", "ripgrep", "ghostty", "font-jetbrains-mono-nerd-font")
        calls, out = self.homebrew_run(herdr="0.9.4")
        self.assertEqual(calls, ["1111-1 upgrade herdr"])
        self.assertIn(catalog_text("install.herdr_old", "0.9.5"), out)
        self.assertIn(catalog_text("install.herdr_upgraded", "0.9.5"), out)

    def test_a_failed_homebrew_install_stops_the_installer(self):
        calls, out = self.homebrew_run(fails=True)
        self.assertEqual(len(calls), 1)                                       # the casks are not tried
        self.assertIn(catalog_text("install.brew_install_failed"), out)
        self.assertNotIn("== " + catalog_text("install.step_theme"), out)

    def test_an_old_herdr_not_from_homebrew_is_told_its_own_update(self):
        self.herdr_of_its_own(version="0.9.4")
        calls, out = self.homebrew_run()
        self.assertFalse([call for call in calls if "upgrade" in call])
        self.assertIn(catalog_text("install.herdr_too_old_own", "0.9.5"), out)

    def test_a_herdr_ghostty_cannot_find_is_named_with_a_link_that_works(self):
        # mise, a download: not on Ghostty's PATH. The line said runs as it is, in a folder with a space, and makes
        # ~/.local/bin when there is none
        folder = os.path.join(self.tmp, "my tools", "bin")
        self.herdr_of_its_own(folder)
        out = self.install()
        said = next(line for line in out.splitlines() if "Ghostty looks for herdr" in line)
        command = said.split(": ", 1)[1].strip()
        self.assertFalse(os.path.exists(self.path(".local/bin")))
        subprocess.run(["/bin/sh", "-c", command], env={"HOME": self.home, "PATH": "/usr/bin:/bin"}, check=True)
        self.assertEqual(os.path.realpath(self.path(".local/bin/herdr")),
                         os.path.realpath(os.path.join(folder, "herdr")))

    def test_a_mise_herdr_is_linked_through_its_shim(self):
        # mise keeps a folder per version, gone after mise upgrade: the shim stays
        mise = os.path.join(self.tmp, "mise")
        self.herdr_of_its_own(os.path.join(mise, "installs", "herdr", "0.9.6", "bin"))
        stubs(os.path.join(mise, "shims"), {"herdr": HERDR_STUB})
        said = next(line for line in self.install().splitlines() if "Ghostty looks for herdr" in line)
        self.assertIn(f'ln -s "{os.path.join(mise, "shims", "herdr")}"', said)

    def test_two_herdrs_name_the_one_ghostty_starts(self):
        # herdr's own installer's first on PATH, a Homebrew one too: Ghostty looks in Homebrew's folders first
        folder = self.path(".local/bin")
        stubs(folder, {"herdr": HERDR_STUB})
        self.env["PATH"] = folder + ":" + self.env["PATH"]
        out = self.install()
        self.assertIn(catalog_text("install.herdr_twice", os.path.join(self.tmp, "stubs", "herdr"),
                                   os.path.join(folder, "herdr")), out)

    def test_in_herdrs_tab_the_herdr_running_it_is_the_one_checked(self):
        # HERDR_BIN_PATH, not the PATH's first: here a download Ghostty would not find
        folder = os.path.join(self.tmp, "my tools", "bin")
        stubs(folder, {"herdr": HERDR_STUB})
        self.env["HERDR_BIN_PATH"] = os.path.join(folder, "herdr")
        said = next(line for line in self.install().splitlines() if "Ghostty looks for herdr" in line)
        self.assertIn(os.path.join(folder, "herdr"), said)

    def test_ghostty_finds_a_herdr_from_herdrs_own_installer(self):
        with open(os.path.join(self.pkg, "config", "ghostty", "config")) as f:
            start = next(line for line in f if line.startswith("initial-command = "))
        self.assertIn(' env PATH="$HOME/.config/herdr-fold/bin:/opt/homebrew/bin:/usr/local/bin:$PATH:$HOME/.local/bin"'
                      ' herdr', start)                                   # last: nothing there hides the system's

    def test_a_copy_in_the_trash_stops_before_anything_changes(self):
        # a terminal left in a folder that went to the Trash runs that old copy, not the one unpacked in its place
        trashed = self.path(".Trash/herdr-fold")
        shutil.copytree(self.pkg, trashed, symlinks=True)
        done = subprocess.run(["bash", os.path.join(trashed, "install.sh")], env=self.env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=120)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn(catalog_text("install.in_trash", "~/.Trash/herdr-fold"), done.stdout + done.stderr)
        self.assertFalse(os.path.exists(self.path(".config/herdr-fold")))

    def test_run_from_herdrs_copy_it_moves_to_a_place_of_its_own(self):
        # from herdr's marketplace: herdr keeps the package in a folder per version and removes an old one
        self.env["HERDR_PLUGIN_ROOT"] = self.pkg
        out = self.install()
        kept = self.path(".local/share/herdr-fold")
        self.assertTrue(os.path.isfile(os.path.join(kept, "install.sh")))
        self.assertEqual(self.read(".config/herdr-fold/setup-folder").strip(), kept)
        self.assertTrue(os.path.isfile(os.path.join(kept, ".kept-by-herdr-fold")))
        self.assertEqual(out.count(catalog_text("install.package_kept", "~/.local/share/herdr-fold")), 1, out)
        self.assertFalse(os.path.exists(kept + ".new") or os.path.exists(kept + ".old"))

    def test_a_linked_root_plugin_stays_where_it_is(self):
        # herdr plugin link: a working copy, not herdr's own, so nothing moves
        self.set_plugins({"plugin_id": "herdr-fold", "source": {"kind": "local"}, "plugin_root": self.pkg})
        self.env["HERDR_PLUGIN_ROOT"] = self.pkg
        self.install()
        self.assertFalse(os.path.exists(self.path(".local/share/herdr-fold")))
        self.assertEqual(self.read(".config/herdr-fold/setup-folder").strip(), self.pkg)

    def test_ctrl_c_during_the_move_leaves_the_package_whole(self):
        # between the two moves the package is nowhere: Ctrl+C there waits until the second is done
        kept, moved = self.path(".local/share/herdr-fold"), os.path.join(self.tmp, "moved")
        self.write(".local/share/herdr-fold/install.sh", "# the earlier one\n")
        self.write(".local/share/herdr-fold/.kept-by-herdr-fold", "")
        stubs(os.path.join(self.tmp, "stubs"), {"mv": f'#!/bin/sh\n/bin/mv "$@" || exit\n'
                                                     f'case "$2" in *.old) touch "{moved}"; sleep 2 ;; esac\n'})
        self.env["HERDR_PLUGIN_ROOT"] = self.pkg
        run = subprocess.Popen(["bash", os.path.join(self.pkg, "install.sh")], env=self.env,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=True)
        self.addCleanup(run.wait)
        for _ in range(200):
            if os.path.exists(moved):
                break
            time.sleep(0.05)
        os.killpg(run.pid, signal.SIGINT)                                  # as the terminal sends Ctrl+C
        run.wait(timeout=120)
        self.assertTrue(os.path.isfile(os.path.join(kept, "install.sh")))
        self.assertNotEqual(self.read(".local/share/herdr-fold/install.sh"), "# the earlier one\n")
        self.assertFalse(os.path.exists(kept + ".old"))

    def test_a_failed_move_keeps_the_earlier_copy(self):
        kept = self.path(".local/share/herdr-fold")
        self.write(".local/share/herdr-fold/install.sh", "# the earlier one\n")
        self.write(".local/share/herdr-fold/.kept-by-herdr-fold", "")
        os.chmod(self.path(".local/share"), 0o555)
        self.addCleanup(os.chmod, self.path(".local/share"), 0o755)
        self.env["HERDR_PLUGIN_ROOT"] = self.pkg
        done = subprocess.run(["bash", os.path.join(self.pkg, "install.sh")], env=self.env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=120)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn(catalog_text("install.package_not_kept", "~/.local/share/herdr-fold"), done.stdout)
        self.assertEqual(self.read(".local/share/herdr-fold/install.sh"), "# the earlier one\n")
        self.assertFalse(os.path.exists(self.path(".config/herdr-fold/setup-folder")))
        self.assertFalse(os.path.exists(kept + ".new"))

    def test_cancelled_at_the_start_the_earlier_copy_stays(self):
        # nothing changes before the start: the package moves once the installer is to go on, and is not asked again
        self.write(".local/share/herdr-fold/install.sh", "# the earlier one\n")
        self.write(".local/share/herdr-fold/.kept-by-herdr-fold", "")
        self.env["HERDR_PLUGIN_ROOT"] = self.pkg
        shown = self.install_answering({catalog_text("lib.press_enter_to_start"): "x"})
        self.assertEqual(self.read(".local/share/herdr-fold/install.sh"), "# the earlier one\n")
        self.assertNotIn(catalog_text("install.package_kept", "~/.local/share/herdr-fold"), shown)

    def test_moved_it_asks_to_start_once(self):
        self.env["HERDR_PLUGIN_ROOT"] = self.pkg
        shown = self.install_answering({})
        self.assertEqual(shown.count(catalog_text("lib.press_enter_to_start")), 1, shown[-3000:])
        self.assertEqual(shown.count(catalog_text("install.intro")), 1)
        self.assertIn(catalog_text("install.package_kept", "~/.local/share/herdr-fold"), shown)

    def test_a_folder_it_did_not_make_is_never_replaced(self):
        # ~/.local/share/herdr-fold holding a clone of someone's (the XDG data folder, the repository's own name)
        self.write(".local/share/herdr-fold/notes.txt", "my changes\n")
        self.env["HERDR_PLUGIN_ROOT"] = self.pkg
        done = subprocess.run(["bash", os.path.join(self.pkg, "install.sh")], env=self.env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=120)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn(catalog_text("install.package_not_herdr_folds", "~/.local/share/herdr-fold"), done.stdout)
        self.assertEqual(os.listdir(self.path(".local/share/herdr-fold")), ["notes.txt"])
        self.assertFalse(os.path.exists(self.path(".local/share/herdr-fold.new")))

    def test_a_folder_named_like_its_copies_is_never_removed(self):
        # the installer's own copy there, and someone's folder moved aside to herdr-fold.old as the message said
        self.write(".local/share/herdr-fold/.kept-by-herdr-fold", "")
        self.write(".local/share/herdr-fold.old/notes.txt", "my changes\n")
        self.env["HERDR_PLUGIN_ROOT"] = self.pkg
        done = subprocess.run(["bash", os.path.join(self.pkg, "install.sh")], env=self.env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=120)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn(catalog_text("install.package_not_herdr_folds", "~/.local/share/herdr-fold.old"), done.stdout)
        self.assertEqual(self.read(".local/share/herdr-fold.old/notes.txt"), "my changes\n")

    def test_started_flag_from_outside_does_not_skip_the_start(self):
        # HERDR_FOLD_STARTED is the moved installer's own: from a folder, the start is asked all the same
        self.env["HERDR_FOLD_STARTED"] = "1"
        shown = self.install_answering({catalog_text("lib.press_enter_to_start"): "x"})
        self.assertIn(catalog_text("lib.press_enter_to_start"), shown)
        self.assertFalse(os.path.exists(self.path(".config/herdr-fold")))

    def test_run_from_a_folder_of_its_own_it_stays(self):
        self.install()                                                          # the zip, a clone: no herdr plugin
        self.assertFalse(os.path.exists(self.path(".local/share/herdr-fold")))
        self.assertEqual(self.read(".config/herdr-fold/setup-folder").strip(), self.pkg)

    def test_the_settings_step_sums_up_in_one_line(self):
        out = self.install()
        self.assertRegex(out, r"\[✓\] \d+ settings in place")
        self.assertNotIn("[✓] .config/herdr-fold/herdrlib.py", out)              # file by file only with VERBOSE

    def test_the_theme_step_shows_the_sheep_in_the_chosen_themes_colors(self):
        # a theme step that takes a while (herdr slow to reload): the sheep walk meanwhile, in the new theme's colors
        slow = HERDR_STUB.replace("#!/bin/sh\n", '#!/bin/sh\n[ "$*" = "server reload-config" ] && sleep 2\n', 1)
        stubs(os.path.join(self.tmp, "stubs"), {"herdr": slow})
        self.env.update(TERM="xterm-256color", LOADING_AFTER="0", LOADING_SHEEP="0")
        shown = self.install_answering({catalog_text("install.theme_ask").strip(): "2"}, keep_colors=True)
        step = shown.split(catalog_text("install.theme_setting"), 1)
        self.assertEqual(len(step), 2, shown[-3000:])
        self.assertIn("38;2;0;120;212",                                                   # VS Code's accent
                      step[0].rsplit(catalog_text("install.theme_ask").strip(), 1)[1])

    def test_the_preview_opens_at_this_macs_theme(self):
        from themes import apply
        vesper = apply.find(apply.load_themes(), "vesper")
        self.write(".config/ghostty/config", "\n".join(apply.ghostty_block(vesper)) + "\n")
        log = os.path.join(self.tmp, "open-calls")
        stubs(os.path.join(self.tmp, "stubs"), {"open": f'#!/bin/sh\necho "$*" >> "{log}"\n'})
        self.install_answering({})
        with open(log) as f:
            opened = f.read().splitlines()
        self.assertEqual(opened, [pathlib.Path(self.pkg, "src", "themes", "preview.html").as_uri() + "#3"])

    def test_verbose_lists_every_file(self):
        self.env["HERDR_FOLD_VERBOSE"] = "1"
        self.assertIn("[✓] .config/herdr-fold/herdrlib.py", self.install())

    def test_untrusted_claude_projects_are_named_and_left_alone_by_default(self):
        project = os.path.join(self.home, "Documents", "my-repo")
        os.makedirs(os.path.join(project, ".git"))                       # a git repository's root
        agents = json.dumps({"result": {"agents": [{"pane_id": "w1:p1", "agent": "claude", "cwd": project}]}})
        with open(os.path.join(self.tmp, "stubs", "herdr"), "w") as f:
            f.write(HERDR_STUB.replace('case "$*" in', f'case "$*" in\n  "agent list"*) echo \'{agents}\' ;;'))
        out = self.install()
        self.assertIn("Claude shows the status line only in projects it trusts", out)
        self.assertIn("~/Documents/my-repo", out)                     # under ~, as ~/…
        self.assertFalse(os.path.exists(self.path(".claude.json")))     # the question's default is no

    def version(self):
        with open(os.path.join(self.pkg, "herdr-plugin.toml")) as f:
            return re.search(r'^version = "([^"]+)"', f.read(), re.M).group(1)

    def test_a_first_install_is_no_update(self):
        shown = self.install_answering({})
        self.assertNotIn(catalog_text("install.update_ask"), shown)
        self.assertIn(catalog_text("lib.press_enter_to_start"), shown)

    def test_an_update_asks_once_and_keeps_the_earlier_choices(self):
        self.install()
        shown = self.install_answering({})                                  # Enter: the earlier choices
        self.assertIn(catalog_text("install.update_ask"), shown)
        for key in ("lib.press_enter_to_start", "status.question", "install.sessions_ask", "install.tab_layout_ask",
                    "install.github_login_ask"):
            self.assertNotIn(catalog_text(key), shown, key)
        self.assertNotIn(catalog_text("install.theme_ask") + " [", shown)          # the question, not the step
        self.assertIn(catalog_text("install.theme_set", "Catppuccin Mocha"), shown)

    def test_no_to_the_update_question_asks_everything_again(self):
        self.install()
        shown = self.install_answering({catalog_text("install.update_ask"): "n"})
        self.assertIn(catalog_text("install.theme_ask") + " [", shown)
        self.assertIn(catalog_text("status.question"), shown)

    def test_the_installed_version_is_kept_and_named_by_the_next(self):
        self.install()
        self.assertEqual(self.read(".local/state/herdr-fold/version").strip(), self.version())
        self.assertIn(catalog_text("install.update_found", self.version(), self.version()), self.install_answering({}))

    def test_an_update_still_asks_before_homebrew_installs_something_new(self):
        self.install()
        calls, shown = self.homebrew_run({})
        self.assertIn(catalog_text("install.update_ask"), shown)
        self.assertIn(catalog_text("install.apps_ask"), shown)
        self.assertIn("1111-1 install starship bat git-delta ripgrep", calls)

    def test_from_herdrs_copy_the_update_keeps_its_choices_past_the_move(self):
        self.install()
        self.env["HERDR_PLUGIN_ROOT"] = self.pkg
        shown = self.install_answering({})
        self.assertIn(catalog_text("install.package_kept", "~/.local/share/herdr-fold"), shown)
        self.assertNotIn(catalog_text("install.theme_ask") + " [", shown)

    def test_the_install_ends_with_done(self):
        self.assertEqual(self.lines_of(self.install(), "install.step_done")[0],
                         "[✓] " + catalog_text("install.finished"))

    def test_warnings_are_counted_at_the_end(self):
        os.remove(os.path.join(self.pkg, "src", "tui.py"))       # one warning: missing from the package
        self.assertEqual(self.lines_of(self.install(), "install.step_done")[0],
                         "[!] " + catalog_text("install.finished_warnings", 1))

    def test_each_step_says_what_it_did_not_its_parts(self):
        # as the usual installers do: a line a step, for what changed or needs attention; the parts with
        # HERDR_FOLD_VERBOSE=1
        out = self.install()
        there = ", ".join(catalog_text(key) for key in ("install.homebrew", "install.claude", "install.codex",
                                                         "install.tailscale"))
        self.assertEqual(self.lines_of(out, "install.step_prerequisites"),
                         ["[✓] " + there, catalog_text("install.ssh_key_missing")])
        self.assertEqual(self.lines_of(out, "install.step_theme"),                   # not asked: no list
                         ["[✓] " + catalog_text("install.theme_set", "Catppuccin Mocha")])
        self.assertEqual(len(self.lines_of(out, "install.step_settings")), 1)           # the settings, the theme set
        self.assertEqual(self.lines_of(out, "install.step_prompt"),
                         ["[✓] " + catalog_text("status.herdr_folds", "Claude Code, Codex") + "; "
                          + catalog_text("status.codex_restart")])
        plugins = ", ".join(catalog_text(key) for key in ("install.plugin_sidebar", "install.plugin_sessions",
                                                           "install.plugin_tab_layout"))
        self.assertEqual(self.lines_of(out, "install.step_plugins"),
                         ["[✓] " + catalog_text("install.plugins", plugins),
                          "[✓] " + catalog_text("install.integrations", "Claude Code, Codex")])
        self.assertEqual(self.lines_of(out, "install.step_done")[1:],
                         [catalog_text("install.open_ghostty"), catalog_text("install.next_steps")])

    def test_every_line_lines_up(self):
        # a step's heading, a status line (its mark two columns in, its text after it) or a line under that text
        out = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", self.install())
        lines = [line for line in out[out.index("\n== ") + 1:].split("\n") if line.strip()]   # past the title
        self.assertEqual([line for line in lines
                          if not re.match(r"(== \S|  \[.\] \S|      \S)", line)], [])

    def test_the_theme_list_goes_once_a_theme_is_chosen(self):
        shown = self.install_answering({catalog_text("install.theme_ask"): "2"}, keep_colors=True)
        step = shown.split("== " + catalog_text("install.step_theme"), 1)[1].split("== ", 1)[0]
        chosen = step.split(catalog_text("install.theme_ask"), 1)[1]
        self.assertRegex(chosen, r"\x1b\[\d+A\r?\x1b\[J")                           # the list and the question go
        self.assertIn(catalog_text("install.theme_set", "VS Code (Dark Modern)"), chosen)

    def test_verbose_says_every_part(self):
        self.env["HERDR_FOLD_VERBOSE"] = "1"
        out = self.install()
        self.assertIn(catalog_text("install.pane_env"), out)
        self.assertIn("[✓] " + catalog_text("theme.ghostty", "Catppuccin Mocha"), out)

    def test_the_end_says_only_what_is_needed_now(self):
        said = self.lines_of(self.install(), "install.step_done")[1:]           # after how it went
        self.assertLessEqual(len(said), 2, said)
        self.assertIn("Ghostty", " ".join(said))
        self.assertIn("Ctrl+B, ?", " ".join(said))

    def test_the_end_waits_for_a_key(self):
        # whichever way it ends (see test_lib.WaitForKey: only with a terminal)
        with open(os.path.join(PACKAGE, "install.sh"), encoding="utf-8") as f:
            source = f.read()
        handler = source[source.index("finish() {"):source.index("trap finish EXIT")]
        self.assertIn("wait_for_key", handler)

    def test_an_early_stop_is_said_too(self):
        stubs(os.path.join(self.tmp, "stubs"), {"uname": "#!/bin/sh\necho Linux\n"})   # not a Mac: it stops
        done = subprocess.run(["bash", os.path.join(self.pkg, "install.sh")], env=self.env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=60)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("The installer stopped before the end — see the lines above.", done.stdout)

    def test_someones_own_herdr_sidebar_stays_and_is_named(self):
        self.set_plugins(SIDEBAR)
        out = self.install()
        touched = ("herdr plugin uninstall", "herdr plugin update", "herdr plugin install")
        self.assertFalse([c for c in self.herdr_calls() if c.startswith(touched)])
        self.assertIn(catalog_text("install.herdr_sidebar_too"), out)

    def test_a_second_run_changes_nothing_more(self):
        self.install()
        self.set_plugins({"plugin_id": "herdr-fold.sidebar", "events": [], "plugin_root": ""})
        before = len(self.herdr_calls())
        self.install()
        again = self.herdr_calls()[before:]
        self.assertFalse([c for c in again if "plugin uninstall" in c or "pane close" in c])
        self.assertEqual(self.read(".local/state/herdr-fold/plugins.txt").split().count("herdr-fold.sidebar"), 1)

    def test_the_summary_names_only_their_plugins(self):
        self.write(".config/herdr/config.toml", THEIR_CONFIG)
        self.set_plugins(*({"plugin_id": p, "events": [], "plugin_root": ""}
                           for p in ("herdr-fold.sidebar", "herdr-fold.sessions-view", "herdr-fold.tab-layout",
                                     "x.mine")))
        out = self.install()
        self.assertIn(catalog_text("install.existing_plugins", "x.mine"), out)

    def test_the_whole_environment_plugin_is_not_called_theirs(self):
        # herdr-fold's own entry from herdr's marketplace: its folder is the whole package, AI Sessions' code too
        self.write(".config/herdr/config.toml", THEIR_CONFIG)
        self.set_plugins({"plugin_id": "herdr-fold", "events": [], "plugin_root": self.pkg,
                          "source": {"kind": "github", "owner": "princesshu", "repo": "herdr-fold"}},
                         {"plugin_id": "x.mine", "events": [], "plugin_root": ""})
        out = self.install()
        self.assertIn(catalog_text("install.existing_plugins", "x.mine"), out)
        self.assertNotIn(catalog_text("install.plugin_like_sessions", "herdr-fold"), out)

    def test_a_plugin_of_theirs_doing_the_same_is_named(self):
        # one that lays out new tabs too: the two would fight over a new tab
        self.set_plugins({"plugin_id": "x.layout", "events": [{"on": "tab.created"}], "plugin_root": ""})
        out = self.install()
        self.assertIn(catalog_text("install.plugin_like_tab_layout", "x.layout"), out)

    def test_no_take_over_without_its_own_copy(self):
        # the installer's own sidebar is not in place: the marketplace's stays rather than leaving none
        self.drop_from_package(".config/herdr-fold/plugins/sidebar/herdr-plugin.toml")
        self.set_plugins({"plugin_id": "herdr-fold.sidebar", "events": [], "plugin_root": "",
                          "source": {"kind": "github"}})
        self.install()
        self.assertNotIn("herdr plugin uninstall herdr-fold.sidebar", self.herdr_calls())

    def test_a_plugin_named_like_herdr_folds_is_still_theirs(self):
        self.set_plugins({"plugin_id": "herdr-fold.x", "events": [{"on": "tab.created"}], "plugin_root": ""})
        out = self.install()
        self.assertIn(catalog_text("install.plugin_like_tab_layout", "herdr-fold.x"), out)

    def test_a_plugin_list_cannot_forge_a_line(self):
        # an id with a line break in it would read as a second plugin: one of herdr-fold's, from the marketplace
        self.set_plugins({"plugin_id": "zz\nherdr-fold.sidebar|1||github", "events": [], "plugin_root": ""})
        self.install()
        self.assertNotIn("herdr plugin uninstall herdr-fold.sidebar", self.herdr_calls())

    def test_a_plugin_of_herdr_folds_from_the_marketplace_is_taken_over(self):
        # installed alone from herdr's marketplace first: the installer's own copy takes its place, and says so
        github = {"kind": "github", "owner": "princesshu", "repo": "herdr-fold"}
        plugins = ("sidebar", "sessions-view", "tab-layout")
        self.set_plugins(*({"plugin_id": f"herdr-fold.{p}", "events": [], "plugin_root": "", "source": github}
                           for p in plugins))
        out = self.install()
        calls = self.herdr_calls()
        for plugin in plugins:
            off = calls.index(f"herdr plugin uninstall herdr-fold.{plugin}")
            on = next(n for n, c in enumerate(calls) if c.startswith("herdr plugin link") and c.endswith("/" + plugin))
            self.assertLess(off, on)
            self.assertIn(catalog_text("install.plugin_taken_over", f"herdr-fold.{plugin}"), out)
        self.set_plugins(*({"plugin_id": f"herdr-fold.{p}", "events": [], "plugin_root": ""} for p in plugins))
        self.install()                                          # linked now: the record of the take-over stays
        record = self.read(".local/state/herdr-fold/plugins.txt").split()
        self.assertEqual([line for line in record if line.startswith("taken:")],
                         [f"taken:herdr-fold.{p}" for p in plugins])

    def test_an_existing_herdr_is_summed_up_and_kept_by_default(self):
        self.write(".config/herdr/config.toml", THEIR_CONFIG)
        out = self.install()
        self.assertIn("herdr is set up here already", out)
        config = self.read(".config/herdr/config.toml")
        self.assertTrue(config.startswith("# mine\n"), config[:200])
        self.assertIn("\n[keys]\n# >>> herdr-fold >>>\n", config)
        self.assertIn('next_agent = ["ctrl+n"]', config)
        self.assertIn('command = "my-finder"', config)
        self.assertNotIn("toggle_column.py", config)                        # their prefix+f stays theirs
        self.assertIn("close_tab.py", config)
        self.assertIn("[!] prefix+f is yours already", out)
        self.assertNotIn(".config/herdr/config.toml", self.read(".local/state/herdr-fold/installed.txt").split())

    def test_an_added_config_is_not_asked_about_again(self):
        self.write(".config/herdr/config.toml", THEIR_CONFIG)
        self.install()
        first = self.read(".config/herdr/config.toml")
        out = self.install()
        self.assertNotIn("herdr is set up here already", out)
        self.assertEqual(self.read(".config/herdr/config.toml"), first)

    def test_their_settings_before_the_first_add_are_kept_where_backups_are_never_pruned(self):
        self.write(".config/herdr/config.toml", THEIR_CONFIG)
        for _ in range(5):                                                  # more installs than dated backups kept
            self.install()
        self.assertEqual(self.read(".local/state/herdr-fold/original/.config/herdr/config.toml"), THEIR_CONFIG)

    def test_replacing_sets_theirs_aside(self):
        self.write(".config/herdr/config.toml", THEIR_CONFIG)
        self.env["HERDR_FOLD_CONFIG"] = "replace"
        self.install()
        self.assertIn("toggle_column.py", self.read(".config/herdr/config.toml"))
        self.assertEqual(self.read(".local/state/herdr-fold/original/.config/herdr/config.toml"), THEIR_CONFIG)

    def test_plugins_doing_the_same_as_herdr_folds_are_named(self):
        root = os.path.join(self.tmp, "their-view")
        os.makedirs(root)
        with open(os.path.join(root, "view.py"), "w") as f:
            f.write('call("agent.view.set", {})\n')
        self.set_plugins(SIDEBAR, {"plugin_id": "x.tabs", "events": [{"on": "tab.created"}], "plugin_root": ""},
                         {"plugin_id": "y.view", "events": [], "plugin_root": root})
        out = self.install()
        self.assertIn("[!] x.tabs", out)
        self.assertIn("[!] y.view", out)

    def test_with_herdr_set_up_already_each_plugin_is_a_question(self):
        self.write(".config/herdr/config.toml", THEIR_CONFIG)
        shown = self.install_answering({catalog_text("install.sessions_ask"): "n"})
        self.assertIn(catalog_text("install.sessions_ask"), shown)
        self.assertIn(catalog_text("install.tab_layout_ask"), shown)
        linked = [call for call in self.herdr_calls() if call.startswith("herdr plugin link")]
        self.assertEqual([call.rsplit("/", 1)[-1] for call in linked], ["sidebar", "tab-layout"])
        self.assertIn("herdr plugin unlink herdr-fold.sessions-view", self.herdr_calls())
        self.assertEqual(sorted(self.read(".local/state/herdr-fold/plugins.txt").split()),
                         ["declined:herdr-fold.sessions-view", "herdr-fold.sidebar", "herdr-fold.tab-layout"])

    def test_a_plugin_said_no_to_stays_unlinked(self):
        self.write(".config/herdr/config.toml", THEIR_CONFIG)
        self.install_answering({catalog_text("install.sessions_ask"): "n"})
        os.remove(self.herdr_log)
        out = self.install()                                                # unattended: every answer the default
        self.assertFalse([call for call in self.herdr_calls() if call.endswith("plugins/sessions-view")], out)
        self.assertIn("herdr plugin link", " ".join(self.herdr_calls()))     # the column layout still is

    def test_a_plugin_said_no_to_stays_unlinked_after_their_settings_were_replaced(self):
        # their config replaced once (from then on it is herdr-fold's, so the next run asks nothing about it), the
        # AI Sessions said no to: the next unattended run keeps that answer
        self.write(".config/herdr/config.toml", THEIR_CONFIG)
        self.env["HERDR_FOLD_CONFIG"] = "replace"
        self.install_answering({catalog_text("install.sessions_ask"): "n"})
        del self.env["HERDR_FOLD_CONFIG"]
        os.remove(self.herdr_log)
        out = self.install()
        self.assertFalse([call for call in self.herdr_calls() if call.endswith("plugins/sessions-view")], out)
        self.assertIn("declined:herdr-fold.sessions-view", self.read(".local/state/herdr-fold/plugins.txt").split())
    def test_herdr_folds_plugins_are_linked_and_recorded(self):
        self.install()
        linked = [call for call in self.herdr_calls() if call.startswith("herdr plugin link")]
        self.assertEqual(len(linked), 3)
        self.assertIn("herdr plugin link " + self.path(".config/herdr-fold/plugins/sidebar"), linked)
        plugins = self.read(".local/state/herdr-fold/plugins.txt").split()
        for plugin in ("herdr-fold.sessions-view", "herdr-fold.tab-layout", "herdr-fold.sidebar"):
            self.assertIn(plugin, plugins)

    def test_connected_machines_are_updated_without_a_question(self):
        log = os.path.join(self.tmp, "machines-calls")
        with open(os.path.join(self.pkg, "machines.sh"), "w") as f:     # a stand-in that only records its command
            f.write(f'#!/bin/sh\necho "$*" >> {log}\n')
        del self.env["HERDR_FOLD_NO_MACHINES"]
        self.install()
        with open(log) as f:     # the questions (no new one: their default is No), then every listed machine
            self.assertEqual(f.read(), "pick\nadd\n")

    def test_records_where_the_package_is(self):
        # Ctrl+B, Shift+M (add_machine.py) runs this package's machines.sh
        self.install()
        self.assertEqual(self.read(".config/herdr-fold/setup-folder").strip(), self.pkg)

    def add_language(self, code):
        lang = os.path.join(self.pkg, "src", "lang")
        shutil.copy(os.path.join(lang, "en.txt"), os.path.join(lang, code + ".txt"))

    def test_a_new_language_file_is_installed_without_listing_it(self):
        self.add_language("xx")
        self.install()
        self.assertTrue(os.path.isfile(self.path(".config/herdr-fold/lang/xx.txt")))
        self.assertIn(".config/herdr-fold/lang/xx.txt", self.read(".local/state/herdr-fold/installed.txt").split("\n"))

    def test_language_dropped_from_the_package_is_removed(self):
        self.add_language("xx")
        self.install()
        os.remove(os.path.join(self.pkg, "src", "lang", "xx.txt"))
        out = self.install()
        self.assertFalse(os.path.exists(self.path(".config/herdr-fold/lang/xx.txt")))
        self.assertTrue(os.path.isfile(self.path(".config/herdr-fold/lang/en.txt")))
        self.assertIn(catalog_text("install.dropped_removed", "~/.local/state/herdr-fold/"), out)
        self.assertNotIn("%s", catalog_text("install.dropped_ask"))           # the copy's place: said once, after
        self.assertNotIn(catalog_text("install.dropped_deleted", ".config/herdr-fold/lang/xx.txt"), out)

    def test_files_no_longer_used_are_asked_about_before_they_go(self):
        self.add_language("xx")
        self.install()
        os.remove(os.path.join(self.pkg, "src", "lang", "xx.txt"))
        shown = self.install_answering({catalog_text("install.update_ask"): "n",       # every question: the one below
                                        catalog_text("install.dropped_ask"): "n"})
        listed = shown.split(catalog_text("install.dropped_heading"), 1)
        self.assertEqual(len(listed), 2, shown[-2000:])
        self.assertTrue(listed[1].startswith(" ~/.config/herdr-fold/lang/xx.txt\n"), listed[1][:200])  # one: inline
        self.assertIn(catalog_text("install.dropped_kept"), listed[1])
        self.assertTrue(os.path.isfile(self.path(".config/herdr-fold/lang/xx.txt")))
        self.assertIn(".config/herdr-fold/lang/xx.txt", self.read(".local/state/herdr-fold/installed.txt").split("\n"))

    def test_an_update_removes_them_unasked_and_keeps_a_copy(self):
        self.add_language("xx")
        self.install()
        os.remove(os.path.join(self.pkg, "src", "lang", "xx.txt"))
        shown = self.install_answering({})                                      # Enter: the earlier choices
        self.assertNotIn(catalog_text("install.dropped_ask"), shown)
        self.assertIn(catalog_text("install.dropped_heading") + " ~/.config/herdr-fold/lang/xx.txt", shown)
        self.assertIn(catalog_text("install.dropped_removed", "~/.local/state/herdr-fold/"), shown)
        self.assertFalse(os.path.exists(self.path(".config/herdr-fold/lang/xx.txt")))

    def test_several_files_no_longer_used_in_a_folder_are_named_by_it(self):
        for code in ("xx", "yy"):
            self.add_language(code)
        self.install()
        for code in ("xx", "yy"):
            os.remove(os.path.join(self.pkg, "src", "lang", code + ".txt"))
        shown = self.install_answering({catalog_text("install.dropped_ask"): "n"})
        listed = shown.split(catalog_text("install.dropped_heading"), 1)[1]
        self.assertIn(catalog_text("install.dropped_folder", "~/.config/herdr-fold/lang", "2"), listed)
        self.assertNotIn("xx.txt", listed)

    def test_a_file_missing_from_the_package_stays_on_the_machine(self):
        self.install()
        os.remove(os.path.join(self.pkg, "src", "tui.py"))       # a broken copy; files.txt still lists it
        out = self.install()
        self.assertTrue(os.path.isfile(self.path(".config/herdr-fold/tui.py")), out)
        self.assertIn("src/tui.py", out)                               # the warning names it
        self.assertIn(".config/herdr-fold/tui.py", self.read(".local/state/herdr-fold/installed.txt").split("\n"))

    def test_an_empty_file_list_deletes_nothing(self):
        self.install()
        with open(os.path.join(self.pkg, "files.txt"), "w") as f:
            f.write("")
        self.install()
        self.assertTrue(os.path.isfile(self.path(".config/herdr-fold/herdrlib.py")))
        self.assertIn(".config/herdr-fold/herdrlib.py", self.read(".local/state/herdr-fold/installed.txt").split("\n"))

    def test_an_own_claude_status_line_is_kept_where_backups_are_never_pruned(self):
        self.write(".claude/settings.json", json.dumps({"statusLine": {"type": "command", "command": "mine.sh"}}))
        self.install()
        kept = self.path(".local/state/herdr-fold/original/claude-statusLine.json")
        with open(kept) as f:
            self.assertEqual(json.load(f)["command"], "mine.sh")
        settings = json.loads(self.read(".claude/settings.json"))
        self.assertEqual(settings["statusLine"]["command"], 'python3 "$HOME/.config/herdr-fold/statusline.py"')

    def test_the_status_line_runs_from_where_the_installer_put_it(self):
        self.install()
        command = json.loads(self.read(".claude/settings.json"))["statusLine"]["command"]
        done = subprocess.run(["/bin/sh", "-c", command], input='{"model": {"display_name": "Opus 5.5"}}',
                              env={"HOME": self.home, "PATH": "/usr/bin:/bin"}, capture_output=True, text=True,
                              timeout=20)
        self.assertEqual((done.stdout, done.stderr), ("\x1b[38;2;78;201;212mOpus 5.5\x1b[0m", ""))

    def test_the_status_line_outcome_is_said(self):
        # the paths under ~, as ~/…: what the installer shows may be pasted into an issue
        state = "~/.local/state/herdr-fold/original"
        cases = [(None, "[✓] " + catalog_text("status.herdr_folds", "Claude Code, Codex")),               # 0: set
                 ({"statusLine": {"type": "command", "command": "mine.sh"}},
                  "[+] " + catalog_text("status.claude_replaced", state)),                       # 2: replaced, kept
                 ("{", "[!] " + catalog_text("status.claude_unreadable", "~/.claude/settings.json"))]   # 1
        for settings, said in cases:
            if settings is None:
                if os.path.exists(self.path(".claude/settings.json")):
                    os.remove(self.path(".claude/settings.json"))
            else:
                self.write(".claude/settings.json", settings if isinstance(settings, str) else json.dumps(settings))
            self.assertIn(said, self.install(), settings)

    def test_a_trust_that_fails_is_said(self):
        project = os.path.join(self.tmp, "app")
        os.makedirs(os.path.join(project, ".git"))
        with open(self.env["STUB_AGENTS"], "w") as f:                       # a Claude pane in an untrusted repository
            json.dump({"result": {"agents": [{"pane_id": "w1:p1", "agent": "claude", "cwd": project}]}}, f)
        self.write(".claude.json", '{"projects": {')                       # half-written by a running Claude
        shown = self.install_answering({catalog_text("install.trust_ask"): "y"})
        failed = [line for line in shown.splitlines()
                  if line.startswith("  [!] " + catalog_text("install.trust_failed", ""))]
        self.assertEqual(len(failed), 1, shown[-3000:])
        self.assertIn(".claude.json", failed[0])
        self.assertNotIn("[✓] " + catalog_text("install.trust_done"), shown)

    def test_the_trust_question_shows_the_projects_and_trusts_those(self):
        # under ~ as ~/…, never the home folder itself nor a folder outside a git repository; on a yes, exactly the
        # projects it showed
        project, downloads = os.path.join(self.home, "Documents", "app"), os.path.join(self.home, "Downloads")
        os.makedirs(os.path.join(project, ".git"))
        os.makedirs(downloads)
        with open(self.env["STUB_AGENTS"], "w") as f:
            json.dump({"result": {"agents": [{"pane_id": "w1:p1", "agent": "claude", "cwd": project},
                                             {"pane_id": "w2:p1", "agent": "claude", "cwd": self.home},
                                             {"pane_id": "w3:p1", "agent": "claude", "cwd": downloads}]}}, f)
        shown = self.install_answering({catalog_text("install.trust_ask"): "y"})
        self.assertIn("      ~/Documents/app\n", shown)
        self.assertNotIn(self.home, shown)
        self.assertIn("[✓] " + catalog_text("install.trust_done"), shown)
        projects = json.loads(self.read(".claude.json"))["projects"]
        self.assertEqual(sorted(projects), [project])

    def test_everything_goes_to_its_own_folder(self):
        self.install()
        elsewhere = {".config/herdr/config.toml", ".config/ghostty/config", ".config/starship.toml"}
        installed = self.read(".local/state/herdr-fold/installed.txt").split()
        self.assertEqual([rel for rel in installed
                          if not rel.startswith(".config/herdr-fold/") and rel not in elsewhere], [])
        self.assertEqual(os.listdir(self.path(".config/herdr")), ["config.toml"])

    def test_fresh_install_records_what_it_installed(self):
        self.install()
        installed = self.read(".local/state/herdr-fold/installed.txt").split("\n")
        self.assertIn(".config/herdr-fold/herdrlib.py", installed)
        self.assertIn(".config/ghostty/config", installed)

    def test_file_dropped_from_the_package_is_removed(self):
        self.install()
        self.drop_from_package(".config/herdr-fold/tui.py")
        self.install()
        self.assertFalse(os.path.exists(self.path(".config/herdr-fold/tui.py")))
        self.assertNotIn(".config/herdr-fold/tui.py", self.read(".local/state/herdr-fold/installed.txt").split("\n"))

    def test_a_dropped_file_another_macs_prepare_still_uses_stays(self):
        self.install()
        # this Mac is a machine of another
        self.write(".local/state/herdr-fold/prepared.txt", ".config/herdr-fold/tui.py\n")
        self.drop_from_package(".config/herdr-fold/tui.py")
        out = self.install()
        self.assertTrue(os.path.isfile(self.path(".config/herdr-fold/tui.py")), out)
        self.assertNotIn(".config/herdr-fold/tui.py", self.read(".local/state/herdr-fold/installed.txt").split("\n"))

    def test_a_folder_emptied_by_the_cleanup_goes_too(self):
        self.install()
        with open(os.path.join(self.pkg, "files.txt")) as f:
            places = [line.split("|")[1].strip() for line in f if "|" in line and not line.lstrip().startswith("#")]
        for rel in places:
            if rel.startswith(".config/herdr-fold/plugins/"):
                self.drop_from_package(rel)
        self.install()
        self.assertFalse(os.path.exists(self.path(".config/herdr-fold/plugins")))
        self.assertTrue(os.path.isfile(self.path(".config/herdr-fold/herdrlib.py")))

    def test_machines_own_file_comes_back_when_the_package_drops_it(self):
        self.write(".config/starship.toml", "# the machine's own prompt\n")
        self.install()
        self.assertNotEqual(self.read(".config/starship.toml"), "# the machine's own prompt\n")
        self.drop_from_package(".config/starship.toml")
        self.install()
        self.assertEqual(self.read(".config/starship.toml"), "# the machine's own prompt\n")

    def test_starship_starts_only_in_herdr_panes(self):
        self.write(".zshrc", "# the machine's own zshrc\n")
        self.install()
        self.assertNotIn("starship init", self.read(".zshrc"))
        self.assertIn('eval "$(starship init zsh)"', self.read(".config/herdr-fold/pane-env.sh"))

    # ~/.zshrc gets one marked block (the herdr panes' environment), replaced on every run
    BEGIN, END = "# >>> herdr-fold >>>", "# <<< herdr-fold <<<"

    def block(self, zshrc):
        lines = zshrc.split("\n")
        return lines[lines.index(self.BEGIN):lines.index(self.END) + 1]

    def test_zshrc_has_one_block_however_often_the_installer_runs(self):
        self.write(".zshrc", "# own line before\n")
        self.install()
        with open(self.path(".zshrc"), "a") as f:
            f.write("# own line after\n")
        self.install()
        zshrc = self.read(".zshrc")
        self.assertEqual((zshrc.count(self.BEGIN), zshrc.count(self.END)), (1, 1))
        self.assertTrue(zshrc.startswith("# own line before\n"))
        self.assertTrue(zshrc.endswith(self.END + "\n# own line after\n"), zshrc)

    def test_the_block_loads_the_installed_pane_environment(self):
        self.install()
        sourced = [line for line in self.block(self.read(".zshrc")) if "pane-env.sh" in line]
        self.assertEqual(len(sourced), 1)
        rel = sourced[0].split('"$HOME/')[1].split('"')[0]
        self.assertIn(rel, self.read(".local/state/herdr-fold/installed.txt").split("\n"))
        self.assertTrue(os.path.isfile(self.path(rel)))

    def test_the_block_is_quiet_outside_a_pane_and_without_the_pane_environment(self):
        self.install()
        os.remove(self.path(".config/herdr-fold/pane-env.sh"))      # e.g. the folder deleted by hand
        block = "\n".join(self.block(self.read(".zshrc")))
        for pane in ("", "p1"):
            done = subprocess.run(["/bin/sh", "-c", block], capture_output=True, text=True,
                                  env={"HOME": self.home, "HERDR_PANE_ID": pane, "PATH": "/usr/bin:/bin"})
            self.assertEqual((done.returncode, done.stderr), (0, ""), pane)  # a failed status colors the first prompt

    def test_a_linked_zshrc_stays_a_link(self):
        self.write("dotfiles/zshrc", "# kept in a dotfiles repo\n")
        os.symlink(self.path("dotfiles/zshrc"), self.path(".zshrc"))
        self.install()
        self.assertTrue(os.path.islink(self.path(".zshrc")))
        self.assertIn(self.BEGIN, self.read("dotfiles/zshrc"))

    def test_a_begin_marker_without_its_end_loses_nothing(self):
        self.write(".zshrc", f"# own line\n{self.BEGIN}\nexport KEEP=1\n")
        self.install()
        zshrc = self.read(".zshrc")
        self.assertTrue(zshrc.startswith(f"# own line\n{self.BEGIN}\nexport KEEP=1\n"), zshrc)
        self.assertEqual(zshrc.count(self.END), 1)

    def gh_calls(self):
        if not os.path.exists(self.gh_log):
            return []
        with open(self.gh_log) as f:
            return [line.strip() for line in f]

    def test_github_account_is_shown_when_already_logged_in(self):
        self.env["GH_STUB_STATE"] = "in"
        self.assertIn("GitHub: testuser", self.install())

    def test_git_pushing_through_gh_is_recorded_for_the_uninstaller(self):
        self.env["GH_STUB_STATE"] = "in"
        self.install()
        self.assertIn("gh auth setup-git --hostname github.com", self.gh_calls())
        self.assertEqual(self.read(".local/state/herdr-fold/outside.txt").splitlines(), ["github-git"])

    def test_github_login_never_starts_without_a_terminal(self):
        out = self.install()
        self.assertFalse(any(call.startswith("gh auth login") for call in self.gh_calls()))
        self.assertIn("gh auth login --web", out)

    def test_existing_git_identity_is_left_alone(self):
        self.write(".gitconfig", "[user]\n\tname = Own Name\n\temail = own@example.com\n")
        self.install()
        self.assertEqual(self.read(".gitconfig"), "[user]\n\tname = Own Name\n\temail = own@example.com\n")

    def test_a_missing_git_identity_is_offered_as_githubs_noreply_address(self):
        # a real address in a commit goes public with it: under GitHub's sign-in, its login and noreply address
        self.env["GH_STUB_STATE"] = "in"
        shown = self.install_answering({})
        self.assertIn("[testuser]", shown)
        self.assertIn("[1234567+testuser@users.noreply.github.com]", shown)
        config = self.read(".gitconfig")
        self.assertIn("name = testuser", config)
        self.assertIn("email = 1234567+testuser@users.noreply.github.com", config)

    def test_missing_git_identity_is_not_guessed_without_a_terminal(self):
        out = self.install()
        self.assertFalse(os.path.exists(self.path(".gitconfig")) and "name =" in self.read(".gitconfig"))
        self.assertIn("git config --global user.name", out)

    def test_a_python_on_path_leaves_no_cache_behind(self):
        stubs(os.path.join(self.tmp, "stubs"), {"python3": IN_PLACE_PYTHON})
        self.install()
        caches = [os.path.join(root, name) for top in (self.home, self.pkg) for root, dirs, _ in os.walk(top)
                  for name in dirs if name == "__pycache__"]
        self.assertEqual(caches, [])

    def test_a_herdr_pane_is_told_at_the_end_to_reopen_ghostty(self):
        self.env["HERDR_PANE_ID"] = "w1:p1"
        out = self.install()
        before, done = out.split(catalog_text("install.step_done"))
        self.assertNotIn("in a herdr pane", before)                  # nothing to do about it yet: no line, no count
        self.assertEqual(self.lines_of(out, "install.step_done")[:2],     # what to do next, not a warning
                         ["[✓] " + catalog_text("install.finished"), catalog_text("install.reopen_ghostty")])
        self.assertNotIn("server stop", out)                      # that would stop the agents

    def test_an_open_ghostty_is_to_be_reopened_from_a_plain_terminal_too(self):
        # the theme, its icon and the keys take effect in a Ghostty started after the install
        stubs(os.path.join(self.tmp, "stubs"), {"pgrep": '#!/bin/sh\n[ "$*" = "-xq ghostty" ]\n'})
        self.assertIn(catalog_text("install.reopen_ghostty"), self.lines_of(self.install(), "install.step_done"))

    def test_no_reopen_line_without_an_open_ghostty(self):
        self.assertNotIn(catalog_text("install.reopen_ghostty"), self.install())

    def herdr_status(self, client, server):
        path = os.path.join(self.tmp, "status")
        with open(path, "w") as f:
            f.write(f"client:\n  version: {client}\n\nserver:\n  status: running\n  version: {server}\n")
        self.env["STUB_STATUS"] = path

    def test_an_old_herdr_in_the_background_is_handed_over_not_stopped(self):
        self.herdr_status("0.9.6", "0.9.5")
        self.assertIn("[!] " + catalog_text("install.handoff", "0.9.6", "0.9.5"), self.install())

    def test_the_same_herdr_in_the_background_says_nothing(self):
        self.herdr_status("0.9.5", "0.9.5")
        self.assertNotIn("live-handoff", self.install())

    def test_double_click_launcher_opens_in_terminal(self):
        launcher = os.path.join(PACKAGE, "install.command")
        self.assertTrue(os.access(launcher, os.X_OK))
        with open(launcher) as f:
            self.assertIn("install.sh", f.read())

    def test_ai_sessions_are_never_deleted(self):
        sessions = (".claude/projects/-x/abc.jsonl", ".codex/sessions/2026/10/17/rollout-abc.jsonl",
                    ".codex/session_index.jsonl", ".local/state/herdr/plugins/herdr-fold.sessions-view/names.json",
                    ".claude/history.jsonl", ".codex/history.jsonl", ".claude/file-history/abc/1.txt")
        for rel in sessions:
            self.write(rel, "conversation\n")
        self.write(".local/state/herdr-fold/installed.txt", "\n".join(sessions) + "\n")
        self.install()
        for rel in sessions:
            self.assertEqual(self.read(rel), "conversation\n", rel)

    def test_a_file_you_changed_since_the_install_is_never_pruned(self):
        self.install()
        with open(self.path(".config/ghostty/config"), "a") as f:
            f.write("# my own line\n")
        for _ in range(4):                                                  # more installs than dated backups kept
            self.install()
        kept = [os.path.join(base, name) for base, _, names in os.walk(self.path(".local/state/herdr-fold"))
                for name in names if name == "config" and "changed-" in base]
        self.assertEqual(len(kept), 1, kept)
        with open(kept[0]) as f:
            self.assertIn("# my own line", f.read())

    def test_a_file_with_nothing_recorded_of_it_is_never_pruned(self):
        # without the sum the install recorded, a changed file cannot be told from an earlier version of the package
        self.install()
        with open(self.path(".config/ghostty/config"), "a") as f:
            f.write("# my own line\n")
        os.remove(self.path(".local/state/herdr-fold/installed.sha256"))
        for _ in range(4):
            self.install()
        kept = [os.path.join(base, name) for base, _, names in os.walk(self.path(".local/state/herdr-fold"))
                for name in names if name == "config" and "changed-" in base]
        self.assertEqual(len(kept), 1, kept)

    def test_the_backups_are_their_owners_only(self):
        # they hold the machine's own files: on a shared machine no one else may read them
        self.write(".config/starship.toml", "# own prompt\n")
        os.chmod(self.path(".config/starship.toml"), 0o600)
        self.install()
        mode = lambda rel: stat.S_IMODE(os.stat(self.path(rel)).st_mode)      # noqa: E731
        self.assertEqual(mode(".local/state/herdr-fold"), 0o700)
        self.assertEqual(mode(".local/state/herdr-fold/original/.config/starship.toml"), 0o600)

    def test_a_file_that_cannot_be_saved_first_is_left_as_it_is(self):
        self.write(".config/starship.toml", "# own prompt\n")
        self.write(".local/state/herdr-fold/original", "in the way\n")         # the originals' folder cannot be made
        out = self.install()
        self.assertEqual(self.read(".config/starship.toml"), "# own prompt\n")
        self.assertIn("[!] " + catalog_text("install.not_kept", ".config/starship.toml"), out)
        self.assertNotIn(".config/starship.toml", self.read(".local/state/herdr-fold/installed.txt").split())

    def test_a_linked_dotfile_is_set_aside_as_a_link_and_never_written_through(self):
        self.write("dotfiles/starship.toml", "# mine, in my dotfiles\n")
        os.makedirs(self.path(".config"), exist_ok=True)
        os.symlink(self.path("dotfiles/starship.toml"), self.path(".config/starship.toml"))
        self.install()
        self.assertEqual(self.read("dotfiles/starship.toml"), "# mine, in my dotfiles\n")
        self.assertFalse(os.path.islink(self.path(".config/starship.toml")))
        self.assertTrue(os.path.islink(self.path(".local/state/herdr-fold/original/.config/starship.toml")))

    def test_keeps_the_three_newest_dated_backups(self):
        for stamp in ("20260101-000000", "20260201-000000", "20260301-000000", "20260401-000000", "20260501-000000"):
            self.write(f".local/state/herdr-fold/{stamp}/x", "old backup\n")
        self.install()
        dated = sorted(d for d in os.listdir(self.path(".local/state/herdr-fold")) if d[:1].isdigit())
        self.assertEqual(dated, ["20260301-000000", "20260401-000000", "20260501-000000"])


if __name__ == "__main__":
    unittest.main()
