"""What the sidebar and the Conversations column share: the loop (draw only after a change, wait for the keys, a job's
answer or the next poll, act on them), background jobs whose answers wake it, a new theme taken at once, and a new
version of the plugin's own files (an update) handed over to in the same pane, where this one was."""
import json
import os
import queue
import threading
import time
import uuid

import column
import statefile
import watch
import widgets
from screen import Renderer
from theme import Theme

CODE = os.path.dirname(os.path.abspath(__file__))       # this plugin's files: an update puts new ones here
SETTLE = 2.0                  # seconds a new version must stay still (an update copies its files one by one)
# the handover to the new version: each pane's program its own file in the shared state folder, named by a token in
# this variable, which only its own new version inherits
RESUME_ENV = "HERDR_FOLD_SIDEBAR_RESUME"
STALE = 3600                  # seconds: a handover, a preview tab's seed or spec this old was left by a pane closed;
                              # a repository's issues this old are no one's answer any more


class Loop:
    def __init__(self, terminal, herdr, state_dir, clock, code=CODE):
        self.term, self.herdr, self.state_dir, self.clock = terminal, herdr, state_dir, clock
        self.colors = watch.stamp(os.path.join(state_dir, "colors.json"))
        self.renderer = Renderer(Theme.load(state_dir))
        self.answers = queue.Queue()
        self.running, self.again = set(), set()
        self.error = self.note = self.canvas = None
        self.quit, self.next_poll = False, 0.0
        self.code_dir, self.code, self.updated, self.restart = code, watch.code(code), None, False

    def run(self):
        """The loop: draw (only after a change: an idle pane costs next to nothing), wait for the keys, a job's answer
        or the next poll, act on them. True when it ended to make room for a new version of its code."""
        with self.term:
            try:
                self.resume()
                self.job("input", self.take_right_clicks)
                changed = True
                while not self.quit:
                    if changed:
                        self.draw()
                    events = self.term.read(self.timeout())
                    for event in events:
                        self.handle(event)
                        if self.quit:
                            break
                    answered = self.collect()
                    changed = self.tick() or answered or bool(events) or widgets.TURNS.ended()
            except KeyboardInterrupt:
                pass
            finally:
                self.stop()
        return self.restart

    def stop(self):
        """What has to end with the loop (a search running on)."""

    # --- background work

    def job(self, kind, work, then=None):
        """WORK on a thread of its own; its answer goes to THEN on the main thread, an exception to the error line.
        The thread is a daemon: quitting never waits for it (an AI may take minutes)."""
        self.running.add(kind)

        def task():
            try:
                answer = (work(), None)
            except Exception as err:            # any failure is one line; the view goes on
                answer = (None, err)
            self.answers.put((kind, then, *answer))
            self.term.wake()

        threading.Thread(target=task, name=f"sidebar-{kind}", daemon=True).start()

    def collect(self):
        """The jobs' answers; whether there were any."""
        answered = False
        while True:
            try:
                kind, then, result, err = self.answers.get_nowait()
            except queue.Empty:
                return answered
            answered = True
            self.running.discard(kind)
            if err is not None:
                self.error = str(err) or type(err).__name__
            elif then:
                then(result)

    def resized(self):
        """The pane changed size: when its column was dragged, every other tab's gets that width too (an unchanged
        share, a window resized, does nothing); once more when it changes while that runs."""
        pane = os.environ.get("HERDR_PANE_ID")
        if not pane:
            return
        if "column" in self.running:
            self.again.add("column")
            return

        def then(result):
            self.dragged(result)
            if "column" in self.again:
                self.again.discard("column")
                self.resized()

        self.job("column", lambda: self.drag(pane), then)

    def drag(self, pane):
        """On the job's thread: PANE (the sidebar's) changed size: its right column's width for every tab."""
        return column.drag(self.state_dir, pane, self.term.size()[0])

    def dragged(self, result):
        """On the main thread: what drag() found."""

    def take_right_clicks(self):
        """On the job's thread: a right click in this pane comes to it (its own menu), not to herdr's pane menu."""
        pane = os.environ.get("HERDR_PANE_ID")
        if pane:
            try:
                self.herdr.call("pane", "input", pane, "--right-click", "pane")
            except RuntimeError:
                pass                                # a herdr without it: its own menu stays

    def act(self, action):
        if action is not None:
            getattr(self, "do_" + action.name)(*action.args)

    def timeout(self):
        turning = widgets.TURNS.deadline()                 # a fold's chevron at rest again
        return max(0.0, min(self.deadlines() + ([turning] if turning else [])) - self.clock())

    def deadlines(self):
        """When the loop has to wake up on its own: the next poll."""
        return [self.next_poll]

    # --- a new theme, a new version

    def follow(self, now):
        """A new theme taken at once (herdr-fold's theme setter writes colors.json), a new version handed over to once
        all of it is in place and nothing would be cut short, the loop left when the code's folder is gone; whether
        anything shown changed."""
        shown = False
        colors = watch.stamp(os.path.join(self.state_dir, "colors.json"))
        if colors != self.colors:
            self.colors, self.renderer, shown = colors, Renderer(Theme.load(self.state_dir)), True
        code = watch.code(self.code_dir)
        if code is None:                            # its folder gone (uninstalled): out, no handover to bring back the
            self.quit = True                        # state folder just removed
            return shown
        if code != self.code:                       # a new version coming in: wait until all of it is in place
            self.code, self.updated = code, now
        elif self.updated is not None and now - self.updated >= SETTLE and not self.busy():
            self.hand_over()
        return shown

    def busy(self):
        """Whether a restart would cut something short: any job, even one only asked again (a status, a look), as the
        program it runs would be left behind in this process, never waited for: a zombie of the new version."""
        return bool(self.running)

    def left(self):
        """What the new version needs to come back where this one is."""
        return {}

    def take(self, left):
        """Come back to LEFT, where the version before this one was."""

    def hand_over(self):
        """Leave for the new version: what it needs to come back where this one is, then out of the loop."""
        token = uuid.uuid4().hex
        try:
            statefile.write(os.path.join(self.state_dir, f"resume-{token}.json"), self.left())
            os.environ[RESUME_ENV] = token
        except OSError:
            pass                                    # the new version then starts as a new one does
        self.restart = self.quit = True

    def resume(self):
        """Come back where the version before this one was, from the handover its token names (a fresh start has none);
        then forget it, and every handover a pane closed in between left behind (a preview tab's seed and spec, and a
        repository's issues as last asked, too)."""
        self.forget_stale()
        token = os.environ.pop(RESUME_ENV, "")
        if not token.isalnum():                     # none, or not a name inside the state folder
            return
        path = os.path.join(self.state_dir, f"resume-{token}.json")
        try:
            with open(path, encoding="utf-8") as f:
                left = json.load(f)
        except (OSError, ValueError):
            left = {}
        try:
            os.remove(path)
        except OSError:
            pass
        if isinstance(left, dict):
            self.take(left)

    def forget_stale(self):
        try:
            names = [name for name in os.listdir(self.state_dir)
                     if name.startswith(("resume-", "seed-", "preview-", "issues-")) and name.endswith(".json")]
        except OSError:
            return
        for name in names:
            path = os.path.join(self.state_dir, name)
            try:
                if time.time() - os.path.getmtime(path) > STALE:
                    os.remove(path)
            except OSError:
                pass
