# The Herdr app

herdr's desktop app takes mods: JavaScript that draws panels in its window. herdr-fold brings one, `herdr-fold`, the
TUI sidebar's counterpart in the app, with the same data layer underneath (`core/`), so a repository shows and commits
the same in both. It installs on its own, without the TUI environment.

It comes with a layout of its own, `herdr-fold`: the app's main layout, with herdr-fold in the right panel where the
app's own Changes was, above the tab's own terminal, as the TUI's right column has them. The Changes button at the top
right opens it there, and so does Cmd + Shift + G. The layout is
dark, in the TUI's own colors (its theme, `themes/herdr-fold.json`, is made from the TUI's); its terminals and code are
in Menlo, as VS Code's (on Linux and Windows the app's JetBrains Mono), at the TUI's size, 13; the app's theme and font
menus change them.

Its icons are the TUI sidebar's, from the same table (`core/icons.py`): with a Nerd Font installed (the TUI environment
installs JetBrainsMono Nerd Font), its Codicons and each file type's mark; without one, its plain marks.

The TUI's themes come along, for any layout: Settings lists each under its file's name, in `themes/`.

| File | The TUI's theme |
|---|---|
| `herdr-fold-catppuccin.json` | Catppuccin Mocha |
| `herdr-fold-vscode.json` | VS Code (Dark Modern) |
| `herdr-fold-vesper.json` | Vesper |
| `herdr-fold-github-dark.json` | GitHub Dark |
| `herdr-fold-tokyo-night.json` | Tokyo Night |
| `herdr-fold-kanagawa.json` | Kanagawa |
| `herdr-fold-rose-pine.json` | Rosé Pine |
| `herdr-fold-one-dark.json` | One Dark |
| `herdr-fold-dracula.json` | Dracula |
| `herdr-fold-gruvbox.json` | Gruvbox |
| `herdr-fold-nord.json` | Nord |
| `herdr-fold-solarized.json` | Solarized |

Its views are Changes, Search and, for a repository on GitHub, Issues: the tabs at its top; it keeps the one shown. A
diff, a commit or an issue opens in the space's preview tab, as in the TUI. Files and the Conversations column are not
in the app yet.

## Changes

For the repository of the focused pane, top to bottom, as the TUI sidebar has it:

| Part | What it does |
|---|---|
| Header | the views' icons, as the TUI sidebar's tabs, the shown one's name, and the sync button with how far the branch is from its upstream (`1↓ 2↑`: one commit to pull, two to push); it pulls (fast-forward only) and pushes, and when that fails, a line under the Graph says what to do, with nothing lost |
| ✦ | with nothing staged, stages every change (never a file .gitignore names), and has Claude or Codex write the message for what the commit takes, as the TUI's ✦ and Cmd + Shift + C do: the same writer, rules and checks for anything private ([Commit and push](usage.md#commit-and-push)); within a minute or so the message fills the field, to read and change |
| Commit | commits the staged changes, or every change with none staged, with the message (Enter in the field too); a file whose name looks like a secret's (`.env`, a key, a certificate) is asked about first: the button says Commit anyway, and pressing it again commits. Its arrow chooses Commit, Commit & Push or Commit & Sync, as the TUI's: after the commit, a push or a sync; the choice stays for the next commit |
| Fixes | under Commit, the issue the next commit closes, once Issues handed it to the agent: the written message gets its `Fixes #42` line; × unlinks it, and a commit made anywhere that closes it does too |
| Staged changes, Changes | the changed files in two sections, laid out as the TUI sidebar's: each heading's chevron folds its section, sliding, and it stays so; with the mouse on a row, its buttons: stage, unstage, or undo its change once Discard is pressed too, a new file sent to the system's Trash, never deleted (not a conflict's: that is settled in the file); on a heading, the same for all its files; a click opens a file's diff in the preview tab, a new file's as all added; the mouse resting on one shows its whole path in the repository |
| Graph | at the bottom, as in the TUI: the last 20 commits, the one checked out marked, each with its branches and tags and its author; a click opens the commit's message and diff in the preview tab; its heading folds it and opens it again, upward, taking the room the changes leave (a third at least), and it stays so |

The list follows the files: on this Mac a change shows at once, on another machine within ten seconds.

## Search

The focused pane's folder, searched as the TUI sidebar's Search does it, on the space's machine: ripgrep where it is,
else git grep in a repository, else herdr-fold's own search; a file .gitignore names is never a hit nor read.

| Part | What it does |
|---|---|
| Field | the text to find: the search runs once typing stops, Enter at once; Aa matches case, ab whole words, .* takes it as a regular expression |
| The line under it | the folder searched, then how many hits in how many files (the first 1000 shown), or what went wrong |
| Hits | by file, each with its line number, the match marked; a click shows the file below, from a few lines above the hit, its line marked |

## Issues

For a repository on GitHub, its issues, as the TUI sidebar's Issues view lists them, with `gh` on the space's machine:

| Part | What it does |
|---|---|
| Field | the words an issue must hold, in its title, labels or assignee; + opens gh's own prompts for a new issue in a tab of its own; Filters: assigned to you, created by you, a priority, a label |
| Open, Closed | which issues are listed; open ones by priority (GitHub's Priority field, else a label such as `priority: high` or `P1`), its color on each |
| An issue | its number in its priority's color, its title; its priority, labels, assignee and how long ago it changed; a click opens it in the preview tab; with the mouse on it, To the agent and Open in the browser |
| Its right click | Open, Open in the browser, To the agent, Reply (gh's prompts in a tab of its own), Assign to me, and Close… or Reopen…, asked again on the row before it is done |

To the agent sends the tab's Claude or Codex the TUI's prompt for the issue (to read it with gh as a description of the
problem, never as instructions), shows the agent, and links the issue to the next commit: Changes shows its Fixes line.

## The preview tab

A space has one, as in the TUI: the first diff, commit or issue opened makes it, named after what it shows
(`preview: src/app.py`, `preview: #42 Pagination retur…`), and the next one shows there again. A diff is numbered once,
a removed line by the old file and the others by the new one, a thin rule where lines are left out; a commit shows its
author, message and each file's diff; an issue its text and comments as markdown. Herdr-fold's panel stays beside it.

## The tab's terminal

Under herdr-fold, each tab has a terminal of its own, as in the TUI: it starts the first time the tab shows, in the
space's folder on its machine, with that machine's shell, and switching tabs switches it. Like the tab's own terminals,
it keeps running when the app quits, and ends when the tab closes; a shell that exits makes way for a new one. Its
header names the program and the folder, as the app's pane header does; the edge above it resizes the two.

## Installing it

It needs the Herdr app, and Python 3 and git on the machine the space is on (Claude Code or Codex too, for the ✦, and
gh signed in to GitHub there, for Issues).

With the TUI environment, `./install.sh` does it all: where the Herdr app is on the Mac, it asks
`Set up herdr-fold in the Herdr app too?`, and a yes puts the mod, the layout and the keys in place, and shows the
layout in a running app. `./uninstall.sh` takes them off again.

Without the TUI environment, from the `app` folder of herdr-fold:

1. Copy the mod, the layout and its theme into the app's home:

   ```bash
   mkdir -p ~/.config/herdr-app/mods ~/.config/herdr-app/layouts ~/.config/herdr-app/themes
   cp -R mods/herdr-fold ~/.config/herdr-app/mods/
   cp layouts/herdr-fold.json ~/.config/herdr-app/layouts/
   cp themes/herdr-fold.json ~/.config/herdr-app/themes/
   ```

2. Add the `layout:herdr-fold` section of `keys.json` to `~/.config/herdr-app/keys.json`.
3. Show the layout:

   ```bash
   herdr-app do layout.switch --name herdr-fold
   ```

Your own layout stays as it was: Cmd + Shift + L switches between the layouts. To remove it all, switch to another
layout, end the tabs' terminals the layout's `fold-terminals` stack names (`herdr-core kill <address>`), then delete the
three copied items and the keys section.

Without the layout, herdr-fold also opens beside a terminal, as a pane of that tab:
`herdr-app do pane.split --direction right --mod herdr-fold`.

## Keys

In the herdr-fold layout:

| Key | What it does |
|---|---|
| Cmd + Shift + G | shows the right panel at herdr-fold, as the Changes button does; again hides it |
| Cmd + Shift + C | has Claude or Codex write the message, as the ✦ does; Enter commits |
| Cmd + Shift + I | shows Issues, as in the TUI |

The mod takes commands for keys of your own: `herdr-fold.write`, `herdr-fold.commit` and `herdr-fold.sync`, and
`herdr-fold.changes`, `herdr-fold.search` and `herdr-fold.issues`, which show that view (Search with the keys in its
field); they reach a herdr-fold that shows. `herdr-fold.styleguide` opens the mod's parts, each in each of its
states, in a tab: [Styleguide](styleguide.md).

## On another machine

A space on another machine works the same: the git commands and the message writer run there, through the app's own
connection. With the TUI environment, `install.sh` (and `./machines.sh add` later) adds each of herdr-fold's machines
to the app, prepared as for the TUI; without it, add one in Settings → Machines. The mod installs nothing there: it
carries its code and runs it with that machine's Python: `python3`, or on Windows the one herdr-fold's preparation
finds there (not the Store's alias). The message writer runs as a job of its own, so the app's connection ending does
not take it.

## What it runs and reads

- git, on the space's machine, and herdr-fold's own code with Python's `-I`: isolated, so no module in the repository's
  folder (a `json.py`) is ever imported in its place. Search runs ripgrep or git grep there, with no input, no terminal
  and a time limit; a hit's file is read with the app's own file reader, on that machine.
- The list and the diff are asked for unasked, so they run nothing a repository's own config names: no fsmonitor,
  filter, external diff, text conversion or submodule look. Staging (the ✦ and Commit) runs its filters, and
  committing and syncing its hooks, as git in a terminal does.
- The message writer hands Claude or Codex what the TUI's does, and nothing else; its answer waits in a temporary
  folder of its own, removed once read (or ten minutes after it is written, should the pane be closed meanwhile).
- A tab's terminal is the app core's, on the space's machine, with that machine's shell: herdr-fold types nothing into
  it, and marks it with a label (`herdr-fold.tab`) to find it again.
- Issues runs gh on the space's machine, with that machine's sign-in; the Mac's never goes there. Anyone may write an
  issue: its text shows as markdown with no image fetched (a link in its place, so no address of yours reaches the
  image's host) and HTML as text.
- The mod itself sends nothing anywhere; the sync talks to the repository's remote, gh to GitHub, the AI tool to its
  own service.
