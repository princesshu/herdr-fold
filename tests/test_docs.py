"""Keeps the docs true to the code: every question, switch, key, command, installed file, theme and plugin version is
documented, relative links resolve, and the house style holds (headings, numbering, italics, badges, README length).
"""
import glob
import os
import re
import sys
import unittest

from support import PACKAGE, SRC, catalog_text, publishable_files

sys.path.insert(0, os.path.join(SRC, "themes"))
import apply  # noqa: E402


def read(rel):
    with open(os.path.join(PACKAGE, rel), encoding="utf-8") as f:
        return f.read()


# what a script asks: `ask "$(t key …)" y|n`, `prompt "$(t key …)" [default]`, and `wanted <id> "$(t key)"` (a plugin
# question: yes, or the last answer); every script's questions are in the installation guide, uninstall.sh's in its own
QUESTION = re.compile(r'\b(ask|prompt|wanted [\w.-]+) "\$\(t ([a-z0-9_.]+)')
GUIDES = {"uninstall.sh": "docs/uninstall.md"}
SCRIPTS = sorted(rel for rel in publishable_files() if rel.endswith(".sh") and not rel.startswith("tests/"))
VALUE = "\0"                         # stands in for every %s value of a text


def questions():
    """(script, key, default) for every question: default "y" / "n", a literal value, or None (a computed one)."""
    found = []
    for rel in SCRIPTS:
        for line in read(rel).splitlines():
            for m in QUESTION.finditer(line):
                after = re.search(r'\)" ([\w-]+)(?=\s|$)', line[m.end():])
                default = "y" if m.group(1).startswith("wanted") else after.group(1) if after else None
                found.append((rel, m.group(2), default))
    return found


def asked(key):
    """A question as a code span of the guide: its fixed text, any %s value in between (no brackets or commas)."""
    text = catalog_text(key, *[VALUE] * 9).strip()
    return re.compile("`" + "[^`(),]*?".join(re.escape(p) for p in text.split(VALUE)) + "`")


class InstallerQuestions(unittest.TestCase):
    """Every question a script can ask is in its guide, word for word, with the default the code gives it."""

    def test_every_question_is_in_its_guide(self):
        missing = [f"{rel}: {key}" for rel, key, _ in questions()
                   if not asked(key).search(read(GUIDES.get(rel, "docs/installation.md")))]
        self.assertEqual(missing, [])

    def test_every_default_in_the_tables_is_the_codes(self):
        said = {"y": "yes", "n": "no"}
        wrong = []
        for rel, key, default in questions():
            rows = [row for row in read(GUIDES.get(rel, "docs/installation.md")).splitlines()
                    if row.startswith("| ") and any(asked(key).fullmatch(span) for span in re.findall(r"`[^`]+`", row))]
            if default and rows and not any(said.get(default, default) in row.split("|")[-2] for row in rows):
                wrong.append(f"{rel}: {key} defaults to {default}")
        self.assertEqual(wrong, [])


SWITCH = re.compile(r"\bHERDR_(?:FOLD|COMMIT)_[A-Z_]+\b")
# read by the code, but not for people: the installer's warning count between its parts, and its start already said yes
# to before it moved, a test switch, the token a running sidebar hands its new version, and what the sidebar hands a
# preview tab's shell
INTERNAL = {"HERDR_FOLD_WARNINGS", "HERDR_FOLD_STARTED", "HERDR_FOLD_UPDATE", "HERDR_FOLD_PLATFORM",
            "HERDR_FOLD_SIDEBAR_RESUME", "HERDR_FOLD_PYTHON", "HERDR_FOLD_PAGER", "HERDR_FOLD_SPEC_FILE",
            "HERDR_FOLD_PROGRAM"}


class Switches(unittest.TestCase):
    def test_every_switch_is_in_the_docs(self):
        used = set()
        for rel in publishable_files():
            if rel.startswith(("tests/", "docs/")) or rel.endswith((".md", ".png")):
                continue
            with open(os.path.join(PACKAGE, rel), "rb") as f:
                used |= set(SWITCH.findall(f.read().decode("utf-8", "replace")))
        documented = {s for page in glob.glob(os.path.join(PACKAGE, "docs", "*.md"))
                      for s in SWITCH.findall(read(os.path.relpath(page, PACKAGE)))}
        self.assertEqual(sorted(used - INTERNAL - documented), [])


MODS = {"super": "Cmd", "shift": "Shift", "alt": "Option", "ctrl": "Ctrl"}
ARROWS = {"up": "↑", "down": "↓", "left": "←", "right": "→"}


def spoken(chord):
    """A chord as the docs write it: super+shift+c → Cmd + Shift + C, prefix+m → Ctrl + B, then M."""
    if chord.startswith("prefix+"):
        return "Ctrl + B, then " + spoken(chord[len("prefix+"):])
    keys = chord.split("+")
    return " + ".join(MODS.get(k) or ARROWS.get(k) or (k.upper() if len(k) == 1 else k.capitalize()) for k in keys)


KEYBIND = re.compile(r"^keybind = (?:performable:)?([^=]+)=(.*)$", re.M)
CSI = {"A": "up", "B": "down", "C": "right", "D": "left"}


def sent(action):
    """The herdr chord a Ghostty `text:` action sends: \x02x → prefix+x, \x02X → prefix+shift+x, ESC [1;<mods><arrow> →
    ctrl+alt+shift+…"""
    prefix = re.fullmatch(r"text:\\x02([A-Za-z])", action)
    if prefix:
        letter = prefix.group(1)
        return "prefix+" + ("shift+" + letter.lower() if letter.isupper() else letter)
    arrow = re.fullmatch(r"text:\\x02\\x1b\[([ABCDZ])", action)         # \x02 ESC [ B → prefix+down
    if arrow:
        return "prefix+" + ("shift+tab" if arrow.group(1) == "Z" else CSI[arrow.group(1)])
    if action == r"text:\x02\t":
        return "prefix+tab"
    csi = re.fullmatch(r"text:\\x1b\[1;(\d)([ABCD])", action)
    if csi:
        bits = int(csi.group(1)) - 1
        mods = [m for m, bit in (("ctrl", 4), ("alt", 2), ("shift", 1)) if bits & bit]
        return "+".join(mods + [CSI[csi.group(2)]])
    return None


def ghostty_keys():
    """The Cmd keys of the package's Ghostty settings, as the docs write them; Cmd + 1…9 as one row."""
    keys = set()
    for chord, _ in KEYBIND.findall(read("config/ghostty/config")):
        if not chord.startswith("super+"):
            continue
        if re.fullmatch(r"super\+(?:digit_)?[1-9]", chord):
            keys.add("Cmd + 1…9")
        else:
            keys.add(", then ".join(spoken(step) for step in chord.split(">")))
    return keys


def herdr_keys():
    """herdr-fold's herdr keys that no Cmd key of Ghostty sends: the [[keys.command]] keys and the [keys] chords."""
    from_ghostty = {sent(action) for _, action in KEYBIND.findall(read("config/ghostty/config"))}
    config = read("config/herdr/config.toml")
    chords = [m for block in config.split("[[keys.command]]")[1:]
              for m in re.findall(r'^key = "([^"]+)"', block.split("\n[")[0], re.M)]
    table = config.split("\n[keys]\n", 1)[1].split("\n[", 1)[0]
    chords += [c for value in re.findall(r"^\w+ = \[([^\]]*)\]", table, re.M) for c in re.findall(r'"([^"]+)"', value)]
    return {spoken(chord) for chord in chords if chord not in from_ghostty}


def key_cells(text):
    """The keys of the reference's tables (first column, each of "A / B" alone), apart from "Without Ghostty"."""
    before, _, after = text.partition("\n## Without Ghostty\n")
    after = after[after.find("\n## "):] if "\n## " in after else ""
    return {key.strip() for row in (before + after).splitlines() if row.startswith("| ") and not row.startswith("| Key")
            for key in row.split("|")[1].split(" / ")}


class Keys(unittest.TestCase):
    def test_every_cmd_key_has_its_own_row(self):
        self.assertEqual(sorted(ghostty_keys() - key_cells(read("docs/keybindings.md"))), [])

    def test_every_herdr_key_herdr_fold_binds_is_in_the_reference(self):
        reference = read("docs/keybindings.md")
        self.assertEqual(sorted(k for k in herdr_keys() if not re.search(r"(?<![\w+])" + re.escape(k) + r"(?!\w)",
                                                                         reference)), [])

    def test_cmd_arrows_step_the_workspaces_and_the_panes(self):
        # herdr's own, two keys each: previous / next workspace, previous / next pane of the tab; both wrap around.
        # Not Ctrl+Tab: a Tab still held once Ctrl is up runs the shell's completion
        bound = dict(KEYBIND.findall(read("config/ghostty/config")))
        self.assertEqual([sent(bound[chord]) for chord in ("super+up", "super+down", "super+left", "super+right")],
                         ["prefix+up", "prefix+down", "prefix+shift+tab", "prefix+tab"])
        self.assertNotIn("ctrl+tab", bound)
        self.assertNotIn("ctrl+shift+tab", bound)

    def test_chords_are_spoken_the_way_the_docs_write_them(self):
        self.assertEqual(spoken("super+shift+c"), "Cmd + Shift + C")
        self.assertEqual(spoken("prefix+shift+m"), "Ctrl + B, then Shift + M")
        self.assertEqual(sent(r"text:\x1b[1;8B"), "ctrl+alt+shift+down")
        self.assertEqual((sent(r"text:\x02u"), sent(r"text:\x02I")), ("prefix+u", "prefix+shift+i"))
        self.assertEqual(sent(r"text:\x02\x1b[B"), "prefix+down")
        self.assertEqual((sent(r"text:\x02\t"), sent(r"text:\x02\x1b[Z")), ("prefix+tab", "prefix+shift+tab"))


# herdr's own agent states, the words AI Sessions shows: the package does not rename them
HERDR_STATES = ["working", "blocked", "done", "idle"]


class Sessions(unittest.TestCase):
    def test_the_guide_names_herdrs_states(self):
        text = read("docs/usage.md").split("\n## Sessions\n", 1)[1].split("\n## ", 1)[0]
        self.assertEqual([s for s in HERDR_STATES if not re.search(rf"\b{s}\b", text)], [])


# Where the installer writes on this Mac besides files.txt: every such place is in "What changes on your Mac"
WRITERS = ["install.sh", "lib/common.sh", "src/claude_trust.py"]
HOME_PATH = re.compile(r'(?:\$HOME|~)/(\.[\w.-]+(?:/[\w.-]+)*)|expanduser\("~/(\.[\w.-]+(?:/[\w.-]+)*)')
INSTALLER_FOLDERS = (".config/herdr-fold", ".local/state/herdr-fold")


class Changes(unittest.TestCase):
    def test_every_place_the_installer_writes_is_listed(self):
        section = read("docs/installation.md").split("## What changes on your Mac", 1)[1].split("\n## ", 1)[0]
        places = {path.rstrip(".") for rel in WRITERS for m in HOME_PATH.findall(read(rel)) for path in m if path}
        self.assertEqual(sorted(p for p in places
                                if not p.startswith(INSTALLER_FOLDERS) and "~/" + p not in section), [])


def installed():
    """Every path files.txt and remote/files.txt put on a machine, relative to its home folder."""
    found = set()
    for listing in ("files.txt", "remote/files.txt"):
        for line in read(listing).splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            src, dest = (p.strip() for p in line.split("|")[:2])      # remote/files.txt adds the platforms
            for f in glob.glob(os.path.join(PACKAGE, src)):
                found.add(dest + os.path.basename(f) if dest.endswith("/") else dest)
    return found


PAGES = ["README.md"] + sorted(os.path.relpath(p, PACKAGE) for p in glob.glob(os.path.join(PACKAGE, "docs", "*.md")))
INSTALLED = re.compile(r"~/(\.config/herdr-fold/[\w./-]+\.(?:py|sh|html))")
SCRIPT = re.compile(r"(?<![\w/~.])\./((?:tools/)?[\w-]+\.(?:sh|command))\b")
MACHINES = re.compile(r"\./machines\.sh ([a-z]+)")


class Commands(unittest.TestCase):
    """What a page tells someone to run exists: the installed files, the package's scripts, machines.sh's commands."""

    def test_every_installed_file_named_exists(self):
        targets = installed()
        self.assertEqual([f"{page}: ~/{rel}" for page in PAGES for rel in INSTALLED.findall(read(page))
                          if rel not in targets], [])

    def test_every_script_named_exists(self):
        self.assertEqual([f"{page}: ./{rel}" for page in PAGES for rel in SCRIPT.findall(read(page))
                          if not os.path.isfile(os.path.join(PACKAGE, rel))], [])

    def test_every_machines_command_exists(self):
        commands = {c for alts in re.findall(r"^  ([\w|-]+)\)", read("machines.sh"), re.M) for c in alts.split("|")}
        self.assertEqual([f"{page}: {c}" for page in PAGES for c in MACHINES.findall(read(page))
                          if c not in commands], [])


MARKDOWN = sorted(rel for rel in publishable_files() if rel.endswith(".md"))
CODE_BLOCK = re.compile(r"```.*?```", re.S)
CODE = re.compile(r"```.*?```|`[^`\n]+`", re.S)
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50]")
NUMBERED = re.compile(r"^\s*0\d[.)]\s", re.M)
ITALIC = re.compile(r"(?<![*\w\\])\*(?![*\s])[^*\n]+?(?<![*\s])\*(?![*\w])"      # *word*, not **bold** or a bullet
                    r"|(?<![\w\\])_(?![_\s])[^_\n]+?(?<![_\s])_(?!\w)")              # _word_, not snake_case
BADGE = re.compile(r"!\[[^\]]*\]\(\s*https://img\.shields\.io/")
COMPARED = re.compile(r"VS\s+Code[-\s]+(?:like|style)|like\s+(?:in\s+)?(?:the\s+)?VS\s+Code", re.I)


def prose(text):
    return CODE.sub("", text)


class Style(unittest.TestCase):
    def test_house_style(self):
        problems = []
        for rel in MARKDOWN:
            body = prose(read(rel))
            problems += [f"{rel}: emoji in a heading or as a bullet: {line}" for line in body.splitlines()
                         if re.match(r"\s*(#{1,6} |[-*] )", line) and EMOJI.search(line)]
            problems += [f"{rel}: 01/02/03 numbering" for _ in NUMBERED.findall(body)]
            problems += [f"{rel}: italics: {m}" for m in ITALIC.findall(body)]
        if len(BADGE.findall(read("README.md"))) > 3:
            problems.append("README.md: more than three badges")
        self.assertEqual(problems, [])

    def test_nothing_is_compared_to_vs_code(self):
        """The package stands on its own: no "VS Code-like" anywhere, in the docs, the settings or the comments."""
        found = []
        for rel in publishable_files():
            if rel == "tests/test_docs.py":
                continue
            with open(os.path.join(PACKAGE, rel), "rb") as f:
                text = f.read().decode("utf-8", "replace")
            found += [f"{rel}: {m}" for m in COMPARED.findall(text)]
        self.assertEqual(found, [])

    def test_the_readme_is_a_front_page(self):
        self.assertLessEqual(len(read("README.md").splitlines()), 200)


LINK = re.compile(r"\]\(([^)\s]+)\)")


def slug(heading):
    """GitHub's anchor for a heading: lowercase, punctuation out (hyphens and underscores stay), spaces to hyphens."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def anchors(rel):
    return {slug(h) for h in re.findall(r"^#{1,6} (.+)$", CODE_BLOCK.sub("", read(rel)), re.M)}


class Links(unittest.TestCase):
    def test_every_relative_link_resolves(self):
        broken = []
        for rel in MARKDOWN:
            for target in LINK.findall(CODE_BLOCK.sub("", read(rel))):
                if re.match(r"[a-z]+:", target):
                    continue                                       # https:, mailto:
                path, _, anchor = target.partition("#")
                dest = os.path.normpath(os.path.join(os.path.dirname(rel), path)) if path else rel
                if not os.path.exists(os.path.join(PACKAGE, dest)):
                    broken.append(f"{rel}: {target}")
                elif anchor and dest.endswith(".md") and anchor not in anchors(dest):
                    broken.append(f"{rel}: {target} (no such heading)")
        self.assertEqual(broken, [])

    def test_a_heading_becomes_githubs_anchor(self):
        self.assertEqual(slug("What changes on your Mac"), "what-changes-on-your-mac")
        self.assertEqual(slug("Commit and push"), "commit-and-push")


class Notices(unittest.TestCase):
    def test_every_theme_names_its_source(self):
        notices = read("THIRD_PARTY_NOTICES.md")
        self.assertEqual([t["name"] for t in apply.load_themes() if t["name"] not in notices], [])

    def test_the_license_is_mit(self):
        self.assertTrue(read("LICENSE").startswith(
            "MIT License\n\nCopyright (c) 2026 princesshu (https://github.com/princesshu)\n"))


def manifests():
    """Each plugin of the package: its manifest's id, version, min_herdr_version and name, and its folder."""
    for path in sorted(glob.glob(os.path.join(PACKAGE, "src", "plugins", "*", "herdr-plugin.toml"))):
        folder = os.path.relpath(os.path.dirname(path), PACKAGE)
        text = read(os.path.join(folder, "herdr-plugin.toml"))
        plugin = {key: re.search(rf'^{key} = "([^"]+)"', text, re.M).group(1)
                  for key in ("id", "version", "min_herdr_version", "name")}
        yield {**plugin, "folder": folder}


class Changelog(unittest.TestCase):
    def test_every_plugin_version_is_in_the_changelog(self):
        changelog = read("CHANGELOG.md")
        listed = [f"{p['id']} {p['version']}" for p in manifests()]
        self.assertEqual([entry for entry in listed if entry not in changelog], [])

    def test_the_whole_environment_is_in_the_changelog(self):
        root = read("herdr-plugin.toml")
        entry = " ".join(re.search(rf'^{key} = "([^"]+)"', root, re.M).group(1) for key in ("id", "version"))
        self.assertIn(f"`{entry}`", read("CHANGELOG.md"))


class PluginReadmes(unittest.TestCase):
    """Each plugin can be read on its own (the herdr plugin listing shows its folder): its name and the herdr
    it needs."""

    def test_every_plugin_has_its_own_readme(self):
        problems = []
        for plugin in manifests():
            readme = os.path.join(plugin["folder"], "README.md")
            if not os.path.exists(os.path.join(PACKAGE, readme)):
                problems.append(f"{plugin['folder']}: no README.md")
            elif (not read(readme).startswith(f"# {plugin['name']}\n")
                  or plugin["min_herdr_version"] not in read(readme)):
                problems.append(f"{readme}: its title is not {plugin['name']!r}, or it does not name herdr "
                                f"{plugin['min_herdr_version']}")
        self.assertEqual(problems, [])


class Pictures(unittest.TestCase):
    """herdr's marketplace links each plugin's row to its folder: a plugin that installs alone shows itself there, and
    the README's list of what you get shows the sidebar."""

    def test_a_plugin_installed_alone_shows_itself(self):
        for plugin in ("sidebar", "sessions-view"):
            pictures = re.findall(r"\]\((\.\./\.\./\.\./docs/media/[\w-]+\.webp)\)",
                                  read(f"src/plugins/{plugin}/README.md"))
            self.assertTrue(pictures, plugin)
            for rel in pictures:
                path = os.path.normpath(os.path.join(PACKAGE, "src", "plugins", plugin, rel))
                self.assertTrue(os.path.isfile(path), rel)

    def test_the_readmes_list_shows_the_sidebar(self):
        what_you_get = read("README.md").split("## What you get", 1)[1].split("\n## ", 1)[0]
        self.assertIn("(docs/media/sidebar.webp)", what_you_get)

    def test_the_readme_opens_with_the_logo_and_says_it_is_the_sheep(self):
        # under the title: above it, GitHub's rule below the title would run through the logo
        readme = read("README.md")
        logo = re.match(r'# herdr-fold\n\n<img src="(src/themes/logo\.svg)" alt="herdr-fold\'s logo[^"]*" width="\d+" '
                        r'align="right">\n', readme)
        self.assertIsNotNone(logo, readme[:200])
        self.assertTrue(os.path.isfile(os.path.join(PACKAGE, logo.group(1))))
        what_you_get = readme.split("## What you get", 1)[1].split("\n## ", 1)[0]
        self.assertIn("herdr-fold's logo, the sheep", what_you_get)


class Templates(unittest.TestCase):
    def test_a_bug_report_asks_for_secrets_to_be_removed_first(self):
        form = read(".github/ISSUE_TEMPLATE/bug_report.yml")
        self.assertIn("type: checkboxes", form)
        checkbox = form.split("type: checkboxes", 1)[1]
        self.assertIn("required: true", checkbox)
        self.assertIn("I removed", checkbox)                 # keys, tokens, machine names, addresses, conversations

    def test_every_issue_form_asks_that_a_person_wrote_it(self):
        # one written by an AI tool, or naming one as its author or co-author, is deleted (CONTRIBUTING.md)
        for name in ("bug_report.yml", "feature_request.yml"):
            form = read(f".github/ISSUE_TEMPLATE/{name}")
            checks = form.split("type: checkboxes", 1)[1] if "type: checkboxes" in form else ""
            self.assertIn("I wrote this myself", checks, name)
            self.assertEqual(checks.count("- label:"), checks.count("required: true"), name)
        self.assertIn("written by an AI tool", read("CONTRIBUTING.md"))

    def test_blank_issues_point_to_the_forms_and_security_reports_stay_private(self):
        config = read(".github/ISSUE_TEMPLATE/config.yml")
        self.assertIn("blank_issues_enabled: false", config)
        self.assertIn("/security/advisories/new", config)


if __name__ == "__main__":
    unittest.main()
