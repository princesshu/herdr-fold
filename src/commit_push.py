"""Commit and push in one step, with an AI-written message (Cmd+Shift+C, in a herdr popup), in the focused pane's repo.
herdr starts it with a minimal PATH, so git, claude and codex are also looked for in nvm, Homebrew and ~/.local/bin."""
import os
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.append(os.path.join(HERE, "plugins", "sidebar"))     # last: its module names never shadow this folder's
import commit_message  # noqa: E402
from i18n import line, t  # noqa: E402
from tui import find, getkey, printable, read_line, wait_and_exit  # noqa: E402

LIST_MAX = 12


GIT = find("git") or "git"


def git(repo, *args, check=True, stdin=None):
    out = subprocess.run([GIT, "-C", repo, *args], capture_output=True, text=True, input=stdin)
    if check and out.returncode != 0:
        raise RuntimeError((out.stderr or out.stdout).strip())
    return out


def with_spinner(text, fn):
    """FN's result, with a spinner while it runs; an error inside FN is raised here, in the caller."""
    result = {}

    def work():
        try:
            result["value"] = fn()
        except BaseException as err:          # handed over to the caller's thread
            result["error"] = err
    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while worker.is_alive():
        print(f"\r{frames[i % len(frames)]} {text}", end="", flush=True)
        i += 1
        time.sleep(0.1)
    print("\r" + " " * (len(text) + 2) + "\r", end="")
    if "error" in result:
        raise result["error"]
    return result.get("value")


def describe(problem):
    """A problem of the message writer, in the catalog's words."""
    kinds = {"secret": t("commit.foreign_secret"), "email": t("commit.foreign_email"), "home": t("commit.foreign_home"),
             "ip": t("commit.foreign_ip"), "tailnet": t("commit.foreign_tailnet"), "name": t("commit.foreign_name")}
    texts = {"missing": t("commit.problem_missing"), "failed": t("commit.problem_failed", problem.detail),
             "empty": t("commit.problem_empty"), "short": t("commit.problem_short"),
             "foreign": t("commit.problem_foreign", ", ".join(kinds.get(k, k) for k in problem.detail.split(",") if k))}
    return f"{problem.backend}: {texts.get(problem.kind, problem.kind)}"


def edit_line(prompt, text):
    """Prefilled single-line editor (the macOS Python line editor cannot prefill).
    ←/→ move · Backspace/Delete delete · Ctrl+A/E line start/end · Ctrl+U clear line · Enter done · Esc = original."""
    buf, pos = list(text), len(text)
    while True:
        back = len(buf) - pos
        print("\r" + prompt + "".join(buf) + "\x1b[K" + (f"\x1b[{back}D" if back else ""), end="", flush=True)
        key = getkey()
        if key in ("\r", "\n"):
            print()
            return "".join(buf)
        if key == "\x1b":
            print()
            return text
        if key in ("\x7f", "\x08") and pos:
            pos -= 1
            del buf[pos]
        elif key == "\x1b[3~" and pos < len(buf):
            del buf[pos]
        elif key == "\x1b[D" and pos:
            pos -= 1
        elif key == "\x1b[C" and pos < len(buf):
            pos += 1
        elif key in ("\x01", "\x1b[H"):
            pos = 0
        elif key in ("\x05", "\x1b[F"):
            pos = len(buf)
        elif key == "\x15":
            buf, pos = [], 0
        elif len(key) == 1 and key.isprintable():
            buf.insert(pos, key)
            pos += 1


def edit(message):
    subject, _, body = message.partition("\n")
    new = edit_line("Subject: ", subject).strip()
    return (new + ("\n" + body if body else "")) if new else message


def sensitive(lines):
    """The paths in LINES whose file name looks like a secret's (.env, keys, credentials), whatever the length of the
    list: lines of `git status --porcelain` ("XY path", a rename "old -> new") or of `git diff --name-status`
    ("M<tab>path", a rename "R100<tab>old<tab>new")."""
    paths = (line.split("\t")[-1] if "\t" in line else line[3:].split(" -> ")[-1] for line in lines)
    return [path for path in (p.strip().strip('"') for p in paths) if commit_message.secret_looking(path)]


def warn_secrets(lines):
    found = sensitive(lines)
    if found:
        print("\n" + line("warn", t("commit.secrets")))
        for path in found:
            print(f"  {path}")


def status_lines(repo):
    """`git status --porcelain`, every file on its own line: a new folder's files too (a .env inside it is named)."""
    return git(repo, "status", "--porcelain", "--untracked-files=all").stdout.splitlines()


def file_row(line):
    """A file of `git status --porcelain` ("XY path") or of `git diff --name-status` ("M<tab>path", a rename
    "R100<tab>old<tab>new") lined up the same way: two columns for the letters, a space, the path."""
    if "\t" not in line:
        return line
    code, *paths = line.split("\t")
    return f"{code[0]:<2} {' → '.join(paths)}"


def show_files(title, lines, full=False):
    """The list, cut at LIST_MAX lines unless FULL (before everything gets committed, every file is shown)."""
    print(f"\n{title}")
    shown = lines if full else lines[:LIST_MAX]
    for l in shown:
        print(f"  {file_row(l)}")
    if len(lines) > len(shown):
        print("  " + t("commit.more", len(lines) - len(shown)))


def push(repo, branch, upstream):
    if upstream:
        out = git(repo, "push", check=False)
    elif git(repo, "remote", check=False).stdout.split():
        out = git(repo, "push", "-u", git(repo, "remote").stdout.split()[0], branch, check=False)
    else:
        print(line("skip", t("commit.no_remote")))
        return True
    if out.returncode == 0:
        print(line("ok", t("commit.pushed")))
        return True
    print(line("fail", t("commit.push_failed", (out.stderr or out.stdout).strip())))
    if any(needle in (out.stderr or "") for needle in ("[rejected]", "fetch first")):  # not a hook's [remote rejected]
        print("      " + t("commit.pull_first"))
    return False


def main():
    cwd = os.environ.get("HERDR_ACTIVE_PANE_CWD") or os.getcwd()
    top = git(cwd, "rev-parse", "--show-toplevel", check=False)
    if top.returncode != 0:
        print(line("fail", t("commit.not_a_repo", cwd)))
        wait_and_exit(1)
    repo = top.stdout.strip()
    branch = git(repo, "branch", "--show-current").stdout.strip() or "HEAD"
    up = git(repo, "rev-parse", "--abbrev-ref", "@{u}", check=False)
    upstream = up.stdout.strip() if up.returncode == 0 else ""
    print(t("commit.title", printable(os.path.basename(repo)),
            printable(branch + (" → " + upstream if upstream else ""))))

    staged = git(repo, "diff", "--cached", "--name-status").stdout.splitlines()
    if not staged:
        changes = status_lines(repo)
        if not changes:
            ahead = (int(git(repo, "rev-list", "--count", "@{u}..HEAD", check=False).stdout.strip() or 0)
                     if upstream else 0)
            if ahead:
                print("\n" + t("commit.push_ahead", ahead))
                if getkey() in ("\r", "\n"):
                    wait_and_exit(0 if push(repo, branch, upstream) else 1)
                sys.exit(0)
            print("\n" + t("commit.nothing"))
            wait_and_exit()
        show_files(t("commit.changes"), changes, full=True)
        warn_secrets(changes)
        print("\n" + t("commit.all_ask"))
        if getkey() not in ("\r", "\n"):
            sys.exit(0)
        git(repo, "add", "-A")
        staged = git(repo, "diff", "--cached", "--name-status").stdout.splitlines()
    else:
        rest = [l for l in status_lines(repo) if l[1:2] not in (" ", "")]
        if rest:
            show_files(t("commit.staged"), staged)
            show_files(t("commit.not_staged"), rest, full=True)
            warn_secrets(staged + rest)
            print("\n" + t("commit.include_ask"))
            key = getkey()
            if key in ("\r", "\n"):
                git(repo, "add", "-A")
                staged = git(repo, "diff", "--cached", "--name-status").stdout.splitlines()
            elif key != "s":
                sys.exit(0)
        elif sensitive(staged):
            show_files(t("commit.staged"), staged)
            warn_secrets(staged)
            print("\n" + t("commit.secrets_ask"))
            if getkey() not in ("\r", "\n"):
                sys.exit(0)
    show_files(t("commit.to_commit"), staged)

    req = commit_message.request(repo)
    linked = commit_message.linked_issue(repo)          # the issue the sidebar linked to this commit: its Fixes line
    message = None
    while True:
        if message is None:
            try:
                suggestion = with_spinner(
                    t("commit.writing_rules", req.rules_from) if req.rules else t("commit.writing"),
                    lambda: commit_message.write(req))
                message, backend = suggestion.message, suggestion.backend
                if message:
                    message = commit_message.with_fixes(message, linked and linked[0])
                reason = "; ".join(describe(problem) for problem in suggestion.problems)
            except Exception as err:              # any failure: the message is asked for instead
                message, reason = None, str(err) or type(err).__name__
            if not message:
                print("\n" + line("warn", t("commit.no_message", reason)))
                message = read_line(t("commit.message_prompt") + " ").strip()
                if not message:
                    sys.exit(0)
                backend = t("commit.by_you")
        print("\n" + (t("commit.message_rules", backend, req.rules_from) if req.rules else t("commit.message", backend))
              + "\n")
        print("\n".join("  " + l for l in message.splitlines()))
        print("\n" + t("commit.message_keys"))
        key = getkey()
        if key in ("\r", "\n"):
            break
        if key == "e":
            message, backend = edit(message), t("commit.edited")
        elif key == "r":
            message = None
        elif key in ("\x1b", "q", "\x03"):
            print(t("commit.canceled"))
            time.sleep(1)
            sys.exit(0)

    print()
    commit = git(repo, "commit", "-F", "-", stdin=message, check=False)
    if commit.returncode != 0:
        print(line("fail", t("commit.failed", (commit.stderr or commit.stdout).strip())))
        wait_and_exit(1)
    print(line("ok", t("commit.done", git(repo, "rev-parse", "--short", "HEAD").stdout.strip())))
    if push(repo, branch, upstream):
        time.sleep(1.5)
        sys.exit(0)
    wait_and_exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except RuntimeError as err:
        print(line("fail", str(err)))
        wait_and_exit(1)
