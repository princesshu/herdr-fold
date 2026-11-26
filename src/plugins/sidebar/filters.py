"""The filters of the Issues view's two lists (issues.py, pulls.py), one rule in both clients: the funnel at the field's
end, its menu in groups built from what the list holds (each value with how many would stay), any of a group's values,
every group, and what is on as one chip a group under the field (× each, Clear all)."""
from dataclasses import replace

from github import LIMIT, ME, TOP_LABELS, offered, ordered, passes
from icons import glyphs
from screen import Style, truncate, width
from widgets import Heading, Menu, Popup, Row, TextInput

MINE = {"assigned": "Assigned to me", "authored": "Created by me"}       # ME's groups, a row each, no head, no count
NAMES = {"level": "Priority", "type": "Type", "label": "Label", "review": "Review", "checks": "Checks"}
CLEAR = "Clear"


def counted(label, totals, state):
    """STATE's LABEL with the repository's count of it from TOTALS (Open 2), the word alone while it is not known: never
    a 0 that is no count."""
    count = (totals or {}).get(state)
    return f"{label} {count}" if type(count) is int else label


class Filters:
    """GROUPS' values on (CHOSEN, each a tuple; ME's two groups (True,) while on), the labels past the first TOP_LABELS
    shown (MORE), its menu's find field; LOOK(group, value, icons) says how a value reads: (its words, its mark (a
    glyph, its role) or None, the role of its words or None)."""

    def __init__(self, groups, look):
        self.groups, self.look = groups, look
        self.chosen = {group: () for group in groups}
        self.more, self.find = False, TextInput(placeholder="Find")

    def on(self):
        """Whether any filter is on (the funnel in the accent, the chips' row shown)."""
        return any(self.chosen.values())

    def narrows(self, facets):
        """Whether an item of FACETS stays with the values on."""
        return passes(facets, self.chosen)

    def toggle(self, group, value):
        """VALUE of GROUP turned on, or off when on."""
        values = self.chosen[group]
        self.chosen[group] = tuple(one for one in values if one != value) if value in values else values + (value,)

    def kept(self):
        return {group: list(values) for group, values in self.chosen.items()}

    def take(self, kept, valid):
        """The values a version before this one kept ({group: list}); VALID(group, value) says which can be one."""
        kept = kept if isinstance(kept, dict) else {}
        for group in self.groups:
            values = kept.get(group) if isinstance(kept.get(group), list) else []
            self.chosen[group] = tuple(dict.fromkeys(value for value in values if valid(group, value)))

    # --- the menu

    def menu(self, items, icons, full):
        """The menu for ITEMS (their facets), ICONS or not, FULL when the list filled LIMIT (its counts the latest
        LIMIT's, its foot says so): (the Menu, what each of its choices does: ("value", group, value), ("more",) or
        None)."""
        typed = self.find.text.strip().lower()
        choices, actions = [], []

        def add(choice, action=None):
            choices.append(choice)
            actions.append(action)
        for group in ME:
            if not typed or typed in MINE[group].lower():
                add(Row(MINE[group], on=bool(self.chosen[group])), ("value", group, True))
        many = False
        for group in (one for one in self.groups if one not in ME):
            values = [(value, count) for value, count, _ in offered(items, self.chosen, group)
                      if not typed or typed in self.look(group, value, icons)[0].lower()]
            hidden = []
            if group == "label":
                many = len(offered(items, {}, group)) > TOP_LABELS
                if many and not typed and not self.more:
                    hidden = [one for one in values[TOP_LABELS:] if one[0] not in self.chosen[group]]
                    values = [one for one in values if one not in hidden]
            if not values:
                continue
            add(Heading(NAMES[group]))
            for value, count in values:
                words, mark, role = self.look(group, value, icons)
                add(Row(words, on=value in self.chosen[group], mark=mark, role=role, count=count, faint=not count),
                    ("value", group, value))
            if hidden:
                add(Row(f"{len(hidden)} more", role="muted"), ("more",))
        if not choices:
            add(Heading("No match"))
        if full:
            add(None)
            add(Heading(f"Counts from the latest {LIMIT}"))
        return Menu(choices, self.find if many else None), actions

    # --- what is on: a chip a group under the field, and the funnel in it

    def chips(self, icons):
        """What is on, a chip a group: [(its group, its mark or None, its words)]."""
        found = [(group, None, MINE[group]) for group in ME if self.chosen[group]]
        for group in (one for one in self.groups if one not in ME):
            values = ordered(group, self.chosen[group])
            if values:
                looks = [self.look(group, value, icons) for value in values]
                found.append((group, looks[0][1], ", ".join(words for words, _, _ in looks)))
        return found

    def drop(self, key):
        """KEY's chip taken off: its group's values."""
        if key in self.chosen:
            self.chosen[key] = ()

    def draw_chips(self, canvas, y, icons, pointed):
        """What is on as one chip a group from column 1 of row Y on as many rows as they need (as the app's wrap), its ×
        lit under the mouse (POINTED), Clear at the last row's end; a chip: air, its mark and a cell, its words, a cell,
        ×, air, on the field's fill, a cell between two. Returns the rows taken."""
        end, rows, x = canvas.width - 1, [[]], 1
        for key, mark, words in self.chips(icons):
            words = truncate(words, max(1, end - 1 - (2 if mark else 0) - 4))      # alone wider than a row: cut
            size = 1 + (2 if mark else 0) + width(words) + 3
            if x > 1 and x + size > end:
                rows.append([])
                x = 1
            rows[-1].append((x, key, mark, words, size))
            x += size + 1
        if x > 1 and x + width(CLEAR) > end:
            rows.append([])
        for n, placed in enumerate(rows):
            for x, key, mark, words, size in placed:
                canvas.chip(y + n, x, size, "input")
                at = x + 1
                if mark:
                    canvas.put(y + n, at, mark[0], Style(fg=mark[1], bg="input"))
                    at += 2
                at = canvas.put(y + n, at, words, Style(fg="text", bg="input"))
                lit = pointed == ("chip", key)
                canvas.put(y + n, at + 1, "×", Style(fg="text" if lit else "muted", bg="input"))
                canvas.region(y + n, at, x + size, ("chip", key))
        last, clear = y + len(rows) - 1, end - width(CLEAR)
        canvas.put(last, clear, CLEAR, Style(fg="text" if pointed == "clear" else "muted"))
        canvas.region(last, clear, end, "clear")
        return len(rows)

    def funnel(self, canvas, row, x, icons, lit):
        """The funnel at column X of the field's ROW: in the accent while a filter is on, else muted, lit (LIT: under
        the mouse, its menu open); a cell each side answers a press."""
        role = "accent" if self.on() else "text" if lit else "muted"
        canvas.put(row, x, glyphs(icons)["funnel"], Style(fg=role, bg="input"))
        canvas.region(row, x - 1, x + 2, "filters")


class Filtered:
    """What Issues and its pull requests share of their filters: self.filters, self.query, self.listing (its ROWS),
    their facets (self.items), the menu (self.menu, self.kind "filters") under the field (self.drop); SEARCH(chosen)
    GitHub's search for the values on, asked once the list fills LIMIT. Each view has ask(), rebuild(), its list."""
    ROWS, SEARCH = "issues", None

    def full(self):
        """Whether the latest answer filled LIMIT: the menu's counts are the latest LIMIT's."""
        return self.listing is not None and len(getattr(self.listing, self.ROWS)) >= LIMIT

    def follow(self):
        """The query asked again where the values on want another search (or none); None while it is the one."""
        query = replace(self.query, search=type(self).SEARCH(self.filters.chosen) if self.full() else "")
        return self.ask(query) if query != self.query else None

    def open_filters(self, at=None):
        """The filters menu right under the field its funnel is in, their right edges in one line, its cursor on AT
        (assigned, authored, or a group's first value)."""
        menu, actions = self.filters.menu(self.items, self.icons, self.full())
        if at:
            menu.index = next((n for n, action in enumerate(actions) if action and action[1:2] == (at,)), menu.index)
        self.menu, self.kind = Popup(menu, actions, self.drop[0], self.drop[1] - menu.width()), "filters"

    def refresh_menu(self):
        """The open filters menu made again (a value turned, an answer came, its find field typed in): its cursor
        where it was, on a choice."""
        if self.kind != "filters" or not self.menu:
            return
        old = self.menu.menu
        menu, actions = self.filters.menu(self.items, self.icons, self.full())
        index = min(old.index, len(menu.choices) - 1)
        menu.index = next((n for n in [*range(index, len(menu.choices)), *range(index, -1, -1)]
                           if menu.choosable(menu.choices[n])), menu.index)
        menu.hover = old.hover
        self.menu = Popup(menu, actions, self.menu.y, self.drop[1] - menu.width())

    def close_menu(self):
        """Its menu closed, as a click outside it closes it: the pane lost the keys, or its header was clicked."""
        self.menu = self.kind = None
        self.filters.find.clear()
        self.filters.more = False

    def turn(self, action):
        """A filters menu's ACTION done, the menu staying open: a value narrowing at once (asked again when its search
        must widen what is loaded), the labels past the first six shown."""
        if action[0] == "more":
            self.filters.more = True
            self.refresh_menu()
            return None
        self.filters.toggle(action[1], action[2])
        self.list.index = 0
        self.rebuild()
        asked = self.follow()
        self.refresh_menu()
        return asked

    def drop_chip(self, key):
        """KEY's chip taken off: its group's values off at once."""
        self.filters.drop(key)
        self.rebuild()
        return self.follow()

    def clear(self):
        """Every filter off (the chips' Clear)."""
        for group in self.filters.chosen:
            self.filters.drop(group)
        self.rebuild()
        return self.follow()

    def backspace(self):
        """Backspace in the empty field: the last chip taken off."""
        chips = self.filters.chips(self.icons)
        return self.drop_chip(chips[-1][0]) if chips else None
