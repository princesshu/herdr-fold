"""Tests for core/statefile.py and the sidebar plugin's writers: every state file and its folder are the owner's only,
whatever the umask, and each is written through its own temporary file, so a planted link is never followed."""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import unittest

from support import SRC, FakeTerminal, set_env

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import column  # noqa: E402
import conversations  # noqa: E402
import loop  # noqa: E402
import panels  # noqa: E402
import sidebar  # noqa: E402
import statefile  # noqa: E402


class Herdr:
    def call(self, *args):
        return {}


class OwnerOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.state = os.path.join(self.tmp, "state")
        set_env(self, HOME=os.path.join(self.tmp, "home"))              # never the user's conversations
        self.addCleanup(os.umask, os.umask(0o022))                          # the usual umask: files 0644, folders 0755

    def mode(self, path):
        return stat.S_IMODE(os.stat(path).st_mode)

    def assert_owner_only(self, *names):
        self.assertEqual({name: self.mode(os.path.join(self.state, name)) for name in names},
                         {name: 0o600 for name in names})
        self.assertEqual(self.mode(self.state), 0o700)

    def test_it_writes_a_whole_file_its_owners_only_and_closes_an_open_folder(self):
        os.makedirs(self.state, mode=0o755)
        statefile.write(os.path.join(self.state, "x.json"), {"a": 1})
        self.assert_owner_only("x.json")
        with open(os.path.join(self.state, "x.json")) as f:
            self.assertEqual(json.load(f), {"a": 1})
        self.assertEqual(os.listdir(self.state), ["x.json"])                 # no temporary file left behind

    def test_a_link_where_the_fixed_temporary_name_was_is_not_followed(self):
        os.makedirs(self.state)
        elsewhere = os.path.join(self.tmp, "elsewhere")
        with open(elsewhere, "w") as f:
            f.write("mine\n")
        os.symlink(elsewhere, os.path.join(self.state, "conversations.json.tmp"))
        conversations.keep(self.state, show_archived=True)
        with open(elsewhere) as f:
            self.assertEqual(f.read(), "mine\n")
        self.assertFalse(os.path.islink(os.path.join(self.state, "conversations.json")))

    def test_every_state_file_is_its_owners_only(self):
        conversations.save_index(self.state, {"/x.jsonl": {"prompt": "the first line of a prompt"}})
        conversations.keep(self.state, show_archived=True)
        panels.note(self.state, {"w1:t1": {"sidebar"}})
        column.keep(self.state, {"ratio": 0.7})
        self.assert_owner_only(conversations.INDEX, conversations.SETTINGS, panels.FILE, column.FILE,
                               conversations.SETTINGS + ".lock", panels.FILE + ".lock", column.FILE + ".lock")

    def test_a_link_planted_where_a_lock_goes_is_not_followed(self):
        os.makedirs(self.state)
        elsewhere = os.path.join(self.tmp, "elsewhere")
        os.symlink(elsewhere, os.path.join(self.state, "x.json.lock"))
        with self.assertRaises(OSError):
            statefile.update(os.path.join(self.state, "x.json"), lambda kept: {**kept, "a": 1})
        self.assertFalse(os.path.exists(elsewhere))

    def test_a_handover_and_the_settings_are_their_owners_only(self):
        set_env(self, **{loop.RESUME_ENV: ""})
        pane = loop.Loop(FakeTerminal(40, 20), Herdr(), self.state, lambda: 0)
        pane.hand_over()
        token = os.environ[loop.RESUME_ENV]
        app = sidebar.App(self.tmp, FakeTerminal(45, 30), Herdr(), self.state)
        app.save(hidden=True)
        self.assert_owner_only(f"resume-{token}.json", "settings.json")


# another process changing the file (another tab's sidebar, the app's helper): it holds it a while, then adds its own
CHANGER = """import sys, time
sys.path.insert(0, sys.argv[1])
import statefile

def change(kept):
    print("in", flush=True)
    time.sleep(0.5)
    return {**kept, "hidden": True}

statefile.update(sys.argv[2], change)
"""


class Changed(unittest.TestCase):
    """statefile.update: a state file changed by one writer at a time, whatever process or thread it runs in."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.path = os.path.join(self.tmp, "state", "settings.json")

    def test_another_processes_change_is_waited_for_and_both_are_kept(self):
        child = subprocess.Popen([sys.executable, "-B", "-c", CHANGER, os.path.join(SRC, "plugins", "sidebar"),
                                  self.path], stdout=subprocess.PIPE, text=True)
        self.addCleanup(child.wait, 5)
        self.addCleanup(child.stdout.close)
        self.assertEqual(child.stdout.readline().strip(), "in")             # its change under way
        statefile.update(self.path, lambda kept: {**kept, "icons": False})
        child.wait(5)
        self.assertEqual(statefile.read(self.path), {"hidden": True, "icons": False})

    def test_a_change_inside_a_change_locks_once(self):
        def change():
            with statefile.locked(self.path):
                statefile.update(self.path, lambda kept: {**kept, "a": 1})
        thread = threading.Thread(target=change, daemon=True)
        thread.start()
        thread.join(3)
        self.assertFalse(thread.is_alive())                                 # no thread waits for itself
        self.assertEqual(statefile.read(self.path), {"a": 1})

    def test_what_cannot_be_read_is_nothing(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as f:
            f.write("[1, 2")
        self.assertEqual(statefile.read(self.path), {})


if __name__ == "__main__":
    unittest.main()
