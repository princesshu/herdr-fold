# Generated from core/usage.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""The agents' limits for the Agent panel's Usage, the 5-hour and the weekly one: herdr-fold's own readings, Claude's
cached ones, Codex's newest chat's, the newest per agent; each agent's block opened or folded, kept for both clients.
Nothing of the agents' is written. Usage (in JSON): usage.py limits | section AGENT [AGENTS] | open AGENT on|off."""
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
SETTINGS = "usage.json"         # in herdr-fold's state folder, both clients': the blocks opened; report.py's budgets
LARGEST = 32 << 20              # bytes of ~/.claude.json read: more is not a file Claude keeps
TAIL = 4 << 20                  # bytes from a Codex chat's end looked through for its last reading
NEWEST = 5                      # Codex chats looked through, the newest first, for one with a reading (a new one: none)
NAMES = {"claude": "Claude", "codex": "Codex"}         # an agent's name where the agents' list does not tell it
SAID = {"five_hour": ("five", "5h", "5 hour"), "week": ("week", "wk", "Week")}   # a window's key, label and name
PLAN = re.compile(r"[A-Za-z][A-Za-z ]{0,23}")           # a plan's word: letters alone, so never an e-mail or an id
AGED = 600                      # a reading older than this many seconds says its age, whoever read it
SOON = 12 * 3600                # a reset nearer than this names its time alone, a later one its day too
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


def keep(agent, windows, at):
    """WINDOWS ({"five_hour", "week"}, each a window or None) read at AT kept as AGENT's newest reading, its owner's
    only; one that tells neither (before a chat's first answer, an API key's) is not kept. Whether it was kept."""
    if agent not in AGENTS:
        raise ValueError(f"not an agent: {agent!r}")
    found = {name: window(obj(windows).get(name)) for name in WINDOWS}
    if not any(found.values()):
        return False
    statefile.write(kept_path(os.path.expanduser("~"), agent), {**found, "at": int(at)})
    return True


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


def current(reading, now):
    """READING's windows that still hold at NOW: one past its reset is None (one with no reset time, past its length
    from the reading)."""
    def holds(name):
        one = reading[name]
        return one and now < (one["resets"] if one["resets"] is not None else reading["at"] + WINDOWS[name])
    return {name: reading[name] if holds(name) else None for name in WINDOWS}


def limits(home, now):
    """Each agent's limits at NOW for the user whose home is HOME, the newest reading first: [{"agent", "five_hour",
    "week", "at", "source": status, claude or codex}], from each agent's newest reading; one with no window left out."""
    found = []
    for agent, own in (("claude", claude_cached), ("codex", codex_newest)):
        readings = [one for one in (kept(home, agent), own(home)) if one and any(one[name] for name in WINDOWS)]
        if not readings:
            continue
        newest = max(readings, key=lambda one: one["at"])
        windows = current(newest, now)
        if any(windows.values()):
            found.append({"agent": agent, **windows, "at": newest["at"], "source": newest["source"]})
    return sorted(found, key=lambda one: one["at"], reverse=True)


def level(used):
    """A percent's level, as the status line colors it: under 50 ok (green), from 50 warn (yellow), from 80 bad."""
    return "bad" if used >= 80 else "warn" if used >= 50 else "ok"


def ago(seconds):
    """How long ago, for a reading's age: just now, 43 min ago, 3 h ago, 3 d ago."""
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    return f"{seconds // 3600} h ago" if seconds < 2 * 86400 else f"{seconds // 86400} d ago"


def kept_open(state):
    """Each agent's block in Usage as the user last left it in either client, {agent: opened}, from STATE's SETTINGS;
    an agent never opened nor folded is not in it."""
    found = statefile.read(os.path.join(state, SETTINGS)).get("open")
    return {agent: found[agent] for agent in AGENTS if isinstance(found.get(agent), bool)} if isinstance(found, dict) \
        else {}


def keep_open(state, agent, on):
    """AGENT's block in Usage kept opened (ON) or folded for both clients, beside what else SETTINGS holds: the blocks
    kept then. ValueError for another agent or what is no choice."""
    if agent not in AGENTS or not isinstance(on, bool):
        raise ValueError(f"not an agent's choice: {agent!r} {on!r}")

    def change(was):
        found = was.get("open") if isinstance(was.get("open"), dict) else {}
        return {**was, "open": {**{one: found[one] for one in AGENTS if isinstance(found.get(one), bool)}, agent: on}}
    return statefile.update(os.path.join(state, SETTINGS), change)["open"]


def section(limits, agents, current, now, kept=None):
    """The Agent panel's Usage in both clients' words, from LIMITS (limits()'s) at NOW: a row an agent, the CURRENT one
    first, then the newest reading; its name and plan's word as AGENTS tell them, each window's percent and level, the
    tightest, its first one's bar and reset ({time}, {day}: the client's); "open": each block as KEPT, else CURRENT."""
    told = {one["key"]: one for one in (agents if isinstance(agents, list) else []) if isinstance(obj(one).get("key"),
                                                                                                 str)}
    rows = []
    for reading in sorted(limits, key=lambda one: one["agent"] != current):      # stable: the newest first
        key, known = reading["agent"], told.get(reading["agent"], {})
        plan, name = known.get("plan"), known.get("name")
        row = {"key": key, "name": name if isinstance(name, str) and name else NAMES.get(key, key),
               "plan": plan if isinstance(plan, str) and PLAN.fullmatch(plan) else None, "current": key == current,
               "bar": None, "resets": None,
               "age": f"as of {ago(now - reading['at'])}" if now - reading["at"] > AGED else None}
        said = []
        for window, (part, label, name) in SAID.items():
            one = reading[window]
            row[part] = one and {"label": label, "used": one["used"], "text": f"{one['used']}%",
                                 "level": level(one["used"])}
            if one:
                said.append(f"{name if not said else name.lower()} {one['used']}%")
            if one and not row["bar"]:                  # its first window: its bar, its reset
                row["bar"] = {"used": one["used"], "level": level(one["used"])}
                when = "at {time}" if one["resets"] is None or one["resets"] - now < SOON else "{day} at {time}"
                row["resets"] = one["resets"] and {"at": one["resets"], "words": f"{name} resets {when}"}
        row["tight"] = max((row[part] for part in ("five", "week") if row[part]), key=lambda one: one["used"])
        rows.append({**row, "said": ", ".join(said + ([row["age"]] if row["age"] else []))})
    keys, kept = list(dict.fromkeys([*AGENTS, *(row["key"] for row in rows)])), kept or {}
    return {"id": "usage", "title": "Usage", "none": "Not known yet", "rows": rows,
            "open": {key: kept.get(key, key == current) for key in keys}}


def twelve_hours(home):
    """Whether hours are written as 12 with AM and PM, as the status line found it for this machine (its time.json, in
    herdr-fold's state under HOME); 24 where it has not said."""
    return read_json(os.path.join(home, *LIMITS[:-1], "time.json")).get("twelve") is True


def reset_said(resets, twelve):
    """RESETS' words (section()'s) with this machine's local time in them, hours as TWELVE says ("2:46 PM", "14:46"),
    and its day ("Mon") where they ask for it; "" for none. The TUI's: the app writes its own, as macOS has them."""
    if not resets:
        return ""
    at = time.localtime(resets["at"])
    clock = f"{at.tm_hour % 12 or 12}:{at.tm_min:02d} {'AM' if at.tm_hour < 12 else 'PM'}" if twelve \
        else f"{at.tm_hour:02d}:{at.tm_min:02d}"
    return resets["words"].replace("{time}", clock).replace("{day}", time.strftime("%a", at))


def main(argv):
    """herdr-fold's Herdr app mod runs this, answering in JSON: limits; section AGENT [AGENTS] (the panel's Usage for
    the agent shown; AGENTS the agents' list as JSON, its names and plans); open AGENT on|off (the blocks kept then)."""
    home, now, state = os.path.expanduser("~"), int(time.time()), statefile.folder()
    if argv[1:] == ["limits"]:
        print(json.dumps(limits(home, now)))
        return 0
    if argv[1:2] == ["section"] and len(argv) in (3, 4):
        try:
            agents = json.loads(argv[3]) if len(argv) == 4 else []
        except (ValueError, RecursionError):
            agents = []
        print(json.dumps(section(limits(home, now), agents, argv[2], now, kept_open(state))))
        return 0
    if argv[1:2] == ["open"] and len(argv) == 4 and argv[2] in AGENTS and argv[3] in ("on", "off"):
        print(json.dumps(keep_open(state, argv[2], argv[3] == "on")))
        return 0
    print("usage: usage.py limits | section AGENT [AGENTS] | open AGENT on|off", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
