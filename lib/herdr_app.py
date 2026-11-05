"""herdr-fold in the Herdr app, for install.sh and uninstall.sh: the mod, its layout, themes and keys into the app's
home and off again, the tabs' terminals it started ended. Usage: herdr_app.py cli | core | home | install PACKAGE (0; 3:
keys.json unreadable, left as it is; 4: a mods/herdr-fold not herdr-fold's) | uninstall PACKAGE | end-terminals"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

MOD, LAYOUT, KEYS = os.path.join("mods", "herdr-fold"), os.path.join("layouts", "herdr-fold.json"), "keys.json"
THEMES = "themes"              # herdr-fold.json (the layout's own) and the TUI's themes, herdr-fold-ID.json
TITLE = "herdr-fold"            # the mod.json title that marks a mods/herdr-fold folder as herdr-fold's copy
TERMINALS = "fold-terminals"    # the layout's stack of the tabs' terminals the mod started (app/mods/herdr-fold)
SHARED = "shared.json"          # the app's shared values: the mod notes there the app's panel buttons it took off
BEFORE, BUTTONS = "herdr-fold.app-panels", "workspace.panels"


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


def app_home():
    return os.environ.get("HERDR_APP_HOME") or os.path.expanduser("~/.config/herdr-app")


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


def give_back(home):
    """The app's own panel buttons as they were before the layout took them off, when the app stopped while showing
    it (a running app's mod gives them back as the layout goes); the mod's note of them gone."""
    path = os.path.join(home, SHARED)
    try:
        with open(path, encoding="utf-8") as f:
            shared = json.load(f)
    except (OSError, ValueError):
        return
    if not isinstance(shared, dict) or BEFORE not in shared:
        return
    before = shared.pop(BEFORE)
    if isinstance(before, dict) and before.get("panels") is None:
        shared.pop(BUTTONS, None)
    elif isinstance(before, dict):
        shared[BUTTONS] = before["panels"]
    write_json(path, shared)


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
    """The themes PACKAGE brings, each a file under themes/: all named herdr-fold, none a person's own."""
    return [os.path.join(THEMES, name) for name in sorted(os.listdir(os.path.join(package, "app", THEMES)))
            if name.startswith("herdr-fold") and name.endswith(".json")]


def package_keys(package):
    with open(os.path.join(package, "app", KEYS), encoding="utf-8") as f:
        return json.load(f)


def install(package, home):
    """PACKAGE's mod, layout and keys into the app's HOME: the exit code (0, 3 or 4) the usage names."""
    if os.path.lexists(os.path.join(home, MOD)) and not herdr_folds(os.path.join(home, MOD)):
        return 4
    replace(os.path.join(home, MOD), os.path.join(package, "app", MOD))
    for rel in (LAYOUT, *themes(package)):
        os.makedirs(os.path.join(home, os.path.dirname(rel)), exist_ok=True)
        shutil.copyfile(os.path.join(package, "app", rel), os.path.join(home, rel))
    mine = read_keys(os.path.join(home, KEYS))
    if mine is None:
        return 3
    write_json(os.path.join(home, KEYS), merge_keys(mine, package_keys(package)))
    return 0


def uninstall(package, home):
    if herdr_folds(os.path.join(home, MOD)):
        replace(os.path.join(home, MOD))
    for rel in (LAYOUT, *themes(package)):
        if os.path.isfile(os.path.join(home, rel)):
            os.remove(os.path.join(home, rel))
    mine = read_keys(os.path.join(home, KEYS))
    if mine:
        write_json(os.path.join(home, KEYS), drop_keys(mine, package_keys(package)))
    give_back(home)


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
    if command == "install" and len(args) == 1:
        return install(args[0], app_home())
    if command == "uninstall" and len(args) == 1:
        uninstall(args[0], app_home())
        return 0
    print("usage: herdr_app.py cli | core | home | install PACKAGE | uninstall PACKAGE | end-terminals",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
