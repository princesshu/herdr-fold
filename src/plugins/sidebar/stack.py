"""The dock's layout in a pane's cells (core/dock.py's GROUPS): the tab row at its top, the panel shown under it, or,
folded, the rail of the panels' icons; and what each folder keeps of it in dock.json: the panel shown."""
import os

import statefile
from dock import PANELS
from icons import glyphs
from screen import Style, centered, truncate, width

ROW, TOP = 1, 3               # the tab row's row, and the panel's first: a blank row above the tab row and below it
GAP, APART = 2, 3             # the cells between two tabs of a group, and between two groups (the last tab and » too)
MORE = 5                      # the cells of the ⋯ (the pane's own menu) at the row's right end
CONTROLS = APART + 2 + MORE + 1   # after the last tab: the gap, » and a cell, the ⋯ and a cell of edge
COUNT = 3                     # the digits of Changes' count at most (999)
# Chats' dot keeps its cells while no conversation waits: the tabs after it stay put under the mouse
KEPT = {"conversations": "●"}
WIDEST = {**KEPT, "changes": "9" * COUNT}
FILE = "dock.json"


def laid(groups, marks):
    """Each tab of GROUPS ([(group, [panel])]) on the tab row: [(panel, its first cell, the cell after it)], its name
    and, a cell after it, its mark (MARKS {panel: (text, role)}); GAP between two tabs of a group, APART between
    groups."""
    found, x = [], 1
    for n, (_group, panels) in enumerate(groups):
        x += APART if n else 0
        for m, panel in enumerate(panels):
            x += GAP if m else 0
            mark = (marks.get(panel) or ("",))[0] or KEPT.get(panel, "")
            end = x + width(PANELS[panel]["name"]) + (1 + width(mark) if mark else 0)
            found.append((panel, x, end))
            x = end
    return found


def cells(groups):
    """The cells the tab row takes with GROUPS, every mark at its widest: what the column keeps to at least."""
    tabs = laid(groups, {panel: (text, None) for panel, text in WIDEST.items()})
    return (tabs[-1][2] if tabs else 1) + CONTROLS


def fitted(groups, marks, room, shown):
    """laid() of the tabs a row of ROOM cells has room for, each whole: the last left out first, never SHOWN; none
    where SHOWN alone has no room (a name never cut short)."""
    groups = [(group, list(panels)) for group, panels in groups]
    while True:
        tabs = laid(groups, marks)
        if not tabs or tabs[-1][2] + CONTROLS <= room:
            return tabs
        last = next((panel for panel, _x, _end in reversed(tabs) if panel != shown), None)
        if last is None:
            return []
        groups = [(group, [panel for panel in panels if panel != last]) for group, panels in groups]
        groups = [(group, panels) for group, panels in groups if panels]


def tab_row(canvas, y, groups, shown, marks, pointed=None):
    """The tabs of GROUPS on row Y of CANVAS (fitted() to its width): SHOWN's name bold in the accent, POINTED's (under
    the mouse) in the text's color, the others muted; each one's mark from MARKS (Chats' dot, Changes' count) after
    it; a click on either answers "tab:PANEL"."""
    for panel, x, end in fitted(groups, marks, canvas.width, shown):
        look = "accent" if panel == shown else "text" if panel == pointed else "muted"
        after = canvas.put(y, x, PANELS[panel]["name"], Style(fg=look, bold=panel == shown))
        text, role = marks.get(panel) or ("", None)
        if text:
            canvas.put(y, after + 1, text, Style(fg=role))
        canvas.region(y, x, end, f"tab:{panel}")


def rail(canvas, top, rows, lit, groups, marks=None, icons=True, left=0, pointed=None):
    """The dock folded to its rail in ROWS rows from TOP, from column LEFT on: each panel of GROUPS ([(group, [panel])])
    its glyph over its name, a blank row between two groups, one without the rows left out; LIT's (opened beside it)
    in the accent, a bar at its edge; POINTED's ("icon:PANEL") lit; MARKS {panel: (text, role)} beside the icon."""
    cells_, y = canvas.width - left, top
    for n, (_group, panels) in enumerate(groups):
        y += 1 if n else 0
        for panel in panels:
            if y + 2 > top + rows:
                return
            target, x, name = f"icon:{panel}", centered(left, cells_), PANELS[panel]["name"]
            look = "accent" if panel == lit else "text" if target == pointed else None
            canvas.put(y, x, glyphs(icons)[PANELS[panel]["glyph"]], Style(fg=look or "subtext"))
            if panel == lit:
                canvas.put(y, left, "▌", Style(fg="accent"))
            text, role = (marks or {}).get(panel) or ("", None)
            canvas.put(y, x + 2, truncate(text, max(0, canvas.width - x - 2)), Style(fg=role))
            canvas.put(y + 1, left + max(0, (cells_ - width(name)) // 2), truncate(name, cells_),
                       Style(fg=look or "muted", bold=panel == lit))
            for row in (y, y + 1):
                canvas.region(row, left, canvas.width, target)
            y += 2


def state(state_dir, folder):
    """What FOLDER keeps: {"shown": the panel shown, or None}."""
    return parsed(statefile.read(os.path.join(state_dir, FILE)).get(folder))


def parsed(kept):
    """state() of a folder's entry KEPT in FILE; what cannot be read (an older version's groups too) is None."""
    shown = kept.get("shown") if isinstance(kept, dict) else None
    return {"shown": shown if isinstance(shown, str) else None}


def keep(state_dir, folder, shown):
    """FOLDER's panel SHOWN kept, on what FILE holds then (statefile.update: another sidebar on this folder, a preview
    tab's, writes it too); every entry rewritten as parsed() reads it, so a folder gone and what an older version kept
    go on the way. OSError when it cannot be written."""
    def changed(data):
        kept = {name: parsed(entry) for name, entry in data.items() if os.path.isdir(name)}
        kept[folder] = {"shown": shown}
        return {name: entry for name, entry in kept.items() if entry["shown"]}

    statefile.update(os.path.join(state_dir, FILE), changed, indent=2)
