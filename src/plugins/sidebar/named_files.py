# Generated from core/named_files.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""The files a terminal's output names that are there, each with its line (Cmd+Shift+L): the TUI's open_file.py lists
them, the Herdr app mod runs this on the terminal's machine (JSON), so both find them by the same rules."""
import collections
import json
import os
import re
import sys

HOME = os.path.expanduser("~")
LINES = 400                # the terminal's recent rows read
# a path's run of characters, then where in the file if it says: :12 (and :5 or -20 after it), #L12, (12,5)
RUN = re.compile(r"([\w.@+~/-]+)(?::(\d+)(?:[:-]\d+)?|#L(\d+)|\((\d+),\d+\))?")
TRACEBACK = re.compile(r'File "([^"\n]+)", line (\d+)')

Found = collections.namedtuple("Found", "path line")


def folders(cwd):
    """Where a relative path is looked for: CWD, then its repository's top folder (agents name paths from there)."""
    up = cwd
    while not os.path.exists(os.path.join(up, ".git")) and os.path.dirname(up) != up:
        up = os.path.dirname(up)
    return [cwd] + ([up] if up != cwd and os.path.exists(os.path.join(up, ".git")) else [])


def where(name, places):
    """NAME as a file that is there: as it is, without a sentence's closing dot, or without a diff side's a/ or b/;
    a relative one in the first of PLACES that has it."""
    name = os.path.expanduser(name)
    for one in (name, name.rstrip("."), name[2:] if name[:2] in ("a/", "b/") else ""):
        for folder in ([""] if os.path.isabs(one) else places) if one else ():
            path = os.path.normpath(os.path.join(folder, one))
            if os.path.isfile(path):
                return path
    return None


def named(text, places):
    """The files TEXT names that are there (a relative one in PLACES), each with the line it gives, the last named
    first, each once; one named without a line too is listed only with it."""
    mentions = [(m.start(), m.group(1), int(m.group(2))) for m in TRACEBACK.finditer(text)]
    for m in RUN.finditer(text):
        name = m.group(1)
        if "/" in name or "." in name.strip("."):
            mentions.append((m.start(), name, next((int(n) for n in m.groups()[1:] if n), None)))
    paths, found = {}, []
    for _, name, at in sorted(mentions, reverse=True):
        path = paths[name] if name in paths else paths.setdefault(name, where(name, places))
        if path and Found(path, at) not in found:
            found.append(Found(path, at))
    lined = {one.path for one in found if one.line}
    return [one for one in found if one.line or one.path not in lined]


def shown(found, root):
    """FOUND as its row says it: from ROOT when in it, else from the home folder as ~; then :line."""
    inside = found.path.startswith(root.rstrip(os.sep) + os.sep)
    name = os.path.relpath(found.path, root) if inside else found.path.replace(HOME, "~", 1)
    return name + (f":{found.line}" if found.line else "")


def main(argv):
    """The Herdr app mod runs this on the terminal's machine: named_files.py CWD TEXT (its output's recent rows); JSON
    back: the files, each its path, line and the name its row shows."""
    if len(argv) != 3:
        print("usage: named_files.py CWD TEXT", file=sys.stderr)
        return 2
    found = named(argv[2], folders(argv[1]))
    print(json.dumps({"files": [{"path": one.path, "line": one.line, "name": shown(one, argv[1])} for one in found]}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
