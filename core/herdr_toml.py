"""herdr's config.toml read and changed by line, for what herdr-fold adds to a user's own (src/herdr_config.py, between
"# >>> herdr-fold >>>" markers) and the one key the sidebar's Settings sets: its tables and keys (parse()), the marked
parts (marked()), a key's string (value()) and a key set as a line of the user's own (put())."""
import re

BEGIN, END = "# >>> herdr-fold >>>", "# <<< herdr-fold <<<"
HEADER = re.compile(r"^(\[\[?)([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)(\]\]?)\s*(#.*)?$")
KEY = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*=\s*(.*)$")
UNSURE = re.compile(r'"""|\'\'\'|^\s*[A-Za-z0-9_-]+\s*\.\s*[A-Za-z0-9_.-]+\s*=|^\s*["\'][^"\']*["\']\s*=')
STRING = re.compile(r'"((?:\\.|[^"\\])*)"|\'([^\']*)\'')


def depth(text):
    """How many more [ than ] a value line opens (strings and comments do not count)."""
    bare = STRING.sub("", text).split("#", 1)[0]
    return bare.count("[") - bare.count("]")


def parse(text):
    """The file's tables ({name: {key: value}}, "" = the top level, each [[array]] item its own), the key chords it
    binds ({chord: what}), its headers in order ([(line, name)]) and the tables it writes inline (key = { … }) — None
    if it has anything this reading is unsure of."""
    tables, chords, headers, inline = {"": {}}, {}, [], set()
    current, open_brackets = "", 0
    for n, raw in enumerate(text.split("\n")):
        if open_brackets > 0:                                 # inside a value spanning several lines
            open_brackets += depth(raw)
            continue
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if UNSURE.search(raw):
            return None
        header = HEADER.match(raw)
        if header:
            if len(header.group(1)) != len(header.group(3)):
                return None
            headers.append((n, header.group(2)))
            current = header.group(2) + (f"#{n}" if header.group(1) == "[[" else "")
            tables[current] = {}
            continue
        key = KEY.match(raw)
        if not key or raw.startswith("["):
            return None
        name, value = key.group(1), key.group(2).strip()
        tables[current][name] = value
        if value.startswith("{"):                            # an inline table: [<table>.<name>] is written already
            inline.add(f"{current.split('#')[0]}.{name}".lstrip("."))
        open_brackets = depth(value)
        table = current.split("#")[0]
        if table == "keys.command" and name == "key" or table == "keys" or table.startswith("keys.") \
                and table != "keys.command":
            for chord in (a or b for a, b in STRING.findall(value)):
                chords[chord.lower().replace(" ", "")] = f"{table}.{name}" if table != "keys.command" else table
    return tables, chords, headers, inline


def marked(lines):
    """The (begin, end) line numbers of herdr-fold's marked parts — None if a marker has lost its pair."""
    found, start = [], None
    for n, raw in enumerate(lines):
        if raw == BEGIN:
            if start is not None:
                return None
            start = n
        elif raw == END:
            if start is None:
                return None
            found.append((start, n))
            start = None
    return None if start is not None else found


def value(theirs, table, key):
    """The string TABLE's KEY holds in their file, or None: not set, no plain string, or a file add() leaves alone."""
    parsed = parse(theirs)
    found = STRING.match((parsed[0].get(table) or {}).get(key, "")) if parsed else None
    return (found.group(1) if found.group(1) is not None else found.group(2)) if found else None


def put(theirs, table, key, source):
    """Their file with TABLE's KEY set to SOURCE (a value as TOML writes it), as a line of their own: one herdr-fold
    added goes out of its marked part with its table's head, so the next add keeps theirs. None: a file left alone."""
    lines = theirs.split("\n")
    spans = marked(lines)
    if spans is None or parse(theirs) is None:
        return None
    inside = {n for begin, end in spans for n in range(begin, end + 1)}
    current, heads, held = "", [], {}                         # the table's headers; its keys' lines, each by its header
    for n, raw in enumerate(lines):
        header, found = HEADER.match(raw), KEY.match(raw) if not raw.lstrip().startswith("#") else None
        if header:
            current = header.group(2) if header.group(1) == "[" else None
            heads += [n] if current == table else []
        elif found and current == table and heads:
            held.setdefault(heads[-1], {})[found.group(1)] = n
    line, at = f"{key} = {source}", next((keys[key] for keys in held.values() if key in keys), None)
    own = next((n for n in heads if n not in inside), None)
    if at is not None and at not in inside:                   # theirs already: its value alone
        lines[at] = line
        return "\n".join(lines)
    head = next((n for n in heads if n in inside), None)
    if own is None and head is not None and set(held.get(head, {})) - {key}:
        lines[at:at + 1] = [line]                             # the marked table holds more of herdr-fold's: in place
        return "\n".join(lines)
    gone = {at} - {None}
    if own is None and head is not None:                      # the marked head with its comments goes with its key
        first = head
        while first - 1 in inside and lines[first - 1].lstrip().startswith("#") and lines[first - 1] != BEGIN:
            first -= 1
        gone |= set(range(first, head + 1))
        gone |= {first - 1} if lines[first - 1] == "" else {head + 2} if lines[head + 2:head + 3] == [""] else set()
    for begin, end in spans:                                  # a marked part left empty goes whole
        if all(n in gone for n in range(begin + 1, end)):
            gone |= {begin, end}
    out = []
    for n, raw in enumerate(lines):
        out += [raw] if n not in gone else []
        out += [line] if n == own else []
    if own is None:
        tail = out.pop() if out and out[-1] == "" else None
        out += [""] * bool(out) + [f"[{table}]", line] + ([""] if tail is not None or not out else [])
    return "\n".join(out)
