"""Tests for herdr-fold's Herdr app mod (app/): its logic under Node, the mod as the app itself loads it (herdr-app
check, on a copy), and the folder the app and its marketplace expect. Without Node or the app a part is skipped, as the
PowerShell tests are without PowerShell."""
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

from support import PACKAGE

APP = os.path.join(PACKAGE, "app")
MOD = os.path.join(APP, "mods", "herdr-fold")
HERDR_APP = shutil.which("herdr-app") or os.path.expanduser("~/.local/bin/herdr-app")


def walk(node):
    yield node
    for child in node.get("children", []):
        yield from walk(child)


class Logic(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "no Node")
    def test_the_mods_logic_passes_its_node_tests(self):
        out = subprocess.run(["node", "--test"], cwd=os.path.join(PACKAGE, "app"), capture_output=True, text=True,
                             timeout=120)                                    # its *.test.js, as every Node finds them
        self.assertEqual(out.returncode, 0, out.stdout[-2000:] + out.stderr[-2000:])

    @unittest.skipUnless(shutil.which("node"), "no Node")
    def test_a_files_icon_is_the_sidebars(self):
        """The mod picks a file's icon as the sidebar picks its glyph (core/icons.py's file_type, icon), from the tables
        tools/build.py copies into it: Catppuccin Icons' file, which tools/icons.py fetched."""
        spec = importlib.util.spec_from_file_location("core_icons", os.path.join(PACKAGE, "core", "icons.py"))
        icons = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(icons)
        names = ["app.py", "README.md", ".gitignore", ".env.local", "Dockerfile", "View.TSX", "archive.tar.gz",
                 ".bashrc", "notes", "package.json", "Makefile", "photo.JPEG", "LICENSE", "data.unknown", "run.ps1"]
        script = (f"import {{ fileIcon }} from {json.dumps(pathlib.Path(MOD, 'logic.js').as_uri())};\n"
                  f"console.log(JSON.stringify({json.dumps(names)}.map((name) => fileIcon(name))));")
        out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True,
                             timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        paths = [f"mods/herdr-fold/icons/catppuccin/{icons.file_type(name)}.svg" for name in names]
        self.assertEqual(json.loads(out.stdout), paths)
        self.assertTrue(all(os.path.isfile(os.path.join(APP, path)) for path in paths))


class Shape(unittest.TestCase):
    def test_the_folder_holds_what_the_app_loads(self):
        with open(os.path.join(MOD, "mod.json"), encoding="utf-8") as f:
            self.assertIn(json.load(f).get("place"), ("right", "left", "top", "bottom", "none"))
        self.assertTrue(os.path.isfile(os.path.join(MOD, "main.js")))

    def test_the_layouts_terminals_are_the_tuis_size(self):
        with open(os.path.join(APP, "layouts", "herdr-fold.json"), encoding="utf-8") as f:
            root = json.load(f)
        with open(os.path.join(PACKAGE, "config", "ghostty", "config"), encoding="utf-8") as f:
            size = int(re.search(r"^font-size = (\d+)$", f.read(), re.M).group(1))
        self.assertEqual(root.get("font_size"), size)

    def test_the_layout_is_the_apps_own_with_herdr_fold_where_changes_was(self):
        """layouts/herdr-fold.json is the app's main layout, the right panel's Changes block showing herdr-fold, under
        ids of its own, so the app's Settings, which shows and hides its panel, leaves it alone."""
        with open(os.path.join(APP, "layouts", "herdr-fold.json"), encoding="utf-8") as f:
            nodes = list(walk(json.load(f)))
        self.assertEqual({"panel", "panel-body"} & {n.get("id") for n in nodes}, set())
        stack = next(n for n in nodes if n.get("id") == "fold-panel-body")
        self.assertEqual([c["id"] for c in stack["children"]], ["files", "changes"])
        self.assertEqual(stack["children"][1]["content"], {"mod": "herdr-fold"})
        self.assertNotIn("changes", [n.get("content", {}).get("mod") for n in nodes])

    def nodes(self):
        """The layout's nodes by id, and the right panel's rail's width (logic.js's RAIL)."""
        with open(os.path.join(APP, "layouts", "herdr-fold.json"), encoding="utf-8") as f:
            nodes = {n.get("id"): n for n in walk(json.load(f))}
        with open(os.path.join(MOD, "logic.js"), encoding="utf-8") as f:
            return nodes, int(re.search(r"^export const RAIL = (\d+);", f.read(), re.M).group(1))

    def test_the_tab_bar_is_herdr_folds(self):
        # the app's own tab bar's + has no tip and no hand; herdr-fold's draws the same bar with them
        nodes, _rail = self.nodes()
        self.assertEqual(nodes["tabs"]["content"], {"mod": "herdr-fold", "props": {"part": "tabs"}})

    def test_the_panel_rail_is_as_wide_as_the_folded_sidebar(self):
        nodes, rail = self.nodes()
        self.assertEqual((nodes["fold-panel"]["min"], rail), (nodes["sidebar"]["min"], nodes["sidebar"]["min"]))

    def test_the_panel_toggle_sits_over_the_rails_middle(self):
        """The top row's panel toggle block is as wide as the rail and the work body's padding, so the toggle,
        centered over the rail's width of it, is level with the folded panel's icons."""
        nodes, rail = self.nodes()
        self.assertEqual(nodes["panel-trigger"]["size"]["px"], rail + nodes["work-body"]["padding"])

    def test_every_key_reaches_a_command_the_mod_takes(self):
        with open(os.path.join(MOD, "main.js"), encoding="utf-8") as f:
            taken = set(re.findall(r'asked === "([\w-]+)"', f.read()))           # what nextCommand() gave
        with open(os.path.join(APP, "keys.json"), encoding="utf-8") as f:
            actions = [a for section in json.load(f).values() for a in section.values()]
        self.assertTrue(actions)
        stray = [a for a in actions if a != "mod.open:herdr-fold" and a.removeprefix("herdr-fold.") not in taken]
        self.assertEqual(stray, [])

    def test_the_icons_are_the_ones_the_mod_draws(self):
        """icons/ holds each icon the mod's views name (icon("name"), or its name passed on to it) and no other; the
        styleguide shows them all, so it names none."""
        names = {name.removesuffix(".svg") for name in os.listdir(os.path.join(MOD, "icons", "lucide"))}
        code = ""
        for name in os.listdir(MOD):
            if name.endswith(".js") and name not in ("icons.js", "styleguide.js"):
                with open(os.path.join(MOD, name), encoding="utf-8") as f:
                    code += f.read()
        self.assertEqual(names - set(re.findall(r'"([\w-]+)"', code)), set(), "not drawn: delete it")
        self.assertEqual(set(re.findall(r'\bicon\("([^"]+)"', code)) - names, set(), "no such file in icons/")

    def test_every_script_has_its_types_checked(self):
        # the app loads JavaScript only; // @ts-check has an editor (and tsc) check it against the app's own types
        for root, _dirs, files in os.walk(os.path.join(PACKAGE, "app")):
            for name in files:
                if name.endswith(".js"):
                    with self.subTest(name), open(os.path.join(root, name), encoding="utf-8") as f:
                        self.assertEqual(f.readline().strip(), "// @ts-check")


class App(unittest.TestCase):
    @unittest.skipUnless(os.access(HERDR_APP, os.X_OK), "no Herdr app")
    def test_the_app_loads_the_mod(self):
        # on a copy in a home of its own: the check writes its editor files beside the mod, and nothing of the user's
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        copy = os.path.join(home, "mods", "herdr-fold")
        shutil.copytree(MOD, copy)
        env = {"HOME": home, "PATH": "/usr/bin:/bin", "HERDR_APP_HOME": home, "HERDR_TELEMETRY": "0",
               "DO_NOT_TRACK": "1"}
        out = subprocess.run([HERDR_APP, "check", copy], env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
