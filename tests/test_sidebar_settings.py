"""Tests for herdr-fold's Settings in the TUI (src/plugins/sidebar/settings.py, herdr's popup that the sidebar's More
opens): its section list, General's Icons, About's rows in each state of the update check, its switch, Check now,
What's new, the notices, and its three ways out; core/update.py and herdr stand-ins, nothing reaches the network."""
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

from support import SRC, FakeTerminal, end_jobs, set_env, text

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import settings  # noqa: E402
import sidebar  # noqa: E402
import theme  # noqa: E402
from vt import Focus, Key, Mouse  # noqa: E402

WIDE, HIGH = 62, 13                       # the popup's inside: herdr-plugin.toml's size less herdr's frame
LIST, AT = 15, 17                         # the section list's cells; the section's first column, past the rule
NOON = time.mktime(time.localtime()[:3] + (12, 30, 0, 0, 0, -1))                 # 12:30 today, this Mac's zone
FOUND = {"version": "0.3.0", "latest": "0.3.0", "newer": False, "on": True, "checked": NOON, "error": None,
         "updated": None, "releases": "https://github.com/princesshu/herdr-fold/releases", "how": settings.update.HOW}
CLOSE = ""                          # Codicons' close


def line(right="", left=""):
    """A row as drawn: LEFT in the section list, the rule, a cell of air, RIGHT in the section."""
    return f"{left:<{LIST}}│ {right}".rstrip()


class Herdr:
    def __init__(self):
        self.calls = []

    def call(self, *args):
        self.calls.append(args)
        return {}


class Popup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_env(self, HOME=self.tmp)
        self.addCleanup(end_jobs)
        self.herdr = Herdr()
        self.state = os.path.join(self.tmp, "state")

    def open(self, found=FOUND, check=None, section="about", clock=time.monotonic):
        """The popup, its first look answered with FOUND (CHECK: core's check stood in for, as it is called), SECTION
        chosen in its list."""
        check = check or mock.Mock(return_value=found)
        patch = mock.patch.object(settings.update, "check", check)
        patch.start()
        self.addCleanup(patch.stop)
        app = settings.Settings(FakeTerminal(WIDE, HIGH), self.herdr, self.state, clock=clock,
                                context={"workspace_id": "w1", "tab_id": "w1:t1", "focused_pane_id": "w1:p2",
                                         "workspace_cwd": self.tmp})
        if section and app.section != section:
            names = list(settings.SECTIONS)
            for _ in range(abs(names.index(section) - names.index(app.section))):
                app.handle(Key("down" if names.index(section) > names.index(app.section) else "up"))
        self.settle(app)
        return app

    def settle(self, app):
        end_jobs()
        app.collect()
        app.draw()

    def rows(self, app):
        return [text(app.canvas, y).rstrip() for y in range(HIGH)]

    def kept(self):
        with open(os.path.join(self.state, "settings.json"), encoding="utf-8") as f:
            return json.load(f)


class General(Popup):
    def test_general_draws_as_the_mockup(self):
        # settings.html's TUI box: the section list, a rule down every row, the section from the same column; Icons
        # with its two options, what it is for under it
        app = self.open(section=None)
        self.assertEqual(app.section, "general")
        self.assertEqual(self.rows(app), [
            " " * LIST + "│" + " " * (WIDE - LIST - 3) + CLOSE,
            line("Icons", " General"),
            line(" Nerd Font   Plain marks", " Notifications"),
            line(left=" About"),
            line("Plain marks where the terminal's font has no"),
            line("Nerd Font icons; i in Files switches it too.")] + [line()] * 7)

    def test_the_chosen_section_and_option_are_lit(self):
        # the chosen section on the selection's background from the popup's side to the rule, bold; the other in the
        # subtext; the rule a guide; the option in use lit as a chosen button, the other plain and faint
        app = self.open(section=None)
        rows = app.canvas.rows
        self.assertEqual({(style.bg, style.bold) for _ch, style in rows[1][:LIST]}, {("selection", True)})
        self.assertEqual({(style.fg, style.bg, style.bold) for _ch, style in rows[2][:LIST]},
                         {("subtext", None, False)})
        self.assertEqual({rows[y][LIST] for y in range(HIGH)}, {("│", settings.Style(fg="guide"))})
        lit = settings.Style(fg="button_text", bg="button", bold=True)
        self.assertEqual([style for _ch, style in rows[2][AT:AT + 11]], [lit] * 11)
        self.assertEqual(rows[2][AT + 11][1].bg, None)                           # a cell between the two
        self.assertEqual({style for _ch, style in rows[2][AT + 13:AT + 24]}, {settings.Style(fg="muted")})
        self.assertEqual((rows[1][AT][1], rows[4][AT][1]), (settings.Style(fg="text"), settings.Style(fg="muted")))
        self.assertEqual(rows[5][AT + len("Nerd Font icons; ")], ("i", settings.Style(fg="text")))

    def test_the_arrows_and_tab_switch_the_icons_at_once(self):
        # no OK: the option chosen is the one in use, written to the sidebar's settings.json beside what it holds;
        # nothing moves, the close button wears the new set at once
        os.makedirs(self.state)
        with open(os.path.join(self.state, "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"agent": "codex"}, f)
        app = self.open(section=None)
        app.handle(Key("right"))
        app.draw()
        self.assertEqual(self.kept(), {"agent": "codex", "icons": False})
        rows = self.rows(app)
        self.assertEqual((rows[0][-1], rows[2]), ("×", line(" Nerd Font   Plain marks", " Notifications")))
        self.assertEqual([app.canvas.rows[2][x][1].bg for x in (AT, AT + 11, AT + 12, AT + 24, AT + 25)],
                         [None, None, "button", "button", None])
        self.assertEqual(app.canvas.rows[2][AT + 1][1], settings.Style(fg="muted"))
        app.handle(Key("left"))
        self.assertIs(self.kept()["icons"], True)
        app.handle(Key("tab"))
        self.assertIs(self.kept()["icons"], False)
        app.handle(Key("backtab"))
        app.draw()
        self.assertEqual((self.kept()["icons"], self.rows(app)[0][-1]), (True, CLOSE))

    def test_a_click_on_an_option_chooses_it(self):
        app = self.open(section=None)
        app.handle(Mouse("press", AT + 14, 2, 0))
        self.assertIs(self.kept()["icons"], False)
        app.draw()
        app.handle(Mouse("press", AT + 14, 2, 0))                               # the one in use: as it is
        self.assertIs(self.kept()["icons"], False)
        app.handle(Mouse("press", AT, 2, 0))
        self.assertIs(self.kept()["icons"], True)

    def test_it_opens_on_the_icons_in_use(self):
        os.makedirs(self.state)
        with open(os.path.join(self.state, "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"icons": False}, f)
        app = self.open(section=None)
        self.assertEqual((self.rows(app)[0][-1], app.canvas.rows[2][AT + 13][1].bg), ("×", "button"))

    def test_settings_that_cannot_be_written_leave_the_option_as_it_was(self):
        app = self.open(section=None)
        with mock.patch.object(settings.statefile, "update", side_effect=OSError("read-only")):
            app.handle(Key("right"))
        app.draw()
        self.assertEqual(app.canvas.rows[2][AT][1].bg, "button")

    def test_abouts_keys_do_nothing_in_general(self):
        check = mock.Mock(return_value=FOUND)
        app = self.open(check=check, section=None)
        with mock.patch.object(settings.update, "switch") as switch, \
                mock.patch.object(settings.preview, "open_preview") as opened:
            app.handle(Key("char", " "))
            app.handle(Key("enter"))
            self.settle(app)
        self.assertEqual((switch.called, opened.called, check.call_count, app.quit), (False, False, 1, False))


class Notifications(Popup):
    """Notifications: herdr's own toast for an agent that waits, on or off in herdr's config.toml, then reloaded."""

    def config(self, body=None):
        path = os.path.join(self.tmp, ".config", "herdr", "config.toml")
        if body is not None:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(body)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_it_draws_between_general_and_about_as_the_mockup_on_by_default(self):
        app = self.open(section="notifications")
        self.assertEqual(self.rows(app), [
            " " * LIST + "│" + " " * (WIDE - LIST - 3) + CLOSE,
            line("An agent waits on you", " General"),
            line(" on   off", " Notifications"),
            line(left=" About"),
            line("herdr's note at the bottom right,"),
            line("once per agent")] + [line()] * 7)
        lit, plain = app.canvas.rows[2][AT + 1][1], app.canvas.rows[2][AT + 6][1]
        self.assertEqual((lit.bg, lit.bold, plain.fg), ("button", True, "muted"))
        self.assertEqual(self.herdr.calls, [])                                  # nothing written or asked to look

    def test_off_writes_herdrs_own_setting_and_reloads_it_and_on_puts_herdr_back(self):
        self.config('[ui]\ncopy_on_select = false\n\n[ui.toast]\ndelivery = "herdr"\n')
        app = self.open(section="notifications")
        app.handle(Key("right"))
        self.settle(app)
        self.assertEqual(self.config(), '[ui]\ncopy_on_select = false\n\n[ui.toast]\ndelivery = "off"\n')
        self.assertEqual(self.herdr.calls, [("server", "reload-config")])
        self.assertEqual(app.canvas.rows[2][AT + 6][1].bg, "button")
        self.assertFalse(self.open(section="notifications").waits)             # read from the file when it opens
        app.handle(Mouse("press", AT + 1, 2, 0))
        self.settle(app)
        self.assertIn('delivery = "herdr"', self.config())
        self.assertEqual(len(self.herdr.calls), 2)

    def test_another_delivery_of_theirs_shows_on_and_stays_until_they_switch(self):
        self.config('[ui.toast]\ndelivery = "terminal"\n')
        app = self.open(section="notifications")
        self.assertTrue(app.waits)
        app.handle(Mouse("press", AT + 1, 2, 0))                                # on, as it is: nothing written
        self.settle(app)
        self.assertEqual((self.config(), self.herdr.calls), ('[ui.toast]\ndelivery = "terminal"\n', []))
        app.handle(Key("tab"))
        self.settle(app)
        self.assertIn('delivery = "off"', self.config())

    def test_a_file_it_cannot_read_for_sure_or_a_reload_that_fails_leaves_the_popup_standing(self):
        self.config('a = """\n')
        app = self.open(section="notifications")
        app.handle(Key("right"))
        self.settle(app)
        self.assertEqual((app.waits, self.config(), self.herdr.calls), (True, 'a = """\n', []))
        self.config('[ui.toast]\ndelivery = "herdr"\n')
        self.herdr.call = mock.Mock(side_effect=RuntimeError("no server"))
        app.handle(Key("right"))
        self.settle(app)
        self.assertEqual((app.waits, app.error), (False, None))                 # written: herdr reads it when it starts


class Sidebars(unittest.TestCase):
    """What General writes reaches every tab's sidebar within a look (a second), whatever its poll's pace."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_env(self, HOME=self.tmp)
        self.addCleanup(end_jobs)
        self.now = 1000.0
        self.state = os.path.join(self.tmp, "state")
        self.app = sidebar.App(self.tmp, FakeTerminal(69, 30), Herdr(), self.state, clock=lambda: self.now)

    def test_an_idle_tabs_sidebar_takes_the_icons_within_a_second(self):
        self.app.tick()
        self.app.next_poll = self.now + 10.0                    # idle: its poll ten seconds away
        popup = settings.Settings(FakeTerminal(WIDE, HIGH), Herdr(), self.state)
        popup.set_icons(False)
        self.assertLessEqual(self.app.timeout(), sidebar.LOOK)  # it wakes for the look, not for the poll
        self.now += sidebar.LOOK
        self.assertTrue(self.app.tick())                        # taken: drawn again
        self.assertEqual({view.icons for view in self.app.views.values()}, {False})
        self.assertIs(self.app.settings["icons"], False)
        self.assertEqual(self.app.next_poll, 1010.0)            # the poll's pace is as it was
        # nothing changed since: a look is one stat, the file not read again, nothing drawn
        with mock.patch.object(sidebar, "load_settings", side_effect=AssertionError("read with no change")):
            for _ in range(3):
                self.now += sidebar.LOOK
                self.assertFalse(self.app.tick())
        popup.set_icons(True)
        self.now += sidebar.LOOK
        self.assertTrue(self.app.tick())
        self.assertEqual({view.icons for view in self.app.views.values()}, {True})

    def idle(self):
        """The sidebar after its first poll, its next one ten seconds away."""
        self.app.tick()
        self.app.next_poll = self.now + 10.0

    def test_an_idle_tabs_sidebar_takes_the_theme_within_a_second(self):
        self.idle()
        os.makedirs(self.state, exist_ok=True)
        with open(os.path.join(self.state, "colors.json"), "w", encoding="utf-8") as f:
            json.dump({"accent": "#123456"}, f)             # as herdr-fold's theme setter writes it
        self.assertLessEqual(self.app.timeout(), sidebar.LOOK)
        self.now += sidebar.LOOK
        self.assertTrue(self.app.tick())                        # taken: drawn again
        self.assertEqual(self.app.renderer.theme.colors, {"accent": "#123456"})
        self.assertEqual(self.app.next_poll, 1010.0)
        # the same theme since: one stat a look, colors.json not read again, nothing drawn
        with mock.patch.object(theme.Theme, "load", side_effect=AssertionError("read with no change")):
            for _ in range(3):
                self.now += sidebar.LOOK
                self.assertFalse(self.app.tick())
        os.remove(os.path.join(self.state, "colors.json"))      # the terminal's own colors again
        self.now += sidebar.LOOK
        self.assertTrue(self.app.tick())
        self.assertEqual(self.app.renderer.theme.colors, {})

    def test_an_idle_tabs_sidebar_takes_the_folded_dock_within_a_second(self):
        self.idle()
        self.assertFalse(self.app.railed)
        self.assertTrue(sidebar.column.keep(self.state, {"rail": True}))     # another tab's sidebar folded the dock
        self.now += sidebar.LOOK
        self.assertTrue(self.app.tick())
        self.assertTrue(self.app.railed)
        self.assertEqual(self.app.next_poll, 1010.0)
        # the dock as it was since: column.json not read again, nothing drawn
        with mock.patch.object(sidebar.column, "kept", side_effect=AssertionError("read with no change")):
            for _ in range(3):
                self.now += sidebar.LOOK
                self.assertFalse(self.app.tick())
        sidebar.column.keep(self.state, {"rail": False})
        self.now += sidebar.LOOK
        self.assertTrue(self.app.tick())
        self.assertFalse(self.app.railed)

    def test_a_poll_reads_each_file_once_and_the_next_look_none_again(self):
        # the poll reads what it always read; its reads count as seen, so the look after it stats and reads nothing
        self.idle()
        sidebar.column.keep(self.state, {"rail": True})
        self.now = self.app.next_poll
        self.app.tick()
        self.assertTrue(self.app.railed)
        with mock.patch.object(sidebar.column, "kept", side_effect=AssertionError("read with no change")), \
                mock.patch.object(sidebar, "load_settings", side_effect=AssertionError("read with no change")):
            self.app.next_poll = self.now + 10.0
            self.now += sidebar.LOOK
            self.assertFalse(self.app.tick())


class Sections(Popup):
    def installed(self, version, latest):
        folder = settings.update.statefile.folder()
        os.makedirs(folder)
        with open(os.path.join(folder, "version"), "w", encoding="utf-8") as f:
            f.write(version + "\n")
        settings.update.keep(latest=latest)

    def test_up_and_down_choose_the_section(self):
        app = self.open(section=None)
        for key, section in (("up", "general"), ("down", "notifications"), ("down", "about"), ("down", "about"),
                             ("up", "notifications"), ("up", "general")):
            app.handle(Key(key))
            self.assertEqual(app.section, section, key)
        app.handle(Key("down"))
        app.draw()
        self.assertEqual({(style.bg, style.bold) for _ch, style in app.canvas.rows[2][:LIST]}, {("selection", True)})
        self.assertEqual(app.canvas.rows[1][1][1], settings.Style(fg="subtext"))

    def test_a_click_chooses_a_section_and_the_mouse_lights_the_other(self):
        app = self.open(section=None)
        app.handle(Mouse("move", LIST - 1, 3, 3))
        app.draw()
        self.assertEqual({style.bg for _ch, style in app.canvas.rows[3][:LIST]}, {"hover"})
        app.handle(Mouse("press", LIST - 1, 3, 0))
        self.assertEqual(app.section, "about")
        app.handle(Mouse("press", LIST - 1, 2, 0))
        self.assertEqual(app.section, "notifications")
        app.handle(Mouse("press", 0, 1, 0))
        self.assertEqual(app.section, "general")
        app.handle(Mouse("press", LIST, 2, 0))                                  # the rule: no one's
        self.assertEqual(app.section, "general")

    def test_it_opens_at_general(self):
        self.installed("0.3.0", "0.3.0")
        self.assertEqual(self.open(section=None).section, "general")

    def test_while_a_newer_version_is_out_it_opens_at_about(self):
        # More's dot leads here: what update.json knew when it opened, nothing asked first
        self.installed("0.3.0", "0.4.0")
        app = self.open({**FOUND, "latest": "0.4.0", "newer": True}, section=None)
        self.assertEqual((app.section, self.rows(app)[4]), ("about", line("↑ 0.4.0 is out · checked at 12:30")))

    def test_a_newer_version_found_while_open_moves_nothing(self):
        app = self.open({**FOUND, "latest": "0.4.0", "newer": True}, section=None)
        self.assertEqual(app.section, "general")


class About(Popup):
    def test_about_draws_each_state(self):
        # as settings.html's TUI box: the name and version, the license, the check's state, its switch, the notices
        # and the buttons, each on its own row in every state: nothing moves when the state changes
        up_to_date = self.rows(self.open())
        self.assertEqual(up_to_date, [
            " " * LIST + "│" + " " * (WIDE - LIST - 3) + CLOSE,
            line("herdr-fold 0.3.0", " General"),
            line("© 2026 princesshu · MIT License", " Notifications"),
            line(left=" About"),
            line("✓ Up to date · checked at 12:30"),
            line(),
            line(),
            line("[✓] Check for updates automatically"),
            line(),
            line("Third-party notices"),
            line(),
            line(" What's new   Check now"),
            line()])
        newer = self.rows(self.open({**FOUND, "latest": "0.4.0", "newer": True}))
        self.assertEqual(newer[4:6], [line("↑ 0.4.0 is out · checked at 12:30"),
                                      line("  git pull in its folder, then ./install.sh")])
        self.assertEqual(newer[11], line(" Release notes ↗   Check now"))
        by_hand = self.rows(self.open({**FOUND, "on": False, "latest": None, "checked": None}))
        self.assertEqual((by_hand[4], by_hand[7]),
                         (line("Checked by hand only"), line("[ ] Check for updates automatically")))
        failed = self.rows(self.open({**FOUND, "error": settings.update.FAILED}))
        self.assertEqual(failed[4], line("Couldn't check · last checked at 12:30"))
        never = self.rows(self.open({**FOUND, "latest": None, "checked": None, "error": settings.update.FAILED}))
        self.assertEqual(never[4], line("Couldn't check · GitHub did not answer"))
        earlier = self.rows(self.open({**FOUND, "checked": NOON - 86400}))
        day = time.localtime(NOON - 86400)
        self.assertEqual(earlier[4], line(f"✓ Up to date · checked on {time.strftime('%b', day)} {day.tm_mday}"))

    def test_a_newer_one_known_and_github_not_reached_says_both_in_the_sections_cells(self):
        # the how line whole, as with a newer one found: the section's 45 cells hold no longer one
        both = self.rows(self.open({**FOUND, "latest": "0.4.0", "newer": True, "error": settings.update.FAILED}))
        self.assertEqual(both[4:6], [line("Couldn't check · 0.4.0 is out"),
                                     line("  git pull in its folder, then ./install.sh")])

    def test_every_row_keeps_to_the_sections_cells(self):
        for found in (FOUND, {**FOUND, "latest": "0.4.0", "newer": True},
                      {**FOUND, "latest": "0.4.0", "newer": True, "error": settings.update.FAILED}):
            for row in self.rows(self.open(found)):
                self.assertNotIn("…", row)
                self.assertEqual(row[LIST:LIST + 2].rstrip(), "│")

    def test_the_colors_are_the_sidebars(self):
        # the mark green, a newer one's in the accent, the faint parts muted, the chosen button lit as a Confirm's
        app = self.open({**FOUND, "latest": "0.4.0", "newer": True})
        styles = {ch: style for ch, style in app.canvas.rows[4][AT:] if ch in "↑·"}
        self.assertEqual((styles["↑"].fg, styles["·"].fg), ("accent", "muted"))
        lit = app.canvas.rows[11][AT + 2][1]
        self.assertEqual((lit.fg, lit.bg, lit.bold), ("button_text", "button", True))
        self.assertEqual(app.canvas.rows[11][AT + len(" Release notes ↗   C")][1].bg, "input")
        self.assertEqual(self.open().canvas.rows[4][AT][1].fg, "added")

    def test_without_an_install_here_it_says_so(self):
        # a remote machine's sidebar: no version to compare, nothing to check; the license and the notices stay
        rows = self.rows(self.open({**FOUND, "version": None, "latest": None, "checked": None}))
        self.assertEqual(rows[1:5], [line("herdr-fold", " General"),
                                     line("© 2026 princesshu · MIT License", " Notifications"),
                                     line(left=" About"), line("Updated with the Mac that installed it")])
        self.assertEqual((rows[7], rows[9], rows[11]), (line(), line("Third-party notices"), line()))
        with mock.patch.object(settings.preview, "open_preview") as opened:        # the one thing Tab reaches
            app = self.open({**FOUND, "version": None, "latest": None, "checked": None})
            app.handle(Key("tab"))                                     # the author's name, then the notices
            app.handle(Key("tab"))
            app.handle(Key("enter"))
            self.settle(app)
        self.assertEqual(opened.call_args.args[3]["title"], "THIRD_PARTY_NOTICES.md")

    def test_space_switches_the_box_and_check_now_asks(self):
        check = mock.Mock(return_value=FOUND)
        app = self.open(check=check)
        with mock.patch.object(settings.update, "switch") as switch:
            check.return_value = {**FOUND, "on": False, "latest": None, "checked": None}
            app.handle(Key("char", " "))
            self.settle(app)
        switch.assert_called_once_with(False)
        self.assertEqual(self.rows(app)[7], line("[ ] Check for updates automatically"))
        check.return_value = {**FOUND, "on": False, "latest": "0.4.0", "newer": True}
        app.handle(Key("tab"))                                          # from What's new to Check now
        app.handle(Key("enter"))
        self.assertEqual(check.call_args.kwargs, {"force": True})
        self.settle(app)
        self.assertEqual(self.rows(app)[4], line("↑ 0.4.0 is out · checked at 12:30"))

    def test_a_look_shows_the_spinner_and_never_leaves_it_turning(self):
        # GitHub not reached on Check now: the spinner while it asks, then Couldn't check with the last good look's
        # time; a look that fails outright says so too; the box still switches meanwhile
        app = self.open()
        asking = mock.Mock(side_effect=lambda **_: time.sleep(0.2) or {**FOUND, "error": settings.update.FAILED})
        with mock.patch.object(settings.update, "check", asking), \
                mock.patch.object(settings.update, "switch") as switch:
            app.handle(Mouse("press", self.rows(app)[11].index("Check now"), 11, 0))
            app.draw()
            self.assertRegex(self.rows(app)[4][AT:], r"^[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏] Checking for updates…$")
            app.handle(Mouse("press", AT + 2, 7, 0))                      # the box, by a click
            app.draw()
            self.assertEqual(self.rows(app)[7], line("[ ] Check for updates automatically"))
            self.settle(app)
        switch.assert_called_once_with(False)
        self.assertEqual(self.rows(app)[4], line("Couldn't check · last checked at 12:30"))
        with mock.patch.object(settings.update, "check", side_effect=OSError("read-only")):
            app.handle(Mouse("press", self.rows(app)[11].index("Check now"), 11, 0))
            self.settle(app)
        self.assertEqual(self.rows(app)[4], line("Couldn't check · last checked at 12:30"))

    def test_whats_new_opens_the_changelog_at_this_version(self):
        with mock.patch.object(settings.update, "section", return_value=150), \
                mock.patch.object(settings.preview, "open_preview") as opened:
            app = self.open()
            app.handle(Key("enter"))                                    # What's new, chosen first
            self.settle(app)
        spec = opened.call_args.args[3]
        self.assertEqual((spec["title"], spec["line"]), ("CHANGELOG.md", 150))
        self.assertEqual(opened.call_args.args[1], "w1")                # the workspace it was opened from
        self.assertTrue(app.quit)

    def test_release_notes_and_the_notices_open_where_they_live(self):
        newer = {**FOUND, "latest": "0.4.0", "newer": True, "releases": "https://example.com/tag/v0.4.0"}
        with mock.patch.object(settings.media, "open_in_browser", return_value=True) as browser:
            app = self.open(newer)
            app.handle(Key("enter"))
        browser.assert_called_once_with("https://example.com/tag/v0.4.0")
        with mock.patch.object(settings.preview, "open_preview") as opened:
            app = self.open()
            app.handle(Mouse("press", AT + 2, 9, 0))
            self.settle(app)
        self.assertEqual(opened.call_args.args[3]["title"], "THIRD_PARTY_NOTICES.md")
        self.assertTrue(app.quit)

    def test_the_authors_name_links_to_their_page_as_the_license_says(self):
        # the plugin's own LICENSE names the author and their page (a fork's its own): the name a link as the notices
        app = self.open()
        start = self.rows(app)[2].index("princesshu")
        name = [style for _ch, style in app.canvas.rows[2][start:start + len("princesshu")]]
        self.assertEqual({(style.fg, style.underline) for style in name}, {("subtext", True)})
        self.assertEqual(app.canvas.rows[2][AT][1].fg, "muted")                 # © 2026, as the rest of the row
        app.handle(Mouse("move", start, 2, 3))
        app.draw()
        self.assertEqual(app.canvas.rows[2][start][1].fg, "accent")
        with mock.patch.object(settings.media, "open_in_browser", return_value=True) as browser:
            app.handle(Mouse("press", start + 3, 2, 0))
        browser.assert_called_once_with("https://github.com/princesshu")
        self.assertTrue(app.quit)
        fork = os.path.join(self.tmp, "LICENSE")
        with open(fork, "w", encoding="utf-8") as f:
            f.write("MIT License\n\nCopyright (c) 2027 Noa Berg (https://github.com/noa-berg)\n\nPermission...\n")
        with mock.patch.object(settings, "LICENSE", fork), \
                mock.patch.object(settings.media, "open_in_browser", return_value=True) as browser:
            app = self.open()
            app.handle(Key("backtab"))                                  # from What's new back to the notices
            app.handle(Key("backtab"))
            app.handle(Key("enter"))
        self.assertEqual(self.rows(app)[2], line("© 2027 Noa Berg · MIT License", " Notifications"))
        browser.assert_called_once_with("https://github.com/noa-berg")
        with mock.patch.object(settings, "LICENSE", os.path.join(self.tmp, "none")):
            self.assertEqual(self.rows(self.open())[2], line("", " Notifications"))    # no license: no row

    def test_tab_and_the_arrows_choose_among_the_buttons_and_the_links(self):
        # in reading order, round from the buttons at its foot: the author's name, the notices, the buttons
        app = self.open()
        for key, lit in (("tab", "Check now"), ("tab", "princesshu"), ("tab", "Third-party notices"),
                         ("tab", "What's new"), ("left", "Third-party notices"), ("backtab", "princesshu"),
                         ("right", "Third-party notices")):
            app.handle(Key(key))
            app.draw()
            row = {"princesshu": 2, "Third-party notices": 9}.get(lit, 11)
            start = self.rows(app)[row].index(lit)
            style = app.canvas.rows[row][start][1]
            self.assertEqual(style.fg, "button_text" if row == 11 else "accent", (key, lit))


class Frame(Popup):
    def test_x_esc_and_a_click_outside_close_it(self):
        # a click outside the popup: herdr gives the keys to the pane clicked, and the popup hears it lose them
        for section in ("general", "about"):
            for event in (Key("esc"), Mouse("press", WIDE - 1, 0, 0), Mouse("press", WIDE - 3, 0, 0), Focus(False)):
                app = self.open(section=section)
                app.handle(event)
                self.assertTrue(app.quit, event)
        app = self.open()
        app.handle(Focus(True))
        self.assertFalse(app.quit)

    def test_herdr_opens_it_as_big_as_its_rows_and_cells(self):
        # herdr's popup frame takes two rows and three columns, the third a blank one inside its right edge (herdr
        # 0.9.5, as drawn): its inside is the layout's, its right inset herdr's column; its title in herdr's frame
        with open(os.path.join(SRC, "plugins", "sidebar", "herdr-plugin.toml"), encoding="utf-8") as f:
            tables = f.read().split("[[panes]]")[1:]
        tables = [table.split("\n[[", 1)[0] for table in tables]
        popups = [table for table in tables if 'placement = "popup"' in table]
        ids = sorted(re.search(r'^id = "([^"]+)"$', table, re.M).group(1) for table in popups)
        self.assertEqual(ids, ["add-machine", "settings"])          # Settings and Add a machine: no About of its own
        table = next(table for table in popups if 'id = "settings"' in table)
        size = {key: int(value) for key, value in re.findall(r"^(width|height) = (\d+)$", table, re.M)}
        self.assertEqual((size["width"] - 3, size["height"] - 2), (WIDE, HIGH))
        for words in ('id = "settings"', 'title = "herdr-fold Settings"',
                      'command = ["/usr/bin/python3", "settings.py"]'):
            self.assertIn(words, table)
        self.assertEqual((settings.BUTTONS + 2, settings.LIST + 2 + settings.ROOM), (HIGH, WIDE))
        self.assertFalse(os.path.exists(os.path.join(SRC, "plugins", "sidebar", "about.py")))

    def test_the_close_button_lights_under_the_mouse_and_says_what_it_does(self):
        # as the row's icons alone: its three cells on the hover color, the glyph in the text's; the tinted line alone
        # (no row above it for a half row); its tip under it at its right edge after a moment, as the sidebar's tips
        now = [50.0]
        for section, under in (("general", line("Icons", " General")), ("about", line("herdr-fold 0.3.0", " General"))):
            app = self.open(section=section, clock=lambda: now[0])
            self.assertEqual([style.bg for _ch, style in app.canvas.rows[0][WIDE - 3:]], [None] * 3)
            self.assertEqual(app.canvas.rows[0][WIDE - 2][1], settings.Style(fg="subtext"))
            app.handle(Mouse("move", WIDE - 2, 0, 3))
            app.draw()
            self.assertEqual([style.bg for _ch, style in app.canvas.rows[0][WIDE - 3:]], ["hover"] * 3)
            self.assertEqual(app.canvas.rows[0][WIDE - 2][1], settings.Style(fg="text", bg="hover"))
            self.assertNotIn("Close (Esc)", self.rows(app)[1])
            now[0] += settings.TIP_DELAY
            self.assertTrue(app.tick())
            app.draw()
            self.assertTrue(self.rows(app)[1].endswith(" Close (Esc) ".rstrip()), self.rows(app)[1])
            self.assertEqual(app.canvas.rows[1][WIDE - 2][1], settings.Style(fg="text", bg="selection"))
            app.handle(Mouse("move", AT + 2, 4, 3))
            app.draw()
            self.assertEqual((self.rows(app)[1], app.canvas.rows[0][WIDE - 2][1].bg), (under, None))


if __name__ == "__main__":
    unittest.main()
