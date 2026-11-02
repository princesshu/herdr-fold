"""Tests for tools/build.py: the shared data layer lives once, in core/, and each piece that installs on its own (the
TUI sidebar, the Herdr app mod) carries a copy of what it needs; a copy that differs from core/ fails here."""
import ast
import importlib.util
import os
import sys
import sysconfig
import unittest

from support import PACKAGE

sys.path.insert(0, os.path.join(PACKAGE, "tools"))
import build  # noqa: E402

CORE = os.path.join(PACKAGE, "core")


class Copies(unittest.TestCase):
    def test_every_copy_is_what_the_core_makes_now(self):
        for rel, content in build.outputs().items():
            with self.subTest(rel), open(os.path.join(PACKAGE, rel), encoding="utf-8") as f:
                self.assertEqual(f.read(), content, "out of date: /usr/bin/python3 tools/build.py")

    def test_a_copy_names_its_source_first(self):
        for rel, content in build.outputs().items():
            with self.subTest(rel):
                self.assertIn("Generated from core/", content.split("\n", 2)[0 if rel.endswith(".py") else 1])

    def test_the_tui_sidebar_gets_each_core_module_it_imports(self):
        sidebar = os.path.join("src", "plugins", "sidebar")
        for name in sorted(os.listdir(CORE)):
            if name.endswith(".py"):
                self.assertIn(os.path.join(sidebar, name), build.outputs(), name)


class Core(unittest.TestCase):
    def test_the_core_uses_the_standard_library_and_itself_only(self):
        # it runs inside the TUI sidebar, the Herdr app's mods and on remote machines: nothing else is there
        own = {name[:-3] for name in os.listdir(CORE) if name.endswith(".py")}
        for name in sorted(own):
            with open(os.path.join(CORE, name + ".py"), encoding="utf-8") as f:
                tree = ast.parse(f.read())
            imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                        for alias in node.names}
            imported |= {node.module.split(".")[0] for node in ast.walk(tree)
                         if isinstance(node, ast.ImportFrom) and node.module}
            with self.subTest(name):
                self.assertEqual(sorted(m for m in imported - own if not standard(m)), [])


def standard(module):
    """Whether MODULE comes with Python itself (built in, or from its own library folder)."""
    spec = importlib.util.find_spec(module)
    return bool(spec) and (spec.origin in ("built-in", "frozen")
                           or (spec.origin or "").startswith(sysconfig.get_paths()["stdlib"]))


if __name__ == "__main__":
    unittest.main()
