"""Writes core/price_table.py, the prices that come with herdr-fold, from LiteLLM's model cost map
(https://github.com/BerriAI/litellm, MIT): Anthropic's and OpenAI's own rows for the agents' models. Run it for a
newer table or when a family is added, then tools/build.py; nothing but core/prices.py asks for the map otherwise."""
import json
import os
import re
import sys
import time
import urllib.request

sys.dont_write_bytecode = True    # core's modules it loads leave no bytecode behind
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE = os.path.join(ROOT, "core", "price_table.py")
AGENT = "herdr-fold-tools"    # the request's User-Agent: the tool, nothing else
# the models bundled: Claude's, and the GPT-5 line and later that Codex runs on, each without a date (a dated id is
# priced as its undated one, core/prices.py's price_of())
BUNDLED = re.compile(r"claude-[a-z0-9-]+|gpt-[5-9][a-z0-9.-]*")
DATED = re.compile(r"-(\d{8}|\d{4}-\d\d-\d\d)$")


def core():
    """core/prices.py loaded, for its reading of the map (the core modules it imports found beside it)."""
    sys.path.insert(0, os.path.join(ROOT, "core"))
    import prices
    return prices


def fetch(url):
    asked = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(asked, timeout=30) as answer:
        return json.load(answer)


def checked(answer, prices):
    """ANSWER, LiteLLM's map, when it still names its prices as core/prices.py reads them (in any row: a maker's own
    may lack one, as a reasoning price); a name gone stops it."""
    names = set().union(*(row for row in answer.values() if isinstance(row, dict)))
    missing = sorted({*prices.FIELDS.values(), prices.SEARCH[0], "litellm_provider"} - names)
    if not any(prices.STEP.fullmatch(name) for name in names):
        missing.append(prices.STEP.pattern)
    if missing:
        sys.exit(f"LiteLLM's map no longer has {', '.join(missing)}: core/prices.py reads it by those names")
    return answer


def models(answer, prices):
    """{id: (the price's kinds, {step: the same past it})} for the BUNDLED models in ANSWER, as price_table.py keeps
    them."""
    found = {}
    for id, one in sorted(prices.table(answer).items()):
        if BUNDLED.fullmatch(id) and not DATED.search(id):
            found[id] = (*(one[kind] for kind in prices.KINDS),
                         {step: tuple(past[kind] for kind in prices.KINDS) for step, past in one["above"].items()})
    return found


def source(as_of, models):
    """core/price_table.py's text for MODELS as of AS_OF, a model a line (a long prompt's prices on lines of their
    own)."""
    lines = ['"""The prices that come with herdr-fold, for when LiteLLM\'s model cost map cannot be had: its rows for',
             "Anthropic's and OpenAI's models on AS_OF (https://github.com/BerriAI/litellm, MIT: see",
             'THIRD_PARTY_NOTICES.md). Written by tools/prices.py: run that for a newer table, never edit this."""',
             f"AS_OF = {json.dumps(as_of)}",
             "# id: dollars a token of input, output, 5-minute cache write, 1-hour cache write, cache read and",
             "# reasoning, dollars a web search, then {thousands of prompt tokens: the same for a prompt past them}",
             "MODELS = {"]
    for id, (*kinds, above) in models.items():
        row = f"    {json.dumps(id)}: ({', '.join(repr(value) for value in kinds)}, {{"
        if not above:
            lines.append(row + "}),")
            continue
        lines.append(row)
        past = [f"        {json.dumps(step)}: ({', '.join(repr(value) for value in one)})," for step, one in
                above.items()]
        lines += past[:-1] + [past[-1][:-1] + "}),"]
    return "\n".join(lines + ["}"]) + "\n"


def main():
    prices = core()
    found = models(checked(fetch(prices.PRICES_URL), prices), prices)
    if not found:
        sys.exit("LiteLLM's map has none of the bundled models")
    with open(TABLE, "w", encoding="utf-8") as f:
        f.write(source(time.strftime("%Y-%m-%d", time.gmtime()), found))
    print(f"core/price_table.py: {len(found)} models")


if __name__ == "__main__":
    sys.exit(main())
