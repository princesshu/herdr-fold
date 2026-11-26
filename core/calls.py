"""A media connector's calls today, for the Agent panel's rows in both clients (these services bill in credits, not
tokens): each MCP tool call in today's Claude chats (their subagents' too) and Codex chats on this machine, counted by
its server, each once by its id. Only read; a module of its own, so the graph's helper does not carry it."""
import calendar
import glob
import os
import re
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
from jsonl import obj, open_regular, parse  # noqa: E402

# what each media service makes (connectors.py's brands), its row's note
MEDIA = {"bfl": "image", "cartesia": "voice", "elevenlabs": "voice", "fal": "image, video",
         "higgsfield": "image, video", "luma": "video", "meshy": "3D", "runway": "video"}
CLAUDE = b'"name":"mcp__'       # a line with a call of a server's tool, as Claude writes it
CODEX = b'"namespace":"mcp__'   # and as Codex does (its tool's name apart, the server's in its namespace)


def key(name):
    """A server's NAME as both agents' tools carry it, one way: every character but a letter or a digit as _."""
    return re.sub(r"[^A-Za-z0-9]", "_", name)


def midnight(now=None):
    """Today's start on this machine's clock, in seconds since 1970."""
    return time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1))


def made_at(stamp):
    """A line's time (2026-11-25T10:05:00.000Z) in seconds since 1970, or None."""
    try:
        return calendar.timegm(time.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S")) if isinstance(stamp, str) else None
    except ValueError:
        return None


def called(entry):
    """The calls of a server's tool a line ENTRY holds: (its id, its server's key) each, Claude's or Codex's."""
    payload, content = obj(entry.get("payload")), obj(entry.get("message")).get("content")
    if payload.get("type") == "function_call" and str(payload.get("namespace", "")).startswith("mcp__"):
        return [(payload.get("call_id"), key(payload["namespace"][len("mcp__"):]))]
    return [(block.get("id"), key(block["name"][len("mcp__"):].partition("__")[0])) for block in map(obj, content)
            if block.get("type") == "tool_use" and str(block.get("name", "")).startswith("mcp__")] \
        if isinstance(content, list) else []


def today(home, now=None):
    """Each server's calls since midnight, {its key: calls}."""
    since, found, seen = midnight(now), {}, set()
    projects = os.path.join(glob.escape(home), ".claude", "projects", "*")
    for path, mark in [(one, CLAUDE) for one in glob.glob(os.path.join(projects, "*.jsonl")) + glob.glob(
            os.path.join(projects, "*", "subagents", "agent-*.jsonl"))] + [(one, CODEX) for one in glob.glob(
            os.path.join(glob.escape(home), ".codex", "sessions", "*", "*", "*", "rollout-*.jsonl"))]:
        try:
            if os.stat(path).st_mtime < since:
                continue
            with open_regular(path, "rb") as f:
                data = f.read()
        except OSError:
            continue
        at = data.find(mark)
        while at >= 0:
            end = data.find(b"\n", at)
            end = len(data) if end < 0 else end
            entry = parse(data[data.rfind(b"\n", 0, at) + 1:end])
            for id, server in called(entry) if (made_at(entry.get("timestamp")) or 0) >= since else ():
                if id not in seen:
                    seen.add(id)
                    found[server] = found.get(server, 0) + 1
            at = data.find(mark, end + 1)
    return found


def counted(servers, home, now=None):
    """SERVERS (a setup's), each media service's with what it "makes" and its calls "today"."""
    found = today(home, now)
    for one in servers:
        if one["brand"] in MEDIA:
            one.update(makes=MEDIA[one["brand"]], today=found.get(key(one["name"]), 0))
    return servers
