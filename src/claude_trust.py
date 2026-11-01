"""Trusts the git projects of this Mac's Claude panes in ~/.claude.json, so Claude Code runs the status line there:
`list` prints the untrusted ones, `trust` marks those of them read from stdin. Only git roots, never home or above (a
trusted folder vouches for every non-git folder below it); a file Claude rewrites meanwhile stays as is (exit 1)."""
import json
import os
import sys
import tempfile

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herdrlib import agents  # noqa: E402
from i18n import t  # noqa: E402

CONFIG = os.path.expanduser("~/.claude.json")


def git_root(path):
    """The project Claude keeps the trust for, found as Claude finds it: the nearest folder at or above PATH with a .git
    (a repository's folder, or a worktree's file); None outside a git repo. Not git's own answer, which a folder's
    .git/config can point elsewhere."""
    folder = path
    while not os.path.exists(os.path.join(folder, ".git")):
        if os.path.dirname(folder) == folder:
            return None
        folder = os.path.dirname(folder)
    return folder


def too_wide(folder):
    """The home folder, / or a folder above home: never trusted."""
    home = os.path.expanduser("~").rstrip(os.sep)
    return folder.rstrip(os.sep) == home or (home + os.sep).startswith(folder.rstrip(os.sep) + os.sep)


class TrustError(Exception):
    """~/.claude.json could not be read safely, or changed meanwhile: nothing was written."""


def load(strict=False):
    """The config; a missing file is empty. STRICT: any other problem raises TrustError instead of looking empty."""
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as err:
        if strict:
            raise TrustError(t("trust.unreadable", "~/.claude.json")) from err
        return {}


def stamp():
    """The file's modification time and size: Claude saving it changes them."""
    try:
        st = os.stat(CONFIG)
    except FileNotFoundError:
        return None
    return st.st_mtime_ns, st.st_size


def untrusted():
    try:
        running = agents()
    except OSError:                       # no herdr
        return []
    projects = load().get("projects") or {}
    roots = {git_root(a["cwd"]) for a in running
             if a.get("agent") == "claude" and a.get("cwd") and os.path.isdir(a["cwd"])}
    return sorted(root for root in roots
                  if root and not too_wide(root) and not (projects.get(root) or {}).get("hasTrustDialogAccepted"))


def trust(folders):
    before = stamp()
    config = load(strict=True)            # read right before writing: Claude itself rewrites the file now and then
    projects = config.setdefault("projects", {})
    for folder in folders:
        projects.setdefault(folder, {})["hasTrustDialogAccepted"] = True
    mode = os.stat(CONFIG).st_mode & 0o777 if os.path.exists(CONFIG) else 0o600
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(CONFIG), prefix=".claude.json.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    os.chmod(tmp, mode)
    if stamp() != before:                 # Claude saved it meanwhile: its version stays, this one is dropped
        os.remove(tmp)
        raise TrustError(t("trust.changed", "~/.claude.json"))
    os.replace(tmp, CONFIG)               # whole, at once: Claude never sees a half-written file


def main():
    command = sys.argv[1:] or ["list"]
    if command == ["list"]:
        for folder in untrusted():
            print(folder)
    elif command == ["trust"]:
        shown = {line.rstrip("\n") for line in sys.stdin}
        folders = [folder for folder in untrusted() if folder in shown]
        if folders:
            try:
                trust(folders)
            except TrustError as err:
                print(err)
                sys.exit(1)
    else:
        sys.exit(t("trust.usage"))


if __name__ == "__main__":
    main()
