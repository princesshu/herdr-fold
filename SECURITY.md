# Security

## Reporting a vulnerability

Report it privately to the maintainer, [princesshu](https://github.com/princesshu): on this repository's **Security**
tab, click **Report a vulnerability**. Please do not open a public issue for it.

## Supported versions

The latest state of the `main` branch.

## What the installer changes

The installer replaces settings files, adds a block to `~/.zshrc`, sets Claude Code's and Codex's status lines, and
links herdr plugins; it saves your own files first. The full list:
[What changes on your Mac](docs/installation.md#what-changes-on-your-mac). Installed from herdr's marketplace, the
plugin runs one check on herdr's start and on each pane's focus (`lib/offer_install.sh`: whether this version was
offered, by a mark file) and opens the installer in a herdr tab, with the same questions; nothing else runs before you
answer.

## The network

herdr-fold's own code asks two things of the network, each once a day at most and with the request alone (no id, no
cookie, nothing about you, your sessions or your models): api.github.com for its latest release (at once on Check now),
and raw.githubusercontent.com for LiteLLM's public table of model prices (`core/prices.py`, for Usage's costs: asked
only when costs are read, kept in `~/.local/state/herdr-fold/prices.json`; without an answer the last one, else the
table that came with herdr-fold, is used). Check for updates automatically in herdr-fold's Settings, under About (More's
Settings… in the TUI sidebar, the sidebar's Settings in the Herdr app), or `HERDR_FOLD_NO_UPDATE_CHECK=1` turns both
off: [A newer version](docs/installation.md#a-newer-version). Everything else goes where you ask: git to the
repository's remote, gh to GitHub, the AI tool to its own service.

Usage's token counts are read from Claude's and Codex's own session files on this machine and kept by the hour in
`~/.local/state/herdr-fold/usage-index.json`, readable by you alone: numbers, each session's id and folder, the
models' names; no message's text, and nothing of it leaves the machine. A monthly budget you set for an agent on an
API key is kept in `usage.json` there, with the budget notices you dismissed. The CSV is made from the same numbers,
with each conversation's title; a title that would start a formula in a spreadsheet is written after an apostrophe.
The Herdr app's Export CSV writes it only where macOS's own save panel says, on your press, and over a file there
only as that panel asks; the Budget… fields take an amount and nothing else, handed to herdr-fold's own code as one
argument.

## Remote machines

herdr-fold reaches remote machines over SSH with keys. For a machine you add by hand that `~/.ssh/known_hosts` does not
know yet, it shows the fingerprint of the machine's ED25519 key and asks whether to trust it (the default is no):
compare it with the machine's own before you answer. Only that key is trusted, and a machine that shows none is not
added. Machines from `~/.ssh/config` and your Tailscale network are trusted on the first
connection (ssh's `accept-new`) and checked against that key from then on.

## A folder you open

The sidebar treats the folder it shows as a stranger's, a download or a clone:

- git runs without the repository's own fsmonitor, signature check, external diff or text conversion, with nothing to
  read and no terminal to open, and stops after a time limit;
- the search reads plain files inside the folder only: never a link, a pipe or a device, nor a path a repository's
  own list names outside it; a program it runs stops after 60 s;
- the preview never shows a pipe or a device, and stops a program after 30 s; it draws an SVG or a page with nothing
  asked of the network and none of its scripts run (an SVG as an image, from its own bytes), so a file cannot learn
  who opened it;
- gh asks GitHub about its issues only once you show them;
- the Agent view reads the folder's agent files (`CLAUDE.md`, `.claude/`, `.mcp.json`) as text and starts none of its
  servers: Retry asks Claude to check one (`claude mcp get`, the name one argument, never through a shell), which
  Claude does only for a server it approved; the Herdr app's Agent panel reads the same, its Retry is the same check,
  and it runs nothing else of the folder's;
- a connector (an agent's MCP server) is changed only by the agent's own command, on your press, each one argv, the
  server's name one argument, never through a shell: Connect runs `claude mcp login <name>` or `codex mcp login
  <name>` in a terminal (the Herdr app: one with no pane, ended by Cancel or after ten minutes; the sidebar: a herdr
  tab), which opens your browser, and herdr-fold reads its output only for the address to open again (https, or http
  to this machine; opened, never kept); Sign out runs `mcp logout <name>` (a claude.ai connector's and a Codex
  server's; for a Claude server added by its address herdr-fold only names Claude's command); Add runs `claude mcp add
  --transport http --scope local|user <name> <url>` or `codex mcp add <name> --url <url>` once the name is letters,
  digits, `-` and `_` and the address https (or http to this machine) with no user or password in it; Turn off and Turn
  on give Claude its own `/mcp disable <name>` or `/mcp enable <name>` in a conversation of that folder (sent by the app
  to an idle Claude, typed but not sent by the sidebar). herdr-fold writes none of Claude's or Codex's files itself, and
  no token is read, kept or printed: the sign-in is between the agent, your browser and the service;
- a chat's + menu in the Herdr app: Upload from computer… opens macOS's own file chooser (`osascript`, a fixed script,
  the chat's folder its one argument) and keeps the paths you picked only until the message is sent, as `@path` in its
  words (herdr-fold reads none of the files); Add context… lists the folder's file names (`core/search.py`, as a search
  walks them, and git's status), never their content; a connector's switch gives Claude its own `/mcp disable <name>` or
  `/mcp enable <name>` in that chat, and Connect on a sign-in's step in the timeline is the Agent panel's Connect
  (`claude mcp login <name>`, then `claude mcp get <name>`); a server's name from a session file reaches a command only
  as one argument, checked first, and is drawn as text;
- the agents' list asks each installed agent whether it is signed in: `claude auth status --json` (kept of its answer:
  signed in or not, the way, the plan's id as a word; never the e-mail or the organization) and `codex login status`
  (its exit code, and whether its words start as an API key's do: what follows that start may hold a masked key and is
  neither looked at nor kept). Sign in, on your press, runs the agent's own
  login (`claude auth login`, `codex login`, `gemini`: fixed words, one argument each) in a terminal tab; herdr-fold
  reads nothing of it and keeps no token. An agent's install line is only shown and copied, never run;
- an issue handed to the agent goes as its number only, as anyone can write an issue.

A repository's filters and hooks still run when you stage, show a diff, commit or sync, as with git in a terminal:
open only folders whose `.git` you trust. The details:
[What it reads and writes](src/plugins/sidebar/README.md#what-it-reads-and-writes).

## A chat you delete

herdr-fold's file operations refuse everything under `~/.claude`, `~/.codex` and herdr's state, and it writes the
agents' files in two cases only. A form's Save in the Agent panel changes one key of a settings file, from a fixed
list of keys, in the layer you choose, never your organization's:
[The agent's harness](docs/harness.md#what-each-edit-writes). The other is Delete… in Chats, for a closed chat of
the list, once you answer its question. Its own file is then moved to the system's Trash, never unlinked (on a Mac
the Finder's Put Back restores it):

- Claude's: `~/.claude/projects/<folder>/<id>.jsonl`, and the folder `<id>` beside it, where its subagents' files are;
- Codex's: `~/.codex/sessions/<year>/<month>/<day>/rollout-…<id>.jsonl`, whose first line names that id.

The file is checked by its real place first (`core/fileops.py`, `trash_chat`): the id is one (letters, digits, `.`,
`_`, `-`), and nothing of another name or depth, no link in the file's place, no folder linked out of the agent's
own, and no other folder is moved. A chat herdr sees an agent in is refused, asked again as the file is about to go.
The archive mark and the name herdr-fold kept for it are dropped; nothing else of the agents' changes (their history,
settings and Codex's `session_index.jsonl` stay as they are), and herdr-fold's token and commit indexes only stop
finding the file.

## Your AI tools' usage limits

The status lines keep the 5-hour and weekly limits Claude tells them, with their reset times, in
`~/.local/state/herdr-fold/limits/`, readable by you alone: nothing of the session, its folder or its model. The usage
limits are also read from Claude's own cache in `~/.claude.json` (the percentages and reset times, never its account)
and from Codex's newest chat; neither tool's files are written.

## What not to post in an issue

Remove these from logs and output before you paste them anywhere:

- SSH keys, tokens and passwords;
- your name and e-mail address (the installer shows git's commit author), folder paths and project names;
- `~/.config/herdr-fold/machines.txt` and other machine names and addresses;
- herdr's logs;
- the text of your Claude or Codex chats.
