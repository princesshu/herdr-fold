"""Tests for core/calls.py in a temporary HOME: a media connector's calls today, each MCP tool call in today's Claude
chats (a subagent's too) and Codex chats counted by its server once, yesterday's and other tools' left out; a setup's
media services told what they make and their calls, the others untouched. The chats are invented."""
import os
import sys
import time

from support import PACKAGE

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import calls  # noqa: E402
import connectors  # noqa: E402
import test_core_tokens as made  # noqa: E402
from test_core_runs import codex_said, tool  # noqa: E402

NOW = time.mktime((2026, 11, 13, 15, 0, 0, 0, 0, -1))      # 15:00 on this machine's clock, the chats' day


def at(minute, day=13):
    """A line's time on this machine's clock, MINUTE past 10:00 on DAY of November 2026, as the agents write it."""
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.mktime((2026, 11, day, 10, minute, 0, 0, 0, -1))))


def stamped(text, stamp):
    return text.replace(made.stamp(0), stamp).replace(made.stamp(1), stamp)


class Today(made.Home):
    def chat(self, text, **where):
        path = self.session(text, **where)
        os.utime(path, (NOW - 60,) * 2)
        return path

    def test_each_servers_calls_since_midnight_once_by_their_id(self):
        self.chat(stamped(tool("mcp__fal__run_model", "t1", 0, prompt="harbour"), at(0))
                  + stamped(tool("mcp__fal__run_model", "t1", 0, prompt="harbour"), at(0))     # written again
                  + stamped(tool("mcp__fal__get_job_result", "t2", 1), at(1))
                  + stamped(tool("mcp__elevenlabs__creative_generate_speech", "t3", 1), at(1))
                  + stamped(tool("Bash", "t4", 1, command="ls"), at(1))
                  + stamped(tool("mcp__fal__run_model", "t5", 0), at(0, day=12)))             # yesterday's
        sub = self.sub(stamped(tool("mcp__claude_ai_Notion__search", "t6", 0), at(0)))
        os.utime(sub, (NOW - 60,) * 2)
        rollout = self.rollout(codex_said({"type": "function_call", "name": "run_model", "namespace": "mcp__fal",
                                           "call_id": "c1", "arguments": "{}"}, 0).replace(made.stamp(0), at(2)))
        os.utime(rollout, (NOW - 60,) * 2)
        self.assertEqual(calls.today(self.home, NOW), {"fal": 3, "elevenlabs": 1, "claude_ai_Notion": 1})

    def test_a_chat_last_written_before_midnight_is_not_read(self):
        path = self.chat(stamped(tool("mcp__fal__run_model", "t1", 0), at(0)))
        os.utime(path, (calls.midnight(NOW) - 60,) * 2)
        self.assertEqual(calls.today(self.home, NOW), {})

    def test_a_media_service_is_told_what_it_makes_and_its_calls_the_others_nothing(self):
        self.chat(stamped(tool("mcp__eleven-labs__creative_generate_speech", "t1", 0), at(0)))
        servers = [{"name": "eleven-labs", "brand": "elevenlabs"}, {"name": "runway", "brand": "runway"},
                   {"name": "sentry", "brand": "sentry"}]
        self.assertEqual(calls.counted(servers, self.home, NOW), [
            {"name": "eleven-labs", "brand": "elevenlabs", "makes": "voice", "today": 1},
            {"name": "runway", "brand": "runway", "makes": "video", "today": 0}, {"name": "sentry", "brand": "sentry"}])

    def test_every_media_service_is_a_known_brand(self):
        self.assertLessEqual(set(calls.MEDIA), set(connectors.BRANDS))
