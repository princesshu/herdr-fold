"""Tests for machines.sh prepare (fake ssh, a profile path with a space): a machine gets exactly its kind's files, keeps
its own, its AI conversations and profile bytes, joins the Herdr app's core too (`remove`: only what herdr-fold added).
Windows needs pwsh (PATH or PWSH); its profiles report as blocked (pwsh on macOS would write the real ~/Documents)."""
import glob
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

from support import (FAILING_SCP, FAKE_PYTHON, FAKE_SSH, FORGET_PLUGIN, PACKAGE, PWSH, SRC, catalog_text, copy_package,
                     logged, run_in_terminal, stubs)


THEIRS = {"type": "command", "command": "printf 'root@server:/srv/app'"}
# herdr on the Mac and on the machine: records its calls; knows the machine only when a test says so (STUB_MACHINE_ID);
# lists the plugins in $HOME/herdr-plugins.json, nothing it can be read from without it
FAKE_HERDR = """#!/bin/sh
printf '%s\\n' "herdr $*" >> "$HOME/herdr-calls"
case "$*" in
  "plugin uninstall "*" "*) echo "usage: herdr plugin uninstall <plugin_id|owner/repo[/subdir...]>" >&2; exit 2 ;;
  "plugin list --json") cat "$HOME/herdr-plugins.json" 2>/dev/null ;;
  "plugin unlink "*|"plugin uninstall "*) """ + FORGET_PLUGIN + """ "$HOME/herdr-plugins.json" "$3" 2>/dev/null ;;
  "machine list --json") if [ -n "$STUB_MACHINE_ID" ]; then echo '[{"label": "box", "id": "m1"}]'; else echo '[]'; fi ;;
esac
exit 0
"""


class Prepare:
    """A temporary Mac and machine (one folder) with the fakes; prepare() runs ./machines.sh prepare."""
    os_name = ""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.package = copy_package(os.path.join(self.tmp, "package"))
        self.profile = os.path.join(self.tmp, "Test User")
        os.makedirs(os.path.join(self.profile, ".config", "herdr-fold"))
        os.makedirs(os.path.join(self.profile, ".claude"))
        with open(os.path.join(self.profile, ".config", "herdr-fold", "machines.txt"), "w") as f:
            f.write(f"box | box | {self.os_name}\n")
        with open(os.path.join(self.profile, ".claude", "settings.json"), "w") as f:
            json.dump({"statusLine": THEIRS, "model": "opus"}, f)
        fakes = stubs(os.path.join(self.tmp, "stubs"), {"ssh": FAKE_SSH, "scp": FAILING_SCP, "python": FAKE_PYTHON,
                                                       "herdr": FAKE_HERDR,
                                                       **{name: "#!/bin/sh\nexit 0\n" for name in ("starship", "git")}})
        # the machine-side scripts put ~/.local/bin first: the fake herdr goes there too, so the real one never runs
        os.makedirs(os.path.join(self.profile, ".local", "bin"))
        shutil.copy(os.path.join(fakes, "herdr"), os.path.join(self.profile, ".local", "bin", "herdr"))
        self.env = {"HOME": self.profile, "USERPROFILE": self.profile, "PROCESSOR_ARCHITECTURE": "AMD64",
                    "LOCALAPPDATA": os.path.join(self.profile, "AppData", "Local"), "PWSH": PWSH or "",
                    "TERM": "dumb", "PATH": f"{fakes}:/usr/bin:/bin", "TMPDIR": self.tmp + "/", "SHELL": "/bin/bash",
                    "HERDR_FOLD_PLATFORM": "Linux-x86_64"}

    def prepare(self):
        done = subprocess.run(["bash", os.path.join(self.package, "machines.sh"), "prepare"], env=self.env,
                              capture_output=True, text=True, timeout=300)
        return done.stdout + done.stderr

    def add(self):
        """./machines.sh add in a terminal (pty), every question answered with Enter."""
        shown, _ = run_in_terminal(["/bin/bash", os.path.join(self.package, "machines.sh"), "add"], self.env,
                                   lambda line: "", timeout=240)
        return shown

    def remove(self):
        self.env["STUB_MACHINE_ID"] = "1"                               # connected in herdr
        done = subprocess.run(["bash", os.path.join(self.package, "machines.sh"), "remove", "box"], env=self.env,
                              capture_output=True, text=True, timeout=300)
        return done.stdout + done.stderr

    def herdr_calls(self):
        with open(os.path.join(self.profile, "herdr-calls")) as f:
            return f.read().splitlines()

    def settings(self):
        with open(os.path.join(self.profile, ".claude", "settings.json"), encoding="utf-8-sig") as f:
            return json.load(f)

    def plugins_listed(self, *ids):
        """What the machine's herdr says it has."""
        with open(os.path.join(self.profile, "herdr-plugins.json"), "w") as f:
            json.dump({"result": {"plugins": [{"plugin_id": plugin_id} for plugin_id in ids]}}, f)


class Prepared(Prepare):
    """What every kind of machine gets."""
    kind = ""
    sidebar = ""                                                    # its sidebar launcher in src/

    def test_their_status_line_is_replaced_and_kept(self):
        out = self.prepare()
        settings = self.settings()
        self.assertIn("statusline.py", settings["statusLine"]["command"], out)
        self.assertEqual(settings["statusLine"]["refreshInterval"], 10, out)  # drawn again for a narrower pane too
        self.assertEqual(settings["model"], "opus")                         # the rest of the settings stay
        saved = glob.glob(os.path.join(self.profile, ".local/state/herdr-fold", "*", "claude-statusLine.json"))
        self.assertEqual(len(saved), 1, out)
        with open(saved[0], encoding="utf-8-sig") as f:
            self.assertEqual(json.load(f), THEIRS)

    def test_no_jq_is_installed(self):
        # the status line was the only one that needed it (every line shown: a tool already there is summed up)
        self.env["HERDR_FOLD_VERBOSE"] = "1"
        out = self.prepare()
        self.assertIn("starship", out)
        self.assertNotRegex(out, r"\bjq\b")

    def test_the_loading_line_follows_the_machines_sections(self):
        # the section headers the machine prints ("  -- …") are the phase the installer's loading line shows after its
        # message (lib/loading.sh); the last one is the settings
        self.env["LOADING_PHASE"] = phase = os.path.join(self.tmp, "phase")
        out = self.prepare()
        with open(phase, encoding="utf-8") as f:
            self.assertEqual(f.read(), catalog_text(f"prepare.{'unix' if self.kind == 'unix' else 'win'}.settings")
                             + "\n", out)

    def test_the_payload_folder_goes_after_the_run(self):
        out = self.prepare()
        self.assertFalse(os.path.exists(os.path.join(self.profile, ".herdr-fold")), out)

    def test_removing_the_machine_takes_herdr_folds_off_and_gives_yours_back(self):
        self.prepare()
        out = self.remove()
        left = [rel for rel in self.listed() if os.path.exists(os.path.join(self.profile, rel))]
        self.assertEqual(left, [], out)
        self.assertFalse(os.path.exists(os.path.join(self.profile, ".local", "state", "herdr-fold")), out)
        self.assertEqual(self.settings()["statusLine"], THEIRS)
        self.assertFalse(os.path.exists(os.path.join(self.profile, ".herdr-fold")), out)
        self.assertIn("herdr machine remove m1", self.herdr_calls())
        # the Mac's machine list (here in the same folder as the machine's files) no longer has it
        with open(os.path.join(self.profile, ".config", "herdr-fold", "machines.txt")) as f:
            self.assertNotIn("box", f.read())
        self.assertEqual(os.listdir(os.path.join(self.profile, ".config", "herdr-fold")), ["machines.txt"])

    def test_the_machines_own_file_comes_back_when_the_machine_is_removed(self):
        own = os.path.join(self.profile, ".config", "herdr-fold", "i18n.py")
        with open(own, "w") as f:
            f.write("# mine\n")
        out = self.prepare()
        with open(own) as f:
            self.assertNotEqual(f.read(), "# mine\n", out)
        out = self.remove()
        with open(own) as f:
            self.assertEqual(f.read(), "# mine\n", out)

    def test_a_linked_file_is_set_aside_as_a_link_never_written_through_and_comes_back(self):
        # a dotfiles repository's file, linked where a listed one goes
        target = os.path.join(self.profile, "dotfiles", "herdrlib.py")
        os.makedirs(os.path.dirname(target))
        with open(target, "w") as f:
            f.write("# mine, in my dotfiles\n")
        link = os.path.join(self.profile, ".config", "herdr-fold", "herdrlib.py")
        os.symlink(target, link)
        out = self.prepare()
        with open(target) as f:
            self.assertEqual(f.read(), "# mine, in my dotfiles\n", out)
        self.assertFalse(os.path.islink(link), out)
        out = self.remove()
        self.assertEqual(os.readlink(link), target, out)

    def test_removing_the_machine_takes_the_sidebars_settings_too(self):
        self.prepare()
        state = os.path.join(self.profile, ".local", "state", "herdr")
        sidebar = os.path.join(state, "plugins", "herdr-fold.sidebar")
        herdrs = os.path.join(state, "agent-detection", "status.toml")
        for path in (os.path.join(sidebar, "settings.json"), os.path.join(sidebar, "resume-0f1e2d3c4b5a.json"),
                     os.path.join(sidebar, ".panels.json.k3j9x2.tmp"), os.path.join(sidebar, "seed-w1-t3.json"),
                     os.path.join(sidebar, "preview-w1.json"), os.path.join(sidebar, "issues-0123456789abcdef.json"),
                     os.path.join(sidebar, "column.json"), os.path.join(sidebar, "conversations.json"),
                     os.path.join(sidebar, "conversation-index.json"), os.path.join(sidebar, "panels.json"), herdrs):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write("{}\n")
        out = self.remove()
        self.assertFalse(os.path.exists(sidebar), out)
        self.assertTrue(os.path.isfile(herdrs), out)                     # herdr's own state is never touched

    def test_removing_the_machine_leaves_no_empty_plugin_folders(self):
        self.prepare()
        self.plugins_listed("herdr-fold.sessions-view", "herdr-fold.tab-layout")
        config = os.path.join(self.profile, ".config", "herdr", "plugins", "config")
        state = os.path.join(self.profile, ".local", "state", "herdr", "plugins")
        folders = [os.path.join(config, "herdr-fold.sessions-view"), os.path.join(config, "herdr-fold.tab-layout"),
                   os.path.join(state, "herdr-fold.tab-layout"), os.path.join(state, "herdr-fold.sessions-view")]
        for folder in folders:
            os.makedirs(folder)
        if self.kind == "unix":                     # the workspaces it follows: never made on Windows
            for name, text in (("spaces.json", '{"w1": {"label": "app"}}\n'), ("focus.json", '{"now": "w1"}\n')):
                with open(os.path.join(folders[2], name), "w") as f:
                    f.write(text)
        # AI Sessions' waits and locks (no conversation names: they would stay)
        for name in ("waits.json", "waits.json.lock", "clock.lock", "names.json.lock"):
            with open(os.path.join(folders[3], name), "w") as f:
                f.write("{}\n" if name.endswith(".json") else "")
        out = self.remove()
        self.assertEqual([folder for folder in folders if os.path.exists(folder)], [], out)

    def test_removing_the_machine_keeps_the_conversation_names_and_says_where(self):
        self.prepare()
        names = os.path.join(self.profile, ".local", "state", "herdr", "plugins", "herdr-fold.sessions-view",
                             "names.json")
        os.makedirs(os.path.dirname(names))
        with open(names, "w") as f:
            f.write('{"s1": "my work"}\n')
        out = self.remove()
        self.assertTrue(os.path.isfile(names), out)
        before, after = catalog_text({"unix": "prepare.unix", "windows": "prepare.win"}[self.kind] + ".kept_names",
                                     "\0").split("\0")
        said = [line for line in out.splitlines() if before.strip() in line and line.rstrip().endswith(after.strip())]
        self.assertEqual(len(said), 1, out)
        self.assertIn("names.json", said[0])

    def test_a_file_missing_from_the_package_is_reported_not_ticked(self):
        os.remove(os.path.join(self.package, "src", self.sidebar))
        lines = [line for line in self.prepare().splitlines() if self.sidebar in line]
        self.assertEqual([line for line in lines if "[✓]" in line], [], lines)
        self.assertTrue([line for line in lines if "[!]" in line], lines)

    def listed(self):
        found = []
        with open(os.path.join(self.package, "remote", "files.txt"), encoding="utf-8") as f:
            for row in f:
                if not row.strip() or row.lstrip().startswith("#"):
                    continue
                src, dest, kinds, _part = (c.strip() for c in row.split("|"))
                if kinds not in ("all", self.kind):
                    continue
                if "*" in src:
                    found += [dest + os.path.basename(p) for p in glob.glob(os.path.join(self.package, src))]
                else:
                    found.append(dest)
        return found

    def record(self):
        with open(os.path.join(self.profile, ".local/state/herdr-fold", "prepared.txt"), encoding="utf-8-sig") as f:
            return [line.strip() for line in f if line.strip()]

    def test_the_machine_gets_exactly_the_listed_files(self):
        out = self.prepare()
        listed = self.listed()
        self.assertTrue(listed)
        for rel in listed:
            self.assertTrue(os.path.isfile(os.path.join(self.profile, rel)), rel + "\n" + out)
        self.assertEqual(set(listed) - set(self.record()), set())

    def test_a_dropped_file_goes_and_the_machines_own_stay(self):
        own = os.path.join(self.profile, ".config", "herdr-fold", "my-notes.txt")
        with open(own, "w") as f:
            f.write("mine\n")
        self.prepare()
        dropped = ".config/herdr-fold/plugins/tab-layout/tab_layout.py"
        path = os.path.join(self.package, "remote", "files.txt")
        with open(path, encoding="utf-8") as f:
            rows = [row for row in f if "tab-layout/tab_layout.py" not in row]
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(rows)
        out = self.prepare()
        self.assertFalse(os.path.exists(os.path.join(self.profile, dropped)), out)
        self.assertTrue(glob.glob(os.path.join(self.profile, ".local/state/herdr-fold", "*", dropped)), out)
        self.assertTrue(os.path.isfile(own))
        self.assertNotIn(dropped, self.record())

    def test_a_folder_emptied_by_the_cleanup_goes_too(self):
        self.prepare()
        path = os.path.join(self.package, "remote", "files.txt")
        with open(path, encoding="utf-8") as f:
            rows = [row for row in f if "plugins/tab-layout/" not in row]
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(rows)
        out = self.prepare()
        self.assertFalse(os.path.exists(os.path.join(self.profile, ".config", "herdr-fold", "plugins", "tab-layout")),
                         out)
        self.assertTrue(os.path.isdir(os.path.join(self.profile, ".config", "herdr-fold", "plugins", "sessions-view")))

    def test_ai_conversations_are_never_removed(self):
        self.prepare()
        sessions = [".claude/projects/-srv-app/s1.jsonl", ".codex/sessions/2026/10/22/rollout-1.jsonl"]
        for rel in sessions:
            os.makedirs(os.path.dirname(os.path.join(self.profile, rel)), exist_ok=True)
            with open(os.path.join(self.profile, rel), "w") as f:
                f.write("{}\n")
        with open(os.path.join(self.profile, ".local/state/herdr-fold", "prepared.txt"), "a", encoding="utf-8") as f:
            f.write("".join(rel + "\n" for rel in sessions))                 # a record that lists them anyway
        out = self.prepare()
        for rel in sessions:
            self.assertTrue(os.path.isfile(os.path.join(self.profile, rel)), out)


class UnixPrepare(Prepared, unittest.TestCase):
    os_name, kind, sidebar = "linux", "unix", "sidebar.sh"

    # A Mac can be a machine of another Mac and have the package installed itself (install.sh, its own record
    # installed.txt): a prepare never takes that record for its own, nor removes a file the installation still uses.
    def installer_record(self, *rels):
        for rel in rels:
            os.makedirs(os.path.dirname(os.path.join(self.profile, rel)), exist_ok=True)
            with open(os.path.join(self.profile, rel), "a") as f:
                f.write("")
        os.makedirs(os.path.join(self.profile, ".local/state/herdr-fold"), exist_ok=True)
        with open(os.path.join(self.profile, ".local/state/herdr-fold", "installed.txt"), "w") as f:
            f.write("".join(rel + "\n" for rel in rels))

    def test_the_backups_are_their_owners_only(self):
        own = os.path.join(self.profile, ".config", "herdr-fold", "i18n.py")
        with open(own, "w") as f:
            f.write("# mine\n")
        os.chmod(own, 0o600)
        out = self.prepare()
        state = os.path.join(self.profile, ".local", "state", "herdr-fold")
        self.assertEqual(stat.S_IMODE(os.stat(state).st_mode), 0o700, out)
        kept = os.path.join(state, "prepared-original", ".config", "herdr-fold", "i18n.py")
        self.assertEqual(stat.S_IMODE(os.stat(kept).st_mode), 0o600, out)

    def test_the_macs_own_installation_is_left_alone(self):
        self.installer_record(".config/ghostty/config")
        out = self.prepare()
        self.assertTrue(os.path.isfile(os.path.join(self.profile, ".config", "ghostty", "config")), out)
        with open(os.path.join(self.profile, ".local/state/herdr-fold", "installed.txt")) as f:
            self.assertEqual(f.read(), ".config/ghostty/config\n")

    def test_a_dropped_file_the_installation_still_uses_stays(self):
        self.prepare()
        dropped = ".config/herdr-fold/plugins/tab-layout/tab_layout.py"
        self.installer_record(dropped)
        path = os.path.join(self.package, "remote", "files.txt")
        with open(path, encoding="utf-8") as f:
            rows = [row for row in f if "tab-layout/tab_layout.py" not in row]
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(rows)
        out = self.prepare()
        self.assertTrue(os.path.isfile(os.path.join(self.profile, dropped)), out)
        self.assertNotIn(dropped, self.record())

    def test_a_mac_with_its_own_install_keeps_its_shell_status_line_and_plugins(self):
        # this Mac's own install: its record, its .bashrc block, its status line choice and its plugin record
        self.installer_record(".config/herdr-fold/herdrlib.py")
        own = {".bashrc": "# >>> herdr-fold >>>\n# the install's own block\n# <<< herdr-fold <<<\n",
               ".config/herdr-fold/herdrlib.py": "# this Mac's own version\n",
               ".config/herdr-fold/statusline.json": '{"claude": {"effort": false}}\n',
               ".local/state/herdr-fold/plugins.txt": "herdr-fold.sidebar\n",
               ".local/state/herdr/plugins/herdr-fold.sidebar/settings.json": '{"view": "git"}\n'}
        for rel, text in own.items():
            os.makedirs(os.path.dirname(os.path.join(self.profile, rel)), exist_ok=True)
            with open(os.path.join(self.profile, rel), "w") as f:
                f.write(text)
        self.prepare()
        self.remove()
        for rel, text in own.items():
            with open(os.path.join(self.profile, rel)) as f:
                self.assertEqual(f.read(), text, rel)
        self.assertFalse([call for call in self.herdr_calls() if "unlink" in call or "uninstall" in call])

    def test_removing_the_machine_gives_its_shell_settings_back(self):
        with open(os.path.join(self.profile, ".bashrc"), "w") as f:
            f.write("# mine\n")
        self.prepare()
        with open(os.path.join(self.profile, ".bashrc")) as f:
            self.assertIn("starship init", f.read())
        self.remove()
        with open(os.path.join(self.profile, ".bashrc")) as f:
            self.assertEqual(f.read(), "# mine\n")

    def test_the_prompt_block_is_written_once(self):
        self.prepare()
        self.prepare()
        with open(os.path.join(self.profile, ".bashrc")) as f:
            self.assertEqual(f.read().count("# >>> herdr-fold >>>"), 1)

    def test_the_status_line_command_is_quoted_for_any_home(self):
        self.prepare()
        self.assertEqual(self.settings()["statusLine"]["command"], 'python3 "$HOME/.config/herdr-fold/statusline.py"')

    def test_the_machines_tools_are_listed_without_jq(self):
        done = subprocess.run(["bash", "-c", '. ./machines.sh; tools_line box linux'], cwd=self.package, env=self.env,
                              capture_output=True, text=True, timeout=60)
        self.assertIn("✓starship", done.stdout, done.stderr)
        self.assertNotIn("jq", done.stdout)

class Payload(unittest.TestCase):
    """What machines.sh sends a machine (stage_payload): the prepare script, its texts and helpers — and, to take
    herdr-fold off, the same files with nothing listed to put in place (they are what a changed file is told by)."""

    def stage(self, script, mode="", mac=None):
        """stage_payload into a folder that is the Mac's home too, with MAC's files ({location: text}) in it."""
        stage = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, stage)
        for rel, text in (mac or {}).items():
            os.makedirs(os.path.dirname(os.path.join(stage, rel)), exist_ok=True)
            with open(os.path.join(stage, rel), "w") as f:
                f.write(text)
        subprocess.run(["bash", "-c", '. ./machines.sh; stage_payload "$1" "$2" "$3"', "machines.sh",
                        stage, script, mode],
                       cwd=PACKAGE, env={"HOME": stage, "PATH": "/usr/bin:/bin"}, check=True, capture_output=True)
        with open(os.path.join(stage, "files.list")) as f:
            return stage, f.read().split()

    def test_a_unix_payload_carries_its_downloader_texts_and_helpers(self):
        stage, listed = self.stage("prepare-unix.sh")
        for rel in ("prepare-unix.sh", "fetch-tool.sh", "lang/en.txt", "lib/files.sh", "lib/output.sh", "lib/i18n.sh"):
            self.assertTrue(os.path.isfile(os.path.join(stage, rel)), rel)
        self.assertIn(".config/herdr-fold/herdrlib.py", listed)

    def test_the_sidebar_gets_the_macs_theme_colors(self):
        # without them a machine's sidebar falls back to the terminal's 16 colors: light buttons on a dark background
        colors = ".local/state/herdr/plugins/herdr-fold.sidebar/colors.json"
        for script in ("prepare-unix.sh", "prepare-windows.ps1"):
            stage, listed = self.stage(script, mac={colors: '{"badge": "#313244"}'})
            self.assertIn(colors, listed, script)
            with open(os.path.join(stage, "files", colors)) as f:
                self.assertEqual(f.read(), '{"badge": "#313244"}', script)

    def test_a_machine_for_the_app_alone_gets_the_shared_files(self):
        records = {".local/state/herdr-fold/plugins.txt": "herdr-fold.app\n",
                   ".local/state/herdr/plugins/herdr-fold.sidebar/colors.json": "{}"}
        for script in ("prepare-unix.sh", "prepare-windows.ps1"):
            _stage, listed = self.stage(script, mac=records)
            self.assertIn(".config/herdr-fold/statusline.py", listed, script)
            self.assertEqual([rel for rel in listed if "/plugins/" in rel or rel.endswith(("starship.toml",
                                                                                         "herdrlib.py"))], [], script)
        self.assertIn(".config/herdr-fold/python.ps1", listed)

    def test_a_removal_payload_lists_nothing_to_put_in_place(self):
        for script in ("prepare-unix.sh", "prepare-windows.ps1"):
            stage, listed = self.stage(script, "remove")
            self.assertEqual(listed, [], script)
            self.assertTrue(os.path.isfile(os.path.join(stage, "files", ".config", "herdr-fold", "herdrlib.py")),
                            script)


@unittest.skipUnless(PWSH, "no PowerShell (pwsh) on this machine")
class WindowsPrepare(Prepared, unittest.TestCase):
    os_name, kind, sidebar = "windows", "windows", "sidebar.ps1"

    def test_a_damaged_claude_settings_file_is_left_alone(self):
        path = os.path.join(self.profile, ".claude", "settings.json")
        for text in ('{"permissions": ', '[1, 2]', '7'):                  # cut short, or not a settings object
            with open(path, "w") as f:
                f.write(text)
            out = self.prepare()
            with open(path) as f:
                self.assertEqual(f.read(), text)
            self.assertIn(catalog_text("prepare.win.settings_unreadable", ""), out.replace(path, ""), text)

    def test_the_status_line_command_survives_a_space_in_the_user_folder(self):
        self.prepare()
        with open(os.path.join(self.profile, ".claude", "settings.json"), encoding="utf-8-sig") as f:
            command = json.load(f)["statusLine"]["command"]
        # PowerShell runs the machine's Python, in Git Bash as in PowerShell (Claude Code uses either on Windows)
        self.assertTrue(command.startswith('powershell -NoProfile -Command "& \''), command)
        self.assertIn("/Test User/.config/herdr-fold/statusline.py'\"", command)

    def test_the_status_line_runs_in_git_bash_and_in_powershell(self):
        # Claude Code on Windows runs the command in Git Bash, or in PowerShell without it
        self.prepare()
        command = self.settings()["statusLine"]["command"]
        bin_dir = stubs(os.path.join(self.tmp, "windows"), {"powershell": f'#!/bin/sh\nexec "{PWSH}" "$@"\n'})
        env = {"HOME": self.profile, "USERPROFILE": self.profile, "PATH": f"{bin_dir}:/usr/bin:/bin"}
        for shell in (["bash", "-c", command], [PWSH, "-NoProfile", "-Command", command]):
            done = subprocess.run(shell, input='{"model": {"display_name": "Opus 5.5"}}', env=env, capture_output=True,
                                  text=True, timeout=60)
            self.assertEqual(done.stdout, "\x1b[38;2;78;201;212mOpus 5.5\x1b[0m", (shell[0], done.stderr))

    def test_settings_land_in_the_profile(self):
        # ~/Documents untouched
        self.assertIn(catalog_text("prepare.win.profiles_blocked", "Restricted"), self.prepare())
        herdr = os.path.join(self.profile, ".config", "herdr-fold")
        for rel in ("herdrlib.py", "restore_panes.py", "statusline_setup.py", "i18n.py", "sidebar.ps1",
                    os.path.join("lang", "en.txt"), os.path.join("plugins", "sessions-view", "sessions.py"),
                    os.path.join("plugins", "tab-layout", "tab_layout.py")):
            self.assertTrue(os.path.isfile(os.path.join(herdr, rel)), rel)
        self.assertTrue(os.path.isfile(os.path.join(herdr, "statusline.py")))
        self.assertTrue(os.path.isfile(os.path.join(herdr, "statusline.json")))    # statusline_setup.py --apply ran

    def test_the_package_gets_there_through_a_powershell_login_shell(self):
        # Windows' SSH server with PowerShell as its shell: every command runs in it, and standard input does not get
        # through (scp fails in every test, as it does there)
        stubs(os.path.join(self.tmp, "stubs"),
              {"ssh": FAKE_SSH.replace('exec bash -c "$*"', 'exec "$PWSH" -NoProfile -Command "$*" </dev/null')})
        out = self.prepare()
        self.assertNotIn(catalog_text("machines.prepare_failed"), out)
        herdr = os.path.join(self.profile, ".config", "herdr-fold")
        for rel in ("statusline.py", "sidebar.ps1", os.path.join("plugins", "sidebar", "sidebar.py")):
            self.assertTrue(os.path.isfile(os.path.join(herdr, rel)), (rel, out))
        self.assertEqual([name for name in os.listdir(self.profile) if name.startswith(".herdr-fold")], [], out)

    def test_the_shared_connection_is_in_a_folder_of_its_own(self):
        # its socket where no one else on the Mac can put one in its place, and closed once the package is there
        log = os.path.join(self.tmp, "ssh-calls")
        record = (f'echo "$*" >> "{log}"\n'
                  f'for a; do case "$a" in ControlPath=*) stat -f "folder %Lp" "$(dirname "${{a#*=}}")" '
                  f'>> "{log}" ;; esac; done\n')
        stubs(os.path.join(self.tmp, "stubs"), {"ssh": FAKE_SSH.replace("#!/bin/bash\n", "#!/bin/bash\n" + record, 1)})
        out = self.prepare()
        with open(log) as f:
            calls = f.read().splitlines()
        folders = {call for call in calls if call.startswith("folder ")}
        self.assertEqual(folders, {"folder 700"}, out)
        self.assertTrue([call for call in calls if " -O exit " in f" {call} "], calls)


# Runs one function of prepare-windows.ps1 on its own: its definition, taken from the script's syntax tree
RUN_FUNCTION = r"""param($script, $name)
$tree = [Management.Automation.Language.Parser]::ParseFile($script, [ref]$null, [ref]$null)
$found = $tree.FindAll({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -eq $name }, $true)
foreach ($definition in $found) { . ([scriptblock]::Create($definition.Extent.Text)) }
& $name @args
"""


@unittest.skipUnless(PWSH, "no PowerShell (pwsh) on this machine")
class WindowsProfile(unittest.TestCase):
    """The prompt block in a PowerShell profile goes in and comes out with every other byte as it was, whatever the
    profile's encoding: Windows PowerShell's own profiles are often ANSI, some UTF-16."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.runner = os.path.join(self.tmp, "run.ps1")
        with open(self.runner, "w") as f:
            f.write(RUN_FUNCTION)
        self.profile = os.path.join(self.tmp, "Documents", "PowerShell", "Microsoft.PowerShell_profile.ps1")

    def set_block(self, block):
        script = os.path.join(PACKAGE, "remote", "prepare-windows.ps1")
        done = subprocess.run([PWSH, "-NoProfile", "-File", self.runner, script, "Set-Block", self.profile, block],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        if os.path.exists(self.profile):
            with open(self.profile, "rb") as f:
                return f.read()
        return None

    def test_every_byte_of_theirs_stays_in_any_encoding(self):
        block = "\n# >>> herdr-fold >>>\n# the prompt\n# <<< herdr-fold <<<"
        os.makedirs(os.path.dirname(self.profile))
        for encoding, theirs in (("ANSI", b"# mine: caf\xe9\r\n"), ("UTF-8", "\ufeff# mine: café\r\n".encode()),
                                 ("UTF-16", "\ufeff# mine: café\r\n".encode("utf-16-le"))):
            with open(self.profile, "wb") as f:
                f.write(theirs)
            added = self.set_block(block)
            self.assertTrue(added.startswith(theirs), encoding)
            text = added.decode("utf-16-le" if encoding == "UTF-16" else "latin-1")
            self.assertIn("# the prompt", text, encoding)
            self.assertEqual(self.set_block(block), added, encoding)                    # once, however often
            self.assertEqual(self.set_block(""), theirs, encoding)

    def test_only_the_python_software_foundation_signs_the_python_installer(self):
        # its certificate's own name, whole: another name that holds it (a Fan Club LLC's) is someone else
        check = os.path.join(self.tmp, "check.ps1")
        with open(check, "w") as f:
            f.write(RUN_FUNCTION.replace("& $name @args", "") + r'''
function Signed($name, $status) {
    $cert = [pscustomobject]@{}
    $cert | Add-Member ScriptMethod GetNameInfo ([scriptblock]::Create("'$name'"))
    [pscustomobject]@{ Status = $status; SignerCertificate = $cert }
}
foreach ($case in @(@('Python Software Foundation', 'Valid'), @('Python Software Foundation Fan Club LLC', 'Valid'),
                    @('Python Software Foundation', 'NotSigned'))) {
    Write-Output (Test-PythonSigner (Signed $case[0] $case[1]))
}
''')
        script = os.path.join(PACKAGE, "remote", "prepare-windows.ps1")
        done = subprocess.run([PWSH, "-NoProfile", "-File", check, script, "Test-PythonSigner"], capture_output=True,
                              text=True, timeout=60)
        self.assertEqual(done.stdout.split(), ["True", "False", "False"], done.stderr)

    def test_no_profile_is_made_only_to_be_emptied(self):
        self.assertIsNone(self.set_block(""))


@unittest.skipUnless(PWSH, "no PowerShell (pwsh) on this machine")
class WindowsFailure(Prepare, unittest.TestCase):
    """A Windows machine the prepare script refuses (not x86_64): the failure shows, not a [✓]."""
    os_name = "windows"

    def test_a_failed_prepare_is_reported(self):
        self.env["PROCESSOR_ARCHITECTURE"] = "ARM64"
        out = self.prepare()
        self.assertIn(catalog_text("machines.prepare_failed"), out)
        self.assertNotIn("[✓] " + catalog_text("machines.preparing"), out)
        self.assertEqual(self.settings()["statusLine"], THEIRS)


class UnixFailure(Prepare, unittest.TestCase):
    """A Linux machine the prepare script refuses (a platform it does not support): the failure shows, not a [✓]."""
    os_name = "linux"

    def test_a_failed_prepare_is_reported(self):
        self.env["HERDR_FOLD_PLATFORM"] = "Plan9-mips"
        out = self.prepare()
        self.assertIn(catalog_text("prepare.unix.unsupported", "Plan9-mips"), out)
        self.assertIn(catalog_text("machines.prepare_failed"), out)
        self.assertNotIn("[✓] " + catalog_text("machines.preparing"), out)


class Unreachable(Prepare, unittest.TestCase):
    """A machine this Mac cannot log in to: why, from what ssh says, and what to do about it."""
    os_name = "linux"

    def reason(self, ssh_says):
        stubs(os.path.join(self.tmp, "stubs"), {"ssh": f"#!/bin/sh\necho '{ssh_says}' >&2\nexit 255\n"})
        return self.prepare()

    def test_a_name_the_network_does_not_know(self):
        out = self.reason("ssh: Could not resolve hostname box: nodename nor servname provided, or not known")
        self.assertIn(catalog_text("machines.ssh_unknown_name", "box"), out)

    def test_a_machine_without_an_ssh_server(self):
        out = self.reason("ssh: connect to host box port 22: Connection refused")
        self.assertIn(catalog_text("machines.ssh_refused", "box"), out)
        self.assertIn(catalog_text("machines.ssh_turn_on"), out)

    def test_a_machine_that_does_not_answer(self):
        for says in ("ssh: connect to host box port 22: Operation timed out",
                     "ssh: connect to host box port 22: No route to host"):
            self.assertIn(catalog_text("machines.ssh_unreachable", "box"), self.reason(says), says)

    def test_a_key_it_does_not_take(self):
        out = self.reason("dev@box: Permission denied (publickey).")
        self.assertIn(catalog_text("machines.ssh_failed", "box"), out)
        self.assertIn(catalog_text("machines.ssh_passphrase"), out)

    def test_a_changed_host_key(self):
        out = self.reason("Host key verification failed.")
        self.assertIn(catalog_text("machines.ssh_host_key", "box", "box"), out)

    def test_anything_else_in_ssh_s_own_words(self):
        says = "kex_exchange_identification: read: Connection reset by peer"
        self.assertIn(catalog_text("machines.ssh_failed_why", "box", says), self.reason(says))


class Quoting(unittest.TestCase):
    """ps_quote (remote.sh): a text reaches PowerShell unchanged — PowerShell also ends a single-quoted string at the
    typographic quotes ‘ ’ ‚ ‛, not only at '."""

    @unittest.skipUnless(PWSH, "no PowerShell (pwsh) on this machine")
    def test_ps_quote_survives_typographic_quotes(self):
        text = "it’s ‘a’ ‚b‛ 'c' $HOME"
        quoted = subprocess.run(["/bin/bash", "-c", '. "$0"; ps_quote "$1"', os.path.join(SRC, "remote.sh"), text],
                                capture_output=True, text=True).stdout
        out = subprocess.run([PWSH, "-NoProfile", "-Command", f"[Console]::Out.Write({quoted})"],
                             capture_output=True, text=True).stdout
        self.assertEqual(out, text)


class HostNotAnOption(unittest.TestCase):
    """A machine's name goes to ssh after --: one that starts with - (from a typed address, a config Host line or a
    network's peer list) is a name that does not resolve, never an option that runs a program (ProxyCommand)."""

    def test_a_name_that_looks_like_an_option_runs_nothing(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        mark = os.path.join(tmp, "ran")
        host = f"-oProxyCommand=touch {mark}"
        # the real ssh, without this Mac's own ssh settings; the helpers that reach a machine by its name
        script = ('. "$0"; SSH_OPTS+=(-F /dev/null); ssh_ok "$1"; remote_os "$1"; remote_home "$1" linux; '
                  'remote_home "$1" windows; remote_is_dir "$1" linux /tmp')
        subprocess.run(["/bin/bash", "-c", script, os.path.join(SRC, "remote.sh"), host], capture_output=True,
                       timeout=60, env={"HOME": tmp, "PATH": "/usr/bin:/bin"})
        self.assertFalse(os.path.exists(mark))


# the app's core: logs its calls; lists the machines named in $STUB_HC_HAS
FAKE_HC = """#!/bin/sh
printf '%s\\n' "hc $*" >> "$HOME/hc-calls"
if [ "$*" = "machine ls --json" ]; then
  if [ -n "$STUB_HC_BROKEN" ]; then echo '{"error":{"message":"the socket path is too long"}}' >&2; exit 2
  elif [ -n "$STUB_HC_HAS" ]; then printf '{"machines": [{"name": "%s"}]}\\n' "$STUB_HC_HAS"
  else echo '{"machines": []}'; fi
fi
exit 0
"""


class AppMachines(Prepare, unittest.TestCase):
    os_name = "linux"

    def setUp(self):
        super().setUp()
        stubs(os.path.join(self.tmp, "stubs"), {"herdr-core": FAKE_HC})
        self.state = os.path.join(self.profile, ".local", "state", "herdr-fold")
        os.makedirs(self.state, exist_ok=True)

    def app_part(self):
        with open(os.path.join(self.state, "plugins.txt"), "w") as f:
            f.write("herdr-fold.sidebar\nherdr-fold.app\n")

    def hc_calls(self):
        return logged(os.path.join(self.profile, "hc-calls"))

    def recorded(self):
        return logged(os.path.join(self.state, "app-machines.txt"))

    def test_a_machine_joins_the_app_too(self):
        self.app_part()
        shown = self.add()
        self.assertIn("hc machine add box --name box --install", self.hc_calls())
        self.assertEqual(self.recorded(), ["box"])
        self.assertIn(catalog_text("machines.app_added", "box"), shown)

    def test_an_hc_that_cannot_list_is_said_in_a_line_not_a_traceback(self):
        self.app_part()
        self.env["STUB_HC_BROKEN"] = "1"
        shown = self.add()
        self.assertNotIn("Traceback", shown)
        self.assertIn("hc machine add box --name box --install", self.hc_calls())

    def test_without_the_app_part_hc_is_not_asked(self):
        self.add()
        self.assertEqual(self.hc_calls(), [])

    def test_a_machine_the_app_has_already_is_left_as_it_is(self):
        self.app_part()
        self.env["STUB_HC_HAS"] = "box"
        self.add()
        self.assertFalse([call for call in self.hc_calls() if call.startswith("hc machine add")])
        self.assertEqual(self.recorded(), [])

    def app_alone(self):
        with open(os.path.join(self.state, "plugins.txt"), "w") as f:
            f.write("herdr-fold.app\n")

    def herdr_logged(self):
        return logged(os.path.join(self.profile, "herdr-calls"))

    def test_the_app_alone_prepares_and_adds_to_the_app_only(self):
        self.app_alone()
        self.add()
        self.assertEqual([call for call in self.herdr_logged() if "machine add" in call or "plugin" in call], [])
        self.assertIn("hc machine add box --name box --install", self.hc_calls())

    def test_a_machine_for_the_app_alone_gets_no_starship(self):
        self.app_alone()
        self.env["HERDR_FOLD_VERBOSE"] = "1"                                  # every item its line
        shown = self.prepare()
        self.assertIn("git", shown)
        self.assertNotIn("starship", shown)

    def test_a_machine_for_the_tui_gets_starship(self):
        self.app_part()
        self.env["HERDR_FOLD_VERBOSE"] = "1"
        self.assertIn("starship", self.prepare())

    def test_remove_takes_off_only_what_herdr_fold_added(self):
        self.app_part()
        self.add()
        self.remove()
        self.assertIn("hc machine rm box", self.hc_calls())
        self.assertEqual(self.recorded(), [])

    def test_remove_leaves_a_machine_herdr_fold_did_not_add(self):
        self.app_part()
        self.env["STUB_HC_HAS"] = "box"
        self.add()
        self.remove()
        self.assertNotIn("hc machine rm box", self.hc_calls())


if __name__ == "__main__":
    unittest.main()
