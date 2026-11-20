# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

The whole environment `herdr-fold 0.4.0` and its plugins `herdr-fold.sidebar 0.4.0`, `herdr-fold.sessions-view 0.4.0`
and `herdr-fold.workspaces 0.4.0` (in Tab Layout's place), with herdr-fold's mod for herdr's desktop app.

### Added

- Delete… for a chat, in Chats, in the TUI sidebar and the Herdr app. Archive stays the everyday way to tidy the list;
  Delete… is the rarer one under it, for a closed chat (an archived one too), Claude's and Codex's alike. It asks
  first, by the chat's name (the TUI at the list's foot, as its views ask; the app in the chat's own row, as Files
  asks Move to Trash), then the row leaves at once and the chat's file is moved to the system's Trash, never
  unlinked: Claude's with its sub-agents' folder, Codex's rollout file. Its archive mark and the name given to it are
  dropped. A running chat is never deleted: the TUI offers none, the app's is faint and says why. In the TUI the
  Delete key asks the same while the filter is empty. A Trash that does not take the file brings the row back and
  says why under the list. What is moved, and what never is: [A chat you delete](SECURITY.md#a-chat-you-delete).

- Codex's approval policy in the Agent view's Permissions, in the TUI sidebar and the Herdr app: where its
  `config.toml` sets one at its top level, the section starts with the row `Approval` and its words as the graph
  says them (Ask unless trusted, Ask on request, Ask on failure, Never ask), tagged Personal. It is only read: Open
  shows the file, nothing sets it; a `config.toml` that names a profile shows none. Claude's has the same row,
  `Mode`, where a settings file names the mode it starts in (`Plan`, `Edit automatically`), tagged by that file.

- What the agents cost, in the TUI sidebar's Agent view. Usage's lines gain each agent's figure at its name's right,
  `~$130.90 API value` on a plan and `~$18.40 of $50` on an API key, with that agent's month under it (`Nov ▰▰▰▱▱▱▱
  on pace for ~$46`, yellow once over); then the period's days as one row of blocks in their costliest models' colors,
  the five costliest projects with their costs and commits, and how much came from the cache with the prices' day.
  `p` or a press on the head's period steps 7 days, 30 days and the month; Enter on the head opens the Usage view.
  Read on a thread of its own, a minute apart while shown, through `core/report.py`, as the Herdr app's.
- The session's cost in Claude's status line, one more item to choose (`statusline_setup.py`, off until chosen):
  `~$4.12`, Claude's own count at list prices, on a plan its API value and with an API key about what it spent; the
  first thing a narrower pane drops. Codex's line is its own and has none.
- A Usage view in the TUI: the Herdr app's Usage in cells, opened over the tab from the Agent view's Usage head (the
  sidebar plugin's pane `usage`; macOS and Linux). The periods' and the agents' chips (Tab, `a`), the summary as aligned
  rows, each day by model as five rows of stacked blocks with its legend, each API-key agent's month against its budget
  with the pace's mark, the projects, conversations and models; Enter edits the monthly budget, kept in herdr-fold's own
  `usage.json`; ↑ ↓ scroll, Esc closes. No CSV export there.
- An agent's graph as a tree in the TUI's preview tab: `g` in the Agent view, or Show graph on its first row's right
  click. The agent, what goes in, what it uses with each edge's gates in brackets and its sub-agents; `c` shows This
  conversation, the numbered path that ran with each agent's costs and each tool's calls, `w` Wiring again.
- The Herdr app's Agents tab, with an agent's graph. A tab of the main area, one a space (the palette's Agents, or
  Show graph on a rule, a skill, a connector or a sub-agent in the Agent panel, which opens it on that row's node):
  what goes in (rules, skills), the agent with its sub-agents under it, and what they use (tools, connectors), in
  three columns; an edge solid for what always loads, dashed on demand, yellow for a connector to sign in to and red
  for one that failed; on an edge its gate, the permission with its exceptions and herdr-fold's hook where it asks.
  A press shows a node's properties and opens its file in the preview tab, and Show in Agent there shows the Agent
  panel on that node's row (on the agent's own node: its panel); the arrows step between the nodes. A node
  drags, its edges following, and stays where it is let go for that space, folder and agent; a double click beside
  the nodes lays the graph out again. Claude and Codex through the same graph.
- This conversation, in the Agents tab's graph. Where the folder has a conversation, a switch turns the graph from
  Wiring to what that conversation ran: its edges lit, the one a call still waits on wider, the rest at half
  strength, each first use numbered in its order. The agent and each sub-agent that ran show what they cost, their
  model's color and their share of the conversation; a tool and a connector their calls. A press on the agent shows
  its tokens by kind and Claude's own count beside herdr-fold's, with Open in Usage.
- Usage, the Agents tab's other view in the Herdr app: what the agents used and what that cost, each message at its
  own model's prices. An agent on a plan reads API value, never spent; one on an API key reads spent. The period
  and the agent in one row; a summary row; each day by model; an API-key agent's month against its budget with the
  pace it is on; the projects; the conversations with their cache share, commits and what a commit cost; the models
  with their tokens by kind, one with no price its tokens alone. Budget… keeps a monthly budget for an agent on an
  API key, and Export CSV saves the period where macOS's save panel says. The palette's Usage opens it.
- One tilde before every dollar figure herdr-fold computes, in both clients and the status line (`~$18.40`,
  `~$130.90 API value`, `on pace for ~$46`): an estimate from the conversations' token counts at list prices, not the
  provider's invoice, as the Usage view's foot says once; the budget you set (`of $50`) and Export CSV's numbers wear
  none, nor the Usage view's table cells.
- What the agents cost, where they are used, in the Herdr app. The Agent panel's Usage says an agent's week as API
  value, or an API key's month with its budget's bar and its pace, yellow once over, and Open Usage leads to the
  Agents tab's Usage. A chat says once a month when an API-key agent has spent 80% of its budget or is on pace to
  pass it, until its × closes it for that month in both clients. A chat's Context panel says what the conversation
  cost, by model, and how much of it came from the cache, with Usage › to its row.

- herdr-fold Mono, herdr-fold's own monospace font, both clients' one: JetBrains Mono with Nerd Fonts' icons, its line
  10% taller (the room split above and below the text, so a row of the TUI and of the Herdr app is as tall), and the
  symbols Claude Code, Codex, herdr and starship print that it lacked drawn from its own glyphs (⏺ ⎿, the spinners'
  ✢ ✳ ✻ ✽ ◐ ◓ ◑ ◒, ⏵ ⏸ ⏹, ✔ ◼ ◻ ☐ ☑ ☒, /context's ⛁ ⛀ ⛶ ⛝, ⇡ ⇣ ⇕, ↻ ↵ ↳ ↯ and more). The TUI's installer puts
  it in `~/Library/Fonts` (the uninstaller takes it off), Ghostty uses it, and the Herdr app's layout loads it from the
  mod for its terminals and the code its views draw. `tools/fonts.py` builds it from Nerd Fonts' release; its
  license, the SIL Open Font License, is beside it.
- Every message's tokens and what they cost, for Usage's cost view to come. `core/tokens.py` reads Claude's sessions
  with their sub-agents' files and Codex's token records, each message once by its id (a message's repeated lines, a
  session resumed into a new file, a sub-agent's file beside its parent's call), and tells input, the cache's
  5-minute and 1-hour writes, its reads, output with its reasoning part and web searches apart, by the hour, model,
  sub-agent type and session. The sessions are large, so each file is read once and then only where it grew, kept in
  `~/.local/state/herdr-fold/usage-index.json` (numbers, session ids and folders, readable by you alone; the
  uninstaller removes it); nothing of Claude's or Codex's is written. `core/prices.py` prices each kind at its own
  model's rate from [LiteLLM](https://github.com/BerriAI/litellm)'s model cost map, a prompt past a size step at
  that step's rate; a model with no price has no cost, never $0. The map is fetched once a day from
  raw.githubusercontent.com with the request alone, under the update check's own switch (Check for updates
  automatically, `HERDR_FOLD_NO_UPDATE_CHECK=1`); without it the last table fetched is used, else the one bundled
  (`core/price_table.py`, written by `tools/prices.py`; LiteLLM's MIT license is in `THIRD_PARTY_NOTICES.md`). It
  also names a model as people say it (Opus 5.5, GPT-5 Codex) and gives each family its color, moved toward a
  theme's text where a mark of it would read under 3:1 on that theme's card (Nord's).
- Usage's report, for both clients' cost view to come. `core/report.py` turns the token counts and prices into what a
  period cost (Today, 7 days, 30 days, the month, as this machine's whole days), of every agent or one, of every
  folder or one: a summary row (an agent on a plan as "API value" with "no charge on the plan" and its week's limit,
  never as spent; an agent on an API key as "spent" with its month, budget and pace; the tokens with the share read
  from the cache; the commits), each day by model, the month against its budget, the projects, the conversations
  (turns, tokens, cache share, cost, what a turn cost, commits with their lines and what one cost) and the models
  (a model with no price says "no price" and keeps its tokens). A monthly budget for an agent on an API key is kept
  in `~/.local/state/herdr-fold/usage.json` (`report.py budget AGENT DOLLARS`); from 80% of it spent, or a pace past
  it, a notice is told for the chat ("Codex has spent ~$45.10 of $50 this month · on pace for ~$58 by Nov 30"),
  dismissed for that month. `report.py csv` gives the same numbers as CSV, a row for each day, agent, model and
  conversation. The words are made once, for the Herdr app and the TUI alike.
- The commits from a conversation, for that report. `core/commits.py` counts the commits a conversation made itself
  (its `git commit`'s own line names each, checked in the repository) and the ones that touched a file it edited,
  within a day of that edit and before another conversation edited the file; with those the figure reads "about".
  Claude's sessions' edits and named commits are kept in `~/.local/state/herdr-fold/commits-index.json` (paths,
  times and commit ids, readable by you alone), each file read once and then only where it grew. git is only read,
  three runs a repository, with nothing the repository's config names run; a conversation whose commits cannot be
  told (Codex's, a folder in no repository, no git) shows "–". The uninstaller removes both files.
- An agent's graph, for the Agents tab and the TUI's tree to come. `core/graph.py` lays out what is in effect for an
  agent in a folder as nodes in three columns (In: the rules and skills; Agents: the agent and its sub-agents; Uses:
  the built-in tools and the connectors) and the edges between them: solid for what always loads, dashed for what
  loads on demand, waiting for a connector to sign in to, failed for one that did not start. An edge to a tool
  carries its gate: allow, ask or deny from the mode and the permission rules, with the exceptions ("ask · pytest
  allowed", "deny git push"), and herdr-fold's hook where a chat of its own asks. The project's own skills and
  sub-agents and the ones a conversation used are a node each; the rest fold into one ("15 more skills"). For a
  conversation it reads the session file and its sub-agents' files and tells what ran: each node numbered at its
  first use, the calls on each edge, the edge of a call with no answer yet as running. `core/costs.py` gives that
  conversation's cost from the token index: the agent and each sub-agent type with its model and its color, turns,
  tokens and share, the lines of an inspector (input, the cache's writes and reads, output), as API value on a plan
  and as spent with an API key, and Claude's own count of the conversation beside it ("the same", or by how much
  it differs). Codex goes through the same shapes: its rules, skills, prefix rules on its shell, servers and its
  newest chat in the folder; its line says its effort and its approval policy (`Ask on request`), from the
  conversation's last turn, else its `config.toml`; a herdr-fold hook and a mode are never said of it. Both only
  read; a name taken from
  a session is drawn as text, cut, its control characters dropped.
- The connectors' commands and brands, for the Agent panel's Connectors to come: `core/connectors.py` builds each
  change as the agent's own command, one argv, nothing of the agent's written by herdr-fold (`claude mcp login`,
  `logout` and `add --transport http --scope local|user`, Codex's `mcp login`, `logout` and `add --url`, and Claude's
  `/mcp enable` and `disable` for a folder), and reads the address Claude prints while it waits for a sign-in. A
  server's name is refused when it starts like an option or holds a control character, a new one's is letters,
  digits, `-` and `_` (what both agents take); an added address is https, or http to this machine, with no user or
  password in it. It also knows eight services by a server's name, else its address's host (Box, Dropbox, Figma,
  Google Drive, Linear, Notion, OneDrive, Sentry): each server `core/agent_setup.py` lists and each Connectors row
  now carries its `brand`. Their logos are in the mod (`icons/logos/`, from SVG Logos, CC0, fetched by
  `tools/icons.py logos`; nothing is fetched while the app runs) and `icons.js` names each (`BRANDS`); the TUI gets a
  Nerd Font brand glyph and a color for each, its letter for Box and Linear.
- Connectors managed in the Agent panel, in the Herdr app and the TUI sidebar. A connector's row wears its service's
  logo (the TUI: its glyph or letter in its color; a server of no known service its letter). Connect, on a server to
  sign in, runs the agent's own login in a terminal (the app: one with no pane; the TUI: a herdr tab) and opens your
  browser; the row says "signing in" with "Finish in your browser", "Open the page again" and Cancel until it ends,
  ten minutes at most, and the agent is then asked about the server again. "Turn off in lumen-api" and "Turn on in
  lumen-api" (the TUI: "Turn off here") give Claude its own `/mcp disable` or `enable` in that folder's conversation
  (the app sends it to an idle Claude, the TUI types it into the tab's Claude); with no Claude there the button waits
  and says so. Sign out, on a claude.ai connector and a Codex server signed in through Codex, runs the agent's
  logout; a Claude server added by its address has no such button, its properties name Claude's own command
  (`claude mcp logout <name>`). Connectors' + (the TUI: More's "Add from claude.ai", "Add by URL" or
  `a`, and Refresh) opens claude.ai's connectors page, or a form: Name, URL and, for Claude, this folder or All
  projects; "Add and connect" runs the agent's own `mcp add` and signs in where the agent says it must. Codex's rows
  have Connect, Sign out and the form alone. herdr-fold writes nothing of Claude's or Codex's itself and keeps no
  token.
- The chat's + menu in the Herdr app, the bar's first button: `Upload from computer…` (⌘ U; macOS's own chooser, the
  files as chips over the prompt, sent after the message's words as `@path`), `Add context…` (also an "@" typed at a
  word's start: a list over the prompt, the changed files first, then the folder's, filtered by what is typed), and
  Connectors: the failed and sign-in ones counted on pills, `Manage ›` to the Agent panel's Connectors, and each one on
  or off in this folder with its logo and a switch (Claude's own `/mcp enable` or `disable`, sent once it is idle).
  `core/search.py` lists a folder's files for it (`{"files": true}`).
- Connectors in the chat's timeline: a connector's call is drawn with its service's logo and name, its tool and its
  first words (`Google Drive search_files paging spec`); a server that comes to need a sign-in during a conversation is
  a step of its own (`Box needs you to sign in`, Connect at its end, `signing in…` while the agent's login runs, done
  once the server is on). `core/chat.py` tells the step from Claude's session file (`signin`).
- The clock in the chat's bar, `This folder's conversations`: the dock's Chats list with that folder's group open and
  scrolled to.
- Usage, the first section of the Agent panel in the Herdr app and of the TUI sidebar's Agent view: a row for each
  agent whose limits are known, the agent shown first, with its plan's word (never an e-mail) and the 5-hour and weekly
  percent in the status line's colors (green, yellow from 50, red from 80). The agent in use is open, with a bar and
  when that limit resets, in this Mac's time (the TUI: `5h ▰▰▰▰▰▱▱ 72%  wk ▰▱▱▱▱▱▱ 16%`), and its costs; every other
  agent folds to one row ending in its tightest figures (`5h 72%  wk 16%`, on an API key `~$18.40 of $50`), the
  color the only sign. A press opens or folds a row (the TUI: Enter or → opens, ← folds), and what you open or fold
  stays, kept once for both clients in herdr-fold's own `usage.json` (`usage.py open AGENT on|off`). Folded whole, its
  head shows one figure: the agent in use's tighter limit, or another agent's where that one is yellow or red and
  worse. A limit past its reset is not shown, a reading older than ten minutes says its age ("as of 43 min ago"), and
  no agent waits under "+N more". Read with the setup, every 30 s while shown. The words are `core/usage.py`'s
  (`usage.py section AGENT [AGENTS]`), the same in both.
- The Herdr app's Agent panel, the dock's fifth tab after Issues, wearing its agent's own icon (Lucide's bot on the
  rail): what the space's agent, Claude or Codex, starts with in the folder, read only, in the words of the TUI's Agent
  view (`core/agent_setup.py`'s layers). Its head names the agent and the folder; under it a bar of what loads at start
  (the rules, the skills' listing, the connectors' tools), "21k loaded at start" and a chip per problem ("1 failed"
  red, "1 sign in" yellow); then Rules, Permissions, Skills, Connectors and Agents with their counts and costs
  (Permissions by behavior, a folded Agents by name), a fold kept per space. A section shows its first five rows, its
  problems and what the open conversation used, then "N more" in place; a row has its icon, name and note, both agents'
  icons where both read it, a green dot where the conversation used it, then its state, its source's tag and its cost
  in columns; a permission a deny or an ask hides has a yellow shield and its sentence under it. The head's search
  filters every section by name, note, state or tag. It is read when shown, when the folder's rules and settings or
  the agent's own folder change, and every 30 s while shown. The command palette lists it (Agent). A space on another
  machine says so. `agent_setup.py layers claude FOLDER [SESSION]` takes a conversation's id too, else the folder's
  newest.
- The Agent panel's properties and actions in the Herdr app: a press chooses a row, and under the layers stand its
  properties as a design tool's (the label left, the value right: where it is from, what a server runs or its address,
  a rule's paths, a sub-agent's tools, how often the conversation used it; a conflict's two rules), a server's error, a
  rule's first lines or a skill's description. Open shows the row's file in the preview tab; Retry asks Claude to check
  a server again (`claude mcp get`), its state a spinner meanwhile, the answer kept until a newer conversation says
  otherwise (`agent_setup.py layers claude … --checked JSON`, which also tells each server's own state). A problem's
  chip chooses its row; while the setup has a problem the Agent tab and the rail's Agent carry a dot, red over yellow.
  The chat's Context panel ends with "Show all in Agent ›", which shows the panel.
- The agents managed in the Agent panel, in both clients. The head is a chip, "Claude in lumen-api ⌄" (the TUI: Enter
  or a click on the head's row), opening "Agents on this Mac": the installed agents only, ✓ on the one shown, its
  plan's word beside it (never an e-mail), "sign in" where the agent says it is signed out, then "Add an agent…" with
  the ones not installed. A pick makes the whole panel that agent's, kept per space (the TUI: per folder, in
  `settings.json`'s `agent_chosen`) until another is picked. An agent with no setup to show says why in its place, in
  core's words (`agent_state.py`'s `standing()`, told with `agents` as "empty"): not signed in, with Sign in, which
  runs the agent's own login (`claude auth login`, `codex login`, `gemini`) in a terminal tab and asks again every 5 s
  until it is in (herdr-fold keeps no token); not installed, with its vendor's install line to copy and its page
  (herdr-fold runs no installer). A new chat's agent list shows the installed agents only, marks one
  to sign in, and ends with "Manage agents…", which shows the panel with its list open; a chat's "Show all in Agent ›"
  shows the panel as that chat's agent's.
- The TUI sidebar's Agent view, the row's fifth button (`5`) between Issues and Chats, under Codicons' robot (◇ without
  a Nerd Font): what the agent in the tab starts with in the folder, in the Herdr app's Agent panel's words
  (`core/agent_setup.py`'s layers, now the sidebar's too), in cells as the mockups draw it. On top "Claude in lumen-api"
  and its problems ("1 failed" red, "1 sign in" yellow; a click chooses that server); then Rules, Permissions, Skills,
  Connectors and Agents with their counts, Connectors open and the rest folded until opened (kept in every tab), each
  showing its first five rows, its problems and what the open conversation used, then "N more" (never for one row). A
  server's row has its state's mark (✕ failed, ● to sign in, ● on, ○ off here, ◐ connecting), its state and its source
  in aligned columns; a rule a deny or an ask hides has a yellow ●, its sentence under it; a skill, a sub-agent or a
  connector the open conversation used has a green ●, as the app's dot. The chosen row's properties
  lie under it as label and value, none its row says already, with its error, first lines or description and its
  buttons: Open shows the file in the preview tab, Retry has Claude check a server that failed (`claude mcp get`), its
  mark spinning meanwhile. ↑ ↓, → ← to open and fold, Enter for the row's first action, a right click for its actions.
  Agent's button and rail icon have a dot while the setup has a problem, red over yellow, the problems in its tip; the
  setup is read every 30 s while shown and every 5 minutes behind another view (not while More leaves it off the row).
- The TUI sidebar folds to its rail by the » at the right end of its row of buttons, in every tab, as Adobe's Collapse
  to Icons: the row's icons alone in a column 5 cells wide, each name in its tip, Changes', Agent's and Chats' dots by
  their icons, the tab's terminal moved under the agent at its fewest rows, the rail's Terminal icon (or 6) raising it
  as tall as it was and lowering it again; the rail stays after herdr restarts. A press on an icon opens that view
  beside the rail (Chats its list), the icon lit; the lit icon again or Esc folds it back, and « at the top of the rail,
  over its icons, opens the dock again as wide as before, as does dragging the rail more than 3 cells wider.
- The Spaces list shows the branch of a repository inside a folder that is no repository itself, with ↑ to push and
  ↓ to pull against its remote branch, in both clients: the active pane's repository where the folder holds several.
- The TUI sidebar's More lists its views first, each with a `✓` while shown, as Adobe's Window menu: one unchecked
  leaves the row in every tab until a check or its key brings it back; one always stays. The menu's kinds of line stand
  apart by a rule, as herdr's own menus.
- The preview's code and picture one under the other: an SVG's or a page's code above its picture where the room is
  taller than wide, as Xcode's canvas, or as chosen (the turn in the status row, `v` and the right click in the TUI;
  the button beside Code, Split and Picture and the right click in the Herdr app), its divider dragged as the side by
  side one.
- The TUI preview's status row starts with Code, Split and Picture, as the Herdr app's buttons, the chosen one in the
  accent, and in Split the turn; a click chooses, `c` and `v` stay, each named faintly before its control. A narrow
  row leaves out its key hints, then cuts the file's name short, and keeps its controls whole; its gray spans the
  pane.
- Every picture macOS reads in the preview, both clients: HEIC, AVIF, JPEG XL, JPEG 2000, PSD, TGA, EXR, ICNS, the
  GPU's textures and a camera's raw file (DNG, CR2, NEF, ARW…) beside PNG, JPEG, GIF, WebP, TIFF and BMP; one no
  browser shows opens in Preview (Open in Preview), where a browser would only download it.
- A changed picture under Changes shown as VS Code's image diff in both clients: before and after side by side, each
  under its name and size (the TUI: Index and Working Tree, staged HEAD and Index; the app: HEAD and Working Tree),
  one above the other where the room is taller than wide; a new one's after alone, a deleted one's before alone.
- herdr-fold's own Settings in the TUI sidebar, More's last line (Settings…), as the Herdr app's: herdr's popup,
  herdr-fold Settings, its sections in a list at the left, General and About (↑ ↓ or a click), the chosen one beside
  it, one size whatever it shows. General has Icons, Nerd Font or Plain marks (← →, Tab or a click): the one lit is in
  use, within a second in every tab's sidebar; `i` in Files stays its shortcut, and another tab's sidebar now takes
  it too.
  About has herdr-fold's version and license (the author's name a link to their GitHub page, from the LICENSE), Up to
  date and when it looked or the newer version, how to get it and its release notes, Check now (GitHub not reached:
  Couldn't check, with the time of the last look that answered), Check for updates automatically (Space), What's new
  (this version's part of the CHANGELOG in the preview tab) and Third-party notices. Its close button, Esc or a click
  outside closes it. While a newer version is out, More has a dot in the accent, its tip naming the version, and
  Settings opens at About; after an update one herdr notification says it (What's new: More › Settings › About).
- Every popup herdr-fold opens in the TUI (Settings, closing a tab with a chat, a new workspace's folder picker, Cmd +
  Shift + L's files, the theme picker) has a close button at its top right, as the sidebar's icons alone: Codicons'
  close (× with the icons off) on three cells, lit under the mouse, its tip `Close (Esc)`; a click closes the popup as
  Esc does, whatever was typed. Their text and buttons keep one cell from each side, herdr's own blank column at the
  right being that side's, as in About. The commit window and Add machine scroll as they ask, so they keep the ways out
  they had.
- herdr-fold's own Settings in the Herdr app, a window of one size that More's last line, Settings…, opens: its
  sections at its left, the chosen one beside them, every change in effect at once. General holds Open agents in, Chat
  or Terminal. About is as the TUI sidebar's and in its words: herdr-fold's version and license (the author's name a
  link to their GitHub page, from the mod's LICENSE), the update check's state (Up to date and when it looked, the
  newer version and how to get it, Couldn't check with the last look that answered, Checked by hand only, a spinner
  while a look runs), What's new (this version's part of the CHANGELOG in the preview tab) or the newer one's release
  notes, Check now, Check for updates automatically and Third-party notices. ↑ and ↓ change the section, Tab steps
  through its controls, Enter or Space presses one, and ×, Esc or a click beside closes it; it opens at the section
  looked at last. While a newer version is out, the status bar says `herdr-fold 0.4.0 is out` at its end, a press
  opening Settings at About; after an update one toast says it, a click on it opening What's new.
  `herdr-fold.settings` opens the window from a key.
- An agent in another tab of the TUI that starts waiting on you says so once, in herdr's own toast at the bottom right
  (`claude needs attention`, or `claude finished`, its workspace and tab), never for the tab in front: herdr-fold's
  herdr settings turn herdr's toasts on (`[ui.toast] delivery = "herdr"`); its sounds stay off.
- The Herdr app starts agents from its tab bar: + after the tabs (Cmd + N) a new chat with the agent used last that the
  chat draws (Claude), New chat and the space with its branch in its middle and the agent's chip in its prompt's bar,
  nothing running until the first message starts the agent (with the model, mode, effort and Ultracode picked
  meanwhile); the chip's list, searched as typed, offers the recent agents first, one not installed dim, one the chat
  cannot draw yet (Codex) marked `terminal` and opened in a terminal tab in the chat's place. >_ beside + opens the
  app's own list (a terminal, each agent in its terminal, a new space, a worktree), which + opened until now. Settings'
  Open agents in, Chat (the default) or Terminal, decides how every way in opens an agent: +, a closed chat reopened
  from Chats (a Claude chat as a chat tab, resuming it; Codex's in its terminal until the chat draws Codex), and Issues'
  To the agent, which with no agent in the tab now hands the issue to a new one (in a chat tab, the chat's own agent
  gets it).
- The Herdr app's chat has a model chip in its prompt's bar: the model and, dimmer, its effort (Opus 5.5 High); a press
  opens Claude's models as Claude Code lists them, each with its line (Default, Opus 5.5, Fable 5.2, Sonnet 5.5, Haiku
  5.5), the one in use checked, a press picking one (`/model`). The mode chip beside it opens the Modes panel: Modes and
  `⇧ + tab to switch` at its head, Claude's modes with their icons and lines, then Effort with a dot slider and the
  level's name (`/effort`, a press or a drag, ← →), then Ultracode with its switch, faint with Claude's reason where
  Claude refuses it; ⇧ + tab in the prompt is Claude's next mode. Before the agent runs, what is picked goes with its
  start (`--model`, `--permission-mode`, `--effort`, Ultracode in its settings). In a narrow chat the model chip leaves
  its level out (its tip says it), then the bar's tools leave whole from their end and the model's name is cut short;
  the mode and send stay whole.
- The Herdr app's chat shows what is in its context: the bar's meter (the ring and `context 34%`, the share in the
  ring's green, yellow or red) opens the Context panel, with how much is in use (68k of 200k · 34%), a bar of what
  fills it and its legend (the rules Claude reads at the start and its skills' list, estimated, and the rest as one
  part), the rules in effect (each file with its folder, the paths it is read for and its scope tag: Personal, Project
  or Local), the skills the chat used and when, how many more there are, and Compact; a press on a rule or a skill
  opens its file in the preview tab. A "/" typed in the prompt opens the / menu over it, as Claude Code's own: This
  conversation (Export the conversation…, Markdown saved where macOS's save panel says), the folder's skills with
  their lines and source tags (Project, Personal, a plugin's name), the ones used first, then Claude's commands, a few
  of each and how many more; what is typed after the "/" filters it, the best match first and lit, Enter picks it,
  ↑ ↓ step, Esc closes. A skill goes into the prompt as Claude takes it (`/api-routes`, `/code-review:code-review`);
  a skill's step in the timeline names its source after it. The bar's panels share one row, as high as what it holds
  (8 over and under): a list's 32, a model's or a mode's with its line 52. Before Claude runs, the mode chip shows
  the mode Claude starts in (`permissions.defaultMode` in its settings), else Manual. `core/agent_setup.py` reads the
  rules, the skills (the enabled plugins' too) and the mode from the chat's folder, only reading. In a narrow chat the
  meter's words give way first. The model and mode chips no longer carry a chevron.
- The TUI sidebar's Issues hand an issue (`t`) to a new agent when the tab has none: the one herdr-fold started last,
  in a new tab of the workspace named after the issue, the sidebar beside it, the prompt typed in for you to send;
  the new workspace's folder picker starts its Claude │ Codex toggle on that agent.
- The usage limits for the Agent panel's Usage: Claude's status line, in the TUI and in a Herdr app chat, keeps the
  5-hour and weekly limits it is told, with their reset times, in `~/.local/state/herdr-fold/limits/claude.json`,
  readable by you alone and nothing else of the session. `core/usage.py` reads each agent's newest: that file, Claude's
  own cached limits in `~/.claude.json` (with their age) or Codex's newest chat, never writing either agent's files; a
  limit past its reset is left out, and so is an agent without limits (an API key). The uninstaller removes them with
  the last part.
- Claude's permissions and sub-agents for the Agent panel: `core/agent_setup.py` reads the permission rules of every
  settings file (your organization's managed ones, yours, the project's, the local ones) with their scope, how many
  allow, ask and deny, and each conflict, a rule Claude never reaches as "deny in Project hides allow in Personal"; and
  the sub-agents (yours, the project's, the enabled plugins' and Claude's own) with their model and tools, only
  reading.
- Claude's MCP servers for the Agent panel: `core/agent_setup.py` lists each one Claude has in a folder (the project's
  `.mcp.json`, the local ones and yours in `~/.claude.json`, your account's claude.ai connectors, the enabled plugins';
  your organization's alone where it sets them) with what it runs or its host and path, never its env or header values
  nor a URL's query. Its state is what Claude's newest session there last said, read with nothing run: on with its
  tools and what they cost in context, failed with its error, sign in, not approved (a `.mcp.json` server waiting for
  your yes), connecting or off here; also what the open conversation used (its skills, servers and sub-agents). One
  server is checked on asking with Claude's own `claude mcp get`, which starts none Claude has not approved.
- The agents on this machine and Codex's setup for the Agent panel: `core/agent_state.py` lists Claude, Codex and
  Gemini CLI, each installed or not, signed in or not and its plan's name (Max, Plus, API key; never an e-mail), asked
  in ways that print no secret: `claude auth status` (its account's e-mail and organization never kept), `codex login
  status`'s exit code, an API key told by how its words start (nothing after that start read), and the plan Codex's
  newest chat names; Gemini CLI tells it to no
  one without its credentials, so it shows none. Each comes with how it signs in, its own command in a terminal tab
  (`claude auth login`, `codex login`, `gemini`), and how to install it. Codex's setup is read as Claude's is: its
  `AGENTS.md` files from the repository's top down to the folder (an `AGENTS.override.md` first), its skills (yours in
  `~/.codex/skills` and `~/.agents/skills`, the repository's `.agents/skills`), its rules in `~/.codex/rules` as allow,
  ask and deny with each conflict, and its MCP servers as `codex mcp list` gives them (on, off or sign in, never their
  env or headers); a rule file or a server both agents read is marked as both's.
- The Agent panel's layers, laid out once for both clients: `core/agent_setup.py layers AGENT FOLDER [SESSION]` turns
  Claude's or Codex's setup in a folder into the panel's words, in the mockups' order: the head (`Claude in
  lumen-api`), the health line (`22k loaded at start`, the context the rules read always, the skills' listing and
  the servers' tools take, and the problems as chips, `1 failed` and `1 sign in`, each leading to its row), then Rules,
  Permissions, Skills, Connectors and Agents with their counts and costs (`6.1k`), the problems first in each (a
  failed server, one to sign in, a conflict in place of the rule it hides: `deny in Project hides allow in
  Personal`). Each row has its tag (Personal, Project, a plugin's name, claude.ai), its state in words (`32 tools`,
  `failed`, `sign in`, `not approved`, `connecting`, `off here`), a dot where the open conversation used it, and its
  properties as label and value: From, Runs or URL, Paths, Model, Tools, Used, a rule's first lines, a skill's
  description, a server's error, and its actions (Retry, Connect, Turn off or on in the folder, Sign out, Open the
  file); Claude's own commands are never offered on a Codex row.
- The Herdr app's window has a title row of its own across the top, 36 px, as VS Code's command centre: the traffic
  lights sit in it on macOS (the window's own buttons at its end elsewhere), and at the window's centre a command field,
  the shown space's name faint in it and the palette's key at its end as bound (Cmd + Shift + P); in a narrow window it
  narrows, down to its mark alone. The tab bar and the sidebar's head sit under it: Herdr's mark and name at the head's
  start, now that the traffic lights have left it, Go to space or tab and the sidebar's toggle at its end (herdr-fold's
  own, on the tab bar's line).
- The Herdr app layout's own command palette, opened onto the title row's field by a press or Cmd + Shift + P (in the
  herdr-fold layout the key opens it in place of the app's, so there is one palette): the field becomes its field, 600
  px wide on the same centre, 8 px under the window's top, and under it the app's commands in the app's groups (Tab,
  Pane, Space, Layout, Terminal, Agent, Window, App), each with its key at its end, the first lit. Typing finds them as
  the chat's / menu finds its rows, the best first, each with its group; Enter runs the lit one, ↑ ↓ move it, and Esc,
  a press beside it or the key again closes it. After the app's groups it lists herdr-fold's own commands in a group
  of its name, found and ranked with the rest: Settings…, the views (Files, Search, Changes, Issues, Chats), New chat,
  Styleguide, Mark agent unread, Commit and push and Write commit message, each with its key where it has one
  (`herdr-fold.files` is new: it shows Files).

### Changed

- A theme switched and the dock folded or opened reach every other tab's TUI sidebar within a second, as a change
  in Settings already did: one look a second at the three files' stamps, a file read only once its stamp changed.
  An idle tab took them at its poll before, up to ten seconds later.
- The Herdr app mod's styleguide page (`herdr-fold.styleguide`) lists its parts in an index at its side and draws the
  one picked, where it drew every part down one page: the app stops a render that long, and the page came up
  "interrupted" after a restart or a zoom.
- The TUI sidebar shows one view at a time, the whole height, under a row of buttons at its top, from where a chosen
  row's highlight starts, a cell between two, each its name in the very middle (9 cells for an odd one, 10 for an even
  one), its icon over the name's middle, a blank row above and below: Files, Search, Changes, Issues, Agent, Chats,
  More. The chosen button's icon and name are in the accent, its name bold; Changes, Agent and Chats have a dot beside
  their icons while there is something to count, the number in the button's tip (1.2k from a thousand, 1.3m from a
  million), so nothing moves when it comes or goes. The button under the mouse stands whole on the hover background a
  list's row has, half a row of it above and below, as a menu's line does. A click, `1` to `5` or F9 to F12 (Files to
  Issues) shows a view, and each folder keeps the one it shows. Without a Nerd Font the icons are plain marks (▤ ⌕ ⎇ # ◇
  ✦ ⋯). The right column first opens as wide as the names need (80 cells; once again after this update, whatever an
  earlier version kept) and keeps the width dragged, in cells, in every tab and window and after herdr restarts;
  narrower than the names need (69 cells without Issues) the row shows its icons alone, each on the middle of five
  cells, a dot or not, and named in its tip, and the column is never narrower than them (49 cells, 43 without Issues). A
  chosen row's highlight runs from edge to edge; everything else (rows' content, », fields, menus, the line at the foot,
  the rail's icons) keeps a cell in from each side. The icon-only view tabs and the shown view's title beside them are
  gone.
- The Herdr app's right panel is one card, its top level with the tab's beside it, with its views' text tabs on top, 8
  px over and under them and 6 at the sides (the first tab's name over the views' words) and a hairline under them, as a
  design tool's panel tabs: Files, Search, Changes, Issues (a repository on GitHub), each as wide as its name, the shown
  one on a raised pill; under them the view chosen, and the tab's terminal at its foot on a card of its own. Changes'
  count follows its name in a small round accent badge, whichever view shows; narrower, the last tabs leave, never the
  shown one. Each space keeps its view, a new one starting on Files. Chats, More and » stand at the tab bar's right end,
  over the dock, open or folded: Chats (its dot while chats wait on you, their number in its tip) opens the list in the
  view's place, its filter taking the keys, no tab shown, and Chats again, Esc or a tab brings the view back; it lists
  every chat of this Mac, one in a folder with no space open under that folder's name, and has left the left sidebar.
  More shows or hides each view by its `✓` and opens herdr-fold's Settings; » folds
  the dock to its rail of the views and the terminal (« in the same place opens it again; Chats then floats its list
  beside the rail), and the tab's terminal then stands under the tab as VS Code's panel, the centre's width, as high as
  last dragged, the rail's Terminal showing and hiding it, lit while it shows; it no longer floats in a window of its
  own. The left sidebar is on the panels' own surface, the frame and the gaps darker. Cmd + Shift + G and Cmd + Shift +
  I show Changes and Issues, Cmd + Shift + F Search, the dock opened; an update drops the app's state of the old panel,
  its groups and its row's own block, keeping its width.
- The Herdr app's status bar is herdr-fold's own, as the mockups draw it: the shown space's machine and branch, then
  its agents in words, those waiting on you first (`1 of 3 agents waiting for you`, a yellow dot), else those working,
  else how many (`1 agent`; the app's said `1 agents`). While Herdr or herdr-core has an update ready, a green dot and
  `Update ready: herdr-core 0.1.21` stand at its end, a press updating herdr-core while the terminals keep running, or
  restarting into Herdr's own; it is the layout's one sign of it, the folded sidebar's Settings losing its dot. With
  neither ready, a newer herdr-fold stands there the same way. The palette's `commands` hint has left it for the title
  row's field.
- The sidebar plugin is named "Sidebar" on herdr's marketplace card.
- Conversations is Chats in both clients, its saved state and its actions too: `conversations.json` and
  `conversation-index.json` in the sidebar's state folder move to `chats.json` and `chat-index.json` on first use, the
  archived chats with them; herdr's action `herdr-fold.sidebar.find-conversation` is `herdr-fold.sidebar.find-chat` and
  the Herdr app's `herdr-fold.conversations` is `herdr-fold.chats`. The installer rewrites its own key bindings; one
  made by hand to an old id has to name the new one.
- The TUI's chat column, its rail and its own pane are gone, and so is a tab's third column: the list opens
over the sidebar, on the views' own background, from Chats, after Issues in the row, under the AI sparkle and a
dot beside it while chats wait for an answer. The keys go to the list while it is open; its lit button, Esc, a click
outside it or another pane closes it. Cmd + Shift + R opens it in the tab's sidebar, its filter empty; Cmd + Shift + H,
which collapsed the column, is gone with it. On an existing install the update closes every tab's chat column and gives
the right column back the width last dragged; what the column kept goes from `chats.json`.
- Tab Layout (`herdr-fold.tab-layout`) is gone, its work split between two plugins: the sidebar lays out every new
  empty tab (its shell on the left, the sidebar above a terminal on the right, as wide as in every other tab) and
  comes back in every tab when herdr starts; Workspaces (`herdr-fold.workspaces 0.3.0`) keeps the rest: the **new**
  button's folder picker, a workspace's name following its folder and its deleted mark, the question before a tab
  with a chat closes, and herdr-fold's agents started again after a restart. Without Workspaces, herdr's own
  **new** button works as herdr's, and every new tab still gets the sidebar. herdr's marketplace card lists Workspaces
  in Tab Layout's place.
- An update takes Tab Layout off herdr (uninstalled when it came from herdr's marketplace) and moves its state, the
  workspaces it followed and the one in front, into Workspaces' folder; a no to Tab Layout stays a no to Workspaces.
  The installer asks `Let a new workspace ask for its folder, and herdr-fold's agents start again after a restart?`
  in place of `Give every new tab the sidebar and a terminal?`: the sidebar does that now. A remote machine gets the
  sidebar, AI Sessions and Workspaces linked, and Tab Layout taken off.
- The TUI folds with one chevron everywhere: the chats' spaces and the issues' filter as the file tree and the
  sections, and without a Nerd Font a plain chevron (› ⌄) for each.
- A fold turns its chevron as it opens or shuts: the Herdr app springs its section open with no overshoot and crosses
  its two chevrons on the same spring (sections, Graph, the chats' spaces, the chat's rows and cards); the TUI
  turns it through a frame at 45° (the file tree, the sections, the chats' spaces, the folder picker).

### Removed

- The installer no longer installs JetBrainsMono Nerd Font with Homebrew, nor Ghostty's `adjust-cell-height`: herdr-fold
  Mono carries both. One installed before stays, and is no longer named by the uninstaller.
- The TUI sidebar's last row no longer says a newer version, and no "is out" notification comes: More's dot and About
  herdr-fold say it. More's version line and Check for Updates went into About.
- The Herdr app's "herdr-fold X is out" toast, and More's version and Check for Updates lines, are gone: the status
  bar's item and Settings' About say it.

### Fixed

- Chats listed one chat as many rows of one name, in both clients. Two causes, neither a compacted chat's parts
  (Claude Code 2.1 compacts and resumes a chat in its own file, under its id; Codex's user chats likewise): a project
  folder linked to another's in `~/.claude/projects` listed each of its chats twice, and every run a program made
  through Claude's Agent SDK (a hook's review of each change, titled after the chat it reviewed) was a row. A file is
  now listed once, by its real folder, and the Agent SDK's runs (`sdk-py`, `sdk-ts`) are not chats, as the agents'
  helpers never were; `claude -p`'s still are. A running agent herdr knows no session of is so matched to its
  folder's newest chat, not to a review newer than it. Copy chat no longer repeats a compacted chat: the summary
  Claude wrote in the user's place and the messages it kept and wrote again under their ids are left out. The chat
  index is read anew once (version 3); archived chats and names are kept as they were.
- The home folder left Spaces once its last tab was closed: the Herdr app ends a space with its last tab, and herdr
  a workspace. Each machine's home is now always a row in Spaces, in both clients. In the Herdr app's herdr-fold
  layout `~` is the first row of its machine's spaces (this computer's and each connected machine's), and with no
  space there it stays as a row with nothing open (its avatar an outline, its name dim), a click opening a terminal
  there; the floating list of the folded sidebar shows it too. In the TUI the Workspaces plugin makes the `home`
  workspace again as soon as none is left, behind the one in front, and keeps it the first row of Spaces: made again,
  or below another workspace after one is made or moved, it goes back to the top (herdr's socket request
  `workspace.move`, which its command line has not). Any other space closed is gone in the Herdr app, as before.
- In the TUI a workspace left Spaces when its only tab was closed with herdr's own close (its tab's menu or key,
  `herdr tab close`): herdr ends a workspace with its last tab. The Workspaces plugin now makes it again at once, in
  its place in the list, with its name, its folder and a new shell, and in front again when it was. herdr tells the
  two apart: a last tab's close sends the workspace's close and the tab's (`tab.closed`, a new event in the plugin's
  manifest), a workspace closed on purpose (its row's menu, the close-workspace key, `herdr workspace close`) the
  first alone, and that one stays closed, as does one whose folder is gone or whose last pane was moved elsewhere.
- The Herdr app's reader of what an agent starts with fits in one command-line argument on a Linux machine (132 KB,
  over Linux's 128 KB for one, now 61 KB): it no longer carries whole modules for a few lines of theirs, finding a
  program, a repository's top and reading the agents' files coming from two small ones of their own. Every reader the
  app runs is checked to stay under 120 KB.
- The Herdr app's captions read 4.5:1 on a control's fill in every theme, as on each level: the model chip's effort
  read 4.2:1 in One Dark and 4.1:1 in Solarized. Its styleguide opens in a tab named Styleguide (it said Terminal), and
  the / menu's specimen stands over its prompt (it opened anywhere over the page).
- The Herdr app's window, its sides and its cards part in every theme, as the mockups draw them: the window behind the
  cards the theme's darkest level, the left sidebar, the bars, the prompt and your messages the next, the chat, the dock
  and the popovers the cards' level, each from the theme's own palette (Catppuccin's crust, mantle and base; GitHub's
  canvas.inset, default and overlay; Nord's nord0 and nord1 with a step between) and at least 1.05:1 apart, where nine
  of the thirteen themes had one color for all three; the terminals keep the TUI theme's own background. A count's
  number on the accent and the words under the pointer read 4.5:1 at least in every theme (VS Code's and Solarized's did
  not), and the sources' tags (Personal, Project, a plugin's, claude.ai, Local) each take a color of their own in every
  theme (Personal and Project were one in Nord). A list's rows stand as far in on the right as on the left.
- The Herdr app's Issues, Chats and Changes no longer jump: an Issues refresh keeps the list where it is, its Refresh
  button (new, beside Open and Closed) a spinner meanwhile; the first load, a failure or none found is said where the
  first row will be; what was done or went wrong (`Closed #42`, `Archived`) stands under the list, as the TUI's last
  row, a done thing for four seconds. Changes keeps its list and Graph where they are: a failure is said over the card's
  foot until the next action or its ×, the push Cmd + Shift + C offers in the empty message field, the issue the next
  commit fixes as a chip at its end; while a commit, sync, pull or push runs, ↻ is a spinner naming the step and Commit
  keeps its words, and with words in the field ✦'s tip says who writes the message.
- The TUI's terminal, moved or resized by the sidebar (folded under the agent, raised, lowered, back in the column),
  draws a bare shell's prompt again from its top (Ctrl+L, once); a running program is left alone. On the rail a tip
  stands centred under its icon.
- The TUI's Changes list no longer jumps: a commit, sync, pull or push running spins in the sync glyph's place, its
  tip naming the step (the glyph no longer turns the accent); a failure such as an empty message stands on the
  sidebar's last row until a key; who writes the message, once the field has text, is ✦'s tip. None of them adds a
  row under the button any more.
- The TUI's Issues list no longer jumps: a refresh (`R`, or the new refresh button at the right of Open and Closed)
  keeps the list where it is, the button a spinner meanwhile, its tip `Loading issues…`; the first load, a failure or
  none found is said on the first issue's row.
- The installer keeps no copy of herdr-fold's own earlier files, which the package has: what is yours stays saved as
  before (your files as they were before the first install, an installed file you changed), and the dated folders of
  copies an earlier version kept go on the next run. A file a run leaves in place keeps the sum it had, so an edit in
  it is never taken for herdr-fold's own and is still saved before a later run replaces it. A remote machine alike: a
  file changed there since it was prepared is kept in `prepared-changed-<date>/`, and its own Claude status line in
  `prepared-original/` with its own files.
- An update while the Herdr app runs closes it for that moment and opens it again behind the installer, its
  terminals running on: the app loads the new mod at once, and nothing an earlier version left in it stays (its state
  of the layout, the mod's shared values). Before, it kept drawing the earlier version until it was quit by hand.
- The TUI's Changes no longer misses a change made just after its last git status (`git init`, a quick edit): it
  showed only on the slow beat, 5 to 15 seconds later.
- Changes made at the same moment are all kept: a chat archived while the TUI sidebar reads its list, a
  reopened one's mark, the right column's width as it is dragged, and a setting changed in two places (two tabs'
  sidebars, or a sidebar and the Herdr app linking an issue or switching the update check).
- A second Enter or click on a closed chat while it reopens no longer opens it in a second tab.
- The TUI preview's key hints in a narrow pane: each left out whole, the last first, never cut (`c: co`).
- Claude's status line writes the weekly reset as the machine writes hours (`Monday 13:00` on a Mac set to 24 hours),
  not always with am and pm.
- The license and the notices of what herdr-fold builds on (its icons' among them) go with every install: herdr-fold's
  folder on each machine, and the Herdr app's mod, which also names its author.
- The Herdr app's themes give a control its own fill, frame and hover, so every button, stepper and field in the
  panels and in the app's Settings looks alike and answers the mouse; GitHub Dark's buttons show on their panel, and
  a field's frame is no longer white.
- A menu opens above its button, or above the row clicked, where it does not fit under it, in both clients: the
  chat bar's model, mode and command menus, and a right click near a pane's foot.
- Ghostty's app icon in the theme's colors is a PNG, a format Ghostty documents (it was an SVG), and the theme's line
  warns, with what Ghostty reads, where Ghostty's own config (`ghostty +show-config`) does not take it.
- The TUI sidebar's last row says what herdr refused in herdr's own sentence (`A popup pane is already open`), not
  its JSON answer.
- What another tab's sidebar or Settings chose (the views shown, the icons) reaches every tab's sidebar within a
  second, an idle one too (it took up to ten).
- The Herdr app's chat showed messages twice: Claude writes lines again into a chat's file under the ids they had
  (the messages a compaction keeps, a chat taken up in another folder), and each was drawn anew. A line is now a step
  once, and an older line written again no longer brings back its day's model, mode or servers to sign in to.

## [0.3.0] - 2026-11-08

The whole environment `herdr-fold 0.3.0` and its plugins `herdr-fold.sidebar 0.3.0`, `herdr-fold.sessions-view 0.3.0`
and `herdr-fold.tab-layout 0.3.0`, with herdr-fold's mod for herdr's desktop app.

### Added

- herdr-fold in herdr's desktop app: a mod with the sidebar's Changes view (the changed files, staged by file or all at
  once, a change discarded (a new file into the Trash), a file's diff, the message Claude or Codex writes, Commit,
  Commit & Push or Commit & Sync, Cmd + Shift + C's commit and push in one step (with nothing to commit, the push of the
  commits ahead), the repository's row as VS Code's (sync, pull, push), and the Graph of the last commits with each
  one's diff), Search (the space's folder, with the TUI's switches, a hit's file shown at its line) and Issues (by
  priority, with the TUI's filters; an issue handed to the tab's Claude or Codex and linked to the next commit, a reply,
  Assign to me, close or reopen; Cmd + Shift + I); a diff, a commit or an issue opens in the space's preview tab, as in
  the TUI; its own Spaces list, as the app's, with the TUI's waits (`waiting 12m`, Cmd + Shift + U), and its own tab
  bar, as the app's, each button saying what it does; Conversations in the left sidebar (this Mac's conversations by
  space, a closed one reopened in a new tab, Rename, Copy conversation, Archive; Cmd + Shift + R), the archived ones and
  the names shared with the TUI's column, and folded, the sidebar a dock of icons, as Illustrator's panels, and so the
  right panel (its toggle, Cmd + Shift + G or a drag), each view and the tab's terminal floating beside its rail; the
  right panel one panel group, its views as its tabs, Files among them (the TUI's, where the app's own was: Catppuccin
  Icons' files and folders, git's marks, a file in the preview tab, New File, New Folder, Rename, Copy Path, Move to
  Trash, New Workspace); for a space on this Mac or on another machine (Linux, macOS or Windows), with the TUI's data
  layer underneath; a layout of its own puts it in the right panel, where the app's Changes was (Cmd + Shift + G), dark
  in the TUI's colors (Catppuccin Mocha), its terminals and code in Menlo as VS Code's, at the TUI's size; the TUI's
  twelve themes come along in the app's Settings; under it, each tab's own terminal, as the TUI's right column has it,
  on the space's machine; Lucide's icons, and a file's Catppuccin Icons' for its type. Where the Herdr app is on the
  Mac, `install.sh` sets it up when its first question names the app, the remote machines in the app too;
  `uninstall.sh` takes it off. See
  [The Herdr app](docs/app.md).
- The installer asks first for the TUI, the Herdr app or both, a page in the browser showing each; the default is
  what is installed, and `HERDR_FOLD_PARTS` answers it. Each step sets up only what the chosen parts need: the Herdr
  app alone installs nothing of the TUI's and runs no herdr. The other part is added later by running it again. With
  the Herdr app chosen and not on this Mac, it offers the app's own installer. See
  [Installation](docs/installation.md#the-tui-the-herdr-app-or-both).
- One theme for both parts: the installer and the TUI's theme picker set herdr-fold's layout in the Herdr app too, and
  a running app switches at once; an update keeps the theme there is. See [Themes](docs/themes.md).
- An image or a PDF chosen in Files is drawn in the preview tab, an image fitted to it and never larger than it is, a
  PDF's pages one under another, a gap apart, scrolled (in the app clear of the scrollbar, smaller in a narrower tab):
  in the sidebar (Ghostty shows pictures in herdr; the wheel, ↑ ↓, Space, `g` `G`) and in the Herdr app mod, its page in
  view above them. A page, a PDF or an image opens in the default browser from Files' right click, or `o` and a button
  in the preview tab. See [The sidebar](docs/sidebar.md) and [The Herdr app](docs/app.md#the-preview-tab).
- An SVG or an HTML page chosen in Files shows its code and its picture side by side in the preview tab, as VS Code's
  preview to the side: the divider between them drags and the page is drawn for its side as a browser that size shows
  it, an SVG at its own size, never larger, what it leaves empty clear (in the Herdr app mod on a canvas, as a design
  tool's artboard). `c` in the sidebar, Code, Split and Picture in the app show either alone or both again; a right
  click in the preview tab offers them, Open in Browser and Close Preview. macOS's WebKit draws it offline: nothing is
  asked of the network and none of its scripts run, so a file cannot learn who opened it. See [the sidebar's
  README](src/plugins/sidebar/README.md) and [The Herdr app](docs/app.md#the-preview-tab).
- In the Herdr app mod, a space's first tab is named as the space until it is renamed, as the TUI's main tab.
- herdr-fold says when a newer version is out: once a day it asks api.github.com for its latest release (the request
  alone), says a newer one once (a herdr or Herdr app notification) and keeps it on the sidebar's last row. The
  version installed is in the sidebar's ⋯ menu, a right click on the app panel's tabs and the installer's last line;
  Check for Updates there, or `HERDR_FOLD_NO_UPDATE_CHECK=1`, turns the look off. See
  [Installation](docs/installation.md#a-newer-version).
- Files' right click offers Close Preview while the workspace has a preview tab, in the sidebar and in the Herdr app
  mod; a preview tab closed any way forgets what it showed, as `q` does.
- A remote machine is prepared for the parts installed on the Mac: with the Herdr app alone it gets git, Python and
  the status line, joins the app's core and nothing of herdr's or starship's. See
  [Remote machines](docs/remote-machines.md).
- The uninstaller takes off the TUI, the Herdr app or both: with both installed it asks which, both by default, and
  `HERDR_FOLD_PARTS` answers it. Either goes alone and the other keeps working; what both use (the status line, the
  archived conversations, the linked issues, the records) goes with the last. See [Uninstall](docs/uninstall.md).
- Cmd + Shift + U marks the focused agent unread: its workspace says `waiting` again, from then, until you come back
  to it after leaving it; again on a marked one takes the mark off. See [Sessions](docs/usage.md#sessions).
- The Herdr app's layout comes with its recipe and a picture, `app/RECIPE.md` and `app/preview.png`, as the app's
  catalog of layouts lists one: what it shows, how it behaves, what it is built from, so another agent can build it
  again. See [The Herdr app](docs/app.md#installing-it).
- A styleguide for the Herdr app mod: its colors, type, sizes and icons, each part in each of its states and the
  panels they make, drawn by the views' own code; `herdr-app do herdr-fold.styleguide` opens it, and
  [Styleguide](docs/styleguide.md) shows it on GitHub.
- The sidebar in a workspace whose folder is no repository itself (your home folder, a folder of projects): Changes
  shows the repository of the folder or file chosen in Files, however deep, with its changes, commit and sync; Files'
  marks and the Issues view follow it. See [The sidebar](docs/sidebar.md#how-it-starts).
- Tips in the sidebar: a control shown by an icon alone says what it does once the mouse rests on it
  (✦, ↻, the view tabs, a row's Stage, Unstage, Discard and diff icons, the Files and Search buttons). A changed
  file's row in Changes shows its whole path in the repository, as in GitHub Desktop, on more rows when it is long;
  so does the Herdr app mod's. A name Files cuts short shows its whole path in the folder the same way.

- An update takes off what an earlier version put in the Herdr app and the new one no longer brings: a theme, a key,
  a setting the mod no longer keeps. The uninstaller takes herdr-fold's settings in the app off too, closing a running
  app for that moment (your terminals keep running) and opening it again. Without the TUI, `python3 lib/herdr_app.py
  install .` sets the mod up and updates it. See [Uninstall](docs/uninstall.md).

### Changed

- While the AI writes the commit message, the field says who writes it, with a spinner: "Claude is writing the
  message…" (Codex when it writes), in the sidebar and in the Herdr app mod; with a message of yours in the field,
  the sidebar says it under Commit.
- The sidebar names its views and the tab's panes in lowercase, as herdr names its own (`changes` beside the view
  tabs, Close conversations in the ⋯ menu).
- The sidebar's Changes view puts the repository on top, as VS Code's Repositories: its name, branch, sync and a
  ⋯ that pulls or pushes alone or opens it on GitHub; the status bar at the sidebar's bottom is gone, its branch
  and sync with it. See [The sidebar](docs/sidebar.md).
- Committing needs no staging, as in GitHub Desktop: with nothing staged, a commit and its written message take every
  change, in the sidebar and in the Herdr app mod; a file .gitignore names is never one of them, nor shows in Changes,
  even if it was tracked before. The sidebar commits exactly the changes it showed (and asked about, for files named
  like secrets): one come since waits. Something staged by hand is still committed alone.
- The sidebar's Changes view keeps the Graph at its bottom, the changes scrolling above it on their own; ↑ and ↓
  cross from one to the other. Each file's letter stands under its section's count. A folded section stays folded
  after an update or a restart, and a new version comes back to the rows you were on.
- The sidebar's Commit button looks the same however the focus came to it, with no dark box over its label; the
  Herdr app mod's stays in the accent too while it cannot commit yet, its message and ✦ above it.

### Fixed

- The sidebar's fields select text as text fields do, the commit message too, where it went only a letter at a
  time: Cmd + A, Shift with an arrow, Home or End, and in the message a drag, a double click (a word) or a triple
  click (all of it); Backspace or Delete takes the selection whole, typing or pasting replaces it, and
  Alt + Backspace takes the word before the cursor. Cmd + A no longer flashes the window (Ghostty's own select
  all, of every pane): it reaches only the sidebar's field you are in. See [Keys](docs/keybindings.md).
- Cmd + Shift + I opens the sidebar's Issues view: the key herdr sends it for that (F12) was not read.
- The AI's button beside a commit message of several lines has its star in the middle: the field opens to an odd
  number of rows, up to seven, a message of two lines with an empty third.
- In the Herdr app mod, a changed file asked about before a discard keeps its name clear of the question: the name
  is cut short, and "Discard?", "Discard all?" and "Move to Trash?" stay whole.
- A preview tab opens as the tab it came from: its columns as wide to the cell, a folded Conversations column folded
  from the start, and it shows once its sidebar and Conversations column have started, with no shell's prompt or
  empty column for a moment.
- The sidebar's commit message scrolls with the wheel: a message longer than the field (one Claude or Codex wrote)
  shows its other rows, the cursor where it was, until a key moves it. A selection goes on past the field's edge,
  the rows following it, and the wheel moves the message while a drag selects.
- The sidebar's lists start at their top when a preview tab or a new version brings back the row chosen: a commit
  chosen in the Graph no longer hides the Graph's heading.

### Security

- The commit message writer (the sidebar's Changes view and Cmd + Shift + C) reads a repository's `/commit` rules only
  from inside it: a downloaded folder's rule file linking to a file elsewhere, a key, is passed over, as its text would
  go to the AI. A written message is checked against the changes alone, never against the rules.

## [0.2.0] - 2026-11-02

The whole environment `herdr-fold 0.2.0` and its plugins `herdr-fold.sidebar 0.2.0`, `herdr-fold.sessions-view 0.2.0`
and `herdr-fold.tab-layout 0.2.0`.

### Changed

- The plugins' names, as herdr's marketplace lists them: `Full Setup` (`herdr-fold`), `AI Sessions`
  (`herdr-fold.sessions-view`), `Files · Search · Git · Issues · AI Conversations` (`herdr-fold.sidebar`) and
  `Tab Layout` (`herdr-fold.tab-layout`); AI Sessions' action is now `AI Sessions: reapply`.
- The folder picker is a tree, as the sidebar's Files view: the folder on top in place of the . row, → and ← open and
  close a folder, ← on the top row goes up one; no repositories from elsewhere at its top.

### Added

- The sidebar's Files view: a folder's right click offers New Workspace, which opens herdr-fold's folder picker on it,
  as herdr's new button does.
- A workspace whose folder is deleted says deleted beside its branch, in the theme's red.
- A workspace where an agent waits on you, blocked or done and not seen yet, says how long beside its branch
  (`waiting 12m`), in the theme's yellow; it counts on while you work elsewhere. See
  [Sessions](docs/usage.md#sessions).
- Cmd + Shift + L: the files the focused pane's output names (`src/app.py:42`, a traceback's line), the newest first;
  Enter shows one at that line in the sidebar's preview tab. See
  [Opening a file the agent named](docs/usage.md#opening-a-file-the-agent-named).
- Buttons where a key was the only way: Cancel and Open in the folder picker, Cancel and Close when a tab with a
  conversation is closed.
- The folder picker takes the mouse: a click chooses a folder, a double click opens it, the wheel moves, and a click
  on Claude or Codex switches the agent.

### Fixed

- A folder renamed or moved: its workspace and main tab take the new name (a name you gave the workspace stays; a
  folder renamed earlier is known by the Claude conversations kept under its old name), and the sidebar opens on it
  again, where it was. Before, the workspace kept the old name and the sidebar showed an empty list.
- Esc in the folder picker goes back to the workspace it was opened from; before, herdr showed a neighbour of the
  closed one.
- The folder picker's rows fit a narrow window (a half-screen Ghostty); before, they wrapped and a click landed a row
  off.
- The small windows (the folder picker, Cmd + Shift + L's list, the close question) keep a cell clear at both edges;
  before, the buttons touched the right border and the title the left one.

## [0.1.0] - 2026-11-01

First release.

### Added

- The installer: Ghostty, herdr, starship, gh, bat, git-delta, ripgrep and the JetBrains Mono Nerd Font with Homebrew,
  after a yes and only what the Mac lacks; their settings, twelve color themes (Ghostty's app icon too: herdr-fold's
  logo, the sheep, in each theme's colors), the Claude Code and Codex status lines, and herdr's Claude and Codex
  integrations; herdr settings of your own are kept. Run again, it updates after one question, with your earlier
  choices. See [Installation](docs/installation.md) and [Themes](docs/themes.md).
- Workspaces: one per repository from a folder picker, the agent beside the Conversations column and the sidebar above
  a terminal; keys for workspaces, tabs, panes and sessions; commit and push with an AI-written message; formatted
  copy; search in the Claude conversation. See [Using it](docs/usage.md) and [Keys](docs/keybindings.md).
- herdr's marketplace: `herdr plugin install princesshu/herdr-fold` (`herdr-fold 0.1.0`, the whole environment)
  opens the installer in a herdr tab; the sidebar and the Sessions list install alone from there too.
- Three herdr plugins; the first two also install on their own:
  - `herdr-fold.sidebar 0.1.0`: Files, Search, Changes and GitHub Issues with previews, on macOS, Linux and Windows,
    and the Conversations column with every workspace's Claude and Codex conversations. See
    [The sidebar](docs/sidebar.md).
  - `herdr-fold.sessions-view 0.1.0`: the Sessions list, each conversation under its name, with its state; the same
    name on its pane and on the tab it has to itself.
  - `herdr-fold.tab-layout 0.1.0`: new workspaces and tabs laid out, and the panes back after a restart.
- Remote Linux, macOS and Windows machines over SSH, with their own workspaces, sidebar and status line. See
  [Remote machines](docs/remote-machines.md).
- The uninstaller, which names what it leaves and where. See [Uninstall](docs/uninstall.md).
- Privacy: no telemetry; the plugins' state readable by you alone; a hand-added machine's host key shown and confirmed
  before the first connection; a privacy test over every file and every commit. See [Security](SECURITY.md).

[Unreleased]: https://github.com/princesshu/herdr-fold/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/princesshu/herdr-fold/releases/tag/v0.3.0
[0.2.0]: https://github.com/princesshu/herdr-fold/releases/tag/v0.2.0
[0.1.0]: https://github.com/princesshu/herdr-fold/releases/tag/v0.1.0
