"""Tests for tools/build.py: the shared data layer lives once, in core/, and each piece that installs on its own (the
TUI sidebar, Workspaces, the Herdr app mod) carries a copy of what it needs; a copy differing from core/ fails here."""
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import sysconfig
import tempfile
import unittest

from support import PACKAGE

sys.path.insert(0, os.path.join(PACKAGE, "tools"))
import build  # noqa: E402

CORE = os.path.join(PACKAGE, "core")


class Copies(unittest.TestCase):
    def test_every_copy_is_what_the_core_makes_now(self):
        for rel, content in build.outputs().items():
            with self.subTest(rel), open(os.path.join(PACKAGE, rel), encoding="utf-8") as f:
                self.assertEqual(f.read(), content, "out of date: /usr/bin/python3 tools/build.py")

    def test_a_copy_names_its_source_first(self):
        for rel, content in build.outputs().items():
            if rel.endswith(".json"):
                continue                                # no comment in JSON: the app's theme, made from the TUI's
            with self.subTest(rel):
                self.assertIn("Generated from core/", content.split("\n", 2)[0 if rel.endswith(".py") else 1])

    def test_the_tui_sidebar_gets_each_core_module_but_the_ones_only_the_mod_runs(self):
        # job.py starts the Herdr app mod's background jobs: the sidebar carries no copy it would never run
        sidebar = os.path.join("src", "plugins", "sidebar")
        for name in sorted(os.listdir(CORE)):
            if name.endswith(".py"):
                self.assertEqual(os.path.join(sidebar, name) in build.outputs(), name not in build.MOD_ONLY, name)
        in_helpers = {name for sources in build.HELPERS.values() for name in sources.values()}
        self.assertLessEqual(build.MOD_ONLY, in_helpers)

    def test_workspaces_gets_core_git_and_what_it_imports(self):
        # its Spaces row's repository inside a folder is core/git.py's, as the Herdr app mod's Spaces list's is
        folder = os.path.join("src", "plugins", "workspaces")
        made = sorted(os.path.basename(rel) for rel in build.outputs() if os.path.dirname(rel) == folder)
        self.assertEqual(made, sorted(["git.py"] + [module + ".py" for module in build.imports("git.py")]))


class Literal(unittest.TestCase):
    def test_a_long_line_is_cut_between_words_and_joined_back_whole(self):
        line = ("    commit, sync, push (whether each worked, else what to do). The arguments each takes: COMMANDS "
                "and the usage line, then a few more words to make it long enough for two cuts at least.")
        made = build.literal(line)
        pieces = [json.loads(piece) for piece in re.findall(r'"(?:[^"\\]|\\.)*"', made)]
        self.assertEqual("".join(pieces[:-1]), line)                     # the last is join()'s own "\\n"
        self.assertTrue(all(piece.endswith(" ") for piece in pieces[:-2]), pieces)
        self.assertTrue(all(len(row) <= 120 for row in made.split("\n")))


class Runnable(unittest.TestCase):
    def test_a_module_that_imports_another_runs_alone_as_the_mod_runs_it(self):
        # one source given to Python's -c on the space's machine: the core modules it imports defined there first
        with tempfile.TemporaryDirectory() as home:
            done = subprocess.run(["/usr/bin/python3", "-I", "-c", build.runnable("conversations.py"), "list", "[]",
                                   "{}"], env={"HOME": home, "PATH": "/usr/bin:/bin"}, capture_output=True, text=True,
                                  timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {"conversations": [], "archived": []})

    def test_what_an_imported_module_imports_is_made_first_too(self):
        # chat.py imports conversations.py, which imports statefile.py and github.py: each made once, before its user
        with tempfile.TemporaryDirectory() as home:
            session = "5f0c6d9e-1b2a-4c3d-8e9f-0a1b2c3d4e5f"
            done = subprocess.run(["/usr/bin/python3", "-I", "-c", build.runnable("chat.py"), "steps", session, "0"],
                                  env={"HOME": home, "PATH": "/usr/bin:/bin"}, capture_output=True, text=True,
                                  timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["steps"], [])
        made = re.findall(r"^_sys\.modules\['(\w+)'\] =", build.runnable("chat.py"), re.M)
        self.assertEqual(sorted(made), ["conversations", "github", "statefile"])
        self.assertGreater(made.index("conversations"), max(made.index("github"), made.index("statefile")))

    def test_a_made_module_keeps_its_lines(self):
        # each line of a module made first stays a line: helper.js reads as core/ does, and the privacy scan sees what
        # it sees there (a decorator after an escaped new line looked like an e-mail address)
        self.assertIn("'@contextlib.contextmanager',", build.runnable("chat.py").split("\n"))

    def test_a_module_that_imports_none_is_its_source(self):
        self.assertEqual(build.runnable("git.py"), build.core("git.py"))


class AppTheme(unittest.TestCase):
    """The Herdr app's herdr-fold layout wears the TUI's own colors: its theme made from the package's (themes.js)."""

    def setUp(self):
        sys.path.insert(0, os.path.join(PACKAGE, "src", "themes"))
        import apply
        self.apply, self.themes = apply, apply.load_themes()
        self.default = apply.current_id(os.path.join(PACKAGE, "config", "ghostty", "config"))

    def made(self, name):
        return json.loads(build.outputs()[os.path.join("app", "themes", name)])

    def test_every_tui_theme_is_one_of_the_apps_in_its_colors(self):
        for tui in self.themes:
            with self.subTest(tui["id"]):
                made, colors, frame = self.made(f"herdr-fold-{tui['id']}.json"), tui["colors"], tui["colors"]["herdr"]
                self.assertEqual((made["background"], made["foreground"], made["cursor"], made["ansi"]),
                                 (colors["background"], colors["foreground"], colors["cursor"], colors["palette"]))
                self.assertEqual((made["colors"]["accent"], made["colors"]["chrome"], made["colors"]["selected"]),
                                 (frame["accent"], frame["sidebar_bg"], frame["active_row_bg"]))
        themes = {rel for rel in build.outputs() if rel.startswith(os.path.join("app", "themes", ""))}
        self.assertEqual(len(themes), len(self.themes) + 1)        # each theme, and the layout's own

    def test_an_agents_state_wears_the_tuis_color(self):
        # as the TUI's column marks it: the state's role (conversation_list.py), the role's palette color (theme.py)
        sys.path.insert(0, os.path.join(PACKAGE, "src", "plugins", "sidebar"))
        import conversation_list
        import theme
        for tui in self.themes:
            with self.subTest(tui["id"]):
                made, palette = self.made(f"herdr-fold-{tui['id']}.json")["colors"], tui["colors"]["palette"]
                for state, role in conversation_list.STATE_ROLE.items():
                    code = int(theme.PALETTE_FG[role])                  # 31-37, or 90-97 the bright ones
                    self.assertEqual(made[state], palette[code - 30 if code < 90 else code - 82], state)

    def test_a_control_shows_its_fill_its_edge_and_the_mouse_over_it(self):
        # Herdr draws a button as its fill (raised) in a frame (border), lighter under the mouse (hover), on a panel
        for tui in self.themes:
            with self.subTest(tui["id"]):
                made = self.made(f"herdr-fold-{tui['id']}.json")["colors"]
                panel, edge, fill, hover = (self.apply.luminance(made[k])
                                            for k in ("surface", "border", "raised", "hover"))
                self.assertTrue(panel < edge < fill < hover, made)
                self.assertGreaterEqual(self.apply.contrast(made["raised"], made["surface"]), 1.15)
                self.assertGreaterEqual(self.apply.contrast(made["hover"], made["raised"]), 1.1)

    def test_a_fields_frame_shows_and_stays_quieter_than_the_words(self):
        for tui in self.themes:
            with self.subTest(tui["id"]):
                made = self.made(f"herdr-fold-{tui['id']}.json")["colors"]
                self.assertGreaterEqual(self.apply.contrast(made["input"], made["surface"]), 1.5)
                self.assertLess(self.apply.luminance(made["input"]), self.apply.luminance(made["muted"]))

    def test_the_layout_wears_the_tuis_default_catppuccin(self):
        self.assertEqual(self.default, "catppuccin")
        self.assertEqual(self.made("herdr-fold.json"), self.made("herdr-fold-catppuccin.json"))
        with open(os.path.join(PACKAGE, "app", "layouts", "herdr-fold.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["theme"], "herdr-fold")


class Core(unittest.TestCase):
    def test_the_core_uses_the_standard_library_and_itself_only(self):
        # it runs inside the TUI sidebar, the Herdr app's mods and on remote machines: nothing else is there
        own = {name[:-3] for name in os.listdir(CORE) if name.endswith(".py")}
        for name in sorted(own):
            with open(os.path.join(CORE, name + ".py"), encoding="utf-8") as f:
                tree = ast.parse(f.read())
            imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                        for alias in node.names}
            imported |= {node.module.split(".")[0] for node in ast.walk(tree)
                         if isinstance(node, ast.ImportFrom) and node.module}
            with self.subTest(name):
                self.assertEqual(sorted(m for m in imported - own if not standard(m)), [])


WINDOWS_ONLY = {"msvcrt", "winreg"}          # Python's own on Windows, so find_spec finds them only there


def standard(module):
    """Whether MODULE comes with Python itself (built in, or from its own library folder), here or on Windows."""
    if module in WINDOWS_ONLY:
        return True
    spec = importlib.util.find_spec(module)
    return bool(spec) and (spec.origin in ("built-in", "frozen")
                           or (spec.origin or "").startswith(sysconfig.get_paths()["stdlib"]))


if __name__ == "__main__":
    unittest.main()
