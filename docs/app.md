# The Herdr app

herdr's desktop app takes mods: JavaScript that draws panels in its window. herdr-fold brings one, `herdr-fold`, the
TUI sidebar's counterpart in the app, with the same data layer underneath (`core/`), so a repository shows and commits
the same in both. The installer sets it up alone or beside the TUI ([Installing it](#installing-it)).

It comes with a layout of its own, `herdr-fold`: the app's main layout under a title row of its own across the window
([The title row](#the-title-row)), with herdr-fold in the right panel where the app's own Changes was, above the tab's
own terminal, as the TUI's right column has them, and in the left sidebar its own Spaces list, where the app's was, on
the side's level (the theme's three: [Color](styleguide.md#color)); its Chats open from the tab bar's end, over the
right panel, as the TUI sidebar's open them; a pane has no header, as in the TUI (the grip on its top edge still drags
it). The layout is in the theme herdr-fold's installer chose (the TUI's twelve, one for both: [Themes](themes.md)); its
terminals and code are in the TUI's font, herdr-fold Mono (the mod brings it in `fonts/`,
[Installation](installation.md#the-font)), at the TUI's size, 13, the TUI's line height with it; the app's theme and
font menus change them.

Its icons are Lucide's, a file's Catppuccin Icons' for its type, as the TUI sidebar tells the types apart
(`core/icons.py`), and a connector's its service's own logo, SVG Logos' (`core/connectors.py` knows eight);
`tools/icons.py` fetches the three sets from Iconify into `app/mods/herdr-fold/icons/`, and `icons.js` names each once,
which every view draws them from. Nothing is fetched while the app runs, and no Nerd Font is needed.

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

The right panel is a dock, as the TUI sidebar: one card, its top level with the tab's beside it, its views' tabs on top
with a hairline under them, then the view chosen; the tab's terminal at its foot, on a card of its own. Both cards and
the tab are 12 px inside on every side; the tabs stand 8 px in. The tabs are the views by name, as a design tool's panel
tabs: Files, Search, Changes, for a repository on GitHub Issues, and Agent (with its agent's own icon before its name:
[Agent](#agent)), each as wide as its name; the one shown stands on a raised pill in the text's color, the others muted,
and fills the card; each space keeps which one it is, a new space starting on Files, and Issues, given way to Files
outside GitHub, comes back in a repository on GitHub. Changes shows its count after its name in a small round accent
badge, 18 px high, short when large (1.2k, 18k, 1.3m), whichever view shows. Narrower than the tabs need, the last ones
leave the row, never the one shown. The dock's own actions stand at the tab bar's right end, over it, open or folded:
Chats (the four-point star: [Chats](#chats)), More and », each an icon, its tip opening to its left. More lists the
views, each with a check while it shows, as Adobe's Window menu: one unchecked leaves the tabs, and one always stays;
below them one line, About herdr-fold, opens [Settings](#settings) at About. », in the row of the left sidebar's
own toggle, or Cmd + Option + B folds the dock to a rail, as the left sidebar folds, and « in the same place (or the
key) opens it again as wide as it was; the Chats list in the dock's view place closes as it folds. Dragged, it settles
once let go, as the TUI sidebar does: narrower than 160 px it folds to its rail; its rail dragged more than 24 px wider
opens it as « does, a smaller nudge leaving the rail as it was; the width it is let go at open is the one « opens it to.
The dock is open or a rail, never hidden. The rail, as Adobe's collapsed panels, on the side's level as the folded left
sidebar, its first icon level with that one's: each view shown (Agent under Lucide's bot, as the rail's icons are one
color) and the tab's Terminal, each a square with its name under it, Changes with its count on its icon's corner; a
press floats that view beside the rail, under the tab bar, every time there, one at a time, its icon lit meanwhile and
the keys in it: its icon again, Esc, its × or a press beside it closes it, as the dock opening does (a press in a menu
it opened is its own). Another icon on the rail, Terminal, «, More or ✦ closes it and does its own at once, as Adobe
switches its panels: the next float opens, the terminal shows, More's menu opens, a press never only closing it. Esc
goes to its view first while that is editing (a search typed, a commit message, a name being given, a list open), then
the keys go back to the float, and the next Esc closes it. Its head drags it while it is open, and it is as tall as last
dragged by the grip at its foot (at least its head and three rows, at most the rail's height; a double click there its
tallest, or back to the height dragged last), each view keeping its own and opening at it; its width is the dock's; a
view's key floats it too. Terminal shows or hides the tab's terminal under the tab, as VS Code's panel, lit in the
accent while it shows. The tab bar is herdr-fold's, drawn as the app's own: the space's tabs, the first one named as the
space until it is renamed (as the TUI's main tab), dragged into order, a double click renaming one, a right click the
app's menu, the wheel stepping through them; after the last tab, + starts an agent (New chat, Cmd + N: [New
chats](#new-chats)) and >_ (New terminal) opens a terminal tab with the machine's shell (an agent starts as + starts
it, a space from Spaces' +, a worktree from a space's right click); every button there says what it does. A text file
opens in an editor tab of its own ([Editing files](#editing-files)); a picture, a page, Markdown, a diff, a commit or an
issue in the space's preview tab, as in the TUI.

## Files

The space's folder, read on the space's machine, as the TUI sidebar's Files shows it, where the app's own Files was:

| Part | What it does |
|---|---|
| The tree | folders first, then files, by name; a folder read only once opened, a very full one ending in `… N more`; what git ignores faint and never read |
| Icons | Catppuccin Icons' for each file type and for a folder, closed or open, as the Changes view's |
| Marks | git's letter on each changed file and a dot on a folder holding changes, in git's colors, as in the TUI |
| A click | a text file opens in an editor tab ([Editing files](#editing-files)); an image, a PDF, a page, an SVG or Markdown in the space's preview tab; a folder opens or closes |
| Right click | Open in Browser (a page, a PDF or an image on this Mac, in the default browser; Open in Preview for a picture no browser shows, as a PSD or an EXR), Close Preview (while the space has a preview tab), New File, New Folder, Rename (the name typed in its row; Enter makes it, Esc gives it up), Copy Path (the path on its machine, onto this computer's clipboard), Move to Trash (asked on its row first), and on a folder New Space there |
| The toolbar | New File and New Folder at the top, Refresh, Collapse Folders, and hidden files shown (the default) or not, kept for the next start |

It follows the folder as it changes; a folder on another machine is looked at again every ten seconds.

## Changes

For the repository of the focused pane, top to bottom, as the TUI sidebar has it. In a space whose folder is no
repository itself but holds one, it is the repository the Spaces row names (`core/git.py`'s `top`), and the tab bar's
count and Issues follow it:

| Part | What it does |
|---|---|
| Repositories | as VS Code's: the repository's name, its branch (`*` with changes) and ↻, which syncs: it pulls (fast-forward only) and pushes, and says how far the branch is from its upstream when it is (`1↓ 2↑`: one commit to pull, two to push); ⋯ pulls or pushes alone, or opens the repository on GitHub. While a commit, a sync, a pull or a push runs, ↻ is a spinner whose tip names the step. When one fails, the card's foot says what to do, with nothing lost, red, over its last strip so nothing moves, until the next action or its ×; the heading folds it, and it stays so |
| Pull request | under the repository, for a pushed branch other than the default one: `No pull request for this branch` and Create pull request…, or its pull request: its checks' mark (✓ passed, ● running, ✕ failed), number and title, its state (Draft, approved, changes requested) and its checks (`checks 2 of 3`); a press opens its review in the preview tab. Asked again once the branch or its last commit changes, else once a minute |
| New pull request | Create pull request…, or the + of Issues' Pull requests, opens the form in the message's place: Into (the remote's branches) from the branch and its commits; the Title and the Body, which Claude or Codex writes from the branch's commits and diff with the commit message's writer and checks (✦ writes them again), with `Fixes #42` for the issue Issues handed the agent and those its commits close; Draft, the default, or Ready for review; and one button saying which, Create draft pull request or Create pull request. Esc or Cancel gives it up; gh's refusal is said under it |
| ✦ | with nothing staged, stages every change (never a file .gitignore names), and has Claude or Codex write the message for what the commit takes, as the TUI's ✦ and Cmd + Shift + C do: the same writer, rules and checks for anything private ([Commit and push](usage.md#commit-and-push)); the field says who writes it meanwhile (with words already in it, ✦'s tip says it, a spinner in ✦), and within a minute or so the message fills it, to read and change |
| Commit | commits the staged changes, or every change with none staged, with the message (Enter in the field too); a file whose name looks like a secret's (`.env`, a key, a certificate) is asked about first: the button says Commit anyway, and pressing it again commits. Its arrow chooses Commit, Commit & Push or Commit & Sync, as the TUI's: after the commit, a push or a sync; the choice stays for the next commit. With nothing to commit it is not lit: the pull request's row is the way on |
| Fixes | at the message field's end, `Fixes #42` in the accent (its title in the tip), the issue the next commit closes, once Issues handed it to the agent: the written message gets its `Fixes #42` line; × unlinks it, and a commit made anywhere that closes it does too |
| Staged changes, Changes | the changed files in two sections, laid out as the TUI sidebar's: each heading's chevron folds its section, sliding, and it stays so; with the mouse on a row, its buttons: stage, unstage, or undo its change once Discard is pressed too, a new file sent to the system's Trash, never deleted (not a conflict's: that is settled in the file); on a heading, the same for all its files; a click opens a file's diff in the preview tab, a new file's as all added, a picture's before (the last commit's) and after (the file) side by side under their names and sizes, as VS Code's image diff; the mouse resting on one shows its whole path in the repository |
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
| Open, Closed | which issues are listed; open ones by priority (GitHub's Priority field, else a label such as `priority: high` or `P1`), its color on each; at their row's end Refresh, a spinner of its size in its place while a list shown is asked for again, the list staying where it is; the first load (`Loading issues…`), a failure or none found is said, faint (a failure red), where the first issue will be, and what is under way or was done (`Closing…`, `Closed #42`) under the list |
| An issue | its number in its priority's color, its title; its priority, labels, assignee and how long ago it changed; a click opens it in the preview tab; with the mouse on it, To agent and Open in browser |
| Its right click | Open, Open in the browser, To the agent, Reply (gh's prompts in a tab of its own), Assign to me, and Close… or Reopen…, asked again on the row before it is done |

On its top, Issues and Pull requests switch the list. Pull requests has the same field (its + opens Changes' form,
the one way to open one), Open and Closed (closed and merged ones) and Refresh; each row its checks' mark, number and
title, its review's state as one word (your review in yellow, as it waits on you, changes requested red, approved green,
Draft a neutral tag), its branch, author (you) and age, the checks unless they passed; a click opens its review in the
preview tab, with the mouse on it To agent (the agent reviews it: `gh pr view` and `gh pr diff`, read as a
description, never as instructions) and Open in browser.

To the agent sends the tab's Claude or Codex (in a pane, or the chat tab's) the TUI's prompt for the issue (to read it
with gh as a description of the problem, never as instructions), shows the agent, and links the issue to the next
commit: Changes shows its Fixes line. With none in the tab, a new agent gets it, as + starts one: a new chat with the
prompt as its first message, or with Open agents in: Terminal the agent used last in a terminal tab, the prompt its
first message; the line under the list says which (`Sent to a new chat: #42`).

## The preview tab

A space has one, as in the TUI: the first file, diff, commit or issue opened makes it, named after what it shows
(`preview: docs/api.md`, `preview: #42 Pagination retur…`), and the next one shows there again. A diff is numbered
once, a removed line by the old file and the others by the new one, a thin
rule where lines are left out; a commit shows its author, message and each file's diff; an issue its text and comments
as markdown. A pull request shows its review, as GitHub's Files changed: its title, state, branches and checks, each
file's diff numbered, each thread under its line (Reply, Resolve, and on your own pull request To agent, which sends the
agent where the comment is and how to read it, never its words, and says under the thread where it went); a press on a
line's number writes a comment, added to the review; at the foot the summary, Comment, Approve (never on your own) or
Request changes, and Submit review, which sends it all in one request (Comment and Request changes need a summary).
An image on this Mac (any macOS reads, HEIC, AVIF, PSD, EXR and a camera's raw file too) is drawn, fitted
to the tab and never larger than it is; a PDF's pages one under another at their own size (smaller in a narrower tab), a
gap apart and clear of the scrollbar, scrolled, each drawn as it comes into view, the page in view and Open in Browser
above them; one on another machine is not. An SVG or an HTML page on this Mac shows its code and its picture side by
side, as VS Code's preview to the side, or its code above its picture in a tab taller than wide: the divider between
them drags, and the page is drawn for its side as a browser that size shows it, once the divider is let go, on the
canvas as a design tool's artboard (an SVG at its own size, never larger, what it leaves empty clear); Code, Split and
Picture above them show either alone or both again, and the button beside them sets the two side by side or one under
the other. WebKit draws it offline, as in the TUI. Markdown is drawn the same way beside its code, as the issues' text
is (no image fetched, no HTML). Their code is the editor ([Editing files](#editing-files)): a page or an SVG saved is
drawn again, Markdown as you type. A right click in the tab offers those, Open in Browser and Close Preview.
Herdr-fold's panel stays beside it.

![A PDF's pages one under another in the preview tab, its first page in view under the page count and Open in
Browser; beside it Files](../assets/screenshots/app-pdf.webp)

![An HTML page's code left and the page right, drawn for its side, under Code, Split and Picture; beside it
Files](../assets/screenshots/app-split.webp)

## Editing files

A text file (JSON, code, TOML, plain text, `.env`) opens in a tab of its own, named for its path, in the app's code
editor: the theme's colors, line numbers, folding. Every file has a tab of its own, never taking another's: opened
again, its tab shows. Typing edits at once, and while there are unsaved changes
a neutral dot stands in the tab's × place (× under the pointer). Cmd + S saves in place, keeping the file's line ends
and mode, with no window; Cmd + F opens the editor's find bar at its top right: the match count, Enter the next,
Shift + Enter the previous, Esc closes it (in a terminal or a chat Cmd + F keeps its meaning). Closing a tab with
unsaved changes asks nothing: a draft of them is written about once a second while you type, in herdr-fold's state
folder (`~/.local/state/herdr-fold/drafts`, its owner's only, never beside the file), and opening the file again brings
it back with its dot. A draft goes once saved, after Reload, or when its file is gone.

If the file changes on disk while you have unsaved changes (an agent wrote it), a quiet bar says so: Reload takes the
disk's text, Keep mine keeps yours for the next save; while it shows, Cmd + S writes nothing. With nothing unsaved the
tab reloads quietly. An agent's settings file (`.claude/settings*.json`, `.codex/config.toml`) opens the same way under
a line saying the Agent panel's forms are its checked way, with Show in Agent. What cannot be edited safely says why and
stays read only: a file over 1 MiB (its start shown), one that is not UTF-8 text, a link leading out of the folder, and
a file on another machine (the app writes on this computer only).

## Spaces

In the left sidebar, herdr-fold draws the Spaces list where the app's own was, as the app draws it, and says how long
an agent in a space waits on you, as the TUI's Space rows do:

| Part | What it does |
|---|---|
| A space | its avatar in the color every app mod gives it (a worktree's, the branch icon, under its checkout's space), its name, then its branch (where its folder only holds a repository, that one's: the active pane's among several), main too, as the TUI shows it, with the repository where it is not the name (never what its name says already), ↑ the commits to push and ↓ to pull; and `waiting 12m` in yellow while an agent there waits on you, blocked or done and not seen yet, or a chat tab there asks you something, the longest wait when several do. A click shows it, a drag puts it elsewhere among its machine's spaces, a right click opens the app's own menu for it |
| Home | each machine's home folder is always a row, `~`, first among its machine's spaces: this computer's, and each connected machine's. The app ends a space with its last tab (it asks first), so with no space there the row stays as a stand-in with nothing open: its avatar an outline, its name dim, no branch. A click opens a terminal there, the space the app calls `~`; the stand-in has no menu, and it is never dragged, nor anything dropped above it. Any other space closed is gone, as the app has it. Folded to its dock, the floating list shows the same rows |
| A root | a space on a machine's root, which the app names by its path (`/`, `C:\`), is named by a word, as in the TUI: `root`, or the drive, `C:`. Its avatar is home's kind: a glyph tile in home's color, `/` or the drive's letter |
| A machine | once another machine is known, a head for each: this computer first, then the others by name, how each is (asleep, unreachable…), + for a new space there on its hover, its dot green while connected; a click folds its spaces away, and folded, it says their longest wait. A machine rebuilt or replaced says so, and Connect adds it again the way it was added |
| + | a new space, its agent started as + after the last tab starts one ([New chats](#new-chats)) |
| The foot | Settings, which opens [Settings](#settings), and Add machine…, as the app's own foot has them |

Cmd + Shift + U marks the focused agent unread, as in the TUI: its space says `waiting` again, from then, until you come
back to it after leaving it; again, it takes the mark off. The app keeps its own waits, apart from the TUI's.

Folded, by its toggle, by Cmd + B or dragged narrower than 160 px and let go, the sidebar is a dock as wide as the right
dock's rail, as Illustrator's and Photoshop's panels collapse to icons: Spaces, its icon and name, its most urgent
state's dot at the corner, level with the right rail's first icon, and at its foot Settings and Add machine…, centered,
as the open sidebar's foot has them, Settings opening [Settings](#settings). Dragged more than 24 px wider, it opens
again as wide as it was, as the right dock's rail does. Its toggle is in its head, on the tab bar's line: at its end
while it is open, centred over the dock while folded, as the right dock's « over its rail; both say Collapse to icons
and Expand panels, and Cmd + B does what it does. The sidebar is open or a dock, never hidden: hidden by anything else,
it shows again at once. A press floats Spaces beside the dock, every time there, as tall as its list and the window's
room under it until the grip at its foot sizes it, which it keeps; its icon lit meanwhile and the keys in it: dragged by
its head, it stays where it is dropped until its icon again, Esc, its ×, a press beside it or the dock's Settings and
Add machine (which go on to their own) close it, or the sidebar opens.

## Chats

Chats, the four-point star at the tab bar's end, over the dock, its dot in the waiting color while chats wait on you (on
a question or a permission, in a pane or a chat tab, each once), their number in its tip, shows every chat of this Mac,
running or closed, as the TUI sidebar's Chats lists them: in the view's place, on the card, its filter taking the keys,
no tab shown, Chats lit. Chats again, Esc in the list or its filter (once the filter's words are cleared: Esc clears
them first), a tab or » brings the view back (More keeps it), and so does a chat opened from it. While the dock is a
rail, Chats floats the list beside it, as the rail's views float, lit meanwhile, and Chats again, Esc, its × or a press
beside it closes it. What is a row and what is not (a program's runs through the Agent SDK, the agents' helpers):
[Chats](usage.md#chats).

| Part | What it does |
|---|---|
| Filter | the words a chat's name, space or folder holds, `archived` for the archived ones; Cmd + Shift + R from anywhere opens the list with the keys here (the dock a rail: floating beside it), Enter opens the first one |
| A space | its chevron first (14, dim), its name, how many chats it holds muted at its end, no dot; its chats, the active tab's first, then the newest; a space with none is left out (so nothing shows `0` while the list is read); a chat whose folder has no space open stands under that folder's name, the newest folder first; a click folds or opens it, the shown space open by itself |
| A chat | its state's mark in herdr's colors (a closed one's a faint dot; a chat tab's blocked while it asks you something), its agent's icon and its name, then its agent's name (where the app draws no icon of it: `Claude`, `Codex`) and how long ago it changed, two right-aligned muted columns; a click goes to a running one (a chat tab's: its tab; one in a terminal: its pane), or reopens a closed one in a new tab of its space as Settings' Open agents in says: a Claude chat as a chat tab, resuming it, else its agent resuming it in a terminal (`claude --resume`, `codex resume`; Codex's always, until the chat draws Codex), and the list closes |
| Its right click | Open, Copy chat (all of it, as Markdown), Rename (in its row: Enter keeps it, as herdr's Rename pane names it), for a closed one Archive or Unarchive, and Delete…, the rarer one: asked in its row first (`Move to Trash?`, Cancel and Move, the chat's name staying beside them; Esc gives it up), then its row leaves at once and its file goes to the Mac's Trash, its archive mark and its name dropped; a running chat's Delete… is faint, its tip saying to close it first; elsewhere in the list, Show or Hide archived; while the list shows, More keeps it and lists `Show archived` first, ✓ while they are |

The archived ones and the names are the TUI's own, so either shows what the other changed. Unlike the TUI's, it copies a
chat as Markdown text, not formatted beside it, and archives one at a time. What it did (`Chat copied`, `Archived "Login
redirect fix"`, `Unarchived "…"`, `Moved to Trash`) or what went wrong (a Trash that did not take the file: its row is
back) stands under the list, as the TUI's last row has it: a done thing for four seconds, a failure until the next; no
row moves for it. A list that cannot be read says why where its first row will be.

## New chats

+ after the last tab (Cmd + N) starts an agent in the space's folder, the way Settings' Open agents in says, for every
way in alike (+, a closed chat reopened from Chats, Issues' To the agent, a new chat's agent list, a new space):

- Chat, the default: a new chat tab, named New chat until its first message names it. Nothing runs yet: New chat and
  `in <space> · <branch>` stand high up in its middle, the prompt at its foot with the agent's chip, the model chip
  and the mode chip in its bar, the agent used last that the chat draws (Claude). The agent's chip opens the agents
  upward, as a menu: a filter on top taking the
  keys (Enter picks the first), the installed agents only, the recent ones first, then the rest by name, one the chat
  cannot draw yet marked `terminal` (Codex, and every agent without an adapter), one signed out `sign in` in yellow;
  under a rule, dim, the ones not installed, each showing the [Agent](#agent) panel at how it installs (the space
  keeps its agent). Picking a `terminal` one opens its own CLI in a terminal tab of the space, what is typed its first
  message, in the chat's place; picking one to sign in shows the Agent panel as that agent's. The first message
  starts the agent with it, the model, mode, effort and Ultracode picked meanwhile at its start (`--model`,
  `--permission-mode`, `--effort`, Ultracode in its settings); until then the bar has no commands, terminal or
  context, which come with the agent.
- Terminal: the agent used last, its own CLI in a terminal tab of the space.

A new space (Spaces' +, a machine's, New space there, Files' New space on a folder, the palette's New space) starts its
agent so too: with Terminal, the agent's CLI as its first tab. With Chat, any space this layout shows on this Mac that
holds shells alone (one the app made, its own picker's + New space too, or an older one) gets an empty chat as its
first tab, shown, the first time it shows: once, so a chat closed stays closed and a space worked in terminals is left
alone. A home space, home's stand-in (a plain terminal in the home folder) and a space on another machine get none:
nothing starts there unasked.

The model chip in a chat's bar names the model and, dimmer, its effort (Opus 5.5 High); a press opens Claude's models
upward, as VS Code's Claude has them: each with its line (Default, the account's own, then Opus 5.5, Fable 5.2, Sonnet
5.5 and Haiku 5.5, as Claude Code lists them; one in use that it does not list on top), the one in use checked on the
accent's tint, a press picking one and closing the list. The mode chip beside it opens the Modes panel: Modes and its
hint, ⇧ + tab to switch, at its head, each of the agent's modes with its icon and its line (the one in use checked),
then Effort with a dot slider and the level's name at the row's end (a press or a drag picks the level), then Ultracode
with its switch, faint with Claude's reason as its tip where Claude refuses it. ↑ ↓ step either panel's rows, ← → the
level, Enter or Space picks or turns, Esc or a press beside closes it; ⇧ + tab in the prompt or the panel is Claude's
own next mode. A running chat sends `/model`, `/effort` and `/effort ultracode` (or `off`) to Claude, and the mode by
Claude's own shift+tab, as typed there, so Claude may keep the model and keeps the level as its defaults; Ultracode
stays the chat's (`herdr-fold.chat-switches`). Before Claude runs, the mode chip shows the mode Claude will start in:
`permissions.defaultMode` in its settings (the user's, the project's, then the local ones, the last that names one),
else Manual. In a narrow chat the context meter's words give way first, then the model chip's level (each tip says
it); narrower still the bar's tools leave whole from their end and the model's name is cut short, never the mode or
send. The rows are the agent's own: Codex, once a chat draws it, brings its own models, modes and levels and no
Ultracode.

The context meter in a running chat's bar, the ring and `context 34%` (the share in the ring's color: green, yellow from
50 %, red from 80 %), opens the Context panel upward: Context and how much is in use (68k of 200k · 34%); a bar of what
fills it with its legend in the Agent panel's colors: the rules Claude reads at the start, its skills' list and its
connectors' tools (estimated at four characters a token), and the rest, the chat and Claude's tools, as one part
(`Rules 6.0k`, `Chat & tools 40.0k`, by the number rule); under them Compact (`/compact`) and, at the end, `Show all
in Agent`, which shows the dock's [Agent](#agent) panel, where the rules, skills and connectors are listed. ↑ ↓ step
the buttons, Enter presses one, Esc or a press beside closes the panel. Over Compact it says what the chat cost, read
as the panel opens: `This chat ~$4.12 API value` (`spent` with an API key), a row a model with its color (`Opus 5.5
~$3.70`, `Haiku 5.5 · 1 subagent ~$0.42`; a model with no price says `no price`), then `1.2M tokens · 82% from
cache` and `Usage`, which shows the Agents tab's [Usage](harness.md#the-usage-view) with this chat's row marked.

Over the prompt a chat also says when an agent on an API key has spent 80% of the monthly budget you set for it, or
is on pace to pass it: `Codex has spent ~$45.10 of $50 this month · on pace for ~$58 by Nov 30` (core's words and
threshold, looked at every 5 minutes while the chat is in front). Its × closes it for that month, in both clients.

While Claude works through a task list (its task tools), a strip over the prompt is the list's one home. Folded, it is
a line: the step at work with a spinner and `3 of 5 done` at its end. A press opens it upward: the done steps folded
into one `3 done` row (a press lists them, faint), the step at work, then the ones to do, `after <step>` dim at the end
of one that waits for another; its head says Plan, with `Open the plan` once a plan is approved. It stays folded while
a card waits, and a finished list says `All 5 done` until the next message, then goes. The timeline tells only the
changes: `Tasks 5 added` (calls one after another one row) and a ticked line for each step done, never the list again.
A plan approved in plan mode is a step of its own, `Plan approved · 4 steps`, its `Open the plan` the strip's: the plan
as a document in the preview tab, copied into the chat's folder in herdr-fold's own state (`plan.md`, its owner's only).
Codex's list (its `update_plan`) comes to the same strip once a chat draws Codex; the TUI's Chats list shows it now.

The + at the bar's start opens the + menu upward (its first row lit: ↑ ↓ step the rows, Enter or Space acts, Esc or a
press beside closes it). `Upload from computer…` (⌘ U in a chat) opens macOS's own file chooser on the chat's folder,
several files at once; the files picked stand as chips over the prompt (the type's icon, the name, its path as its tip,
× takes one off) and go with the next message, after its words, each named as Claude reads a file: `@src/books.py`, from
the chat's folder when in it, `@"docs/error format.md"` quoted where it holds a space. `Add context…` types an "@" at
the text's end, and an "@" typed at a word's start does the same: a list opens over the prompt in the / menu's form, the
repository's changed files first (Changed), then the folder's files as a search walks them (Files, no ignored one), five
of each and how many more there are; what is typed after the "@" filters it, the best match first, and Enter or a press
puts the file's path in its place, a space after it (the app's text field tells no caret, so the "@" that counts is the
one at the text's end). Under a rule, Connectors: the failed ones and the ones to sign in counted on pills, `Manage`,
which shows the dock's [Agent](#agent) panel with Connectors open (their home: Connect, add, sign out), and each
connector on or off in this folder with its service's logo and a switch. A switch gives Claude its own `/mcp disable
<name>` or `/mcp enable <name>` in this chat: shown at once, sent once Claude is idle (a new chat's once its agent
runs), and the setup is read again as Claude writes it. The menu's two parts are the agent's: one that takes no files
has no first part, one whose connectors a chat does not switch no second.

The clock after the context meter (`This folder's chats`) shows the dock's [Chats](#chats) list, the chats' one
home, with this folder's group open and scrolled to; while the dock is a rail, the list floats beside it.

A "/" typed at the start of a running chat's prompt opens the / menu over the prompt, as Claude Code's own: This chat
(Export the chat…, once there is one), Skills (Lucide's scroll-text; those the chat used first, each with its line and
its source's tag), Claude's commands (`/compact` runs at once, `/review` waits in the prompt for its words), the first
five of each and how many more there are. What is typed after the "/" filters it into one list, the best match first (a
name's start, a word's, a name holding it, then a line), and lights it: Enter picks the lit row, ↑ ↓ step the rows, Esc
closes the menu until the text changes, as do a space and a press beside it; with nothing found it goes, and Enter sends
what is typed to Claude as it is (a command of Claude's the menu does not list, as `/init`). A skill goes into the
prompt as Claude takes it (`/api-routes`, a plugin's `/code-review:code-review`) for its words. The / button types the
"/" into an empty prompt; over a message it opens the menu as it is, and a command picked goes before the message.
Export the chat saves it as Markdown (Copy chat's, from Chats: its title, then each turn under who said it) where
macOS's save panel says, named after it in the chat's folder at first. In the timeline a skill's step names its source
after it, dim (Skill api-routes Project). The rules, the skills (the user's, the project's and the enabled plugins') and
the start mode come from `core/agent_setup.py`, which only reads them, as the chat opens, when it comes back in front
and as the Context panel or the / menu opens.

A connector's call in the timeline wears its service's logo (a server of no known service its letter on a tile) and its
name, then the tool's own name in the code font and the call's first words: `Google Drive search_files paging spec`.
When a server comes to need a sign-in during the conversation (Claude's session file lists it among the servers to sign
in to; the ones listed at the conversation's start are the Agent panel's alone), a step says so on the line: `Box needs
you to sign in`, its dot in the waiting color, Connect at its end. Connect runs the agent's own login as the Agent
panel's does (a terminal with no pane, your browser); the step says `signing in…` beside a spinner until it ends, Claude
is then asked about the server again (`claude mcp get`), and the step is done, `signed in`, once the server is on. Why a
sign-in could not start is said on the step, Connect still there.

A space on another machine starts its agents in a terminal there: a chat runs on this Mac for now. A running chat keeps
the way it opened when the setting changes; Chats lists both kinds as one list, each opening the way it runs. The
agents used last are the mod's own (`herdr-fold.agents-recent`, eight at most), apart from the TUI's.

## Settings

The sidebar's Settings (at its foot, open or folded) and Cmd + , open the one Settings, in a window over the app's,
always the same size (600 × 380): its sections at its left, the chosen one beside them. herdr-fold's come first,
General, Notifications and About; under Application, Look, Machines, Updates and Privacy each open the app's own
Settings at that section, as a mod cannot add a section there. Every change is in effect at once: there is no OK and
no Cancel.
It opens at the section looked at last; More's About herdr-fold opens it at About. ↑ and ↓ change the section; Tab steps
through the section's controls, a ring in the accent round the one it is on, and Enter or Space presses it; ×, Esc or a
click beside closes the window.
`herdr-fold.settings` opens it from a key or `herdr-app do`.

General has one setting, Open agents in: Chat (the default) or Terminal, for every way in alike
([New chats](#new-chats)); with Tab on it, ← and → choose too.

Notifications has An agent waits on you, On (the default) or Off: off, no note at the window's corner and no sound when
an agent asks or finishes; errors always show. herdr-fold's layout then names herdr-fold as its toast, which closes
every note at once (herdr-fold's own too, as an update's) but an error or a warning, which it draws as the app's own
toast (its icon or its level's dot, the title, the body's first line; a click runs its action and closes it), the app's
sounds are turned off (your own setting kept and given back when it is on again), and a chat's own wait is quiet. Under
it, Herdr app alerts opens the app's own Settings at Alerts, where its sounds are chosen.

About is as the TUI sidebar's About in herdr's popup and in the same words: herdr-fold's version and license (the
author's name a link to their GitHub page, from the mod's LICENSE); the update check's state, Up to date and when it
looked (at its time today, else on its day), or the newer version with how to get it, or Couldn't check (in the
error's color, with the time of the last look that answered), or Checked by hand only, a spinner while a look runs;
What's new (this version's part of the CHANGELOG in the preview tab) or a newer one's Release notes, and Check now
(GitHub asked at once); Check for updates automatically; Third-party notices (in the preview tab). While a newer
version is out, [the status bar](#the-status-bar) says so at its end, a press opening Settings at About; More has no
dot. After an update, one toast says Updated to herdr-fold X, a click on it opening What's new.

## The tab's terminal

Under herdr-fold, each tab has a terminal of its own, as in the TUI: it starts the first time the tab shows, in the
space's folder on its machine, with that machine's shell, and switching tabs switches it. Like the tab's own terminals,
it keeps running when the app quits, and ends when the tab closes; a shell that exits makes way for a new one. It has no
header of its own; one that could not start says why in its place. With the dock open it stands at the dock's foot, two
sevenths of its height at first and 120 px at least, and the boundary between the views and the terminal drags, as
the TUI's does; with the dock folded to its rail it stands under the tab, the centre's full
width, 240 px high at first, a card of its own 8 px under the tab's, the edge between them resizing it; a tab with no
terminal leaves the centre whole there, as the TUI shows nothing under its agent then, until one comes. The rail's
Terminal shows or hides it there, as the TUI's rail raises and lowers its terminal; its height and whether it shows stay
for the next fold, and the dock opened again takes it back to its foot.

## The title row

The window's top is a row of herdr-fold's own, 36 px across the whole window over the sidebar and the tab bar, on the
window's level with a hairline under it: on macOS the traffic lights sit in it, elsewhere the window's own buttons at
its end; dragging it moves the window, a double click maximizes it. At the window's centre the command field, the shown
space's name faint in it and the palette's key at its end as it is bound (Cmd + Shift + P unless rebound), opens
herdr-fold's command palette onto it: the field becomes the palette's field, 600 px wide on the same centre, 8 px under
the window's top (the nearest the app lets it come), and under it the app's commands, named and grouped as the app's own
palette has them (Tab, Pane, Space, Layout, Terminal, Agent, Window, App), each with its key at its end as it works in
this layout, the first lit. After them herdr-fold's own, in a group of its name: Settings…, the views (Files, Search,
Changes, Issues where the repository is on GitHub, Agent, Chats), Agents (the space's Agents tab), Show or hide the
dock, Restore panels, New chat (or the agent + would start), New space in a folder…, Add machine…, Open file from
output…, Color theme…, Styleguide,
Mark agent unread, Commit and push and Write commit message, each with its key where it has one. What you type finds
them all as the chat's / menu finds its rows, the best first: a name or command that starts so, then one with a word
that does, then one that holds it, then one whose other words do (`fullscreen` finds Zoom pane), each with its group.
Enter runs the lit one, ↑ ↓ move it, and Esc, a press beside it or the key again closes it; a command that needs a name
asks for it, as the app's does. In this layout the palette's key opens herdr-fold's palette in place of the app's, so
there is one. In a narrow window the field narrows, down to its mark alone. Under it, the sidebar's head has Herdr's
mark and name at its start, and Go to space or tab and its toggle at its end, on the tab bar's line.

## The status bar

The window's foot is herdr-fold's own status bar, where the app's was, as the mockups draw it: on the side's level under
a hairline, the shown space's machine (This computer, else its name) and branch, then its agents, a dot and their words:
those waiting on you first (`1 of 3 agents waiting for you`, the dot yellow), else those working (`2 agents working`,
the dot in the accent), else how many (`1 agent`, `2 agents`). While Herdr has an update ready, a quiet item stands at
its right end: a green dot and `Update ready: herdr-core 0.1.21`, a press updating herdr-core while the terminals keep
running (a spinner and `Updating herdr-core to 0.1.21…` meanwhile), or `Update ready: Herdr 0.1.16`, a press restarting
into it, herdr-core with it when it waits too; its tip says which. A herdr-core a package manager owns shows none (it
updates there). With neither ready, a newer herdr-fold stands there the same way, `herdr-fold 0.4.0 is out`: a press
updates nothing, it opens [Settings](#settings) at About, which says how. One item shows at a
time, in that order. This is the one place herdr-fold says it: the sidebar's Settings has no dot. The app's own
notice in the window's corner is Herdr's: a layout cannot turn it off, and its × closes it.

## Installing it

It needs the Herdr app, and Python 3 and git on the machine the space is on (Claude Code or Codex too, for the ✦, and
gh signed in to GitHub there, for Issues).

`./install.sh` sets it up: choose `2` (the Herdr app) or `3` (both) at its first question
([Installation](installation.md#the-tui-the-herdr-app-or-both)); where the app is not on the Mac yet, it offers the
app's own installer. It puts the mod, the layout, its themes and its keys in place and shows the layout in a running
app; an update closes a running app for that moment and opens it again, on the new version
([Run it again](installation.md#run-it-again)). An update of the TUI alone asks once, `Set up herdr-fold in the Herdr
app too?`, where the app is on the Mac.
`./uninstall.sh` takes it off again, alone or with the TUI, herdr-fold's settings in the app too: a running app closes
for that moment and opens again ([Uninstall](uninstall.md)).

Without the installer, from the herdr-fold folder:

```bash
python3 lib/herdr_app.py install .
herdr-app do layout.switch --name herdr-fold
```

The first puts the mod, the layout, its themes and its keys (the `layout:herdr-fold` section of `keys.json`) into the
app's home (`~/.config/herdr-app`, or `HERDR_APP_HOME`); run again after an update, it takes off what the earlier
version put there and this one no longer brings, and what the app kept of a part of the layout that is gone. Your own
layout stays as it was: Cmd + Shift + L switches between the layouts. To remove it all, switch to another layout, end
the terminals it started for tabs (`python3 lib/herdr_app.py end-terminals`), close the app (while it runs, it keeps
herdr-fold's settings and writes them back), then `python3 lib/herdr_app.py uninstall .`.

The `app/` folder is laid out as the app's home, the way the app's catalog of shared layouts takes one:
`app/RECIPE.md` is the brief another agent can build the layout from (what you see, how it behaves, what it is
built from, what to watch out for, when it is done), and `app/preview.png` is its picture.

Without the layout, herdr-fold also opens beside a terminal, as a pane of that tab:
`herdr-app do pane.split --direction right --mod herdr-fold`.

## Keys

The keys are in one table for both clients: [Keys](keybindings.md#the-herdr-app). In herdr-fold's layout the app
takes the TUI's keys, and a few are the app's own. Where a shared key does its work the app's way:

- Cmd + Shift + G, Cmd + Shift + I and Cmd + Shift + R open the dock on their view; while the dock is a rail, the
  view floats beside it.
- Cmd + Shift + C writes the message into Changes' field, and Commit says Commit & Push for this one commit: Enter
  commits and pushes, ✦ writes another, Esc cancels. With nothing to commit it offers to push the commits ahead.
- Cmd + Shift + E hides the dock entirely, open or its rail, and shows it again as it was; Cmd + Option + B stays
  the fold.
- Cmd + Shift + L lists the files the focused terminal's output names at the window's top, by the TUI's rules
  (core's `named_files.py`); a text file picked opens in its editor tab at its line. In this layout it takes the app's
  Next layout key, which stays in the palette.
- Cmd + S and Cmd + F are herdr-fold's while one of its views has the keys (`mod:herdr-fold` in `keys.json`): they save
  and find in the editor tab shown, and do nothing elsewhere.
- Cmd + K, then Cmd + T sets the app's theme, from herdr-fold's themes by the TUI's names.
- Ctrl + B, then Shift + N opens the Mac's folder picker, then the space there, its agent started as Spaces' + starts
  one.

The layout takes the app's own Cmd + 1…9 (its tabs), Cmd + T (a new tab: + and >_ after the tabs) and Cmd + D (Split
right: the palette); the app's other navigation keys stay as it has them.

The mod takes commands for keys of your own: `herdr-fold.commit-push`, `herdr-fold.write`, `herdr-fold.commit` and
`herdr-fold.sync`, and `herdr-fold.files`, `herdr-fold.changes`, `herdr-fold.search` and `herdr-fold.issues`, which show
that view (Search with the keys in its field), `herdr-fold.chats`, which opens Chats with the keys in its filter,
`herdr-fold.new-agent`, which starts an agent as + does, `herdr-fold.unread`, which marks the focused agent unread,
`herdr-fold.palette`, which opens or closes the command palette, `herdr-fold.new-space`, `herdr-fold.add-machine`,
`herdr-fold.column`, `herdr-fold.restore`, `herdr-fold.open-file` and `herdr-fold.theme`, the six commands the TUI has
too, `herdr-fold.agents`, which shows the space's [Agents](#agents) tab, `herdr-fold.usage`, which shows that tab's
[Usage](harness.md#the-usage-view), and `herdr-fold.settings`, which opens Settings; they reach a herdr-fold that shows,
and in its layout the tab bar hands a view's on to it, the view shown first. `herdr-fold.styleguide` opens the mod's
parts, each in each of its states, in a tab, an index of them at its side: [Styleguide](styleguide.md).

## On another machine

A space on another machine works the same: the git commands and the message writer run there, through the app's own
connection. `install.sh` (and `./machines.sh add` later) prepares each of herdr-fold's machines for the parts installed
and adds it to the app ([Remote machines](remote-machines.md)); one added in Settings → Machines works too, with git and
Python 3 there. The mod installs nothing there: it
carries its code and runs it with that machine's Python: `python3`, or on Windows the one herdr-fold's preparation
finds there (not the Store's alias). The message writer runs as a job of its own, so the app's connection ending does
not take it.

## Agent

The dock's fifth view: what the space's agent, Claude or Codex, starts with in the space's folder, as a design tool's
layers, with a form on each row that can be changed. Its sections, each edit and what it writes are in
[The agent's harness](harness.md#the-agent-panel), for both clients.

What is the app's own: the Agent tab carries a dot after its name, and the rail's Agent one on its corner, while the
setup has a problem, red for a server that failed, else yellow for one to sign in to. A chat's Context panel leads
here (`Show all in Agent` shows the panel as that chat's agent's, beside the rail while the dock is folded), and an
agent not installed, picked in a new chat's list, shows it at how it installs. The command palette's Agent shows it.

The picture is from before the panel's redesign: its head, sections and tags are as that page says.

![A chat at work in lumen-api: Claude's two edits of tests/test_books.py open in the timeline, then git diff --stat,
the prompt queuing a message while Claude works; beside it the Agent panel: Claude on Max, its 5 hours at 64% and the
week at 38%, Codex's month against its budget, the project's rules and permissions with its mode, Edit
automatically](../assets/screenshots/app-chat.webp)

## Agents

A tab of the main area, one a space, under Lucide's share icon, with two views its head switches at its right end:
Graph, how the space's agent is wired in the folder, and Usage, what the agents used and what that cost. Both are in
[The agent's harness](harness.md#the-graph), with [the Usage view](harness.md#the-usage-view). The palette's Agents
opens the tab on its graph and the Agent panel's `Show in graph` on a row's node; the palette's Usage, the panel's
Open Usage and a chat's `Usage` open it on Usage; opened again, the same tab is shown.

The two pictures are from before the redesign (the switch says `This chat` now, the gates read `allow pytest`, and
`Budget…` stands on the month's card).

![The Agents tab's graph, Wiring: Claude in lumen-api, Edit automatically, between the project's CLAUDE.md, AGENTS.md
and three skills on the left and Read · Edit · Write and Bash with their allow, ask and deny gates, and the project's
github, linear and sentry behind an ask, on the right](../assets/screenshots/app-agents-graph.webp)

![The Agents tab's Usage, seven days of all spaces: Claude on Max as API value, Codex on an API key spent with
November against its $150 budget, 35.3M tokens, per day by model, the month's line and pace, and by
project](../assets/screenshots/app-agents-usage.webp)

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
- Chats reads the files Claude Code and Codex keep their chats in on this Mac (`~/.claude/projects`,
  `~/.codex/sessions`), and never writes them; a rename goes where herdr's Rename pane keeps names, the archived ones
  beside the TUI column's settings. Delete… alone moves one: a closed chat's own file, to the Trash, once you answer
  its question: [A chat you delete](../SECURITY.md#a-chat-you-delete). A closed one reopens only by an id that is one
  (letters, digits, `.`, `_`, `-`): read from a file, it is never taken for an option or a control code.
- Agent reads the agent's own files as text, and writes one of its settings files only on a form's Save, one key at
  a time; every other change is the agent's own command, run on your press. It starts no server and keeps no token:
  [What it reads and writes](harness.md#what-it-reads-and-writes).
- An SVG or a page is drawn with nothing asked of the network and none of its scripts run, so a file cannot learn who
  opened it.
- The mod itself sends nothing anywhere but two daily looks, each the request alone: for a newer herdr-fold
  (api.github.com) and for the model prices Usage's costs are counted with (LiteLLM's public table,
  raw.githubusercontent.com), both switched in herdr-fold's Settings, under About. The sync talks to the
  repository's remote, gh to GitHub, the AI tool to its own service.
