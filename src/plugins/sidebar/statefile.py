# Generated from core/statefile.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""The plugin's state files, its owner's only whatever the umask: they hold every conversation's folder and title and a
private repository's issues. Each is written whole to a temporary file beside it, then put in place: writers never mix,
a reader sees the old file or the new, and a link planted under a predictable name is never followed."""
import json
import os
import tempfile


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
