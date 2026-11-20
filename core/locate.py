"""Where things are on this machine, for the readers that run an agent or read a repository: a program on the PATH or
in the usual places and the environment it runs in, the repository a folder is in. Kept small: each helper the Herdr
app mod runs carries it whole, and Linux takes one argument of 128 KiB at most."""
import getpass
import glob
import os
import shutil


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


def dot_git(root):
    """ROOT's git folder when ROOT is a repository's top (a .git folder, or a worktree's .git file naming one), told as
    herdr tells it: by the HEAD there. Read from the files: nothing a repository's config names runs."""
    found = os.path.join(root, ".git")
    if os.path.isfile(found):
        try:
            with open(found, encoding="utf-8") as f:
                named = f.readline().strip()
        except (OSError, UnicodeDecodeError):
            return None
        if not named.startswith("gitdir:"):
            return None
        found = os.path.join(root, named[len("gitdir:"):].strip())
    return found if os.path.isfile(os.path.join(found, "HEAD")) else None


def repo_top(path):
    """The top of the repository PATH is in, looked for upwards as herdr does; None outside one."""
    path = os.path.normpath(path)
    while not dot_git(path):
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent
    return path
