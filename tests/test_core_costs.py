"""Tests for core/costs.py in a temporary HOME: one chat's cost by its agent and its subagents, each with its model,
turns, tokens, share and inspector lines. The sessions and prices are invented (usage.html's lumen-api); nothing here
reaches the network."""
import contextlib
import io
import json
import os
import sys

from support import PACKAGE, set_env

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import costs  # noqa: E402
import prices  # noqa: E402
import test_core_tokens as made  # noqa: E402
import tokens  # noqa: E402

OPUS, HAIKU, GPT, REVIEW = "claude-opus-5-5", "claude-haiku-5-5", "gpt-6-astra", "codex-auto-review"
PLAN = [{"key": "claude", "name": "Claude", "plan": "Max"}, {"key": "codex", "name": "Codex", "plan": "API key"}]
# invented prices, dollars a token, that make usage.html's figures: Opus's conversation $3.70, Haiku's subagent $0.42
TABLE = {"as_of": "2026-11-09", "source": "kept", "models": {
    OPUS: prices.price({"input_cost_per_token": 1e-5, "output_cost_per_token": 1.6e-5,
                        "cache_creation_input_token_cost": 1e-5,
                        "cache_creation_input_token_cost_above_1hr": 1.5e-5, "cache_read_input_token_cost": 1e-6}),
    HAIKU: prices.price({"input_cost_per_token": 2e-6, "output_cost_per_token": 1e-5}),
    GPT: prices.price({"input_cost_per_token": 1e-5, "output_cost_per_token": 0})}}


class Conversation(made.Home):
    """usage.html's conversation: Opus's 38 turns of a million tokens, and an Explore subagent on Haiku."""

    def setUp(self):
        super().setUp()
        set_env(self, HERDR_FOLD_NO_UPDATE_CHECK="1")
        self.turns = made.said("msg_01", input=30_000, write_1h=90_000, write_5m=30_000, read=790_000,
                               output=60_000) + "".join(made.said(f"msg_{n:02d}", minute=n) for n in range(2, 39))
        self.path = self.session(self.turns)
        self.sub(made.said("msg_50", minute=5, model=HAIKU, sidechain=True, input=210_000))

    def costs(self, agent="claude", path=None, agents=PLAN, **more):
        tokens.index(self.state, self.home)
        return costs.costs(self.state, agent, path or self.path, agents=agents, table=TABLE, **more)

    def test_the_agent_and_its_sub_agent_each_with_cost_model_turns_tokens_and_share(self):
        found = self.costs()
        self.assertEqual((found["session"], found["kind"], found["text"], found["tokens"]),
                         (made.SESSION, "API value", "~$4.12", "1.2M"))
        agent, sub = found["agent"], found["subs"]["Explore"]
        self.assertAlmostEqual(agent["cost"], 3.70)
        self.assertEqual((agent["text"], agent["sub"], agent["turns"], agent["tokens"], round(agent["share"], 2)),
                         ("~$3.70", "Opus 5.5 · 38 turns · 1.0M tokens", 38, 1_000_000, 0.9))
        self.assertEqual(agent["model"], {"id": OPUS, "name": "Opus 5.5", "color": "#3987e5"})
        self.assertEqual(agent["title"], "~$3.70 API value")
        self.assertAlmostEqual(sub["cost"], 0.42)
        self.assertEqual((sub["text"], sub["sub"], round(sub["share"], 2), sub["model"]["color"]),
                         ("~$0.42", "Haiku 5.5 · 210k tokens", 0.1, "#199e70"))
        self.assertEqual(list(found["subs"]), ["Explore"])

    def test_the_agents_lines_are_label_value_and_a_short_note(self):
        # the number rule, the cache's writes as one, each agent's share beside a subagent
        self.assertEqual(self.costs()["agent"]["lines"], [
            ["Model", "Opus 5.5", None], ["Input", "30.0k", None], ["Cache write", "120k", None],
            ["Cache read", "790k", "84% of its input"], ["Output", "60.0k", None], ["Share", "90% of this chat", None]])
        self.assertEqual(self.costs()["subs"]["Explore"]["lines"], [
            ["Model", "Haiku 5.5", None], ["Input", "210k", None], ["Cache write", "0", None],
            ["Cache read", "0", None], ["Output", "0", None], ["Share", "10% of this chat", None]])

    def test_with_no_sub_agent_no_share(self):
        other = self.session(made.said("msg_70", session=made.OTHER, input=370_000), made.OTHER)
        found = self.costs(path=other)
        self.assertEqual([line[0] for line in found["agent"]["lines"]],
                         ["Model", "Input", "Cache write", "Cache read", "Output"])
        self.assertEqual((found["subs"], round(found["agent"]["share"], 2)), ({}, 1.0))

    def test_an_api_keys_cost_is_spent_and_an_untold_agent_is_never_spent(self):
        key = [{"key": "claude", "name": "Claude", "plan": "API key"}]
        self.assertEqual((self.costs(agents=key)["kind"], self.costs(agents=key)["agent"]["title"]),
                         ("spent", "~$3.70 spent"))
        self.assertEqual(self.costs(agents=None)["kind"], "API value")

    def test_a_model_with_no_price_shows_its_tokens_and_no_price_never_zero_dollars(self):
        self.session(made.said("msg_01", model="claude-nova-9", input=68_400))
        os.remove(self.path[:-len(".jsonl")] + "/subagents/agent-a1b2c3.jsonl")
        found = self.costs()
        self.assertEqual((found["text"], found["agent"]["cost"], found["agent"]["text"], found["agent"]["title"]),
                         ("no price", None, "no price", "no price"))
        self.assertEqual(found["agent"]["sub"], "Nova 9 · 1 turn · 68.4k tokens")
        self.assertNotIn("$", json.dumps(found))

    def test_two_models_name_the_one_that_took_the_most_and_list_both(self):
        self.session(self.turns + made.said("msg_60", minute=40, model=HAIKU, input=1000))
        agent = self.costs()["agent"]
        self.assertEqual((agent["model"]["name"], agent["lines"][0], agent["turns"]),
                         ("Opus 5.5", ["Model", "Opus 5.5, Haiku 5.5", None], 39))

    def test_a_models_color_is_lifted_on_a_theme_where_it_would_not_read(self):
        nord = self.costs(theme=("#3b4252", "#eceff4"))
        self.assertEqual((nord["agent"]["model"]["color"], nord["subs"]["Explore"]["model"]["color"]),
                         ("#4b91e6", "#2ea67d"))

    def test_a_codex_rollout_by_its_turns_models(self):
        path = self.write(f".codex/sessions/2026/11/13/rollout-2026-11-13T10-00-00-{made.THREAD}.jsonl",
                          made.meta() + made.turn(GPT) + made.record("resp_01", input_tokens=860_000)
                          + made.record("resp_02", minute=2, output_tokens=40_000))
        found = self.costs("codex", path)
        self.assertEqual((found["session"], found["kind"], found["text"]), (made.THREAD, "spent", "~$8.60"))
        self.assertEqual(found["agent"]["sub"], "GPT-6 Astra · 2 turns · 900k tokens")
        self.assertEqual([line[0] for line in found["agent"]["lines"]],
                         ["Model", "Input", "Cache write", "Cache read", "Output"])         # one agent: no share

    def test_a_conversation_with_no_messages_yet_has_no_costs(self):
        empty = self.session(made.asked(), session=made.OTHER)
        self.assertIsNone(self.costs(path=empty))
        self.assertIsNone(self.costs(path=os.path.join(self.home, "none.jsonl")))

    def test_nothing_of_the_agents_is_written(self):
        def files():
            return {os.path.join(here, name): os.stat(os.path.join(here, name)).st_mtime_ns
                    for base in (".claude", ".codex") for here, _, names in os.walk(os.path.join(self.home, base))
                    for name in names}
        before = files()
        self.costs()
        self.assertEqual(files(), before)

    def test_the_cli_brings_the_index_up_to_date_and_answers_in_json(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = costs.main(["costs.py", "claude", self.path, "--agents=" + json.dumps(PLAN)])
        found = json.loads(out.getvalue())
        self.assertEqual((code, found["session"], found["agent"]["turns"], found["left"]), (0, made.SESSION, 38, 0))
        with contextlib.redirect_stderr(io.StringIO()) as said:
            self.assertEqual(costs.main(["costs.py", "gemini", self.path]), 2)
            self.assertEqual(costs.main(["costs.py", "claude", self.path, "--agents=not json"]), 2)
        self.assertIn("usage: costs.py", said.getvalue())

    def test_the_whole_says_its_tokens_and_how_much_of_the_prompt_came_from_the_cache(self):
        self.assertEqual(self.costs()["line"], "1.2M tokens · 69% from cache")      # 790k of a prompt of 1.15M
        self.session(made.said("msg_90", output=500), session=made.OTHER)
        other = os.path.join(os.path.dirname(self.path), f"{made.OTHER}.jsonl")
        self.assertEqual(self.costs(path=other)["line"], "500 tokens")               # no prompt: no share said

    def test_a_conversation_is_found_by_its_id_too_and_the_cli_takes_one(self):
        tokens.index(self.state, self.home)
        self.assertEqual(costs.filed(self.state, "claude", made.SESSION), self.path)
        self.assertIsNone(costs.filed(self.state, "claude", "no-such-session"))
        self.assertIsNone(costs.filed(self.state, "codex", made.SESSION))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = costs.main(["costs.py", "claude", made.SESSION, "--agents=" + json.dumps(PLAN)])
        found = json.loads(out.getvalue())
        self.assertEqual((code, found["session"], found["agent"]["turns"]), (0, made.SESSION, 38))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(costs.main(["costs.py", "claude", "no-such-session"]), 0)
        self.assertIsNone(json.loads(out.getvalue()))
