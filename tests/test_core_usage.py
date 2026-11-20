"""Tests for core/usage.py in a temporary HOME: the agents' limits from herdr-fold's own readings, Claude's cache and
Codex's newest chat, the newest per agent, a limit past its reset left out, an agent with none left out; nothing of the
agents' files written; both status lines keep the same shape."""
import contextlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

from support import PACKAGE, set_env

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import chat_hook  # noqa: E402
import usage  # noqa: E402

NOW = 1794571200                # Friday, 13 November 2026, 12:00 UTC
HOUR, DAY = 3600, 86400
FIVE = NOW + 2 * HOUR + 46 * 60                         # the 5-hour window's reset: 14:46 UTC
WEEK = NOW + 3 * DAY + 5 * HOUR                         # the weekly one's: Monday, 16 November, 17:00 UTC
ACCOUNT = "00000000-0000-4000-8000-00000000c1a0"        # an invented account id, never answered
STATUSLINE = os.path.join(PACKAGE, "src", "statusline.py")


def windows(five=None, week=None):
    """A reading's windows: FIVE and WEEK each (used, resets) or None."""
    return {name: None if one is None else {"used": one[0], "resets": one[1]}
            for name, one in (("five_hour", five), ("week", week))}


class Home(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        set_env(self, HOME=self.home)

    def write(self, rel, text, mtime=None):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def claude(self, five=None, week=None, fetched=NOW):
        """Claude's ~/.claude.json with its cached limits, as Claude 2.1.325 keeps them (FIVE and WEEK each (percent,
        reset text)), fetched at FETCHED."""
        used = {name: None if one is None else {"utilization": one[0], "resets_at": one[1], "limit_dollars": None,
                                                "used_dollars": None, "locked_reason": None}
                for name, one in (("five_hour", five), ("seven_day", week))}
        self.write(".claude.json", json.dumps({"numStartups": 12, "cachedUsageUtilization": {
            "fetchedAtMs": fetched * 1000 + 250, "accountUuid": ACCOUNT,
            "utilization": {**used, "seven_day_opus": None, "extra_usage": {"is_enabled": False}}}}))

    def codex(self, name, entries, mtime):
        """A Codex chat (rollout) with ENTRIES after its first line, changed at MTIME."""
        lines = [{"timestamp": "2026-11-13T09:00:00.000Z", "type": "session_meta",
                  "payload": {"id": name, "cwd": "/work/tidepool", "source": "cli"}}] + entries
        rel = os.path.join(".codex", "sessions", "2026", "11", "13", f"rollout-2026-11-13T09-00-00-{name}.jsonl")
        return self.write(rel, "".join(json.dumps(line) + "\n" for line in lines), mtime)

    def limits(self, now=NOW):
        return usage.limits(self.home, now)


def token_count(at, primary=None, secondary=None, limit_id="codex"):
    """A Codex token_count event at AT (seconds), its rate_limits' windows PRIMARY and SECONDARY each (percent,
    minutes, reset) or None."""
    def one(window):
        return None if window is None else {"used_percent": window[0], "window_minutes": window[1],
                                            "resets_at": window[2]}
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(at))
    return {"timestamp": stamp, "type": "event_msg", "payload": {
        "type": "token_count", "info": {"total_token_usage": {"input_tokens": 5120, "output_tokens": 840}},
        "rate_limits": {"limit_id": limit_id, "limit_name": None, "primary": one(primary),
                        "secondary": one(secondary), "credits": {"has_credits": False}, "plan_type": "plus"}}}


class Sources(Home):
    def test_herdr_folds_own_reading(self):
        self.assertTrue(usage.keep("claude", windows((72, FIVE), (16, WEEK)), NOW - 60))
        self.assertEqual(self.limits(), [{"agent": "claude", **windows((72, FIVE), (16, WEEK)), "at": NOW - 60,
                                          "source": "status"}])

    def test_claudes_own_cache_with_its_age_and_never_its_account(self):
        self.claude(five=(43, "2026-11-13T14:46:00.512340+00:00"), week=(9, "2026-11-16T18:00:00+01:00"),
                    fetched=NOW - 43 * 60)
        found = self.limits()
        self.assertEqual(found, [{"agent": "claude", **windows((43, FIVE), (9, WEEK)), "at": NOW - 43 * 60,
                                  "source": "claude"}])
        self.assertNotIn(ACCOUNT, json.dumps(found))

    def test_a_reset_as_text_or_seconds_else_unknown(self):
        for written in ("2026-11-13T14:46:00Z", "2026-11-13T14:46:00.5Z", "2026-11-13T09:46:00-05:00", FIVE):
            with self.subTest(written=written):
                self.claude(five=(30, written))
                self.assertEqual(self.limits()[0]["five_hour"], {"used": 30, "resets": FIVE})
        for written in ("2026-13-40T14:46:00Z", "in 2 hours", True, None):
            with self.subTest(written=written):
                self.claude(five=(30, written))
                self.assertEqual(self.limits()[0]["five_hour"], {"used": 30, "resets": None})

    def test_codexs_newest_chat_by_its_windows_length(self):
        self.codex("a1", [token_count(NOW - 120, primary=(61.6, 300, FIVE), secondary=(23.2, 10080, WEEK))], NOW - 100)
        self.assertEqual(self.limits(), [{"agent": "codex", **windows((62, FIVE), (23, WEEK)), "at": NOW - 120,
                                          "source": "codex"}])

    def test_codexs_primary_as_the_week(self):
        # Codex 0.166 on a plan with a weekly limit alone: its primary window is the week's
        self.codex("b2", [token_count(NOW - 120, primary=(37.0, 10080, WEEK))], NOW - 100)
        self.assertEqual(self.limits(), [{"agent": "codex", **windows(None, (37, WEEK)), "at": NOW - 120,
                                          "source": "codex"}])

    def test_codexs_last_reading_with_a_window(self):
        # a premium model's own limit tells no window: the reading before it holds
        self.codex("c3", [token_count(NOW - 900, primary=(30.0, 10080, WEEK)),
                          token_count(NOW - 600, primary=(31.0, 10080, WEEK)),
                          token_count(NOW - 300, limit_id="premium")], NOW - 300)
        self.assertEqual(self.limits()[0]["week"], {"used": 31, "resets": WEEK})
        self.assertEqual(self.limits()[0]["at"], NOW - 600)

    def test_a_newer_codex_chat_with_no_answer_yet_is_passed_over(self):
        self.codex("d4", [token_count(NOW - 900, primary=(40.0, 10080, WEEK))], NOW - 800)
        self.codex("e5", [], NOW - 10)
        self.assertEqual(self.limits()[0]["week"], {"used": 40, "resets": WEEK})

    def test_an_earlier_codex_reset_told_as_seconds_left(self):
        event = token_count(NOW - 60)
        event["payload"]["rate_limits"]["primary"] = {"used_percent": 12.0, "window_minutes": 300,
                                                      "resets_in_seconds": FIVE - (NOW - 60)}
        self.codex("f6", [event], NOW - 60)
        self.assertEqual(self.limits()[0]["five_hour"], {"used": 12, "resets": FIVE})

    def test_the_newest_reading_wins(self):
        usage.keep("claude", windows((40, FIVE), (10, WEEK)), NOW - 600)
        self.claude(five=(45, "2026-11-13T14:46:00Z"), week=(11, "2026-11-16T17:00:00Z"), fetched=NOW - 60)
        self.assertEqual((self.limits()[0]["source"], self.limits()[0]["five_hour"]["used"]), ("claude", 45))
        usage.keep("claude", windows((47, FIVE), (12, WEEK)), NOW - 30)
        self.assertEqual((self.limits()[0]["source"], self.limits()[0]["five_hour"]["used"]), ("status", 47))

    def test_the_newest_reading_first(self):
        usage.keep("claude", windows((40, FIVE)), NOW - 600)
        self.codex("g7", [token_count(NOW - 60, primary=(20.0, 10080, WEEK))], NOW - 60)
        self.assertEqual([one["agent"] for one in self.limits()], ["codex", "claude"])


class Current(Home):
    def test_a_window_past_its_reset_is_none(self):
        usage.keep("claude", windows((90, NOW - 1), (35, WEEK)), NOW - 4 * HOUR)
        self.assertEqual(self.limits()[0]["five_hour"], None)
        self.assertEqual(self.limits()[0]["week"], {"used": 35, "resets": WEEK})
        usage.keep("claude", windows((90, FIVE), (35, WEEK)), NOW - HOUR)
        self.assertIsNone(self.limits(now=FIVE)[0]["five_hour"])            # at its reset it is past

    def test_an_agent_whose_windows_all_passed_is_left_out(self):
        usage.keep("claude", windows((90, NOW - 1), (35, NOW - 1)), NOW - DAY)
        self.codex("h8", [token_count(NOW - 8 * DAY, primary=(80.0, 10080, NOW - DAY))], NOW - 8 * DAY)
        self.assertEqual(self.limits(), [])

    def test_a_window_with_no_reset_lasts_its_length_from_the_reading(self):
        usage.keep("claude", windows((25, None), (5, None)), NOW - 4 * HOUR)
        self.assertEqual(self.limits()[0]["five_hour"], {"used": 25, "resets": None})
        self.assertEqual(self.limits(now=NOW + 2 * HOUR)[0]["five_hour"], None)
        self.assertEqual(self.limits(now=NOW + 2 * HOUR)[0]["week"], {"used": 5, "resets": None})


class LeftOut(Home):
    def test_an_api_keys_claude_is_left_out_not_zero(self):
        # without a subscription Claude's status JSON has no rate_limits, and its cache no windows
        self.assertFalse(usage.keep("claude", windows(), NOW))
        self.assertFalse(usage.keep("claude", {"five_hour": {"used": None, "resets": None}, "week": None}, NOW))
        self.claude()
        self.assertFalse(os.path.exists(os.path.join(self.home, ".local", "state", "herdr-fold", "limits")))
        self.assertEqual(self.limits(), [])

    def test_an_api_keys_codex_is_left_out(self):
        # its newest chat tells no window: an older chat's reading is not taken for today's
        self.codex("i9", [token_count(NOW - 2 * DAY, primary=(50.0, 10080, WEEK))], NOW - 2 * DAY)
        newest = token_count(NOW - 60)
        newest["payload"]["rate_limits"] = None
        self.codex("j0", [newest], NOW - 60)
        self.assertEqual(self.limits(), [])

    def test_damaged_files_are_left_out(self):
        self.write(".claude.json", '{"cachedUsageUtilization": ')
        self.write(".local/state/herdr-fold/limits/claude.json", "[1, 2]")
        self.write(".local/state/herdr-fold/limits/codex.json", '{"five_hour": {"used": "72"}, "at": 1}')
        with open(self.codex("k1", [], NOW), "a") as f:
            f.write('{"type": "event_msg", "payload": {"type": "token_count", "rate_limits": {"primary": 7}}}\n'
                    '{"type": "event_msg", "payload": {"type": "token_count", "rate_l\n'
                    '{"type": "event_msg", "payload": {"type": "token_count", "rate_limits": {"primary": '
                    '{"used_percent": true, "window_minutes": 300, "resets_at": 1}}}}\n')
        self.assertEqual(self.limits(), [])

    def test_a_pipe_in_a_files_place_is_not_read(self):
        os.mkfifo(os.path.join(self.home, ".claude.json"))
        self.assertEqual(self.limits(), [])


class ReadOnly(Home):
    def snapshot(self):
        found = {}
        for root, folders, files in os.walk(self.home):
            for name in folders + files:
                path = os.path.join(root, name)
                info = os.lstat(path)
                found[path] = (stat.S_IMODE(info.st_mode), info.st_mtime_ns, None)
                if stat.S_ISREG(info.st_mode):
                    with open(path, "rb") as f:
                        found[path] = found[path][:2] + (f.read(),)
        return found

    def test_reading_leaves_the_home_byte_for_byte_as_it_was(self):
        usage.keep("claude", windows((40, FIVE), (10, WEEK)), NOW - 600)
        self.claude(five=(45, "2026-11-13T14:46:00Z"), week=(11, "2026-11-16T17:00:00Z"), fetched=NOW - 60)
        self.codex("l2", [token_count(NOW - 60, primary=(20.0, 10080, WEEK))], NOW - 60)
        before = self.snapshot()
        self.assertEqual(len(self.limits()), 2)
        self.assertEqual(self.snapshot(), before)


class Keep(Home):
    def test_kept_whole_its_owners_only(self):
        self.assertTrue(usage.keep("codex", windows((61.6, FIVE), (23.2, WEEK)), NOW))
        folder = os.path.join(self.home, ".local", "state", "herdr-fold", "limits")
        self.assertEqual(stat.S_IMODE(os.stat(folder).st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(folder, "codex.json")).st_mode), 0o600)
        with open(os.path.join(folder, "codex.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {**windows((62, FIVE), (23, WEEK)), "at": NOW})
        self.assertEqual(os.listdir(folder), ["codex.json"])

    def test_only_an_agent_is_kept(self):
        for agent in ("gemini", "../claude", "", "claude/x"):
            with self.subTest(agent=agent):
                with self.assertRaises(ValueError):
                    usage.keep(agent, windows((10, FIVE)), NOW)

    def test_a_reading_with_no_window_leaves_the_last_one(self):
        usage.keep("claude", windows((40, FIVE)), NOW - 60)
        usage.keep("claude", windows(), NOW)
        self.assertEqual(self.limits()[0]["at"], NOW - 60)

    def test_the_command_answers_in_json(self):
        now = int(time.time())
        usage.keep("claude", windows((72, now + HOUR), (16, now + DAY)), now)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(usage.main(["usage.py", "limits"]), 0)
        self.assertEqual(json.loads(out.getvalue()), [{"agent": "claude", **windows((72, now + HOUR), (16, now + DAY)),
                                                       "at": now, "source": "status"}])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(usage.main(["usage.py"]), 2)


class Section(unittest.TestCase):
    """The Agent panel's Usage as both clients draw it: a row an agent, the words made here."""

    AGENTS = [{"key": "claude", "name": "Claude", "plan": "Max"}, {"key": "codex", "name": "Codex", "plan": "Plus"}]

    def reading(self, agent, five=None, week=None, at=NOW - 60, source="status"):
        return {"agent": agent, **windows(five, week), "at": at, "source": source}

    def rows(self, limits, current="claude", agents=None):
        return usage.section(limits, self.AGENTS if agents is None else agents, current, NOW)["rows"]

    def test_a_row_an_agent_its_name_plan_and_both_percents_with_their_levels(self):
        found = usage.section([self.reading("claude", (72, FIVE), (16, WEEK))], self.AGENTS, "claude", NOW)
        self.assertEqual((found["id"], found["title"], found["none"]), ("usage", "Usage", "Not known yet"))
        row, = found["rows"]
        self.assertEqual((row["key"], row["name"], row["plan"], row["current"]), ("claude", "Claude", "Max", True))
        self.assertEqual(row["five"], {"label": "5h", "used": 72, "text": "72%", "level": "warn"})
        self.assertEqual(row["week"], {"label": "wk", "used": 16, "text": "16%", "level": "ok"})
        self.assertEqual(row["said"], "5 hour 72%, week 16%")

    def test_a_percents_level_is_the_status_lines(self):
        self.assertEqual([usage.level(used) for used in (0, 49, 50, 79, 80, 100)],
                         ["ok", "ok", "warn", "warn", "bad", "bad"])

    def test_the_current_agent_first_then_the_newest_reading(self):
        limits = [self.reading("codex", (8, FIVE), (3, WEEK), at=NOW - 10),
                  self.reading("claude", (72, FIVE), (16, WEEK), at=NOW - 500)]
        self.assertEqual([(row["key"], row["current"]) for row in self.rows(limits)],
                         [("claude", True), ("codex", False)])
        self.assertEqual([row["key"] for row in self.rows(limits, current="codex")], ["codex", "claude"])
        # the current one on an API key has no row: the newest reading first, none lit
        self.assertEqual([(row["key"], row["current"]) for row in self.rows(limits, current="gemini")],
                         [("codex", False), ("claude", False)])

    def test_every_row_its_first_windows_bar_and_reset_for_its_block_opened(self):
        first, second = self.rows([self.reading("claude", (72, FIVE), (16, WEEK)),
                                   self.reading("codex", (8, FIVE + HOUR), (3, WEEK))])
        self.assertEqual(first["bar"], {"used": 72, "level": "warn"})
        self.assertEqual(first["resets"], {"at": FIVE, "words": "5 hour resets at {time}"})
        self.assertEqual(second["bar"], {"used": 8, "level": "ok"})
        self.assertEqual(second["resets"], {"at": FIVE + HOUR, "words": "5 hour resets at {time}"})

    def test_its_tightest_window_is_the_one_used_most_the_five_hours_on_a_tie(self):
        rows = [self.rows([self.reading("claude", five, week)])[0]["tight"]
                for five, week in (((72, FIVE), (16, WEEK)), ((12, FIVE), (85, WEEK)), ((40, FIVE), (40, WEEK)),
                                   (None, (16, WEEK)))]
        self.assertEqual([(one["label"], one["text"], one["level"]) for one in rows],
                         [("5h", "72%", "warn"), ("wk", "85%", "bad"), ("5h", "40%", "ok"), ("wk", "16%", "ok")])

    def test_the_agent_in_use_is_open_the_others_folded_till_one_is_turned(self):
        limits = [self.reading("claude", (72, FIVE), (16, WEEK)), self.reading("codex", (8, FIVE), (3, WEEK))]
        self.assertEqual(usage.section(limits, self.AGENTS, "claude", NOW)["open"], {"claude": True, "codex": False})
        self.assertEqual(usage.section(limits, self.AGENTS, "codex", NOW)["open"], {"claude": False, "codex": True})
        # what the user opened or folded stays, whichever agent is in use; the others as before
        self.assertEqual(usage.section(limits, self.AGENTS, "codex", NOW, {"claude": True})["open"],
                         {"claude": True, "codex": True})
        self.assertEqual(usage.section(limits, self.AGENTS, "claude", NOW, {"claude": False})["open"],
                         {"claude": False, "codex": False})
        # an agent on an API key has no row here but a block of its own in the clients: it is told too
        self.assertEqual(usage.section([], self.AGENTS, "codex", NOW)["open"], {"claude": False, "codex": True})

    def test_a_window_past_its_reset_leaves_the_other_alone_the_bar_and_the_reset_its(self):
        row, = self.rows([self.reading("claude", None, (16, WEEK))])
        self.assertIsNone(row["five"])
        self.assertEqual(row["bar"], {"used": 16, "level": "ok"})
        self.assertEqual(row["resets"], {"at": WEEK, "words": "Week resets {day} at {time}"})    # days away: its day
        self.assertEqual(row["said"], "Week 16%")
        row, = self.rows([self.reading("claude", (91, FIVE), None)])
        self.assertEqual((row["week"], row["said"]), (None, "5 hour 91%"))

    def test_a_reset_within_twelve_hours_names_its_time_alone_one_not_told_nothing(self):
        row, = self.rows([self.reading("claude", None, (16, NOW + 11 * HOUR))])
        self.assertEqual(row["resets"]["words"], "Week resets at {time}")
        row, = self.rows([self.reading("claude", (72, None), (16, WEEK))])
        self.assertEqual((row["bar"], row["resets"]), ({"used": 72, "level": "warn"}, None))

    def test_a_reading_older_than_ten_minutes_says_its_age_whoever_read_it(self):
        for source in ("claude", "status", "codex"):
            ages = {seconds: self.rows([self.reading("claude", (72, FIVE), at=NOW - seconds, source=source)])[0]["age"]
                    for seconds in (20, 600, 43 * 60, 3 * HOUR + 59 * 60, 3 * DAY)}
            self.assertEqual(ages, {20: None, 600: None, 43 * 60: "as of 43 min ago",
                                    3 * HOUR + 59 * 60: "as of 3 h ago", 3 * DAY: "as of 3 d ago"})
        row, = self.rows([self.reading("claude", (72, FIVE), (16, WEEK), at=NOW - 43 * 60, source="codex")])
        self.assertEqual(row["said"], "5 hour 72%, week 16%, as of 43 min ago")

    def test_a_plan_is_its_word_alone_never_an_e_mail_or_an_id(self):
        for plan, shown in (("Max", "Max"), ("API key", "API key"), ("ada@lumen.example", None), ("max_20x", None),
                            (None, None), (7, None)):
            row, = self.rows([self.reading("claude", (72, FIVE))], agents=[{"key": "claude", "name": "Claude",
                                                                            "plan": plan}])
            self.assertEqual(row["plan"], shown, plan)

    def test_an_agent_not_told_keeps_its_own_name_and_no_plan(self):
        for agents in ([], None, "x", [7, {"key": "codex"}]):
            found = usage.section([self.reading("codex", (8, FIVE))], agents, "claude", NOW)
            self.assertEqual([(row["name"], row["plan"]) for row in found["rows"]], [("Codex", None)], agents)

    def test_no_limits_no_rows(self):
        self.assertEqual(usage.section([], self.AGENTS, "claude", NOW)["rows"], [])


class Clock(Home):
    """A reset's words in this machine's time, for the TUI (the app writes its own, as macOS has them)."""

    def setUp(self):
        super().setUp()
        self.addCleanup(time.tzset)                         # after the zone is back
        set_env(self, TZ="America/New_York")
        time.tzset()

    def test_a_reset_is_said_in_local_time_twelve_hours_or_24(self):
        five = {"at": FIVE, "words": "5 hour resets at {time}"}
        self.assertEqual(usage.reset_said(five, True), "5 hour resets at 9:46 AM")
        self.assertEqual(usage.reset_said(five, False), "5 hour resets at 09:46")
        week = {"at": WEEK, "words": "Week resets {day} at {time}"}
        self.assertEqual(usage.reset_said(week, True), "Week resets Mon at 12:00 PM")
        self.assertEqual(usage.reset_said(week, False), "Week resets Mon at 12:00")
        self.assertEqual(usage.reset_said(None, True), "")

    def test_hours_are_written_as_the_status_line_found_them_else_24(self):
        self.assertFalse(usage.twelve_hours(self.home))
        path = os.path.join(self.home, ".local", "state", "herdr-fold", "time.json")
        os.makedirs(os.path.dirname(path))
        for body, twelve in (('{"twelve": true}', True), ('{"twelve": false}', False), ('{"twelve": "yes"}', False),
                             ("{", False)):
            with open(path, "w", encoding="utf-8") as f:
                f.write(body)
            self.assertEqual(usage.twelve_hours(self.home), twelve, body)


class SectionCommand(Home):
    def run_main(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = usage.main(["usage.py", *args])
        return code, out.getvalue()

    def test_the_command_answers_the_section_for_the_agent_shown(self):
        usage.keep("claude", windows((72, int(time.time()) + HOUR), (16, int(time.time()) + DAY)), int(time.time()))
        code, out = self.run_main("section", "claude", json.dumps([{"key": "claude", "name": "Claude",
                                                                    "plan": "Max"}]))
        row, = json.loads(out)["rows"]
        self.assertEqual((code, row["name"], row["plan"], row["five"]["text"], row["current"]),
                         (0, "Claude", "Max", "72%", True))
        code, out = self.run_main("section", "codex")       # the agents not told yet: no plan
        self.assertEqual((code, json.loads(out)["rows"][0]["plan"]), (0, None))
        code, out = self.run_main("section", "claude", "{not json")
        self.assertEqual((code, json.loads(out)["rows"][0]["plan"]), (0, None))
        self.assertEqual(self.run_main("section")[0], 2)

    def test_the_command_keeps_a_block_opened_or_folded_and_the_section_tells_it(self):
        self.assertEqual(self.run_main("open", "codex", "on"), (0, '{"codex": true}\n'))
        self.assertEqual(json.loads(self.run_main("section", "claude")[1])["open"], {"claude": True, "codex": True})
        self.assertEqual(self.run_main("open", "claude", "off"), (0, '{"codex": true, "claude": false}\n'))
        self.assertEqual(json.loads(self.run_main("section", "claude")[1])["open"], {"claude": False, "codex": True})
        for args in (("open", "gemini", "on"), ("open", "codex", "yes"), ("open", "codex")):
            self.assertEqual(self.run_main(*args)[0], 2, args)


class Opened(Home):
    """Each agent's block opened or folded by the user, kept once for both clients in herdr-fold's own usage.json."""

    def setUp(self):
        super().setUp()
        self.state = os.path.join(self.home, ".local", "state", "herdr-fold")
        self.path = os.path.join(self.state, "usage.json")

    def test_a_block_turned_is_kept_beside_the_budgets_its_owners_only(self):
        self.assertEqual(usage.kept_open(self.state), {})
        os.makedirs(self.state)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"budgets": {"codex": 50}, "dismissed": ["codex:2026-11"]}, f)
        self.assertEqual(usage.keep_open(self.state, "codex", True), {"codex": True})
        self.assertEqual(usage.keep_open(self.state, "claude", False), {"codex": True, "claude": False})
        self.assertEqual(usage.kept_open(self.state), {"codex": True, "claude": False})
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"budgets": {"codex": 50}, "dismissed": ["codex:2026-11"],
                                            "open": {"codex": True, "claude": False}})
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertEqual(sorted(os.listdir(os.path.join(self.home, ".local", "state"))), ["herdr-fold"])

    def test_what_is_no_agent_or_no_choice_is_refused_or_not_read(self):
        for agent, on in (("gemini", True), ("../codex", True), ("codex", "on"), ("codex", 1)):
            with self.subTest(agent=agent, on=on), self.assertRaises(ValueError):
                usage.keep_open(self.state, agent, on)
        os.makedirs(self.state)
        for body in ('{"open": {"codex": "yes", "gemini": true, "claude": false}}', '{"open": [1]}', "{"):
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(body)
            self.assertEqual(usage.kept_open(self.state), {"claude": False} if "claude" in body else {}, body)


class Writers(unittest.TestCase):
    """The app's chat (chat_hook.py's status) and the status line (src/statusline.py, on its own) keep one shape."""

    STATUS = {"session_id": "5f0c6d9e-1b2a-4c3d-8e9f-0a1b2c3d4e5f", "cwd": "/work/lumen-api",
              "transcript_path": "/work/x.jsonl", "workspace": {"current_dir": "/work/lumen-api"},
              "model": {"id": "claude-opus-5-5", "display_name": "Opus 5.5"}, "effort": {"level": "high"},
              "context_window": {"used_percentage": 12.5, "context_window_size": 1000000},
              "rate_limits": {"five_hour": {"used_percentage": 72.5, "resets_at": FIVE},
                              "seven_day": {"used_percentage": 15.6, "resets_at": WEEK}}}

    def kept(self, writer, data):
        """What WRITER (hook or line) keeps of Claude's status JSON DATA in a home of its own; None for nothing."""
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        os.makedirs(os.path.join(home, ".local", "state", "herdr-fold"))
        with open(os.path.join(home, ".local", "state", "herdr-fold", "time.json"), "w") as f:
            json.dump({"twelve": False}, f)                 # the line asks the machine nothing
        if writer == "hook":
            set_env(self, HOME=home)
            with contextlib.redirect_stdout(io.StringIO()):
                chat_hook.write_status(data)
        else:
            done = subprocess.run([sys.executable, STATUSLINE], input=json.dumps(data).encode("utf-8"),
                                  capture_output=True, timeout=20, env={"HOME": home, "PATH": "", "TZ": "UTC"})
            self.assertEqual((done.returncode, done.stderr), (0, b""))
        path = os.path.join(home, ".local", "state", "herdr-fold", "limits", "claude.json")
        if not os.path.exists(path):
            return None
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_both_keep_the_same_shape_and_nothing_of_the_session(self):
        texts = {writer: self.kept(writer, self.STATUS) for writer in ("hook", "line")}
        found = {writer: json.loads(text) for writer, text in texts.items()}
        for writer, one in found.items():
            self.assertIsInstance(one.pop("at"), int, writer)
            self.assertLess(abs(json.loads(texts[writer])["at"] - time.time()), 60, writer)
            for word in ("/work", "lumen", "Opus", "5f0c6d9e", "context"):
                self.assertNotIn(word, texts[writer], writer)
        self.assertEqual(found["hook"], windows((72, FIVE), (16, WEEK)))      # a half to even, as the line rounds it
        self.assertEqual(found["line"], found["hook"])
        self.assertEqual(usage.window(found["line"]["five_hour"]), found["line"]["five_hour"])

    def test_neither_keeps_a_status_without_limits(self):
        data = {key: value for key, value in self.STATUS.items() if key != "rate_limits"}
        self.assertEqual([self.kept(writer, data) for writer in ("hook", "line")], [None, None])

    def test_one_window_alone(self):
        data = {**self.STATUS, "rate_limits": {"seven_day": {"used_percentage": 15.6, "resets_at": WEEK}}}
        found = [json.loads(self.kept(writer, data)) for writer in ("hook", "line")]
        self.assertEqual([{key: one[key] for key in ("five_hour", "week")} for one in found],
                         [windows(None, (16, WEEK))] * 2)


if __name__ == "__main__":
    unittest.main()
