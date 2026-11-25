"""What tokens cost, for Usage: each kind at its model's price in LiteLLM's model cost map, asked of
raw.githubusercontent.com (the request alone: no id, no cookie) once a day while the daily look is on (update.py's
switch), else the last kept or the bundled table; a model's color, a dollar figure. Usage (in JSON): prices.py table."""
import json
import math
import os
import re
import sys
import time
import urllib.request

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import price_table  # noqa: E402
import statefile  # noqa: E402
from words import DATED, MAKERS, family  # noqa: E402

PRICES_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
KEPT = "prices.json"            # the table as last fetched, and when it was asked for
DAY = 86400
LARGEST = 8 << 20               # bytes of an answer read (the map is some 4 MB): more is not it
# a price's kinds, dollars a token (search: a web search), and LiteLLM's name for each
KINDS = ("input", "output", "write_5m", "write_1h", "read", "reasoning", "search")
FIELDS = {"input": "input_cost_per_token", "output": "output_cost_per_token",
          "write_5m": "cache_creation_input_token_cost", "write_1h": "cache_creation_input_token_cost_above_1hr",
          "read": "cache_read_input_token_cost", "reasoning": "output_cost_per_reasoning_token"}
SEARCH = ("search_context_cost_per_query", "search_context_size_medium")
STEP = re.compile(r"input_cost_per_token_above_(\d+)k_tokens")         # a long prompt's own prices, by its step
DAY_SAID = re.compile(r"\d{4}-\d\d-\d\d")
# The models' colors, a family one: the mockups' four (the dataviz palette's first dark steps), another family the
# next slot in order of first use, past the last one REST. Never a limit's state colors. On a card: model_color().
SLOTS = {"opus": "#3987e5", "sonnet": "#d95926", "haiku": "#199e70", "codex": "#c98500"}
NEXT = ("#d55181", "#0ca30c", "#9085e9", "#e66767")
REST = "#8b8b8b"
MARK = 3                        # the contrast a mark (a bar, a swatch) needs on the card it is drawn on
HEX = re.compile(r"#[0-9a-fA-F]{6}")
ABOUT = "~"                     # before a dollar figure herdr-fold computes, an estimate at list prices; a budget none


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def obj(value):
    return value if isinstance(value, dict) else {}


# --- a price

def price(row):
    """ROW of LiteLLM's map as a price, {KINDS…, "above": {"272": a prompt over 272k tokens' KINDS}}; None for a row
    with no token price. A missing 1-hour write is the 5-minute one's price, that one and a read the input's,
    reasoning the output's."""
    def told(suffix):
        return {kind: row.get(field + suffix) if number(row.get(field + suffix)) else None
                for kind, field in FIELDS.items()}

    def whole(one):
        five = one["input"] if one["write_5m"] is None else one["write_5m"]
        return {"input": one["input"], "output": one["output"], "write_5m": five,
                "write_1h": five if one["write_1h"] is None else one["write_1h"],
                "read": one["input"] if one["read"] is None else one["read"],
                "reasoning": one["output"] if one["reasoning"] is None else one["reasoning"], "search": search}

    if not isinstance(row, dict):
        return None
    base, search = told(""), obj(row.get(SEARCH[0])).get(SEARCH[1])
    search = search if number(search) else 0
    if base["input"] is None or base["output"] is None:
        return None
    steps = sorted(int(found.group(1)) for found in map(STEP.fullmatch, row) if found and number(row[found.group(0)]))
    above = {str(step): whole({kind: base[kind] if value is None else value
                               for kind, value in told(f"_above_{step}k_tokens").items()}) for step in steps}
    return {**whole(base), "above": above}


def whole(price):
    """Whether PRICE has a price's shape (a kept table's row is checked before it prices anything)."""
    def kinds(one):
        return isinstance(one, dict) and all(number(one.get(kind)) for kind in KINDS)
    above = price.get("above") if isinstance(price, dict) else None
    return kinds(price) and isinstance(above, dict) and all(step.isdigit() and kinds(one)
                                                            for step, one in above.items())


def table(answer):
    """LiteLLM's map ANSWER as {model id: price}: the MAKERS' own rows (a model as its maker sells it, no reseller's)
    that have a token price."""
    found = {id: price(row) for id, row in obj(answer).items() if obj(row).get("litellm_provider") in MAKERS}
    return {id: one for id, one in found.items() if one}


def bundled():
    """The table that came with herdr-fold (price_table.py, tools/prices.py's), as {model id: price}."""
    return {id: {**dict(zip(KINDS, row)), "above": {step: dict(zip(KINDS, one)) for step, one in above.items()}}
            for id, (*row, above) in price_table.MODELS.items()}


# --- the table

def on(state):
    """Whether the daily look is on: update.py's own switch (About's Check for updates automatically, kept in
    update.json) and HERDR_FOLD_NO_UPDATE_CHECK=1."""
    kept = statefile.read(os.path.join(state, "update.json"))
    return kept.get("on", True) is not False and os.environ.get("HERDR_FOLD_NO_UPDATE_CHECK") != "1"


def fetch():
    """LiteLLM's map, asked of GitHub now, or None."""
    request = urllib.request.Request(PRICES_URL, headers={"User-Agent": "herdr-fold"})
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:
            body = answer.read(LARGEST + 1)
        found = json.loads(body) if len(body) <= LARGEST else None
    except (OSError, ValueError, RecursionError):
        return None
    return found if isinstance(found, dict) else None


def prices(state, now=None, fetch=fetch):
    """The prices at NOW, {"as_of": the table's day (UTC), "source": fetched, kept or bundled, "models": {id: price}}:
    asked again (through FETCH) a day after the last asking, kept in STATE; an answer with no price in it keeps the
    last. The bundled table where none is kept, or the kept one is older."""
    now, path = time.time() if now is None else now, os.path.join(state, KEPT)
    kept, source = statefile.read(path), "kept"
    asked = kept.get("asked") if number(kept.get("asked")) else 0
    if on(state) and not now - DAY < asked <= now:
        found = table(fetch())
        made = {"as_of": time.strftime("%Y-%m-%d", time.gmtime(now)), "models": found} if found else {}
        source = "fetched" if found else "kept"
        try:
            kept = statefile.update(path, lambda was: {**was, "asked": now, **made}, separators=(",", ":"))
        except OSError:
            kept = {**kept, **made}             # not kept: asked again the next time
    day, models = kept.get("as_of"), kept.get("models")
    if isinstance(day, str) and DAY_SAID.fullmatch(day) and day >= price_table.AS_OF and isinstance(models, dict) \
            and models and all(whole(one) for one in models.values()):
        return {"as_of": day, "source": source, "models": models}
    return {"as_of": price_table.AS_OF, "source": "bundled", "models": bundled()}


def price_of(model, models):
    """MODEL's price in MODELS (prices()'s): by its id, then with its maker before it, then without its date; None
    for a model with no price (its tokens are shown alone)."""
    if not isinstance(model, str) or not model:
        return None
    for id in (model, DATED.sub("", model)):
        for known in (id, *(f"{maker}/{id}" for maker in MAKERS)):
            if whole(models.get(known)):
                return models[known]
    return None


def cost(sums, price):
    """What SUMS (tokens.py's kinds, a message's or a row's, with its "over") cost at PRICE in dollars, a prompt over
    a step at that step's prices, the reasoning part of the output at its own; None for no PRICE, never 0."""
    if not price:
        return None
    step = max((int(one) for one in price["above"] if int(one) <= sums.get("over", 0)), default=0)
    at = price["above"][str(step)] if step else price
    reasoning = min(sums["reasoning"], sums["output"])
    return (sums["input"] * at["input"] + sums["write_5m"] * at["write_5m"] + sums["write_1h"] * at["write_1h"]
            + sums["read"] * at["read"] + (sums["output"] - reasoning) * at["output"] + reasoning * at["reasoning"]
            + sums["searches"] * at["search"])


# --- words

def money(dollars, about=False):
    """DOLLARS as both clients write them, $1,234.50; ABOUT: one herdr-fold computed, ~$1,234.50."""
    return f"{ABOUT if about else ''}${dollars:,.2f}"


# --- a model's color

def luminance(color):
    """COLOR's (#rrggbb) relative luminance, as WCAG counts it: 0 black, 1 white."""
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in (int(color[n:n + 2], 16) / 255 for n in (1, 3, 5))]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(one, other):
    light, dark = sorted((luminance(one), luminance(other)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def lifted(color, text, surface):
    """COLOR, or moved toward TEXT by tenths until a mark of it reads MARK on SURFACE (a theme's card; the themes'
    readable()): COLOR itself where the two are not told as #rrggbb."""
    if not all(isinstance(one, str) and HEX.fullmatch(one) for one in (text, surface)):
        return color
    channels = [[int(one[n:n + 2], 16) for n in (1, 3, 5)] for one in (color, text)]
    for tenth in range(11):
        made = "#" + "".join(f"{round(a + (b - a) * tenth / 10):02x}" for a, b in zip(*channels))
        if contrast(made, surface) >= MARK:
            return made
    return text


def model_color(model, seen, surface=None, text=None):
    """MODEL's color as hex: its family's slot, another family's the next one in order of first use in SEEN (the
    models met so far, MODEL after them where it is not among them), so a model keeps its color; on a theme's card
    SURFACE with its TEXT, lifted() where it would read under MARK there."""
    own = family(model)
    if own in SLOTS:
        return lifted(SLOTS[own], text, surface)
    others = []
    for one in [*seen, model]:
        if family(one) not in SLOTS and family(one) not in others:
            others.append(family(one))
    return lifted(NEXT[others.index(own)] if others.index(own) < len(NEXT) else REST, text, surface)


def main(argv):
    """herdr-fold's Herdr app mod runs this, answering in JSON: table (the prices now, fetched when a day has
    passed)."""
    if argv[1:] == ["table"]:
        print(json.dumps(prices(statefile.folder())))
        return 0
    print("usage: prices.py table", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
