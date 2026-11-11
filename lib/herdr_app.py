"""herdr-fold in the Herdr app: the mod, its layout, themes and keys into the app's home and off again, the tabs'
terminals it started ended. Usage: herdr_app.py cli | core | home | install PACKAGE [THEME] (0; 3: keys.json unreadable,
left as it is; 4: a mods/herdr-fold not herdr-fold's) | uninstall PACKAGE | end-terminals | close | open"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the package's scripts
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from parts import app_home  # noqa: E402
from themes import apply  # noqa: E402

MOD, LAYOUT, KEYS = os.path.join("mods", "herdr-fold"), os.path.join("layouts", "herdr-fold.json"), "keys.json"
LAYOUT_STATE = os.path.join("layouts", ".state", "herdr-fold.json")   # the app's state of the layout (its panels)
PICTURES = "herdr-fold-pictures"             # the preview tab's pictures (core/media.py makes them there)
DATA = os.path.join("data", "herdr-fold")    # the app's data of the mod (its views' state, store.json)
# in HOME: the app's localStorage of each mod copy, made when it loads one (herdr-fold's stays empty), named
# NAME-HASH by the copy's folder and the FNV-1a hash of its real path
STORAGE = os.path.join("Library", "Application Support", "gpui-shell", "apps")
THEMES = "themes"              # herdr-fold.json (the layout's own) and the TUI's themes, herdr-fold-ID.json
TITLE = "herdr-fold"            # the mod.json title that marks a mods/herdr-fold folder as herdr-fold's copy
TERMINALS = "fold-terminals"    # the layout's stack of the tabs' terminals the mod started (app/mods/herdr-fold)
SHARED = "shared.json"          # the app's shared values, the mod's named herdr-fold.*; a running app holds them all
PREFIX = "herdr-fold."
RECORD = "app-keys.json"        # in the installer's state folder: what the last install put in keys.json
THEMES_RECORD = "app-themes.json"    # and the themes it put in the app's themes/
CLOSING = 10                    # seconds a running app may take to close
ANSWER = 30                     # seconds the app's command line may take to answer


def cli():
    """The app's command line (herdr-app on PATH, else where the app puts it), or None without the app."""
    local = os.path.expanduser("~/.local/bin/herdr-app")
    return shutil.which("herdr-app") or (local if os.access(local, os.X_OK) else None)


def core():
    """The app's core, hc (herdr-core): on PATH, else beside the app's command line, or None."""
    app = cli()
    beside = os.path.join(os.path.dirname(app), "herdr-core") if app else ""
    return shutil.which("herdr-core") or shutil.which("hc") or (beside if os.access(beside, os.X_OK) else None)


def nodes(node):
    yield node
    for child in node.get("children") or []:
        yield from nodes(child)


def tab_terminals(home):
    """The terminals the mod started for tabs, as the layout in HOME names them: this computer's and other machines'
    (`lab/t7`)."""
    try:
        with open(os.path.join(home, LAYOUT), encoding="utf-8") as f:
            layout = json.load(f)
    except (OSError, ValueError):
        return []
    stacks = [n for n in nodes(layout) if isinstance(n, dict) and n.get("id") == TERMINALS]
    return [address for stack in stacks for child in stack.get("children") or []
            if isinstance(address := (child.get("content") or {}).get("terminal"), str)]


def end_terminals(hc, home):
    for address in tab_terminals(home):
        subprocess.run([hc, "kill", "--", address], capture_output=True, timeout=30, stdin=subprocess.DEVNULL)


def state_dir():
    return os.path.join(os.path.expanduser("~"), ".local", "state", "herdr-fold")


def answer(app, *args):
    """The app's command line's exit code for ARGS, or None when it did not answer in time."""
    try:
        return subprocess.run([app, *args], capture_output=True, timeout=ANSWER, stdin=subprocess.DEVNULL).returncode
    except subprocess.TimeoutExpired:
        return None


def running(app):
    """Whether the app runs; one that does not answer is taken for running, as it may still write its values back."""
    return answer(app, "status") in (0, None)


def close(app):
    """A running app closed, its terminals running on in its core: whether it ran and is closed now."""
    if not running(app):
        return False
    answer(app, "do", "app.quit")
    for _ in range(CLOSING * 2):
        if not running(app):
            return True
        time.sleep(0.5)
    return False


def bundle(app):
    """The Herdr.app the command line links into (Herdr.app/Contents/MacOS/Herdr), or None."""
    path = os.path.realpath(app)
    top = os.path.dirname(os.path.dirname(os.path.dirname(path)))
    return top if top.endswith(".app") and os.path.basename(os.path.dirname(path)) == "MacOS" else None


def storage(mod):
    """The app's localStorage folder of the mod copy at MOD."""
    hashed = 0xcbf29ce484222325
    for byte in os.path.realpath(mod).encode():
        hashed = (hashed ^ byte) * 0x100000001b3 % 2 ** 64
    return os.path.join(os.path.expanduser("~"), STORAGE, f"{os.path.basename(mod)}-{hashed:016x}")


def herdr_folds(folder):
    """Whether FOLDER is herdr-fold's mod (its mod.json says so), not a link or someone's own by that name."""
    try:
        with open(os.path.join(folder, "mod.json"), encoding="utf-8") as f:
            return not os.path.islink(folder) and json.load(f).get("title") == TITLE
    except (OSError, ValueError, AttributeError):
        return False


def replace(dest, src=None):
    """DEST (a folder) swapped whole for a copy of SRC, or taken off without one, through a folder of its own."""
    parent = os.path.dirname(dest)
    os.makedirs(parent, exist_ok=True)
    staged = tempfile.mkdtemp(dir=parent, prefix=".herdr-fold.")
    if src:
        shutil.copytree(src, os.path.join(staged, "new"))
    if os.path.lexists(dest):
        os.rename(dest, os.path.join(staged, "old"))
    if src:
        os.rename(os.path.join(staged, "new"), dest)
    shutil.rmtree(staged)


def read_keys(path):
    """keys.json's sections ({} when there is none), or None when it is not an object of sections."""
    try:
        with open(path, encoding="utf-8") as f:
            keys = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return None
    return keys if isinstance(keys, dict) and all(isinstance(v, dict) for v in keys.values()) else None


def write_json(path, data):
    fd, temp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".herdr-fold.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(temp, path)


def tidy(home, keep=None):
    """herdr-fold's shared values in HOME gone but those in KEEP. Never with the app running: it holds them all and
    writes them back."""
    path = os.path.join(home, SHARED)
    try:
        with open(path, encoding="utf-8") as f:
            shared = json.load(f)
    except (OSError, ValueError):
        return
    if not isinstance(shared, dict):
        return
    tidied = {key: value for key, value in shared.items() if not key.startswith(PREFIX) or key in (keep or ())}
    if tidied != shared:
        write_json(path, tidied)


def card_pad(app):
    """logic.js's PAD in APP (the app's home, or the package's app/): a card's inside on every side, which a folded
    group keeps under its head; None without it."""
    try:
        with open(os.path.join(app, MOD, "logic.js"), encoding="utf-8") as f:
            found = re.search(r"^export const PAD = (\d+);", f.read(), re.M)
    except OSError:
        return None
    return int(found.group(1)) if found else None


def folded_groups(layout, pad):
    """LAYOUT's groups, each (its column's id, its stack's id, its height folded: its head, PAD under it, its frame,
    as logic.js's FOLDED_GROUP)."""
    for node in nodes(layout):
        kids = node.get("children") or []
        if len(kids) == 2 and ((kids[0].get("content") or {}).get("props") or {}).get("part") == "group-head":
            edge = (node.get("border") or {}).get("width", 0)
            yield node.get("id"), kids[1].get("id"), kids[0]["size"]["px"] + pad + 2 * edge


def prune_state(state, layout, pad=None):
    """STATE (the app's of a layout: its clicks by node) without the nodes LAYOUT no longer has, so a node by a new
    id opens as the layout says; with PAD, a group saved folded at another height at this one's; anything else as it
    was."""
    if not isinstance(state, dict) or not isinstance(state.get("nodes"), dict):
        return state
    ids = {node.get("id") for node in nodes(layout) if isinstance(node, dict)}
    kept = {key: value for key, value in state["nodes"].items() if key in ids}
    for group, stack, folded in folded_groups(layout, pad) if pad is not None else ():
        saved = kept.get(group)
        if (kept.get(stack) or {}).get("hidden") is True and isinstance((saved or {}).get("size"), dict) \
                and "px" in saved["size"]:
            kept[group] = {**saved, "size": {"px": folded}}
    return {**state, "nodes": kept}


def prune(home):
    """The app's state of herdr-fold's layout in HOME pruned to the layout there, a group saved folded at the height the
    mod there folds it to. Never with the app running: it holds the state and writes it back."""
    path = os.path.join(home, LAYOUT_STATE)
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        with open(os.path.join(home, LAYOUT), encoding="utf-8") as f:
            layout = json.load(f)
    except (OSError, ValueError):
        return
    pruned = prune_state(state, layout, card_pad(home))
    if pruned != state:
        write_json(path, pruned)


def named(package):
    """The shared values PACKAGE's mod keeps: every "herdr-fold.NAME" its files spell out."""
    found = set()
    for root, _dirs, files in os.walk(os.path.join(package, "app", MOD)):
        for name in (name for name in files if name.endswith(".js")):
            with open(os.path.join(root, name), encoding="utf-8") as f:
                found.update(re.findall(r'"(herdr-fold\.[\w.-]+)"', f.read()))
    return found


def merge_keys(mine, added):
    """MINE with ADDED's keys in their sections; every other section and key of MINE as it was."""
    merged = {section: dict(keys) for section, keys in mine.items()}
    for section, keys in added.items():
        merged.setdefault(section, {}).update(keys)
    return merged


def drop_keys(mine, added):
    """MINE without the keys ADDED put there (one rebound since stays), and without a section that held only those."""
    kept = {}
    for section, keys in mine.items():
        left = {key: action for key, action in keys.items() if added.get(section, {}).get(key) != action}
        if left or section not in added:
            kept[section] = left
    return kept


def themes(package):
    """The themes PACKAGE brings, each a file under themes/ of its app folder."""
    folder = os.path.join(package, "app", THEMES)
    return [os.path.join(THEMES, name) for name in sorted(os.listdir(folder)) if name.endswith(".json")]


def put_themes(state):
    """The themes the last install put in the app's home, as it recorded them in STATE ([] without a record)."""
    try:
        with open(os.path.join(state, THEMES_RECORD), encoding="utf-8") as f:
            found = json.load(f)
    except (OSError, ValueError):
        return []
    return [rel for rel in found if isinstance(rel, str) and os.path.dirname(rel) == THEMES] \
        if isinstance(found, list) else []


def recorded(state):
    """The keys the last install put, as it recorded them in STATE ({} without a record)."""
    return read_keys(os.path.join(state, RECORD)) or {}


def package_keys(package):
    with open(os.path.join(package, "app", KEYS), encoding="utf-8") as f:
        return json.load(f)


def install(package, home, state, app_running=False, theme=None):
    """PACKAGE's mod, layout (in THEME, a number or name of themes.js's; none: the one it had) and keys into the app's
    HOME, what an earlier version put there and this one does not have taken off: the exit code (0, 3 or 4) the usage
    names; a running app's shared values and state of the layout are left to it."""
    if os.path.lexists(os.path.join(home, MOD)) and not herdr_folds(os.path.join(home, MOD)):
        return 4
    had = apply.layout_theme(os.path.join(home, LAYOUT))
    replace(os.path.join(home, MOD), os.path.join(package, "app", MOD))
    brought = themes(package)
    for rel in set(put_themes(state)) - set(brought):            # an earlier version's, this one no longer brings
        if os.path.isfile(os.path.join(home, rel)):
            os.remove(os.path.join(home, rel))
    for rel in (LAYOUT, *brought):
        os.makedirs(os.path.join(home, os.path.dirname(rel)), exist_ok=True)
        shutil.copyfile(os.path.join(package, "app", rel), os.path.join(home, rel))
    os.makedirs(state, mode=0o700, exist_ok=True)              # the installer's records: their owner's only
    write_json(os.path.join(state, THEMES_RECORD), brought)
    chosen = apply.find(apply.load_themes(), theme) if theme else None
    name = apply.APP_THEME + chosen["id"] if chosen else had
    if name:
        apply.set_layout_theme(os.path.join(home, LAYOUT), name)
    if not app_running:
        tidy(home, named(package))
        prune(home)
    mine = read_keys(os.path.join(home, KEYS))
    if mine is None:
        return 3
    added = package_keys(package)
    write_json(os.path.join(home, KEYS), merge_keys(drop_keys(mine, recorded(state)), added))
    write_json(os.path.join(state, RECORD), added)
    return 0


def uninstall(package, home, state, app_running=False):
    if herdr_folds(os.path.join(home, MOD)):
        replace(os.path.join(home, MOD))
        shutil.rmtree(storage(os.path.join(home, MOD)), ignore_errors=True)
        shutil.rmtree(os.path.join(home, DATA), ignore_errors=True)
    for rel in (LAYOUT, LAYOUT_STATE, *sorted(set(themes(package)) | set(put_themes(state)))):
        if os.path.isfile(os.path.join(home, rel)):
            os.remove(os.path.join(home, rel))
    shutil.rmtree(os.path.join(home, PICTURES), ignore_errors=True)
    mine = read_keys(os.path.join(home, KEYS))
    if mine:
        write_json(os.path.join(home, KEYS), drop_keys(drop_keys(mine, package_keys(package)), recorded(state)))
    for record in (RECORD, THEMES_RECORD):
        if os.path.isfile(os.path.join(state, record)):
            os.remove(os.path.join(state, record))
    if not app_running:
        tidy(home)


def main(argv):
    command, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    if command == "cli" and not args:
        found = cli()
        if found:
            print(found)
        return 0 if found else 1
    if command == "core" and not args:
        found = core()
        if found:
            print(found)
        return 0 if found else 1
    if command == "end-terminals" and not args:
        found = core()
        if found:
            end_terminals(found, app_home())
        return 0
    if command == "home" and not args:
        print(app_home())
        return 0
    if command == "install" and len(args) in (1, 2):
        app = cli()
        return install(args[0], app_home(), state_dir(), bool(app) and running(app), *args[1:])
    if command == "uninstall" and len(args) == 1:
        app = cli()
        return uninstall(args[0], app_home(), state_dir(), bool(app) and running(app)) or 0
    if command == "close" and not args:
        app = cli()
        return 0 if app and close(app) else 1
    if command == "open" and not args:
        found = bundle(cli() or "")
        return subprocess.run(["open", "-g", found], capture_output=True).returncode if found else 1
    print("usage: herdr_app.py cli | core | home | install PACKAGE | uninstall PACKAGE | end-terminals | close | open",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
