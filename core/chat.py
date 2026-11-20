"""A Claude Code chat as the Herdr app's chat tab draws it: its session file read into steps, only where it grew
(nothing of Claude's is ever written), and the files its hook and the app share. The format is Claude's own: a field
of a wrong type is missing, a block the chat does not know a plain step, an entry it does not know left out."""
import difflib
import json
import os
import re
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import statefile  # noqa: E402
from chats import NOT_A_PROMPT, obj, open_regular, parse, session_files, text, texts_of          # noqa: E402

READ = 4 << 20                  # bytes read at a time: a longer line is read whole, and the next call goes on
OUTPUT = 4000                   # characters of a result's output kept
INPUT = 2000                    # characters of each of a call's texts kept
SUMMARY = 200                   # characters of a plain step's line
# what a call's row shows of it, by the tool
MAIN = {"Read": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "Write": "file_path",
        "NotebookEdit": "notebook_path", "Bash": "command", "Grep": "pattern", "Glob": "pattern", "WebFetch": "url",
        "WebSearch": "query"}
AGENT = ("Agent", "Task")       # a sub-agent's call (Task: its name before Claude Code 2.1)
MARK = re.compile(r"^\s*(?:[-*]|\d+[.)])\s*")      # a plan's list mark, before its words
HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
NEEDS = b'"needsAuthMcpServers"'   # in a line of Claude's that lists the servers to sign in to
NAMED = 80                      # characters of a server's name a step keeps
UUID = re.compile(rb'"uuid":"([^"\\]{1,64})"')      # a line's id in its bytes, as Claude writes it
EDGE = 80                       # bytes of a block read again with the next: an id cut by the block's end is whole there
SEEN = "seen.json"              # in a chat's folder: the ids of the lines read so far, and where that read stopped
SESSION = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")   # as Claude and the app make one


def cut(value, limit):
    """VALUE whole if it fits in LIMIT characters, else its start and its end."""
    if len(value) <= limit:
        return value
    half = (limit - 3) // 2
    return f"{value[:half]}\n…\n{value[-half:]}"


def change(result):
    """What a file tool's RESULT (Claude's toolUseResult) changed, as unified diff lines with their hunk headers, a new
    file all its lines added; None for any other result."""
    result = obj(result)
    path, hunks = text(result.get("filePath")), result.get("structuredPatch")
    if not path or not isinstance(hunks, list):
        return None
    lines = []
    for hunk in map(obj, hunks):
        numbers, body = [hunk.get(key) for key in ("oldStart", "oldLines", "newStart", "newLines")], hunk.get("lines")
        if all(isinstance(number, int) for number in numbers) and isinstance(body, list):
            lines += ["@@ -{},{} +{},{} @@".format(*numbers), *(line for line in body if isinstance(line, str))]
    content = text(result.get("content"))
    if not lines and result.get("type") == "create" and content is not None:
        added = content.splitlines()
        lines = [f"@@ -0,0 +1,{len(added)} @@", *("+" + line for line in added)]
    return {"path": path, "lines": lines} if lines else None


def first_words(name, args):
    """What a question's or a plan's row says: its first question, or its plan's first line of words (no heading)."""
    if name == "AskUserQuestion":
        questions = args.get("questions")
        return text(obj(questions[0]).get("question")) if isinstance(questions, list) and questions else None
    lines = (text(args.get("plan")) or "").splitlines() if name == "ExitPlanMode" else []
    return next((MARK.sub("", line).strip() for line in lines
                 if line.strip() and not line.lstrip().startswith("#")), None)


def call(block, cwd=None):
    """A tool call's step, a file named from CWD (Claude's folder) when it is in it; a skill, a sub-agent and a todo
    list are steps of their own kinds."""
    name, args, call_id = text(block.get("name")) or "", obj(block.get("input")), text(block.get("id"))
    if name == "Skill":
        return {"kind": "skill", "id": call_id, "name": text(args.get("skill"))}
    if name in AGENT:
        return {"kind": "agent", "id": call_id, "name": text(args.get("subagent_type")),
                "task": text(args.get("description"))}
    if name == "TodoWrite":
        todos = args.get("todos") if isinstance(args.get("todos"), list) else []
        return {"kind": "todo", "id": call_id, "items": [{"text": text(todo.get("content")) or "",
                                                          "done": todo.get("status") == "completed"}
                                                         for todo in map(obj, todos)]}
    key = MAIN.get(name, "")
    main = text(args.get(key)) or first_words(name, args)
    root = os.path.join(cwd, "") if cwd else None
    if main and root and key.endswith("path") and main.startswith(root):
        main = main[len(root):]
    return {"kind": "tool", "id": call_id, "name": name, "main": main and cut(main, INPUT),
            "input": {key: cut(value, INPUT) for key, value in args.items() if isinstance(value, str)}}


def outcome(block, entry):
    """A tool result's step: what came back, and what a file tool changed."""
    return {"kind": "result", "id": text(block.get("tool_use_id")), "ok": block.get("is_error") is not True,
            "output": cut("\n".join(texts_of(block.get("content"))), OUTPUT),
            "change": change(entry.get("toolUseResult"))}


def other(block):
    """A block the chat does not know: its type, and its first text (a name, a query) as a line."""
    words = next((value.strip() for key, value in block.items()
                  if key not in ("type", "id") and isinstance(value, str) and value.strip()), "")
    return {"kind": "other", "type": text(block.get("type")) or "", "summary": words.split("\n")[0][:SUMMARY]}


def needing(entry):
    """The servers ENTRY (a deferred tools line of the conversation's own) says are to sign in to, their names as text
    (no control character); None where it lists none."""
    delta = obj(entry.get("attachment")) if entry.get("type") == "attachment" and not entry.get("isSidechain") else {}
    names = delta.get("needsAuthMcpServers")
    if delta.get("type") != "deferred_tools_delta" or not isinstance(names, list):
        return None
    return {"".join(ch for ch in name if ch.isprintable())[:NAMED] for name in names if isinstance(name, str)}


def again(entry, ids):
    """Whether ENTRY is a line Claude wrote before and writes again (the messages a compaction keeps, a chat taken up
    in another folder: under the id it had): its id is one of IDS, which holds it from now on. One with no id is not."""
    one = entry.get("uuid")
    if not isinstance(one, str):
        return False
    known = one in ids
    ids.add(one)
    return known


def ids_before(path, offset):
    """The ids of the lines in PATH's first OFFSET bytes, found in its bytes (READ of them at a time, no line read as
    JSON: the file may be hundreds of megabytes); none where it cannot be read."""
    found, rest = set(), b""
    try:
        with open_regular(path, "rb") as f:
            while offset > 0:
                block = f.read(min(READ, offset))
                if not block:
                    break
                offset -= len(block)
                found.update(UUID.findall(rest + block))
                rest = (rest + block)[-EDGE:]
    except OSError:
        pass
    return {one.decode("utf-8", "replace") for one in found}


def ids_kept(kept, offset):
    """The ids the read that stopped at byte OFFSET left in KEPT (a chat's SEEN); None when the file holds another
    read's, or none."""
    was = read(kept) or {}
    ids = was.get("ids")
    if was.get("offset") != offset or not isinstance(ids, list):
        return None
    return {one for one in ids if isinstance(one, str)}


def needed_before(path, offset):
    """The servers to sign in to as PATH's lines before byte OFFSET last listed them (a line written again lists its
    day's: not counted); None where none did."""
    found, at, ids = None, 0, set()
    try:
        with open_regular(path, "rb") as f:
            for raw in f:
                at += len(raw)
                if at > offset:
                    break
                if NEEDS in raw:
                    entry = parse(raw.decode("utf-8", "replace"))
                    listed = None if again(entry, ids) else needing(entry)
                    found = found if listed is None else listed
    except OSError:
        return None
    return found


def said(entry, seen):
    """ENTRY's steps, each with its time; what it names of the model, the effort and the permission mode goes into
    SEEN, as do the servers it lists to sign in to: one new on that list is a sign-in's step (the first list is the
    conversation's start: none). Claude's helpers, meta lines, a compaction's summary and a line again() have none."""
    if again(entry, seen["ids"]) or entry.get("isSidechain") or entry.get("isMeta") or entry.get("isCompactSummary"):
        return []
    kind, message = entry.get("type"), obj(entry.get("message"))
    content, found = message.get("content"), []
    seen["mode"] = text(entry.get("permissionMode")) or seen["mode"]
    if kind == "user":
        words = [part.strip() for part in texts_of(content)
                 if part.strip() and not part.lstrip().startswith(NOT_A_PROMPT)]
        found = [{"kind": "user", "text": "\n\n".join(words)}] if words else []
        found += [outcome(block, entry) for block in map(obj, content if isinstance(content, list) else [])
                  if block.get("type") == "tool_result"]
    elif kind == "assistant" and isinstance(content, list):
        model = text(message.get("model"))
        seen["requested"] = text(entry.get("requestedModel")) or seen["requested"]
        seen["model"] = model if model and not model.startswith("<") else seen["model"]     # <synthetic>: an error
        seen["effort"] = text(entry.get("effort")) or seen["effort"]
        ms = entry.get("thinkingDurationMs")
        for block in map(obj, content):
            if block.get("type") == "text":
                found += [{"kind": "text", "text": block["text"]}] if (text(block.get("text")) or "").strip() else []
            elif block.get("type") in ("thinking", "redacted_thinking"):
                found.append({"kind": "thought", "ms": ms if isinstance(ms, int) else None})
            else:
                found.append(call(block, text(entry.get("cwd"))) if block.get("type") == "tool_use" else other(block))
    elif kind == "attachment" and needing(entry) is not None:
        listed, known = needing(entry), seen.get("needs")
        found = [{"kind": "signin", "server": name} for name in sorted(listed - known)] if known is not None else []
        seen["needs"] = listed
    elif kind == "system" and entry.get("subtype") == "compact_boundary":
        found = [{"kind": "other", "type": "compact_boundary", "summary": text(entry.get("content")) or ""}]
    return [{**step, "at": text(entry.get("timestamp"))} for step in found]


def whole_lines(path, offset):
    """PATH's whole lines from byte OFFSET, about READ bytes of them but at least one, and where they end; a line still
    being written waits for the next call."""
    with open_regular(path, "rb") as f:
        f.seek(offset)
        chunks = [f.read(READ)]
        while chunks[-1] and b"\n" not in chunks[-1]:         # a line longer than READ: read on to its end
            chunks.append(f.read(READ))
    data = b"".join(chunks)
    end = data.rfind(b"\n") + 1
    return data[:end], offset + end


def steps(path, offset=0, kept=None):
    """The steps of the chat in PATH from byte OFFSET, where the read stopped, and the newest model, effort and
    permission mode its lines name (None when they name none). No file (None) or one not there yet has no steps. A
    sign-in's step is told against the list before OFFSET, looked up only when these lines hold a list."""
    # a line the file held before OFFSET is no step again: the ids before it are those the last read left in KEPT (a
    # file of the chat's own, written anew by a read that found lines), else, or with no KEPT, the file's own
    seen = dict.fromkeys(("requested", "model", "effort", "mode"))
    try:
        data, offset = whole_lines(path, offset) if path else (b"", offset)
    except OSError:
        data = b""
    start = offset - len(data)
    seen["needs"] = needed_before(path, start) if NEEDS in data else None
    known = ids_kept(kept, start) if data and kept and start else None
    seen["ids"] = known if known is not None else ids_before(path, start) if data else set()
    found = [step for raw in data.splitlines() for step in said(parse(raw.decode("utf-8", "replace")), seen)]
    if data and kept:
        try:
            statefile.write(kept, {"offset": offset, "ids": sorted(seen["ids"])}, separators=(",", ":"))
        except OSError:
            pass                                # not kept: the next read finds the ids in the file
    return {"offset": offset, "steps": found, "model": seen["requested"] or seen["model"], "effort": seen["effort"],
            "mode": seen["mode"]}


# --- what Claude waits on, the app's answer, the status line's numbers

def checked(session):
    """SESSION if it is a session id; ValueError for anything else, before a path is built of it."""
    if not isinstance(session, str) or not SESSION.fullmatch(session):
        raise ValueError(f"not a session id: {session!r}")
    return session


def session_file(session):
    """The file of Claude's chat with SESSION, wherever Claude keeps it; None before it writes one."""
    return next(iter(session_files("claude", checked(session))), None)


def chat_dir(session):
    """The folder of the chat with SESSION: what Claude waits on (request.json), the app's answer (answer.json), the
    status line's numbers (status.json)."""
    return os.path.join(statefile.folder(), "chat", checked(session))


def status_path(session):
    return os.path.join(chat_dir(session), "status.json")


def read(path):
    """The JSON object in PATH; None when it is not there or not one."""
    try:
        with open_regular(path, "rb") as f:
            return parse(f.read()) or None
    except OSError:
        return None


def pending(session):
    """What Claude waits on in the chat with SESSION; None when nothing."""
    return read(os.path.join(chat_dir(session), "request.json"))


def answer(session, reply):
    """REPLY, the app's answer, to what Claude waits on in the chat with SESSION (one Claude asks in its own dialog, its
    card answered there: the request goes): False, and nothing written, when it answers another request or none."""
    asked = pending(session) or {}
    request_id = text(asked.get("id"))
    if not request_id or not isinstance(reply, dict) or reply.get("id") != request_id:
        return False
    if asked.get("kind") == "dialog":
        os.unlink(os.path.join(chat_dir(session), "request.json"))
    else:
        statefile.write(os.path.join(chat_dir(session), "answer.json"), reply)
    return True


def asked_change(request):
    """The change a waiting Edit or Write asks for (REQUEST, request.json's) as diff lines numbered where they stand in
    the file, its old text looked up there; None for any other request."""
    args, tool = obj(request.get("tool_input")), request.get("tool_name")
    path = text(args.get("file_path"))
    if tool not in ("Edit", "Write") or not path:
        return None
    try:
        with open_regular(path, "rb") as f:
            current = f.read(READ).decode("utf-8", "replace")
    except OSError:
        current = ""
    old, new = (current, text(args.get("content")) or "") if tool == "Write" \
        else (text(args.get("old_string")) or "", text(args.get("new_string")) or "")
    at = current.find(old) if tool == "Edit" and old else -1
    shift = current.count("\n", 0, at) if at >= 0 else 0
    lines = []
    for line in difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm=""):
        hunk = HUNK.fullmatch(line)
        if hunk:
            a, b, c, d = (int(n) if n is not None else 1 for n in hunk.groups())
            line = f"@@ -{a + shift if b else a},{b} +{c + shift if d else c},{d} @@"
        if not line.startswith(("---", "+++")):
            lines.append(line)
    return {"path": path, "lines": lines} if lines else None


def status(session):
    """The status line's last numbers for the chat with SESSION (context, model, limits); None before the first."""
    return read(status_path(session))


def main(argv):
    """herdr-fold's Herdr app mod runs this on the space's machine, answering in JSON: steps SESSION OFFSET (the
    chat's steps from OFFSET and where the read stopped, what Claude waits on and the status line's numbers:
    one read a poll, its lines' ids kept for the next) and answer SESSION REPLY ({"ok": whether it went to Claude})."""
    command, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    try:
        if command == "steps" and len(args) == 2 and int(args[1]) >= 0:
            asked = pending(args[0])
            change = asked_change(asked) if asked else None
            kept = os.path.join(chat_dir(args[0]), SEEN)
            found = {**steps(session_file(args[0]), int(args[1]), kept), "status": status(args[0]),
                     "pending": {**asked, "change": change} if change else asked}
        elif command == "answer" and len(args) == 2:
            reply = json.loads(args[1])
            try:
                found = {"ok": answer(args[0], reply)}
            except OSError:
                found = {"ok": False}
        else:
            raise ValueError("unknown command")
    except (ValueError, RecursionError):
        print("usage: chat.py steps SESSION OFFSET | answer SESSION REPLY", file=sys.stderr)
        return 2
    print(json.dumps(found))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
