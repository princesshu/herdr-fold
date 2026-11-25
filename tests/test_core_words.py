"""Tests for core/words.py: how both clients say a model (its name, its family, its context window) and a figure (a
token count by the number rule, a share as a percent)."""
import importlib.util
import json
import os
import sys
import unittest

from support import PACKAGE

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import model_windows  # noqa: E402
import prices  # noqa: E402
import words  # noqa: E402


class Tokens(unittest.TestCase):
    def test_the_number_rule(self):
        # whole under 1,000; one decimal under 100k; whole to 999k; one decimal from 1M: never <0.1k or 0.06M
        for count, said in ((0, "0"), (30, "30"), (999, "999"), (1000, "1.0k"), (5949, "5.9k"), (21_400, "21.4k"),
                            (99_949, "99.9k"), (99_950, "100k"), (120_000, "120k"), (999_499, "999k"),
                            (999_500, "1.0M"), (60_000, "60.0k"), (1_200_000, "1.2M"), (38_200_000, "38.2M"),
                            (2_100_000_000, "2.1B")):
            with self.subTest(count):
                self.assertEqual(words.tokens(count), said)

    def test_a_share_as_a_whole_percent_never_0_for_some(self):
        for share, said in ((0, "0%"), (0.004, "<1%"), (0.005, "1%"), (0.84, "84%"), (0.9, "90%"), (1, "100%")):
            with self.subTest(share):
                self.assertEqual(words.percent(share), said)


class Models(unittest.TestCase):
    def test_a_model_is_named_as_people_say_it(self):
        for model, name in (("claude-opus-5-5", "Opus 5.5"), ("claude-haiku-4-5-20251001", "Haiku 4.5"),
                            ("claude-opus-5", "Opus 5"), ("claude-3-5-sonnet-20241022", "Sonnet 3.5"),
                            ("claude-mythos-preview", "Mythos Preview"), ("anthropic/claude-sonnet-5-5", "Sonnet 5.5"),
                            ("claude-opus-5-5[1m]", "Opus 5.5"), ("Opus 5.5", "Opus 5.5"),
                            ("gpt-5-codex", "GPT-5 Codex"),
                            ("gpt-6.2-astra", "GPT-6.2 Astra"), ("gpt-5.1-codex-max", "GPT-5.1 Codex Max"),
                            ("codex-auto-review", "Codex Auto Review"), ("o3", "o3"), ("unknown", "Unknown"),
                            ("", ""), (None, "")):
            with self.subTest(model):
                self.assertEqual(words.model_name(model), name)

    def test_a_models_family(self):
        for model, family in (("claude-opus-5-5", "opus"), ("claude-3-5-sonnet-20241022", "sonnet"),
                              ("opus", "opus"), ("haiku[1m]", "haiku"), ("gpt-5.2-codex", "codex"), ("o3", "codex"),
                              ("claude-fable-5-2", "fable"), ("", "")):
            with self.subTest(model):
                self.assertEqual(words.family(model), family)

    def test_a_models_context_window_is_the_price_tables(self):
        self.assertEqual(words.window("claude-opus-5-5"), model_windows.WINDOWS["claude-opus-5-5"])
        self.assertEqual(words.window("claude-sonnet-4-5-20250929"), model_windows.WINDOWS["claude-sonnet-4-5"])
        self.assertEqual(words.window("anthropic/claude-sonnet-4-5"), model_windows.WINDOWS["claude-sonnet-4-5"])
        self.assertEqual(words.window("claude-sonnet-4-5[1m]"), 1_000_000)        # Claude's own 1M spelling
        for model in ("llama-9", "", None, "opus"):
            with self.subTest(model):
                self.assertIsNone(words.window(model))

    def test_opus_5_5_and_later_keep_an_effort_of_their_own(self):
        # Claude's modelSettings.<id>.effortLevel: the id without a date or a [1m], an alias's the table's newest
        newest = max((id for id in model_windows.WINDOWS if id.startswith("claude-opus-")),
                     key=lambda id: [int(part) for part in id.split("-")[2:] if part.isdigit()])
        for model, own in (("claude-opus-5-5", "claude-opus-5-5"), ("claude-opus-5-5-20261101", "claude-opus-5-5"),
                           ("claude-opus-5-5[1m]", "claude-opus-5-5"), ("claude-opus-6", "claude-opus-6"),
                           ("opus", newest), ("opus[1m]", newest), ("claude-opus-5", None),
                           ("claude-opus-4-8", None), ("sonnet", None), ("claude-sonnet-5-5", None),
                           ("gpt-5.3-codex", None), ("", None), (None, None)):
            with self.subTest(model):
                self.assertEqual(words.own_effort(model), own)
        self.assertEqual(words.own_effort("opus"), "claude-opus-5-5")       # today's table

    def test_the_windows_are_what_the_tool_writes(self):
        # tools/prices.py's, from the map's max_input_tokens beside the prices: a hand edit fails here
        spec = importlib.util.spec_from_file_location("tools_prices", os.path.join(PACKAGE, "tools", "prices.py"))
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        with open(os.path.join(PACKAGE, "core", "model_windows.py"), encoding="utf-8") as f:
            self.assertEqual(f.read(), tool.windows_source(model_windows.WINDOWS))
        self.assertTrue(all(type(n) is int and n > 0 for n in model_windows.WINDOWS.values()))
        self.assertEqual(tool.windows({"claude-opus-5-5": {"litellm_provider": "anthropic",
                                                           "max_input_tokens": 1000000},
                                       "claude-opus-5-5-20261101": {"litellm_provider": "anthropic",
                                                                    "max_input_tokens": 1000000},
                                       "gpt-5-codex": {"litellm_provider": "openai", "max_input_tokens": 272000},
                                       "vertex_ai/claude-x": {"litellm_provider": "vertex_ai", "max_input_tokens": 9},
                                       "claude-none": {"litellm_provider": "anthropic", "max_input_tokens": "1M"}},
                                      prices),
                         {"claude-opus-5-5": 1000000, "gpt-5-codex": 272000})
        self.assertEqual(json.loads(json.dumps(model_windows.WINDOWS)), model_windows.WINDOWS)


if __name__ == "__main__":
    unittest.main()
