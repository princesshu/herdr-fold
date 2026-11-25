"""Tests for the sidebar's Usage view (src/plugins/sidebar/usage_view.py, the pane the Agent view's Usage head opens),
as usage.html's TUI usage pane: core's report in cells at 40, 60 and 100 of them, its chips and keys, the budget's form;
core's readers stood in for, a temporary home and state, nothing of an agent's read or written."""
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

from support import SRC, FakeTerminal, end_jobs, set_env, text

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import report as core  # noqa: E402
import usage_view  # noqa: E402
from screen import Style  # noqa: E402
from vt import Focus, Key, Mouse  # noqa: E402

OPUS, SONNET, HAIKU, CODEX = "#3987e5", "#d95926", "#199e70", "#c98500"
NAMES = {OPUS: "Opus 5.5", SONNET: "Sonnet 5.5", HAIKU: "Haiku 5.5", CODEX: "GPT-5 Codex"}
# usage.html's week, Nov 3 to 9: each day's cost by model, the legend's order
DAYS = ((12.0, 1.5, 0.5, 0), (25.0, 2.0, 1.0, 0.5), (9.0, 1.0, 0.5, 2.0), (24.0, 2.5, 1.0, 0), (26.0, 4.0, 2.0, 1.5),
        (0, 0, 0, 0), (10.0, 4.0, 1.5, 4.6))
AGENTS = [{"key": "claude", "name": "Claude", "plan": "Max", "installed": True},
          {"key": "codex", "name": "Codex", "plan": "API key", "installed": True}]


def month(today=18.4, pace=46.0, budget=50):
    line = f"~${today:.2f}{f' of ${budget}' if budget else ''} · on pace for ~${pace:.0f}"
    over = bool(budget) and max(pace, today) > budget
    return {"agent": "codex", "name": "Codex", "key": "Codex · API key", "id": "2026-11", "label": "November",
            "budget": budget, "days": 30, "day": 12, "today": today, "pace": pace, "line": line, "over": over,
            "level": ("bad" if today >= budget else "warn" if over else "ok") if budget else None,
            "pace_line": {"text": f"on pace for ~${pace:.0f} by November 30",
                          "narrow": f"on pace for ~${pace:.0f} by Nov 30"} if over else None,
            "end": "Nov 30", "color": CODEX}


def chat(title, space, cost, **more):
    return {"session": title[:4], "agent": "claude", "folder": f"/work/{space}", "title": title, "space": space,
            "models": [{"name": "Opus 5.5", "color": OPUS}], "turns": 38, "tokens": 1_240_000, "cache": 82,
            "cost": cost, "kind": "value", **more}


def reported(months=None, none=None, more=0):
    """A week as core's report() tells it: usage.html's Riport, its figures and core's own words."""
    months = [month()] if months is None else months
    daily = [{"day": f"2026-11-{n + 3:02d}", "label": f"Nov {n + 3}", "total": sum(costs), "models": [
        {"model": name, "name": name, "color": color, "cost": cost}
        for (color, name), cost in zip(NAMES.items(), costs) if cost]} for n, costs in enumerate(DAYS)]
    return {
        "period": {"id": "7d", "label": "7 days"}, "prices_as_of": "Nov 9, 2026", "none": none,
        "filters": {"periods": [{"id": id, "label": label} for id, label in (
                        ("today", "Today"), ("7d", "7 days"), ("30d", "30 days"), ("month", "November"))],
                    "agents": [{"id": None, "label": "All agents"}, {"id": "claude", "label": "Claude"},
                               {"id": "codex", "label": "Codex"}]},
        "summary": [
            {"key": "Claude · Max plan", "agent": "claude", "value": 130.9, "text": "~$130.90", "unit": "API value",
             "line": "no charge on the plan"},
            {"key": "Codex · API key", "agent": "codex", "value": 46.08, "text": "~$46.08", "unit": "spent in 7 days",
             "line": ""},
            {"key": "Tokens", "value": 38_200_000, "text": "38.2M", "line": "81% read from cache"}],
        "daily": daily, "top": {"day": "2026-11-07", "label": "Nov 7", "total": 33.5},
        "legend": [{"model": name, "name": name, "color": color, "cost": 1.0, "share": share}
                   for (color, name), share in zip(NAMES.items(), (83, 11, 5, 6))],
        "months": months, "month": months[0] if months else None,
        "projects": [{"folder": f"/work/{name}", "name": name, "cost": cost, "tokens": 1000}
                     for name, cost in (("lumen-api", 84.2), ("harbor-web", 41.1), ("tidepool", 14.2))],
        "chats": [chat("Fix the page past the last one", "lumen-api", 31.4),
                  chat("Login redirect fix", "harbor-web", 24.1),
                  chat("Document the error format", "lumen-api", 12.3),
                  chat("Plan the tide table", "tidepool", None, cache=None)],
        "more": more,
        "models": [{"model": "o", "name": "Opus 5.5", "color": OPUS, "agent": "Claude", "input": 1_200_000,
                    "write": 3_400_000, "read": 30_100_000, "output": 410_000, "cost": 118.2, "kind": "value",
                    "text": "$118.20"},
                   {"model": "h", "name": "Haiku 5.5", "color": HAIKU, "agent": "Claude · subagents", "input": 90_000,
                    "write": 0, "read": 1_100_000, "output": 12_000, "cost": 4.1, "kind": "value", "text": "$4.10"},
                   {"model": "x", "name": "Tide 1", "color": "#d55181", "agent": "Codex", "input": 5000, "write": 0,
                    "read": 0, "output": 700, "cost": None, "kind": "spent", "text": "no price"}],
        "columns": core.COLUMNS,
        "words": {"daily": "Per day, by model", "month": "November, against its budget", "projects": "By project",
                  "projects_note": "API value and spend combined", "chats": "Chats", "chats_note": "by cost",
                  "models": "Models", "budget": "Budget…", "export": "Export CSV", "no_price": "no price",
                  "foot": "~ estimated from token counts at Anthropic's and OpenAI's list prices (Nov 9, 2026); on "
                          "a plan, what the same use would cost on the API"}}


class View(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.addCleanup(time.tzset)
        set_env(self, HOME=os.path.join(self.tmp, "home"), TZ="UTC")
        time.tzset()
        self.addCleanup(end_jobs)
        self.asked, self.answer, self.left = [], reported(), [0]
        read = mock.patch.object(usage_view, "figures", lambda period, agents, theme, home, agent=None, state=None: (
            self.asked.append((period, agent)), {"report": self.answer, "left": self.left[0]})[1])
        agents = mock.patch.object(usage_view.agent_state, "machine_agents", lambda home: [dict(one) for one in AGENTS])
        for patch in (read, agents):
            patch.start()
            self.addCleanup(patch.stop)
        self.now = [100.0]

    def open(self, cells=60, rows=60):
        app = usage_view.UsageView(FakeTerminal(cells, rows), mock.Mock(), os.path.join(self.tmp, "plugin"),
                                   clock=lambda: self.now[0], home=os.path.join(self.tmp, "home"),
                                   state=os.path.join(self.tmp, "state"))
        self.settle(app)
        return app

    def settle(self, app):
        for _ in range(2):
            end_jobs()
            app.collect()
        app.draw()

    def rows(self, app):
        return [text(app.canvas, y).rstrip() for y in range(app.canvas.height)]

    def at(self, app, words):
        for y, line in enumerate(self.rows(app)):
            if words in line:
                return y, line.index(words)
        self.fail(f"{words!r} not drawn:\n" + "\n".join(self.rows(app)))

    def look(self, app, words):
        y, x = self.at(app, words)
        return app.canvas.rows[y][x][1]

    def press(self, app, *keys):
        for key in keys:
            app.handle(Key(key) if len(key) > 1 else Key("char", key))
        self.settle(app)

    def click(self, app, words, button=0):
        y, x = self.at(app, words)
        app.handle(Mouse("press", x, y, button))
        self.settle(app)

    # --- the report in cells

    def test_the_report_at_60_cells_as_the_mockups_usage_pane(self):
        rows = self.rows(self.open(60))
        self.assertTrue(rows[0].startswith("  Today   7 days   30 days   November "), rows[0])
        self.assertEqual(rows[1], "  All agents   Claude   Codex")                  # no room beside the periods
        self.assertEqual(rows[2:9], [
            "",
            " Claude · Max plan  ~$130.90 API value",
            "   no charge on the plan",
            " Codex · API key    ~$46.08 spent in 7 days",
            " Tokens             38.2M",
            "   81% read from cache",
            ""])
        self.assertEqual(rows[9:18], [
            " Per day, by model                       top ~$33.50, Nov 7",
            "     ▂   ▁ ▄",
            "     ▆   ▅ ▇",
            "   ▁ █   █ █   ▁",
            "   ▆ █ ▇ █ █   ▄",
            "   █ █ █ █ █   █",
            "   3 4 5 6 7 8 9",
            " ■ Opus 5.5 83%  ■ Sonnet 5.5 11%  ■ Haiku 5.5 5%",
            " ■ GPT-5 Codex 6%"])
        self.assertEqual(rows[18:22], [
            "",
            " November, against its budget               Codex · API key",
            " ▰▰▰▰▰▰▰▰▱▱▱▱▱▱▱▱▱▱▱▱▱│▱  ~$18.40 of $50 · on pace for ~$46",
            "  Budget…"])
        self.assertEqual(rows[22:27], [
            "",
            " By project                    API value and spend combined",
            " lumen-api   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰  $84.20",
            " harbor-web  ▰▰▰▰▰▰▰▰▰▰▰▰              $41.10",
            " tidepool    ▰▰▰▰                      $14.20"])
        self.assertEqual(rows[27:33], [
            "",
            " Chats by cost                                         Cost",
            " Fix the page past the last one                      $31.40",
            " Login redirect fix                                  $24.10",
            " Document the error format                           $12.30",
            " Plan the tide table                               no price"])
        self.assertEqual(rows[33:42], [
            "",
            " Models           Cache write  Cache read  Output      Cost",
            " ■ Opus 5.5              3.4M       30.1M    410k   $118.20",
            " ■ Haiku 5.5                –        1.1M   12.0k     $4.10",
            " ■ Tide 1                   –           –     700  no price",
            "",
            " ~ estimated from token counts at Anthropic's and OpenAI's",
            " list prices (Nov 9, 2026); on a plan, what the same use",
            " would cost on the API"])
        self.assertTrue(all(len(row) <= 59 for row in rows[1:]), rows)          # a cell in from the right too
        self.assertEqual([row for row in rows if "conversation" in row.lower()], [])    # the glossary's chat

    def test_at_100_cells_the_tables_show_every_column_names_left_figures_right(self):
        rows = self.rows(self.open(100))
        self.assertTrue(rows[0].startswith("  Today   7 days   30 days   November     All agents   Claude   Codex"))
        y = self.at(self.open(100), " Chats")[0]
        self.assertEqual(rows[y:y + 5], [
            " Chats by cost".ljust(57) + "Space       Turns  Tokens  Cache      Cost",
            " Fix the page past the last one".ljust(57) + "lumen-api      38    1.2M    82%    $31.40",
            " Login redirect fix".ljust(57) + "harbor-web     38    1.2M    82%    $24.10",
            " Document the error format".ljust(57) + "lumen-api      38    1.2M    82%    $12.30",
            " Plan the tide table".ljust(57) + "tidepool       38    1.2M      –  no price"])
        self.assertEqual(rows[y + 6:y + 10], [
            " Models                        Agent               Input  Cache write  Cache read  Output      Cost",
            " ■ Opus 5.5                    Claude               1.2M         3.4M       30.1M    410k   $118.20",
            " ■ Haiku 5.5                   Claude · subagents  90.0k            –        1.1M   12.0k     $4.10",
            " ■ Tide 1                      Codex                5.0k            –           –     700  no price"])
        self.assertIn(" ■ Opus 5.5 83%  ■ Sonnet 5.5 11%  ■ Haiku 5.5 5%  ■ GPT-5 Codex 6%", rows)    # one line there
        self.assertIn(" lumen-api   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰  $84.20", rows)               # no wider than at 60
        self.assertEqual(rows[y + 11:y + 13], [" ~ estimated from token counts at Anthropic's and OpenAI's list "
                                               "prices (Nov 9, 2026); on a plan,", " what the same use would cost "
                                               "on the API"])

    def test_a_pane_narrower_than_the_chips_says_nov_and_puts_the_agents_under_the_periods(self):
        rows = self.rows(self.open(40))
        self.assertTrue(rows[0].startswith("  Today   7 days   30 days   Nov "), rows[0])
        self.assertEqual(rows[1:4], ["  All agents   Claude   Codex", "", " Claude · Max plan  ~$130.90 API value"])
        self.assertEqual(rows[5], " Codex · API key    ~$46.08 spent in 7…")              # cut, never past it
        self.assertTrue(all(len(row) <= 39 for row in rows[1:]), rows)
        y = self.at(self.open(40), " By project")[0]
        self.assertEqual(rows[y + 1], " lumen-api   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰  $84.20")       # the bars give way

    def test_only_the_models_wear_color_figures_lit_notes_dim(self):
        app = self.open()
        self.assertEqual([self.look(app, words) for words in (
            "Claude · Max plan", "~$130.90", "API value", "no charge", "Per day", "top ~$33.50", "3 4 5",
            "Opus 5.5 83%", "Codex · API key  ", "By project", "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰  $84", "Cost",
            "no price", "~ estimated")],
            [Style(fg="subtext"), Style(fg="text", bold=True), Style(fg="muted"), Style(fg="muted"),
             Style(fg="text", bold=True), Style(fg="muted"), Style(fg="muted"), Style(fg="subtext"),
             Style(fg="subtext"), Style(fg="text", bold=True), Style(fg="muted"), Style(fg="muted"),
             Style(fg="muted"), Style(fg="muted")])
        y, x = self.at(app, "■ Opus 5.5 83%")
        self.assertEqual([app.canvas.rows[y][at][1] for at in (x, x + 16, x + 34)],
                         [Style(fg=OPUS), Style(fg=SONNET), Style(fg=HAIKU)])
        y, x = self.at(app, "█ █ █ █ █   █")
        self.assertEqual(app.canvas.rows[y][x][1], Style(fg=OPUS))
        self.assertEqual(self.look(app, "▰▰▰▰▰▰▰▰▱"), Style(fg="added"))
        self.assertEqual(self.look(app, "│▱"), Style(fg="text"))                # the pace's mark

    def test_a_days_models_are_stacked_in_the_legends_order_two_meeting_in_a_cell_share_it(self):
        day = {"total": 40.0, "models": [{"cost": 20.0, "color": OPUS}, {"cost": 15.0, "color": SONNET},
                                         {"cost": 5.0, "color": CODEX}]}
        half = {"total": 20.0, "models": [{"cost": 19.0, "color": OPUS}, {"cost": 1.0, "color": HAIKU}]}
        tiny = {"total": 0.01, "models": [{"cost": 0.01, "color": HAIKU}]}
        none = {"total": 0, "models": []}
        whole, low, least, empty = usage_view.chart([day, half, tiny, none])
        self.assertEqual(whole, [("█", OPUS, None), ("█", OPUS, None), ("▄", OPUS, SONNET), ("█", SONNET, None),
                                 ("▃", SONNET, CODEX)])
        self.assertEqual(low, [("█", OPUS, None), ("█", OPUS, None), ("▄", OPUS, None)] + [(" ", None, None)] * 2)
        self.assertEqual((least[0], empty[0]), (("▁", HAIKU, None), (" ", None, None)))     # never empty with a cost

    def test_thirty_days_stand_a_cell_apart_where_they_fit_their_numbers_clear_of_each_other(self):
        daily = [{"label": f"Nov {n + 1}"} for n in range(30)]
        self.assertEqual(usage_view.day_labels(daily[:9], 2), [(n * 2, str(n + 1)) for n in range(9)])
        self.assertEqual(usage_view.day_labels(daily[8:14], 2), [(0, "9"), (4, "11"), (10, "14")])
        self.assertEqual([number for _, number in usage_view.day_labels(daily, 1)],
                         ["1", "5", "10", "15", "20", "25", "30"])
        self.answer["daily"] = [{"day": f"2026-11-{n + 1:02d}", "label": f"Nov {n + 1}", "total": 1.0 + n,
                                 "models": [{"model": "o", "name": "Opus 5.5", "color": OPUS, "cost": 1.0 + n}]}
                                for n in range(30)]
        for cells, wide in ((60, 30), (100, 59)):                              # at 60 no room for a cell between
            app = self.open(cells)
            self.assertEqual(len(self.rows(app)[self.at(app, "Per day")[0] + 5]), 3 + wide)

    def test_the_first_day_a_months_first_and_the_last_day_are_always_numbered(self):
        # 30 days over a month's end, as the finding had them: Oct 21 to Nov 19, the costliest day the last
        daily = [{"label": f"Oct {n}"} for n in range(21, 32)] + [{"label": f"Nov {n}"} for n in range(1, 20)]
        said = [number for _, number in usage_view.day_labels(daily, 2)]
        self.assertEqual(said, ["21", "23", "25", "27", "29", "1", "3", "5", "7", "9", "11", "13", "15", "17", "19"])
        self.assertEqual(usage_view.day_labels(daily, 2)[5], (22, "1"))             # the 31st gives way to the 1st
        self.assertEqual([number for _, number in usage_view.day_labels(daily, 1)],
                         ["21", "25", "1", "5", "10", "15", "19"])
        # an end that is no step's day is numbered all the same, the step's day beside it left out
        self.assertEqual([number for _, number in usage_view.day_labels(daily[1:-1], 2)],
                         ["22", "25", "27", "29", "1", "3", "5", "7", "9", "11", "13", "15", "18"])
        for days, pitch in ((daily, 2), (daily, 1), (daily[1:-1], 2), (daily[10:13], 1), (daily[:2], 1), (daily, 3)):
            with self.subTest((len(days), pitch)):
                found = usage_view.day_labels(days, pitch)
                self.assertEqual(found[-1], ((len(days) - 1) * pitch, days[-1]["label"].split()[-1]))
                for (at, number), (after, _) in zip(found, found[1:]):
                    self.assertGreater(after, at + len(number))                 # a cell clear, never colliding
        self.assertEqual(usage_view.day_labels([], 2), [])
        self.assertEqual(usage_view.day_labels(daily[:1], 2), [(0, "21")])
        self.assertEqual(usage_view.day_labels(daily[10:13], 2), [(0, "31"), (4, "2")])     # the ends before the 1st

    def test_a_month_over_its_pace_is_yellow_its_mark_past_the_budgets_end(self):
        self.answer = reported([month(45.1, 58.0)])
        app = self.open()
        y = self.at(app, "November, against")[0]
        self.assertEqual(self.rows(app)[y + 1], " ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▱▱  │  ~$45.10 of $50 · on pace for ~$58")
        self.assertEqual({self.look(app, words) for words in ("▰▰▰▰▰▰▰▰▰▰▰▱▱", "~$45.10 of $50")},
                         {Style(fg="modified")})
        self.assertEqual(usage_view.pace_bar(month()), (9, 24, 22))
        self.assertEqual(usage_view.pace_bar(month(60.0, 150.0)), (10, 8, 23))  # spent past it: the bar runs on

    def test_a_month_with_no_budget_is_its_words_alone_under_its_name(self):
        self.answer = reported([month(budget=None)])
        app = self.open()
        y = next(y for y, row in enumerate(self.rows(app)) if row.startswith(" November "))
        self.assertEqual(self.rows(app)[y:y + 3], [" November" + "Codex · API key".rjust(50),
                                                   " ~$18.40 · on pace for ~$46", "  Budget…"])

    # --- the chips and the keys

    def test_the_chosen_chips_are_bold_on_the_hover_fill_tab_steps_the_periods_a_the_agents(self):
        app = self.open()
        lit = Style(fg="text", bg="hover", bold=True)
        self.assertEqual([self.look(app, words) for words in ("7 days", "30 days", "All agents", "Claude  ")],
                         [lit, Style(fg="subtext"), lit, Style(fg="subtext")])
        self.assertEqual(self.asked, [("7d", None)])
        self.press(app, "tab")
        self.assertEqual((self.look(app, "30 days"), self.asked[-1]), (lit, ("30d", None)))
        self.press(app, "tab", "tab", "backtab")
        self.assertEqual((app.period, self.asked[-1]), ("month", ("month", None)))
        self.press(app, "a")
        self.assertEqual((self.look(app, "Claude  "), self.asked[-1]), (lit, ("month", "claude")))
        self.press(app, "a", "a")
        self.assertEqual((app.agent, self.asked[-1]), (None, ("month", None)))

    def test_a_press_on_a_chip_chooses_it_and_the_chosen_one_asks_nothing(self):
        app = self.open()
        self.click(app, "30 days")
        self.click(app, "Codex")
        self.assertEqual(self.asked, [("7d", None), ("30d", None), ("30d", "codex")])
        self.click(app, "30 days")
        self.assertEqual(len(self.asked), 3)

    def test_it_opens_on_seven_days_as_the_app_and_a_chip_under_the_mouse_is_lit_in_the_text_color(self):
        app = self.open()
        self.assertEqual(app.period, "7d")
        y, x = self.at(app, "30 days")
        app.handle(Mouse("move", x, y, 0))
        app.draw()
        self.assertEqual(self.look(app, "30 days"), Style(fg="text"))

    def test_the_arrows_and_the_wheel_scroll_under_the_chips_never_past_the_last_line(self):
        app = self.open(rows=12)
        self.assertEqual(self.rows(app)[3], " Claude · Max plan  ~$130.90 API value")
        self.press(app, "down", "down")
        self.assertEqual(self.rows(app)[3], " Codex · API key    ~$46.08 spent in 7 days")
        self.assertTrue(self.rows(app)[0].startswith("  Today"))                # the chips stay
        self.press(app, "end")
        self.assertEqual(self.rows(app)[11], " would cost on the API")
        self.press(app, "pagedown", "home")
        app.handle(Mouse("wheel_down", 5, 5))
        self.settle(app)
        self.assertEqual(self.rows(app)[3], " Tokens             38.2M")                        # three lines on
        self.press(app, "pageup")
        self.assertEqual(app.top, 0)

    def test_esc_q_its_close_button_and_a_click_outside_close_it(self):
        for way in (Key("esc"), Key("char", "q"), Focus(False), Mouse("press", 58, 0, 0)):
            app = self.open()
            self.assertFalse(app.quit)
            app.handle(way)
            self.assertTrue(app.quit, way)
        app = self.open()
        app.handle(Focus(True))
        self.assertFalse(app.quit)

    def test_the_close_buttons_tip_comes_after_a_rest_on_it(self):
        app = self.open()
        app.handle(Mouse("move", 58, 0, 3))
        self.assertEqual((app.tick(), app.tip), (False, False))
        self.now[0] += usage_view.TIP_DELAY
        self.assertTrue(app.tick())
        app.draw()
        self.assertTrue(self.rows(app)[1].endswith(" Close (Esc)"), self.rows(app)[1])

    # --- what stands in the report's place

    def test_before_the_report_it_says_loading_then_what_core_says_of_an_empty_period(self):
        self.answer = reported(none="Nothing used in this period")
        app = usage_view.UsageView(FakeTerminal(60, 20), mock.Mock(), os.path.join(self.tmp, "plugin"),
                                   clock=lambda: self.now[0], home=self.tmp, state=os.path.join(self.tmp, "state"))
        app.draw()
        self.assertEqual(self.rows(app)[3][3:], "Loading usage…")
        self.assertTrue(self.rows(app)[0].startswith("  Today   7 days   30 days   November "))
        self.assertEqual(self.rows(app)[1], "  All agents   Claude   Codex")
        self.settle(app)
        self.assertEqual(self.rows(app)[3:5], [" Nothing used in this period", ""])
        self.assertEqual(self.look(app, "Nothing used"), Style(fg="muted"))

    def test_while_chats_are_read_it_says_so_and_reads_on_at_once(self):
        self.left[0] = 4096
        self.answer = reported(none="Nothing used in this period")
        app = usage_view.UsageView(FakeTerminal(60, 20), mock.Mock(), os.path.join(self.tmp, "plugin"),
                                   clock=lambda: self.now[0], home=self.tmp, state=os.path.join(self.tmp, "state"))
        end_jobs()
        app.collect()
        app.draw()
        self.assertEqual(self.rows(app)[3][3:], "Reading chats…")
        self.assertIn("report", app.running)                                    # the next look, not a minute later
        self.left[0], self.answer = 0, reported()
        self.settle(app)
        self.assertEqual((len(self.asked) > 1, app.reading, self.rows(app)[3][:18]),
                         (True, False, " Claude · Max plan"))

    def test_a_read_that_fails_says_so_in_red_and_the_next_one_clears_it(self):
        failing = mock.patch.object(usage_view, "figures", mock.Mock(side_effect=OSError("no index")))
        failing.start()
        app = self.open()
        failing.stop()
        self.assertEqual(self.rows(app)[3], " Couldn't read the usage: no index")
        self.assertEqual(self.look(app, "Couldn't"), Style(fg="deleted"))
        self.now[0] += usage_view.POLL
        app.tick()
        self.settle(app)
        self.assertEqual(self.rows(app)[3][:18], " Claude · Max plan")

    def test_it_reads_again_every_minute_while_open(self):
        app = self.open()
        self.assertEqual((app.tick(), len(self.asked)), (False, 1))
        self.assertEqual(min(app.deadlines()), 100.0 + usage_view.POLL)
        self.now[0] += usage_view.POLL
        app.tick()
        self.settle(app)
        self.assertEqual(len(self.asked), 2)

    # --- the budget

    def kept(self):
        return core.budget(os.path.join(self.tmp, "state"))

    def test_enter_edits_the_budget_in_the_months_place_and_enter_keeps_it_in_herdr_folds_own_state(self):
        core.set_budget(os.path.join(self.tmp, "state"), "codex", 50)
        app = self.open()
        self.press(app, "enter")
        y = self.at(app, "Monthly budget")[0]
        self.assertEqual(self.rows(app)[y - 1:y + 3], [
            " ▰▰▰▰▰▰▰▰▱▱▱▱▱▱▱▱▱▱▱▱▱│▱  ~$18.40 of $50 · on pace for ~$46", " Monthly budget",
            " Codex  $ 50           a month", "  Save   Cancel"])
        self.assertEqual(self.look(app, "Save"), Style(fg="button_text", bg="button", bold=True))
        self.assertEqual(app.canvas.cursor, (y + 1, 12))                        # the keys are in the field
        self.press(app, "backspace", "backspace", "7", "5", ".", "5")
        self.assertEqual(self.rows(app)[y + 1], " Codex  $ 75.5         a month")
        asked = len(self.asked)
        self.press(app, "enter")
        self.assertEqual((self.kept(), app.form, len(self.asked)), ({"codex": 75.5}, None, asked + 1))
        self.assertNotIn("Monthly budget", "\n".join(self.rows(app)))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "home", ".codex")))      # nothing of Codex's

    def test_what_is_no_amount_is_said_under_the_field_and_nothing_is_kept(self):
        app = self.open()
        self.click(app, "Budget…")
        self.press(app, "f", "i", "f", "t", "y", "enter")
        y = self.at(app, "Monthly budget")[0]
        self.assertEqual(self.rows(app)[y + 2], " Codex's is not an amount")
        self.assertEqual((self.look(app, "Codex's is"), self.kept()), (Style(fg="deleted"), {}))
        self.press(app, "x")
        self.assertNotIn("not an amount", "\n".join(self.rows(app)))            # typed over

    def test_an_empty_field_takes_the_budget_away_esc_and_cancel_leave_it_as_it_was(self):
        state = os.path.join(self.tmp, "state")
        core.set_budget(state, "codex", 50)
        app = self.open()
        self.press(app, "enter", "5", "esc")
        self.assertEqual((app.form, app.quit, self.kept()), (None, False, {"codex": 50}))     # Esc left the form alone
        self.press(app, "enter", "tab", "tab", "enter")                         # on Cancel
        self.assertEqual((app.form, self.kept()), (None, {"codex": 50}))
        self.press(app, "enter", "backspace", "backspace")
        self.click(app, "Save")
        self.assertEqual((app.form, self.kept()), (None, {}))

    def test_with_every_agent_on_a_plan_there_is_no_budget_to_set(self):
        plans = mock.patch.object(usage_view.agent_state, "machine_agents", lambda home: [
            {**one, "plan": "Plus" if one["key"] == "codex" else one["plan"]} for one in AGENTS])
        plans.start()
        self.addCleanup(plans.stop)
        self.answer = reported([])
        app = self.open()
        self.press(app, "enter")
        self.assertIsNone(app.form)
        self.assertNotIn("Budget…", "\n".join(self.rows(app)))

    def test_with_nothing_spent_this_month_enter_still_opens_the_form(self):
        self.answer = reported([])
        app = self.open()
        self.press(app, "enter")
        y = self.at(app, "Monthly budget")[0]
        self.assertEqual(self.rows(app)[y + 1], " Codex  $              a month")


class Reading(unittest.TestCase):
    """The view's own read: core's indexes and report in a temporary home, Claude's files as they were."""

    def test_it_reads_the_sessions_into_herdr_folds_state_and_reports_them_an_agents_alone_too(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        home, state, now = os.path.join(tmp, "home"), os.path.join(tmp, "state"), int(time.time())
        folder = os.path.join(home, ".claude", "projects", "-work-lumen-api")
        os.makedirs(folder)
        line = ('{"type":"assistant","timestamp":"%s","cwd":"/work/lumen-api","message":{"id":"msg_1","model":'
                '"claude-opus-5-5","usage":{"input_tokens":200000,"output_tokens":40000}}}\n'
                % time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(now - 60)))
        with open(os.path.join(folder, "c1.jsonl"), "w", encoding="utf-8") as f:
            f.write(line)
        found = usage_view.figures("7d", AGENTS, (None, None), home, state=state)
        self.assertEqual((found["left"], [one["name"] for one in found["report"]["projects"]]), (0, ["lumen-api"]))
        self.assertEqual(found["report"]["summary"][0]["unit"], "API value")
        self.assertEqual(usage_view.figures("7d", AGENTS, (None, None), home, "codex", state)["report"]["none"],
                         "Nothing used in this period")
        with open(os.path.join(folder, "c1.jsonl"), encoding="utf-8") as f:
            self.assertEqual(f.read(), line)
        self.assertEqual(sorted(os.listdir(folder)), ["c1.jsonl"])
        self.assertNotIn("commits-index.json", os.listdir(state))              # no commits read for a count
