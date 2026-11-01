#!/usr/bin/env python3
"""Adds herdr-fold's settings to the user's herdr config.toml between "# >>> herdr-fold >>>" markers; theirs win.
  herdr_config.py add <package's> <theirs>   in place; exit 1: a file it cannot read for sure, left alone
  herdr_config.py strip <theirs>             takes herdr-fold's settings out again (the uninstaller)"""
import os
import re
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from i18n import line, t  # noqa: E402

BEGIN, END = "# >>> herdr-fold >>>", "# <<< herdr-fold <<<"
THEME_BEGIN, THEME_END = "# --- theme: ", "# --- end of theme ---"
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


def paragraphs(text):
    """The package's file in units: the theme section whole, then each run of lines between empty lines."""
    units, lines, n = [], text.split("\n"), 0
    while n < len(lines):
        if lines[n].startswith(THEME_BEGIN):
            end = next(i for i in range(n, len(lines)) if lines[i] == THEME_END)
            units.append(lines[n:end + 1])
            n = end + 1
        elif lines[n].strip():
            end = n
            while end < len(lines) and lines[end].strip() and not lines[end].startswith(THEME_BEGIN):
                end += 1
            units.append(lines[n:end])
            n = end
        else:
            n += 1
    return units


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


def strip(text):
    """The file without herdr-fold's marked parts; unchanged when a marker has lost its pair (nothing of yours goes
    with it)."""
    lines = text.split("\n")
    drop = {n for begin, end in marked(lines) or [] for n in range(begin, end + 1)}
    return "\n".join(raw for n, raw in enumerate(lines) if n not in drop)


def add(package, theirs):
    """(their file with the package's added, notes) — or (None, [the reason]) when their file is left alone."""
    if marked(theirs.split("\n")) is None:
        return None, [t("config.markers_broken")]
    theirs = strip(theirs)
    parsed = parse(theirs)
    if parsed is None:
        return None, [t("config.unsure")]
    tables, chords, headers, inline = parsed

    def written_inline(name):                                 # the table, or one above it, is theirs inline
        return any(name == table or name.startswith(table + ".") for table in inline)
    notes, top, into, before, end = [], [], {}, {}, []
    lines = theirs.split("\n")

    def taken(chord_values):
        return next((c for c in chord_values if c.lower().replace(" ", "") in chords), None)

    for unit in paragraphs(package):
        unit_header = next((HEADER.match(raw) for raw in unit if HEADER.match(raw)), None)
        if unit[0].startswith(THEME_BEGIN):
            if any(name == "theme" or name.startswith(("theme.", "ui.sidebar.agents")) for _, name in headers) \
                    or any(written_inline(name) for name in ("theme", "theme.custom", "ui.sidebar.agents")):
                notes.append(t("config.theme_yours"))
            else:
                end += [""] + unit
            continue
        if unit_header and unit_header.group(1) == "[[":
            fields = dict(KEY.match(raw).groups() for raw in unit if KEY.match(raw))
            chord = taken([a or b for a, b in STRING.findall(fields.get("key", ""))])
            if chord:
                about = next((a or b for a, b in STRING.findall(fields.get("description", ""))), chord)
                notes.append(t("config.chord_yours", chord, chords[chord.lower().replace(" ", "")], about))
            else:
                end += [""] + unit
            continue
        name = unit_header.group(2) if unit_header else ""
        if name and written_inline(name):
            notes.append(t("config.key_yours", name))
            continue
        theirs_table = tables.get(name) if name in tables else None
        keep = []
        for raw in unit:
            key = KEY.match(raw) if not raw.lstrip().startswith("#") and not HEADER.match(raw) else None
            if not key:
                continue
            value = key.group(2).strip()
            where = f"{name}.{key.group(1)}" if name else key.group(1)
            if theirs_table is not None and key.group(1) in theirs_table:
                if theirs_table[key.group(1)] != value:
                    notes.append(t("config.key_yours", where))
                continue
            chord = taken([a or b for a, b in STRING.findall(value)]) if name == "keys" else None
            if chord:
                notes.append(t("config.chord_yours", chord, chords[chord.lower().replace(" ", "")], where))
                continue
            keep.append(raw)
        if not keep:
            continue
        if not name:
            top += keep
        elif theirs_table is not None:
            at = next(n for n, h in headers if h == name)
            into.setdefault(at, []).extend(keep)
        else:
            comments = [raw for raw in unit[:unit.index(unit_header.group(0))] if raw.lstrip().startswith("#")]
            block = comments + [unit_header.group(0)] + keep
            sub = next((n for n, h in headers if h.startswith(name + ".")), None)
            if sub is None:
                end += [""] + block
            else:
                before.setdefault(sub, []).extend(block + [""])
    if top and headers:                                       # top-level keys: before the first table of theirs
        before.setdefault(headers[0][0], [])[:0] = top + [""]
    elif top:                                                 # no table of theirs: first in the marked part at the end
        end = [""] + top + end
    out = []
    for n, raw in enumerate(lines):
        if n in before:
            out += [BEGIN] + before[n][:-1 if before[n][-1:] == [""] else None] + [END]
        out.append(raw)
        if n in into:
            out += [BEGIN] + into[n] + [END]
    if end:
        tail = 1 if out and out[-1] == "" else 0
        out[len(out) - tail:len(out) - tail] = [BEGIN] + end[1:] + [END]
    return "\n".join(out), notes


def main(args):
    if args[:1] == ["strip"] and len(args) == 2:
        with open(args[1], encoding="utf-8") as f:
            theirs = f.read()
        if marked(theirs.split("\n")) is None:
            print(t("config.markers_broken"))
            return 1
        if strip(theirs) != theirs:
            with open(args[1], "w", encoding="utf-8") as f:
                f.write(strip(theirs))
        return 0
    if len(args) != 3 or args[0] != "add":
        print(__doc__.strip(), file=sys.stderr)
        return 2
    with open(args[1], encoding="utf-8") as f:
        package = f.read()
    with open(args[2], encoding="utf-8") as f:
        theirs = f.read()
    merged, notes = add(package, theirs)
    if merged is None:
        print(notes[0])
        return 1
    for note in notes:
        print(line("warn", note))
    if merged != theirs:
        with open(args[2], "w", encoding="utf-8") as f:     # into the file itself: a link stays a link
            f.write(merged)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
