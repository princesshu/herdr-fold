# Using it

Every key is in [Keys](keybindings.md); the sidebar's views, one by one, in
[its README](../src/plugins/sidebar/README.md).

## Workspaces

One workspace per repo:

1. Click **new** under Spaces in herdr's sidebar (or Ctrl + B, then Shift + N). The folder picker shows the folder
   holding most of your git repositories as a tree, as the sidebar's Files view does: the folder on top, open.
2. Type to filter; ↑ ↓ or the wheel move, a click chooses. → opens a folder (or steps into an open one), ← closes it
   (or steps to its parent), and ← on the top row goes up a folder; a click on a folder's ▸ opens or closes it. Tab, or
   a click on Claude or Codex at the top right, switches between them.
3. Enter, **Open** or a double click opens the workspace, or jumps to the one the folder already has. Esc or
   **Cancel** goes back to the workspace you came from.

![The folder picker over the new workspace: Documents as a tree, driftwood chosen, Claude or Codex at its top
right, Cancel and Open at the bottom](media/new-workspace.webp)

The workspace's main tab is named after the folder (the home folder's is `home`): the agent on the left, the
Conversations column, and on the right the sidebar above a terminal. Drag the right column's edge to resize it in every
tab. In a new folder the agent first asks whether you trust it: answer in the pane. A pane you close stays closed in its
tab, after a restart too, until Cmd + Shift + O (Restore panels) or the sidebar's ⋯ menu brings it back; a new tab
always comes with every pane.

A folder in the sidebar's Files view opens a workspace too: right-click it → **New Workspace**, and the folder picker
opens on it, with the Claude / Codex toggle.

Rename or move the folder, and the workspace and its main tab take the folder's new name at the next pane you focus
(a folder renamed earlier too, known by the Claude conversations kept under its old name), and the sidebar opens on it
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

herdr's sidebar lists the current workspace's conversations under Sessions, each with its state: working, blocked (it
needs you: an approval, an answer or a choice), done (finished since you last looked) or idle (ready for your next
prompt). Cmd + D and Cmd + E step through them.

The Spaces list says how long an agent has waited on you, blocked or done, beside its workspace's branch: `waiting
12m` in the theme's yellow, the longest wait when several agents wait there. It counts on while you work elsewhere and
goes once you answer, or look at the finished one.

![The Spaces list: harbor-web's agent blocked and waiting 12 minutes, tidepool's done and waiting 3 minutes, beside
their branch](media/waiting.webp)

A conversation goes by one name: in AI Sessions, on its pane's border, in the Conversations column, and on its
tab when it has the tab to itself (a reopened one's); the workspace's main tab keeps the workspace's name. To rename it:

- right-click its pane → **Rename pane** (**Clear pane name** brings back the conversation's own title);
- or right-click it in the Conversations column → **Rename**, a closed one too;
- or type `/rename New name` in the conversation, which also names it in the program's own `/resume` list; it shows
  after your next prompt, or when you switch tab or pane. A name set in herdr wins.

A tab you renamed yourself keeps your name until you rename the conversation.

## Conversations

Every conversation of the workspaces under Spaces, running or closed, in the column before the sidebar:

1. Cmd + Shift + R, from anywhere: the column opens in every tab, its filter empty, the keys going to it.
2. Type: the conversations of every workspace narrow at once.
3. Enter goes to a running conversation, or reopens a closed one in a new tab of its workspace.

![The Conversations column open beside Claude: each workspace's conversations, a running one's mark in its state's
color, the closed ones faint](media/conversations.webp)

A right click on a conversation offers Open, Copy conversation (all of it, formatted for Notes, Mail or Docs), Rename
and, for a closed one, Archive: it leaves the list and its file stays as it was, so `claude --resume` or `codex resume`
still finds it; a right click elsewhere in the column offers Show archived. Cmd + Shift + H collapses the column to a
rail in every tab, and opens it again as wide as you last dragged it.

## GitHub issues

For a repository on GitHub:

1. Cmd + Shift + I (or `4` in the sidebar) shows its issues, the most pressing first: by GitHub's own Priority field,
   else a priority label, then a severity label, then a word alone such as `urgent` (the ones it reads:
   [the sidebar's README](../src/plugins/sidebar/README.md)).
2. `t` hands the chosen one to the agent: a prompt typed into its pane, for you to send with Enter. The prompt holds the
   issue's number, not its words: anyone can write an issue, so the agent reads it with gh and is told to take it as a
   description of the problem, not as instructions. The Changes view shows `Fixes #42` from then on.
3. When the agent is done, the ✦ beside the message has Claude or Codex write it, ending with that line (Cmd + Shift +
   C adds it too); once the commit is pushed, GitHub closes the issue.

![An issue from the sidebar goes to Claude, which fixes it, and the message it writes closes the
issue](media/issue-to-agent.webp)

## Commit and push

Cmd + Shift + C commits and pushes the repo of the focused pane, in one step:

- If nothing is staged, it offers all changes; if only some are staged, it offers the rest too. Files that look like
  secrets (`.env`, keys, certificates) are named first, staged ones too, and committed only when you go on; the AI
  gets their names, never their contents.
- Claude (Haiku) writes the message, or a small Codex model if Claude is missing or fails (`HERDR_COMMIT_AI=claude` or
  `codex` in the environment herdr starts with: only that one, for the sidebar's ✦ too). The message is always in
  English: a subject of at most 72 characters and a bullet for each change. It is written from the staged changes only,
  so an ignored file never shows up in it; the AI runs with no tools, memories or plugins, and Claude with none of your
  instructions (Codex still reads its own `~/.codex/AGENTS.md`), so a diff cannot make it read or send anything else. If
  the repo has a `/commit` skill (`.claude/skills/commit/SKILL.md`, `.claude/commands/commit.md` or
  `.agents/skills/commit/SKILL.md`; or, without one, the one under `~/.claude`), it follows that skill's rules;
  otherwise the style of the recent commits.
- A suggested message that holds a secret, an e-mail address, a home folder path, an IP address, a tailnet's name or a
  private name (this Mac's names, your full name) the changes do not is dropped: the next AI tries, or you type the
  message.
- You see the whole message first: Enter commits and pushes, `e` edits, `r` asks for a new one, Esc cancels.

It works for repos on this Mac; on a remote machine, use the sidebar's Changes view.

**A repo without a remote:** the sidebar and Cmd + Shift + C have nowhere to push. In the workspace's terminal:

```bash
git remote -v                                                            # empty: no remote yet
gh repo create <account>/<name> --private --source . --remote origin     # a new private GitHub repo from this folder
git remote add origin https://github.com/<account>/<name>.git            # or an existing one
```

The first push, from either, sets the upstream (`push -u`).

## Closing tabs

Cmd + W closes the active tab, never the main tab. A tab with a conversation asks first (Enter or **Close** closes,
Esc or **Cancel** keeps it); the conversation stays in the Conversations column, where Cmd + Shift + R finds it.

## Copying and searching

Select text with the mouse. In a Claude pane it is copied when you release; in other panes Cmd + C copies. Text
selected from a Claude or Codex reply is copied formatted too (headings, lists, tables, bold, code, links): Docs, Mail,
Notes and Slack get the formatted version, plain-text targets the plain one. Only web and mail links stay links.

Cmd + F searches the Claude conversation of the focused pane: type, Enter accepts, `n` / `N` jump to the next /
previous match, Esc goes back to typing.

## Opening a file the agent named

Cmd + Shift + L lists the files the focused pane's recent output names, the newest first: `src/app.py:42`,
`src/app.ts(12,5)`, `README.md#L3`, a Python traceback's `File "…", line 9`, or a path alone. Only files that are
there show, a relative path found from the pane's folder or its repository's top. Type to narrow the list; Enter, a
double click or Open shows the file in the sidebar's preview tab at that line, marked, and the tab's sidebar opens
Files on it. It works on any pane: an agent's reply, a test run's failure, a compiler's errors. A remote machine's
pane lists nothing: its files are on that machine, and the list shows only files that are on the Mac.

![An agent's reply naming the files it changed and the lines that matter, and over it the list of those files, the
newest first, each with its line, Cancel and Open at the bottom](media/open-file.webp)

## The status line

Next to the model name, the status line can show the effort, the context used with the context window size, and the
5-hour and weekly limits: the same items, in the same order, for Claude and for Codex. The installer asks with one
checkbox list, a group for Claude and one for Codex; everything is on by default. To change it later, or to keep your
own status line instead:

```bash
python3 ~/.config/herdr-fold/statusline_setup.py
```

Claude's line is drawn by `~/.config/herdr-fold/statusline.py`; Codex's is its own `[tui] status_line` setting in
`~/.codex/config.toml`, where your own items are kept. The choice carries over to the remote machines.

Your own status line: Space on the group's title (Claude Code or Codex) turns herdr-fold's off. Claude gets back the
status line it had before, or none; Codex keeps your own items, or shows its default line. No install or update puts
herdr-fold's back until you turn it on again. Set yours with Claude's or Codex's `/statusline` command, before or
after. While herdr-fold's is on, the next install or update replaces one set with `/statusline` (Claude's is saved
first).

In a narrow pane Claude's line gets shorter until it fits: shorter reset times, the model name without its note,
shorter labels (`ctx`, `5h`, `wk`), no context window size, then no reset times and no effort. Claude Code draws it
again every 10 seconds (`refreshInterval`), so it fits a pane made narrower too, the Conversations column opened beside
it. Codex cuts its own line at the end, so its items go in the order of importance.

## Claude in herdr panes

In herdr panes Claude runs full screen: the input box stays at the bottom with the status line under it, Claude
scrolls the conversation, and a "Jump to bottom" button appears when you scroll up. Claude elsewhere is unchanged. A
Claude that was already running switches on its next start.

## Quitting and restarting

Cmd + Q quits Ghostty after a question: herdr and the agents keep running, and reopening Ghostty picks up where you left
off. After the Mac restarts (or `herdr server stop`), the local agents stop, but every workspace comes back when herdr
starts, and Claude and Codex continue the same conversations. The tab-layout plugin restarts the Conversations
columns, the sidebars and the still-empty agent panes a few seconds after herdr starts. By hand:

```bash
python3 ~/.config/herdr-fold/restore_panes.py                      # this Mac
python3 ~/.config/herdr-fold/restore_panes.py --machine alpha      # one connected machine
python3 ~/.config/herdr-fold/restore_panes.py --all                # this Mac and every connected machine
```
