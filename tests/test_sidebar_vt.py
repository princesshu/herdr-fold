"""Tests for the sidebar's input decoder (src/plugins/sidebar/vt.py): terminal bytes become keys, mouse events, pasted
text and focus changes, the same on every system."""
import os
import sys
import unittest

from support import SRC

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
from vt import Decoder, Focus, Key, Mouse  # noqa: E402


def decode(data):
    decoder = Decoder()
    return decoder.feed(data) + decoder.flush()


class Keys(unittest.TestCase):
    def test_arrows_and_named_keys(self):
        self.assertEqual(decode(b"\x1b[A\x1b[B\x1b[C\x1b[D"), [Key("up"), Key("down"), Key("right"), Key("left")])
        self.assertEqual(decode(b"\r\x7f\t\x1b[Z\x1b[3~\x1b[H\x1b[F"),
                         [Key("enter"), Key("backspace"), Key("tab"), Key("backtab"), Key("delete"), Key("home"),
                          Key("end")])

    def test_f9_to_f11_switch_the_views(self):
        self.assertEqual(decode(b"\x1b[20~\x1b[21~\x1b[23~"), [Key("f9"), Key("f10"), Key("f11")])

    def test_text_with_accents_and_symbols(self):
        self.assertEqual(decode("aé€".encode()), [Key("char", "a"), Key("char", "é"), Key("char", "€")])

    def test_a_lone_escape_comes_after_a_pause(self):
        decoder = Decoder()
        self.assertEqual(decoder.feed(b"\x1b"), [])
        self.assertEqual(decoder.flush(), [Key("esc")])

    def test_a_sequence_split_across_reads(self):
        decoder = Decoder()
        self.assertEqual(decoder.feed(b"\x1b["), [])
        self.assertEqual(decoder.feed(b"A"), [Key("up")])

    def test_modifiers(self):
        self.assertEqual(decode(b"\x1bx"), [Key("char", "x", alt=True)])
        self.assertEqual(decode(b"\x01"), [Key("char", "a", ctrl=True)])
        self.assertEqual(decode(b"\x1b[1;2A"), [Key("up", shift=True)])

    def test_pasted_text_is_one_event(self):
        self.assertEqual(decode(b"\x1b[200~line one\nline two\x1b[201~"), [Key("paste", "line one\nline two")])

    def test_unknown_sequences_are_dropped(self):
        self.assertEqual(decode(b"\x1b[99~x"), [Key("char", "x")])


class Mice(unittest.TestCase):
    def test_press_release_move_and_wheel(self):
        self.assertEqual(decode(b"\x1b[<0;5;3M\x1b[<0;5;3m\x1b[<35;7;4M\x1b[<64;1;1M\x1b[<65;1;1M\x1b[<2;2;2M"),
                         [Mouse("press", 4, 2, 0), Mouse("release", 4, 2, 0), Mouse("move", 6, 3, 3),
                          Mouse("wheel_up", 0, 0, 0), Mouse("wheel_down", 0, 0, 0), Mouse("press", 1, 1, 2)])

    def test_modifiers_on_a_click(self):
        self.assertEqual(decode(b"\x1b[<16;3;3M"), [Mouse("press", 2, 2, 0, ctrl=True)])


class Panes(unittest.TestCase):
    def test_the_pane_losing_and_getting_the_keys(self):
        # herdr reports it once the program asks (?1004h): a click in another pane, then back in this one
        self.assertEqual(decode(b"\x1b[O\x1b[I"), [Focus(False), Focus(True)])


if __name__ == "__main__":
    unittest.main()
