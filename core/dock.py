"""The panels the dock shows and the groups they stand in, one under the other: each panel's name on its group's head,
its short name on the rail and its glyph (core/icons.py's), defined once for both clients; tools/build.py copies it."""

PANELS = {
    "files": {"title": "Files", "short": "Files", "glyph": "files"},
    "search": {"title": "Search", "short": "Search", "glyph": "search"},
    "changes": {"title": "Changes", "short": "Changes", "glyph": "git"},
    "issues": {"title": "Issues", "short": "Issues", "glyph": "issues"},
}
GROUPS = (("project", ("files", "search")), ("work", ("changes", "issues")))
