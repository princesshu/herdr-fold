# Generated from core/words.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""How both clients say a model and a figure: a model's name (Opus 5.5, GPT-5 Codex), its family and its context
window (the price table's, model_windows.py); a token count by the one number rule, a share as a percent."""
import re
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
from model_windows import WINDOWS  # noqa: E402

DATED = re.compile(r"-(\d{8}|\d{4}-\d\d-\d\d)$")        # a model id's date
ONE_M = "[1m]"                  # Claude's spelling of a model with its 1M-token window
MAKERS = ("anthropic", "openai")                        # a model id's maker, before it
FAMILIES = ("opus", "sonnet", "haiku")                  # Claude's families by name; every model of OpenAI's: codex


def parts(model):
    """MODEL's id in its parts, without its maker, its date and a [1m]: claude-opus-5-5-20261101 as claude, opus, 5,
    5."""
    if not isinstance(model, str):
        return []
    id = model.rsplit("/", 1)[-1].strip().lower()
    id = DATED.sub("", id[:-len(ONE_M)] if id.endswith(ONE_M) else id)
    return [part for part in id.split("-") if part]


def model_name(model):
    """MODEL as people say it: Opus 5.5, Haiku 4.5, GPT-5 Codex; another's id in words, a name said so already (one
    with a space, as Claude's status line names it) as it is."""
    if isinstance(model, str) and " " in model.strip():
        return model.strip()
    found = parts(model)
    if found[:1] == ["claude"]:
        digits = [part for part in found[1:] if part.isdigit()]
        return " ".join([part.capitalize() for part in found[1:] if not part.isdigit()]
                        + ([".".join(digits)] if digits else []))
    if found[:1] == ["gpt"] and len(found) > 1:
        return " ".join([f"GPT-{found[1]}"] + [part.capitalize() for part in found[2:]])
    return " ".join(part if any(ch.isdigit() for ch in part) else part.capitalize() for part in found)


def family(model):
    """The family of MODEL (an id or Claude's alias): opus, sonnet, haiku, codex (every model of OpenAI's), else its
    first word."""
    found = [part for part in parts(model) if part != "claude" and not part.replace(".", "").isdigit()]
    if re.match(r"gpt$|codex$|o\d", "".join(parts(model)[:1])):
        return "codex"
    return next((part for part in found if part in FAMILIES), found[0] if found else "")


def own_effort(model):
    """The id Claude keeps MODEL's effort under (its settings' modelSettings) where the model takes one of its own, Opus
    5.5 and later: its id without a date and a [1m], an alias's the newest the price table has; None for a model that
    takes the settings' one effortLevel."""
    found, version = parts(model), lambda id: tuple(int(part) for part in id[2:] if part.isdigit())    # noqa: E731
    if found[:1] != ["claude"]:
        found = max((parts(id) for id in WINDOWS if parts(id)[:2] == ["claude"] + found), key=version, default=[])
    return "-".join(found) if found[1:2] == ["opus"] and version(found) >= (5, 5) else None


def window(model):
    """MODEL's context window in tokens: 1M for a [1m] one, else the price table's by its id, its maker's or its date
    left out; None for a model it does not know."""
    if not isinstance(model, str) or not model:
        return None
    if model.lower().endswith(ONE_M):
        return 1_000_000
    id = model.rsplit("/", 1)[-1] if model.split("/", 1)[0] in MAKERS else model
    return WINDOWS.get(id) or WINDOWS.get(DATED.sub("", id))


def tokens(count):
    """COUNT tokens by the number rule: whole under 1,000 (850), one decimal under 100k (5.9k, 21.4k), whole to 999k
    (120k), one decimal from 1M (1.2M) and from 1B."""
    if count < 1000:
        return str(count)
    if count < 99_950:
        return f"{count / 1e3:.1f}k"
    if count < 999_500:
        return f"{count / 1e3:.0f}k"
    return f"{count / 1e6:.1f}M" if count < 999_950_000 else f"{count / 1e9:.1f}B"


def percent(share):
    """SHARE (0 to 1) as a whole percent, "<1%" for some that rounds to none."""
    return "<1%" if 0 < share < 0.005 else f"{int(share * 100 + 0.5)}%"
