"""The edits herdr-fold makes in an agent's own settings files, for harness.py: Claude's three settings.json and
Codex's two config.toml alone, the file found by its layer's name, read again, changed at the one key the edit expects
a value at, written whole; each edit gives the one that takes it back. The organization's files are never written."""
import contextlib
import json
import os
import re
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
import agent_setup as setup  # noqa: E402

GLOBAL, PROJECT, LOCAL, MANAGED = setup.GLOBAL, setup.PROJECT, setup.LOCAL, setup.MANAGED
LAYERS = {"claude": (GLOBAL, PROJECT, LOCAL), "codex": (GLOBAL, PROJECT)}       # the layers written: never Managed
MODE_KEY, EFFORT_KEY, ENABLED_KEY = ("permissions", "defaultMode"), ("effortLevel",), ("sandbox", "enabled")
HOSTS_KEY = ("sandbox", "network", "allowedDomains")
# what a key may be set to: Claude's modes as its settings name them, each agent's efforts, Codex's approval policies
# that are one word
MODE_IDS = ("default", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions")
CLAUDE_EFFORTS, CODEX_EFFORTS = ("low", "medium", "high", "xhigh"), ("low", "medium", "high", "xhigh", "max")
POLICIES = ("on-request", "never")
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/\[\]-]{0,99}")       # a model's alias or id
HOST = re.compile(r"(?:\*\.)?[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")      # a host, or every host under one
# config.toml's lines changed: a table's head, a key and its value, a plain string value, a name in a key or a head
STRING = r""""(?:[^"\\]|\\.)*"|'[^']*'"""
TOML_HEAD = re.compile(rf"""\s*\[((?:[^\]\["'#]|{STRING})+)\]\s*(?:#.*)?""")
TOML_PAIR = re.compile(rf"""(\s*)((?:[^="'#\[\]]|{STRING})+?)(\s*=\s*)(.*)""", re.S)
TOML_PLAIN = re.compile(r"""(["'])([^"'\\]*)\1(\s*(?:#.*)?)""")
TOML_NAME = re.compile(rf"""\s*([A-Za-z0-9_-]+|{STRING})\s*(\.|$)""")
OTHER = object()                # the name of an array of tables: none of its keys is one changed here
# why a file is not changed ({path}: the file, as the panel names it)
STALE = "{path} changed since: nothing saved"
UNWRITTEN = "Couldn't write {path}"
NOT_EDITED = "{path} is not written in a way herdr-fold changes: change it in the file"
LINK = "{path} is a link: change it where it lives"


class Refused(Exception):
    """Why a file is not changed, in the panel's words."""


def place(agent, layer, folder, home):
    """The one file AGENT keeps LAYER in for FOLDER, made from the layer's name alone: Claude's three settings files,
    Codex's two config.toml; ValueError for any other (the organization's is never written)."""
    if layer not in LAYERS.get(agent, ()) or not isinstance(folder, str) or not os.path.isabs(folder):
        raise ValueError("not a layer herdr-fold writes")
    if agent == "codex":
        return os.path.join(setup.codex_home(home) if layer == GLOBAL else os.path.join(folder, ".codex"),
                            "config.toml")
    return next(path for path, scope in setup.settings(folder, home) if scope == layer)


def text_of(path):
    """PATH's text as it is, "" for no file yet; Refused for a link (the file or its folder: never followed), for what
    is no file, and for one too large or not UTF-8."""
    if os.path.islink(path) or os.path.islink(os.path.dirname(path)):
        raise Refused(LINK)
    if not os.path.lexists(path):
        return ""
    try:
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read(setup.LARGEST + 1) if os.path.isfile(path) else None
    except (OSError, UnicodeDecodeError):
        text = None
    if text is None or len(text) > setup.LARGEST:
        raise Refused(NOT_EDITED)
    return text


def value_at(data, key):
    """What DATA holds at KEY's path; None where a step of it is missing."""
    for name in key:
        data = data.get(name) if isinstance(data, dict) else None
    return data


def same(one, other):
    return json.dumps(one, sort_keys=True) == json.dumps(other, sort_keys=True)


def load(text):
    """A settings file's TEXT as its object, the keys in their order ({} for an empty one); Refused for what is no
    JSON object, and for one naming a key twice (written again it would lose one)."""
    def pairs(found):
        if len({name for name, _ in found}) != len(found):
            raise ValueError("a key twice")
        return dict(found)

    def constant(name):
        raise ValueError(name)
    try:
        data = json.loads(text, object_pairs_hook=pairs, parse_constant=constant) if text.strip() else {}
    except (ValueError, RecursionError):
        data = None
    if not isinstance(data, dict):
        raise Refused(NOT_EDITED)
    return data


def names(text):
    """The names in a TOML key or a table's head TEXT (bare, or quoted); Refused for another shape."""
    found, at = [], 0
    while True:
        part = TOML_NAME.match(text, at)
        try:
            word = part.group(1)
            found.append(json.loads(word) if word[0] == '"' else word[1:-1] if word[0] == "'" else word)
        except (AttributeError, ValueError):
            raise Refused(NOT_EDITED) from None
        at = part.end()
        if not part.group(2):
            return tuple(found)


def toml_scan(text):
    """Config TEXT's lines that set a key or head a table, in order: {line, last (a value over several lines), names
    (the table's, then the key's), table, head, plain (TOML_PLAIN's match of a plain string value, else None)};
    Refused for a shape not read by line (a string over several lines, a line that is neither)."""
    if '"""' in text or "'''" in text:
        raise Refused(NOT_EDITED)
    found, table, depth = [], (), 0
    for n, line in enumerate(text.split("\n")):
        bare, inside = re.sub(STRING, '""', line).split("#")[0], depth
        depth += sum(bare.count(ch) for ch in "[{") - sum(bare.count(ch) for ch in "]}")
        if inside:
            found[-1]["last"] = n
        elif bare.lstrip().startswith("[["):
            table = (OTHER,)
        elif TOML_HEAD.fullmatch(line):
            table = names(TOML_HEAD.fullmatch(line).group(1))
            found.append({"line": n, "last": n, "names": table, "table": table, "head": True, "plain": None})
        elif bare.strip():
            pair = TOML_PAIR.fullmatch(line)
            if not pair:
                raise Refused(NOT_EDITED)
            found.append({"line": n, "last": n, "names": table + names(pair.group(2)), "table": table, "head": False,
                          "plain": TOML_PLAIN.fullmatch(pair.group(4))})
    return found


def toml_find(text, name):
    """Where config TEXT sets its top-level key NAME to a plain string: its line (toml_scan()'s) or None, and the
    top-level key lines. Refused where NAME is set in a shape not changed by line: twice, by a dotted key, in an
    inline table, as a table of its own, to what is no plain string."""
    mine, lines = None, []
    for one in toml_scan(text):
        if one["names"][0] == name:
            if mine or one["head"] or one["names"] != (name,) or not one["plain"]:
                raise Refused(NOT_EDITED)
            mine = one
        lines += [one] if not one["head"] and one["table"] == () else []
    return mine, lines


def plain(value, form=None):
    """Whether VALUE is a name written as it is: a string of 200 characters at most, no control character in it, no
    space at an end; FORM's where given."""
    return isinstance(value, str) and 0 < len(value) <= 200 and value == value.strip() \
        and not setup.controlled(value) and (form is None or bool(form.fullmatch(value)))


def put(path, text):
    """TEXT in PATH: written whole beside it, then put in place, the file's mode kept (a new one its owner's alone)."""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=folder, prefix=f".{os.path.basename(path)}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        if os.path.exists(path):
            shutil.copymode(path, temporary)
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise


def dumped(data, text):
    """DATA as the file whose TEXT it was read from keeps it: its indentation (two spaces in a new one, none in a
    one-line one), its line ends, its letters outside ASCII written out or not, what follows its last brace."""
    found = re.search(r"\n([ \t]+)\S", text)
    indent = found.group(1) if found else "  " if text.strip() in ("", "{}") else None
    made = json.dumps(data, indent=indent, ensure_ascii=text.isascii())
    return (made.replace("\n", "\r\n") if "\r\n" in text else made) + (text[len(text.rstrip()):] if text.strip()
                                                                       else "\n")


def json_edit(text, edit):
    """The settings TEXT with EDIT made at its one key (a value set or taken out, a list's item put in, taken out or
    replaced in place) and the edit that takes it back; Refused where TEXT no longer holds what EDIT expects."""
    data, key, listed = load(text), edit["key"], "before" not in edit
    now, parents, made = value_at(data, key), [data], None
    for depth, name in enumerate(key[:-1]):
        if name not in parents[-1]:
            made = depth if made is None else made
            parents[-1][name] = {}
        if not isinstance(parents[-1][name], dict):
            raise Refused(NOT_EDITED)
        parents.append(parents[-1][name])
    owner, name = parents[-1], key[-1]
    made = len(key) - 1 if made is None and name not in owner else made         # the topmost key EDIT makes
    if listed:
        items, gone, come, at = [] if now is None else now, edit.get("remove"), edit.get("add"), edit.get("at")
        if not isinstance(items, list):
            raise Refused(NOT_EDITED)
        if gone is not None and gone not in items or come is not None and come in items:
            raise Refused(STALE)
        at = items.index(gone) if gone is not None else len(items) if at is None else min(at, len(items))
        items = items[:at] + [come] * (come is not None) + items[at + (gone is not None):]
        back = {"key": key, "remove": come, "add": gone, **({"at": at} if now is not None else {"prune": made})}
        after = None if not items and edit.get("prune") is not None else items
    else:
        after = edit["after"]
        if not same(now, edit["before"]):
            raise Refused(STALE)
        back = {"key": key, "before": after, "after": now}
        back.update({"at": list(owner).index(name)} if after is None and name in owner else
                    {"prune": made} if now is None and made is not None else {})
    if after is None:
        owner.pop(name, None)
        for depth in range(len(key) - 2, (len(key) if edit.get("prune") is None else edit["prune"]) - 1, -1):
            if parents[depth + 1]:
                break
            del parents[depth][key[depth]]          # an object EDIT's own change made, empty again
    elif name in owner:
        owner[name] = after
    else:
        entries, at = list(owner.items()), None if listed else edit.get("at")
        entries.insert(len(entries) if at is None else at, (name, after))
        owner.clear()
        owner.update(entries)
    return dumped(data, text), back


def toml_edit(text, edit):
    """The config TEXT with EDIT made on its one line (a top-level key's plain string replaced, its line put in under
    the last top-level key or taken out) and the edit that takes it back; Refused as toml_find() and json_edit() do."""
    (name,), before, after = edit["key"], edit["before"], edit["after"]
    mine, keys = toml_find(text, name)
    lines, back = text.split("\n"), {"key": [name], "before": after, "after": before}
    if (mine["plain"].group(2) if mine else None) != before:
        raise Refused(STALE)
    if not mine:
        lines.insert(keys[-1]["last"] + 1 if keys else 0, f'{name} = "{after}"' + "\r" * ("\r\n" in text))
    elif after is None:
        if mine["plain"].group(3).strip():
            raise Refused(NOT_EDITED)               # its comment would go with it
        del lines[mine["line"]]
    else:
        pair, plain = TOML_PAIR.fullmatch(lines[mine["line"]]), mine["plain"]
        lines[mine["line"]] = "".join(pair.group(1, 2, 3)) + plain.group(1) + after + plain.group(1) + plain.group(3)
    return "\n".join(lines), back


# what an edit may put at each key it changes, a test of the value: Claude's settings', their lists' items, Codex's
CLAUDE_KEYS = {MODE_KEY: MODE_IDS.__contains__, ("model",): lambda value: plain(value, MODEL),
               EFFORT_KEY: CLAUDE_EFFORTS.__contains__, ENABLED_KEY: lambda value: isinstance(value, bool),
               ("disableAllHooks",): lambda value: value is True}
CLAUDE_LISTS = {**{("permissions", behavior): lambda value: setup.rule_text(value) == value
                   for behavior in setup.BEHAVIORS},
                HOSTS_KEY: lambda value: plain(value, HOST), ("enabledMcpjsonServers",): plain,
                ("disabledMcpjsonServers",): plain,
                ("deniedMcpServers",): lambda value: isinstance(value, dict) and list(value) == ["serverName"]
                and plain(value["serverName"])}
CODEX_KEYS = {("model",): lambda value: plain(value, MODEL), ("model_reasoning_effort",): CODEX_EFFORTS.__contains__,
              ("approval_policy",): POLICIES.__contains__,
              ("sandbox_mode",): tuple(setup.SANDBOXES).__contains__}


def kind(agent, edit):
    """The test of what EDIT may put at its key (CLAUDE_KEYS', CLAUDE_LISTS', CODEX_KEYS'; a skill's override, a
    model's own effort); None for a key never changed."""
    key, listed = tuple(edit["key"]), "before" not in edit
    if agent == "codex":
        return None if listed else CODEX_KEYS.get(key)
    if not listed and len(key) == 2 and key[0] == "skillOverrides" and plain(key[1]):
        return "off".__eq__
    if not listed and len(key) == 3 and key[::2] == ("modelSettings", "effortLevel") and plain(key[1], MODEL):
        return CLAUDE_EFFORTS.__contains__
    return (CLAUDE_LISTS if listed else CLAUDE_KEYS).get(key)


def checked(agent, edit):
    """EDIT as a plan makes one, else ValueError: a key herdr-fold changes, what it puts there that key's kind, what
    it expects there told."""
    if not isinstance(edit, dict) or not isinstance(edit.get("key"), list) or not edit["key"] \
            or not all(isinstance(name, str) and name for name in edit["key"]):
        raise ValueError("not an edit")
    listed = "before" not in edit
    takes, puts = (edit.get("remove"), edit.get("add")) if listed else (edit["before"], edit.get("after"))
    test = kind(agent, edit)
    if not test or takes is None and puts is None or not listed and same(takes, puts) \
            or puts is not None and test(puts) is not True \
            or any(edit.get(name) is not None and (type(edit[name]) is not int or edit[name] < 0)
                   for name in ("at", "prune")):
        raise ValueError("not an edit herdr-fold makes")
    return edit


def changed(agent, folder, home, edits):
    """EDITS tried in order on each file as it is now, nothing written: ({path: (its text, the text they make)}, the
    edits that take them back, the last first). Refused in the panel's words; ValueError for an edit no plan makes."""
    texts, undo = {}, []
    for edit in edits if isinstance(edits, list) and edits else [None]:
        path = place(agent, checked(agent, edit).get("layer"), folder, home)
        try:
            was, now = texts[path] if path in texts else [text_of(path)] * 2
            now, back = (toml_edit if agent == "codex" else json_edit)(now, edit)
        except Refused as why:
            raise Refused(why.args[0].format(path=setup.shown(path, folder, home))) from None
        texts[path] = (was, now)
        undo.insert(0, {"layer": edit["layer"], **back})
    return texts, undo


def apply(agent, folder, home, edits):
    """EDITS (a plan's, or an answer's "undo") made, each file read again and written once: {"applied": True, "error":
    None, "undo": the edits that take them back, "made" where they made the file}; else nothing written (a file
    written before one that failed put back) and {"applied": False, "error": why, "undo": []}. ValueError: no plan's."""
    try:
        texts, undo = changed(agent, folder, home, edits)
    except Refused as why:
        return {"applied": False, "error": str(why), "undo": []}
    written = []
    made = {place(agent, edit["layer"], folder, home) for edit in edits if edit.get("made")}
    try:
        for path, (was, now) in texts.items():
            written.append((path, was, os.path.lexists(path)))
            if path in made and now.strip() in ("", "{}"):       # an undo: the file the edit made goes with it
                os.unlink(path)
            else:
                put(path, now)
    except OSError:
        for path, was, existed in written[:-1]:
            with contextlib.suppress(OSError):
                put(path, was) if existed else os.unlink(path)
        return {"applied": False, "error": UNWRITTEN.format(path=setup.shown(written[-1][0], folder, home)),
                "undo": []}
    new = {path for path, _, existed in written if not existed}
    return {"applied": True, "error": None, "undo": [
        dict(back, made=True) if place(agent, back["layer"], folder, home) in new else back for back in undo]}
