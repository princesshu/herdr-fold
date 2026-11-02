"""AI Sessions in herdr's sidebar: the Agents panel ("sessions") shows only this workspace's agents that have a
conversation, and each Space row how long an agent there waits on you. Marks are recomputed at startup and on each
event, written only on change (no feedback loop). No event reports title changes: names follow on agent and focus."""
import collections
import contextlib
import errno
import glob
import json
import os
import re
import socket
import stat
import sys
import tempfile
import time

SOCKET_PATH = os.environ.get("HERDR_SOCKET_PATH") or os.path.expanduser("~/.config/herdr/herdr.sock")
PLUGIN_ID = os.environ.get("HERDR_PLUGIN_ID")
SOURCE = f"plugin:{PLUGIN_ID}" if PLUGIN_ID else "herdr-fold"
TOKEN = "has_session"
# Default titles of fresh agents that have no conversation yet
GENERIC_TITLES = {"", "claude code", "claude", "codex", "openai codex"}
# A shell's path, e.g. C:\Windows\...\powershell.exe or /bin/zsh: a Windows console shows it as its title
SHELL_TITLE = re.compile(r"(?i)[\\/][^\\/]*(\.exe|sh)$")
TAB_NAME = 24          # characters of a conversation's name on its tab: herdr's tab row fits several
WAITING = ("blocked", "done")   # waiting on you: a question, or an answer not seen yet (seen, done turns idle)
WAIT_TOKEN = "waiting"          # the theme's Space rows show it beside the branch ($waiting)
TICK = 20              # seconds between two looks while an agent waits: a label is late by this much at most


def generic(title):
    """True for a title that is not a conversation's: a fresh agent's default, or a shell's path."""
    title = title.strip()
    return title.lower() in GENERIC_TITLES or bool(SHELL_TITLE.search(title))


def read_line(read):
    reply = b""
    while not reply.endswith(b"\n"):
        chunk = read(65536)
        if not chunk:
            break
        reply += chunk
    return reply


def pipe_name(socket_path):
    """On Windows herdr listens on a named pipe called after its socket path (as herdr's own plugin examples do)."""
    return "\\\\.\\pipe\\" + socket_path


def call(method, params):
    request = (json.dumps({"id": method, "method": method, "params": params}) + "\n").encode()
    if os.name == "nt":  # a named pipe can be opened as a file
        with open(pipe_name(SOCKET_PATH), "r+b", buffering=0) as pipe:
            pipe.write(request)
            return json.loads(read_line(pipe.read) or b"{}")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(SOCKET_PATH)
        s.sendall(request)
        return json.loads(read_line(s.recv) or b"{}")


def current_tokens(agent):
    tokens = agent.get("tokens")
    if tokens is None:
        tokens = (agent.get("metadata") or {}).get("tokens")
    return tokens or {}


MESSAGE = re.compile(r'"type":\s*"(user|assistant)"')


def open_regular(path, *args, **kwargs):
    """open(PATH, *ARGS, **KWARGS) for reading, a regular file only (OSError otherwise): a pipe named like a
    transcript would hold the plugin for good, so it is opened without waiting, then refused."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(errno.EINVAL, "not a regular file", path)
        return os.fdopen(fd, *args, **kwargs)
    except BaseException:
        os.close(fd)
        raise


def has_messages(agent):
    """True if the session's transcript holds a message. Claude creates the file as soon as it starts, with only its
    settings in it; Codex only on the first message."""
    session = (agent.get("agent_session") or {}).get("value")
    if not session:
        return False
    home = os.path.expanduser("~")
    if agent.get("agent") == "codex":
        return bool(glob.glob(os.path.join(home, ".codex", "sessions", "*", "*", "*", f"*{session}.jsonl")))
    if agent.get("agent") != "claude":
        return False
    for transcript in glob.glob(os.path.join(home, ".claude", "projects", "*", f"{session}.jsonl")):
        try:
            with open_regular(transcript, encoding="utf-8", errors="replace") as f:
                if any(MESSAGE.search(line) for line in f):
                    return True
        except OSError:
            pass
    return False


def last_line_values(path, marks, *wanted):
    """For each function of WANTED, the value of the last line of the JSON-lines file at PATH it accepts (returns a
    value), or "": one reading for them all, and only a line holding one of MARKS is parsed (a transcript is hundreds
    of megabytes). A damaged line (cut off, nested too deep, not an object) is skipped."""
    values = [""] * len(wanted)
    try:
        with open_regular(path, encoding="utf-8", errors="replace") as f:
            for raw in f:
                if not any(mark in raw for mark in marks):
                    continue
                try:
                    entry = json.loads(raw)
                except (ValueError, RecursionError):
                    continue
                if isinstance(entry, dict):
                    values = [want(entry) or value for want, value in zip(wanted, values)]
    except OSError:
        pass
    return values


def conversation_title(agent):
    """The conversation's own title, from its files: Claude — the last /rename (custom-title), or else the last title it
    generated (ai-title) in the transcript; Codex — the thread name in its session index. A resumed conversation does
    not send its terminal title again, so without this its row would stay "claude"."""
    session = (agent.get("agent_session") or {}).get("value")
    if not session:
        return ""
    home = os.path.expanduser("~")
    if agent.get("agent") == "claude":
        transcript = next(iter(glob.glob(os.path.join(home, ".claude", "projects", "*", f"{session}.jsonl"))), "")
        if not transcript:
            return ""
        own, generated = last_line_values(transcript, ('"custom-title"', '"ai-title"'),
                                          lambda d: d.get("type") == "custom-title" and d.get("customTitle"),
                                          lambda d: d.get("type") == "ai-title" and d.get("aiTitle"))
        return own or generated
    if agent.get("agent") == "codex":
        return last_line_values(os.path.join(home, ".codex", "session_index.jsonl"), (session,),
                                lambda d: d.get("id") == session and d.get("thread_name"))[0]
    return ""


def has_session(agent):
    if agent.get("agent_status") == "working" or has_messages(agent):
        return True
    return not generic(agent.get("terminal_title_stripped") or "")


def sync_names(agents):
    """Names each session's pane after its title (which follows /rename too) until the user renames the pane. names.json
    records each name and whose it is, so a manual name is kept and the Conversations column reuses it; a damaged
    file is set aside, and only this run's changes are written."""
    names = load_names()
    if names is None:
        set_aside_damaged()
        names = {}
    labels = {p["pane_id"]: p.get("label") or "" for p in call("pane.list", {}).get("result", {}).get("panes", [])}
    tabs = {tab["tab_id"]: tab for tab in call("tab.list", {}).get("result", {}).get("tabs", [])}
    agents_in = collections.Counter(agent.get("tab_id") for agent in agents)
    changes = {}
    known = {entry["name"] for entry in names.values()
             if isinstance(entry, dict) and isinstance(entry.get("name"), str)}
    given_names = {entry["name"] for entry in names.values()
                   if isinstance(entry, dict) and entry.get("given") and isinstance(entry.get("name"), str)}
    for agent in agents:
        key = (agent.get("agent_session") or {}).get("value") or agent["pane_id"]
        title = (agent.get("terminal_title_stripped") or "").strip()
        if generic(title):
            title = conversation_title(agent).strip()
        title = "".join(ch for ch in title if ch.isprintable())          # a title from a file may hold escape codes
        label = labels.get(agent["pane_id"], "")
        # the plugin's to change: a placeholder, or a name it gave — this conversation or the pane's previous one
        # (/clear, /resume)
        if label in ("", "claude", "codex") or label in given_names:
            # Since herdr 0.9.5 the `pane` field in a Sessions row is just the pane name: for an unnamed pane the row
            # would stay empty, so until the conversation has a title, the agent's name goes there
            want = title or agent.get("agent") or label
            if want and label != want:
                call("pane.rename", {"pane_id": agent["pane_id"], "label": want})
            changes[key] = {"name": title, "given": True} if title else None
            name, chosen = title, False
        else:
            # renamed in herdr since the last run (the Conversations column's Rename names the tab itself)
            name, chosen = label, names.get(key) != {"name": label, "given": False}
            changes[key] = {"name": label, "given": False}
        tab = tabs.get(agent.get("tab_id"))
        if name and tab and agents_in[tab["tab_id"]] == 1:
            name_tab(tab, name, chosen, known | {label})
    save_names(changes)


def tab_name(name):
    """NAME as its conversation's tab shows it: TAB_NAME characters at most, a longer one cut with "…"."""
    return name if len(name) <= TAB_NAME else name[:TAB_NAME - 1] + "…"


def name_tab(tab, name, chosen, known):
    """TAB, which a conversation has to itself, shows its NAME; a workspace's main tab keeps the workspace's name.
    A name you gave the conversation (CHOSEN) goes on the tab whatever it shows; a title only while the tab shows
    herdr's number for it or a name a conversation went by (KNOWN): a name you gave the tab itself is kept."""
    want, shown = tab_name(name), tab.get("label") or ""
    if tab.get("number") == 1 or shown == want:
        return
    if chosen or shown.isdigit() or shown in {tab_name(one) for one in known}:
        call("tab.rename", {"tab_id": tab["tab_id"], "label": want})


def set_aside_damaged():
    """A names.json that cannot be read goes aside as names.json.damaged-<date> — never deleted, the names in it stay
    there — and herdr says so; naming goes on in a new file. Under the lock: one of the runs at the same time
    does it."""
    with locked(names_path() + ".lock"):
        if load_names() is not None:                     # another run set it aside already
            return
        aside = names_path() + time.strftime(".damaged-%Y%m%d-%H%M%S")
        os.replace(names_path(), aside)
    call("notification.show", {"title": "Sessions: the names file could not be read",
                               "body": f"set aside as {os.path.basename(aside)} (its names are kept there); "
                                       "new names go on"})


def load_names():
    """names.json: missing = {}, damaged = None (then nothing may be written over it)."""
    try:
        with open(names_path(), encoding="utf-8") as f:
            names = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return None
    return names if isinstance(names, dict) else None


@contextlib.contextmanager
def locked(path, wait=True):
    """The lock file PATH held for the block; yields whether this run holds it: WAIT for it, or give up at once while
    another run has it. herdr runs the plugin once per event, often several at once (focus changes)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a+b") as f:
        try:
            if os.name == "nt":
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK if wait else msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except OSError:
            if wait:
                raise
            yield False
            return
        try:
            yield True
        finally:
            if os.name == "nt":
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def write_json(path, value):
    """VALUE in PATH, written whole to a file beside it first: a reader sees the old file or the new."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=f".{os.path.basename(path)}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False)
    os.replace(tmp, path)


def save_names(changes):
    """Applies CHANGES (session key → entry, or None to drop it) to what is on disk NOW, under the lock, and writes the
    file whole at once: a run that saved meanwhile keeps its names."""
    if not changes:
        return
    with locked(names_path() + ".lock"):
        names = load_names()
        if names is None:
            return
        before = json.dumps(names, sort_keys=True)
        for key, entry in changes.items():
            if entry is None:
                names.pop(key, None)
            else:
                names[key] = entry
        if json.dumps(names, sort_keys=True) != before:
            write_json(names_path(), names)


def state_path(name):
    state_dir = os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.expanduser(
        "~/.local/state/herdr/plugins/herdr-fold.sessions-view")
    return os.path.join(state_dir, name)


def names_path():
    return state_path("names.json")


def waited(seconds):
    """A wait as its Space row says it: under a minute, then whole minutes, hours, days."""
    minutes = int(seconds // 60)
    if minutes < 1:
        return "waiting <1m"
    for unit, size in (("d", 1440), ("h", 60), ("m", 1)):
        if minutes >= size:
            return f"waiting {minutes // size}{unit}"


def load_waits():
    """waits.json: each waiting agent's pane → its state change and since when; {} when missing or damaged (a wait
    recorded there then only starts again)."""
    try:
        with open(state_path("waits.json"), encoding="utf-8") as f:
            waits = json.load(f)
    except (OSError, ValueError):
        return {}
    return waits if isinstance(waits, dict) else {}


def still_unread(was, pane, focused):
    """WAS, the record of PANE's agent marked unread, once the focus went to FOCUSED (None: no focus change): kept
    while it stays there, noted as left when another pane gets it, and gone (read) when it comes back after that."""
    if focused is None or (focused == pane and not was.get("left")):
        return was
    return dict(was, left=True) if focused != pane else None


def report_waits(agents, now, focused=None):
    """Each agent waiting on you, since its last state change (herdr's state_change_seq) or since it was marked
    unread, kept in waits.json; each workspace's $waiting token set to its longest wait, or cleared, where it changed.
    FOCUSED: the pane a focus change went to. Whether any agent waits."""
    with locked(state_path("waits.json.lock")):
        known, waits = load_waits(), {}
        for agent in agents:
            pane, seq = agent["pane_id"], agent.get("state_change_seq")
            was = known.get(pane) if isinstance(known.get(pane), dict) else None
            if was and was.get("unread") and isinstance(was.get("since"), (int, float)):
                was = still_unread(was, pane, focused)
                if was:
                    waits[pane] = was
                    continue
            if agent.get("agent_status") in WAITING:
                same = bool(was) and was.get("seq") == seq and isinstance(was.get("since"), (int, float))
                waits[pane] = {"seq": seq, "since": was["since"] if same else now}
        if waits != known:
            write_json(state_path("waits.json"), waits)
    first = {}
    for agent in agents:
        if agent["pane_id"] in waits:
            space = agent["workspace_id"]
            first[space] = min(first.get(space, now), waits[agent["pane_id"]]["since"])
    for space in call("workspace.list", {}).get("result", {}).get("workspaces", []):
        ws = space["workspace_id"]
        want = waited(now - first[ws]) if ws in first else None
        if (space.get("tokens") or {}).get(WAIT_TOKEN) != want:
            call("workspace.report_metadata", {"workspace_id": ws, "source": SOURCE, "tokens": {WAIT_TOKEN: want}})
    return bool(waits)


def mark_unread(pane, agents, now):
    """Cmd+Shift+U: PANE's agent waits on you again, from NOW or from when it began to wait, until you come back to it
    after leaving it; marked already, the mark goes. Then the labels."""
    agent = next((one for one in agents if one["pane_id"] == pane), None)
    if agent is None:
        return
    with locked(state_path("waits.json.lock")):
        waits = load_waits()
        was = waits.get(pane) if isinstance(waits.get(pane), dict) else {}
        if was.get("unread"):
            del waits[pane]
        else:
            since = was["since"] if isinstance(was.get("since"), (int, float)) else now
            waits[pane] = {"seq": agent.get("state_change_seq"), "since": since, "unread": True, "left": False}
        write_json(state_path("waits.json"), waits)
    report_waits(agents, now)


def code_stamp():
    """This file as it is now: another one after an update, None once it is removed."""
    try:
        found = os.stat(os.path.abspath(__file__))
    except OSError:
        return None
    return found.st_ino, found.st_mtime_ns, found.st_size


def keep_time(clock=time.time, sleep=time.sleep):
    """While an agent waits, the labels stay current: one run looks again every TICK seconds, until none waits, herdr
    stops answering or this file changes (an update, an uninstall: the next event starts the new one)."""
    while load_waits():
        with locked(state_path("clock.lock"), wait=False) as mine:
            if not mine:
                return
            code = code_stamp()
            while True:
                sleep(TICK)
                if code_stamp() != code:
                    return
                try:
                    if not report_waits(call("agent.list", {}).get("result", {}).get("agents", []), clock()):
                        break
                except (OSError, ValueError):
                    return
        # let go: a wait recorded meanwhile, whose own run was turned away, is kept by this one


def mark_panes():
    agents = call("agent.list", {}).get("result", {}).get("agents", [])
    for agent in agents:
        want = has_session(agent)
        have = TOKEN in current_tokens(agent)
        if want != have:
            call("pane.report_metadata", {
                "pane_id": agent["pane_id"],
                "source": SOURCE,
                "tokens": {TOKEN: "yes" if want else None},
            })
    return agents


def apply_view():
    return call("agent.view.set", {
        "source": SOURCE,
        "label": "sessions",
        "filter": {"op": "all", "filters": [
            {"op": "eq", "field": "workspace_id", "value": {"context": "current_workspace_id"}},
            {"op": "exists", "field": {"token": TOKEN}},
        ]},
    })


def refresh(focused=None):
    """The marks, the names and the waits, once (FOCUSED: the pane a focus change went to)."""
    agents = mark_panes()
    sync_names(agents)
    report_waits(agents, time.time(), focused)


if __name__ == "__main__":
    event = os.environ.get("HERDR_PLUGIN_EVENT", "")
    if sys.argv[1:] == ["--unread"]:                    # Cmd+Shift+U, on the focused pane
        mark_unread(os.environ.get("HERDR_PANE_ID"), mark_panes(), time.time())
        keep_time()
        sys.exit(0)
    refresh(os.environ.get("HERDR_PANE_ID") if event in ("pane.focused", "tab.focused") else None)
    applied = True
    # At startup and on manual runs the view is set too; on events only the marks are refreshed.
    if event in ("", "startup") or os.environ.get("HERDR_PLUGIN_ACTION_ID"):
        result = apply_view()
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if event == "startup":
            # Agents of resumed conversations take a few seconds to come up and get their titles.
            # There is no plugin event for title changes, so after startup the plugin keeps re-marking for a minute.
            for _ in range(20):
                time.sleep(3)
                refresh()
        applied = bool(result.get("result", {}).get("active"))
    keep_time()
    sys.exit(0 if applied else 1)
