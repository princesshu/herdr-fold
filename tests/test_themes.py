"""Tests for themes/apply.py on temporary files: the config's current theme, replacing the block between its markers,
the sidebar's colors (each text readable on its background), and the Ghostty app icon in the theme's colors."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import PACKAGE, SRC, png_alpha, png_rgba, set_attrs, set_env

sys.path.insert(0, os.path.join(SRC, "themes"))
sys.path.append(os.path.join(SRC, "plugins", "sidebar"))
import apply  # noqa: E402
from theme import PALETTE_BG, PALETTE_FG  # noqa: E402

DRAWER = os.path.join(PACKAGE, "tools", "logo.swift")                     # herdr-fold's logo, its app icon
# the maintainer's media folder beside the repository: its images are drawn by the same drawer (never published)
MEDIA_TOOL = os.path.join(os.path.dirname(PACKAGE), "media", "tools", "overview.py")
CONFIG = ("font-size = 13\n# --- theme: vesper — written by apply.py ---\ntheme = Vesper\n# --- end of theme ---\n"
          "mine = 1\n")


class Themes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.path = os.path.join(self.tmp, "config")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(CONFIG)

    def test_the_current_theme_is_read_from_the_marker(self):
        self.assertEqual(apply.current_id(self.path), "vesper")

    def test_no_marker_means_no_current_theme(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("font-size = 13\n")
        self.assertIsNone(apply.current_id(self.path))

    def test_the_block_is_replaced_and_the_rest_kept(self):
        apply.replace_block(self.path, ["# --- theme: nord ---", "theme = Nord", "# --- end of theme ---"])
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "font-size = 13\n# --- theme: nord ---\ntheme = Nord\n# --- end of theme ---\n"
                                       "mine = 1\n")

    def test_a_file_without_markers_is_left_alone(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("font-size = 13\n")
        with self.assertRaises(apply.ThemeError):
            apply.replace_block(self.path, ["x"])
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "font-size = 13\n")


class Themed(unittest.TestCase):
    """Every file apply.py writes is in a temporary folder, and the herdr it calls is never the running one."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_attrs(self, apply, GHOSTTY=os.path.join(self.tmp, "ghostty"), HERDR=os.path.join(self.tmp, "config.toml"),
                  STARSHIP=os.path.join(self.tmp, "starship.toml"),
                  SIDEBAR_COLORS=os.path.join(self.tmp, "state", "herdr-fold.sidebar", "colors.json"),
                  LOADING_COLORS=os.path.join(self.tmp, "state", "herdr-fold", "loading-colors.txt"),
                  GHOSTTY_ICON=os.path.join(self.tmp, "herdr-fold-icon"),
                  ICONS=os.path.join(self.tmp, "state", "herdr-fold", "ghostty-icon"), MAC=True)
        set_env(self, HERDR_BIN_PATH="/usr/bin/true")
        with open(apply.GHOSTTY, "w", encoding="utf-8") as f:
            f.write(CONFIG)


class Apply(Themed):
    """Applying a theme: Ghostty, herdr and the prompt — herdr's only where its config has herdr-fold's theme section
    (someone's own herdr theme stays, the installer's "add" mode)."""

    def test_their_own_herdr_theme_stays(self):
        theirs = '[theme]\nname = "tokyonight"\n'
        with open(apply.HERDR, "w", encoding="utf-8") as f:
            f.write(theirs)
        nord = apply.find(apply.load_themes(), "nord")
        herdr_themed = apply.apply(nord)[0]
        self.assertFalse(herdr_themed)
        with open(apply.HERDR, encoding="utf-8") as f:
            self.assertEqual(f.read(), theirs)
        self.assertEqual(apply.current_id(apply.GHOSTTY), "nord")

    def test_every_file_it_writes_is_in_the_test_folder(self):
        home = [name for name, value in vars(apply).items() if isinstance(value, str) and not name.startswith("__")
                and value.startswith(apply.HOME + os.sep) and not value.startswith(PACKAGE + os.sep)]
        self.assertEqual([name for name in home if not getattr(apply, name).startswith(self.tmp + os.sep)], [])


class WrittenBeside(Themed):
    """Each file apply.py writes goes through one of its own beside it, under a name no one can foresee: a link planted
    under the foreseeable one (the file's name with .tmp) is never followed, and nothing is left beside it."""

    def test_a_link_planted_beside_a_file_is_never_followed(self):
        target = os.path.join(self.tmp, "elsewhere")
        with open(target, "w", encoding="utf-8") as f:
            f.write("mine\n")
        theme = apply.find(apply.load_themes(), "nord")
        drawn = hashlib.sha256(apply.themed_logo(theme).encode()).hexdigest()[:8]
        written = [apply.SIDEBAR_COLORS, apply.LOADING_COLORS, apply.GHOSTTY_ICON,
                   os.path.join(apply.ICONS, f"nord-{drawn}.svg")]
        for path in written:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            os.symlink(target, path + ".tmp")
        apply.write_sidebar_colors(theme)
        apply.write_loading_colors(theme)
        self.assertIsNotNone(apply.write_ghostty_icon(theme))
        with open(target, encoding="utf-8") as f:
            self.assertEqual(f.read(), "mine\n")
        self.assertEqual([path for path in written if not os.path.isfile(path) or os.path.islink(path)], [])
        left = [os.path.join(folder, name) for folder, _, names in os.walk(self.tmp) for name in names
                if name.endswith(".tmp") and not os.path.islink(os.path.join(folder, name))]
        self.assertEqual(left, [])


class PackageSettings(unittest.TestCase):
    """The package's own Ghostty and herdr settings: the room the whole app gives its rows, and theme blocks exactly as
    apply.py writes them."""

    def setUp(self):
        with open(os.path.join(PACKAGE, "config", "ghostty", "config"), encoding="utf-8") as f:
            self.ghostty = f.read()
        with open(os.path.join(PACKAGE, "config", "herdr", "config.toml"), encoding="utf-8") as f:
            self.herdr = f.read()

    def test_ghostty_gives_the_rows_and_the_window_room(self):
        for setting in ("adjust-cell-height = 10%", "window-padding-x = 8", "window-padding-y = 8"):
            self.assertIn("\n" + setting + "\n", self.ghostty)

    def test_herdrs_sessions_have_their_state_faint_below_and_an_empty_row_between_them(self):
        # the name, and below it the state in herdr's own faint style, as a space's branch, and the agent
        name = r'  \["state_icon", \{ token = "pane"[^\n]*\],\n'
        state = r'  \["state_text", \{ token = "agent", fg = "#[0-9a-f]{6}" \}\],\n'
        self.assertRegex(self.herdr, r"\[ui\.sidebar\.agents\]\nrow_gap = 1\nrows = \[\n" + name + state + r"\]\n")
        self.assertNotIn("$nav", self.herdr)

    def test_a_space_says_how_long_an_agent_waits_and_whether_its_folder_is_gone_beside_its_branch(self):
        # herdr's own Space rows; after the branch AI Sessions' $waiting in the theme's yellow, then the tab layout's
        # $folder in its red (it reports "deleted")
        for theme in apply.load_themes():
            h = theme["colors"]["herdr"]
            body = "\n".join(apply.herdr_block(theme))
            rows = body.split("[ui.sidebar.spaces]\n", 1)[-1].split("\n]", 1)[0]
            self.assertEqual(rows.split("\n"), ["rows = [", '  ["state_icon", "workspace"],',
                                                 f'  ["branch", "git_status", {{ token = "$waiting", fg = '
                                                 f'"{h["yellow"]}" }}, {{ token = "$folder", fg = "{h["red"]}" }}],'],
                             theme["id"])
            self.assertGreaterEqual(apply.contrast(h["yellow"], h["sidebar_bg"]), 4.5, theme["id"])

    def test_a_sessions_agent_shows_on_the_active_row_and_stays_fainter_than_its_name(self):
        # the active row is mixed from the accent: herdr's own faint gray all but vanished on it
        for theme in apply.load_themes():
            h = theme["colors"]["herdr"]
            found = re.search(r'\{ token = "agent", fg = "(#[0-9a-f]{6})" \}', "\n".join(apply.herdr_block(theme)))
            self.assertIsNotNone(found, theme["id"])
            agent = found.group(1)
            self.assertGreaterEqual(apply.contrast(agent, h["active_row_bg"]), apply.ON_ACTIVE_ROW, theme["id"])
            self.assertLess(apply.contrast(agent, h["sidebar_bg"]), apply.contrast(h["text"], h["sidebar_bg"]),
                            theme["id"])

    def test_the_frames_of_the_panes_out_of_focus_are_faint_in_every_theme(self):
        # herdr draws the focused pane's frame in the accent and the others in overlay0: faint, so the focused one
        # stands out, never stronger than the palette's own (overlay0 also writes herdr's small labels: still legible)
        for theme in apply.load_themes():
            h = theme["colors"]["herdr"]
            body = "\n".join(apply.herdr_block(theme))
            found = re.search(r'^overlay0 = "(#[0-9a-f]{6})"$', body.split("[theme.custom]", 1)[-1], re.M)
            self.assertIsNotNone(found, theme["id"])
            faint, ground = found.group(1), h["sidebar_bg"]
            self.assertLessEqual(apply.contrast(faint, ground), apply.FRAMES + 0.05, theme["id"])
            self.assertLessEqual(apply.contrast(faint, ground), apply.contrast(h["overlay0"], ground) + 0.01,
                                 theme["id"])
            self.assertGreaterEqual(apply.contrast(faint, ground), min(1.6, apply.contrast(h["overlay0"], ground)),
                                    theme["id"])

    def test_the_prompt_fits_the_narrow_terminal(self):
        # the folder from the repository's root alone on the first line, the branch and the git status before the ❯:
        # a line of the whole path, the branch and the status broke in the right-hand column's terminal
        with open(os.path.join(PACKAGE, "config", "starship.toml"), encoding="utf-8") as f:
            starship = f.read()
        layout = starship.split('format = """\n', 1)[1].split('"""', 1)[0]
        self.assertEqual(layout.split("\n"), ["$directory", "$git_branch$git_status$character"])
        self.assertIn("\ntruncate_to_repo = true\n", starship)

    def test_the_pickers_sample_prompt_is_the_one_the_terminal_shows(self):
        # the folder from the repository's root alone, then the branch, the status and the ❯, as starship draws them
        import picker
        rows = [re.sub(r"\x1b\[[0-9;]*m", "", row).rstrip() for row in picker.sample(apply.load_themes()[0], 56)]
        self.assertEqual(rows[:2], [" repo", " main [!] ❯ claude"])

    def test_the_previews_sketch_shows_no_tilde(self):
        # as the app: the home folder's workspace is home, the prompt's folder starts at the repository's root
        with open(os.path.join(SRC, "themes", "preview.html"), encoding="utf-8") as f:
            sketch = f.read().split("function mock(", 1)[1].split("\n}\n", 1)[0]
        self.assertNotIn("~", sketch)
        self.assertIn('<span class="n">1</span>home', sketch)

    def test_ghostty_takes_its_app_icon_from_the_file_the_theme_writes(self):
        # a file of its own beside the config, outside the theme block: the icon's path is this Mac's, never the repo's
        self.assertIn("\nconfig-file = ?herdr-fold-icon\n", self.ghostty)
        self.assertNotIn("config-file", self.ghostty.split(apply.BEGIN, 1)[1].split(apply.END, 1)[0])
        self.assertEqual(os.path.dirname(apply.GHOSTTY_ICON), os.path.dirname(apply.GHOSTTY))
        self.assertEqual(os.path.basename(apply.GHOSTTY_ICON), "herdr-fold-icon")

    def test_the_theme_blocks_are_what_apply_writes(self):
        theme = apply.find(apply.load_themes(), apply.current_id(os.path.join(PACKAGE, "config", "ghostty", "config")))
        for text, body in ((self.ghostty, apply.ghostty_block(theme)), (self.herdr, apply.herdr_block(theme))):
            self.assertIn("\n".join(body) + "\n", text)

    def test_what_every_theme_shares_is_said_once(self):
        # the highlights are made the same way in every theme: apply.py says so, no theme's note repeats it
        themes = apply.load_themes()
        self.assertEqual([t["id"] for t in themes if "highlight" in t["herdr"].get("note", "")], [])
        self.assertEqual([t["id"] for t in themes if "highlight" not in "\n".join(apply.herdr_block(t))], [])


class TerminalColors(unittest.TestCase):
    def test_no_theme_bends_a_terminal_color_for_a_sidebar(self):
        """The sidebar takes the theme's exact colors from colors.json: Catppuccin Mocha keeps its own blues."""
        themes = apply.load_themes()
        mocha = apply.find(themes, "catppuccin")
        blues = [s["value"] for s in mocha["ghostty"]["set"]
                 if s["key"] == "palette" and s["value"][:2] in ("4=", "12")]
        self.assertEqual(blues, [])
        self.assertEqual((mocha["colors"]["palette"][4], mocha["colors"]["palette"][12]), ("#89b4fa", "#74a8fc"))


def luminance(color):
    def channel(value):
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(one, other):
    light, dark = sorted((luminance(one), luminance(other)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


class SidebarColors(Themed):
    def setUp(self):
        super().setUp()
        with open(apply.HERDR, "w", encoding="utf-8") as f:
            f.write('[theme]\nname = "tokyonight"\n')

    def test_applying_a_theme_writes_every_role(self):
        nord = apply.find(apply.load_themes(), "nord")
        apply.apply(nord)
        with open(apply.SIDEBAR_COLORS, encoding="utf-8") as f:
            colors = json.load(f)
        self.assertEqual(set(colors), set(PALETTE_FG) | set(PALETTE_BG))
        self.assertEqual(colors["accent"], nord["colors"]["herdr"]["accent"])

    def test_the_faint_color_is_fainter_than_the_text_in_every_theme(self):
        # GitHub Dark's overlay1 is white: as faint text it would stand out more than the text itself
        louder = [theme["id"] for theme in apply.load_themes() if contrast(apply.sidebar_colors(theme)["muted"],
                  theme["colors"]["background"]) >= contrast(apply.sidebar_colors(theme)["text"],
                                                             theme["colors"]["background"])]
        self.assertEqual(louder, [])

    def test_the_faintest_text_is_legible_and_fainter_than_the_faint_one(self):
        # Nord's overlay0, as faint as herdr makes its frames, stood out by only 1.7 against its background
        problems = []
        for theme in apply.load_themes():
            colors, background = apply.sidebar_colors(theme), theme["colors"]["background"]
            guide, muted = contrast(colors["guide"], background), contrast(colors["muted"], background)
            if not apply.GUIDE <= guide < muted:
                problems.append(f"{theme['id']}: {guide:.2f} (muted {muted:.2f})")
        self.assertEqual(problems, [])

    def test_an_archived_conversation_is_a_legible_shade_between_the_faint_text_and_the_lines(self):
        problems = []
        for theme in apply.load_themes():
            colors, background = apply.sidebar_colors(theme), theme["colors"]["background"]
            guide, archived, muted = (contrast(colors[role], background) for role in ("guide", "archived", "muted"))
            if not (apply.ARCHIVED <= archived < muted and guide <= archived):
                problems.append(f"{theme['id']}: {archived:.2f} (guide {guide:.2f}, muted {muted:.2f})")
        self.assertEqual(problems, [])

    def test_every_theme_is_readable_in_the_sidebar(self):
        pairs = (("button_text", "button"), ("badge_text", "badge"), ("text", "selection"), ("text", "hover"),
                 ("text", "input"), ("text", "panel"), ("accent", "panel"))
        low = []
        for theme in apply.load_themes():
            colors, background = apply.sidebar_colors(theme), theme["colors"]["background"]
            low += [f"{theme['id']}: {fg} on {bg}" for fg, bg in pairs if contrast(colors[fg], colors[bg]) < 3]
            low += [f"{theme['id']}: {fg}" for fg in ("text", "subtext", "muted", "accent", "added", "modified",
                                                       "deleted", "done")
                    if contrast(colors[fg], background) < 3]
        self.assertEqual(low, [])


class Preview(unittest.TestCase):
    """The theme preview (preview.html) shows each theme as the package sets it: what it needs beyond themes.js comes
    from tools/preview_colors.py, out of the theme setter and the sidebar themselves."""

    def test_its_colors_are_the_theme_setters(self):
        sys.path.insert(0, os.path.join(PACKAGE, "tools"))
        import preview_colors
        with open(os.path.join(SRC, "themes", "preview-colors.js"), encoding="utf-8") as f:
            self.assertEqual(f.read(), preview_colors.content(),
                             "out of date: /usr/bin/python3 tools/preview_colors.py")

    def test_each_card_sets_the_logos_four_colors(self):
        # the logo's colors (the package's own theme's, written in) become CSS variables each card sets
        with open(os.path.join(SRC, "themes", "preview-colors.js"), encoding="utf-8") as f:
            data = json.loads(f.read().split("const PREVIEW = ", 1)[1].rsplit(";", 1)[0])
        logo = "\n".join(data["logo"])
        self.assertEqual([logo.count(f"var(--{name})") for name in ("bottom", "middle", "top", "ears")], [1] * 4)
        own = apply.find(apply.load_themes(), apply.current_id(os.path.join(PACKAGE, "config", "ghostty", "config")))
        self.assertEqual([color for color in apply.icon_colors(own) if color in logo], [])

    @unittest.skipUnless(sys.platform == "darwin", "the page's script runs in macOS's own JavaScript here")
    def test_each_card_shows_the_logo_in_its_themes_colors(self):
        # one drawing for every card (the drawer's SVG), each card's colors and names of its own: a gradient a card
        # names is never another card's
        with open(os.path.join(SRC, "themes", "preview.html"), encoding="utf-8") as f:
            source = "function icon(" + f.read().split("function icon(", 1)[1].split("\n}\n", 1)[0] + "\n}\n"
        preview = {"logo": ["<svg><linearGradient id='icon-screen'/>", "<rect fill='url(#icon-screen)'/></svg>"],
                   "themes": {"a": {"icon": ["#100000", "#200000", "#300000", "#400000"]},
                              "b": {"icon": ["#010000", "#020000", "#030000", "#040000"]}}}
        script = (f"var PREVIEW = {json.dumps(preview)};\n{source}"
                  "JSON.stringify([icon({id: 'a'}, 1), icon({id: 'b'}, 2)])")
        done = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", "-e", script], capture_output=True, text=True,
                              timeout=30)
        self.assertEqual(json.loads(done.stdout or "null"), [
            '<div class="icon" style="--bottom:#100000;--middle:#200000;--top:#300000;--ears:#400000">'
            "<svg><linearGradient id='icon1-screen'/>\n<rect fill='url(#icon1-screen)'/></svg></div>",
            '<div class="icon" style="--bottom:#010000;--middle:#020000;--top:#030000;--ears:#040000">'
            "<svg><linearGradient id='icon2-screen'/>\n<rect fill='url(#icon2-screen)'/></svg></div>"], done.stderr)

    @unittest.skipUnless(sys.platform == "darwin", "the page's script runs in macOS's own JavaScript here")
    def test_the_sheep_are_whole_pixels_never_characters(self):
        # a character is never a whole number of pixels wide: letters drawn side by side leave seams (Safari shows
        # them). The page's sheep() on a tiny flock: rectangles on a whole-pixel grid, every pixel where the terminal
        # draws it: the two sheep, the fence between them on the last two rows, the grass below
        with open(os.path.join(SRC, "themes", "preview.html"), encoding="utf-8") as f:
            source = "function sheep(" + f.read().split("function sheep(", 1)[1].split("\n}\n", 1)[0] + "\n}\n"
        preview = {"sheep": ["WW", "FL"], "themes": {"t": {"loading": ["#a", "#b", "#c", "#d", "#e", "#f"]}}}
        script = f"var PREVIEW = {json.dumps(preview)};\n{source}sheep({{id: 't'}})"
        done = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", "-e", script], capture_output=True, text=True,
                              timeout=30)
        drawn = done.stdout.strip()
        self.assertTrue(drawn.startswith("<svg") and 'shape-rendering="crispEdges"' in drawn, drawn or done.stderr)
        self.assertFalse(set("▀▄█") & set(drawn))
        pixels = {}
        for x, y, width, height, fill in re.findall(
                r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)" fill="([^"]+)"/>', drawn):
            for row in range(int(y), int(y) + int(height)):
                for col in range(int(x), int(x) + int(width)):
                    pixels[row, col] = fill
        expected = {(0, 2): "#a", (0, 3): "#a", (1, 2): "#b", (1, 3): "#b",               # wool, face and legs
                    (0, 7): "#e", (1, 7): "#e",                                         # the fence
                    (0, 11): "#c", (0, 12): "#c", (1, 11): "#d", (1, 12): "#d",         # the second sheep
                    **{(2, col): "#f" for col in range(15)}}                            # the grass
        self.assertEqual(pixels, expected)

    def test_its_sidebar_has_only_the_sidebars_colors(self):
        with open(os.path.join(SRC, "themes", "preview.html"), encoding="utf-8") as f:
            page = f.read()
        rules = re.findall(r"^\s*\.sb[^{]*\{([^}]*)\}", page, re.M)
        self.assertTrue(rules)
        colors = [value.strip() for rule in rules
                  for value in re.findall(r"(?:^|;)\s*(?:color|background)\s*:([^;]+)", rule)]
        self.assertEqual([value for value in colors if not value.startswith("var(--s-")], [])


class LoadingColors(Themed):
    """The installer's loading animation in the theme's own colors, three of them (its text, its accent and its faint
    color), each readable on the theme's background, instead of a fixed white, gray, brown and green."""

    def setUp(self):
        super().setUp()
        with open(apply.HERDR, "w", encoding="utf-8") as f:
            f.write('[theme]\nname = "tokyonight"\n')

    def test_applying_a_theme_writes_the_scenes_colors(self):
        apply.apply(apply.find(apply.load_themes(), "catppuccin"))
        text, accent, faint = "2;205;214;244", "2;203;166;247", "2;127;132;156"
        with open(apply.LOADING_COLORS, encoding="utf-8") as f:   # wool, face, wool, face, fence, grass
            self.assertEqual(f.read(), " ".join((text, faint, accent, faint, accent, faint)) + "\n")

    def test_every_theme_draws_the_scene_from_its_own_three_colors_readably(self):
        problems = []
        for theme in apply.load_themes():
            sidebar, background = apply.sidebar_colors(theme), theme["colors"]["background"]
            wool, face, other_wool, other_face, fence, _ = scene = apply.loading_colors(theme)
            if not set(scene) <= {sidebar["text"], sidebar["accent"], sidebar["muted"]}:
                problems.append(f"{theme['id']}: not its text, accent and faint color")
            problems += [f"{theme['id']}: {color} on its background" for color in scene
                         if contrast(color, background) < 3]
            problems += [f"{theme['id']}: a face like its wool" for one, two in ((wool, face), (other_wool, other_face))
                         if contrast(one, two) < 1.3]
            if (wool, fence) != (sidebar["text"], sidebar["accent"]):
                problems.append(f"{theme['id']}: a light sheep and an accent fence first")
        self.assertEqual(problems, [])


class GhosttyIcon(Themed):
    """The Ghostty app icon in the theme's colors, on a Mac: herdr-fold's logo (logo.svg beside apply.py) with its four
    colors the theme's, a file of its own; Ghostty finds it through the file its config includes. Where it cannot be
    written, Ghostty's own icon stays."""

    def setUp(self):
        super().setUp()
        with open(apply.HERDR, "w", encoding="utf-8") as f:
            f.write('[theme]\nname = "tokyonight"\n')
        themes = apply.load_themes()
        self.nord, self.dracula = apply.find(themes, "nord"), apply.find(themes, "dracula")

    def icon(self):
        with open(apply.GHOSTTY_ICON, encoding="utf-8") as f:
            text = f.read()
        found = re.fullmatch(r"(?:#.*\n)*macos-icon = custom\nmacos-custom-icon = (.+)\n", text)
        self.assertIsNotNone(found, text)
        return found.group(1)

    @staticmethod
    def colors(svg):
        """The colors the logo's parts holding one have (apply.LOGO_COLORS), and the rest of it with them left out."""
        pattern = "|".join(rf"id='{part}'[^>]*?(?:stop-color|fill)='(#[0-9a-fA-F]{{6}})'" for part in apply.LOGO_COLORS)
        found = [next(c for c in m.groups() if c) for m in re.finditer(pattern, svg)]
        return found, re.sub(r"(?:stop-color|fill)='#[0-9a-fA-F]{6}'", "", svg)

    def test_a_theme_gives_ghostty_the_logo_in_its_colors(self):
        apply.apply(self.nord)
        path = self.icon()
        self.assertTrue(path.startswith(apply.ICONS + os.sep) and path.endswith(".svg"), path)
        with open(path, encoding="utf-8") as f:
            drawn = self.colors(f.read())
        with open(apply.LOGO, encoding="utf-8") as f:
            logo = self.colors(f.read())
        self.assertEqual(drawn[0], apply.icon_colors(self.nord))
        self.assertEqual(drawn[1], logo[1])                                  # nothing else of the logo changed

    def test_only_the_icon_of_the_theme_in_use_is_kept(self):
        # another theme's is written again at once: no picture kept that nothing shows
        apply.apply(self.nord)
        first = self.icon()
        apply.apply(self.dracula)
        second = self.icon()
        self.assertFalse(os.path.exists(first))
        self.assertEqual(os.listdir(apply.ICONS), [os.path.basename(second)])

    def test_a_folder_in_the_icons_folder_is_never_deleted(self):
        # only files go from it: deleting a folder would be deleting all in it
        os.makedirs(os.path.join(apply.ICONS, "kept", "inside"))
        apply.apply(self.nord)
        self.assertTrue(os.path.isdir(os.path.join(apply.ICONS, "kept", "inside")))

    def test_where_it_cannot_be_written_ghostty_keeps_its_own_icon(self):
        set_attrs(self, apply, LOGO=os.path.join(self.tmp, "no-logo.svg"))
        with open(apply.GHOSTTY_ICON, "w", encoding="utf-8") as f:
            f.write("macos-icon = custom\nmacos-custom-icon = /an/earlier/icon.svg\n")
        self.assertIsNone(apply.apply(self.nord)[2])
        self.assertFalse(os.path.exists(apply.GHOSTTY_ICON))
        self.assertEqual(apply.current_id(apply.GHOSTTY), "nord")

    def test_a_logo_without_one_of_its_colors_gives_no_icon(self):
        logo = os.path.join(self.tmp, "logo.svg")
        with open(apply.LOGO, encoding="utf-8") as f, open(logo, "w", encoding="utf-8") as out:
            out.write(f.read().replace("id='icon-ears'", "id='other'"))
        set_attrs(self, apply, LOGO=logo)
        with self.assertRaises(ValueError):
            apply.themed_logo(self.nord)
        self.assertIsNone(apply.ghostty_icon(self.nord))

    def test_the_preview_is_the_page_beside_apply(self):
        self.assertEqual(apply.preview_address(3), apply.pathlib.Path(apply.HERE, "preview.html").as_uri() + "#3")
        self.assertEqual(apply.preview_address(), apply.pathlib.Path(apply.HERE, "preview.html").as_uri())

    def test_not_on_a_mac_no_icon_is_written(self):
        set_attrs(self, apply, MAC=False)
        apply.apply(self.nord)
        self.assertFalse(os.path.exists(apply.GHOSTTY_ICON))
        self.assertFalse(os.path.exists(apply.ICONS))

    def test_a_changed_logo_writes_anew_and_the_old_icon_goes(self):
        logo = os.path.join(self.tmp, "logo.svg")
        shutil.copy(apply.LOGO, logo)
        set_attrs(self, apply, LOGO=logo)
        apply.apply(self.nord)
        old = self.icon()
        with open(logo, "a", encoding="utf-8") as f:
            f.write("<!-- changed -->\n")
        apply.apply(self.nord)
        self.assertNotEqual(self.icon(), old)
        self.assertFalse(os.path.exists(old))
        self.assertEqual(len(os.listdir(apply.ICONS)), 1)


class IconScreen(unittest.TestCase):
    """The icon's screen, bottom to top, in each theme's own accent, as light as Catppuccin Mocha's: its background
    moved 30, 52 and 78 % toward its mauve. A dark accent (VS Code's blue) goes no further than itself."""

    def test_catppuccins_screen_is_its_background_moved_toward_its_mauve(self):
        c = apply.find(apply.load_themes(), "catppuccin")["colors"]
        self.assertEqual(apply.icon_screen(apply.find(apply.load_themes(), "catppuccin")),
                         [apply.mix(c["background"], c["herdr"]["accent"], share) for share in (0.30, 0.52, 0.78)])

    def test_every_themes_screen_is_as_light_as_catppuccins(self):
        off = []
        for theme in apply.load_themes():
            accent = theme["colors"]["herdr"]["accent"]
            for color, light in zip(apply.icon_screen(theme), apply.ICON_LIGHT):
                if color != accent and abs(apply.luminance(color) - light) > 0.01:
                    off.append(f"{theme['id']}: {color}")
                if color == accent and apply.luminance(accent) > light + 0.01:
                    off.append(f"{theme['id']}: its accent, lighter than asked")
        self.assertEqual(off, [])


class IconEars(unittest.TestCase):
    """The sheep's ears: the theme's accent, lightened toward white only where it would melt into the screen behind
    them (a third of the way up), until they stand out from it as much as in the theme where they show least."""

    def behind(self, theme):
        bottom, middle, _ = apply.icon_screen(theme)
        return apply.mix(bottom, middle, apply.EARS_UP)

    def test_every_themes_ears_stand_out_from_the_screen(self):
        faint = [theme["id"] for theme in apply.load_themes()
                 if apply.contrast(apply.icon_ears(theme), self.behind(theme)) < apply.EARS]
        self.assertEqual(faint, [])

    def test_ears_that_show_keep_the_accent(self):
        for name in ("catppuccin", "nord", "kanagawa"):
            theme = apply.find(apply.load_themes(), name)
            self.assertEqual(apply.icon_ears(theme), theme["colors"]["herdr"]["accent"], name)


@unittest.skipUnless(sys.platform == "darwin" and shutil.which("swiftc"), "needs a Mac with Swift")
class GhosttyIconDrawing(unittest.TestCase):
    """The real drawer (tools/logo.swift) compiled and run, its SVG read through sips (CoreSVG, as the Dock and Finder
    read it): Apple's app icon grid (an 824-pixel rounded square), the sheep lifted off the screen like a Liquid Glass
    layer (a soft shadow below, a light top edge), and the screen showing through its eyes and nose."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.drawer = os.path.join(cls.tmp, "draw")
        subprocess.run(["swiftc", "-O", DRAWER, "-o", cls.drawer], check=True, capture_output=True)
        cls.colors = apply.icon_colors(apply.find(apply.load_themes(), "catppuccin"))
        cls.drawn = subprocess.run([cls.drawer, "0_0", *cls.colors], check=True, capture_output=True,
                                   text=True).stdout
        svg, png = os.path.join(cls.tmp, "logo.svg"), os.path.join(cls.tmp, "logo.png")
        with open(svg, "w", encoding="utf-8") as f:
            f.write(cls.drawn)
        subprocess.run(["/usr/bin/sips", "-s", "format", "png", svg, "--out", png], check=True, capture_output=True)
        cls.alpha, cls.pixels = png_alpha(png), png_rgba(png)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def rgb(self, x, y):
        return tuple(self.pixels[y][4 * x:4 * x + 3])

    def lightness(self, x, y):
        r, g, b = self.rgb(x, y)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def sheet(self, x, y):
        """Whether the pixel is the sheep's sheet: light and gray (the screen and the glass's edge have the theme's
        hue)."""
        r, g, b = self.rgb(x, y)
        return min(r, g, b) > 200 and max(r, g, b) - min(r, g, b) < 12

    def test_it_draws_a_1024_square_svg(self):
        self.assertTrue(self.drawn.startswith("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1024 1024' "
                                              "width='1024' height='1024'>"), self.drawn[:200])
        self.assertEqual(len(self.pixels), 1024)

    def test_it_fills_apples_grid_with_wide_round_corners(self):
        a = self.alpha
        self.assertGreater(a[100][512], 128)                    # the top edge, the bottom one, the sides: 100 .. 923
        self.assertGreater(a[923][512], 128)
        self.assertGreater(a[512][100], 128)
        self.assertLess(a[512][98], 128)
        self.assertLess(a[150][150], 128)                       # a tight corner would fill this
        self.assertGreater(a[200][200], 128)

    def test_it_casts_the_systems_shadow_downward(self):
        a = self.alpha
        below, above = a[930][512], a[93][512]
        self.assertTrue(0 < below < 128, below)
        self.assertLess(above, below)

    def test_the_glass_has_its_light_edge(self):
        self.assertGreater(self.lightness(512, 103), self.lightness(512, 130) + 20)

    def test_the_sheep_is_in_the_middle(self):
        found = [(x, y) for y in range(120, 904) for x in range(120, 904) if self.sheet(x, y)]
        xs, ys = [x for x, _ in found], [y for _, y in found]
        self.assertLessEqual(abs((min(xs) + max(xs)) / 2 - 511.5), 1, (min(xs), max(xs)))
        self.assertLessEqual(abs((min(ys) + max(ys)) / 2 - 511.5), 1, (min(ys), max(ys)))

    def test_its_eyes_and_nose_show_the_screen_and_nothing_else(self):
        # holes: in each, the screen's own color on its row (beside the sheep), at most darkened by the sheep's shadow
        # through it, never lighter: no tint, no speck (the screen's gradient is dithered: a shade or two either way)
        for x, y in ((440, 483), (584, 483), (512, 590)):
            screen = self.rgb(130, y)
            seen = {self.rgb(x + dx, y + dy) for dx in range(-4, 5) for dy in range(-4, 5)}
            self.assertEqual([c for c in seen if any(a > b + 3 or a < b * 0.6 for a, b in zip(c, screen))], [],
                             (x, y, screen))

    def test_the_sheep_casts_a_soft_shadow_and_no_glow(self):
        # beside its right side, below its ear: the screen darker next to it than further out, never lighter
        side = next(x for x in range(915, 500, -1) if self.sheet(x, 640))
        rows = range(610, 671)

        def mean(column):
            return sum(self.lightness(column, y) for y in rows) / len(rows)
        self.assertGreater(mean(side + 70) - mean(side + 6), 4)
        hem = next(y for y in range(923, 500, -1) if self.sheet(512, y))         # and close below its hem
        self.assertGreater(self.lightness(130, hem + 6) - self.lightness(512, hem + 6), 8)

    def test_a_light_edge_runs_along_the_top_of_its_fleece(self):
        top = next(y for y in range(120, 600) if self.sheet(512, y))
        self.assertGreater(self.lightness(512, top + 2), self.lightness(512, top + 20) + 6)

    def test_its_ears_are_the_themes_color_with_a_light_edge(self):
        # down a line through the left ear, beside the sheet: the theme's color itself, and lighter at its top edge
        ears = tuple(int(self.colors[3][i:i + 2], 16) for i in (1, 3, 5))
        column = [self.rgb(290, y) for y in range(440, 620)]
        self.assertTrue([c for c in column if max(abs(a - b) for a, b in zip(c, ears)) <= 2], column)
        first = next(n for n, c in enumerate(column) if max(abs(a - b) for a, b in zip(c, ears)) < 40)
        self.assertGreater(max(sum(c) for c in column[first:first + 3]), sum(ears) + 30, column[first:first + 6])

    def test_the_sheet_is_gray_a_shade_darker_below(self):
        inside = [y for y in range(120, 904) if self.sheet(365, y)]
        top, bottom = inside[0], inside[-1]
        colors = [self.rgb(365, round(top + t * (bottom - top))) for t in (0.3, 0.5, 0.7)]
        self.assertEqual([max(c) - min(c) > 1 for c in colors], [False] * 3, colors)
        self.assertGreater(colors[0][1], colors[2][1] + 5, colors)

    def test_the_light_comes_from_above_no_lower_edge_is_lit(self):
        # a light edge along a lower one too would run beside the top edge of what is below it (an ear), slipped
        for x in (512, 330):                                   # the hem; the lowest curl beside the left ear
            bottom = next(y for y in range(923, 400, -1) if self.sheet(x, y))
            self.assertLess(self.lightness(x, bottom - 3), self.lightness(x, bottom - 20) + 4, x)

    def test_each_openings_rim_is_even_all_round(self):
        # the white rim round the left eye as wide above it as below it: a rim moved down reads as slipped
        def rim(step):
            y = 483
            while not self.sheet(440, y):                      # out of the hole
                y += step
            return sum(1 for k in range(30) if min(self.rgb(440, y + step * k)) > 245)    # its white pixels
        self.assertLessEqual(abs(rim(-1) - rim(1)), 1, (rim(-1), rim(1)))

    def test_the_svg_is_plain_its_colors_written_in_and_its_parts_named_for_the_preview(self):
        # no CSS variable, style or filter: the Dock, the Finder and Preview (CoreSVG) know none of them; it drew them
        # black, and drew no shadow
        for unknown in ("var(", "style=", "filter"):
            self.assertNotIn(unknown, self.drawn)
        self.assertEqual([self.drawn.count(color) for color in self.colors], [1] * 4)     # the theme setter swaps them
        # every name of a part, and only those, starts with icon-: the preview gives each card names of its own
        self.assertEqual(set(re.findall(r"(.)icon-", self.drawn)), {"'", "#"})

    def test_the_macs_own_svg_reader_shows_its_colors(self):
        # the screen in its colors, the ears in theirs, never black
        screen, ear = self.rgb(150, 512), self.rgb(290, 540)
        middle, ears = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (self.colors[1], self.colors[3]))
        self.assertLess(max(abs(a - b) for a, b in zip(screen, middle)), 30, screen)
        self.assertLess(max(abs(a - b) for a, b in zip(ear, ears)), 30, ear)

    def test_the_svg_has_the_icons_liquid_glass(self):
        # its parts named icon-glass-…: the lift's shadow, the light edges (a flat logo leaves them out)
        for part in ("icon-glass-shadow", "icon-glass-fleece-light", "icon-glass-ear-light"):
            self.assertIn(f"id='{part}'", self.drawn)

    def test_a_light_edge_follows_the_outline_inside_never_a_moved_copy(self):
        # a copy of the shape moved down and taken out of it reads as two layers slipped: the light is the outline's
        # own edge, inside it, along every arc into the corners; no part of the drawing is moved
        self.assertNotIn("translate(", self.drawn)
        light = re.search(r"<path id='icon-glass-fleece-light'.*?/>", self.drawn, re.S).group(0)
        self.assertIn("fill='none'", light)
        self.assertIn("clip-path='url(#icon-glass-body)'", light)

    def test_a_wrong_color_or_face_draws_nothing(self):
        for args in (["0_0", "red", *self.colors[1:]], ["0_00", *self.colors], ["0_0", *self.colors[:3]]):
            drawn = subprocess.run([self.drawer, *args], capture_output=True, text=True, timeout=60)
            self.assertEqual((drawn.returncode, drawn.stdout), (1, ""), args)

    @unittest.skipUnless(os.path.isfile(MEDIA_TOOL), "no media folder beside the repository")
    def test_the_media_folders_images_are_the_drawers(self):
        # drawn again where the drawer changes (tools/preview_colors.py does it): never an image of an older drawing
        done = subprocess.run([sys.executable, MEDIA_TOOL, "--check", "--draw", self.drawer], capture_output=True,
                              text=True, timeout=300)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_the_logo_is_the_drawers(self):
        sys.path.insert(0, os.path.join(PACKAGE, "tools"))
        import preview_colors
        with open(apply.LOGO, encoding="utf-8") as f:
            self.assertEqual(f.read(), preview_colors.logo(self.drawer), "out of date: /usr/bin/python3 "
                                                                         "tools/preview_colors.py")


if __name__ == "__main__":
    unittest.main()
