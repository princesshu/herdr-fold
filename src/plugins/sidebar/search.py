"""The sidebar's search of the root or a folder or file in it: ripgrep, else git grep in a repository, else a built-in
search. Ignored files are never hits nor read; every program runs with no stdin, no terminal and a time limit. A line
ends only at a newline (no splitlines()), as ripgrep and git grep count; one Python regex marks the match everywhere."""
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field

MAX_FILE = 2_000_000
MAX_LINE = 500
TIMEOUT = 60                  # seconds a search's program may run: a repository's config can make git wait for good
QUICK = 10                    # seconds for git's look at a folder (whether it is a repository, its file list)
# how every program a search runs starts: with nothing to read and no terminal to open (a repository's config can
# name /dev/stdin or /dev/tty for git to read, which would be the sidebar's own terminal and its keys)
DETACHED = {"stdin": subprocess.DEVNULL, "start_new_session": True}


def stop(proc):
    """PROC and whatever it started (its own session, DETACHED): a child of it may hold the output open."""
    try:
        if os.name == "nt":
            proc.kill()
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass


@dataclass(frozen=True)
class Query:
    text: str
    case: bool = False
    word: bool = False
    regex: bool = False


@dataclass
class Hit:
    path: str
    line_no: int
    text: str
    spans: list = field(default_factory=list)


@dataclass
class Result:
    hits: list = field(default_factory=list)
    total: int = 0
    files: int = 0
    error: str = None


def pattern(query):
    """The Python regex for QUERY (the switches applied)."""
    body = query.text if query.regex else re.escape(query.text)
    if query.word:
        body = rf"\b(?:{body})\b"
    return re.compile(body, 0 if query.case else re.IGNORECASE)


class Collector:
    def __init__(self, regex, limit, folder=""):
        self.regex, self.limit, self.result, self.seen = regex, limit, Result(), set()
        self.prefix = folder + "/" if folder else ""      # the paths found in FOLDER, from the root

    def add(self, path, line_no, text):
        self.result.total += 1
        self.seen.add(path)
        if len(self.result.hits) < self.limit:
            text = text.rstrip("\r\n")[:MAX_LINE]
            spans = [m.span() for m in self.regex.finditer(text) if m.end() > m.start()]
            self.result.hits.append(Hit(self.prefix + path.replace(os.sep, "/"), line_no, text, spans))

    def done(self, error=None):
        self.result.files, self.result.error = len(self.seen), error
        return self.result


def stream(argv, cwd, cancel, parse, collector):
    """Run ARGV, handing each output line (split by PARSE) to the collector; None, or the error's last line. Its
    errors go to a file, not a pipe: a full pipe nobody reads would stop the command for good. A newer search, or
    TIMEOUT, stops it even while it says nothing."""
    with tempfile.TemporaryFile() as errors:
        try:
            proc = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=errors, **DETACHED)
        except OSError as err:
            return str(err)
        ended, late = threading.Event(), []

        def guard():
            deadline = time.monotonic() + TIMEOUT
            while not ended.wait(0.2):
                if (cancel is not None and cancel.is_set()) or time.monotonic() > deadline:
                    late.append(time.monotonic() > deadline)
                    stop(proc)
                    return

        threading.Thread(target=guard, daemon=True).start()
        for raw in proc.stdout:
            if cancel is not None and cancel.is_set():
                stop(proc)
                break
            parsed = parse(raw.decode("utf-8", "replace"))
            if parsed:
                collector.add(*parsed)
        proc.stdout.close()
        proc.wait()
        ended.set()
        errors.seek(max(0, errors.seek(0, 2) - 4096))
        err = errors.read().decode("utf-8", "replace").strip()
    if late == [True]:
        return f"the search took over {TIMEOUT} s and was stopped"
    return None if proc.returncode in (0, 1, -9) else (err.splitlines() or ["search failed"])[-1]


def parse_rg(line):
    path, _, rest = line.partition("\0")
    number, _, text = rest.partition(":")
    return (path, int(number), text) if number.isdigit() else None


def parse_git(line):
    parts = line.split("\0", 2)
    return (parts[0], int(parts[1]), parts[2]) if len(parts) == 3 and parts[1].isdigit() else None


def scan(root, paths, cancel, collector, inside=None):
    """The built-in search over PATHS (relative to ROOT): plain files inside INSIDE (the folder opened; ROOT by
    default) only, never a link (it may lead out of the folder), a pipe or a device (they may never end), told by what
    is opened, so a file swapped meanwhile is no way round it."""
    real = os.path.realpath(inside or root)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    for rel in paths:
        if cancel is not None and cancel.is_set():
            return
        full = os.path.join(root, rel)
        try:
            if os.path.commonpath([os.path.realpath(full), real]) != real:
                continue
            fd = os.open(full, flags)
        except (OSError, ValueError):
            continue
        with os.fdopen(fd, "rb") as f:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE:
                continue
            try:
                data = f.read()
            except OSError:
                continue
        if b"\0" in data[:8192]:
            continue                                        # a binary file
        lines = data.decode("utf-8", "replace").split("\n")
        if lines[-1] == "":
            lines.pop()
        for number, text in enumerate(lines, 1):
            if collector.regex.search(text):
                collector.add(rel, number, text.rstrip("\r"))


def walk(root, git=None):
    """The files under ROOT, hidden folders left out; a git repository in it by its own list (with GIT), so its ignored
    files (node_modules, build output) are neither hits nor read, as in a search inside it."""
    for folder, dirs, names in os.walk(root):
        inner = repo_files(git, folder) if git and os.path.lexists(os.path.join(folder, ".git")) else None
        if inner is not None:
            dirs[:] = []
            yield from (os.path.relpath(os.path.join(folder, path), root) for path in inner)
            continue
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(names):
            yield os.path.relpath(os.path.join(folder, name), root)


def repo_files(git, folder):
    """The files under FOLDER, in a git repository, as git sees them (tracked, and untracked ones not ignored), from
    FOLDER; None when git cannot list them. Its fsmonitor never runs; a path its list (a downloaded index) names
    outside FOLDER is left out."""
    try:
        listed = subprocess.run([git, "-c", "core.fsmonitor=false", "-C", folder, "ls-files", "-z", "-co",
                                 "--exclude-standard"], capture_output=True, timeout=QUICK, **DETACHED)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if listed.returncode:
        return None
    paths = (p for p in listed.stdout.decode("utf-8", "replace").split("\0") if p)
    return sorted(p for p in paths if not os.path.isabs(p) and os.path.normpath(p).split(os.sep)[0] != "..")


def in_repo(root, git):
    if git is None:
        return False
    try:
        return subprocess.run([git, "-C", root, "rev-parse", "--git-dir"], capture_output=True, timeout=QUICK,
                              **DETACHED).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def search(root, query, limit=2000, cancel=None, which=shutil.which, place=""):
    """QUERY in ROOT, or only in PLACE there: a folder or a file (from the root, with "/")."""
    if not query.text:
        return Result()
    try:
        regex = pattern(query)
    except re.error as err:
        return Result(error=f"invalid regex: {err}")
    path, opened = os.path.join(root, *place.split("/")) if place else root, os.path.realpath(root)
    if place and (os.path.islink(path) or os.path.commonpath([os.path.realpath(path), opened]) != opened):
        return Result()                                     # a link, or a way out of the folder: nothing searched
    if os.path.isfile(path):                                # a file: its lines, though ignored (it was asked for)
        collector = Collector(regex, limit, place.rpartition("/")[0])
        scan(os.path.dirname(path), [os.path.basename(path)], cancel, collector, opened)
        return collector.done()
    collector, root = Collector(regex, limit, place), path
    rg, git = which("rg"), which("git")
    if rg:
        argv = [rg, "--line-number", "--no-heading", "--color", "never", "--null", "--max-columns", str(MAX_LINE * 2)]
        argv += [] if query.regex else ["--fixed-strings"]
        argv += (["--word-regexp"] if query.word else []) + (["--case-sensitive"] if query.case else ["--ignore-case"])
        error = stream(argv + ["-e", query.text, "."], root, cancel, lambda l: strip_dot(parse_rg(l)), collector)
        return collector.done(error)
    if in_repo(root, git):
        argv = [git, "-c", "core.fsmonitor=false", "-C", root, "grep", "-n", "-I", "-z", "--untracked",
                "-P" if query.regex else "-F"]
        argv += (["-w"] if query.word else []) + ([] if query.case else ["-i"])
        error = stream(argv + ["-e", query.text], root, cancel, parse_git, collector)
        if not (query.regex and error):
            return collector.done(error)
        collector = Collector(regex, limit, place)           # no Perl regex in this git: git's file list instead
        scan(root, repo_files(git, root) or [], cancel, collector, opened)
        return collector.done()
    scan(root, walk(root, git), cancel, collector, opened)
    return collector.done()


def strip_dot(parsed):
    """Ripgrep's path without its leading ./ (.\\ on Windows)."""
    if parsed and parsed[0][:2] in ("./", ".\\"):
        return (parsed[0][2:],) + parsed[1:]
    return parsed
