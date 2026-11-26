# The sidebar

The sidebar at the top of the right column is herdr-fold's own herdr plugin, `herdr-fold.sidebar`
(`src/plugins/sidebar/`): Files, Search, Changes (git), for a repository on GitHub Issues, the Chats list and the
agent's setup (Agent) in one pane, on macOS, Linux and Windows. Its keys, what it reads and writes on the machine, and
how to use it without herdr-fold are in [its README](../src/plugins/sidebar/README.md). This page is what herdr-fold
does with it.

![The four views: Files with its git marks, Search narrowed to the folder chosen in Files, Changes with the repository
on top, a message, the issue it fixes and the Graph, Issues by priority](../assets/screenshots/tui-sidebar.webp)

![A commit's diff in the preview tab, its message and each file's lines numbered, the tab laid out as the one it
was opened from](../assets/screenshots/tui-preview.webp)

![A PDF's pages one under another in the preview tab, where its first page meets its second, and the sidebar's
Files with the PDF chosen in its folder](../assets/screenshots/tui-pdf.webp)

![An HTML page's code above and the page under it, drawn for its width, in the preview tab, Split chosen; the
sidebar's Files with the page chosen](../assets/screenshots/tui-split.webp)

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
  repository. And it brings `micro`, the editor a text file opens in where `$VISUAL` and `$EDITOR` name none.
- The Issues view uses `gh`, which the installer brings and signs in to GitHub. On a remote machine it shows once gh is
  installed and signed in there; the Mac's sign-in never goes to the machine.

## How it starts

It runs in a plain herdr pane named `sidebar`, with the system Python: the space builder and `restore_panes.py`
start it through `src/sidebar.sh` (`src/sidebar.ps1` on Windows), the plugin itself in a new tab and when herdr starts.
In your home folder it opens `~/Documents` instead. In a space whose folder is no repository itself (your home
folder, a folder of projects), Changes shows the repository of the folder or file chosen in Files, however deep, else
the one the Spaces row names (the only one two folders down), its name in the repository row above the message: its
changes, commit and sync, its branch's pull request (the row under it, a new one's form in the message's place), Files'
marks and the Issues view, with its Pull requests, follow it.
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
the views' own background, with the keys; its lit button, Esc, a click outside it or another pane closes it, and a
press on another of the dock's buttons (a view's, ») closes it and does its own at once, as a flyout switches; the
chosen chat's task list stands under its row ([Chats](usage.md#chats)). More, the row's last button, opens the pane's
own menu under it (over the list while it is open, Show archived first there).

The column keeps one width everywhere, in cells: it first opens as wide as the names need (80 cells inside herdr's
frame); drag it wider or narrower in one tab, and every other tab's column, in every space and window, gets that
width at once, and keeps it after herdr restarts; a new column opens at it too. It leaves the agent 30 % of the tab at
least, a drag wider coming back to that; a window resized keeps the width, narrower only while the window leaves the
agent less, as wide again once it has the room. Narrower than the names need (80 cells,
69 without Issues), the row shows its icons alone, each on the middle of five cells, a dot or not, the dot on the last
one, its name in its tip; a tab's column is never narrower than that row (49 cells, 43 without Issues): dragged
narrower and let go there, the dock folds to its rail as » folds it, « opening it again at the width it had. In a
window too narrow for it, the row is cut at its right end, and the keys still show every view.

The » at the right end of the row's icons' line, on an icon alone's five cells a cell after More, lit under the mouse as
a button of the row, or Cmd + Option + B from anywhere (the same key opens it again), folds the dock to its rail, in
every tab as the width is, kept after herdr restarts: the row's icons alone, one under another, each on the middle of
five cells, its name in its tip (centred under it), Changes', Agent's and Chats' dots on the last cell, each with its
own half rows, three rows apart; the column takes 5 cells inside herdr's frame (a tenth of the tab where that is more,
and odd), the icons on its middle. The terminal moves under the agent, down to its fewest rows (herdr's least share, a
tenth of the tab's); Terminal, the rail's icon after Chats (or 6), raises it as tall as it was in the right column and
lowers it again (a bare shell drawing its prompt again from the top, Ctrl+L), lit while raised (its tip says so where
the tab has no terminal); the dock opened again puts it back at that height, and the choice stays for the next fold, a
new tab's terminal or one brought back taking it too. A press on an icon opens the dock in every tab, as « does, on that
view (Chats on its list), the keys its own, as VS Code's activity bar; so do Cmd + Shift + G and the other views' keys.
« at the top, on five cells over the icons, opens the dock again at the width it had; so does dragging the rail's edge
more than 3 cells wider, a smaller nudge going back to the rail.

## The Agent view

Agent, the row's fifth button, shows what the agent in the tab starts with in the folder, changes a part of it from a
form, and leads to the Usage view (`U`), the Runs view (`r`: what the agents ran in the background) and the agent's
graph as a tree in the preview tab (`g`). All of it, for both clients: [The agent's harness](harness.md). A known
service's connector wears its letter or glyph, and a media service's says what it makes and its calls today; More's `Add
fal…`, `Add ElevenLabs…` and the like fill the add form ([Media services](harness.md#media-services)). What such a
service made shows in the preview tab with where it came from ([Pictures, audio and video an agent
made](usage.md#pictures-audio-and-video-an-agent-made)).

The pictures below are from before the view's redesign; its sections, their order and the words are in that page.

![The Agent view beside Claude in lumen-api: Usage folded to Claude's 5 hours at 64%, Rules, Permissions open with
the mode (Edit automatically) and the project's allow and ask rules, Skills, Connectors and
Agents](../assets/screenshots/tui-agent.webp)

![The Usage view over lumen-api's tab, 7 days of every agent: Claude on Max as API value, Codex on an API key spent,
November against its $150 budget, the tokens, per day by model, by project and the
conversations](../assets/screenshots/tui-usage.webp)

![The preview tab's graph on This conversation: Claude's path numbered (Read · Edit · Write, then Bash), its cost,
model and tokens, and each tool's calls; the sidebar's Agent view beside it](../assets/screenshots/tui-graph.webp)

It reads the setup again every 30 s while shown and every 5 minutes behind another view, for its dot (not at all
while More leaves it off the row).

## Keys

Cmd + Shift + G (Changes), Cmd + Shift + I (Issues), Cmd + Shift + R (Chats), Cmd + Shift + E, Cmd + Shift + O and Cmd +
Option + B (the rail) reach it from anywhere: [Keys](keybindings.md#panes-and-tabs). Cmd + Shift + L opens a file the
focused pane's output names at that line, a text file in your editor and a picture in the preview ([Opening a file the
agent named](usage.md#opening-a-file-the-agent-named)).

More at the row's end (or a right click on the row) lists the views first, each with a ✓ while shown, as Adobe's Window
menu: one unchecked leaves the row in every tab, and a check or its key brings it back; one view always stays. Below
them it closes or shows back the tab's terminal and offers Restore panels while a pane is closed. Last, Settings… opens
herdr-fold's own Settings in herdr's popup, as the Herdr app's: its sections in a list at the left, General,
Notifications and About (↑ ↓ or a click), the chosen one beside it, in a window of one size. General has Icons, Nerd
Font or Plain marks (← →, Tab or a click): the one lit is in use, within a second in every tab's sidebar; `i` in Files
switches it too. Notifications has "An agent waits on you", on or off: herdr's own note at the bottom right, once per
agent (`[ui.toast] delivery` in `~/.config/herdr/config.toml`, `herdr` or `off`, which herdr then reads again). About
has herdr-fold's version and license, its author's name a link to their GitHub page, Up to date and when it looked or a
newer version and how to get it, Check now, Check for updates automatically (Space), What's new (this version's part of
the CHANGELOG in the preview tab) and Third-party notices (Tab and ← → choose, Enter presses). Its close button, Esc or
a click outside closes it. While a newer version is out, More has a dot, in the accent, and Settings opens at About. The
keys inside the sidebar are in its README.

## Colors and icons

The theme setter (`src/themes/apply.py`) writes the theme's colors to
`~/.local/state/herdr/plugins/herdr-fold.sidebar/colors.json`, and a running sidebar takes them at once. Without that
file it uses the terminal's 16 colors. Its icons are made for herdr-fold Mono, whose Nerd Font icons are full size;
with a Nerd Font's `… Mono` variant they look small or off-center: set Ghostty's font back, then press Cmd + Shift + ,.
