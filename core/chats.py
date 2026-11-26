"""This machine's Claude Code, Codex, OpenCode and Copilot chats for Chats and the formatted copy: nothing of the
agents' or herdr's is written, and only a closed chat's own file leaves, for the Trash, on Delete… (delete). Each file
is read once, then only where it grew (INDEX); OpenCode's database is asked as it is. One unreadable is left out."""
import contextlib
import errno
import glob
import json
import os
import sqlite3
import stat
import sys
import unicodedata
import urllib.parse
from dataclasses import asdict, dataclass, replace

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import fileops  # noqa: E402
import statefile  # noqa: E402
from jsonl import claude_project_dir, newest_first, obj, open_regular, parse  # noqa: E402
from words import since  # noqa: E402

INDEX = "chat-index.json"             # what was read of each file, and where it stopped
SETTINGS = "chats.json"               # the list's settings, the archived chats among them
INDEX_VERSION = 4                     # another version's index (its shape, its types) is not read: the files are
# how Claude names a chat a program ran through the Agent SDK (its "entrypoint"): a hook's review of every change, a
# script's question, never the user's own chat. claude -p's (sdk-cli), the editors' and the desktop app's are listed
PROGRAMS = ("sdk-py", "sdk-ts")
PROMPT = 200                          # characters of a first prompt the index keeps: more than a row can ever show
RUNS = "runs.json"                    # in herdr-fold's state: the background sessions runs.py last listed (Runs')
FIRST_LINE = 1 << 20                  # bytes of a Codex file's first line read for its folder (some 23 KB in use)
TAIL = 8 << 20                        # bytes from a chat's end the formatted copy looks for a reply in
# a text that is not the user's own prompt: the agent's system text or a command (<…>), the project's notes, a note
# that a reply was cut off
NOT_A_PROMPT = ("<", "# AGENTS.md", "[Request interrupted")
# the agents whose chats are listed, and the word before an id each one's CLI reopens
NAMES = {"claude": "Claude", "codex": "Codex", "opencode": "OpenCode", "copilot": "Copilot"}
RESUME = {"claude": "--resume", "codex": "resume", "opencode": "--session", "copilot": "--resume"}
TRASHED = ("claude", "codex")         # those whose chat is a file of its own, which Delete… moves to the Trash
# why the others' are not: each keeps its chats its own way, its own command deletes one
KEPT = {"opencode": "OpenCode keeps its chats in its own database", "copilot": "Copilot keeps its chats in its own "
        "session store"}
WORKSPACE = 64 << 10                  # bytes of a Copilot chat's workspace.yaml read (some 400 in use)
# OpenCode's chats in its database (its V2 tables), each with its first prompt: its subagents' and those it archived
# left out (a scripted `opencode run --archived` too)
OPENCODE_CHATS = ("select id, title, directory, time_updated, (select data from session_message where session_id = "
                  "s.id and type = 'user' order by seq limit 1) from session_v2 s where parent_id is null and "
                  "time_archived is null")
# an OpenCode chat's turns in order: the user's text in its message, a reply's in its text parts
OPENCODE_TURNS = ("select m.id, m.type, m.data, p.data from session_message m left join session_part p on "
                  "p.message_id = m.id and p.type = 'text' where m.session_id = ? and m.type in ('user', 'assistant') "
                  "order by m.seq, p.ordinal")


@dataclass(frozen=True)
class Chat:
    agent: str              # claude, codex, opencode or copilot
    id: str                 # its session, as its agent's CLI reopens it (RESUME's word, then this)
    title: str
    folder: str             # where it was started
    time: float             # when it last changed
    state: str = ""         # a running one's state as herdr names it (working, blocked, done, idle); "" if closed
    pane: str = ""          # a running one's herdr pane


# --- the files

def text(value):
    return value if isinstance(value, str) else None


def read_jsonl(path, tail=None):
    """The entries of a JSON-lines file (TAIL: of its last TAIL bytes only, from the first whole line there); damaged
    lines are skipped."""
    with open_regular(path, "rb") as f:
        if tail is not None:
            start = max(0, os.fstat(f.fileno()).st_size - tail)
            f.seek(start)
            if start:
                f.readline()                          # the rest of a line cut by the start
        for raw in f:
            entry = parse(raw.decode("utf-8", "replace"))
            if entry:
                yield entry


def once(paths):
    """PATHS without the files a linked folder lists again (a project's folder linked to another's, to share its
    chats, holds each of them twice): each file by its real folder's path, as found before a link's."""
    real = {}
    for folder in {os.path.dirname(path) for path in paths}:
        real[folder] = (os.path.islink(folder), os.path.realpath(folder))
    kept = {}
    for path in sorted(paths, key=lambda path: real[os.path.dirname(path)][0]):
        kept.setdefault((real[os.path.dirname(path)][1], os.path.basename(path)), path)
    return list(kept.values())


def claude_files():
    return once(glob.glob(os.path.join(os.path.expanduser("~"), ".claude", "projects", "*", "*.jsonl")))


def codex_session_files():
    """Every Codex chat file (sessions/<year>/<month>/<day>/rollout-*.jsonl)."""
    return glob.glob(os.path.join(os.path.expanduser("~"), ".codex", "sessions", "*", "*", "*", "rollout-*.jsonl"))


def copilot_home():
    """Copilot's own folder: COPILOT_HOME, as Copilot takes it, else ~/.copilot."""
    return os.environ.get("COPILOT_HOME") or os.path.join(os.path.expanduser("~"), ".copilot")


def copilot_files():
    """Every Copilot chat's event log (session-state/<id>/events.jsonl)."""
    return glob.glob(os.path.join(glob.escape(copilot_home()), "session-state", "*", "events.jsonl"))


def session_files(kind, session):
    """The files of one chat: KIND is claude, codex or copilot, SESSION its id."""
    home = os.path.expanduser("~")
    if kind == "claude":
        return once(glob.glob(os.path.join(home, ".claude", "projects", "*", f"{session}.jsonl")))
    if kind == "codex":
        return glob.glob(os.path.join(home, ".codex", "sessions", "*", "*", "*", f"*{session}.jsonl"))
    if kind == "copilot" and fileops.CHAT_ID.fullmatch(session):
        path = os.path.join(copilot_home(), "session-state", session, "events.jsonl")
        return [path] if os.path.isfile(path) else []
    return []


def folder_files(kind, folder):
    """The files of the chats started in FOLDER, the newest first (read as needed): KIND is claude or codex.
    Codex's own helpers (subagents, such as its approvals reviewer) are left out."""
    if kind == "claude":
        paths = glob.glob(os.path.join(claude_project_dir(folder), "*.jsonl"))
    elif kind == "codex":
        paths = codex_session_files()
    else:
        return
    for path in newest_first(paths):
        if kind == "codex":
            try:
                with open_regular(path, encoding="utf-8", errors="replace") as f:
                    meta = obj(parse(f.readline(FIRST_LINE)).get("payload"))
            except OSError:
                continue
            if meta.get("cwd") != folder or isinstance(meta.get("source"), dict):
                continue
        yield path


# --- what a file holds

def first_prompt(texts):
    """The first line of the first text that is the user's own."""
    return next((text.strip().splitlines()[0] for text in texts
                 if text.strip() and not text.lstrip().startswith(NOT_A_PROMPT)), "")


def texts_of(content):
    """The texts of a message's content: a text itself, or a list of parts with texts."""
    if isinstance(content, str):
        return [content]
    return [block["text"] for block in content if isinstance(block, dict) and isinstance(block.get("text"), str)] \
        if isinstance(content, list) else []


def parts(content, kind):
    """The texts of CONTENT's parts of KIND (text, output_text, input_text)."""
    return [block["text"] for block in content if isinstance(block, dict) and block.get("type") == kind
            and isinstance(block.get("text"), str)] if isinstance(content, list) else []


def messages(kind, path, tail=None):
    """The chat in PATH (KIND claude, codex or copilot) as (role, text), in order: "user" for the user's own prompts,
    "assistant" for each part of a reply; no tool call, result, system text, helper's or subagent's line, nor what a
    compacted Claude chat holds again (its summary in the user's place, the messages anew). TAIL: read_jsonl's."""
    seen = set()
    for entry in read_jsonl(path, tail):
        if kind == "claude":
            if entry.get("isSidechain") or entry.get("isMeta") or entry.get("isCompactSummary") \
                    or entry.get("type") not in ("user", "assistant"):
                continue
            again = entry.get("uuid")
            if isinstance(again, str):
                if again in seen:
                    continue
                seen.add(again)
            role, content = entry["type"], obj(entry.get("message")).get("content")
            texts = parts(content, "text") if role == "assistant" else texts_of(content)
        elif kind == "copilot":
            if entry.get("type") not in ("user.message", "assistant.message") or "agentId" in entry:
                continue
            role, texts = entry["type"].split(".")[0], texts_of(obj(entry.get("data")).get("content"))
        else:
            payload = obj(entry.get("payload"))
            role = payload.get("role")
            if payload.get("type") != "message" or role not in ("user", "assistant"):
                continue
            texts = parts(payload.get("content"), "output_text" if role == "assistant" else "input_text")
        for text in texts:
            if text.strip() and not (role == "user" and text.lstrip().startswith(NOT_A_PROMPT)):
                yield role, text


def markdown(item):
    """ITEM's chat as Markdown, its title, then each turn under who said it, the parts of a turn together; None where
    its file (OpenCode's rows) is gone. No control character but line breaks and tabs: pasted into a terminal, a code
    the chat holds would run there."""
    if item.agent == "opencode":
        said = list(opencode_messages(item.id))
    else:
        paths = session_files(item.agent, item.id)
        said = list(messages(item.agent, paths[0])) if paths else []
    if not said:
        return None
    who = {"user": "You", "assistant": NAMES[item.agent]}
    turns = []
    for role, text in said:
        if turns and turns[-1][0] == role:
            turns[-1][1].append(text.strip())
        else:
            turns.append((role, [text.strip()]))
    parts = [f"# {item.title}"]
    for role, texts in turns:
        parts += [f"**{who[role]}**", *texts]
    text = "\n\n".join(parts) + "\n"
    return "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch) != "Cc")


def read_claude(entry, raw):
    """What a line of a Claude chat adds: the latest rename and AI title, the first prompt, the folder, and whether
    a program ran it (PROGRAMS: the line of its first prompt says how it was started)."""
    if b'"type":"custom-title"' in raw:
        entry["custom"] = text(parse(raw).get("customTitle")) or entry.get("custom")
    elif b'"type":"ai-title"' in raw:
        entry["ai"] = text(parse(raw).get("aiTitle")) or entry.get("ai")
    elif "prompt" not in entry and b'"type":"user"' in raw and b'"isSidechain":false' in raw:
        message = parse(raw)
        entry["folder"] = entry.get("folder") or text(message.get("cwd"))
        entry["prompt"] = first_prompt(texts_of(obj(message.get("message")).get("content")))[:PROMPT] or None
        if not entry["prompt"]:
            del entry["prompt"]
        elif message.get("entrypoint") in PROGRAMS:
            entry["helper"] = True


def read_codex(entry, raw):
    """What a line of a Codex chat adds: its id, folder, whether it is a helper or a run of `codex exec` (Runs', the
    first line), then the first prompt, after which nothing more is needed (its name lives in session_index.jsonl)."""
    if "id" not in entry:
        meta = obj(parse(raw).get("payload"))
        entry.update(id=text(meta.get("id")) or "", folder=text(meta.get("cwd")) or "",
                     helper=isinstance(meta.get("source"), dict))
        if meta.get("source") == "exec":
            entry["run"] = True
    elif b'"role":"user"' in raw:
        payload = obj(parse(raw).get("payload"))
        if payload.get("type") == "message" and payload.get("role") == "user":
            prompt = first_prompt(parts(payload.get("content"), "input_text"))[:PROMPT]
            if prompt:
                entry.update(prompt=prompt, done=True)


def read_copilot(entry, raw):
    """What a line of a Copilot chat's event log adds: its folder (session.start's), then the first prompt of the user's
    (a subagent's lines, with their agentId, left out), after which nothing more is needed (its name: workspace())."""
    if "folder" not in entry and b'"type":"session.start"' in raw:
        entry["folder"] = text(obj(obj(parse(raw).get("data")).get("context")).get("cwd")) or ""
    elif b'"type":"user.message"' in raw:
        event = parse(raw)
        if event.get("type") == "user.message" and "agentId" not in event:
            prompt = first_prompt([text(obj(event.get("data")).get("content")) or ""])[:PROMPT]
            if prompt:
                entry.update(prompt=prompt, done=True)


def workspace(path):
    """What a Copilot chat's workspace.yaml beside its event log PATH tells, its flat keys as Copilot writes them: its
    name (yours, else the one Copilot gave it) and its folder, where it resumes; {} where it cannot be read."""
    try:
        with open_regular(os.path.join(os.path.dirname(path), "workspace.yaml"), encoding="utf-8",
                          errors="replace") as f:
            lines = f.read(WORKSPACE).split("\n")
    except OSError:
        return {}
    found, key = {}, None
    for line in lines:
        if key and line[:1] in (" ", "\t") and line.strip():          # a long value folded onto the next line
            found[key] += " " + line.strip()
            continue
        name, colon, value = line.partition(":")
        key = name if colon and name in ("name", "cwd") else None
        if key:
            found[key] = value.strip()
    for key, value in found.items():
        try:
            found[key] = json.loads(value) if value[:1] == '"' else value[1:-1].replace("''", "'") \
                if value[:1] == "'" else value
        except ValueError:
            found[key] = ""
    return {key: value for key, value in found.items() if isinstance(value, str) and value}


def update(path, kind, entry):
    """ENTRY, what INDEX has of PATH, brought up to date: read from where it stopped, whole lines only (one still being
    written waits for the next time); from the start again when the file got shorter. None if PATH is gone or cannot be
    read."""
    try:
        info = os.stat(path)
    except OSError:
        return None
    if not stat.S_ISREG(info.st_mode):
        return None
    if entry.get("size") == info.st_size and entry.get("mtime") == info.st_mtime:
        return entry
    entry = dict(entry) if entry.get("offset", 0) <= info.st_size else {}
    offset = entry.get("offset", 0)
    if not entry.get("done"):
        read = {"claude": read_claude, "codex": read_codex, "copilot": read_copilot}[kind]
        try:
            with open_regular(path, "rb") as f:
                f.seek(offset)
                for raw in f:
                    if not raw.endswith(b"\n"):
                        break
                    offset += len(raw)
                    read(entry, raw)
                    if entry.get("done"):
                        break
        except OSError:
            return None
    entry.update(offset=offset, size=info.st_size, mtime=info.st_mtime)
    return entry


# --- OpenCode's database

def opencode_db():
    """OpenCode's database, which holds its chats: under XDG_DATA_HOME, as OpenCode takes it, else ~/.local/share."""
    data = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(data, "opencode", "opencode.db")


def opencode_rows(query, *args):
    """QUERY's rows (ARGS its values) in OpenCode's database, opened read-only; none where it is not there or cannot be
    read (busy past a second, another version's tables)."""
    try:
        with contextlib.closing(sqlite3.connect(f"file:{urllib.parse.quote(opencode_db())}?mode=ro", uri=True,
                                                timeout=1)) as db:
            return db.execute(query, args).fetchall()
    except sqlite3.Error:
        return []


def opencode_chats(names):
    """OpenCode's chats with a prompt of the user's (OPENCODE_CHATS'), named as AI Sessions names them, else as
    OpenCode does, else by that prompt."""
    found = []
    for id, title, folder, updated, first in opencode_rows(OPENCODE_CHATS):
        prompt = first_prompt([text(parse(first or "").get("text")) or ""])[:PROMPT]
        if isinstance(id, str) and prompt and isinstance(updated, (int, float)):
            found.append(Chat("opencode", id, names.get(id) or text(title) or prompt, text(folder) or "",
                              updated / 1000))
    return found


def opencode_messages(session):
    """OpenCode's chat SESSION as messages() gives one: the user's prompts and each text part of a reply, in order."""
    seen = set()
    for message, role, data, part in opencode_rows(OPENCODE_TURNS, session):
        if role == "user" and message in seen:
            continue
        seen.add(message)
        said = text(parse(data if role == "user" else part or "").get("text"))
        if said and said.strip():
            yield role, said


# --- the names given elsewhere

def names_path():
    """Where herdr-fold's AI Sessions keeps each chat's name, and whose it is (sessions-view's names.json)."""
    return os.path.join(os.path.expanduser("~"), ".local", "state", "herdr", "plugins", "herdr-fold.sessions-view",
                        "names.json")


def manual_names():
    """Names given by hand (herdr's Rename pane, the column's Rename), as AI Sessions keeps them:
    {session: name}."""
    try:
        with open(names_path(), encoding="utf-8") as f:
            names = json.load(f)
    except (OSError, ValueError):
        return {}
    return {key: entry["name"] for key, entry in names.items() if isinstance(entry, dict)
            and not entry.get("given") and isinstance(entry.get("name"), str)} if isinstance(names, dict) else {}


@contextlib.contextmanager
def names_lock():
    """AI Sessions' own lock on its names (sessions-view's names_lock): one writer at a time."""
    path = names_path() + ".lock"
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with open(path, "a+b") as f:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def name_session(session, name):
    """SESSION named NAME by hand, as herdr's Rename pane names one, where AI Sessions keeps such names: under
    its lock, the other names as they are, the file written whole. One that cannot be read stays as it is (OSError):
    AI Sessions sets it aside, its names kept."""
    with names_lock():
        try:
            with open(names_path(), encoding="utf-8") as f:
                names = json.load(f)
        except FileNotFoundError:
            names = {}
        except (ValueError, RecursionError) as err:
            raise OSError(errno.EINVAL, "the names file cannot be read", names_path()) from err
        if not isinstance(names, dict):
            raise OSError(errno.EINVAL, "the names file cannot be read", names_path())
        names[session] = {"name": name, "given": False}
        statefile.write(names_path(), names, ensure_ascii=False)


def forget_name(session):
    """SESSION's name dropped where AI Sessions keeps them, the others as they are; no file made where there is
    none, one that cannot be read left as it is."""
    if not os.path.exists(names_path()):
        return
    with names_lock():
        try:
            with open(names_path(), encoding="utf-8") as f:
                names = json.load(f)
        except (OSError, ValueError, RecursionError):
            return
        if isinstance(names, dict) and names.pop(session, None) is not None:
            statefile.write(names_path(), names, ensure_ascii=False)


def codex_names():
    """Thread names given with Codex's /rename (the latest one wins)."""
    names = {}
    try:
        for entry in read_jsonl(os.path.join(os.path.expanduser("~"), ".codex", "session_index.jsonl")):
            if isinstance(entry.get("thread_name"), str) and isinstance(entry.get("id"), str):
                names[entry["id"]] = entry["thread_name"]
    except OSError:
        pass
    return names


# --- the list

def load_index(state_dir):
    """What was read of each file, {path: entry}; nothing of another version's index."""
    try:
        with open(os.path.join(state_dir, INDEX), encoding="utf-8") as f:
            index = obj(json.load(f))
    except (OSError, ValueError, RecursionError):
        return {}
    if index.get("version") != INDEX_VERSION:
        return {}
    return {path: entry for path, entry in obj(index.get("files")).items() if isinstance(entry, dict)}


def save_index(state_dir, index):
    """Written whole, its owner's only (statefile.py): another pane reading it meanwhile sees the old one or the new."""
    try:
        statefile.write(os.path.join(state_dir, INDEX), {"version": INDEX_VERSION, "files": index})
    except OSError:
        pass                                    # read again next time


def chat(kind, path, entry, names, threads, runs=frozenset()):
    """The chat ENTRY describes; None for a file without a prompt of the user's, for Codex's helpers and a program's
    run of Claude, and for what Runs lists instead: a run of `codex exec`, a background session of RUNS'."""
    if not entry.get("prompt") or entry.get("helper") or entry.get("run"):
        return None
    if kind == "claude":
        session = os.path.basename(path)[:-len(".jsonl")]
        if session in runs:
            return None
        title = names.get(session) or entry.get("custom") or entry.get("ai") or entry["prompt"]
    elif kind == "copilot":                             # its folder its id, as Copilot names it
        session, own = os.path.basename(os.path.dirname(path)), workspace(path)
        return Chat(kind, session, names.get(session) or own.get("name") or entry["prompt"],
                    own.get("cwd") or entry.get("folder") or "", entry["mtime"])
    else:
        session = entry.get("id")
        if not session:
            return None
        title = names.get(session) or threads.get(session) or entry["prompt"]
    return Chat(kind, session, title, entry.get("folder") or "", entry["mtime"])


def running(found, agents, resumed=None):
    """FOUND with the running ones marked, from AGENTS (herdr's agent list): by the session herdr was told of, the one
    reopened in its pane (RESUMED: {pane: chat id}) until herdr is told, or else the newest chat of
    its kind in its folder."""
    told, untold = {}, {}
    for agent in agents:
        if agent.get("agent") not in NAMES:
            continue
        seen = (agent.get("agent_status") or "", agent.get("pane_id") or "")
        session = (agent.get("agent_session") or {}).get("value") or (resumed or {}).get(agent.get("pane_id"))
        if session:
            told[session] = seen
        else:
            untold.setdefault((agent["agent"], agent.get("cwd")), seen)
    marked = []
    for item in found:                                  # the newest first
        seen = told.get(item.id) or untold.pop((item.agent, item.folder), None)
        marked.append(replace(item, state=seen[0], pane=seen[1]) if seen else item)
    return marked


def indexed(state_dir):
    """Every chat file's entry, {path: (kind, entry)}, the index brought up to date and kept."""
    index, fresh, found = load_index(state_dir), {}, {}
    for kind, paths in (("claude", claude_files()), ("codex", codex_session_files()), ("copilot", copilot_files())):
        for path in paths:
            entry = update(path, kind, index.get(path, {}))
            if entry is not None:
                fresh[path], found[path] = entry, (kind, entry)
    if fresh != index:
        save_index(state_dir, fresh)
    return found


def background():
    """The sessions of Claude's background runs as runs.py last listed them (Runs lists them, not Chats)."""
    found = statefile.read(os.path.join(statefile.folder(), RUNS)).get("sessions")
    return frozenset(one for one in found if isinstance(one, str)) if isinstance(found, list) else frozenset()


def local(state_dir, agents=(), resumed=None):
    """This machine's chats, the newest first; AGENTS: herdr's agent list, and RESUMED, the chats
    reopened in panes herdr knows no session of yet ({pane: id}), for the running ones."""
    names, threads, runs = manual_names(), codex_names(), background()
    found = [item for item in (chat(kind, path, entry, names, threads, runs)
                               for path, (kind, entry) in indexed(state_dir).items()) if item] + opencode_chats(names)
    return running(sorted(found, key=lambda item: item.time, reverse=True), agents, resumed)


def setting(state_dir):
    """The list's settings, {} when there are none or they cannot be read."""
    return statefile.read(os.path.join(state_dir, SETTINGS))


def change(state_dir, how):
    """SETTINGS changed by HOW (given what it holds then, its answer kept) under statefile.update: every tab's sidebar
    and the app's helper write it. Nothing when it cannot be written."""
    try:
        statefile.update(os.path.join(state_dir, SETTINGS), how)
    except OSError:
        pass


def keep(state_dir, **values):
    """VALUES kept in SETTINGS, the rest staying."""
    change(state_dir, lambda kept: {**kept, **values})


def archived(state_dir):
    """The chats taken off the list, as "<agent>:<id>"."""
    return archived_in(setting(state_dir))


def archived_in(kept):
    found = kept.get("archived")
    return {key for key in found if isinstance(key, str)} if isinstance(found, list) else set()


def archive(state_dir, keys, off=True):
    """The chats KEYS ("<agent>:<id>") off the list (OFF), or back on it; their files stay as they are."""
    change(state_dir, lambda kept: {**kept, "archived": sorted(archived_in(kept) | keys if off
                                                               else archived_in(kept) - keys)})


def own_files(kind, session):
    """Chat SESSION's own files: session_files', a Codex one only if its first line names SESSION (another's name
    may end as this id does)."""
    found = []
    for path in session_files(kind, session):
        if kind == "codex":
            entry = {}
            try:
                with open_regular(path, "rb") as f:
                    read_codex(entry, f.readline(FIRST_LINE))
            except OSError:
                continue
            if entry.get("id") != session:
                continue
        found.append(path)
    return found


def delete(state_dir, kind, session, agents=(), resumed=None, **how):
    """Chat SESSION of KIND deleted: its own file to the system's Trash (fileops.trash_chat, HOW its stand-ins), then
    its archive and its name dropped. Only a chat of the list, never a running one (AGENTS, RESUMED: local()'s):
    fileops.Refused says why not, nothing moved or dropped then."""
    listed = local(state_dir, agents, resumed) if kind in TRASHED and fileops.CHAT_ID.fullmatch(session) else []
    item = next((one for one in listed if (one.agent, one.id) == (kind, session)), None)
    paths = own_files(kind, session) if item else []
    if not paths:
        raise fileops.Refused("no such chat in the list")
    if item.state or item.pane:
        raise fileops.Refused("the chat is running: close it first")
    for path in paths:
        where = fileops.trash_chat(kind, session, path, **how)
    archive(state_dir, {f"{kind}:{session}"}, off=False)
    with contextlib.suppress(OSError):
        forget_name(session)
    return where


def said(err):
    """Why a chat was not deleted, as a line to show."""
    words = str(err) or type(err).__name__
    return words[:1].upper() + words[1:]


def state_folder():
    return os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.join(os.path.expanduser("~"), ".local", "state",
                                                                    "herdr", "plugins", "herdr-fold.sidebar")


def main(argv):
    """The Herdr app mod's, on the Mac, answering in JSON: list AGENTS RESUMED (herdr's agents and {pane: id}, as JSON:
    the running ones marked, how long ago each changed), rename SESSION NAME, archive|unarchive KEY… ("<agent>:<id>"),
    markdown AGENT ID (Copy chat's) and delete AGENT ID AGENTS RESUMED (a closed one's file to the Trash, or why)."""
    command, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    state = state_folder()
    try:
        if command in ("list", "delete") and len(args) == (2 if command == "list" else 4):
            agents, resumed = json.loads(args[-2]), json.loads(args[-1])
            if not isinstance(agents, list) or not isinstance(resumed, dict):
                raise ValueError("not a list")
        if command == "list" and len(args) == 2:
            listed = local(state, agents, resumed)
            answer = {"chats": [{**asdict(item), "ago": since(item.time)} for item in listed],
                      "archived": sorted(archived(state))}
        elif command == "rename" and len(args) == 2:
            try:
                name_session(args[0], args[1])
                answer = {"ok": True, "advice": None}
            except OSError as err:
                answer = {"ok": False, "advice": f"The name could not be kept: {err.strerror or err}"}
        elif command in ("archive", "unarchive") and args:
            archive(state, set(args), command == "archive")
            answer = {"ok": True}
        elif command == "delete" and len(args) == 4:
            try:
                delete(state, args[0], args[1], agents, resumed)
                answer = {"ok": True}
            except OSError as err:                      # Refused too: the line to show
                answer = {"ok": False, "advice": said(err)}
        elif command == "markdown" and len(args) == 2:
            item = next((c for c in local(state) if (c.agent, c.id) == tuple(args)), None)
            answer = {"markdown": markdown(item) if item else None}
        else:
            raise ValueError("unknown command")
    except (ValueError, TypeError, AttributeError):
        print("usage: chats.py list AGENTS RESUMED | rename SESSION NAME | archive|unarchive KEY… | markdown "
              "AGENT ID | delete AGENT ID AGENTS RESUMED", file=sys.stderr)
        return 2
    print(json.dumps(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
