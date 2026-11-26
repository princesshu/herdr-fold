"""Tests for core/usage.py in a temporary HOME: the agents' limits from herdr-fold's own readings, Claude's cache (a
model's own week too) and Codex's newest chat, the newest per agent, a limit past its reset 0% or not known, an agent
with none left out; nothing of the agents' files written; both status lines keep the same shape."""
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
FABLE = NOW + 3 * DAY + 21 * HOUR                       # Fable's own week's: Tuesday, 17 November, 09:00 UTC
ACCOUNT = "00000000-0000-4000-8000-00000000c1a0"        # an invented account id, never answered
STATUSLINE = os.path.join(PACKAGE, "src", "statusline.py")


def windows(five=None, week=None, models=()):
    """A reading's windows: FIVE and WEEK each (used, resets) or None; MODELS each (name, used, resets)."""
    return {**{name: None if one is None else {"used": one[0], "resets": one[1]}
               for name, one in (("five_hour", five), ("week", week))},
            "models": [{"name": name, "used": used, "resets": resets} for name, used, resets in models]}


def scoped(name, percent, resets, active=False, scope="model"):
    """A row of Claude's cached usage meters (limits[]) for NAME's own week, as Claude 2.1.332 keeps them."""
    return {"kind": "weekly_scoped", "group": "weekly", "percent": percent, "severity": "normal", "resets_at": resets,
            "scope": {scope: {"display_name": name}}, "is_active": active}


class Home(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        set_env(self, HOME=self.home, CLAUDE_CONFIG_DIR=None)

    def write(self, rel, text, mtime=None):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def claude(self, five=None, week=None, fetched=NOW, folder="", signed=ACCOUNT, meters=None):
        """Claude's .claude.json in FOLDER (the home's, or a CLAUDE_CONFIG_DIR's) with its cached limits, as Claude
        2.1.325 keeps them (FIVE and WEEK each (percent, reset text)), METERS its usage rows (limits[], none before
        2.1.332), fetched at FETCHED, SIGNED in now."""
        used = {name: None if one is None else {"utilization": one[0], "resets_at": one[1], "limit_dollars": None,
                                                "used_dollars": None, "locked_reason": None}
                for name, one in (("five_hour", five), ("seven_day", week))}
        if meters is not None:
            used["limits"] = meters
        self.write(os.path.join(folder, ".claude.json"), json.dumps({
            "numStartups": 12, "oauthAccount": {"accountUuid": signed, "emailAddress": "dev@example.com"},
            "cachedUsageUtilization": {"fetchedAtMs": fetched * 1000 + 250, "accountUuid": ACCOUNT,
                                       "utilization": {**used, "seven_day_opus": None,
                                                       "extra_usage": {"is_enabled": False}}}}))

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


class Freshest(Home):
    """Each chat keeps the limits its last answer told; the one kept is the freshest any told, so an idle chat's older
    reading never takes it back, in the status lines, the app's notice or Usage."""

    def test_an_older_reading_of_the_same_window_never_lowers_it(self):
        usage.keep("claude", windows((47, FIVE), (12, WEEK)), NOW - 60)
        self.assertEqual(usage.keep("claude", windows((40, FIVE), (10, WEEK)), NOW), windows((47, FIVE), (12, WEEK)))
        self.assertEqual(self.limits()[0]["five_hour"]["used"], 47)

    def test_two_windows_open_at_once_are_never_mixed(self):
        # one chat told the weekly window, another a second weekly limit that resets later: each keeps its own
        other = WEEK + 18 * HOUR
        usage.keep("claude", windows(week=(100, other)), NOW - 60)
        self.assertEqual(usage.keep("claude", windows(week=(95, WEEK)), NOW)["week"], {"used": 95, "resets": WEEK})
        usage.keep("claude", windows(week=(95, WEEK)), NOW - 60)
        self.assertEqual(usage.keep("claude", windows(week=(100, other)), NOW)["week"], {"used": 100, "resets": other})

    def test_a_window_past_its_reset_gives_way_to_the_newer_one_kept(self):
        later = FIVE + 5 * HOUR
        usage.keep("claude", windows((5, later)), FIVE + 60)
        self.assertEqual(usage.keep("claude", windows((90, FIVE)), FIVE + 120)["five_hour"],
                         {"used": 5, "resets": later})

    def test_claudes_own_reading_names_the_accounts_windows(self):
        # Claude's /usage said 89% for the week an hour ago; a chat's status JSON tells another weekly limit at 100%
        self.claude(five=(10, "2026-11-13T14:46:00Z"), week=(89, "2026-11-16T17:00:00Z"), fetched=NOW - HOUR)
        self.assertEqual(usage.keep("claude", windows(week=(100, WEEK + 18 * HOUR)), NOW)["week"],
                         {"used": 89, "resets": WEEK})
        # a chat told that week since: its use stands, and the 5-hour Claude's own until a chat tells it
        self.assertEqual(usage.keep("claude", windows(week=(95, WEEK)), NOW), windows((10, FIVE), (95, WEEK)))
        self.assertEqual(usage.keep("claude", windows((51, FIVE), (94, WEEK)), NOW), windows((51, FIVE), (95, WEEK)))

    def test_a_reading_with_no_reset_is_its_own(self):
        usage.keep("claude", windows((90, FIVE)), NOW - 60)
        self.assertEqual(usage.keep("claude", windows((20, None)), NOW)["five_hour"], {"used": 20, "resets": None})

    def test_claudes_status_json_tells_its_windows(self):
        data = {"rate_limits": {"five_hour": {"used_percentage": 12.4, "resets_at": FIVE},
                                "seven_day": {"used_percentage": 40.6, "resets_at": WEEK}}}
        self.assertEqual(usage.told(data), windows((12, FIVE), (41, WEEK)))
        self.assertEqual(usage.told(None), windows())


class Accounts(Home):
    """Two Claude accounts on one machine, the second in its own CLAUDE_CONFIG_DIR as Claude takes it: each keeps its
    own reading and reads its own cache, so one's limits are never drawn for the other."""

    def test_a_second_accounts_readings_are_its_own(self):
        self.claude(five=(10, "2026-11-13T14:46:00Z"), week=(30, "2026-11-16T17:00:00Z"), fetched=NOW - HOUR)
        usage.keep("claude", windows((12, FIVE), (31, WEEK)), NOW - 60)
        later = WEEK + 18 * HOUR
        self.claude(five=(65, FIVE + HOUR), week=(78, later), fetched=NOW - HOUR, folder=".claude-work")
        set_env(self, CLAUDE_CONFIG_DIR=os.path.join(self.home, ".claude-work"))
        self.assertEqual(usage.keep("claude", windows((70, FIVE + HOUR), (80, later)), NOW),
                         windows((70, FIVE + HOUR), (80, later)))
        set_env(self, CLAUDE_CONFIG_DIR=None)
        self.assertEqual(usage.keep("claude", windows((12, FIVE), (31, WEEK)), NOW), windows((12, FIVE), (31, WEEK)))
        self.assertEqual(self.limits(), [{"agent": "claude", **windows((12, FIVE), (31, WEEK)), "at": NOW,
                                          "source": "status"}])

    def test_the_default_folder_named_is_the_default_account(self):
        set_env(self, CLAUDE_CONFIG_DIR=os.path.join(self.home, ".claude") + "/")
        usage.keep("claude", windows((12, FIVE), (31, WEEK)), NOW)
        set_env(self, CLAUDE_CONFIG_DIR=None)
        self.assertEqual(self.limits()[0]["five_hour"], {"used": 12, "resets": FIVE})

    def test_a_cache_of_another_account_than_the_one_signed_in_is_not_read(self):
        self.claude(five=(43, "2026-11-13T14:46:00Z"), fetched=NOW - HOUR,
                    signed="00000000-0000-4000-8000-0000000b0b00")
        self.assertEqual(self.limits(), [])
        self.assertIsNone(usage.claude_cached(self.home))


class Current(Home):
    def test_a_window_past_its_reset_is_0_with_nothing_run_since_else_not_known(self):
        usage.keep("claude", windows((90, NOW - HOUR), (35, WEEK)), NOW - 4 * HOUR)
        self.assertEqual(self.limits()[0]["five_hour"], {"used": 0, "resets": None})
        self.assertEqual(self.limits()[0]["week"], {"used": 35, "resets": WEEK})
        # a chat written since the reset, and no reading after it: what it used since is not known
        self.write(".claude/projects/-work-lumen-api/a0.jsonl", "{}\n", NOW - 10)
        self.assertEqual(self.limits()[0]["five_hour"], {"used": None, "resets": None})
        usage.keep("claude", windows((90, FIVE), (35, WEEK)), NOW - HOUR)
        self.assertEqual(self.limits(now=FIVE)[0]["five_hour"], {"used": 0, "resets": None})     # at its reset: past

    def test_an_agents_windows_all_past_stay_its_row(self):
        usage.keep("claude", windows((90, NOW - 1), (35, NOW - 1)), NOW - DAY)
        self.codex("h8", [token_count(NOW - 8 * DAY, primary=(80.0, 10080, NOW - DAY))], NOW - 8 * DAY)
        self.assertEqual([(one["agent"], one["five_hour"], one["week"]) for one in self.limits()], [
            ("claude", {"used": 0, "resets": None}, {"used": 0, "resets": None}),
            ("codex", None, {"used": 0, "resets": None})])

    def test_a_window_with_no_reset_lasts_its_length_from_the_reading(self):
        usage.keep("claude", windows((25, None), (5, None)), NOW - 4 * HOUR)
        self.assertEqual(self.limits()[0]["five_hour"], {"used": 25, "resets": None})
        self.assertEqual(self.limits(now=NOW + 2 * HOUR)[0]["five_hour"], {"used": 0, "resets": None})
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
        self.assertEqual(found, {"id": "usage", "title": "Usage", "none": "Not known yet", "rows": [{
            "key": "claude", "name": "Claude", "plan": "Max", "current": True, "age": "Read 1 min ago",
            "five": {"label": "5h", "used": 72, "text": "72%", "level": "warn",
                     "resets": {"at": FIVE, "words": "5h resets {time}"}},
            "week": {"label": "wk", "used": 16, "text": "16%", "level": "ok",
                     "resets": {"at": WEEK, "words": "Week resets {day} {time}"}},       # days away: its day
            "models": [],
            "tight": {"label": "5h", "used": 72, "text": "72%", "level": "warn",
                      "resets": {"at": FIVE, "words": "5h resets {time}"}},
            # the reset under the row only while its window is yellow or red
            "reset": {"at": FIVE, "words": "5h resets {time}"}, "untold": None}]})
        row, = self.rows([self.reading("claude", (32, FIVE), (16, WEEK))])
        self.assertIsNone(row["reset"])

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

    def test_its_tightest_window_is_the_one_used_most_the_five_hours_on_a_tie(self):
        rows = [self.rows([self.reading("claude", five, week)])[0]["tight"]
                for five, week in (((72, FIVE), (16, WEEK)), ((12, FIVE), (85, WEEK)), ((40, FIVE), (40, WEEK)),
                                   (None, (16, WEEK)), ((None, None), (16, WEEK)))]
        self.assertEqual([(one["label"], one["text"], one["level"]) for one in rows],
                         [("5h", "72%", "warn"), ("wk", "85%", "bad"), ("5h", "40%", "ok"), ("wk", "16%", "ok"),
                          ("wk", "16%", "ok")])

    def test_a_window_just_reset_says_0_or_not_known(self):
        row, = self.rows([self.reading("claude", (0, None), (41, WEEK)), ])
        self.assertEqual(row["five"], {"label": "5h", "used": 0, "text": "0%", "level": "ok", "resets": None})
        row, = self.rows([self.reading("codex", (None, None), (41, WEEK))], "codex")
        self.assertEqual(row["five"], {"label": "5h", "used": None, "text": "–", "level": None, "resets": None})
        row, = self.rows([self.reading("claude", (None, None), (None, None))])
        self.assertEqual((row["tight"], row["reset"]), (None, None))
        row, = self.rows([self.reading("claude", (91, FIVE), None)])
        self.assertEqual((row["week"], row["reset"]["words"]), (None, "5h resets {time}"))

    def test_a_reset_within_twelve_hours_names_its_time_alone_one_not_told_nothing(self):
        row, = self.rows([self.reading("claude", None, (86, NOW + 11 * HOUR))])
        self.assertEqual(row["reset"]["words"], "Week resets {time}")
        row, = self.rows([self.reading("claude", (72, None), (16, WEEK))])
        self.assertEqual((row["five"]["resets"], row["reset"]), (None, None))

    def test_the_readings_age_whoever_read_it(self):
        for source in ("claude", "status", "codex"):
            ages = {seconds: self.rows([self.reading("claude", (72, FIVE), at=NOW - seconds, source=source)])[0]["age"]
                    for seconds in (20, 3 * 60, 3 * HOUR + 59 * 60, 3 * DAY)}
            self.assertEqual(ages, {20: "Read just now", 3 * 60: "Read 3 min ago", 3 * HOUR + 59 * 60: "Read 3 h ago",
                                    3 * DAY: "Read 3 d ago"})

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

    def test_no_limits_and_no_agent_told_no_rows(self):
        self.assertEqual(usage.section([], [], "claude", NOW)["rows"], [])

    def test_the_current_agent_with_no_reading_says_so_in_its_rows_place(self):
        rows = self.rows([self.reading("claude", (72, FIVE))], "codex")
        self.assertEqual([(row["key"], row["current"], (row["untold"] or {}).get("text")) for row in rows],
                         [("codex", True, "limits not told"), ("claude", False, None)])
        self.assertEqual((rows[0]["name"], rows[0]["plan"], rows[0]["five"], rows[0]["week"], rows[0]["models"],
                          rows[0]["tight"], rows[0]["reset"], rows[0]["age"]),
                         ("Codex", "Plus", None, None, [], None, None, None))
        self.assertEqual(rows[0]["untold"]["why"], "Codex tells its limits in a chat's token counts: none of its "
                                                   "newest chats holds one yet.")
        self.assertIn("status line", self.rows([], "claude")[0]["untold"]["why"])
        # another agent's missing reading is no row; an API key has no window to tell; one not told is not named
        self.assertEqual([row["key"] for row in self.rows([self.reading("claude", (72, FIVE))], "claude")], ["claude"])
        on_key = [{"key": "codex", "name": "Codex", "plan": usage.API_KEY}]
        self.assertEqual(self.rows([], "codex", on_key), [])
        self.assertEqual(self.rows([], "aider"), [])


class Models(Home):
    """A model's own weekly allowance (Fable's), which Claude's status JSON never tells: its cache's usage rows alone,
    kept by the rules of the others, a row each, in Usage as a third window labelled with the model's name."""

    def test_claudes_cache_tells_each_models_own_week_whether_or_not_it_is_the_headline(self):
        # is_active is the server's headline pick for a one-figure indicator: Claude's /usage lists every row
        self.claude(five=(43, "2026-11-13T14:46:00Z"), week=(9, "2026-11-16T17:00:00Z"), fetched=NOW - 60, meters=[
            {"kind": "session", "group": "session", "percent": 43, "severity": "normal",
             "resets_at": "2026-11-13T14:46:00Z", "scope": None, "is_active": True},
            {"kind": "weekly_all", "group": "weekly", "percent": 9, "severity": "normal",
             "resets_at": "2026-11-16T17:00:00Z", "scope": None, "is_active": False},
            scoped("Fable", 37.6, "2026-11-17T09:00:00Z"),
            scoped("Sonnet 5.1", 12, "2026-11-17T10:00:00+01:00", active=True)])
        self.assertEqual(self.limits(), [{"agent": "claude", **windows((43, FIVE), (9, WEEK), [
            ("Fable", 38, FABLE), ("Sonnet 5.1", 12, FABLE)]), "at": NOW - 60, "source": "claude"}])

    def test_only_a_models_named_row_counts_the_first_of_a_name_and_damaged_ones_none(self):
        for meters, found in (
                ([scoped("Fable", 38, FABLE), scoped("Fable", 90, FABLE)], [("Fable", 38, FABLE)]),
                ([scoped("Code", 20, FABLE, scope="surface"), scoped("ada@lumen.example", 5, FABLE),
                  scoped("", 5, FABLE), scoped(7, 5, FABLE), {**scoped("Fable", 38, FABLE), "percent": "38"},
                  {**scoped("Fable", 38, FABLE), "kind": "weekly_all"}, None, 7], []),
                ({"Fable": scoped("Fable", 38, FABLE)}, []), (7, [])):
            with self.subTest(meters=meters):
                self.claude(five=(43, FIVE), meters=meters)
                self.assertEqual(self.limits()[0]["models"], windows(models=found)["models"])
        self.claude(five=(43, FIVE), meters=[{**scoped("Fable", 38, None), "resets_at": "soon"}])
        self.assertEqual(self.limits()[0]["models"], [{"name": "Fable", "used": 38, "resets": None}])

    def test_the_status_line_keeps_the_caches_beside_what_it_was_told_and_draws_them(self):
        self.claude(five=(43, "2026-11-13T14:46:00Z"), fetched=NOW - HOUR, meters=[scoped("Fable", 38, FABLE)])
        self.assertEqual(usage.keep("claude", windows((47, FIVE)), NOW),
                         windows((47, FIVE), models=[("Fable", 38, FABLE)]))
        self.assertEqual(self.limits()[0], {"agent": "claude", **windows((47, FIVE), models=[("Fable", 38, FABLE)]),
                                            "at": NOW, "source": "status"})
        # the cache gone (another account signed in): the ones kept stand; the cache with none: none
        os.remove(os.path.join(self.home, ".claude.json"))
        self.assertEqual(usage.keep("claude", windows((48, FIVE)), NOW + 60)["models"], [
            {"name": "Fable", "used": 38, "resets": FABLE}])
        self.claude(five=(43, "2026-11-13T14:46:00Z"), fetched=NOW, meters=[])
        self.assertEqual(usage.keep("claude", windows((49, FIVE)), NOW + 120)["models"], [])

    def test_a_second_accounts_model_weeks_are_its_own(self):
        self.claude(five=(10, FIVE), fetched=NOW - HOUR, meters=[scoped("Fable", 38, FABLE)])
        self.claude(five=(65, FIVE), fetched=NOW - HOUR, folder=".claude-work", meters=[scoped("Fable", 81, FABLE)])
        set_env(self, CLAUDE_CONFIG_DIR=os.path.join(self.home, ".claude-work"))
        self.assertEqual(usage.keep("claude", windows((70, FIVE)), NOW)["models"][0]["used"], 81)
        set_env(self, CLAUDE_CONFIG_DIR=None)
        self.assertEqual(usage.keep("claude", windows((12, FIVE)), NOW)["models"][0]["used"], 38)
        self.assertEqual(self.limits()[0]["models"][0]["used"], 38)

    def test_one_past_its_reset_is_0_with_nothing_run_since_else_not_known(self):
        self.claude(five=(43, FIVE), fetched=NOW - 2 * DAY, meters=[scoped("Fable", 38, NOW - HOUR)])
        self.assertEqual(self.limits()[0]["models"], [{"name": "Fable", "used": 0, "resets": None}])
        self.write(".claude/projects/-work-lumen-api/a0.jsonl", "{}\n", NOW - 10)
        self.assertEqual(self.limits()[0]["models"], [{"name": "Fable", "used": None, "resets": None}])

    def test_usage_draws_each_as_a_window_of_its_own_labelled_with_its_name(self):
        def row_of(five, week, models):
            reading = {"agent": "claude", **windows(five, week, models), "at": NOW - 60, "source": "status"}
            return usage.section([reading], Section.AGENTS, "claude", NOW)["rows"][0]
        row = row_of((32, FIVE), (16, WEEK), [("Fable", 86, FABLE), ("Sonnet 5.1", 4, NOW + 6 * HOUR)])
        self.assertEqual(row["models"], [
            {"label": "Fable", "used": 86, "text": "86%", "level": "bad",
             "resets": {"at": FABLE, "words": "Fable resets {day} {time}"}},
            # its words' first word stays its whole name, the clients' label
            {"label": "Sonnet 5.1", "used": 4, "text": "4%", "level": "ok",
             "resets": {"at": NOW + 6 * HOUR, "words": "Sonnet\u00a05.1 resets {time}"}}])
        # the tightest of all three: its reset under the row
        self.assertEqual((row["tight"]["label"], row["reset"]["words"]), ("Fable", "Fable resets {day} {time}"))
        self.assertEqual(row_of((40, FIVE), (16, WEEK), [("Fable", 40, FABLE)])["tight"]["label"], "5h")   # a tie


class Clock(Home):
    """A reset's words in this machine's time, for the TUI (the app writes its own, as macOS has them)."""

    def setUp(self):
        super().setUp()
        self.addCleanup(time.tzset)                         # after the zone is back
        set_env(self, TZ="America/New_York")
        time.tzset()

    def test_a_reset_is_said_in_local_time_twelve_hours_or_24(self):
        five = {"at": FIVE, "words": "5h resets {time}"}
        self.assertEqual(usage.reset_said(five, True), "5h resets 9:46 AM")
        self.assertEqual(usage.reset_said(five, False), "5h resets 09:46")
        week = {"at": WEEK, "words": "Week resets {day} {time}"}
        self.assertEqual(usage.reset_said(week, True), "Week resets Mon 12:00 PM")
        self.assertEqual(usage.reset_said(week, False), "Week resets Mon 12:00")
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

    def test_the_folds_command_is_gone(self):
        # one row per agent, no block of its own to fold (the owner, 2026-11-20)
        self.assertEqual(self.run_main("open", "codex", "on")[0], 2)
        self.assertFalse(hasattr(usage, "keep_open") or hasattr(usage, "kept_open"))


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
        self.assertEqual([{key: one[key] for key in ("five_hour", "week", "models")} for one in found],
                         [windows(None, (16, WEEK))] * 2)


if __name__ == "__main__":
    unittest.main()
