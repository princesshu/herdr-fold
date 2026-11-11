"""The plugin's state files, its owner's only whatever the umask (every conversation's folder and title, a private
repository's issues): each written whole beside it, then put in place, a planted link never followed; one that every
tab's sidebar and the app's helper change is changed by one writer at a time (update())."""
import contextlib
import json
import os
import tempfile
import threading

HELD = threading.local()      # the files this thread holds the lock of: a change inside a change locks once


def folder():
    """herdr-fold's own state folder: the version the installer put in, the update check, the app's chats."""
    return os.path.join(os.path.expanduser("~"), ".local", "state", "herdr-fold")


def write(path, value, **dump):
    """VALUE as JSON in PATH (DUMP: json.dump's own options); OSError when it cannot be written."""
    folder = os.path.dirname(path)
    os.makedirs(folder, mode=0o700, exist_ok=True)
    if os.name != "nt":
        os.chmod(folder, 0o700)                 # herdr makes a plugin's state folder open to everyone
    fd, temporary = tempfile.mkstemp(dir=folder, prefix=f".{os.path.basename(path)}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, **dump)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def read(path):
    """The JSON object in PATH; {} for none, or what cannot be read as one."""
    try:
        with open(path, encoding="utf-8") as f:
            value = json.load(f)
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


@contextlib.contextmanager
def locked(path):
    """PATH held by this thread alone among every process's, through the lock file PATH.lock beside it (the file itself
    is put in place anew by each write); held already by this thread, held on. OSError when it cannot be locked."""
    held = HELD.__dict__.setdefault("paths", set())
    if path in held:
        yield
        return
    folder = os.path.dirname(path)
    os.makedirs(folder, mode=0o700, exist_ok=True)
    fd = os.open(path + ".lock", os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0),
                 0o600)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)       # its first byte, the same for every writer
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
        held.add(path)
        try:
            yield
        finally:
            held.discard(path)
            if os.name == "nt":
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(fd)                                    # flock's lock goes with it


def update(path, change, **dump):
    """PATH's JSON object changed by CHANGE (given what it holds now, read(); its answer written whole) inside locked():
    the answer. OSError when it cannot be locked or written."""
    with locked(path):
        value = change(read(path))
        write(path, value, **dump)
    return value
