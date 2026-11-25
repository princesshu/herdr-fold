# Generated from core/statefile.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""The plugin's state files, its owner's only whatever the umask: each written whole beside it, then put in place, a
planted link never followed; one many change, by one writer at a time (update()). For the app's drafts, which it writes
itself, in JSON: statefile.py folder NAME, remove NAME FILE, sweep NAME."""
import contextlib
import json
import os
import sys
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


def private(name):
    """The state folder's folder NAME, made its owner's only (the state folder too), as the app's drafts need."""
    path = os.path.join(folder(), name)
    os.makedirs(path, mode=0o700, exist_ok=True)
    if os.name != "nt":
        for one in (folder(), path):
            os.chmod(one, 0o700)
    return path


def sweep(name):
    """The files in folder NAME about a file that is gone (their JSON's "path") taken out: how many."""
    gone = [one.path for one in os.scandir(private(name)) if one.is_file()
            and not os.path.exists(str(read(one.path).get("path") or ""))]
    for path in gone:
        os.remove(path)
    return len(gone)


def main(argv):
    command, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    if command == "folder" and len(args) == 1:
        answer = {"folder": private(args[0])}
    elif command == "remove" and len(args) == 2 and os.path.basename(args[1]) == args[1] not in ("", ".", ".."):
        with contextlib.suppress(FileNotFoundError):
            os.remove(os.path.join(private(args[0]), args[1]))
        answer = {}
    elif command == "sweep" and len(args) == 1:
        answer = {"removed": sweep(args[0])}
    else:
        print("usage: statefile.py folder NAME | remove NAME FILE | sweep NAME", file=sys.stderr)
        return 2
    print(json.dumps(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
