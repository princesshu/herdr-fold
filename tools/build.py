"""Writes the copies of core/, the shared data layer: into the TUI sidebar (src/plugins/sidebar/, which installs on its
own) and into the Herdr app mod (helper.js: the source, run with Python's -c on the space's machine); and the app
layout's theme, made from the TUI's. Edit those, then run this: tests/test_build.py fails while a copy differs."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIDEBAR = os.path.join("src", "plugins", "sidebar")
WIDTH = 110                   # a string literal's cells on a line of helper.js
# the Herdr app mod's helper.js: the name it imports each module's source by, and the module
HELPERS = {os.path.join("app", "mods", "herdr-fold", "helper.js"): {"COMMIT_MESSAGE": "commit_message.py",
                                                                    "FILEOPS": "fileops.py", "GIT": "git.py",
                                                                    "JOB": "job.py", "SEARCH": "search.py"}}
MOD_ONLY = {"job.py"}         # what only the mod runs (its background jobs): the sidebar gets no copy
THEME = os.path.join("app", "themes", "herdr-fold.json")      # the herdr-fold layout's own theme in the Herdr app


def core(name):
    with open(os.path.join(ROOT, "core", name), encoding="utf-8") as f:
        return f.read()


def note(name):
    return f"Generated from core/{name} by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py"


def js_note(names):
    """helper.js's opening comment: where it comes from, and what it is for."""
    return ["// @ts-check", f"// Generated from core/ ({', '.join(names)}) by tools/build.py:",
            "// change them there, then run it again. Each module's source, run with Python's -c on the space's "
            "machine."]


def literal(text):
    """TEXT as a JS expression of string literals, one per source line (a long one cut into pieces), joined at run time:
    every line of helper.js stays inside the 120 cells every file keeps to."""
    rows = []
    for line in text.split("\n"):
        pieces, piece = [], ""
        for ch in line:
            if len(json.dumps(piece + ch)) > WIDTH:
                pieces.append(piece)
                piece = ""
            piece += ch
        rows.append(" +\n    ".join(json.dumps(one) for one in pieces + [piece]))
    return "[\n  " + ",\n  ".join(rows) + ',\n].join("\\n")'


def app_theme():
    """The herdr-fold layout's theme in the Herdr app: the package's TUI theme (src/themes/themes.js, the one its
    Ghostty config sets), in the app's theme format, the panels in the colors of herdr's frame round the TUI's panes."""
    sys.path.insert(0, os.path.join(ROOT, "src", "themes"))
    import apply
    theme = apply.find(apply.load_themes(), apply.current_id(os.path.join(ROOT, "config", "ghostty", "config")))
    colors, frame = theme["colors"], theme["colors"]["herdr"]
    selection = theme["herdr"].get("custom", {}).get("selection_bg") or frame["surface0"]
    panels = {"canvas": "sidebar_bg", "chrome": "sidebar_bg", "surface": "panel_bg", "popover": "panel_bg",
              "raised": "surface0", "hover": "surface0", "selected": "active_row_bg", "border": "surface0",
              "input": "overlay1", "foreground": "text", "muted": "subtext0", "dim": "overlay0", "accent": "accent",
              "solid": "accent", "working": "blue", "blocked": "yellow", "done": "green", "idle": "overlay0",
              "unknown": "overlay0"}
    made = {"background": colors["background"], "foreground": colors["foreground"], "selection": selection,
            "cursor": colors["cursor"], "ansi": colors["palette"],
            "colors": {**{name: frame[key] for name, key in panels.items()}, "selection": selection,
                       "accent_foreground": colors["background"], "solid_foreground": colors["background"]}}
    return json.dumps(made, indent=2) + "\n"


def outputs():
    """{path from the package's root: its content}."""
    made = {os.path.join(SIDEBAR, name): f"# {note(name)}\n" + core(name)
            for name in sorted(os.listdir(os.path.join(ROOT, "core"))) if name.endswith(".py") and name not in MOD_ONLY}
    for path, sources in HELPERS.items():
        lines = js_note(list(sources.values()))
        lines += [f"export const {const} = {literal(core(name))};" for const, name in sources.items()]
        made[path] = "\n".join(lines) + "\n"
    made[THEME] = app_theme()
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
