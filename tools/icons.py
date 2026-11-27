"""Fetches the Herdr app mod's icons into app/mods/herdr-fold/icons/: Lucide's (UI, a network's plain one), Catppuccin
Icons' for a file's type (core/icons.py), a connector's or a network's logo, from Iconify (https://iconify.design) or
ELSEWHERE. Run it when a list changes (icons.py logos: that folder alone), then tools/build.py; the app fetches none."""
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
AGENT = "herdr-fold-tools"    # the request's User-Agent (the API turns away Python's own): the tool, nothing else
WIDTH = 120                   # a line's cells, as every file keeps to
SVG = "http://www.w3.org/2000/svg"
# the views' icons, Lucide's names: the mod draws each with icon(name), and tests/test_app.py fails on one it does not
UI = ("arrow-up", "arrow-up-from-line", "at-sign", "audio-lines", "book-marked", "bot", "bug", "check", "chevron-down",
      "chevron-right", "chevron-up", "chevrons-down-up", "chevrons-left", "chevrons-right", "circle-dot",
      "clipboard-list", "clock", "code", "columns-2", "command", "copy", "corner-down-right", "download", "ellipsis",
      "external-link", "eye", "eye-off", "file", "file-plus", "files", "folder-plus", "git-branch", "git-pull-request",
      "hand", "layers", "leaf", "lightbulb", "link", "list", "list-filter", "loader-circle", "minus", "monitor",
      "notebook", "panel-left", "play", "plug", "plus", "refresh-cw", "rotate-ccw", "rows-2", "scroll-text", "search",
      "server", "settings", "share-2", "sparkle", "sparkles", "square", "square-slash", "square-terminal", "terminal",
      "undo-2", "wrench", "x", "zap")
# a logo SVG Logos lacks: Simple Icons' (CC0 1.0; Iconify's prefix:name), else its maker's own file, at a release
ELSEWHERE = {"zerotier": "simple-icons:zerotier",
             "netbird": "https://raw.githubusercontent.com/netbirdio/netbird/v0.83.2/client/ui/frontend/src/assets/"
                        "logos/netbird.svg"}            # BSD-3-Clause, as all its repository but the servers' folders
LARGEST = 1 << 20             # bytes of a maker's own file
KEPT = ("width", "height", "viewBox", "version")      # what a maker's root says of itself alone, not of its shapes


def core(name):
    """core/NAME.py loaded, for its tables."""
    spec = importlib.util.spec_from_file_location(f"core_{name}", os.path.join(ROOT, "core", f"{name}.py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def file_types():
    """Catppuccin Icons' names core/icons.py gives a file, and any other file's."""
    icons = core("icons")
    return tuple(sorted({name for _glyph, name, _ in icons.FILE_TYPES + icons.BY_NAME} | {icons.FILE}
                        | set(icons.FOLDER.values())))


def logos():
    """The logos of the brands core/connectors.py knows a connector by and core/icons.py a network by, by SVG Logos'
    name (else ELSEWHERE's); one with none is drawn by its letter."""
    tables = core("connectors").BRANDS, core("icons").NETWORKS
    return tuple(sorted({one["logo"] for table in tables for one in table.values() if one["logo"]}))


def plain():
    """Lucide's names of the views' icons and of a network's plain one (core/icons.py's)."""
    return tuple(sorted(set(UI) | {one["icon"] for one in core("icons").NETWORKS.values() if one["icon"]}))


def sets():
    """{a folder of icons/: the names fetched into it}, Iconify's set by that prefix (logos: ELSEWHERE's too)."""
    return {"lucide": plain(), "catppuccin": file_types(), "logos": logos()}


def chosen(names):
    """The sets NAMES ask for (none: all); one that is no set stops it."""
    every = sets()
    unknown = sorted(set(names) - set(every))
    if unknown:
        sys.exit(f"no set {', '.join(unknown)}: {', '.join(every)}")
    return {prefix: every[prefix] for prefix in names} if names else every


def fetch(prefix, names):
    """{name: its SVG} from Iconify's set PREFIX; a name it does not have stops it."""
    url = f"{API}/{prefix}.json?" + urllib.parse.urlencode({"icons": ",".join(names)})
    asked = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(asked, timeout=30) as answer:
        data = json.load(answer)
    missing = sorted(set(names) - set(data.get("icons", {})))
    if missing:
        sys.exit(f"{prefix} has no {', '.join(missing)}")
    width, height = data.get("width", 16), data.get("height", 16)
    return {name: svg(icon["body"], icon.get("width", width), icon.get("height", height))
            for name, icon in data["icons"].items()}


def gathered(prefix, names):
    """{name: its SVG} for the folder PREFIX: Iconify's set by that name; a logo ELSEWHERE names from there."""
    if prefix != "logos":
        return fetch(prefix, names)
    made = fetch(prefix, [name for name in names if name not in ELSEWHERE])
    for name in (name for name in names if name in ELSEWHERE):
        source = ELSEWHERE[name]
        if source.startswith("https://"):
            made[name] = from_file(download(source))
        else:
            other, icon = source.split(":")
            made[name] = fetch(other, [icon])[icon]
    return made


def download(url):
    """URL's text, LARGEST bytes at most; more stops it."""
    asked = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(asked, timeout=30) as answer:
        data = answer.read(LARGEST + 1)
    if len(data) > LARGEST:
        sys.exit(f"{url}: larger than {LARGEST} bytes")
    return data.decode("utf-8")


def from_file(text):
    """A maker's own SVG file TEXT as svg() writes Iconify's: its box from 0 0 (else ValueError), what its root gives
    every shape kept on a group round them, its drawing unchanged. A DTD or an entity stops it as in svg()."""
    if "<!" in text:
        raise ValueError("a DTD or an entity: not an icon this writes")
    root, own = ET.fromstring(text), "{" + SVG + "}"
    box = (root.get("viewBox") or "").split()
    if root.tag != own + "svg" or len(box) != 4 or box[:2] != ["0", "0"]:
        raise ValueError("not a drawing from 0 0: not an icon this writes")
    for node in root.iter():
        if not node.tag.startswith(own) or any(name.startswith("{") for name in node.attrib):
            raise ValueError(f"{node.tag}: another vocabulary than SVG's, not an icon this writes")
        node.tag = node.tag[len(own):]
    body = "".join(ET.tostring(child, encoding="unicode") for child in root)
    given = {name: value for name, value in root.attrib.items() if name not in KEPT}
    if given:
        body = "<g" + "".join(f" {name}={quoteattr(value)}" for name, value in given.items()) + f">{body}</g>"
    width, height = (int(n) if float(n).is_integer() else float(n) for n in box[2:])
    return svg(body, width, height)


def svg(body, width, height):
    """BODY (Iconify's) as an SVG file, square (a tall or wide mark centered in it, so a one-color one drawn in a square
    never runs out of it), an element a line, none longer than WIDTH, a long path's data broken before its commands. A
    DTD or an entity (the answer is someone else's) stops it."""
    if "<!" in body:
        raise ValueError("a DTD or an entity: not an icon this writes")
    side = max(width, height)
    box = " ".join(f"{n:g}" for n in ((width - side) / 2, (height - side) / 2, side, side))
    root = ET.fromstring(f'<svg xmlns="{SVG}" width="{side}" height="{side}" viewBox="{box}">{body}</svg>')
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


def main(argv=()):
    for prefix, names in chosen(list(argv[1:])).items():
        folder = os.path.join(ICONS, prefix)
        os.makedirs(folder, exist_ok=True)
        made = gathered(prefix, names)
        for name in os.listdir(folder):
            if name.endswith(".svg") and name[:-len(".svg")] not in made:
                os.remove(os.path.join(folder, name))
        for name, text in made.items():
            with open(os.path.join(folder, f"{name}.svg"), "w", encoding="utf-8") as f:
                f.write(text)
        print(f"{prefix}: {len(made)}")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
