"""Tests for core/icons.py: a file's icon, the TUI's Nerd Font glyph and the Herdr app's Catppuccin Icons name, from one
table."""
import os
import sys
import unittest

from support import PACKAGE

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import icons  # noqa: E402


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
