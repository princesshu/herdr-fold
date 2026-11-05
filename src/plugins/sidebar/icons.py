# Generated from core/icons.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""The sidebar's icons, the TUI's and the Herdr app mod's: Nerd Fonts glyphs, plain marks for a font without them,
and each file type's mark. tools/build.py copies it into the sidebar and writes the mod's icons.js from it."""
import os

# Nerd Fonts 3 glyphs (all Codicons, one line weight), and plain ones for a font without them. Ghostty draws each a bit
# wider than its cell, so the views' icons are equally wide and Issues' is GitHub's mark (the symmetric issue icon would
# look off-center). The file types' marks below are the languages' own
NERD_GLYPHS = {"closed": "\ueab6", "open": "\ueab4", "folder": "\uea83", "folder_open": "\ueaf7", "file": "\uea7b",
               "new_file": "\uea7f", "new_issue": "\uea60", "new_folder": "\uea80", "refresh": "\ueb37",
               "collapse": "\ueac5", "check": "\ueab2", "more": "\ueab4", "stage": "\uea60", "unstage": "\ueb3b",
               "discard": "\ueae2", "diff": "\ueae1", "files": "\ueaf0", "search": "\uea6d", "git": "\uea68",
               "ai": "\uec10", "issues": "\ueb00", "agent": "\uec0f", "web": "\ueb14", "fold": "\ueac7",
               "unfold": "\ueac7"}
PLAIN_GLYPHS = {"closed": "▸", "open": "▾", "new_file": "+", "new_issue": "+", "new_folder": "⊞", "refresh": "↻",
                "collapse": "⊟", "check": "✓", "more": "⌄", "stage": "+", "unstage": "−", "discard": "↺",
                "diff": "⇄", "files": "▤", "search": "⌕", "git": "⎇", "ai": "✦", "issues": "#", "agent": "»",
                "web": "↗", "fold": "«", "unfold": "»"}
EXTENSIONS = {"\ue73c": "py pyi", "\ue74e": "js mjs cjs", "\ue628": "ts", "\ue7ba": "jsx tsx", "\ue60b": "json jsonc",
              "\uf48a": "md markdown", "\ue736": "html htm", "\ue749": "css scss sass less",
              "\ue615": "toml yaml yml ini cfg conf", "\uf489": "sh bash zsh fish",
              "\U000f0a0a": "ps1 psm1 psd1 bat cmd", "\ue61d": "c h cpp cc cxx hpp", "\ue627": "go", "\ue7a8": "rs",
              "\ue791": "rb", "\ue738": "java", "\ue755": "swift", "\ue620": "lua", "\ue706": "sql db sqlite",
              "\uf1c3": "csv tsv", "\uf15c": "txt log", "\uf1c1": "pdf",
              "\uf1c5": "png jpg jpeg gif webp bmp ico svg tiff", "\uf1c7": "mp3 wav flac ogg",
              "\uf1c8": "mp4 mkv avi mov webm", "\uf1c6": "zip tar gz tgz bz2 xz 7z rar", "\uf023": "lock",
              "\uf031": "ttf otf woff woff2"}
# git's change codes as shown: an untracked file is U, a conflict !
GIT_LETTER = {"?": "U", "U": "!"}
BY_EXTENSION = {ext: glyph for glyph, exts in EXTENSIONS.items() for ext in exts.split()}
BY_NAME = (("\ue702", (".gitignore", ".gitattributes", ".gitmodules")), ("\uf308", ("dockerfile", "docker-compose")),
           ("\uf02d", ("readme",)), ("\uf24e", ("license", "copying")), ("\uf084", (".env",)),
           ("\uf487", ("package.json", "pyproject.toml", "cargo.toml", "go.mod")), ("\uf0ad", ("makefile",)))


def glyphs(icons):
    return NERD_GLYPHS if icons else PLAIN_GLYPHS


def icon(name, is_dir=False, expanded=False):
    """The Nerd Font glyph for a folder, or for a file by its name or extension."""
    if is_dir:
        return NERD_GLYPHS["folder_open" if expanded else "folder"]
    name = name.lower()
    for glyph, starts in BY_NAME:
        if name.startswith(starts):
            return glyph
    return BY_EXTENSION.get(os.path.splitext(name)[1][1:], NERD_GLYPHS["file"])
