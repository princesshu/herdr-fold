"""Tests for core/icons.py: a file's icon, the TUI's Nerd Font glyph and the Herdr app's Catppuccin Icons name, from one
table."""
import os
import sys
import unittest

from support import PACKAGE

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import icons  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
