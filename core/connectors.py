"""An agent's connectors (its MCP servers) for both clients: the agent's own command for each change, as one argv, and
a known service's brand. herdr-fold writes nothing of an agent's itself. Usage (in JSON): connectors.py login|logout
AGENT NAME | add|form AGENT NAME URL [SCOPE] | toggle NAME on|off | brand LABEL [URL] | login-url TEXT."""
import json
import re
import sys
import urllib.parse

CLAUDE_AI = "https://claude.ai/settings/connectors"     # where a claude.ai connector is added, in the browser
AGENTS = ("claude", "codex")    # the agents whose `mcp` commands these are
SCOPES = ("local", "user")      # Claude's scope for an added server: this folder's (the user's alone), every folder's
NAME = re.compile(r"[A-Za-z0-9 ._:()-]{1,80}")          # a server's name as the agents give them (claude.ai Box)
ADDED = re.compile(r"[A-Za-z0-9_-]{1,80}")              # a new one's: what `claude mcp add` and Codex's both take
LOCAL = ("localhost", "127.0.0.1", "::1")               # the hosts plain http is for
LARGEST = 2048                  # characters of an added server's address
ASKED_LARGEST = 8192            # and of the address a sign-in opens (its query carries the request)
ESCAPES = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;?]*[ -/]*[@-~]")    # a link's target, a color
# A known service: its name, its logo (SVG Logos' name, the mod's icons/logos/ file), whether that is a one-color dark
# mark (drawn in the text's color), and for the TUI its glyph in the font's icons (None: its letter) and its color.
BRANDS = {
    "box": {"name": "Box", "logo": "box", "mono": False, "glyph": None, "color": "#3b8fe6"},
    "dropbox": {"name": "Dropbox", "logo": "dropbox", "mono": False, "glyph": "", "color": "#3d8bff"},
    "figma": {"name": "Figma", "logo": "figma", "mono": False, "glyph": "", "color": "#f24e1e"},
    "google-drive": {"name": "Google Drive", "logo": "google-drive-2020", "mono": False, "glyph": "\U000f02b6",
                     "color": "#1fa463"},
    "linear": {"name": "Linear", "logo": "linear-icon", "mono": True, "glyph": None, "color": "#7c86e6"},
    "notion": {"name": "Notion", "logo": "notion-icon", "mono": False, "glyph": "", "color": "#e6e6e6"},
    "onedrive": {"name": "OneDrive", "logo": "microsoft-onedrive", "mono": False, "glyph": "\U000f03ca",
                 "color": "#28a8ea"},
    "sentry": {"name": "Sentry", "logo": "sentry-icon", "mono": True, "glyph": "", "color": "#e1567c"},
}
# a server's name in lower-case words (no "mcp", no "server") and its address's host, or a host under it, to its brand
NAMES = {"box": "box", "dropbox": "dropbox", "figma": "figma", "google drive": "google-drive", "gdrive": "google-drive",
         "googledrive": "google-drive", "linear": "linear", "notion": "notion", "onedrive": "onedrive",
         "microsoft onedrive": "onedrive", "sentry": "sentry"}
HOSTS = {"box.com": "box", "dropbox.com": "dropbox", "figma.com": "figma", "drive.google.com": "google-drive",
         "linear.app": "linear", "notion.com": "notion", "notion.so": "notion", "onedrive.com": "onedrive",
         "onedrive.live.com": "onedrive", "sentry.io": "sentry", "sentry.dev": "sentry"}
FILLER = ("mcp", "server")
ADDRESS = "Its address, starting with https://"         # what the add form says of an address it does not take


def named(name, form=NAME):
    """NAME as one argv element, or ValueError: FORM's characters, never an option's start nor a space at an end."""
    if not isinstance(name, str) or not form.fullmatch(name) or name.startswith("-") or name != name.strip():
        raise ValueError("not a server's name")
    return name


def address(url, largest=LARGEST):
    """URL as one argv element, or ValueError: https, or http to this machine, a host, no user or password in it,
    printable ASCII alone."""
    if not isinstance(url, str) or not 0 < len(url) <= largest or not all("!" <= ch <= "~" for ch in url):
        raise ValueError("not an address")
    parts = urllib.parse.urlsplit(url)
    host, _port = parts.hostname, parts.port            # a port that is no number is a ValueError too
    if not host or parts.username is not None or parts.password is not None or not (
            parts.scheme == "https" or parts.scheme == "http" and host in LOCAL):
        raise ValueError("not an address")
    return url


def agent_of(agent):
    if agent not in AGENTS:
        raise ValueError("not an agent with connectors")
    return agent


def login(agent, name):
    """The argv that signs AGENT in to its server NAME: it opens the browser and waits, in a terminal."""
    return [agent_of(agent), "mcp", "login", named(name)]


def logout(agent, name):
    return [agent_of(agent), "mcp", "logout", named(name)]


def add(agent, name, url, scope=None):
    """The argv that adds the HTTP server NAME at URL to AGENT: Claude's for SCOPE, Codex's for every folder."""
    name, url = named(name, ADDED), address(url)
    if agent_of(agent) == "codex":
        return ["codex", "mcp", "add", name, "--url", url]
    if scope not in SCOPES:
        raise ValueError("not a scope")
    return ["claude", "mcp", "add", "--transport", "http", "--scope", scope, name, url]


def form(agent, name, url, scope=None):
    """What the add form's NAME and URL make, typed with spaces round them or not: {"argv": add()'s, "name"}, or the
    field refused and why ({"field", "error"}); an unknown AGENT or SCOPE is a ValueError (the form offers none)."""
    name, url = (text.strip() if isinstance(text, str) else "" for text in (name, url))
    add(agent, "a", "https://a", scope)                 # the agent and the scope alone: never the form's to get wrong
    for field, check, text, none, error in (("name", lambda: named(name, ADDED), name, "Name it",
                                             "Letters, digits, - and _ only"),
                                            ("url", lambda: address(url), url, ADDRESS, ADDRESS)):
        try:
            check()
        except ValueError:
            return {"field": field, "error": error if text else none}
    return {"argv": add(agent, name, url, scope), "name": name}


def toggle(name, on):
    """What Claude is told in a conversation to turn its server NAME on or off in that folder (no command does it)."""
    return f"/mcp {'enable' if on else 'disable'} {named(name)}"


def login_url(text):
    """The address `claude mcp login` printed in TEXT (a terminal's, with its colors and links) while it waits: a
    line's only word, the line ended; None until then. It is opened, never kept: its query is the request's own."""
    for line in ESCAPES.sub("", text if isinstance(text, str) else "").split("\n")[:-1]:
        try:
            return address(line.strip(), ASKED_LARGEST)
        except ValueError:
            continue
    return None


def brand(label, url=None):
    """The brand (BRANDS' key) of a server by its LABEL, else by its URL's host (with a scheme or not); None for one
    not known: a client draws its letter."""
    words = re.sub(r"\s*\(\d+\)$", "", label.lower()) if isinstance(label, str) else ""
    key = NAMES.get(" ".join(word for word in re.split(r"[^a-z0-9]+", words) if word and word not in FILLER))
    if key or not isinstance(url, str):
        return key
    try:
        host = urllib.parse.urlsplit(url if "//" in url else "//" + url).hostname or ""
    except ValueError:
        return None
    return next((key for domain, key in HOSTS.items() if host == domain or host.endswith("." + domain)), None)


def main(argv):
    """The Herdr app mod runs this, answering in JSON: a command's argv, the add form's, toggle's words, a brand's
    key, the address in a sign-in's output; a refused name, address, agent or scope is the usage."""
    asked, args = argv[1:2], argv[2:]
    try:
        if asked in (["login"], ["logout"]) and len(args) == 2:
            made = (login if asked == ["login"] else logout)(*args)
        elif asked in (["add"], ["form"]) and len(args) in (3, 4):
            made = (add if asked == ["add"] else form)(*args)
        elif asked == ["toggle"] and len(args) == 2 and args[1] in ("on", "off"):
            made = toggle(args[0], args[1] == "on")
        elif asked == ["brand"] and len(args) in (1, 2):
            made = brand(*args)
        elif asked == ["login-url"] and len(args) == 1:
            made = login_url(args[0])
        else:
            raise ValueError("not a command")
    except ValueError:
        print("usage: connectors.py login|logout AGENT NAME | add|form AGENT NAME URL [SCOPE] | toggle NAME on|off | "
              "brand LABEL [URL] | login-url TEXT", file=sys.stderr)
        return 2
    print(json.dumps(made))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
