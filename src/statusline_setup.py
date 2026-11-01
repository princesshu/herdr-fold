"""The status line items of Claude Code and Codex, one checkbox list; a group turned off gives the user's own status
line back. The installer runs it (and its --claude-settings / --claude-restore); --apply skips the questions. Claude's
line reads statusline.json; Codex's items are written into ~/.codex/config.toml's [tui] status_line."""
import glob
import json
import os
import re
import shutil
import sys
import tempfile
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
from i18n import line, t

HOME = os.path.expanduser("~")
CONFIG = os.path.join(HOME, ".config", "herdr-fold", "statusline.json")
CODEX = os.path.join(HOME, ".codex", "config.toml")
SETTINGS = os.path.join(HOME, ".claude", "settings.json")
STATE = os.path.join(HOME, ".local", "state", "herdr-fold")
SAVED = "claude-statusLine.json"                    # an own Claude status line, saved before herdr-fold's went in
# seconds: Claude Code runs the line on a new message, not when its pane gets narrower (a column opened beside it),
# so it is drawn again this often for the width it has now (and the limits' reset times stay current); a run takes
# about 25 ms
REFRESH = 10
COMMAND = 'python3 "$HOME/.config/herdr-fold/statusline.py"'      # as install.sh sets it (Windows: a form of its own)
# (key, label, sample) — the items of the current status lines; all are on by default. The samples show what the status
# line itself prints, so they stay as they are in every language.
ITEMS = {
    "claude": [("effort", t("status.effort"), "Opus 5.5 (high)"),
               ("context", t("status.context"), "context: 22%/1M"),
               ("five_hour", t("status.five_hour"), "current: 18%/4hr 18m"),
               ("weekly", t("status.weekly"), "weekly: 46%/Monday 1pm")],
    "codex": [("effort", t("status.effort"), "gpt-… medium"),
              ("context", t("status.context"), "context-used, context-window-size"),
              ("five_hour", t("status.five_hour"), "five-hour-limit"),
              ("weekly", t("status.weekly"), "weekly-limit")],
}
TITLES = {"claude": t("status.title_claude"), "codex": t("status.title_codex")}
# the Codex status_line items herdr-fold manages (the model first), context-remaining too: herdr-fold shows the context
# as used. The window size comes last: Codex cuts its line at the end, and Claude's narrow line drops it first too
CODEX_ITEMS = {"context": "context-used", "five_hour": "five-hour-limit", "weekly": "weekly-limit"}
CODEX_WINDOW = "context-window-size"
CODEX_MODEL = {"model", "reasoning", "model-with-reasoning"}
CODEX_MANAGED = CODEX_MODEL | set(CODEX_ITEMS.values()) | {CODEX_WINDOW, "context-remaining"}
# config.toml: the [tui] table's header (spaces and a comment allowed), a tui key set outside it
TUI_HEADER = re.compile(r"^\s*\[\s*tui\s*\]\s*(#.*)?$")
TUI_ELSEWHERE = re.compile(r"^\s*tui\s*[.=]")
KEY = re.compile(rb"\x1b[\[O][A-D]|[\s\S]")                           # an arrow key, or any other single byte


def load():
    """The saved choice for each tool: whether herdr-fold's status line is on ("on"), and its items. What is not of
    its shape (a damaged file, another form of it) counts as on."""
    try:
        with open(CONFIG, encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        saved = {}
    choice = {}
    for tool, items in ITEMS.items():
        mine = saved.get(tool) if isinstance(saved, dict) else None
        mine = mine if isinstance(mine, dict) else {}
        choice[tool] = {key: bool(mine.get(key, True)) for key in ["on"] + [key for key, _, _ in items]}
    return choice


def save(choice):
    write_whole(CONFIG, json.dumps(choice, indent=1) + "\n")


def write_whole(path, text):
    """TEXT into the file at once (written next to it, then put in its place: a reader never sees half of it), through
    a symlink (a file kept in a dotfiles repo stays linked), keeping its permissions."""
    real = os.path.realpath(path)
    os.makedirs(os.path.dirname(real), exist_ok=True)
    mode = os.stat(real).st_mode & 0o777 if os.path.exists(real) else 0o600
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(real), prefix="." + os.path.basename(real) + ".")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, real)


def has_codex():
    return bool(shutil.which("codex")) or os.path.isdir(os.path.join(HOME, ".codex"))


def checkboxes(tty_fd, sections):
    """One checkbox list, a group for each SECTION (title, items, state); Space on a group's title switches herdr-fold's
    status line off or on. Returns the states. termios is imported here so that --apply also runs on Windows."""
    import termios
    import tty
    rows = [(group, n) for group, (_, items, _) in enumerate(sections) for n in [None, *range(len(items))]]
    height = 2 + sum(1 + len(items) for _, items, _ in sections)        # the question, a title and items a group, keys
    chosen, out = 1, os.fdopen(os.dup(tty_fd), "w")                     # on the first item, as before titles were

    def draw(first=False):
        if not first:
            out.write(f"\x1b[{height}A")
        out.write(f'\r\x1b[K  {t("status.question")}\n')
        for group, (title, items, state) in enumerate(sections):
            mark, pointer = "x" if state["on"] else " ", "›" if rows[chosen] == (group, None) else " "
            yours = "" if state["on"] else f'  \x1b[2m{t("status.yours")}\x1b[22m'
            out.write(f"\r\x1b[K  {pointer} [{mark}] \x1b[1m{title}\x1b[22m{yours}\n")
            faint = "" if state["on"] else "\x1b[2m"
            for n, (key, label, sample) in enumerate(items):
                mark = "x" if state[key] else " "
                pointer = "›" if rows[chosen] == (group, n) else " "
                out.write(f"\r\x1b[K  {pointer}     {faint}[{mark}] {label:28} \x1b[2m{sample}\x1b[22m\n")
        out.write(f'\r\x1b[K  \x1b[2m{t("status.keys")}\x1b[22m\n')
        out.flush()

    saved = termios.tcgetattr(tty_fd)
    tty.setcbreak(tty_fd, termios.TCSANOW)
    try:
        draw(first=True)
        while True:
            for key in KEY.findall(os.read(tty_fd, 64)):             # keys that came in together, one by one
                if key in (b"\x1b[A", b"\x1bOA", b"k") and chosen > 0:
                    chosen -= 1
                elif key in (b"\x1b[B", b"\x1bOB", b"j") and chosen < len(rows) - 1:
                    chosen += 1
                elif key == b" ":
                    group, n = rows[chosen]
                    _, items, state = sections[group]
                    name = "on" if n is None else items[n][0]
                    state[name] = not state[name]
                elif key in (b"\r", b"\n"):
                    out.write(f"\x1b[{height}A\r\x1b[J")              # done: the list goes, the summary lines come
                    out.flush()
                    return [state for _, _, state in sections]
            draw()
    finally:
        termios.tcsetattr(tty_fd, termios.TCSANOW, saved)
        out.close()


def toml_list(text):
    """The strings of the TOML list after the first = in TEXT, and how many line breaks come before its ], as TOML
    reads it: a ] in a string or a comment does not end it, a string in a comment is no item. None if it does not
    end."""
    items, depth, n = [], 0, text.index("=") + 1
    while n < len(text):
        ch = text[n]
        if ch == "#":                                     # a comment, to the end of its line
            n = text.find("\n", n)
            if n < 0:
                return None
        elif ch in "\"'":
            value, n = [], n + 1
            while n < len(text) and text[n] != ch:
                if ch == '"' and text[n] == "\\":         # an escape in a basic string; a literal string has none
                    n += 1
                value.append(text[n:n + 1])
                n += 1
            items.append("".join(value))
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return items, text.count("\n", 0, n)
        n += 1
    return None


def apply_codex(state):
    """Writes the [tui] status_line: the model, the chosen items, then the user's own in their order (only those when
    herdr-fold's is off). Returns None and leaves the file alone if tui is set another way (a second [tui] table would
    stop Codex from starting) or the status_line list does not end."""
    lines = []
    if os.path.exists(CODEX):
        with open(CODEX, encoding="utf-8") as f:
            lines = f.read().split("\n")
    tui = next((n for n, line in enumerate(lines) if TUI_HEADER.match(line)), None)
    if tui is None:
        if any(TUI_ELSEWHERE.match(line) for line in lines):
            return None
        if not state["on"]:
            return []                                     # nothing of herdr-fold's there
        lines += ["", "[tui]"]
        tui = len(lines) - 1
    end = next((n for n in range(tui + 1, len(lines)) if lines[n].lstrip().startswith("[")), len(lines))
    start = next((n for n in range(tui + 1, end) if re.match(r"\s*status_line\s*=", lines[n])), None)
    others = []
    if start is not None:
        listed = toml_list("\n".join(lines[start:end]))   # the list may span several lines
        if listed is None:
            return None
        found, breaks = listed
        others = [item for item in found if item not in CODEX_MANAGED]
        del lines[start:start + breaks + 1]
    elif not state["on"]:
        return []                                         # nothing of herdr-fold's there
    else:
        start = tui + 1
    items = others
    if state["on"]:
        items = ["model-with-reasoning" if state["effort"] else "model"]
        items += [item for key, item in CODEX_ITEMS.items() if state[key]]
        items += ([CODEX_WINDOW] if state["context"] else []) + others
    if items:
        lines.insert(start, "status_line = [" + ", ".join(f'"{item}"' for item in items) + "]")
    write_whole(CODEX, "\n".join(lines).rstrip("\n") + "\n")
    return items


def outcome(herdr_folds, yours):
    """The one line a run says: where herdr-fold's status line is on (HERDR_FOLDS, the tools' keys), where your own
    stays (YOURS); Codex shows a new one once it restarts."""
    said = [t("status.herdr_folds", ", ".join(TITLES[tool] for tool in herdr_folds))] if herdr_folds else []
    said += [t("status.yours_kept", ", ".join(TITLES[tool] for tool in yours))] if yours else []
    said += [t("status.codex_restart")] if "codex" in herdr_folds else []
    return "; ".join(said)


# The status line commands this package writes: python3 with statusline.py (its folder as $HOME/… or written out), and
# on Windows PowerShell running it with the machine's Python. Anything else is yours.
PACKAGE_COMMANDS = re.compile(r'python3 "(\$HOME|/[^"]*)/\.config/herdr-fold/statusline\.py"'
                              r'''|powershell -NoProfile -Command "& '[^"]*' '''
                              r''''[^"]*[/\\]\.config[/\\]herdr-fold[/\\]statusline\.py'"''')


def is_herdr_folds(status_line):
    """A status line this package wrote."""
    return isinstance(status_line, dict) and bool(PACKAGE_COMMANDS.fullmatch(str(status_line.get("command", ""))))


def set_claude_statusline(path, command, backup):
    """Claude Code's statusLine → COMMAND. An own status line goes to BACKUP/claude-statusLine.json first. The file is
    written whole at once, through a symlink (a settings file kept in a dotfiles repo stays linked); a damaged file
    raises ValueError and stays exactly as it was. Returns "set", "replaced" or "unchanged"."""
    real = os.path.realpath(path)
    try:
        with open(real, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(path)                    # not a JSON object
    wanted = {"type": "command", "command": command, "refreshInterval": REFRESH}
    old = data.get("statusLine")
    if old == wanted:
        return "unchanged"
    if is_herdr_folds(old):               # herdr-fold's own: nothing of yours to keep
        old = None
    if old:                               # saved, never over an earlier saved one
        os.makedirs(backup, exist_ok=True)
        saved = os.path.join(backup, "claude-statusLine.json")
        if os.path.exists(saved):
            saved = os.path.join(backup, time.strftime("claude-statusLine-%Y%m%d-%H%M%S.json"))
        with open(saved, "w", encoding="utf-8") as f:
            json.dump(old, f, indent=2, ensure_ascii=False)
    data["statusLine"] = wanted
    write_whole(real, json.dumps(data, indent=2, ensure_ascii=False))
    return "replaced" if old else "set"


def restore_claude_statusline(path, saved):
    """While Claude's statusLine is still herdr-fold's, the one SAVED (a file, or None) comes back and its saved copy
    goes, or, none saved, the setting goes. Returns "restored", "removed" or "not herdr-fold's"."""
    real = os.path.realpath(path)
    with open(real, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(path)                    # not a JSON object
    if not is_herdr_folds(data.get("statusLine")):
        return "not herdr-fold's"
    if saved and os.path.exists(saved):
        with open(saved, encoding="utf-8") as f:
            data["statusLine"] = json.load(f)
        write_whole(real, json.dumps(data, indent=2, ensure_ascii=False))
        os.remove(saved)
        return "restored"
    del data["statusLine"]
    write_whole(real, json.dumps(data, indent=2, ensure_ascii=False))
    return "removed"


def shown(path):
    """PATH under the home folder as ~/…, as the installer shows paths (what it says may be pasted into an issue)."""
    return "~" + path[len(HOME):] if path.startswith(HOME + os.sep) else path


def latest_saved():
    """The own Claude status line saved last, the one herdr-fold's replaced most recently (the installer keeps them in
    original/, a remote machine in prepared-*/), or None."""
    found = [path for folder in ("original", "prepared-*")
             for path in glob.glob(os.path.join(STATE, folder, "claude-statusLine*.json"))]
    return max(found, key=os.path.getmtime, default=None)


def apply_claude(on, backup):
    """Claude Code's status line as chosen: herdr-fold's (ON; any other one is saved to BACKUP first) or the user's own
    (the saved one comes back, or herdr-fold's goes). Returns what set_claude_statusline() or
    restore_claude_statusline() did; raises OSError or ValueError on a settings file it cannot read."""
    if not on:
        if not os.path.exists(SETTINGS):
            return "not herdr-fold's"
        return restore_claude_statusline(SETTINGS, latest_saved())
    try:
        with open(os.path.realpath(SETTINGS), encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    if isinstance(data, dict) and is_herdr_folds(data.get("statusLine")):
        return "unchanged"
    return set_claude_statusline(SETTINGS, COMMAND, backup)


def claude_settings(backup, command):
    """--claude-settings: says what happened, and its exit status tells the caller (0 set, 2 replaced, 1 unreadable,
    3 left alone: the choice is your own status line)."""
    if not load()["claude"]["on"]:
        return 3
    path = SETTINGS
    try:
        done = set_claude_statusline(path, command, backup)
    except (OSError, ValueError):
        print(t("status.claude_unreadable", path))
        return 1
    print(t("status.claude_replaced", backup) if done == "replaced" else t("status.claude_set"))
    return 2 if done == "replaced" else 0


def main():
    if sys.argv[1:2] == ["--claude-settings"] and len(sys.argv) == 4:
        sys.exit(claude_settings(sys.argv[2], sys.argv[3]))
    if sys.argv[1:2] == ["--claude-restore"] and len(sys.argv) == 3:
        try:
            done = restore_claude_statusline(SETTINGS, os.path.join(sys.argv[2], SAVED))
        except FileNotFoundError:
            sys.exit(3)
        except (OSError, ValueError):
            sys.exit(1)
        sys.exit(3 if done == "not herdr-fold's" else 0)
    choice = load()
    was = choice["claude"]["on"]
    if sys.argv[1:] != ["--apply"]:
        tools = ["claude"] + (["codex"] if has_codex() else [])
        with open("/dev/tty", "r+b", buffering=0) as tty_in:      # read (keys) and write (the list)
            states = checkboxes(tty_in.fileno(), [(TITLES[tool], ITEMS[tool], choice[tool]) for tool in tools])
        choice.update(zip(tools, states))
    save(choice)
    on, original = choice["claude"]["on"], os.path.join(STATE, "original")
    herdr_folds, yours = [], []
    try:            # left on: the installers have put it in (--claude-settings); else turned on, or your own
        done = "unchanged" if on and was else apply_claude(on, original)
    except (OSError, ValueError):
        print(line("warn", t("status.claude_unreadable", shown(SETTINGS))))
    else:
        (herdr_folds if on else yours).append("claude")
        if done == "replaced":
            print(line("saved", t("status.claude_replaced", shown(original))))
    if has_codex():
        if apply_codex(choice["codex"]) is None:
            print(line("warn", t("status.codex_tui_elsewhere", CODEX)))
        else:
            (herdr_folds if choice["codex"]["on"] else yours).append("codex")
    if herdr_folds or yours:
        print(line("ok", outcome(herdr_folds, yours)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
