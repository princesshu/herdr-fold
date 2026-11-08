"""The Claude Code status line (model, effort, context, 5-hour and weekly limits), on the standard library alone for
macOS, Linux and Windows. Claude Code passes the session's JSON on stdin and the pane's width in COLUMNS; the items
come from statusline.json (statusline_setup.py), and a narrow pane drops them step by step (STEPS)."""
import json
import os
import plistlib
import re
import subprocess
import sys
import time

CHOICE = os.path.join(os.path.expanduser("~"), ".config", "herdr-fold", "statusline.json")
# how this machine's user has hours written, kept a DAY (asked): a Mac's own setting is a process to ask at worst
TIME = os.path.join(os.path.expanduser("~"), ".local", "state", "herdr-fold", "time.json")
DAY = 86400
HOURS = ("ObjC.import('Foundation'); "
         "$.NSDateFormatter.dateFormatFromTemplateOptionsLocale('j', 0, $.NSLocale.currentLocale).js")


def rgb(r, g, b):
    return f"\x1b[38;2;{r};{g};{b}m"


TEAL = rgb(78, 201, 212)        # the model
PURPLE = rgb(197, 134, 192)     # the effort, next to the model
YELLOW = rgb(215, 186, 125)     # the context
GREEN = rgb(166, 227, 161)      # a limit's use: below 50%
WARN = rgb(249, 226, 175)       # from 50%
CRIT = rgb(243, 139, 168)       # from 80%
GRAY = rgb(147, 153, 178)       # labels, separators, details
RESET = "\x1b[0m"
SEP = f"{GRAY}|{RESET}"
COLOR = re.compile(r"\x1b\[[0-9;]*m")
NOTE = re.compile(r"\s*\(.*\)$")                       # the model name's note: "Opus 5.5 (1M context)"
INDENT = 2                                              # Claude Code draws the line two cells in
# What a narrower pane takes, one more each step: shorter reset times (/1h 36m, /Mon 1pm), the model name's note,
# shorter labels (ctx, 5h, wk), the context window size, the weekly reset, the 5-hour reset, the effort
SHORT_TIMES, NO_NOTE, SHORT_LABELS, NO_SIZE, NO_WEEKLY_RESET, NO_RESET, NO_EFFORT = range(1, 8)
STEPS = NO_EFFORT
LABELS = {"context": ("context:", "ctx"), "five_hour": ("current:", "5h"), "weekly": ("weekly:", "wk")}


def shown():
    """The items the installer's choice keeps: each one unless it is set to false; all of them without a readable
    choice."""
    try:
        with open(CHOICE, encoding="utf-8") as f:
            claude = json.load(f).get("claude")
    except (OSError, ValueError, AttributeError):
        claude = None
    if not isinstance(claude, dict):
        claude = {}
    return {key: claude.get(key) is not False for key in ("effort", "context", "five_hour", "weekly")}


def field(data, *keys):
    """The value at KEYS in Claude's JSON; None where it is missing, null or false."""
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return None if data is False else data


def percent(value):
    """A percentage as a whole number, a half rounded to even (as printf rounds it); None if it is not a number."""
    try:
        return int("%.0f" % float(value))
    except (TypeError, ValueError):
        return None


def tokens(value):
    """A context window's size in short, e.g. "/200k", "/1M", "/1.5M"; nothing if it is not a number."""
    try:
        size = int(value)
    except (TypeError, ValueError):
        return ""
    if size >= 1_000_000:
        return f"/{size / 1_000_000:g}M"
    return f"/{round(size / 1000)}k" if size > 0 else ""


def level(used):
    return CRIT if used >= 80 else WARN if used >= 50 else GREEN


def until(reset, now, short=False):
    """The time left until the 5-hour limit resets, e.g. "/4hr 18m" (SHORT: "/4h 18m") or "/18m"; nothing once it has
    passed."""
    try:
        left = int(reset) - now
    except (TypeError, ValueError):
        return ""
    if left <= 0:
        return ""
    hours, minutes = left // 3600, left % 3600 // 60
    return f"/{hours}{'h' if short else 'hr'} {minutes}m" if hours else f"/{minutes}m"


def asked():
    """Whether this machine's user has hours written as 12 with am and pm: a Mac's Language & Region (its 24-hour
    switch, else its region's way, asked of macOS), Windows' short time, else the locale's time format."""
    if sys.platform == "darwin":
        try:
            with open(os.path.join(os.path.expanduser("~"), "Library", "Preferences", ".GlobalPreferences.plist"),
                      "rb") as f:
                prefs = plistlib.load(f)
        except (OSError, ValueError, plistlib.InvalidFileException):
            prefs = {}
        if prefs.get("AppleICUForce24HourTime") or prefs.get("AppleICUForce12HourTime"):
            return bool(prefs.get("AppleICUForce12HourTime"))
        try:
            return "a" in subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", "-e", HOURS], capture_output=True,
                                         text=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            return False
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\International") as key:
                return "h" in winreg.QueryValueEx(key, "sShortTime")[0]          # h: 12 hours, H: 24
        except OSError:
            return False
    import locale
    try:
        locale.setlocale(locale.LC_TIME, "")
        form = locale.nl_langinfo(locale.T_FMT)
    except (locale.Error, AttributeError):
        return False
    return any(mark in form for mark in ("%p", "%I", "%r"))


def twelve_hours(now):
    """asked(), as time.json keeps it for a DAY: the line is drawn often, the answer rarely changes."""
    try:
        if now - os.path.getmtime(TIME) < DAY:
            with open(TIME, encoding="utf-8") as f:
                kept = json.load(f).get("twelve")
            if isinstance(kept, bool):
                return kept
    except (OSError, ValueError, AttributeError):
        pass
    twelve = asked()
    try:
        os.makedirs(os.path.dirname(TIME), mode=0o700, exist_ok=True)
        with open(TIME, "w", encoding="utf-8") as f:
            json.dump({"twelve": twelve}, f)
        os.utime(TIME, (now, now))
    except OSError:
        pass
    return twelve


def weekday(reset, now, short=False):
    """The day and hour of the weekly reset in local time, as the machine writes hours: e.g. "/Monday 1pm" or
    "/Monday 13:00" (SHORT: "/Mon 1pm"; English, as the line's labels)."""
    try:
        at = time.localtime(int(reset))
    except (TypeError, ValueError, OverflowError, OSError):
        return ""
    hour = f"{at.tm_hour % 12 or 12}{'am' if at.tm_hour < 12 else 'pm'}" if twelve_hours(now) \
        else f"{at.tm_hour:02d}:{at.tm_min:02d}"
    return f"/{time.strftime('%a' if short else '%A', at)} {hour}"


def room():
    """The cells the line has: Claude Code's pane width (COLUMNS) less its indent; None without it (never shortened)."""
    try:
        columns = int(os.environ["COLUMNS"])
    except (KeyError, ValueError):
        return None
    return columns - INDENT if columns > 0 else None


def statusline(data, show, now, width=None):
    """The line; with WIDTH, the first of its shorter forms that fits in it (the shortest if none does)."""
    for step in range(STEPS + 1):
        line = draw(data, show, now, step)
        if width is None or len(COLOR.sub("", line)) <= width:
            break
    return line


def draw(data, show, now, step):
    line = ""
    model = field(data, "model", "display_name")
    if model not in (None, ""):
        if step >= NO_NOTE:
            model = NOTE.sub("", model) or model
        line = f"{TEAL}{model}{RESET}"
        effort = field(data, "effort", "level")             # absent where the model has no reasoning effort
        if show["effort"] and effort not in (None, "") and step < NO_EFFORT:
            line += f" {GRAY}({RESET}{PURPLE}{effort}{RESET}{GRAY}){RESET}"
    label = {key: names[step >= SHORT_LABELS] for key, names in LABELS.items()}
    # the context, and the limits (Pro and Max subscribers only), from the first answer on
    used = percent(field(data, "context_window", "used_percentage"))
    if show["context"] and used is not None:
        size = tokens(field(data, "context_window", "context_window_size")) if step < NO_SIZE else ""
        line += f" {SEP} {GRAY}{label['context']}{RESET} {YELLOW}{used}%{RESET}"
        line += f"{GRAY}{size}{RESET}" if size else ""
    used = percent(field(data, "rate_limits", "five_hour", "used_percentage"))
    if show["five_hour"] and used is not None:
        reset = field(data, "rate_limits", "five_hour", "resets_at")
        extra = until(reset, now, step >= SHORT_TIMES) if step < NO_RESET else ""
        line += f" {SEP} {GRAY}{label['five_hour']}{RESET} {level(used)}{used}%{RESET}{GRAY}{extra}{RESET}"
    used = percent(field(data, "rate_limits", "seven_day", "used_percentage"))
    if show["weekly"] and used is not None:
        reset = field(data, "rate_limits", "seven_day", "resets_at")
        extra = "" if reset is None or step >= NO_WEEKLY_RESET else weekday(reset, now, step >= SHORT_TIMES)
        line += f" {SEP} {GRAY}{label['weekly']}{RESET} {level(used)}{used}%{RESET}{GRAY}{extra}{RESET}"
    return line


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig", "replace"))
    except ValueError:
        data = None
    # bytes, not text: a Windows console's code page would not take every model name
    sys.stdout.buffer.write(statusline(data, shown(), int(time.time()), room()).encode("utf-8"))


if __name__ == "__main__":
    main()
