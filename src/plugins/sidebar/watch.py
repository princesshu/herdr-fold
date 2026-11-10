"""The sidebar's change watching by modification times (Python has no file system events): the open folders and git's
index, HEAD and refs. It slows down when idle, and asks for git status on a slow beat too, since a file edited in place
does not change its folder's time; never more often than the repository's speed allows."""
import os
import time

ACTIVE, QUIET = 30, 300                       # seconds after the last activity
PACES = (1.0, 3.0, 10.0)                      # poll interval: active, quiet, idle
BEAT_SHOWN, BEAT_HIDDEN = 5.0, 15.0           # git status beat, with Changes shown or not
CHANGE_GAP, CHANGE_FACTOR, BEAT_FACTOR = 0.5, 10, 50
GIT_FILES = ("index", "HEAD", "packed-refs", "FETCH_HEAD", "ORIG_HEAD", "MERGE_HEAD")


def stamp(path):
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return None


def code(folder):
    """The stamps of FOLDER's Python files: a new version of the program changes them (None: no folder)."""
    try:
        names = sorted(name for name in os.listdir(folder) if name.endswith(".py"))
    except OSError:
        return None
    return tuple((name, stamp(os.path.join(folder, name))) for name in names)


class Watcher:
    def __init__(self, dirs_fn, git_dir, clock=time.monotonic):
        self.dirs_fn, self.git_dir, self.clock = dirs_fn, git_dir, clock
        self.seen, self.git_seen = {}, None
        self.active_at = clock()
        self.last_status = None
        self.unanswered = None                    # when a change no git status started since was first seen

    def git_stamp(self):
        if not self.git_dir:
            return None
        files = [os.path.join(self.git_dir, name) for name in GIT_FILES]
        for base in ("heads", "remotes"):
            for folder, _, names in os.walk(os.path.join(self.git_dir, "refs", base)):
                files += [os.path.join(folder, name) for name in sorted(names)]
        return tuple((path, stamp(path)) for path in files)

    def poll(self):
        """The open folders that changed since the last poll, and "git" if git's state did (the first poll only
        records)."""
        current = {path: stamp(path) for path in self.dirs_fn()}
        changed = {path for path, value in current.items() if path in self.seen and self.seen[path] != value}
        self.seen = current
        git = self.git_stamp()
        if self.git_seen is not None and git != self.git_seen:
            changed.add("git")
        self.git_seen = git
        if changed:
            self.touch()
        return changed

    def touch(self):
        """Something happened (a change, a key, a click): poll at the active pace again."""
        self.active_at = self.clock()

    def interval(self):
        idle = self.clock() - self.active_at
        return PACES[0] if idle <= ACTIVE else PACES[1] if idle <= QUIET else PACES[2]

    def status_due(self, changed, scm_shown):
        """Whether a git status is due: after a change (kept until one answers it) as soon as the repository's speed
        allows, else on the slow beat."""
        if changed and self.unanswered is None:
            self.unanswered = self.clock()
        if self.last_status is None:
            return True
        started, finished = self.last_status
        took, since = finished - started, self.clock() - finished
        if self.unanswered is not None:
            return since >= max(CHANGE_GAP, CHANGE_FACTOR * took)
        return since >= max(BEAT_SHOWN if scm_shown else BEAT_HIDDEN, BEAT_FACTOR * took)

    def status_done(self, started, finished):
        self.last_status = (started, finished)
        if self.unanswered is not None and started >= self.unanswered:
            self.unanswered = None
