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
import herdr_toml  # noqa: E402

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
        self.assertIn("cmd_keys.py w", merged)                         # the other commands are added (Cmd+W's)

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


class Put(unittest.TestCase):
    """One key set from Settings: a line of theirs outside the markers, which the next add keeps."""

    def test_it_reads_a_tables_string_and_none_where_none_is_set(self):
        self.assertEqual(herdr_toml.value(PACKAGE_CONFIG, "ui.toast", "delivery"), "herdr")
        self.assertEqual(herdr_toml.value('[ui.toast]\ndelivery = "off"  # quiet\n', "ui.toast", "delivery"), "off")
        self.assertIsNone(herdr_toml.value(THEIRS, "ui.toast", "delivery"))
        self.assertIsNone(herdr_toml.value('a = """\n', "ui.toast", "delivery"))

    def test_in_the_packages_own_file_the_line_changes_in_place(self):
        made = herdr_toml.put(PACKAGE_CONFIG, "ui.toast", "delivery", '"off"')
        self.assertEqual(herdr_toml.value(made, "ui.toast", "delivery"), "off")
        self.assertEqual(made.replace('delivery = "off"', 'delivery = "herdr"'), PACKAGE_CONFIG)

    def test_out_of_the_marked_part_it_becomes_theirs_and_survives_the_next_add(self):
        added, _ = herdr_config.add(PACKAGE_CONFIG, THEIRS)
        made = herdr_toml.put(added, "ui.toast", "delivery", '"off"')
        self.assertIn('delivery = "off"', outside_markers(made))
        self.assertEqual(made.count("[ui.toast]"), 1)                           # no table twice
        self.assertEqual([line for line in made.split("\n") if line.startswith("delivery")], ['delivery = "off"'])
        self.assertFalse([line for line in THEIRS.split("\n") if line not in outside_markers(made)])
        again, notes = herdr_config.add(PACKAGE_CONFIG, made)
        self.assertEqual(herdr_toml.value(again, "ui.toast", "delivery"), "off")
        self.assertEqual(again.count("[ui.toast]"), 1)
        back = herdr_toml.put(again, "ui.toast", "delivery", '"herdr"')        # on again: still theirs
        self.assertIn('delivery = "herdr"', outside_markers(back))
        self.assertIsNotNone(herdr_toml.parse(back))

    def test_under_a_table_of_theirs_it_goes_after_their_header(self):
        theirs = THEIRS + "\n[ui.toast]\nposition = \"top\"\n"
        added, _ = herdr_config.add(PACKAGE_CONFIG, theirs)
        made = herdr_toml.put(added, "ui.toast", "delivery", '"off"')
        self.assertEqual(table(made, "ui.toast")[:2], ['delivery = "off"', 'position = "top"'])
        self.assertNotIn('delivery = "herdr"', made)
        self.assertEqual(herdr_toml.value(herdr_config.add(PACKAGE_CONFIG, made)[0], "ui.toast", "delivery"), "off")

    def test_a_file_with_none_gets_the_table_and_an_unsure_one_is_left_alone(self):
        self.assertEqual(herdr_toml.put("", "ui.toast", "delivery", '"off"'), '[ui.toast]\ndelivery = "off"\n')
        self.assertTrue(herdr_toml.put(THEIRS, "ui.toast", "delivery", '"off"').endswith(
            '\n[ui.toast]\ndelivery = "off"\n'))
        self.assertIsNone(herdr_toml.put('a = """\n', "ui.toast", "delivery", '"off"'))
        self.assertIsNone(herdr_toml.put(BEGIN + "\n", "ui.toast", "delivery", '"off"'))


    def test_the_installer_reads_a_key_before_it_copies_the_packages_file_and_puts_it_back_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.toml")
            with open(path, "w", encoding="utf-8") as f:
                f.write(PACKAGE_CONFIG.replace('delivery = "herdr"', 'delivery = "off"'))
            run = [sys.executable, os.path.join(SRC, "herdr_config.py")]
            kept = subprocess.run(run + ["value", path, "ui.toast", "delivery"], capture_output=True, text=True)
            self.assertEqual((kept.returncode, kept.stdout), (0, "off\n"))
            with open(path, "w", encoding="utf-8") as f:                        # the update's copy
                f.write(PACKAGE_CONFIG)
            self.assertEqual(subprocess.run(run + ["put", path, "ui.toast", "delivery", "off"]).returncode, 0)
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), PACKAGE_CONFIG.replace('delivery = "herdr"', 'delivery = "off"'))
            self.assertEqual(subprocess.run(run + ["put", path, "ui.toast", "delivery", 'a"b']).returncode, 1)


class SidebarKey(unittest.TestCase):
    """Cmd+Shift+G (prefix+u) opens the sidebar's Changes, Cmd+Shift+I (prefix+shift+i) its issues: the
    herdr-fold.sidebar plugin's actions."""

    def test_an_agent_waiting_in_another_tab_is_told_by_herdrs_own_toast(self):
        # a chat that starts waiting: herdr's own toast ("claude needs attention", once a wait, never for the tab in
        # front; measured in herdr 0.9.5), so no toast of herdr-fold's doubles it; its sound herdr's, off as before
        tables = herdr_config.parse(PACKAGE_CONFIG)[0]
        self.assertEqual((tables["ui.toast"].get("delivery"), tables["ui.sound"].get("enabled")), ('"herdr"', "false"))

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

    def test_an_update_rewrites_its_block_to_the_chat_actions_id(self):
        # find-conversation, the id before the rename: its block of an earlier install goes, the new one comes
        older = (THEIRS + f'\n{BEGIN}\n[[keys.command]]\nkey = "prefix+m"\ntype = "plugin_action"\n'
                 f'command = "herdr-fold.sidebar.find-conversation"\n{END}\n')
        result, _ = herdr_config.add(PACKAGE_CONFIG, older)
        self.assertNotIn("find-conversation", result)
        self.assertEqual(result.count('command = "herdr-fold.sidebar.find-chat"'), 1)


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
