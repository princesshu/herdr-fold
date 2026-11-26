"""The agents' limits for the Agent panel's Usage, the 5-hour and the weekly one: herdr-fold's own readings, Claude's
cached ones, Codex's newest chat's, the newest per agent, a window just reset told as such. Nothing of the agents' is
written. Usage (in JSON): usage.py limits | section AGENT [AGENTS]."""
import calendar
import errno
import glob
import json
import math
import os
import re
import stat
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import statefile  # noqa: E402

AGENTS = ("claude", "codex")
WINDOWS = {"five_hour": 5 * 3600, "week": 7 * 86400}    # each window's length: one with no reset time lasts as long
CODEX_WINDOWS = {300: "five_hour", 10080: "week"}       # Codex's windows by their minutes (its primary may be either)
LIMITS = (".local", "state", "herdr-fold", "limits")    # herdr-fold's readings in the home, <agent>.json each
SETTINGS = "usage.json"         # in herdr-fold's state folder, both clients': report.py's budgets and notices dismissed
LARGEST = 32 << 20              # bytes of ~/.claude.json read: more is not a file Claude keeps
TAIL = 4 << 20                  # bytes from a Codex chat's end looked through for its last reading
NEWEST = 5                      # Codex chats looked through, the newest first, for one with a reading (a new one: none)
NAMES = {"claude": "Claude", "codex": "Codex"}         # an agent's name where the agents' list does not tell it
SAID = {"five_hour": ("five", "5h", "5h"), "week": ("week", "wk", "Week")}   # a window's key, label and name
PLAN = re.compile(r"[A-Za-z][A-Za-z ]{0,23}")           # a plan's word: letters alone, so never an e-mail or an id
API_KEY = "API key"             # agent_state.py's word for a plan on an API key: it has no window to tell
UNTOLD = "limits not told"      # the current agent's row with no reading: said in its place, why in its properties
WHY = {"claude": "Claude tells its limits to herdr-fold's status line and to its own cache: neither holds a reading "
                 "yet.",
       "codex": "Codex tells its limits in a chat's token counts: none of its newest chats holds one yet.",
       "opencode": "OpenCode tells no plan's limits on this machine: its stats count tokens and cost alone.",
       "copilot": "Copilot asks GitHub for its plan's use when its /usage shows it: nothing on this machine keeps it."}
SOON = 12 * 3600                # a reset nearer than this names its time alone, a later one its day too
SAME = 3600                     # resets this close are one window's: the next resets a window's length later at least
STAMP = re.compile(r"(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d):(\d\d)(?:\.\d*)?(Z|[+-]\d\d:?\d\d)?$")


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def obj(value):
    return value if isinstance(value, dict) else {}


def epoch(value):
    """VALUE, a time in seconds since 1970 or an ISO 8601 text (UTC unless it names its offset), in whole seconds; None
    for anything else."""
    if number(value):
        return int(value)
    found = STAMP.match(value) if isinstance(value, str) else None
    if not found:
        return None
    *parts, zone = found.groups()
    try:
        seconds = calendar.timegm(tuple(int(part) for part in parts))
    except (ValueError, OverflowError):
        return None             # no such day (a 13th month)
    if zone and zone != "Z":
        digits = zone[1:].replace(":", "")
        seconds -= (1 if zone[0] == "+" else -1) * (int(digits[:2]) * 3600 + int(digits[2:]) * 60)
    return seconds


def window(value):
    """A window as kept and answered, {"used": a whole percent, "resets": seconds since 1970 or None}, from VALUE in
    that shape; None for one that does not tell its use."""
    value = obj(value)
    if not number(value.get("used")):
        return None
    return {"used": round(value["used"]), "resets": epoch(value.get("resets"))}


def opened(path):
    """PATH opened to read in binary, a regular file only (OSError otherwise): a pipe in its place would hold the
    reader for good."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(errno.EINVAL, "not a regular file", path)
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


def read_json(path):
    """The JSON object in PATH; {} for none, or what cannot be read as one."""
    try:
        with opened(path) as f:
            found = json.loads(f.read(LARGEST))
    except (OSError, ValueError, RecursionError):
        return {}
    return obj(found)


def kept_path(home, agent):
    return os.path.join(home, *LIMITS, f"{agent}.json")


def told(data):
    """The windows Claude's status-line JSON DATA tells ({"five_hour", "week"}): its rate_limits as last answered."""
    limits = obj(obj(data).get("rate_limits"))
    return {name: window({"used": obj(limits.get(key)).get("used_percentage"),
                          "resets": obj(limits.get(key)).get("resets_at")})
            for name, key in (("five_hour", "five_hour"), ("week", "seven_day"))}


def fresher(mine, kept, now, own=None):
    """MINE (a chat's reading of a window) against KEPT at NOW: while OWN (Claude's /usage, the account's) is open, the
    highest use told of that window alone; else in one window the higher use, KEPT where MINE's is past its reset and
    KEPT's not, else MINE: two open windows (a chat may tell another weekly limit), or no reset, never mixed."""
    if own and own["resets"] is not None and own["resets"] > now:
        return max((one for one in (own, mine, kept) if one and one["resets"] is not None
                    and abs(one["resets"] - own["resets"]) < SAME), key=lambda one: one["used"])
    if not mine or not kept or mine["resets"] is None or kept["resets"] is None:
        return mine
    if abs(mine["resets"] - kept["resets"]) < SAME:
        return mine if mine["used"] >= kept["used"] else kept
    return kept if mine["resets"] <= now < kept["resets"] else mine


def keep(agent, windows, at):
    """WINDOWS ({"five_hour", "week"}, each a window or None) read at AT kept as AGENT's newest reading, each the
    fresher() of it, the one kept (another chat's may be newer) and Claude's own; its owner's only. The windows kept;
    None for a reading that tells neither (before a chat's first answer, an API key's), which is not kept."""
    if agent not in AGENTS:
        raise ValueError(f"not an agent: {agent!r}")
    found = {name: window(obj(windows).get(name)) for name in WINDOWS}
    if not any(found.values()):
        return None
    home = os.path.expanduser("~")
    before, own = kept(home, agent) or {}, (claude_cached(home) if agent == "claude" else None) or {}
    found = {name: fresher(found[name], before.get(name), int(at), own.get(name)) for name in WINDOWS}
    statefile.write(kept_path(os.path.expanduser("~"), agent), {**found, "at": int(at)})
    return found


def kept(home, agent):
    """AGENT's reading as herdr-fold's status lines kept it, or None."""
    found = read_json(kept_path(home, agent))
    return {**{name: window(found.get(name)) for name in WINDOWS}, "at": int(found["at"]), "source": "status"} \
        if number(found.get("at")) else None


def claude_cached(home):
    """Claude's own reading, kept in ~/.claude.json at its own pace (cachedUsageUtilization, when it was fetched), or
    None. Its account is never read."""
    cached = obj(read_json(os.path.join(home, ".claude.json")).get("cachedUsageUtilization"))
    if not number(cached.get("fetchedAtMs")):
        return None
    used = obj(cached.get("utilization"))
    found = {name: obj(used.get(key)) for name, key in (("five_hour", "five_hour"), ("week", "seven_day"))}
    return {**{name: window({"used": one.get("utilization"), "resets": one.get("resets_at")})
               for name, one in found.items()}, "at": int(cached["fetchedAtMs"] // 1000), "source": "claude"}


def codex_windows(limits, at):
    """The windows in a Codex reading's rate_limits LIMITS, told at AT, by their length."""
    found = dict.fromkeys(WINDOWS)
    for key in ("primary", "secondary"):
        one = obj(obj(limits).get(key))
        name = CODEX_WINDOWS.get(one.get("window_minutes")) if number(one.get("window_minutes")) else None
        if name:
            resets = one.get("resets_at")
            if resets is None and number(one.get("resets_in_seconds")):    # an earlier Codex's way
                resets = at + one["resets_in_seconds"]
            found[name] = window({"used": one.get("used_percent"), "resets": resets})
    return found


def codex_readings(path):
    """Each token_count event's limits in the last TAIL bytes of the Codex chat in PATH, in order, as windows read at
    the event's time (the file's for one without)."""
    with opened(path) as f:
        size, changed = os.fstat(f.fileno()).st_size, int(os.fstat(f.fileno()).st_mtime)
        f.seek(max(0, size - TAIL))
        lines = f.read().split(b"\n")[1 if size > TAIL else 0:]      # the first one cut by the start
    for raw in lines:
        if b'"token_count"' not in raw:
            continue
        try:
            entry = obj(json.loads(raw.decode("utf-8", "replace")))
        except (ValueError, RecursionError):
            continue
        payload = obj(entry.get("payload"))
        if entry.get("type") == "event_msg" and payload.get("type") == "token_count":
            at = epoch(entry.get("timestamp")) or changed
            yield {**codex_windows(payload.get("rate_limits"), at), "at": at, "source": "codex"}


def codex_newest(home):
    """Codex's reading in its newest chat that has any: the last with a window (a premium model's own limit has none);
    None where that chat's readings have no window (an API key's)."""
    found = []
    for path in glob.glob(os.path.join(home, ".codex", "sessions", "*", "*", "*", "rollout-*.jsonl")):
        try:
            found.append((os.stat(path).st_mtime, path))
        except OSError:
            continue
    for _, path in sorted(found, reverse=True)[:NEWEST]:
        try:
            readings = list(codex_readings(path))
        except OSError:
            continue
        if readings:
            return next((one for one in reversed(readings) if any(one[name] for name in WINDOWS)), None)
    return None


def current(reading, now, used):
    """READING's windows at NOW: one still holding as it is; one past its reset (one with no reset time, past its
    length from the reading) used 0 where nothing ran since it (USED: when the agent last wrote a chat), else not
    known (None), with no reset."""
    found = {}
    for name in WINDOWS:
        one = reading[name]
        ends = one and (one["resets"] if one["resets"] is not None else reading["at"] + WINDOWS[name])
        found[name] = one if not one or now < ends else {"used": 0 if used < ends else None, "resets": None}
    return found


def last_used(agent, home):
    """When AGENT last wrote one of its chats in HOME, in seconds since 1970; 0 for never."""
    place = (".claude", "projects", "*", "*.jsonl") if agent == "claude" else \
        (".codex", "sessions", "*", "*", "*", "rollout-*.jsonl")
    found = 0
    for path in glob.glob(os.path.join(home, *place)):
        try:
            found = max(found, os.stat(path).st_mtime)
        except OSError:
            continue
    return found


def limits(home, now):
    """Each agent's limits at NOW for the user whose home is HOME, the newest reading first: [{"agent", "five_hour",
    "week", "at", "source": status, claude or codex}], from each agent's newest reading (current()'s windows); one
    with no window left out."""
    found = []
    for agent, own in (("claude", claude_cached), ("codex", codex_newest)):
        readings = [one for one in (kept(home, agent), own(home)) if one and any(one[name] for name in WINDOWS)]
        if readings:
            newest = max(readings, key=lambda one: one["at"])
            found.append({"agent": agent, **current(newest, now, last_used(agent, home)), "at": newest["at"],
                          "source": newest["source"]})
    return sorted(found, key=lambda one: one["at"], reverse=True)


def level(used):
    """A percent's level, as the status line colors it: under 50 ok (green), from 50 warn (yellow), from 80 bad."""
    return "bad" if used >= 80 else "warn" if used >= 50 else "ok"


def ago(seconds):
    """How long ago, for a reading's age: just now, 3 min ago, 3 h ago, 3 d ago."""
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    return f"{seconds // 3600} h ago" if seconds < 2 * 86400 else f"{seconds // 86400} d ago"


def section(limits, agents, current, now):
    """The Agent panel's Usage from LIMITS at NOW: a row an agent (CURRENT first; with no reading "untold", its words
    and why, but on an API key), its name and plan as AGENTS tell, each window's percent ("0%" just reset, "–" not
    known), level and reset ({time}, {day}: the client's), the tightest, "reset" (while yellow or red), the age."""
    told = {one["key"]: one for one in (agents if isinstance(agents, list) else []) if isinstance(obj(one).get("key"),
                                                                                                 str)}
    rows = []
    for reading in sorted(limits, key=lambda one: one["agent"] != current):      # stable: the newest first
        key, known = reading["agent"], told.get(reading["agent"], {})
        plan, name = known.get("plan"), known.get("name")
        row = {"key": key, "name": name if isinstance(name, str) and name else NAMES.get(key, key),
               "plan": plan if isinstance(plan, str) and PLAN.fullmatch(plan) else None, "current": key == current,
               "age": f"Read {ago(now - reading['at'])}", "untold": None}
        for window, (part, label, said) in SAID.items():
            one, when = reading[window], "{time}"
            if one and one["resets"] is not None and one["resets"] - now >= SOON:
                when = "{day} {time}"
            row[part] = one and {"label": label, "used": one["used"],
                                 "text": "–" if one["used"] is None else f"{one['used']}%",
                                 "level": None if one["used"] is None else level(one["used"]),
                                 "resets": one["resets"] and {"at": one["resets"], "words": f"{said} resets {when}"}}
        known = [row[part] for part in ("five", "week") if row[part] and row[part]["used"] is not None]
        row["tight"] = max(known, key=lambda one: one["used"]) if known else None
        row["reset"] = row["tight"]["resets"] if row["tight"] and row["tight"]["level"] in ("warn", "bad") else None
        rows.append(row)
    mine = told.get(current)
    if mine and not any(row["current"] for row in rows) and mine.get("plan") != API_KEY:
        plan, name = mine.get("plan"), mine.get("name") if isinstance(mine.get("name"), str) else None
        name = name or NAMES.get(current, current)
        rows.insert(0, {"key": current, "name": name, "current": True, "age": None, "five": None, "week": None,
                        "plan": plan if isinstance(plan, str) and PLAN.fullmatch(plan) else None, "tight": None,
                        "reset": None, "untold": {"text": UNTOLD, "why": WHY.get(
                            current, f"{name} does not tell herdr-fold its limits.")}})
    return {"id": "usage", "title": "Usage", "none": "Not known yet", "rows": rows}


def twelve_hours(home):
    """Whether hours are written as 12 with AM and PM, as the status line found it for this machine (its time.json, in
    herdr-fold's state under HOME); 24 where it has not said."""
    return read_json(os.path.join(home, *LIMITS[:-1], "time.json")).get("twelve") is True


def reset_said(resets, twelve):
    """RESETS' words (a window's in section()) with this machine's local time in them, hours as TWELVE says ("2:46 PM",
    "14:46"), and its day ("Mon") where they ask for it; "" for none. The TUI's: the app writes its own, as macOS has
    them."""
    if not resets:
        return ""
    at = time.localtime(resets["at"])
    clock = f"{at.tm_hour % 12 or 12}:{at.tm_min:02d} {'AM' if at.tm_hour < 12 else 'PM'}" if twelve \
        else f"{at.tm_hour:02d}:{at.tm_min:02d}"
    return resets["words"].replace("{time}", clock).replace("{day}", time.strftime("%a", at))


def main(argv):
    """herdr-fold's Herdr app mod runs this, answering in JSON: limits; section AGENT [AGENTS] (the panel's Usage for
    the agent shown; AGENTS the agents' list as JSON, its names and plans)."""
    home, now = os.path.expanduser("~"), int(time.time())
    if argv[1:] == ["limits"]:
        print(json.dumps(limits(home, now)))
        return 0
    if argv[1:2] == ["section"] and len(argv) in (3, 4):
        try:
            agents = json.loads(argv[3]) if len(argv) == 4 else []
        except (ValueError, RecursionError):
            agents = []
        print(json.dumps(section(limits(home, now), agents, argv[2], now)))
        return 0
    print("usage: usage.py limits | section AGENT [AGENTS]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
