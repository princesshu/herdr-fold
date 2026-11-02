# Generated from core/git.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""The sidebar's git layer: nothing loses work silently (a pull is fast-forward only; no reset, clean or force push).
Every command runs without optional locks or prompts, with a time limit, a file name never read as a pattern. The
unasked status and diff run nothing a repository's config names (fsmonitor, filters, submodules); staging still does."""
import json
import os
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
class Commit:
    hash: str
    subject: str
    author: str
    refs: tuple
    head: bool


def run(root, *args, stdin=None, timeout=TIMEOUT):
    """git ARGS in ROOT, STDIN its input (else nothing to read), with no terminal to open: a repository's config can
    name /dev/stdin or /dev/tty for git to read, which would be the sidebar's own terminal and its keys."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_LITERAL_PATHSPECS="1", LC_ALL="C")
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    given = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
    try:
        return subprocess.run([GIT, "-c", "core.fsmonitor=false", "-c", "log.showSignature=false", "-C", root, *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                              env=env, start_new_session=True, **given)
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


def head(root):
    """The latest commit: (its hash, its message), or (None, "") without one."""
    out = run(root, "log", "-1", "--format=%H%n%B")
    if out.returncode != 0 or not out.stdout.strip():
        return None, ""
    sha, _, message = out.stdout.partition("\n")
    return sha.strip(), message


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


def stage_all(root, rest=False):
    """Every change status lists staged (never an ignored file, nor a repository of its own inside, "inner/"), as
    GitHub Desktop commits: with nothing staged yet, or REST: beside what is. (whether it worked, else the error)"""
    st = status(root)
    if st.error:
        return False, st.error
    paths = [c.path for c in st.changes if not c.path.endswith("/")] if rest or not st.staged else []
    out = run(root, "add", "-A", "--", *paths) if paths else None
    return (True, "") if out is None or out.returncode == 0 else (False, last_line(out))


def commit(root, message):
    """The staged changes committed, or every change with none staged (stage_all)."""
    ok, line = stage_all(root)
    if not ok:
        return False, line
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


def main(argv):
    """herdr-fold's Herdr app mod runs this on the repository's machine, answering in JSON: status ROOT, diff ROOT PATH
    (its text, else why there is none), stage ROOT (stage_all), commit ROOT MESSAGE, sync ROOT or push ROOT (whether
    each worked, else what to do)."""
    command, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    if command not in ("status", "diff", "stage", "commit", "sync", "push") or \
            len(args) != (2 if command in ("diff", "commit") else 1):
        print("usage: git.py status|stage|sync|push ROOT, git.py diff ROOT PATH, git.py commit ROOT MESSAGE",
              file=sys.stderr)
        return 2
    if command == "status":
        st = status(args[0])
        answer = dict(asdict(st), ignored=sorted(st.ignored))
    elif command == "diff":
        text, error = diff(*args)
        answer = {"text": text, "error": error}
    else:
        ok, line = {"stage": stage_all, "commit": commit, "sync": sync, "push": push}[command](*args)
        answer = {"ok": ok, "advice": None if ok else advice(line)}
    print(json.dumps(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
