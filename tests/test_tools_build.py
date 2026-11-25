"""Tests for tools/build.py: the shared data layer lives once, in core/, and each piece that installs on its own (the
TUI sidebar, Spaces, the Herdr app mod) carries a copy of what it needs; a copy differing from core/ fails here."""
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
HELPER_LARGEST = 120 * 1024     # bytes of a helper's source: Linux's MAX_ARG_STRLEN (128 KiB) with room to grow
HELPER_ROOM = 8 * 1024          # bytes each helper keeps free of that: the next lines its modules gain fit


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
        self.assertIn(os.path.join(sidebar, "agent_setup.py"), build.outputs())     # the TUI's Agent view reads it

    def test_the_mod_gets_each_brand_with_its_logos_path(self):
        # icons.js's BRANDS: core/connectors.py's, a logo by the path the app loads it (tools/icons.py fetched it)
        connectors = build.module("connectors")
        made = build.outputs()[build.ICONS]
        brands = json.loads(re.search(r"^export const BRANDS = (\{.*?^\});$", made, re.M | re.S).group(1))
        self.assertEqual(sorted(brands), sorted(connectors.BRANDS))
        self.assertEqual(brands["linear"], {"name": "Linear", "logo": "mods/herdr-fold/icons/logos/linear-icon.svg",
                                            "mono": True})
        self.assertEqual(brands["google-drive"]["mono"], False)
        for key, one in brands.items():
            with self.subTest(key):
                self.assertTrue(os.path.isfile(os.path.join(PACKAGE, "app", one["logo"])))

    def test_the_mod_runs_the_connectors_commands(self):
        helper = os.path.join("app", "mods", "herdr-fold", "helper.js")
        self.assertEqual(build.HELPERS[helper]["CONNECTORS"], "connectors.py")
        self.assertIn("connectors", build.imports("agent_setup.py"))                # a server's brand is core's

    def test_spaces_gets_core_git_and_what_it_imports(self):
        # its Spaces row's repository inside a folder is core/git.py's, as the Herdr app mod's Spaces list's is
        folder = os.path.join("src", "plugins", "spaces")
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


def undocumented(tree):
    """TREE without its docstrings, a body that was one alone a pass: what slim() leaves of a module."""
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and body \
                and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            node.body = body[1:] or [ast.Pass()]
    return tree


class Runnable(unittest.TestCase):
    def test_a_module_that_imports_another_runs_alone_as_the_mod_runs_it(self):
        # one source given to Python's -c on the space's machine: the core modules it imports defined there first
        with tempfile.TemporaryDirectory() as home:
            done = subprocess.run(["/usr/bin/python3", "-I", "-c", build.runnable("chats.py"), "list", "[]",
                                   "{}"], env={"HOME": home, "PATH": "/usr/bin:/bin"}, capture_output=True, text=True,
                                  timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {"chats": [], "archived": []})

    def test_what_an_imported_module_imports_is_made_first_too(self):
        # chat.py imports plan.py, which imports chats.py, which imports fileops.py, statefile.py, github.py and
        # jsonl.py: each made once, before what imports it
        with tempfile.TemporaryDirectory() as home:
            session = "5f0c6d9e-1b2a-4c3d-8e9f-0a1b2c3d4e5f"
            done = subprocess.run(["/usr/bin/python3", "-I", "-c", build.runnable("chat.py"), "steps", session, "0"],
                                  env={"HOME": home, "PATH": "/usr/bin:/bin"}, capture_output=True, text=True,
                                  timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["steps"], [])
        made = re.findall(r"^_sys\.modules\['(\w+)'\] =", build.runnable("chat.py"), re.M)
        self.assertEqual(sorted(made), ["chats", "fileops", "github", "jsonl", "plan", "statefile"])
        self.assertGreater(made.index("chats"), max(made.index(name) for name in ("fileops", "github", "jsonl",
                                                                                  "statefile")))
        self.assertGreater(made.index("plan"), made.index("chats"))

    def test_a_made_module_keeps_its_lines(self):
        # each line of a module made first stays a line: helper.js reads as core/ does, and the privacy scan sees what
        # it sees there (a decorator after an escaped new line looked like an e-mail address)
        self.assertIn("'@contextlib.contextmanager',", build.runnable("chat.py").split("\n"))

    def test_a_module_that_imports_none_is_its_source(self):
        self.assertEqual(build.runnable("statefile.py"), build.core("statefile.py"))

    def test_a_made_module_leaves_its_blank_and_comment_lines_out(self):
        # a helper is one argument of 120 KiB at most: what Python never runs of a module made first stays in core/;
        # a string's own lines stay; a comment after code goes, its code staying
        source = 'A = 1\n\n# alone\nB = """a\n\n# kept\n"""  # after\nC = [\n    # inside\n\n    2]  # "#"\nD = "#"\n'
        self.assertEqual(build.slim(source), 'A = 1\nB = """a\n\n# kept\n"""\nC = [\n    2]\nD = "#"')
        for name in sorted(os.listdir(CORE)):
            if name.endswith(".py"):
                with self.subTest(name):
                    slim = build.slim(build.core(name))
                    self.assertEqual(ast.dump(ast.parse(slim)), ast.dump(undocumented(ast.parse(build.core(name)))))
                    self.assertFalse([line for line in slim.split("\n") if line.lstrip().startswith("# ")])
        made = build.runnable("graph.py")
        self.assertTrue(made.endswith(build.core("graph.py")), "the module itself as its source: its own lines count")
        self.assertIn('"""', build.core("graph.py").split("\n")[0])
        self.assertNotIn(repr(build.core("agent_setup.py").split("\n")[0]), made)    # a made one's docstrings out
        alone = next(line for line in build.core("agent_setup.py").split("\n") if line.startswith("# "))
        self.assertNotIn(f"{alone!r},\n", made[:-len(build.core("graph.py"))])
        self.assertIn(alone, build.core("agent_setup.py"))

    def test_a_made_module_leaves_its_docstrings_out(self):
        # what Python never runs either: a body that was a docstring alone keeps a pass; another string stays
        source = ('"""The module."""\nimport os\n\n\ndef f():\n    """What f does,\n    on two lines."""\n'
                  '    return 1\n\n\nclass C:\n    """Only this."""\n\n\ndef g():\n    x = """not a docstring"""\n'
                  '    return x\n')
        self.assertEqual(build.slim(source), 'import os\ndef f():\n    return 1\nclass C:\n    pass\ndef g():\n'
                                             '    x = """not a docstring"""\n    return x')

    def test_the_graphs_helper_has_room_to_grow(self):
        # agent_setup.py is most of it, and grows with the Agent panel: a few KiB at least stay free
        self.assertLess(len(build.runnable("graph.py").encode("utf-8")), HELPER_LARGEST - 2 * 1024)

    def test_no_helper_carries_what_it_never_runs(self):
        # the agents on this machine and a server's check are agent_state.py's: the graph's helper leaves them out,
        # and every helper keeps HELPER_ROOM free for what its modules gain next
        self.assertNotIn("agent_state", build.imports("graph.py"))
        self.assertEqual(build.imports("agent_state.py")[-1], "agent_setup")
        for sources in build.HELPERS.values():
            self.assertIn("agent_state.py", sources.values())
            for const, name in sources.items():
                with self.subTest(const):
                    self.assertLess(len(build.runnable(name).encode("utf-8")), HELPER_LARGEST - HELPER_ROOM)

    def test_every_helper_fits_in_one_argument_on_linux(self):
        # the mod runs each as one argument of python3 -c (its exec has no stdin); Linux takes 128 KiB at most there
        for sources in build.HELPERS.values():
            for const, name in sources.items():
                with self.subTest(const):
                    self.assertLess(len(build.runnable(name).encode("utf-8")), HELPER_LARGEST)


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
                self.assertEqual((made["colors"]["accent"], made["colors"]["selected"]),
                                 (frame["accent"], frame["active_row_bg"]))
        themes = {rel for rel in build.outputs() if rel.startswith(os.path.join("app", "themes", ""))}
        self.assertEqual(len(themes), len(self.themes) + 1)        # each theme, and the layout's own

    def test_an_agents_state_wears_the_tuis_color(self):
        # as the TUI's column marks it: the state's role (chat_list.py), the role's palette color (theme.py)
        sys.path.insert(0, os.path.join(PACKAGE, "src", "plugins", "sidebar"))
        import chat_list
        import theme
        for tui in self.themes:
            with self.subTest(tui["id"]):
                made, palette = self.made(f"herdr-fold-{tui['id']}.json")["colors"], tui["colors"]["palette"]
                for state, role in chat_list.STATE_ROLE.items():
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
                self.assertGreaterEqual(self.apply.contrast(made["raised"], made["surface"]), build.RAISED)
                # a level's step at least: a smaller one only where the text on it would read under 4.5 (Solarized)
                self.assertGreaterEqual(self.apply.contrast(made["hover"], made["raised"]), build.MIN_STEP)

    def test_a_fields_frame_shows_and_stays_quieter_than_the_words(self):
        for tui in self.themes:
            with self.subTest(tui["id"]):
                made = self.made(f"herdr-fold-{tui['id']}.json")["colors"]
                self.assertGreaterEqual(self.apply.contrast(made["input"], made["surface"]), 1.5)
                self.assertLess(self.apply.luminance(made["input"]), self.apply.luminance(made["muted"]))

    def every_app_theme(self):
        """Each app theme the build makes ({file name: its colors}), the layout's own among them."""
        return {os.path.basename(rel): json.loads(content)["colors"] for rel, content in build.outputs().items()
                if rel.startswith(os.path.join("app", "themes", ""))}

    def test_each_theme_names_its_three_levels_in_its_palettes_words(self):
        self.assertEqual(sorted(build.LEVELS), sorted(theme["id"] for theme in self.themes))
        for name, given in build.LEVELS.items():
            with self.subTest(name):
                self.assertEqual(len(given["names"].split(" / ")), 3)
                self.assertTrue(given["source"].startswith("https://"))
                self.assertRegex(given["surface"], r"^#[0-9a-f]{6}$")             # the cards always the palette's
                for level in ("canvas", "chrome"):
                    self.assertRegex(given[level] or "#000000", r"^#[0-9a-f]{6}$")
        made = {theme["id"]: self.made(f"herdr-fold-{theme['id']}.json")["colors"] for theme in self.themes}
        for name, given in build.LEVELS.items():
            for level in ("canvas", "chrome", "surface"):
                if given[level]:
                    self.assertEqual(made[name][level], given[level], (name, level))

    def test_every_themes_three_levels_darkest_first_parted_by_the_minimum_step(self):
        # the window (canvas), the side (chrome), the cards (surface) and the popovers as the cards
        themes = self.every_app_theme()
        self.assertEqual(len(themes), 13)
        for name, colors in themes.items():
            with self.subTest(name):
                canvas, chrome, surface = (colors[level] for level in ("canvas", "chrome", "surface"))
                self.assertLess(self.apply.luminance(canvas), self.apply.luminance(chrome))
                self.assertLess(self.apply.luminance(chrome), self.apply.luminance(surface))
                self.assertGreaterEqual(self.apply.contrast(canvas, chrome), build.MIN_STEP)
                self.assertGreaterEqual(self.apply.contrast(chrome, surface), build.MIN_STEP)
                self.assertEqual(colors["popover"], surface)

    def test_small_text_reads_on_every_level_and_control_in_every_theme(self):
        # WCAG AA for text of 11 to 13: the body and the captions on each level and on a control (a chip's words),
        # the body under the mouse, a count's number on the accent, Commit's words on its fill
        for name, colors in self.every_app_theme().items():
            with self.subTest(name):
                read = lambda ink, ground: self.assertGreaterEqual(                          # noqa: E731
                    self.apply.contrast(colors[ink], colors[ground]), build.READ, (ink, ground))
                for ground in ("canvas", "chrome", "surface", "raised", "hover"):
                    read("foreground", ground)
                for ground in ("canvas", "chrome", "surface", "raised"):
                    read("muted", ground)
                for ground in ("canvas", "chrome", "surface"):
                    self.assertGreaterEqual(self.apply.contrast(colors["dim"], colors[ground]), self.apply.GUIDE)
                read("accent_foreground", "accent")
                read("solid_foreground", "solid")

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
