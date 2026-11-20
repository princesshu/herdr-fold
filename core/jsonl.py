"""The agents' JSON-lines files, read safely: a regular file only, a damaged line as none, the newest first, where
Claude keeps a folder's chats. Kept small: the chat list's reader and the agents' setup reader share it, and each
helper the Herdr app mod runs carries it whole (Linux takes one argument of 128 KiB at most)."""
import errno
import json
import os
import re
import stat


def open_regular(path, *args, **kwargs):
    """open(PATH, *ARGS, **KWARGS) for reading, a regular file only (OSError otherwise): a pipe named like a
    chat would hold the reader for good, so it is opened without waiting, then refused."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(errno.EINVAL, "not a regular file", path)
        return os.fdopen(fd, *args, **kwargs)
    except BaseException:
        os.close(fd)
        raise


def obj(value):
    return value if isinstance(value, dict) else {}


def parse(line):
    """One JSON line (text or bytes) as a dict; a damaged line (cut off, stray bytes, nested too deep, not an object)
    is empty."""
    try:
        entry = json.loads(line)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return {}
    return entry if isinstance(entry, dict) else {}


def newest_first(paths):
    """PATHS that are regular files, the most recently changed first."""
    found = []
    for path in paths:
        try:
            info = os.stat(path)
        except OSError:
            continue
        if stat.S_ISREG(info.st_mode):
            found.append((info.st_mtime, path))
    return [path for _, path in sorted(found, key=lambda pair: pair[0], reverse=True)]


def claude_project_dir(folder, home=None):
    """Claude's folder for the chats started in FOLDER (HOME's, else this user's): every character but a letter, digit
    or - becomes -."""
    return os.path.join(home or os.path.expanduser("~"), ".claude", "projects", re.sub(r"[^A-Za-z0-9-]", "-", folder))
