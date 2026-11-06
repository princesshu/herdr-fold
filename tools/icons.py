"""Fetches the Herdr app mod's icons from Iconify (https://iconify.design) by name into app/mods/herdr-fold/icons/:
Lucide's for the views (UI), Catppuccin Icons' for a file by its type (core/icons.py). Run it when either list changes,
then tools/build.py; the mod draws the files it writes, and nothing asks Iconify while the app runs."""
import importlib.util
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "app", "mods", "herdr-fold", "icons")
API = "https://api.iconify.design"
WIDTH = 120                   # a line's cells, as every file keeps to
SVG = "http://www.w3.org/2000/svg"
# the views' icons, Lucide's names: the mod draws each with icon(name), and tests/test_app.py fails on one it does not
UI = ("book-marked", "bot", "check", "chevron-down", "chevron-right", "chevrons-down-up", "ellipsis", "external-link",
      "eye", "eye-off", "file-plus", "folder-plus", "git-branch", "layers", "message-square", "minus", "monitor",
      "panel-left", "panel-right", "plus", "refresh-cw", "server", "settings", "sparkles", "undo-2", "x")


def file_types():
    """Catppuccin Icons' names core/icons.py gives a file, and any other file's."""
    spec = importlib.util.spec_from_file_location("core_icons", os.path.join(ROOT, "core", "icons.py"))
    icons = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(icons)
    return tuple(sorted({name for _glyph, name, _ in icons.FILE_TYPES + icons.BY_NAME} | {icons.FILE}
                        | set(icons.FOLDER.values())))


def sets():
    """{Iconify's prefix: the names fetched from it}, a folder of icons/ each."""
    return {"lucide": UI, "catppuccin": file_types()}


def fetch(prefix, names):
    """{name: its SVG} from Iconify's set PREFIX; a name it does not have stops it."""
    url = f"{API}/{prefix}.json?" + urllib.parse.urlencode({"icons": ",".join(names)})
    asked = urllib.request.Request(url, headers={"User-Agent": "herdr-fold-tools"})    # the API turns away Python's
    with urllib.request.urlopen(asked, timeout=30) as answer:
        data = json.load(answer)
    missing = sorted(set(names) - set(data.get("icons", {})))
    if missing:
        sys.exit(f"{prefix} has no {', '.join(missing)}")
    width, height = data.get("width", 16), data.get("height", 16)
    return {name: svg(icon["body"], icon.get("width", width), icon.get("height", height))
            for name, icon in data["icons"].items()}


def svg(body, width, height):
    """BODY (Iconify's) as an SVG file, an element a line, none longer than WIDTH: a long tag's attributes one a line,
    a long path's data broken before its commands. A DTD or an entity (the answer is someone else's) stops it."""
    if "<!" in body:
        raise ValueError("a DTD or an entity: not an icon this writes")
    root = ET.fromstring(f'<svg xmlns="{SVG}" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
                         f"{body}</svg>")
    return "\n".join(element(root, 0, top=True)) + "\n"


def element(node, depth, top=False):
    """NODE and what it holds as lines, at DEPTH."""
    tag, pad = node.tag.removeprefix("{" + SVG + "}"), "  " * depth
    attrs = ([("xmlns", SVG)] if top else []) + list(node.attrib.items())
    if any(name.startswith("{") for name, _ in attrs) or (node.text or "").strip():
        raise ValueError(f"<{tag}>: a namespaced attribute or text this does not write")
    close = ">" if len(node) else " />"
    one = f"{pad}<{tag}" + "".join(f" {name}={quoteattr(value)}" for name, value in attrs) + close
    lines = [one] if len(one) <= WIDTH else [f"{pad}<{tag}"] + [
        line for name, value in attrs for line in attribute(name, value, pad + "  ")] + [pad + close.strip()]
    if len(node):
        lines += [line for child in node for line in element(child, depth + 1)] + [f"{pad}</{tag}>"]
    return lines


def attribute(name, value, pad):
    """NAME="VALUE" as lines at PAD: a path's data broken before its commands (never an exponent's e) when long."""
    if len(f"{pad}{name}={quoteattr(value)}") <= WIDTH or name != "d" or '"' in value:
        return [f"{pad}{name}={quoteattr(value)}"]
    lines, line, room = [], f'{pad}{name}="', " " * len(f'{pad}{name}="')
    for piece in re.split(r"(?=[MmLlHhVvCcSsQqTtAaZz])", value):
        if len(line) + len(piece) + 1 > WIDTH and line.strip() != f'{name}="':
            lines.append(line.rstrip())
            line = room
        line += piece
    return lines + [line + '"']


def main():
    for prefix, names in sets().items():
        folder = os.path.join(ICONS, prefix)
        os.makedirs(folder, exist_ok=True)
        made = fetch(prefix, names)
        for name in os.listdir(folder):
            if name.endswith(".svg") and name[:-len(".svg")] not in made:
                os.remove(os.path.join(folder, name))
        for name, text in made.items():
            with open(os.path.join(folder, f"{name}.svg"), "w", encoding="utf-8") as f:
                f.write(text)
        print(f"{prefix}: {len(made)}")


if __name__ == "__main__":
    sys.exit(main())
