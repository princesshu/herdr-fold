# The Herdr app

herdr's desktop app takes mods: JavaScript that draws panels in its window. herdr-fold brings one, `herdr-fold`, the
TUI sidebar's counterpart in the app, with the same data layer underneath (`core/`), so a repository shows and commits
the same in both. It installs on its own, without the TUI environment.

It comes with a layout of its own, `herdr-fold`: the app's main layout, with herdr-fold in the right panel where the
app's own Changes was, above the tab's own terminal, as the TUI's right column has them, and in the left sidebar its own
Spaces list, where the app's was, and under it its Conversations, where the app's Agents list was; a pane has no header,
as in the TUI (the grip on its top edge still drags it). The toggle at the top right, where the app's Files and Changes
buttons were, folds it to a rail of icons and opens it again, and so does Cmd + Shift + G. The layout is dark, in the
TUI's own colors (its theme, `themes/herdr-fold.json`, is made from the TUI's); its terminals and code are in Menlo, as
VS Code's (on Linux and Windows the app's JetBrains Mono), at the TUI's size, 13; the app's theme and font menus change
them.

Its icons are Lucide's, a file's Catppuccin Icons' for its type, as the TUI sidebar tells the types apart
(`core/icons.py`); `tools/icons.py` fetches both from Iconify into `app/mods/herdr-fold/icons/`, and `icons.js` names
each once, which every view draws them from. No Nerd Font is needed.

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

Its views are tabs of one panel group, as Adobe's panels are grouped, in VS Code's order: Files, Search, Changes and,
for a repository on GitHub, Issues; the shown one on a raised pad, Changes with its changed files' count in a round
badge, as VS Code's; it keeps the one shown. The toggle at the tab bar's right end (or Cmd + Shift + G) folds the panel
to a rail, as the left sidebar folds, and opens it again as wide as it was; dragged narrower than 160 px, it folds too.
The rail, as Adobe's collapsed panels: Files, Search, Changes with its count, Issues on GitHub and the tab's Terminal,
each a square with its name under it; a press floats that view beside the rail, nearly as tall as the window, one at a
time, its head dragging it and its × closing it; a key of a view's (Cmd + Shift + C, Cmd + Shift + I) floats it too. ×
at the end of the tabs hides the panel, and the toggle shows it again. The tab bar is herdr-fold's, drawn as the app's
own: the space's tabs, dragged into order, a double click renaming one, a right click the app's menu, the wheel
stepping through them; + after the last tab (New tab) starts a terminal or an agent, and every button there says
what it does. A file, a diff, a commit or an issue opens in the space's preview tab, as in the TUI.

## Files

The space's folder, read on the space's machine, as the TUI sidebar's Files shows it, where the app's own Files was:

| Part | What it does |
|---|---|
| The tree | folders first, then files, by name; a folder read only once opened, a very full one ending in `… N more`; what git ignores faint and never read |
| Icons | Catppuccin Icons' for each file type and for a folder, closed or open, as the Changes view's |
| Marks | git's letter on each changed file and a dot on a folder holding changes, in git's colors, as in the TUI |
| A click | a file opens in the space's preview tab, its lines numbered; a folder opens or closes |
| Right click | New File, New Folder, Rename (the name typed in its row; Enter makes it, Esc gives it up), Copy Path (the path on its machine, onto this computer's clipboard), Move to Trash (asked on its row first), and on a folder New Workspace there |
| The toolbar | New File and New Folder at the top, Refresh, Collapse Folders, and hidden files shown or not, kept for the next start |

It follows the folder as it changes; a folder on another machine is looked at again every ten seconds.

## Changes

For the repository of the focused pane, top to bottom, as the TUI sidebar has it:

| Part | What it does |
|---|---|
| Repositories | as VS Code's: the repository's name, its branch (`*` with changes) and ↻, which syncs: it pulls (fast-forward only) and pushes, and says how far the branch is from its upstream when it is (`1↓ 2↑`: one commit to pull, two to push); ⋯ pulls or pushes alone, or opens the repository on GitHub. When a sync fails, a line under the Graph says what to do, with nothing lost; the heading folds it, and it stays so |
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
| An issue | its number in its priority's color, its title; its priority, labels, assignee and how long ago it changed; a click opens it in the preview tab; with the mouse on it, To agent and Open in browser |
| Its right click | Open, Open in the browser, To the agent, Reply (gh's prompts in a tab of its own), Assign to me, and Close… or Reopen…, asked again on the row before it is done |

To the agent sends the tab's Claude or Codex the TUI's prompt for the issue (to read it with gh as a description of the
problem, never as instructions), shows the agent, and links the issue to the next commit: Changes shows its Fixes line.

## The preview tab

A space has one, as in the TUI: the first file, diff, commit or issue opened makes it, named after what it shows
(`preview: src/app.py`, `preview: #42 Pagination retur…`), and the next one shows there again. A file's lines are
numbered from the first; a diff is numbered once, a removed line by the old file and the others by the new one, a thin
rule where lines are left out; a commit shows its author, message and each file's diff; an issue its text and comments
as markdown. Herdr-fold's panel stays beside it.

## Spaces

In the left sidebar, herdr-fold draws the Spaces list where the app's own was, as the app draws it, and says how long
an agent in a space waits on you, as the TUI's Space rows do:

| Part | What it does |
|---|---|
| A space | its avatar in the color every app mod gives it (a worktree's, the branch icon, under its checkout's space), its name, then its branch, main too, as the TUI shows it, with the repository where it is not the name (never what its name says already), ↑ the commits to push and ↓ to pull; and `waiting 12m` in yellow while an agent there waits on you, blocked or done and not seen yet, the longest wait when several do. A click shows it, a drag puts it elsewhere among its machine's spaces, a right click opens the app's own menu for it |
| A machine | once another machine is known, a head for each: this computer first, then the others by name, how each is (asleep, unreachable…), + for a new space there on its hover, its dot green while connected; a click folds its spaces away, and folded, it says their longest wait. A machine rebuilt or replaced says so, and Connect adds it again the way it was added |
| + | a new space |

Cmd + Shift + U marks the focused agent unread, as in the TUI: its space says `waiting` again, from then, until you come
back to it after leaving it; again, it takes the mark off. The app keeps its own waits, apart from the TUI's.

## Conversations

In the left sidebar, every conversation of this Mac's spaces, running or closed, as the TUI's Conversations column
lists them:

| Part | What it does |
|---|---|
| Filter | the words a conversation's name, space or folder holds, `archived` for the archived ones; Cmd + Shift + R from anywhere gives it the keys, Enter opens the first one |
| A space | its most urgent agent's state mark, as the Spaces list has it, and its conversations, the active tab's first, then the newest; a click folds or opens it, the shown space open by itself |
| A conversation | its state's mark in herdr's colors (a closed one's a faint dot), its name, its agent and how long ago it changed; a click goes to a running one, or reopens a closed one in a new tab of its space, its agent resuming it (`claude --resume`, `codex resume`) |
| Its right click | Open, Copy conversation (all of it, as Markdown), Rename (in its row: Enter keeps it, as herdr's Rename pane names it) and, for a closed one, Archive or Unarchive; elsewhere in the list, Show or Hide archived |

Folded, by its toggle or dragged as narrow, the sidebar is a dock, as Illustrator's and Photoshop's panels collapse to
icons: Spaces and Conversations, each its icon and name, its most urgent state's dot at the corner, and at its foot the
app's Settings and Add machine, centered. A press floats that panel beside the dock, as tall as its content and one at a
time: dragged by its head, it stays where it is dropped, and opens there next time, until its × closes it. The toggle
left of the tabs opens the sidebar again. Open, the edge between Spaces and Conversations drags, Spaces only as far as
its list goes; Conversations takes the rest.

The archived ones and the names are the TUI column's own, so either shows what the other changed. Unlike the TUI's,
it copies a conversation as Markdown text, not formatted beside it, and archives one at a time.

## The tab's terminal

Under herdr-fold, each tab has a terminal of its own, as in the TUI: it starts the first time the tab shows, in the
space's folder on its machine, with that machine's shell, and switching tabs switches it. Like the tab's own terminals,
it keeps running when the app quits, and ends when the tab closes; a shell that exits makes way for a new one. It has
no header of its own; one that could not start says why in its place. The edge above it resizes the two.

## Installing it

It needs the Herdr app, and Python 3 and git on the machine the space is on (Claude Code or Codex too, for the ✦, and
gh signed in to GitHub there, for Issues).

With the TUI environment, `./install.sh` does it all: where the Herdr app is on the Mac, it asks
`Set up herdr-fold in the Herdr app too?`, and a yes puts the mod, the layout and the keys in place, and shows the
layout in a running app. `./uninstall.sh` takes them off again, alone or with the TUI, herdr-fold's settings in the app
too: a running app closes for that moment and opens again.

Without the TUI environment, from the herdr-fold folder:

```bash
python3 lib/herdr_app.py install .
herdr-app do layout.switch --name herdr-fold
```

The first puts the mod, the layout, its themes and its keys (the `layout:herdr-fold` section of `keys.json`) into the
app's home (`~/.config/herdr-app`, or `HERDR_APP_HOME`); run again after an update, it takes off what the earlier
version put there and this one no longer brings. Your own layout stays as it was: Cmd + Shift + L switches between the
layouts. To remove it all, switch to another layout, end the terminals it started for tabs (`python3
lib/herdr_app.py end-terminals`), close the app (while it runs, it keeps herdr-fold's settings and writes them back),
then `python3 lib/herdr_app.py uninstall .`.

Without the layout, herdr-fold also opens beside a terminal, as a pane of that tab:
`herdr-app do pane.split --direction right --mod herdr-fold`.

## Keys

In the herdr-fold layout:

| Key | What it does |
|---|---|
| Cmd + Shift + G | opens the right panel at Changes; again folds it to its rail |
| Cmd + Shift + C | commits and pushes in one step, as in the TUI: Claude or Codex writes the message into the field, and Commit says Commit & Push for this one commit; Enter commits and pushes, the field changes the message, ✦ writes another, Esc cancels; with nothing to commit, it offers to push the commits ahead, and Enter or Push pushes them |
| Cmd + Shift + I | shows Issues, as in the TUI |
| Cmd + Shift + R | gives Conversations' filter the keys, as in the TUI |
| Cmd + Shift + U | marks the focused agent unread: its space says `waiting` again, as in the TUI |

The mod takes commands for keys of your own: `herdr-fold.commit-push`, `herdr-fold.write`, `herdr-fold.commit` and
`herdr-fold.sync`, and `herdr-fold.changes`, `herdr-fold.search` and `herdr-fold.issues`, which show that view (Search
with the keys in its field), `herdr-fold.conversations`, which gives Conversations' filter the keys, and
`herdr-fold.unread`, which marks the focused agent unread; they reach a herdr-fold that shows. `herdr-fold.styleguide`
opens the mod's parts, each in each of its states, in a tab: [Styleguide](styleguide.md).

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
- Conversations reads the files Claude Code and Codex keep their conversations in on this Mac (`~/.claude/projects`,
  `~/.codex/sessions`), and never writes them; a rename goes where herdr's Rename pane keeps names, the archived ones
  beside the TUI column's settings. A closed one reopens only by an id that is one (letters, digits, `.`, `_`, `-`):
  read from a file, it is never taken for an option or a control code.
- The mod itself sends nothing anywhere; the sync talks to the repository's remote, gh to GitHub, the AI tool to its
  own service.
