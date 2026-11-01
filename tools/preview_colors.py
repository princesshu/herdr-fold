"""Writes src/themes/preview-colors.js: what the theme preview shows beyond themes.js (the sidebar's colors and icons,
the loading animation, the app icon), taken from where the package keeps it; on a Mac with Swift it first redraws the
logo (tools/logo.swift). Run it after changing any of those: tests/test_themes.py fails while the file is outdated."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "src", "themes", "preview-colors.js")
DRAWER = os.path.join(ROOT, "tools", "logo.swift")
FACE = "0_0"                                    # the logo's sheep: its round eyes, its nose between them
MEDIA_TOOL = os.path.join(os.path.dirname(ROOT), "media", "tools", "overview.py")    # never published
sys.dont_write_bytecode = True
sys.path[:0] = [os.path.join(ROOT, "src", "themes"), os.path.join(ROOT, "src", "plugins", "sidebar")]
import apply  # noqa: E402
from screen import glyphs  # noqa: E402


def sheep():
    """The loading animation's sheep, row by row (W wool, F face, L legs), as lib/loading.sh draws it."""
    with open(os.path.join(ROOT, "lib", "loading.sh"), encoding="utf-8") as f:
        art = f.read().split("\nSHEEP_ART=(", 1)[1].split(")", 1)[0]
    return re.findall(r'"([^"]*)"', art)


def own_colors():
    """The logo's colors: the app icon's in the package's own theme (its Ghostty config's)."""
    themes = apply.load_themes()
    return apply.icon_colors(apply.find(themes, apply.current_id(os.path.join(ROOT, "config", "ghostty", "config"))))


def logo(draw=None):
    """herdr-fold's logo: the app icon with its round-eyed sheep in the package's own theme, as tools/logo.swift draws
    it. DRAW: the drawer compiled, or None to compile it here."""
    with tempfile.TemporaryDirectory() as folder:
        if draw is None:
            draw = os.path.join(folder, "draw")
            subprocess.run(["swiftc", "-O", DRAWER, "-o", draw], check=True, capture_output=True)
        return subprocess.run([draw, FACE, *own_colors()], check=True, capture_output=True, text=True).stdout


def for_cards(svg):
    """The logo with its parts holding a color (apply.LOGO_COLORS) set by CSS variables instead, which each of the
    preview's cards sets to its theme's (--bottom, --middle, --top, --ears)."""
    for part, name in zip(apply.LOGO_COLORS, ("bottom", "middle", "top", "ears")):
        svg, found = re.subn(rf"(id='{part}'[^>]*?)(stop-color|fill)='#[0-9a-fA-F]{{6}}'",
                             rf"\1style='\2:var(--{name})'", svg)
        if found != 1:
            raise SystemExit(f"{part} is in the logo {found} times, not once: the preview cannot color it")
    return svg


def content():
    views = glyphs(True)
    with open(apply.LOGO, encoding="utf-8") as f:
        drawn = f.read()
    data = {"sheep": sheep(), "views": {view: views[view] for view in ("files", "search", "git", "issues")},
            "logo": for_cards(drawn).splitlines(),
            "themes": {theme["id"]: {"sidebar": apply.sidebar_colors(theme), "loading": apply.loading_colors(theme),
                                     "icon": apply.icon_colors(theme)}
                       for theme in apply.load_themes()}}
    return ("// What the theme preview shows beyond themes.js — written by tools/preview_colors.py, do not edit\n"
            "const PREVIEW = " + json.dumps(data, indent=1, ensure_ascii=False) + ";\n")


if __name__ == "__main__":
    if sys.platform == "darwin" and shutil.which("swiftc"):
        with tempfile.TemporaryDirectory() as folder:
            drawer = os.path.join(folder, "draw")
            subprocess.run(["swiftc", "-O", DRAWER, "-o", drawer], check=True, capture_output=True)
            drawn = logo(drawer)
            with open(apply.LOGO, "w", encoding="utf-8") as f:
                f.write(drawn)
            print(os.path.relpath(apply.LOGO, ROOT))
            if os.path.isfile(MEDIA_TOOL):
                subprocess.run([sys.executable, MEDIA_TOOL, "--draw", drawer], check=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(content())
    print(os.path.relpath(OUT, ROOT))
