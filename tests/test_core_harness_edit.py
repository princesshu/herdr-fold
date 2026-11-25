"""Tests for core/harness_edit.py in a temporary home and folder: an edit made at its one key with every other key, the
order and the indentation kept, a stale one refused, the edit that takes it back restoring the file byte for byte, the
keys and the files never changed, a layer's one file, config.toml's lines changed and the shapes refused."""
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

from support import PACKAGE, set_env

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import agent_setup    # noqa: E402
import harness_edit    # noqa: E402

MODE = ["permissions", "defaultMode"]
ALLOW, DENY = ["permissions", "allow"], ["permissions", "deny"]
CONFIG = ('# Codex\nmodel = "gpt-5.2-codex"   # the default\nmodel_reasoning_effort = \'high\'\n\n'
          '[projects."/Users/dev/lumen-api"]\ntrust_level = "trusted"\n\n[mcp_servers.docs]\ncommand = "docs-mcp"\n')


class Files(unittest.TestCase):
    def setUp(self):
        top = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, top)
        self.home = os.path.join(top, "home")
        self.folder = os.path.join(top, "work", "lumen-api")
        self.managed = os.path.join(top, "managed")     # the organization's folder, never this machine's own
        os.makedirs(self.folder)
        patch = mock.patch.object(agent_setup, "MANAGED_DIR", self.managed)
        patch.start()
        self.addCleanup(patch.stop)
        set_env(self, CODEX_HOME=None)
        self.user = os.path.join(self.home, ".claude", "settings.json")
        self.project = os.path.join(self.folder, ".claude", "settings.json")
        self.local = os.path.join(self.folder, ".claude", "settings.local.json")
        self.config = os.path.join(self.home, ".codex", "config.toml")

    def put(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return path

    def text(self, path):
        with open(path, encoding="utf-8", newline="") as f:
            return f.read()

    def apply(self, *edits, agent="claude"):
        return harness_edit.apply(agent, self.folder, self.home, list(edits))

    def files(self):
        found = {}
        for base in (self.home, self.folder, self.managed):
            for here, _, names in os.walk(base):
                found.update({os.path.join(here, name): self.text(os.path.join(here, name)) for name in names})
        return found


class Places(Files):
    def test_a_layers_name_gives_the_agents_own_file_and_no_other(self):
        place = lambda agent, layer: harness_edit.place(agent, layer, self.folder, self.home)   # noqa: E731
        self.assertEqual([place("claude", layer) for layer in ("Global", "Project", "Local")],
                         [path for path, _ in agent_setup.settings(self.folder, self.home)[:3]])
        self.assertEqual(place("claude", "Local"), os.path.join(self.folder, ".claude", "settings.local.json"))
        self.assertEqual([place("codex", layer) for layer in ("Global", "Project")],
                         [os.path.join(self.home, ".codex", "config.toml"),
                          os.path.join(self.folder, ".codex", "config.toml")])
        for agent, layer in (("claude", "Managed"), ("claude", "Built-in"), ("codex", "Local"), ("claude", None),
                             ("claude", os.path.join(self.home, ".claude.json")), ("claude", "../../.claude.json"),
                             ("gemini", "Global")):
            with self.assertRaises(ValueError):
                place(agent, layer)
        with self.assertRaises(ValueError):
            harness_edit.place("claude", "Project", "lumen-api", self.home)    # a folder by its whole path alone

    def test_a_file_is_read_as_it_is_and_a_link_never_followed(self):
        path = os.path.join(self.folder, ".claude", "settings.json")
        os.makedirs(os.path.dirname(path))
        self.assertEqual(harness_edit.text_of(path), "")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("{}\r\n")
        self.assertEqual(harness_edit.text_of(path), "{}\r\n")
        link = os.path.join(self.folder, ".claude", "settings.local.json")
        os.symlink(path, link)
        os.symlink(os.path.join(self.folder, ".claude"), os.path.join(self.folder, ".codex"))
        os.mkdir(os.path.join(self.folder, "config.toml"))
        with open(os.path.join(self.folder, ".claude", "latin.json"), "wb") as f:
            f.write(b'{"a": "\xe9"}')
        for one, why in ((link, harness_edit.LINK), (os.path.join(self.folder, ".codex", "config.toml"),
                                                      harness_edit.LINK),
                         (os.path.join(self.folder, "config.toml"), harness_edit.NOT_EDITED),
                         (os.path.join(self.folder, ".claude", "latin.json"), harness_edit.NOT_EDITED)):
            with self.assertRaises(harness_edit.Refused) as refused:
                harness_edit.text_of(one)
            self.assertEqual(refused.exception.args[0], why)

    def test_a_settings_file_is_read_strictly(self):
        self.assertEqual(harness_edit.load(""), {})
        self.assertEqual(list(harness_edit.load('{"b": 1, "a": {"d": 1, "c": 2}}')["a"]), ["d", "c"])
        for text in ("[]", "{", '{"a": 1, "a": 2}', '{"a": {"b": 1, "b": 1}}', '{"a": Infinity}', "null"):
            with self.assertRaises(harness_edit.Refused, msg=text):
                harness_edit.load(text)

    def test_a_top_level_key_is_found_by_its_line(self):
        text = 'model = "gpt-5.2"  # mine\nnotify = [\n  "x",\n]\n\n[tui]\nmodel = "another"\n'
        mine, keys = harness_edit.toml_find(text, "model")
        self.assertEqual((mine["line"], mine["plain"].group(2), [(one["line"], one["last"]) for one in keys]),
                         (0, "gpt-5.2", [(0, 0), (1, 3)]))
        self.assertEqual(harness_edit.toml_find(text, "sandbox_mode")[0], None)
        for shape in ("[model]\na = 1\n", 'model.name = "gpt-5.2"\n', 'model = { name = "gpt-5.2" }\n',
                      'model = "a"\nmodel = "b"\n', 'model = """\ngpt\n"""\n', "no toml\n"):
            with self.assertRaises(harness_edit.Refused, msg=shape):
                harness_edit.toml_find(shape, "model")


    def test_an_edit_names_a_layer_never_a_path(self):
        self.put(os.path.join(self.home, ".claude.json"), "{}")
        before = self.files()
        for edit in ({"layer": os.path.join(self.home, ".claude.json"), "key": MODE, "before": None, "after": "plan"},
                     {"layer": "Managed", "key": MODE, "before": None, "after": "plan"},
                     {"path": self.user, "key": MODE, "before": None, "after": "plan"}):
            with self.assertRaises(ValueError):
                self.apply(edit)
        self.assertEqual(self.files(), before)

    def test_a_link_is_never_followed(self):
        target = self.put(os.path.join(self.home, "dotfiles", "settings.json"), "{}")
        os.makedirs(os.path.dirname(self.user))
        os.symlink(target, self.user)
        os.symlink(os.path.join(self.home, "dotfiles"), os.path.join(self.folder, ".claude"))
        for layer, said in (("Global", "~/.claude/settings.json"), ("Project", ".claude/settings.json")):
            made = self.apply({"layer": layer, "key": MODE, "before": None, "after": "plan"})
            self.assertEqual(made, {"applied": False, "undo": [],
                                    "error": f"{said} is a link: change it where it lives"})
        self.assertEqual(self.text(target), "{}")
        self.assertTrue(os.path.islink(self.user))


class Settings(Files):
    def test_one_key_changes_and_every_other_stays_in_its_place(self):
        was = {"zeta": {"deep": [1, 2.5, None, {"k": True}]}, "permissions": {"future": "kept", "allow": ["Read"]},
               "model": "opus", "unknownKey": "é"}
        self.put(self.project, json.dumps(was, indent=2, ensure_ascii=False))
        made = self.apply({"layer": "Project", "key": MODE, "before": None, "after": "acceptEdits"})
        self.assertTrue(made["applied"])
        now = json.loads(self.text(self.project))
        self.assertEqual(now, {**was, "permissions": {**was["permissions"], "defaultMode": "acceptEdits"}})
        self.assertEqual(list(now), list(was))
        self.assertEqual(list(now["permissions"]), ["future", "allow", "defaultMode"])
        self.assertIn('"unknownKey": "é"', self.text(self.project))

    def test_the_files_indentation_and_ends_are_kept(self):
        for indent, end, newline in ((4, "\n", "\n"), ("\t", "", "\n"), (2, "\r\n", "\r\n"), (None, "\n", "\n")):
            text = json.dumps({"model": "opus", "permissions": {"allow": ["Read"]}}, indent=indent)
            self.put(self.project, text.replace("\n", newline) + end)
            self.apply({"layer": "Project", "key": ["model"], "before": "opus", "after": "sonnet"})
            self.assertEqual(self.text(self.project), text.replace("opus", "sonnet").replace("\n", newline) + end)

    def test_a_new_file_is_claudes_own_shape(self):
        made = self.apply({"layer": "Local", "key": ["skillOverrides", "release-notes"], "before": None,
                           "after": "off"})
        self.assertEqual(self.text(self.local), '{\n  "skillOverrides": {\n    "release-notes": "off"\n  }\n}\n')
        self.assertTrue(self.apply(*made["undo"])["applied"])
        self.assertFalse(os.path.exists(self.local))                # the file it made goes with the undo
        with open(self.local, "w", encoding="utf-8") as f:          # one that was there stays, emptied or not
            f.write("{}\n")
        self.apply(*self.apply({"layer": "Local", "key": ["skillOverrides", "release-notes"], "before": None,
                                "after": "off"})["undo"])
        self.assertEqual(self.text(self.local), "{}\n")

    def test_a_stale_edit_is_refused_and_nothing_is_written(self):
        self.put(self.project, json.dumps({"model": "haiku", "permissions": {"allow": ["Read"], "deny": ["Bash"]}}))
        self.put(self.local, "{}")
        before = self.files()
        for edit in ({"layer": "Project", "key": ["model"], "before": "opus", "after": "sonnet"},
                     {"layer": "Project", "key": ["model"], "before": None, "after": "sonnet"},
                     {"layer": "Local", "key": ["model"], "before": "opus", "after": None},
                     {"layer": "Project", "key": ALLOW, "remove": "Bash(curl:*)"},
                     {"layer": "Project", "key": ALLOW, "add": "Read"},
                     {"layer": "Project", "key": DENY, "remove": "Bash", "add": "Bash"}):
            made = self.apply(edit)
            self.assertFalse(made["applied"], edit)
            self.assertRegex(made["error"], r"^\.claude/settings(\.local)?\.json changed since: nothing saved$")
        self.assertEqual(self.files(), before)

    def test_the_edit_that_takes_one_back_restores_the_file_byte_for_byte(self):
        text = json.dumps({"model": "opus", "permissions": {"allow": ["Read", "Bash(pytest:*)", "Edit"], "deny": []},
                           "sandbox": {"enabled": True}, "last": 1}, indent=2) + "\n"
        for edit in ({"key": ["model"], "before": "opus", "after": "sonnet"},
                     {"key": ["model"], "before": "opus", "after": None},
                     {"key": ["effortLevel"], "before": None, "after": "high"},
                     {"key": MODE, "before": None, "after": "plan"},
                     {"key": ["skillOverrides", "changelog"], "before": None, "after": "off"},
                     {"key": ["sandbox", "enabled"], "before": True, "after": None},
                     {"key": ALLOW, "remove": "Bash(pytest:*)"},
                     {"key": ALLOW, "remove": "Read", "add": "Read(./docs/**)"},
                     {"key": ALLOW, "add": "Bash(npm run test:*)"},
                     {"key": DENY, "add": "Agent(doc-checker)"},
                     {"key": ["permissions", "ask"], "add": "Bash(curl:*)"},
                     {"key": ["sandbox", "network", "allowedDomains"], "add": "pypi.org"},
                     {"key": ["deniedMcpServers"], "add": {"serverName": "github"}},
                     {"key": ["disableAllHooks"], "before": None, "after": True}):
            self.put(self.project, text)
            made = self.apply({"layer": "Project", **edit})
            self.assertTrue(made["applied"], edit)
            self.assertNotEqual(self.text(self.project), text, edit)
            self.assertEqual(self.apply(*made["undo"]), {"applied": True, "error": None, "undo": mock.ANY}, edit)
            self.assertEqual(self.text(self.project), text, edit)

    def test_a_rule_taken_back_leaves_what_was_added_since(self):
        self.put(self.project, "{}")
        made = self.apply({"layer": "Project", "key": ALLOW, "add": "Bash(pytest:*)"})
        self.put(self.project, json.dumps({"permissions": {"allow": ["Bash(pytest:*)", "Read"]}}))
        self.assertTrue(self.apply(*made["undo"])["applied"])
        self.assertEqual(json.loads(self.text(self.project)), {"permissions": {"allow": ["Read"]}})

    def test_a_list_keeps_its_order(self):
        self.put(self.project, json.dumps({"permissions": {"allow": ["a", "b", "c"]}}))
        self.apply({"layer": "Project", "key": ALLOW, "remove": "b", "add": "B"})
        self.apply({"layer": "Project", "key": ALLOW, "add": "d"})
        made = self.apply({"layer": "Project", "key": ALLOW, "remove": "a"})
        self.assertEqual(json.loads(self.text(self.project))["permissions"]["allow"], ["B", "c", "d"])
        self.apply(*made["undo"])
        self.assertEqual(json.loads(self.text(self.project))["permissions"]["allow"], ["a", "B", "c", "d"])

    def test_only_the_keys_herdr_fold_changes_are_ever_written(self):
        self.put(self.project, json.dumps({"hooks": {}, "env": {"A": "b"}, "permissions": {"allow": []}}))
        before = self.files()
        for edit in ({"key": ["hooks"], "before": {}, "after": None},
                     {"key": ["hooks", "PreToolUse"], "add": {"hooks": [{"type": "command", "command": "id"}]}},
                     {"key": ["env", "A"], "before": "b", "after": "c"},
                     {"key": ["permissions"], "before": {"allow": []}, "after": None},
                     {"key": ["apiKeyHelper"], "before": None, "after": "id"},
                     {"key": MODE, "before": None, "after": "everything"},
                     {"key": MODE, "before": None, "after": ["plan"]},
                     {"key": ["sandbox", "enabled"], "before": None, "after": 1},
                     {"key": ["disableAllHooks"], "before": None, "after": False},
                     {"key": ["skillOverrides", "changelog"], "before": None, "after": "on"},
                     {"key": ["model"], "before": None, "after": "opus\nmore"},
                     {"key": ALLOW, "add": "Bash(\x1b[0m)"},
                     {"key": ALLOW, "add": 5},
                     {"key": ALLOW},
                     {"key": ALLOW, "add": "Read", "at": -1},
                     {"key": ["deniedMcpServers"], "add": {"serverName": "github", "serverUrl": "*"}},
                     {"key": ["model"], "before": "opus", "after": "opus"},
                     {"key": [], "before": None, "after": "opus"},
                     {"key": "model", "before": None, "after": "opus"}):
            with self.assertRaises(ValueError, msg=edit):
                self.apply({"layer": "Project", **edit})
        for edits in ([], None, "model", [None]):
            with self.assertRaises(ValueError):
                harness_edit.apply("claude", self.folder, self.home, edits)
        self.assertEqual(self.files(), before)

    def test_a_file_that_is_no_settings_object_is_left_alone(self):
        edit = {"layer": "Project", "key": ALLOW, "add": "Read"}
        for text in ("[1]", "{", '{"a": 1, "a": 2}', '{"permissions": []}', '{"permissions": {"allow": "Read"}}',
                     '{"a": NaN}', "// mine\n{}"):
            self.put(self.project, text)
            self.assertEqual(self.apply(edit)["error"], ".claude/settings.json is not written in a way herdr-fold "
                             "changes: change it in the file", text)
            self.assertEqual(self.text(self.project), text)

    def test_edits_of_two_files_are_made_together_or_not_at_all(self):
        self.put(self.project, json.dumps({"permissions": {"allow": ["Bash(pytest:*)"]}}, indent=2))
        move = [{"layer": "Project", "key": ALLOW, "remove": "Bash(pytest:*)"},
                {"layer": "Local", "key": ALLOW, "add": "Bash(python -m pytest:*)"}]
        self.put(self.local, json.dumps({"permissions": {"allow": ["Bash(python -m pytest:*)"]}}))
        before = self.files()
        self.assertFalse(self.apply(*move)["applied"])
        self.assertEqual(self.files(), before)
        os.unlink(self.local)
        with mock.patch.object(harness_edit, "put", side_effect=[None, OSError("full"), None]):
            self.assertEqual(self.apply(*move), {"applied": False, "undo": [],
                                                 "error": "Couldn't write .claude/settings.local.json"})
        made = self.apply(*move)
        self.assertEqual(json.loads(self.text(self.project)), {"permissions": {"allow": []}})
        self.assertEqual(json.loads(self.text(self.local)), {"permissions": {"allow": ["Bash(python -m pytest:*)"]}})
        self.assertEqual([one["layer"] for one in made["undo"]], ["Local", "Project"])
        self.apply(*made["undo"])
        self.assertEqual(self.text(self.project), before[self.project])
        self.assertFalse(os.path.exists(self.local))                # made by the move: gone with its undo

    def test_a_file_written_before_one_that_failed_is_put_back(self):
        self.put(self.project, '{"permissions": {"allow": ["Read"]}}')
        real, calls = harness_edit.put, []

        def failing(path, text):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("full")
            real(path, text)
        with mock.patch.object(harness_edit, "put", failing):
            made = self.apply({"layer": "Project", "key": ALLOW, "remove": "Read"},
                              {"layer": "Local", "key": ALLOW, "add": "Read"})
        self.assertFalse(made["applied"])
        self.assertEqual(self.text(self.project), '{"permissions": {"allow": ["Read"]}}')
        self.assertFalse(os.path.exists(self.local))

    @unittest.skipIf(os.name == "nt", "a file's mode is POSIX's")
    def test_the_files_mode_is_kept_and_no_temporary_file_is_left(self):
        self.put(self.project, "{}")
        os.chmod(self.project, 0o640)
        self.apply({"layer": "Project", "key": ["model"], "before": None, "after": "opus"})
        self.assertEqual(stat.S_IMODE(os.stat(self.project).st_mode), 0o640)
        self.assertEqual(os.listdir(os.path.dirname(self.project)), ["settings.json"])


class Config(Files):
    def edit(self, text, key, before, after):
        return harness_edit.toml_edit(text, {"key": [key], "before": before, "after": after})

    def test_a_values_line_keeps_its_spacing_its_quotes_and_its_comment(self):
        made, back = self.edit(CONFIG, "model", "gpt-5.2-codex", "gpt-5.2")
        self.assertEqual(made, CONFIG.replace('"gpt-5.2-codex"   # the default', '"gpt-5.2"   # the default'))
        self.assertEqual(harness_edit.toml_edit(made, back)[0], CONFIG)
        made, back = self.edit(CONFIG, "model_reasoning_effort", "high", "xhigh")
        self.assertEqual(made, CONFIG.replace("'high'", "'xhigh'"))
        self.assertEqual(harness_edit.toml_edit(made, back)[0], CONFIG)
        made, back = self.edit(' "model"="gpt-5.2"\r\n', "model", "gpt-5.2", "gpt-5.1-codex")
        self.assertEqual(made, ' "model"="gpt-5.1-codex"\r\n')

    def test_a_new_key_goes_under_the_last_top_level_one_and_comes_out_again(self):
        for text, made in ((CONFIG, CONFIG.replace("'high'\n", "'high'\nsandbox_mode = \"read-only\"\n")),
                           ('[tui]\nnotifications = true\n',
                            'sandbox_mode = "read-only"\n[tui]\nnotifications = true\n'),
                           ("", 'sandbox_mode = "read-only"\n'),
                           ('model = "gpt-5.2"', 'model = "gpt-5.2"\nsandbox_mode = "read-only"'),
                           ('model = "gpt-5.2"\r\n', 'model = "gpt-5.2"\r\nsandbox_mode = "read-only"\r\n')):
            now, back = self.edit(text, "sandbox_mode", None, "read-only")
            self.assertEqual(now, made, repr(text))
            self.assertEqual(back, {"key": ["sandbox_mode"], "before": "read-only", "after": None})
            self.assertEqual(harness_edit.toml_edit(now, back)[0], text, repr(text))

    def test_a_value_over_several_lines_and_another_tables_key_are_stepped_over(self):
        text = ('notify = [\n  "notify-send",\n  ["x"]\n]\nwritable = { roots = [\n  "/tmp/a",\n] }\n\n'
                '[[rules]]\nmodel = "a rule of its own"\n\n[mcp_servers.docs]\nmodel = "nor this"\nargs = [\n'
                '  "model = 1",\n]\n')
        made, back = self.edit(text, "model", None, "gpt-5.2")
        self.assertEqual(made, text.replace("] }\n", '] }\nmodel = "gpt-5.2"\n'))
        self.assertEqual(harness_edit.toml_edit(made, back)[0], text)

    def test_a_stale_line_is_refused(self):
        for key, before, after in (("model", "gpt-5.2", "gpt-5.1-codex"), ("model", None, "gpt-5.1-codex"),
                                   ("sandbox_mode", "read-only", None), ("sandbox_mode", "read-only", "read-write")):
            with self.assertRaises(harness_edit.Refused) as refused:
                self.edit(CONFIG, key, before, after)
            self.assertEqual(refused.exception.args[0], harness_edit.STALE)

    def test_a_shape_not_changed_by_line_is_refused(self):
        for text, key, before, after in (
                ('model = "gpt-5.2"\nnotes = """\nmodel = "x"\n"""\n', "model", "gpt-5.2", "gpt-5.1"),
                ("model = '''gpt-5.2'''\n", "model", "gpt-5.2", "gpt-5.1"),
                ('model = "gpt-5.2"\nmodel = "gpt-5.2"\n', "model", "gpt-5.2", "gpt-5.1"),
                ("model = 5\n", "model", None, "gpt-5.1"),
                ('model = "gpt\\u002d5"\n', "model", None, "gpt-5.1"),
                ('model = ["gpt-5.2"]\n', "model", None, "gpt-5.1"),
                ('[approval_policy.granular]\nrules = true\n', "approval_policy", None, "never"),
                ('[approval_policy]\ngranular = true\n', "approval_policy", None, "never"),
                ('approval_policy.granular.rules = true\n', "approval_policy", None, "never"),
                ('approval_policy = { granular = { rules = true } }\n', "approval_policy", None, "never"),
                ('model = "gpt-5.2"\nthis is no toml\n', "model", "gpt-5.2", "gpt-5.1"),
                ('[broken\nmodel = "gpt-5.2"\n', "model", None, "gpt-5.1"),
                ('"model\\q" = "gpt-5.2"\n', "model", None, "gpt-5.1"),
                ('model = "gpt-5.2"  # mine\n', "model", "gpt-5.2", None)):
            with self.assertRaises(harness_edit.Refused, msg=text) as refused:
                self.edit(text, key, before, after)
            self.assertEqual(refused.exception.args[0], harness_edit.NOT_EDITED, text)

    def test_codexs_file_is_changed_in_place_and_restored(self):
        self.put(self.config, CONFIG)
        made = self.apply({"layer": "Global", "key": ["model"], "before": "gpt-5.2-codex", "after": "gpt-5.2"},
                          {"layer": "Global", "key": ["sandbox_mode"], "before": None, "after": "workspace-write"},
                          {"layer": "Global", "key": ["approval_policy"], "before": None, "after": "never"},
                          agent="codex")
        self.assertTrue(made["applied"])
        found = agent_setup.codex_config(self.home)
        self.assertEqual((found["model"], found["sandbox_mode"], found["approval_policy"]),
                         ("gpt-5.2", "workspace-write", "never"))
        self.assertIn('[projects."/Users/dev/lumen-api"]\ntrust_level = "trusted"\n', self.text(self.config))
        self.assertTrue(self.apply(*made["undo"], agent="codex")["applied"])
        self.assertEqual(self.text(self.config), CONFIG)
        stale = self.apply({"layer": "Global", "key": ["model"], "before": "gpt-5.2", "after": "gpt-5.1-codex"},
                           agent="codex")
        self.assertEqual(stale["error"], "~/.codex/config.toml changed since: nothing saved")
        project = self.apply({"layer": "Project", "key": ["model"], "before": None, "after": "gpt-5.2"}, agent="codex")
        self.assertTrue(project["applied"])
        self.assertEqual(self.text(os.path.join(self.folder, ".codex", "config.toml")), 'model = "gpt-5.2"\n')

    def test_only_codexs_keys_herdr_fold_changes_are_ever_written(self):
        self.put(self.config, CONFIG)
        for edit in ({"layer": "Global", "key": ["model_provider"], "before": None, "after": "other"},
                     {"layer": "Global", "key": ["mcp_servers", "docs", "command"], "before": "docs-mcp",
                      "after": "id"},
                     {"layer": "Global", "key": ["projects", "/Users/dev/lumen-api", "trust_level"],
                      "before": "trusted", "after": "untrusted"},
                     {"layer": "Global", "key": ["approval_policy"], "before": None, "after": "untrusted"},
                     {"layer": "Global", "key": ["sandbox_mode"], "before": None, "after": "none"},
                     {"layer": "Global", "key": ["model"], "before": None, "after": 'a"\nb = "c'},
                     {"layer": "Global", "key": ["model"], "add": "gpt-5.2"},
                     {"layer": "Local", "key": ["model"], "before": None, "after": "gpt-5.2"}):
            with self.assertRaises(ValueError, msg=edit):
                self.apply(edit, agent="codex")
        self.assertEqual(self.text(self.config), CONFIG)


if __name__ == "__main__":
    unittest.main()
