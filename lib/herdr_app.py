"""herdr-fold in the Herdr app (herdr's desktop app), for install.sh and uninstall.sh: the mod, its layout (in its own
theme) and its keys into the app's home, and off again; nothing else of the app's is touched. Usage: herdr_app.py cli |
home | install PACKAGE (0; 3: keys.json unreadable, left as it is; 4: a mods/herdr-fold not herdr-fold's) | uninstall"""
import json
import os
import shutil
import sys
import tempfile

MOD, LAYOUT, KEYS = os.path.join("mods", "herdr-fold"), os.path.join("layouts", "herdr-fold.json"), "keys.json"
THEME = os.path.join("themes", "herdr-fold.json")   # the layout's own (the app offers it only there)
TITLE = "herdr-fold"            # the mod.json title that marks a mods/herdr-fold folder as herdr-fold's copy


def cli():
    """The app's command line (herdr-app on PATH, else where the app puts it), or None without the app."""
    local = os.path.expanduser("~/.local/bin/herdr-app")
    return shutil.which("herdr-app") or (local if os.access(local, os.X_OK) else None)


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


def write_keys(path, keys):
    fd, temp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".keys.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(temp, path)


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


def package_keys(package):
    with open(os.path.join(package, "app", KEYS), encoding="utf-8") as f:
        return json.load(f)


def install(package, home):
    """PACKAGE's mod, layout and keys into the app's HOME: the exit code (0, 3 or 4) the usage names."""
    if os.path.lexists(os.path.join(home, MOD)) and not herdr_folds(os.path.join(home, MOD)):
        return 4
    replace(os.path.join(home, MOD), os.path.join(package, "app", MOD))
    for rel in (LAYOUT, THEME):
        os.makedirs(os.path.join(home, os.path.dirname(rel)), exist_ok=True)
        shutil.copyfile(os.path.join(package, "app", rel), os.path.join(home, rel))
    mine = read_keys(os.path.join(home, KEYS))
    if mine is None:
        return 3
    write_keys(os.path.join(home, KEYS), merge_keys(mine, package_keys(package)))
    return 0


def uninstall(package, home):
    if herdr_folds(os.path.join(home, MOD)):
        replace(os.path.join(home, MOD))
    for rel in (LAYOUT, THEME):
        if os.path.isfile(os.path.join(home, rel)):
            os.remove(os.path.join(home, rel))
    mine = read_keys(os.path.join(home, KEYS))
    if mine:
        write_keys(os.path.join(home, KEYS), drop_keys(mine, package_keys(package)))


def main(argv):
    command, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    if command == "cli" and not args:
        found = cli()
        if found:
            print(found)
        return 0 if found else 1
    if command == "home" and not args:
        print(app_home())
        return 0
    if command == "install" and len(args) == 1:
        return install(args[0], app_home())
    if command == "uninstall" and len(args) == 1:
        uninstall(args[0], app_home())
        return 0
    print("usage: herdr_app.py cli | home | install PACKAGE | uninstall PACKAGE", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
