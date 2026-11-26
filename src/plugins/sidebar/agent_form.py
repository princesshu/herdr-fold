"""A form of the Agent view (layers.py lays it under the chosen item): one of core's plans (harness.py's) in cells as
harness-editing.html's TUI frames: its controls, the layer, the lines it changes, when and what overrides it, all in
core's words; its keys and presses. It only asks: the family plans and saves."""
from harness_edit import MANAGED
from screen import AIR, INSET, Style, truncate, width
from widgets import Action, TextInput, wrap

SWITCH = ((True, "on"), (False, "off"))      # a switch's two chips, as the frames draw them
BACK, ON = "‹", "›"                          # round the one of a few shown: the layer, a built-in subagent's name
REMOVE_KEY = "x"                             # Remove from the keys, off a text field
ROWS = 3                                     # rows a change line, a warning or a refusal takes at most
SIGNS = {"-": ("−", "deleted"), "+": ("+", "added")}
QUIET = ("now", "more", "remove")            # the buttons the keys step to: Enter anywhere else is the primary one


def pieces(words, room):
    """WORDS in rows ROOM cells wide, ROWS of them at most."""
    return [words[start:end].rstrip() for start, end in wrap(words, max(1, room))][:ROWS]


def low(words):
    """Core's WORDS as a line of the TUI starts them: the first letter small."""
    return words[:1].lower() + words[1:]


class Form:
    def __init__(self, key, base, names=(), said=(), parts=False):
        self.key, self.base = key, base       # the item it lies under; core's request as the form opens
        self.names = list(names)              # Claude's own subagents, one of them the switch's
        self.said = said                      # what its item says already: a control labelled so has no label
        self.parts = parts                    # a server not approved yet: its switch is core's two words, none held
        self.asked, self.plan, self.waits = dict(base), None, True       # the request, core's plan, none of it yet
        self.entered, self.at = False, None   # whether the keys are its own, and the control they are in
        self.inputs, self.error, self.told = {}, None, 0     # its text fields, a save's refusal, the commands typed

    # --- the request

    def ask(self, **change):
        """The request with CHANGE (None: left out), planned again before the next draw."""
        self.asked = {key: value for key, value in {**self.asked, **change}.items() if value is not None}
        self.waits, self.error = True, None

    def planned(self, asked, plan):
        """Core's PLAN for ASKED (None: no form for it); an answer to an older request is left."""
        if asked != self.asked:
            return
        self.plan, self.waits = plan or {}, False
        for one in self.fields():
            if one["kind"] == "text" and one["id"] not in self.inputs:
                self.inputs[one["id"]] = made = TextInput()
                made.insert(one["value"] or "")
        stops = self.stops()
        self.at = self.at if self.at in stops else stops[0] if stops else None

    def fields(self):
        """The plan's controls, a switch as a choice of two (on and off after its short label; a server not approved
        yet: core's two words alone, the one asked for held); none while it asks before a removal."""
        plan = self.plan or {}

        def two(one):
            if self.parts:
                return {**one, "label": None, "value": self.asked.get("on"), "choices": [
                    {"id": value, "label": one["turn"][word], "off": None} for value, word in SWITCH]}
            return {**one, "label": one.get("short") or one["label"], "choices": [
                {"id": value, "label": word, "off": None} for value, word in SWITCH]}

        return [] if plan.get("ask") else [two(one) if one["kind"] == "switch" else one
                                           for one in plan.get("fields") or []]

    def field(self, key):
        return next((one for one in self.fields() if one["id"] == key), None)

    def locked(self):
        """Whether the form as it opened cannot be changed: core's sentence stands in its place."""
        return not self.plan or bool(self.plan["error"]) and not self.entered

    def hosts(self, one):
        """The numbers of the hosts of the text field ONE that can be taken out: a layer's own, not a rule's."""
        return [n for n, item in enumerate(one.get("items") or []) if not item["rule"] and item["layer"] != MANAGED]

    def buttons(self, chat):
        """The buttons in order, [(id, label)]: the primary one (where a chat is told instead: the switch's own
        words), Switch this chat now with a Claude in the tab (CHAT), More options, Remove."""
        plan = self.plan
        switch = next((one for one in plan["fields"] if one["kind"] == "switch"), None)
        told = plan["say"] and not plan["edits"] and not plan["now"] and switch
        found = [("submit", plan["submit"])] if plan["submit"] else [("submit", switch["turn"]["on"])] if told else []
        found += [("now", plan["now"])] if plan["now"] and chat else []
        found += [("more", f"{plan['more']['label']} {ON}")] if plan["more"] else []
        return found + ([("remove", plan["remove"])] if plan["remove"] and not plan["ask"] else [])

    def stops(self):
        """What ↑ and ↓ step through: the name, each control (a host that can go before its field), the quiet
        buttons."""
        if self.locked():
            return []
        found = ["name"] if self.names and self.fields() else []
        for one in self.fields():
            found += [("host", n) for n in self.hosts(one)] if one["kind"] == "text" else []
            found += [one["id"]] if one["kind"] == "text" or any(not c["off"] for c in one["choices"]) else []
        return found + [key for key, _ in self.buttons(True) if key in QUIET]

    def enter(self):
        """The keys its own, in its first control; False where there is nothing to change."""
        stops = self.stops()
        if not stops:
            return False
        self.entered, self.at = True, self.at if self.at in stops else stops[0]
        return True

    def leave(self):
        """As it opened, the keys the view's again."""
        self.entered, self.asked, self.inputs, self.error, self.waits = False, dict(self.base), {}, None, True
        self.at = None

    def choose(self, key, value):
        """The control KEY set to VALUE: another name starts its switch anew, another way its rule."""
        if key == "name":
            self.ask(name=value, on=None, layer=None)
        elif key == "way":
            self.inputs.pop("to", None)
            self.ask(way=value, to=None)
        else:
            self.ask(**{key: value})

    def step(self, key, by):
        """The control KEY's next choice (BY: 1 or -1), a grey one passed over; the name and the layer go round."""
        if key in ("name", "layer"):
            ids = self.names if key == "name" else [one["id"] for one in self.plan["layers"]]
            now = self.asked["name"] if key == "name" else next(one["id"] for one in self.plan["layers"]
                                                               if one["chosen"])
            return self.choose(key, ids[(ids.index(now) + by) % len(ids)])
        one = self.field(key)
        ids = [choice["id"] for choice in one["choices"] if not choice["off"]]
        at = ids.index(one["value"]) + by if one["value"] in ids else 0 if by > 0 else len(ids) - 1
        return self.choose(key, ids[max(0, min(len(ids) - 1, at))])

    def remove(self):
        """The rule's removal asked for: core's one question, then Remove."""
        self.asked, self.waits, self.error = {**self.base, "remove": True}, True, None

    def take_out(self, n):
        """Host N of the list out of its own layer's file."""
        item = next(one for one in self.fields() if one.get("items"))["items"][n]
        self.ask(remove=item["host"], layer=item["layer"])

    def do(self, what):
        """A button done: the plan's edits saved (a chat told instead where core says so), the chat's command typed,
        the layer's file opened, the removal asked for."""
        plan = self.plan
        if what == "submit" and plan["submit"] and not self.waits:
            return Action("save_harness", (plan["edits"],))
        if what == "submit" and any(key == "submit" for key, _ in self.buttons(False)) and not self.waits:
            return Action("turn_server", (self.asked["name"],))
        if what == "now" and plan["say"]:
            self.told += 1
            return Action("type_command", (plan["say"][(self.told - 1) % len(plan["say"])],))
        if what == "more":
            return Action("open_layer", (next(one["id"] for one in plan["layers"] if one["chosen"]),))
        if what == "remove":
            self.remove()
        return None

    def saved(self):
        """The foot's words once the plan is saved: what was removed, else when it applies."""
        return self.plan["done"] or low(self.plan["when"] or "")

    # --- keys and presses

    def handle(self, event):
        """A key in the form: ↑ ↓ step, ← → or Space choose, Tab the layer, a field takes what is typed, x removes
        (a host in the list, else the rule), Enter the primary button (on a quiet one: that), Esc leaves."""
        name, stops, at = event.name, self.stops(), self.at
        typed = event.char if name == "char" and not (event.ctrl or event.alt) else None
        text = at in self.inputs
        if name == "esc" or not self.plan:
            self.leave()
        elif name in ("tab", "backtab") and self.plan["layers"] and not self.plan["ask"]:
            self.step("layer", 1 if name == "tab" else -1)
        elif name in ("up", "down") and stops:
            to = (stops.index(at) if at in stops else 0) + (1 if name == "down" else -1)
            self.at = stops[max(0, min(len(stops) - 1, to))]
        elif name == "enter":
            return self.do(at if at in QUIET else "submit")
        elif text:
            before = self.inputs[at].text
            self.inputs[at].handle(event)
            if self.inputs[at].text != before:
                self.asked, self.waits, self.error = {**self.asked, at: self.inputs[at].text}, True, None
        elif isinstance(at, tuple) and (typed == REMOVE_KEY or name in ("delete", "backspace")):
            self.take_out(at[1])
        elif typed == REMOVE_KEY and self.plan["remove"] and not self.plan["ask"]:
            self.remove()
        elif (name in ("left", "right") or typed == " ") and isinstance(at, str) and at not in QUIET:
            self.step(at, -1 if name == "left" else 1)
        return None

    def press(self, target):
        """A press on one of its parts: a choice made, the layer's next, its file opened, the keys in a field, a host
        taken out, a button done; the keys its own from then on."""
        kind = target[0]
        if kind == "path":
            return Action("open_layer", (target[1],))
        if kind == "do":
            return self.do(target[1])
        self.entered = True
        if kind == "choose":
            self.at = target[1]
            self.choose(target[1], target[2])
        elif kind == "next":
            self.step(target[1], 1)
        elif kind == "stop":
            self.at = target[1]
        elif kind == "host":
            self.take_out(target[1])
        return None

    # --- its lines

    def column(self, one):
        """The cells the control ONE's label takes with its air: none where its item says the label already; a
        switch's its own, the others' one column."""
        if not one["label"] or one["label"] in self.said:
            return 0
        return max(width(each["label"]) for each in self.fields() if each["id"] == one["id"] or "switch" not in (
            each["kind"], one["kind"]) and each["label"] and each["label"] not in self.said) + 2

    def chips(self, one, room):
        """The choice ONE's chips in rows ROOM cells wide, its label before the first."""
        rows, used = [[]], 0
        for choice in one["choices"]:
            cells = width(choice["label"]) + 2
            if rows[-1] and used + cells > room - self.column(one):
                rows.append([])
                used = 0
            rows[-1].append(choice)
            used += cells
        return [("chips", (one, row, not n)) for n, row in enumerate(rows)]

    def lines(self, room, chat=False):
        """Its lines ROOM cells wide, [(kind, what)]. As it opens: its choices alone, or why it is locked; with the
        keys in it: every control, the layer and its file, the change by file, when, the warnings, the refusal, the
        buttons (CHAT: a Claude runs in the tab)."""
        plan = self.plan
        if not plan:
            return []
        if self.locked():
            return [("said", piece) for piece in pieces(plan["error"], room)]
        found = [("words", plan["ask"])] if plan["ask"] else []
        found += [("name", None)] if self.names and self.fields() else []
        for one in self.fields():
            if one["kind"] != "text":
                found += self.chips(one, room)
                found += [("said", piece) for piece in pieces(one.get("hint") or "", room) if piece] * self.entered
            elif self.entered:
                items = one.get("items") or []
                found += [("item", (one, n)) for n in range(len(items))] + [("text", (one, not items))]
        if not self.entered:
            return found
        layers, blocks = ([] if plan["ask"] else plan["layers"]), plan["changes"]
        chosen = next((one for one in layers if one["chosen"]), None)
        beside = bool(chosen) and all(block["path"] == chosen["path"] for block in blocks) and width(
            f"{plan['saved']} {BACK} {chosen['label']} {ON}  {chosen['path']}") <= room
        ids = {one["path"]: one["id"] for one in layers}
        found += [("layer", (chosen, beside))] if chosen else []
        found += [("file", (chosen["path"], chosen["id"]))] if chosen and not beside and not blocks else []
        for block in blocks:
            found += [] if beside else [("file", (block["path"], ids.get(block["path"])))]
            found += [("change", (sign if not n else None, piece)) for sign, words in block["lines"]
                      for n, piece in enumerate(pieces(words, room - 2))]
        found += [("said", words) for words in plan["say"]] if not plan["edits"] else []
        found += [("said", piece) for piece in pieces(low(plan["when"] or ""), room) if piece]
        found += [("warn", piece) for words in plan["warns"] for piece in pieces(words, room)]
        found += [("error", piece) for piece in pieces(plan["error"] or self.error or "", room) if piece]
        rows, used = [[]], 0
        for key, label in self.buttons(chat):
            cells = width(label) + 2
            if rows[-1] and used + cells > room:
                rows.append([])
                used = 0
            rows[-1].append((key, label))
            used += cells + 2
        return found + [("buttons", row) for row in rows if row]

    def draw(self, canvas, y, x, line, hover=None):
        """One of lines()'s from column X: a part that can be pressed its region ("edit", target), the terminal's
        cursor where the keys are."""
        kind, what = line
        end = canvas.width - INSET
        plain = {"words": "text", "said": "muted", "warn": "modified", "error": "deleted"}
        if kind in plain:
            canvas.put(y, x, truncate(what, max(1, end - x)), Style(fg=plain[kind]))
        elif kind == "file":
            self.path(canvas, y, x, *what)
        elif kind == "change":
            sign, words = what
            glyph, role = SIGNS[sign] if sign else (" ", "muted")
            canvas.put(y, x, glyph, Style(fg=role))
            canvas.put(y, x + 2, truncate(words, max(1, end - x - 2)), Style(fg="subtext"))
        elif kind == "name":
            self.one_of(canvas, y, x, "name", self.asked["name"])
        elif kind == "layer":
            chosen, beside = what
            at = canvas.put(y, x, self.plan["saved"], Style(fg="muted"))
            at = self.one_of(canvas, y, at + 1, "layer", chosen["label"])
            if beside:
                self.path(canvas, y, at + 2, chosen["path"], chosen["id"])
        elif kind == "chips":
            self.chip_row(canvas, y, x, *what, hover)
        elif kind == "item":
            self.item(canvas, y, x, *what, hover)
        elif kind == "text":
            one, labelled = what
            col = self.column(one)
            if labelled:
                canvas.put(y, x, one["label"], Style(fg="text" if self.at == one["id"] else "muted"))
            self.inputs[one["id"]].draw(canvas, y, x + col, max(1, end - x - col), 1, Style(fg="text", bg="input"),
                                        self.entered and self.at == one["id"])
            canvas.region(y, x + col, end, ("edit", ("stop", one["id"])))
        elif kind == "buttons":
            self.button_row(canvas, y, x, what, hover)

    def path(self, canvas, y, x, path, layer):
        """A file by the name core shows it with; a LAYER's own opens with a press (no Open button beside it)."""
        words = truncate(path, max(1, canvas.width - INSET - x))
        canvas.put(y, x, words, Style(fg="muted"))
        if layer:
            canvas.region(y, x, x + width(words), ("edit", ("path", layer)))

    def one_of(self, canvas, y, x, key, shown):
        """‹ SHOWN ›: the one of a few the control KEY holds, a press its next. Where it ends."""
        at = canvas.put(y, x, f"{BACK} ", Style(fg="muted"))
        at = canvas.put(y, at, shown, Style(fg="text"))
        end = canvas.put(y, at, f" {ON}", Style(fg="muted"))
        canvas.region(y, x, end, ("edit", ("next", key)))
        if self.entered and self.at == key:
            canvas.cursor = (y, x + 2)
        return end

    def chip_row(self, canvas, y, x, one, row, first, hover):
        """A row of the choice ONE's chips: the one held lit (the accent's with the keys in the form), a grey one
        that cannot be chosen here."""
        end, held = canvas.width - INSET, self.entered and self.at == one["id"]
        if first and self.column(one):
            canvas.put(y, x, one["label"], Style(fg="text" if held else "muted"))
        x += self.column(one) - 1                # a chip's words in the values' column, its air before it
        for n, choice in enumerate(row):
            words = truncate(choice["label"], max(1, end - x - 2))
            lit, target = choice["id"] == one["value"] and one["value"] is not None, ("edit", (
                "choose", one["id"], choice["id"]))
            if lit:
                canvas.chip(y, x, width(words) + 2, "button" if self.entered else "input")
            canvas.put(y, x + 1, words, Style(fg="muted") if choice["off"] else Style(
                fg="button_text", bg="button", bold=True) if lit and self.entered else Style(
                fg="text", bg="input") if lit else Style(fg="text" if hover == target else "subtext"))
            if not choice["off"]:
                canvas.region(y, x, x + width(words) + 2, target)
            if held and (lit or one["value"] is None and first and not n):
                canvas.cursor = (y, x + 1)
            x += width(words) + 2

    def item(self, canvas, y, x, one, n, hover):
        """A host of the list: its name, its layer dim, × AIR after it where it can be taken out."""
        end, at, item = canvas.width - INSET, x + self.column(one), one["items"][n]
        if not n:
            canvas.put(y, x, one["label"], Style(fg="muted"))
        goes = n in self.hosts(one)
        room = end - at - width(item["layer"]) - 2 - (AIR + 1 if goes else 0)
        at = canvas.put(y, at, truncate(item["host"], max(1, room)), Style(fg="text"))
        at = canvas.put(y, at + 2, item["layer"], Style(fg="muted"))
        if goes:
            target, cross = ("edit", ("host", n)), at + AIR
            canvas.put(y, cross, "×", Style(fg="text" if hover == target else "subtext"))
            canvas.region(y, cross - 1, cross + 2, target)
            if self.entered and self.at == ("host", n):
                canvas.cursor = (y, cross)

    def button_row(self, canvas, y, x, row, hover):
        """The buttons: the primary one the accent's block, the others quiet, Remove plain words after its key."""
        for key, label in row:
            target = ("edit", ("do", key))
            lit = hover == target or self.at == key
            if key == "remove":
                canvas.put(y, x, REMOVE_KEY, Style(fg="muted"))
                canvas.put(y, x + 1, f" {label}", Style(fg="text" if lit else "subtext"))
            else:
                bg = "button" if key == "submit" else "hover" if lit else "input"
                canvas.chip(y, x, width(label) + 2, bg)
                canvas.put(y, x + 1, label, Style(fg="button_text", bg=bg, bold=True) if key == "submit"
                           else Style(fg="text" if lit else "subtext", bg=bg))
            canvas.region(y, x, x + width(label) + 2, target)
            if self.entered and self.at == key:
                canvas.cursor = (y, x + 1)
            x += width(label) + 4
