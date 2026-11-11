"""The panels the dock shows and the groups they stand in: each panel's name (on its tab, under its icon on the rail, in
the ⋯'s Panels) and its glyph (core/icons.py's), defined once for both clients; tools/build.py copies it."""

PANELS = {
    "conversations": {"name": "Chats", "glyph": "ai"},
    "files": {"name": "Files", "glyph": "files"},
    "search": {"name": "Search", "glyph": "search"},
    "changes": {"name": "Changes", "glyph": "git"},
    "issues": {"name": "Issues", "glyph": "issues"},
}
GROUPS = (("conversations", ("conversations",)), ("project", ("files", "search")), ("work", ("changes", "issues")))
