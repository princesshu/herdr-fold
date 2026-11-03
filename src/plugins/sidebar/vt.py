"""The sidebar's input decoder: bytes from the terminal (or, on Windows, the characters of its input records) become
keys, mouse events, pasted text and the pane getting or losing the keys. Both systems feed it, so everything above it
is the same everywhere."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Key:
    name: str
    char: str = ""
    shift: bool = False
    alt: bool = False
    ctrl: bool = False


@dataclass(frozen=True)
class Mouse:
    kind: str                 # press, release, move, wheel_up, wheel_down
    x: int                    # column, from 0
    y: int                    # row, from 0
    button: int = 0           # 0 left, 1 middle, 2 right, 3 none (a move with no button down)
    shift: bool = False
    alt: bool = False
    ctrl: bool = False


@dataclass(frozen=True)
class Resize:
    width: int
    height: int


@dataclass(frozen=True)
class Focus:
    gained: bool              # the pane got the keys back; False: a click in another pane took them


CSI_KEYS = {"A": "up", "B": "down", "C": "right", "D": "left", "H": "home", "F": "end", "Z": "backtab"}
TILDE_KEYS = {"1": "home", "3": "delete", "4": "end", "5": "pageup", "6": "pagedown", "7": "home", "8": "end",
              "19": "f8", "20": "f9", "21": "f10", "23": "f11", "24": "f12"}
CSI = re.compile(rb"\x1b\[([<?]?)([\d;]*)([A-Za-z~])")
PASTE_START, PASTE_END = b"\x1b[200~", b"\x1b[201~"
LONGEST = 32                  # an escape sequence longer than this is not one: its Esc is dropped


class Decoder:
    def __init__(self):
        self.pending = b""

    def feed(self, data):
        self.pending += data
        events = []
        while self.pending:
            event, used = self.next(self.pending)
            if used == 0:
                break                                  # an unfinished sequence: wait for more bytes
            self.pending = self.pending[used:]
            if event is not None:
                events.append(event)
        return events

    def flush(self):
        """After a pause: a lone Esc is the Esc key; any other unfinished bytes are dropped."""
        events = [Key("esc")] if self.pending == b"\x1b" else []
        self.pending = b""
        return events

    def next(self, data):
        if data.startswith(PASTE_START):
            end = data.find(PASTE_END)
            if end < 0:
                return None, 0
            return Key("paste", data[len(PASTE_START):end].decode("utf-8", "replace")), end + len(PASTE_END)
        if data[:1] != b"\x1b":
            return self.text(data)
        if len(data) == 1:
            return None, 0
        if data[1:2] == b"[":
            m = CSI.match(data)
            if not m:
                return (None, 0) if len(data) < LONGEST else (None, 1)
            return self.csi(*m.groups()), m.end()
        key, used = self.text(data[1:])
        if used == 0:
            return None, 0
        return Key(key.name, key.char, alt=True), used + 1

    @staticmethod
    def text(data):
        byte = data[0]
        if byte in (0x0d, 0x0a):
            return Key("enter"), 1
        if byte == 0x09:
            return Key("tab"), 1
        if byte in (0x7f, 0x08):
            return Key("backspace"), 1
        if byte < 0x20:
            return Key("char", chr(byte + 0x60), ctrl=True), 1
        size = 1 if byte < 0x80 else 2 if byte < 0xe0 else 3 if byte < 0xf0 else 4
        if len(data) < size:
            return None, 0
        return Key("char", data[:size].decode("utf-8", "replace")), size

    @staticmethod
    def csi(private, params, final):
        numbers = [int(p) if p else 0 for p in params.decode().split(";")] if params else []
        if private == b"<" and final in b"Mm" and len(numbers) == 3:
            code, x, y = numbers
            mods = dict(shift=bool(code & 4), alt=bool(code & 8), ctrl=bool(code & 16))
            if code & 64:
                return Mouse("wheel_down" if code & 1 else "wheel_up", x - 1, y - 1, 0, **mods)
            kind = "move" if code & 32 else ("press" if final == b"M" else "release")
            return Mouse(kind, x - 1, y - 1, code & 3, **mods)
        if not private and not params and final in (b"I", b"O"):        # focus reporting (?1004h)
            return Focus(final == b"I")
        mod = numbers[1] - 1 if len(numbers) > 1 else 0
        mods = dict(shift=bool(mod & 1), alt=bool(mod & 2), ctrl=bool(mod & 4))
        if final == b"~":
            name = TILDE_KEYS.get(str(numbers[0])) if numbers else None
            return Key(name, **mods) if name else None
        name = CSI_KEYS.get(final.decode())
        return Key(name, **mods) if name else None
