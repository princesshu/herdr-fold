"""Tests for the Claude status line (src/statusline.py) and statusline_setup.py, which puts it into Claude Code's
settings.json: an existing status line is backed up first, a damaged file left alone, a symlink kept a link; the setup
runs without termios too, as on Windows."""
import gc
import glob
import importlib.util
import json
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import warnings

from support import PACKAGE, catalog_text

SCRIPT = os.path.join(PACKAGE, "src", "statusline.py")
COMMAND = 'python3 "$HOME/.config/herdr-fold/statusline.py"'             # the command the installer sets
MONDAY = 1793019600                                     # Monday, 26 October 2026, 1 pm UTC
FULL = ('{"model":{"display_name":"Opus 5.5"},"effort":{"level":"high"},"context_window":{"used_percentage":12.5},'
        '"rate_limits":{"five_hour":{"used_percentage":63.5,"resets_at":1000},'
        '"seven_day":{"used_percentage":91,"resets_at":%d}}}' % MONDAY)
TEAL, PURPLE, YELLOW = "\x1b[38;2;78;201;212m", "\x1b[38;2;197;134;192m", "\x1b[38;2;215;186;125m"
GREEN, WARN, CRIT = "\x1b[38;2;166;227;161m", "\x1b[38;2;249;226;175m", "\x1b[38;2;243;139;168m"
GRAY, RESET = "\x1b[38;2;147;153;178m", "\x1b[0m"
SEP = f" {GRAY}|{RESET} "


def run(data, choice=None, columns=None):
    """What the status line prints for Claude's JSON DATA, with CHOICE as statusline.json and COLUMNS as the pane's
    width — in UTC, with no jq or anything else on the PATH."""
    with tempfile.TemporaryDirectory() as home:
        if choice is not None:
            os.makedirs(os.path.join(home, ".config", "herdr-fold"))
            with open(os.path.join(home, ".config", "herdr-fold", "statusline.json"), "w") as f:
                f.write(choice)
        env = {"HOME": home, "PATH": "", "TZ": "UTC", **({"COLUMNS": columns} if columns else {})}
        done = subprocess.run([sys.executable, SCRIPT], input=data.encode("utf-8"), capture_output=True, timeout=20,
                              env=env)
        assert done.returncode == 0 and not done.stderr, done.stderr
        return done.stdout.decode("utf-8")


class Statusline(unittest.TestCase):
    """The line the bash and PowerShell scripts printed before, byte for byte, color codes included."""

    def test_the_whole_line(self):
        self.assertEqual(run(FULL),
                         f"{TEAL}Opus 5.5{RESET} {GRAY}({RESET}{PURPLE}high{RESET}{GRAY}){RESET}"
                         f"{SEP}{GRAY}context:{RESET} {YELLOW}12%{RESET}"
                         f"{SEP}{GRAY}current:{RESET} {WARN}64%{RESET}{GRAY}{RESET}"
                         f"{SEP}{GRAY}weekly:{RESET} {CRIT}91%{RESET}{GRAY}/Monday 1pm{RESET}")

    def test_only_the_chosen_items(self):
        self.assertEqual(run(FULL, '{"claude": {"effort": false, "weekly": false}}'),
                         f"{TEAL}Opus 5.5{RESET}{SEP}{GRAY}context:{RESET} {YELLOW}12%{RESET}"
                         f"{SEP}{GRAY}current:{RESET} {WARN}64%{RESET}{GRAY}{RESET}")

    def test_the_context_window_size_beside_the_context(self):
        # one item with the context, as Codex's line has it (context-window-size): the same items for both agents
        model = f"{TEAL}Opus 5.5{RESET}{SEP}"
        for size, shown in ((1000000, "/1M"), (200000, "/200k"), (1500000, "/1.5M")):
            data = ('{"model":{"display_name":"Opus 5.5"},"context_window":{"used_percentage":12.5,'
                    '"context_window_size":%d}}' % size)
            self.assertEqual(run(data), f"{model}{GRAY}context:{RESET} {YELLOW}12%{RESET}{GRAY}{shown}{RESET}")
        data = ('{"model":{"display_name":"Opus 5.5"},"context_window":{"used_percentage":12.5,'
                '"context_window_size":1000000}}')
        self.assertEqual(run(data, '{"claude": {"context": false}}'), f"{TEAL}Opus 5.5{RESET}")

    def test_the_context_and_its_window_size_are_one_choice(self):
        # two would show the context twice in the installer's list (context: 22% and context: 22%/1M)
        import statusline_setup
        for tool in ("claude", "codex"):
            self.assertEqual([key for key, _, _ in statusline_setup.ITEMS[tool]],
                             ["effort", "context", "five_hour", "weekly"], tool)
        self.assertEqual(statusline_setup.ITEMS["claude"][1][2], "context: 22%/1M")

    def test_a_damaged_choice_shows_everything(self):
        self.assertEqual(run(FULL, '{"claude": '), run(FULL))

    def test_before_the_first_answer(self):
        self.assertEqual(run('{"model":{"display_name":"Haiku 5.5"},"effort":{"level":"medium"}}'),
                         f"{TEAL}Haiku 5.5{RESET} {GRAY}({RESET}{PURPLE}medium{RESET}{GRAY}){RESET}")

    def test_none_used_yet_is_zero_and_a_half_rounds_to_even(self):
        self.assertEqual(run('{"model":{"display_name":"Opus 5.5"},"context_window":{"used_percentage":0},'
                             '"rate_limits":{"five_hour":{"used_percentage":13.5}}}'),
                         f"{TEAL}Opus 5.5{RESET}{SEP}{GRAY}context:{RESET} {YELLOW}0%{RESET}"
                         f"{SEP}{GRAY}current:{RESET} {GREEN}14%{RESET}{GRAY}{RESET}")

    def test_the_time_left_until_the_five_hour_reset(self):
        now = int(time.time())
        for left, shown in ((7530, "/2hr 5m"), (330, "/5m")):          # 30 seconds to spare for a slow start
            data = '{"rate_limits":{"five_hour":{"used_percentage":80,"resets_at":%d}}}' % (now + left)
            self.assertIn(f"{CRIT}80%{RESET}{GRAY}{shown}{RESET}", run(data))

    def test_a_narrow_pane_gets_a_shorter_line_one_step_at_a_time(self):
        data = ('{"model":{"display_name":"Opus 5.5 (1M context)"},"effort":{"level":"high"},'
                '"context_window":{"used_percentage":13},"rate_limits":{"five_hour":{"used_percentage":93,'
                '"resets_at":%d},"seven_day":{"used_percentage":46,"resets_at":%d}}}' % (time.time() + 5850, MONDAY))
        steps = [("200", "Opus 5.5 (1M context) (high) | context: 13% | current: 93%/1hr 37m | weekly: 46%/Monday 1pm"),
                 ("90", "Opus 5.5 (1M context) (high) | context: 13% | current: 93%/1h 37m | weekly: 46%/Mon 1pm"),
                 ("78", "Opus 5.5 (high) | context: 13% | current: 93%/1h 37m | weekly: 46%/Mon 1pm"),
                 ("70", "Opus 5.5 (high) | ctx 13% | 5h 93%/1h 37m | wk 46%/Mon 1pm"),
                 ("56", "Opus 5.5 (high) | ctx 13% | 5h 93%/1h 37m | wk 46%"),
                 ("50", "Opus 5.5 (high) | ctx 13% | 5h 93% | wk 46%"),
                 ("40", "Opus 5.5 | ctx 13% | 5h 93% | wk 46%"),
                 ("20", "Opus 5.5 | ctx 13% | 5h 93% | wk 46%")]               # the shortest, even if too long
        for columns, line in steps:
            self.assertEqual(re.sub(r"\x1b\[[0-9;]*m", "", run(data, columns=columns)), line, columns)

    def test_without_a_width_the_line_stays_whole(self):
        for columns in ("0", "wide"):
            self.assertEqual(run(FULL, columns=columns), run(FULL), columns)

    def test_unreadable_input_prints_nothing(self):
        for data in ("", "{", "[1, 2]", '{"model": "Opus", "rate_limits": 7}'):
            self.assertEqual(run(data), "", data)


def load_setup():
    sys.path.insert(0, os.path.join(PACKAGE, "src"))        # its i18n.py, as when it runs from there
    spec = importlib.util.spec_from_file_location(
        "statusline_setup", os.path.join(PACKAGE, "src", "statusline_setup.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ClaudeSettings(unittest.TestCase):
    def setUp(self):
        self.module = load_setup()
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.settings = os.path.join(self.tmp, "settings.json")
        self.backup = os.path.join(self.tmp, "backup")

    def write(self, data):
        with open(self.settings, "w") as f:
            json.dump(data, f)

    def test_an_own_status_line_is_backed_up_before_herdr_folds_goes_in(self):
        self.write({"statusLine": {"type": "command", "command": "mine.sh"}, "env": {"A": "1"}})
        self.assertEqual(self.module.set_claude_statusline(self.settings, "bash herdr-fold.sh", self.backup),
                         "replaced")
        with open(os.path.join(self.backup, "claude-statusLine.json")) as f:
            self.assertEqual(json.load(f)["command"], "mine.sh")
        with open(self.settings) as f:
            data = json.load(f)
        self.assertEqual((data["statusLine"]["command"], data["env"]), ("bash herdr-fold.sh", {"A": "1"}))

    def test_it_is_drawn_again_every_few_seconds(self):
        # Claude Code runs it on a new message, not when its pane gets narrower (the Conversations column opened):
        # the line stayed cut short until the next answer; refreshInterval draws it again for the width it has now
        self.module.set_claude_statusline(self.settings, COMMAND, self.backup)
        with open(self.settings) as f:
            self.assertEqual(json.load(f)["statusLine"], {"type": "command", "command": COMMAND,
                                                          "refreshInterval": self.module.REFRESH})

    def test_an_earlier_herdr_folds_line_gets_the_interval_unsaved(self):
        self.write({"statusLine": {"type": "command", "command": COMMAND}})
        self.assertEqual(self.module.set_claude_statusline(self.settings, COMMAND, self.backup), "set")
        with open(self.settings) as f:
            self.assertEqual(json.load(f)["statusLine"]["refreshInterval"], self.module.REFRESH)
        self.assertFalse(os.path.exists(self.backup))                   # nothing of yours was in it

    def test_an_earlier_saved_status_line_is_never_overwritten(self):
        self.write({"statusLine": {"type": "command", "command": "first.sh"}})
        self.module.set_claude_statusline(self.settings, "bash herdr-fold.sh", self.backup)
        self.write({"statusLine": {"type": "command", "command": "second.sh"}})       # the user set an own one again
        self.module.set_claude_statusline(self.settings, "bash herdr-fold.sh", self.backup)
        saved = []
        for name in sorted(os.listdir(self.backup)):
            with open(os.path.join(self.backup, name)) as f:
                saved.append(json.load(f)["command"])
        self.assertEqual(sorted(saved), ["first.sh", "second.sh"])

    def test_herdr_folds_again_changes_nothing(self):
        self.write({"statusLine": {"type": "command", "command": "bash herdr-fold.sh",
                                   "refreshInterval": self.module.REFRESH}})
        self.assertEqual(self.module.set_claude_statusline(self.settings, "bash herdr-fold.sh", self.backup),
                         "unchanged")
        self.assertFalse(os.path.exists(self.backup))

    def test_your_own_script_of_the_same_name_is_yours(self):
        # Claude Code's own /statusline helper writes ~/.claude/statusline-command.sh too
        for yours in ("~/.claude/statusline-command.sh", "sh ~/.claude/statusline-command.sh --compact",
                      "python3 ~/.claude/statusline.py", 'python3 "$HOME/.config/herdr-fold/statusline.py" --mine'):
            self.write({"statusLine": {"type": "command", "command": yours, "padding": 0}})
            self.assertEqual(self.module.set_claude_statusline(self.settings, COMMAND, self.backup), "replaced", yours)
            saved = os.path.join(self.backup, "claude-statusLine.json")
            self.assertEqual(self.module.restore_claude_statusline(self.settings, saved), "restored", yours)
            with open(self.settings) as f:
                self.assertEqual(json.load(f)["statusLine"]["command"], yours)

    def test_your_own_text_stays_readable(self):
        self.write({"env": {"GREETING": "café ☕"}})
        self.module.set_claude_statusline(self.settings, "bash herdr-fold.sh", self.backup)
        with open(self.settings, encoding="utf-8") as f:
            self.assertIn("café ☕", f.read())

    def test_a_damaged_settings_file_is_left_alone(self):
        with open(self.settings, "w") as f:
            f.write('{"permissions": ')
        with self.assertRaises(ValueError):
            self.module.set_claude_statusline(self.settings, "bash herdr-fold.sh", self.backup)
        with open(self.settings) as f:
            self.assertEqual(f.read(), '{"permissions": ')

    def your_own(self, on):
        """The module pointed at this test's folder: settings.json, the state folder, herdr-fold's status line ON."""
        m = self.module
        m.SETTINGS, m.STATE, m.CONFIG = self.settings, os.path.join(self.tmp, "state"), os.path.join(self.tmp, "c.json")
        m.save({**m.load(), "claude": {**m.load()["claude"], "on": on}})
        return m

    def test_your_own_chosen_the_one_saved_before_comes_back(self):
        m = self.your_own(False)
        self.write({"statusLine": {"type": "command", "command": "mine.sh"}})
        original = os.path.join(m.STATE, "original")
        m.set_claude_statusline(self.settings, COMMAND, original)              # the installer, before the choice
        self.assertEqual(m.apply_claude(False, original), "restored")
        with open(self.settings) as f:
            self.assertEqual(json.load(f)["statusLine"]["command"], "mine.sh")
        self.assertEqual(m.apply_claude(False, original), "not herdr-fold's")  # yours from then on, left alone

    def test_your_own_chosen_the_one_replaced_last_comes_back(self):
        m = self.your_own(False)
        original = os.path.join(m.STATE, "original")
        for yours, at in (("first.sh", 1000), ("set-later.sh", 2000)):     # an install, then an update over /statusline
            self.write({"statusLine": {"type": "command", "command": yours}})
            m.set_claude_statusline(self.settings, COMMAND, original)
            saved = max(glob.glob(os.path.join(original, "claude-statusLine*.json")), key=os.path.getctime)
            os.utime(saved, (at, at))
        self.assertEqual(m.apply_claude(False, original), "restored")
        with open(self.settings) as f:
            self.assertEqual(json.load(f)["statusLine"]["command"], "set-later.sh")

    def test_your_own_chosen_with_none_saved_herdr_folds_just_goes(self):
        m = self.your_own(False)
        self.write({"statusLine": {"type": "command", "command": COMMAND}, "env": {"A": "1"}})
        self.assertEqual(m.apply_claude(False, self.backup), "removed")
        with open(self.settings) as f:
            self.assertEqual(json.load(f), {"env": {"A": "1"}})

    def test_your_own_chosen_the_installer_leaves_the_status_line_alone(self):
        m = self.your_own(False)
        self.write({"statusLine": {"type": "command", "command": "mine.sh"}})
        self.assertEqual(m.claude_settings(self.backup, COMMAND), 3)
        with open(self.settings) as f:
            self.assertEqual(json.load(f)["statusLine"]["command"], "mine.sh")
        self.assertFalse(os.path.exists(self.backup))

    def test_herdr_folds_chosen_any_form_of_it_stays_and_yours_is_saved_first(self):
        m = self.your_own(True)
        windows = ("powershell -NoProfile -Command \"& 'C:/Python/python.exe' "
                   "'C:/Users/dev/.config/herdr-fold/statusline.py'\"")
        self.write({"statusLine": {"type": "command", "command": windows}})
        self.assertEqual(m.apply_claude(True, self.backup), "unchanged")     # the Windows prepare's form
        self.write({"statusLine": {"type": "command", "command": "mine.sh"}})
        self.assertEqual(m.apply_claude(True, self.backup), "replaced")
        with open(os.path.join(self.backup, "claude-statusLine.json")) as f:
            self.assertEqual(json.load(f)["command"], "mine.sh")

    def test_a_symlinked_settings_file_stays_a_link(self):
        real = os.path.join(self.tmp, "dotfiles-settings.json")
        with open(real, "w") as f:
            json.dump({}, f)
        os.symlink(real, self.settings)
        self.module.set_claude_statusline(self.settings, "bash herdr-fold.sh", self.backup)
        self.assertTrue(os.path.islink(self.settings))
        with open(real) as f:
            self.assertEqual(json.load(f)["statusLine"]["command"], "bash herdr-fold.sh")


class Apply(unittest.TestCase):
    """statusline_setup.py --apply, as the installers run it after putting herdr-fold's status line in: Claude's
    settings touched only for your own (or herdr-fold's turned on again), so a damaged settings file is reported once,
    by the installer."""

    def run_apply(self, choice, settings):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        for rel, text in ((".config/herdr-fold/statusline.json", choice), (".claude/settings.json", settings)):
            os.makedirs(os.path.dirname(os.path.join(home, rel)), exist_ok=True)
            with open(os.path.join(home, rel), "w") as f:
                f.write(text)
        done = subprocess.run([sys.executable, os.path.join(PACKAGE, "src", "statusline_setup.py"), "--apply"],
                              capture_output=True, text=True, timeout=20, env={"HOME": home, "PATH": ""})
        with open(os.path.join(home, ".claude", "settings.json")) as f:
            return done.stdout, f.read()

    def test_your_own_chosen_herdr_folds_goes(self):
        said, settings = self.run_apply('{"claude": {"on": false}}', json.dumps({"statusLine": {
            "type": "command", "command": COMMAND}}))
        self.assertEqual(json.loads(settings), {})
        self.assertIn(catalog_text("status.yours_kept", "Claude Code"), said)

    def test_left_on_a_damaged_settings_file_is_left_to_the_installer(self):
        said, settings = self.run_apply("{}", '{"permissions": ')
        self.assertEqual(settings, '{"permissions": ')
        self.assertNotIn(catalog_text("status.claude_unreadable", ""), said)

    def test_it_runs_where_termios_is_missing(self):
        with tempfile.TemporaryDirectory() as home:
            blocker = os.path.join(home, "block")
            os.makedirs(blocker)
            for name in ("termios", "tty"):                # as on Windows: these modules do not exist
                with open(os.path.join(blocker, name + ".py"), "w") as f:
                    f.write("raise ImportError('not available on this system')\n")
            done = subprocess.run(["/usr/bin/python3", os.path.join(PACKAGE, "src", "statusline_setup.py"), "--apply"],
                                  env={"HOME": home, "PYTHONPATH": blocker, "PATH": "/usr/bin:/bin"},
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertTrue(os.path.exists(os.path.join(home, ".config", "herdr-fold", "statusline.json")))


class Checkboxes(unittest.TestCase):
    """The installer's status line question in a terminal: one list, a group for Claude Code and one for Codex, so a
    single Enter answers both (two lists one after the other, the second in the first one's place, looked like the
    same list coming back)."""

    def setUp(self):
        self.module = load_setup()

    def answer(self, keys, tools=("claude", "codex"), yours=()):
        """KEYS typed at once into the list, the status lines of YOURS your own at first; the states it returns, and
        everything the terminal showed."""
        m = self.module
        master, slave = os.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        shown, done = [], threading.Event()

        def drain():                               # the terminal keeps taking the drawing, so it never blocks
            while not done.is_set() or select.select([master], [], [], 0)[0]:
                if select.select([master], [], [], 0.05)[0]:
                    shown.append(os.read(master, 65536))
        reader = threading.Thread(target=drain)
        reader.start()
        os.write(master, keys)
        sections = [(m.TITLES[tool], m.ITEMS[tool],
                     {"on": tool not in yours, **{key: True for key, _, _ in m.ITEMS[tool]}}) for tool in tools]
        try:
            states = m.checkboxes(slave, sections)
        finally:
            done.set()
            reader.join()
        return states, b"".join(shown).decode()

    def test_one_enter_answers_both(self):
        states, shown = self.answer(b"\r")
        self.assertEqual([set(state.values()) for state in states], [{True}, {True}])
        for title in self.module.TITLES.values():
            self.assertEqual(shown.count(title), 1, shown)

    def test_the_arrows_go_on_from_claudes_group_into_codexs(self):
        claude = len(self.module.ITEMS["claude"])                        # from the first item, past Codex's title
        states, _ = self.answer(b"\x1b[B" * claude + b"\x1b[B \r")      # typed at once: every key still counts
        self.assertEqual(set(states[0].values()), {True})
        self.assertEqual((states[1]["on"], states[1]["effort"]), (True, False))

    def test_a_groups_title_turns_its_status_line_into_your_own(self):
        states, _ = self.answer(b"\x1b[A \r")                            # up from the first item: Claude's title
        self.assertEqual((states[0]["on"], states[0]["effort"], states[1]["on"]), (False, True, True))
        _, shown = self.answer(b"\r", yours=("codex",))
        self.assertEqual(shown.count(catalog_text("status.yours")), 1)
        # its items faint, Claude's (the same words) not
        self.assertEqual(shown.count("\x1b[2m[x] " + self.module.ITEMS["codex"][1][1]), 1)

    def test_without_codex_only_claudes_group(self):
        states, shown = self.answer(b"\r", tools=("claude",))
        self.assertEqual(len(states), 1)
        self.assertNotIn(self.module.TITLES["codex"], shown)


class Choice(unittest.TestCase):
    """The saved choice (statusline.json): a file of another shape, or a damaged one, gives everything on."""

    def test_a_choice_of_another_shape_gives_everything(self):
        module = load_setup()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        module.CONFIG = os.path.join(tmp, "statusline.json")
        for text in ('{"claude": ["effort"]}', '["claude"]', '{"claude": {"effort": false}}', "{"):
            with open(module.CONFIG, "w") as f:
                f.write(text)
            choice = module.load()
            expected = text != '{"claude": {"effort": false}}'                # only the right shape turns it off
            self.assertEqual(choice["claude"]["effort"], expected, text)
            self.assertTrue(all(choice["codex"].values()), text)
            self.assertTrue(choice["claude"]["on"], text)                   # on, unless chosen otherwise
        with open(module.CONFIG, "w") as f:
            f.write('{"codex": {"on": false}}')
        self.assertEqual((module.load()["claude"]["on"], module.load()["codex"]["on"]), (True, False))


class CodexConfig(unittest.TestCase):
    """The [tui] status_line in ~/.codex/config.toml: found however its header is written, never a second [tui] table
    (Codex would refuse to start), and the user's own items are kept."""

    def setUp(self):
        self.module = load_setup()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.module.CODEX = os.path.join(tmp, "config.toml")

    def apply(self, text, on=True):
        with open(self.module.CODEX, "w") as f:
            f.write(text)
        state = {"on": on, "effort": False, **{key: False for key in self.module.CODEX_ITEMS}}
        result = self.module.apply_codex(state)
        with open(self.module.CODEX) as f:
            return result, f.read()

    def test_a_list_over_several_lines_is_read_as_toml_reads_it(self):
        # a ] in a comment or in an item does not end the list, and an item commented out stays out
        for text in ('[tui]\nstatus_line = [ # mine [x]\n  "model",\n  "my-item",\n]\nother = 1\n',
                     '[tui]\nstatus_line = [\n  "a]b",\n  "my-item",\n]\nother = 1\n',
                     '[tui]\nstatus_line = [\n  "model",\n  # "git-branch",\n  "my-item"\n]\nother = 1\n'):
            items, written = self.apply(text)
            self.assertNotIn("git-branch", items, text)
            self.assertIn("my-item", items, text)
            self.assertEqual(written.count("my-item"), 1, written)
            self.assertTrue(written.rstrip().endswith("]\nother = 1"), written)
            self.assertEqual([line for line in written.splitlines() if line.lstrip().startswith(('"', "]"))], [],
                             written)

    def test_a_list_that_does_not_end_is_left_alone(self):
        text = '[tui]\nstatus_line = [\n  "model",\n'
        self.assertEqual(self.apply(text), (None, text))

    def test_a_tui_header_with_a_comment_is_found(self):
        _, text = self.apply('[tui]  # my settings\nstatus_line = ["model"]\n')
        self.assertEqual(text.count("[tui]"), 1)

    def test_a_tui_key_elsewhere_is_never_doubled(self):
        result, text = self.apply('model = "gpt-5"\ntui.status_line = ["model"]\n')
        self.assertIsNone(result)
        self.assertEqual(text, 'model = "gpt-5"\ntui.status_line = ["model"]\n')

    def test_single_quoted_own_items_are_kept(self):
        _, text = self.apply("[tui]\nstatus_line = ['model', 'my-item']\n")
        self.assertIn('"my-item"', text)

    def test_codex_shows_the_context_used_as_claude_does(self):
        # the same metric for both agents: what is used, not what is left; an earlier remaining one is replaced
        with open(self.module.CODEX, "w") as f:
            f.write('[tui]\nstatus_line = ["model", "context-remaining", "my-item"]\n')
        state = {"on": True, "effort": False, **{key: True for key in self.module.CODEX_ITEMS}}
        self.assertEqual(self.module.apply_codex(state), ["model", "context-used", "five-hour-limit", "weekly-limit",
                                                          "context-window-size", "my-item"])
        with open(self.module.CODEX) as f:
            self.assertNotIn("context-remaining", f.read())
        self.assertEqual([key for key, _, _ in self.module.ITEMS["claude"]],
                         [key for key, _, _ in self.module.ITEMS["codex"]])               # the same, in one order

    def test_your_own_chosen_herdr_folds_items_go_and_yours_stay(self):
        result, text = self.apply('[tui]\nstatus_line = ["model-with-reasoning", "context-remaining", "my-item"]\n',
                                  on=False)
        self.assertEqual((result, text), (["my-item"], '[tui]\nstatus_line = ["my-item"]\n'))
        result, text = self.apply('[tui]\nstatus_line = ["model", "weekly-limit"]\nx = 1\n', on=False)
        self.assertEqual((result, text), ([], "[tui]\nx = 1\n"))                  # none of yours: Codex's own
        result, text = self.apply('model = "gpt-5"\n', on=False)
        self.assertEqual((result, text), ([], 'model = "gpt-5"\n'))               # none of herdr-fold's: untouched

    def test_running_twice_changes_nothing_more(self):
        _, once = self.apply('model = "gpt-5"\n')
        _, twice = self.apply(once)
        self.assertEqual(once, twice)

    def test_a_linked_config_stays_a_link(self):
        real = self.module.CODEX + ".dotfiles"
        with open(real, "w") as f:
            f.write('model = "gpt-5"\n')
        os.symlink(real, self.module.CODEX)
        self.module.apply_codex({"on": True, "effort": True, **{key: True for key in self.module.CODEX_ITEMS}})
        self.assertTrue(os.path.islink(self.module.CODEX))
        with open(real) as f:
            self.assertIn("[tui]", f.read())

    def test_every_file_is_closed(self):
        self.module.CONFIG = self.module.CODEX + ".choice.json"
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always")
            self.module.save(self.module.load())
            self.module.load()
            self.apply('model = "gpt-5"\n')
            gc.collect()
        self.assertEqual([str(w.message) for w in seen if issubclass(w.category, ResourceWarning)], [])


if __name__ == "__main__":
    unittest.main()
