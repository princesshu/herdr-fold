"""Shared test helpers: package paths, fake programs, a package copy to run in, per-test environment variables and
running a script in a pty. Tests import only from here, never from each other; src/ is on the import path.
"""
import json
import os
import pty
import queue
import re
import select
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import zlib

PACKAGE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SRC = os.path.join(PACKAGE, "src")
# No test reaches the live herdr: its socket (the code's, and a real herdr command's a test may start) is looked for
# where there is none, unless a test sets up a fake of its own (FakeHerdrSocket, set_env)
os.environ["HERDR_SOCKET_PATH"] = os.path.join("/tmp", f"herdr-fold-tests-{os.getpid()}-none.sock")
sys.path.insert(0, SRC)
# PowerShell 7 for the Windows scripts: the PWSH variable or pwsh on PATH; the tests that need it are skipped without
PWSH = os.environ.get("PWSH") or shutil.which("pwsh")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def is_webp(data):
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# [Y/n] in any language's letters, a prompt, "press Enter to start…", "press any key."
QUESTION_END = re.compile(r"(\[\w+/\w+\]|:|cancel\.|exit\.)$")

# ssh to a machine that is the temporary folder itself: its commands run right here, in $HOME; a PowerShell command
# (-File, or powershell -EncodedCommand) runs in PWSH, with Windows' backslashes turned into slashes
FAKE_SSH = r"""#!/bin/bash
while [ $# -gt 0 ]; do case "$1" in -o) shift 2 ;; -O) exit 0 ;; -*) shift ;; *) break ;; esac; done
shift
cd "$HOME" || exit 1
case "$*" in
  *" -File "*) set -- ${*//\\//}; while [ "$1" != -File ]; do shift; done; shift
    exec "$PWSH" -NoProfile -Command "function Get-ExecutionPolicy { 'Restricted' }; & ./$*" ;;
  powershell\ *) set -- $*; shift; a=(); for x in "$@"; do a+=("${x//\\//}"); done; exec "$PWSH" "${a[@]}" ;;
  *) exec bash -c "$*" ;;
esac
"""
# scp as a Windows SSH server with PowerShell as its shell answers it: the package never needs it
FAILING_SCP = "#!/bin/sh\necho 'scp: Connection closed' >&2\nexit 1\n"
# Windows' python, called with a backslashed script path
FAKE_PYTHON = r"""#!/bin/bash
f=${1//\\//}; shift
exec /usr/bin/python3 "$f" "$@"
"""
# A fake herdr's `plugin uninstall` / `unlink` ID, as herdr does it: the plugin list file ($1) no longer has ID ($2)
FORGET_PLUGIN = """/usr/bin/python3 -c 'import json, sys
listed = json.load(open(sys.argv[1]))
listed["result"]["plugins"] = [p for p in listed["result"]["plugins"] if p.get("plugin_id") != sys.argv[2]]
json.dump(listed, open(sys.argv[1], "w"))'"""


def catalog_text(key, *args):
    """A text of the catalog (src/lang/en.txt), as the scripts show it — a key it does not have fails the test, so an
    assertion never quietly matches an empty text."""
    import i18n
    text = i18n.t(key, *args)
    if not text:
        raise KeyError(f"{key} is not in the catalog")
    return text


def publishable_files():
    """What would be published: git's tracked and untracked-but-not-ignored files (without git: a walk that skips
    .git, __pycache__ and .DS_Store)."""
    try:
        done = subprocess.run(["git", "-C", PACKAGE, "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                              capture_output=True)
    except OSError:                                                 # no git on this machine
        done = None
    if done and done.returncode == 0:
        # a file deleted from the working tree is not published by the next commit (history: the pre-publish check)
        return sorted({p for p in done.stdout.decode("utf-8").split("\0")
                       if p and os.path.isfile(os.path.join(PACKAGE, p))})
    found = []
    for root, dirs, files in os.walk(PACKAGE):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        found += [os.path.relpath(os.path.join(root, f), PACKAGE) for f in files if f != ".DS_Store"]
    return sorted(found)


def copy_package(dest):
    """A copy of the package to run (and change) in a test, without git, the tests and Python's caches."""
    shutil.copytree(PACKAGE, dest, ignore=shutil.ignore_patterns(".git", "tests", "__pycache__"))
    return dest


def png_alpha(path):
    """An 8-bit RGBA PNG's alpha channel: one bytes object per row, from the top."""
    return [bytes(row[3::4]) for row in png_rgba(path)]


def png_rgba(path):
    """An 8-bit RGBA PNG's pixels: one bytes object per row, from the top, four bytes (R, G, B, A) a pixel."""
    with open(path, "rb") as f:
        data = f.read()
    at, packed = len(PNG_SIGNATURE), b""
    while at < len(data):
        length, kind = struct.unpack(">I4s", data[at:at + 8])
        body = data[at + 8:at + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
            assert (depth, color, interlace) == (8, 6, 0), "not an 8-bit RGBA PNG without interlacing"
        elif kind == b"IDAT":
            packed += body
        at += 12 + length
    raw, stride, rows, above = zlib.decompress(packed), width * 4, [], bytearray(width * 4)
    for y in range(height):
        start = y * (stride + 1)
        kind, line = raw[start], bytearray(raw[start + 1:start + 1 + stride])
        for i in range(stride):                     # the PNG filters: none, sub, up, average, Paeth
            left, up = (line[i - 4] if i >= 4 else 0), above[i]
            corner = above[i - 4] if i >= 4 else 0
            if kind == 1:
                line[i] = (line[i] + left) & 255
            elif kind == 2:
                line[i] = (line[i] + up) & 255
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 255
            elif kind == 4:
                guess = left + up - corner
                near = min((abs(guess - left), 0, left), (abs(guess - up), 1, up), (abs(guess - corner), 2, corner))
                line[i] = (line[i] + near[2]) & 255
        rows.append(bytes(line))
        above = line
    return rows


def stubs(folder, programs):
    """Executable fakes in FOLDER: {name: script, or None for one that only fails}; returns FOLDER."""
    os.makedirs(folder, exist_ok=True)
    for name, body in programs.items():
        path = os.path.join(folder, name)
        with open(path, "w") as f:
            f.write(body or "#!/bin/sh\nexit 1\n")
        os.chmod(path, 0o755)
    return folder


def from_homebrew(folder, name="herdr", version="0.9.6"):
    """FOLDER's fake NAME moved where Homebrew keeps a program (FOLDER/../Cellar/NAME/VERSION/bin) and linked back onto
    PATH from there, as Homebrew links it: the installer takes it for Homebrew's."""
    kept = os.path.join(os.path.dirname(folder), "Cellar", name, version, "bin")
    os.makedirs(kept, exist_ok=True)
    os.replace(os.path.join(folder, name), os.path.join(kept, name))
    os.symlink(os.path.join(kept, name), os.path.join(folder, name))


def trap(repo, key, folder):
    """Sets KEY in REPO's own git config to a program in FOLDER that leaves a mark, as a downloaded folder's .git/config
    could; returns the mark's path, which exists only if git ran the program."""
    mark = os.path.join(folder, key + ".ran")
    stubs(folder, {key: f"#!/bin/sh\ntouch '{mark}'\n"})
    subprocess.run(["git", "-C", repo, "config", key, os.path.join(folder, key)], check=True)
    return mark


def sign_head(repo):
    """Makes REPO's HEAD a commit with a (made-up) signature, as a downloaded repository can hold one: git log and git
    show then hand it to the signature program (gpg.program) when log.showSignature is on."""
    def git(*args, stdin=None):
        return subprocess.run(["git", "-C", repo, *args], input=stdin, capture_output=True, text=True,
                              check=True).stdout.strip()
    tree, parent = git("rev-parse", "HEAD^{tree}"), git("rev-parse", "HEAD")
    body = (f"tree {tree}\nparent {parent}\nauthor dev <dev@example.com> 1700000000 +0000\n"
            "committer dev <dev@example.com> 1700000000 +0000\n"
            "gpgsig -----BEGIN PGP SIGNATURE-----\n \n iQ\n -----END PGP SIGNATURE-----\n\nsigned\n")
    git("update-ref", "HEAD", git("hash-object", "-t", "commit", "-w", "--stdin", stdin=body))


class FakeTerminal:
    """The app's terminal here: what the test types, a fixed size, and wake()."""

    def __init__(self, cols=45, rows=30):
        self.cols, self.rows, self.queue = cols, rows, queue.Queue()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def size(self):
        return self.cols, self.rows

    def write(self, data):
        pass

    def flush(self):
        pass

    def wake(self):
        self.queue.put(None)

    def type(self, *events):
        for event in events:
            self.queue.put(event)

    def read(self, timeout):
        items = []
        try:
            items.append(self.queue.get(timeout=max(0.0, timeout)))
            while True:
                items.append(self.queue.get_nowait())
        except queue.Empty:
            pass
        return [item for item in items if item is not None]


def set_env(test, **values):
    """Environment variables for this test only (None: unset); the earlier values come back after it."""
    for name, value in values.items():
        test.addCleanup(lambda name=name, old=os.environ.get(name):
                        os.environ.pop(name, None) if old is None else os.environ.__setitem__(name, old))
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def set_attrs(test, obj, **values):
    """Attributes of OBJ (e.g. a module's herdr call or a config path) for this test only; the earlier
    ones come back."""
    for name, value in values.items():
        test.addCleanup(setattr, obj, name, getattr(obj, name))
        setattr(obj, name, value)


def finished(test, fn, seconds=5):
    """FN's result, an error of FN's raised here; the test fails when FN still runs after SECONDS (a pipe opened to
    read waits for a writer for good)."""
    result = {}

    def work():
        try:
            result["value"] = fn()
        except BaseException as err:
            result["error"] = err
    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(seconds)
    test.assertFalse(worker.is_alive(), f"still running after {seconds} s")
    if "error" in result:
        raise result["error"]
    return result.get("value")


def waits_for_an_answer(shown):
    """Whether a script waits for an answer, by what it showed last: a question left on its line with the cursor after
    it ([Y/n] or [y/N] in the language's letters, a prompt's ": ", the opening "press Enter to start, any other key to
    cancel.", the closing "press any key."), or a checkbox list (its key line ends with "Enter done")."""
    if shown.endswith("\n"):
        return shown.rstrip("\n").rsplit("\n", 1)[-1].rstrip().endswith("Enter done")
    line = shown.rsplit("\n", 1)[-1]
    return line.endswith(" ") and bool(QUESTION_END.search(line.rstrip()))


def run_in_terminal(argv, env, answer, timeout=120, idle=0.5, keep_colors=False):
    """Run ARGV in a pty; when it waits for an answer (waits_for_an_answer, then IDLE quiet seconds), type
    answer(last line) and Enter; None leaves it waiting. Returns (output, without colors unless KEEP_COLORS; whether
    it ended by itself); one still running after TIMEOUT is killed (only the child it started)."""
    pid, fd = pty.fork()
    if pid == 0:
        os.execve(argv[0], argv, env)
    shown, last, end = "", time.time(), time.time() + timeout
    while time.time() < end:
        if select.select([fd], [], [], 0.1)[0]:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            text = chunk.decode("utf-8", "replace").replace("\r", "")
            shown += text if keep_colors else ANSI.sub("", text)
            last = time.time()
        elif time.time() - last > idle:
            plain = ANSI.sub("", shown)                   # a question is told by its words, whatever its colors
            line = plain.rstrip("\n").rsplit("\n", 1)[-1]
            reply = answer(line) if waits_for_an_answer(plain) else None
            if reply is not None:
                os.write(fd, reply.encode() + b"\r")
                shown += "\n"                             # the answer ends that line
            last = time.time()
    ended = False
    for _ in range(30):
        if os.waitpid(pid, os.WNOHANG) != (0, 0):
            ended = True
            break
        time.sleep(0.1)
    if not ended:
        os.kill(pid, 9)
    os.close(fd)                    # first: a child killed with its output unread ends only once the pty is let go
    if not ended:
        os.waitpid(pid, 0)
    return shown, ended


class FakeHerdrSocket:
    """A stand-in for herdr's socket API at PATH serving TABS {tab_id: (layout tree, zoomed)}, each WIDTH cells wide;
    pane.current is in the first tab, and a split's first side is round(width x ratio) cells, as herdr gives it.
    Every call is recorded in .calls; close it with .server.close()."""

    def __init__(self, path, tabs, width=200):
        self.tabs, self.calls, self.width = {tab: list(value) for tab, value in tabs.items()}, [], width
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(path)
        self.server.listen()
        threading.Thread(target=self.serve, daemon=True).start()

    @staticmethod
    def panes(node):
        if node.get("type") == "pane":
            return [node]
        return FakeHerdrSocket.panes(node["first"]) + FakeHerdrSocket.panes(node["second"])

    @staticmethod
    def rects(node, x, w, out):
        if node.get("type") == "pane":
            out.append({"pane_id": node["pane_id"], "rect": {"x": x, "y": 0, "width": w, "height": 40}})
        elif node["direction"] == "right":
            first = int(w * node["ratio"] + 0.5)
            FakeHerdrSocket.rects(node["first"], x, first, out)
            FakeHerdrSocket.rects(node["second"], x + first, w - first, out)
        else:
            FakeHerdrSocket.rects(node["first"], x, w, out)
            FakeHerdrSocket.rects(node["second"], x, w, out)
        return out

    def tab_of(self, pane):
        return next(tab for tab, (root, _) in self.tabs.items() if any(p["pane_id"] == pane for p in self.panes(root)))

    def answer(self, method, params):
        if method == "pane.current":                                    # the first tab is on screen
            return {"pane": {"tab_id": next(iter(self.tabs))}}
        if method == "pane.list":
            return {"panes": [{"pane_id": p["pane_id"], "label": p.get("label"), "tab_id": tab}
                              for tab, (root, _) in self.tabs.items() for p in self.panes(root)]}
        tab = params.get("tab_id") or self.tab_of(params["pane_id"])
        root, zoomed = self.tabs[tab]
        if method == "layout.export":
            return {"layout": {"tab_id": tab, "zoomed": zoomed, "root": root}}
        if method == "pane.layout":
            return {"layout": {"panes": self.rects(root, 0, self.width, [])}}
        node = root
        for second in params["path"]:
            node = node["second" if second else "first"]
        node["ratio"] = params["ratio"]
        return {"type": "layout_split_ratio_set"}

    def serve(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            with conn:
                data = b""
                while not data.endswith(b"\n"):
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                request = json.loads(data)
                self.calls.append((request["method"], request["params"]))
                reply = {"id": request["id"], "result": self.answer(request["method"], request["params"])}
                conn.sendall((json.dumps(reply) + "\n").encode())
