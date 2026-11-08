"""Writes the copies of core/, the shared data layer: into the TUI sidebar (src/plugins/sidebar/) and into the Herdr app
mod (helper.js, the source it runs with Python's -c on the space's machine; icons.js, the icons); and the app layout's
theme, made from the TUI's. Edit those, then run this: tests/test_tools_build.py fails while a copy differs."""
import importlib.util
import json
import os
import re
import sys

sys.dont_write_bytecode = True    # core's modules it loads leave no bytecode behind
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIDEBAR = os.path.join("src", "plugins", "sidebar")
WIDTH = 110                   # a string literal's cells on a line of helper.js
# the Herdr app mod's helper.js: the name it imports each module's source by, and the module
HELPERS = {os.path.join("app", "mods", "herdr-fold", "helper.js"): {"COMMIT_MESSAGE": "commit_message.py",
                                                                    "CONVERSATIONS": "conversations.py",
                                                                    "FILEOPS": "fileops.py", "GIT": "git.py",
                                                                    "GITHUB": "github.py", "JOB": "job.py",
                                                                    "MEDIA": "media.py", "SEARCH": "search.py",
                                                                    "TREE": "tree.py", "UPDATE": "update.py"}}
MOD_ONLY = {"job.py"}         # what only the mod runs (its background jobs): the sidebar gets no copy
ICONS = os.path.join("app", "mods", "herdr-fold", "icons.js")       # the mod's icons, by name, and the file types'
SVGS = "mods/herdr-fold/icons"     # its icons as the app loads them: lucide/ the views', catppuccin/ a file's
THEMES = os.path.join("app", "themes")      # the TUI's themes in the Herdr app: herdr-fold-ID.json for each, and
THEME = os.path.join(THEMES, "herdr-fold.json")   # the herdr-fold layout's own (the package's, Catppuccin Mocha)


def core(name):
    with open(os.path.join(ROOT, "core", name), encoding="utf-8") as f:
        return f.read()


def runnable(name):
    """core/NAME's source as the mod runs it, with Python's -c on the space's machine: the core modules it imports made
    there first, each from its own source, so it runs alone."""
    source = core(name)
    needed = [module for module in re.findall(r"^(?:import|from) (\w+)", source, re.M)
              if os.path.isfile(os.path.join(ROOT, "core", module + ".py"))]
    made = "".join(f"_sys.modules[{m!r}] = _types.ModuleType({m!r})\n"
                   f"exec({core(m + '.py')!r}, _sys.modules[{m!r}].__dict__)\n" for m in needed)
    return f"import sys as _sys, types as _types\n{made}{source}" if needed else source


def note(name):
    return f"Generated from core/{name} by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py"


def js_note():
    """helper.js's opening comment: where it comes from, and what it is for."""
    return ["// @ts-check",
            "// Generated from core/ by tools/build.py, each export a module's source (MEDIA_*: media.py's",
            "// tables): change them there, then run it again. Each runs with Python's -c on the space's machine."]


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
    its extension, by its name's start, and any other's (core/icons.py's), and a change's letter."""
    icons = module("icons")
    file = lambda name: f"{SVGS}/catppuccin/{name}.svg"                                  # noqa: E731
    views = sorted(name[:-len(".svg")] for name in os.listdir(os.path.join(ROOT, "app", SVGS, "lucide")))
    tables = {"ICONS": {name: f"{SVGS}/lucide/{name}.svg" for name in views},
              "BY_EXTENSION": {ext: file(name) for ext, (_glyph, name) in icons.BY_EXTENSION.items()},
              "BY_NAME": [[file(name), list(starts)] for _glyph, name, starts in icons.BY_NAME],
              "FILE": file(icons.FILE), "FOLDER": {state: file(name) for state, name in icons.FOLDER.items()},
              "LETTER": icons.GIT_LETTER}
    lines = ["// @ts-check",
             "// Generated from core/icons.py and the icons/ folder by tools/build.py: change them there, then run",
             "// /usr/bin/python3 tools/build.py. Each icon by the path the app loads it."]
    lines += [f"export const {name} = {json.dumps(table, indent=2)};" for name, table in tables.items()]
    lines.append("/** @typedef {keyof typeof ICONS} IconName */")
    return "\n".join(lines) + "\n"


def tui_themes():
    """The TUI's themes (src/themes/themes.js), and the package's own among them (the one its Ghostty config sets)."""
    sys.path.insert(0, os.path.join(ROOT, "src", "themes"))
    import apply
    themes = apply.load_themes()
    return themes, apply.find(themes, apply.current_id(os.path.join(ROOT, "config", "ghostty", "config")))


def app_theme(theme):
    """THEME, one of the TUI's, as a Herdr app theme: the TUI's terminal colors, the panels in the colors of herdr's
    frame round the TUI's panes."""
    colors, frame = theme["colors"], theme["colors"]["herdr"]
    selection = theme["herdr"].get("custom", {}).get("selection_bg") or frame["surface0"]
    panels = {"canvas": "sidebar_bg", "chrome": "sidebar_bg", "surface": "panel_bg", "popover": "panel_bg",
              "raised": "surface0", "hover": "surface0", "selected": "active_row_bg", "border": "surface0",
              "input": "overlay1", "foreground": "text", "muted": "subtext0", "dim": "overlay0", "accent": "accent",
              "solid": "accent"}
    # an agent's state as the TUI's column marks it, its role's terminal color: blocked red, done cyan, working
    # yellow, idle green, unknown faint
    states = {"blocked": 1, "done": 6, "working": 3, "idle": 2, "unknown": 8}
    made = {"background": colors["background"], "foreground": colors["foreground"], "selection": selection,
            "cursor": colors["cursor"], "ansi": colors["palette"],
            "colors": {**{name: frame[key] for name, key in panels.items()},
                       **{state: colors["palette"][n] for state, n in states.items()}, "selection": selection,
                       "accent_foreground": colors["background"], "solid_foreground": colors["background"]}}
    return json.dumps(made, indent=2) + "\n"


def outputs():
    """{path from the package's root: its content}."""
    made = {os.path.join(SIDEBAR, name): f"# {note(name)}\n" + core(name)
            for name in sorted(os.listdir(os.path.join(ROOT, "core"))) if name.endswith(".py") and name not in MOD_ONLY}
    for path, sources in HELPERS.items():
        lines = js_note()
        lines += [f"export const {const} = {literal(runnable(name))};" for const, name in sources.items()]
        lines.append(f"export const MEDIA_KINDS = {json.dumps(module('media').KINDS, indent=2)};")
        lines.append(f"export const MEDIA_WEB = {json.dumps(module('media').WEB, indent=2)};")
        made[path] = "\n".join(lines) + "\n"
    made[ICONS] = icons_js()
    themes, own = tui_themes()
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
