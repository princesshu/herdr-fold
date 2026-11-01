"""The sidebar's terminal on Windows: the console in VT mode, so input arrives as the same escape sequences as on macOS
and Linux, through vt.py's decoder. ctypes loads only when a WindowsTerminal is made, so this module imports on any
system (the tests use events_from_records)."""
import shutil
import sys

from vt import PASTE_START, Decoder, Resize

ON = "\x1b[?1049h\x1b[?25l\x1b[?1000h\x1b[?1003h\x1b[?1006h\x1b[?2004h\x1b[?1004h"
OFF = "\x1b[?1004l\x1b[?2004l\x1b[?1006l\x1b[?1003l\x1b[?1000l\x1b[0 q\x1b[?25h\x1b[?1049l"
ESC_WAIT = 0.05

# console modes (Win32 SetConsoleMode)
ENABLE_PROCESSED_INPUT, ENABLE_LINE_INPUT, ENABLE_ECHO_INPUT = 0x1, 0x2, 0x4
ENABLE_WINDOW_INPUT, ENABLE_QUICK_EDIT_MODE, ENABLE_EXTENDED_FLAGS = 0x8, 0x40, 0x80
ENABLE_VIRTUAL_TERMINAL_INPUT = 0x200
ENABLE_PROCESSED_OUTPUT, ENABLE_VIRTUAL_TERMINAL_PROCESSING, DISABLE_NEWLINE_AUTO_RETURN = 0x1, 0x4, 0x8
KEY_EVENT, WINDOW_BUFFER_SIZE_EVENT = 0x1, 0x4
STD_INPUT_HANDLE, STD_OUTPUT_HANDLE = -10, -11
WAIT_OBJECT_0 = 0


def events_from_records(records, decoder):
    """Events from the console's records: ("key", character) or ("size", width, height). The characters go through
    the decoder; a character outside the basic plane arrives as two UTF-16 halves and is put back together."""
    events, chars = [], []

    def flush_chars():
        if chars:
            text = "".join(chars).encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")
            events.extend(decoder.feed(text.encode("utf-8")))
            chars.clear()

    for record in records:
        if record[0] == "key":
            chars.append(record[1])
        elif record[0] == "size":
            flush_chars()
            events.append(Resize(record[1], record[2]))
    flush_chars()
    return events


def _console():
    """The Win32 calls and records the terminal needs (ctypes, Windows only)."""
    import ctypes

    class Coord(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class Char(ctypes.Union):
        _fields_ = [("UnicodeChar", ctypes.c_ushort), ("AsciiChar", ctypes.c_char)]

    class KeyEventRecord(ctypes.Structure):
        _fields_ = [("bKeyDown", ctypes.c_int), ("wRepeatCount", ctypes.c_ushort), ("wVirtualKeyCode", ctypes.c_ushort),
                    ("wVirtualScanCode", ctypes.c_ushort), ("uChar", Char), ("dwControlKeyState", ctypes.c_uint32)]

    class MouseEventRecord(ctypes.Structure):
        _fields_ = [("dwMousePosition", Coord), ("dwButtonState", ctypes.c_uint32),
                    ("dwControlKeyState", ctypes.c_uint32), ("dwEventFlags", ctypes.c_uint32)]

    class SizeRecord(ctypes.Structure):
        _fields_ = [("dwSize", Coord)]

    class Event(ctypes.Union):
        _fields_ = [("KeyEvent", KeyEventRecord), ("MouseEvent", MouseEventRecord),
                    ("WindowBufferSizeEvent", SizeRecord)]

    class InputRecord(ctypes.Structure):
        _fields_ = [("EventType", ctypes.c_ushort), ("Event", Event)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetStdHandle.restype = ctypes.c_void_p
    kernel32.CreateEventW.restype = ctypes.c_void_p
    return ctypes, kernel32, InputRecord


class WindowsTerminal:
    def __init__(self, stdout=None):
        self.out = stdout or sys.stdout
        self.decoder = Decoder()
        self.ctypes = self.k32 = self.InputRecord = None
        self.hin = self.hout = self.event = None
        self.saved_in = self.saved_out = None

    def __enter__(self):
        self.ctypes, self.k32, self.InputRecord = _console()
        c = self.ctypes
        self.hin = c.c_void_p(self.k32.GetStdHandle(STD_INPUT_HANDLE))
        self.hout = c.c_void_p(self.k32.GetStdHandle(STD_OUTPUT_HANDLE))
        mode_in, mode_out = c.c_uint32(), c.c_uint32()
        self.k32.GetConsoleMode(self.hin, c.byref(mode_in))
        self.k32.GetConsoleMode(self.hout, c.byref(mode_out))
        self.saved_in, self.saved_out = mode_in.value, mode_out.value
        new_in = (self.saved_in | ENABLE_VIRTUAL_TERMINAL_INPUT | ENABLE_WINDOW_INPUT | ENABLE_EXTENDED_FLAGS) & ~(
            ENABLE_LINE_INPUT | ENABLE_ECHO_INPUT | ENABLE_PROCESSED_INPUT | ENABLE_QUICK_EDIT_MODE)
        self.k32.SetConsoleMode(self.hin, new_in)
        self.k32.SetConsoleMode(self.hout, self.saved_out | ENABLE_PROCESSED_OUTPUT |
                                ENABLE_VIRTUAL_TERMINAL_PROCESSING | DISABLE_NEWLINE_AUTO_RETURN)
        self.event = c.c_void_p(self.k32.CreateEventW(None, True, False, None))
        self.write(ON)
        self.flush()
        return self

    def __exit__(self, *exc):
        self.write(OFF)
        self.flush()
        self.k32.SetConsoleMode(self.hin, self.saved_in)
        self.k32.SetConsoleMode(self.hout, self.saved_out)
        self.k32.CloseHandle(self.event)

    def wake(self):
        """Return a waiting read() at once (safe from any thread)."""
        if self.event is not None:
            self.k32.SetEvent(self.event)

    def size(self):
        """Columns and lines; 80×24 for a window that reports none (Python 3.9 passes a 0×0 size on)."""
        columns, lines = shutil.get_terminal_size((80, 24))
        return columns or 80, lines or 24

    def _wait(self, timeout):
        handles = (self.ctypes.c_void_p * 2)(self.hin, self.event)
        return self.k32.WaitForMultipleObjects(2, handles, False, int(timeout * 1000))

    def _records(self):
        c = self.ctypes
        records, count = (self.InputRecord * 256)(), c.c_uint32()
        if not self.k32.ReadConsoleInputW(self.hin, records, 256, c.byref(count)):
            return []
        items = []
        for record in records[:count.value]:
            if record.EventType == KEY_EVENT and record.Event.KeyEvent.bKeyDown:
                code = record.Event.KeyEvent.uChar.UnicodeChar
                if code:
                    items += [("key", chr(code))] * max(1, record.Event.KeyEvent.wRepeatCount)
            elif record.EventType == WINDOW_BUFFER_SIZE_EVENT:
                items.append(("size", *self.size()))
        return items

    def read(self, timeout):
        """The events that arrive within TIMEOUT seconds (fewer, or none, if woken)."""
        result = self._wait(timeout)
        if result == WAIT_OBJECT_0 + 1:
            self.k32.ResetEvent(self.event)
            return []
        if result != WAIT_OBJECT_0:
            return []
        events = events_from_records(self._records(), self.decoder)
        if self.decoder.pending and not self.decoder.pending.startswith(PASTE_START):
            if self._wait(ESC_WAIT) == WAIT_OBJECT_0:
                events += events_from_records(self._records(), self.decoder)
            if self.decoder.pending:
                events += self.decoder.flush()
        return events

    def write(self, text):
        self.out.write(text)

    def flush(self):
        self.out.flush()
