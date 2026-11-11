"""Every Python script the package installs finds its own modules there: what it imports from the package is in the
same file list (files.txt for this Mac, remote/files.txt for each kind of remote machine).
"""
import ast
import glob
import os
import re
import shutil
import tempfile
import unittest

PACKAGE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def rows(rel, kind=None, part=None):
    """{path in the package: location on the machine} of a file list; remote/files.txt rows for KIND only; a list's
    rows for PART only ("both": the shared ones, what the Herdr app alone gets)."""
    found = {}
    with open(os.path.join(PACKAGE, rel), encoding="utf-8") as f:
        for row in f:
            if not row.strip() or row.lstrip().startswith("#"):
                continue
            cols = [c.strip() for c in row.split("|")]
            if kind and cols[2] not in ("all", kind) or part and cols[-1] != part:
                continue
            src, dest = cols[0], cols[1]
            for path in sorted(glob.glob(os.path.join(PACKAGE, src))):
                rel_src = os.path.relpath(path, PACKAGE)
                found[rel_src] = dest + os.path.basename(path) if "*" in src else dest
    return found


def own_imports(src):
    """The package modules SRC imports, as package paths: a module next to it, or one of config/herdr."""
    with open(os.path.join(PACKAGE, src), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    for name in sorted(names):
        for candidate in (os.path.join(os.path.dirname(src), name + ".py"), os.path.join("src", name + ".py")):
            if os.path.isfile(os.path.join(PACKAGE, candidate)):
                yield candidate
                break


class Manifests(unittest.TestCase):
    def check(self, files):
        missing = [f"{src} imports {module}" for src in files if src.endswith(".py")
                   for module in own_imports(src) if module not in files]
        self.assertEqual(missing, [])

    def test_this_macs_scripts_find_their_modules(self):
        self.check(rows("files.txt"))

    def test_a_unix_machines_scripts_find_their_modules(self):
        self.check(rows("remote/files.txt", "unix"))

    def test_a_windows_machines_scripts_find_their_modules(self):
        self.check(rows("remote/files.txt", "windows"))

    def test_the_shared_scripts_find_their_modules_without_the_tui(self):
        self.check(rows("files.txt", part="both"))
        self.check(rows("remote/files.txt", "unix", "both"))
        self.check(rows("remote/files.txt", "windows", "both"))

    def test_workspaces_copies_go_where_it_goes(self):
        # it loads its copy of core/git.py by its path (herdrlib's sidebar modules bring the sidebar's as git): no
        # import names it for the checks above
        folder = os.path.join("src", "plugins", "workspaces")
        script = os.path.join(folder, "workspaces.py")
        own = sorted(os.path.join(folder, name) for name in os.listdir(os.path.join(PACKAGE, folder))
                     if name.endswith(".py"))
        self.assertIn(os.path.join(folder, "git.py"), own)
        for listed in (rows("files.txt"), rows("remote/files.txt", "unix"), rows("remote/files.txt", "windows")):
            self.assertEqual({rel: os.path.dirname(listed.get(rel, "")) for rel in own},
                             dict.fromkeys(own, os.path.dirname(listed[script])))

    def test_every_line_names_its_part(self):
        for rel, column in (("files.txt", 2), (os.path.join("remote", "files.txt"), 3)):
            with open(os.path.join(PACKAGE, rel), encoding="utf-8") as f:
                bad = [row for row in f if row.strip() and not row.lstrip().startswith("#")
                       and [c.strip() for c in row.split("|")][column:] not in (["tui"], ["both"])]
            self.assertEqual(bad, [], rel)
        with open(os.path.join(PACKAGE, "Brewfile"), encoding="utf-8") as f:
            bad = [row for row in f if row.startswith(("brew ", "cask ")) and not re.search(r"\[(tui|both)\]\s*$", row)]
        self.assertEqual(bad, [])


def own_imports_of(path):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    return {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | \
        {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}


def outside_needs(folder):
    """What the plugin in FOLDER needs from the rest of the package: the package's modules it imports, and the package's
    installed folder named in its code."""
    package = {name[:-3] for name in os.listdir(os.path.join(PACKAGE, "src")) if name.endswith(".py")}
    own = {name[:-3] for name in os.listdir(folder) if name.endswith(".py")}
    needs = []
    for name in sorted(os.listdir(folder)):
        if name.endswith(".py"):
            path = os.path.join(folder, name)
            needs += [f"{name} imports {module}" for module in sorted((own_imports_of(path) & package) - own)]
            with open(path, encoding="utf-8") as f:
                if ".config/herdr-fold" in f.read():
                    needs.append(f"{name} names ~/.config/herdr-fold")
    return needs


class Standalone(unittest.TestCase):
    """The herdr marketplace lists every plugin of the repository as installable on its own: the sidebar and
    AI Sessions run without the rest of the package; Workspaces, which does not, says so."""

    def test_the_sidebar_and_the_sessions_list_need_nothing_else(self):
        for plugin in ("sidebar", "sessions-view"):
            self.assertEqual(outside_needs(os.path.join(PACKAGE, "src", "plugins", plugin)), [], plugin)

    def test_a_plugin_that_imports_the_package_is_caught(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        with open(os.path.join(folder, "view.py"), "w", encoding="utf-8") as f:
            f.write("import os\nfrom herdrlib import herdr\nCONFIG = '~/.config/herdr-fold/settings.json'\n")
        self.assertEqual(outside_needs(folder), ["view.py imports herdrlib", "view.py names ~/.config/herdr-fold"])

    def test_workspaces_says_it_needs_the_installer(self):
        with open(os.path.join(PACKAGE, "src", "plugins", "workspaces", "herdr-plugin.toml"), encoding="utf-8") as f:
            self.assertIn("install it with herdr-fold's installer", f.read())


def tables(plugin, kind):
    """The id, on, command and platforms of each of a plugin's [[KIND]] tables (actions, events, startup, panes), as
    its manifest writes them (one line each): {field: its text}."""
    with open(os.path.join(PACKAGE, "src", "plugins", plugin, "herdr-plugin.toml"), encoding="utf-8") as f:
        found = f.read().split(f"[[{kind}]]")[1:]
    return [dict(re.findall(r"^(id|on|command|platforms) = (.*)$", table.split("\n[[", 1)[0], re.MULTILINE))
            for table in found]


def actions(plugin):
    """{id: (command, platforms)} of a plugin's [[actions]]."""
    return {table["id"].strip('"'): (ast.literal_eval(table["command"]), ast.literal_eval(table["platforms"]))
            for table in tables(plugin, "actions")}


def hooks(plugin, kind, on=None):
    """(command, platforms) of each of a plugin's [[KIND]] tables (events, startup), the events herdr's ON only."""
    return [(ast.literal_eval(table["command"]), ast.literal_eval(table["platforms"])) for table in tables(plugin, kind)
            if on is None or table.get("on") == f'"{on}"']


class SidebarAlone(unittest.TestCase):
    """The sidebar installed on its own (herdr's marketplace): one action lays the tab out, the sidebar above its
    terminal, as Restore panels does in herdr-fold."""

    def test_restore_panels_is_an_action_on_every_system(self):
        found = actions("sidebar")
        self.assertEqual(found.get("restore-panels"),
                         (["/usr/bin/python3", "panes.py", "--restore"], ["macos", "linux"]))
        self.assertEqual(found.get("restore-panels-windows"),
                         (["python", "panes.py", "--restore"], ["windows"]))


class Hooks(unittest.TestCase):
    """What herdr runs by itself: the dock lays out a new tab and comes back when herdr starts, Workspaces brings back
    herdr-fold's agents, each on every system."""

    def test_the_dock_lays_out_a_new_tab(self):
        self.assertEqual(hooks("sidebar", "events", "tab.created"),
                         [(["/usr/bin/python3", "panes.py", "--new-tab"], ["macos", "linux"]),
                          (["python", "panes.py", "--new-tab"], ["windows"])])

    def test_the_dock_comes_back_when_herdr_starts(self):
        self.assertEqual(hooks("sidebar", "startup"),
                         [(["/usr/bin/python3", "panes.py", "--startup"], ["macos", "linux"]),
                          (["python", "panes.py", "--startup"], ["windows"])])

    def test_workspaces_brings_back_the_agents_when_herdr_starts(self):
        self.assertEqual(hooks("workspaces", "startup"),
                         [(["/bin/sh", "-c", 'exec /usr/bin/python3 "$HOME/.config/herdr-fold/restore_panes.py" '
                                             "--startup"], ["macos", "linux"]),
                          (["python", "..\\..\\restore_panes.py", "--startup"], ["windows"])])

    def test_a_windows_command_starts_as_the_windows_setup_finds_it(self):
        # prepare-windows.ps1 puts the machine's Python's full path in where a command starts so, word for word
        odd = []
        for plugin in sorted(os.listdir(os.path.join(PACKAGE, "src", "plugins"))):
            if not os.path.isfile(os.path.join(PACKAGE, "src", "plugins", plugin, "herdr-plugin.toml")):
                continue
            odd += [f"{plugin} {kind}: {table['command']}" for kind in ("actions", "events", "startup", "panes")
                    for table in tables(plugin, kind)
                    if table.get("platforms") == '["windows"]' and not table["command"].startswith('["python", ')]
        self.assertEqual(odd, [])


class Commands(unittest.TestCase):
    """What a machine runs is where the file lists put it."""

    def test_the_windows_sidebar_runs_the_file_a_windows_machine_gets(self):
        import sys
        sys.path.insert(0, os.path.join(PACKAGE, "src"))
        import herdrlib
        script = herdrlib.WINDOWS_SIDEBAR_COMMAND.split('"$HOME\\', 1)[1].split('"', 1)[0].replace("\\", "/")
        self.assertIn(script, rows("remote/files.txt", "windows").values())


if __name__ == "__main__":
    unittest.main()
