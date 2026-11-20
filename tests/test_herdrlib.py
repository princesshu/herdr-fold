"""Tests for herdrlib.py's shared helpers: a pane's agent name, herdr's agents and machines, whether an agent holds a
chat, and the sidebar's launcher for a folder's system (the shell names are the sidebar's panes.py's, tested
there). herdr is a fake (a recorded call list); its socket a one-answer stand-in in a temporary folder."""
import json
import os
import shutil
import socket
import tempfile
import threading
import unittest

import support  # noqa: F401  (puts src/ on the import path)

import herdrlib  # noqa: E402


class AgentName(unittest.TestCase):
    def test_a_label_becomes_a_safe_name(self):
        self.assertEqual(herdrlib.agent_name("My Repo (v2)", "claude"), "my-repo--v2")

    def test_a_name_starts_with_a_letter(self):
        self.assertEqual(herdrlib.agent_name("2026 notes", "codex"), "codex-2026-notes")

    def test_a_name_is_at_most_32_characters(self):
        self.assertLessEqual(len(herdrlib.agent_name("x" * 80, "claude")), 32)


class Listing(unittest.TestCase):
    def fake(self, **answers):
        calls = []

        def h(*args, check=True):
            calls.append(args)
            return answers.get(" ".join(args[:2]), {})
        return h, calls

    def test_agents_and_chats(self):
        h, _ = self.fake(**{"agent list": {"agents": [
            {"pane_id": "w1:p1", "agent": "claude", "tokens": {"has_session": "yes"}},
            {"pane_id": "w1:p2", "agent": "codex", "tokens": {}}]}})
        agents = herdrlib.agents(h)
        self.assertEqual([a["pane_id"] for a in agents], ["w1:p1", "w1:p2"])
        self.assertEqual([herdrlib.has_chat(a) for a in agents], [True, False])

    def test_no_herdr_answer_means_no_agents(self):
        h, _ = self.fake()
        self.assertEqual(herdrlib.agents(h), [])

    def test_machines(self):
        h, calls = self.fake(**{"machine list": [{"label": "box", "enabled": True}]})
        self.assertEqual(herdrlib.machines(h), [{"label": "box", "enabled": True}])
        self.assertEqual(calls, [("machine", "list", "--json")])


class SidebarCommand(unittest.TestCase):
    def test_windows_folder_gets_the_powershell_launcher(self):
        self.assertIn("sidebar.ps1", herdrlib.sidebar_command("C:\\Users\\dev\\project"))
        self.assertIn("powershell", herdrlib.sidebar_command("D:/projects"))

    def test_unix_folder_gets_the_bash_launcher(self):
        self.assertEqual(herdrlib.sidebar_command("/home/dev/project"), "bash ~/.config/herdr-fold/sidebar.sh")
        self.assertEqual(herdrlib.sidebar_command(None), "bash ~/.config/herdr-fold/sidebar.sh")


class Request(unittest.TestCase):
    """herdr's socket API for what its command line has not: one JSON line asked, the answer's result given; nothing
    when herdr is not there or refuses (an older herdr does not know the method)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir="/tmp")             # short: a socket's path fits in 104 bytes
        self.addCleanup(shutil.rmtree, self.tmp)
        self.path, self.asked = os.path.join(self.tmp, "herdr.sock"), []
        support.set_env(self, HERDR_SOCKET_PATH=self.path)

    def serve(self, reply):
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(server.close)
        server.bind(self.path)
        server.listen()

        def answer():
            conn, _ = server.accept()
            with conn:
                self.asked.append(json.loads(conn.makefile().readline()))
                conn.sendall((json.dumps(reply) + "\n").encode())
        thread = threading.Thread(target=answer, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)

    def test_the_method_and_its_fields_are_asked_and_the_result_given(self):
        self.serve({"id": "workspace.move", "result": {"type": "workspace_list", "workspaces": []}})
        self.assertEqual(herdrlib.request("workspace.move", {"workspace_id": "w2", "insert_index": 0}),
                         {"type": "workspace_list", "workspaces": []})
        self.assertEqual([(asked["method"], asked["params"]) for asked in self.asked],
                         [("workspace.move", {"workspace_id": "w2", "insert_index": 0})])

    def test_a_herdr_that_does_not_know_the_method_gives_nothing(self):
        self.serve({"id": "", "error": {"code": "invalid_request", "message": "unknown variant `workspace.move`"}})
        self.assertEqual(herdrlib.request("workspace.move", {"workspace_id": "w2", "insert_index": 0}), {})

    def test_no_herdr_gives_nothing(self):
        self.assertEqual(herdrlib.request("workspace.move", {"workspace_id": "w2", "insert_index": 0}), {})


if __name__ == "__main__":
    unittest.main()
