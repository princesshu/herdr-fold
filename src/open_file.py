"""Open a file the focused pane's output names (Cmd+Shift+L, in a herdr popup): the files its recent lines name that are
there, the newest first, each with the line it gives; Open shows the file at that line in the sidebar's preview tab."""
import collections
import os
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herdrlib import HERDR, PLUGIN_STATE  # noqa: E402
import conversations_pane  # noqa: E402  the sidebar's, on the path herdrlib gives
import panels  # noqa: E402
import preview  # noqa: E402
import statefile  # noqa: E402
from i18n import line, t  # noqa: E402
from screen import after, icon, icons_on  # noqa: E402
from tui import GRAY, INVERT, RESET, button_at, buttons, clicked, getkey, mouse, printable, wait_and_exit  # noqa: E402

HOME = os.path.expanduser("~")
BOLD = "\x1b[1m"
FIRST_ROW = 3              # the list's first row on screen, under the title and the filter
DOUBLE = 0.4               # seconds within which a second click on a row opens it
LINES = 400                # the pane's recent rows read
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


class Picker:
    """The files, narrowed by what is typed; the keys and the mouse as in the folder picker."""

    def __init__(self, files, root):
        self.files, self.root, self.filt = files, root, ""
        self.chosen = self.top = 0
        self.last = None                          # the click before: its time and row (a second one there opens)

    def rows(self):
        return [one for one in self.files if self.filt.lower() in shown(one, self.root).lower()]

    def chosen_file(self):
        rows = self.rows()
        return rows[min(self.chosen, len(rows) - 1)] if rows else None

    def fit(self, height):
        """The rows on screen, HEIGHT at most, the chosen one among them."""
        rows = self.rows()
        self.chosen = min(self.chosen, max(len(rows) - 1, 0))
        self.top = min(max(self.top, self.chosen - height + 1), self.chosen)
        return rows[self.top:self.top + height]

    def press(self, key, height):
        """KEY's effect; "open", "cancel" or None."""
        if key == "\x1b[A":
            self.chosen = max(self.chosen - 1, 0)
        elif key == "\x1b[B":
            self.chosen += 1
        elif key in ("\x1b[5~", "\x1b[6~"):
            self.chosen = max(self.chosen + (height if key == "\x1b[6~" else -height), 0)
        elif key in ("\r", "\n"):
            return "open" if self.chosen_file() else None
        elif key == "\x1b" and self.filt:
            self.filt, self.chosen = "", 0
        elif key in ("\x1b", "\x03"):
            return "cancel"
        elif key in ("\x7f", "\x08"):
            self.filt, self.chosen = self.filt[:-1], 0
        elif len(key) == 1 and key.isprintable():
            self.filt, self.chosen, self.top = self.filt + key, 0, 0
        return None

    def click(self, event, now, width, height):
        """A mouse EVENT (tui.clicked()): a click chooses a row, the same one again within DOUBLE seconds opens it, a
        button opens or cancels, the wheel moves. "open", "cancel" or None."""
        button, column, at, pressed = event
        if button in (64, 65):
            self.chosen = max(min(self.chosen + (1 if button == 65 else -1), len(self.rows()) - 1), 0)
            return None
        if button != 0 or not pressed:
            return None
        shown_rows = self.fit(height)
        if at == FIRST_ROW + max(len(shown_rows), not self.files) + 1:
            label = button_at(column, picker_buttons(width, bool(self.files))[1])
            return label and ("open" if label == t("common.open") else "cancel")
        if not FIRST_ROW <= at < FIRST_ROW + len(shown_rows):
            return None
        self.chosen = self.top + at - FIRST_ROW
        if self.last and self.last[1] == self.chosen and now - self.last[0] <= DOUBLE:
            self.last = None
            return "open"
        self.last = (now, self.chosen)
        return None


def picker_buttons(width, any_file):
    """The last row: Cancel, and Open (Enter's) while there is a file to open."""
    return buttons([t("common.cancel")] + ([t("common.open")] if any_file else []), width)


def row(found, root, chosen, width, icons):
    """A file's row: its folder faint, its name, its line faint; the chosen one inverted across the width; a name too
    long for it cut at its start."""
    text = printable(shown(found, root))
    mark = icon(os.path.basename(found.path)) + after(True) if icons else ""
    cells = width - 2 - len(mark)
    text = text if len(text) <= cells else "…" + text[len(text) - cells + 1:]
    if chosen:
        return f"{INVERT} {mark}{text:{cells}} {RESET}"
    folder, _, rest = text.rpartition("/")
    name, colon, at = rest.partition(":")
    return f" {mark}{GRAY}{folder + '/' if folder else ''}{RESET}{name}{GRAY}{colon}{at}{RESET}"


def screen(picker, height, width):
    """The popup: the pane's folder as the title, what you type to filter by (only then), the files, Cancel and Open."""
    rows, icons = picker.fit(height), icons_on(PLUGIN_STATE)
    lines = [f"{BOLD}{printable(picker.root.replace(HOME, '~', 1))}{RESET}", f"{picker.filt}▏" if picker.filt else ""]
    lines += [row(one, picker.root, n == picker.chosen, width, icons) for n, one in enumerate(rows, picker.top)]
    if not picker.files:
        lines.append(" " + GRAY + t("named.none") + RESET)
    lines += ["", picker_buttons(width, bool(picker.files))[0]]
    return "\x1b[2J\x1b[H" + "\n".join(lines)


def output(pane):
    """PANE's recent rows, as text, wrapped lines joined back."""
    try:
        out = subprocess.run([HERDR, "pane", "read", pane, "--source", "recent-unwrapped", "--lines", str(LINES)],
                             capture_output=True, text=True)
    except OSError:
        return ""
    return out.stdout if out.returncode == 0 else ""


def open_found(h, found, root, pane, state_dir=PLUGIN_STATE):
    """FOUND at its line in PANE's workspace's preview tab (H: preview.Herdr); a new one gets the panes of the plugin's
    PANE's tab has, and its sidebar's Files view the file chosen, its folders open."""
    info = h.call("pane", "get", pane)["pane"]
    kinds = panels.present(h.call("pane", "list").get("panes") or []).get(info["tab_id"]) or set(panels.KINDS)
    place = root if found.path.startswith(root.rstrip(os.sep) + os.sep) else os.path.dirname(found.path)
    opened, up = [], os.path.dirname(found.path)
    while up != place and up.startswith(place):
        opened.insert(0, up)
        up = os.path.dirname(up)
    seed = {"view": "files", "selected": found.path, "expanded": opened}

    def lay_out(tab):
        statefile.write(preview.seed_file(state_dir, tab), seed)
        conversations_pane.bring(h.call, tab, kinds, state_dir)

    preview.open_preview(h, info["workspace_id"], place, preview.file_spec(place, found.path, found.line), state_dir,
                         lay_out, info["tab_id"])


def main():
    pane = os.environ.get("HERDR_ACTIVE_PANE_ID")
    if not pane:
        print(line("fail", t("common.not_in_herdr")))
        wait_and_exit(1)
    root = os.environ.get("HERDR_ACTIVE_PANE_CWD") or os.getcwd()
    picker = Picker(named(output(pane), folders(root)), root)
    mouse(True)
    while True:
        height, width = max(3, os.get_terminal_size().lines - 4), os.get_terminal_size().columns
        print(screen(picker, height, width), end="", flush=True)
        key = getkey()
        event = clicked(key)
        action = picker.click(event, time.monotonic(), width, height) if event else picker.press(key, height)
        if action == "open" and picker.chosen_file():
            return open_found(preview.Herdr(), picker.chosen_file(), root, pane)
        if action == "cancel":
            return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except RuntimeError as err:
        print(line("fail", str(err)))
        wait_and_exit(1)
