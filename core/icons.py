"""The TUI sidebar's icons: Nerd Fonts glyphs, plain marks for a font without them, and each file type's mark, with
the Herdr app mod's own for it (Catppuccin Icons'); each network's mark in both clients. tools/build.py copies it into
the sidebar and the mod's icons.js."""
import os

# Nerd Fonts 3 glyphs (Codicons, one line weight; Task's clipboard Material Design's: Codicons have none), and plain
# ones for a font without them; a check is ✓ in both, the one mark of done. Ghostty draws each a bit wider than its
# cell, so the views' icons are equally wide; Issues' is the issue icon itself (cod-issues), as the owner asked.
NERD_GLYPHS = {"closed": "\ueab6", "open": "\ueab4", "folder": "\uea83", "folder_open": "\ueaf7", "file": "\uea7b",
               "new_file": "\uea7f", "new_folder": "\uea80", "refresh": "\ueb37", "collapse": "\ueac5",
               "check": "✓", "more": "\ueab4", "stage": "\uea60", "unstage": "\ueb3b", "discard": "\ueae2",
               "diff": "\ueae1", "files": "\ueaf0", "search": "\uea6d", "git": "\uea68", "ai": "\uec10",
               "issues": "\ueb0c", "agent": "\uec0f", "robot": "\uec20", "web": "\ueb14", "repo": "\uea62",
               "terminal": "\uea85", "close": "\uea76", "funnel": "\ueb83", "Bug": "\ueaaf", "Feature": "\uea61",
               "Task": "\U000f0a38", "lan": "\U000f0317", "globe": "\ueb01", "shield": "\ueb53"}
# an issue type has no plain mark: without icons its word says it; a public address's ⊕ is the Earth's sign
PLAIN_GLYPHS = {"closed": "›", "open": "⌄", "new_file": "+", "new_folder": "⊞", "refresh": "↻", "collapse": "⊟",
                "check": "✓", "more": "⌄", "stage": "+", "unstage": "−", "discard": "↺", "diff": "⇄", "files": "▤",
                "search": "⌕", "git": "⎇", "ai": "✦", "issues": "#", "agent": "»", "robot": "◇", "web": "↗",
                "repo": "▣", "terminal": "$", "close": "×", "funnel": "▽", "lan": "⌂", "globe": "⊕", "shield": "∩"}
# each network's mark, core/machines.py's networks in order (one behind another: its indent): a brand's logo (icons/
# logos/), MONO in COLOR or the text's, where its terms allow one, else its LETTER, NEUTRAL where they forbid it; the
# others' icon, Lucide's in the app, GLYPHS' key in the TUI
NETWORKS = {
    "local": {"logo": None, "mono": False, "icon": "network", "glyph": "lan", "letter": None, "color": None,
              "neutral": False},
    "tailscale": {"logo": "tailscale", "mono": True, "icon": None, "glyph": None, "letter": "T", "color": None,
                  "neutral": False},
    "netbird": {"logo": "netbird", "mono": False, "icon": None, "glyph": None, "letter": "N", "color": "#f68330",
                "neutral": False},
    "zerotier": {"logo": "zerotier", "mono": True, "icon": None, "glyph": None, "letter": "Z", "color": "#ffb441",
                 "neutral": False},
    "wireguard": {"logo": None, "mono": False, "icon": None, "glyph": None, "letter": "W", "color": None,
                  "neutral": True},
    "tunnel": {"logo": None, "mono": False, "icon": "shield", "glyph": "shield", "letter": None, "color": None,
               "neutral": False},
    "cloudflare": {"logo": None, "mono": False, "icon": None, "glyph": None, "letter": "C", "color": None,
                   "neutral": True},
    "public": {"logo": None, "mono": False, "icon": "globe", "glyph": "globe", "letter": None, "color": None,
               "neutral": False},
}
# the file types' marks: the languages' own, and Catppuccin Icons' name for each, the app's
FILE_TYPES = (("\ue73c", "python", "py pyi"), ("\ue74e", "javascript", "js mjs cjs"), ("\ue628", "typescript", "ts"),
              ("\ue7ba", "javascript-react", "jsx"), ("\ue7ba", "typescript-react", "tsx"),
              ("\ue60b", "json", "json jsonc"), ("\uf48a", "markdown", "md markdown"), ("\ue736", "html", "html htm"),
              ("\ue749", "css", "css"), ("\ue749", "sass", "scss sass"), ("\ue749", "less", "less"),
              ("\ue615", "toml", "toml"), ("\ue615", "yaml", "yaml yml"), ("\ue615", "config", "ini cfg conf"),
              ("\uf489", "bash", "sh bash zsh fish"), ("\U000f0a0a", "powershell", "ps1 psm1 psd1"),
              ("\U000f0a0a", "batch", "bat cmd"), ("\ue61d", "c", "c"), ("\ue61d", "c-header", "h"),
              ("\ue61d", "cpp", "cpp cc cxx hpp"), ("\ue627", "go", "go"), ("\ue7a8", "rust", "rs"),
              ("\ue791", "ruby", "rb"), ("\ue738", "java", "java"), ("\ue755", "swift", "swift"),
              ("\ue620", "lua", "lua"), ("\ue706", "database", "sql db sqlite"), ("\uf1c3", "csv", "csv tsv"),
              ("\uf15c", "text", "txt"), ("\uf15c", "log", "log"), ("\uf1c1", "pdf", "pdf"),
              ("\uf1c5", "image", "png jpg jpeg gif webp bmp ico tiff"), ("\uf1c5", "svg", "svg"),
              ("\uf1c7", "audio", "mp3 wav flac ogg"), ("\uf1c8", "video", "mp4 mkv avi mov webm"),
              ("\uf1c6", "zip", "zip tar gz tgz bz2 xz 7z rar"), ("\uf023", "lock", "lock"),
              ("\uf031", "font", "ttf otf woff woff2"))
# git's change codes as shown: an untracked file is U, a conflict !
GIT_LETTER = {"?": "U", "U": "!"}
BY_EXTENSION = {ext: (glyph, name) for glyph, name, exts in FILE_TYPES for ext in exts.split()}
BY_NAME = (("\ue702", "git", (".gitignore", ".gitattributes", ".gitmodules")),
           ("\uf308", "docker", ("dockerfile", "docker-compose")), ("\uf02d", "readme", ("readme",)),
           ("\uf24e", "license", ("license", "copying")), ("\uf084", "env", (".env",)),
           ("\uf487", "package-json", ("package.json",)), ("\uf487", "python-config", ("pyproject.toml",)),
           ("\uf487", "cargo", ("cargo.toml",)), ("\uf487", "go-mod", ("go.mod",)),
           ("\uf0ad", "makefile", ("makefile",)))
FILE = "file"                   # Catppuccin Icons' name for any other file
FOLDER = {"closed": "folder", "open": "folder-open"}      # and for a folder, closed and open


def glyphs(icons):
    return NERD_GLYPHS if icons else PLAIN_GLYPHS


def network_mark(kind, icons):
    """Network KIND's mark in one cell for the TUI and its color, None for none known: its icon's glyph (ICONS: the
    font's, else the plain one), muted; else its letter in its brand's color, else the text's, or muted if neutral."""
    mark = NETWORKS.get(kind)
    if not mark:
        return None
    if mark["glyph"]:
        return glyphs(icons)[mark["glyph"]], "muted"
    return mark["letter"], mark["color"] or ("muted" if mark["neutral"] else "text")


def kind(name):
    """A file's (glyph, Catppuccin Icons' name) by its name's start, else its extension; None for any other."""
    name = name.lower()
    for glyph, icon_name, starts in BY_NAME:
        if name.startswith(starts):
            return glyph, icon_name
    return BY_EXTENSION.get(os.path.splitext(name)[1][1:])


def icon(name, is_dir=False, expanded=False):
    """The Nerd Font glyph for a folder, or for a file by its name or extension."""
    if is_dir:
        return NERD_GLYPHS["folder_open" if expanded else "folder"]
    found = kind(name)
    return found[0] if found else NERD_GLYPHS["file"]


def file_type(name):
    """The Herdr app's icon for a file, Catppuccin Icons' name, as icon() picks the TUI's."""
    found = kind(name)
    return found[1] if found else FILE
