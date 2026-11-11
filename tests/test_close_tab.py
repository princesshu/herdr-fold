"""Tests for close_tab.py (Cmd+W): the main tab never closes, a tab without a conversation closes at once, one with
a conversation asks first (--confirm: Enter closes, Esc keeps it). herdr is a fake that records the calls.
"""
import contextlib
import io
import os
import unittest

from support import ANSI, set_attrs, set_env

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
        self.assertEqual(calls[0][:7], ("plugin", "pane", "open", "--plugin", "herdr-fold.workspaces", "--entrypoint",
                                        "close-confirm"))
        self.assertIn("HERDR_CLOSE_TAB=w1:t2", calls[0])

    def test_nothing_without_an_active_tab(self):
        os.environ.pop("HERDR_ACTIVE_TAB_ID", None)
        close_tab.main([])
        self.assertEqual(self.calls, [])

    def confirm(self, key):
        """KEY pressed (a function of the screen shown so far gives a click)."""
        os.environ["HERDR_CLOSE_TAB"] = "w1:t2"
        with contextlib.redirect_stdout(io.StringIO()) as out:
            set_attrs(self, close_tab, getkey=lambda: key(out.getvalue()) if callable(key) else key)
            close_tab.main(["--confirm"])
        return out.getvalue(), [c for c in self.calls if c[:2] == ("tab", "close")]

    @staticmethod
    def click_on(label):
        """A click on the button LABEL (the bottom row: the question names Close too), then Esc."""
        clicks = []

        def key(shown):
            if clicks:
                return "\x1b"
            lines = ANSI.sub("", shown.split("\x1b[H")[-1]).split("\n")
            row = max(n for n, line in enumerate(lines, 1) if label in line)
            clicks.append(row)
            return f"\x1b[<0;{lines[row - 1].rindex(label) + 1};{row}M"
        return key

    def test_close_and_cancel_buttons_take_a_click(self):
        shown, closed = self.confirm(self.click_on("Close"))
        self.assertTrue(ANSI.sub("", shown).rstrip().endswith("Cancel    Close"), shown[-80:])
        lines = ANSI.sub("", shown.split("\x1b[H")[-1]).split("\n")
        self.assertTrue(lines[0].startswith(" Close the tab"), lines[0])            # a cell clear at each edge
        self.assertTrue(lines[-1].endswith(" Close  "), lines[-1])
        self.assertEqual(closed, [("tab", "close", "w1:t2")])
        _, closed = self.confirm(self.click_on("Cancel"))
        self.assertEqual(closed, [("tab", "close", "w1:t2")])                  # the first one's, no other

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
