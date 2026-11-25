"""The right column's width in cells, the same in every tab and window: first as wide as the row's names need, then as
dragged, kept across herdr's restarts; so is the dock folded to its rail. A tab splits as agent | right column, set
through herdr's socket API (its command line cannot set a split): a first side is round(width x ratio)."""
import json
import os
import socket
import time
from dataclasses import dataclass

import stack
import statefile
from dock import GROUPS

FILE = "column.json"
WIDTH = "open"              # FILE's key for the cells last dragged, frame and all
SIDEBAR = "sidebar"         # the right column's top pane, by its name
RIGHT = 0.75                # the share before the right column where the tab's width cannot be read
TOLERANCE = 0.002           # shares this close are the same width (a cell is about 0.007 of a wide window)
# the share before a dragged column: outside this nobody chose it (a tab too small); the agent keeps the first, so the
# open column is never wider than the rest (most()) but where its row needs it
LIMITS = (0.3, 0.9)
SPLIT = (0.1, 0.9)          # the shares herdr lets a split have
SETTLE = 0.2                # seconds a tab's widths stay put before a pane takes them as chosen
# the right column's cells inside herdr's frame: the row's buttons a cell apart and »'s block (stack.cells())
WITHOUT_ISSUES = [(group, [panel for panel in panels if panel != "issues"]) for group, panels in GROUPS]
NARROWEST = stack.cells(GROUPS, names=False)    # every view's icon alone and More's (49): never narrower
FEWEST = stack.cells(WITHOUT_ISSUES, names=False)   # the same without Issues (43): a tab's sidebar takes at least
IDEAL = stack.cells(GROUPS)                     # every view's name and More's (80): the width it first opens to
FRAME = 2                   # herdr's frame round a pane, in cells, where it is not measured
RAIL = 5                    # the rail: an icon's five cells (stack.ICON_BUTTON) and the margins, each on the middle


def socket_path():
    return os.environ.get("HERDR_SOCKET_PATH") or os.path.join(os.path.expanduser("~"), ".config", "herdr",
                                                               "herdr.sock")


def call(method, params):
    """herdr's answer to METHOD; any failure (no herdr, an error answer) raises OSError."""
    request = (json.dumps({"id": method, "method": method, "params": params}) + "\n").encode()
    if os.name == "nt":                     # herdr listens on a named pipe called after its socket path
        with open("\\\\.\\pipe\\" + socket_path(), "r+b", buffering=0) as pipe:
            pipe.write(request)
            reply = read_line(pipe.read)
    else:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(5)
            conn.connect(socket_path())
            conn.sendall(request)
            reply = read_line(conn.recv)
    try:
        answer = json.loads(reply)
    except ValueError as err:
        raise OSError("herdr gave no answer") from err
    if not isinstance(answer, dict) or not isinstance(answer.get("result"), dict):
        raise OSError(refusal(answer) or "herdr refused")
    return answer["result"]


def refusal(answer):
    """herdr's error answer as the foot says it: its own message as a sentence ("A popup pane is already open"), never
    its JSON. ANSWER: the answer, or a line of it as text; None where it holds no message."""
    if isinstance(answer, str):
        try:
            answer = json.loads(answer) if answer.lstrip().startswith("{") else None
        except ValueError:
            return None
    error = answer.get("error") if isinstance(answer, dict) else None
    message = error.get("message") if isinstance(error, dict) else error
    message = " ".join(message.split()) if isinstance(message, str) else ""
    return message[:1].upper() + message[1:] if message else None


def read_line(read):
    reply = b""
    while not reply.endswith(b"\n"):
        chunk = read(65536)
        if not chunk:
            break
        reply += chunk
    return reply


@dataclass
class Columns:
    """A tab's columns: the path of the split before the right column (OUTER), the shares of its width before it and of
    the right column; OUTER's width in cells (0: not known), and each pane's (WIDTHS, frame and all)."""
    tab: str
    outer: list
    left: float
    right: float
    cells: int = 0
    widths: dict = None


def at(node, path):
    for second in path:
        node = node.get("second" if second else "first") or {}
    return node


def panes(node):
    if node.get("type") == "pane":
        return [node.get("pane_id")]
    return panes(node.get("first") or {}) + panes(node.get("second") or {})


def find(node, label, path=()):
    """The path to the pane named LABEL, or None."""
    if node.get("type") == "pane":
        return list(path) if node.get("label") == label else None
    return find(node.get("first") or {}, label, (*path, False)) or find(node.get("second") or {}, label, (*path, True))


def columns(found, label=SIDEBAR):
    """The columns in FOUND (a tab's layout.export), or None when it has no right column: the innermost split to the
    right whose second side holds the sidebar (or the pane named LABEL)."""
    root = found.get("root") or {}
    path = find(root, label)
    if path is None:
        return None
    for depth in range(len(path) - 1, -1, -1):
        node = at(root, path[:depth])
        if node.get("direction") == "right" and path[depth]:
            outer = float(node.get("ratio", 0))
            return Columns(found.get("tab_id"), path[:depth], outer, 1 - outer)
    return None


def layout(pane):
    """The tab's layout around PANE, or None (no herdr, or the agent zoomed: the column is not on screen)."""
    try:
        found = call("layout.export", {"pane_id": pane}).get("layout") or {}
    except OSError:
        return None
    return None if found.get("zoomed") else found


def chosen(state_dir):
    """The right column's cells, its frame's too, as last dragged on this machine (WIDTH); None until one is dragged,
    so it first opens at the row's ideal width."""
    cells = kept(state_dir).get(WIDTH)
    return cells if isinstance(cells, int) and not isinstance(cells, bool) and cells > 0 else None


def opened(state_dir, tab):
    """TAB's right column's cells while the dock is open: as last dragged, else as wide as the row's names need (IDEAL
    and the frame), never narrower than its sidebar's row (least())."""
    return max(chosen(state_dir) or IDEAL + FRAME, least(state_dir, tab.tab) + FRAME)


def most(cells):
    """The open right column's most cells in a tab CELLS wide: the agent keeps LIMITS[0] of it."""
    return int(cells * (1 - LIMITS[0]))


def room(state_dir, tab):
    """TAB's open right column's cells (TAB.cells known): opened()'s, within the agent's room (most()) but never
    narrower than its sidebar's row: a narrow window opens it narrower, a wider one as chosen again."""
    return max(least(state_dir, tab.tab) + FRAME, min(opened(state_dir, tab), most(tab.cells)))


def split_share(state_dir, pane):
    """The share before a new right column split off PANE (a new tab's only pane: the tab's width), so it opens as
    wide as room() at once; where herdr cannot say how wide PANE is, RIGHT."""
    try:
        rects = call("pane.layout", {"pane_id": pane}).get("layout", {})["panes"]
        total = next(r["rect"]["width"] for r in rects if r["pane_id"] == pane)
    except (OSError, KeyError, TypeError, StopIteration):
        return RIGHT
    return share(1 - max(FEWEST + FRAME, min(chosen(state_dir) or IDEAL + FRAME, most(total))) / total)


def kept(state_dir):
    return statefile.read(os.path.join(state_dir, FILE))


def keep(state_dir, values):
    """VALUES kept in FILE, whatever else it keeps staying; whether they were."""
    return change(state_dir, lambda found: {**found, **values})


def change(state_dir, how):
    """FILE changed by HOW (given what it holds then, its answer kept) under statefile.update: every tab's sidebar
    writes it. Whether it was."""
    try:
        statefile.update(os.path.join(state_dir, FILE), how)
    except OSError:
        return False
    return True


def least(state_dir, tab):
    """The right column's fewest cells inside herdr's frame in TAB: what its sidebar's row takes (need()), or
    FEWEST until it has said (a sidebar with more widens its tab itself, at once)."""
    cells = (kept(state_dir).get("least") or {}).get(tab)
    return cells if isinstance(cells, int) and 0 < cells <= NARROWEST else FEWEST


def need(state_dir, tab, cells, tabs):
    """TAB's sidebar's row takes CELLS: kept, for the TABS there are now only."""
    def needed(found):
        known = found.get("least")
        known = {name: value for name, value in (known if isinstance(known, dict) else {}).items() if name in tabs}
        return {**found, "least": {**known, tab: cells}}

    known = kept(state_dir).get("least")
    if not isinstance(known, dict) or known.get(tab) != cells:
        change(state_dir, needed)


def remember(state_dir, cells):
    """CELLS (the right column's, its frame's too) kept in FILE as WIDTH, whatever else it keeps staying, when it is a
    new width; whether it was."""
    if cells == chosen(state_dir):
        return False
    return change(state_dir, lambda found: {**found, WIDTH: cells})


def share(ratio):
    return min(SPLIT[1], max(SPLIT[0], ratio))


def arrange(tab, right=None):
    """TAB's columns set so the right column takes RIGHT of the width (None: as it is), within herdr's shares. Whether
    anything was set."""
    ratio = share(1 - (tab.right if right is None else right))
    if abs(ratio - tab.left) <= TOLERANCE:
        return False
    try:
        call("layout.set_split_ratio", {"tab_id": tab.tab, "path": tab.outer, "ratio": round(ratio, 4)})
    except OSError:
        return False
    return True


def read(pane):
    """PANE's tab's columns, with their width in cells when herdr tells it; or None (no herdr, the agent zoomed, no
    right column)."""
    found = layout(pane)
    tab = columns(found) if found else None
    if tab is None:
        return None
    try:
        shown = {p["pane_id"]: p["rect"] for p in call("pane.layout", {"pane_id": pane}).get("layout", {})["panes"]}
        rects = [shown[name] for name in panes(at(found["root"], tab.outer))]
        tab.cells = max(r["x"] + r["width"] for r in rects) - min(r["x"] for r in rects)
        tab.widths = {name: rect["width"] for name, rect in shown.items()}
    except (OSError, KeyError, TypeError, ValueError):
        pass
    return tab


def copy(source, target):
    """TARGET's tab's columns as wide as SOURCE's, to the cell (a new preview tab's, before anything in it starts);
    whether anything was set."""
    mine, theirs = read(source), read(target)
    return bool(mine and theirs) and arrange(theirs, right=mine.right)


def cells(tab):
    """TAB's (left, right column) in cells."""
    right = round(tab.right * tab.cells)
    return tab.cells - right, right


def settled(pane):
    """PANE's tab's columns once they stay put for SETTLE seconds (a width set in two steps is between them for a
    moment), or None (still moving, or not to be read)."""
    first = read(pane)
    time.sleep(SETTLE)
    second = read(pane)
    if not first or not second or not first.cells or (first.cells, cells(first)) != (second.cells, cells(second)):
        return None
    return second


def rested(pane, tab, seconds, wait=time.sleep):
    """Whether PANE's tab's columns are TAB's still after SECONDS more: a drag let go there, not a pause on its way."""
    wait(seconds)
    later = read(pane)
    return bool(later) and (later.cells, cells(later)) == (tab.cells, cells(tab))


def sidebars():
    """{tab: its sidebar's pane} of every tab with one; none without herdr."""
    try:
        panes = call("pane.list", {}).get("panes") or []
    except OSError:
        return {}
    return {p["tab_id"]: p["pane_id"] for p in panes if p.get("label") == SIDEBAR}


def others(pane):
    """Every other tab's columns than that of PANE, its sidebar: a tab with a sidebar."""
    return [tab for tab in (read(other) for other in sidebars().values() if other != pane) if tab]


def hidden(pane):
    """Whether PANE's tab has its agent zoomed, its right column off screen."""
    try:
        return bool((call("layout.export", {"pane_id": pane}).get("layout") or {}).get("zoomed"))
    except OSError:
        return False


def owe(state_dir, done, skipped, alive=None):
    """FILE's "owed": the sidebars whose tab the dock's fold left as it was (its agent zoomed: SKIPPED), each to set
    its own once shown again; the ones set now (DONE) off it, and with ALIVE (every sidebar there is) the gone ones."""
    def owed(found):
        before = found.get("owed") if isinstance(found.get("owed"), list) else []
        left = {pane for pane in before if pane not in done and (alive is None or pane in alive)}
        return {**found, "owed": sorted(left | set(skipped))}

    found = kept(state_dir)
    if owed(found)["owed"] != (found.get("owed") or []):
        change(state_dir, owed)


def railed(state_dir):
    """Whether the dock is folded to its rail, in every tab (FILE's "rail", beside the width it opens to)."""
    return kept(state_dir).get("rail") is True


def width(state_dir, tab, rail=False):
    """TAB's right column's share (TAB.cells known): room()'s cells; on the RAIL, RAIL cells inside the frame, or the
    tenth of the tab herdr keeps at least (SPLIT) where that is more, a cell more where that would be even: each icon
    on the rail's very middle."""
    if not rail:
        return room(state_dir, tab) / tab.cells
    agent = min(tab.cells - RAIL - FRAME, int(tab.cells * SPLIT[1] + 0.5))     # herdr's round(width x ratio)
    agent -= (tab.cells - agent - FRAME + 1) % 2
    return (tab.cells - agent) / tab.cells


def frame(tab, pane, inside):
    """herdr's frame round PANE (INSIDE cells inside it), in cells: its width in TAB less INSIDE."""
    around = (tab.widths or {}).get(pane, 0) - inside
    return around if 0 <= around <= 4 else FRAME


def drag(state_dir, pane, inside, here=None):
    """PANE's right column (INSIDE cells inside its frame; HERE: its tab's columns, settled) was dragged: kept at least
    least() wide and at most most(), its cells remembered and set in every other tab; as wide as chosen, or at its own
    least for a narrower one (another tab's drag set it so), nothing new. How many were set."""
    here = here or settled(pane)
    if not here:
        return 0
    right = cells(here)[1]
    narrowest = least(state_dir, here.tab) + frame(here, pane, inside)
    if not narrowest <= right <= most(here.cells):
        right = max(narrowest, min(right, most(here.cells)))
        arrange(here, right=right / here.cells)
    kept = chosen(state_dir)
    if not LIMITS[0] <= 1 - right / here.cells <= LIMITS[1] or kept is not None and right == max(kept, narrowest):
        return 0
    return spread(state_dir, pane, right)


def spread(state_dir, pane, right):
    """RIGHT (the right column's cells) remembered and every other tab set to it, its right column never narrower than
    its own sidebar takes; how many were set."""
    if not remember(state_dir, right):
        return 0
    moved = 0
    for tab in others(pane):
        if tab.cells:
            moved += arrange(tab, right=max(right, least(state_dir, tab.tab) + FRAME) / tab.cells)
    return moved
