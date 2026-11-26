# The agent's harness

An agent's harness is what Claude Code, Codex, OpenCode or Copilot CLI starts with in a folder: its model and effort,
its rules, skills, subagents, permissions, hooks and connectors, and what all of that costs. herdr-fold shows it,
changes a part of it from a form, and draws it as a graph, for Claude and Codex in full and for OpenCode and Copilot as
far as they tell ([below](#the-agent-panel)). Both clients have it, in the same words: `core/` reads the files, words
the rows, plans each change and writes it.

| | The TUI sidebar | The Herdr app |
|---|---|---|
| The setup | the Agent view, the row's fifth button (`5`) | the Agent panel, the dock's fifth tab |
| The graph | a tree in the preview tab (`g`) | the Agents tab's Graph, a canvas |
| Usage in full | the Usage view, over the tab (`U`) | the Agents tab's Usage |
| Runs | the Runs view, over the tab (`r`) | the Agents tab's Runs |

This page calls the first one the Agent panel in both. The TUI's keys inside the view are in
[the sidebar's README](../src/plugins/sidebar/README.md#keys).

## The Agent panel

It shows the agent picked for the folder, kept until another is picked (the TUI: per folder, in every tab; the app:
per space). With none picked it is the tab's Claude, Codex, OpenCode or Copilot, else the one herdr-fold started last.
The setup is read when the panel shows, when the folder's rules and settings or the agent's own folder change (the
app), and every 30 s while it shows; behind another view it is looked at every 5 minutes, for the dot on its button. A
space on another machine says `On <machine>: with a later version` in the app.

### The head

- The first row names the agent and the folder, `Claude in lumen-api ⌄`. A press on it (the TUI: Enter too) opens
  `Agents on this Mac`: the installed agents, ✓ on the one shown, each with its plan's word (`Max`, `Plus`, `API key`;
  never an e-mail) where the agent tells one, or `sign in` in yellow where it says it is signed out. A pick makes the
  whole panel that agent's. Under a rule, dim, `Not installed`: the agents herdr-fold knows that are not on this
  machine; a pick shows how that one is installed, and the space keeps its agent. Narrow, a plan's word goes before
  a name is cut. The list's words are core's (`agent_state.py`'s `listed()`).
- Under it, muted, the model, the effort and what the agent starts with of its window: `Opus 5.5 · High · starts at
  34.2k of 1M`, measured from the first turn of the folder's newest chat, `starts at ~21.9k` estimated where the
  folder has none. A press on the model or the effort opens their form.
- At the line's end the problems: `1 failed` in red, `1 sign in` in yellow (chips in the app). A press chooses that
  row.
- Then a bar of what loads at start by share: the rules read always, the skills' listing and the connectors' tools.
  The TUI draws it as a ━ rule across the pane. There is no legend: each section's head wears its part's swatch.
- The app's head ends with a filter's button: every word typed must be in a row's name, note, state or tag. The TUI
  has no filter.

An agent with no setup to show says why in its place, in core's words:

- not signed in: Sign in runs the agent's own login (`claude auth login`, `codex login`, `gemini`) in a terminal tab.
  The panel asks the agents again every 5 s, 10 minutes at most. herdr-fold keeps no token. OpenCode is never said to
  be signed out: with no provider it runs its free models. `opencode auth login`, in a terminal, connects one, and once
  `opencode auth list` names it, OpenCode is signed in. Copilot is never said to be signed out either: it has no
  command that tells, and its token is its own (`copilot login` signs in, `/user` in Copilot shows the account).
- not installed: its vendor's install line with Copy, and a link to its page. herdr-fold runs no installer.

An agent whose setup herdr-fold does not read (Gemini CLI, signed in) has its head alone.

OpenCode's setup is read as far as OpenCode tells it (`core/opencode_setup.py`, V2's): Rules, the instructions it
reads (its config folder's `AGENTS.md`, else `~/.claude/CLAUDE.md`; then each folder's `AGENTS.md`, else its
`CLAUDE.md`, from the folder up to the home folder, the nearest first), and Connectors, the MCP servers of your own
config files (`opencode debug config`, run in the home folder) and the project's `opencode.json` and `.opencode/`,
read as text and never run: a project's config can load its plugins, code. Each `off` where its config says so, else
`not checked`; the head's model
and effort are its config's. It has no Subagents, Skills or Permissions here, nothing of it is changed from the panel
(no form, no +), it has no graph, and Usage says its limits are not told: it keeps no plan's limits on the machine.

Copilot's setup is read the same way (`core/copilot_setup.py`, Copilot CLI 1.0's): Rules, the instructions it reads in
the order `copilot instruction list` gives them (your `~/.copilot/copilot-instructions.md` and
`~/.copilot/instructions/`; then in the repository's top, and in the folder below it, `.github/copilot-instructions.md`,
then `AGENTS.md`, `CLAUDE.md`, `.claude/CLAUDE.md` and `GEMINI.md`, then `.github/instructions/` and `.claude/rules/`),
an `.instructions.md` file's `applyTo` read as the files it is for; and Connectors, your servers as `copilot mcp list`
gives them, run in the home folder (yours, your plugins', its built-in plugins'), and the project's `.mcp.json` (else
`.github/mcp.json`), read as text from the folder up to the repository's top, the nearest winning, as Copilot merges
them. Each `off` where Copilot or a settings file's `disabledMcpServers` says so, else `not checked`: Copilot starts a
project's servers only in a folder you trusted, which herdr-fold does not read. The head's model and effort are its
settings' (`~/.copilot/settings.json`, then the repository's `.github/copilot/settings.json` and `settings.local.json`
over it). The rest is as OpenCode's: no Subagents, Skills, Permissions, form, + or graph, and Usage says its limits
are not told: Copilot asks GitHub for its plan's use when its `/usage` shows it, and keeps none of it on the machine.
`COPILOT_HOME` moves its own folder, as it does Copilot's.

### The sections

Usage, Subagents, Rules, Skills, Permissions and Connectors, in that order. Each head has a chevron (none on an
empty section), its title and its count; Rules, Skills and Connectors end with their swatch and what they load
always (`■ 5.4k`), Permissions with its rules by behavior (`12 allow  3 ask  2 deny`). A section shows its first
five rows, its problems and what the open chat used, then `N more`, which opens the rest in place.

| Section | What it shows |
|---|---|
| Usage | a row an agent, with its limits or its month's cost: [Usage](#usage) |
| Subagents | your own, the project's and the plugins', each with its model and tools (`Opus · 4 tools`, `Haiku · read-only`); Claude's own in one row tagged `Built-in` |
| Rules | the rule files the agent reads, each with when it loads (`when src/lumen/** is read`, `imported by CLAUDE.md`); the count is what always loads |
| Skills | the skills, yours, the project's and the enabled plugins' |
| Permissions | `Mode` (Codex: `Approval`), then `Sandbox` (Claude's Bash sandbox and its hosts, `Bash · 2 hosts`; Codex's `Workspace write`), the conflicts, the rules, and under `Hooks` every hook of every settings layer, the ones that decide a call first (`guard.sh on PreToolUse · Bash`) |
| Connectors | the MCP servers, with their state as the agent's newest chat told it |

Mode, Approval and Sandbox are always there. Where no file sets one, its tag is `Default` and its note is the agent's
own default (`Manual`, `off`, `Codex's default`).

What opens and folds differs: in the TUI, Usage and Connectors are open and the rest folded until opened, kept in
every tab; in the app every section is open but Subagents, kept per space.

### Usage

The panel's first section: a row an agent, the agent shown first.

- On a plan: the plan's word and each window's bar and percent in its level's color, green under 50, yellow from 50,
  red from 80 (`Claude Max   5h ▰▰▰▰▱ 72%  wk ▰▱▱▱▱ 16%`); where the account has a model's own weekly limit, a third
  window labelled with the model's name (`Fable ▰▰▱▱▱ 38%`). `0%` is a window that reset with nothing run since, `–`
  one run in since with no reading yet. The reset stands under the row only while a window is yellow or red (`5h
  resets 14:46`, in this machine's time).
- On an API key: the month spent against the budget you set (`Codex  API key   ~$56.60 of $150`), yellow on pace
  past it, red once spent; the pace under it only then (`on pace for ~$58 by November 30`).
- The chosen row's properties say each window's reset, the reading's age and Open Usage.
- Folded, the head shows one figure: the agent shown's tighter limit (`Claude 5h 72%`) or its month, or another
  agent's where that one is yellow or red and stands worse.
- A narrow panel drops a model's own week first (the app under 364 px, the plans' words making room for it under 392;
  the TUI keeps it while it is the tightest), then the bars (the app under 300 px), then the looser windows. Before
  any reading: `Not known yet`.
- The agent shown always has its row: with no reading of its limits it says `limits not told`, and its properties
  say why (an agent on an API key has no such limit, so no such row).
- What could not be read is said in its place, never left out: where Codex gives no list of its servers
  (`codex mcp list`), Connectors holds one dim row, `not read`, with the reason in its properties, and no count.

Every dollar figure herdr-fold computes wears `~`: an estimate from the chats' token counts at list prices. The
budget you set wears none.

The limits are Claude's and Codex's own numbers. For Claude the windows are the ones its `/usage` reading names
(cached in `~/.claude.json`, and read only while it is the signed-in account's), each at the highest use it or any
chat's status line told since: use only grows in a window, so an idle chat's older reading never takes it back, and
another weekly limit one chat tells is left out. Without that reading (a remote machine, before Claude's first look)
a chat's own reading stands. A model's own week is Claude's reading's alone (its `weekly_scoped` rows, every one it
lists), as no chat's status line tells it. Codex's are its newest chat's. A limit past its reset is left out. What
the status line keeps for this is in [The status line](usage.md#the-status-line). A second Claude account in its own
`CLAUDE_CONFIG_DIR` keeps its own reading, for its own status lines; Usage shows the account the app runs with.

### A row and its properties

One column of marks stands before the names: ✕ red for a connector that failed, a yellow dot for one to sign in to
or for a conflict, a green dot for what the open chat used. On and off have no mark. A row ends with its state (`32
tools`, `on`, `failed`, `sign in`, `off here`; `allow`, `ask`, `deny`) and where it comes from (Global, Project,
Local, Managed, claude.ai, Built-in, a plugin's name), each in a column; the tags are muted, never a hue. A known
service's connector is named as its maker writes it (Sentry, ElevenLabs, fal, FLUX), its name in the agent's config
in its properties (`Name`), and wears its logo where the maker's licence gives one (SVG Logos'; FLUX and Meshy their
letter; the TUI: its glyph or its letter). A file both agents read carries both agents' icons in the app.

A conflict is a permission a deny or an ask hides: a yellow dot, the rule, and its sentence under it (`deny in
Project hides allow in Global`).

A skill, a subagent or a connector turned off for the folder stays a row, dim, with `off here`. With every hook off,
the `Hooks` line says `off here` over dim rows.

A press chooses a row. Its properties are label and value: where it is from, what it runs or its address, a rule's
paths, a subagent's tools, a hook's event, how often the chat used it, an error in words (the file it names in its
tip), a rule's first lines or a skill's description. The TUI lays them under the row, the app under the layers. Then
its buttons:

| Button | What it does |
|---|---|
| Open | the row's file in the preview tab |
| Show in graph | [the graph](#the-graph), on that row's node |
| Retry | on a Claude server that failed or was never checked: Claude checks it (`claude mcp get`), the mark a spinner meanwhile |
| Connect | on a server to sign in: the agent's own login (`claude mcp login <name>`, `codex mcp login <name>`) in a terminal, which opens your browser; the row says `signing in` with `Open the page again` and Cancel, ten minutes at most |
| Sign out | on a claude.ai connector and a Codex server signed in through Codex: the agent's own `mcp logout <name>`; for a Claude server added by its address the properties name the command instead |

### Adding a connector

A connector is added from Connectors' + (the TUI: More's `Add from claude.ai…` and `Add by URL…`, or `a`). `From
claude.ai…` opens claude.ai's connectors page. `By URL…` is a form: Name (letters, digits, `-`, `_`), URL (https, or
http to this machine) and, for Claude, For: this folder (Claude's `local` scope) or `All projects` (`user`). `Add and
connect` runs the agent's own `mcp add`. Codex adds for every folder. Under them, by name and logo (the TUI: `Add
fal…`), the media services and Figma not added yet: each fills the form with its maker's hosted MCP, signed in to in the
browser by Connect, never a key (fal `https://mcp.fal.ai/mcp-relay`, ElevenLabs `https://api.elevenlabs.io/v1/mcp`, FLUX
`https://mcp.bfl.ai`, Runway `https://mcp.runwayml.com/mcp`, Figma `https://mcp.figma.com/mcp`).

### Media services

A media service (ElevenLabs, fal, FLUX, Runway, Higgsfield, Luma, Cartesia, Meshy) bills in credits, not tokens: its row
says what it makes (`voice`, `image, video`) and its calls today in place of its tools and their cost (`7 calls today`,
`no calls today`), each MCP call of that server in today's Claude and Codex chats on the machine counted once
(`core/calls.py`); what its tools load at start is in its properties (`Loads`). Money is never shown: no service tells a
call's price in the chat.

The prompt-writing know-how for a service (its style, ratio and what to avoid) is a skill of your own (`kling-video`,
`hero-image`), listed under Skills with its cost like any other; herdr-fold ships none. What such a service makes shows
in the preview tab with where it came from: in the app ([The preview tab](app.md#the-preview-tab)) and in the TUI
([Pictures, audio and video an agent made](usage.md#pictures-audio-and-video-an-agent-made)).

## Changing the setup

A row that can be changed holds its form: in the app in the chosen row's properties, in the TUI under the row.
The head's line holds the form of the model and the effort, Permissions' head the form of a new rule (the app: its
+; the TUI: `a`), the `Hooks` line the switch of every hook.

Every form works the same way:

1. It opens with the values in effect. Nothing is written yet.
2. A control touched shows the rest: `Saved in` with the layers to choose from and the chosen one's file, the lines
   the save takes out and puts in, when it applies (`Applies now`, `From the next session`), in yellow what would
   override it (a stronger layer, the environment, a rule that hides the new one), and in red why it cannot be saved.
   The change is tried on the file as it is, so a file that cannot take it says so here.
3. Save (`Add`, `Remove`) writes one key in one file. A removal asks once first (`Remove from Project?`).
4. The setup is read again, and a line at the panel's foot says what was saved, with Undo.

In the TUI → (or Enter) puts the keys in the form, ↑ ↓ step through its controls, ← → or Space choose, Tab changes
the layer, Enter saves and Esc leaves; `x` on a rule removes it. In the app Tab steps, Enter in a field saves and Esc
cancels.

### The layers and their files

| Layer | Claude's file | Codex's file |
|---|---|---|
| Global | `~/.claude/settings.json` | `~/.codex/config.toml` |
| Project | `.claude/settings.json` in the folder | `.codex/config.toml` in the folder |
| Local | `.claude/settings.local.json` in the folder | none |
| Managed | your organization's: read, never written | none |

A later layer wins over an earlier one, Managed over all. Codex reads a project's file only once it trusts the
folder; the form says so (`Codex reads it once it trusts lumen-api`).

### What each edit writes

Claude's:

| Edit | Key | Layers (first offered) | Applies |
|---|---|---|---|
| Mode | `permissions.defaultMode` | Global, Project, Local (Project) | from the next session |
| Model | `model` | Global, Project, Local (Project) | from the next session |
| Effort | `modelSettings.<model>.effortLevel` for Opus 5.5 and later, else `effortLevel` | Global, Project, Local (Project) | from the next session |
| Bash sandbox on or off | `sandbox.enabled` | Global, Project, Local (Project) | now |
| A sandbox host added or removed | an item of `sandbox.network.allowedDomains` | Global, Project, Local (Project) | now |
| A rule added, changed, moved or removed | an item of `permissions.allow`, `.ask` or `.deny` | Global, Project, Local (Project) | now |
| A conflict resolved | the hiding rule in `permissions.deny` or `.ask`, removed or narrowed, where it is | none to choose | now |
| A skill off | `skillOverrides.<name>: "off"` | Project, Local (Local) | from the next session |
| A subagent off | `Agent(<name>)` in `permissions.deny` | Project, Local (Local) | from the next session |
| A connector off | `{"serverName": <name>}` in `deniedMcpServers`; a project's `.mcp.json` server: its name in `disabledMcpjsonServers` | Project, Local (Local) | from the next session |
| A project's server approved | its name in `enabledMcpjsonServers` (and out of `disabledMcpjsonServers`) | Project, Local (Local) | from the next session |
| Every hook off | `disableAllHooks: true` | Global, Project, Local (Local) | now |

Codex's, at the top of `config.toml`:

| Edit | Key | Layers (first offered) | Applies |
|---|---|---|---|
| Model | `model` | Global, Project (Global) | from the next session |
| Effort | `model_reasoning_effort` | Global, Project (Global) | from the next session |
| Approval | `approval_policy` (Ask on request, Never ask) | Global, Project (Global) | from the next session |
| Sandbox | `sandbox_mode` (Read only, Workspace write, Full access) | Global, Project (Global) | from the next session |

A form opens on the strongest layer that already sets the value, else on the one first offered.

Notes on single edits:

- Mode: Manual, Edit automatically, Plan, Auto, Don't ask, Bypass permissions. Auto and Bypass permissions are grey
  outside Global, where Claude ignores them.
- Model and effort: the file takes effect from the next session. A running Claude chat can be switched at once with
  `Switch this chat now`: the app sends `/model` and `/effort` to it, the TUI types them into the tab's Claude for
  you to send. A model or effort set in the environment (`ANTHROPIC_MODEL`, `CLAUDE_CODE_EFFORT_LEVEL`) wins over
  every file, and the form says so.
- Sandbox hosts: a host that comes from an allow rule (`WebFetch(domain:…)`) has no ×; its rule's row removes it.
  `More options` opens the file for the rest (filesystem rules, excluded commands).
- A rule: a change in place keeps the rule's position in its list. A move between layers changes two files; if the
  second write fails, the first is put back. A Project rule in a repository says `In git: your team gets it with
  your next commit`.
- A conflict: `Remove the deny in Project`, or `Narrow the deny` with the rule to type; the new rule must be narrower
  and no longer hide the allow.
- The switches: turning a thing off writes one entry into the chosen layer; turning it on takes the entry out of
  every layer that has it. Claude's built-in subagents are switched one by one, by name. A subagent's deny rule also
  shows as a rule in Permissions: it is the same entry.
- Every hook off also stops herdr-fold's own hook in an app chat: its questions go back to Claude's terminal. The
  form warns of it.
- A connector Claude's own state turned off (`/mcp disable`, kept in `~/.claude.json`) is in no settings file. Its
  switch gives Claude `/mcp enable <name>` in the folder's chat (the app sends it once Claude is idle, the TUI types
  it into the tab's Claude); with no Claude there the form says what it waits for.

### What a save keeps

- Only the keys above are ever written, each with its own kind of value. The file is found by its layer's name,
  never by a path.
- A JSON file keeps every other key, the key order, its indentation and its line ends. `config.toml` is changed by
  line: the value inside its quotes, its spacing and its comment kept.
- An edit says what it expects to find. A file changed since the form opened is refused: `.claude/settings.json
  changed since: nothing saved`.
- A new file is yours alone (0600); an existing one keeps its mode.

### Undo

Each save gives back the edit that undoes it. The line at the panel's foot holds it until the next change (the TUI:
until Esc): Undo in the app, `u` or a press in the TUI. It puts the key back as it was, the rule at its place in its
list, and takes away what the save itself added. A file written the way Claude writes it comes back byte for byte.
One formatted by hand is rewritten in its own indentation on the first change, so Undo restores its content, not its
formatting. A file the save created goes with its Undo.

### What cannot be changed here

| What | Why | It says |
|---|---|---|
| A rule, server or entry of your organization | Managed files are never written | `Set by your organization` |
| A plugin's skill | it turns off with its plugin | `Turns off with its plugin` |
| A plugin's subagent | how a deny rule names one is not verified | no switch |
| Codex's rules | they live in `.rules` files, which herdr-fold does not write | `Codex keeps its rules in a file of their own: change it there` |
| A skill, subagent, hook or connector switch for Codex | its files have no per-folder off | no switch |
| Codex's granular approval | a table in the file, not one word | `Granular is set in the file` |
| Codex's trust of a folder | left to Codex | the form says when a folder is not trusted |
| A single hook, a rules file, a subagent's own file | not built yet | Open shows the file |
| A settings file that is a link, or whose folder is one | no file outside the agent's folders is written | `… is a link: change it where it lives` |
| A file not written in the plain way | a key set twice, a JSON file that is no object, a TOML value in a table or over several lines | `… is not written in a way herdr-fold changes: change it in the file` |

## The graph

How the agent is wired in the folder (`core/graph.py`), for Claude and Codex alike. The app draws it on a canvas in
the Agents tab, one a space (the palette's Agents, or Show in graph on a row). The TUI writes it as a tree in the
preview tab, titled `graph: Claude in lumen-api` (`g` in the Agent view, More's Show graph, or a row's Show in
graph).

Wiring has three parts:

- In: the rules, the hooks that add context and the skills, each with when it loads (`always · 2.4k`, `when
  src/lumen/** is read`). A skill the project owns or the chat used is a node; the others fold into one (`15 more
  skills`).
- The agent, with its model, effort and mode (Codex: its approval policy, `Ask on request`) and the hooks that watch
  it, and its subagents under it.
- Uses: the tools and the connectors, each with its state.

An edge is solid for what always loads and dashed for what loads on demand; a connector to sign in to is yellow, one
that failed red. An edge to a tool or a connector carries its gates, each a verb and its object: `ask`, `allow
pytest, git status +1`, `deny git push`, `hook guard.sh`. The TUI writes them in brackets after the tool, each verb
in its color.

Where the folder has a chat, `This chat` shows the same graph with what that chat ran: each first use numbered in
its order, the agent and each subagent with its model, what it cost and its share (`core/costs.py`), a tool and a
connector with their calls. The app lights the edges that ran and draws the one a call still waits on wider; its head
says the chat's whole (`This chat · ~$4.12`). The TUI writes the path as one line (`1 api-routes → 2 Read · Edit ·
Write → 3 Bash`); `c` shows This chat and `w` Wiring.

In the app a press chooses a node: its properties, Open for its file, and `Show in Agent`, which shows the Agent
panel on that node's row. A node drags and stays where it is let go, for that space, folder and agent; a double
click beside the nodes lays the graph out again. A canvas too narrow brings the columns nearer first, then scrolls.
The app reads the graph again as the setup changes; the TUI reads it when asked, and `g` again reads it anew.

The graph only shows: changing a server or a rule stays the Agent panel's.

## The Usage view

The one place usage is read in full: what the agents used and what that cost, each message at its own model's
prices (`core/report.py`). The TUI opens it over the tab's panes from the ↗ on Usage's head, `U` or More's Open
Usage (macOS and Linux); in the app it is the Agents tab's Usage, opened by the panel's Open Usage, the palette's
Usage or a chat's `Usage`.

An agent on a plan reads `API value`: what the same use would cost on the API, nothing you pay. One on an API key
reads `spent`.

- On top the period (`Today`, `7 days`, `30 days`, the month) and the agent (`All agents`, `Claude`, `Codex`). The
  app's head also picks the spaces it covers.
- The summary: an agent a cell (`~$130.90 API value`, `no charge on the plan`; `~$46.08 spent in 7 days`), then the
  tokens with the share read from the cache.
- `Per day, by model`: a day a column, its models stacked in their colors.
- For each agent on an API key, its month against its budget, with the pace it is on (`~$18.40 of $50 · on pace for
  ~$46`).
- `By project`, a bar a folder.
- `Chats` by cost: its space, turns, tokens, the cache's share and its cost.
- `Models`: each with its input, cache write, cache read and output tokens and its cost; one with no price says `no
  price`, never $0.
- The foot says once where the prices come from: `~ estimated from token counts at Anthropic's and OpenAI's list
  prices (Nov 9, 2026); on a plan, what the same use would cost on the API`.

The summary's and the charts' dollar figures wear `~`; the tables' cells do not.

`Budget…` on a month (the TUI: Enter too) sets the monthly budget of an agent on an API key; an empty field takes it
away. It is kept in herdr-fold's own `~/.local/state/herdr-fold/usage.json`, one for both clients. From 80% of it
spent, or on a pace past it, an app chat says so once a month over its prompt.

The differences: the app has `Export CSV` (the period where macOS's save panel says, a row for each day, agent,
model and chat) and shows a day's or a row's figures under the pointer; the TUI has neither, steps the periods with
Tab and the agents with `a`, and scrolls with ↑ ↓.

The chats are read into herdr-fold's token index first (`core/tokens.py`): a first read of many sessions takes a
while, and the view says `Reading chats…` until the figures are whole. It reads again every minute while open.

## The Runs view

What the agents ran in the background, away from a chat (`core/runs.py`): Claude's background sessions (`claude
--bg`, as `claude agents --json --all` lists them), Codex's `codex exec` runs (their rollouts) and Codex's cloud tasks
(`codex cloud list --json`). The TUI opens it over the tab's panes from More's Open Runs or `r` in the Agent view
(macOS and Linux); in the app it is the Agents tab's Runs, opened by its head's switch, the palette's Runs or the status
bar's `1 run working`.

- A row a run, under `Running`, `Today`, `Yesterday` or `Earlier`: a spinner while it works (the waiting dot while a
  background session needs you), a red ✕ for one that failed, no mark for one done; its name (the prompt's start), its
  agent, its folder (the app's), when it started, what it made (`2 files`, `PR #61`, `2 images`, `no change`) and its
  cost (`~$0.31`, from the token index as Usage counts it; `–` for a cloud task, whose list tells no tokens).
- A PR is the one `gh pr create` printed in the run; the media are the run's written files of a picture's, a sound's or
  a video's type, the pictures shown small in its properties.
- The chosen run's properties under it: `Ran as` (`Background session · Claude · Opus 5.5`, `codex exec`, `Codex
  cloud`), its folder, day and length, its prompt, what it does now or made, its cost; then its buttons, each the
  agent's own command: `Attach` (`claude attach`, in a terminal, where a permission it waits on is answered) and `Stop`
  (`claude stop`) while it works; `Open as chat` (a background session leaves the list with `claude rm` and is a chat
  in Chats from then on), `Run again` and `Remove` once it ended; a cloud task's `Show diff` (`codex cloud diff`),
  `Apply to lumen-api` (`codex cloud apply` in the space's folder) and `Open on the web`. What a press did, or the
  agent's own words where it did not, is said under them.
- `New run` (the TUI: `n`) asks the agent, the prompt, where (Codex: this Mac or its cloud, in one of the environments
  its tasks ran in) and when, and starts it with `claude --bg`, `codex exec` or `codex cloud exec`. `On a schedule`
  opens a new Claude chat with `/schedule` and your words, where Claude asks the rest; Codex schedules only in its
  own app, so its choice is greyed.
- The list's foot says that scheduled cloud runs are not listed: Claude keeps its routines at claude.ai (the app's
  `Claude's routines` opens a chat with `/schedule list`, Claude's own way to list them), Codex its scheduled tasks in
  its app. herdr-fold never schedules anything itself.

The Chats list leaves out what Runs lists, so nothing is in both: a `codex exec` run always, a background session
once Runs (or the app's status bar) has read Claude's list. A `claude -p` run stays in Chats: its transcript is told
apart only by a field Claude Code does not document. Claude's list is kept 30 seconds; the view reads again every 30
seconds while open, every 5 while a run works.

## What it reads and writes

- It reads the agent's own files as text: the folder's and the home's rules, settings, skills and subagents
  (`CLAUDE.md`, `AGENTS.md`, `.claude/`, `.mcp.json`, `~/.claude`, `~/.claude.json`, `~/.codex`), and the agent's
  session files for the servers' state, what a chat used and its token counts. OpenCode's config is what `opencode debug
  config` lists, run in the home folder, and a project's `opencode.json` and `.opencode/` read as text, never run.
  Copilot's servers are what `copilot mcp list` lists, run in the home folder, and a project's `.mcp.json` read as text;
  its settings and instructions are read as text. A server's command line and address show; its environment, its
  headers' values and an address's query never leave the reader.
- It writes an agent's settings file only on a form's Save, one key of the list above.
- Every other change is the agent's own command, run on your press: a server checked, a sign-in, a sign-out, a
  connector added, `/mcp enable`, a run started, stopped, removed or applied.
- It keeps no token and reads none. Its own state (the token index, the budgets, the limits it was told) is in
  `~/.local/state/herdr-fold/`.
