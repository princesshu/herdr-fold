"""A Claude Code conversation as the Herdr app's chat draws it: its session file read into steps, only where it grew
(nothing of Claude's is ever written), and the files its hook and the app share. The format is Claude's own: a field
of a wrong type is missing, a block the chat does not know a plain step, an entry it does not know left out."""
import json
import os
import re
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import statefile  # noqa: E402
from conversations import NOT_A_PROMPT, obj, open_regular, parse, session_files, text, texts_of  # noqa: E402

READ = 4 << 20                  # bytes read at a time: a longer line is read whole, and the next call goes on
OUTPUT = 4000                   # characters of a result's output kept
INPUT = 2000                    # characters of each of a call's texts kept
SUMMARY = 200                   # characters of a plain step's line
# what a call's row shows of it, by the tool
MAIN = {"Read": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "Write": "file_path",
        "NotebookEdit": "notebook_path", "Bash": "command", "Grep": "pattern", "Glob": "pattern", "WebFetch": "url",
        "WebSearch": "query"}
AGENT = ("Agent", "Task")       # a sub-agent's call (Task: its name before Claude Code 2.1)
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


def call(block):
    """A tool call's step; a skill, a sub-agent and a todo list are steps of their own kinds."""
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
    main = text(args.get(MAIN.get(name, "")))
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


def said(entry, seen):
    """ENTRY's steps, each with its time; what it names of the model, the effort and the permission mode goes into
    SEEN. Claude's helpers, its meta lines and its summary of a compacted conversation have none."""
    if entry.get("isSidechain") or entry.get("isMeta") or entry.get("isCompactSummary"):
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
                found.append(call(block) if block.get("type") == "tool_use" else other(block))
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


def steps(path, offset=0):
    """The steps of the conversation in PATH from byte OFFSET, where the read stopped, and the newest model, effort and
    permission mode its lines name (None when they name none). No file (None) or one not there yet has no steps."""
    seen = dict.fromkeys(("requested", "model", "effort", "mode"))
    try:
        data, offset = whole_lines(path, offset) if path else (b"", offset)
    except OSError:
        data = b""
    found = [step for raw in data.splitlines() for step in said(parse(raw.decode("utf-8", "replace")), seen)]
    return {"offset": offset, "steps": found, "model": seen["requested"] or seen["model"], "effort": seen["effort"],
            "mode": seen["mode"]}


# --- what Claude waits on, the app's answer, the status line's numbers

def checked(session):
    """SESSION if it is a session id; ValueError for anything else, before a path is built of it."""
    if not isinstance(session, str) or not SESSION.fullmatch(session):
        raise ValueError(f"not a session id: {session!r}")
    return session


def session_file(session):
    """The file of Claude's conversation with SESSION, wherever Claude keeps it; None before it writes one."""
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
    """REPLY, the app's answer, to what Claude waits on in the chat with SESSION: False, and nothing written, when it
    answers another request or none (one asked since, one given up on)."""
    request_id = text((pending(session) or {}).get("id"))
    if not request_id or not isinstance(reply, dict) or reply.get("id") != request_id:
        return False
    statefile.write(os.path.join(chat_dir(session), "answer.json"), reply)
    return True


def status(session):
    """The status line's last numbers for the chat with SESSION (context, model, limits); None before the first."""
    return read(status_path(session))


def main(argv):
    """herdr-fold's Herdr app mod runs this on the space's machine, answering in JSON: steps SESSION OFFSET (the
    conversation's steps from OFFSET and where the read stopped, what Claude waits on and the status line's numbers:
    one read a poll) and answer SESSION REPLY ({"ok": whether it went to Claude})."""
    command, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    try:
        if command == "steps" and len(args) == 2 and int(args[1]) >= 0:
            found = {**steps(session_file(args[0]), int(args[1])), "pending": pending(args[0]),
                     "status": status(args[0])}
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
