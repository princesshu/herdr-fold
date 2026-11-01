"""The sidebar's colors: the terminal's own 16 by default, so it follows the terminal's theme; colors.json in the
plugin's state folder (herdr-fold's theme setter writes it) gives each role an exact color. subtext, guide and done are
herdr's own (its Spaces list's names, faint tree lines, done state); panel is its menus' background."""
import json
import os
import re

# the terminal palette's color for each role (SGR codes); a badge (the view tabs, a count, the status bar) on the
# terminal's own background, which reads on a dark and on a light one alike
PALETTE_FG = {"text": "39", "subtext": "39", "muted": "90", "guide": "90", "archived": "90", "accent": "35",
              "added": "32", "modified": "33", "deleted": "31", "done": "36", "conflict": "91", "ignored": "90",
              "badge_text": "39", "button_text": "30"}
PALETTE_BG = {"selection": "100", "hover": "100", "badge": "49", "button": "45", "input": "100", "panel": "49"}
HEX = re.compile(r"#([0-9a-fA-F]{6})")


class Theme:
    def __init__(self, colors=None):
        self.colors = {role: value for role, value in (colors or {}).items()
                       if isinstance(value, str) and HEX.fullmatch(value)}

    @classmethod
    def load(cls, state_dir):
        try:
            with open(os.path.join(state_dir, "colors.json"), encoding="utf-8") as f:
                colors = json.load(f)
        except (OSError, ValueError):
            colors = None
        return cls(colors if isinstance(colors, dict) else None)

    def color(self, role, ground):
        """The SGR code of ROLE as foreground ("fg") or background ("bg")."""
        value = self.colors.get(role)
        if value:
            r, g, b = (int(value[i:i + 2], 16) for i in (1, 3, 5))
            return f"{38 if ground == 'fg' else 48};2;{r};{g};{b}"
        if ground == "fg" and role not in PALETTE_FG and role in PALETTE_BG:    # a background as a half block's color:
            return str(int(PALETTE_BG[role]) - 10)                              # its foreground code (45 → 35)
        return (PALETTE_FG if ground == "fg" else PALETTE_BG).get(role, "39" if ground == "fg" else "49")

    def sgr(self, style):
        codes = [code for flag, code in ((style.bold, "1"), (style.underline, "4"), (style.strike, "9")) if flag]
        if style.fg:
            codes.append(self.color(style.fg, "fg"))
        if style.bg:
            codes.append(self.color(style.bg, "bg"))
        return f"\x1b[{';'.join(codes)}m" if codes else ""
