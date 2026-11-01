"""This machine's Claude Code and Codex conversations, running or not, for the Conversations column and herdr-fold's
formatted copy; nothing of Claude's, Codex's or herdr's is ever written. The files are large: each is read once, then
only where it grew (INDEX, shared by every pane). An unreadable file is left out, a field of a wrong type as missing."""
import contextlib
import errno
import glob
import json
import os
import re
import stat
import unicodedata
from dataclasses import dataclass, replace

import statefile

INDEX = "conversation-index.json"     # what was read of each file, and where it stopped
INDEX_VERSION = 2                     # another version's index (its shape, its types) is not read: the files are
PROMPT = 200                          # characters of a first prompt the index keeps: more than a row can ever show
FIRST_LINE = 1 << 20                  # bytes of a Codex file's first line read for its folder (some 23 KB in use)
TAIL = 8 << 20                        # bytes from a conversation's end the formatted copy looks for a reply in
# a text that is not the user's own prompt: the agent's system text or a command (<…>), the project's notes, a note
# that a reply was cut off
NOT_A_PROMPT = ("<", "# AGENTS.md", "[Request interrupted")


@dataclass(frozen=True)
class Conversation:
    agent: str              # claude or codex
    id: str                 # its session: claude --resume ID, codex resume ID
    title: str
    folder: str             # where it was started
    time: float             # when it last changed
    state: str = ""         # a running one's state as herdr names it (working, blocked, done, idle); "" if closed
    pane: str = ""          # a running one's herdr pane


# --- the files

def open_regular(path, *args, **kwargs):
    """open(PATH, *ARGS, **KWARGS) for reading, a regular file only (OSError otherwise): a pipe named like a
    conversation would hold the reader for good, so it is opened without waiting, then refused."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(errno.EINVAL, "not a regular file", path)
        return os.fdopen(fd, *args, **kwargs)
    except BaseException:
        os.close(fd)
        raise


def obj(value):
    return value if isinstance(value, dict) else {}


def text(value):
    return value if isinstance(value, str) else None


def parse(line):
    """One JSON line (text or bytes) as a dict; a damaged line (cut off, stray bytes, nested too deep, not an object)
    is empty."""
    try:
        entry = json.loads(line)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return {}
    return entry if isinstance(entry, dict) else {}


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


def claude_project_dir(folder):
    """Claude's folder for the conversations started in FOLDER: every character but a letter, digit or - becomes -."""
    return os.path.join(os.path.expanduser("~"), ".claude", "projects", re.sub(r"[^A-Za-z0-9-]", "-", folder))


def claude_files():
    return glob.glob(os.path.join(os.path.expanduser("~"), ".claude", "projects", "*", "*.jsonl"))


def codex_session_files():
    """Every Codex conversation file (sessions/<year>/<month>/<day>/rollout-*.jsonl)."""
    return glob.glob(os.path.join(os.path.expanduser("~"), ".codex", "sessions", "*", "*", "*", "rollout-*.jsonl"))


def session_files(kind, session):
    """The files of one conversation: KIND is claude or codex, SESSION its id."""
    home = os.path.expanduser("~")
    if kind == "claude":
        return glob.glob(os.path.join(home, ".claude", "projects", "*", f"{session}.jsonl"))
    if kind == "codex":
        return glob.glob(os.path.join(home, ".codex", "sessions", "*", "*", "*", f"*{session}.jsonl"))
    return []


def newest_first(paths):
    """PATHS that are regular files, the most recently changed first."""
    found = []
    for path in paths:
        try:
            info = os.stat(path)
        except OSError:
            continue
        if stat.S_ISREG(info.st_mode):
            found.append((info.st_mtime, path))
    return [path for _, path in sorted(found, key=lambda pair: pair[0], reverse=True)]


def folder_files(kind, folder):
    """The files of the conversations started in FOLDER, the newest first (read as needed): KIND is claude or codex.
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
    """The messages of the conversation in PATH (KIND claude or codex), in order, as (role, text): role "user" for the
    user's own prompts, "assistant" for the agent's replies, one per part of a reply; tool calls, their results, system
    text and the lines of the agent's helpers left out. TAIL: of the file's last TAIL bytes only (read_jsonl)."""
    for entry in read_jsonl(path, tail):
        if kind == "claude":
            if entry.get("isSidechain") or entry.get("isMeta") or entry.get("type") not in ("user", "assistant"):
                continue
            role, content = entry["type"], obj(entry.get("message")).get("content")
            texts = parts(content, "text") if role == "assistant" else texts_of(content)
        else:
            payload = obj(entry.get("payload"))
            role = payload.get("role")
            if payload.get("type") != "message" or role not in ("user", "assistant"):
                continue
            texts = parts(payload.get("content"), "output_text" if role == "assistant" else "input_text")
        for text in texts:
            if text.strip() and not (role == "user" and text.lstrip().startswith(NOT_A_PROMPT)):
                yield role, text


def markdown(item, path):
    """ITEM's conversation (its file PATH) as Markdown: its title, then each turn under who said it, the parts of a
    turn together. No control character but line breaks and tabs: pasted into a terminal, a code the conversation holds
    would run there."""
    who = {"user": "You", "assistant": item.agent.capitalize()}
    turns = []
    for role, text in messages(item.agent, path):
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
    """What a line of a Claude conversation adds: the latest rename and AI title, the first prompt, the folder."""
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


def read_codex(entry, raw):
    """What a line of a Codex conversation adds: its id, folder and whether it is a helper (the first line), then the
    first prompt, after which nothing more is needed (its name lives in session_index.jsonl)."""
    if "id" not in entry:
        meta = obj(parse(raw).get("payload"))
        entry.update(id=text(meta.get("id")) or "", folder=text(meta.get("cwd")) or "",
                     helper=isinstance(meta.get("source"), dict))
    elif b'"role":"user"' in raw:
        payload = obj(parse(raw).get("payload"))
        if payload.get("type") == "message" and payload.get("role") == "user":
            prompt = first_prompt(parts(payload.get("content"), "input_text"))[:PROMPT]
            if prompt:
                entry.update(prompt=prompt, done=True)


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
        read = read_claude if kind == "claude" else read_codex
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


# --- the names given elsewhere

def names_path():
    """Where herdr-fold's Sessions list keeps each conversation's name, and whose it is (sessions-view's names.json)."""
    return os.path.join(os.path.expanduser("~"), ".local", "state", "herdr", "plugins", "herdr-fold.sessions-view",
                        "names.json")


def manual_names():
    """Names given by hand (herdr's Rename pane, the column's Rename), as the Sessions list keeps them:
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
    """The Sessions list's own lock on its names (sessions-view's names_lock): one writer at a time."""
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
    """SESSION named NAME by hand, as herdr's Rename pane names one, where the Sessions list keeps such names: under
    its lock, the other names as they are, the file written whole. One that cannot be read stays as it is (OSError):
    the Sessions list sets it aside, its names kept."""
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


def conversation(kind, path, entry, names, threads):
    """The conversation ENTRY describes; None for a file without a prompt of the user's, and for Codex's helpers."""
    if not entry.get("prompt") or entry.get("helper"):
        return None
    if kind == "claude":
        session = os.path.basename(path)[:-len(".jsonl")]
        title = names.get(session) or entry.get("custom") or entry.get("ai") or entry["prompt"]
    else:
        session = entry.get("id")
        if not session:
            return None
        title = names.get(session) or threads.get(session) or entry["prompt"]
    return Conversation(kind, session, title, entry.get("folder") or "", entry["mtime"])


def running(found, agents, resumed=None):
    """FOUND with the running ones marked, from AGENTS (herdr's agent list): by the session herdr was told of, the one
    reopened in its pane (RESUMED: {pane: conversation id}) until herdr is told, or else the newest conversation of
    its kind in its folder."""
    told, untold = {}, {}
    for agent in agents:
        if agent.get("agent") not in ("claude", "codex"):
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


def local(state_dir, agents=(), resumed=None):
    """This machine's conversations, the newest first; AGENTS: herdr's agent list, and RESUMED, the conversations
    reopened in panes herdr knows no session of yet ({pane: id}), for the running ones."""
    index, fresh, found = load_index(state_dir), {}, []
    names, threads = manual_names(), codex_names()
    for kind, paths in (("claude", claude_files()), ("codex", codex_session_files())):
        for path in paths:
            entry = update(path, kind, index.get(path, {}))
            if entry is None:
                continue
            fresh[path] = entry
            item = conversation(kind, path, entry, names, threads)
            if item:
                found.append(item)
    if fresh != index:
        save_index(state_dir, fresh)
    return running(sorted(found, key=lambda item: item.time, reverse=True), agents, resumed)


def state_folder():
    return os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.join(os.path.expanduser("~"), ".local", "state",
                                                                    "herdr", "plugins", "herdr-fold.sidebar")
