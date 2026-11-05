"""Tests for herdrlib.py's shared helpers: shell-only panes, a pane's agent name, herdr's agents and machines, whether
an agent holds a conversation, and the sidebar's launcher for a folder's system. herdr is a fake (a recorded call list).
"""
import unittest

import support  # noqa: F401  (puts src/ on the import path)

import herdrlib  # noqa: E402


class Shells(unittest.TestCase):
    def test_a_shell_alone_is_only_a_shell(self):
        for names in (["-zsh"], ["C:\\Program Files\\PowerShell\\7\\pwsh.exe"], ["powershell.exe"], ["bash", "sh"]):
            self.assertTrue(herdrlib.only_shells([{"name": n} for n in names]), names)

    def test_a_program_in_the_foreground_is_not(self):
        self.assertFalse(herdrlib.only_shells([{"name": "pwsh.exe"}, {"name": "node.exe"}]))
        self.assertFalse(herdrlib.only_shells([]))

    def test_program_names_are_plain(self):
        self.assertEqual(herdrlib.program_names([{"name": "C:\\Tools\\Node.EXE"}, {"name": "-zsh"}]), ["node", "zsh"])


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

    def test_agents_and_conversations(self):
        h, _ = self.fake(**{"agent list": {"agents": [
            {"pane_id": "w1:p1", "agent": "claude", "tokens": {"has_session": "yes"}},
            {"pane_id": "w1:p2", "agent": "codex", "tokens": {}}]}})
        agents = herdrlib.agents(h)
        self.assertEqual([a["pane_id"] for a in agents], ["w1:p1", "w1:p2"])
        self.assertEqual([herdrlib.has_conversation(a) for a in agents], [True, False])

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


if __name__ == "__main__":
    unittest.main()
