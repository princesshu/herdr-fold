"""Tests for herdr_config.py's "add" mode: herdr-fold's settings go between "# >>> herdr-fold >>>" markers in the
user's config.toml; their lines, keys and key chords stay theirs ([!] names them); an unclear file is left alone.
"""
import os
import subprocess
import sys
import tempfile
import unittest

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, SRC)
import herdr_config  # noqa: E402

with open(os.path.join(SRC, "..", "config", "herdr", "config.toml"), encoding="utf-8") as f:
    PACKAGE_CONFIG = f.read()
BEGIN, END = "# >>> herdr-fold >>>", "# <<< herdr-fold <<<"
THEIRS = """# my herdr
onboarding = true

[keys]
next_agent = ["ctrl+n"]
quit = "prefix+q"
my_switch = "prefix+down"

[[keys.command]]
key = "prefix+f"
type = "shell"
command = "my-finder"
"""


def outside_markers(text):
    lines, inside = [], False
    for line in text.split("\n"):
        if line == BEGIN:
            inside = True
        elif line == END:
            inside = False
        elif not inside:
            lines.append(line)
    return lines


def table(text, name):
    """The lines of table [name] (up to the next table header)."""
    lines = text.split("\n")
    start = lines.index(f"[{name}]")
    rest = lines[start + 1:]
    end = next((n for n, line in enumerate(rest) if line.startswith("[")), len(rest))
    return rest[:end]


class Add(unittest.TestCase):
    def add(self, theirs=THEIRS):
        merged, notes = herdr_config.add(PACKAGE_CONFIG, theirs)
        self.assertIsNotNone(merged, notes)
        return merged, " ".join(notes)

    def test_every_line_of_theirs_stays_in_order(self):
        merged, _ = self.add()
        self.assertEqual(outside_markers(merged), THEIRS.split("\n"))

    def test_a_key_they_set_stays_theirs(self):
        merged, notes = self.add()
        self.assertEqual([line for line in merged.split("\n") if line.startswith("next_agent")],
                         ['next_agent = ["ctrl+n"]'])
        self.assertIn("next_agent", notes)

    def test_herdr_folds_other_keys_go_into_their_table(self):
        merged, _ = self.add()
        self.assertIn('switch_workspace = "alt+1..9"', table(merged, "keys"))
        self.assertEqual(merged.count("\n[keys]\n"), 1)

    def test_a_chord_of_theirs_keeps_herdr_folds_out(self):
        merged, notes = self.add()
        self.assertNotIn("toggle_column.py", merged)                  # herdr-fold's prefix+f command
        self.assertNotIn('next_workspace = "prefix+down"', merged)     # their my_switch has prefix+down
        self.assertIn("prefix+f", notes)
        self.assertIn("prefix+down", notes)
        self.assertIn("close_tab.py", merged)                          # the other commands are added

    def test_their_top_level_settings_stay(self):
        merged, _ = self.add()
        self.assertNotIn("onboarding = false", merged)

    def test_herdr_folds_top_level_settings_come_before_every_table(self):
        for theirs in ("", "# only a comment\n"):
            merged, _ = self.add(theirs)
            lines = merged.split("\n")
            first_table = next(n for n, line in enumerate(lines) if line.startswith("["))
            self.assertLess(lines.index("onboarding = false"), first_table, merged[:300])

    def test_a_new_table_comes_before_their_subtables(self):
        merged, _ = self.add('[ui.sound]\nenabled = true\n')
        lines = merged.split("\n")
        self.assertLess(lines.index("[ui]"), lines.index("[ui.sound]"))
        self.assertEqual(merged.count("[ui.sound]"), 1)
        self.assertIn("[ui.toast.clipboard]", lines)

    def test_their_theme_stays(self):
        merged, notes = self.add('[theme]\nname = "tokyonight"\n')
        self.assertEqual(merged.count("[theme]"), 1)
        self.assertNotIn("# --- theme:", merged)
        self.assertIn("theme", notes)

    def test_without_a_theme_of_theirs_herdr_folds_comes_with_its_markers(self):
        merged, _ = self.add("onboarding = true\n")
        self.assertIn("# --- theme:", merged)
        self.assertIn("# --- end of theme ---", merged)

    def test_adding_again_changes_nothing(self):
        once, _ = self.add()
        self.assertEqual(self.add(once)[0], once)

    def test_a_marker_without_its_pair_loses_nothing(self):
        once, _ = self.add()
        lines = once.split("\n")
        cut = len(lines) - 1 - lines[::-1].index(END)                      # the user deleted the last END line…
        broken = "\n".join(lines[:cut] + lines[cut + 1:]) + '[ui.sound]\nenabled = true\n'   # …and wrote below
        self.assertIn("[ui.sound]\nenabled = true", herdr_config.strip(broken))
        merged, notes = herdr_config.add(PACKAGE_CONFIG, broken)
        self.assertIsNone(merged)
        self.assertTrue(notes)

    def test_an_inline_table_of_theirs_is_theirs(self):
        for theirs, what in (('[ui]\nsound = { enabled = true }\n', "[ui.sound]"),
                             ('[ui.toast]\nclipboard = { enabled = true }\n', "[ui.toast.clipboard]"),
                             ('theme = { name = "nord" }\n', "# --- theme:")):
            merged, notes = self.add(theirs)
            self.assertNotIn(what, merged, theirs)
            self.assertTrue(notes, theirs)

    def test_a_file_it_cannot_read_for_sure_is_left_alone(self):
        for theirs in ('ui.sound.enabled = true\n', 'note = """\n[keys]\n"""\n', '["quoted table"]\nx = 1\n'):
            merged, notes = herdr_config.add(PACKAGE_CONFIG, theirs)
            self.assertIsNone(merged, theirs)
            self.assertTrue(notes, theirs)


class SidebarKey(unittest.TestCase):
    """Cmd+Shift+G (prefix+u) opens the sidebar's Changes, Cmd+Shift+I (prefix+shift+i) its issues: the
    herdr-fold.sidebar plugin's actions."""

    def test_the_package_binds_the_sidebars_changes_view(self):
        self.assertIn('command = "herdr-fold.sidebar.show-git"', PACKAGE_CONFIG)

    def test_the_package_binds_the_sidebars_issues(self):
        block = PACKAGE_CONFIG.split('command = "herdr-fold.sidebar.show-issues"')[0].rsplit("[[keys.command]]", 1)[1]
        self.assertIn('key = "prefix+shift+i"', block)

    def test_an_older_block_of_herdr_folds_gets_the_new_key_once(self):
        older = (THEIRS + f'\n{BEGIN}\n[[keys.command]]\nkey = "prefix+u"\ntype = "plugin_action"\n'
                 f'command = "herdr-sidebar.show-git"\n{END}\n')
        result, _ = herdr_config.add(PACKAGE_CONFIG, older)
        self.assertNotIn("herdr-sidebar", result)
        self.assertEqual(result.count('command = "herdr-fold.sidebar.show-git"'), 1)


class CommandLine(unittest.TestCase):
    def test_the_installer_merges_the_file_in_place_and_a_link_stays(self):
        with tempfile.TemporaryDirectory() as tmp:
            real, link = os.path.join(tmp, "dotfiles-config.toml"), os.path.join(tmp, "config.toml")
            with open(real, "w") as f:
                f.write(THEIRS)
            os.symlink(real, link)
            package = os.path.join(SRC, "..", "config", "herdr", "config.toml")
            done = subprocess.run([sys.executable, os.path.join(SRC, "herdr_config.py"), "add", package, link],
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertTrue(os.path.islink(link))
            with open(real) as f:
                self.assertIn(BEGIN, f.read())
            self.assertIn("  [!] ", done.stdout)
            self.assertIn("prefix+f", done.stdout)


if __name__ == "__main__":
    unittest.main()
