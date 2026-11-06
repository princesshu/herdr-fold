# Generated from core/fileops.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""The sidebar's file operations: a new file or folder, renaming, and deleting, always into the system's Trash. Each
stays inside the root (a symbolic link leading out too), never overwrites, and never touches the AI tools' folders
(PROTECTED) nor moves a folder holding one. Copying a path uses the clipboard program, else the caller's OSC 52."""
import datetime
import json
import os
import shutil
import subprocess
import sys
import urllib.parse

PROTECTED = (".claude", ".codex", os.path.join(".local", "state", "herdr"))
# SHFileOperationW: undo (the Recycle Bin), no questions, no progress, no error boxes — but a warning, which can be
# refused, before an item that cannot be recycled (a network drive, a too large one) would be deleted for good
RECYCLE_FLAGS = 0x40 | 0x10 | 0x4 | 0x400 | 0x4000


class Refused(OSError):
    """An operation the sidebar does not do; its message is the line the app shows."""


def unique(name, taken):
    """NAME, or "NAME 2", "NAME 3"… (before its extension) while TAKEN(candidate) says it is in use."""
    base, ext = os.path.splitext(name)
    candidate, n = name, 2
    while taken(candidate):
        candidate, n = f"{base} {n}{ext}", n + 1
    return candidate


def windows_recycle(path):
    """Move PATH to the Windows Recycle Bin (SHFileOperationW with undo)."""
    import ctypes

    class FileOp(ctypes.Structure):
        _fields_ = [("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint), ("pFrom", ctypes.c_wchar_p),
                    ("pTo", ctypes.c_wchar_p), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", ctypes.c_int),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", ctypes.c_wchar_p)]

    fo_delete = 3
    op = FileOp(None, fo_delete, os.path.abspath(path) + "\0", None, RECYCLE_FLAGS, 0, None, None)
    if ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) or op.fAnyOperationsAborted:
        raise Refused(f"could not move to the Recycle Bin: {path}")


def mac_trash(path):
    """Move PATH to the macOS Trash the way Finder does (NSFileManager's trashItemAtURL: a free name when one is taken,
    Put Back works, no Full Disk Access needed)."""
    import ctypes
    import ctypes.util

    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
    ctypes.cdll.LoadLibrary(ctypes.util.find_library("Foundation"))
    for function in (objc.objc_getClass, objc.sel_registerName):
        function.restype, function.argtypes = ctypes.c_void_p, [ctypes.c_char_p]
    address = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value

    def send(returns, receiver, selector, *args):
        """One Objective-C message, through a function pointer of its own (safe on any thread)."""
        kinds = [ctypes.c_char_p if isinstance(arg, bytes) else ctypes.c_void_p for arg in args]
        call = ctypes.CFUNCTYPE(returns, ctypes.c_void_p, ctypes.c_void_p, *kinds)(address)
        return call(receiver, objc.sel_registerName(selector), *args)

    def new(name):
        return send(ctypes.c_void_p, objc.objc_getClass(name), b"alloc")

    pool = send(ctypes.c_void_p, new(b"NSAutoreleasePool"), b"init")
    try:
        text = send(ctypes.c_void_p, objc.objc_getClass(b"NSString"), b"stringWithUTF8String:",
                    os.fsencode(os.path.abspath(path)))
        url = send(ctypes.c_void_p, objc.objc_getClass(b"NSURL"), b"fileURLWithPath:", text)
        manager = send(ctypes.c_void_p, objc.objc_getClass(b"NSFileManager"), b"defaultManager")
        error = ctypes.c_void_p()
        if not send(ctypes.c_bool, manager, b"trashItemAtURL:resultingItemURL:error:", url, None,
                    ctypes.addressof(error)):
            reason = b""
            if error.value:
                described = send(ctypes.c_void_p, error.value, b"localizedDescription")
                reason = send(ctypes.c_char_p, described, b"UTF8String") or b""
            raise Refused(reason.decode("utf-8", "replace") or f"could not move to the Trash: {path}")
    finally:
        send(None, pool, b"drain")


def system_clipboard(system):
    """A function that puts text on the clipboard and says whether it could."""
    if system == "darwin":
        argv, encoding = ["pbcopy"], "utf-8"
    elif system == "win32":
        argv, encoding = ["clip"], "utf-16"
    else:
        tool = shutil.which("wl-copy") or shutil.which("xclip")
        argv = None if not tool else [tool] if tool.endswith("wl-copy") else [tool, "-selection", "clipboard"]
        encoding = "utf-8"

    def copy(text):
        if not argv:
            return False
        try:
            return subprocess.run(argv, input=text.encode(encoding), env=dict(os.environ, LC_CTYPE="UTF-8"),
                                  capture_output=True, timeout=5).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False
    return copy


class Ops:
    def __init__(self, root, home=None, system=sys.platform, clipboard=None, recycle=None):
        self.root = os.path.realpath(root)
        self.home = home or os.path.expanduser("~")
        self.guarded = [os.path.join(os.path.realpath(self.home), rel) for rel in PROTECTED]
        self.system = system
        self.clipboard = clipboard or system_clipboard(system)
        self.recycle = recycle or (mac_trash if system == "darwin" else windows_recycle)   # the system's own Trash

    def check(self, path):
        """PATH's real place, if it may be touched: inside the root, outside the AI tools' folders."""
        real = os.path.realpath(path)
        if real != self.root and not real.startswith(self.root + os.sep):
            raise Refused(f"outside {self.root}: {path}")
        if any(real == guard or real.startswith(guard + os.sep) for guard in self.guarded):
            raise Refused(f"an AI tool's folder: {path}")
        return real

    def target(self, folder, name):
        if not name or name in (".", "..") or "/" in name or os.sep in name or "\0" in name:
            raise Refused(f"not a file name: {name!r}")
        self.check(folder)
        path = os.path.join(folder, name)
        if os.path.lexists(path):
            raise Refused(f"already there: {name}")
        self.check(path)
        return path

    def new_file(self, folder, name):
        path = self.target(folder, name)
        with open(path, "x"):
            pass
        return path

    def new_folder(self, folder, name):
        path = self.target(folder, name)
        os.mkdir(path)
        return path

    def movable(self, path):
        real = self.check(path)
        if real == self.root:
            raise Refused("the root folder itself")
        if any(guard.startswith(real + os.sep) for guard in self.guarded):
            raise Refused(f"it holds an AI tool's folder: {path}")
        if not os.path.lexists(path):
            raise Refused(f"not there: {path}")

    def rename(self, path, new_name):
        self.movable(path)
        target = self.target(os.path.dirname(path), new_name)
        os.rename(path, target)
        return target

    def trash(self, path):
        """Move PATH to the system's Trash; returns where it went."""
        self.movable(path)
        name = os.path.basename(os.path.normpath(path))
        if self.system in ("darwin", "win32"):
            self.recycle(path)
            return "Trash" if self.system == "darwin" else "Recycle Bin"
        if self.system.startswith("linux"):
            return self.freedesktop(path, name)
        raise Refused(f"no Trash on this system: {self.system}")

    def freedesktop(self, path, name):
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(self.home, ".local", "share")
        files, info = os.path.join(base, "Trash", "files"), os.path.join(base, "Trash", "info")
        os.makedirs(files, exist_ok=True)
        os.makedirs(info, exist_ok=True)
        stem = unique(name, lambda c: os.path.lexists(os.path.join(files, c))
                      or os.path.lexists(os.path.join(info, c + ".trashinfo")))
        record = (f"[Trash Info]\nPath={urllib.parse.quote(os.path.abspath(path))}\n"
                  f"DeletionDate={datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}\n")
        with open(os.path.join(info, stem + ".trashinfo"), "x", encoding="utf-8") as f:
            f.write(record)
        dest = os.path.join(files, stem)
        shutil.move(path, dest)
        return dest

    def copy_path(self, path):
        """Put PATH on the clipboard; False when there is no clipboard program (then OSC 52 is the caller's)."""
        return self.clipboard(path)


def main(argv):
    """herdr-fold's Herdr app mod runs this on the space's machine, paths from ROOT: trash ROOT PATH, new-file or
    new-folder ROOT FOLDER NAME, rename ROOT PATH NAME; and on its own, copy TEXT onto its clipboard. JSON: what it
    made or where it went, else why not."""
    command, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    if {"trash": 2, "new-file": 3, "new-folder": 3, "rename": 3, "copy": 1}.get(command) != len(args):
        print("usage: fileops.py trash ROOT PATH | new-file|new-folder ROOT FOLDER NAME | rename ROOT PATH NAME"
              " | copy TEXT", file=sys.stderr)
        return 2
    if command == "copy":
        print(json.dumps({"ok": system_clipboard(sys.platform)(args[0])}))
        return 0
    ops, at = Ops(args[0]), os.path.join(args[0], args[1])
    try:
        if command == "trash":
            answer = {"ok": True, "where": ops.trash(at)}
        else:
            made = {"new-file": ops.new_file, "new-folder": ops.new_folder, "rename": ops.rename}[command](at, args[2])
            answer = {"ok": True, "path": os.path.relpath(os.path.realpath(made), ops.root).replace(os.sep, "/")}
    except OSError as err:                              # Refused too: the line to show
        answer = {"ok": False, "advice": str(err)}
    print(json.dumps(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
