"""herdr-fold's Settings in herdr's popup (the sidebar's More: Settings…), as settings.html's TUI box: its sections in a
list (↑ ↓). General: the sidebar's icons (settings.json's `icons`). Notifications: herdr's own toast for an agent that
waits (its config.toml, reloaded). About: the version, license, update check and its switch, the notices. Esc closes."""
import json
import os
import re
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import herdr_toml  # noqa: E402
import media  # noqa: E402
import panels  # noqa: E402
import panes  # noqa: E402
import preview  # noqa: E402
import statefile  # noqa: E402
import update  # noqa: E402
from icons import glyphs  # noqa: E402
from loop import Loop  # noqa: E402
from screen import SPIN, SPINNER, Canvas, Style, icons_on, truncate  # noqa: E402
from vt import Focus, Key, Mouse  # noqa: E402

LICENSE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "LICENSE")     # the plugin's own: a fork's its own
COPYRIGHT = re.compile(r"Copyright \(c\) (\S+) (.+?)(?: \((https://\S+)\))?")
SWITCH = "Check for updates automatically"
NOTICES = "Third-party notices"
# the list at the left, from the row under the close button
SECTIONS = {"general": "General", "notifications": "Notifications", "about": "About"}
LIST, ROOM = 15, 45           # the list's cells (a cell of air before a name); the rule, a cell of air; the section's
INSET = LIST + 2              # the section's first column
ICONS = {True: "Nerd Font", False: "Plain marks"}       # General's one setting: the option in use is the lit one
ICONS_NOTE = ("Plain marks where the terminal's font has no", "Nerd Font icons; ", "i", " in Files switches it too.")
WAITS = "An agent waits on you"         # Notifications' one setting: herdr's [ui.toast] delivery, "herdr" or "off"
WAITS_ON = {True: "on", False: "off"}
WAITS_NOTE = ("herdr's note at the bottom right,", "once per agent")
TOAST = ("ui.toast", "delivery")
CLOSE, NAME, LEGAL, STATE, HOW, BOX, LINK, BUTTONS = 0, 1, 2, 4, 5, 7, 9, 11    # each one's row, in every state
CHOICES = ("first", "check", "author", "notices")   # Tab's way: What's new (or the notes), Check now, then the links
RIGHT = 0                     # the right inset: herdr's popup keeps a blank column of its own inside its right edge
CLOSE_CELLS, CLOSE_TIP, TIP_DELAY = 3, "Close (Esc)", 0.5     # air, the glyph, air; its tip, after the sidebar's wait


def legal():
    """The LICENSE's words for About's second row: (its year, its author, the author's page or None, its name), or
    None when it cannot be read."""
    try:
        with open(LICENSE, encoding="utf-8") as f:
            lines = [line.strip() for line in f]
    except OSError:
        return None
    found = next((COPYRIGHT.fullmatch(line) for line in lines if COPYRIGHT.fullmatch(line)), None)
    kind = next((line for line in lines if line), "")
    return (*found.groups(), kind) if found and kind else None


def when(seconds, now=None):
    """A look's time as About says it: at 12:30 today, else on the day (Nov 12), in this Mac's zone."""
    shown, today = time.localtime(seconds), time.localtime(now)
    if shown[:3] == today[:3]:
        return f"at {time.strftime('%H:%M', shown)}"
    return f"on {time.strftime('%b', shown)} {shown.tm_mday}"


def newer_out():
    """Whether a newer herdr-fold is out, as update.json knew it last (nothing asked): More's dot then, which leads
    to About."""
    try:
        return update.newer(update.kept().get("latest"), update.installed())
    except (OSError, ValueError):
        return False


class Settings(Loop):
    def __init__(self, terminal, herdr, state_dir, clock=time.monotonic, context=None):
        super().__init__(terminal, herdr, state_dir, clock)
        self.context = context or {}      # where it was opened: herdr's workspace, tab, pane and folder then
        self.found = None                 # update.check()'s last answer
        self.asked = 0                    # the looks asked for: an answer to an earlier one than the last is old
        self.checking = None              # when the last look started, while it runs: the spinner's first frame
        self.on = None                    # the switch as last pressed, until the look after it answers
        self.legal = legal()
        self.section = "about" if newer_out() else "general"
        self.icons = icons_on(state_dir)  # the sidebar's icons, as its settings.json has them
        self.waits = self.toast() != "off"     # herdr's toast for an agent that waits: on unless its file says off
        self.chosen = "first"             # About's control Tab is on
        self.pointed = None
        self.over, self.tip = None, False      # since when the mouse rests on the close button; its tip drawn
        self.look()

    # --- the update check

    def look(self, now=False, switch=None):
        """update.check() on a thread (NOW: Check now, asking GitHub at once; SWITCH: the automatic check turned on or
        off first); the spinner until its answer, a failure Couldn't check, as GitHub not answering is."""
        self.asked += 1
        self.checking = self.clock()

        def work():
            try:
                if switch is not None:
                    update.switch(switch)
                return update.check(force=now)
            except Exception:                     # any failure is a look that did not answer: never a spinner left
                return None

        self.job("look", work, lambda found, n=self.asked: self.looked(found, n))

    def looked(self, found, n):
        if n != self.asked:
            return
        self.checking, self.on = None, None
        self.found = found or {**(self.found or {}), "error": update.FAILED}

    def switched(self):
        """The box's state: as last pressed, until the look after it answers."""
        return self.on if self.on is not None else bool((self.found or {}).get("on", True))

    # --- what it does

    def handle(self, event):
        if isinstance(event, Focus):
            self.quit = self.quit or not event.gained    # a click outside: the pane clicked has the keys now
        elif isinstance(event, Key):
            self.key(event)
        elif isinstance(event, Mouse):
            target = self.canvas.hit(event.x, event.y) if self.canvas else None
            if event.kind == "move":
                if (target == "close") != (self.pointed == "close"):
                    self.over, self.tip = (self.clock() if target == "close" else None), False
                self.pointed = target
            elif event.kind == "press" and event.button == 0 and target:
                self.press(target)

    def key(self, key):
        if key.name == "esc" or (key.name == "char" and (key.char == "q" or key.ctrl and key.char == "c")):
            self.quit = True
        elif key.name in ("up", "down"):                  # the list's ends hold: two keys, two ways
            names = list(SECTIONS)
            at = names.index(self.section) + (1 if key.name == "down" else -1)
            self.section = names[max(0, min(len(names) - 1, at))]
        elif self.section in ("general", "notifications"):
            if key.name in ("tab", "right", "backtab", "left"):       # two options: a step is the other one
                self.set_icons(not self.icons) if self.section == "general" else self.set_waits(not self.waits)
        elif key.name == "char" and key.char == " ":
            self.press("box")
        elif key.name in ("tab", "right", "backtab", "left"):
            step = -1 if key.name in ("backtab", "left") else 1
            shown = [one for one in CHOICES if one in self.choices()]
            self.chosen = shown[(shown.index(self.chosen) + step) % len(shown) if self.chosen in shown else 0]
        elif key.name == "enter":
            self.press(self.chosen)

    def set_icons(self, on):
        """The sidebar's icons ON or plain marks, in its settings.json beside what it holds (every tab's sidebar takes
        it at its next poll); as it was when that cannot be written."""
        try:
            statefile.update(os.path.join(self.state_dir, "settings.json"), lambda kept: {**kept, "icons": on},
                             indent=2)
        except OSError:
            return
        self.icons = on

    @staticmethod
    def config():
        return os.path.join(os.path.expanduser("~"), ".config", "herdr", "config.toml")

    def toast(self):
        """herdr's toast delivery as its config.toml sets it, or None: not set, or a file not read for sure."""
        try:
            with open(self.config(), encoding="utf-8") as f:
                return herdr_toml.value(f.read(), *TOAST)
        except (OSError, ValueError):
            return None

    def set_waits(self, on):
        """herdr's toast ON ("herdr") or off in its config.toml (herdr_toml.py's put(): a line of the user's own),
        then herdr asked to read it again; as it was where the file is not one it changes for sure."""
        try:
            try:
                with open(self.config(), encoding="utf-8") as f:
                    theirs = f.read()
            except FileNotFoundError:
                theirs = ""
            made = herdr_toml.put(theirs, *TOAST, '"herdr"' if on else '"off"')
            if made is None:
                return
            os.makedirs(os.path.dirname(self.config()), exist_ok=True)
            with open(self.config(), "w", encoding="utf-8") as f:     # into the file itself: a link stays a link
                f.write(made)
        except (OSError, ValueError):
            return
        self.waits = on

        def work():
            try:
                self.herdr.call("server", "reload-config")
            except RuntimeError:                  # no server to tell: herdr reads its file when it starts
                pass

        self.job("reload", work)

    def choices(self):
        """What Tab reaches: the buttons with an install here, the author's page where the LICENSE names it, the
        notices."""
        buttons = ["first", "check"] if (self.found or {}).get("version") else []
        return buttons + (["author"] if self.legal and self.legal[2] else []) + ["notices"]

    def press(self, target):
        found = self.found or {}
        if target == "close":
            self.quit = True
        elif isinstance(target, tuple) and target[0] == "section":
            self.section = target[1]
        elif isinstance(target, tuple) and target[0] == "icons":
            if target[1] != self.icons:
                self.set_icons(target[1])
        elif isinstance(target, tuple) and target[0] == "waits":
            if target[1] != self.waits:
                self.set_waits(target[1])
        elif target == "author" and self.legal and self.legal[2]:
            media.open_in_browser(self.legal[2])
            self.quit = True
        elif target == "box" and found.get("version"):
            self.on = not self.switched()
            self.look(switch=self.on)
        elif target == "check" and found.get("version"):
            self.look(now=True)
        elif target == "first" and found.get("newer"):
            media.open_in_browser(found["releases"])
            self.quit = True
        elif target == "first" and found.get("version"):
            self.open(update.changelog(), update.section(found["version"]))
        elif target == "notices":
            self.open(os.path.join(os.path.dirname(update.changelog()), "THIRD_PARTY_NOTICES.md"))

    def open(self, path, line=None):
        """PATH at LINE in the preview tab of the workspace it was opened from (a new one laid out as the tab it was
        opened in), then out of the way."""
        place, workspace, tab = (self.context.get(key) for key in ("workspace_cwd", "workspace_id", "tab_id"))
        place = place or os.path.expanduser("~")
        spec = {**preview.file_spec(place, path, line), "title": os.path.basename(path)}

        def lay_out(made):
            kinds = panels.present(self.herdr.call("pane", "list").get("panes") or []).get(tab)
            panes.bring(self.herdr.call, made, kinds or set(panels.KINDS), self.state_dir)

        def work():
            if workspace:
                preview.open_preview(self.herdr, workspace, place, spec, self.state_dir, lay_out, tab)

        self.job("open", work, lambda _: setattr(self, "quit", True))

    # --- the loop's

    def tick(self):
        """The spinner's next frame, the close button's tip come due."""
        due = self.over is not None and not self.tip and self.clock() >= self.over + TIP_DELAY
        self.tip = self.tip or due
        return self.checking is not None or due

    def deadlines(self):
        tip = [self.over + TIP_DELAY] if self.over is not None and not self.tip else []
        return tip + ([self.clock() + SPIN] if self.checking is not None else [self.clock() + 3600])

    # --- drawing

    def draw(self):
        cells, rows = self.term.size()
        canvas, corner = Canvas(cells, rows), cells - RIGHT - CLOSE_CELLS
        lit = self.pointed == "close"                 # as the row's icons alone: the hover color, the glyph lit
        close = glyphs(self.icons)["close"]           # Codicons' close, or × with the icons off
        canvas.put(CLOSE, corner, f" {close} ", Style(fg="text" if lit else "subtext", bg="hover" if lit else None))
        canvas.region(CLOSE, corner, corner + CLOSE_CELLS, "close")
        self.draw_list(canvas)
        if self.section == "general":
            self.draw_options(canvas, "Icons", "icons", ICONS, self.icons)
            self.draw_icons_note(canvas)
        elif self.section == "notifications":
            self.draw_options(canvas, WAITS, "waits", WAITS_ON, self.waits)
            for y, words in zip((STATE, HOW), WAITS_NOTE):
                canvas.put(y, INSET, words, Style(fg="muted"))
        else:
            self.draw_about(canvas, self.found or {})
        if self.tip:                                  # under the button at its right edge, as the sidebar's tips
            words = f" {CLOSE_TIP} "
            canvas.put(NAME, corner + CLOSE_CELLS - len(words), words, Style(fg="text", bg="selection"))
        self.canvas = canvas
        self.term.write(self.renderer.frame(canvas))
        self.term.flush()

    def draw_list(self, canvas):
        """The sections, a row each from the popup's side to the rule: the chosen one on the selection's background,
        the one under the mouse on the hover's; the rule down every row."""
        for y, (name, words) in enumerate(SECTIONS.items(), NAME):
            target = ("section", name)
            if name == self.section:
                canvas.put(y, 0, f" {words}".ljust(LIST), Style(fg="text", bg="selection", bold=True))
            else:
                bg = "hover" if self.pointed == target else None
                canvas.put(y, 0, f" {words}".ljust(LIST), Style(fg="text" if bg else "subtext", bg=bg))
            canvas.region(y, 0, LIST, target)
        for y in range(canvas.height):
            canvas.put(y, LIST, "│", Style(fg="guide"))

    def draw_options(self, canvas, name, key, options, held):
        """A setting of two: its NAME, its OPTIONS side by side, a cell of air round each and one between them, the
        one HELD lit as a chosen button; a press on one is (KEY, the option)."""
        canvas.put(NAME, INSET, name, Style(fg="text"))
        x = INSET
        for on, words in options.items():
            target = (key, on)
            if on == held:
                style = Style(fg="button_text", bg="button", bold=True)
            else:
                style = Style(fg="text", bg="hover") if self.pointed == target else Style(fg="muted")
            end = canvas.put(LEGAL, x, f" {words} ", style)
            canvas.region(LEGAL, x, end, target)
            x = end + 1

    def draw_icons_note(self, canvas):
        """What Icons is for, under its options, the key that switches it too in the text's color."""
        first, before, key, after_ = ICONS_NOTE
        canvas.put(STATE, INSET, first, Style(fg="muted"))
        x = canvas.put(HOW, INSET, before, Style(fg="muted"))
        x = canvas.put(HOW, x, key, Style(fg="text"))
        canvas.put(HOW, x, after_, Style(fg="muted"))

    def draw_about(self, canvas, found):
        """About's rows, each on its own in every state: nothing moves when the check's state changes."""
        room, version = ROOM, found.get("version")
        canvas.put(NAME, INSET, truncate(f"herdr-fold {version}" if version else "herdr-fold", room),
                   Style(fg="text", bold=True))
        self.draw_legal(canvas, room)
        self.draw_state(canvas, found)
        if version:
            x = canvas.put(BOX, INSET, "[")
            x = canvas.put(BOX, x, "✓" if self.switched() else " ", Style(fg="accent"))
            canvas.put(BOX, x, f"] {SWITCH}")
            canvas.region(BOX, INSET, INSET + 4 + len(SWITCH), "box")
        lit = self.chosen == "notices"
        end = canvas.put(LINK, INSET, NOTICES, Style(fg="accent" if lit or self.pointed == "notices" else "subtext",
                                                      underline=True))
        canvas.region(LINK, INSET, end, "notices")
        if version:
            first = "Release notes ↗" if found.get("newer") else "What's new"
            x = INSET
            for name, label in (("first", first), ("check", "Check now")):
                style = Style(fg="button_text", bg="button", bold=True) if self.chosen == name else Style(bg="input")
                end = canvas.put(BUTTONS, x, f" {label} ", style)
                canvas.region(BUTTONS, x, end, name)
                x = end + 1

    def draw_legal(self, canvas, room):
        """© its year, its author (a link to their page, as the notices), its license: the LICENSE's own words."""
        if not self.legal:
            return
        year, author, page, kind = self.legal
        lit = "accent" if "author" in (self.chosen, self.pointed) else "subtext"
        x = INSET
        for words, style in ((f"© {year} ", Style(fg="muted")),
                             (author, Style(fg=lit, underline=True) if page else Style(fg="muted")),
                             (f" · {kind}", Style(fg="muted"))):
            start, x = x, canvas.put(LEGAL, x, truncate(words, max(0, INSET + room - x)), style)
            if words == author and page:
                canvas.region(LEGAL, start, x, "author")

    def draw_state(self, canvas, found):
        """The check's state on its row (a newer one's how under it): looking, Couldn't check, a newer one out, up to
        date, checked by hand only, or no install here to check."""
        room, latest, checked = ROOM, found.get("latest"), found.get("checked")
        if not found.get("version") and self.checking is None:
            parts = [("Updated with the Mac that installed it", "subtext")]
        elif self.checking is not None or not found:
            frame = SPINNER[int(self.clock() / SPIN) % len(SPINNER)]
            parts = [(f"{frame} Checking for updates…", "muted")]
        elif found.get("error") and found.get("newer"):       # both in the section's cells: the how line whole
            parts = [("Couldn't check", "deleted"), (" · ", "muted"), (f"{latest} is out", "text")]
            canvas.put(HOW, INSET + 2, truncate(found["how"], room - 2), Style(fg="subtext"))
        elif found.get("error"):
            parts = [("Couldn't check", "deleted"),
                     (f" · last checked {when(checked)}" if checked else f" · {found['error']}", "muted")]
        elif found.get("newer"):
            parts = [("↑", "accent"), (f" {latest} is out", "text"), (f" · checked {when(checked)}", "muted")]
            canvas.put(HOW, INSET + 2, truncate(found["how"], room - 2), Style(fg="subtext"))
        elif checked:
            parts = [("✓", "added"), (" Up to date", "text"), (f" · checked {when(checked)}", "muted")]
        else:
            parts = [("Checked by hand only", "subtext")]
        x = INSET
        for words, role in parts:
            x = canvas.put(STATE, x, truncate(words, max(0, INSET + room - x)), Style(fg=role))


def main():
    try:
        context = json.loads(os.environ.get("HERDR_PLUGIN_CONTEXT_JSON") or "{}")
    except ValueError:
        context = {}
    state = os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.join(
        os.path.expanduser("~"), ".local", "state", "herdr", "plugins", "herdr-fold.sidebar")
    if os.name == "nt":
        from keys_windows import WindowsTerminal as Terminal
    else:
        from keys_unix import UnixTerminal as Terminal
    Settings(Terminal(), preview.Herdr(), state, context=context if isinstance(context, dict) else {}).run()


if __name__ == "__main__":
    main()
