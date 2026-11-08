"""Repository hygiene: publishable files keep .editorconfig and .gitattributes (LF, final newline, lines up to 120,
PowerShell UTF-8 with a BOM), comments stay short, and .gitignore keeps machine-specific and generated files out.
"""
import ast
import fnmatch
import glob
import os
import re
import subprocess
import unittest

from support import PACKAGE, PNG_SIGNATURE, catalog_text, is_webp, package_text, publishable_files

# what must never reach the repository: system and editor clutter, caches, secrets and keys, backups, the files of AI
# tools, and the per-machine state that lives in the user's config folder
MUST_IGNORE = [".DS_Store", "._x", "Thumbs.db", "desktop.ini", "__pycache__/x.pyc", ".venv/x", ".mypy_cache/x",
               ".idea/x", ".vscode/x", "x.swp", "x~", ".env", ".env.local", "x.pem", "x.key", "id_ed25519",
               "id_rsa.pub", "x.log", "x.bak", "x.tmp", "x.orig", ".claude/settings.local.json", ".codex/x",
               ".cursor/x", ".aider.chat.history.md", "CLAUDE.md", "AGENTS.md", "machines.txt",
               "statusline.json", "setup-folder", "private-words.txt"]


def text_files():
    for rel in publishable_files():
        with open(os.path.join(PACKAGE, rel), "rb") as f:
            data = f.read()
        if not (data.startswith(PNG_SIGNATURE) or is_webp(data)):
            yield rel, data


class RepoFiles(unittest.TestCase):
    def test_lf_line_endings_and_a_final_newline(self):
        bad = [rel for rel, data in text_files() if b"\r\n" in data or (data and not data.endswith(b"\n"))]
        self.assertEqual(bad, [])

    def test_no_first_person_plural(self):
        # the repository names herdr-fold, its installer, its plugins: never a first-person plural, in prose or in a
        # name (a word, or a part of one between _ . -); "US", the country, aside. The words are spelled in parts here,
        # so this test does not find itself
        words = ["w" "e", "o" "ur", "o" "urs", "o" "urselves", "u" "s"]
        word = re.compile(r"(?<![A-Za-z])(?:" + "|".join(words + [w.capitalize() for w in words if w != "u" "s"])
                          + r")(?![A-Za-z])")
        found = []
        for rel, data in text_files():
            found += [f"{rel}:{n}" for n, line in enumerate(data.decode("utf-8").splitlines(), 1) if word.search(line)]
        self.assertEqual(found, [])

    def test_no_line_is_longer_than_120_characters(self):
        # .editorconfig's max_line_length, counted in characters; a Markdown table row and a line that is only a URL
        # cannot be broken
        long = [f"{rel}:{n} ({len(line)})" for rel, data in text_files()
                for n, line in enumerate(data.decode("utf-8-sig").split("\n"), 1)
                if len(line) > 120 and not (rel.endswith(".md") and line.lstrip().startswith("|"))
                and not re.fullmatch(r"\s*https?://\S+", line)]
        self.assertEqual(long, [])

    def test_scripts_have_at_most_two_empty_lines_in_a_row(self):
        bad = [rel for rel, data in text_files() if rel.endswith((".py", ".sh", ".ps1")) and b"\n\n\n\n" in data]
        self.assertEqual(bad, [])

    def test_every_file_a_script_opens_is_closed(self):
        # open() only as a `with` item: a file left open is a ResourceWarning, and on Windows a file that stays locked
        loose = []
        for rel, data in text_files():
            if not rel.endswith(".py"):
                continue
            tree = ast.parse(data.decode("utf-8"))
            closed = {id(item.context_expr) for node in ast.walk(tree) if isinstance(node, ast.With)
                      for item in node.items}
            loose += [f"{rel}:{node.lineno}" for node in ast.walk(tree) if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Name) and node.func.id == "open" and id(node) not in closed]
        self.assertEqual(loose, [])

    def test_herdr_folds_scripts_leave_no_python_cache_beside_the_installed_files(self):
        # run by hand, by a herdr key or by the installer, a package script writes no __pycache__ into the installed
        # package: it turns that off before it imports a module of its own (the environment's setting would reach
        # everyone's Python in the panes)
        roots = [os.path.join(PACKAGE, "src"), os.path.join(PACKAGE, "src", "plugins", "sidebar")]
        late = []
        for rel, data in text_files():
            if not (rel.startswith("src/") and rel.endswith(".py")):
                continue
            source = data.decode("utf-8")
            tree = ast.parse(source)
            if not any(isinstance(node, ast.If) and "__main__" in ast.dump(node.test) for node in tree.body):
                continue
            local_modules = {name[:-3] for folder in roots + [os.path.dirname(os.path.join(PACKAGE, rel))]
                             for name in os.listdir(folder) if name.endswith(".py")}
            imports = [node.lineno for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
                       and (node.module if isinstance(node, ast.ImportFrom) else node.names[0].name).split(".")[0]
                       in local_modules]
            if not imports:
                continue
            off = [n for n, line in enumerate(source.splitlines(), 1)
                   if line.startswith("sys.dont_write_bytecode = True")]
            if not off or off[0] > imports[0]:
                late.append(rel)
        self.assertEqual(late, [])

    def test_prose_names_the_sidebar_in_lower_case(self):
        # "the sidebar", as any other part; "Sidebar" only as a name: herdr-sidebar's pane label ("Sidebar"), the
        # plugin's display name, its action titles ("Sidebar: files") and the class
        name = re.compile(r'"Sidebar"|Sidebar \(herdr-fold\)|Sidebar:|class Sidebar|Sidebar\(')
        found = [f"{rel}:{n}" for rel, data in text_files() if rel != "tests/test_repo_files.py"
                 for n, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1)
                 if re.search(r"\bSidebar\b", name.sub("", line))]
        self.assertEqual(found, [])

    def test_powershell_variables_differ_by_more_than_case(self):
        # PowerShell ignores case in variable names: $here would overwrite $Here
        clashes = []
        for rel, data in text_files():
            if rel.endswith(".ps1"):
                names = {}
                for name in re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", data.decode("utf-8-sig")):
                    names.setdefault(name.lower(), set()).add(name)
                clashes += [f"{rel}: {' '.join(sorted(spellings))}" for low, spellings in names.items()
                            if len(spellings) > 1 and low not in ("true", "false", "null", "env")]
        self.assertEqual(clashes, [])

    def test_powershell_scripts_have_a_bom(self):
        bad = [rel for rel, data in text_files() if rel.endswith(".ps1") and not data.startswith(b"\xef\xbb\xbf")]
        self.assertEqual(bad, [])

    def test_gitignore_keeps_machine_files_out(self):
        # the repository's own .gitignore only, not this machine's global excludes
        done = subprocess.run(["git", "-C", PACKAGE, "-c", "core.excludesFile=/dev/null", "check-ignore", "--no-index",
                               *MUST_IGNORE],
                              capture_output=True, text=True)
        self.assertEqual(sorted(done.stdout.split()), sorted(MUST_IGNORE))


def listed_rows(rel):
    """A file list's rows by their package path: (location, ..., part), as the row has them."""
    rows = {}
    with open(os.path.join(PACKAGE, rel), encoding="utf-8") as f:
        for row in f:
            if row.strip() and not row.lstrip().startswith("#"):
                cells = [cell.strip() for cell in row.split("|")]
                rows[cells[0]] = tuple(cells[1:])
    return rows


def listed(rel):
    """The package paths a file list names (glob rows: the files they match), and the rows that match nothing."""
    found, empty = set(), []
    with open(os.path.join(PACKAGE, rel), encoding="utf-8") as f:
        for row in f:
            if not row.strip() or row.lstrip().startswith("#"):
                continue
            src = row.split("|")[0].strip()
            matches = glob.glob(os.path.join(PACKAGE, src))
            found.update(os.path.relpath(m, PACKAGE) for m in matches)
            if not matches:
                empty.append(src)
    return found, empty


# files nothing has to name: the repository's own files and the tests (unittest finds them)
SELF_EVIDENT = {".editorconfig", ".gitattributes", ".gitignore", "README.md", "LICENSE", "CHANGELOG.md",
                "CONTRIBUTING.md", "SECURITY.md", "THIRD_PARTY_NOTICES.md"}


class Comments(unittest.TestCase):
    MOST = 3
    SLASHES = (".js", ".swift", ".html", ".svg")                 # their line comments start with //, the rest's with #
    PAIRS = {".js": [("/*", "*/")], ".swift": [("/*", "*/")], ".html": [("/*", "*/"), ("<!--", "-->")],
             ".svg": [("<!--", "-->")], ".ps1": [("<#", "#>")]}

    def blocks(self, rel, text):
        """(line, length) of each comment block: full-line comments in a row, a block comment, a docstring."""
        ext = os.path.splitext(rel)[1]
        mark = "//" if ext in self.SLASHES else "#"
        found, start, run, closing = [], 0, 0, None
        for n, line in enumerate(text.splitlines() + [""], 1):
            s = line.strip()
            if closing:
                if closing in s:
                    found.append((start, n - start + 1))
                    closing = None
                continue
            pair = next(((o, c) for o, c in self.PAIRS.get(ext, []) if s.startswith(o)), None)
            if pair:
                if pair[1] in s[len(pair[0]):]:
                    found.append((n, 1))
                else:
                    start, closing = n, pair[1]
            elif s.startswith(mark) and not (n == 1 and s.startswith("#!")):
                start, run = start if run else n, run + 1
            elif run:
                found.append((start, run))
                run = 0
        if ext == ".py":
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    doc = ast.get_docstring(node, clean=False)
                    if doc:
                        found.append((node.body[0].lineno, doc.count("\n") + 1))
        return found

    def test_no_comment_is_longer_than_three_lines(self):
        """A longer explanation belongs in docs/."""
        long = []
        for rel, data in text_files():
            if rel.endswith(".md") or os.path.basename(rel) == "LICENSE":
                continue
            text = data.decode("utf-8-sig")
            long += [f"{rel}:{line} ({n} lines)" for line, n in self.blocks(rel, text) if n > self.MOST]
        self.assertEqual(long, [])


class GhosttySettings(unittest.TestCase):
    def test_ctrl_option_zero_types_a_zero(self):
        # the layouts that put zero there would send it as a command; for the others the chord does nothing else
        with open(os.path.join(PACKAGE, "config", "ghostty", "config")) as f:
            self.assertIn("keybind = ctrl+alt+digit_0=text:0", f.read().splitlines())

    def test_quitting_asks_first(self):
        # herdr and the agents keep running after Ghostty quits, but a Cmd+Q by mistake is asked about first
        with open(os.path.join(PACKAGE, "config", "ghostty", "config"), encoding="utf-8") as f:
            self.assertIn("confirm-close-surface = true", f.read().splitlines())


class Brewfile(unittest.TestCase):
    def test_it_brings_the_sidebars_tools(self):
        """bat colors a file's preview, delta a diff's and ripgrep searches fast; without them the sidebar's own pager
        shows them plainer and its search runs git grep or its own."""
        with open(os.path.join(PACKAGE, "Brewfile")) as f:
            names = set(re.findall(r'^brew "([^"]+)"', f.read(), re.M))
        self.assertTrue({"bat", "git-delta", "ripgrep"} <= names)
        with open(os.path.join(PACKAGE, "THIRD_PARTY_NOTICES.md")) as f:
            notices = f.read()
        self.assertIn("| bat |", notices)
        self.assertIn("| delta |", notices)
        self.assertIn("| ripgrep |", notices)
        self.assertNotIn("herdr-sidebar", notices)

    def test_the_installers_first_screen_names_its_programs(self):
        """Every program the Brewfile brings is named before the first question (git-delta by its own name, delta);
        the font is the one left out."""
        with open(os.path.join(PACKAGE, "Brewfile")) as f:
            names = re.findall(r'^(?:brew|cask) "([^"]+)"', f.read(), re.M)
        intro = catalog_text("install.intro").lower()
        missing = [name for name in names if not name.startswith("font-")
                   and not re.search(rf"\b{re.escape(name.removeprefix('git-'))}\b", intro)]
        self.assertEqual(missing, [])


class Layout(unittest.TestCase):
    def test_every_listed_file_exists(self):
        for rel in ("files.txt", os.path.join("remote", "files.txt")):
            self.assertEqual(listed(rel)[1], [], rel)

    def test_every_file_is_used(self):
        files = publishable_files()
        used = listed("files.txt")[0] | listed(os.path.join("remote", "files.txt"))[0]
        texts = {rel: data.decode("utf-8", "replace") for rel, data in text_files()}
        def named(rel, text):                          # by its file name, or as a module another file imports
            name = os.path.basename(rel)
            module = re.escape(name[:-3]) if name.endswith(".py") else None
            return name in text or bool(module and re.search(rf"^\s*(from {module} import|import {module}\b)", text,
                                                             re.MULTILINE))
        # GitHub reads .github/ by convention: nothing has to name those files
        orphans = [rel for rel in files
                   if rel not in SELF_EVIDENT and rel not in used and not fnmatch.fnmatch(rel, "tests/test_*.py")
                   and not rel.startswith(".github/")
                   and not any(other != rel and named(rel, text) for other, text in texts.items())]
        self.assertEqual(orphans, [])

    def test_the_package_table_names_every_file(self):
        with open(os.path.join(PACKAGE, "docs", "architecture.md"), encoding="utf-8") as f:
            table = f.read().split("## What's in the package", 1)[1].split("\n## ", 1)[0]
        names = {name for row in table.splitlines() if row.startswith("| `")
                 for name in re.findall(r"`([^`]+)`", row.split("|")[1])}
        missing = [rel for rel in publishable_files() if rel not in SELF_EVIDENT and rel not in names
                   and not any(name.endswith("/") and rel.startswith(name) for name in names)]
        self.assertEqual(missing, [])

class Credits(unittest.TestCase):
    """The author, princesshu, named with a link to the GitHub account wherever the project speaks for itself; the
    programs it builds on named as others' work; and each plugin carrying the license, so that a plugin taken on its
    own, or installed on a machine, keeps the author's name."""

    AUTHOR = "https://github.com/princesshu"

    def test_the_author_is_named_with_a_link(self):
        missing = [rel for rel in ("LICENSE", "README.md", "THIRD_PARTY_NOTICES.md", "CONTRIBUTING.md", "SECURITY.md")
                   if self.AUTHOR not in package_text(rel)]
        self.assertEqual(missing, [])

    def test_the_readme_tells_the_authors_work_from_the_programs_it_builds_on(self):
        readme = package_text("README.md")
        self.assertIn(f"[princesshu]({self.AUTHOR})", readme)
        self.assertIn("https://github.com/herdrdev/herdr", readme)

    def test_each_plugin_carries_the_license_and_names_its_author(self):
        license_text, problems = package_text("LICENSE"), []
        installed = listed("files.txt")[0], listed(os.path.join("remote", "files.txt"))[0]
        for plugin in sorted(os.listdir(os.path.join(PACKAGE, "src", "plugins"))):
            folder = os.path.join("src", "plugins", plugin)
            if not os.path.isfile(os.path.join(PACKAGE, folder, "herdr-plugin.toml")):
                continue
            own = os.path.join(folder, "LICENSE")
            if not os.path.isfile(os.path.join(PACKAGE, own)) or package_text(own) != license_text:
                problems.append(own + ": not the package's license")
            problems += [f"{own}: not installed by {name}" for name, files in zip(("files.txt", "remote"), installed)
                         if os.path.isfile(os.path.join(PACKAGE, own)) and own not in files]
            if self.AUTHOR not in package_text(os.path.join(folder, "README.md")):
                problems.append(os.path.join(folder, "README.md") + ": no author")
        self.assertEqual(problems, [])

    def test_every_install_carries_the_license_and_the_notices(self):
        # herdr-fold's own folder on a machine (the TUI's, a remote one's) and the Herdr app's mod, which the app keeps
        # in a folder of its own: each with the license and the notices of what it builds on (its icons' among them)
        problems = []
        for name, rows in (("files.txt", listed_rows("files.txt")), ("remote", listed_rows("remote/files.txt"))):
            for own in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
                if rows.get(own, ("", ""))[0] != f".config/herdr-fold/{own}" or rows[own][-1] != "both":
                    problems.append(f"{own}: not installed to .config/herdr-fold for both parts by {name}")
        mod = os.path.join("app", "mods", "herdr-fold")
        for own in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            path = os.path.join(mod, own)
            if not os.path.isfile(os.path.join(PACKAGE, path)) or package_text(path) != package_text(own):
                problems.append(f"{path}: not the package's {own}")
        if self.AUTHOR not in package_text(os.path.join(mod, "README.md")):
            problems.append(os.path.join(mod, "README.md") + ": no author")
        self.assertEqual(problems, [])

    def test_each_plugin_says_it_is_part_of_herdr_fold(self):
        # herdr's marketplace lists every manifest of the repository as a plugin of its own, by its name, linked to its
        # folder (its README): the id tells where it comes from, the name what it does (the card names the repository
        # above it), the README is titled with that name, and the tab layout, which needs the rest, says how it installs
        problems = []
        for plugin in sorted(os.listdir(os.path.join(PACKAGE, "src", "plugins"))):
            manifest = os.path.join("src", "plugins", plugin, "herdr-plugin.toml")
            if not os.path.isfile(os.path.join(PACKAGE, manifest)):
                continue
            head = package_text(manifest).split("\n[", 1)[0]                     # before its actions and panes
            top = dict(re.findall(r'^(id|name) = "(.*)"$', head, re.MULTILINE))
            if top.get("id") != "herdr-fold." + plugin:
                problems.append(f"{manifest}: id {top.get('id')}")
            if not top.get("name") or "herdr-fold" in top["name"]:
                problems.append(f"{manifest}: name {top.get('name')}")
            elif package_text(f"src/plugins/{plugin}/README.md").split("\n", 1)[0] != "# " + top["name"]:
                problems.append(f"{plugin}: its README's title is not its name, the one the marketplace shows")
        tab_layout = package_text(os.path.join("src", "plugins", "tab-layout", "herdr-plugin.toml"))
        if "herdr-fold's installer" not in tab_layout.split("\n[", 1)[0]:
            problems.append("tab-layout: its description does not name herdr-fold's installer")
        self.assertEqual(problems, [])

    def test_herdrs_marketplace_finds_four_plugins(self):
        # each manifest is a row on the repository's card, with what the index reads; the root's, the whole
        # environment, sorts first
        found = sorted(rel for rel in publishable_files() if os.path.basename(rel) == "herdr-plugin.toml")
        self.assertEqual(found, ["herdr-plugin.toml"] + [f"src/plugins/{plugin}/herdr-plugin.toml"
                                                          for plugin in ("sessions-view", "sidebar", "tab-layout")])
        for rel in found:
            head = package_text(rel).split("\n[", 1)[0]
            self.assertEqual([key for key in ("id", "name", "version", "min_herdr_version")
                              if not re.search(rf'^{key} = "[^"]+"$', head, re.MULTILINE)], [], rel)

    def test_the_whole_environment_offers_the_installer_on_a_mac(self):
        manifest = package_text("herdr-plugin.toml")
        head = manifest.split("\n[", 1)[0]
        self.assertEqual(dict(re.findall(r'^(id|name|version|min_herdr_version) = "(.*)"$', head, re.MULTILINE)),
                         {"id": "herdr-fold", "name": "Full Setup", "version": "0.3.0",
                          "min_herdr_version": "0.9.5"})
        self.assertIn('platforms = ["macos"]', head)
        self.assertIn("[[startup]]", manifest)
        self.assertIn('on = "pane.focused"', manifest)
        self.assertRegex(manifest, r'\[\[panes\]\]\nid = "install"\n(?:\w+ = .*\n)*placement = "tab"\n')
        for script in ("lib/offer_install.sh", "install.sh"):
            self.assertIn(f"$HERDR_PLUGIN_ROOT/{script}", manifest)
            self.assertTrue(os.path.isfile(os.path.join(PACKAGE, script)), script)

if __name__ == "__main__":
    unittest.main()
