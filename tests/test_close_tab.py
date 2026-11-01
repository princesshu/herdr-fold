"""Tests for close_tab.py (Cmd+W): the main tab never closes, a tab without a conversation closes at once, one with
a conversation asks first (--confirm: Enter closes, Esc keeps it). herdr is a fake that records the calls.
"""
import contextlib
import io
import os
import unittest

from support import set_attrs, set_env

import close_tab


class CloseTab(unittest.TestCase):
    def setUp(self):
        self.calls, self.label, self.number = [], "notes", 2
        self.agents = [{"pane_id": "w1:p1", "tab_id": "w1:t2", "agent": "claude", "tokens": {"has_session": "yes"},
                        "terminal_title_stripped": "Fix the login"},
                       {"pane_id": "w1:p5", "tab_id": "w1:t3", "agent": "claude", "tokens": {}}]

        def herdr(*args, check=True):
            self.calls.append(args)
            if args[:2] == ("tab", "get"):
                return {"tab": {"tab_id": args[2], "label": self.label, "number": self.number}}
            if args[:2] == ("agent", "list"):
                return {"agents": self.agents}
            return {}
        set_attrs(self, close_tab, herdr=herdr)
        set_env(self, HERDR_ACTIVE_TAB_ID=None, HERDR_CLOSE_TAB=None)

    def press(self, tab):
        os.environ["HERDR_ACTIVE_TAB_ID"] = tab
        close_tab.main([])
        return [c for c in self.calls if c[:2] != ("agent", "list") and c[:2] != ("tab", "get")]

    def test_the_main_tab_never_closes_whatever_its_name(self):
        for name in ("app", "my notes", "files"):
            self.calls.clear()
            self.label, self.number = name, 1
            self.assertEqual([c[:2] for c in self.press("w1:t1")], [("notification", "show")], name)

    def test_a_later_tab_called_files_closes_as_any_other(self):
        self.label = "files"
        self.assertEqual(self.press("w1:t3"), [("tab", "close", "w1:t3")])

    def test_a_tab_without_a_conversation_closes_at_once(self):
        self.assertEqual(self.press("w1:t3"), [("tab", "close", "w1:t3")])

    def test_a_tab_with_a_conversation_asks_first(self):
        calls = self.press("w1:t2")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][:3], ("plugin", "pane", "open"))
        self.assertIn("HERDR_CLOSE_TAB=w1:t2", calls[0])

    def test_nothing_without_an_active_tab(self):
        os.environ.pop("HERDR_ACTIVE_TAB_ID", None)
        close_tab.main([])
        self.assertEqual(self.calls, [])

    def confirm(self, key):
        os.environ["HERDR_CLOSE_TAB"] = "w1:t2"
        close_tab.getkey = lambda: key
        with contextlib.redirect_stdout(io.StringIO()) as out:
            close_tab.main(["--confirm"])
        return out.getvalue(), [c for c in self.calls if c[:2] == ("tab", "close")]

    def test_enter_closes_and_names_the_conversation(self):
        shown, closed = self.confirm("\r")
        self.assertIn("Fix the login", shown)
        self.assertIn("Cmd+Shift+R", shown)
        self.assertEqual(closed, [("tab", "close", "w1:t2")])

    def test_esc_keeps_the_tab(self):
        _, closed = self.confirm("\x1b")
        self.assertEqual(closed, [])

    def test_a_name_cannot_send_terminal_codes(self):
        # the tab's label and the conversation's title come from elsewhere: escape codes in them show as ?
        self.label = "notes\x1b]52;c;ZXZpbA==\x07"
        self.agents[0]["terminal_title_stripped"] = "Fix\x1b]0;owned\x07 the login"
        shown, _ = self.confirm("\x1b")
        self.assertNotIn("\x1b]", shown)
        self.assertNotIn("\x07", shown)
        self.assertIn("Fix?]0;owned? the login", shown)

if __name__ == "__main__":
    unittest.main()
