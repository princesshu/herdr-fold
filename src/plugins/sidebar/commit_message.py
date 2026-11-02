# Generated from core/commit_message.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""The commit message writer, shared by the sidebar, Cmd+Shift+C and herdr-fold's Herdr app mod (JSON from REPO):
Claude Haiku, then Codex, both without tools, write it from the staged changes only. A message with a secret or private
name the changes lack is dropped (a diff can steer an AI); a squashed one is asked again. Returns data, not words."""
import fnmatch
import getpass
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import asdict, dataclass, field, replace

MAX_DIFF = 60_000
# file names that look like a secret's: named before such a file is committed, its contents never shown to an AI
SECRET_LOOKING = (".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ecdsa*", "id_ed25519*",
                  "*credentials*", "*secret*")
SUBJECT_MAX = 72
CODEX_MODEL, CODEX_EFFORT = "gpt-6-luna", 'model_reasoning_effort="low"'
TIMEOUTS = {"claude": 120, "codex": 180}
# the /commit skill's or command's rules: the repository's first, then the shared ones under ~/.claude
RULE_FILES = [".claude/skills/commit/SKILL.md", ".claude/commands/commit.md", ".agents/skills/commit/SKILL.md"]
SHAPE = ("Output ONLY the message: a subject line of at most 72 characters, a blank line, then a body: one imperative "
         "bullet per distinct change, wrapped at 72 characters, covering every group of changed files. Do not merge "
         "changes into one vague line, do not write \"update files\" or \"various fixes\". No quotes, no code fences.")
PROMPT = ("Write a git commit message in English for the staged changes below, and describe only them. Match the "
          "style of the recent commit subjects shown (for example Conventional Commits, if they use it). " + SHAPE)
RULES_PROMPT = ("Write the git commit message for the staged changes below, and describe only them, strictly following "
                "the commit message rules of this repository, quoted between the RULES markers. The message is always "
                "in English. Parts of the rules about running git commands, staging files or formatting the answer "
                "(code blocks, introductions) do not apply here: you only get the diff, and you must output ONLY the "
                "plain commit message text. Unless the rules explicitly forbid a body: " + SHAPE)
# a diff can carry instructions, so the AIs get nothing to act with and nothing private to copy: no tools, MCP servers,
# memories, hooks or plugins, Claude no CLAUDE.md (a Codex that does not know a switch does not run); Codex still reads
# its global instructions, so a message is checked for private names (foreign)
CLAUDE_LOCKED = ["--tools", "", "--strict-mcp-config", "--setting-sources", ""]
CLAUDE_ENV = {"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}
CODEX_LOCKED = [arg for feature in ("shell_tool", "view_image", "apps", "plugins", "browser_use", "in_app_browser",
                                    "computer_use", "standalone_web_search", "multi_agent", "memories", "hooks")
                for arg in ("--disable", feature)] + ["-c", 'web_search="disabled"', "-c", "mcp_servers={}"]
AGAIN = "\n\nThe previous answer was too short: add the body with one bullet per change, as described."
# what a message may hold only if the text it was written from does
PRIVATE = (("secret", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}|\bsk-(?:ant-)?[\w-]{20,}"
                                 r"|AKIA[0-9A-Z]{16}|xox[abpr]-[\w-]{10,}|AIza[\w-]{30,}"
                                 r"|-----BEGIN [A-Z ]*PRIVATE KEY")),
           ("email", re.compile(r"\b[\w.%+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b")),
           ("home", re.compile(r"(?:/(?:Users|home)/|\b[A-Za-z]:[\\/]Users[\\/])[^/\\\s]+")),
           ("ip", re.compile(r"(?<![\w.])\d{1,3}(?:\.\d{1,3}){3}(?![\w.])")),
           ("tailnet", re.compile(r"\b[\w-]+\.tail[0-9a-f]+\.ts\.net\b|\btail[0-9a-f]{4,}\b")))
GENERIC_NAMES = {"", "localhost", "mac", "macbook", "macbook pro", "macbook air", "imac", "mac mini", "mac studio"}


@dataclass
class Request:
    diff: str
    files: list
    subjects: str
    rules: str = None
    rules_from: str = None


@dataclass(frozen=True)
class Problem:
    backend: str
    kind: str                 # missing, failed, empty, short, foreign
    detail: str = ""          # a failure's last line; the private kinds, comma-separated


# a problem in words: the sidebar's and the Herdr app's (Cmd+Shift+C words its own, in the installer's language)
WORDS = {"missing": "{0} is not installed", "failed": "{0} failed: {1}", "empty": "{0} gave no message",
         "short": "{0} wrote too short a message, twice", "foreign": "{0}'s message held what the changes do not: {1}"}


@dataclass
class Suggestion:
    message: str = None
    backend: str = None
    problems: list = field(default_factory=list)


def search_path():
    home = os.path.expanduser("~")
    extra = [os.path.join(home, ".local", "bin"), "/opt/homebrew/bin", "/usr/local/bin",
             os.path.join(home, ".bun", "bin"), os.path.join(home, ".npm-global", "bin")]
    extra += sorted(glob.glob(os.path.join(home, ".nvm", "versions", "node", "*", "bin")), reverse=True)
    return os.pathsep.join([os.environ.get("PATH", ""), *extra])


def find(name):
    """NAME on the PATH or in the usual places (herdr may start this process with a minimal PATH)."""
    return shutil.which(name, path=search_path())


def tool_env(binary):
    """The environment for an AI: the node next to an nvm-installed one on the PATH, the user name Claude finds its
    login by, and no herdr pane identity (an AI started here must not become the pane's agent)."""
    env = dict(os.environ, PATH=os.pathsep.join([os.path.dirname(binary), search_path()]))
    user = os.environ.get("USER") or getpass.getuser()
    env.update(USER=user, LOGNAME=os.environ.get("LOGNAME") or user)
    for name in ("HERDR_PANE_ID", "HERDR_PANE_RUNTIME_ID"):
        env.pop(name, None)
    return env


def git(root, *args):
    """git's plain output: no colors, whatever the user's settings say; no program the repository's own config names
    (fsmonitor, a signature check); nothing to read and no terminal to open (that config can name /dev/stdin or
    /dev/tty, the sidebar's own keys), and a time limit."""
    argv = [find("git") or "git", "-C", root, "-c", "color.ui=never", "-c", "core.fsmonitor=false",
            "-c", "log.showSignature=false", *args]
    try:
        return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                              stdin=subprocess.DEVNULL, start_new_session=True).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def rules(root):
    """(rules text, where they come from) of the /commit skill, or (None, None). The repository's own file is read only
    from inside it: a downloaded folder's may link to a key elsewhere, and the rules go to the AI."""
    home, inside = os.path.expanduser("~"), os.path.join(os.path.realpath(root), "")
    own = [os.path.join(root, f) for f in RULE_FILES]
    shared = [os.path.join(home, ".claude", "skills", "commit", "SKILL.md"),
              os.path.join(home, ".claude", "commands", "commit.md")]
    for path in own + shared:
        if not os.path.isfile(path) or (path in own and not os.path.realpath(path).startswith(inside)):
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if text.startswith("---"):
            text = text.split("---", 2)[-1]
        return text.strip(), os.path.relpath(path, root) if path in own else path.replace(home, "~")
    return None, None


def explain(problems):
    """Why no AI wrote a message, in one line."""
    return "; ".join(WORDS[p.kind].format(p.backend, p.detail) for p in problems)


def secret_looking(path):
    return any(fnmatch.fnmatch(os.path.basename(path), pattern) for pattern in SECRET_LOOKING)


def staged(root):
    return [path for path in git(root, "diff", "--cached", "--name-only", "-z").split("\0") if path]


def request(root):
    """What the AI gets: the staged diff only (cut at MAX_DIFF), without the contents of a file whose name looks like a
    secret's; every staged file; the recent subjects; the rules."""
    files = staged(root)
    withheld = [path for path in files if secret_looking(path)]
    diff = git(root, "diff", "--cached", "--no-ext-diff", "--no-textconv", "--", ":/",
               *(f":(top,exclude,literal){path}" for path in withheld))
    if len(diff) > MAX_DIFF:
        diff = diff[:MAX_DIFF] + "\n[diff truncated — the file list is complete]"
    if withheld:
        diff += "\n[left out, as their names look like secrets: " + ", ".join(withheld) + "]"
    text, where = rules(root)
    return Request(diff, files, git(root, "log", "-8", "--pretty=%s"), text, where)


def context(req):
    head = f"<<RULES\n{req.rules}\nRULES>>" if req.rules else f"Recent commit subjects:\n{req.subjects or '(none)'}"
    return f"{head}\n\nChanged files:\n" + "\n".join(req.files) + f"\n\nStaged diff:\n{req.diff}"


def clean(message):
    """MESSAGE as a commit message: no code fence, no quotes round it, and no control character (a diff can carry escape
    codes and ask the model to repeat them); tabs and line breaks stay."""
    lines = [line for line in (message or "").strip().splitlines() if not line.strip().startswith("```")]
    lines = ["".join(ch for ch in line if ch.isprintable() or ch == "\t") for line in lines]
    return "\n".join(lines).strip().strip('"').strip("'").strip()


def well_formed(message, file_count):
    lines = message.splitlines()
    if not lines or len(lines[0]) > SUBJECT_MAX:
        return False
    return file_count <= 1 or any(line.lstrip().startswith(("- ", "* ")) for line in lines[1:])


def fold(text):
    """TEXT in lowercase without its accents, whichever Unicode form it is in."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)).lower()


def own_names():
    """The names a message must not hold unless the changes do, folded: this machine's names and its owner's full
    name."""
    names = [socket.gethostname().split(".")[0]]
    if shutil.which("scutil"):                            # a Mac: its network and computer names
        for key in ("LocalHostName", "ComputerName"):
            names.append(subprocess.run(["scutil", "--get", key], capture_output=True, text=True).stdout.strip())
    try:
        import pwd
        person = pwd.getpwuid(os.getuid())
        full = person.pw_gecos.split(",")[0].strip()
        if full.lower() != person.pw_name.lower():
            names.append(full)
    except (ImportError, KeyError):                       # Windows, or an account without an entry
        pass
    return {fold(name) for name in names if fold(name) not in GENERIC_NAMES}


def holds(text, name):
    """Whether folded TEXT holds NAME: a short one (under five letters) only as a whole word."""
    return name in text if len(name) >= 5 else re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", text)


def foreign(message, source):
    """The private kinds MESSAGE holds that SOURCE, the text it was written from, does not."""
    found = [kind for kind, pattern in PRIVATE if any(m.group(0) not in source for m in pattern.finditer(message))]
    said, given = fold(message), fold(source)
    if any(holds(said, name) and not holds(given, name) for name in own_names()):
        found.append("name")
    return found


def ask(backend, binary, prompt, text, model=True):
    """One answer from BACKEND: (message, None) or (None, the reason)."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            if backend == "claude":
                out = subprocess.run([binary, "-p", "--model", "haiku", "--no-session-persistence", *CLAUDE_LOCKED,
                                      prompt], input=text, capture_output=True, text=True, cwd=tmp,
                                     timeout=TIMEOUTS[backend], env=dict(tool_env(binary), **CLAUDE_ENV))
                answer = out.stdout if out.returncode == 0 else ""
            else:
                result = os.path.join(tmp, "message.txt")
                argv = [binary, "exec", "--ephemeral", "--skip-git-repo-check", "-s", "read-only", *CODEX_LOCKED]
                argv += ["-m", CODEX_MODEL, "-c", CODEX_EFFORT] if model else []
                out = subprocess.run(argv + ["-C", tmp, "-o", result, prompt], input=text, capture_output=True,
                                     text=True, timeout=TIMEOUTS[backend], env=tool_env(binary))
                answer = ""
                if out.returncode == 0 and os.path.exists(result):
                    with open(result, encoding="utf-8") as f:
                        answer = f.read()
        except (OSError, subprocess.TimeoutExpired) as err:
            return None, str(err)
    message = clean(answer)
    if message:
        return message, None
    return None, ((out.stderr or "").strip().splitlines() or [""])[-1][:120]


def write(req, order=None, which=find):
    """A detailed message for REQ, trying each AI of ORDER (HERDR_COMMIT_AI, else Claude then Codex)."""
    order = order or ([os.environ["HERDR_COMMIT_AI"]] if os.environ.get("HERDR_COMMIT_AI") else ["claude", "codex"])
    prompt, text, problems = (RULES_PROMPT if req.rules else PROMPT), context(req), []
    for backend in order:
        binary = which(backend)
        if not binary:
            problems.append(Problem(backend, "missing"))
            continue
        model = True
        message, reason = ask(backend, binary, prompt, text, model)
        if message is None and backend == "codex":
            model = False                                     # the small model is unknown or failed: Codex's own
            message, reason = ask(backend, binary, prompt, text, model)
        if message is not None and not well_formed(message, len(req.files)):
            message, reason = ask(backend, binary, prompt + AGAIN, text, model)
            if message is not None and not well_formed(message, len(req.files)):
                problems.append(Problem(backend, "short"))
                continue
        if message is None:
            problems.append(Problem(backend, "failed" if reason else "empty", reason or ""))
            continue
        held = foreign(message, context(replace(req, rules=None)))     # the changes: not what the rules name
        if held:
            problems.append(Problem(backend, "foreign", ",".join(held)))
            continue
        return Suggestion(message, backend, problems)
    return Suggestion(None, None, problems)


# --- the issue a commit closes: the sidebar links one to a repository's next commit (Issues view, a)

FIXES = ("Fixes", "Closes", "Resolves")      # the words with which a commit message closes an issue on GitHub
# the sidebar's own state folder, where its settings keep the linked issues (not HERDR_PLUGIN_STATE_DIR: in the commit
# window that names whichever plugin runs it)
SIDEBAR_STATE = os.path.join(os.path.expanduser("~"), ".local", "state", "herdr", "plugins", "herdr-fold.sidebar")


def fixes(message, number):
    """Whether MESSAGE closes issue NUMBER on GitHub (Fixes, Closes or Resolves #NUMBER)."""
    words = message.replace(":", " ").split()
    return any(word.capitalize() in FIXES and following == f"#{number}" for word, following in zip(words, words[1:]))


def with_fixes(message, number):
    """A written MESSAGE with issue NUMBER's Fixes line at its end, unless it closes the issue already (or there is
    none)."""
    if number is None or fixes(message, number):
        return message
    return f"{message.rstrip()}\n\nFixes #{number}"


def linked_issue(repo, state=None):
    """The issue the sidebar linked to REPO's next commit, (number, title), or None: from its settings in STATE (the
    sidebar's state folder by default)."""
    try:
        with open(os.path.join(state or SIDEBAR_STATE, "settings.json"), encoding="utf-8") as f:
            found = (json.load(f).get("linked") or {}).get(repo)
        return (int(found[0]), str(found[1])) if isinstance(found, list) and len(found) == 2 else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def main(argv):
    """herdr-fold's Herdr app mod runs this on the repository's machine, answering in JSON: write REPO (the message for
    its staged changes with the linked issue's Fixes line, who wrote it, why the others could not, the staged files),
    secrets REPO (the staged files named like secrets, asked before a commit)."""
    if len(argv) != 3 or argv[1] not in ("write", "secrets"):
        print("usage: commit_message.py write|secrets REPO", file=sys.stderr)
        return 2
    if argv[1] == "secrets":
        print(json.dumps({"secret_looking": [path for path in staged(argv[2]) if secret_looking(path)]}))
        return 0
    req = request(argv[2])
    found = write(req)
    linked = linked_issue(argv[2])
    print(json.dumps({"message": found.message and with_fixes(found.message, linked and linked[0]),
                      "backend": found.backend, "problems": [asdict(problem) for problem in found.problems],
                      "note": None if found.message else explain(found.problems),
                      "files": req.files, "secret_looking": [path for path in req.files if secret_looking(path)]}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
