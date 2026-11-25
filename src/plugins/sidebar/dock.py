# Generated from core/dock.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""The panels the dock shows and the groups they stand in: each panel's short name (under its icon in the row and on the
rail, in the ⋯'s Panels) and its glyph (core/icons.py's), defined once for both clients; tools/build.py copies it."""

PANELS = {
    "files": {"name": "Files", "glyph": "files"},
    "search": {"name": "Search", "glyph": "search"},
    "changes": {"name": "Changes", "glyph": "git"},
    "issues": {"name": "Issues", "glyph": "issues"},
    "agent": {"name": "Agent", "glyph": "robot"},
    "chats": {"name": "Chats", "glyph": "ai"},
}
GROUPS = (("project", ("files", "search")), ("work", ("changes", "issues")), ("agent", ("agent",)),
          ("chats", ("chats",)))
