"""Writes the copies of core/, the shared data layer: into the TUI sidebar (src/plugins/sidebar/, which installs on its
own) and into the Herdr app mod (helper.js: the source, run as python3 -c on the space's machine). Edit core/, then run
this: tests/test_build.py fails while a copy differs."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIDEBAR = os.path.join("src", "plugins", "sidebar")
ALSO = {"repos.py": ["src"]}  # a module the scripts of src/ use too (the folder picker), beside the sidebar's copy
WIDTH = 110                   # a string literal's cells on a line of helper.js
# the Herdr app mod's helper.js: the name it imports each module's source by, and the module
HELPERS = {os.path.join("app", "mods", "herdr-fold", "helper.js"): {"COMMIT_MESSAGE": "commit_message.py",
                                                                    "GIT": "git.py"}}


def core(name):
    with open(os.path.join(ROOT, "core", name), encoding="utf-8") as f:
        return f.read()


def note(name):
    return f"Generated from core/{name} by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py"


def js_note(names):
    """helper.js's opening comment: where it comes from, and what it is for."""
    sources = " and ".join("core/" + name for name in names)
    return ["// @ts-check", f"// Generated from {sources} by tools/build.py: change them there,",
            "// then run /usr/bin/python3 tools/build.py. Each module's source, run as python3 -c on the space's "
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


def outputs():
    """{path from the package's root: its content}."""
    made = {os.path.join(SIDEBAR, name): f"# {note(name)}\n" + core(name)
            for name in sorted(os.listdir(os.path.join(ROOT, "core"))) if name.endswith(".py")}
    made.update({os.path.join(folder, name): f"# {note(name)}\n" + core(name)
                 for name, folders in ALSO.items() for folder in folders})
    for path, sources in HELPERS.items():
        lines = js_note(list(sources.values()))
        lines += [f"export const {const} = {literal(core(name))};" for const, name in sources.items()]
        made[path] = "\n".join(lines) + "\n"
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
