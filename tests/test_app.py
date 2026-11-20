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
import sys
import tempfile
import unittest

from support import PACKAGE, set_env

sys.path.insert(0, os.path.join(PACKAGE, "lib"))
import herdr_app  # noqa: E402

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

    def test_the_folder_holds_what_the_catalog_lists(self):
        """herdr.dev/layouts lists the folder by its RECIPE.md, in the parts and order the app's guide gives a recipe,
        and its preview.png."""
        with open(os.path.join(APP, "RECIPE.md"), encoding="utf-8") as f:
            recipe = f.read()
        self.assertEqual(re.findall(r"^#+ (.+)$", recipe, re.M),
                         ["herdr-fold", "What you see", "How it behaves", "Built from", "Watch out", "Done when"])
        self.assertIn("![herdr-fold](preview.png)", recipe)
        with open(os.path.join(APP, "preview.png"), "rb") as f:
            self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")

    def test_the_layouts_terminals_are_the_tuis_font_and_size(self):
        with open(os.path.join(APP, "layouts", "herdr-fold.json"), encoding="utf-8") as f:
            root = json.load(f)
        with open(os.path.join(PACKAGE, "config", "ghostty", "config"), encoding="utf-8") as f:
            ghostty = f.read()
        self.assertEqual(root.get("font_size"), int(re.search(r"^font-size = (\d+)$", ghostty, re.M).group(1)))
        self.assertEqual(root.get("font"), re.search(r"^font-family = (.+)$", ghostty, re.M).group(1))

    def test_fixed_width_text_has_one_font(self):
        """Every font_family in the mod is the code font, parts.js's codeFont (the layout's, CODE_FONT where none is
        set), which the views get as `code`; no other face is named, and the mod brings that one in fonts/."""
        named, sources = [], {}
        for name in sorted(os.listdir(MOD)):
            if name.endswith(".js") and name != "icons.js":
                with open(os.path.join(MOD, name), encoding="utf-8") as f:
                    sources[name] = f.read()
        for name, text in sources.items():
            named += [f"{name}: {m}" for m in re.findall(r"font_family\(((?:[^()]|\(\))*)\)", text)
                      if m not in ("code", "codeFont()", "CODE_FONT") and not m.endswith('? code : ""')]
            faces = re.findall(r"[\"'`]([^\"'`]*(?:Mono|Menlo|Nerd Font)[^\"'`]*)[\"'`]", text)
            named += [f"{name}: {m}" for m in faces if name != "parts.js" and "${" not in m]
        self.assertEqual(named, [])
        with open(os.path.join(APP, "layouts", "herdr-fold.json"), encoding="utf-8") as f:
            font = json.load(f)["font"]
        self.assertIn(f'export const CODE_FONT = "{font}";', sources["parts.js"])
        self.assertTrue(os.path.isfile(os.path.join(MOD, "fonts", "herdr-fold-Mono-Regular.ttf")))

    def test_the_layout_is_the_apps_own_with_herdr_fold_where_changes_was(self):
        """layouts/herdr-fold.json is the app's main layout, its right panel herdr-fold's dock: one stack of the views
        and the Chats list (logic.js's VIEWS_APP, its node test the rest), under ids of its own, so the app's Settings,
        which shows and hides its panel, leaves it alone."""
        with open(os.path.join(APP, "layouts", "herdr-fold.json"), encoding="utf-8") as f:
            nodes = list(walk(json.load(f)))
        self.assertEqual({"panel", "panel-body"} & {n.get("id") for n in nodes}, set())
        stacks = {n["id"]: [c["id"] for c in n["children"]] for n in nodes if n.get("id", "").endswith("-body")
                  and n.get("type") == "stack"}
        self.assertEqual(stacks, {})                                     # no group bodies: one stack of views
        views = next(n for n in nodes if n.get("id") == "fold-views")
        self.assertEqual([c["id"] for c in views["children"]],
                         ["files", "search", "changes", "issues", "agent", "fold-chats"])
        self.assertEqual(next(n for n in nodes if n.get("id") == "agent")["content"],
                         {"mod": "herdr-fold", "props": {"view": "agent"}})
        self.assertEqual(next(n for n in nodes if n.get("id") == "changes")["content"],
                         {"mod": "herdr-fold", "props": {"view": "changes"}})
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

    def test_every_spacing_text_size_and_corner_is_on_its_scale(self):
        """Padding and gaps on parts.js's SPACE (a 4 px grid), text on its TEXT, corners on its RADII, which the
        styleguide shows: a value off them is a look of its own."""
        with open(os.path.join(MOD, "parts.js"), encoding="utf-8") as f:
            parts = f.read()
        scale = {name: {float(v) for v in re.search(rf"^export const {name} = \[([\d., ]+)\];", parts, re.M)
                        .group(1).split(",")} for name in ("SPACE", "TEXT", "RADII")}
        off = []
        for name in sorted(n for n in os.listdir(MOD) if n.endswith(".js")):
            with open(os.path.join(MOD, name), encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    for call, value in re.findall(r"\.(p[xytblr]?|gap|text_size|rounded)\(([\d.]+)\)", line):
                        kind = {"text_size": "TEXT", "rounded": "RADII"}.get(call, "SPACE")
                        if float(value) not in scale[kind]:
                            off.append(f"{name}:{n} {call}({value})")
        self.assertEqual(off, [])

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

    def test_the_dock_first_opens_at_its_ideal_width_and_keeps_the_width_dragged(self):
        """The layout's right panel and logic.js's PANEL_PX agree on the width it first opens at; the app keeps a
        dragged or folded one in the layout's own state, which the installer's prune keeps (test_lib_herdr_app)."""
        nodes, _rail = self.nodes()
        logic = pathlib.Path(MOD, "logic.js").read_text(encoding="utf-8")
        self.assertEqual(nodes["fold-panel"]["size"]["px"], int(re.search(r"^export const PANEL_PX = (\d+);", logic,
                                                                           re.M).group(1)))

    def test_the_left_sidebar_is_on_the_sides_level_and_chats_in_the_dock(self):
        """The left sidebar is the mockups' side level (chrome: its head and foot, Herdr's workspace-chrome, paint it
        too), the window round it canvas; the Spaces list paints the same, Chats shows in the dock, no popover."""
        nodes, _rail = self.nodes()
        with open(os.path.join(APP, "layouts", "herdr-fold.json"), encoding="utf-8") as f:
            root = json.load(f)
        self.assertEqual((root["background"], nodes["sidebar"]["background"]), ("canvas", "chrome"))
        sources = {name: pathlib.Path(MOD, name).read_text(encoding="utf-8") for name in ("spaces.js", "chats.js")}
        self.assertIn(".bg(t.chrome)", sources["spaces.js"])
        self.assertNotIn("t.background", sources["spaces.js"])
        self.assertNotIn("popup", sources["chats.js"])                     # in the dock, on its card, no popover

    def test_the_dock_and_the_chat_are_cards_and_the_terminals_keep_the_tuis_background(self):
        """The dock's card (its row and every view under it) and the chat are the cards' level (surface), as the
        mockups' --panel; a terminal and the pane round it the terminals' own background, which every theme the app
        brings sets to the TUI's (themes.js); the views draw no fill of their own over the card."""
        nodes, _rail = self.nodes()
        self.assertEqual(nodes["fold-views"]["background"], "surface")
        self.assertEqual({nodes["fold-terminals"]["background"], nodes["main"]["content"]["pane"]["background"]},
                         {"background"})
        apply = herdr_app.apply
        shared = {theme["id"]: theme["colors"]["background"] for theme in apply.load_themes()}
        own = apply.current_id(os.path.join(PACKAGE, "config", "ghostty", "config"))
        for name in sorted(os.listdir(os.path.join(APP, "themes"))):
            with open(os.path.join(APP, "themes", name), encoding="utf-8") as f:
                theme = json.load(f)
            key = name.removesuffix(".json").removeprefix("herdr-fold").removeprefix("-") or own
            with self.subTest(name):
                self.assertEqual(theme["background"], shared[key])
                self.assertNotIn("background", theme["colors"])           # one background: the terminals'
        roots = {"files.js": "  draw(t) {", "main.js": "  panel(t) {", "chats.js": "  list(t, rows) {",
                 "issues.js": "  render(t) {", "panel.js": "export function dockTabs", "agent.js": "  frame(t) {"}
        for name, start in roots.items():
            source = pathlib.Path(MOD, name).read_text(encoding="utf-8")
            first = re.split(r"\.child(?:ren)?\(", source[source.index(start):], 1)[0]   # its frame, before its parts
            with self.subTest(name):
                self.assertNotIn(".bg(", first)
        # a chat tab: its timeline a card, the mask behind a fading dot the same; the prompt, the person's message, a
        # tool's output and what Claude waits on the side's level (the mockups' --mantle), a command and a No's words
        # in a well (--base: canvas); nothing of the terminals' own color
        chat, card = (pathlib.Path(MOD, name).read_text(encoding="utf-8") for name in ("chat.js", "card.js"))
        self.assertIn('v_flex().id("chat").size_full().min_h(0).bg(t.surface)', chat)
        self.assertIn(".child(disc().bg(t.surface))", chat)
        # the prompt as center-chat.html's .box: the input line, the side's level, a shadow
        self.assertIn('.border_color(this.typing ? t.accent : t.input ?? t.border).bg(t.chrome).shadow_lg()', chat)
        self.assertIn(".border_color(t.border).bg(t.chrome)\n          .child(row.text)", chat)
        self.assertIn('.border_color(t.ansi3 + "59").bg(t.chrome)', card)
        self.assertEqual(re.findall(r"\.bg\(t\.background\)", chat + card), [])

    def test_chats_and_more_stand_at_the_tab_bars_end_over_the_dock_whose_tabs_and_rail_are_its_views(self):
        """As center-chat.html's: the dock's text tabs are its views; Chats (Lucide's sparkle), More and » stand at the
        tab bar's end, open or folded, so the rail has the views and the terminal alone."""
        panel = pathlib.Path(MOD, "panel.js").read_text(encoding="utf-8")
        tabs = pathlib.Path(MOD, "tabs.js").read_text(encoding="utf-8")
        end = tabs[tabs.index("export const barEnd"):tabs.index("export class TabsView")]
        self.assertLess(end.index('"bar-chats", "sparkle"'), end.index('"bar-more", "ellipsis"'))
        self.assertLess(end.index('"bar-more", "ellipsis"'), end.index("panelToggle("))
        dock = panel[panel.index("export function dockTabs"):panel.index("export function liveDockTabs")]
        self.assertIn("views.map((id) => [id, TAB_PX.get(id) ?? 0])", dock)  # the views alone, in their order
        railed = re.findall(r'\["(\w+)", "([\w-]+)", "\w+"\]', panel[panel.index("const RAILED"):])[:6]
        self.assertEqual(railed, [("files", "files"), ("search", "search"), ("changes", "git-branch"),
                                  ("issues", "circle-dot"), ("agent", "bot"), ("terminal", "square-terminal")])
        self.assertIn('mark: id === "agent" ? agentMark(agent, 14) ?? icon("bot") : null', dock)    # its agent's icon
        self.assertNotIn("groupHead", panel)

    def test_a_count_hangs_off_its_icon_on_the_rail(self):
        """A badge coming, going or growing never moves its own icon, its name or another button: it hangs off the
        icon's corner out of the flow (parts.js's countBadge, absolute), as VS Code's activity bar has it."""
        parts = pathlib.Path(MOD, "parts.js").read_text(encoding="utf-8")
        at = parts.index("export function iconTab")
        body = parts[at:parts.index("\n}\n", at)]
        self.assertIn("countBadge(t, count", body)
        self.assertNotIn("badge(t,", body)
        self.assertIn("export const countBadge = (t, count, x, y, spot = badgeSpot(x, y)) => div().absolute()", parts)

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
        set_env(self, HOME=home)
        self.assertTrue(os.path.isdir(herdr_app.storage(copy)), "the app's storage, where uninstall takes it off")


if __name__ == "__main__":
    unittest.main()
