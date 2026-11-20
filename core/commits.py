"""The commits from a conversation, for Usage's report: the ones it made (a result of its own names the new commit)
and the ones that touched a file it edited, within a day and before another conversation edited it. Claude's sessions
are read once (INDEX), git only read, nothing a repository's config names run. Usage (in JSON): commits.py index."""
import json
import os
import re
import shutil
import stat
import subprocess
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import statefile  # noqa: E402
import tokens  # noqa: E402
from jsonl import obj, parse  # noqa: E402
from locate import repo_top  # noqa: E402

INDEX = "commits-index.json"    # what was read of each session file: the files it edited and when, the commits named
VERSION = 1                     # another version's index (its shape) is not read: the files are
LINES = 20000                   # commits whose lines are kept (a commit's never change), the newest
DAY = 86400                     # a commit this long after an edit is no longer that edit's
EDITS = ("Edit", "MultiEdit", "Write")          # Claude's calls that change the file their file_path names
MARKS = tuple(f'"name":"{name}"'.encode() for name in EDITS) + (b" file changed", b" files changed")
# git commit's own first line: [main a1b2c3d] Subject, [main (root-commit) a1b2c3d], [detached HEAD a1b2c3d]
MADE = re.compile(r"^\[(?:detached HEAD|[^\] ]+)(?: \(root-commit\))? ([0-9a-f]{7,40})\] ", re.M)
SHA = re.compile(r"[0-9a-f]{7,40}")
TIMEOUT = 30
GIT = shutil.which("git") or next(
    (p for p in ("/usr/bin/git", "/opt/homebrew/bin/git", "/usr/local/bin/git") if os.path.exists(p)), "git")


# --- what a session tells

def told(path, offset=0, most=tokens.CHUNK):
    """What the Claude session file PATH tells from OFFSET (MOST bytes of it): its edits as [(when, the file)], the
    commits its Bash results name (as git commit printed them), and where the next read starts."""
    lines, offset = tokens.marked(path, offset, most, MARKS)
    edits, made, hours = [], [], {}
    for raw in lines:
        entry = parse(raw)
        if entry.get("type") == "assistant":
            at, blocks = tokens.seconds(entry.get("timestamp"), hours), obj(entry.get("message")).get("content")
            for block in blocks if isinstance(blocks, list) and at is not None else []:
                block = obj(block)
                file = obj(block.get("input")).get("file_path")
                if block.get("type") == "tool_use" and block.get("name") in EDITS and isinstance(file, str) \
                        and os.path.isabs(file):
                    edits.append((at, os.path.normpath(file)))
        elif entry.get("type") == "user":
            printed = obj(entry.get("toolUseResult")).get("stdout")
            made += MADE.findall(printed) if isinstance(printed, str) else []
    return edits, made, offset


def session_of(path):
    """The session the Claude file PATH belongs to: its own, a sub-agent's file its parent's."""
    folder, name = os.path.split(path)
    return os.path.basename(os.path.dirname(folder)) if os.path.basename(folder) == "subagents" \
        else name[:-len(".jsonl")]


# --- the index

def whole(entry):
    """Whether ENTRY, a file's in the index, has the shape this version keeps."""
    edits, made = (entry.get("edits"), entry.get("made")) if isinstance(entry, dict) else (None, None)
    return isinstance(edits, dict) and isinstance(made, list) and type(entry.get("offset")) is int \
        and isinstance(entry.get("session"), str) and all(isinstance(sha, str) and SHA.fullmatch(sha) for sha in made) \
        and all(isinstance(times, list) and all(type(at) is int for at in times) for times in edits.values())


def load(state):
    """The index in STATE, {"version", "files": {path: what was read of it}, "lines": {a commit: [when, added,
    removed]}}; none of another version's, or of a damaged one's."""
    kept = statefile.read(os.path.join(state, INDEX))
    kept = kept if kept.get("version") == VERSION else {}
    found = {path: entry for path, entry in obj(kept.get("files")).items() if whole(entry)}
    lines = {sha: one for sha, one in obj(kept.get("lines")).items() if isinstance(sha, str) and SHA.fullmatch(sha)
             and isinstance(one, list) and len(one) == 3 and all(type(n) is int for n in one)}
    return {"version": VERSION, "files": found if len(found) == len(obj(kept.get("files"))) else {},
            "lines": lines if len(lines) == len(obj(kept.get("lines"))) else {}}


def keep_lines(state, lines):
    """LINES ({a commit: [when, added, removed]}) kept in the index with those it has, the LINES newest; a failure is
    nothing kept (they are counted again)."""
    def change(_):
        was = load(state)
        newest = sorted({**was["lines"], **lines}.items(), key=lambda one: one[1][0])[-LINES:]
        return {**was, "lines": dict(newest)}
    try:
        statefile.update(os.path.join(state, INDEX), change, separators=(",", ":"))
    except OSError:
        pass


def index(state, home=None, most=tokens.MOST):
    """The index in STATE brought up to date with HOME's Claude sessions (this user's), one writer at a time: a file
    that grew read on from where it stopped, MOST bytes a call (the oldest first), one that is gone dropped, one that
    got shorter read again. The files in it, the bytes read and left."""
    path = os.path.join(state, INDEX)
    with statefile.locked(path):
        was, found = load(state), []
        kept = was["files"]
        for one in tokens.files(home or os.path.expanduser("~"))["claude"]:
            try:
                info = os.stat(one)
            except OSError:
                continue
            if stat.S_ISREG(info.st_mode):
                found.append((info.st_mtime, one, info.st_size))
        sizes = {one: size for _, one, size in found}
        entries = {one: entry for one, entry in kept.items() if entry["offset"] <= sizes.get(one, -1)}
        read, left = 0, 0
        for mtime, one, size in sorted(found):
            entry = entries.get(one)
            if entry and entry.get("size") == size and entry.get("mtime") == mtime:
                continue
            while read < most:
                entry = entries.setdefault(one, {"offset": 0, "session": session_of(one), "edits": {}, "made": []})
                before, room = entry["offset"], min(tokens.CHUNK, most - read)
                try:
                    edits, made, entry["offset"] = told(one, before, room)
                except OSError:
                    break                   # as it was: the next look tries again
                for at, file in edits:
                    entry["edits"].setdefault(file, []).append(at)
                entry["made"] += [sha for sha in made if sha not in entry["made"]]
                read += entry["offset"] - before
                if entry["offset"] - before < room or entry["offset"] >= size:
                    entry.update(size=size, mtime=mtime)
                    break
            if not entry or entry.get("size") != size or entry.get("mtime") != mtime:
                if entry:
                    entry["size"] = -1
                left += max(0, size - (entry["offset"] if entry else 0))
        if read or len(entries) < len(kept) or not os.path.exists(path):
            statefile.write(path, {**was, "files": entries}, separators=(",", ":"))
    return {"files": len(entries), "read": read, "left": left}


def sessions(index):
    """INDEX's (load()'s) files by session: {session: {"edits": {file: when, in order}, "made": [commits named]}}."""
    found = {}
    for entry in index["files"].values():
        one = found.setdefault(entry["session"], {"edits": {}, "made": []})
        for file, times in entry["edits"].items():
            one["edits"][file] = sorted(one["edits"].get(file, []) + times)
        one["made"] += [sha for sha in entry["made"] if sha not in one["made"]]
    return found


# --- the repository

def run(repo, *args, stdin=None):
    """git ARGS in REPO, only reading, as git.py runs it (no optional lock, no prompt, no terminal to read) and with
    no program REPO's config names: no fsmonitor, signature check, external diff, text conversion or pager. Its
    output, None when it failed or there is no git."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_LITERAL_PATHSPECS="1", LC_ALL="C",
               GIT_PAGER="cat")
    given = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
    try:
        done = subprocess.run([GIT, "--no-pager", "-c", "core.fsmonitor=false", "-c", "log.showSignature=false",
                               "-C", repo, *args], capture_output=True, timeout=TIMEOUT, env=env,
                              start_new_session=True, text=True, encoding="utf-8", errors="replace", **given)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def logged(repo, *args, stdin=None):
    """REPO's commits git log ARGS lists (with --name-only or --numstat), [{"sha", "at": when it was committed,
    "files": the paths it touched, "added", "removed": its lines where counted}]; None when git cannot tell."""
    out = run(repo, "log", "--no-renames", "--no-ext-diff", "--no-textconv", "-z", "--format=%x01%H%x00%ct", *args,
              stdin=stdin)
    if out is None:
        return None
    found = []
    for part in out.split("\x01")[1:]:
        sha, at, *files = part.split("\0")
        lines = [file.lstrip("\n").split("\t", 2) for file in files if file.strip()]
        if SHA.fullmatch(sha) and at.isdigit():
            found.append({"sha": sha, "at": int(at), "files": [line[-1] for line in lines],
                          "added": sum(int(line[0]) for line in lines if len(line) == 3 and line[0].isdigit()),
                          "removed": sum(int(line[1]) for line in lines if len(line) == 3 and line[1].isdigit())})
    return found


def history(repo, since, until):
    """REPO's commits on its branches from SINCE until UNTIL (seconds since 1970) with the files each touched, merges
    left out; None when git cannot tell (no repository, no git)."""
    return logged(repo, "--name-only", f"--since={since}", f"--until={until}", "--no-merges", "HEAD", "--branches",
                  "--")


def whole_ids(repo, shas):
    """SHAS (as a result named them, short) that are commits of REPO's, {short: its whole id}; None when git cannot
    tell (asked with none too: whether there is a repository)."""
    asked = list(dict.fromkeys(sha for sha in shas if isinstance(sha, str) and SHA.fullmatch(sha)))
    out = run(repo, "cat-file", "--batch-check", stdin="".join(f"{sha}^{{commit}}\n" for sha in asked))
    if out is None:
        return None
    told = (line.split() for line in out.splitlines())      # in the order asked, a line each
    return {sha: line[0] for sha, line in zip(asked, told) if line[1:2] == ["commit"] and SHA.fullmatch(line[0])}


def followed(repo, edits, others, lately, made=()):
    """The commits of LATELY (history()'s) that followed one conversation's edits in REPO: each touched a file of
    EDITS ({file: when}) at most DAY after its last edit before the commit, with none of OTHERS (the other
    conversations' edits of it) between the two. Those among MADE (its own) are left out."""
    def inside(files):
        top = repo.rstrip(os.sep) + os.sep
        return {file[len(top):].replace(os.sep, "/"): times for file, times in files.items() if file.startswith(top)}

    mine, theirs, found = inside(edits), inside(others), []
    for one in lately if mine else ():
        for file in one["files"] if one["sha"] not in made else ():
            last = max((at for at in mine.get(file, ()) if at <= one["at"]), default=None)
            if last is not None and one["at"] - last <= DAY \
                    and not any(last < at <= one["at"] for at in theirs.get(file, ())):
                found.append(one["sha"])
                break
    return found


def in_repo(repo, talks, since=None, until=None, lines=None):
    """Each of TALKS' ({key: (the commits it named, its edits, the others' edits)}) commits in REPO from SINCE until
    UNTIL, {key: [{"sha", "added", "removed", "at", "how": "made" or "after"}] in time's order}; None when git cannot
    tell. Git runs three times at most: LINES ({a commit: [when, added, removed]}) saves the last and gets its own."""
    times = [at for _, edits, _ in talks.values() for file in edits.values() for at in file]
    ids = whole_ids(repo, [sha for made, _, _ in talks.values() for sha in made])
    lately = history(repo, min(times) if since is None else since, max(times) + DAY + 1 if until is None else until) \
        if times and ids is not None else []
    if ids is None or lately is None:
        return None
    hows = {}
    for key, (made, edits, others) in talks.items():
        own = {ids[sha] for sha in made if sha in ids}
        hows[key] = {**dict.fromkeys(followed(repo, edits, others, lately, own), "after"), **dict.fromkeys(own, "made")}
    lines = {} if lines is None else lines
    wanted = sorted({sha for how in hows.values() for sha in how if sha not in lines})
    counted = logged(repo, "--numstat", "--no-walk=unsorted", "--stdin",
                     stdin="".join(f"{sha}\n" for sha in wanted)) if wanted else []
    if counted is None:
        return None
    lines.update({one["sha"]: [one["at"], one["added"], one["removed"]] for one in counted})
    return {key: sorted(({"sha": sha, "added": lines[sha][1], "removed": lines[sha][2], "at": lines[sha][0],
                          "how": how[sha]} for sha in how if sha in lines
                         and (since is None or since <= lines[sha][0]) and (until is None or lines[sha][0] < until)),
                        key=lambda one: (one["at"], one["sha"])) for key, how in hows.items()}


def commits(repo, made, edits, others, since=None, until=None):
    """The commits from one conversation in the repository whose top is REPO, those committed from SINCE until UNTIL
    where given: MADE the commits its results named, EDITS its edits ({file: when}), OTHERS the other conversations'.
    None when git cannot tell."""
    found = in_repo(repo, {None: (made, edits, others)}, since, until)
    return found and found[None]


def found(told, wanted, since, until, lines=None):
    """The commits from each of WANTED's conversations ({session: the folder it started in}) from SINCE until UNTIL,
    by what TOLD (sessions()'s) has of every session: in the repositories its edited files and its folder are in
    (LINES: in_repo()'s). None for one not known: not in TOLD, in no repository, or git cannot tell."""
    every, tops, by_top, result = {}, {}, {}, dict.fromkeys(wanted)
    for session, one in told.items():
        for file, times in one["edits"].items():
            every.setdefault(file, []).extend((at, session) for at in times)
    for session in wanted:
        one = told.get(session)
        for folder in {wanted[session], *map(os.path.dirname, one["edits"])} if one else ():
            if folder and folder not in tops:
                tops[folder] = repo_top(folder)
            if folder and tops[folder]:
                others = {file: [at for at, whose in every[file] if whose != session] for file in one["edits"]}
                by_top.setdefault(tops[folder], {})[session] = (one["made"], one["edits"], others)
    for top, talks in by_top.items():
        for session, mine in (in_repo(top, talks, since, until, lines) or {}).items():
            known = {one["sha"] for one in result[session] or ()}
            result[session] = sorted((result[session] or []) + [one for one in mine if one["sha"] not in known],
                                     key=lambda one: (one["at"], one["sha"]))
    return result


def main(argv):
    """herdr-fold's Herdr app mod runs this, answering in JSON: index (the index brought up to date: the files in it,
    the bytes read and those left for the next call)."""
    if argv[1:] == ["index"]:
        print(json.dumps(index(statefile.folder())))
        return 0
    print("usage: commits.py index", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
