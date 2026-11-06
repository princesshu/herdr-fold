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
    AI Sessions run without the rest of the package; the tab layout, which does not, says so."""

    def test_the_sidebar_and_the_sessions_list_need_nothing_else(self):
        for plugin in ("sidebar", "sessions-view"):
            self.assertEqual(outside_needs(os.path.join(PACKAGE, "src", "plugins", plugin)), [], plugin)

    def test_a_plugin_that_imports_the_package_is_caught(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        with open(os.path.join(folder, "view.py"), "w", encoding="utf-8") as f:
            f.write("import os\nfrom herdrlib import herdr\nCONFIG = '~/.config/herdr-fold/settings.json'\n")
        self.assertEqual(outside_needs(folder), ["view.py imports herdrlib", "view.py names ~/.config/herdr-fold"])

    def test_the_tab_layout_says_it_needs_the_installer(self):
        with open(os.path.join(PACKAGE, "src", "plugins", "tab-layout", "herdr-plugin.toml"), encoding="utf-8") as f:
            self.assertIn("install it with herdr-fold's installer", f.read())


def actions(plugin):
    """{id: (command, platforms)} of a plugin's [[actions]], as its manifest writes them (one line each)."""
    with open(os.path.join(PACKAGE, "src", "plugins", plugin, "herdr-plugin.toml"), encoding="utf-8") as f:
        blocks = f.read().split("[[actions]]")[1:]
    found = {}
    for block in blocks:
        fields = dict(re.findall(r"^(id|command|platforms) = (.*)$", block.split("\n[[", 1)[0], re.MULTILINE))
        found[fields["id"].strip('"')] = (ast.literal_eval(fields["command"]), ast.literal_eval(fields["platforms"]))
    return found


class SidebarAlone(unittest.TestCase):
    """The sidebar installed on its own (herdr's marketplace): one action lays the tab out, the sidebar and its
    terminal and the Conversations column, as Restore panels does in herdr-fold."""

    def test_restore_panels_is_an_action_on_every_system(self):
        found = actions("sidebar")
        self.assertEqual(found.get("restore-panels"),
                         (["/usr/bin/python3", "conversations_pane.py", "--restore"], ["macos", "linux"]))
        self.assertEqual(found.get("restore-panels-windows"),
                         (["python", "conversations_pane.py", "--restore"], ["windows"]))


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
