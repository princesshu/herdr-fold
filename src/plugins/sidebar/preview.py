"""The sidebar's preview: one tab per workspace, laid out as the tab it was opened from, showing a file, a diff, a
commit or an issue in the pager. The spec goes to a file the pager reads, never through a shell; the line typed into a
tab's shell stays in its history, so it names no path (a home folder names its account): paths go in Launch's env."""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field

import media
import statefile

PAGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pager.py")
LABEL = "preview: "
PANE = "preview"              # the preview tab's pane the pager runs in
READY = 1.5                   # seconds a new tab's sidebar may take to start before the tab is shown all the same


class Herdr:
    """herdr's command line: the result part of its JSON answer; an error raises RuntimeError."""

    def __init__(self, binary=None):
        self.binary = binary or os.environ.get("HERDR_BIN_PATH") or shutil.which("herdr") or "herdr"

    def call(self, *args):
        try:
            out = subprocess.run([self.binary, *args], capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as err:
            raise RuntimeError(str(err)) from err
        if out.returncode != 0:
            raise RuntimeError(((out.stderr or out.stdout).strip().splitlines() or ["herdr failed"])[-1])
        try:
            data = json.loads(out.stdout) if out.stdout.strip() else {}
        except ValueError:
            return {}
        return data.get("result", {}) if isinstance(data, dict) else {}


def file_spec(root, path, line, which=shutil.which):
    """An image or a PDF as a picture; else bat with LINE marked (one row per line, so the pager's line N is the
    file's), or the file itself: a pipe or a device too, which bat would wait on and the pager does not read."""
    if media.kind_of(path) in ("image", "pdf"):          # a pager from before pictures shows the file: binary
        return {"title": os.path.relpath(path, root), "line": None, "file": path, "pipeline": [], "picture": path}
    bat = which("bat") if not (os.path.exists(path) and not os.path.isfile(path)) else None
    marked = ["--highlight-line", str(line)] if line else []
    pipeline = [[bat, "--color=always", "--paging=never", "--wrap=never", "--style=numbers,changes", *marked, path]]
    pipeline = pipeline if bat else []
    spec = {"title": os.path.relpath(path, root), "line": line, "file": None if bat else path, "pipeline": pipeline}
    return {**spec, "open": path} if media.kind_of(path) == "html" else spec


def git_argv(git, root, command):
    """git COMMAND without a program the repository's own config names (a downloaded folder's .git/config is not the
    user's): no fsmonitor, no signature check, no external diff, no text conversion; a path is read as a name, not a
    pattern."""
    return [git, "--literal-pathspecs", "-c", "core.fsmonitor=false", "-c", "log.showSignature=false", "-C", root,
            command, "--no-ext-diff", "--no-textconv"]


# delta as the preview shows it: the lines numbered, a hunk headed by its function alone (delta's own header is a box
# open on the left, its line number flush against the edge)
DELTA = ["--paging=never", "--line-numbers", "--hunk-header-decoration-style=none", "--hunk-header-style=syntax"]


def diff_spec(root, path, staged, which=shutil.which):
    """The diff of PATH (pages/[id].tsx is that one file)."""
    git, delta = which("git") or "git", which("delta")
    diff = git_argv(git, root, "diff") + (["--cached"] if staged else [])
    pipeline = [diff + ["--", path], [delta, *DELTA]] if delta else [diff + ["--color=always", "--", path]]
    return {"title": path, "line": None, "file": None, "pipeline": pipeline}


def commit_spec(root, commit, which=shutil.which):
    git, delta = which("git") or "git", which("delta")
    show = git_argv(git, root, "show")
    pipeline = [show + [commit], [delta, *DELTA]] if delta else [show + ["--color=always", commit]]
    return {"title": commit, "line": None, "file": None, "pipeline": pipeline}


def spec_file(state_dir, workspace):
    """Where WORKSPACE's preview tab takes what to show from, in the plugin's state folder."""
    return os.path.join(state_dir, "preview-" + re.sub(r"[^A-Za-z0-9]", "-", workspace) + ".json")


def quote_powershell(text):
    """TEXT as one PowerShell string: it ends a quoted string at a curly quote too, so those are doubled as well."""
    for mark in "'\u2018\u2019\u201a\u201b":
        text = text.replace(mark, mark * 2)
    return "'" + text + "'"


@dataclass(frozen=True)
class Launch:
    """What a tab runs: the LINE typed into its shell, and the ENV herdr starts that shell with."""
    line: str
    env: dict = field(default_factory=dict)


def interactive(argv, windows=os.name == "nt"):
    """What runs ARGV with the keyboard, the program's path in the environment: when it ends well, so does the shell,
    and the tab closes; after an error it stays open."""
    env = {"HERDR_FOLD_PROGRAM": argv[0]}
    if windows:
        line = "& $env:HERDR_FOLD_PROGRAM " + " ".join(quote_powershell(arg) for arg in argv[1:]) + "; if ($?) { exit }"
        return Launch(line, env)
    return Launch('"$HERDR_FOLD_PROGRAM" ' + shlex.join(argv[1:]) + " && exit", env)


def command(path, windows=os.name == "nt"):
    """What pages the spec written to PATH, and each one written there after it: this Python (-B: no caches next to the
    plugin) and the pager, both paths and PATH in the environment. When the pager ends (closing its tab), so does the
    shell; after an error it stays open."""
    env = {"HERDR_FOLD_PYTHON": sys.executable, "HERDR_FOLD_PAGER": PAGER, "HERDR_FOLD_SPEC_FILE": path}
    if windows:
        return Launch("& $env:HERDR_FOLD_PYTHON -B $env:HERDR_FOLD_PAGER; if ($?) { exit }", env)
    return Launch('"$HERDR_FOLD_PYTHON" -B "$HERDR_FOLD_PAGER" && exit', env)


def seed_file(state_dir, tab, kind="sidebar"):
    """Where a new preview TAB's pane of KIND finds what it starts with (the sidebar: where the one that opened it was),
    taken just before it first draws: the tab is shown once every one is (seeded())."""
    name = "".join(ch if ch.isalnum() else "-" for ch in tab)
    return os.path.join(state_dir, f"seed-{name}.json" if kind == "sidebar" else f"seed-{name}-{kind}.json")


def seeded(state_dir, tab):
    """Whether TAB's panes have all taken their seeds."""
    name = os.path.basename(seed_file(state_dir, tab))[:-len(".json")]
    try:
        return not any(found == f"{name}.json" or found.startswith(f"{name}-") for found in os.listdir(state_dir))
    except OSError:
        return True


def this_tab(herdr):
    """The tab of the pane this runs in (None outside herdr): a call to herdr."""
    pane = os.environ.get("HERDR_PANE_ID")
    try:
        return herdr.call("pane", "get", pane)["pane"]["tab_id"] if pane else None
    except (RuntimeError, KeyError, TypeError):
        return None


def open_preview(herdr, workspace, root, spec, state_dir, lay_out=None, here=None):
    """SPEC in WORKSPACE's preview tab, else in a new tab in ROOT laid out by LAY_OUT(tab) before the pager starts.
    A preview tab whose pager no longer runs, or whose spec file is gone, is closed after, HERE (the asking pane's tab)
    last: closing it ends the sidebar that asks."""
    path = spec_file(state_dir, workspace)
    watched = os.path.exists(path)
    statefile.write(path, spec)
    name, stale = label(LABEL + spec["title"]), []
    panes = [p for p in herdr.call("pane", "list", "--workspace", workspace).get("panes") or [] if isinstance(p, dict)]
    for tab in herdr.call("tab", "list", "--workspace", workspace).get("tabs") or []:
        if not (isinstance(tab, dict) and tab.get("tab_id") and str(tab.get("label", "")).startswith(LABEL)):
            continue
        pane = next((p.get("pane_id") for p in panes if p.get("tab_id") == tab["tab_id"] and p.get("label") == PANE),
                    None)
        if pane and watched and paging(herdr, pane):
            herdr.call("tab", "rename", tab["tab_id"], name)
            herdr.call("tab", "focus", tab["tab_id"])
            return
        stale.append(tab["tab_id"])
    made = []

    def laid(tab):
        made.append(tab)
        if lay_out:
            lay_out(tab)

    try:
        open_tab(herdr, workspace, root, name, command(path), PANE, laid,
                 lambda: not made or seeded(state_dir, made[0]))
    finally:
        for tab in sorted(stale, key=lambda tab: tab == here) if made else ():   # only once a new one is there
            herdr.call("tab", "close", tab)


def paging(herdr, pane):
    """Whether the pager runs in PANE (once herdr starts again, a shell is left there)."""
    try:
        running = herdr.call("pane", "process-info", "--pane", pane)["process_info"]["foreground_processes"]
        names = [str(p.get("name", "")) for p in running if isinstance(p, dict)]
    except (RuntimeError, KeyError, TypeError, AttributeError):
        return False
    return any(name.replace("\\", "/").split("/")[-1].lower().startswith("python") for name in names)


def label(text):
    """TEXT as a herdr tab or pane name: printable characters only (a file name or a conversation's title may hold
    escape codes), and no leading dash, which herdr's command line would take for an option."""
    return "".join(ch for ch in text if ch.isprintable()).lstrip("- ")


def open_tab(herdr, workspace, root, name, launch, pane_name="issue", lay_out=None, ready=lambda: True):
    """A new tab in ROOT labeled NAME, LAUNCH running in it once LAY_OUT(tab) has laid it out, shown once READY() says
    what started there draws; other tabs stay. Its pane is named first: a layout plugin (herdr-fold's tab-layout)
    leaves a new tab alone once its pane has a name."""
    env = [arg for key, value in launch.env.items() for arg in ("--env", f"{key}={value}")]
    created = herdr.call("tab", "create", "--workspace", workspace, "--cwd", root, "--label", label(name), *env,
                         "--no-focus")
    pane, tab = created["root_pane"]["pane_id"], created["tab"]["tab_id"]
    herdr.call("pane", "rename", pane, pane_name)
    try:
        if lay_out:
            lay_out(tab)
    finally:
        herdr.call("pane", "run", pane, launch.line)
        end = time.monotonic() + READY                 # no half-drawn tab, no column starting empty, on screen
        while not ready() and time.monotonic() < end:
            time.sleep(0.05)
        herdr.call("tab", "focus", tab)
