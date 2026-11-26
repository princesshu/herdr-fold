# Generated from core/runs.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""The agents' runs for Runs in both clients: Claude's background sessions (`claude agents --json --all`), Codex's
`codex exec` runs and cloud tasks (`codex cloud list --json`), each with what it made and cost (tokens.py's index); for
the preview, where a chat's media file came from. A run is the agent's own command; nothing is scheduled here."""
import calendar
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import chats  # noqa: E402
import costs  # noqa: E402
import statefile  # noqa: E402
import tokens  # noqa: E402
from filekinds import MEDIA, kind_of  # noqa: E402
from jsonl import claude_project_dir, obj, open_regular, parse  # noqa: E402
from words import model_name  # noqa: E402

NAMES = {"claude": "Claude", "codex": "Codex"}
RAN_AS = {"background": "Background session", "exec": "codex exec", "cloud": "Codex cloud"}
CACHE = "runs-index.json"       # in herdr-fold's state: what was read of each run's file, by its size and time
READ = 2                        # what a file's reading holds: another's is read again (2: what connectors made)
DIFFS = "diffs"                 # in herdr-fold's state: a cloud task's diff, as its preview shows it
KEEP = 30                       # seconds the background sessions' list is kept before claude is asked again
TIMEOUT = 25                    # seconds an agent's command may take: the app's exec stops a program after 30
RECENT = 40                     # runs listed at most, the newest first
TOLD = 3                        # seconds a codex exec run is watched for a failure at its start (not signed in)
STALE = 15 * 60                 # seconds without a line after which a Codex run that never ended no longer runs
PROMPT = 600                    # characters of a run's prompt its properties keep
CLAUDE_STATES = {"working": "running", "blocked": "blocked", "done": "done", "failed": "failed", "stopped": "stopped"}
CLOUD_STATES = {"pending": "running", "ready": "ready", "applied": "applied", "error": "failed"}
SCHEDULED = ("Scheduled cloud runs are not listed: Claude keeps its routines at claude.ai, Codex its scheduled tasks "
             "in its app.")
LIVE = ("running", "blocked")   # the states of a run that works now: Running's group, the status bar's count
WRITES = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
MAIN = ("file_path", "notebook_path", "command", "pattern", "url", "query", "description")    # a step's words
PR = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/(\d+)")       # as `gh pr create` prints the one it opened
OPENS_PR = "gh pr create"
PATCHED = re.compile(r"^\*\*\* (?:Add|Update) File: (.+?)\s*$", re.M)    # apply_patch's files, added or changed
# a media connector's call as its input tells it: its model and prompt, at its top or one level in (fal's "input")
MODELS = ("model", "model_id", "modelId", "endpoint_id", "endpointId", "endpoint", "app_id")
PROMPTS = ("prompt", "text", "prompt_text", "promptText", "description")
LINK = re.compile(r"https?://[^\s\"'`<>()\[\]{}\\]+")       # an address a result gives, a command downloads
WORD = re.compile(r"[^\s\"'`<>()\[\]{},;|&=\\]+")            # a word that may name a file
SEARCHED = 12                   # chats looked through for where a file came from, the newest first
LEFT = []                       # the codex exec runs started here that run on: known until they end, then reaped
COUNTED = {"image": ("image", "images"), "audio": ("audio file", "audio files"), "video": ("video", "videos"),
           "file": ("file", "files")}


def counted(n, kind):
    return f"{n} {COUNTED[kind][n != 1]}"


def agent_says(done):
    """What a finished command DONE (subprocess.run's) said: its error's last line, else its output's."""
    lines = [line.strip() for line in (done.stderr or done.stdout or "").splitlines() if line.strip()]
    return lines[-1][:300] if lines else f"it ended with code {done.returncode}"


def command(argv, folder=None):
    """ARGV run in FOLDER: (whether it worked, what it printed or said). Its program missing or slow says so."""
    if not shutil.which(argv[0]):
        return False, f"{argv[0]} is not on this machine's PATH"
    try:
        done = subprocess.run(argv, cwd=folder, capture_output=True, text=True, timeout=TIMEOUT,
                              stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False, f"{argv[0]} did not answer in {TIMEOUT} s"
    except OSError as err:
        return False, err.strerror or str(err)
    return (True, done.stdout) if done.returncode == 0 else (False, agent_says(done))


# --- what a run's file tells

def step(name, told, folder):
    """A tool call as a run's Now line says it: its name, then its file (in FOLDER's terms), command or pattern."""
    main = next((told[key] for key in MAIN if isinstance(told.get(key), str) and told[key].strip()), "")
    if main.startswith(folder + os.sep):
        main = main[len(folder) + 1:]
    return f"{name} {main.strip().splitlines()[0][:120]}".strip() if main else name


def written(files, path, folder):
    path = path.strip()
    if path:
        path = path if os.path.isabs(path) else os.path.join(folder, path)
        files[path] = None


def given(told, keys):
    """The first of KEYS a tool's input TOLD gives as text, at its top or one level in; None for none."""
    for place in [told] + [one for one in told.values() if isinstance(one, dict)]:
        found = next((place[key].strip() for key in keys if isinstance(place.get(key), str) and place[key].strip()),
                     None)
        if found:
            return found[:PROMPT]
    return None


def named(text, folder):
    """The media files TEXT names (a result's words, a command), each a path: from FOLDER where it is relative."""
    words = (word.rstrip(".,:;!?") for word in WORD.findall(LINK.sub(" ", text)))
    return [os.path.normpath(os.path.join(folder, os.path.expanduser(word))) for word in words
            if MEDIA.get(kind_of(word)) and not word.startswith("-") and not set(word) & set("*?$")]


class Made:
    """What a chat's connectors made, read call by call: each call's server, model and prompt (a job's poll the asking
    call's), the skill in use and its turn's calls of that server; a media file its result names, or one a command
    downloads from an address its result gave."""

    def __init__(self, folder):
        self.folder, self.calls, self.asked, self.links, self.origins, self.skill, self.turn, self.counts = \
            folder, {}, {}, {}, {}, None, 0, {}

    def call(self, id, server, told):
        asked = {"server": server, "model": given(told, MODELS), "prompt": given(told, PROMPTS), "skill": self.skill}
        if asked["prompt"]:
            self.asked[server] = asked
        self.calls[id] = {**(self.asked.get(server) or asked), "turn": self.turn}
        self.counts[self.turn, server] = self.counts.get((self.turn, server), 0) + 1

    def result(self, id, text, files):
        if id in self.calls:
            self.links.update(dict.fromkeys((link.rstrip(".,;:") for link in LINK.findall(text)), id))
            for path in named(text, self.folder):
                files[path], self.origins[path] = None, id

    def command(self, text, files):
        ids = [self.links[link.rstrip(".,;:")] for link in LINK.findall(text) if link.rstrip(".,;:") in self.links]
        for path in named(text, self.folder) if ids else ():
            files[path], self.origins[path] = None, ids[-1]

    def told(self):
        """Each media file made: its call's server, model, prompt and skill, and its turn's calls of that server."""
        return {path: {**{key: self.calls[id][key] for key in ("server", "model", "prompt", "skill")},
                       "calls": self.counts[self.calls[id]["turn"], self.calls[id]["server"]]}
                for path, id in self.origins.items()}


def claude_read(path, folder):
    """What the Claude session in PATH (started in FOLDER) ran: its prompt, model, the files it wrote and the media
    its connectors made (Made's, each with where it came from), the PR `gh pr create` opened, its last step and the
    times of its first and last lines."""
    found, files, opening, hours = {"prompt": "", "model": None, "pr": None, "now": None, "times": []}, {}, set(), {}
    made = Made(folder)
    with open_regular(path, "rb") as f:
        for raw in f:
            if b'"isSidechain":true' in raw or not (b'"type":"user"' in raw or b'"type":"assistant"' in raw):
                continue
            entry = parse(raw)
            at = tokens.seconds(entry.get("timestamp"), hours)
            if at is not None:
                found["times"].append(at)
            content = obj(entry.get("message")).get("content")
            texts = [one.strip() for one in chats.texts_of(content) if one.strip()
                     and not one.lstrip().startswith(chats.NOT_A_PROMPT)] if entry.get("type") == "user" else []
            made.turn += bool(texts)
            found["prompt"] = found["prompt"] or (texts[0][:PROMPT] if texts else "")
            for block in content if isinstance(content, list) else ():
                block = obj(block)
                if block.get("type") == "tool_use" and isinstance(block.get("name"), str):
                    name, told = block["name"], obj(block.get("input"))
                    found["now"] = step(name, told, folder)
                    if isinstance(told.get(WRITES.get(name, "")), str):
                        written(files, told[WRITES[name]], folder)
                    if OPENS_PR in str(told.get("command", "")):
                        opening.add(block.get("id"))
                    if name.startswith("mcp__"):
                        made.call(block.get("id"), name[len("mcp__"):].partition("__")[0], told)
                    made.skill = told["skill"] if name == "Skill" and isinstance(told.get("skill"), str) \
                        else made.skill
                    made.command(str(told.get("command", "")), files)
                elif block.get("type") == "tool_result":
                    said = " ".join(chats.texts_of(block.get("content")))
                    made.result(block.get("tool_use_id"), said, files)
                    if block.get("tool_use_id") in opening:
                        pr = PR.search(said)
                        found["pr"] = {"number": int(pr.group(1)), "url": pr.group(0)} if pr else found["pr"]
            model = obj(entry.get("message")).get("model")
            found["model"] = model if entry.get("type") == "assistant" and isinstance(model, str) \
                and not model.startswith("<") else found["model"]
    return {**found, "files": list(files), "origins": made.told()}


def codex_read(path):
    """What the Codex rollout in PATH ran: its id, folder, prompt, model, the files apply_patch wrote and the media its
    connectors made (Made's), the PR it opened, its last step, how its last turn ended (None while it runs) and its
    first and last lines' times."""
    found, files, opening, hours = {"id": "", "folder": "", "prompt": "", "model": None, "pr": None, "now": None,
                                    "ended": None, "times": []}, {}, set(), {}
    made = Made("")
    with open_regular(path, "rb") as f:
        for raw in f:
            entry = parse(raw)
            told, kind = obj(entry.get("payload")), entry.get("type")
            at = tokens.seconds(entry.get("timestamp"), hours)
            if at is not None:
                found["times"].append(at)
            if kind == "session_meta":
                found.update(id=chats.text(told.get("id")) or "", folder=chats.text(told.get("cwd")) or "")
                made.folder = found["folder"]
            elif kind == "turn_context" and isinstance(told.get("model"), str):
                found["model"] = told["model"]
            elif kind == "event_msg":
                ended = {"task_started": None, "task_complete": "done", "turn_aborted": "failed", "error": "failed"}
                found["ended"] = ended.get(told.get("type"), found["ended"])
            elif told.get("type") == "message" and told.get("role") == "user":
                texts = [one.strip() for one in chats.parts(told.get("content"), "input_text") if one.strip()
                         and not one.lstrip().startswith(chats.NOT_A_PROMPT)]
                made.turn += bool(texts)
                found["prompt"] = found["prompt"] or (texts[0][:PROMPT] if texts else "")
            elif told.get("type") in ("function_call", "custom_tool_call") and isinstance(told.get("name"), str):
                said, space = str(told.get("arguments") or told.get("input") or ""), str(told.get("namespace", ""))
                for one in PATCHED.findall(said):
                    written(files, one, found["folder"])
                if OPENS_PR in said:
                    opening.add(told.get("call_id"))
                if space.startswith("mcp__"):          # a server's tool: its name apart, the server in its namespace
                    made.call(told.get("call_id"), space[len("mcp__"):], parse(said))
                else:
                    made.command(said, files)
                found["now"] = f"{told['name']} {said.strip().splitlines()[0][:120]}".strip() if said else told["name"]
            elif told.get("type") == "function_call_output":
                said = str(told.get("output", ""))
                made.result(told.get("call_id"), said, files)
                if told.get("call_id") in opening:
                    pr = PR.search(said)
                    found["pr"] = {"number": int(pr.group(1)), "url": pr.group(0)} if pr else found["pr"]
    return {**found, "files": list(files), "origins": made.told()}


def cached(cache, path, read):
    """READ()'s answer for the file PATH, kept in CACHE while the file stays as it was; None when it cannot be read."""
    try:
        info = os.stat(path)
    except OSError:
        return None
    kept = cache.get(path)
    if isinstance(kept, dict) and kept.get("size") == info.st_size and kept.get("mtime") == info.st_mtime \
            and kept.get("version") == READ:
        return kept["read"]
    try:
        found = read()
    except (OSError, TypeError):
        return None
    cache[path] = {"size": info.st_size, "mtime": info.st_mtime, "version": READ, "read": found}
    return found


# --- the runs

def made(state, files, pr):
    """A run's Made: failed, the PR it opened, its media by their kind, its files, or no change ("" while it runs)."""
    kinds = [MEDIA.get(kind_of(one)) for one in files]
    media = max(("image", "audio", "video"), key=kinds.count)
    if state == "failed":
        return "failed"
    if pr:
        return f"PR #{pr['number']}"
    if media in kinds:
        return counted(kinds.count(media), media)
    return counted(len(files), "file") if files else "" if state in LIVE else "no change"


def took(times):
    """How long a run went, from its first line's time to its last: 4 min, 1 h 5 min; None for no times."""
    if not times:
        return None
    minutes = round((max(times) - min(times)) / 60)
    return "<1 min" if minutes < 1 else f"{minutes} min" if minutes < 60 else \
        f"{minutes // 60} h" + (f" {minutes % 60} min" if minutes % 60 else "")


def when(at, now=None):
    """A run's group and time by when it started (AT, seconds since 1970): Today and 14:02, Yesterday, or Earlier
    with its day (Nov 21)."""
    day, today = time.localtime(at), time.localtime(now)
    days = (time.mktime(today[:3] + (0, 0, 0, 0, 0, -1)) - time.mktime(day[:3] + (0, 0, 0, 0, 0, -1))) / 86400
    if round(days) <= 1:
        return ("Today" if round(days) <= 0 else "Yesterday"), time.strftime("%H:%M", day)
    return "Earlier", time.strftime("%b ", day) + str(day.tm_mday)


def priced(state, agent, path, agents):
    """What the run in PATH cost as costs.py says a chat's: ["~$0.22", "~$0.22 API value"]; "–" before a message."""
    found = costs.costs(state, agent, path, agents)
    if not found:
        return ["–", "Nothing counted yet"]
    return [found["text"], found["text"] + ("" if found["text"] == "no price" else f" {found['kind']}")]


def row(agent, kind, id, read, folder, at, state, cost, **more):
    """A run as both clients list it: its row's words and its properties'."""
    day, clock = when(at)
    model = model_name(read["model"]) if read.get("model") else None
    named, went = more.pop("title", ""), took(read.get("times", []))
    prompt = read.get("prompt") or named or RAN_AS[kind]
    said = {"running": " · ".join(filter(None, ["running", went])), "ready": "ready · not applied",
            "blocked": " · ".join(filter(None, ["needs you", more.get("waiting")]))}.get(state, state)
    return {"key": f"{agent}:{id}", "agent": agent, "name": NAMES[agent], "id": id, "kind": kind,
            "title": prompt.splitlines()[0], "prompt": prompt, "folder": folder,
            "place": more.pop("place", None) or os.path.basename(folder.rstrip(os.sep)), "at": at,
            "group": "Running" if state in LIVE else day, "day": day, "time": clock, "took": went,
            "state": state, "said": said, "made": made(state, read.get("files", []), read.get("pr")),
            "files": read.get("files", []),
            "media": [{"path": one, "kind": MEDIA[kind_of(one)]} for one in read.get("files", [])
                      if MEDIA.get(kind_of(one))],
            "pr": read.get("pr"), "cost": cost[0], "cost_line": cost[1],
            "ran_as": " · ".join(filter(None, [RAN_AS[kind], NAMES[agent] if kind != "cloud" else None, model])),
            "now": read.get("now") if state in LIVE else None, **more}


def background(state, fresh=False):
    """Claude's background sessions as `claude agents --json --all` lists them, kept KEEP seconds in RUNS (Chats
    leaves their sessions out): [its entries], and why the list could not be read, or None."""
    path = os.path.join(state, chats.RUNS)
    kept = statefile.read(path)
    if not fresh and isinstance(kept.get("at"), (int, float)) and 0 <= time.time() - kept["at"] < KEEP \
            and isinstance(kept.get("listed"), list):
        return kept["listed"], kept.get("error")
    if not shutil.which("claude"):
        return [], None
    ok, said = command(["claude", "agents", "--json", "--all"])
    try:
        listed = [obj(one) for one in json.loads(said) if obj(one).get("kind") == "background"] if ok else []
        error = None if ok else said
    except ValueError:
        listed, error = [], "its list could not be read"
    sessions = [one["sessionId"] for one in listed if isinstance(one.get("sessionId"), str)]
    try:
        statefile.write(path, {"at": time.time(), "listed": listed, "error": error, "sessions": sessions})
    except OSError:
        pass                            # asked again next time
    return listed, error


def claude_runs(state, cache, agents, fresh=False):
    """Claude's background sessions as runs, and why they could not be listed (or None)."""
    listed, error = background(state, fresh)
    found = []
    for one in listed:
        id, session, folder = chats.text(one.get("id")), chats.text(one.get("sessionId")), chats.text(one.get("cwd"))
        if not id or not folder:
            continue
        path = os.path.join(claude_project_dir(folder), f"{session}.jsonl") if session else ""
        read = (cached(cache, path, lambda: claude_read(path, folder)) if path else None) or {}
        started = one.get("startedAt")
        at = started / 1000 if isinstance(started, (int, float)) else min(read.get("times") or [time.time()])
        found.append(row("claude", "background", id, read, folder, at,
                         CLAUDE_STATES.get(one.get("state"), "done"),
                         priced(state, "claude", path, agents) if read else ["–", "Nothing counted yet"],
                         session=session, title=chats.text(one.get("name")) or "",
                         waiting=chats.text(one.get("waitingFor"))))
    return found, error


def codex_runs(state, cache, agents):
    """Codex's `codex exec` runs, from the chats' index (chats.py marks them), the newest RECENT."""
    exec_files = sorted(((entry.get("mtime") or 0, path) for path, (kind, entry)
                         in chats.indexed(chats.state_folder()).items() if kind == "codex" and entry.get("run")),
                        reverse=True)[:RECENT]
    found = []
    for mtime, path in exec_files:
        read = cached(cache, path, lambda: codex_read(path))
        if not read or not read["id"]:
            continue
        ended = read["ended"] or ("done" if time.time() - mtime > STALE else "running")
        found.append(row("codex", "exec", read["id"], read, read["folder"], min(read["times"] or [mtime]), ended,
                         priced(state, "codex", path, agents), session=read["id"]))
    return found


def cloud_runs():
    """Codex's cloud tasks (`codex cloud list --json`), and why they could not be listed (or None). The list tells
    no tokens: their cost is –."""
    if not shutil.which("codex"):
        return [], None
    ok, said = command(["codex", "cloud", "list", "--json"])
    if not ok:
        return [], said
    try:
        tasks = obj(json.loads(said)).get("tasks")
    except ValueError:
        return [], "its list could not be read"
    found = []
    for task in tasks if isinstance(tasks, list) else ():
        task, id = obj(task), chats.text(obj(task).get("id"))
        summary, stamp = obj(task.get("summary")), chats.text(task.get("updated_at")) or ""
        if not id:
            continue
        try:
            at = calendar.timegm(time.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            at = time.time()
        files = summary.get("files_changed") if type(summary.get("files_changed")) is int else 0
        state = CLOUD_STATES.get(str(task.get("status", "")).lower(), "done")
        env = chats.text(task.get("environment_label")) or chats.text(task.get("environment_id")) or ""
        found.append(row("codex", "cloud", id, {"prompt": chats.text(task.get("title")) or ""}, "", at, state,
                         ["–", "Codex cloud does not tell its tokens"], place=env, env=env,
                         env_id=chats.text(task.get("environment_id")), url=chats.text(task.get("url")),
                         diff=f"{counted(files, 'file')} +{summary.get('lines_added', 0)} "
                              f"−{summary.get('lines_removed', 0)}" if files else None))
        if files and state != "failed":
            found[-1]["made"] = counted(files, "file")
    return found, None


def runs(agents=None, fresh=False):
    """Every run, the working ones first, then the newest: {"runs", "working", "envs": Codex cloud's environments
    (theirs, from its tasks), "notes": what could not be read, "left": the bytes the token index has yet to read}."""
    state = statefile.folder()
    left = tokens.index(state)["left"]
    cache_path = os.path.join(state, CACHE)
    cache = obj(statefile.read(cache_path).get("files"))
    kept = dict(cache)
    claude, error = claude_runs(state, cache, agents, fresh)
    cloud, cloud_error = cloud_runs()
    found = sorted(claude + codex_runs(state, cache, agents) + cloud,
                   key=lambda one: (one["state"] not in LIVE, -one["at"]))[:RECENT]
    if cache != kept:
        try:
            statefile.write(cache_path, {"files": {path: cache[path] for path in cache if os.path.exists(path)}})
        except OSError:
            pass
    envs = {one["env_id"]: one["env"] for one in cloud if one.get("env_id")}
    notes = [f"Couldn't list {name}'s runs: {why}" for name, why in (("Claude", error), ("Codex cloud", cloud_error))
             if why]
    return {"runs": found, "working": sum(one["state"] in LIVE for one in found), "notes": notes,
            "scheduled": SCHEDULED,
            "envs": [{"id": id, "label": label} for id, label in envs.items()], "left": left}


def working():
    """How many runs work now, for the status bar: Claude's background sessions (their list kept KEEP seconds)."""
    listed, _ = background(statefile.folder())
    return sum(CLAUDE_STATES.get(one.get("state")) in LIVE for one in listed)


# --- where a file came from

def title(kind, path):
    """The chat in PATH as Chats names it: its rename, its title, else its first prompt."""
    entry = chats.update(path, kind, {}) or {}
    one = chats.chat(kind, path, {**entry, "run": None, "helper": None}, chats.manual_names(), chats.codex_names())
    return one.title if one else entry.get("prompt") or ""


def origin(path):
    """Where the media file PATH came from, as the chat that made it tells it (one of its folder's or a folder's above
    it, written to since the file was): its agent, session and title, Made's, and "again", the request for another
    take that Ask for Another puts in that chat; None where none tells it."""
    path = os.path.abspath(path)
    try:
        since = os.stat(path).st_mtime - 60
    except OSError:
        return None
    places, folder, seen = {}, os.path.dirname(path), set()
    while folder not in seen:                                    # its folder's chats, then each folder's above it
        seen.add(folder)
        places.update(dict.fromkeys(glob.glob(os.path.join(glob.escape(claude_project_dir(folder)), "*.jsonl")),
                                    ("claude", folder)))
        folder = os.path.dirname(folder)
    places.update(dict.fromkeys(chats.codex_session_files(), ("codex", None)))
    name, recent = os.path.basename(path).encode(), []
    for file in places:
        try:
            recent += [(os.stat(file).st_mtime, file)]
        except OSError:
            continue
    for _, file in sorted((one for one in recent if one[0] >= since), reverse=True)[:SEARCHED]:
        kind, folder = places[file]
        try:
            with open_regular(file, "rb") as f:
                if name not in f.read():
                    continue
            read = claude_read(file, folder) if kind == "claude" else codex_read(file)
        except (OSError, TypeError):
            continue
        told = read["origins"].get(path)
        if told:
            session = os.path.basename(file)[:-len(".jsonl")] if kind == "claude" else read["id"]
            folder = folder or read["folder"]
            shown = os.path.relpath(path, folder) if folder and path.startswith(folder + os.sep) else path
            return {"agent": kind, "session": session, "title": title(kind, file), **told,
                    "again": f"Another take on {shown}: the same prompt, model and skill, saved beside it."}
    return None


# --- what is done to one

def start(agent, where, folder, prompt, env=None):
    """A run started as the agent starts one: Claude's in the background (claude --bg), Codex's here (codex exec,
    left running on its own) or in its cloud (codex cloud exec in ENV); {"ok", "said"}: what happened."""
    if not prompt.strip() or not os.path.isdir(folder):
        return {"ok": False, "said": "A prompt and a folder are needed"}
    if agent == "claude":
        ok, said = command(["claude", "--bg", prompt], folder)
        return {"ok": ok, "said": "Started in the background" if ok else f"Claude didn't start it: {said}"}
    if agent == "codex" and where == "cloud":
        ok, said = command(["codex", "cloud", "exec", "--env", env or "", prompt], folder)
        return {"ok": ok, "said": "Sent to Codex cloud" if ok else f"Codex didn't send it: {said}"}
    if agent != "codex" or not shutil.which("codex"):
        return {"ok": False, "said": f"{NAMES.get(agent, agent)} is not on this machine's PATH"}
    with tempfile.TemporaryFile("w+") as log:      # the run's own once this ends: a pipe would break its writes
        try:
            child = subprocess.Popen(["codex", "exec", prompt], cwd=folder, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=log, start_new_session=True)
            child.wait(TOLD)            # one that fails at once says so here; else it runs on
        except subprocess.TimeoutExpired:
            LEFT.append(child)
            return {"ok": True, "said": "Started with codex exec"}
        except OSError as err:
            return {"ok": False, "said": f"Codex didn't start it: {err.strerror or err}"}
        log.seek(0)
        lines = [line.strip() for line in log.read().splitlines() if line.strip()]
    if child.returncode:
        return {"ok": False, "said": f"Codex didn't start it: {lines[-1][:300] if lines else child.returncode}"}
    return {"ok": True, "said": "Ran with codex exec"}


def act(what, id, folder=None):
    """WHAT done to run ID with its agent's own command: stop or remove Claude's background session, a cloud task's
    diff (kept in DIFFS for the preview: "path") or apply (into FOLDER); {"ok", "said"}."""
    if what == "diff":
        ok, said = command(["codex", "cloud", "diff", id])
        path = os.path.join(statefile.folder(), DIFFS, re.sub(r"[^\w.-]", "-", id)[:80] + ".diff")
        if ok:
            os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(said)
        return {"ok": ok, "said": "" if ok else f"Codex didn't show it: {said}", "path": path if ok else None}
    argv, done, failed = {"stop": (["claude", "stop", id], "Stopped", "Claude didn't stop it"),
                          "remove": (["claude", "rm", id], "Removed from the list", "Claude didn't remove it"),
                          "apply": (["codex", "cloud", "apply", id], "Applied", "Codex didn't apply it")}[what]
    ok, said = command(argv, folder)
    if ok and what in ("stop", "remove"):
        background(statefile.folder(), fresh=True)
    return {"ok": ok, "said": done if ok else f"{failed}: {said}"}


def main(argv):
    """herdr-fold's Herdr app mod runs this, answering in JSON: list [--agents=JSON] [--fresh] (runs()'s), working
    (the count), start AGENT WHERE FOLDER PROMPT [ENV], stop|remove ID, diff TASK, apply TASK FOLDER, origin PATH
    (where a media file came from, or null)."""
    options = dict(arg[2:].split("=", 1) for arg in argv[1:] if arg.startswith("--") and "=" in arg)
    args = [arg for arg in argv[1:] if not arg.startswith("--")]
    asked, args = (args[0], args[1:]) if args else ("", [])
    try:
        agents = json.loads(options["agents"]) if "agents" in options else None
        if asked == "list" and not args:
            answer = runs(agents, "--fresh" in argv)
        elif asked == "working" and not args:
            answer = {"working": working()}
        elif asked == "start" and len(args) in (4, 5) and args[0] in NAMES:
            answer = start(*args)
        elif asked in ("stop", "remove", "diff") and len(args) == 1 or asked == "apply" and len(args) == 2:
            answer = act(asked, *args)
        elif asked == "origin" and len(args) == 1:
            answer = origin(args[0])
        else:
            raise ValueError("unknown command")
    except ValueError:
        print("usage: runs.py list [--agents=JSON] [--fresh] | working | start AGENT WHERE FOLDER PROMPT [ENV] | "
              "stop|remove|diff ID | apply TASK FOLDER | origin PATH", file=sys.stderr)
        return 2
    print(json.dumps(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
