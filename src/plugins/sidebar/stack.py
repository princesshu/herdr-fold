"""The dock's layout in a pane's cells (core/dock.py's GROUPS): the row of buttons at its top, each icon over its short
name, the view shown under it, or, folded, the rail of the panels' icons; and what each folder keeps of it in dock.json:
the view shown."""
import os

import statefile
from dock import PANELS
from icons import glyphs
from screen import INSET, MARGIN, Style, centered, truncate, width

ROW, NAMES, TOP = 1, 2, 4     # the buttons' icons, their names under them, the view's first row: a blank row around
MORE = "More"                 # the row's last button, an ellipsis over its name: the pane's own menu
AIR = 1                       # the cells each side of the widest name
BUTTON = max(width(name) for name in [MORE, *(panel["name"] for panel in PANELS.values())]) + 2 * AIR
ICON_BUTTON = 5               # its icon alone, as the first version's tabs: the icon in the very middle, a dot last
GAP = 1                       # the cells between two buttons
EDGE = 1                      # the row's air at the pane's sides, as the views' content keeps: no block on the frame
HOVER = "hover"               # the background of a button under the mouse: a list's row's under it
FILE = "dock.json"


def label(panel):
    return MORE if panel == "panels" else PANELS[panel]["name"]


def size(panel, names=True):
    """PANEL's button's cells: BUTTON for a name as long as the widest one's parity, a cell more for the other, so the
    name stands in its very middle; ICON_BUTTON for its icon alone."""
    return BUTTON + (width(label(panel)) - BUTTON) % 2 if names else ICON_BUTTON


def cells(groups, names=True):
    """The cells the row takes with GROUPS, More's too, its NAMES or its icons alone: an EDGE of air, the buttons a GAP
    apart, a GAP more, »'s block of an icon alone (corner()) and an EDGE at the other side."""
    panels = [panel for _group, panels in groups for panel in panels] + ["panels"]
    return 2 * EDGE + sum(size(panel, names) for panel in panels) + GAP * len(panels) + ICON_BUTTON


def named(groups, room):
    """Whether a row of ROOM cells shows GROUPS' names; below that, its icons alone."""
    return cells(groups) <= room


def laid(groups, room):
    """GROUPS' buttons, then More ("panels"), in a row of ROOM cells, an EDGE in from the pane's side, a GAP apart, what
    is left at the right: [(panel, its first cell, the cell after it, its name's first cell or None, its icon's cell)],
    each name in its button's very middle, its icon over the name's middle or the button's."""
    names, x, found = named(groups, room), EDGE, []
    for panel in [panel for _group, panels in groups for panel in panels] + ["panels"]:
        cells_, name = size(panel, names), width(label(panel))
        first = x + (cells_ - name) // 2 if names else None
        found.append((panel, x, x + cells_, first, centered(first, name) if names else centered(x, cells_)))
        x += cells_ + GAP
    return found


def corner(cells):
    """The first cell of »'s block in a pane CELLS wide, an icon alone's: at the right end of the row's icons' line, an
    EDGE of air after it."""
    return cells - EDGE - ICON_BUTTON


def rail_column(cells):
    """The column of the rail's icons, « over them, in a pane CELLS wide: its content's very middle."""
    return centered(INSET, max(0, cells - 2 * INSET))


def block(x, cells):
    """The cells (first, after the last) of an icon alone's block round column X, inside columns 0..CELLS-1."""
    return max(MARGIN, x - ICON_BUTTON // 2), min(cells - MARGIN, x + ICON_BUTTON // 2 + 1)


def hover(canvas, lines, first, end):
    """Columns FIRST..END-1 of LINES (an icon's, a name's) on HOVER, half a row of it on the blank rows round them
    (▄ above, ▀ below), as the first version's tall controls; nothing drawn moves or changes color."""
    canvas.put(lines[0] - 1, first, "▄" * (end - first), Style(fg=HOVER))
    for row in lines:
        canvas.tint(row, first, end, HOVER)
    canvas.put(lines[-1] + 1, first, "▀" * (end - first), Style(fg=HOVER))


def button_row(canvas, y, groups, chosen, marks, opened=None, pointed=None, icons=True):
    """GROUPS' buttons (laid()) on row Y, their names under them where the row has room, MARKS' dots by the icons, More
    last: CHOSEN's and OPENED's in the accent, CHOSEN's name bold, the rest faint; each one, the blank rows round it
    too, answers "button:PANEL", lit under the mouse (POINTED, hover()). More's first cell."""
    buttons, lit = laid(groups, canvas.width), None
    lines = (y, y + 1) if buttons[0][3] is not None else (y,)
    for panel, x, end, first, icon in buttons:
        more = panel == "panels"
        target = panel if more else f"button:{panel}"
        look = "accent" if panel in (chosen, opened) else "text" if target == pointed else None
        canvas.put(y, icon, ("⋯" if more else glyphs(icons)[PANELS[panel]["glyph"]]), Style(fg=look or "subtext"))
        text, role = marks.get(panel) or ("", None)
        canvas.put(y, icon + 2, truncate(text, max(0, end - icon - 2)), Style(fg=role))
        if first is not None:
            canvas.put(y + 1, first, label(panel), Style(fg=look or "muted", bold=panel == chosen))
        for row in (y - 1, lines[-1] + 1, *lines):  # its own lines last, as the latest region on top
            canvas.region(row, x, end, target)
        lit = (x, end) if target == pointed else lit
    if lit:
        hover(canvas, lines, *lit)
    return buttons[-1][1]


def floor(y, top):
    """The ▀ row of the rail's block row Y falls in, its blocks from row TOP (rail())."""
    return y - (y - top) % 3 + 2


def rail(canvas, top, rows, groups, marks=None, icons=True, pointed=None, terminal=None):
    """The dock folded to its rail in ROWS rows from TOP: GROUPS' icons alone as the row's, then the tab's TERMINAL's
    (True: raised, in the accent), each a block with its own half rows; those without room left out from the end."""
    marks_ = glyphs(icons)
    items = [(f"icon:{panel}", marks_[PANELS[panel]["glyph"]], panel) for _group, panels in groups for panel in panels]
    items += [("terminal", marks_["terminal"], None)] if terminal is not None else []
    x = rail_column(canvas.width)
    first, end = block(x, canvas.width)
    for n, (target, glyph, panel) in enumerate(items[:rows // 3]):
        y = top + 1 + 3 * n                         # its icon's line, under its own ▄ row, the last one's ▀ before it
        look = "accent" if target == "terminal" and terminal else "text" if target == pointed else None
        text, role = (marks or {}).get(panel) or ("", None)
        canvas.put(y, x, glyph, Style(fg=look or "subtext"))
        canvas.put(y, x + 2, truncate(text, max(0, end - x - 2)), Style(fg=role))
        if target == pointed:
            hover(canvas, (y,), first, end)
        for row in (y - 1, y + 1, y):
            canvas.region(row, 0, canvas.width, target)


def state(state_dir, folder):
    """What FOLDER keeps: {"shown": the view shown, or None}."""
    return parsed(statefile.read(os.path.join(state_dir, FILE)).get(folder))


def parsed(kept):
    """state() of a folder's entry KEPT in FILE; what cannot be read is None."""
    shown = kept.get("shown") if isinstance(kept, dict) else None
    return {"shown": shown if isinstance(shown, str) else None}


def keep(state_dir, folder, shown):
    """FOLDER's view SHOWN kept, on what FILE holds then (statefile.update: another sidebar on this folder, a preview
    tab's, writes it too); every entry rewritten as parsed() reads it, so a folder gone goes on the way. OSError when
    it cannot be written."""
    def changed(data):
        kept = {name: parsed(entry) for name, entry in data.items() if os.path.isdir(name)}
        kept[folder] = {"shown": shown}
        return {name: entry for name, entry in kept.items() if entry["shown"]}

    statefile.update(os.path.join(state_dir, FILE), changed, indent=2)
