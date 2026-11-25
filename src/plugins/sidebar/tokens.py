# Generated from core/tokens.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""Every message's tokens, for Usage: Claude's sessions with their subagents' files and Codex's token records, each
message once by its id, kept by the hour in INDEX. The files are large: each is read once, then only where it grew.
Only read: nothing of Claude's or Codex's is ever written. Usage (in JSON): tokens.py index."""
import base64
import calendar
import glob
import hashlib
import json
import os
import re
import stat
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import statefile  # noqa: E402
from jsonl import obj, open_regular, parse  # noqa: E402

INDEX = "usage-index.json"      # what was read of each file, by the hour, and where it stopped
VERSION = 1                     # another version's index (its shape) is not read: the files are
CHUNK = 32 << 20                # bytes of a file read at a time, then on to its line's end
MOST = 256 << 20                # bytes one look reads (half a second of this Mac's): the next look goes on
FIRST_LINE = 1 << 20            # bytes of a Codex file's first line read for its session (some 28 KB in use)
NAME = 64                       # characters of a subagent's type kept
# what a message's tokens are told apart as: output holds its reasoning, input neither the cache's reads nor writes
KINDS = ("input", "write_5m", "write_1h", "read", "output", "reasoning", "searches")
# thousands of prompt tokens past which a price table may ask more (LiteLLM's above_272k_tokens): a message tells
# the largest it is over, so each is priced at its own size (prices.py's cost())
STEPS = (100, 128, 200, 256, 272, 512)
CLAUDE = (b'"type":"assistant"',)                                       # the lines read, by what they hold
CODEX = (b'"type":"turn_context"', b'"type":"token_usage_record"')
MODEL = re.compile(r"[A-Za-z0-9][\w.:/@\[\]-]{0,79}")                   # a model's id: never Claude's "<synthetic>"
STAMP = re.compile(r"(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.\d+)?Z")


# --- a file's messages

def count(value):
    return value if type(value) is int and value > 0 else 0


def seconds(stamp, hours):
    """STAMP (2026-11-13T10:05:00.000Z, as both agents write a line's time) in seconds since 1970, or None; HOURS
    keeps each hour's start, found once."""
    found = STAMP.fullmatch(stamp) if isinstance(stamp, str) else None
    if not found:
        return None
    if stamp[:13] not in hours:
        try:
            hours[stamp[:13]] = calendar.timegm(tuple(int(part) for part in found.groups()[:4]) + (0, 0))
        except (ValueError, OverflowError):
            return None                 # no such day (a 13th month)
    return hours[stamp[:13]] + int(found.group(5)) * 60 + int(found.group(6))


def over(prompt):
    """The largest of STEPS a prompt of PROMPT tokens is over, in thousands; 0 for none."""
    return max((step for step in STEPS if prompt > step * 1000), default=0)


def marked(path, offset, most, marks):
    """The whole lines of PATH from OFFSET that hold one of MARKS, in order, and where the next read starts: MOST
    bytes read, then on to that line's end; a half-written last line waits. OSError when it cannot be read."""
    with open_regular(path, "rb") as f:
        f.seek(offset)
        data = f.read(most)
        if len(data) == most:
            data += f.readline()
    end = data.rfind(b"\n") + 1
    places = []
    for mark in marks:
        place = data.find(mark, 0, end)
        while place >= 0:
            places.append(place)
            place = data.find(mark, place + 1, end)
    found, stop = [], 0
    for place in sorted(places) if len(marks) > 1 else places:
        if place >= stop:               # a line that holds a mark twice is one line
            stop = data.index(b"\n", place) + 1
            found.append(data[data.rfind(b"\n", 0, place) + 1:stop])
    return found, offset + end


def once(messages):
    """MESSAGES, each id's lines as one message: a later line's usage is the whole (the larger of each kind)."""
    found = {}
    for n, one in enumerate(messages):
        earlier = found.get(one["id"]) if one["id"] else None
        if earlier:
            one = {**earlier, **{kind: max(one[kind], earlier[kind]) for kind in KINDS + ("over",)}}
        found[one["id"] or n] = one
    return list(found.values())


def sub_type(path):
    """The type of the subagent whose file is PATH (Explore), from the meta file beside it, as text; "agent" where
    that does not tell it."""
    try:
        with open_regular(path[:-len(".jsonl")] + ".meta.json", "rb") as f:
            kind = parse(f.read(FIRST_LINE)).get("agentType")
    except OSError:
        kind = None
    return "".join(ch for ch in kind if ch.isprintable())[:NAME] or "agent" if isinstance(kind, str) else "agent"


def claude_messages(path, offset=0, most=CHUNK):
    """The messages in the Claude session file PATH from OFFSET (MOST bytes of it), each once by its id, and where the
    next read starts. A subagent's file (<session>/subagents/agent-*.jsonl): its type as "sub", its parent's
    session."""
    lines, offset = marked(path, offset, most, CLAUDE)
    folder, name = os.path.split(path)
    session, sub = name[:-len(".jsonl")], None
    if lines and os.path.basename(folder) == "subagents":
        session, sub = os.path.basename(os.path.dirname(folder)), sub_type(path)
    found, hours = [], {}
    for raw in lines:
        entry = parse(raw)
        message = obj(entry.get("message"))
        used, id, model = message.get("usage"), message.get("id"), message.get("model")
        at = seconds(entry.get("timestamp"), hours)
        if entry.get("type") != "assistant" or not isinstance(used, dict) or not isinstance(id, str) or not id \
                or not isinstance(model, str) or not MODEL.fullmatch(model) or at is None:
            continue
        written, kept = count(used.get("cache_creation_input_tokens")), obj(used.get("cache_creation"))
        hour = count(kept.get("ephemeral_1h_input_tokens"))
        five = max(count(kept.get("ephemeral_5m_input_tokens")), written - hour)    # an earlier Claude: all of it
        one = {"agent": "claude", "id": id, "session": session, "at": at, "model": model, "sub": sub,
               "folder": entry.get("cwd") if isinstance(entry.get("cwd"), str) else "",
               "input": count(used.get("input_tokens")), "write_5m": five, "write_1h": hour,
               "read": count(used.get("cache_read_input_tokens")), "output": count(used.get("output_tokens")),
               "searches": count(obj(used.get("server_tool_use")).get("web_search_requests"))}
        one["reasoning"] = min(count(obj(used.get("output_tokens_details")).get("thinking_tokens")), one["output"])
        one["over"] = over(one["input"] + five + hour + one["read"])
        found.append(one)
    return once(found), offset


def codex_session(path):
    """The Codex file PATH's session, folder and, for a helper's, what it is (its first line's): Codex's own helper by
    its word (guardian), an agent a thread started as "agent" in that thread's session."""
    with open_regular(path, "rb") as f:
        meta = obj(parse(f.readline(FIRST_LINE)).get("payload"))
    session = meta.get("id") if isinstance(meta.get("id"), str) and meta.get("id") else path[-len(".jsonl") - 36:-6]
    helper, sub = obj(meta.get("source")).get("subagent"), None
    if helper is not None:
        started, word = obj(obj(helper).get("thread_spawn")), helper if isinstance(helper, str) \
            else obj(helper).get("other")
        if isinstance(started.get("parent_thread_id"), str) and started["parent_thread_id"]:
            session = started["parent_thread_id"]
        sub = "".join(ch for ch in word if ch.isprintable())[:NAME] or "agent" if isinstance(word, str) else "agent"
    return session, meta.get("cwd") if isinstance(meta.get("cwd"), str) else "", sub


def codex_messages(path, offset=0, most=CHUNK, model=""):
    """The responses in the Codex file PATH from OFFSET (MOST bytes of it), each once by its id, where the next read
    starts, and the model then: each record is the model of the turn before it (MODEL: the one a read before ended
    on). Its cached input is taken out of its input."""
    lines, offset = marked(path, offset, most, CODEX)
    found, hours = [], {}
    session, folder, sub = codex_session(path) if lines else ("", "", None)
    for raw in lines:
        entry = parse(raw)
        payload = obj(entry.get("payload"))
        if entry.get("type") == "turn_context":
            told = payload.get("model")
            model = told if isinstance(told, str) and MODEL.fullmatch(told) else model
            continue
        used, at = payload.get("usage"), seconds(entry.get("timestamp"), hours)
        if entry.get("type") != "token_usage_record" or not isinstance(used, dict) or at is None:
            continue
        id, prompt, output = payload.get("response_id"), count(used.get("input_tokens")), \
            count(used.get("output_tokens"))
        read = min(count(used.get("cached_input_tokens")), prompt)
        found.append({"agent": "codex", "id": id if isinstance(id, str) and id else None, "session": session,
                      "at": at, "model": model or "unknown", "sub": sub, "folder": folder, "input": prompt - read,
                      "write_5m": count(used.get("cache_write_input_tokens")), "write_1h": 0, "read": read,
                      "output": output, "reasoning": min(count(used.get("reasoning_output_tokens")), output),
                      "searches": 0, "over": over(prompt)})
    return once(found), offset, model


# --- the index

def files(home):
    """Every file with messages under HOME, by agent: Claude's sessions and their subagents', Codex's chats."""
    projects = os.path.join(home, ".claude", "projects", "*")
    return {"claude": glob.glob(os.path.join(projects, "*.jsonl"))
            + glob.glob(os.path.join(projects, "*", "subagents", "agent-*.jsonl")),
            "codex": glob.glob(os.path.join(home, ".codex", "sessions", "*", "*", "*", "rollout-*.jsonl"))}


def short(id):
    """ID as the index remembers it: 8 characters of its hash (48 bits: a million ids hardly ever share one)."""
    return base64.urlsafe_b64encode(hashlib.blake2b(id.encode("utf-8", "replace"), digest_size=6).digest()).decode()


def whole(entry):
    """Whether ENTRY, a file's in the index, has the shape this version keeps."""
    hours = entry.get("hours") if isinstance(entry, dict) else None
    return isinstance(hours, dict) and type(entry.get("offset")) is int and isinstance(entry.get("ids"), str) \
        and all(isinstance(sums, list) and len(sums) == len(KINDS) + 1 and all(type(n) is int for n in sums)
                and re.fullmatch(r"\d+\|[^|]+\|\d+", key) for key, sums in hours.items())


def load(state):
    """The index in STATE, {"version", "files": {path: what was read of it}}; none of another version's, or of a
    damaged one's."""
    try:
        with open(os.path.join(state, INDEX), encoding="utf-8") as f:
            kept = obj(json.load(f))
    except (OSError, ValueError, RecursionError):
        kept = {}
    found = obj(kept.get("files")) if kept.get("version") == VERSION else {}
    return {"version": VERSION, "files": {path: entry for path, entry in found.items() if whole(entry)}}


def add(entry, message, seen):
    """MESSAGE counted in ENTRY, its file's, in its hour's sums (KINDS, then the messages); one whose id SEEN holds
    is another file's copy (a session resumed in a new file), skipped; the file's last one going on, counted anew."""
    for name in ("agent", "session", "sub"):
        entry.setdefault(name, message[name])
    entry["folder"] = entry.get("folder") or message["folder"]
    key, sums, last = message["id"] and short(message["id"]), [message[kind] for kind in KINDS], entry.get("last")
    if key and last and last[0] == key:
        was = entry["hours"][last[1]]
        was[:] = [a - b for a, b in zip(was, last[2] + [1])]
        if not any(was):
            del entry["hours"][last[1]]
        sums = [max(a, b) for a, b in zip(sums, last[2])]
    elif key and key in seen:
        entry["skipped"] = entry.get("skipped", 0) + 1
        return
    elif key:
        seen.add(key)
        entry["ids"] += key
    hour = f"{message['at'] // 3600}|{message['model']}|{message['over']}"
    kept = entry["hours"].setdefault(hour, [0] * (len(KINDS) + 1))
    kept[:] = [a + b for a, b in zip(kept, sums + [1])]
    if key:
        entry["last"] = [key, hour, sums]


def advance(agent, path, entry, seen, most, size):
    """ENTRY brought on by MOST bytes of AGENT's file PATH (SIZE bytes) from where it stopped: the bytes read, and
    whether it reached what is whole of the file. OSError when it cannot be read."""
    start = entry["offset"]
    while True:
        before = entry["offset"]
        room = min(CHUNK, most - (before - start))
        if agent == "claude":
            messages, entry["offset"] = claude_messages(path, before, room)
        else:
            messages, entry["offset"], entry["model"] = codex_messages(path, before, room, entry.get("model", ""))
        for message in messages:
            add(entry, message, seen)
        if entry["offset"] - before < room or entry["offset"] >= size:
            return entry["offset"] - start, True
        if entry["offset"] - start >= most:
            return entry["offset"] - start, False


def index(state, home=None, most=MOST):
    """The index in STATE brought up to date with HOME's files (this user's), one writer at a time: a file that grew
    read on from where it stopped, MOST bytes a call (the oldest first; "left": the bytes for the next calls), one
    that is gone dropped, one that got shorter read again. The files in it, the bytes read and left."""
    path = os.path.join(state, INDEX)
    with statefile.locked(path):
        kept, found = load(state)["files"], []
        for agent, paths in files(home or os.path.expanduser("~")).items():
            for one in paths:
                try:
                    info = os.stat(one)
                except OSError:
                    continue
                if stat.S_ISREG(info.st_mode):
                    found.append((info.st_mtime, one, agent, info.st_size))
        sizes = {one: size for _, one, _, size in found}
        entries = {one: entry for one, entry in kept.items() if entry["offset"] <= sizes.get(one, -1)}
        if len(entries) < len(kept):        # a file gone or begun anew: what another skipped as its copy is read again
            entries = {one: entry for one, entry in entries.items() if not entry.get("skipped")}
        seen, read, left = None, 0, 0
        for mtime, one, agent, size in sorted(found):
            entry = entries.get(one)
            if entry and entry.get("size") == size and entry.get("mtime") == mtime:
                continue
            if read < most:
                if seen is None:
                    seen = {ids[n:n + 8] for ids in (each["ids"] for each in entries.values())
                            for n in range(0, len(ids), 8)}
                entry = entries.setdefault(one, {"offset": 0, "ids": "", "hours": {}})
                try:
                    done, ended = advance(agent, one, entry, seen, most - read, size)
                except OSError:
                    continue                # as it was: the next look tries again
                read += done
                entry.update({"size": size, "mtime": mtime} if ended else {"size": -1})
            if not entry or entry.get("size") == -1:
                left += max(0, size - (entry["offset"] if entry else 0))
        if read or len(entries) < len(kept) or not os.path.exists(path):
            statefile.write(path, {"version": VERSION, "files": entries}, separators=(",", ":"))
    return {"files": len(entries), "read": read, "left": left}


def rows(index, since, until):
    """INDEX's (load()'s) sums for the hours from SINCE until UNTIL (seconds since 1970, UNTIL not in it): a row for
    each agent, model, subagent type, session, hour and prompt step, [{"agent", "model", "sub", "session", "folder",
    "hour", "over", KINDS…, "messages"}]."""
    found = {}
    for entry in index["files"].values():
        for key, sums in entry["hours"].items():
            hour, model, step = key.split("|")
            hour = int(hour) * 3600
            if since <= hour < until:
                group = (entry.get("agent"), model, entry.get("sub"), entry.get("session"), hour, int(step))
                row = found.setdefault(group, [entry.get("folder") or "", [0] * len(sums)])
                row[1] = [a + b for a, b in zip(row[1], sums)]
    return [{"agent": agent, "model": model, "sub": sub, "session": session, "folder": folder, "hour": hour,
             "over": step, **dict(zip(KINDS + ("messages",), sums))}
            for (agent, model, sub, session, hour, step), (folder, sums) in found.items()]


def main(argv):
    """herdr-fold's Herdr app mod runs this, answering in JSON: index (the index brought up to date: the files in it,
    the bytes read and those left for the next call)."""
    if argv[1:] == ["index"]:
        print(json.dumps(index(statefile.folder())))
        return 0
    print("usage: tokens.py index", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
