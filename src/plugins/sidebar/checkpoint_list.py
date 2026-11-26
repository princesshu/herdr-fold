"""A Claude chat's checkpoints over the Chats list (a chat's Checkpoints…, or → on its row): its prompts, the newest
first, those whose turn wrote files Claude still keeps with Restore files to here…, which asks Claude's dry run and
shows what changes and what stays first; after a restore one line says so, u undoes it. Actions go to Chats."""
from datetime import datetime

from screen import CONTENT, PLAIN, Style, truncate, width
from vt import Key, Mouse
from widgets import Action, ListView, wrap

TIME = 3                      # where a point's time starts, the back mark two cells before it
ROOM = 28                     # cells the chosen point's lines keep at least: in fewer they start under its time
FOOT = 3                      # rows of the foot's words at most
RUNNING = "Claude runs in its pane: Esc Esc there rewinds files and chat in place"
ASK = "Restore files to here…"
HINT = "Enter restores files · ← back to Chats"
NONE = "Nothing to restore · ← back to Chats"


def counted(n, one):
    return f"{n} {one}{'' if n == 1 else 's'}"


def restorable(point):
    """Whether POINT can take the chat's files back: Claude still keeps it, and its turn wrote a file."""
    return bool(point.get("kept")) and point.get("files", 0) > 0


def stays(point):
    """What a restore to POINT leaves as it is, a line each: what Bash and subagents changed from it on (Claude's
    checkpoints cover its file tools alone), edits made outside Claude, and the chat itself."""
    return [line for line in (f"what {counted(point['bash'], 'Bash command')} changed" if point.get("bash") else "",
                              f"what {counted(point['agents'], 'subagent')} changed" if point.get("agents") else "",
                              "edits made outside Claude", "this chat: Claude keeps the later turns") if line]


def shown_path(path, folder, cells):
    """PATH from the chat's FOLDER (whole outside it) in CELLS: a longer one keeps its end, the file's name."""
    top = folder.rstrip("/") + "/"
    path = path[len(top):] if path.startswith(top) else path
    return path if width(path) <= cells else "…" + path[len(path) - max(0, cells - 1):]


def wrapped(kind, words, cells):
    """WORDS as lines of KIND, wrapped at CELLS."""
    return [(kind, words[start:end].strip()) for start, end in wrap(words, cells)]


def clock(at, twelve):
    """AT (an ISO time) as this machine's time of day, 1:36 PM or 13:36 (TWELVE: with AM and PM); "" for none."""
    try:
        when = datetime.fromisoformat(str(at).replace("Z", "+00:00")).astimezone()
    except ValueError:
        return ""
    return f"{when.hour % 12 or 12}:{when.minute:02d} {'AM' if when.hour < 12 else 'PM'}" if twelve \
        else f"{when.hour:02d}:{when.minute:02d}"


class CheckpointList:
    def __init__(self, item, twelve=False):
        self.item, self.twelve = item, twelve           # the chat (chats.Chat), its machine's hours
        self.points = None                              # core's points, newest first; None while read
        self.undo = None                                # the restore that can be undone (core's undoable)
        self.asked = None                               # the chosen point's dry run: "asking", core's answer, or None
        self.busy = False                               # a restore or an Undo under way
        self.told = None                                # (words, error) of what was just done
        self.list = ListView()
        self.canvas, self.top, self.height = None, 0, 0

    def set(self, found):
        """FOUND (core's listed()): the points, newest first, the chosen one kept chosen."""
        chosen = self.chosen()
        self.points = list(reversed(found["points"]))
        self.undo = found["undo"]
        self.list.set(self.points)
        ids = [point["id"] for point in self.points]
        if chosen and chosen["id"] in ids:
            self.list.index = ids.index(chosen["id"])
        elif chosen is None:
            self.list.index = next((i for i, point in enumerate(self.points) if restorable(point)), 0)
        self.list.keep_visible()

    def chosen(self):
        return self.list.selected()

    def at(self, point_id):
        """The time of the point POINT_ID, as its row shows it."""
        point = next((one for one in self.points or () if one["id"] == point_id), None)
        return clock(point["at"], self.twelve) if point else ""

    def restored_words(self, files, point_id):
        return f"Restored {counted(files, 'file')} to before {self.at(point_id)}"

    # --- what the chosen point shows under its row

    def detail(self, cells):
        """The chosen point's lines under its row, CELLS wide: Restore files to here…, then what Claude's dry run
        says (the files and the lines in all, what stays as it is, the restore); each (kind, words)."""
        point, room = self.chosen(), max(1, cells - self.inset(cells) - 1)
        if not point or not restorable(point):
            return []
        if self.asked is None:
            return [("ask", ASK)]
        if self.asked == "asking":
            return wrapped("muted", "Asking Claude which files would change…", room)
        if "error" in self.asked:
            return wrapped("error", self.asked["error"], room) + [("dim", "Esc cancels")]
        files = self.asked["files"]
        lines = wrapped("muted", "Files as they were before this message", room)
        lines += [("file", shown_path(path, self.item.folder, room)) for path in files]
        lines += [("sum", (counted(len(files), "file"), self.asked["insertions"], self.asked["deletions"])),
                  ("gap", ""), ("muted", "Stays as it is")]
        lines += [one for line in stays(point) for one in wrapped("muted", line, room)]
        label = "Restoring…" if self.busy else f"Restore {counted(len(files), 'file')}"
        return lines + [("gap", ""), ("restore", label)]

    @staticmethod
    def fit(lines, rows):
        """LINES (detail()'s) in ROWS at most: the gaps go first, then the files past those that fit (a line says how
        many more), then what is over the restore's line, which always stays."""
        if len(lines) <= rows:
            return lines
        lines = [line for line in lines if line[0] != "gap"]
        files = [n for n, line in enumerate(lines) if line[0] == "file"]
        if len(lines) > rows and len(files) > 1:
            keep = max(1, len(files) - (len(lines) - rows) - 1)
            lines = lines[:files[0] + keep] + [("muted", f"and {len(files) - keep} more")] + lines[files[-1] + 1:]
        return lines if len(lines) <= rows else lines[:max(0, rows - 1)] + lines[-1:]

    def indent(self):
        """Where a point's words start: after its time."""
        return TIME + max([width(clock(point["at"], self.twelve)) for point in self.points or ()] or [5]) + 2

    def inset(self, cells):
        """Where the chosen point's lines start: under its words, or under its time where CELLS leave them too few."""
        return self.indent() if cells - self.indent() >= ROOM else TIME

    # --- drawing

    def draw(self, canvas, top, height):
        """The view from row TOP, HEIGHT rows: the chat's name with the way back, a running Claude's own rewind, the
        points with the chosen one's lines, the foot."""
        self.canvas, self.top, self.height, cells = canvas, top, height, canvas.width
        for y in range(top, top + height):
            canvas.backdrop(y, 0, cells, "blank")
        name = "Claude"
        canvas.put(top, 1, "‹", Style(fg="muted"))
        canvas.region(top, 0, 3, "points:back")
        canvas.put(top, cells - 1 - width(name), name, Style(fg="muted"))
        canvas.put(top, TIME, truncate(self.item.title, max(1, cells - TIME - width(name) - 3)), Style(bold=True))
        y = top + 2
        if self.item.state:
            for start, end in wrap(RUNNING, max(1, cells - TIME - 1))[:2]:
                canvas.put(y, TIME, RUNNING[start:end].strip(), Style(fg="muted"))
                y += 1
            y += 1
        feet = self.foot_lines(cells)
        foot = top + height - len(feet)
        if self.points is None:
            canvas.put(y, TIME, "Reading the chat…", Style(fg="muted"))
        elif not self.points:
            canvas.put(y, TIME, "No prompt in this chat yet", Style(fg="muted"))
        else:
            rows = max(1, foot - 1 - y)          # a row of air over the foot
            detail = self.fit(self.detail(cells), rows - 1)
            if self.list.height != rows - len(detail):
                self.list.resize(rows - len(detail))
            for row in range(self.list.height):
                index = self.list.at(row)
                if index is None:
                    break
                self.draw_point(canvas, y, index)
                y += 1
                for kind, words in detail if index == self.list.index else ():
                    self.draw_detail(canvas, y, kind, words)
                    y += 1
        self.draw_foot(canvas, foot, feet)

    def draw_point(self, canvas, y, index):
        """A point: its time, its prompt's first line, how many files its turn wrote where it can restore them; the
        chosen one on its highlight, a cell inside it at its end (CONTENT)."""
        point, cells = self.points[index], canvas.width
        chosen = index == self.list.index
        bg = "selection" if chosen else None
        if bg:
            canvas.band(y, bg)
        canvas.region(y, 0, cells, ("point", index))
        count = f"wrote {counted(point['files'], 'file')}" if restorable(point) else ""    # its turn's; Ask: since
        canvas.put(y, cells - CONTENT - width(count), count, Style(fg="muted_row" if bg else "muted", bg=bg))
        canvas.put(y, TIME, clock(point["at"], self.twelve), Style(fg="text" if chosen else "subtext", bg=bg))
        room = max(1, cells - CONTENT - self.indent() - (width(count) + 2 if count else 0))
        canvas.put(y, self.indent(), truncate(point["text"], room), Style(fg="text" if chosen else "subtext", bg=bg,
                                                                        bold=chosen))

    def draw_detail(self, canvas, y, kind, words):
        cells = canvas.width
        x = self.inset(cells)
        room = max(1, cells - x - 1)
        if kind in ("ask", "restore"):                  # the one button at the row's right end, Esc cancels left of it
            label = f" {truncate(words, room - 2)} "
            start = max(x, cells - 1 - width(label))
            if kind == "restore" and x + width("Esc cancels") + 2 <= start:
                canvas.put(y, x, "Esc cancels", Style(fg="guide"))
            look = (Style(fg="button_text", bg="button", bold=True) if kind == "restore"
                    else Style(fg="text", bg="input"))
            canvas.region(y, start, canvas.put(y, start, label, look), f"points:{kind}")
        elif kind == "sum":
            files, plus, minus = words
            end = canvas.put(y, x, f"{files} · ", Style(fg="muted"))
            end = canvas.put(y, end, f"+{plus}", Style(fg="added"))
            canvas.put(y, end + 1, f"−{minus}", Style(fg="deleted"))
        elif kind != "gap":
            look = {"error": Style(fg="deleted"), "dim": Style(fg="guide"), "file": PLAIN}.get(kind, Style(fg="muted"))
            canvas.put(y, x, truncate(words, room), look)

    def foot_words(self):
        """The foot's line: what was just done (with u Undo while it can be undone), else the keys."""
        if self.told:
            return self.told[0], self.told[1], bool(self.undo) and not self.told[1]
        if self.undo:
            return self.restored_words(self.undo["files"], self.undo["point"]), False, True
        return (HINT if any(restorable(point) for point in self.points or ()) else NONE), False, False

    def foot_lines(self, cells):
        """The foot's words wrapped in CELLS, room left on the last for u Undo; FOOT rows at most."""
        words, _error, undo = self.foot_words()
        lines = [words[start:end].strip() for start, end in wrap(words, max(1, cells - 2))]
        if undo and width(lines[-1]) + 2 + width("u Undo") > cells - 2:
            lines.append("")
        return lines[:FOOT]

    def draw_foot(self, canvas, y, lines):
        _words, error, undo = self.foot_words()
        cells = canvas.width
        for n, line in enumerate(lines):
            canvas.put(y + n, 1, truncate(line, max(1, cells - 2)), Style(fg="deleted" if error else "muted"))
        if undo:
            last = y + len(lines) - 1
            canvas.put(last, cells - 1 - width("u Undo"), "u", Style(bold=True))
            canvas.put(last, cells - 1 - width("Undo"), "Undo", Style(fg="muted"))
            canvas.region(last, cells - 1 - width("u Undo"), cells - 1, "points:undo")

    # --- keys and the mouse

    def handle(self, event):
        """EVENT: an Action for Chats, "back" to the list, or None."""
        if isinstance(event, Mouse):
            return self.mouse(event)
        if not isinstance(event, Key) or self.busy:
            return None
        name = event.char if event.name == "char" and not (event.ctrl or event.alt) else event.name
        if name in ("up", "down", "pageup", "pagedown", "home", "end"):
            self.asked = None
            if name in ("up", "down"):
                self.list.move(1 if name == "down" else -1)
            elif name in ("pageup", "pagedown"):
                self.list.page(1 if name == "pagedown" else -1)
            else:
                self.list.move(len(self.list.items) * (1 if name == "end" else -1))
        elif name == "enter":
            return self.press()
        elif name == "esc":
            if self.asked is None:
                return "back"
            self.asked = None
        elif name == "left":
            return "back"
        elif name == "u" and self.foot_words()[2]:
            return self.undone()
        return None

    def press(self):
        """Enter, or a click on the chosen point's button: its dry run asked, or with its answer in the restore."""
        point = self.chosen()
        if not point or not restorable(point) or self.asked == "asking" or self.busy:
            return None
        if self.asked is None or "error" in self.asked:
            self.asked = "asking"
            return Action("checkpoint_ask", (self.item, point))
        self.busy = True
        return Action("checkpoint_restore", (self.item, point, self.points[0]["id"]))

    def undone(self):
        self.busy = True
        return Action("checkpoint_undo", (self.item,))

    def mouse(self, event):
        target = self.canvas.hit(event.x, event.y) if self.canvas else None
        if event.kind in ("wheel_up", "wheel_down"):
            self.list.scroll(3 if event.kind == "wheel_down" else -3)
        elif event.kind == "press" and event.button == 0 and not self.busy:
            if target == "points:back":
                return "back"
            if target in ("points:ask", "points:restore"):
                return self.press()
            if target == "points:undo":
                return self.undone()
            if isinstance(target, tuple) and target[0] == "point" and target[1] != self.list.index:
                self.list.index, self.asked = target[1], None
        return None
