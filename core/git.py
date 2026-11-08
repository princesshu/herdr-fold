"""The sidebar's git layer: nothing loses work silently (a pull is fast-forward only; no reset, clean or force push).
Every command runs without optional locks or prompts, with a time limit, a file name never read as a pattern. The
unasked status and diff run nothing a repository's config names (fsmonitor, filters, submodules); staging still does."""
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field

TIMEOUT = 60
NO_STATUS = "No status: a filter in its git config cannot be turned off"
NO_DIFF = "No diff: a filter in its git config cannot be turned off"
GIT = shutil.which("git") or next(
    (p for p in ("/usr/bin/git", "/opt/homebrew/bin/git", "/usr/local/bin/git") if os.path.exists(p)), "git")


@dataclass(frozen=True)
class Change:
    path: str
    code: str                 # M, A, D, R, U (conflict), ? (untracked)


@dataclass
class Status:
    branch: str = None        # None: a detached HEAD (or not a repository)
    upstream: str = None
    ahead: int = 0
    behind: int = 0
    staged: list = field(default_factory=list)
    changes: list = field(default_factory=list)
    ignored: set = field(default_factory=set)       # paths from the root; a folder ends in "/"
    error: str = None


@dataclass(frozen=True)
class Place:
    name: str                 # the repository's: its main checkout's folder, a worktree's too
    branch: str               # None: a detached HEAD
    ahead: int
    behind: int
    repo: str                 # its .git folder, the same for each of its worktrees
    linked: bool              # a worktree beside the main checkout


@dataclass(frozen=True)
class Commit:
    hash: str
    subject: str
    author: str
    refs: tuple
    head: bool


def run(root, *args, stdin=None, timeout=TIMEOUT, binary=False):
    """git ARGS in ROOT, STDIN its input (else nothing to read), with no terminal to open: a repository's config can
    name /dev/stdin or /dev/tty for git to read, which would be the sidebar's own terminal and its keys. BINARY: its
    output as bytes."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_LITERAL_PATHSPECS="1", LC_ALL="C")
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    given = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
    text = {} if binary else {"text": True, "encoding": "utf-8", "errors": "replace"}
    try:
        return subprocess.run([GIT, "-c", "core.fsmonitor=false", "-c", "log.showSignature=false", "-C", root, *args],
                              capture_output=True, timeout=timeout, env=env, start_new_session=True, **text, **given)
    except FileNotFoundError:
        return subprocess.CompletedProcess([GIT], 1, "", "git is not installed")
    except (OSError, subprocess.TimeoutExpired) as err:
        return subprocess.CompletedProcess([GIT], 1, "", str(err))


def last_line(out):
    lines = [line.strip() for line in (out.stderr or out.stdout or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def top(path):
    out = run(path, "rev-parse", "--show-toplevel")
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


def git_dir(path):
    """The repository's own folder (.git, or where a worktree's .git file points), or None outside a repository."""
    out = run(path, "rev-parse", "--absolute-git-dir")
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


def no_filters(root):
    """The -c arguments that turn off every filter driver git knows at ROOT (each command empty, none required): a
    repository's own could run anything (git-lfs may then show a file as changed until git looks again). None when the
    config cannot be read or a driver's name cannot round-trip through -c (an =, a non-UTF-8 byte, a control char)."""
    out = run(root, "config", "-z", "--name-only", "--get-regexp", r"^filter\.")
    if out.returncode not in (0, 1):                     # 1: no filter at all
        return None
    names = {key.rsplit(".", 1)[0] for key in out.stdout.split("\0") if key}
    if any("=" in name or "\ufffd" in name or not name.isprintable() for name in names):
        return None
    return [arg for name in sorted(names)
            for arg in ("-c", f"{name}.clean=", "-c", f"{name}.smudge=", "-c", f"{name}.process=",
                        "-c", f"{name}.required=false")]


def place(path):
    """Where PATH is, as the Herdr app mod's Spaces list names it, or None outside a repository; no file is read, so
    nothing a repository's config names runs. git that cannot answer (a folder gone) raises RuntimeError."""
    where = run(path, "rev-parse", "--show-toplevel", "--git-common-dir")
    if where.returncode != 0:
        if "not a git repository" in where.stderr:
            return None
        raise RuntimeError(last_line(where) or "git did not answer")
    top, common = where.stdout.splitlines()[:2]
    common = os.path.realpath(os.path.join(path, common))      # relative to PATH before git 2.31's --path-format
    linked = common != os.path.realpath(os.path.join(top, ".git"))
    name = os.path.basename(os.path.dirname(common) if os.path.basename(common) == ".git" else common)
    branch = run(path, "symbolic-ref", "--short", "-q", "HEAD").stdout.strip() or None
    counts = run(path, "rev-list", "--left-right", "--count", "HEAD...@{upstream}").stdout.split()
    ahead, behind = (int(n) for n in counts) if len(counts) == 2 else (0, 0)
    return Place(name[:-4] if name.endswith(".git") else name, branch, ahead, behind, common, linked)


def status(root):
    off = no_filters(root)
    if off is None:
        return Status(error=NO_STATUS)
    out = run(root, *off, "status", "--porcelain=v2", "-z", "--branch", "--ignored=matching",
              "--untracked-files=all", "--ignore-submodules=dirty")
    if out.returncode != 0:
        return Status(error=last_line(out) or "not a git repository")
    st = Status()
    fields, i = out.stdout.split("\0"), 0

    def add(xy, path):
        x, y = xy[0], xy[1]
        if x != ".":
            st.staged.append(Change(path, x if x in "ADR" else "M"))
        if y != ".":
            st.changes.append(Change(path, "D" if y == "D" else "M"))

    while i < len(fields):
        entry = fields[i]
        i += 1
        if entry.startswith("# branch.head "):
            head = entry[len("# branch.head "):]
            st.branch = None if head == "(detached)" else head
        elif entry.startswith("# branch.upstream "):
            st.upstream = entry[len("# branch.upstream "):]
        elif entry.startswith("# branch.ab "):
            ahead, behind = entry[len("# branch.ab "):].split()
            st.ahead, st.behind = int(ahead[1:]), int(behind[1:])
        elif entry.startswith("1 "):
            parts = entry.split(" ", 8)
            add(parts[1], parts[8])
        elif entry.startswith("2 "):
            parts = entry.split(" ", 9)
            add(parts[1], parts[9])
            i += 1                                          # the rename's earlier path
        elif entry.startswith("u "):
            st.changes.append(Change(entry.split(" ", 10)[10], "U"))
        elif entry.startswith("? "):
            st.changes.append(Change(entry[2:], "?"))
        elif entry.startswith("! "):
            st.ignored.add(entry[2:])
    # a file .gitignore names is no change, even one committed before it named it
    tracked_ignored = set(run(root, "ls-files", "-ci", "--exclude-standard", "-z").stdout.split("\0")) - {""}
    st.changes = [c for c in st.changes if c.path not in tracked_ignored]
    return st


def diff(root, path):
    """PATH's diff against the last commit, an untracked file's as all added: (its text, else why there is none)."""
    off = no_filters(root)
    if off is None:
        return "", NO_DIFF
    tracked = run(root, "ls-files", "-z", "--", path).stdout
    against = ["HEAD", "--", path] if tracked else ["--no-index", "--", os.devnull, path]
    out = run(root, *off, "diff", "--no-ext-diff", "--no-textconv", "--no-color", "--ignore-submodules=dirty",
              *against)
    return out.stdout, (last_line(out) or "No diff") if out.returncode > 1 else None    # --no-index: 1, they differ


def committed(root, path, out, at="HEAD"):
    """PATH as the last commit has it (AT "": as the index has it), written to OUT (a changed picture's before): git's
    own bytes, as cat-file gives them with no filter run; whether it was there."""
    done = run(root, "cat-file", "blob", f"{at}:{path}", binary=True)     # one argument: never an option
    if done.returncode != 0:
        return False
    with open(out, "wb") as f:
        f.write(done.stdout)
    return True


def show(root, rev):
    """Commit REV's message and diff, REV a hash only (never a name or an option git would take): (its text, else why
    there is none)."""
    if not re.fullmatch(r"[0-9a-f]{4,40}", rev):
        return "", "Not a commit"
    off = no_filters(root)
    if off is None:
        return "", NO_DIFF
    out = run(root, *off, "show", "--no-ext-diff", "--no-textconv", "--no-color", "--ignore-submodules=dirty",
              "--format=%h  %an  %ar%n%n%B", rev, "--")                # the author by name, not by address
    return out.stdout, (last_line(out) or "Not a commit") if out.returncode else None


def stage(root, paths):
    out = run(root, "add", "--", *paths)
    return None if out.returncode == 0 else last_line(out)


def unstage(root, paths):
    out = run(root, "restore", "--staged", "--", *paths)
    if out.returncode != 0:                              # no commit yet: nothing to restore from
        out = run(root, "rm", "--cached", "-q", "--", *paths)
    return None if out.returncode == 0 else last_line(out)


def discard(root, path):
    """Undo a tracked file's unstaged change; None on success, else the error."""
    out = run(root, "restore", "--worktree", "--", path)
    return None if out.returncode == 0 else last_line(out)


def taken(changes):
    """The paths a commit of CHANGES takes: never a repository of its own inside ("inner/")."""
    return [c.path for c in changes if not c.path.endswith("/")]


def stage_all(root, rest=False):
    """Every change status lists staged (never an ignored file, nor a repository of its own inside, "inner/"), as
    GitHub Desktop commits: with nothing staged yet, or REST: beside what is. (whether it worked, else the error)"""
    st = status(root)
    if st.error:
        return False, st.error
    paths = taken(st.changes) if rest or not st.staged else []
    out = run(root, "add", "-A", "--", *paths) if paths else None
    return (True, "") if out is None or out.returncode == 0 else (False, last_line(out))


def commit(root, message, paths=None):
    """The staged changes committed, PATHS staged first (the changes a question about secrets saw: one come since
    waits), or without PATHS every change when none is staged (stage_all)."""
    if paths is None:
        ok, line = stage_all(root)
        if not ok:
            return False, line
    elif paths:
        out = run(root, "add", "-A", "--", *paths)
        if out.returncode != 0:
            return False, last_line(out)
    out = run(root, "commit", "-F", "-", stdin=message)
    return out.returncode == 0, last_line(out)


def push(root):
    """Push; a branch without an upstream goes to the first remote with -u. One whose upstream was deleted on the
    remote (merged, say) is not pushed back."""
    if run(root, "rev-parse", "--abbrev-ref", "@{u}").returncode == 0:
        out = run(root, "push")
        return out.returncode == 0, last_line(out)
    branch = run(root, "branch", "--show-current").stdout.strip()
    if branch and run(root, "config", "--get", f"branch.{branch}.merge").returncode == 0:
        return False, "its upstream branch is gone from the remote"
    remotes = run(root, "remote").stdout.split()
    if not remotes:
        return False, "no remote"
    if not branch:
        return False, "detached HEAD"
    out = run(root, "push", "-u", remotes[0], branch)
    return out.returncode == 0, last_line(out)


def pull(root):
    """Pull, fast-forward only: when the branches have diverged, nothing is merged and the reason comes back."""
    out = run(root, "pull", "--ff-only")
    return out.returncode == 0, last_line(out)


def sync(root):
    """Pull (fast-forward only), then push; a branch without an upstream is only pushed, with -u."""
    if run(root, "rev-parse", "--abbrev-ref", "@{u}").returncode == 0:
        ok, line = pull(root)
        if not ok:
            return ok, line
    return push(root)


# a failed pull or push, and the one line that says what to do
ADVICE = ((("Not possible to fast-forward", "diverged"), "The branches have diverged: merge or rebase in a terminal"),
          (("no remote", "No configured push destination", "does not appear to be a git repository"),
           "No remote to sync with: add one with git remote add"),
          (("Authentication failed", "Permission denied", "could not read Username"),
           "The remote refused the sign-in: sign in to it, then sync again"),
          (("upstream branch is gone",),
           "The branch was deleted on the remote: push it from a terminal to bring it back"))


def advice(line):
    return next((text for needles, text in ADVICE if any(needle in line for needle in needles)), line)


# github.com in a remote's address: https://[user@]github.com/OWNER/NAME[.git][/], git@github.com:OWNER/NAME[.git],
# ssh://git@github.com/OWNER/NAME[.git]
ADDRESS = re.compile(r"^(?:https?://(?:[^@/]+@)?|ssh://(?:[^@/]+@)?|[^@/:]+@)github\.com[:/]([\w.-]+)/([\w.-]+?)"
                     r"(?:\.git)?/?$")


def github_name(root):
    """OWNER/NAME of the repository at ROOT on GitHub: origin's when it is there, else the first other remote's;
    None without one (no repository, no remote, or none on github.com)."""
    out = run(root, "config", "--local", "--get-regexp", r"^remote\..*\.url$")
    if out.returncode != 0:
        return None
    found = {}
    for line in out.stdout.splitlines():
        key, _, url = line.partition(" ")
        match = ADDRESS.match(url.strip())
        if match:
            found.setdefault(key[len("remote."):-len(".url")], "/".join(match.groups()))
    return found.get("origin") or next(iter(found.values()), None)


def graph(root, n=20):
    out = run(root, "log", f"-n{n}", "--format=%h%x00%s%x00%an%x00%D%x1e")
    commits = []
    for record in out.stdout.split("\x1e") if out.returncode == 0 else []:
        if not record.strip():
            continue
        hash_, subject, author, decoration = record.strip("\n").split("\0")
        refs = [ref.strip() for ref in decoration.split(",") if ref.strip()]
        head = any(ref == "HEAD" or ref.startswith("HEAD -> ") for ref in refs)
        refs = tuple(ref[len("HEAD -> "):] if ref.startswith("HEAD -> ") else ref for ref in refs if ref != "HEAD")
        commits.append(Commit(hash_, subject, author, refs, head))
    return commits


# what the Herdr app mod asks for: the arguments each command takes after ROOT, at least and at most (None: any number)
COMMANDS = {"status": (0, 0), "place": (0, 0), "diff": (1, 1), "show": (1, 1), "graph": (0, 0), "github": (0, 0),
            "stage": (0, None), "unstage": (1, None), "discard": (1, 1), "commit": (1, 1), "sync": (0, 0),
            "push": (0, 0), "pull": (0, 0)}


def main(argv):
    """herdr-fold's Herdr app mod runs this on the repository's machine, answering in JSON: status, place, graph,
    github (its name on GitHub); diff, show (the text, else why there is none); stage (no PATH: every change), unstage,
    discard, commit, sync, push, pull (whether each worked, else what to do). COMMANDS, the usage: their arguments."""
    command, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    least, most = COMMANDS.get(command, (0, -1))                # an unknown command: no count fits
    given = len(args) - 1                                        # after ROOT
    if not args or given < least or (most is not None and given > most):
        print("usage: git.py status|place|graph|github|sync|push|pull ROOT, git.py diff|discard ROOT PATH, "
              "git.py show ROOT HASH, git.py stage ROOT [PATH…], git.py unstage ROOT PATH…, "
              "git.py commit ROOT MESSAGE", file=sys.stderr)
        return 2
    root, rest = args[0], args[1:]
    if command == "status":
        st = status(root)
        answer = dict(asdict(st), ignored=sorted(st.ignored))
    elif command == "place":
        try:
            found = place(root)
        except RuntimeError as err:                             # not a no: the mod asks again later
            print(err, file=sys.stderr)
            return 1
        answer = found and asdict(found)
    elif command in ("diff", "show"):
        text, error = (diff if command == "diff" else show)(root, *rest)
        answer = {"text": text, "error": error}
    elif command == "graph":
        answer = {"commits": [dict(asdict(c), refs=list(c.refs)) for c in graph(root)]}
    elif command == "github":
        answer = {"name": github_name(root)}
    else:
        if command in ("unstage", "discard") or (command == "stage" and rest):     # named files: None, or the error
            error = {"stage": stage, "unstage": unstage}[command](root, rest) if command != "discard" \
                else discard(root, rest[0])
            ok, line = error is None, error or ""
        else:
            act = {"stage": stage_all, "commit": commit, "sync": sync, "push": push, "pull": pull}[command]
            ok, line = act(root, *rest)
        answer = {"ok": ok, "advice": None if ok else advice(line)}
    print(json.dumps(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
