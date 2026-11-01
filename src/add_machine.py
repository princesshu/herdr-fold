"""Add a remote machine (Ctrl+B, Shift+M): herdr has only its `herdr machine add` command, no button for it.
Runs the package's ./machines.sh new, so it needs the package folder, which the installer records in setup-folder."""
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from i18n import t  # noqa: E402
from tui import search_path, wait_and_exit  # noqa: E402

RECORD = os.path.join(HERE, "setup-folder")


def main():
    try:
        with open(RECORD, encoding="utf-8") as f:
            folder = f.read().strip()
    except OSError:
        folder = ""
    script = os.path.join(folder, "machines.sh") if folder else ""
    if script and os.path.isfile(script):
        # herdr starts the window with a bare-bones PATH: machines.sh calls herdr, ssh and the Homebrew tools by name
        herdr = os.environ.get("HERDR_BIN_PATH")
        path = os.pathsep.join(([os.path.dirname(herdr)] if herdr else []) + [search_path()])
        os.execve("/bin/bash", ["bash", script, "new"], dict(os.environ, PATH=path))
    print(t("add_machine.no_package", folder or t("add_machine.no_record")))
    wait_and_exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
