"""Rich copy: herdr's own pbcopy runs this after copying a selection as plain text. A Claude/Codex reply excerpt is
found in the conversation file by the order of its visible words (the screen hides Markdown marks and wraps lines) and
added as HTML and RTF, unless the clipboard changed meanwhile. Writes to the clipboard on macOS only."""
import collections
import itertools
import os
import re
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins", "sidebar"))   # reader, format
from conversations import TAIL, folder_files, messages, session_files  # noqa: E402
from herdrlib import AGENTS, agents  # noqa: E402
from i18n import t  # noqa: E402
from richtext import copy_rich  # noqa: E402
GUESSES = 3                                                     # conversations of a folder looked in, the newest
WORD = re.compile(r"[^\W_]+")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")                  # [text](url): the url is not visible
FENCE = re.compile(r"^[ \t]*(```|~~~)([^\n]*)$", re.M)          # the code block's language is not visible
INLINE = ("**", "~~", "`")


# ---------------------------------------------------------------------------------------------------------------
# The conversations' replies (newest first)
# ---------------------------------------------------------------------------------------------------------------

def replies(kind, path):
    """The agent's replies in the conversation in PATH, the newest first: of its last TAIL bytes, where a reply still
    on screen is (a conversation is hundreds of megabytes, and every open one is looked in on each copy)."""
    return [text for role, text in messages(kind, path, tail=TAIL) if role == "assistant"][::-1]


def open_sessions():
    """(kind, conversation file) for the local agents running in herdr — the focused one first. Where herdr has no
    conversation for an agent (it was not told one), the newest few started in the agent's folder."""
    try:
        running = agents()
    except OSError:                             # no herdr on this machine
        return []
    found = []
    for agent in sorted(running, key=lambda a: not a.get("focused")):
        kind, session = agent.get("agent"), (agent.get("agent_session") or {}).get("value")
        if kind not in AGENTS:
            continue
        if session:
            found += [(kind, path) for path in session_files(kind, session)]
        elif agent.get("cwd"):
            found += [(kind, path) for path in itertools.islice(folder_files(kind, agent["cwd"]), GUESSES)]
    return found


# ---------------------------------------------------------------------------------------------------------------
# The selection → the Markdown excerpt
# ---------------------------------------------------------------------------------------------------------------

def visible_words(md):
    """The Markdown's words that stay visible when rendered, with their positions in the source."""
    hidden = [m.span(1) for m in LINK.finditer(md)] + [m.span(2) for m in FENCE.finditer(md)]
    return [(m.group(), m.start(), m.end()) for m in WORD.finditer(md)
            if not any(a <= m.start() < b for a, b in hidden)]


def locate(words, md):
    """(start, end) in the source: the first place where the selection's start and end (3 words each) appear in order,
    with almost every word of the selection in between (wrapped table cells may be out of order). A word cut in
    half at either edge still matches."""
    vw = visible_words(md)
    toks = [w for w, _, _ in vw]
    n, k = len(words), min(3, len(words))
    head, tail, need = words[:k], words[-k:], collections.Counter(words[1:-1])
    for i in range(len(toks)):
        if not (toks[i].endswith(head[0]) and toks[i + 1:i + k] == head[1:]):
            continue
        for j in range(i + n - 1, min(len(toks), i + int(n * 1.15) + 3)):
            if toks[j].startswith(tail[-1]) and toks[j - k + 1:j] == tail[:-1]:
                span = collections.Counter(toks[i:j + 1])
                if sum(min(c, span[w]) for w, c in need.items()) >= 0.97 * sum(need.values()):
                    return vw[i][1], vw[j][2]
    return None


def line_bounds(md, pos):
    start = md.rfind("\n", 0, pos) + 1
    end = md.find("\n", pos)
    return start, len(md) if end < 0 else end


def excerpt(md, a, b):
    """Valid Markdown around the matched words (a..b): from the start / to the end of the line if the selection starts /
    ends there (keeping list and heading marks and the table edge); tables with their header, code with the code
    fence; a **, ~~, ` or link cut in half gets closed."""
    ls, le = line_bounds(md, a)
    first = [s for _, s, _ in visible_words(md[ls:le])]
    if first and a == ls + first[0]:
        a = ls
    ls_b, le_b = line_bounds(md, b)
    last = [e for _, _, e in visible_words(md[ls_b:le_b])]
    if last and b == ls_b + last[-1]:
        b = le_b
    fences = [m for m in FENCE.finditer(md)]
    opened = [m for m in fences if m.start() < a]
    if len(opened) % 2:                                       # starts inside a code block
        a = opened[-1].start()
    closes = [m for m in fences if a <= m.start() < b]
    suffix = "\n" + closes[0].group(1) if len(closes) % 2 else ""
    if not len(opened) % 2 and not len(closes) % 2:
        ls, le = line_bounds(md, a)
        prefix = md[ls:a]
        for mark in INLINE:                                   # mark opened earlier on the line → back to it
            if prefix.count(mark) % 2:
                a = ls + prefix.rfind(mark)
                prefix = md[ls:a]
        ls_b, le_b = line_bounds(md, b)
        for mark in INLINE:                                   # mark left open → on to its closing mark (same line)
            if md[max(a, ls_b):b].count(mark) % 2:
                close = md.find(mark, b, le_b)
                if close >= 0:
                    b = close + len(mark)
        start_link = md.rfind("[", ls_b, b)
        if start_link >= 0 and "](" not in md[start_link:b] and md.find("](", b, le_b) >= 0:
            b = md.find(")", md.find("](", b, le_b)) + 1      # ends inside the link text
    text = md[a:b]
    rows = text.split("\n")
    if rows[0].lstrip().startswith("|"):                       # table: the header and the separator row are needed too
        lines = md[:a].split("\n")[:-1]
        block = []
        while lines and lines[-1].lstrip().startswith("|"):
            block.insert(0, lines.pop())
        if len(block) >= 2:
            text = "\n".join(block[:2]) + "\n" + text
    return text + suffix


def find_source(selection, texts):
    """The selection's original Markdown excerpt from the first (newest) text that contains it; None if none does."""
    words = WORD.findall(selection)
    if len(words) < 2:
        return None
    for md in texts:
        hit = locate(words, md)
        if hit:
            return excerpt(md, *hit)
    return None


# ---------------------------------------------------------------------------------------------------------------

def upgrade(selection):
    """Puts the formatted version of the selection on the clipboard if it comes from a reply in an open conversation.
    True if it did."""
    if sys.platform != "darwin" or not selection.strip():
        return False
    for kind, path in open_sessions():
        try:
            source = find_source(selection, replies(kind, path))
        except OSError:                         # gone meanwhile, or not to be read: the next one
            continue
        if source:
            return copy_rich(source, selection)
    return False


if __name__ == "__main__":
    if sys.argv[1:] == ["--upgrade"]:                  # the selection on standard input (herdr's pbcopy)
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.exit(0 if upgrade(sys.stdin.read()) else 1)
    print(t("clip.usage"), file=sys.stderr)
    sys.exit(2)
