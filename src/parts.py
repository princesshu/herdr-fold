"""Which of herdr-fold's parts are installed, the TUI and the Herdr app, as the installer's records say, so nothing
records it twice. Usage: parts.py [STATE] (the records' folder): the parts, a line each, the TUI first; parts.py
--preview [MARK...]: the address of the page the installer's first question opens. And the Herdr app's home."""
import os
import pathlib
import sys

STATE = os.path.join(os.path.expanduser("~"), ".local", "state", "herdr-fold")
# the TUI's own files: one of them on the record is the TUI there, whatever else an install could not put down
TUI_FILES = (".config/ghostty/", ".config/starship.toml", ".config/herdr/", ".config/herdr-fold/plugins/")


def lines(path):
    try:
        with open(path, encoding="utf-8") as f:
            return [line.strip() for line in f]
    except OSError:
        return []


def installed(state=STATE):
    """The parts the records in STATE name: "tui" for a TUI file put down or its sidebar linked, "app" for the app's."""
    plugins, found = lines(os.path.join(state, "plugins.txt")), set()
    if "herdr-fold.sidebar" in plugins or any(rel.startswith(TUI_FILES)
                                              for rel in lines(os.path.join(state, "installed.txt"))):
        found.add("tui")
    if "herdr-fold.app" in plugins:
        found.add("app")
    return found


def app_home():
    return os.environ.get("HERDR_APP_HOME") or os.path.expanduser("~/.config/herdr-app")


def preview_address(marks):
    """The page beside the package's scripts (install/parts.html), MARKS after its #: tui, app (installed), found."""
    page = pathlib.Path(os.path.dirname(os.path.abspath(__file__)), "install", "parts.html").as_uri()
    return page + (f"#{','.join(marks)}" if marks else "")


def main(argv):
    if argv[1:2] == ["--preview"]:
        print(preview_address(argv[2:]))
        return 0
    found = installed(argv[1] if len(argv) > 1 else STATE)
    for part in ("tui", "app"):
        if part in found:
            print(part)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
