"""A panel family's face to the dock (the sidebar that hosts it): its PANELS and their views, its own work done through
HOST (its jobs, herdr, the repository's status, the preview tab), and what the dock asks of it; each hook does
nothing until a family has something to do there."""


class Family:
    PANELS = ()               # the panels it brings, by their core/dock.py names

    def __init__(self, host):
        self.host, self.views = host, {}

    def tick(self, now):
        """Its own work come due at NOW; whether anything shown changed."""
        return False

    def deadlines(self):
        """When the loop has to wake up for it."""
        return []

    def came(self, panel):
        """PANEL on screen again: what it needs then."""

    def resume(self):
        """The dock started, its terminal taken: what is asked for once."""

    def reload(self, folders=None):
        """FOLDERS changed on disk (None: any of them): shown as they are now."""

    def took_status(self, answer):
        """The repository's status as the dock got it (the dock's status job): what it shows of it."""

    def drawing(self):
        """Just before the dock draws its views: what changes on every frame."""

    def holds(self):
        """What a new version waits for: a name being typed, a question on screen."""
        return ()

    def left(self):
        """Its part of what a new version or a new preview tab starts with."""
        return {}

    def take(self, left):
        """Its part of LEFT taken back."""

    def stop(self):
        """What has to end with the dock."""
