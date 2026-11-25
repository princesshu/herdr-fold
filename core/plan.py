"""A chat's task list and its approved plan, read from the agent's own file: Claude's task tools and the plan its
plan mode had approved, Codex's update_plan. One list for both clients, in the words they show; a field of a wrong
type is missing."""
import copy
import os
import re
import sys
import tempfile

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
from chats import NOT_A_PROMPT, obj, open_regular, parse, parts, text, texts_of          # noqa: E402

TASKS = ("TaskCreate", "TaskUpdate", "TaskList", "TaskGet")     # Claude's task tools: the list's, no step of their own
CREATED = re.compile(r"Task #(\S+) created successfully")       # a new task's number, in its call's answer
STATES = {"pending": "next", "in_progress": "now", "completed": "done"}     # a step's state, by either agent's word
NUMBERED = re.compile(r"^\d+[.)]\s", re.M)                      # a step of a plan's own numbered list
DOC = "plan.md"                 # the approved plan as herdr-fold keeps it for the preview
# what a line of a chat's file holds when it may change the list (the rest is never read as JSON)
LINES = {"claude": (b'"TaskCreate"', b'"TaskUpdate"', b"created successfully", b'"plan"'), "codex": (b'"update_plan"',)}
PROMPTS = {"claude": b'"type":"user"', "codex": b'"role":"user"'}           # a line that may be the person's message


def new():
    """A chat's list before its first line: its tasks in order, the ones Claude has not numbered yet by their call,
    Codex's note, and the steps of the plan approved last (None: none)."""
    return {"tasks": [], "asked": {}, "note": None, "plan": None}


def finished(state):
    return bool(state["tasks"]) and all(task["status"] == "completed" for task in state["tasks"])


def prompted(state):
    """The person's next message: a finished list goes, one with work left stays."""
    if finished(state):
        state["tasks"], state["note"] = [], None


def approved(entry):
    """The plan ENTRY (a line of Claude's) says was approved: ExitPlanMode's answer holds its text; None for any other
    line, and for a plan turned down."""
    result, content = obj(entry.get("toolUseResult")), obj(entry.get("message")).get("content")
    blocks = [block for block in map(obj, content if isinstance(content, list) else [])
              if block.get("type") == "tool_result"]
    words = text(result.get("plan"))
    if not words or not words.strip() or text(result.get("filePath")) is None or len(blocks) != 1 \
            or blocks[0].get("is_error") is True:
        return None
    return words, text(blocks[0].get("tool_use_id"))


def update(state, args):
    """Claude's TaskUpdate with ARGS: the task renamed, moved on, waiting for others or deleted; whether it is done
    now and was not."""
    names = [text(args.get(key)) for key in ("taskId", "subject", "status")]
    task = next((one for one in state["tasks"] if one["id"] == names[0]), None)
    if task is None:
        return False
    if names[2] == "deleted":
        state["tasks"].remove(task)
        return False
    was = task["status"]
    task["text"] = names[1] or task["text"]
    task["status"] = names[2] if names[2] in STATES else was
    ids = {key: [one for one in args.get(key) if isinstance(one, str)] if isinstance(args.get(key), list) else []
           for key in ("addBlockedBy", "addBlocks")}
    task["after"] += [one for one in ids["addBlockedBy"] if one not in task["after"]]
    for other in state["tasks"]:
        if other["id"] in ids["addBlocks"] and task["id"] not in other["after"]:
            other["after"].append(task["id"])
    return task["status"] == "completed" != was


def claude(state, entry):
    """ENTRY (a line of Claude's own chat, not a helper's) folded into STATE; what the timeline tells of it, by its
    call: a task added, a step done (a step of their kinds), an approved plan's count of steps."""
    told = {}
    if entry.get("isSidechain") or entry.get("isMeta") or entry.get("isCompactSummary"):
        return told
    kind, content = entry.get("type"), obj(entry.get("message")).get("content")
    blocks = [block for block in map(obj, content if isinstance(content, list) else [])]
    if kind == "assistant":
        for block in blocks:
            name, args, call_id = block.get("name"), obj(block.get("input")), text(block.get("id"))
            if block.get("type") != "tool_use" or not call_id:
                continue
            if name == "TaskCreate":
                state["asked"][call_id] = text(args.get("subject")) or ""
                told[call_id] = {"kind": "tasks", "id": call_id, "added": 1}
            elif name == "TaskUpdate" and update(state, args):
                told[call_id] = {"kind": "task", "id": call_id, "text": next(
                    task["text"] for task in state["tasks"] if task["id"] == text(args.get("taskId")))}
    elif kind == "user":
        for block in blocks:
            asked = state["asked"].pop(text(block.get("tool_use_id")), None) if block.get("type") == "tool_result" \
                else None
            made = CREATED.search("\n".join(texts_of(block.get("content")))) if asked is not None else None
            if made and block.get("is_error") is not True:
                state["tasks"] = [task for task in state["tasks"] if task["id"] != made.group(1)]
                state["tasks"].append({"id": made.group(1), "text": asked, "status": "pending", "after": []})
        plan = approved(entry)
        if plan:
            state["plan"] = len(NUMBERED.findall(plan[0]))
            told[plan[1]] = state["plan"]
        elif any(part.strip() and not part.lstrip().startswith(NOT_A_PROMPT) for part in texts_of(content)):
            prompted(state)
    return told


def codex(state, entry):
    """ENTRY (a line of a Codex rollout) folded into STATE: an update_plan is the whole list anew, with its note."""
    payload = obj(entry.get("payload"))
    if payload.get("type") == "function_call" and payload.get("name") == "update_plan":
        args = parse(text(payload.get("arguments")) or "")
        if isinstance(args.get("plan"), list):
            state["note"] = text(args.get("explanation"))
            state["tasks"] = [{"id": str(n), "text": text(step.get("step")) or "", "after": [],
                               "status": step.get("status") if step.get("status") in STATES else "pending"}
                              for n, step in enumerate(map(obj, args["plan"]))]
    elif payload.get("type") == "message" and payload.get("role") == "user" and any(
            part.strip() and not part.lstrip().startswith(NOT_A_PROMPT)
            for part in parts(payload.get("content"), "input_text")):
        prompted(state)


def shown(state):
    """STATE as both clients show it: its steps in order (done, now or next; what one waits for), the note, how many
    are done in the folded strip's words and the done row's, an approved plan's steps; None while it has no list."""
    tasks = state["tasks"]
    if not tasks:
        return None
    left = {task["id"]: task["text"] for task in tasks if task["status"] != "completed"}
    done = len(tasks) - len(left)

    def after(task):
        waits = [left[one] for one in task["after"] if one in left and task["id"] in left]
        return None if not waits else f"after {waits[0]}" if len(waits) == 1 else f"after {len(waits)} steps"
    return {"steps": [{"text": task["text"], "state": STATES[task["status"]], "after": after(task)} for task in tasks],
            "note": state["note"], "done": f"{done} done" if done else None, "finished": not left,
            "count": f"{done} of {len(tasks)} done" if left else f"All {done} done", "plan": state["plan"]}


def lines(kind, path, offset, end, state):
    """The lines of PATH from byte OFFSET (to END; None: its end) that may change STATE as entries (None for the rest),
    each with the offset after it: the person's messages only while a finished list waits for one; a line still being
    written is left."""
    with open_regular(path, "rb") as f:
        f.seek(offset)
        for raw in f:
            offset += len(raw)
            if not raw.endswith(b"\n") or end is not None and offset > end:
                return
            if any(mark in raw for mark in LINES[kind]) or finished(state) and PROMPTS[kind] in raw:
                yield parse(raw), offset
            else:
                yield None, offset


def read(kind, path, was=None, end=None):
    """The list of the chat in PATH (KIND: claude or codex) read on from WAS, an earlier read's answer (None: from its
    start), to byte END at most: its state, where the read stopped, the ids of the lines read (one Claude writes again
    is not read twice). A file that cannot be read keeps what was."""
    got = copy.deepcopy(was) if was else {"state": new(), "offset": 0, "ids": []}
    state, ids = got["state"], set(got["ids"])
    try:
        for entry, offset in lines(kind, path, got["offset"], end, state) if path else ():
            got["offset"], one = offset, entry.get("uuid") if entry else None
            if entry and one not in ids:
                ids.update([one] if isinstance(one, str) else [])
                (claude if kind == "claude" else codex)(state, entry)
    except OSError:
        pass
    return {**got, "ids": sorted(ids)}


def document(path, folder):
    """The plan approved last in Claude's chat file PATH, kept as DOC in FOLDER (herdr-fold's own, its owner's only):
    its path there; None for a chat with none, and nothing written."""
    words = None
    try:
        with open_regular(path, "rb") as f:
            for raw in f:
                found = approved(parse(raw)) if b'"plan"' in raw else None
                words = found[0] if found else words
    except OSError:
        return None
    if words is None:
        return None
    os.makedirs(folder, mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=folder, prefix=f".{DOC}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(words.rstrip("\n") + "\n")
    os.replace(temporary, os.path.join(folder, DOC))
    return os.path.join(folder, DOC)
