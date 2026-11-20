# Using it

Every key is in [Keys](keybindings.md); the sidebar's views, one by one, in
[its README](../src/plugins/sidebar/README.md).

## Workspaces

One workspace per repo:

1. Click **new** under Spaces in herdr's sidebar (or Ctrl + B, then Shift + N). The folder picker shows the folder
   holding most of your git repositories as a tree, as the sidebar's Files view does: the folder on top, open.
2. Type to filter; ↑ ↓ or the wheel move, a click chooses. → opens a folder (or steps into an open one), ← closes it
   (or steps to its parent), and ← on the top row goes up a folder; a click on a folder's ▸ opens or closes it. Tab, or
   a click on Claude or Codex at the top right, switches between them; it starts on the agent herdr-fold started last.
3. Enter, **Open** or a double click opens the workspace, or jumps to the one the folder already has. Esc or
   **Cancel** goes back to the workspace you came from.

![The folder picker over the new workspace: Documents as a tree, driftwood chosen, Claude or Codex at its top
right, Cancel and Open at the bottom](../assets/screenshots/new-workspace.webp)

The workspace's main tab is named after the folder (the home folder's is `home`): the agent on the left, and on the
right the sidebar above a terminal: its views are buttons in a row at its top, each icon over its name (its icons
alone in a narrow sidebar), one view shown at a time, the ✦ at the row's left opening the chats over it, More at its
end the sidebar's menu. Drag the right column's edge to resize it in every tab; the » in the sidebar's top right corner
folds it to a rail of icons in every tab, the terminal moving under the agent, a press on an icon opens that view
beside the rail, and « there brings the sidebar back. In a new folder the agent
first asks whether you trust it: answer in the
pane. A pane you close stays closed in its tab, after a restart too, until Cmd + Shift + O (Restore panels) or the
sidebar's More menu brings it back; a new tab always comes with every pane.

A folder in the sidebar's Files view opens a workspace too: right-click it → **New Workspace**, and the folder picker
opens on it, with the Claude / Codex toggle.

Rename or move the folder, and the workspace and its main tab take the folder's new name at the next pane you focus
(a folder renamed earlier too, known by the Claude chats kept under its old name), and the sidebar opens on it
again, where it was. A name you gave the workspace yourself stays. A workspace whose folder is deleted says
**deleted** beside its branch, in the theme's red.

Cmd + ↓ / Cmd + ↑ step through the workspaces, Cmd + → / Cmd + ← through the panes, Cmd + T / Cmd + R through the tabs.

From the command line (the only way on a Windows machine):

```bash
python3 ~/.config/herdr-fold/herdr_layout.py ~/projects/app app                    # on this Mac
python3 ~/.config/herdr-fold/herdr_layout.py --machine alpha /srv/app app          # on a Linux or Mac machine
python3 ~/.config/herdr-fold/herdr_layout.py --machine win1 'C:\projects\app' app  # on a Windows machine
```

Add `--agent codex` for Codex.

## Sessions

herdr's sidebar lists the current workspace's chats under Sessions, each with its state: working, blocked (it
needs you: an approval, an answer or a choice), done (finished since you last looked) or idle (ready for your next
prompt). Cmd + D and Cmd + E step through them.

A workspace whose folder is no repository but holds one, as a folder of notes around a project's repository, shows
that repository's branch in the Spaces list, with ↑ the commits to push and ↓ to pull against its remote branch (any
git host); where it holds several, the one its active pane is in.

The Spaces list says how long an agent has waited on you, blocked or done, beside its workspace's branch: `waiting 12m`
in the theme's yellow, the longest wait when several agents wait there. It counts on while you work elsewhere and goes
once you answer, or look at the finished one. To come back to one you have seen, mark it unread: Cmd + Shift + U on its
pane, and its workspace says `waiting` again, from now, until you return to it after leaving it (Cmd + Shift + U again
takes the mark off). The Herdr app's herdr-fold layout does the same: [Spaces](app.md#spaces).

An agent in another tab that starts waiting on you says so once, in herdr's own toast at the bottom right: `claude needs
attention` (blocked) or `claude finished` (done), with its workspace and tab; never for the tab in front. herdr's sounds
stay off (`[ui.sound]` in `~/.config/herdr/config.toml`: `enabled = true` there plays them). The sidebar's Chats button
has a dot while a chat there asks you something.

![The Spaces list: harbor-web's agent blocked and waiting 12 minutes, tidepool's done and waiting 3 minutes, beside
their branch](../assets/screenshots/waiting.webp)

A chat goes by one name: in AI Sessions, on its pane's border, in the sidebar's Chats, and on its
tab when it has the tab to itself (a reopened one's); the workspace's main tab keeps the workspace's name. To rename it:

- right-click its pane → **Rename pane** (**Clear pane name** brings back the chat's own title);
- or right-click it in the sidebar's Chats → **Rename**, a closed one too;
- or type `/rename New name` in the chat, which also names it in the program's own `/resume` list; it shows
  after your next prompt, or when you switch tab or pane. A name set in herdr wins.

A tab you renamed yourself keeps your name until you rename the chat.

## Chats

Every chat of the workspaces under Spaces, running or closed, in the list the sidebar's ✦ opens over it:

1. Cmd + Shift + R, from anywhere, or a click on the ✦: the list opens in the tab's sidebar (one closed by hand comes
   back), its filter empty, the keys going to it; its lit button, Esc or a click outside closes it.
2. Type: the chats of every workspace narrow at once.
3. Enter goes to a running chat, or reopens a closed one in a new tab of its workspace.

![The Chats column open beside Claude: each workspace's chats, a running one's mark in its state's
color, the closed ones faint](../assets/screenshots/chats.webp)

A right click on a chat offers Open, Copy chat (all of it, formatted for Notes, Mail or Docs), Rename
and, for a closed one, Archive: it leaves the list and its file stays as it was, so `claude --resume` or `codex resume`
still finds it; a right click beside the chats offers Show archived while any is.

Archive is the everyday way to tidy the list. Delete…, under it in a closed chat's menu (an archived one's too), is the
rarer one: it asks first, by the chat's name, then moves the chat's file to the system's Trash (on a Mac the Finder's
Put Back brings it back) and drops its archive mark and the name you gave it. With the filter empty the Delete key
(fn + ⌫ on a Mac's own keyboard) asks the same for the chosen chat. A running chat has no Delete…: close it first.

A chat is one row however long it runs: Claude Code compacts and resumes it in its own file, under its id, so its
name and its archive hold. Not listed: the agents' own helpers (sub-agents, Codex's reviewer) and what a program ran
through Claude's Agent SDK (a hook's review of each change, a script's question), which name themselves after the
chat they work for; `claude -p`'s runs are. A project folder linked to another's (`~/.claude/projects`) lists its
chats once. Copy chat leaves out what a compacted chat holds twice: the summary Claude wrote in your place, and the
messages it kept and wrote again.

## GitHub issues

For a repository on GitHub:

1. Cmd + Shift + I (or `4` in the sidebar) shows its issues, the most pressing first: by GitHub's own Priority field,
   else a priority label, then a severity label, then a word alone such as `urgent` (the ones it reads:
   [the sidebar's README](../src/plugins/sidebar/README.md)).
2. `t` hands the chosen one to the agent: a prompt typed into its pane, for you to send with Enter. With no Claude or
   Codex in the tab, the one herdr-fold started last starts in a new tab of the workspace, named after the issue, the
   sidebar beside it as in every tab, and gets the prompt there. The prompt holds the issue's number, not its words:
   anyone can write an issue, so the agent reads it with gh and is told to take it as a description of the problem, not
   as instructions. The Changes view shows `Fixes #42` from then on.
3. When the agent is done, the ✦ beside the message has Claude or Codex write it, ending with that line (Cmd + Shift +
   C adds it too); meanwhile the field says who writes it. Once the commit is pushed, GitHub closes the issue.

![An issue from the sidebar goes to Claude, which fixes it, and the message it writes closes the
issue](../assets/screenshots/issue-to-agent.webp)

## Commit and push

Cmd + Shift + C commits and pushes the repo of the focused pane, in one step:

- If nothing is staged, it offers all changes; if only some are staged, it offers the rest too: never a file
  .gitignore names, even one tracked before (the sidebar's Commit and ✦ take every change unasked when nothing is
  staged). Files that look like
  secrets (`.env`, keys, certificates) are named first, staged ones too, and committed only when you go on; the AI
  gets their names, never their contents.
- Claude (Haiku) writes the message, or a small Codex model if Claude is missing or fails (`HERDR_COMMIT_AI=claude` or
  `codex` in the environment herdr starts with: only that one, for the sidebar's ✦ too). The message is always in
  English: a subject of at most 72 characters and a bullet for each change. It is written from the staged changes only,
  so an ignored file never shows up in it; the AI runs with no tools, memories or plugins, and Claude with none of your
  instructions (Codex still reads its own `~/.codex/AGENTS.md`), so a diff cannot make it read or send anything else. If
  the repo has a `/commit` skill (`.claude/skills/commit/SKILL.md`, `.claude/commands/commit.md` or
  `.agents/skills/commit/SKILL.md`; or, without one, the one under `~/.claude`), it follows that skill's rules;
  otherwise the style of the recent commits. The repo's own rule file is read only from inside it: one linking to a
  file elsewhere is passed over, as its text would go to the AI.
- A suggested message that holds a secret, an e-mail address, a home folder path, an IP address, a tailnet's name or a
  private name (this Mac's names, your full name) the changes do not is dropped: the next AI tries, or you type the
  message.
- You see the whole message first: Enter commits and pushes, `e` edits, `r` asks for a new one, Esc cancels.
- With nothing to commit and the branch ahead of its upstream, it offers to push those commits: Enter pushes them.

It works for repos on this Mac; on a remote machine, use the sidebar's Changes view. In the Herdr app, Cmd + Shift + C
does it in the Changes view, on any machine: [Keys](app.md#keys).

**A repo without a remote:** the sidebar and Cmd + Shift + C have nowhere to push. In the workspace's terminal:

```bash
git remote -v                                                            # empty: no remote yet
gh repo create <account>/<name> --private --source . --remote origin     # a new private GitHub repo from this folder
git remote add origin https://github.com/<account>/<name>.git            # or an existing one
```

The first push, from either, sets the upstream (`push -u`).

## Closing tabs

Cmd + W closes the active tab, never the main tab. A tab with a chat asks first (Enter or **Close** closes,
Esc or **Cancel** keeps it); the chat stays in the sidebar's Chats, where Cmd + Shift + R finds it.

herdr's own close of a tab (its tab's ×, its menu, its key) ends a workspace with its last tab, after asking
"Close workspace?"; `herdr tab close` does without asking. The workspace stays a row in Spaces all the same: it is
made again at once in its place, with its name, its folder and a new shell (what ran in the old one has ended), and
in front again when it was. A workspace you close itself (its row's menu in Spaces, herdr's close-workspace key,
`herdr workspace close`) stays closed, and so does one whose folder is gone or whose last pane you moved elsewhere.

The home folder's workspace, `home`, is always the first row in Spaces: closed either way, it is made again at once
with a new shell, behind the one in front unless its last tab was closed while it was in front; moved below another
workspace, it goes back to the top. On a connected machine with herdr-fold's plugins, its workspaces stay the same
way. The Herdr app's herdr-fold layout keeps only home: [Spaces](app.md#spaces).

## Copying and searching

Select text with the mouse. In a Claude pane it is copied when you release; in other panes Cmd + C copies. Text
selected from a Claude or Codex reply is copied formatted too (headings, lists, tables, bold, code, links): Docs, Mail,
Notes and Slack get the formatted version, plain-text targets the plain one. Only web and mail links stay links.

Cmd + F searches the Claude chat of the focused pane: type, Enter accepts, `n` / `N` jump to the next /
previous match, Esc goes back to typing.

## Opening a file the agent named

Cmd + Shift + L lists the files the focused pane's recent output names, the newest first: `src/app.py:42`,
`src/app.ts(12,5)`, `README.md#L3`, a Python traceback's `File "…", line 9`, or a path alone. Only files that are
there show, a relative path found from the pane's folder or its repository's top. Type to narrow the list; Enter, a
double click or Open shows the file in the sidebar's preview tab at that line, marked (an image or a PDF drawn
there, `o` opening it in the browser), and the tab's sidebar opens Files on it. It works on any pane: an agent's
reply, a test run's failure, a compiler's errors. A remote machine's pane lists nothing: its files are on that
machine, and the list shows only files that are on the Mac.

![An agent's reply naming the files it changed and the lines that matter, and over it the list of those files, the
newest first, each with its line, Cancel and Open at the bottom](../assets/screenshots/open-file.webp)

## The status line

Next to the model name, the status line can show the effort, the context used with the context window size, and the
5-hour and weekly limits: the same items, in the same order, for Claude and for Codex. The installer asks with one
checkbox list, a group for Claude and one for Codex; everything is on by default. To change it later, or to keep your
own status line instead:

```bash
python3 ~/.config/herdr-fold/statusline_setup.py
```

Once chosen (it is the one item that starts off), Claude's line also ends with the session's cost, Claude's own
count of it at list prices (`cost.total_cost_usd`): `~$4.12`, the tilde herdr-fold puts before every dollar figure
it does not read off an invoice. On a plan it is what the session would cost at API prices and nothing you pay; with
an API key, about what was spent. It is the first thing a narrower pane drops, and it is not shown before anything is
counted. Codex's line is Codex's own and has no such item; what Codex cost is
in the sidebar's Usage.

Claude's line is drawn by `~/.config/herdr-fold/statusline.py`; Codex's is its own `[tui] status_line` setting in
`~/.codex/config.toml`, where your own items are kept. The choice carries over to the remote machines.

The weekly reset is written as the machine writes hours: `Monday 13:00`, or `Monday 1pm` with 12 hours (a Mac's
Language & Region, Windows' short time, else the locale's). The line asks once a day and keeps the answer in
`~/.local/state/herdr-fold/time.json`.

On every answer Claude's line, and a chat's in the Herdr app, keeps the 5-hour and weekly limits it was told, with
their reset times and when, in `~/.local/state/herdr-fold/limits/claude.json`, readable by you alone: nothing else of
the session, its folder or its model. herdr-fold's Usage reads it, else Claude's own cached limits in `~/.claude.json`
and Codex's in its newest chat, the newest of them, a limit past its reset left out; it writes neither agent's files.
Without a subscription's limits (an API key) nothing is kept.

Your own status line: Space on the group's title (Claude Code or Codex) turns herdr-fold's off. Claude gets back the
status line it had before, or none; Codex keeps your own items, or shows its default line. No install or update puts
herdr-fold's back until you turn it on again. Set yours with Claude's or Codex's `/statusline` command, before or
after. While herdr-fold's is on, the next install or update replaces one set with `/statusline` (Claude's is saved
first).

In a narrow pane Claude's line gets shorter until it fits: shorter reset times, the model name without its note,
shorter labels (`ctx`, `5h`, `wk`), no context window size, then no reset times and no effort. Claude Code draws it
again every 10 seconds (`refreshInterval`), so it fits a pane made narrower too, the right column dragged wider beside
it. Codex cuts its own line at the end, so its items go in the order of importance.

## Claude in herdr panes

In herdr panes Claude runs full screen: the input box stays at the bottom with the status line under it, Claude
scrolls the chat, and a "Jump to bottom" button appears when you scroll up. Claude elsewhere is unchanged. A
Claude that was already running switches on its next start.

## Quitting and restarting

Cmd + Q quits Ghostty after a question: herdr and the agents keep running, and reopening Ghostty picks up where you left
off. After the Mac restarts (or `herdr server stop`), the local agents stop, but every workspace comes back when herdr
starts, and Claude and Codex continue the same chats. A few seconds after herdr starts, the sidebar plugin
brings back each tab's sidebar and terminal (a pane closed by hand stays closed), and Workspaces starts the still-empty
agent panes again. By hand:

```bash
python3 ~/.config/herdr-fold/restore_panes.py                      # this Mac
python3 ~/.config/herdr-fold/restore_panes.py --machine alpha      # one connected machine
python3 ~/.config/herdr-fold/restore_panes.py --all                # this Mac and every connected machine
```
