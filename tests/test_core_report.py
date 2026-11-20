"""Tests for core/report.py in a temporary HOME: what the agents used in a period, as value on a plan and as spent
with an API key, by day, model, project and conversation, the month against its budget and its pace, the chat's notice
and the CSV. The sessions and prices are invented; nothing here reaches the network or runs git."""
import contextlib
import io
import json
import os
import subprocess
import sys
import time
from unittest import mock

from support import PACKAGE, set_env

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import prices  # noqa: E402
import report  # noqa: E402
import test_core_tokens as made  # noqa: E402
import tokens  # noqa: E402
import usage  # noqa: E402

DAY = 86400
NOW = 1794484800                # Thursday, 12 November 2026, 12:00 UTC
SESSION, OTHER, THREAD = made.SESSION, made.OTHER, made.THREAD
LUMEN, HARBOR, TIDEPOOL = "/Users/dev/lumen-api", "/Users/dev/harbor-web", "/Users/dev/tidepool"
OPUS, HAIKU, GPT, REVIEW = "claude-opus-5-5", "claude-haiku-5-5", "gpt-6-astra", "codex-auto-review"
AGENTS = [{"key": "claude", "name": "Claude", "plan": "Max"}, {"key": "codex", "name": "Codex", "plan": "API key"}]
# invented prices, dollars a token: Opus 10 a million in, 50 out, its cache 12.50, 20 and 1; the others' input alone
TABLE = {"as_of": "2026-11-09", "source": "kept", "models": {
    OPUS: prices.price({"input_cost_per_token": 1e-5, "output_cost_per_token": 5e-5,
                        "cache_creation_input_token_cost": 1.25e-5,
                        "cache_creation_input_token_cost_above_1hr": 2e-5, "cache_read_input_token_cost": 1e-6}),
    HAIKU: prices.price({"input_cost_per_token": 1e-6, "output_cost_per_token": 5e-6}),
    GPT: prices.price({"input_cost_per_token": 1e-5, "output_cost_per_token": 0})}}


def at(day, hour=10, minute=0):
    """A time on November DAY, 2026 (UTC), as the agents write a line's."""
    return f"2026-11-{day:02d}T{hour:02d}:{minute:02d}:00.000Z"


def said(id, when, model=OPUS, session=SESSION, folder=LUMEN, **counts):
    entry = json.loads(made.said(id, model=model, session=session, folder=folder, **counts))
    return made.line({**entry, "timestamp": when})


def record(response, when, turn="turn-1", **counts):
    return made.line({**json.loads(made.record(response, turn=turn, **counts)), "timestamp": when})


def turn(model, id, when, folder=TIDEPOOL):
    entry = json.loads(made.turn(model, id))
    return made.line({**entry, "timestamp": when, "payload": {**entry["payload"], "cwd": folder}})


def meta(folder=TIDEPOOL):
    entry = json.loads(made.meta())
    return made.line({**entry, "payload": {**entry["payload"], "cwd": folder}})


class Used(made.Home):
    """A home with twelve days of November: a Claude conversation in lumen-api with its Explore sub-agent, an older
    one in harbor-web, and a Codex one in tidepool with a model that has no price."""

    def setUp(self):
        super().setUp()
        set_env(self, TZ="UTC", HERDR_FOLD_NO_UPDATE_CHECK="1", HERDR_PLUGIN_STATE_DIR=None)
        time.tzset()
        self.addCleanup(time.tzset)
        self.chats = os.path.join(self.home, ".local", "state", "herdr", "plugins", "herdr-fold.sidebar")
        first = self.session(said("msg_01", at(10, 10, 5), input=20_000, write_1h=100_000, read=880_000,
                                  output=10_000) + said("msg_02", at(11, 9), input=100_000))
        self.sub(said("msg_03", at(10, 10, 6), model=HAIKU, input=200_000))
        self.write(f".claude/projects/-Users-dev-harbor-web/{OTHER}.jsonl",
                   said("msg_04", at(3), session=OTHER, folder=HARBOR, input=500_000))
        rollout = self.write(f".codex/sessions/2026/11/02/rollout-2026-11-02T10-00-00-{THREAD}.jsonl",
                             meta() + turn(GPT, "turn-1", at(2)) + record("resp_01", at(2), input_tokens=980_000)
                             + record("resp_02", at(10), input_tokens=860_000) + turn(REVIEW, "turn-2", at(10, 11))
                             + record("resp_03", at(10, 11), turn="turn-2", input_tokens=900_000,
                                      cached_input_tokens=100_000))
        tokens.index(self.state, self.home)
        self.write(".local/state/herdr/plugins/herdr-fold.sidebar/chat-index.json", json.dumps({
            "version": 2, "files": {first: {"prompt": "fix it", "ai": "Fix the page past the last one"},
                                    rollout: {"id": THREAD, "prompt": "Spike the search API"}}}))
        self.write(".local/state/herdr-fold/limits/claude.json", json.dumps({
            "five_hour": {"used": 72, "resets": NOW + 3600}, "week": {"used": 16, "resets": NOW + 3 * DAY},
            "at": NOW - 60}))

    def report(self, period="7d", agent=None, folder=None, now=NOW, agents=AGENTS, **more):
        return report.report(self.state, self.home, period, agent, folder, now, agents=agents, table=TABLE, **more)

    def cell(self, found, key):
        return next(one for one in found["summary"] if one["key"].startswith(key))


class Periods(Used):
    def test_each_period_is_whole_local_days_ending_today(self):
        midnight = NOW - 12 * 3600
        for id, label, start in (("today", "Today", midnight), ("7d", "7 days", midnight - 6 * DAY),
                                 ("30d", "30 days", midnight - 29 * DAY), ("month", "November", midnight - 11 * DAY)):
            with self.subTest(id):
                self.assertEqual(self.report(id)["period"],
                                 {"id": id, "label": label, "from": start, "to": midnight + DAY})

    def test_the_filters_are_named_once_for_both_clients(self):
        found = self.report()["filters"]
        self.assertEqual(found["periods"], [{"id": "today", "label": "Today"}, {"id": "7d", "label": "7 days"},
                                            {"id": "30d", "label": "30 days"}, {"id": "month", "label": "November"}])
        self.assertEqual(found["agents"], [{"id": None, "label": "All agents"}, {"id": "claude", "label": "Claude"},
                                           {"id": "codex", "label": "Codex"}])
        self.assertEqual(found["spaces"], "All spaces")

    def test_a_day_is_this_machines_across_the_utc_date_line(self):
        # Auckland is 13 hours ahead in November: 12:00 UTC on the 12th is 1 AM on the 13th there, and the 13th
        # began at 11:00 UTC; msg_02 (the 11th, 9:00 UTC) was said at 10 PM on the 11th there
        set_env(self, TZ="Pacific/Auckland")
        time.tzset()
        self.session(said("msg_05", at(12, 10, 30), input=300_000) + said("msg_06", at(12, 11, 5), input=700_000),
                     session="9c8b7a6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d")
        tokens.index(self.state, self.home)
        today = self.report("today")
        self.assertEqual(today["period"]["from"], NOW - 3600)
        self.assertEqual(today["period"]["to"], NOW - 3600 + DAY)
        self.assertEqual([(one["day"], round(one["total"], 2)) for one in today["daily"]], [("2026-11-13", 7.0)])
        week = {one["day"]: round(one["total"], 2) for one in self.report("7d")["daily"]}
        self.assertEqual(list(week), [f"2026-11-{day:02d}" for day in range(7, 14)])
        self.assertEqual((week["2026-11-12"], week["2026-11-13"], week["2026-11-11"]), (3.0, 7.0, 1.0))

    def test_an_unknown_period_is_refused(self):
        with self.assertRaises(ValueError):
            self.report("year")


class Summary(Used):
    def test_a_plans_figure_is_api_value_never_spent(self):
        found = self.report()
        cell = self.cell(found, "Claude")
        self.assertEqual(cell, {"key": "Claude · Max plan", "agent": "claude", "value": cell["value"],
                                "text": "~$4.78", "unit": "API value",
                                "line": "no charge on the plan · week 16% of its limit", "over": False})
        self.assertAlmostEqual(cell["value"], 4.78)
        claude = self.report(agent="claude")
        self.assertNotIn("spent", json.dumps(claude))
        self.assertEqual({one["kind"] for one in claude["conversations"] + claude["models"]}, {"value"})
        self.assertEqual(claude["words"]["projects_note"], "API value · 7 days")
        self.assertEqual(found["words"]["projects_note"], "value and spent together · 7 days")
        self.assertEqual(self.report(agent="codex")["words"]["projects_note"], "spent · 7 days")

    def test_a_plan_whose_week_is_not_known_says_the_plan_alone(self):
        os.unlink(os.path.join(self.state, "limits", "claude.json"))
        self.assertEqual(self.cell(self.report(), "Claude")["line"], "no charge on the plan")

    def test_an_agent_whose_sign_in_is_not_told_is_never_spent(self):
        for agents in (None, [], "no", [{"key": "codex", "plan": None}], [{"key": "codex"}, 7]):
            with self.subTest(agents=agents):
                cell = self.cell(self.report(agents=agents), "Codex")
                self.assertEqual((cell["key"], cell["unit"], cell["line"]), ("Codex", "API value", ""))

    def test_an_api_keys_figure_is_spent_with_its_month_budget_and_pace(self):
        report.set_budget(self.state, "codex", 50)
        cell = self.cell(self.report(), "Codex")
        self.assertEqual((cell["key"], cell["text"], cell["unit"], cell["line"], cell["over"]),
                         ("Codex · API key", "~$8.60", "spent", "November ~$18.40 of $50 · on pace for ~$46", False))

    def test_a_pace_past_the_budget_is_over(self):
        report.set_budget(self.state, "codex", 40)
        cell = self.cell(self.report(), "Codex")
        self.assertEqual((cell["line"], cell["over"]), ("November ~$18.40 of $40 · on pace for ~$46", True))

    def test_an_api_key_with_no_budget_says_its_month_and_pace(self):
        cell = self.cell(self.report(), "Codex")
        self.assertEqual((cell["line"], cell["over"]), ("November ~$18.40 · on pace for ~$46", False))

    def test_the_tokens_and_the_share_read_from_the_cache(self):
        cell = self.cell(self.report(), "Tokens")
        self.assertEqual(cell, {"key": "Tokens", "value": 3_070_000, "text": "3.1M", "line": "32% read from cache"})

    def test_a_period_with_nothing_used_says_so(self):
        found = self.report("today")
        self.assertEqual((found["summary"][0], found["conversations"], found["models"], found["projects"]),
                         ({"key": "Tokens", "value": 0, "text": "0", "line": ""}, [], [], []))
        self.assertEqual(found["none"], "Nothing used in this period")

    def test_the_prices_day_and_the_foot(self):
        found = self.report()
        self.assertEqual(found["prices_as_of"], "Nov 9, 2026")
        self.assertEqual(found["words"]["foot"], "Costs are estimates from the conversations' token counts at list "
                                                 "prices (LiteLLM's model cost map, as of Nov 9, 2026), not the "
                                                 "provider's invoice · a model with no price shows its tokens alone")

    def test_a_figure_herdr_fold_computes_wears_a_tilde_a_cell_of_the_tables_and_the_csv_none(self):
        report.set_budget(self.state, "codex", 50)
        found = self.report()
        self.assertEqual([one["text"][:2] for one in found["summary"][:2]], ["~$", "~$"])
        self.assertEqual(found["months"][0]["line"], "~$18.40 of $50 · on pace for ~$46")        # the budget none
        self.assertTrue(all(one["text"].startswith("$") or one["text"] == "no price" for one in found["models"]))
        self.assertTrue(all(one["tip"].startswith("$") for one in found["conversations"] if one["tip"]))
        self.assertNotIn("~", report.csv(self.state, self.home, "7d", now=NOW, agents=AGENTS, table=TABLE))


class Breakdown(Used):
    def test_each_day_has_its_models_in_the_legends_order(self):
        found = self.report()
        self.assertEqual([one["day"] for one in found["daily"]], [f"2026-11-{day:02d}" for day in range(6, 13)])
        tenth = found["daily"][4]
        self.assertEqual((tenth["label"], round(tenth["total"], 2)), ("Nov 10", 12.38))
        self.assertEqual([(one["name"], one["color"], round(one["cost"], 2)) for one in tenth["models"]],
                         [("GPT-6 Astra", "#c98500", 8.6), ("Opus 5.5", "#3987e5", 3.58),
                          ("Haiku 5.5", "#199e70", 0.2)])
        self.assertEqual([(one["name"], one["share"]) for one in found["legend"]],
                         [("GPT-6 Astra", 64), ("Opus 5.5", 34), ("Haiku 5.5", 1)])
        self.assertEqual(found["daily"][0], {"day": "2026-11-06", "label": "Nov 6", "total": 0, "models": []})
        self.assertEqual(found["top"], {"day": "2026-11-10", "label": "Nov 10", "total": tenth["total"]})

    def test_the_colors_are_lifted_on_a_theme_that_needs_it(self):
        found = self.report(theme=("#3b4252", "#eceff4"))       # Nord's card and text
        self.assertEqual([one["color"] for one in found["legend"]], ["#c98500", "#4b91e6", "#2ea67d"])

    def test_the_projects_the_most_first(self):
        self.assertEqual([(one["folder"], one["name"], round(one["cost"], 2)) for one in self.report()["projects"]],
                         [(TIDEPOOL, "tidepool", 8.6), (LUMEN, "lumen-api", 4.78)])
        self.assertEqual([one["name"] for one in self.report("30d")["projects"]],
                         ["tidepool", "harbor-web", "lumen-api"])

    def test_a_conversations_row(self):
        rows = self.report()["conversations"]
        self.assertEqual([one["title"] for one in rows], ["Spike the search API", "Fix the page past the last one"])
        row = rows[1]
        self.assertEqual({key: row[key] for key in ("session", "agent", "folder", "space", "turns", "tokens", "cache",
                                                    "kind", "unpriced")},
                         {"session": SESSION, "agent": "claude", "folder": LUMEN, "space": "lumen-api", "turns": 2,
                          "tokens": 1_310_000, "cache": 68, "kind": "value", "unpriced": False})
        self.assertEqual(row["models"], [{"name": "Opus 5.5", "color": "#3987e5"},
                                         {"name": "Haiku 5.5", "color": "#199e70"}])
        self.assertAlmostEqual(row["cost"], 4.78)
        self.assertAlmostEqual(row["per_turn"], 2.39)
        self.assertEqual(row["tip"], "$2.39 a turn · 68% read from cache")

    def test_a_conversation_with_a_model_that_has_no_price_keeps_its_tokens(self):
        row = self.report()["conversations"][0]
        self.assertEqual((row["tokens"], round(row["cost"], 2), row["kind"], row["unpriced"], row["turns"]),
                         (1_760_000, 8.6, "spent", True, 2))

    def test_a_title_is_text_and_a_conversation_without_one_is_untitled(self):
        path = os.path.join(self.chats, "chat-index.json")
        with open(path, encoding="utf-8") as f:
            kept = json.load(f)
        first = next(one for one in kept["files"] if one.endswith(f"{SESSION}.jsonl"))
        kept["files"][first] = {"prompt": "Fix\x1b[31m the\npage " + "x" * 300}
        self.write(os.path.relpath(path, self.home), json.dumps(kept))
        titles = {one["session"]: one["title"] for one in self.report("30d")["conversations"]}
        self.assertEqual(titles[SESSION], "Fix[31m the page " + "x" * 63)
        self.assertEqual(titles[OTHER], "Untitled")

    def test_a_name_given_by_hand_is_the_title(self):
        self.write(".local/state/herdr/plugins/herdr-fold.sessions-view/names.json",
                   json.dumps({SESSION: {"name": "Paging"}, OTHER: {"name": "made up", "given": True}}))
        titles = {one["session"]: one["title"] for one in self.report("30d")["conversations"]}
        self.assertEqual((titles[SESSION], titles[OTHER]), ("Paging", "Untitled"))

    def test_the_models_table_tells_sub_agents_apart_and_no_price(self):
        rows = self.report()["models"]
        self.assertEqual([(one["name"], one["agent"], one["input"], one["write"], one["read"], one["output"],
                           one["cost"] and round(one["cost"], 2), one["kind"], one["text"]) for one in rows],
                         [("GPT-6 Astra", "Codex", 860_000, 0, 0, 0, 8.6, "spent", "$8.60"),
                          ("Opus 5.5", "Claude", 120_000, 100_000, 880_000, 10_000, 4.58, "value", "$4.58"),
                          ("Haiku 5.5", "Claude · sub-agents", 200_000, 0, 0, 0, 0.2, "value", "$0.20"),
                          ("Codex Auto Review", "Codex", 800_000, 0, 100_000, 0, None, "spent", "no price")])

    def test_one_agent_alone(self):
        found = self.report(agent="codex")
        self.assertEqual([one["key"] for one in found["summary"]],
                         ["Codex · API key", "Tokens", "Commits from these conversations"])
        self.assertEqual({one["agent"] for one in found["conversations"]}, {"codex"})
        with self.assertRaises(ValueError):
            self.report(agent="gemini")

    def test_one_folder_alone_with_what_is_under_it(self):
        self.write(f".claude/projects/-Users-dev-lumen-api-docs/{OTHER[:-1]}0.jsonl",
                   said("msg_07", at(11), session=OTHER[:-1] + "0", folder=LUMEN + "/docs", input=100_000)
                   + said("msg_08", at(11), session=OTHER[:-1] + "0", folder=LUMEN + "-old", input=100_000))
        self.write(f".claude/projects/-Users-dev-lumen-api-old/{OTHER[:-1]}1.jsonl",
                   said("msg_09", at(11), session=OTHER[:-1] + "1", folder=LUMEN + "-old", input=100_000))
        tokens.index(self.state, self.home)
        found = self.report(folder=LUMEN)
        self.assertEqual(sorted(one["folder"] for one in found["projects"]), [LUMEN, LUMEN + "/docs"])
        self.assertEqual([one["key"] for one in found["summary"]][0], "Claude · Max plan")


class Month(Used):
    def test_the_month_against_its_budget(self):
        report.set_budget(self.state, "codex", 50)
        found = self.report("today")                    # the month is the calendar's, whatever the period
        month = found["month"]
        self.assertEqual(found["months"], [month])
        self.assertEqual({key: month[key] for key in ("agent", "name", "key", "id", "label", "budget", "days", "day",
                                                      "over", "line", "end", "color")},
                         {"agent": "codex", "name": "Codex", "key": "Codex · API key", "id": "2026-11",
                          "label": "November", "budget": 50, "days": 30, "day": 12, "over": False,
                          "line": "~$18.40 of $50 · on pace for ~$46", "end": "Nov 30", "color": "#c98500"})
        self.assertEqual([[day, round(sum, 2)] for day, sum in month["spent"]],
                         [[1, 0]] + [[day, 9.8] for day in range(2, 10)] + [[10, 18.4], [11, 18.4], [12, 18.4]])
        self.assertAlmostEqual(month["today"], 18.4)
        self.assertAlmostEqual(month["pace"], 46)
        self.assertEqual(found["words"]["month"], "November, against its budget")
        # its words for both clients' lines and its folded row: the spent, the budget (no tilde), the pace; its level
        self.assertEqual((month["words"], month["level"]), ({"spent": "~$18.40", "of": "of $50",
                                                             "pace": "on pace for ~$46"}, "ok"))

    def test_a_months_level_is_the_open_blocks_yellow_once_over_and_none_without_a_budget(self):
        report.set_budget(self.state, "codex", 40)
        self.assertEqual(self.report()["month"]["level"], "warn")
        report.set_budget(self.state, "codex", None)
        month = self.report()["month"]
        self.assertEqual((month["words"]["of"], month["level"]), ("", None))

    def test_a_plan_has_no_month_and_a_budget_kept_for_it_is_not_shown(self):
        report.set_budget(self.state, "claude", 100)
        found = self.report(agent="claude")
        self.assertEqual((found["month"], found["months"]), (None, []))
        self.assertEqual(self.cell(found, "Claude")["line"], "no charge on the plan · week 16% of its limit")

    def test_the_pace_is_the_month_at_the_days_so_far(self):
        self.assertAlmostEqual(report.pace(18.40, 12, 30), 46)
        self.assertEqual(report.pace(0, 1, 31), 0)
        self.assertAlmostEqual(report.pace(45.10, 23, 30), 58.826, places=2)
        self.assertEqual(report.pace(5, 0, 30), 150)         # never by nothing: the first day counts whole

    def month(self, today, pace, budget=50):
        return {"agent": "codex", "name": "Codex", "id": "2026-11", "budget": budget, "today": today, "pace": pace,
                "end": "Nov 30", "to": NOW + 18 * DAY}

    def test_the_notice_from_four_fifths_of_the_budget_or_a_pace_past_it(self):
        self.assertEqual(report.notice(self.month(45.10, 58.2), [], NOW),
                         {"key": "codex:2026-11", "agent": "codex",
                          "text": "Codex has spent ~$45.10 of $50 this month · on pace for ~$58 by Nov 30"})
        self.assertEqual(report.notice(self.month(40, 48), [], NOW)["text"],
                         "Codex has spent ~$40.00 of $50 this month · on pace for ~$48 by Nov 30")
        self.assertEqual(report.notice(self.month(12, 51), [], NOW)["text"],
                         "Codex has spent ~$12.00 of $50 this month · on pace for ~$51 by Nov 30")
        self.assertIsNone(report.notice(self.month(39.99, 50), [], NOW))
        self.assertIsNone(report.notice(self.month(45.10, 58.2, budget=None), [], NOW))
        self.assertIsNone(report.notice(None, [], NOW))

    def test_a_notice_dismissed_stays_away_for_its_month(self):
        month = self.month(45.10, 58.2)
        self.assertIsNone(report.notice(month, ["codex:2026-11"], NOW))
        self.assertIsNotNone(report.notice(month, ["codex:2026-10", "claude:2026-11"], NOW))
        self.assertIsNone(report.notice(month, [], month["to"]))        # a month that is over says nothing

    def test_the_notices_of_this_home_and_one_dismissed(self):
        report.set_budget(self.state, "codex", 20)
        found = report.notices(self.state, NOW, agents=AGENTS, table=TABLE)
        self.assertEqual(found, [{"key": "codex:2026-11", "agent": "codex",
                                  "text": "Codex has spent ~$18.40 of $20 this month · on pace for ~$46 by Nov 30"}])
        report.dismiss(self.state, "codex:2026-11")
        self.assertEqual(report.notices(self.state, NOW, agents=AGENTS, table=TABLE), [])
        self.assertEqual(report.budget(self.state), {"codex": 20})      # the budget stays
        for key in ("codex", "gemini:2026-11", "codex:2026-13", "codex:2026-11\n", 7):
            with self.subTest(key=key), self.assertRaises(ValueError):
                report.dismiss(self.state, key)


class Budget(Used):
    def test_a_budget_is_kept_in_herdr_folds_own_state_its_owners_only(self):
        self.assertEqual(report.budget(self.state), {})
        self.assertEqual(report.BUDGET, usage.SETTINGS)          # one file, the blocks opened in Usage beside it
        self.assertEqual(report.set_budget(self.state, "codex", 50), {"codex": 50})
        self.assertEqual(report.set_budget(self.state, "claude", "$1,250.505"), {"codex": 50, "claude": 1250.51})
        path = os.path.join(self.state, "usage.json")
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"budgets": {"codex": 50, "claude": 1250.51}})
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertEqual(report.budget(self.state), {"codex": 50, "claude": 1250.51})

    def test_no_budget_takes_it_away(self):
        report.set_budget(self.state, "codex", 50)
        for none in (None, "", 0, "0"):
            with self.subTest(none=none):
                report.set_budget(self.state, "codex", 50)
                self.assertEqual(report.set_budget(self.state, "codex", none), {})

    def test_what_is_no_amount_or_no_agent_is_refused(self):
        report.set_budget(self.state, "codex", 50)
        for agent, dollars in (("codex", -1), ("codex", "fifty"), ("codex", True), ("codex", float("nan")),
                               ("codex", float("inf")), ("codex", 1_000_001), ("codex", "1e3"), ("codex", [50]),
                               ("codex", 0.001), ("gemini", 50), ("", 50), (None, 50), ("codex\n", 50)):
            with self.subTest(agent=agent, dollars=dollars), self.assertRaises(ValueError):
                report.set_budget(self.state, agent, dollars)
        self.assertEqual(report.budget(self.state), {"codex": 50})

    def test_a_damaged_file_is_no_budget(self):
        for kept in ("[]", "{", json.dumps({"budgets": []}),
                     json.dumps({"budgets": {"codex": "50", "gemini": 5, "claude": -2}})):
            with self.subTest(kept=kept):
                self.write(".local/state/herdr-fold/usage.json", kept)
                self.assertEqual(report.budget(self.state), {})


class Csv(Used):
    def test_its_head_and_a_row(self):
        lines = report.csv(self.state, self.home, "7d", now=NOW, agents=AGENTS, table=TABLE).split("\r\n")
        self.assertEqual(lines[0], "day,agent,model,conversation,space,input,cache_write_5m,cache_write_1h,"
                                   "cache_read,output,reasoning,searches,cost,kind")
        self.assertIn("2026-11-11,Claude,Opus 5.5,Fix the page past the last one,lumen-api,100000,0,0,0,0,0,0,"
                      "1.000000,value", lines)
        self.assertIn("2026-11-10,Codex,Codex Auto Review,Spike the search API,tidepool,800000,0,0,100000,0,0,0,,"
                      "spent", lines)
        self.assertEqual((len(lines), lines[-1]), (7, ""))
        self.assertEqual(lines[1:-1], sorted(lines[1:-1]))

    def test_a_title_never_starts_a_formula(self):
        path = os.path.join(self.chats, "chat-index.json")
        with open(path, encoding="utf-8") as f:
            kept = json.load(f)
        for entry in kept["files"].values():
            entry.update(prompt='=HYPERLINK("https://example.com", "x")', ai=None)
        self.write(os.path.relpath(path, self.home), json.dumps(kept))
        text = report.csv(self.state, self.home, "7d", now=NOW, agents=AGENTS, table=TABLE)
        self.assertIn(',"\'=HYPERLINK(""https://example.com"", ""x"")",', text)
        self.assertNotIn(",=", text)

    def test_its_files_name(self):
        self.assertEqual(self.report()["csv_name"], "herdr-fold usage 2026-11-06 to 2026-11-12.csv")


class Reads(Used):
    def test_nothing_is_written_but_herdr_folds_own_state(self):
        def tree():
            return {os.path.join(folder, name): os.stat(os.path.join(folder, name)).st_mtime_ns
                    for folder, _, names in os.walk(self.home) for name in names}
        before = tree()
        self.report("30d")
        report.csv(self.state, self.home, "30d", now=NOW, agents=AGENTS, table=TABLE)
        self.assertEqual(tree(), before)

    def test_the_prices_are_not_asked_for_with_the_daily_look_off(self):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("the network")):
            found = report.report(self.state, self.home, "7d", now=NOW, agents=AGENTS)
        self.assertEqual(found["prices_as_of"][-4:], "2026")

    def test_money_and_tokens_as_both_clients_write_them(self):
        self.assertEqual([report.money(n) for n in (0, 0.004, 4.126, 130.9, 1234.5)],
                         ["$0.00", "$0.00", "$4.13", "$130.90", "$1,234.50"])
        self.assertEqual([report.whole(n) for n in (50, 45.6, 1250.51, 1250)], ["$50", "$46", "$1,251", "$1,250"])
        self.assertEqual((report.money(130.9, about=True), report.whole(45.6, about=True)), ("~$130.90", "~$46"))
        self.assertEqual([report.short(n) for n in (0, 999, 1000, 68_400, 210_000, 999_950, 1_000_000, 38_240_000,
                                                    2_100_000_000)],
                         ["0", "999", "1.0k", "68k", "210k", "1.0M", "1.0M", "38.2M", "2.1B"])


class Cli(Used):
    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()), \
                mock.patch("time.time", return_value=NOW):
            code = report.main(["report.py", *args])
        return code, out.getvalue()

    def test_report_budget_csv_and_notice(self):
        code, out = self.run_cli("budget", "codex", "20")
        self.assertEqual((code, json.loads(out)), (0, {"codex": 20}))
        self.assertEqual(json.loads(self.run_cli("budget")[1]), {"codex": 20})
        agents = "--agents=" + json.dumps(AGENTS)
        code, out = self.run_cli("report", "7d", "codex", TIDEPOOL, agents, "--surface=#3b4252", "--text=#eceff4")
        found = json.loads(out)
        self.assertEqual((code, found["period"]["label"], found["summary"][0]["unit"]), (0, "7 days", "spent"))
        self.assertEqual(json.loads(self.run_cli("report", "month")[1])["summary"][0]["unit"], "API value")
        self.assertEqual(json.loads(self.run_cli("notice", agents)[1])["notices"][0]["key"], "codex:2026-11")
        self.assertEqual(self.run_cli("dismiss", "codex:2026-11"), (0, '{"ok": true}\n'))
        self.assertEqual(json.loads(self.run_cli("notice", agents)[1]), {"notices": []})
        code, out = self.run_cli("csv", "7d", agents)
        self.assertEqual((code, out.split("\r\n")[0][:10]), (0, "day,agent,"))

    def test_what_it_cannot_take_is_refused_with_its_usage(self):
        for args in ((), ("report",), ("report", "year"), ("report", "7d", "gemini"), ("budget", "codex"),
                     ("budget", "codex", "fifty"), ("dismiss", "codex"), ("csv",), ("report", "7d", "--agents=[")):
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(*args), (2, ""))

    def test_it_runs_alone_as_the_mod_runs_it(self):
        sys.path.insert(0, os.path.join(PACKAGE, "tools"))
        import build
        done = subprocess.run([sys.executable, "-c", build.runnable("report.py"), "budget"], capture_output=True,
                              text=True, env={**os.environ, "HOME": self.home}, timeout=60)
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "{}\n", ""))
