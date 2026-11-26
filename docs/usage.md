# Using it

Every key is in [Keys](keybindings.md); the sidebar's views, one by one, in [its
README](../src/plugins/sidebar/README.md); the agent's setup, its limits, costs and graph in [The agent's
harness](harness.md); the Herdr app's own ways in [The Herdr app](app.md). This page follows the workspace: the spaces,
the agent's pane, the sidebar's Changes, Issues and Chats, the terminal, then what opens in a tab.

## Spaces

A space is a row of the Spaces list in herdr's sidebar; herdr's own commands and settings call it a workspace
(`herdr workspace list`, `switch_workspace`). One space per repo:

1. Click **new** under Spaces in herdr's sidebar (or Ctrl + B, then Shift + N). The folder picker shows the folder
   holding most of your git repositories as a tree, as the sidebar's Files view does: the folder on top, open.
2. Type to filter; ↑ ↓ or the wheel move, a click chooses. → opens a folder (or steps into an open one), ← closes it
   (or steps to its parent), and ← on the top row goes up a folder; a click on a folder's chevron opens or closes it.
   Tab, or a click on Claude, Codex, OpenCode or Copilot at the top right, switches between them; it starts on the
   agent herdr-fold started last. A long folder's name gives way to them, cut with "…"; in a narrow window the toggle
   shows the chosen agent alone, and a click on it steps to the next.
3. Enter, **Open** or a double click opens the space, or jumps to the one the folder already has, an agent in it or
   not. While the picker is open the new space is named `New space…` in the list. Esc or
   **Cancel** goes back to the space you came from. **Add machine…**, left of them, opens Add a machine instead
   (Ctrl + B, then Shift + M's): a space on another machine starts with the machine
   ([Remote machines](remote-machines.md)).

![The New space folder picker over the new space: Documents as a tree with its four repositories, lumen-api already
open, Claude or Codex at its top right, Cancel and Open at the bottom](../assets/screenshots/tui-new-space.webp)

The space's main tab is named after the folder (the home folder's is `home`, the root's `root`, a Windows drive's
its letter, `C:`): the agent on the left, and on the right the sidebar above a terminal. The sidebar's views are
buttons in a row at its top, each icon over its name (its icons alone in a narrow sidebar), one view shown at a
time; Chats (✦) opens the chats over it, and More at the row's end is the sidebar's menu.

Drag the right column's edge to resize it in every tab: the agent keeps 30 % of the tab at least, a window resized
keeps the width, and narrower than its icons the column folds to a rail. The » at the row's end, or Cmd + Option + B,
folds it to that rail of icons in every tab, the terminal moving under the agent; a press on an icon opens the
sidebar again on that view, as « there does.

In a new folder the agent first asks whether you trust it: answer in the pane. A pane you close stays closed in its
tab, after a restart too, until Cmd + Shift + O (Restore panels) or the sidebar's More menu brings it back; a new
tab always comes with every pane.

A folder in the sidebar's Files view opens a space too: right-click it → **New space**, and the folder picker
opens on it, with the agent toggle.

Rename or move the folder, and the space and its main tab take the folder's new name at the next pane you focus
(a folder renamed earlier too, known by the Claude chats kept under its old name), and the sidebar opens on it
again, where it was. A name you gave the space yourself stays. A space herdr named itself after the home folder or
a root, by its path (`~`, `/`, `C:\`), takes herdr-fold's name at the next pane you focus (on a Windows machine, when
herdr starts): `home`, `root`, or the drive, `C:`. A space whose folder is deleted says **deleted** beside its branch,
in the theme's red.

Cmd + ↓ / Cmd + ↑ step through the spaces, Cmd + → / Cmd + ← through the panes, Cmd + T / Cmd + R through the tabs.

From the command line (the only way on a Windows machine):

```bash
python3 ~/.config/herdr-fold/herdr_layout.py ~/projects/app app                    # on this Mac
python3 ~/.config/herdr-fold/herdr_layout.py --machine alpha /srv/app app          # on a Linux or Mac machine
python3 ~/.config/herdr-fold/herdr_layout.py --machine win1 'C:\projects\app' app  # on a Windows machine
```

Add `--agent codex`, `--agent opencode` or `--agent copilot` for another agent.

## Sessions

herdr's sidebar lists the current space's chats under Sessions, each with its state: working, blocked (it
needs you: an approval, an answer or a choice), done (finished since you last looked) or idle (ready for your next
prompt). Cmd + D and Cmd + E step through them.

In the Spaces list a branch always stands under the name it belongs to, in gray, and a space with no branch is one
line: a space in a repository shows that one's branch and git status under its name. A space whose folder is no
repository but holds one, as a folder of notes around a project's repository, shows that repository's name under its
own (left out where it is the same), and its branch under that, with ↑ the commits to push and ↓ to pull against its
remote branch (any git host); where it holds several, the one its active pane is in:

```
· home
  harbor-web
  main ↑2
```

The Spaces list says how long an agent has waited on you, blocked or done, beside its space's name: `waiting 12m`
in the theme's yellow, the longest wait when several agents wait there. It counts on while you work elsewhere and goes
once you answer, or look at the finished one. To come back to one you have seen, mark it unread: Cmd + Shift + U on its
pane, and its space says `waiting` again, from now, until you return to it after leaving it (Cmd + Shift + U again
takes the mark off). The Herdr app's herdr-fold layout does the same: [Spaces](app.md#spaces).

An agent in another tab that starts waiting on you says so once, in herdr's own toast at the bottom right:
`claude needs attention` (blocked) or `claude finished` (done), with its space and tab; never for the tab in front (off
and on in the sidebar's Settings, Notifications). herdr's sounds stay off (`[ui.sound]` in
`~/.config/herdr/config.toml`: `enabled = true` there plays them). The sidebar's Chats button has a dot while a chat
there asks you something.

![The Spaces list: lumen-api's Claude done and waiting 6 minutes, tidepool's blocked and waiting 32 minutes, beside
their name](../assets/screenshots/tui-waiting.webp)

A chat goes by one name: in AI Sessions, on its pane's border, in the sidebar's Chats, and on its
tab when it has the tab to itself (a reopened one's); the space's main tab keeps the space's name. To rename it:

- right-click its pane → **Rename pane** (**Clear pane name** brings back the chat's own title);
- or right-click it in the sidebar's Chats → **Rename**, a closed one too;
- or type `/rename New name` in the chat, which also names it in the program's own `/resume` list; it shows
  after your next prompt, or when you switch tab or pane. A name set in herdr wins.

A tab you renamed yourself keeps your name until you rename the chat.

## Closing tabs

Cmd + W closes the active tab, never the main tab. A tab with a chat asks first (Enter or **Close** closes,
Esc or **Cancel** keeps it); the chat stays in the sidebar's Chats, where Cmd + Shift + R finds it.

herdr's own close of a tab (its tab's ×, its menu, its key) ends a space with its last tab, after asking
"Close workspace?"; `herdr tab close` does without asking. The space stays a row in Spaces all the same: it is
made again at once in its place, with its name, its folder and a new shell (what ran in the old one has ended), and
in front again when it was. A space you close itself (its row's menu in Spaces, herdr's close-workspace key,
`herdr workspace close`) stays closed, and so does one whose folder is gone or whose last pane you moved elsewhere.

The home folder's space, `home`, is always the first row in Spaces: closed either way, it is made again at once
with a new shell, behind the one in front unless its last tab was closed while it was in front; moved below another
space, it goes back to the top. On a connected machine with herdr-fold's plugins, its spaces stay the same
way. The Herdr app's herdr-fold layout keeps only home: [Spaces](app.md#spaces).

## Claude in herdr panes

In herdr panes Claude runs full screen: the input box stays at the bottom with the status line under it, Claude
scrolls the chat, and a "Jump to bottom" button appears when you scroll up. Claude elsewhere is unchanged. A
Claude that was already running switches on its next start.

## The status line

Next to the model name, the status line can show the effort, the context used with the context window size, and the
5-hour and weekly limits: the same items, in the same order, for Claude and for Codex. Claude's line also shows a
model's own weekly limit where the account has one (`Fable: 38%`), as Claude's VS Code extension does. The installer
asks with one checkbox list, a group for Claude and one for Codex; everything is on by default. To change it later,
or to keep your own status line instead:

```bash
python3 ~/.config/herdr-fold/statusline_setup.py
```

Once chosen (it is the one item that starts off), Claude's line also ends with the session's cost, Claude's own
count of it at list prices (`cost.total_cost_usd`): `~$4.12`, the tilde herdr-fold puts before every dollar figure
it does not read off an invoice. On a plan it is what the session would cost at API prices and nothing you pay; with
an API key, about what was spent. A narrower pane drops it right after a model's own week, and it is not shown before
anything is counted. Codex's line is Codex's own and has no such item; what Codex cost is in
[the Usage view](harness.md#the-usage-view).

Claude's line is drawn by `~/.config/herdr-fold/statusline.py`; Codex's is its own `[tui] status_line` setting in
`~/.codex/config.toml`, where your own items are kept. The choice carries over to the remote machines.

The weekly reset is written as the machine writes hours: `Monday 13:00`, or `Monday 1pm` with 12 hours (a Mac's
Language & Region, Windows' short time, else the locale's). The line asks once a day and keeps the answer in
`~/.local/state/herdr-fold/time.json`.

On every answer Claude's line, and a chat's in the Herdr app, keeps the 5-hour and weekly limits it was told, with
their reset times and when, in `~/.local/state/herdr-fold/limits/claude.json`, readable by you alone: nothing else of
the session, its folder or its model. A model's own week, which Claude tells its status line nothing of, is kept
beside them from Claude's own `/usage` reading (cached in `~/.claude.json`); one past its reset is left off the line.
A second Claude account on the machine (its own `CLAUDE_CONFIG_DIR`) keeps its own beside it and reads its own
`.claude.json`, so neither account's limits show on the other's line. It writes neither agent's files, and without a
subscription's limits (an API key) nothing is kept. Every status line and the Agent panel's Usage show the same
reading, whichever chat answered last: how it is put together is in [Usage](harness.md#usage).

Your own status line: Space on the group's title (Claude Code or Codex) turns herdr-fold's off. Claude gets back the
status line it had before, or none; Codex keeps your own items, or shows its default line. No install or update puts
herdr-fold's back until you turn it on again. Set yours with Claude's or Codex's `/statusline` command, before or
after. While herdr-fold's is on, the next install or update replaces one set with `/statusline` (Claude's is saved
first).

In a narrow pane Claude's line gets shorter until it fits: no model's own week, no cost, shorter reset times, the
model name without its note, shorter labels (`ctx`, `5h`, `wk`), no context window size, then no reset times and no
effort. Claude Code draws it again every 10 seconds (`refreshInterval`), so it fits a pane made narrower too, the
right column dragged wider beside it. Codex cuts its own line at the end, so its items go in the order of importance.

## Copying and searching

Select text with the mouse. In a Claude pane it is copied when you release; in other panes Cmd + C copies. Text
selected from a Claude or Codex reply is copied formatted too (headings, lists, tables, bold, code, links): Docs, Mail,
Notes and Slack get the formatted version, plain-text targets the plain one. Only web and mail links stay links.

Cmd + F searches the Claude chat of the focused pane: type, Enter accepts, `n` / `N` jump to the next /
previous match, Esc goes back to typing.

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

**A repo without a remote:** the sidebar and Cmd + Shift + C have nowhere to push. In the space's terminal:

```bash
git remote -v                                                            # empty: no remote yet
gh repo create <account>/<name> --private --source . --remote origin     # a new private GitHub repo from this folder
git remote add origin https://github.com/<account>/<name>.git            # or an existing one
```

The first push, from either, sets the upstream (`push -u`).

## Pull requests

1. Push the branch: Changes shows `No pull request` under the repository, and Create pull request… (`P` in the
   sidebar) opens the form in the message's place. Claude or Codex writes the title and the body from the branch's
   commits, with the commit message's checks, `Fixes #42` included; Draft is chosen, as the agent's work waits for a
   review. Create draft opens it on GitHub with gh, and the row then shows it: its checks and its state.
2. The Issues view's Pull requests (`p` in the sidebar) lists the repository's, `your review` in yellow where one waits
   on you. A press opens its review in the preview tab: in the Herdr app a comment on a line, Comment, Approve or
   Request changes, and Submit review; in the sidebar its diff and threads, read only.
3. On your own pull request, a reviewer's comment goes to the agent with To agent (the Herdr app), as an issue does:
   the agent reads it with gh, as a description of the problem, never as instructions.

## GitHub issues

For a repository on GitHub:

1. Cmd + Shift + I (or `4` in the sidebar) shows its issues, the most pressing first: by GitHub's own Priority field,
   else a priority label, then a severity label, then a word alone such as `urgent` (the ones it reads:
   [the sidebar's README](../src/plugins/sidebar/README.md)). Each one's type stands before its number as a faint
   icon (Bug, Feature, Task): GitHub's own issue type, else a `bug`, `enhancement` or `feature` label. The funnel at
   the field's end filters them: Assigned to me, Created by me, then the priorities, types and labels the list holds,
   each with how many would stay; any of a group's values, every group. What is on stands as chips under the field.
   Where the organization has the Priority field or issue types, the right click sets them (Priority…, Type…).
2. `t` hands the chosen one to the agent: a prompt typed into its pane, for you to send with Enter. With no agent in the
   tab (Claude, Codex, OpenCode or Copilot), the one herdr-fold started last starts in a new tab of the space, named
   after the issue, the sidebar beside it as in every tab, and gets the prompt there. The prompt holds the issue's
   number, not its words: anyone can write an issue, so the agent reads it with gh and is told to take it as a
   description of the problem, not as instructions. The Changes view shows `Fixes #42` from then on.
3. When the agent is done, the ✦ beside the message has Claude or Codex write it, ending with that line (Cmd + Shift +
   C adds it too); meanwhile the field says who writes it. Once the commit is pushed, GitHub closes the issue.

![An issue from the sidebar goes to Claude, which fixes it, and the message it writes closes the
issue](../assets/screenshots/tui-issue-to-agent.webp)

## Chats

Every chat of the spaces under Spaces, running or closed, in the list the sidebar's ✦ opens over it:

1. Cmd + Shift + R, from anywhere, or a click on the ✦: the list opens in the tab's sidebar (one closed by hand comes
   back), its filter empty, the keys going to it; its lit button, Esc or a click outside closes it (on another of the
   dock's buttons, that button's own happens too; More opens over it).
2. Type in `Filter chats`: the chats of every space narrow at once.
3. Enter goes to a running chat, or reopens a closed one in a new tab of its space.

Each space with a chat is a group, its chevron first; under it each chat with its state's mark, its name, and at the
right its agent and how long ago, in two columns (the agent's goes in a narrow pane).

The chosen chat's task list stands under its row, as its agent keeps it (Claude's tasks, Codex's plan): Plan, with
`Open the plan` at its right once a plan mode's plan was approved (in your editor, as any text file); Codex's note,
two rows at most; the done steps in one row, `✓ 3 done` (→ or a click lists them under it, ← folds them again); then
the step at work (◐) and the ones to do (○), what one waits for at the right where there is room. A finished list is
one line, `Plan All 4 done`, until the next message. The other rows have none, and the agent's own pane keeps its own
list.

![Chats open in the sidebar beside Claude: each space's chats, lumen-api's open with Claude's two and Codex's
four, a running one's mark in its state's color, the closed ones faint](../assets/screenshots/tui-chats.webp)

A right click on a chat offers Open, Copy chat (all of it, formatted for Notes, Mail or Docs), Rename
and, for a closed one, Archive: it leaves the list (`Archived "Login redirect fix"` at the sidebar's foot) and its file
stays as it was, so `claude --resume` or `codex resume` still finds it; while any is archived, More (⋯) and a right
click beside the chats offer Show archived.

Archive is the everyday way to tidy the list. Delete…, under it in a closed chat's menu (an archived one's too), is the
rarer one: it asks first, by the chat's name, then moves the chat's file to the system's Trash (on a Mac the Finder's
Put Back brings it back) and drops its archive mark and the name you gave it. With the filter empty the Delete key (fn +
⌫ on a Mac's own keyboard) asks the same for the chosen chat. A running chat has no Delete…: close it first. An OpenCode
or Copilot chat has none either: OpenCode keeps its chats in its own database and Copilot in its own session store
(`/session delete` in Copilot), so Archive is their way off the list.

A chat is one row however long it runs: Claude Code compacts and resumes it in its own file, under its id, so its
name and its archive hold. Not listed: the agents' own helpers (subagents, Codex's reviewer) and what a program ran
through Claude's Agent SDK (a hook's review of each change, a script's question), which name themselves after the
chat they work for; `claude -p`'s runs are. Nor what [the Runs view](harness.md#the-runs-view) lists: `codex exec`'s
runs and Claude's background sessions, which come to Chats once Runs' Open as chat or Remove took them off Claude's
list. A project folder linked to another's (`~/.claude/projects`) lists its
chats once. Copy chat leaves out what a compacted chat holds twice: the summary Claude wrote in your place, and the
messages it kept and wrote again.

### Checkpoints

A Claude chat's right click also offers Checkpoints…, and → on its row opens them too (once its plan's done steps, if
any, are listed): its prompts in the list's place, the newest first, the chat's name over them (‹ or ← goes back to the
chats). Each prompt that starts a turn is a checkpoint, and where its turn wrote files Claude still keeps, the row says
how many it wrote (`wrote 2 files`) and the chosen one offers `Restore files to here…`. Enter asks Claude first which
files would change (its dry run): `Files as they were before this message`, those files, the lines in all, and what
stays as it is (what Bash commands and subagents changed since, edits made outside Claude, and the chat, which keeps the
later turns), then `Esc cancels` and `Restore 2 files` at the row's right end; Enter restores them through Claude's own
`--rewind-files`, Esc gives it up. herdr-fold keeps the files' contents from just before, so the foot says `Restored 2
files to before 13:32` and `u` puts them back, once, until the next message. A running Claude rewinds files and chat
together in its own pane (Esc Esc there); the list says so over the prompts. Codex keeps no file checkpoints, so its
chats have no Checkpoints….

## Opening a file the agent named

Cmd + Shift + L lists the files the focused pane's recent output names, the newest first: `src/app.py:42`,
`src/app.ts(12,5)`, `README.md#L3`, a Python traceback's `File "…", line 9`, or a path alone. Only files that are
there show, a relative path found from the pane's folder or its repository's top. Type to narrow the list; Enter, a
double click or Open opens a text file at that line in your editor ([Editing files](#editing-files)); an image, a PDF,
a page or an SVG shows in the sidebar's preview tab (`o` opening it in the browser), audio or a video too (`o` opening
it in the player), and that tab's sidebar opens Files on it. It works on any pane: an agent's reply, a test run's
failure, a compiler's errors. A remote machine's pane lists nothing: its files are on that machine, and the list shows
only files that are on the Mac.

## Editing files

Enter or a click on a text file in Files, a search hit, the Agent panel's Open, a saved file's name and Cmd + Shift + L
open the file in your own editor, in a terminal tab named for its path: `$VISUAL`, else `$EDITOR` (`code -w` too), else
the first of micro, nano and vim found, at the line asked where the editor takes `+N`. Opened again, its tab shows
(never a second editor on one file). There the Cmd keys are the editor's own, as in VS Code: Cmd + S saves, Cmd + F
finds (never the chat search), Cmd + Z and Cmd + Shift + Z undo and redo, Cmd + A, C, X and V select all, copy, cut and
paste, and Cmd + W quits the editor, never the tab under it ([each editor's keys](keybindings.md#the-editor-tab)); in
vim only the paste works. micro's bottom line names the file, a + while it is unsaved, the line and column, and those
keys; nano's help lines, of other keys, are hidden. When the editor quits, the tab closes and Files, Changes and the
preview show the file as saved. A desktop editor without `-w` opens its own window: the sidebar says so. A page or an
SVG stays in the preview, drawn, and `e` (Edit in its status row) opens the same editor tab; once saved, the picture is
drawn again. A binary file or one over 1 MiB stays in the read-only preview. With an agent's settings file chosen in
Files (`.claude/settings*.json`, `.codex/config.toml`), Files' last row says the Agent panel's forms are its checked
way, with Show in Agent.

## Pictures, audio and video an agent made

An image the agent made through a connector (fal, ElevenLabs, FLUX, Runway: [Media services](harness.md#media-services))
shows in the preview tab with where it came from under it, as the chat tells it: `fal-ai/flux-pro/v1.1 · 16:9 · fal · 2
calls · hero-image`, then the prompt. A video shows a frame of it, its shape and length (`16:9 · 5 s`); audio its
waveform in the accent, with its length; `o` opens either in the player. A right click offers Open in Player (Browser,
Preview), Show in Finder on a Mac, and Ask for Another, which types the chat that made it a request for another take,
never sent: Enter in that chat sends it. Runs counts the same files.

## Quitting and restarting

Cmd + Q quits Ghostty after a question: herdr and the agents keep running, and reopening Ghostty picks up where you left
off. After the Mac restarts (or `herdr server stop`), the local agents stop, but every space comes back when herdr
starts, and Claude and Codex continue the same chats. A few seconds after herdr starts, the sidebar plugin
brings back each tab's sidebar and terminal (a pane closed by hand stays closed), and Spaces starts the still-empty
agent panes again. By hand:

```bash
python3 ~/.config/herdr-fold/restore_panes.py                      # this Mac
python3 ~/.config/herdr-fold/restore_panes.py --machine alpha      # one connected machine
python3 ~/.config/herdr-fold/restore_panes.py --all                # this Mac and every connected machine
```
