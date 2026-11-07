"""herdr-fold's installed version, and the newest release on GitHub: asked of api.github.com at most once a day (the
request alone: no id, no cookie), never with HERDR_FOLD_NO_UPDATE_CHECK=1 or Check for Updates turned off in a menu.
Usage (the Herdr app mod's, in JSON): update.py check | told VERSION | switch on|off."""
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


def folder():
    """herdr-fold's state folder, where the installer records the version it installed."""
    return os.path.join(os.path.expanduser("~"), ".local", "state", "herdr-fold")


def kept():
    """What update.json keeps: when GitHub was last asked, its answer, the version told about, whether it is on."""
    try:
        with open(os.path.join(folder(), "update.json"), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def keep(**changes):
    statefile.write(os.path.join(folder(), "update.json"), {**kept(), **changes})


def installed():
    """The version the installer put on this machine, or None (it never ran here: a remote machine)."""
    try:
        with open(os.path.join(folder(), "version"), encoding="utf-8") as f:
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


def check(now=None, ask=ask):
    """This version, the newest known (GitHub asked again once a day, through ASK), whether it is newer, whether the
    check is on, and the newer version already told about."""
    data, now, version = kept(), time.time() if now is None else now, installed()
    on = data.get("on", True) is not False and os.environ.get("HERDR_FOLD_NO_UPDATE_CHECK") != "1"
    if on and version and not now - DAY < data.get("checked", 0) <= now:
        latest = ask()
        keep(checked=now, **({"latest": latest} if latest else {}))
        data = kept()
    latest = data.get("latest") if on and version else None
    return {"version": version, "latest": latest, "newer": bool(latest) and newer(latest, version), "on": on,
            "told": data.get("told"), "releases": RELEASES, "how": HOW}


def told(version):
    """VERSION told about, by a sidebar or the app: the others do not tell it again."""
    keep(told=version)


def switch(on):
    """Check for Updates turned ON or off."""
    keep(on=bool(on))


def main(argv):
    command, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    if command == "check" and not args:
        answer = check()
    elif command == "told" and len(args) == 1 and parts(args[0]):
        told(args[0])
        answer = {"told": args[0]}
    elif command == "switch" and args in (["on"], ["off"]):
        switch(args[0] == "on")
        answer = {"on": args[0] == "on"}
    else:
        print("usage: update.py check | told VERSION | switch on|off", file=sys.stderr)
        return 2
    print(json.dumps(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
