# Generated from core/checkpoints.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""A Claude chat's checkpoints, both clients': each prompt that starts a turn is one, its files taken back to how they
were there by Claude's own --rewind-files after its dry run (the Agent SDK's rewind_files), the files it changes set
aside here first for one Undo. The conversation is never touched: Claude rewinds a chat in place in its terminal."""
import json
import os
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import statefile  # noqa: E402
from chats import NOT_A_PROMPT, obj, open_regular, parse, session_files, text, texts_of  # noqa: E402
from locate import find, tool_env  # noqa: E402

# Claude's file tools, the only changes a checkpoint covers, and the argument naming the file each writes
WRITES = {"Edit": "file_path", "MultiEdit": "file_path", "Write": "file_path", "NotebookEdit": "notebook_path"}
AGENTS = ("Agent", "Task")            # a subagent's call (Task: its name before Claude Code 2.1)
KEEPS = 100                           # the newest checkpoints whose files Claude keeps (its checkpointing docs)
FLAG = {"CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING": "true"}    # a rewind from outside Claude's terminal needs it
WAIT = 60                             # seconds Claude has to answer
UNDO = "checkpoints"                  # in herdr-fold's state: a chat's folder, the files a restore changed as they were
ASK = "herdr-fold"                    # the dry run's request id
ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")   # a session's, a message's


def points(path):
    """The checkpoints of the Claude chat in PATH, oldest first: each prompt that starts a turn (its id, time and first
    line), how many files its turn wrote, the Bash and subagent calls from it on (their changes stay), and whether
    Claude still keeps its files (its snapshot for it is one of the KEEPS newest)."""
    found, snapshots, last = [], [], None
    with open_regular(path, "rb") as f:
        for raw in f:
            entry = parse(raw.decode("utf-8", "replace"))
            kind, message = entry.get("type"), obj(entry.get("message"))
            if kind == "file-history-snapshot":
                snapshots.append(text(entry.get("messageId")))
            elif entry.get("isSidechain") or entry.get("isMeta") or entry.get("isCompactSummary"):
                continue
            elif kind == "user" and text(entry.get("uuid")):
                words = [part.strip() for part in texts_of(message.get("content"))
                         if part.strip() and not part.lstrip().startswith(NOT_A_PROMPT)]
                if words:
                    last = {"id": entry["uuid"], "at": text(entry.get("timestamp")),
                            "text": words[0].splitlines()[0], "files": set(), "bash": 0, "agents": 0}
                    found.append(last)
            elif kind == "assistant" and last and isinstance(message.get("content"), list):
                for block in map(obj, message["content"]):
                    name, args = block.get("name"), obj(block.get("input"))
                    if block.get("type") != "tool_use":
                        continue
                    if name in WRITES and text(args.get(WRITES[name])):
                        last["files"].add(args[WRITES[name]])
                    last["bash"] += name == "Bash"
                    last["agents"] += name in AGENTS
    kept = set(list(dict.fromkeys(snapshots))[-KEEPS:])
    bash = agents = 0
    for point in reversed(found):                       # what ran from a point on: its own turn and every later one
        bash, agents = bash + point["bash"], agents + point["agents"]
        point.update(files=len(point["files"]), bash=bash, agents=agents, kept=point["id"] in kept)
    return found


def folder_of(path):
    """The folder the chat in PATH ran in, as its first line naming one says; None for none."""
    with open_regular(path, "rb") as f:
        for raw in f:
            folder = text(parse(raw.decode("utf-8", "replace")).get("cwd"))
            if folder:
                return folder
    return None


def claude(session, point):
    """Claude Code here and the folder chat SESSION ran in; ValueError says what is missing (SESSION and POINT are
    ids: never an option or a path)."""
    path = session_file(session)
    binary = find("claude")
    if not ID.fullmatch(point):
        raise ValueError("not a checkpoint")
    if not path:
        raise ValueError("Claude's file of this chat is gone")
    if not binary:
        raise ValueError("Claude Code is not installed here")
    folder = folder_of(path)
    if not folder or not os.path.isdir(folder):
        raise ValueError("the chat's folder is gone")
    return binary, folder


def session_file(session):
    """Claude's file of chat SESSION, None before it writes one; ValueError for anything but a session's id."""
    if not ID.fullmatch(session):
        raise ValueError("not a session id")
    return next(iter(session_files("claude", session)), None)


def ask(session, point):
    """Claude's dry run of taking chat SESSION's files back to POINT: {files (paths), insertions, deletions}, or
    {error} in Claude's words."""
    try:
        binary, folder = claude(session, point)
    except ValueError as err:
        return {"error": str(err)}
    request = {"type": "control_request", "request_id": ASK,
               "request": {"subtype": "rewind_files", "user_message_id": point, "dry_run": True}}
    try:
        done = subprocess.run([binary, "-p", "--input-format", "stream-json", "--output-format", "stream-json",
                               "--verbose", "--strict-mcp-config", "--resume", session], cwd=folder,
                              env={**tool_env(binary), **FLAG}, input=json.dumps(request) + "\n", capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=WAIT)
    except (OSError, subprocess.TimeoutExpired) as err:
        return {"error": f"Claude did not answer: {err}"}
    for line in done.stdout.splitlines():
        reply = obj(parse(line).get("response"))
        if parse(line).get("type") != "control_response" or reply.get("request_id") != ASK:
            continue
        answer = obj(reply.get("response"))
        if reply.get("subtype") != "success" or answer.get("canRewind") is not True:
            return {"error": text(answer.get("error")) or text(reply.get("error")) or "Claude cannot rewind here"}
        return {"files": [one for one in answer.get("filesChanged") or [] if text(one)],
                "insertions": answer.get("insertions") or 0, "deletions": answer.get("deletions") or 0}
    return {"error": said(done.stderr) or "Claude did not answer"}


def said(output):
    """Claude's last line on stderr, without its "Error: "."""
    lines = [line.strip() for line in (output or "").splitlines() if line.strip()]
    return lines[-1].removeprefix("Error: ") if lines else ""


def undo_folder(session):
    if not ID.fullmatch(session):
        raise ValueError("not a session id")
    return os.path.join(statefile.private(UNDO), session)


def restore(session, point, last):
    """Chat SESSION's files back to how they were at POINT: the dry run's files set aside first (one Undo, LAST the
    chat's newest point then), then Claude's --rewind-files. {files: how many}, or {error} in Claude's words."""
    asked = ask(session, point)
    if "error" in asked:
        return asked
    if not asked["files"]:
        return {"error": "The files are already as they were there"}
    binary, folder = claude(session, point)
    kept = undo_folder(session)
    shutil.rmtree(kept, ignore_errors=True)
    os.makedirs(kept, mode=0o700)
    files = []
    for n, path in enumerate(asked["files"]):
        copy = str(n) if os.path.isfile(path) else None          # none: the restore makes it, an Undo removes it
        if copy:
            shutil.copy2(path, os.path.join(kept, copy))
        files.append({"path": path, "copy": copy})
    statefile.write(os.path.join(kept, "undo.json"), {"point": point, "last": last, "files": files})
    try:
        done = subprocess.run([binary, "-p", "--resume", session, "--rewind-files", point], cwd=folder,
                              env={**tool_env(binary), **FLAG}, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=WAIT)
        error = None if done.returncode == 0 else said(done.stderr) or "Claude could not rewind the files"
    except (OSError, subprocess.TimeoutExpired) as err:
        error = f"Claude did not answer: {err}"
    if error:
        shutil.rmtree(kept, ignore_errors=True)
        return {"error": error}
    return {"files": len(files)}


def undoable(session, last):
    """The last restore of chat SESSION while it can be undone (no prompt since: LAST is still the newest point):
    {point, files}; None otherwise."""
    record = statefile.read(os.path.join(undo_folder(session), "undo.json"))
    if not record or record.get("last") != last or not isinstance(record.get("files"), list):
        return None
    return {"point": record.get("point"), "files": len(record["files"])}


def undo(session):
    """The last restore of chat SESSION undone: its files put back as they were before it, once. {files: how many},
    or {error}."""
    kept = undo_folder(session)
    record = statefile.read(os.path.join(kept, "undo.json"))
    if not isinstance(record.get("files"), list):
        return {"error": "Nothing to undo"}
    for one in map(obj, record["files"]):
        path, copy = text(one.get("path")), text(one.get("copy"))
        if not path:
            continue
        if copy:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            shutil.copy2(os.path.join(kept, copy), path)
        elif os.path.isfile(path):
            os.remove(path)
    shutil.rmtree(kept, ignore_errors=True)
    return {"files": len(record["files"])}


def listed(session):
    """Chat SESSION's checkpoints and its restore that can be undone: {points, undo}."""
    path = session_file(session)
    found = points(path) if path else []
    return {"points": found, "undo": undoable(session, found[-1]["id"] if found else None)}


def main(argv):
    """The Herdr app mod's, on the space's machine, answering in JSON: points SESSION, ask SESSION POINT, restore
    SESSION POINT LAST, undo SESSION."""
    command, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    try:
        if command == "points" and len(args) == 1:
            found = listed(args[0])
        elif command == "ask" and len(args) == 2:
            found = ask(args[0], args[1])
        elif command == "restore" and len(args) == 3:
            found = restore(args[0], args[1], args[2])
        elif command == "undo" and len(args) == 1:
            found = undo(args[0])
        else:
            print("usage: checkpoints.py points SESSION | ask SESSION POINT | restore SESSION POINT LAST | "
                  "undo SESSION", file=sys.stderr)
            return 2
    except (OSError, ValueError) as err:
        found = {"error": str(err)}
    print(json.dumps(found))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
