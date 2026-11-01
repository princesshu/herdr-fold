"""Pick a color theme (Cmd+K, Cmd+T, in a herdr popup): the themes.js themes with swatches and a sample of the
selected one; Enter applies it through apply.py, p opens the browser preview. herdr switches at once, Ghostty after
Cmd+Shift+,."""
import os
import subprocess
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import apply  # noqa: E402
from i18n import line, t  # noqa: E402
from tui import getkey, wait_and_exit  # noqa: E402

RESET, BOLD, NORMAL = "\x1b[0m", "\x1b[1m", "\x1b[22m"


def rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[n:n + 2], 16) for n in (0, 2, 4))


def fg(color):
    return "\x1b[38;2;%d;%d;%dm" % rgb(color)


def bg(color):
    return "\x1b[48;2;%d;%d;%dm" % rgb(color)


def paint(background, segments, width):
    """One row on the theme's background: (color, text[, bold]) segments, padded to the width."""
    body, used = "", 0
    for color, text, *bold in segments:
        body += fg(color) + (BOLD + text + NORMAL if bold and bold[0] else text)
        used += len(text)
    return f"{bg(background)}{body}{' ' * max(width - used, 0)}{RESET}"


def swatch(theme):
    c = theme["colors"]
    dots = [(c["palette"][n], "●") for n in (1, 2, 3, 4, 5, 6)]
    return paint(c["background"], [(c["foreground"], " Aa "), *dots, (c["herdr"]["accent"], "  ▎files ")], 16)


def sample(theme, width):
    c, prompt = theme["colors"], theme["prompt"]
    p, h = c["palette"], c["herdr"]
    rows = [
        [(prompt["path"], " repo", True)],
        [(prompt["branch"], " main"), (prompt["status"], " [!]"), (prompt["path"], " ❯", True),
         (c["foreground"], " claude")],
        [(p[2], " + return redirect(next)"), (p[1], "   - return redirect('/')")],
        [(h["green"], " ● idle"), (h["yellow"], "   ● working"), (h["accent"], "   ▎focused pane"),
         (p[8], "   ignored.log")],
    ]
    return [paint(c["background"], row, width) for row in rows]


def render(themes, chosen, current):
    out = ["\x1b[2J\x1b[H" + f"{BOLD}Color theme{NORMAL}   ↑/↓ choose · Enter apply · p preview in browser · Esc close",
           ""]
    for n, theme in enumerate(themes):
        marker = "›" if n == chosen else " "
        name = f"{BOLD}{theme['name']:28}{NORMAL}" if n == chosen else f"{theme['name']:28}"
        now = "  current" if theme["id"] == current else ""
        out.append(f" {marker} {n + 1:2}. {name} {swatch(theme)}{now}")
    out += ["", *[f"   {line}" for line in sample(themes[chosen], 56)]]
    print("\n".join(out), end="", flush=True)


def main():
    themes, current = apply.load_themes(), apply.current_id()
    chosen = next((n for n, t in enumerate(themes) if t["id"] == current), 0)
    while True:
        render(themes, chosen, current)
        key = getkey()
        if key == "\x1b[A":
            chosen = (chosen - 1) % len(themes)
        elif key == "\x1b[B":
            chosen = (chosen + 1) % len(themes)
        elif key == "p":
            # the preview: every theme with its app icon, the one set now marked
            number = next((n for n, theme in enumerate(themes, 1) if theme["id"] == current), None)
            subprocess.run(["open", apply.preview_address(number)], capture_output=True)
        elif key in ("\r", "\n"):
            break
        elif key in ("\x1b", "q", "\x03"):
            return
    theme = themes[chosen]
    try:
        herdr_themed, reloaded, icon = apply.apply(theme)
    except apply.ThemeError as err:
        print("\n\n" + line("fail", t("theme.no_section", err)))
        wait_and_exit(1)
    print("\n\n" + line("ok", t("theme.picked", theme["name"])))
    note = apply.icon_line(icon)
    if note:
        print(note)
    if not herdr_themed:
        print(line("skip", t("config.theme_yours")))
    elif reloaded:
        print(line("ok", t("theme.reloaded")))
    print("      " + t("theme.ghostty_reload"))
    wait_and_exit()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
