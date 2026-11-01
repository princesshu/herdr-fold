# How it is built

herdr-fold is a folder of shell, Python and PowerShell scripts. The installer copies them to `~/.config/herdr-fold/` on
the Mac and on each remote machine, puts the settings of Ghostty, herdr and starship in place, and links three herdr
plugins of its own.

## What's in the package

### Installer

| File | What it is |
|---|---|
| `install.sh` | the install wizard |
| `install.command` | double-click launcher: runs `install.sh` in the Terminal app |
| `uninstall.sh` | takes it all off this Mac again, by the installer's records |
| `herdr-plugin.toml` | the whole environment as a herdr plugin (Full Setup), for herdr's marketplace: it opens `install.sh` in a herdr tab, once for each copy herdr keeps (`lib/offer_install.sh`) |
| `Brewfile` | the programs: herdr, Ghostty, starship, gh, bat, git-delta, ripgrep, the JetBrains Mono Nerd Font |
| `files.txt` | which file goes where on this Mac |
| `lib/` | the shell helpers: texts (`i18n.sh`), status lines (`output.sh`), file rules (`files.sh`), the loading animation (`loading.sh`), shared settings (`common.sh`); `offer_install.sh`, the whole-environment plugin's hook |

### Settings

| File | What it is |
|---|---|
| `config/ghostty/config` | Ghostty: theme (written by the installer), font, the Cmd keys |
| `config/herdr/config.toml` | herdr: theme (written by the installer), keys, Sessions and Spaces rows |
| `config/starship.toml` | the prompt in herdr panes |
| `src/pane-env.sh` | the herdr pane environment, loaded by `~/.zshrc` only in herdr panes |

### herdr scripts

| File | What it is |
|---|---|
| `src/herdr_layout.py` | builds the workspace for a repo, on this Mac or on a remote machine |
| `src/new_workspace.py` | the folder picker of a new workspace |
| `src/restore_panes.py` | after a restart, starts the Conversations columns, the sidebars and the still-empty agent panes again |
| `src/toggle_column.py` | hides and shows the right column (Cmd + Shift + E) |
| `src/close_tab.py` | closes a tab (Cmd + W); asks first for a tab with a conversation |
| `src/commit_push.py` | commit and push with an AI-written message (Cmd + Shift + C) |
| `src/claude_search.py` | searches the Claude conversation (Cmd + F) |
| `src/rich_clipboard.py` | formatted copy: the selected part of a reply, as HTML, RTF and plain text (written by the sidebar plugin's `richtext.py`) |
| `src/bin/pbcopy` | herdr's own `pbcopy`: passes the selection to the system's, then runs `rich_clipboard.py` |
| `src/claude_trust.py` | lists the git repositories of the herdr Claude panes that Claude does not trust yet, and trusts them on a yes |
| `src/statusline.py` | the Claude Code status line, on macOS, Linux and Windows |
| `src/statusline_setup.py` | the status line items: one checkbox list, a group for Claude and one for Codex |
| `src/herdr_config.py` | adds this package's keys and theme to your own herdr settings, between marks, and takes them out again |
| `src/projects.py` | where the folder picker starts: the folder holding the most git repositories, found by itself |
| `src/add_machine.py` | adds a remote machine (Ctrl + B, then Shift + M) through `machines.sh new` |
| `src/sidebar.sh`, `src/sidebar.ps1` | starts the sidebar at the top of the right column (`.ps1`: on Windows) |
| `src/tui.py`, `src/herdrlib.py` | key handling for the small windows, the shared herdr helpers |
| `src/themes/` | the 12 themes (`themes.js`), their preview (`preview.html`, with the colors the theme setter gives the sidebar, the loading sheep and the logo in `preview-colors.js`), the theme setter (`apply.py`, which gives Ghostty the logo in a theme's colors as its app icon), the picker (`picker.py`), herdr-fold's logo (`logo.svg`, from `tools/logo.swift`) |

### Plugins

| File | What it is |
|---|---|
| `src/plugins/sessions-view/` | AI Sessions: only sessions with a conversation, under their names ([its README](../src/plugins/sessions-view/README.md)) |
| `src/plugins/tab-layout/` | a new workspace asks for a folder, a new tab gets the columns, a workspace takes its renamed folder's name; runs `restore_panes.py` when herdr starts ([its README](../src/plugins/tab-layout/README.md)) |
| `src/plugins/sidebar/` | the sidebar plugin: Files, Search, Changes and Issues, the preview pager, the commit message writer `commit_push.py` uses too; the Conversations column (`conversations.py` reads the conversation files, the formatted copy too; `conversation_list.py`, `conversations_app.py`; `conversations_pane.py` its place in every tab, and Cmd+Shift+R); `panels.py` what each tab has had, so a pane closed by hand stays closed, and bringing one back; `richtext.py` puts Markdown on the clipboard formatted, for Copy conversation and the formatted copy; the loop both share (`loop.py`) ([its README](../src/plugins/sidebar/README.md); [The sidebar](sidebar.md)) |

### Remote machines

| File | What it is |
|---|---|
| `machines.sh` | connects and updates the remote machines |
| `src/remote.sh` | the remote machine helpers `machines.sh` and `herdr_layout.py` share: OpenSSH and the herdr CLI only |
| `remote/files.txt` | which file goes where on a remote machine |
| `remote/prepare-unix.sh`, `remote/prepare-windows.ps1` | set a Linux, macOS or Windows machine up (and, with `--remove`, take it off) |
| `remote/fetch-tool.sh` | downloads starship for a machine from a pinned release, kept only if its SHA-256 matches |

### Texts, docs, tests

| File | What it is |
|---|---|
| `src/lang/en.txt` | every text the scripts print, one `key = text` per line (see [Translating](translating.md)) |
| `src/i18n.py` | looks the texts up for the Python scripts |
| `docs/` | the guides, and their screenshots, the animation and the logo (`docs/media/`) |
| `tests/` | the tests: `/usr/bin/python3 -m unittest discover -s tests` |
| `tools/sync.sh` | copies this Mac's settings back into the package (not over a file edited there and not committed), then checks the files for private data |
| `tools/preview_colors.py` | writes `src/themes/preview-colors.js` from the theme setter, the sidebar's icons, the loading sheep and the logo, which it first draws anew on a Mac with Swift (`src/themes/logo.svg`) |
| `tools/logo.swift` | draws herdr-fold's logo, its app icon, as SVG: the sheep with Liquid Glass in the shape of the Mac's own app icons |
| `tools/check_updates.py` | for the maintainer: whether what herdr-fold builds on moved on ([Keeping up](../CONTRIBUTING.md#keeping-up)) |
| `.githooks/` | `pre-commit` runs the privacy test before a commit, `commit-msg` reads its message the same way (on with `git config core.hooksPath .githooks`) |
| `.github/` | the issue forms, the pull request template, and the weekly run of `tools/check_updates.py` (`workflows/check-updates.yml`) |

## Where things go

`files.txt` lists each file of the package and its place under the home folder on the Mac; `remote/files.txt` does the
same for a remote machine. A line with `*` stands for every matching file, so a new language file needs no new line.
Everything the scripts need at run time lives in `~/.config/herdr-fold/`; herdr's own folder, `~/.config/herdr/`, holds
only herdr's files and its `config.toml`.

## The installer's records

`~/.local/state/herdr-fold/` holds what the installer needs to update and to uninstall cleanly:

| Entry | What it holds |
|---|---|
| `installed.txt` | every file the installer put down; one a newer version no longer has goes on the next run after a question (kept, it stays on the record and the next run asks again; an update with the earlier choices removes it unasked, saved first), or the machine's own original comes back |
| `installed.sha256` | each of those files' content right after the install: the uninstaller sets aside a file you changed since |
| `original/` | the machine's own files, as they were before the first install, its herdr settings too when herdr-fold's part was added to them; never pruned |
| `<date>/` | earlier versions of the installed files that a newer install replaced; the three newest are kept |
| `changed-<date>/` | installed files you changed (or with no sum recorded to tell), kept when a newer install replaced or dropped them; never deleted |
| `version` | the installed version, which the next install names in its update question |
| `plugins.txt` | the plugins and herdr integrations this installer put there, and the plugins you said no to |
| `loading-colors.txt` | the loading sheep's colors, the chosen theme's |
| `ghostty-icon/` | the Ghostty app icon of the theme in use: herdr-fold's logo in its colors |
| `outside.txt` | what the installer did outside its own folders (the SSH key, trusted host keys, the GitHub sign-in, git's settings): it stays, and the uninstaller names it |
| `prepared.txt`, `prepared-<date>/` | only on a Mac that is also another Mac's remote machine: what that Mac's setup put there |
