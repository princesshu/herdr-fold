"""Tests for core/prices.py: each kind of token at its model's price from LiteLLM's table, fetched at most once a day
(never with the daily look switched off), the last kept or the bundled table when it cannot be had, a model's
color. Nothing here reaches the network: the asking is handed in, or urlopen is a stand-in."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from support import PACKAGE, set_env

sys.path.insert(0, os.path.join(PACKAGE, "core"))
sys.path.insert(0, os.path.join(PACKAGE, "src", "themes"))
import price_table  # noqa: E402
import prices  # noqa: E402
import tokens  # noqa: E402

DAY = 86400
NOW = 1794571200                # Friday, 13 November 2026, 12:00 UTC
M = 1_000_000
# rows as LiteLLM's map writes them, the prices invented
OPUS = {"litellm_provider": "anthropic", "mode": "chat", "input_cost_per_token": 5e-06,
        "output_cost_per_token": 2.5e-05, "cache_creation_input_token_cost": 6.25e-06,
        "cache_creation_input_token_cost_above_1hr": 1e-05, "cache_read_input_token_cost": 5e-07,
        "search_context_cost_per_query": {"search_context_size_low": 0.01, "search_context_size_medium": 0.01,
                                          "search_context_size_high": 0.01}}
GPT = {"litellm_provider": "openai", "mode": "chat", "input_cost_per_token": 1e-05, "output_cost_per_token": 5e-05,
       "cache_read_input_token_cost": 1e-06, "input_cost_per_token_above_272k_tokens": 2e-05,
       "output_cost_per_token_above_272k_tokens": 7.5e-05, "cache_read_input_token_cost_above_272k_tokens": 2e-06,
       "input_cost_per_token_batches": 5e-06}
MAP = {"sample_spec": {"input_cost_per_token": 0.0, "litellm_provider": "one of the providers"},
       "claude-opus-5-5": OPUS, "gpt-6-astra": GPT, "openai/gpt-6-astra-law": GPT,
       "claude-haiku-4-5-20251001": {**OPUS, "input_cost_per_token": 1e-06},
       "vertex_ai/claude-opus-5-5": {**OPUS, "litellm_provider": "vertex_ai", "input_cost_per_token": 9e-06},
       "dall-e-3": {"litellm_provider": "openai", "mode": "image_generation", "output_cost_per_image": 0.04},
       "broken": "not a row"}


def sums(**counts):
    return {**dict.fromkeys(tokens.KINDS, 0), "over": 0, **counts}


class Price(unittest.TestCase):
    def test_a_row_gives_each_kind_its_price(self):
        self.assertEqual(prices.price(OPUS), {"input": 5e-06, "output": 2.5e-05, "write_5m": 6.25e-06,
                                              "write_1h": 1e-05, "read": 5e-07, "reasoning": 2.5e-05, "search": 0.01,
                                              "above": {}})

    def test_a_missing_price_is_the_nearest_one(self):
        # no 1-hour price: the 5-minute one; no reasoning price: the output's; no cache price at all: the input's
        found = prices.price({"input_cost_per_token": 2e-06, "output_cost_per_token": 8e-06,
                              "cache_creation_input_token_cost": 3e-06})
        self.assertEqual((found["write_5m"], found["write_1h"], found["read"], found["reasoning"], found["search"]),
                         (3e-06, 3e-06, 2e-06, 8e-06, 0))
        own = prices.price({"input_cost_per_token": 2e-06, "output_cost_per_token": 8e-06,
                            "output_cost_per_reasoning_token": 9e-06})
        self.assertEqual((own["write_5m"], own["write_1h"], own["reasoning"]), (2e-06, 2e-06, 9e-06))

    def test_a_row_with_no_token_price_is_none(self):
        for row in ({"output_cost_per_image": 0.04}, {"input_cost_per_token": "free", "output_cost_per_token": 1e-06},
                    {"input_cost_per_token": True, "output_cost_per_token": 1e-06},
                    {"input_cost_per_token": -1, "output_cost_per_token": 1e-06}, "not a row", None):
            with self.subTest(row=row):
                self.assertIsNone(prices.price(row))

    def test_a_long_prompts_prices_are_kept_by_their_step(self):
        above = prices.price(GPT)["above"]
        self.assertEqual(list(above), ["272"])
        self.assertEqual((above["272"]["input"], above["272"]["output"], above["272"]["read"],
                          above["272"]["write_5m"]), (2e-05, 7.5e-05, 2e-06, 2e-05))

    def test_the_table_keeps_the_agents_own_makers_rows(self):
        # the rows a model's maker sells it by (anthropic, openai), each under its id: no reseller's, none unpriced
        self.assertEqual(sorted(prices.table(MAP)), ["claude-haiku-4-5-20251001", "claude-opus-5-5", "gpt-6-astra",
                                                     "openai/gpt-6-astra-law"])
        self.assertEqual(prices.table("nothing"), {})


class Cost(unittest.TestCase):
    def setUp(self):
        self.opus, self.gpt = prices.price(OPUS), prices.price(GPT)

    def test_each_kind_of_token_is_priced(self):
        self.assertAlmostEqual(prices.cost(sums(input=M), self.opus), 5.0)
        self.assertAlmostEqual(prices.cost(sums(read=M), self.opus), 0.5)
        self.assertAlmostEqual(prices.cost(sums(write_5m=M), self.opus), 6.25)
        self.assertAlmostEqual(prices.cost(sums(output=M), self.opus), 25.0)
        self.assertAlmostEqual(prices.cost(sums(searches=3), self.opus), 0.03)
        self.assertAlmostEqual(prices.cost(sums(input=1000, read=20_000, write_5m=400, write_1h=600, output=300,
                                                reasoning=200, searches=1), self.opus),
                               0.005 + 0.01 + 0.0025 + 0.006 + 0.0075 + 0.01)

    def test_the_one_hour_write_has_its_own_price(self):
        self.assertAlmostEqual(prices.cost(sums(write_1h=M), self.opus), 10.0)

    def test_reasoning_is_part_of_the_output_at_the_outputs_price(self):
        self.assertAlmostEqual(prices.cost(sums(output=M, reasoning=M // 2), self.opus), 25.0)
        own = prices.price({**OPUS, "output_cost_per_reasoning_token": 5e-05})
        self.assertAlmostEqual(prices.cost(sums(output=M, reasoning=M // 2), own), 12.5 + 25.0)

    def test_a_long_prompt_is_priced_at_its_step(self):
        self.assertAlmostEqual(prices.cost(sums(input=M, output=M), self.gpt), 10 + 50)
        self.assertAlmostEqual(prices.cost(sums(input=M, output=M, over=256), self.gpt), 10 + 50)
        self.assertAlmostEqual(prices.cost(sums(input=M, output=M, over=272), self.gpt), 20 + 75)
        self.assertAlmostEqual(prices.cost(sums(input=M, output=M, over=512), self.gpt), 20 + 75)

    def test_an_unpriced_model_is_none_never_zero(self):
        models = prices.table(MAP)
        row = sums(output=500)
        self.assertIsNone(prices.price_of("codex-auto-review", models))
        self.assertIsNone(prices.cost(row, prices.price_of("codex-auto-review", models)))
        self.assertEqual(row["output"], 500)                      # its tokens stay, shown alone
        self.assertEqual(prices.cost(sums(), self.opus), 0.0)

    def test_a_model_is_found_by_its_id_its_makers_prefix_or_without_its_date(self):
        models = prices.table(MAP)
        self.assertEqual(prices.price_of("claude-opus-5-5", models)["input"], 5e-06)
        self.assertEqual(prices.price_of("gpt-6-astra-law", models)["input"], 1e-05)
        self.assertEqual(prices.price_of("claude-opus-5-5-20261101", models)["input"], 5e-06)
        self.assertEqual(prices.price_of("claude-haiku-4-5-20251001", models)["input"], 1e-06)
        for model in ("claude-opus-5", "", None, 7):
            self.assertIsNone(prices.price_of(model, models))


class Kept(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_env(self, HOME=self.tmp, HERDR_FOLD_NO_UPDATE_CHECK=None)
        self.state = os.path.join(self.tmp, ".local", "state", "herdr-fold")
        self.asked = []
        patched = mock.patch.object(price_table, "AS_OF", "2026-11-01")       # the bundled table's day, for these
        patched.start()
        self.addCleanup(patched.stop)

    def fetch(self, answer=MAP):
        def asking():
            self.asked.append(1)
            return answer
        return asking

    def test_the_table_is_fetched_once_a_day(self):
        found = prices.prices(self.state, NOW, self.fetch())
        self.assertEqual((found["as_of"], found["source"]), ("2026-11-13", "fetched"))
        self.assertEqual(found["models"]["claude-opus-5-5"], prices.price(OPUS))
        again = prices.prices(self.state, NOW + DAY - 1, self.fetch())
        self.assertEqual((len(self.asked), again["as_of"], again["source"], again["models"]),
                         (1, "2026-11-13", "kept", found["models"]))
        later = prices.prices(self.state, NOW + DAY, self.fetch({"claude-opus-5-5": {**OPUS,
                                                                                      "input_cost_per_token": 4e-06}}))
        self.assertEqual((len(self.asked), later["as_of"], later["models"]["claude-opus-5-5"]["input"]),
                         (2, "2026-11-14", 4e-06))
        self.assertEqual(sorted(os.listdir(self.state)), ["prices.json", "prices.json.lock"])
        self.assertEqual(os.stat(os.path.join(self.state, "prices.json")).st_mode & 0o777, 0o600)

    def test_a_refused_fetch_keeps_the_last_table_and_waits_a_day(self):
        prices.prices(self.state, NOW, self.fetch())
        for answer in (None, {}, {"claude-opus-5-5": "gone"}, "<html>"):
            self.asked.clear()
            with self.subTest(answer=answer):
                found = prices.prices(self.state, NOW + 3 * DAY, self.fetch(answer))
                self.assertEqual((found["as_of"], found["source"], sorted(found["models"])),
                                 ("2026-11-13", "kept", sorted(prices.table(MAP))))
                prices.prices(self.state, NOW + 3 * DAY + 60, self.fetch(answer))
                self.assertEqual(len(self.asked), 1)
            with open(os.path.join(self.state, "prices.json"), encoding="utf-8") as f:
                kept = json.load(f)
            kept["asked"] = NOW
            with open(os.path.join(self.state, "prices.json"), "w", encoding="utf-8") as f:
                json.dump(kept, f)

    def test_with_nothing_kept_a_refused_fetch_gives_the_bundled_table(self):
        found = prices.prices(self.state, NOW, self.fetch(None))
        self.assertEqual((found["as_of"], found["source"]), (price_table.AS_OF, "bundled"))
        self.assertEqual(found["models"], prices.bundled())
        self.assertIn("claude-opus-5-5", found["models"])

    def test_a_kept_table_older_than_the_bundled_one_gives_way(self):
        # herdr-fold updated while the network is away: its own table is the newer
        early = NOW - 400 * DAY
        prices.prices(self.state, early, self.fetch())
        found = prices.prices(self.state, early + 60, self.fetch(None))
        self.assertEqual((found["source"], found["as_of"]), ("bundled", price_table.AS_OF))

    def test_switched_off_nothing_is_fetched(self):
        # the daily look's own switch (update.py's): the variable, or About's Check for updates automatically
        set_env(self, HERDR_FOLD_NO_UPDATE_CHECK="1")
        self.assertEqual(prices.prices(self.state, NOW, self.fetch())["source"], "bundled")
        set_env(self, HERDR_FOLD_NO_UPDATE_CHECK=None)
        os.makedirs(self.state)
        with open(os.path.join(self.state, "update.json"), "w", encoding="utf-8") as f:
            json.dump({"on": False}, f)
        self.assertEqual(prices.prices(self.state, NOW, self.fetch())["source"], "bundled")
        self.assertEqual(self.asked, [])
        with open(os.path.join(self.state, "update.json"), "w", encoding="utf-8") as f:
            json.dump({"on": True}, f)
        self.assertEqual(prices.prices(self.state, NOW, self.fetch())["source"], "fetched")
        set_env(self, HERDR_FOLD_NO_UPDATE_CHECK="1")
        self.assertEqual(prices.prices(self.state, NOW + 9 * DAY, self.fetch())["source"], "kept")     # the last one
        self.assertEqual(len(self.asked), 1)

    def test_a_damaged_kept_table_is_as_none(self):
        os.makedirs(self.state)
        for text in ("{", "[]", json.dumps({"asked": NOW, "as_of": 7, "models": {"x": 1}}),
                     json.dumps({"asked": NOW, "as_of": "2099-01-01", "models": {"x": {"input": "1"}}})):
            with open(os.path.join(self.state, "prices.json"), "w", encoding="utf-8") as f:
                f.write(text)
            with self.subTest(text=text):
                self.assertEqual(prices.prices(self.state, NOW + 60, self.fetch(None))["source"], "bundled")

    def test_the_command_answers_the_table(self):
        set_env(self, HERDR_FOLD_NO_UPDATE_CHECK="1")
        out = io.StringIO()
        refused = mock.patch.object(prices.urllib.request, "urlopen", side_effect=AssertionError("the network"))
        with contextlib.redirect_stdout(out), refused:
            self.assertEqual(prices.main(["prices.py", "table"]), 0)
        self.assertEqual(json.loads(out.getvalue())["source"], "bundled")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(prices.main(["prices.py"]), 2)
        self.assertIn("usage: prices.py", err.getvalue())


class Fetch(unittest.TestCase):
    """What is asked of the network, through a stand-in urlopen."""

    def answer(self, body):
        class Answer(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False
        return Answer(body)

    def test_the_request_is_the_address_alone(self):
        asked = []

        def urlopen(request, timeout):
            asked.append((request.full_url, request.get_method(), dict(request.header_items()), request.data, timeout))
            return self.answer(json.dumps(MAP).encode())

        with mock.patch.object(prices.urllib.request, "urlopen", urlopen):
            self.assertEqual(prices.fetch(), MAP)
        self.assertEqual(asked, [(prices.PRICES_URL, "GET", {"User-agent": "herdr-fold"}, None, 20)])
        self.assertTrue(prices.PRICES_URL.startswith("https://raw.githubusercontent.com/BerriAI/litellm/"))

    def test_a_refusal_a_damaged_or_an_oversized_answer_is_none(self):
        def refusing(request, timeout):
            raise OSError("no network")

        large = b'{"x": "' + b"a" * prices.LARGEST + b'"}'
        for urlopen in (refusing, lambda *_, **__: self.answer(b"<html>"), lambda *_, **__: self.answer(large),
                        lambda *_, **__: self.answer(b"[1]")):
            with mock.patch.object(prices.urllib.request, "urlopen", urlopen):
                self.assertIsNone(prices.fetch())


class Bundled(unittest.TestCase):
    def test_the_bundled_table_prices_the_models_in_use(self):
        models = prices.bundled()
        for model in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-haiku-4-5-20251001",
                      "gpt-6-astra", "gpt-5-codex"):
            with self.subTest(model):
                found = prices.price_of(model, models)
                self.assertTrue(0 < found["read"] <= found["input"] <= found["write_5m"] <= found["write_1h"]
                                and found["input"] < found["output"] <= found["reasoning"], found)
        self.assertRegex(price_table.AS_OF, r"^20\d\d-\d\d-\d\d$")

    def test_every_bundled_step_is_one_a_message_can_tell(self):
        # a long prompt's price applies from a step tokens.py tells (STEPS): a new one in the table fails here
        steps = {step for one in prices.bundled().values() for step in one["above"]}
        self.assertTrue(steps)
        self.assertLessEqual(steps, {str(step) for step in tokens.STEPS})

    def test_the_bundled_table_is_what_the_tool_writes(self):
        # tools/prices.py's own rows and form: a hand edit, or a change of the tool without a run, fails here
        spec = importlib.util.spec_from_file_location("tools_prices", os.path.join(PACKAGE, "tools", "prices.py"))
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        with open(os.path.join(PACKAGE, "core", "price_table.py"), encoding="utf-8") as f:
            self.assertEqual(f.read(), tool.source(price_table.AS_OF, price_table.MODELS))


class Models(unittest.TestCase):
    def test_the_four_families_keep_the_mockups_colors(self):
        for model, color in (("claude-opus-5-5", "#3987e5"), ("claude-opus-4-8", "#3987e5"),
                             ("claude-sonnet-5-5", "#d95926"), ("claude-haiku-4-5-20251001", "#199e70"),
                             ("gpt-6-astra", "#c98500"), ("gpt-5-codex", "#c98500"),
                             ("codex-auto-review", "#c98500")):
            with self.subTest(model):
                self.assertEqual(prices.model_color(model, []), color)
                self.assertEqual(prices.model_color(model, ["claude-fable-5-2", "gpt-6-astra", model]), color)

    def test_another_family_takes_the_next_slot_in_order_of_first_use_and_keeps_it(self):
        seen = ["claude-opus-5-5", "claude-fable-5-2", "gpt-6-astra", "claude-mythos-5", "claude-fable-5-1"]
        self.assertEqual([prices.model_color(model, seen) for model in seen],
                         ["#3987e5", prices.NEXT[0], "#c98500", prices.NEXT[1], prices.NEXT[0]])
        self.assertEqual(prices.model_color("claude-fable-5-2", seen + ["llama-9"]), prices.NEXT[0])     # stable
        self.assertEqual(prices.model_color("llama-9", seen), prices.NEXT[2])                # not yet in SEEN: next
        many = [f"maker{n}-large" for n in range(6)]
        self.assertEqual([prices.model_color(model, many) for model in many], list(prices.NEXT) + [prices.REST] * 2)

    def test_every_slot_reads_on_every_app_themes_surface(self):
        # a mark's 3:1 against the card it is drawn on, in all 13 themes: a slot that reads less there (Nord's
        # lighter card) is moved toward the theme's text, as a source's tag is, and stays the mockups' elsewhere
        import apply
        models = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "gpt-6-astra"] \
            + [f"maker{n}-large" for n in range(5)]
        slots = list(prices.SLOTS.values()) + list(prices.NEXT) + [prices.REST]
        self.assertEqual(len(set(slots)), 9)
        themes = os.path.join(PACKAGE, "app", "themes")
        self.assertEqual(len(os.listdir(themes)), 13)
        for name in sorted(os.listdir(themes)):
            with open(os.path.join(themes, name), encoding="utf-8") as f:
                colors = json.load(f)["colors"]
            surface, text = colors["surface"], colors["foreground"]
            made = [prices.model_color(model, models, surface, text) for model in models]
            self.assertEqual(len(set(made)), 9, name)
            for model, slot, color in zip(models, slots, made):
                with self.subTest(theme=name, model=model):
                    self.assertGreaterEqual(apply.contrast(color, surface), 3)
                    if apply.contrast(slot, surface) >= 3:
                        self.assertEqual(color, slot)
                    else:
                        self.assertEqual(color, apply.readable(slot, text, surface, 3))

    def test_a_color_is_the_slots_own_where_the_theme_is_not_told(self):
        self.assertEqual(prices.model_color("claude-opus-5-5", [], "#3b4252", "#eceff4"), "#4b91e6")    # Nord's
        self.assertEqual(prices.model_color("claude-opus-5-5", [], "#1e1e2e", "#cdd6f4"), "#3987e5")
        for surface, text in ((None, None), ("#3b4252", None), ("red", "#eceff4"), ("#3b4252", "#eceff")):
            with self.subTest(surface=surface, text=text):
                self.assertEqual(prices.model_color("claude-opus-5-5", [], surface, text), "#3987e5")


if __name__ == "__main__":
    unittest.main()
