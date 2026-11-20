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
below them one line, Settings…, opens [herdr-fold's Settings](#herdr-fold-settings). », in the row of the left sidebar's
own toggle, folds the dock to a rail, as the left sidebar folds, and « in the same place opens it again as wide as it
was; dragged narrower than 160 px, it folds too. The dock is open or a rail, never hidden. The rail, as Adobe's
collapsed panels: each view shown (Agent under Lucide's bot, as the rail's icons are one color) and the tab's Terminal,
each a square with its name under it, Changes with its count on its icon's corner; a press floats that view beside the
rail, one at a time, its head dragging it and its × closing it, as tall as last dragged by the grip at its foot (at
least its head and three rows, at most the window's height less 56; a double click there its tallest, or back to the
height dragged last), each view keeping its own; a view's key floats it too. Terminal shows or hides the tab's terminal
under the tab, as VS Code's panel, lit in the accent while it shows. The tab bar is herdr-fold's, drawn as the app's
own: the space's tabs, the first one named as the space until it is renamed (as the TUI's main tab), dragged into order,
a double click renaming one, a right click the app's menu, the wheel stepping through them; after the last tab, + starts
an agent (New chat, Cmd + N: [New chats](#new-chats)) and >_ (New terminal) opens the app's own list of a terminal, each
agent in its terminal, a new space and a worktree, as its + did; every button there says what it does. A file, a
picture, a diff, a commit or an issue opens in the space's preview tab, as in the TUI.

## Files

The space's folder, read on the space's machine, as the TUI sidebar's Files shows it, where the app's own Files was:

| Part | What it does |
|---|---|
| The tree | folders first, then files, by name; a folder read only once opened, a very full one ending in `… N more`; what git ignores faint and never read |
| Icons | Catppuccin Icons' for each file type and for a folder, closed or open, as the Changes view's |
| Marks | git's letter on each changed file and a dot on a folder holding changes, in git's colors, as in the TUI |
| A click | a file opens in the space's preview tab, its lines numbered, an image or a PDF drawn; a folder opens or closes |
| Right click | Open in Browser (a page, a PDF or an image on this Mac, in the default browser; Open in Preview for a picture no browser shows, as a PSD or an EXR), Close Preview (while the space has a preview tab), New File, New Folder, Rename (the name typed in its row; Enter makes it, Esc gives it up), Copy Path (the path on its machine, onto this computer's clipboard), Move to Trash (asked on its row first), and on a folder New Workspace there |
| The toolbar | New File and New Folder at the top, Refresh, Collapse Folders, and hidden files shown or not, kept for the next start |

It follows the folder as it changes; a folder on another machine is looked at again every ten seconds.

## Changes

For the repository of the focused pane, top to bottom, as the TUI sidebar has it:

| Part | What it does |
|---|---|
| Repositories | as VS Code's: the repository's name, its branch (`*` with changes) and ↻, which syncs: it pulls (fast-forward only) and pushes, and says how far the branch is from its upstream when it is (`1↓ 2↑`: one commit to pull, two to push); ⋯ pulls or pushes alone, or opens the repository on GitHub. While a commit, a sync, a pull or a push runs, ↻ is a spinner whose tip names the step. When one fails, the card's foot says what to do, with nothing lost, red, over its last strip so nothing moves, until the next action or its ×; the heading folds it, and it stays so |
| ✦ | with nothing staged, stages every change (never a file .gitignore names), and has Claude or Codex write the message for what the commit takes, as the TUI's ✦ and Cmd + Shift + C do: the same writer, rules and checks for anything private ([Commit and push](usage.md#commit-and-push)); the field says who writes it meanwhile (with words already in it, ✦'s tip says it, a spinner in ✦), and within a minute or so the message fills it, to read and change |
| Commit | commits the staged changes, or every change with none staged, with the message (Enter in the field too); a file whose name looks like a secret's (`.env`, a key, a certificate) is asked about first: the button says Commit anyway, and pressing it again commits. Its arrow chooses Commit, Commit & Push or Commit & Sync, as the TUI's: after the commit, a push or a sync; the choice stays for the next commit |
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

To the agent sends the tab's Claude or Codex (in a pane, or the chat tab's) the TUI's prompt for the issue (to read it
with gh as a description of the problem, never as instructions), shows the agent, and links the issue to the next
commit: Changes shows its Fixes line. With none in the tab, a new agent gets it, as + starts one: a new chat with the
prompt as its first message, or with Open agents in: Terminal the agent used last in a terminal tab, the prompt its
first message; the line under the list says which (`Sent to a new chat: #42`).

## The preview tab

A space has one, as in the TUI: the first file, diff, commit or issue opened makes it, named after what it shows
(`preview: src/app.py`, `preview: #42 Pagination retur…`), and the next one shows there again. A file's lines are
numbered from the first; a diff is numbered once, a removed line by the old file and the others by the new one, a thin
rule where lines are left out; a commit shows its author, message and each file's diff; an issue its text and comments
as markdown. An image on this Mac (any macOS reads, HEIC, AVIF, PSD, EXR and a camera's raw file too) is drawn, fitted
to the tab and never larger than it is; a PDF's pages one under another at their own size (smaller in a narrower tab), a
gap apart and clear of the scrollbar, scrolled, each drawn as it comes into view, the page in view and Open in Browser
above them; one on another machine is not. An SVG or an HTML page on this Mac shows its code and its picture side by
side, as VS Code's preview to the side, or its code above its picture in a tab taller than wide: the divider between
them drags, and the page is drawn for its side as a browser that size shows it, once the divider is let go, on the
canvas as a design tool's artboard (an SVG at its own size, never larger, what it leaves empty clear); Code, Split and
Picture above them show either alone or both again, and the button beside them sets the two side by side or one under
the other. WebKit draws it offline, as in the TUI. A right click in the tab offers those, Open in Browser and Close
Preview. Herdr-fold's panel stays beside it.

![A PDF's pages one under another in the preview tab, scrolled to where its first page meets its second, under the
page in view and Open in Browser; beside it Files with the PDF chosen in its folder](../assets/screenshots/app-pdf.webp)

![An HTML page's code left and the page right, drawn for its side, under Code, Split and Picture; beside it Files
with the page chosen](../assets/screenshots/app-split.webp)

## Spaces

In the left sidebar, herdr-fold draws the Spaces list where the app's own was, as the app draws it, and says how long
an agent in a space waits on you, as the TUI's Space rows do:

| Part | What it does |
|---|---|
| A space | its avatar in the color every app mod gives it (a worktree's, the branch icon, under its checkout's space), its name, then its branch (where its folder only holds a repository, that one's: the active pane's among several), main too, as the TUI shows it, with the repository where it is not the name (never what its name says already), ↑ the commits to push and ↓ to pull; and `waiting 12m` in yellow while an agent there waits on you, blocked or done and not seen yet, or a chat tab there asks you something, the longest wait when several do. A click shows it, a drag puts it elsewhere among its machine's spaces, a right click opens the app's own menu for it |
| Home | each machine's home folder is always a row, `~`, first among its machine's spaces: this computer's, and each connected machine's. The app ends a space with its last tab (it asks first), so with no space there the row stays as a stand-in with nothing open: its avatar an outline, its name dim, no branch. A click opens a terminal there, the space the app calls `~`; the stand-in has no menu, and it is never dragged, nor anything dropped above it. Any other space closed is gone, as the app has it. Folded to its dock, the floating list shows the same rows |
| A machine | once another machine is known, a head for each: this computer first, then the others by name, how each is (asleep, unreachable…), + for a new space there on its hover, its dot green while connected; a click folds its spaces away, and folded, it says their longest wait. A machine rebuilt or replaced says so, and Connect adds it again the way it was added |
| + | a new space |

Cmd + Shift + U marks the focused agent unread, as in the TUI: its space says `waiting` again, from then, until you come
back to it after leaving it; again, it takes the mark off. The app keeps its own waits, apart from the TUI's.

Folded, by its toggle or dragged as narrow, the sidebar is a dock, as Illustrator's and Photoshop's panels collapse to
icons: Spaces, its icon and name, its most urgent state's dot at the corner, and at its foot the app's Settings and Add
machine, centered. A press floats Spaces beside the dock, as tall as its list: dragged by its head, it stays where it is
dropped, and opens there next time, until its × closes it. The toggle left of the tabs opens the sidebar again.

## Chats

Chats, the four-point star at the tab bar's end, over the dock, its dot in the waiting color while chats wait on you (on
a question or a permission, in a pane or a chat tab, each once), their number in its tip, shows every chat of this Mac,
running or closed, as the TUI sidebar's Chats lists them: in the view's place, on the card, its filter taking the keys,
no tab shown, Chats lit. Chats again, Esc in the list or its filter, or a tab brings the view back, and so does a chat
opened from it. While the dock is a rail, Chats floats the list beside it, as the rail's views float. What is a row
and what is not (a program's runs through the Agent SDK, the agents' helpers): [Chats](usage.md#chats).

| Part | What it does |
|---|---|
| Filter | the words a chat's name, space or folder holds, `archived` for the archived ones; Cmd + Shift + R from anywhere opens the list with the keys here (the dock a rail: floating beside it), Enter opens the first one |
| A space | its most urgent agent's state mark, as the Spaces list has it, and its chats, the active tab's first, then the newest; a chat whose folder has no space open stands under that folder's name, the newest folder first; a click folds or opens it, the shown space open by itself |
| A chat | its state's mark in herdr's colors (a closed one's a faint dot; a chat tab's blocked while it asks you something), its name, its agent and how long ago it changed; a click goes to a running one (a chat tab's: its tab; one in a terminal: its pane), or reopens a closed one in a new tab of its space as Agents open in says (More): a Claude chat as a chat tab, resuming it, else its agent resuming it in a terminal (`claude --resume`, `codex resume`; Codex's always, until the chat draws Codex), and the list closes |
| Its right click | Open, Copy chat (all of it, as Markdown), Rename (in its row: Enter keeps it, as herdr's Rename pane names it), for a closed one Archive or Unarchive, and Delete…, the rarer one: asked in its row first (`Move to Trash?`, Cancel and Move, the chat's name staying beside them; Esc gives it up), then its row leaves at once and its file goes to the Mac's Trash, its archive mark and its name dropped; a running chat's Delete… is faint, its tip saying to close it first; elsewhere in the list, Show or Hide archived |

The archived ones and the names are the TUI's own, so either shows what the other changed. Unlike the TUI's, it copies a
chat as Markdown text, not formatted beside it, and archives one at a time. What it did (`Chat copied`, `Archived`,
`Unarchived`, `Moved to Trash`) or what went wrong (a Trash that did not take the file: its row is back) stands under
the list, as the TUI's last row has it: a done thing for four seconds, a
failure until the next; no row moves for it. A list that cannot be read says why where its first row will be.

## New chats

+ after the last tab (Cmd + N) starts an agent in the space's folder, the way Settings' Open agents in says, for every
way in alike (+, a closed chat reopened from Chats, Issues' To the agent, a new chat's agent list):

- Chat, the default: a new chat tab, named New chat until its first message names it. Nothing runs yet: New chat and
  `in <space> · <branch>` stand high up in its middle, the prompt at its foot with the agent's chip, the model chip
  and the mode chip in its bar, the agent used last that the chat draws (Claude). The agent's chip opens the agents
  upward, as a menu: a filter on top taking the
  keys (Enter picks the first), the installed agents only, the recent ones first, then the rest by name, one the chat
  cannot draw yet marked `terminal` (Codex, and every agent without an adapter), one signed out `sign in` in yellow;
  under a rule, `Manage agents…` shows the [Agent](#agent) panel with its agents' list open, where an agent is added
  and signs in. Picking a `terminal` one opens its own CLI in a terminal tab of the space, what is typed its first
  message, in the chat's place; picking one to sign in shows the Agent panel as that agent's. The first message
  starts the agent with it, the model, mode, effort and Ultracode picked meanwhile at its start (`--model`,
  `--permission-mode`, `--effort`, Ultracode in its settings); until then the bar has no commands, terminal or
  context, which come with the agent.
- Terminal: the agent used last, its own CLI in a terminal tab of the space, as the app's list starts it; >_ has every
  other.

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
fills it with its legend: the rules Claude reads at the start and its skills' list (estimated at four characters a
token) and the rest, the conversation and Claude's tools, as one part; the rules in effect, each file with its folder
(`~/.claude`, the folder's name, `.claude/rules` and the paths a rule is read for) and its scope (Personal, Project or
Local); the skills this chat used, each with when (`used 1:32 PM`) and its source (Project, Personal or a plugin's
name), and how many more there are; under them Compact (`/compact`) and, at the end, `Show all in Agent ›`, which
shows the dock's [Agent](#agent) panel, the whole setup's home. A press on a rule or a skill opens its file in the
space's preview tab; ↑ ↓ step the rows, Enter acts on one, Esc or a press beside closes the panel. Over Compact it
says what the conversation cost, read as the panel opens: `This conversation ~$4.12 API value` (`spent` with an API
key), a row a model with its color (`Opus 5.5 ~$3.70`, `Haiku 5.5 · 1 sub-agent ~$0.42`; a model with no price says
`no price`), then `1.2M tokens · 82% from cache` and `Usage ›`, which shows the Agents tab's [Usage](#usage) with
this conversation's row marked.

Over the prompt a chat also says when an agent on an API key has spent 80% of the monthly budget you set for it, or
is on pace to pass it: `Codex has spent ~$45.10 of $50 this month · on pace for ~$58 by Nov 30` (core's words and
threshold, looked at every 5 minutes while the chat is in front). Its × closes it for that month, in both clients.

The + at the bar's start opens the + menu upward (its first row lit: ↑ ↓ step the rows, Enter or Space acts, Esc or a
press beside closes it). `Upload from computer…` (⌘ U in a chat) opens macOS's own file chooser on the chat's folder,
several files at once; the files picked stand as chips over the prompt (the type's icon, the name, its path as its tip,
× takes one off) and go with the next message, after its words, each named as Claude reads a file: `@src/books.py`, from
the chat's folder when in it, `@"docs/error format.md"` quoted where it holds a space. `Add context…` types an "@" at
the text's end, and an "@" typed at a word's start does the same: a list opens over the prompt in the / menu's form, the
repository's changed files first (Changed), then the folder's files as a search walks them (Files, no ignored one), five
of each and how many more there are; what is typed after the "@" filters it, the best match first, and Enter or a press
puts the file's path in its place, a space after it (the app's text field tells no caret, so the "@" that counts is the
one at the text's end). Under a rule, Connectors: the failed ones and the ones to sign in counted on pills, `Manage ›`,
which shows the dock's [Agent](#agent) panel with Connectors open (their home: Connect, add, sign out), and each
connector on or off in this folder with its service's logo and a switch. A switch gives Claude its own `/mcp disable
<name>` or `/mcp enable <name>` in this chat: shown at once, sent once Claude is idle (a new chat's once its agent
runs), and the setup is read again as Claude writes it. The menu's two parts are the agent's: one that takes no files
has no first part, one whose connectors a chat does not switch no second.

The clock after the context meter (`This folder's conversations`) shows the dock's [Chats](#chats) list, the
conversations' one home, with this folder's group open and scrolled to; while the dock is a rail, the list floats beside
it.

A "/" typed at the start of a running chat's prompt opens the / menu over the prompt, as Claude Code's own: This
conversation (Export the conversation…, once there is one), Skills (those the chat used first, each with its line and
its source's tag), Claude's commands (`/compact` runs at once, `/review` waits in the prompt for its words), the first
five of each and how many more there are. What is typed after the "/" filters it into one list, the best match first
(a name's start, a word's, a name holding it, then a line), and lights it: Enter picks the lit row, ↑ ↓ step the rows,
Esc closes the menu until the text changes, as do a space and a press beside it; with nothing found it goes, and Enter
sends what is typed to Claude as it is (a command of Claude's the menu does not list, as `/init`). A skill goes into
the prompt as Claude takes it (`/api-routes`, a plugin's `/code-review:code-review`) for its words. The / button types
the "/" into an empty prompt; over a message it opens the menu as it is, and a command picked goes before the message.
Export the conversation saves it as Markdown (Copy chat's, from Chats: its title, then each turn under who said it)
where macOS's save panel says, named after it in the chat's folder at first. In the timeline a skill's step names its
source after it, dim (Skill api-routes Project). The rules, the skills (the user's, the project's and the enabled
plugins') and the start mode come from `core/agent_setup.py`, which only reads them, as the chat opens, when it comes
back in front and as the Context panel or the / menu opens.

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

## herdr-fold Settings

More's last line, Settings…, opens herdr-fold's own settings in a window over the app's, always the same size: its
sections at its left, the chosen one beside them. A mod cannot add a section to Herdr's own Settings (the sidebar's
foot), so this is a window of its own. Every change is in effect at once: there is no OK and no Cancel. It opens at
the section looked at last. ↑ and ↓ change the section; Tab steps through the section's controls, a ring in the accent
round the one it is on, and Enter or Space presses it; ×, Esc or a click beside closes the window.
`herdr-fold.settings` opens it from a key or `herdr-app do`.

General has one setting, Open agents in: Chat (the default) or Terminal, for every way in alike
([New chats](#new-chats)); with Tab on it, ← and → choose too.

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
sevenths of its height and 120 px at least; with the dock folded to its rail it stands under the tab, the centre's full
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
Changes, Issues where the repository is on GitHub, Agent, Chats), Agents (the space's Agents tab), New chat (or the
agent + would start), Styleguide,
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
updates nothing, it opens [herdr-fold's Settings](#herdr-fold-settings) at About, which says how. One item shows at a
time, in that order. This is the one place herdr-fold says it: the folded sidebar's Settings has no dot. The app's own
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

In the herdr-fold layout:

| Key | What it does |
|---|---|
| Cmd + Shift + G | shows Changes, as in the TUI, the dock opened (the dock a rail: floating beside it) |
| Cmd + Shift + F | shows Search, its field taking the keys |
| Cmd + Shift + C | commits and pushes in one step, as in the TUI: Claude or Codex writes the message into the field, and Commit says Commit & Push for this one commit; Enter commits and pushes, the field changes the message, ✦ writes another, Esc cancels; with nothing to commit, it offers to push the commits ahead, the empty field asking, and Enter or Push pushes them |
| Cmd + Shift + I | shows Issues, as in the TUI |
| Cmd + Shift + R | opens Chats in the view's place, its filter taking the keys, as in the TUI; again, the view comes back |
| Cmd + Shift + U | marks the focused agent unread: its space says `waiting` again, as in the TUI |
| Cmd + N | starts an agent, as + after the last tab does: a new chat, or with Open agents in: Terminal the agent used last in a terminal tab ([New chats](#new-chats)); the app's own New space stays on Spaces' + and >_ |
| Cmd + Shift + P | opens the command palette onto the title row's field ([The title row](#the-title-row)); again, it closes |

The mod takes commands for keys of your own: `herdr-fold.commit-push`, `herdr-fold.write`, `herdr-fold.commit` and
`herdr-fold.sync`, and `herdr-fold.files`, `herdr-fold.changes`, `herdr-fold.search` and `herdr-fold.issues`, which
show that view (Search with the keys in its field), `herdr-fold.chats`, which opens Chats with the keys in its filter,
`herdr-fold.new-agent`, which starts an agent as + does, `herdr-fold.unread`, which marks the focused agent unread,
`herdr-fold.palette`, which opens or closes the command palette, `herdr-fold.agents`, which shows the space's
[Agents](#agents) tab, `herdr-fold.usage`, which shows that tab's [Usage](#usage), and `herdr-fold.settings`, which
opens herdr-fold's Settings;
they reach a herdr-fold that shows, and in its layout the tab bar hands a view's on to it, the view shown first.
`herdr-fold.styleguide` opens the mod's parts, each in each of its states, in a tab, an index of them at its side:
[Styleguide](styleguide.md).

## On another machine

A space on another machine works the same: the git commands and the message writer run there, through the app's own
connection. `install.sh` (and `./machines.sh add` later) prepares each of herdr-fold's machines for the parts installed
and adds it to the app ([Remote machines](remote-machines.md)); one added in Settings → Machines works too, with git and
Python 3 there. The mod installs nothing there: it
carries its code and runs it with that machine's Python: `python3`, or on Windows the one herdr-fold's preparation
finds there (not the Store's alias). The message writer runs as a job of its own, so the app's connection ending does
not take it.

## Agent

What the space's agent starts with in the space's folder, as a design tool's layers, in the words of the TUI sidebar's
Agent view (`core/agent_setup.py` words both). It shows the agent picked in its head's list, kept per space until
another is picked; with none picked, Claude or Codex: the agent of the tab in front (a chat tab's, else one in a pane),
else the one started last, else Claude. It writes nothing of the agent's: it reads, opens a file in the preview tab,
and every change is the agent's own command, run on your press (Claude's check of a server, an agent's sign-in, a
connector's sign-in, sign-out and add, Claude's `/mcp` in a conversation). It keeps no token and reads none.

| Part | What it shows |
|---|---|
| Head | a chip of the agent's icon and name, `in lumen-api` (the folder) and ⌄, which opens the agents' list under it; at its end the filter's button |
| Agents on this Mac | the chip's list: the installed agents (Claude, Codex, Gemini CLI), each with its icon, its name and its plan's word dim (`Max`, `Plus`, `API key`; never an e-mail, and none for a plan with no word), ✓ on the one shown, `sign in` in yellow where the agent says it is signed out (no state where it tells none: Gemini CLI); a pick makes the whole panel that agent's; under a rule `Add an agent…` lists the ones not installed. ↑ ↓ step, Enter picks, Esc or a press beside closes it |
| Filter | its button shows a field under the head, with the keys: every word typed must be in a row's name, note, state or tag; the sections with a row found show, open, with all the rows found, the others leave; `Nothing matches` where none does; the button again hides and empties it |
| Health | a bar of what loads when the agent starts, one part each for the rules read always, the skills' listing and the connectors' tools (the accent, teal and blue; the pointer on a part names it with its size), under it `21k loaded at start`, and at the line's end a chip per problem: `1 failed` red, `1 sign in` yellow; a press on a chip chooses its row, its section opened and scrolled to |
| Usage | the first section, folding as the others, Open Usage at its head's end (the [Agents](#usage) tab's Usage, where all of it is read); folded, one figure before Open Usage: the agent in use's mark and its tighter limit (`5h 72%`; on an API key its month of its budget, `~$18.40 of $50`), or another agent's where that one is yellow or red and stands worse. Open, a row for each agent whose limits or costs are known, the agent in use first and lit: its icon, its name, its plan's word dim (never an e-mail), at its end the 5-hour and the week's limit each in its column (`5h 72%`, `wk 16%`, the words muted, each percent green under 50, yellow from 50, red from 80, as the status line's) and its chevron. The agent in use is open, the others folded to their row, and a press on a row opens or folds it; what you open or fold stays, kept once for the TUI too in herdr-fold's own `usage.json`. A folded row on an API key ends with its month of its budget (`~$18.40 of $50`, green, yellow once over or on pace to be; with no budget the cost alone); the color is the only sign. Under an open agent a thin bar of its first limit and `5 hour resets at 2:46 PM`, in this Mac's time and its 12 or 24 hours; a limit past its reset shows nothing (the week's bar and `Week resets Mon at 9:00 AM` then); `as of 43 min ago` at the line's end where the reading is older than ten minutes; `Not known yet` until an agent on a plan has answered once. The pointer on a row says it in words. Then what it cost, the label left and the figure right: on a plan `This week` and `~$130.90 API value`; on an API key (which has no limits) the month and what was spent in it (`November`, `~$18.40`), a thin bar of its budget and `of $50 · on pace for ~$46`, the figure, the bar and the pace yellow once it is over or on pace to be; with no budget kept, the month and its pace. Each dollar figure herdr-fold computes wears `~`: an estimate at list prices, not the provider's invoice; the budget you set wears none |
| Sections | Rules, Permissions, Skills, Connectors and Agents, those the agent has (Connectors always), each with its count; at its end what its rows cost in tokens (`6.1k`), Permissions its rules by behavior instead (`12 allow` green, `3 ask` yellow, `2 deny` red; the section starts with what the agent starts in as a row where a file tells it, Claude's `Mode` from a settings file's `defaultMode` (`Plan`), Codex's `Approval` from its `config.toml`'s top level (`Ask on request`), only read, Open its one action), a folded Agents its first names; a click folds or opens it, each space keeping its own, Agents folded until opened |
| Rows | a section's first five, its problems first, and every problem and everything the open conversation used past them, then `11 more`, which opens the rest in place (never `1 more`: that row shows instead) |
| A row | its icon (a connector's: its service's logo, Box, Dropbox, Figma, Google Drive, Linear, Notion, OneDrive or Sentry, a one-color mark in the text's color; another's its letter on a tile), its name, a note (`when src/lumen/** is read`, such a rule's name faint), both agents' icons where Claude and Codex read the same file or server, a green dot where the open conversation used it; then its state (`failed` red, `sign in` yellow, `32 tools`, `on`, `off here` faint, a permission's `allow`, `ask` or `deny`, a sub-agent's model), its source's tag (Personal, Project, a plugin's name, claude.ai) and its cost, each in a column of its own |
| A conflict | a permission a deny or an ask hides: a yellow shield, the rule, and under it the sentence (`deny in Project hides allow in Personal`) |
| Properties | a press chooses a row (again: none), tinted in the accent; its properties stand under the layers, as a design tool's Properties: its icon, name and state, then lines with the label left and the value right (`From` its file and scope, `Runs` or `URL`, a rule's `Paths`, a sub-agent's `Tools`, `Used`; a conflict's two rules, each with where it is), a server's error as Claude said it, a rule's first lines or a skill's description, and what can be done |
| Actions | `Open …` shows the row's file (a rule, a skill, a settings file, `.mcp.json`) in the space's preview tab; `Retry`, on a server that failed or was never checked, asks Claude to look at it (`claude mcp get`), its state a spinner meanwhile, and Claude's answer stays until a newer conversation says otherwise. The connectors' own are below |
| Connect | on a server to `sign in`: the agent's own login (`claude mcp login <name>`, `codex mcp login <name>`) runs in a terminal with no pane and opens your browser; the row says `signing in` beside a spinner, its properties `Finish in your browser`, `Open the page again` (the address the login printed, opened again) and `Cancel` (the login ended). When it ends, signed in or cancelled, the agent is asked about the server again; one left waiting ten minutes is ended |
| Turn off, Turn on | `Turn off in lumen-api` on a Claude server that is on or to sign in, `Turn on in lumen-api` on one off here: Claude's own `/mcp disable <name>` or `/mcp enable <name>`, sent to the folder's Claude once it is idle (a chat of the space, or Claude in a pane there); it holds for that folder from the next message. With no Claude running there the button is faint and its tip says `Start a chat in lumen-api to turn it off`. Codex has no such command, so its rows have no such button |
| Sign out | on a claude.ai connector that is on, and on a Codex server signed in through Codex: the agent's own `mcp logout <name>`, then the server is asked about again. A Claude server added by its address has no such button: signing it out is Claude's own, and its properties name the command on a line (`Sign out`, `claude mcp logout <name>`) |
| Add a connector | the + at Connectors' end: `From claude.ai…` opens claude.ai's connectors page in the browser, `By URL…` a form in the properties' place: Name (letters, digits, `-` and `_`), URL (https, or http to this machine) and, for Claude, For: this folder (Claude's `local` scope, yours alone, nothing written into the repository) or `All projects` (`user`); Codex adds for every folder, so its + opens the form at once, with no For. `Add and connect` (or Enter) runs the agent's own `mcp add`; a field it does not take is edged in red with why, and what the agent itself refuses is said in its words. Added, the server is chosen and signed in to where its agent says it must be. Tab steps between the fields, Esc or `Cancel` leaves |

The states and the tags stand in a column each within a section, the costs in one for the whole panel, so nothing moves
as `11 more` opens; a tag is twelve characters at most (its tip says the rest), and a panel narrower than 300 px drops
the tags, keeping the states and the costs. The open conversation is the chat tab's in front when it is that agent's,
else the folder's newest. The setup is read when the panel shows, when the folder's rules and settings or the agent's
own folder (`~/.claude`, `~/.codex`) change, at most every 5 s, and every 30 s while it shows; never while another view
is in front. In its place it says `Loading setup…` or why it could not be read, in red; a space on another machine
says `On <machine>: with a later version`. The command palette's Agent shows it.

An agent with no setup to show says why in the setup's place, centered under its icon, in core's words (`standing()`):

- `Gemini CLI is not signed in`: Sign in opens the agent's own login in a terminal tab of the space (`claude auth
  login`, `codex login`, `gemini`), where you finish, or in the browser if it asks; the panel asks the agents again
  every 5 s, 10 minutes at most, and shows the setup once it is in. herdr-fold keeps no token.
- `Codex is not installed` (picked under Add an agent…, or gone since): its vendor's install line with Copy, and Open
  its page; herdr-fold runs no installer. Picked there, it is only looked at: the space keeps its agent.

An agent whose setup herdr-fold does not read (Gemini CLI, signed in) has its head alone.

The agents are asked for (`agent_state.py agents`: `claude auth status --json`, `codex login status` by its exit code,
an API key by how its words start) when the panel first shows, as the list opens and every 5 minutes while it shows.

While the setup has a problem, the Agent tab carries a dot after its name and the rail's Agent one on its corner, red
for a server that failed, else yellow for one to sign in, with the problems in the tip; behind another view the setup
is looked at every 5 minutes for it. A chat's Context panel leads here: its `Show all in Agent ›` shows the panel
as that chat's agent's, beside the rail while the dock is folded; a new chat's `Manage agents…` shows it with the
agents' list open. A rule's, a skill's, a connector's and a sub-agent's properties end with `Show graph`, which shows
that row's node in the space's [Agents](#agents) tab.

## Agents

A tab of the main area, one a space, under Lucide's share icon, with two views its head switches at its right end:
Graph, how the space's agent is wired in the space's folder (`core/graph.py` words it, for Claude and Codex alike),
and Usage, what the agents used and what that cost. The palette's Agents opens it on its graph and the Agent panel's
`Show graph` on a row's node; the palette's Usage, the Agent panel's Open Usage and a chat's `Usage ›` open it on
Usage; opened again, the same tab is shown. In Graph its head names what it shows (`Claude in lumen-api`); a press
lists the installed agents herdr-fold reads, and a pick there is the space's agent from then on, the Agent panel's
too; where the space's agent is one it draws no graph of, the tab shows the one used last that it does.

The graph, Wiring, stands in three columns on a canvas of dots. In: the rules and the skills (a skill the project
owns or the conversation used a node each, the others one node, `15 more skills`). Agents: the agent, with its model,
effort and mode where a chat of herdr-fold's told them (Codex's effort and its approval policy, `Ask on request`,
from the conversation's last turn, else its `config.toml`) and the hook herdr-fold answers its questions through,
and its
sub-agents under it. Uses: the files' tools, the shell, and each connector (one that is off here faint, with no
edge); the other built-in tools a conversation called stand as one node (`12 more tools`), each with its gates in
that node's properties. An edge is solid for what always loads and dashed for what loads on demand, yellow and
dashed for a connector to sign in to, red and dashed for one that failed, as the legend at the canvas's top right
says. On an edge to a tool or a connector stands its gate: the permission (`allow`, `ask`, `deny` with its
exceptions: `ask · pytest allowed`, `deny git push`) and `hook` where herdr-fold's hook answers.

A press chooses a node: its properties at the canvas's foot, as the Agent panel's (where it is from, what it runs,
its error), with Open for its file, in the preview tab; × , Esc or a press beside the nodes puts them away. `Show in
Agent`, the last of its buttons, shows the dock's [Agent](#agent) panel as that agent's with the node's row chosen,
its section opened and scrolled to (a rule, a skill, a connector, a sub-agent; the agent's own node: its panel); a
node the panel has no row of (a built-in tool, a folded one) has none. The arrows step to the nearest node that way.
A node drags by its body, its edges following; where it is let go is kept
for that space, folder and agent (`herdr-fold.graph-layout`, the app's shared values), and a double click beside the
nodes lays the graph out again. A canvas narrower or lower than its graph scrolls. Changing a server (Retry, Connect,
Turn off) stays the Agent panel's.

The graph is read when the tab first shows, when the folder's or the agent's setup files change (5 seconds apart at
least) and every 30 seconds while it shows; a long conversation, whose file takes seconds to read, no sooner than ten
times as long as its last read took. A space on another machine says `On <machine>: with a later version`.

Where the folder has a conversation, a switch beside the head's name turns the graph from `Wiring` to `This
conversation`: the same graph with what that conversation ran lit. The edges that ran are drawn in the accent (the
legend's `ran here`), the one a call is still waiting on wider; what did not run stands at half strength, its edges
faint. Each first use carries its number, in order, on its node's top right corner. The agent and each sub-agent
that ran show what they cost (`~$3.70`), their model's color before their line (`Opus 5.5 · 38 turns · 1.0M tokens`)
and their share of the conversation as a thin bar in that color; a tool and a connector show their calls (`14
calls`). A press on the agent shows its figures, the label left and the value right: its model and effort, input,
the cache's writes (1 hour and 5 minutes apart) and reads with their share of its input, output, its share, and
Claude's own count of the conversation beside herdr-fold's (`the same`, or by how much it differs); `Open in Usage`
shows the Usage view with this conversation's row marked, `Show in Agent` beside it the Agent panel. The costs are
`core/costs.py`'s, read after the token index
is brought up to date; while a call runs the view is read again every 5 seconds.

### Usage

The tab's other view, the one place usage is read in full: `core/report.py`'s report, each message at its own
model's prices. An agent on a plan reads `API value` (what the same use would cost on the API; the plan charges
nothing more), never spent; one on an API key reads `spent`; an agent whose sign-in is not told yet reads `API
value`. Its head names the spaces it covers (`All spaces`, or one picked from its list). Under it, in one row: the
period (`Today`, `7 days`, `30 days`, the month), the agent (`All agents`, `Claude`, `Codex`), and at the right
`Budget…` (with an agent on an API key) and `Export CSV`.

- The summary row: a cell an agent (its cost, its plan's line or its month against its budget, a pace past the
  budget in yellow), then the tokens with the share read from the cache, and the commits from these conversations
  with what one cost. Its dollar figures wear `~` (`~$130.90`, `~$18.40 of $50 · on pace for ~$46`); the tables'
  cells under it do not, and the foot says once that the costs are estimates.
- `Per day, by model`: a column a day, its models stacked in their colors, the legend beside the title; the pointer
  on a day shows its date, its sum (`~$33.50`) and each model's cost. The colors are the models' own everywhere (the
  graph's too), moved toward the text where a theme's card would not show them 3:1.
- An API-key agent's month against its budget: what was spent by each day, the pace on to the month's end drawn
  fainter, the budget a line across, `~$18.40 today` and `on pace for ~$46`. With no budget kept, the line and the
  pace alone.
- `By project`: a bar a folder, the most first.
- `Conversations`, the costliest first: its space, its models, turns, tokens, the share read from the cache, its
  cost, its commits with their lines (`about` where some only followed its edits, `none yet`, `–` where they are
  not known: a folder that is no repository, Codex's conversations, one not read yet) and what one cost. The
  pointer on a row says what a turn cost; a press opens the conversation as Chats does.
- `Models`: each model by agent (Claude's sub-agents apart) with its input, cache writes and reads, output and
  cost; a model with no price shows its tokens and `no price`, never $0.00.
- The foot: `Costs are estimates from the conversations' token counts at list prices (LiteLLM's model cost map, as
  of Nov 9, 2026), not the provider's invoice`, and that a model with no price shows its tokens alone.

`Budget…` opens a field for each agent on an API key, dollars a month; an empty field takes the budget away, Enter
or Save keeps it (in herdr-fold's own `usage.json`, the TUI's too). `Export CSV` saves the period as CSV where
macOS's save panel says, a row for each day, agent, model and conversation, its costs plain numbers.

The conversations are read into herdr-fold's indexes before the figures are whole (`core/tokens.py index`, then
`core/commits.py index`, each called again until nothing is left to read): a first read of many sessions takes a
while, `Reading the conversations…` says so, and until then a cost is what was read so far and a commit `–`. While
the view shows, the indexes and the report are read again every minute.

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
- Agent reads the agent's own files as text and never writes them: the folder's and the home's rules, settings, skills
  and sub-agents (`CLAUDE.md`, `AGENTS.md`, `.claude/`, `.mcp.json`, `~/.claude`, `~/.claude.json`, `~/.codex`), and
  Claude's file of the open conversation for the servers' state and what it used. It starts no server; with Codex
  installed it runs `codex mcp list`, to mark a server both agents read. A server's command line and address show; its
  environment, its headers' values and an address's query never leave the reader. For the agents' list it asks each
  agent whether it is signed in (`claude auth status --json`, of which only that, the way and the plan's id are kept,
  never the e-mail or the organization; `codex login status`, its exit code and whether its words start as an API
  key's do, nothing after that start); Sign in starts the agent's own
  login in a terminal tab, on your press, and herdr-fold sees and keeps nothing of it.
- An SVG or a page is drawn with nothing asked of the network and none of its scripts run, so a file cannot learn who
  opened it.
- The mod itself sends nothing anywhere but two daily looks, each the request alone: for a newer herdr-fold
  (api.github.com) and for the model prices Usage's costs are counted with (LiteLLM's public table,
  raw.githubusercontent.com), both switched in herdr-fold's Settings (More, then About). The sync talks to the
  repository's remote, gh to GitHub, the AI tool to its own service.
