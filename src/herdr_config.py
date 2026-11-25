#!/usr/bin/env python3
"""Adds herdr-fold's settings to the user's herdr config.toml between "# >>> herdr-fold >>>" markers; theirs win.
  herdr_config.py add <package's> <theirs> | strip <theirs>   in place; exit 1: a file not read for sure, left alone
  herdr_config.py value|put <theirs> <table> <key> [<string>]   a key of theirs read, or set (kept over an update)"""
import os
import re
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herdr_toml import BEGIN, END, HEADER, KEY, STRING, marked, parse, put, value  # noqa: E402
from i18n import line, t  # noqa: E402

THEME_BEGIN, THEME_END = "# --- theme: ", "# --- end of theme ---"
WORD = re.compile(r"[A-Za-z0-9_-]+")        # a string `put` writes as it is, between quotes


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
    if args[:1] in (["value"], ["put"]) and len(args) == (4 if args[0] == "value" else 5):
        with open(args[1], encoding="utf-8") as f:
            theirs = f.read()
        if args[0] == "value":
            print(value(theirs, args[2], args[3]) or "")
            return 0
        made = put(theirs, args[2], args[3], f'"{args[4]}"') if WORD.fullmatch(args[4]) else None
        if made is not None and made != theirs:
            with open(args[1], "w", encoding="utf-8") as f:
                f.write(made)
        return 0 if made is not None else 1
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
