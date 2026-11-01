"""Tests for the sidebar's terminal on Windows (src/plugins/sidebar/keys_windows.py) with made-up console records: the
same events as on macOS and Linux, and 80×24 when no size is reported. The ctypes layer runs only on Windows."""
import os
import shutil
import sys
import unittest
from unittest import mock

from support import SRC

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import keys_windows  # noqa: E402
from vt import Decoder, Focus, Key, Mouse, Resize  # noqa: E402


def events(*records):
    decoder = Decoder()
    return keys_windows.events_from_records(list(records), decoder) + decoder.flush()


class Records(unittest.TestCase):
    def test_characters_go_through_the_same_decoder(self):
        self.assertEqual(events(*[("key", c) for c in "\x1b[A"]), [Key("up")])
        self.assertEqual(events(*[("key", c) for c in "\x1b[<0;3;2M"]), [Mouse("press", 2, 1, 0)])
        self.assertEqual(events(*[("key", c) for c in "\x1b[O"]), [Focus(False)])

    def test_focus_reporting_is_switched_on_and_back_off(self):
        self.assertIn("\x1b[?1004h", keys_windows.ON)
        self.assertIn("\x1b[?1004l", keys_windows.OFF)

    def test_a_character_outside_the_basic_plane_arrives_in_two_halves(self):
        self.assertEqual(events(("key", "\ud83d"), ("key", "\ude00")), [Key("char", "😀")])

    def test_a_size_record_is_a_resize(self):
        self.assertEqual(events(("size", 80, 24)), [Resize(80, 24)])

    def test_the_module_loads_on_any_system(self):
        self.assertTrue(hasattr(keys_windows, "WindowsTerminal"))

    def test_a_window_without_a_size_is_80_by_24(self):
        with mock.patch.object(shutil, "get_terminal_size", return_value=os.terminal_size((0, 0))):
            self.assertEqual(keys_windows.WindowsTerminal().size(), (80, 24))


if __name__ == "__main__":
    unittest.main()
