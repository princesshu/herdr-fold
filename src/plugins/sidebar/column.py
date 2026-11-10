"""The columns' widths, the same in every tab: a column dragged in one tab sets every other tab's. A tab splits as
agent | (Conversations | right column), so herdr's smallest share (a tenth) lets Conversations narrow to a rail. Set
through herdr's socket API (its command line cannot set a split), to the cell: a first side is round(width x ratio)."""
import json
import os
import socket
import time
from dataclasses import dataclass

import statefile

FILE = "column.json"
SIDEBAR, CONVERSATIONS = "sidebar", "conversations"          # the panes' names
RIGHT = 0.75                # the share before the right column until it is dragged
TOLERANCE = 0.002           # shares this close are the same width (a cell is about 0.007 of a wide window)
LIMITS = (0.3, 0.9)         # a remembered share: outside this nobody chose it (a tab too small, or a stray value)
SPLIT = (0.1, 0.9)          # the shares herdr lets a split have
SETTLE = 0.2                # seconds a tab's widths stay put before a pane takes them as chosen
NARROWEST = 29              # the right column's cells inside herdr's frame: the widest group's head and the ⋯
FEWEST = 23                 # the same without Issues: what a tab's sidebar takes at least
FRAME = 2                   # herdr's frame round a pane, in cells, where it is not measured


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
        raise OSError(str(answer.get("error") if isinstance(answer, dict) else answer) or "herdr refused")
    return answer["result"]


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
    """A tab's columns: the paths of the split before them (OUTER) and of the one between the Conversations column and
    the right column (INNER, None without it there); the shares of OUTER's width before them, the Conversations
    column's and the right column's; OUTER's width in cells (0: not known), and each pane's (WIDTHS, frame and all)."""
    tab: str
    outer: list
    inner: list
    left: float
    conversations: float
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


def columns(found):
    """The columns in FOUND (a tab's layout.export), or None when it has no right column: the innermost split to the
    right whose second side holds the sidebar, past one whose first side is the Conversations column."""
    root = found.get("root") or {}
    path = find(root, SIDEBAR)
    if path is None:
        return None
    inner = None
    for depth in range(len(path) - 1, -1, -1):
        node = at(root, path[:depth])
        if node.get("direction") != "right" or not path[depth]:
            continue
        first = node.get("first") or {}
        if inner is None and first.get("type") == "pane" and first.get("label") == CONVERSATIONS:
            inner = path[:depth]
            continue
        outer = float(node.get("ratio", 0))
        if inner is None:
            return Columns(found.get("tab_id"), path[:depth], None, outer, 0.0, 1 - outer)
        share = float(at(root, inner).get("ratio", 0))
        return Columns(found.get("tab_id"), path[:depth], inner, outer, (1 - outer) * share, (1 - outer) * (1 - share))
    return None


def layout(pane):
    """The tab's layout around PANE, or None (no herdr, or the agent zoomed: the column is not on screen)."""
    try:
        found = call("layout.export", {"pane_id": pane}).get("layout") or {}
    except OSError:
        return None
    return None if found.get("zoomed") else found


def saved(state_dir, file=FILE):
    """The share remembered on this machine, or None."""
    try:
        with open(os.path.join(state_dir, file), encoding="utf-8") as f:
            ratio = json.load(f).get("ratio")
    except (OSError, ValueError, AttributeError):
        return None
    return float(ratio) if isinstance(ratio, (int, float)) and LIMITS[0] <= ratio <= LIMITS[1] else None


def kept(state_dir, file=FILE):
    try:
        with open(os.path.join(state_dir, file), encoding="utf-8") as f:
            found = json.load(f)
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def keep(state_dir, values, file=FILE):
    """VALUES kept in FILE, whatever else it keeps staying; whether they were."""
    try:
        statefile.write(os.path.join(state_dir, file), {**kept(state_dir, file), **values})
    except OSError:
        return False
    return True


def least(state_dir, tab):
    """The right column's fewest cells inside herdr's frame in TAB: what its sidebar's buttons take (need()), or FEWEST
    until it has said (a sidebar with more widens its tab itself, at once)."""
    cells = (kept(state_dir).get("least") or {}).get(tab)
    return cells if isinstance(cells, int) and 0 < cells <= NARROWEST else FEWEST


def need(state_dir, tab, cells, tabs):
    """TAB's sidebar's buttons take CELLS: kept, for the TABS there are now only."""
    known = kept(state_dir).get("least")
    known = {name: value for name, value in (known if isinstance(known, dict) else {}).items() if name in tabs}
    if known.get(tab) != cells:
        keep(state_dir, {"least": {**known, tab: cells}})


def remember(state_dir, ratio, file=FILE):
    """RATIO kept in FILE (whatever else it keeps stays) when somebody chose it and it is a new one; whether it was."""
    if not LIMITS[0] <= ratio <= LIMITS[1]:
        return False
    before = saved(state_dir, file)
    if before is not None and abs(before - ratio) <= TOLERANCE:
        return False
    return keep(state_dir, {"ratio": round(ratio, 4)}, file)


def share(ratio):
    return min(SPLIT[1], max(SPLIT[0], ratio))


def arrange(tab, right=None, conversations=None):
    """TAB's columns set so the right column takes RIGHT of the width and the Conversations column CONVERSATIONS (None:
    as they are), to the cell where TAB's width is known (the Conversations column as near as herdr's smallest share
    lets it). Whether anything was set."""
    right = tab.right if right is None else right
    conversations = tab.conversations if conversations is None else conversations
    if tab.inner is None:
        ratios = [(tab.outer, share(1 - right), tab.left)]
    elif tab.cells:
        whole = tab.cells
        right_cells, mine = round(right * whole), max(1, round(conversations * whole))
        while mine / (mine + right_cells) < SPLIT[0]:       # herdr's smallest share: the column a cell wider
            mine += 1
        if (right_cells, mine) == (round(tab.right * whole), round(tab.conversations * whole)):
            return False
        ratios = [(tab.outer, share((whole - right_cells - mine) / whole), tab.left),
                  (tab.inner, mine / (mine + right_cells), tab.conversations / (tab.conversations + tab.right))]
    else:
        inner = share(conversations / max(conversations + right, 0.001))
        ratios = [(tab.outer, share(1 - right / (1 - inner)), tab.left),
                  (tab.inner, inner, tab.conversations / max(tab.conversations + tab.right, 0.001))]
    changed = False
    for path, ratio, now in ratios:
        if abs(ratio - now) > TOLERANCE:
            try:
                call("layout.set_split_ratio", {"tab_id": tab.tab, "path": path, "ratio": round(ratio, 4)})
            except OSError:
                return changed
            changed = True
    return changed


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
    if not mine or not theirs or (mine.inner is None) != (theirs.inner is None):
        return False
    return arrange(theirs, right=mine.right, conversations=mine.conversations)


def cells(tab):
    """TAB's (left, Conversations column, right column) in cells."""
    right, mine = round(tab.right * tab.cells), round(tab.conversations * tab.cells)
    return tab.cells - right - mine, mine, right


def visible(tab):
    """Whether TAB is the tab on screen: only there can a border be dragged."""
    try:
        return (call("pane.current", {}).get("pane") or {}).get("tab_id") == tab.tab
    except OSError:
        return False


def settled(pane):
    """PANE's tab's columns once they stay put for SETTLE seconds (a width set in two steps is between them for a
    moment), or None (still moving, or not to be read)."""
    first = read(pane)
    time.sleep(SETTLE)
    second = read(pane)
    if not first or not second or not first.cells or (first.cells, cells(first)) != (second.cells, cells(second)):
        return None
    return second


def others(pane):
    """Every other tab's columns: a tab with a sidebar."""
    try:
        panes = call("pane.list", {}).get("panes") or []
    except OSError:
        return []
    sidebars = {p["tab_id"]: p["pane_id"] for p in panes if p.get("label") == SIDEBAR}
    here = next((p["tab_id"] for p in panes if p.get("pane_id") == pane), None)
    return [tab for tab in (read(other) for name, other in sidebars.items() if name != here) if tab]


def frame(tab, pane, inside):
    """herdr's frame round PANE (INSIDE cells inside it), in cells: its width in TAB less INSIDE."""
    around = (tab.widths or {}).get(pane, 0) - inside
    return around if 0 <= around <= 4 else FRAME


def drag(state_dir, pane, inside):
    """PANE's right column (INSIDE cells inside its frame) was resized in a tab without the Conversations column (whose
    pane sees to the widths otherwise): kept at least least() wide, its share remembered to the cell and set in every
    other tab. How many were set."""
    here = settled(pane)
    if not here or here.inner is not None:
        return 0
    right = cells(here)[2]
    narrowest = least(state_dir, here.tab) + frame(here, pane, inside)
    if right < narrowest:
        right = narrowest
        arrange(here, right=right / here.cells)
    before = saved(state_dir)
    if before is not None and round((1 - before) * here.cells) == right:
        return 0
    return spread(state_dir, pane, right=right / here.cells)


def spread(state_dir, pane, right=None, agent=None, file=None):
    """RIGHT (the right column's share) and AGENT (the agent's share of what is before the right column, kept in FILE)
    remembered, where given, and every other tab set to them, its right column never narrower than its own buttons
    take; how many were set."""
    if right is not None and not remember(state_dir, 1 - right):
        right = None
    if agent is not None and not remember(state_dir, agent, file):
        agent = None
    if right is None and agent is None:
        return 0
    moved = 0
    for tab in others(pane):
        width = right if right is not None else tab.right
        if tab.cells:
            width = max(width, (least(state_dir, tab.tab) + FRAME) / tab.cells)
        if agent is None or tab.inner is None:
            moved += arrange(tab, right=width)
        else:
            space = tab.cells - round(width * tab.cells) if tab.cells else 0
            mine = round((1 - agent) * space) / tab.cells if tab.cells else (1 - agent) * (1 - width)
            moved += arrange(tab, right=width, conversations=mine)
    return moved
