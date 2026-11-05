"""Tests for the installer's catalogs (src/lang/<language>.txt): every used key exists, none is unused, all languages
have the same keys, and the installer scripts print and ask only through the catalog.
"""
import ast
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

PACKAGE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LANG_DIR = os.path.join(PACKAGE, "src", "lang")
KEY = r"[a-z0-9_.]+"
USES = {   # kind of file → how it looks a text up
    ".sh": r"\$\(t (%s)" % KEY,
    ".ps1": r"\(T '(%s)'" % KEY,
    ".py": r"\bt\(\"(%s)\"" % KEY,
}
# the shell scripts print through the helpers; the text is a $(t key) or a value ($var, ~/$var), never a sentence
SHELL_HELPERS = re.compile(r'\b(ok|warn|fail|skip|have|saved|note|step|section|ask|prompt) "(?!\$\(t |\$|~/\$)')
# PowerShell prints through Line (its marks); the text is a T 'key' or a value, never a literal sentence
# words in a row: a sentence, not a format or a single name
SENTENCE = re.compile(r"[A-Za-z]{2,}[ ,:]+[A-Za-z]{2,}")
PS_OUTPUT = re.compile(r'Write-Output "(?!\$\(T |  \$mark )|\bLine \w+ ["\'][^"\']* [^"\']*["\']')


def catalog(path):
    """KEY → text of a catalog; a text that goes on (a line ending in \\) is joined with the next, indented line."""
    entries, going_on = {}, None
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if going_on:
                assert line.startswith("  ") and line.strip(), f"{os.path.basename(path)}:{n}: not indented: {line!r}"
                entries[going_on] += line.lstrip()
            elif not line.strip() or line.startswith("#"):
                continue
            else:
                m = re.fullmatch(r"(%s) = (.*)" % KEY, line)
                assert m, f"{os.path.basename(path)}:{n}: not a `key = text` line: {line!r}"
                assert m.group(1) not in entries, f"{os.path.basename(path)}:{n}: duplicate key {m.group(1)}"
                going_on, entries[m.group(1)] = m.group(1), m.group(2)
            if entries[going_on].endswith("\\"):
                entries[going_on] = entries[going_on][:-1]
            else:
                going_on = None
    return entries


def used_keys():
    """Every key the package's scripts look up, with the first file that does (the tests themselves not counted)."""
    keys = {}
    for root, dirs, files in os.walk(PACKAGE):
        dirs[:] = [d for d in dirs if d not in (".git", "tests", "__pycache__")]
        for name in sorted(files):
            pattern = USES.get(os.path.splitext(name)[1])
            if pattern:
                path = os.path.join(root, name)
                with open(path, encoding="utf-8-sig") as f:
                    for key in re.findall(pattern, f.read()):
                        keys.setdefault(key, os.path.relpath(path, PACKAGE))
    return keys


class Catalog(unittest.TestCase):
    def setUp(self):
        self.english = catalog(os.path.join(LANG_DIR, "en.txt"))

    def test_every_used_key_is_in_english(self):
        missing = {k: f for k, f in used_keys().items() if k not in self.english}
        self.assertEqual(missing, {})

    def test_no_unused_keys(self):
        self.assertEqual(sorted(set(self.english) - set(used_keys())), [])

    def test_all_languages_have_the_same_keys(self):
        for path in glob.glob(os.path.join(LANG_DIR, "*.txt")):
            self.assertEqual(sorted(catalog(path)), sorted(self.english), os.path.basename(path))


class GoesOn(unittest.TestCase):
    """A text over more lines (a line ending in \\, the next one indented) reads the same in Python and in the shell."""

    CATALOG = ("# a comment \\\n"
               "long.words = One sentence, \\\n"
               "  then the rest: %s.\n"
               "long.lines = Usage:\\\n"
               "  \\n  first\\\n"
               "    \\n  second\n"
               "short = Done\n")

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        with open(os.path.join(self.tmp, "en.txt"), "w", encoding="utf-8") as f:
            f.write(self.CATALOG)

    def python(self, key, *args):
        sys.path.insert(0, os.path.join(PACKAGE, "src"))
        import i18n
        saved = i18n.LANG_DIR, i18n._texts
        i18n.LANG_DIR, i18n._texts = self.tmp, None
        try:
            return i18n.t(key, *args)
        finally:
            i18n.LANG_DIR, i18n._texts = saved

    def shell(self, key, *args):
        script = 'CATALOG_DIR="$1"; shift; . "$0"; t "$@"'
        return subprocess.run(["bash", "-c", script, os.path.join(PACKAGE, "lib", "i18n.sh"), self.tmp, key, *args],
                              capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"}).stdout

    def test_words_part_at_the_space_before_the_backslash(self):
        for read in (self.python, self.shell):
            self.assertEqual(read("long.words", "here"), "One sentence, then the rest: here.", read.__name__)

    def test_lines_part_right_before_a_new_line_and_keep_their_own_indentation(self):
        for read in (self.python, self.shell):
            self.assertEqual(read("long.lines"), "Usage:\n  first\n  second", read.__name__)
            self.assertEqual(read("short"), "Done", read.__name__)


class NoHardcodedText(unittest.TestCase):
    def test_shell_installer_prints_and_asks_through_the_catalog(self):
        for rel in ("install.sh", "uninstall.sh", "machines.sh", "remote/prepare-unix.sh", "tools/sync.sh"):
            with open(os.path.join(PACKAGE, rel), encoding="utf-8") as f:
                hits = [f"{rel}:{n}: {line.strip()}" for n, line in enumerate(f, 1)
                        if SHELL_HELPERS.search(line) and not line.lstrip().startswith("#")]
            self.assertEqual(hits, [])

    def test_python_scripts_print_through_the_catalog(self):
        # a sentence handed straight to print(), line(), an error or a notification is a text outside the catalog; the
        # sessions-view and sidebar plugins are standalone (their own English texts)
        hits = []
        for root, dirs, files in os.walk(os.path.join(PACKAGE, "src")):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "sessions-view", "sidebar")]
            for name in (n for n in files if n.endswith(".py")):
                path = os.path.join(root, name)
                with open(path, encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    if not (isinstance(node, ast.Call) and self.shown(node.func)):
                        continue
                    compared = {id(c) for arg in node.args for n in ast.walk(arg) if isinstance(n, ast.Compare)
                                for c in ast.walk(n)}           # done == "not herdr-fold's": compared, not shown
                    texts = [c.value for arg in node.args for c in ast.walk(arg)
                             if isinstance(c, ast.Constant) and isinstance(c.value, str) and id(c) not in compared]
                    if any(SENTENCE.search(text) for text in texts):
                        hits.append(f"{os.path.relpath(path, PACKAGE)}:{node.lineno}")
        self.assertEqual(hits, [])

    @staticmethod
    def shown(func):
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
        return name in ("print", "line", "exit", "herdr") or name.endswith("Error")

    def test_windows_prepare_prints_through_the_catalog(self):
        with open(os.path.join(PACKAGE, "remote/prepare-windows.ps1"), encoding="utf-8-sig") as f:
            hits = [f"prepare-windows.ps1:{n}: {line.strip()}" for n, line in enumerate(f, 1) if PS_OUTPUT.search(line)]
        self.assertEqual(hits, [])

    def test_texts_never_suggest_killing_processes_by_name(self):
        for path in glob.glob(os.path.join(PACKAGE, "src", "lang", "*.txt")):
            with open(path, encoding="utf-8") as f:
                found = [line for line in f if re.search(r"\b(pkill|killall)\b", line)]
            self.assertEqual(found, [], path)

    def test_texts_carry_no_status_marks(self):
        # the mark comes from the code that prints the line (lib/output.sh, i18n.line, Line in PowerShell)
        marked = [key for key, text in catalog(os.path.join(LANG_DIR, "en.txt")).items()
                  if re.match(r"\s*(✓|!|»|\*|·|--|\[[✓!✗*-]\])\s", text)]
        self.assertEqual(marked, [])

    def test_no_text_banners_left_in_the_installer(self):
        with open(os.path.join(PACKAGE, "install.sh"), encoding="utf-8") as f:
            self.assertNotIn("<<'EOF'", f.read())


if __name__ == "__main__":
    unittest.main()
