"""Writes the copies of core/, the shared data layer: into the TUI sidebar (src/plugins/sidebar/), Spaces (git.py), the
status line (usage.py), the Herdr app mod (helper.js, the source it runs with Python's -c on the space's machine;
icons.js, the icons); and the app's themes, from the TUI's. Edit those, run this: tests/test_tools_build.py checks."""
import ast
import importlib.util
import io
import json
import os
import re
import sys
import tokenize

sys.dont_write_bytecode = True    # core's modules it loads leave no bytecode behind
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIDEBAR = os.path.join("src", "plugins", "sidebar")
# Spaces' copies: core/git.py, its Spaces row's repository inside a folder (the app's list's too), and its imports
SPACES, SPACES_CORE = os.path.join("src", "plugins", "spaces"), ["git.py"]
# the status line's (src/statusline.py, both clients'): the limits every chat told, and their imports
STATUSLINE, STATUSLINE_CORE = "src", ["usage.py"]
# the installer's (src/herdr_config.py): herdr's config.toml read by line, which the sidebar's Settings changes too
CONFIG, CONFIG_CORE = "src", ["herdr_toml.py"]
WIDTH = 110                   # a string literal's cells on a line of helper.js
# the Herdr app mod's helper.js: the name it imports each module's source by, and the module
HELPERS = {os.path.join("app", "mods", "herdr-fold", "helper.js"): {"AGENT_LAYERS": "agent_layers_cli.py",
                                                                    "AGENT_SETUP": "agent_setup.py",
                                                                    "AGENT_STATE": "agent_state.py",
                                                                    "CHAT": "chat.py",
                                                                    "CHAT_HOOK": "chat_hook.py",
                                                                    "COMMIT_MESSAGE": "commit_message.py",
                                                                    "CONNECTORS": "connectors.py",
                                                                    "COSTS": "costs.py",
                                                                    "CHATS": "chats.py",
                                                                    "FILEOPS": "fileops.py", "GIT": "git.py",
                                                                    "GITHUB": "github.py", "GRAPH": "graph_cli.py",
                                                                    "HARNESS": "harness.py", "JOB": "job.py",
                                                                    "MEDIA": "media.py",
                                                                    "NAMED_FILES": "named_files.py",
                                                                    "PRICES": "prices.py",
                                                                    "REPORT": "report.py",
                                                                    "SEARCH": "search.py",
                                                                    "STATEFILE": "statefile.py", "TOKENS": "tokens.py",
                                                                    "TREE": "tree.py", "UPDATE": "update.py",
                                                                    "USAGE": "usage.py"}}
# only the mod runs these: its chat, its jobs, the commands of what the sidebar imports itself
MOD_ONLY = {"agent_layers_cli.py", "chat.py", "chat_hook.py", "graph_cli.py", "job.py"}
ICONS = os.path.join("app", "mods", "herdr-fold", "icons.js")       # the mod's icons, by name, and the file types'
SVGS = "mods/herdr-fold/icons"     # as the app loads them: lucide/ the views', catppuccin/ a file's, logos/ a brand's
THEMES = os.path.join("app", "themes")      # the TUI's themes in the Herdr app: herdr-fold-ID.json for each, and
THEME = os.path.join(THEMES, "herdr-fold.json")   # the herdr-fold layout's own (the package's, Catppuccin Mocha)
RAISED = 1.15                 # the contrast a control's fill needs on its panel (GitHub Dark's surface0 has none)
MIN_STEP = 1.05               # the contrast that parts two surface levels (Catppuccin's own steps: 1.07)
READ = 4.5                    # small text's contrast on what it stands on (WCAG AA)
BLACK, WHITE = "#000000", "#ffffff"
# Each theme's three surface levels in its palette's words, darkest first, as the mockups use them (docs/styleguide.md,
# Color): canvas the window, chrome the side, the bars and the prompt, surface the cards and popovers; None where the
# palette has none (levels() makes it). The terminals keep the TUI's own background (Herdr paints them with it).
LEVELS = {
    "catppuccin": {"canvas": "#11111b", "chrome": "#181825", "surface": "#1e1e2e", "names": "crust / mantle / base",
                   "source": "https://catppuccin.com/palette (Mocha)"},
    "vscode": {"canvas": None, "chrome": "#181818", "surface": "#1f1f1f",
               "names": "a step under sideBar.background / sideBar.background / editor.background",
               "source": "https://github.com/microsoft/vscode extensions/theme-defaults/themes/dark_modern.json"},
    "vesper": {"canvas": "#101010", "chrome": "#161616", "surface": "#1c1c1c",
               "names": "editor.background / tab.activeBackground / input.background",
               "source": "https://github.com/raunofreiberg/vesper themes/Vesper-dark-color-theme.json"},
    "github-dark": {"canvas": "#010409", "chrome": "#0d1117", "surface": "#161b22",
                    "names": "canvas.inset / canvas.default / canvas.overlay",
                    "source": "https://github.com/primer/primitives v7 data/colors/vars/global_dark.ts"},
    "tokyo-night": {"canvas": "#0c0e14", "chrome": "#16161e", "surface": "#1a1b26", "names": "bg_dark1 / bg_dark / bg",
                    "source": "https://github.com/folke/tokyonight.nvim lua/tokyonight/colors/night.lua"},
    "kanagawa": {"canvas": "#16161d", "chrome": "#1f1f28", "surface": "#2a2a37",
                 "names": "sumiInk0 / sumiInk3 / sumiInk4",
                 "source": "https://github.com/rebelot/kanagawa.nvim lua/kanagawa/colors.lua (wave)"},
    "rose-pine": {"canvas": "#191724", "chrome": "#1f1d2e", "surface": "#26233a", "names": "base / surface / overlay",
                  "source": "https://rosepinetheme.com/palette (main)"},
    "one-dark": {"canvas": None, "chrome": "#21252b", "surface": "#282c34",
                 "names": "a step under @level-3-color / @level-3-color / @syntax-background-color",
                 "source": "https://github.com/atom/atom packages/one-dark-ui, one-dark-syntax"},
    "dracula": {"canvas": "#191a21", "chrome": "#21222c", "surface": "#282a36", "names": "BGDarker / BGDark / BG",
                "source": "https://github.com/dracula/visual-studio-code src/dracula.yml"},
    "gruvbox": {"canvas": "#1d2021", "chrome": "#282828", "surface": "#32302f", "names": "bg0_h / bg0 / bg0_s",
                "source": "https://github.com/morhetz/gruvbox colors/gruvbox.vim (dark)"},
    "nord": {"canvas": "#2e3440", "chrome": None, "surface": "#3b4252", "names": "nord0 / halfway / nord1",
             "source": "https://www.nordtheme.com/docs/colors-and-palettes"},
    # base0, the body text, reads 4.75:1 on base03 and 4.11 on base02: the cards are base03, the two under it made
    "solarized": {"canvas": None, "chrome": None, "surface": "#002b36",
                  "names": "two steps under base03 / a step under base03 / base03",
                  "source": "https://ethanschoonover.com/solarized/"},
}


def core(name):
    with open(os.path.join(ROOT, "core", name), encoding="utf-8") as f:
        return f.read()


def imports(name):
    """The core modules core/NAME imports and the ones they import, each once, after what it imports itself."""
    found = []
    for module in re.findall(r"^(?:import|from) (\w+)", core(name), re.M):
        if os.path.isfile(os.path.join(ROOT, "core", module + ".py")):
            found += [one for one in imports(module + ".py") + [module] if one not in found]
    return found


def slim(source):
    """SOURCE without what Python never runs: the blank lines, those of a comment alone, a comment after code and the
    docstrings, a body that was one alone left a pass (a string's own lines stay)."""
    rows, rewritten = set(), {}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and token.line.lstrip().startswith("#") \
                or token.type == tokenize.NL and not token.line.strip():
            rows.add(token.start[0])
        elif token.type == tokenize.COMMENT:
            rewritten[token.start[0]] = token.line[:token.start[1]].rstrip()
    for node in ast.walk(ast.parse(source)):
        body = getattr(node, "body", None)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and body \
                and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            rows.update(range(body[0].lineno, body[0].end_lineno + 1))
            if len(body) == 1:
                rewritten[body[0].lineno] = " " * body[0].col_offset + "pass"
    return "\n".join(rewritten.get(n, line) for n, line in enumerate(source.split("\n"), 1)
                     if n not in rows or n in rewritten).rstrip("\n")


def runnable(name):
    """core/NAME's source as the mod runs it, with Python's -c on the space's machine: the core modules it needs made
    there first (imports()), each from its own source slimmed (slim(): a helper is one argument, 120 KiB at most; the
    module itself stays whole, its lines counted from its own first), so it runs alone."""
    source, needed = core(name), imports(name)
    made = "".join(f"_sys.modules[{m!r}] = _types.ModuleType({m!r})\nexec('\\n'.join([\n"
                   + "".join(f"{line!r},\n" for line in slim(core(m + ".py")).split("\n"))
                   + f"]), _sys.modules[{m!r}].__dict__)\n" for m in needed)      # its lines kept, one per line
    return f"import sys as _sys, types as _types\n{made}{source}" if needed else source


def with_imports(names):
    """NAMES (core/'s files) and the core files they import."""
    return sorted({one for name in names for one in [name] + [module + ".py" for module in imports(name)]})


def note(name):
    return f"Generated from core/{name} by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py"


def js_note():
    """helper.js's opening comment: where it comes from, and what it is for."""
    return ["// @ts-check",
            "// Generated from core/ by tools/build.py: each export a module's source, run with Python's -c on the",
            "// space's machine (MEDIA_*, OUTPUT_LINES, THEME_NAMES: core's tables, the TUI's). Change them there."]


def literal(text):
    """TEXT as a JS expression of string literals, one per source line (a long one cut into pieces), joined at run time:
    every line of helper.js stays inside the 120 cells every file keeps to."""
    rows = []
    for line in text.split("\n"):
        pieces, piece = [], ""
        for ch in line:
            if len(json.dumps(piece + ch)) > WIDTH:
                cut = piece.rfind(" ") + 1 or len(piece)          # after its last space: no word cut in two
                pieces.append(piece[:cut])
                piece = piece[cut:]
            piece += ch
        rows.append(" +\n    ".join(json.dumps(one) for one in pieces + [piece]))
    return "[\n  " + ",\n  ".join(rows) + ',\n].join("\\n")'


def module(name):
    """core/NAME.py loaded, for its tables (the core modules it imports found beside it)."""
    if os.path.join(ROOT, "core") not in sys.path:
        sys.path.insert(0, os.path.join(ROOT, "core"))
    spec = importlib.util.spec_from_file_location(f"core_{name}", os.path.join(ROOT, "core", f"{name}.py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def icons_js():
    """The mod's icons.js, by the path the app loads each: the views' (ICONS, the lucide/ folder's) and a file's by
    its extension, by its name's start, and any other's (core/icons.py's), a change's letter, and a connector's brand
    (core/connectors.py's: its name, its logo, whether that is drawn in the text's color)."""
    icons, brands = module("icons"), module("connectors").BRANDS
    file = lambda name: f"{SVGS}/catppuccin/{name}.svg"                                  # noqa: E731
    views = sorted(name[:-len(".svg")] for name in os.listdir(os.path.join(ROOT, "app", SVGS, "lucide")))
    tables = {"ICONS": {name: f"{SVGS}/lucide/{name}.svg" for name in views},
              "BY_EXTENSION": {ext: file(name) for ext, (_glyph, name) in icons.BY_EXTENSION.items()},
              "BY_NAME": [[file(name), list(starts)] for _glyph, name, starts in icons.BY_NAME],
              "FILE": file(icons.FILE), "FOLDER": {state: file(name) for state, name in icons.FOLDER.items()},
              "LETTER": icons.GIT_LETTER,
              "BRANDS": {key: {"name": one["name"], "logo": f"{SVGS}/logos/{one['logo']}.svg", "mono": one["mono"]}
                         for key, one in brands.items()}}
    lines = ["// @ts-check",
             "// Generated from core/icons.py, core/connectors.py and the icons/ folder by tools/build.py: change",
             "// them there, then run /usr/bin/python3 tools/build.py. Each icon by the path the app loads it."]
    lines += [f"export const {name} = {json.dumps(table, indent=2)};" for name, table in tables.items()]
    lines.append("/** @typedef {keyof typeof ICONS} IconName */")
    return "\n".join(lines) + "\n"


def tui_themes():
    """The TUI's themes (src/themes/themes.js), and the package's own among them (the one its Ghostty config sets)."""
    sys.path.insert(0, os.path.join(ROOT, "src", "themes"))
    import apply
    themes = apply.load_themes()
    return themes, apply.find(themes, apply.current_id(os.path.join(ROOT, "config", "ghostty", "config")))


def step(color, toward):
    """COLOR moved toward TOWARD in fiftieths until it parts from COLOR by MIN_STEP."""
    import apply
    return next(made for made in (apply.mix(color, toward, n / 50) for n in range(1, 51))
                if apply.contrast(made, color) >= MIN_STEP)


def levels(name):
    """Theme NAME's canvas, chrome and surface (LEVELS'), a level its palette lacks made: between two halfway, under
    the darkest a step toward black."""
    import apply
    given = LEVELS[name]
    surface = given["surface"]
    chrome = given["chrome"] or (apply.mix(given["canvas"], surface, 0.5) if given["canvas"] else step(surface, BLACK))
    return {"canvas": given["canvas"] or step(chrome, BLACK), "chrome": chrome, "surface": surface}


def lighter(raised, text):
    """What the mouse is on: RAISED a tenth of the way to TEXT, less where TEXT on it would read under READ (Solarized),
    never closer to RAISED than MIN_STEP."""
    import apply
    shares = [n / 100 for n in range(10, 0, -1)]
    return next((made for made in (apply.mix(raised, text, share) for share in shares)
                 if apply.contrast(text, made) >= READ and apply.contrast(made, raised) >= MIN_STEP),
                apply.mix(raised, text, 0.1))


def on_accent(accent, canvas, text):
    """The words on the accent (a count's badge, Commit's): the window's level, else the text toward white or the
    window's level toward black, whichever reads by READ first (VS Code's blue takes white, as VS Code's own)."""
    import apply
    if apply.contrast(canvas, accent) >= READ:
        return canvas
    made = (apply.readable(text, WHITE, accent, READ), apply.readable(canvas, BLACK, accent, READ))
    return next((one for one in made if apply.contrast(one, accent) >= READ), BLACK)


def app_theme(theme):
    """THEME, one of the TUI's, as a Herdr app theme: the TUI's terminal colors (the terminals' background its own),
    the window, the side and the cards in its palette's three levels (LEVELS), the rest in herdr's frame's colors."""
    import apply
    colors, frame = theme["colors"], theme["colors"]["herdr"]
    selection = theme["herdr"].get("custom", {}).get("selection_bg") or frame["surface0"]
    level = levels(theme["id"])
    panels = {"selected": "active_row_bg", "foreground": "text", "accent": "accent", "solid": "accent"}
    # a control as Herdr draws it on a card: its fill (the TUI's surface0, else a step lighter than the card), in a
    # frame between the two, lighter under the mouse; a field's frame a step lighter again
    card, text = level["surface"], frame["text"]
    raised = frame["surface0"] if apply.contrast(frame["surface0"], card) >= RAISED else apply.mix(card, text, 0.1)
    controls = {"raised": raised, "hover": lighter(raised, text), "border": apply.mix(card, raised, 0.5),
                "input": apply.mix(raised, text, 0.2)}
    # the captions (subtext0) read on a control's fill too, as a chip's words stand there (One Dark's read 4.2:1 on
    # it, Solarized's 4.1); the faintest words (folders, line numbers) legible on a card, as the TUI keeps its own
    muted = apply.readable(frame["subtext0"], text, raised, READ)
    dim = apply.readable(frame["overlay0"], text, card, apply.GUIDE)
    # an agent's state as the TUI's column marks it, its role's terminal color: blocked red, done cyan, working
    # yellow, idle green, unknown faint
    states = {"blocked": 1, "done": 6, "working": 3, "idle": 2, "unknown": 8}
    ink = on_accent(frame["accent"], level["canvas"], text)
    made = {"background": colors["background"], "foreground": colors["foreground"], "selection": selection,
            "cursor": colors["cursor"], "ansi": colors["palette"],
            "colors": {**level, "popover": card, **{name: frame[key] for name, key in panels.items()},
                       "muted": muted, "dim": dim, **controls,
                       **{state: colors["palette"][n] for state, n in states.items()},
                       "selection": selection, "accent_foreground": ink, "solid_foreground": ink}}
    return json.dumps(made, indent=2) + "\n"


def outputs():
    """{path from the package's root: its content}."""
    made = {os.path.join(SIDEBAR, name): f"# {note(name)}\n" + core(name)
            for name in sorted(os.listdir(os.path.join(ROOT, "core"))) if name.endswith(".py") and name not in MOD_ONLY}
    made.update({os.path.join(folder, name): f"# {note(name)}\n" + core(name)
                 for folder, names in ((SPACES, SPACES_CORE), (STATUSLINE, STATUSLINE_CORE),
                                       (CONFIG, CONFIG_CORE))
                 for name in with_imports(names)})
    themes, own = tui_themes()
    for path, sources in HELPERS.items():
        lines = js_note()
        lines += [f"export const {const} = {literal(runnable(name))};" for const, name in sources.items()]
        lines.append(f"export const MEDIA_KINDS = {json.dumps(module('media').KINDS, indent=2)};")
        lines.append(f"export const MEDIA_WEB = {json.dumps(module('media').WEB, indent=2)};")
        lines.append(f"export const OUTPUT_LINES = {module('named_files').LINES};")
        # the app's herdr-fold themes by the TUI's names, in its order (Cmd+Shift+T's list)
        names = {f"herdr-fold-{theme['id']}": theme["name"] for theme in themes}
        lines.append(f"export const THEME_NAMES = {json.dumps(names, indent=2)};")
        made[path] = "\n".join(lines) + "\n"
    made[ICONS] = icons_js()
    made.update({os.path.join(THEMES, f"herdr-fold-{theme['id']}.json"): app_theme(theme) for theme in themes})
    made[THEME] = app_theme(own)
    return made


def main():
    for rel, content in outputs().items():
        path = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(rel)


if __name__ == "__main__":
    sys.exit(main())
