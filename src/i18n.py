"""The Python scripts' texts: t(key, *args) returns KEY's text from lang/<HERDR_FOLD_LANG>.txt (en.txt by default or
when missing); %s takes the next argument, %% is a percent sign, \\n a new line (docs/translating.md has the format).
line(kind, text) is a status line in the installer's own form (lib/output.sh)."""
import os
import re
import sys

LANG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang")
_texts = None


def _load():
    path = os.path.join(LANG_DIR, (os.environ.get("HERDR_FOLD_LANG") or "en") + ".txt")
    if not os.path.isfile(path):
        path = os.path.join(LANG_DIR, "en.txt")
    texts, key = {}, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if key:                                         # the text goes on: without its indentation
                texts[key] += line.lstrip()
            else:
                key, sep, text = line.partition(" = ")
                if not sep or key.startswith("#"):
                    key = None
                    continue
                texts[key] = text
            if texts[key].endswith("\\"):
                texts[key] = texts[key][:-1]                 # a space before it stays: the break between two words
            else:
                key = None
    return texts


def t(key, *args):
    global _texts
    if _texts is None:
        _texts = _load()
    values = iter(args)

    def fill(match):
        if match.group() == "%s":
            return str(next(values, ""))
        return "%" if match.group() == "%%" else "\n"

    return re.sub(r"%s|%%|\\n", fill, _texts.get(key, ""))


# The status marks, as in lib/output.sh: (mark, color of the mark; None: the whole mark dim)
MARKS = {"ok": ("✓", "32"), "have": ("✓", None), "warn": ("!", "33"), "fail": ("✗", "31"), "skip": ("-", None),
         "saved": ("+", "")}


def line(kind, text):
    """A status line: "  [✓] text". In a terminal (and without NO_COLOR) the bracket is dim and the mark colored. A
    control character in the text, but a line break or a tab, shows as ?: a name from elsewhere (a machine's workspace,
    a remote's answer) may hold escape codes that set the window title or write the clipboard."""
    glyph, color = MARKS[kind]
    text = "".join(ch if ch.isprintable() or ch in "\n\t" else "?" for ch in str(text))
    if sys.stdout.isatty() and not os.environ.get("NO_COLOR"):
        if color is None:
            mark = f"\033[2m[{glyph}]\033[0m"
        else:
            mark = f"\033[2m[\033[0m{chr(27) + '[' + color + 'm' if color else ''}{glyph}\033[0m\033[2m]\033[0m"
        return f"  {mark} {text}"
    return f"  [{glyph}] {text}"
