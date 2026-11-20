# The sidebar

The sidebar at the top of the right column is herdr-fold's own herdr plugin, `herdr-fold.sidebar`
(`src/plugins/sidebar/`): Files, Search, Changes (git), for a repository on GitHub Issues, and the agent's setup (Agent)
in one pane, on macOS, Linux and Windows. Its keys, what it reads and writes on the machine, and how to use it without
herdr-fold are in [its README](../src/plugins/sidebar/README.md). This page is what herdr-fold does with it.

![The four views: Files with its git marks, Search narrowed to the folder chosen in Files, Changes with the repository
on top, the message Claude wrote, the issue it fixes and the Graph, Issues by
priority](../assets/screenshots/sidebar.webp)

![A commit's diff in the preview tab, its message and each file's lines numbered, the tab laid out as the one it
was opened from](../assets/screenshots/preview.webp)

![A PDF's pages one under another in the preview tab, scrolled to where its first page meets its second, the
Chats column folded beside it, and the sidebar's Files with the PDF chosen](../assets/screenshots/pdf.webp)

![An HTML page's code left and the page right, drawn for its side, in the preview tab; the sidebar's Files with the
page chosen](../assets/screenshots/split.webp)

## How it gets there

- The installer copies it to `~/.config/herdr-fold/plugins/sidebar` and links it (`herdr plugin link`): it lays out
  every new empty tab, comes back in every tab when herdr starts, and brings its actions (the panels, Chats:
  find, Restore panels) and the one-time tip when a pane is closed by hand; the link is recorded in
  `~/.local/state/herdr-fold/plugins.txt`.
- `machines.sh` copies it to each remote machine and links it there too.
- On its own, without the rest of herdr-fold: `herdr plugin install princesshu/herdr-fold/src/plugins/sidebar`, then
  `herdr plugin action invoke restore-panels --plugin herdr-fold.sidebar` (`restore-panels-windows` on Windows) lays
  out the tab you are in ([its README](../src/plugins/sidebar/README.md#install)).
- A herdr-sidebar you installed yourself stays; the installer names it, since the two do the same.
- The `Brewfile` brings `bat` and `git-delta`, which color the previews; without them a file shows plain and a diff in
  git's colors. It brings `ripgrep` for Search too; without it Search runs git grep, or its own search outside a
  repository.
- The Issues view uses `gh`, which the installer brings and signs in to GitHub. On a remote machine it shows once gh is
  installed and signed in there; the Mac's sign-in never goes to the machine.

## How it starts

It runs in a plain herdr pane named `sidebar`, with the system Python: the workspace builder and `restore_panes.py`
start it through `src/sidebar.sh` (`src/sidebar.ps1` on Windows), the plugin itself in a new tab and when herdr starts.
In your home folder it opens `~/Documents` instead. In a workspace whose folder is no repository itself (your home
folder, a folder of projects), Changes shows the repository of the folder or file chosen in Files, however deep, its
name in the repository row above the message: its changes, commit and sync, Files' marks and the Issues view follow it.
Quitting it (`q`) leaves a shell; `python3 ~/.config/herdr-fold/restore_panes.py` starts it there again. After an update
it starts its new version by itself, where it was, and so it does on its folder's new place when the folder is renamed
or moved.

Its views are buttons in one row at the top, a cell in from each side as the views' content, a cell between two, as the
first version's tabs: each its name in the very middle, as much air left of it as right (9 cells for a name of an odd
length, 10 for an even one), its icon over the name's middle, a blank row above and below: Files, Search, Changes,
Issues, Agent, then Chats and More. The chosen one, in the accent, fills the rest of the pane, and each folder keeps
which one it is. A chosen row's highlight runs from edge to edge; everything else, every row's content, », fields,
headers, menus and the line at the foot, keeps a cell in from each side. Changes and Chats show a dot beside their icons
while there is something to count, in the changes' color and the waiting chats', the number in the button's tip, and
Agent while its setup has a problem, red for a server that failed over yellow for one to sign in to, the problems in its
tip; nothing moves when a dot comes or goes. The button under the mouse stands whole on the hover background a list's
row has under it, half a row of it above and below; so does a rail's icon, its five cells, and a menu's line from frame
to frame, its text a cell in. Chats, under the AI sparkle, opens the Chats list over the sidebar, under its button, on
the views' own background, with the keys; its lit button, Esc, a click outside it or another pane closes it. More, the
row's last button, opens the pane's own menu under it.

The column keeps one width everywhere, in cells: it first opens as wide as the names need (80 cells inside herdr's
frame); drag it wider or narrower in one tab, and every other tab's column, in every workspace and window, gets that
width at once, and keeps it after herdr restarts; a new column opens at it too. Narrower than the names need (80 cells,
69 without Issues), the row shows its icons alone, each on the middle of five cells, a dot or not, the dot on the last
one, its name in its tip; a tab's column is never narrower than that row, a drag narrower going back to it: 49 cells, 43
without Issues. In a window too narrow for it, the row is cut at its right end, and the keys still show every view.

The » at the right end of the row's icons' line, on an icon alone's five cells a cell after More, lit under the mouse as
a button of the row, folds the dock to its rail, in every tab as the width is, kept after herdr restarts: the row's
icons alone, one under another, each on the middle of five cells, its name in its tip (centred under it), Changes',
Agent's and Chats' dots on the last cell, each with its own half rows, three rows apart, the ⋯ last while a view is
beside it; the column takes 5 cells inside herdr's frame (a tenth of the tab where that is more, and odd), the icons on
its middle. The terminal moves under the agent, down to its fewest rows (herdr's least share, a tenth of the tab's);
Terminal, the rail's icon after Chats (or 6), raises it as tall as it was in the right column and lowers it again (a
bare shell drawing its prompt again from the top, Ctrl+L), lit while raised (its tip says so where the tab has no
terminal); the dock opened again puts it back at that height, and the choice stays for the next fold. A press on an icon
opens that view beside the rail (Chats its list), the column wider, the icon in the accent; the lit icon again, or Esc,
folds it back, and « at the top, on five cells over the icons, opens the dock again at the width it had; so does
dragging the rail's edge more than 3 cells wider, a smaller nudge going back to the rail.

## The Agent view

Agent, under its robot, shows what the agent in the tab starts with in the sidebar's folder, in the Herdr app's Agent
panel's words: on its first row the agent picked for the folder, else the tab's Claude or Codex (herdr's agent list;
with none there, the one herdr-fold started last) and the folder, "Claude in lumen-api ⌄", its problems at the right ("1
failed" in red, "1 sign in" in yellow; a click chooses that server). Enter or a click on that row opens "Agents on this
Mac" under it: the installed agents, ✓ on the one shown, at the right its plan's word (never an e-mail) or "sign in" in
yellow where the agent says it is signed out; a pick makes the view that agent's for this folder, in every tab, until
another is picked, and "Add an agent…" lists the ones not installed. An agent with no setup to show says why in its
place: not signed in, with Sign in, which runs the agent's own login in a herdr tab of its own (the view asks the agents
again every 5 s, 10 minutes at most; herdr-fold keeps no token); not installed, with its vendor's install line, Copy and
"Open its page ↗" (herdr-fold runs no installer). An agent whose setup herdr-fold does not read (Gemini CLI, signed
in) has its first row alone. Under the head Usage, open until folded:
a row for each agent whose 5-hour or weekly limit is known (one on an API key has none), the agent shown first, then the
newest reading: ▾ or ▸ dim, its name and its plan's word. The agent shown is open, the others folded, and what you open
or fold stays, kept once for the Herdr app too in herdr-fold's own `~/.local/state/herdr-fold/usage.json`. An open
agent has a second line, `5h ▰▰▰▰▰▱▱ 72%  wk ▰▱▱▱▱▱▱ 16%`, each bar and percent green under 50, yellow from 50, red
from 80, as the status line's; at the right of its name, dim, when its 5 hours reset ("5 hour resets at 2:46 PM", in
this machine's time, its hours as the status line writes them); a limit past its reset leaves its place empty, and "as
of 43 min ago" stands at the right of a name whose reading is older than ten minutes. A folded agent is its row alone,
its figures at its end in their levels' colors, the color the only sign: `5h 72%  wk 16%` (the tighter alone where both
do not fit). With none known it says "Not known yet"; a pane too narrow for the bars keeps the percents. ↑ ↓ stop on
Usage's head and each agent: on an agent Enter or → opens it, ← folds it (folded, ← goes up to the head), and a press
opens or folds it ([What the agents cost](#what-the-agents-cost) is its costs and the head's keys). Folded whole, the
head's end shows one figure instead of the period: the agent shown's name and its tighter limit (`Claude 5h 72%`, an
agent on an API key its month of its budget, `Codex ~$18.40 of $50`), or another agent's where that one is yellow or
red and stands worse. Then the sections, each with its count: Rules,
Permissions, Skills, Connectors (every MCP server: the project's, yours, a plugin's, claude.ai's) and Agents (the
sub-agents); Connectors open and the rest folded until opened, kept in every tab. A section shows its first five rows,
its problems and what the open conversation used always, then "N more" (never "1 more": that line shows the row itself).
A server's row starts with its state's mark (✕ failed, ● to sign in in yellow, ● on in green, ○ off here, not approved
or not checked, ◐ connecting or signing in), then its service's glyph in its color (Dropbox, Figma, Google Drive,
Notion, OneDrive, Sentry; a letter for Box and Linear, for every one without a Nerd Font, and dim for a server of no
known service), and ends with its state and where it comes from (Project, Personal, Local, claude.ai or a plugin's
name), each in its column; a rule a deny or an ask hides has a yellow ●, its sentence under it; Permissions
start with what the agent starts in, where a file tells it: Claude's `Mode` (a settings file's `defaultMode`, in the
chat's words, `Plan`) and Codex's `Approval` (its `config.toml`'s top-level policy, in the graph's words, `Ask on
request`), the words dim, only read: its one button opens the file (no row where `config.toml` names a
profile). A skill,
a sub-agent or a connector the open conversation used has a green ● there (a server's problem keeps its own mark).
The chosen row's
properties are under it, label and value, none its row says already: its file, what it runs or its address, its error,
its first lines or its description, then its buttons: Open shows the file in the preview tab, and Retry, on a Claude
server that failed, connects or is not checked, asks Claude to check it (`claude mcp get`), its mark spinning meanwhile,
its answer shown until a newer session says otherwise. Connect, lit, on a server to sign in, runs the agent's own login
(`claude mcp login <name>`, `codex mcp login <name>`) in a herdr tab of its own, which opens your browser; the row says
"signing in" until that tab is gone, with "Finish in your browser", "Open the page again" (the address the login
printed) and Cancel (the tab closed) under it, and the agent is asked about the server again when it ends; ten minutes
at most. "Turn off here" and "Turn on here" type Claude's own `/mcp disable <name>` or `/mcp enable <name>` into the
tab's Claude and put the keys there: Enter sends it; with no Claude in the tab the button is dim and says so. "Sign
out", on a claude.ai connector and on a Codex server signed in through Codex, runs the agent's own `mcp logout
<name>`; a Claude server added by its address has no such button: signing it out is Claude's own, and its properties
name the command (`Sign out`, `claude mcp logout <name>`). Codex's rows have Connect and Sign out alone. While Agent
shows, More (⋯) lists "Add from claude.ai" (claude.ai's connectors page, in the browser), "Add by URL" (`a`) and Refresh
first: the form lies under Connectors' head, Name, URL and, for Claude, For (this folder, or All projects), then "Add
and connect" and Cancel; Tab or ↓ steps on, ← → choose For, Enter adds with the agent's own `mcp add`, Esc leaves, and a
field or an add the agent refuses says why in the form. ↑ ↓ choose (the head row first), → opens a section and ← folds
it (on a row, ← goes up to its section), Enter opens a section, "N more" or the row's first action, and a right click
offers the row's actions. It reads the setup again every 30 s while shown and every 5 minutes behind another view, for
its dot (not at all while More leaves it off the row); it writes nothing of the agent's itself and keeps no token: every
change is the agent's own command.

### What the agents cost

Once the conversations are read, Usage's lines also say what each agent cost, in the Herdr app's Usage's words and
numbers (`core/report.py`): at the right of an open agent's name its figure, `~$130.90 API value` for one on a plan
(what its week would cost at API prices, never "spent"), `~$18.40 of $50` for one on an API key (its month against its
budget, `~$18.40 spent` with no budget; Claude's `auth status` and Codex's `login status` say which is on one), each
message at its own model's price; an agent on an API key gets a row of its own, first where it is the agent shown,
open with `Nov ▰▰▰▱▱▱▱ on pace for ~$46` under it, the bar and the pace yellow once the month is on pace past its
budget; folded, its row ends with `~$18.40 of $50`, green, yellow once over (the cost alone with no budget). Each
dollar figure herdr-fold computes wears `~`, an estimate at list prices; the budget you set wears none. When a limit
resets, and a reading's age, then stand after the bars where the pane has room. Under the agents, `per day`: one
block a day, an eighth of a row its least step, in the color of the model that day cost the most in, and the days they
span (`Nov 3 – 9`); then the projects, the costliest five, each with its cost and its conversations' commits (`5
commits`, `about 2 commits` where some only followed an edit, `none yet`, `–` where they are not known: a folder that
is no repository, Codex's conversations, or ones not read yet); last, dim, how much of the prompts came from
the cache and the prices' day (`81% read from cache · prices Nov 9`). A model with no price shows no figure, never
`$0.00`. The head's right end says the period, `7 days`: `p` or a press on it steps to `30 days`, the month (`Nov`) and
back (folded, `p` still steps it). Enter on the head opens the Usage view; a press folds the section as the others, ←
and → too (→ on the open head goes down to its first agent), and a right click offers Open Usage. A pane too narrow
for a figure's word keeps the figure, and one too narrow for the commits keeps the costs. The costs are read on a
thread of their own, a minute apart while the view shows and never behind another one;
until the first read ends, and while conversations are still being read (`Reading the conversations…`), the limits stand
alone.

### The Usage view

Enter on Usage's head opens herdr-fold's Usage view over the tab's panes (`usage_view.py`, the plugin's pane `usage`,
herdr's overlay; macOS and Linux), on the period the head had: the Herdr app's Usage in cells, the same report in the
same order. At the top the periods as chips, `7 days`, `30 days` and the month, the chosen one on the accent (Tab and
Shift+Tab step them), then the agents, `All agents`, `Claude`, `Codex` (`a` steps them; under the periods where one row
has no room for both), and its close button. Under them, scrolling (↑ ↓, PgUp, PgDn, Home, End, the wheel): the summary
as aligned rows, a key left, its figure and unit beside it, its line dim under it (`Claude · Max plan`, `~$130.90 API
value`, `no charge on the plan · week 16% of its limit`); `Per day, by model` with the costliest day at its right, five
rows of blocks a day, each model's part in its color, stacked in the legend's order, the days' numbers under them (the
first day, each month's 1st and the last always, the rest evenly where they fit, `1 5 10 15` in a narrow pane) and
the legend with each model's share; for each agent on an API key its month against its budget, a bar of the budget with
a mark where the pace ends (past the bar's end once over, the bar and its words yellow; the bar gives way to its words
in a narrower pane) and `~$18.40 of $50 · on pace for ~$46`; `By project`, a bar by the costliest one's cost, the cost
and the commits; `Conversations`, the most first, with cost and commits, and in a pane of 90 cells or more the space,
turns, tokens and the cache's share; `Models`, each with
its color, its input, cache write, cache read and output tokens and its cost (`no price` where it has none), its agent
too in a wide pane; last the foot: the costs are estimates from the conversations' token counts at list prices, not
the provider's invoice, and where the prices are from. The summary's and the charts' dollar figures wear `~`, the
tables' cells do not. Enter, or a press on `Budget…` under a month, edits the monthly
budget of each agent on an API key in the month's place: `Codex $ 50 a month`, Save (Enter) and Cancel (Esc); an empty
field takes the budget away, and what is no amount is said under the field. The budget is kept in herdr-fold's own
`~/.local/state/herdr-fold/usage.json`, the app's too; nothing of Claude's or Codex's is written. Esc, `q`, the close
button or a click in another pane closes the view. It reads again every minute while open; before the first read it says
`Loading usage…`, and a period with nothing used says so. The TUI has no CSV export.

### The graph as a tree

`g` in the Agent view, or a right click on its first row and Show graph, opens the agent's graph in the preview tab as a
tree, the Herdr app's Agents tab's graph in text (`core/graph.py`): the agent with its model, effort and mode (Codex's
own: its approval policy, `Ask on request`, from the conversation's last turn, else its `config.toml`) and its hook in
brackets; under `in` the rules and skills, each with where it is from and when it loads (`always · 2.4k`, `when
src/lumen/** is read`); under `uses` the tools and connectors, each with its state (a failed one red, one to sign in to
yellow, one off here dim) and its edge's gates in brackets (`Bash built-in [ask · pytest allowed, deny git push,
hook]`); under `sub-agents` each with its plugin, model and tools. Where the tab's Claude has a conversation (else the
folder's newest), `c` in the preview shows This conversation: the path that ran, numbered at each first use (`1
api-routes → 2 Read · Edit · Write → 3 Bash → 4 code-reviewer → 5 github`), then the agent and each sub-agent that ran
with what it cost, label and value (Cost, Model, Input, Cache write, Cache read, Output, Share, Claude's own count), and
each tool's and connector's calls in a column; `w` goes back to Wiring, and the status row's names do the same on a
press. The graph is read when asked, on a thread of its own (`Reading the graph…`), and is not followed: `g` again reads
it anew.

## Keys

Cmd + Shift + G (Changes), Cmd + Shift + I (Issues), Cmd + Shift + E and Cmd + Shift + O reach it from anywhere:
[Keys](keybindings.md#panes-and-tabs). Cmd + Shift + L opens a file the focused pane's output names in its preview,
at that line ([Opening a file the agent named](usage.md#opening-a-file-the-agent-named)).

More at the row's end (or a right click on the row) lists the views first, each with a ✓ while shown, as Adobe's Window
menu: one unchecked leaves the row in every tab, and a check or its key brings it back; one view always stays. Below
them it closes or shows back the tab's terminal and offers Restore panels while a pane is closed. Last, Settings… opens
herdr-fold's own Settings in herdr's popup, as the Herdr app's: its sections in a list at the left, General and About
(↑ ↓ or a click), the chosen one beside it, in a window of one size. General has Icons, Nerd Font or Plain marks (← →,
Tab or a click): the one lit is in use, within a second in every tab's sidebar; `i` in Files switches it too. About has
herdr-fold's version and license, its author's name a link to their GitHub page, Up to date and when it looked or a
newer version and how to get it, Check now, Check for updates automatically (Space), What's new (this version's part of
the CHANGELOG in the preview tab) and Third-party notices (Tab and ← → choose, Enter presses). Its close button, Esc or
a click outside closes it. While a newer version is out, More has a dot, in the accent, and Settings opens at About.
The keys inside the sidebar are in its README.

## Colors and icons

The theme setter (`src/themes/apply.py`) writes the theme's colors to
`~/.local/state/herdr/plugins/herdr-fold.sidebar/colors.json`, and a running sidebar takes them at once. Without that
file it uses the terminal's 16 colors. Its icons are made for herdr-fold Mono, whose Nerd Font icons are full size;
with a Nerd Font's `… Mono` variant they look small or off-center: set Ghostty's font back, then press Cmd + Shift + ,.
