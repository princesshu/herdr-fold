"""Tests for herdr-fold Mono, the fonts tools/fonts.py builds into app/mods/herdr-fold/fonts/: its names its own, its
line 10% taller and split evenly, the symbols Claude Code and Codex print in it, its license beside it, the TUI's copy
in ~/Library/Fonts; read with a small sfnt reader, so without fontTools (a rebuild needs it, and is skipped without)."""
import importlib.util
import os
import struct
import subprocess
import sys
import unittest

from support import PACKAGE, font_names, font_tables

FONTS = os.path.join(PACKAGE, "app", "mods", "herdr-fold", "fonts")
STYLES = {"Regular": "Regular", "Bold": "Bold", "Italic": "Italic", "BoldItalic": "Bold Italic"}
SOURCE_LINE = (1020, -300)          # JetBrains Mono's ascender and descender, its line 1320 units, no gap
# what Claude Code, Codex, herdr, starship and herdr-fold's own lines print that JetBrainsMono Nerd Font lacked
SYMBOLS = ("⏺⎿✢✳✻✽⏵⏸⏹✔✘✖ℹ◻◼☐☑☒⧉⧈◐◑◒◓↳↵↻↺↯⌁⑂⇆⇡⇣⇕※▰▱⛀⛁⛝⛶⬢⬡⬝✂➤★☆ⓘ‑⁻⁽⁾₊₋₌₍₎"
           "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f")
CENTRED = "✢✳✻✽⏵⏸⏹◻◼⧉⧈◐◑◒◓※⛀⛁⛝⛶⬢⬡⬝★☆ⓘ"   # drawn round the middle ● and ✶ sit on, as tall at most
LEFT_ALONE = "✦✧⌕⇄▤⎇▣"                      # herdr-fold's plain marks: the fallback font's, as the owner fixed them


def font(style):
    with open(os.path.join(FONTS, f"herdr-fold-Mono-{style}.ttf"), "rb") as f:
        return f.read()


def cmap(tables):
    """The format 4 subtable's characters → glyph ids."""
    table = tables["cmap"]
    count = struct.unpack(">H", table[2:4])[0]
    for n in range(count):
        platform, encoding, at = struct.unpack(">HHI", table[4 + 8 * n:12 + 8 * n])
        if (platform, encoding) == (3, 1) and struct.unpack(">H", table[at:at + 2])[0] == 4:
            sub = table[at:]
            segments = struct.unpack(">H", sub[6:8])[0] // 2
            ends = struct.unpack(f">{segments}H", sub[14:14 + 2 * segments])
            starts = struct.unpack(f">{segments}H", sub[16 + 2 * segments:16 + 4 * segments])
            deltas = struct.unpack(f">{segments}h", sub[16 + 4 * segments:16 + 6 * segments])
            offsets_at = 16 + 6 * segments
            offsets = struct.unpack(f">{segments}H", sub[offsets_at:offsets_at + 2 * segments])
            found = {}
            for i in range(segments):
                for code in range(starts[i], ends[i] + 1):
                    if offsets[i] == 0:
                        found[code] = (code + deltas[i]) % 65536
                    else:
                        where = offsets_at + 2 * i + offsets[i] + 2 * (code - starts[i])
                        glyph = struct.unpack(">H", sub[where:where + 2])[0]
                        found[code] = (glyph + deltas[i]) % 65536 if glyph else 0
            return found
    raise AssertionError("no Windows Unicode format 4 cmap")


def advance(tables, glyph):
    metrics = struct.unpack(">H", tables["hhea"][34:36])[0]
    return struct.unpack(">H", tables["hmtx"][4 * min(glyph, metrics - 1):4 * min(glyph, metrics - 1) + 2])[0]


def box(tables, glyph):
    """A glyph's xMin, yMin, xMax, yMax, from its glyf header."""
    long_loca = struct.unpack(">h", tables["head"][50:52])[0] == 1
    loca = tables["loca"]
    at = (struct.unpack(">I", loca[4 * glyph:4 * glyph + 4])[0] if long_loca
          else 2 * struct.unpack(">H", loca[2 * glyph:2 * glyph + 2])[0])
    return struct.unpack(">4h", tables["glyf"][at + 2:at + 10])


class Names(unittest.TestCase):
    """The SIL Open Font License keeps a Modified Version from its Original's names."""

    def test_every_style_is_herdr_fold_mono(self):
        for style, words in STYLES.items():
            names = font_names(font(style))
            for platform in (1, 3):
                self.assertEqual(names[(platform, 1)], "herdr-fold Mono", style)
                self.assertEqual(names[(platform, 2)], words, style)
                self.assertEqual(names[(platform, 4)], f"herdr-fold Mono {words}", style)
                self.assertEqual(names[(platform, 6)], f"herdrfoldMono-{style}", style)
                self.assertIn(f"herdrfoldMono-{style}", names[(platform, 3)], style)

    def test_no_name_is_the_originals(self):
        for style in STYLES:
            names = font_names(font(style))
            left = [key for key, text in names.items() if key[1] in (1, 3, 4, 6, 16, 17, 21, 22)
                    and ("JetBrains" in text or "Nerd" in text or " NF" in text)]
            self.assertEqual(left, [], style)

    def test_the_originals_copyright_and_license_stay(self):
        names = font_names(font("Regular"))
        self.assertTrue(names[(3, 0)].startswith("Copyright 2020 The JetBrains Mono Project Authors"))
        self.assertIn("SIL Open Font License, Version 1.1", names[(3, 13)])


class Line(unittest.TestCase):
    def test_the_line_is_ten_percent_taller_split_evenly(self):
        above, below = SOURCE_LINE
        more = round((above - below) * 0.10 / 2)
        for style in STYLES:
            tables = font_tables(font(style))
            ascender, descender, gap = struct.unpack(">hhh", tables["hhea"][4:10])
            self.assertEqual((ascender, descender, gap), (above + more, below - more, 0), style)
            os2 = tables["OS/2"]
            selection = struct.unpack(">H", os2[62:64])[0]
            self.assertEqual(struct.unpack(">hhh", os2[68:74]), (ascender, descender, 0), style)
            self.assertEqual(struct.unpack(">HH", os2[74:78]), (ascender, -descender), style)
            self.assertTrue(selection & 1 << 7, f"{style}: USE_TYPO_METRICS")


class Symbols(unittest.TestCase):
    def test_claude_codes_and_codexs_symbols_are_in_every_style_one_cell_wide(self):
        for style in STYLES:
            tables = font_tables(font(style))
            chars = cmap(tables)
            missing = [c for c in SYMBOLS if not chars.get(ord(c))]
            self.assertEqual(missing, [], style)
            self.assertEqual([c for c in LEFT_ALONE if chars.get(ord(c))], [], style)
            wide = [c for c in SYMBOLS if advance(tables, chars[ord(c)]) != advance(tables, chars[ord("x")])]
            self.assertEqual(wide, [], style)

    def test_the_bullet_and_the_corner_are_the_fonts_own(self):
        # ⏺ is ●, as Claude Code prints off a Mac; ⎿ is └, the box drawing's line
        for style in STYLES:
            tables = font_tables(font(style))
            chars = cmap(tables)
            for new, own in (("⏺", "●"), ("⎿", "└")):
                self.assertEqual(box(tables, chars[ord(new)]), box(tables, chars[ord(own)]), f"{style}: {new}")

    def test_herdrs_folds_are_the_sidebars_chevrons(self):
        # herdr's ▾ ▸ before a machine in its Spaces list: the glyphs of the sidebar's open and shut chevrons
        for style in STYLES:
            chars = cmap(font_tables(font(style)))
            self.assertEqual([chars[ord("▾")], chars[ord("▸")]], [chars[0xEAB4], chars[0xEAB6]], style)

    def test_the_drawn_ones_sit_where_the_fonts_symbols_do(self):
        tables = font_tables(font("Regular"))
        chars = cmap(tables)
        x0, y0, x1, y1 = box(tables, chars[ord("●")])
        middle, low, high = ((x0 + x1) / 2, (y0 + y1) / 2), y0, y1         # and no taller than ●
        for c in CENTRED:
            gx0, gy0, gx1, gy1 = box(tables, chars[ord(c)])
            self.assertLessEqual(abs((gx0 + gx1) / 2 - middle[0]), 10, c)
            self.assertLessEqual(abs((gy0 + gy1) / 2 - middle[1]), 10, c)
            self.assertTrue(low - 1 <= gy0 and gy1 <= high + 1, c)


class Shipped(unittest.TestCase):
    def test_its_license_is_beside_it(self):
        with open(os.path.join(FONTS, "OFL.txt"), encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("Copyright 2020 The JetBrains Mono Project Authors"))
        self.assertIn("SIL OPEN FONT LICENSE Version 1.1", text)
        self.assertEqual(sorted(os.listdir(FONTS)),
                         ["OFL.txt"] + sorted(f"herdr-fold-Mono-{style}.ttf" for style in STYLES))

    def test_the_tui_gets_the_fonts_and_their_license_in_its_fonts_folder(self):
        with open(os.path.join(PACKAGE, "files.txt"), encoding="utf-8") as f:
            rows = [[cell.strip() for cell in line.split("|")] for line in f
                    if "|" in line and not line.lstrip().startswith("#")]
        fonts = [row for row in rows if row[0].startswith("app/mods/herdr-fold/fonts/")]
        self.assertEqual(fonts, [["app/mods/herdr-fold/fonts/*.ttf", "Library/Fonts/", "tui"],
                                 ["app/mods/herdr-fold/fonts/OFL.txt", "Library/Fonts/herdr-fold-Mono-OFL.txt", "tui"]])

    def test_ghostty_and_the_app_layout_use_it(self):
        with open(os.path.join(PACKAGE, "config", "ghostty", "config"), encoding="utf-8") as f:
            ghostty = f.read().splitlines()
        self.assertIn("font-family = herdr-fold Mono", ghostty)
        self.assertEqual([line for line in ghostty if line.startswith("adjust-cell-height")], [])   # the font has it
        with open(os.path.join(PACKAGE, "app", "layouts", "herdr-fold.json"), encoding="utf-8") as f:
            self.assertIn('"font": "herdr-fold Mono"', f.read())


@unittest.skipUnless(importlib.util.find_spec("fontTools")
                     and os.path.isfile(os.path.expanduser("~/.cache/herdr-fold/fonts/JetBrainsMono-3.5.1.tar.xz")),
                     "a rebuild needs fontTools and Nerd Fonts' release in the cache (CONTRIBUTING.md, The font)")
class Rebuild(unittest.TestCase):
    def test_the_committed_fonts_are_what_the_script_builds(self):
        done = subprocess.run([sys.executable, os.path.join(PACKAGE, "tools", "fonts.py"), "--check"],
                              capture_output=True, text=True, timeout=300)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
