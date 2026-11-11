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
| `uninstall.sh` | takes the TUI, the Herdr app or both off this Mac again, by the installer's records |
| `herdr-plugin.toml` | the whole environment as a herdr plugin (Full Setup), for herdr's marketplace: it opens `install.sh` in a herdr tab, once for each copy herdr keeps (`lib/offer_install.sh`) |
| `Brewfile` | the programs: herdr, Ghostty, starship, gh, bat, git-delta, ripgrep, the JetBrains Mono Nerd Font |
| `files.txt` | which file goes where on this Mac |
| `lib/` | the shell helpers: texts (`i18n.sh`), status lines (`output.sh`), file rules (`files.sh`), the loading animation (`loading.sh`), shared settings (`common.sh`); `offer_install.sh`, the whole-environment plugin's hook; `herdr_app.py`, herdr-fold in the Herdr app for the installer and the uninstaller (the mod, its layout and keys, in the app's home, the app's state of the layout pruned to it; the tabs' terminals its layout names, ended), and where the app's core is |

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
| `src/open_file.py` | opens a file the focused pane's output names, at its line, in the sidebar's preview tab (Cmd + Shift + L) |
| `src/restore_panes.py` | after a restart, starts herdr-fold's still-empty agent panes again (Workspaces runs it when herdr starts); run by hand, it brings each tab's right column back too, through the sidebar's `panes.py` |
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
| `src/python.ps1` | on a Windows machine, the real Python's path (not the Store's alias): its sidebar's launcher, its prepare script and the Herdr app mod ask it |
| `src/tui.py`, `src/herdrlib.py` | key handling for the small windows, the shared herdr helpers |
| `src/themes/` | the 12 themes (`themes.js`), their preview (`preview.html`, with the colors the theme setter gives the sidebar, the loading sheep and the logo in `preview-colors.js`), the theme setter (`apply.py`, which gives Ghostty the logo in a theme's colors as its app icon), the picker (`picker.py`), herdr-fold's logo (`logo.svg`, from `tools/logo.swift`) |

### Plugins

| File | What it is |
|---|---|
| `src/plugins/sessions-view/` | AI Sessions: only sessions with a conversation, under their names, and how long an agent waits on you in the Spaces list, one you marked unread too ([its README](../src/plugins/sessions-view/README.md)) |
| `src/plugins/workspaces/` | Workspaces: a new workspace asks for its folder, a workspace takes its renamed folder's name and says deleted when the folder is gone, one whose folder only holds a repository shows that one's branch (`git.py`, `core/`'s copy), a tab with a conversation asks before it closes; runs `restore_panes.py` when herdr starts ([its README](../src/plugins/workspaces/README.md)) |
| `src/plugins/sidebar/` | the sidebar plugin: Conversations, Files, Search, Changes and Issues, the preview pager, the commit message writer `commit_push.py` uses too; each panel family's work in a module of its own, the dock (`sidebar.py`) hosting them through one face (`family.py`): Files and Search (`files_panel.py`), Changes and Issues (`changes_panel.py`), Conversations (`conversations_panel.py`; the list `conversation_list.py`, the conversation files read by `core/conversations.py`, the formatted copy too); `panes.py` the right column in every new empty tab and back in every tab when herdr starts (an older install's Conversations columns closed), a pane brought back, Restore panels; `panels.py` what each tab has had, so a pane closed by hand stays closed, and bringing one back; `richtext.py` puts Markdown on the clipboard formatted, for Copy conversation and the formatted copy; `stack.py` the panels' groups in the pane's rows (a fold, a drag, what each folder keeps); the loop (`loop.py`) ([its README](../src/plugins/sidebar/README.md); [The sidebar](sidebar.md)) |

### Shared core

| File | What it is |
|---|---|
| `core/` | the data layer the TUI sidebar and the Herdr app mod share, its one source: `icons.py` (the sidebar's icons: Nerd Font glyphs, plain marks, each file type's, with the app's Catppuccin Icons name for it, a change's letter), `git.py` (the status, a folder's repository and branch for a Space row, a file's diff, staging, the last commits, a sync that loses nothing, the repository's name on GitHub), `tree.py` (the file tree: folders first, a folder read only when open, git's marks on it), `fileops.py` (new, rename and the system's Trash, never outside the root nor in an AI tool's folder), `search.py` (ripgrep, else git grep, else its own search: ignored files never read), `media.py` (an image as a PNG, a PDF's pages through PDFKit, the default browser), `github.py` (the issues through gh, GitHub's priority field, a change, the agent's prompt), `commit_message.py` (the commit message Claude or Codex writes, the staged files named like secrets), `job.py` (the mod's background job: started out of the exec that starts it, polled, cleared), `conversations.py` (this machine's Claude Code and Codex conversations, each file read once and then only where it grew; the formatted copy; the archived ones, kept with the column's settings, so the TUI and the app share them), `statefile.py` (a state file written whole, its owner's only, changed by one writer at a time across every process; herdr-fold's own state folder), `dock.py` (the panels and the groups they stand in, defined once for both clients), `chat.py` (a Claude Code conversation read into the steps the app's chat draws, only where it grew; what Claude waits on and the app's answer, a folder for each chat), `chat_hook.py` (what Claude runs in a chat, passed with `--settings`: its PermissionRequest hook answered from the app, a plan only posted, as Claude takes no hook's yes to leave plan mode; its status line's numbers kept for the app's bar); those the mod runs answer it in JSON from the command line; `tools/build.py` copies it into the sidebar's folder (all but `job.py`, `chat.py` and `chat_hook.py`) and into the mod, each installing on its own |

### The Herdr app

| File | What it is |
|---|---|
| `app/mods/herdr-fold/` | herdr-fold's mod for the Herdr desktop app, the TUI sidebar's counterpart ([The Herdr app](app.md)), with its `README.md` (its author), `LICENSE` and `THIRD_PARTY_NOTICES.md` (the package's own, which the app's copy keeps): `main.js` the Changes, Search and Issues views, a block each in the layout, and the keys the tab bar hands on to them; `issues.js` the Issues view (its list, filters and what an issue's buttons and menu do, through `core/github.py` and `core/commit_message.py`'s link); `files.js` the right panel's Files (the space's folder through `core/tree.py`, a file in the preview tab, new, rename, Copy Path and the Trash through `core/fileops.py`); `conversations.js` the left sidebar's Conversations (this Mac's conversations by space, through `core/conversations.py`; what a click and the menu do with one); `spaces.js` the left sidebar's Spaces list, where the app's own was (each space's place through `core/git.py`, how long its agents wait on you, Cmd+Shift+U); `tabs.js` the tab bar, where the app's own was (the space's tabs, dragged into order, renamed, the app's menu; its + New tab, and off macOS the window's buttons); `sidebar.js` the left sidebar folded to a dock (Spaces and Conversations floating beside it, the app's footer buttons) and its toggle left of the tabs; `preview.js` the space's preview tab, where a file, a diff, a commit or an issue opens; `terminal.js` the tab's own terminal under them: it follows the focused tab, starts one through the app's core on the space's machine, and ends a closed tab's, a closed chat tab's agent too; `helper.js` holds the core's source, which it runs with Python's `-I` on the space's machine (`python3`, or what a Windows machine's `python.ps1` names); `icons.js` its icons by the path the app loads each: the views', Lucide's in `icons/lucide/`, and a file's by its type, Catppuccin Icons' in `icons/catppuccin/` (both fetched by `tools/icons.py`), and a change's letter; `parts.js` the parts its views draw with (an icon, a button, a row's button, a chip, a key's cap, the context ring); `panel.js` the right dock: its head (⋯ with the panels' checks and herdr-fold's version, » to its rail), each group's head (its tabs, its fold), the « at the tab bar's end, its rail (the views floating beside it, the tab's terminal too), a key handed on to its view, and a folder followed on this computer; `chat.js` the chat tab: an agent's conversation drawn as a timeline from its session file, the agent in a core terminal with no pane, ended with its tab; its prompt and bar (the commands, the context ring and Compact, the model and effort, the mode, send and stop) and a usage limit's notice; `card.js` what Claude waits on, answered in the prompt's place (a command, a change numbered by its file, Claude's questions, its plan, whose choices are read off Claude's own dialog and answered there by keys); `timeline.js` the timeline without the window (a call and its result one row, each row's time in this Mac's zone); `agents.js` the agents a chat draws, each an adapter (how Claude is started and resumed, the settings that bring the chat's hook and status line, its modes, efforts and commands); `menus.js` its menus, popups as the app's own, a choice run back in the copy that opened it; `styleguide.js` the styleguide: each part in each of its states, drawn by the views' own code ([Styleguide](styleguide.md)), and `styleguide-page.svg` the page its PDF specimen shows; `logic.js` what it works out without a window: a file's icon, the Spaces list's waits, order, colors and height, a tab's name and the room for the traffic lights, a diff's rows, the preview tab's name and which tab it is, a priority's color, an issue's markdown made safe, the tab's agent, the sync label, the question before a commit, the message writer as a background job, the right dock's groups and what a key, a tab, a fold or a panel's check does to the layout, the layout with a tab's terminal in it or a closed tab's out |
| `app/layouts/herdr-fold.json` | the app's main layout with herdr-fold in the right panel (`fold-panel`, herdr-fold's own id, which the app's Settings leaves alone), where the app's own Changes and Files were: its dock's head (`fold-dock-head`), then its dock (`fold-dock`) of two groups, `fold-project` and `fold-work`, each a head over a stack of its views' blocks (`files` and `search`, `changes` and `issues`), its rail a block shown only while it is folded (`panel-rail`); « at the tab bar's right end and the views' keys open it; its Conversations in the left sidebar, under Spaces, where the app's own Agents list was; in the dock under the groups, the `fold-terminals` stack, a block per tab's terminal, its header (0 high) herdr-fold picking the one shown |
| `app/themes/` | the TUI's themes as the app's, made by `tools/build.py` from `src/themes/themes.js`: `herdr-fold.json`, that layout's own (the package's, Catppuccin Mocha), and `herdr-fold-ID.json` for each of the TUI's, offered in the app's Settings for every layout |
| `app/keys.json` | the keys, merged into the app's own: in that layout Cmd+Shift+G, Cmd+Shift+F and Cmd+Shift+I show Changes, Search and Issues, and Cmd+Shift+C has it write the message |
| `app/tests/` | the mod's logic tested with Node (`logic.test.js`, the chat's agents in `agents.test.js` and its timeline in `timeline.test.js`; `node --test` in `app/`); `tests/test_app.py` runs them, and the app's own check of the mod |
| `app/RECIPE.md`, `app/preview.png` | the layout's entry in the app's catalog (herdr.dev/layouts, for a public repository with the `herdr-layout` topic): the brief an agent builds it from, in the parts and order the app's guide gives, and a picture of it from the demo; the installer copies neither |

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
| `src/parts.py` | which of herdr-fold's parts are installed, the TUI and the Herdr app, as the installer's records say; the address of the installer's first question's page; where the Herdr app keeps its home |
| `src/install/parts.html` | the page the installer's first question opens in the browser: the TUI (with its picture) and the Herdr app, the one installed or the app on this Mac marked |
| `docs/` | the guides |
| `assets/` | the pictures the README and the guides show: the screenshots and the animation (`screenshots/`), the styleguide's (`styleguide/`) |
| `tests/` | the tests (`/usr/bin/python3 -m unittest discover -s tests`), a file named after where what it tests lives: `test_core_git.py` for `core/git.py`, `test_sidebar_scm.py` for the sidebar's `scm.py`, `test_close_tab.py` for `src/close_tab.py`; `test_lib_*`, `test_tools_*`, `test_remote_*` and `test_lab.py` for those folders, `test_install*`, `test_uninstall*` and `test_machines_*` for the scripts, `test_app.py` for the app mod, `test_repo_*` for what holds for the whole repository (docs, privacy, files); what more than one file needs is in `support.py`, and a test imports from there, never from another test |
| `lab/` | the test lab: a Linux machine in a container reached over SSH as a remote machine, run only when called (`python3 lab/lab.py test`); `lab.py`, the machine in `linux/` (`Containerfile`, `sshd.conf`, a stand-in `claude`), its tests in `tests/`, the mod's way through a change in `walk.py`, what GitHub's runners run in `ci/` ([its README](../lab/README.md)) |
| `tools/sync.sh` | copies this Mac's settings back into the package (not over a file edited there and not committed), then checks the files for private data |
| `tools/icons.py` | fetches the app mod's icons by name from Iconify into `app/mods/herdr-fold/icons/`: Lucide's for the views, Catppuccin Icons' for each file type `core/icons.py` names; run it when either list changes (nothing asks Iconify while the app runs) |
| `tools/build.py` | copies `core/` into the TUI sidebar (`src/plugins/sidebar/`, all but the mod's own `job.py`, `chat.py` and `chat_hook.py`) and into the app mod (`app/mods/herdr-fold/helper.js`, and `icons.js` from `core/icons.py` and the mod's `icons/` folder), and `git.py` into Workspaces (`src/plugins/workspaces/`); a test fails while a copy differs |
| `tools/preview_colors.py` | writes `src/themes/preview-colors.js` from the theme setter, the sidebar's icons, the loading sheep and the logo, which it first draws anew on a Mac with Swift (`src/themes/logo.svg`) |
| `tools/logo.swift` | draws herdr-fold's logo, its app icon, as SVG: the sheep with Liquid Glass in the shape of the Mac's own app icons |
| `tools/check_updates.py` | for the maintainer: whether what herdr-fold builds on moved on ([Keeping up](../CONTRIBUTING.md#keeping-up)) |
| `.githooks/` | `pre-commit` runs the privacy test before a commit, `commit-msg` reads its message the same way (on with `git config core.hooksPath .githooks`) |
| `.github/` | the issue forms, the pull request template, the weekly run of `tools/check_updates.py` (`workflows/check-updates.yml`), and the lab on GitHub's runners, run by hand (`workflows/lab.yml`) |

## Where things go

`files.txt` lists each file of the package and its place under the home folder on the Mac; `remote/files.txt` does the
same for a remote machine. A line with `*` stands for every matching file, so a new language file needs no new line.
Each line also names its part: `tui` for a file of the TUI alone, `both` for one the Herdr app uses too; the `Brewfile`
marks each program the same way (`[tui]`, `[both]`), so the installer and the uninstaller know what belongs to which.
Everything the scripts need at run time lives in `~/.config/herdr-fold/`; herdr's own folder, `~/.config/herdr/`, holds
only herdr's files and its `config.toml`. What is made on first use is in `~/.cache/herdr-fold/` (the helpers that
draw a PDF's pages and an SVG or a page, compiled once), the Herdr app's pictures in its home's `herdr-fold-pictures/`
(a day at most); the app keeps the mod's data there too (`data/herdr-fold/`, its views' state), the layout's
(`layouts/.state/herdr-fold.json`, its panels' sizes) and the mod's storage in
`~/Library/Application Support/gpui-shell/apps/herdr-fold-…` (empty: the mod stores nothing). The uninstaller takes
all of them off.

## The installer's records

`~/.local/state/herdr-fold/` holds what the installer needs to update and to uninstall cleanly; which parts are
installed is read from it (`src/parts.py`): the TUI where `installed.txt` names a TUI file or `plugins.txt` the
sidebar, the Herdr app where `plugins.txt` names `herdr-fold.app`.

| Entry | What it holds |
|---|---|
| `installed.txt` | every file the installer put down; one a newer version no longer has goes on the next run after a question (kept, it stays on the record and the next run asks again; an update with the earlier choices removes it unasked, saved first), or the machine's own original comes back |
| `installed.sha256` | each of those files' content right after the install: the uninstaller sets aside a file you changed since |
| `original/` | the machine's own files, as they were before the first install, its herdr settings too when herdr-fold's part was added to them; never pruned |
| `<date>/` | earlier versions of the installed files that a newer install replaced; the three newest are kept |
| `changed-<date>/` | installed files you changed (or with no sum recorded to tell), kept when a newer install replaced or dropped them; never deleted |
| `version` | the installed version, which the next install names in its update question |
| `plugins.txt` | the plugins and herdr integrations this installer put there, and the plugins you said no to (the Herdr app, once taken off alone, among them) |
| `app-keys.json` | the keys the last install put in the Herdr app's `keys.json`: the next install and the uninstaller take off one a newer version no longer has, unless you rebound it |
| `app-themes.json` | the themes the last install put in the Herdr app's `themes/`: the next install takes off one a newer version no longer brings, the uninstaller all of them; a theme of yours there stays, whatever its name |
| `app-machines.txt` | the remote machines herdr-fold added to the Herdr app, which the uninstaller takes off |
| `loading-colors.txt` | the loading sheep's colors, the chosen theme's |
| `ghostty-icon/` | the Ghostty app icon of the theme in use: herdr-fold's logo in its colors |
| `outside.txt` | what the installer did outside its own folders (the SSH key, trusted host keys, the GitHub sign-in, git's settings): it stays, and the uninstaller names it |
| `prepared.txt`, `prepared-<date>/` | only on a Mac that is also another Mac's remote machine: what that Mac's setup put there |
