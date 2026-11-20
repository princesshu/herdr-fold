# Generated from core/update.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""herdr-fold's installed version, and the newest release on GitHub: asked of api.github.com (the request alone: no id,
no cookie) once a day while the automatic check is on (not with HERDR_FOLD_NO_UPDATE_CHECK=1), at once by Check now.
Usage (About's, in JSON): update.py check [--now] | seen VERSION | section VERSION | switch on|off."""
import json
import os
import re
import sys
import time
import urllib.request

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import statefile  # noqa: E402

LATEST = "https://api.github.com/repos/princesshu/herdr-fold/releases/latest"
RELEASES = "https://github.com/princesshu/herdr-fold/releases"
HOW = "git pull in its folder, then ./install.sh"             # README's Updating, in a line
DAY = 86400
FAILED = "GitHub did not answer"


def kept():
    """What update.json keeps: when GitHub was last asked and last answered, its answer, why the last look failed, the
    version last said as installed (seen), whether the automatic check is on."""
    return statefile.read(os.path.join(statefile.folder(), "update.json"))


def keep(**changes):
    """CHANGES made to update.json as it is then (statefile.update): every sidebar and the app write it."""
    statefile.update(os.path.join(statefile.folder(), "update.json"), lambda found: {**found, **changes})


def installed():
    """The version the installer put on this machine, or None (it never ran here: a remote machine)."""
    try:
        with open(os.path.join(statefile.folder(), "version"), encoding="utf-8") as f:
            version = f.read().strip()
    except OSError:
        return None
    return version if parts(version) else None


def parts(version):
    """VERSION (v0.4.0, 0.4.0) as numbers to compare, or None."""
    found = re.fullmatch(r"v?(\d+(?:\.\d+)*)", version or "")
    return tuple(int(n) for n in found.group(1).split(".")) if found else None


def newer(latest, current):
    """Whether LATEST is a later version than CURRENT (1.0 after 0.10.0)."""
    a, b = parts(latest), parts(current)
    return bool(a and b) and a + (0,) * (len(b) - len(a)) > b + (0,) * (len(a) - len(b))


def version_of(answer):
    """The version GitHub's latest release ANSWER names, or None."""
    tag = answer.get("tag_name") if isinstance(answer, dict) else None
    return tag.lstrip("v") if isinstance(tag, str) and parts(tag) else None


def ask():
    """The newest release's version, asked of GitHub now, or None."""
    request = urllib.request.Request(LATEST, headers={"Accept": "application/vnd.github+json",
                                                      "User-Agent": "herdr-fold"})
    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            return version_of(json.load(answer))
    except (OSError, ValueError):
        return None


def check(now=None, ask=ask, force=False):
    """This version, the newest known (GitHub asked again once a day, or at once FORCEd: Check now, through ASK),
    whether it is newer, whether the check is on, the last good look's time, why the last look failed, and this
    version when it was not yet said as installed (updated)."""
    data, now, version = kept(), time.time() if now is None else now, installed()
    on = data.get("on", True) is not False and os.environ.get("HERDR_FOLD_NO_UPDATE_CHECK") != "1"
    if version and not data:
        keep(seen=version)                                    # a new install: nothing to say
    if version and (force or on and not now - DAY < (data.get("asked", data.get("checked")) or 0) <= now):
        latest = ask()
        keep(asked=now, **({"latest": latest, "checked": now, "error": None} if latest else {"error": FAILED}))
    data = kept()
    latest = data.get("latest") if version else None
    found = bool(latest) and newer(latest, version)
    return {"version": version, "latest": latest, "newer": found, "on": on,
            "checked": data.get("checked") if version else None, "error": data.get("error") if version else None,
            "updated": version if version and data.get("seen") != version else None,
            "releases": f"{RELEASES}/tag/v{latest}" if found else RELEASES, "how": HOW}


def seen(version):
    """VERSION said as installed (Updated to herdr-fold VERSION): whether this call said it, true for one sidebar or the
    app alone, however many look at once."""
    said = []

    def change(found):
        said.append(found.get("seen") != version)
        return {**found, "seen": version}

    statefile.update(os.path.join(statefile.folder(), "update.json"), change)
    return said[-1]


def switch(on):
    """The automatic check turned ON (it looks at once) or off (its last look forgotten: About says by hand only)."""
    keep(on=True, asked=None) if on else keep(on=False, latest=None, checked=None, error=None)


def changelog():
    """The CHANGELOG the installer put beside herdr-fold's LICENSE."""
    return os.path.join(os.path.expanduser("~"), ".config", "herdr-fold", "CHANGELOG.md")


def section(version):
    """The line (from 1) of VERSION's heading in the CHANGELOG (What's new opens it there), or None for none."""
    head = re.compile(rf"## \[v?{re.escape(version.lstrip('v'))}\]( .*)?")
    try:
        with open(changelog(), encoding="utf-8") as f:
            return next((n for n, line in enumerate(f, 1) if head.fullmatch(line.rstrip("\r\n"))), None)
    except OSError:
        return None


def main(argv):
    command, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    if command == "check" and args in ([], ["--now"]):
        answer = check(force=args == ["--now"])
    elif command == "seen" and len(args) == 1 and parts(args[0]):
        answer = {"seen": args[0], "said": seen(args[0])}
    elif command == "section" and len(args) == 1 and parts(args[0]):
        answer = {"path": changelog(), "line": section(args[0])}
    elif command == "switch" and args in (["on"], ["off"]):
        switch(args[0] == "on")
        answer = {"on": args[0] == "on"}
    else:
        print("usage: update.py check [--now] | seen VERSION | section VERSION | switch on|off", file=sys.stderr)
        return 2
    print(json.dumps(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
