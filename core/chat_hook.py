"""What Claude runs in herdr-fold's chats, passed with --settings (nothing installed, the user's own settings never
touched): its PermissionRequest hook, answered from the app through the chat's files, and its status line, whose
numbers it keeps for the app's bar. Without an answer in time it prints nothing, and Claude asks in its terminal."""
import json
import os
import sys
import time
import uuid

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import chat  # noqa: E402
import statefile  # noqa: E402
from conversations import obj, parse, text  # noqa: E402

TIMEOUT = 590                   # seconds the hook waits for the app: Claude gives it 600
NO = "The user said no."
# where a kept rule goes, by the scope the user chose: this conversation, this project (its local settings), everywhere
DESTINATION = {"session": "session", "project": "localSettings", "user": "userSettings"}
ASKED = ("tool_name", "tool_input", "permission_suggestions", "cwd")   # what the app's card is drawn from
DIALOG = ("ExitPlanMode",)      # Claude takes no hook's yes for these: its own dialog asks, the card answers there


def remove(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def post(request, kind):
    """REQUEST, the hook's input, put where the app sees it with a fresh id (KIND: permission, answered through the
    hook; dialog, in Claude's own); the request and its answer's paths."""
    folder = chat.chat_dir(text(request.get("session_id")))
    asked = {"id": uuid.uuid4().hex, "kind": kind, **{key: request.get(key) for key in ASKED}}
    paths = [os.path.join(folder, "request.json"), os.path.join(folder, "answer.json")]
    remove(paths[1])                                       # an answer to a request given up on
    statefile.write(paths[0], asked)
    return asked, paths


def wait_for(request, timeout=TIMEOUT, poll=0.2):
    """REQUEST posted, and the app's answer to it; None when none comes in TIMEOUT seconds or a newer request takes its
    place. Its files go after it, never another's."""
    asked, paths = post(request, "permission")
    end = time.monotonic() + timeout
    try:
        while time.monotonic() < end and (chat.read(paths[0]) or {}).get("id") == asked["id"]:
            reply = chat.read(paths[1]) or {}
            if reply.get("id") == asked["id"]:
                return reply
            time.sleep(poll)
        return None
    finally:
        for path in paths:
            if (chat.read(path) or {}).get("id") == asked["id"]:
                remove(path)


def claude_decision(request, reply):
    """The hook's answer to Claude for REQUEST from the app's REPLY: allow (keep: with the rule Claude suggested, kept
    where the user chose), the answers to its questions, or no with the user's words."""
    choice, tool = reply.get("choice"), request.get("tool_name")
    if choice not in ("allow", "keep"):
        decision = {"behavior": "deny", "message": text(reply.get("text")) or NO}
    elif tool == "AskUserQuestion":
        decision = {"behavior": "allow", "updatedInput": {**obj(request.get("tool_input")),
                                                          "answers": obj(reply.get("answers"))}}
    else:
        suggested = request.get("permission_suggestions")
        rule = obj(suggested[0]) if choice == "keep" and isinstance(suggested, list) and suggested else {}
        decision = {"behavior": "allow", **({"updatedPermissions": [
            {**rule, "destination": DESTINATION.get(reply.get("scope"), "session")}]} if rule else {})}
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}


def field(data, *keys):
    """The value at KEYS in Claude's JSON; None where it is missing."""
    for key in keys:
        data = obj(data).get(key)
    return data


def percent(value):
    """A percentage as a whole number; None if it is not a number."""
    return round(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def write_status(data):
    """The status line's numbers from DATA, Claude's status JSON, kept in the chat's status file for the app's bar (no
    folder, no prompt, nothing else of it), and the short line Claude shows."""
    model = text(field(data, "model", "display_name")) or text(field(data, "model", "id")) or "Claude"
    context = percent(field(data, "context_window", "used_percentage"))
    window = field(data, "context_window", "context_window_size")

    def limit(name):
        resets = field(data, "rate_limits", name, "resets_at")
        return {"used": percent(field(data, "rate_limits", name, "used_percentage")),
                "resets": resets if isinstance(resets, (int, float)) and not isinstance(resets, bool) else None}
    statefile.write(chat.status_path(text(data.get("session_id"))), {
        "context": context, "window": window if isinstance(window, int) else None, "model": model,
        "effort": text(field(data, "effort", "level")), "limits": {"five_hour": limit("five_hour"),
                                                                   "week": limit("seven_day")}, "at": int(time.time())})
    return model if context is None else f"{model} · ctx {context}%"


def main(argv):
    """Claude runs this with its input on stdin: permission (prints Claude's decision, or nothing) or status (prints
    the line). Anything wrong with the input prints nothing: Claude then goes on as without the hook."""
    if len(argv) != 2 or argv[1] not in ("permission", "status"):
        print("usage: chat_hook.py permission|status (Claude's JSON on stdin)", file=sys.stderr)
        return 2
    data = parse(sys.stdin.read())
    try:
        if argv[1] == "status":
            print(write_status(data))
        elif data.get("tool_name") in DIALOG:
            post(data, "dialog")
        else:
            reply = wait_for(data, TIMEOUT)
            if reply:
                print(json.dumps(claude_decision(data, reply)))
    except (ValueError, OSError):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
