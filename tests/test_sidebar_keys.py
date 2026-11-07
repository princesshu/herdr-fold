"""Tests for the sidebar's keys (src/plugins/sidebar/): vt.py's decoder makes terminal bytes keys, mouse events, pasted
text and focus changes on every system; the terminal of macOS and Linux (keys_unix.py) in a real pty, of Windows
(keys_windows.py) with made-up console records (its ctypes layer runs only there); 80×24 when no size is reported."""
import os
import pty
import select
import shutil
import sys
import time
import unittest
from unittest import mock

from support import SRC, end_child

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import keys_windows  # noqa: E402
from vt import Decoder, Focus, Key, Mouse, Resize  # noqa: E402


def decode(data):
    decoder = Decoder()
    return decoder.feed(data) + decoder.flush()


class Keys(unittest.TestCase):
    def test_arrows_and_named_keys(self):
        self.assertEqual(decode(b"\x1b[A\x1b[B\x1b[C\x1b[D"), [Key("up"), Key("down"), Key("right"), Key("left")])
        self.assertEqual(decode(b"\r\x7f\t\x1b[Z\x1b[3~\x1b[H\x1b[F"),
                         [Key("enter"), Key("backspace"), Key("tab"), Key("backtab"), Key("delete"), Key("home"),
                          Key("end")])

    def test_f8_selects_a_fields_text_and_f9_to_f12_switch_the_views(self):
        # what herdr sends for the sidebar's actions: F8 for Cmd + A, F9 to F12 for the views
        self.assertEqual(decode(b"\x1b[19~\x1b[20~\x1b[21~\x1b[23~\x1b[24~"),
                         [Key("f8"), Key("f9"), Key("f10"), Key("f11"), Key("f12")])

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


PROGRAM = r"""
import sys, threading, time
sys.path.insert(0, %r)
from keys_unix import UnixTerminal
with UnixTerminal() as term:
    print("SIZE", term.size(), flush=True)
    threading.Timer(0.3, term.wake).start()
    started = time.time()
    term.read(5)
    print("WOKE %%.1f" %% (time.time() - started), flush=True)
    seen = []
    while not any(getattr(e, "char", "") == "q" for e in seen):
        seen += term.read(1)
    print("EVENTS", seen, flush=True)
"""


def run(keys):
    """The program in a pty; KEYS are typed once it is waiting. Returns everything it wrote."""
    pid, fd = pty.fork()
    if pid == 0:
        os.execv(sys.executable, [sys.executable, "-c", PROGRAM % os.path.join(SRC, "plugins", "sidebar")])
    out, deadline, typed = b"", time.monotonic() + 10, False
    while time.monotonic() < deadline:
        if not typed and b"WOKE" in out:            # in its key loop: typed sooner, the wake's read takes them
            os.write(fd, keys)
            typed = True
        if select.select([fd], [], [], 0.2)[0]:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
    end_child(pid, fd)
    return out.decode("utf-8", "replace")


class Terminal(unittest.TestCase):
    def test_modes_are_switched_on_and_back_off(self):
        out = run(b"q")
        for on in ("\x1b[?1049h", "\x1b[?1006h", "\x1b[?2004h", "\x1b[?1004h"):
            self.assertIn(on, out)
            self.assertIn(on[:-1] + "l", out[out.index(on):])
        self.assertIn("\x1b[0 q\x1b[?25h", out)                          # the terminal's own cursor back as it was

    def test_keys_arrive_as_events(self):
        self.assertIn("Key(name='up'", run(b"\x1b[Aq"))

    def test_another_thread_wakes_the_loop(self):
        out = run(b"q")
        self.assertLess(float(out.split("WOKE ")[1].split()[0]), 1.0)

    def test_a_window_without_a_size_is_80_by_24(self):
        self.assertIn("SIZE (80, 24)", run(b"q"))             # pty.fork makes a 0×0 one


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
