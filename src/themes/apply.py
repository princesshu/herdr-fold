"""Sets one of themes.js's themes in herdr-fold's installed parts at once: the TUI's Ghostty, herdr, starship, sidebar,
loading animation and Mac app icon (only the "# --- theme: …" sections of the configs change), the Herdr app's
herdr-fold layout. With no argument it lists the themes. herdr reloads on its own, Ghostty on Cmd+Shift+,."""
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))     # i18n.py (the texts) and parts.py are one folder up
from i18n import line, t  # noqa: E402
from parts import app_home, installed  # noqa: E402

HOME = os.path.expanduser("~")
GHOSTTY = os.path.join(HOME, ".config", "ghostty", "config")
HERDR = os.path.join(HOME, ".config", "herdr", "config.toml")
STARSHIP = os.path.join(HOME, ".config", "starship.toml")
SIDEBAR_COLORS = os.path.join(HOME, ".local", "state", "herdr", "plugins", "herdr-fold.sidebar", "colors.json")
LOADING_COLORS = os.path.join(HOME, ".local", "state", "herdr-fold", "loading-colors.txt")   # lib/loading.sh reads it
APP_LAYOUT = os.path.join(app_home(), "layouts", "herdr-fold.json")   # the Herdr app's, its theme one of themes/
APP_THEME = "herdr-fold-"                           # app/themes/herdr-fold-ID.json: each of themes.js's in the app
GHOSTTY_ICON = os.path.join(HOME, ".config", "ghostty", "herdr-fold-icon")     # the Ghostty config includes it
ICONS = os.path.join(HOME, ".local", "state", "herdr-fold", "ghostty-icon")    # the theme in use's app icon
LOGO = os.path.join(HERE, "logo.svg")               # herdr-fold's logo, in the package's own theme (tools/logo.swift)
LOGO_COLORS = ("icon-bottom", "icon-middle", "icon-top", "icon-ears")   # its parts holding its colors (icon_colors')
MAC = sys.platform == "darwin"
BEGIN, END = "# --- theme: ", "# --- end of theme ---"


class ThemeError(Exception):
    """A config file has no theme section (the package's fresh configs provide it)."""
# the frames of the panes out of focus against the sidebar: faint, herdr's small labels in the same color still legible
FRAMES = 2.4
# a session's agent in AI Sessions against the active row's background: still legible there
ON_ACTIVE_ROW = 3.0
# the sidebar's faintest text (a conversation's agent, the tree lines) against the panes' background: still legible
GUIDE = 2.2
# an archived conversation in the Conversations column: a shade behind the faint text, still legible
ARCHIVED = 2.8


def load_themes():
    with open(os.path.join(HERE, "themes.js"), encoding="utf-8") as f:
        text = f.read()
    # a long text is split into parts joined by + at the end of a line (JavaScript), which JSON does not have
    return json.loads(re.sub(r'" *\+\n *"', "", text.split("\nconst THEMES = ", 1)[1].rsplit(";", 1)[0]))


def layout_theme(layout=None):
    """The theme herdr-fold's LAYOUT (the Herdr app's) names, or None (missing, not JSON, someone else's)."""
    data = herdr_folds_layout(layout or APP_LAYOUT)
    return data.get("theme") if data else None


def herdr_folds_layout(layout):
    """LAYOUT's data where it is herdr-fold's (a block shows its mod), else None."""
    try:
        with open(layout, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    def nodes(node):
        yield node
        for child in node.get("children") or []:
            if isinstance(child, dict):
                yield from nodes(child)
    if not isinstance(data, dict) or not any((n.get("content") or {}).get("mod") == "herdr-fold" for n in nodes(data)):
        return None
    return data


def set_layout_theme(layout, name):
    """herdr-fold's LAYOUT names the theme NAME; False where it is missing, not JSON or someone else's."""
    data = herdr_folds_layout(layout)
    if data is None:
        return False
    if data.get("theme") != name:
        write_whole(layout, json.dumps({**data, "theme": name}, indent=2) + "\n")
    return True


def current():
    """The theme in use: the TUI's (Ghostty's config), else the one the Herdr app's herdr-fold layout names (the
    package's own, herdr-fold, names none: the installer's default), else None."""
    name = layout_theme() or ""
    return current_id(GHOSTTY) or (name[len(APP_THEME):] if name.startswith(APP_THEME) else None)


def current_id(path=GHOSTTY):
    try:
        with open(path, encoding="utf-8") as f:
            return next((line[len(BEGIN):].split()[0] for line in f if line.startswith(BEGIN)), None)
    except OSError:
        return None


def find(themes, key):
    if key.isdigit() and 1 <= int(key) <= len(themes):
        return themes[int(key) - 1]
    return next((t for t in themes if t["id"] == key), None)


def replace_block(path, body):
    """Replaces the theme section in the file; the markers come with the package's configs."""
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    start = next((n for n, line in enumerate(lines) if line.startswith(BEGIN)), None)
    end = next((n for n, line in enumerate(lines) if line == END), None)
    if start is None or end is None or end < start:
        raise ThemeError(path)
    lines[start:end + 1] = body
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def comment(text):
    """TEXT as comment lines of at most 120 characters."""
    return textwrap.wrap(text, 120, initial_indent="# ", subsequent_indent="# ", break_long_words=False,
                         break_on_hyphens=False)


def ghostty_block(theme):
    body = [f"{BEGIN}{theme['id']} ({theme['name']}) — written by ~/.config/herdr-fold/themes/apply.py ---",
            f"theme = {theme['ghostty']['theme']}"]
    for item in theme["ghostty"]["set"]:
        if item["note"]:
            body += comment(item["note"])
        body.append(f"{item['key']} = {item['value']}")
    return body + [END]


def herdr_block(theme):
    body = [f"{BEGIN}{theme['id']} — written by ~/.config/herdr-fold/themes/apply.py ---", "[theme]",
            f'name = "{theme["herdr"]["theme"]}"']
    body += [""] + comment(theme["herdr"].get("note", ""))
    body += ["# The active row mixed from the accent, the navigate-mode highlight from the text color, both 1.6:1 or",
             "# more against the sidebar; the frames of the panes out of focus faint, so the focused one's stands out",
             "[theme.custom]"]
    custom = {**(theme["herdr"]["custom"] or {}), "overlay0": quiet_frames(theme)}
    body += [f'{key} = "{value}"' for key, value in custom.items()]
    # The Sessions rows: on its own, herdr would draw the session name faint too. The name is the pane name, which the
    # sessions-view plugin sets to the session title until the user renames the pane
    h = theme["colors"]["herdr"]
    body += ["", "# The Sessions rows: the session name (the pane name) in the theme's text color, bold; the state",
             "# and the agent below it, faint, the agent still legible on the active row; an empty row between two",
             "# sessions", "[ui.sidebar.agents]", "row_gap = 1", "rows = [",
             f'  ["state_icon", {{ token = "pane", fg = "{h["text"]}", bold = true }}],',
             f'  ["state_text", {{ token = "agent", fg = "{agent_color(theme)}" }}],', "]"]
    body += ["",
             "# The Spaces rows: herdr's own; beside the branch, how long an agent there waits on you in the theme's",
             "# yellow (the sessions-view plugin says so), and deleted in its red when the space's folder is gone (the",
             "# tab-layout plugin says so)", "[ui.sidebar.spaces]", "rows = [",
             '  ["state_icon", "workspace"],',
             f'  ["branch", "git_status", {{ token = "$waiting", fg = "{h["yellow"]}" }}, '
             f'{{ token = "$folder", fg = "{h["red"]}" }}],', "]"]
    return body + [END]


def set_starship(path, prompt):
    """Prompt colors: the folder and ❯ in the theme's accent color, the branch muted, git status and a failed ❯ red."""
    wanted = {"directory": {"style": f'"bold {prompt["path"]}"'},
              "git_branch": {"style": f'"{prompt["branch"]}"'},
              "git_status": {"style": f'"{prompt["status"]}"'},
              "character": {"success_symbol": f'"[❯](bold {prompt["path"]})"',
                            "error_symbol": f'"[❯](bold {prompt["status"]})"'}}
    section, out = None, []
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    for line in lines:
        header = re.match(r"\s*\[([^\]]+)\]\s*$", line)
        if header:
            section = header.group(1).strip()
        key = re.match(r"(\s*)(\w+)(\s*=\s*)", line)
        if key and key.group(2) in wanted.get(section, {}):
            line = key.group(1) + key.group(2) + key.group(3) + wanted[section][key.group(2)]
        out.append(line)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def channels(color):
    return [int(color[i:i + 2], 16) for i in (1, 3, 5)]


def luminance(color):
    """A color's relative luminance (WCAG): 0 black, 1 white."""
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in (value / 255 for value in channels(color))]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(one, other):
    """The WCAG contrast ratio of two colors."""
    light, dark = sorted((luminance(one), luminance(other)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def mix(color, toward, share):
    """COLOR moved SHARE of the way (0 to 1) toward TOWARD."""
    return "#" + "".join(f"{round(a + (b - a) * share):02x}" for a, b in zip(channels(color), channels(toward)))


# The Ghostty icon's screen, bottom to top, as light as Catppuccin Mocha's background (#11111b) moved 30, 52 and 78 %
# toward its mauve (#cba6f7): every theme's icon as bright as that one
ICON_LIGHT = [luminance(mix("#11111b", "#cba6f7", share)) for share in (0.30, 0.52, 0.78)]


def readable(color, toward, background, ratio):
    """COLOR, or moved toward TOWARD by tenths until it stands out from BACKGROUND by RATIO."""
    for tenth in range(11):
        mixed = mix(color, toward, tenth / 10)
        if contrast(mixed, background) >= ratio:
            return mixed
    return toward


def quiet_frames(theme):
    """herdr's overlay0 — the frames of the panes out of focus, and its own small labels — moved toward the sidebar's
    background until it stands out from it by no more than FRAMES, never stronger than the palette's own."""
    h = theme["colors"]["herdr"]
    for twentieth in range(21):
        mixed = mix(h["overlay0"], h["sidebar_bg"], twentieth / 20)
        if contrast(mixed, h["sidebar_bg"]) <= FRAMES:
            return mixed
    return h["sidebar_bg"]


def faint(theme):
    """The theme's faint text color: its overlay1, readable on its background; where that is no fainter than the text
    (GitHub Dark's is white), the text color moved halfway toward the background."""
    h, background = theme["colors"]["herdr"], theme["colors"]["background"]
    color = h["overlay1"]
    if contrast(color, background) >= contrast(h["text"], background):
        color = mix(h["text"], background, 0.5)
    return readable(color, h["text"], background, 3.5)


def agent_color(theme):
    """A session's agent in AI Sessions: the theme's faint text color, moved toward its text color until it
    stands out from the active row's background by ON_ACTIVE_ROW — on the other rows still fainter than the name."""
    h = theme["colors"]["herdr"]
    return readable(faint(theme), h["text"], h["active_row_bg"], ON_ACTIVE_ROW)


def sidebar_colors(theme):
    """The sidebar plugin's color for each of its roles (theme.py there names them), from the theme's herdr palette;
    its faint text as faint() makes it, its faintest (the guide lines) as herdr's own (quiet_frames()), legible, an
    archived conversation's a shade between the two."""
    h, background = theme["colors"]["herdr"], theme["colors"]["background"]
    muted = faint(theme)
    return {"text": h["text"], "subtext": h["subtext0"], "muted": muted,
            "guide": readable(quiet_frames(theme), h["text"], background, GUIDE),
            "archived": readable(mix(muted, background, 0.4), muted, background, ARCHIVED),
            "accent": h["accent"], "added": h["green"], "modified": h["yellow"], "deleted": h["red"],
            "done": h["teal"], "conflict": h["peach"],
            "ignored": h["overlay0"], "selection": h["active_row_bg"], "hover": h["surface0"], "input": h["surface0"],
            "badge": h["surface0"], "badge_text": h["text"], "button": h["accent"], "button_text": h["sidebar_bg"],
            "panel": h["panel_bg"]}


def beside(path):
    """A new empty file of its own beside PATH, for its next version, under a name no one can foresee (a link planted
    under a foreseeable one is never followed): (its open descriptor, its path)."""
    return tempfile.mkstemp(dir=os.path.dirname(path), prefix=f".{os.path.basename(path)}.", suffix=".tmp")


def write_whole(path, text):
    """TEXT into PATH through a file of its own beside it, then put in place: a reader sees the old file or the new."""
    fd, temporary = beside(path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.remove(temporary)
        except OSError:
            pass
        raise


def write_sidebar_colors(theme):
    os.makedirs(os.path.dirname(SIDEBAR_COLORS), exist_ok=True)
    write_whole(SIDEBAR_COLORS, json.dumps(sidebar_colors(theme), indent=2))


def loading_colors(theme):
    """The loading animation's colors (lib/loading.sh) from the sidebar's text, accent and faint ones, in the order it
    reads them: wool, face, wool, face, fence, grass. A face takes whichever other one stands out more from its wool."""
    sidebar = sidebar_colors(theme)
    text, accent, faint = sidebar["text"], sidebar["accent"], sidebar["muted"]

    def face(wool, *others):
        return max(others, key=lambda other: contrast(other, wool))
    return [text, face(text, faint, accent), accent, face(accent, faint, text), accent, faint]


def write_loading_colors(theme):
    """The loading animation's colors as terminal color codes (2;R;G;B), on one line."""
    os.makedirs(os.path.dirname(LOADING_COLORS), exist_ok=True)
    write_whole(LOADING_COLORS,
                " ".join("2;" + ";".join(map(str, channels(color))) for color in loading_colors(theme)) + "\n")


def icon_screen(theme):
    """The Ghostty icon's screen, bottom to top: the theme's background moved toward its accent by hundredths until it
    is as light as ICON_LIGHT asks; an accent darker than that goes no further than itself."""
    background, accent = theme["colors"]["background"], theme["colors"]["herdr"]["accent"]

    def lit(light):
        for hundredth in range(101):
            mixed = mix(background, accent, hundredth / 100)
            if luminance(mixed) >= light:
                return mixed
        return accent
    return [lit(light) for light in ICON_LIGHT]


# The sheep's ears stand out from the screen behind them (EARS_UP of the way from its bottom color to its middle one)
# at least as much as in the theme where they show least while still clear (Kanagawa's)
EARS, EARS_UP = 2.3, 0.74


def icon_ears(theme):
    """The color of the sheep's ears in the theme's Ghostty icon: its accent, lightened toward white by tenths (its hue
    stays) where it would melt into the screen behind them (VS Code's blue on a screen of the same blue)."""
    bottom, middle, _ = icon_screen(theme)
    return readable(theme["colors"]["herdr"]["accent"], "#ffffff", mix(bottom, middle, EARS_UP), EARS)


def icon_colors(theme):
    """The app icon's colors for THEME, in the order of the logo's parts (LOGO_COLORS): the screen's (icon_screen),
    the sheep's ears (icon_ears)."""
    return [*icon_screen(theme), icon_ears(theme)]


def themed_logo(theme):
    """herdr-fold's logo in THEME's colors: each of its parts holding a color (LOGO_COLORS) given the theme's;
    ValueError where one is not there exactly once."""
    with open(LOGO, encoding="utf-8") as f:
        svg = f.read()
    for part, color in zip(LOGO_COLORS, icon_colors(theme)):
        svg, found = re.subn(rf"(id='{part}'[^>]*?(?:stop-color|fill)=')#[0-9a-fA-F]{{6}}'", rf"\g<1>{color}'", svg)
        if found != 1:
            raise ValueError(part)                   # never shown: ghostty_icon gives no icon instead
    return svg


def ghostty_icon(theme):
    """The theme's Ghostty app icon: herdr-fold's logo in its colors (themed_logo), a file of its own in ICONS, the
    only file kept there (another theme's is written again when it is chosen). Its path, or None: not a Mac, or the logo
    could not be read or written."""
    if not MAC:
        return None
    try:
        svg = themed_logo(theme)
        icon = os.path.join(ICONS, f"{theme['id']}-{hashlib.sha256(svg.encode()).hexdigest()[:8]}.svg")
        os.makedirs(ICONS, exist_ok=True)
        if not os.path.exists(icon):
            write_whole(icon, svg)
        for name in os.listdir(ICONS):
            other = os.path.join(ICONS, name)
            if other != icon and not os.path.isdir(other):
                os.remove(other)
    except (OSError, ValueError):
        return None
    return icon


def write_ghostty_icon(theme):
    """Points Ghostty at the theme's app icon, in the file its config includes; where there is none, that file goes and
    Ghostty's own icon stays. The icon's path, or None."""
    icon = ghostty_icon(theme)
    if icon is None:
        if os.path.exists(GHOSTTY_ICON):
            os.remove(GHOSTTY_ICON)
        return None
    write_whole(GHOSTTY_ICON, "# The app icon in the theme's colors — written by ~/.config/herdr-fold/themes/apply.py\n"
                              f"macos-icon = custom\nmacos-custom-icon = {icon}\n")
    return icon


def preview_address(number=None):
    """The address of the preview beside this file, theme NUMBER (the one set now) marked (#NUMBER)."""
    return pathlib.Path(HERE, "preview.html").as_uri() + (f"#{number}" if number else "")


def icon_line(icon):
    """What became of Ghostty's app icon, as a line to print; None off a Mac."""
    if icon:
        return line("ok", t("theme.ghostty_icon"))
    return line("skip", t("theme.ghostty_icon_kept")) if MAC else None


def apply(theme, parts=None):
    """The theme in PARTS (the installed ones unless named): with the TUI, the Ghostty, herdr and starship configs and
    Ghostty's app icon; with the app, herdr-fold's layout: (herdr themed, the running herdr reloaded it, the icon's path
    or None, the app's layout themed). herdr's config without herdr-fold's theme section keeps its own theme."""
    parts = installed() if parts is None else parts
    app_themed = "app" in parts and set_layout_theme(APP_LAYOUT, APP_THEME + theme["id"])
    if "tui" not in parts:
        return False, False, None, app_themed
    replace_block(GHOSTTY, ghostty_block(theme))
    try:
        icon = write_ghostty_icon(theme)
    except OSError:
        icon = None                             # Ghostty keeps the icon it has; the theme still applies
    try:
        replace_block(HERDR, herdr_block(theme))
        herdr_themed = True
    except ThemeError:
        herdr_themed = False
    if os.path.exists(STARSHIP):
        set_starship(STARSHIP, theme["prompt"])
    try:
        write_sidebar_colors(theme)
    except OSError:
        pass                                    # the sidebar keeps the terminal's own colors; the theme still applies
    try:
        write_loading_colors(theme)
    except OSError:
        pass                                    # the loading animation keeps its own colors
    herdr_bin = os.environ.get("HERDR_BIN_PATH") or shutil.which("herdr")
    reloaded = bool(herdr_bin) and subprocess.run([herdr_bin, "server", "reload-config"],
                                                  capture_output=True).returncode == 0
    return herdr_themed, reloaded, icon, app_themed


def main():
    themes, args = load_themes(), sys.argv[1:]
    if args[:1] == ["--current"]:                   # the theme in use, or the one a Ghostty config (PATH) sets
        tid = current_id(args[1]) if len(args) > 1 else current()
        number = next((n for n, t in enumerate(themes, 1) if t["id"] == tid), None)
        if number:
            print(number)
        return
    if args[:1] == ["--preview"] and len(args) <= 2:
        print(preview_address(args[1] if len(args) == 2 else None))
        return
    if args[:1] == ["--name"] and len(args) == 2:            # the installer's line names the theme it set
        theme = find(themes, args[1])
        if not theme:
            raise SystemExit(line("fail", t("theme.no_such", args[1], len(themes))))
        print(theme["name"])
        return
    if args[:1] == ["--loading-colors"] and len(args) == 2:
        theme = find(themes, args[1])
        if not theme:
            raise SystemExit(line("fail", t("theme.no_such", args[1], len(themes))))
        write_loading_colors(theme)
        return
    if not args:
        now = current()
        for n, theme in enumerate(themes, 1):
            mark = "   " + t("theme.current") if theme["id"] == now else ""
            print(f"  {n:2}. {theme['name']} — {theme['tag']}{mark}")
        return
    theme = find(themes, args[0])
    if not theme:
        raise SystemExit(line("fail", t("theme.no_such", args[0], len(themes))))
    parts = set(args[1:]) or installed()          # the parts named after it (the installer's), else the installed
    try:
        herdr_themed, reloaded, icon, app_themed = apply(theme, parts)
    except ThemeError as err:
        raise SystemExit(line("fail", t("theme.no_section", err)))
    if app_themed:
        print(line("ok", t("theme.app")))
    if "tui" not in parts:
        return
    print(line("ok", t("theme.ghostty", theme["ghostty"]["theme"])))
    note = icon_line(icon)
    if note:
        print(note)
    herdr = theme["herdr"]["theme"]
    if not herdr_themed:
        print(line("skip", t("config.theme_yours")))
    else:
        print(line("ok", t("theme.herdr_custom", herdr) if theme["herdr"]["custom"] else t("theme.herdr", herdr)))
    if os.path.exists(STARSHIP):
        print(line("ok", t("theme.starship")))
    if reloaded:
        print(line("ok", t("theme.reloaded")))
    if sys.stdout.isatty():                         # for a person at a terminal; the installer says it at its end
        print("      " + t("theme.ghostty_reload"))     # a note: under the text of the lines above


if __name__ == "__main__":
    main()
