"""Tests for core/icons.py: a file's icon, the TUI's Nerd Font glyph and the Herdr app's Catppuccin Icons name, from one
table; each network's mark in both clients, from one table too."""
import os
import sys
import unittest

from support import PACKAGE

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import icons  # noqa: E402
import machines  # noqa: E402

# the Nerd Font glyphs that are WireGuard's and Cloudflare's logos (linux-wireguard, dev-cloudflare): their terms keep
# a logo out of an app without written permission, so neither client draws them
FORBIDDEN = {"wireguard": "\uf383", "cloudflare": "\ue792"}


class Glyphs(unittest.TestCase):
    def test_a_popups_close_button_has_its_own_glyph(self):
        # Codicons' close, or the plain ×: the close button of every popup herdr-fold opens in the TUI
        self.assertEqual((icons.glyphs(True)["close"], icons.glyphs(False)["close"]), ("\uea76", "×"))

    def test_the_agent_view_has_its_robot_the_rows_other_icons_stay(self):
        # Codicons' robot, or a plain ◇; Chats' sparkle and Issues' To agent arrow as the owner chose them
        self.assertEqual((icons.glyphs(True)["robot"], icons.glyphs(False)["robot"]), ("\uec20", "◇"))
        self.assertEqual([icons.glyphs(True)[name] for name in ("files", "search", "git", "issues", "ai", "agent")],
                         ["\ueaf0", "\uea6d", "\uea68", "\ueb0c", "\uec10", "\uec0f"])     # Issues: cod-issues


class FileType(unittest.TestCase):
    def test_a_files_type_goes_by_its_names_start_then_its_extension(self):
        cases = {"app.py": "python", "README.md": "readme", ".gitignore": "git", ".env.local": "env",
                 "Dockerfile": "docker", "View.TSX": "typescript-react", "pyproject.toml": "python-config",
                 "Cargo.toml": "cargo", "photo.JPEG": "image", "logo.svg": "svg", "notes": "file",
                 "data.unknown": "file", "run.ps1": "powershell", "b.bat": "batch", "x.ini": "config"}
        self.assertEqual({name: icons.file_type(name) for name in cases}, cases)

    def test_the_tui_and_the_app_tell_the_same_files_apart(self):
        """Every name the table gives a glyph also has its own Catppuccin icon, so both show the same kinds."""
        for glyph, name, exts in icons.FILE_TYPES:
            for ext in exts.split():
                with self.subTest(ext):
                    self.assertEqual((icons.icon(f"x.{ext}"), icons.file_type(f"x.{ext}")), (glyph, name))


class Networks(unittest.TestCase):
    def test_every_network_has_a_mark_in_both_clients(self):
        # a route's every network but a machine behind another (its indent says it), in the routes' order
        kinds = [kind for kind in machines.NETWORKS if kind != "through"]
        self.assertEqual(list(icons.NETWORKS), kinds)
        for kind, mark in icons.NETWORKS.items():
            with self.subTest(kind):
                self.assertLessEqual(bool(mark["logo"]) + bool(mark["icon"]), 1)            # a logo or an icon
                self.assertTrue(mark["logo"] or mark["icon"] or mark["letter"])            # the app's
                for on in (True, False):
                    glyph, color = icons.network_mark(kind, on)                            # the TUI's, one cell
                    self.assertEqual(len(glyph), 1)
                    self.assertTrue(color in ("text", "muted") or color.startswith("#"))
        self.assertIsNone(icons.network_mark("through", True))

    def test_no_mark_the_brands_terms_forbid(self):
        # WireGuard and Cloudflare: their letter, neutral, in both clients; no logo, no glyph that is their logo
        for kind, logo in FORBIDDEN.items():
            with self.subTest(kind):
                mark = icons.NETWORKS[kind]
                self.assertEqual((mark["logo"], mark["glyph"], mark["color"], mark["neutral"]),
                                 (None, None, None, True))
                self.assertNotIn(logo, icons.NERD_GLYPHS.values())
                self.assertEqual([icons.network_mark(kind, on) for on in (True, False)],
                                 [(kind[0].upper(), "muted")] * 2)

    def test_a_brand_is_its_letter_in_its_color_in_the_tui_the_others_a_plain_glyph(self):
        # no Nerd Font glyph is Tailscale's, NetBird's or ZeroTier's: their letter, Tailscale's in the text's color as
        # its one-color mark is in the app; the local network md-lan, a public address cod-globe, a tunnel cod-shield
        self.assertEqual({kind: icons.network_mark(kind, True) for kind in ("tailscale", "netbird", "zerotier")},
                         {"tailscale": ("T", "text"), "netbird": ("N", "#f68330"), "zerotier": ("Z", "#ffb441")})
        self.assertEqual([icons.network_mark(kind, True) for kind in ("local", "public", "tunnel")],
                         [("\U000f0317", "muted"), ("\ueb01", "muted"), ("\ueb53", "muted")])
        self.assertEqual([icons.network_mark(kind, False)[0] for kind in ("local", "public", "tunnel")],
                         ["⌂", "⊕", "∩"])
        self.assertEqual(icons.network_mark("tailscale", False), ("T", "text"))

    def test_the_app_draws_a_brands_own_mark_and_a_plain_icon_for_the_others(self):
        # Tailscale's one-color mark in the text's color (its light version on a dark theme), ZeroTier's in its gold,
        # NetBird's in its own colors; Lucide's network, globe and shield
        logos = {kind: (mark["logo"], mark["mono"], mark["color"]) for kind, mark in icons.NETWORKS.items()
                 if mark["logo"]}
        self.assertEqual(logos, {"tailscale": ("tailscale", True, None), "netbird": ("netbird", False, "#f68330"),
                                 "zerotier": ("zerotier", True, "#ffb441")})
        self.assertEqual({kind: mark["icon"] for kind, mark in icons.NETWORKS.items() if mark["icon"]},
                         {"local": "network", "tunnel": "shield", "public": "globe"})

    def test_the_views_glyphs_stay_as_they_were(self):
        # the networks' glyphs are new keys: every view's own glyph is the one it had
        self.assertEqual({key: icons.NERD_GLYPHS[key] for key in ("files", "search", "git", "issues", "web", "more")},
                         {"files": "\ueaf0", "search": "\uea6d", "git": "\uea68", "issues": "\ueb0c", "web": "\ueb14",
                          "more": "\ueab4"})


if __name__ == "__main__":
    unittest.main()
