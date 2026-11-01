"""For the maintainer: whether starship (pinned in remote/fetch-tool.sh), herdr (HERDR below) or Claude Code or Codex
(a major version: it changes the status line input and conversation files) moved on. Exit status 0: nothing newer,
1: something to do, 2: a release could not be looked up. GITHUB_TOKEN, when set, eases GitHub's rate limit."""
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# What the package was last tried with: raise each once the package is checked with the newer one
HERDR = "0.9.5"               # the installer, the plugins and AI Sessions against this herdr
CLAUDE_MAJOR = 2              # Claude Code: the status line and the Conversations column
CODEX_MAJOR = 0               # Codex: the same

SOURCES = {"starship": "https://api.github.com/repos/starship/starship/releases/latest",
           "herdr": "https://api.github.com/repos/herdrdev/herdr/releases/latest",
           "claude": "https://registry.npmjs.org/@anthropic-ai/claude-code/latest",
           "codex": "https://registry.npmjs.org/@openai/codex/latest"}


def pinned_starship():
    """The starship release remote/fetch-tool.sh downloads."""
    with open(os.path.join(ROOT, "remote", "fetch-tool.sh"), encoding="utf-8") as f:
        return re.search(r"^STARSHIP_VERSION=(\S+)$", f.read(), re.M).group(1)


def version(text):
    """A version's numbers: v1.27.0 and 1.27.0 alike."""
    return tuple(int(part) for part in re.findall(r"\d+", text)[:3])


def released(name):
    """NAME's latest release, from GitHub or npm."""
    request = urllib.request.Request(SOURCES[name], headers={"User-Agent": "herdr-fold check_updates"})
    if "github.com" in SOURCES[name] and os.environ.get("GITHUB_TOKEN"):
        request.add_unredirected_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])   # never elsewhere
    with urllib.request.urlopen(request, timeout=15) as answer:
        data = json.load(answer)
    return data.get("tag_name") or data["version"]


def lines(fetch):
    """(what to do, or that it is up to date; whether something is to do) for each."""
    starship, herdr, claude, codex = (fetch(name) for name in ("starship", "herdr", "claude", "codex"))
    pin = pinned_starship()
    if version(starship) > version(pin):
        yield (f"{'starship':<12}{pin} pinned, {starship} out: put {starship} and its checksums (the release's .sha256 "
               "files) in remote/fetch-tool.sh, then update a machine"), True
    else:
        yield f"{'starship':<12}{pin}: up to date", False
    if version(herdr) > version(HERDR):
        yield (f"{'herdr':<12}{HERDR} tried, {herdr} out: try the install, the sidebar and AI Sessions with it, "
               "then raise HERDR in tools/check_updates.py"), True
    else:
        yield f"{'herdr':<12}{HERDR}: up to date", False
    for label, major, now, setting in (("Claude Code", CLAUDE_MAJOR, claude, "CLAUDE_MAJOR"),
                                       ("Codex", CODEX_MAJOR, codex, "CODEX_MAJOR")):
        if version(now)[0] > major:
            yield (f"{label:<12}{now} out, a new major version: check the status line and the Conversations column "
                   f"with it, then raise {setting} in tools/check_updates.py"), True
        else:
            yield f"{label:<12}{major}.x: up to date", False


def main(fetch=released):
    try:
        found = list(lines(fetch))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as err:
        print(f"a release could not be looked up: {err}")
        return 2
    for line, _ in found:
        print(line)
    return 1 if any(todo for _, todo in found) else 0


if __name__ == "__main__":
    sys.exit(main())
