"""The sidebar's preview: one tab per workspace, a picture, a page, a diff, a commit or an issue in the pager; a text
file in the user's editor in a tab of its own. The spec goes to a file the pager reads; the line typed into a tab's
shell stays in its history, so it names no path (a home folder names its account): paths go in Launch's env."""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field

import column
import filekinds
import media
import statefile

PAGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pager.py")
LABEL = "preview: "
PANE = "preview"              # the preview tab's pane the pager runs in
EDIT = "edit"                 # an editor tab's pane, the user's editor in it
EDITORS = ("micro", "nano", "vim")    # looked for in this order where $VISUAL and $EDITOR name none
AT_LINE = ("micro", "nano", "vim", "vi", "nvim")    # the editors that open at a line given as +N
# on a Mac, where the tab's Cmd keys reach the editor (cmd_keys.py), what it adds to the editor's words: micro's status
# line the file, its line and column and those keys; nano's help lines, which name other keys, hidden (pico's too)
OPTIONS = {"micro": ["-basename", "true", "-statusformatl", " $(filename) $(modified)Ln $(line), Col $(col)",
                     "-statusformatr", "  Cmd+S Save  Cmd+F Find  Cmd+Z Undo  Cmd+W Close "], "nano": ["-x"]}
# Esc in micro, as a preview's: a selection off, else the tab closed (micro asks first where a change is unsaved)
MICRO_ESC = "Deselect|Quit"
READY = 1.5                   # seconds a new tab's sidebar may take to start before the tab is shown all the same
QUICK = 2                     # seconds within which an editor that ends opened its own window


class Herdr:
    """herdr's command line: the result part of its JSON answer; an error raises RuntimeError with its message."""

    def __init__(self, binary=None):
        self.binary = binary or os.environ.get("HERDR_BIN_PATH") or shutil.which("herdr") or "herdr"

    def call(self, *args):
        try:
            out = subprocess.run([self.binary, *args], capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as err:
            raise RuntimeError(str(err)) from err
        if out.returncode != 0:
            line = ((out.stderr or out.stdout).strip().splitlines() or ["herdr failed"])[-1]
            raise RuntimeError(column.refusal(line) or line)        # its error's own message, never its JSON
        try:
            data = json.loads(out.stdout) if out.stdout.strip() else {}
        except ValueError:
            return {}
        return data.get("result", {}) if isinstance(data, dict) else {}

    def text(self, *args):
        """What a command prints as text (a pane's rows): "" where it fails."""
        try:
            out = subprocess.run([self.binary, *args], capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return out.stdout if out.returncode == 0 else ""


def editor(line=None, env=os.environ, which=shutil.which, mac=sys.platform == "darwin"):
    """The user's editor's argv, at LINE where it takes +N: $VISUAL, else $EDITOR (its words split as a shell would:
    code -w), else the first of micro, nano and vim found (micro with micro_config()'s folder), on a MAC with its
    OPTIONS before +N; None without one."""
    named = env.get("VISUAL") or env.get("EDITOR")
    try:
        argv = shlex.split(named, posix=os.name != "nt") if named else []
    except ValueError:
        argv = []
    found = next((which(name) for name in EDITORS if which(name)), None)
    argv = argv or ([found] if found else [])
    program = os.path.basename(argv[0] if argv else "").lower()
    at = [f"+{line}"] if line and program in AT_LINE else []
    folder = micro_config(env) if program == "micro" else None
    return argv + (["-config-dir", folder] if folder else []) + (OPTIONS.get(program, []) if mac else []) + at \
        if argv else None


def micro_config(env=os.environ):
    """A config folder for micro that is the user's own, each of its entries linked in, but for its bindings: theirs
    with Esc as MICRO_ESC; None (micro as it is) where they bound Esc, their bindings cannot be read or ENV has no
    HOME."""
    home = env.get("HOME")
    if not home:
        return None
    own = env.get("MICRO_CONFIG_HOME") or os.path.join(env.get("XDG_CONFIG_HOME") or os.path.join(home, ".config"),
                                                      "micro")
    try:
        with open(os.path.join(own, "bindings.json"), encoding="utf-8") as f:
            bindings = json.load(f)
    except FileNotFoundError:
        bindings = {}
    except (OSError, ValueError):
        return None
    if not isinstance(bindings, dict) or "Esc" in bindings:
        return None
    folder = os.path.join(env.get("XDG_STATE_HOME") or os.path.join(home, ".local", "state"), "herdr-fold", "micro")
    try:
        for name in ("buffers", "backups"):            # its history and backups in their own folder, not this one
            os.makedirs(os.path.join(own, name), exist_ok=True)
        os.makedirs(folder, exist_ok=True)
        for name in os.listdir(folder):                 # the last editor's links, made again as their folder is now
            if os.path.islink(os.path.join(folder, name)) or name == "bindings.json":
                os.remove(os.path.join(folder, name))
        for name in os.listdir(own):
            if name != "bindings.json":
                os.symlink(os.path.join(own, name), os.path.join(folder, name))
        statefile.write(os.path.join(folder, "bindings.json"), {**bindings, "Esc": MICRO_ESC})
    except OSError:
        return None
    return folder


def writable(path, root):
    """Whether PATH under ROOT may be written in an editor, as the app's editor decides it (media.text()): text, and
    not a link that leads out of ROOT (a repository's notes.txt that is your ~/.zshrc stays in the preview)."""
    return media.text(root, path)["why"] is None


def editable(path, root):
    """Whether PATH opens in the user's editor: writable() under ROOT, nothing drawn here (a page or an SVG drawn stays
    in the preview, where e edits it)."""
    kind = filekinds.kind_of(path)
    if kind in ("image", "pdf", "audio", "video") or kind in ("svg", "html") and media.drawable(path):
        return False
    return writable(path, root)


def file_spec(root, path, line, which=shutil.which):
    """An image, a PDF, audio or a video as a picture; else bat with LINE marked (one row per line, so the pager's
    line N is the file's), or the file itself: a pipe or a device too, which bat would wait on and the pager does not
    read."""
    if filekinds.kind_of(path) in ("image", "pdf", "audio", "video"):
        return {"title": os.path.relpath(path, root), "line": None, "file": None, "pipeline": [], "picture": path}
    bat = which("bat") if not (os.path.exists(path) and not os.path.isfile(path)) else None
    marked = ["--highlight-line", str(line)] if line else []
    pipeline = [[bat, "--color=always", "--paging=never", "--wrap=never", "--style=numbers,changes", *marked, path]]
    pipeline = pipeline if bat else []
    spec = {"title": os.path.relpath(path, root), "line": line, "file": None if bat else path, "pipeline": pipeline}
    if filekinds.kind_of(path) in ("svg", "html") and media.drawable(path):     # code and a picture beside it; e edits
        spec.update(picture=path, **({"edit": path} if writable(path, root) else {}))
    return {**spec, "open": path} if filekinds.kind_of(path) in ("html", "svg") and media.browsable() else spec


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
    """The diff of PATH (pages/[id].tsx is that one file); a picture's before and after (pager.PictureChange)."""
    if filekinds.kind_of(path) == "image":
        return {"title": path, "change": {"root": root, "path": path, "staged": staged}}
    git, delta = which("git") or "git", which("delta")
    diff = git_argv(git, root, "diff") + (["--cached"] if staged else [])
    pipeline = [diff + ["--", path], [delta, *DELTA]] if delta else [diff + ["--color=always", "--", path]]
    return {"title": path, "line": None, "file": None, "pipeline": pipeline}


def commit_spec(root, commit, which=shutil.which):
    git, delta = which("git") or "git", which("delta")
    show = git_argv(git, root, "show")
    pipeline = [show + [commit], [delta, *DELTA]] if delta else [show + ["--color=always", commit]]
    return {"title": commit, "line": None, "file": None, "pipeline": pipeline}


# a tree row's role as its colors: the terminal's own, so they follow its theme (pager.py lets colors alone through);
# a network's brand letter its own #rrggbb (core/icons.py's), as the Machines view draws it
ROLES = {"bold": "1", "dim": "90", "ok": "32", "bad": "31", "warn": "33", "accent": "1;35", "bold_dim": "1;90"}
GRAPH_VIEWS = (("w", "wiring", False), ("c", "run", True))    # a graph's views: its key, core's name, tree()'s RUN
MACHINES = "machines"         # the machines' tree's title, the preview tab's name after "preview: "


def colored(role):
    """ROLE's SGR numbers: ROLES', else a brand's #rrggbb as a 24-bit color."""
    if role in ROLES:
        return ROLES[role]
    return "38;2;" + ";".join(str(int(role[at:at + 2], 16)) for at in (1, 3, 5))


def painted(rows):
    """A tree's ROWS (layers.py's tree_rows()) as the pager's lines, each part in its role's colors."""
    return ["".join(f"\x1b[{colored(role)}m{words}\x1b[0m" if role else words for words, role in row).rstrip()
            for row in rows]


def graph_spec(graph, rows, view="w"):
    """Core's GRAPH as a tree in the preview tab, titled graph: Claude in lumen-api: its views (Wiring, and This chat
    where one was read) each its key, core's word and its lines, ROWS(run) giving a view's rows; the pager's w and c
    switch them. A pager from before the views reads the file it names, which is none."""
    views = [{"key": key, "name": graph["words"]["views"][name], "lines": painted(rows(run))}
             for key, name, run in GRAPH_VIEWS if not run or graph["run"]]
    return {"title": f"graph: {graph['name']} in {os.path.basename(graph['folder'].rstrip(os.sep))}", "line": None,
            "file": os.devnull, "pipeline": [], "views": views, "view": view if view in [v["key"] for v in views]
            else "w"}


def machines_spec(rows):
    """How the machines connect as a tree in the preview tab (ROWS: layers.py's tree_rows() of core's machines' graph),
    titled machines: one view, so no control to switch; the pager's own keys."""
    return {"title": MACHINES, "line": None, "file": os.devnull, "pipeline": [],
            "views": [{"key": None, "name": "Machines", "lines": painted(rows)}], "view": None}


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


def interactive(argv, file=None, windows=os.name == "nt"):
    """What runs ARGV with the keyboard (FILE after its words), the program's and the file's paths in the environment:
    when it ends well, so does the shell, and the tab closes; after an error it stays open."""
    env = {"HERDR_FOLD_PROGRAM": argv[0], **({"HERDR_FOLD_FILE": file} if file else {})}
    if windows:
        words = [quote_powershell(arg) for arg in argv[1:]] + (["$env:HERDR_FOLD_FILE"] if file else [])
        return Launch(" ".join(["& $env:HERDR_FOLD_PROGRAM", *words]) + "; if ($?) { exit }", env)
    words = ([shlex.join(argv[1:])] if argv[1:] else []) + (['"$HERDR_FOLD_FILE"'] if file else [])
    return Launch(" ".join(['"$HERDR_FOLD_PROGRAM"', *words]) + " && exit", env)


def command(path, windows=os.name == "nt"):
    """What pages the spec written to PATH, and each one written there after it: this Python (-B: no caches next to the
    plugin) and the pager, both paths and PATH in the environment. When the pager ends (closing its tab), so does the
    shell; after an error it stays open."""
    env = {"HERDR_FOLD_PYTHON": sys.executable, "HERDR_FOLD_PAGER": PAGER, "HERDR_FOLD_SPEC_FILE": path}
    if windows:
        return Launch("& $env:HERDR_FOLD_PYTHON -B $env:HERDR_FOLD_PAGER; if ($?) { exit }", env)
    return Launch('"$HERDR_FOLD_PYTHON" -B "$HERDR_FOLD_PAGER" && exit', env)


def seed_file(state_dir, tab):
    """Where a new TAB's sidebar finds what it starts with (in a preview tab, where the one that opened it was), taken
    just before it first draws: a preview tab is shown once it is (seeded())."""
    name = "".join(ch if ch.isalnum() else "-" for ch in tab)
    return os.path.join(state_dir, f"seed-{name}.json")


def seeded(state_dir, tab):
    """Whether TAB's sidebar has taken its seed."""
    return not os.path.exists(seed_file(state_dir, tab))


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


def close_preview(herdr, workspace):
    """WORKSPACE's preview tab closed (Files' Close Preview): its pager, hung up, forgets what it showed."""
    for tab in herdr.call("tab", "list", "--workspace", workspace).get("tabs") or []:
        if isinstance(tab, dict) and tab.get("tab_id") and str(tab.get("label", "")).startswith(LABEL):
            herdr.call("tab", "close", tab["tab_id"])


def paging(herdr, pane):
    """Whether the pager runs in PANE (once herdr starts again, a shell is left there)."""
    try:
        running = herdr.call("pane", "process-info", "--pane", pane)["process_info"]["foreground_processes"]
        names = [str(p.get("name", "")) for p in running if isinstance(p, dict)]
    except (RuntimeError, KeyError, TypeError, AttributeError):
        return False
    return any(name.replace("\\", "/").split("/")[-1].lower().startswith("python") for name in names)


def open_editor(herdr, workspace, root, path, argv, name=None):
    """PATH in the user's editor (ARGV, editor()'s) in a tab of its own, named NAME (else its path from ROOT, or from
    home), or the tab already editing it shown: no second editor on one file (vim's swap file). Its (pane, tab)."""
    home = os.path.expanduser("~")
    inside = path.startswith(root.rstrip(os.sep) + os.sep)
    name = label(name or (os.path.relpath(path, root) if inside else path.replace(home, "~", 1)))
    panes = [p for p in herdr.call("pane", "list", "--workspace", workspace).get("panes") or [] if isinstance(p, dict)]
    for tab in herdr.call("tab", "list", "--workspace", workspace).get("tabs") or []:
        pane = next((p.get("pane_id") for p in panes if isinstance(tab, dict) and tab.get("label") == name
                     and p.get("tab_id") == tab.get("tab_id") and p.get("label") == EDIT), None)
        if pane:
            herdr.call("tab", "focus", tab["tab_id"])
            return pane, tab["tab_id"]
    return open_tab(herdr, workspace, root, name, interactive(argv, path), EDIT)


def gone_at_once(herdr, pane, wait=QUICK):
    """Whether PANE's editor ended within WAIT seconds: a desktop editor told no -w opens its own window and returns."""
    end = time.monotonic() + wait
    while time.monotonic() < end:
        time.sleep(0.25)
        try:
            if pane not in {p.get("pane_id") for p in herdr.call("pane", "list").get("panes") or []
                            if isinstance(p, dict)}:
                return True
        except RuntimeError:
            return False
    return False


def label(text):
    """TEXT as a herdr tab or pane name: printable characters only (a file name or a chat's title may hold
    escape codes), and no leading dash, which herdr's command line would take for an option."""
    return "".join(ch for ch in text if ch.isprintable()).lstrip("- ")


def open_tab(herdr, workspace, root, name, launch, pane_name="issue", lay_out=None, ready=lambda: True):
    """A new tab in ROOT labeled NAME, LAUNCH running in it once LAY_OUT(tab) has laid it out, shown once READY() says
    what started there draws; other tabs stay. Its pane is named first: the dock (panes.py --new-tab) leaves a new
    tab alone once its pane has a name. Its (pane, tab)."""
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
    return pane, tab
