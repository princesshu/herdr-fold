"""Tests for uninstall.sh after a full install, in a temporary HOME with a space in it (herdr, brew, gh are stubs):
installed files and herdr-fold's settings go (a changed file is set aside), the machine's own files and Claude's
earlier status line come back; the conversations, herdr's data and the Homebrew programs stay."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from support import FORGET_PLUGIN, PACKAGE, catalog_text, copy_package, from_homebrew, stubs

HERDR = """#!/bin/sh
printf '%s\\n' "herdr $*" >> "$STUB_HERDR_LOG"
case "$*" in
  "plugin uninstall "*" "*) echo "usage: herdr plugin uninstall <plugin_id|owner/repo[/subdir...]>" >&2; exit 2 ;;
  "plugin list --json") cat "$STUB_PLUGINS" ;;
  "integration status") cat "$STUB_INTEGRATIONS" ;;
  "plugin unlink "*|"plugin uninstall "*)        # like herdr: only a running herdr takes a plugin off
    [ -n "${STUB_NO_SERVER:-}" ] && { echo '{"error":{"code":"server_not_running"}}'; exit 1; }
    """ + FORGET_PLUGIN + """ "$STUB_PLUGINS" "$3" 2>/dev/null ;;
  "integration uninstall "*) [ -n "${STUB_INTEGRATION_FAILS:-}" ] && exit 1 ;;
esac
exit 0
"""
CONVERSATIONS = [".claude/projects/-Users-dev-app/s1.jsonl", ".codex/sessions/2026/10/22/rollout-1.jsonl",
                 ".local/state/herdr/plugins/herdr-fold.sessions-view/names.json"]
THEIRS = {"type": "command", "command": "printf mine"}
THEIR_CONFIG = '# mine\n[keys]\nnext_agent = ["ctrl+n"]\n'


class Uninstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home = os.path.join(self.tmp, "Test User")
        self.pkg = os.path.join(self.tmp, "package")
        copy_package(self.pkg)
        fakes = stubs(os.path.join(self.tmp, "stubs"), {"herdr": HERDR, "defaults": None, "gh": None, "brew": None,
                                                       "open": None, "claude": None, "codex": None})
        from_homebrew(fakes)
        self.log, self.plugins = os.path.join(self.tmp, "herdr-calls"), os.path.join(self.tmp, "plugins.json")
        with open(self.plugins, "w") as f:
            json.dump({"result": {"plugins": []}}, f)
        self.integrations = os.path.join(self.tmp, "integrations")
        self.set_integrations("claude: not installed (x)\ncodex: not installed (x)\n")
        self.env = {"HOME": self.home, "PATH": f"{fakes}:/usr/bin:/bin", "TERM": "dumb", "HERDR_FOLD_YES": "1",
                    "HERDR_FOLD_NO_BREW": "1", "HERDR_FOLD_NO_MACHINES": "1", "STUB_HERDR_LOG": self.log,
                    "STUB_PLUGINS": self.plugins, "STUB_INTEGRATIONS": self.integrations}
        self.write(".zshrc", "# own\n")
        self.write(".config/starship.toml", "# own prompt\n")
        self.write(".claude/settings.json", json.dumps({"statusLine": THEIRS, "model": "opus"}))
        for rel in CONVERSATIONS + [".config/herdr/herdr.sock"]:
            self.write(rel, "{}\n")

    def set_integrations(self, text):
        with open(self.integrations, "w") as f:
            f.write(text)

    def path(self, rel):
        return os.path.join(self.home, rel)

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "w") as f:
            f.write(text)

    def read(self, rel):
        with open(self.path(rel)) as f:
            return f.read()

    def run_script(self, name):
        done = subprocess.run(["bash", os.path.join(self.pkg, name)], env=self.env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=300)
        self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-2000:])
        return done.stdout

    def install_and_uninstall(self, between=None):
        self.run_script("install.sh")
        installed = self.read(".local/state/herdr-fold/installed.txt").split()
        if between:
            between()
        return installed, self.run_script("uninstall.sh")

    def test_the_machines_own_files_come_back(self):
        self.install_and_uninstall()
        self.assertEqual(self.read(".config/starship.toml"), "# own prompt\n")

    def test_what_it_installed_is_gone(self):
        installed, out = self.install_and_uninstall()
        left = [rel for rel in installed if os.path.exists(self.path(rel)) and rel != ".config/starship.toml"]
        self.assertEqual(left, [], out)
        self.assertFalse(os.path.exists(self.path(".config/herdr-fold")), out)
        self.assertFalse(os.path.exists(self.path(".config/ghostty")), out)

    def test_the_zshrc_block_goes(self):
        self.install_and_uninstall()
        self.assertEqual(self.read(".zshrc"), "# own\n")

    def test_the_parts_added_to_their_herdr_settings_go(self):
        self.write(".config/herdr/config.toml", THEIR_CONFIG)
        _, out = self.install_and_uninstall()
        self.assertEqual(self.read(".config/herdr/config.toml"), THEIR_CONFIG)
        # their settings as they were before the add stay, and where is said
        self.assertEqual(self.read(".local/state/herdr-fold/original/.config/herdr/config.toml"), THEIR_CONFIG)
        self.assertIn(catalog_text("uninstall.kept", "~/.local/state/herdr-fold"), out)

    def test_a_file_changed_since_the_install_is_set_aside(self):
        changed = ".config/herdr-fold/tui.py"
        _, out = self.install_and_uninstall(lambda: self.write(changed, "# my change\n"))
        self.assertFalse(os.path.exists(self.path(changed)))
        kept = [os.path.join(base, name) for base, _, names in os.walk(self.path(".local/state/herdr-fold"))
                for name in names if name == "tui.py"]
        self.assertEqual(len(kept), 1, out)
        with open(kept[0]) as f:
            self.assertEqual(f.read(), "# my change\n")
        self.assertIn("[+]", out)

    def test_a_linked_dotfile_comes_back_as_its_link(self):
        self.write("dotfiles/starship.toml", "# mine, in my dotfiles\n")
        os.remove(self.path(".config/starship.toml"))
        os.symlink(self.path("dotfiles/starship.toml"), self.path(".config/starship.toml"))
        self.install_and_uninstall()
        self.assertTrue(os.path.islink(self.path(".config/starship.toml")))
        self.assertEqual(self.read("dotfiles/starship.toml"), "# mine, in my dotfiles\n")

    def test_no_python_cache_is_left(self):
        def run_python_there():         # a Python that writes its cache in place (Homebrew's, Linux's): the picker
            self.write(".config/herdr-fold/themes/__pycache__/apply.cpython-314.pyc", "")
            self.write(".config/herdr-fold/__pycache__/i18n.cpython-314.pyc", "")
        self.install_and_uninstall(run_python_there)
        self.assertFalse(os.path.exists(self.path(".config/herdr-fold")))

    def test_a_conversation_on_the_record_stays(self):
        def record_one():
            self.write(".claude/history.jsonl", "{}\n")
            with open(self.path(".local/state/herdr-fold/installed.txt"), "a") as f:
                f.write(".claude/history.jsonl\n")
        self.install_and_uninstall(record_one)
        self.assertTrue(os.path.isfile(self.path(".claude/history.jsonl")))

    def test_the_zshrc_line_only_when_a_block_was_there(self):
        _, out = self.install_and_uninstall(lambda: self.write(".zshrc", "# own\n"))
        self.assertNotIn(catalog_text("uninstall.zshrc"), out)

    def linked(self, *ids):
        with open(self.plugins, "w") as f:
            json.dump({"result": {"plugins": [{"plugin_id": i} for i in ids]}}, f)

    def test_plugins_it_put_there_are_taken_out(self):
        _, out = self.install_and_uninstall(
            between=lambda: self.linked("herdr-fold.sessions-view", "herdr-fold.tab-layout", "herdr-fold.sidebar"))
        calls = self.calls()
        for plugin in ("herdr-fold.sessions-view", "herdr-fold.tab-layout", "herdr-fold.sidebar"):
            self.assertIn("herdr plugin unlink " + plugin, calls)
            self.assertIn(catalog_text("uninstall.plugin_removed", plugin), out)
        self.assertFalse([c for c in calls if "herdr-sidebar" in c])

    def test_the_whole_environment_plugin_goes_too(self):
        # installed from herdr's marketplace (it offered this installer): not on the record, herdr-fold's all the same
        def from_the_marketplace():
            self.linked("herdr-fold", "herdr-fold.sidebar")
            self.write(".local/state/herdr/plugins/herdr-fold/offered-123", "")
        _, out = self.install_and_uninstall(between=from_the_marketplace)
        self.assertIn("herdr plugin uninstall herdr-fold", self.calls())
        self.assertIn(catalog_text("uninstall.plugin_removed", "herdr-fold"), out)
        self.assertFalse(os.path.exists(self.path(".local/state/herdr/plugins/herdr-fold")), out)

    def test_the_marks_stay_while_the_whole_environment_plugin_does(self):
        # herdr did not take it off (not running): its marks stay, or it would offer the installer again on its start
        self.env["STUB_NO_SERVER"] = "1"
        def from_the_marketplace():
            self.linked("herdr-fold")
            self.write(".local/state/herdr/plugins/herdr-fold/offered-123", "")
        _, out = self.install_and_uninstall(between=from_the_marketplace)
        self.assertIn(catalog_text("uninstall.plugin_left", "herdr-fold", "herdr plugin uninstall herdr-fold"), out)
        self.assertTrue(os.path.exists(self.path(".local/state/herdr/plugins/herdr-fold/offered-123")), out)

    def test_the_package_kept_for_herdrs_copy_goes(self):
        def kept():
            self.write(".local/share/herdr-fold/install.sh", "#\n")
            self.write(".local/share/herdr-fold/.kept-by-herdr-fold", "")
            self.write(".local/share/herdr-fold.new/install.sh", "#\n")            # a move cut short
            self.write(".local/share/herdr-fold.new/.kept-by-herdr-fold", "")
            self.write(".local/share/theirs/keep.txt", "mine\n")
        _, out = self.install_and_uninstall(between=kept)
        self.assertEqual([rel for rel in (".local/share/herdr-fold", ".local/share/herdr-fold.new")
                          if os.path.exists(self.path(rel))], [], out)
        self.assertEqual(self.read(".local/share/theirs/keep.txt"), "mine\n")

    def test_a_plugin_taken_over_is_named_with_the_way_back(self):
        # installed alone from herdr's marketplace before: the installer took its place, so it is gone after this
        with open(self.plugins, "w") as f:
            json.dump({"result": {"plugins": [{"plugin_id": "herdr-fold.sidebar", "events": [], "plugin_root": "",
                                               "source": {"kind": "github"}}]}}, f)
        _, out = self.install_and_uninstall()
        self.assertIn(catalog_text("uninstall.taken_back", "herdr-fold.sidebar",
                                   "herdr plugin install princesshu/herdr-fold/src/plugins/sidebar"), out)

    def test_a_folder_the_installer_did_not_make_stays(self):
        # a clone of someone's in ~/.local/share/herdr-fold: not the installer's kept package
        _, out = self.install_and_uninstall(between=lambda: self.write(".local/share/herdr-fold/notes.txt", "mine\n"))
        self.assertEqual(self.read(".local/share/herdr-fold/notes.txt"), "mine\n")

    def test_a_plugin_herdr_did_not_take_off_is_named_with_its_command(self):
        # herdr takes a plugin off only while it runs: no "removed" then, but the command that does it
        self.env["STUB_NO_SERVER"] = "1"
        _, out = self.install_and_uninstall(between=lambda: self.linked("herdr-fold.sidebar"))
        self.assertNotIn(catalog_text("uninstall.plugin_removed", "herdr-fold.sidebar"), out)
        self.assertIn(catalog_text("uninstall.plugin_left", "herdr-fold.sidebar",
                                   "herdr plugin unlink herdr-fold.sidebar"), out)

    def plugin_folders(self, ids):
        """What herdr keeps of plugins IDS after unlinking them: their config folders; the tab layout's state folder,
        empty; and AI Sessions' conversation names. Returns the folders that ought to go."""
        for plugin_id in ids:
            os.makedirs(self.path(".config/herdr/plugins/config/" + plugin_id), exist_ok=True)
        os.makedirs(self.path(".local/state/herdr/plugins/herdr-fold.tab-layout"), exist_ok=True)
        self.write(".local/state/herdr/plugins/herdr-fold.sessions-view/names.json", '{"s1": "my work"}\n')
        return [self.path(".config/herdr/plugins/config/" + plugin_id) for plugin_id in ids] + [
            self.path(".local/state/herdr/plugins/herdr-fold.tab-layout")]

    def test_no_empty_plugin_folder_is_left_and_the_names_stay(self):
        ids = ("herdr-fold.sessions-view", "herdr-fold.tab-layout", "herdr-fold.sidebar")
        folders = []

        def between():
            self.linked(*ids)
            folders.extend(self.plugin_folders(ids))
        _, out = self.install_and_uninstall(between)
        self.assertEqual([folder for folder in folders if os.path.exists(folder)], [], out)
        self.assertEqual(self.read(".local/state/herdr/plugins/herdr-fold.sessions-view/names.json"),
                         '{"s1": "my work"}\n')

    def test_a_plugin_herdr_did_not_take_off_keeps_its_folders(self):
        self.env["STUB_NO_SERVER"] = "1"

        def between():
            self.linked("herdr-fold.sidebar")
            self.plugin_folders(["herdr-fold.sidebar"])
        self.install_and_uninstall(between)
        self.assertTrue(os.path.exists(self.path(".config/herdr/plugins/config/herdr-fold.sidebar")))

    def test_a_plugin_herdr_no_longer_has_is_left_alone(self):
        _, out = self.install_and_uninstall(between=lambda: self.linked("herdr-fold.sidebar"))
        self.assertNotIn("herdr plugin unlink herdr-fold.tab-layout", self.calls())
        self.assertNotIn(catalog_text("uninstall.plugin_removed", "herdr-fold.tab-layout"), out)

    def calls(self):
        with open(self.log) as f:
            return f.read().splitlines()

    def test_the_integrations_it_put_there_are_taken_out(self):
        self.install_and_uninstall()
        self.assertIn("herdr integration uninstall claude", self.calls())
        self.assertIn("herdr integration uninstall codex", self.calls())

    def test_an_integration_herdr_did_not_take_off_is_named_with_its_command(self):
        self.env["STUB_INTEGRATION_FAILS"] = "1"
        _, out = self.install_and_uninstall()
        self.assertNotIn(catalog_text("uninstall.plugin_removed", "integration:codex"), out)
        self.assertIn(catalog_text("uninstall.integration_left", "codex", "herdr integration uninstall codex"), out)

    def test_an_integration_that_was_there_before_stays(self):
        self.set_integrations("claude: installed (x)\ncodex: not installed (x)\n")
        self.install_and_uninstall()
        self.assertNotIn("herdr integration uninstall claude", self.calls())
        self.assertIn("herdr integration uninstall codex", self.calls())

    def test_claudes_earlier_status_line_comes_back(self):
        self.install_and_uninstall()
        settings = json.loads(self.read(".claude/settings.json"))
        self.assertEqual(settings, {"statusLine": THEIRS, "model": "opus"})

    def test_without_an_earlier_one_herdr_folds_just_goes(self):
        self.write(".claude/settings.json", json.dumps({"model": "opus"}))
        self.install_and_uninstall()
        self.assertEqual(json.loads(self.read(".claude/settings.json")), {"model": "opus"})

    def test_the_sidebars_colors_and_settings_go(self):
        folder = ".local/state/herdr/plugins/herdr-fold.sidebar"
        self.write(".local/state/herdr/plugins/other/state.json", "{}\n")

        def used():
            self.assertTrue(os.path.isfile(self.path(f"{folder}/colors.json")))          # the theme wrote it
            self.write(f"{folder}/settings.json", "{}\n")                              # the sidebar's own toggles
            self.write(f"{folder}/resume-0f1e2d3c4b5a.json", "{}\n")                  # a handover never taken up
            self.write(f"{folder}/seed-w1-t3.json", "{}\n")                           # a preview tab's, never taken up
            self.write(f"{folder}/preview-w1.json", "{}\n")                           # a preview tab still open
            self.write(f"{folder}/issues-0123456789abcdef.json", "{}\n")             # a repository's issues
            self.write(f"{folder}/column.json", '{"ratio": 0.6}\n')                    # the column's width
            self.write(f"{folder}/conversations.json", '{"collapsed": true}\n')       # the Conversations choice
            self.write(f"{folder}/conversation-index.json", "{}\n")                   # what it read of the files
            self.write(f"{folder}/panels.json", '{"w1:t1": ["sidebar"]}\n')           # what each tab has had
            self.write(f"{folder}/.panels.json.k3j9x2.tmp", "{")                       # a write cut short
        _, out = self.install_and_uninstall(between=used)
        self.assertFalse(os.path.exists(self.path(folder)), out)
        self.assertTrue(os.path.isfile(self.path(".local/state/herdr/plugins/other/state.json")))

    def test_the_loading_animations_colors_go(self):
        colors, cut = ".local/state/herdr-fold/loading-colors.txt", ".local/state/herdr-fold/.loading-colors.txt.a1.tmp"

        def used():
            self.assertTrue(os.path.isfile(self.path(colors)))                     # the theme wrote it
            self.write(cut, "2;")                                                  # a write cut short
        _, out = self.install_and_uninstall(between=used)
        self.assertFalse(os.path.exists(self.path(colors)), out)
        self.assertFalse(os.path.exists(self.path(cut)), out)

    def test_the_themes_app_icon_goes(self):
        include, icons = ".config/ghostty/herdr-fold-icon", ".local/state/herdr-fold/ghostty-icon"
        cut = ".config/ghostty/.herdr-fold-icon.a1.tmp"

        def used():
            self.assertTrue(os.path.isfile(self.path(include)))                    # the theme drew it
            self.assertTrue(os.listdir(self.path(icons)))
            self.write(cut, "#")                                                   # a write cut short
        _, out = self.install_and_uninstall(between=used)
        self.assertEqual([path for path in [include, icons, cut] if os.path.exists(self.path(path))], [], out)

    def outside(self, *lines):
        # what the installer and machines.sh did outside herdr-fold's own folders, as they record it
        with open(self.path(".local/state/herdr-fold/outside.txt"), "a") as f:
            f.writelines(line + "\n" for line in lines)

    def test_what_stays_on_the_mac_is_named_with_where_it_is(self):
        # nothing private stays unsaid: each thing kept is named, with how to take it off where that is a command
        def used():
            self.write(".config/herdr-fold/machines.txt",
                       "# the list\nalpha | dev@alpha.example | linux\nwin1 | dev@192.0.2.9 | windows\n")
            self.write(".config/herdr-fold/private-words.txt", "word\n")
            self.outside("ssh-key", "known-host alpha.example", "known-host 192.0.2.9", "github-sign-in", "github-git",
                         "git-author")
        _, out = self.install_and_uninstall(between=used)
        for key, *args in (
                ("uninstall.kept_names", "~/.local/state/herdr/plugins/herdr-fold.sessions-view/names.json"),
                ("uninstall.kept_machine_list", "~/.config/herdr-fold/machines.txt"),
                ("uninstall.kept_private_words", "~/.config/herdr-fold/private-words.txt"),
                ("uninstall.kept_ssh_key",),
                ("uninstall.kept_host_keys", "alpha.example, 192.0.2.9"),
                ("uninstall.kept_github",),
                ("uninstall.kept_github_git",),
                ("uninstall.kept_git_author",),
                ("uninstall.machines", "alpha, win1")):
            self.assertIn(catalog_text(key, *args), out)
        for rel in (".config/herdr-fold/machines.txt", ".config/herdr-fold/private-words.txt"):
            self.assertTrue(os.path.isfile(self.path(rel)), rel)
        self.assertNotIn(catalog_text("uninstall.kept", "~/.config/herdr-fold"),           # each file said instead
                         [line.strip() for line in out.splitlines()])
        self.assertFalse(os.path.exists(self.path(".local/state/herdr-fold/outside.txt")), out)

    def test_only_what_the_installer_did_outside_its_folders_is_named(self):
        _, out = self.install_and_uninstall()
        for key in ("uninstall.kept_ssh_key", "uninstall.kept_github", "uninstall.kept_github_git",
                    "uninstall.kept_git_author"):
            self.assertNotIn(catalog_text(key), out)
        self.assertNotIn("known_hosts", out)
        self.assertNotIn("machines.sh remove", out)                    # no machine on the list, no line about them

    def test_conversations_herdrs_own_data_and_the_programs_stay(self):
        with open(os.path.join(PACKAGE, "Brewfile")) as f:                         # Homebrew has every program
            brewfile = f.read()
        listed = {kind: "\\n".join(re.findall(rf'^{kind} "([^"]+)"', brewfile, re.M)) for kind in ("brew", "cask")}
        stubs(os.path.join(self.tmp, "stubs"),
              {"brew": f'#!/bin/sh\ncase "$*" in\n  "list --formula -1") printf "{listed["brew"]}\\n" ;;\n'
                       f'  "list --cask -1") printf "{listed["cask"]}\\n" ;;\nesac\n'})
        _, out = self.install_and_uninstall()
        for rel in CONVERSATIONS + [".config/herdr/herdr.sock"]:
            self.assertTrue(os.path.isfile(self.path(rel)), rel)
        self.assertIn("brew uninstall", out)

    def test_the_programs_named_are_the_ones_homebrew_has(self):
        # herdr from its own installer is not Homebrew's to remove
        log = os.path.join(self.tmp, "brew-calls")
        stubs(os.path.join(self.tmp, "stubs"),
              {"brew": f'#!/bin/sh\necho "$*" >> "{log}"\ncase "$*" in\n'
                       '  "list --formula -1") printf "starship\\ngh\\nbat\\ngit-delta\\nripgrep\\npcre2\\n" ;;\n'
                       '  "list --cask -1") printf "ghostty\\nfont-jetbrains-mono-nerd-font\\nfirefox\\n" ;;\n'
                       'esac\nexit 0\n'})
        _, out = self.install_and_uninstall()
        hint = ("brew uninstall starship gh bat git-delta ripgrep && "
                "brew uninstall --cask ghostty font-jetbrains-mono-nerd-font")
        self.assertIn(catalog_text("uninstall.brew", hint), out)
        with open(log) as f:
            self.assertEqual(len([call for call in f.read().splitlines() if call.startswith("list")]), 2)  # not 8


if __name__ == "__main__":
    unittest.main()
