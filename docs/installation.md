# Installation

The installer sets up Ghostty, herdr, starship, gh, bat, git-delta, ripgrep and the JetBrains Mono Nerd Font with
Homebrew, then puts the settings, the herdr plugins and the Claude Code and Codex status lines in place.

A program already on your Mac stays, whoever installed it (Ghostty from its website, ripgrep from cargo): Homebrew
gets no second copy and takes over no app. The installer names what is missing and asks before Homebrew installs it.
Nothing already there is upgraded: Ghostty updates itself, and Homebrew and the rest are yours to upgrade when you
choose (`brew upgrade`, `herdr update`). When nothing is missing, Homebrew does not run. The one exception is a herdr
older than 0.9.5, which herdr-fold needs: Homebrew's is upgraded after the same question, and one from herdr's own
installer is named with `herdr update`. During its run Homebrew cleans up nothing (old versions of your other
programs, its downloads) and its analytics count nothing; your own Homebrew settings stay as they are.

## Requirements

- A Mac with Apple silicon and macOS 15 or later: what Homebrew supports. Homebrew no longer supports Intel Macs: the
  install may get through there, but it is not supported or tested.
- Homebrew. If it is missing, the installer offers to install it.
- Claude Code and/or Codex, signed in. The installer does not install them; it tells you if one is missing.
- herdr 0.9.5 or newer. The installer installs it with Homebrew (`Brewfile`), unless a herdr from elsewhere (herdr's
  own installer, in `~/.local/bin`) is there: that one stays, without a second from Homebrew. Homebrew has it
  ready-built only for the newest macOS; on an older one it builds it first (with rust and zig, which it brings), which
  takes several minutes.

## From herdr's marketplace

With herdr already on your Mac, the whole environment is one herdr plugin, Full Setup:

```bash
herdr plugin install princesshu/herdr-fold
```

herdr shows what the plugin runs and asks first. Then, at the next pane you focus, the installer opens in a herdr tab
of its own and asks the questions below; nothing changes before you answer. It keeps the package in
`~/.local/share/herdr-fold`, as herdr's own copy moves with each version. The tab opens once for each version; open it
again any time:

```bash
herdr plugin pane open --plugin herdr-fold --entrypoint install
```

`herdr plugin update herdr-fold` brings a newer version, and the installer opens once more to put it in place, with
one question: Enter keeps your earlier choices. The sidebar and AI Sessions install alone from there too, without
the rest: their READMEs say how.

## Get the folder

```bash
git clone https://github.com/princesshu/herdr-fold.git
```

Or copy the `herdr-fold` folder to the Mac (for example with AirDrop). The folder can live anywhere; the installer
records where it is. After moving it, run `./install.sh` once in the new place.

## Start the installer

Double-click `install.command` in the folder: the installer opens in the Terminal app. Or, in Terminal:

```bash
cd herdr-fold
./install.sh
```

On macOS 15 and later, a file you downloaded or got with AirDrop may not open on a double-click, and right-click →
Open no longer helps. Go to System Settings → Privacy & Security and click **Open Anyway**. A folder you got with
`git clone` does not have this problem.

Terminal, a herdr pane or the marketplace's herdr tab are all the same to it. If Ghostty is open while it runs, it
tells you at the end to reopen it: the new settings, the theme and its icon take effect then. If something goes wrong,
see [Troubleshooting](troubleshooting.md).

## The questions

The installer starts on Enter (any other key cancels it, before anything changed); where herdr-fold is installed
already, it asks the update question below instead. Then it asks only where a decision is needed. Enter always gives
the default: the capital letter in `[Y/n]` (yes) or `[y/N]` (no). Each line it prints starts with a mark: `[✓]` done
(dim: already there), `[!]` needs attention, `[✗]` stopped, `[-]` skipped, `[+]` a copy was kept, where the line says,
`[…]` at work (its dots turn while a step takes a while).

| Step | Question | When | Default |
|---|---|---|---|
| Start | `Update with your earlier choices? No: the entire install process again, step by step` | herdr-fold is installed here already, instead of Enter to start | yes: the theme, settings, status line, plugins, GitHub and machines stay as chosen, and only something new is asked about (a program Homebrew is to install) |
| 1 Prerequisites | `Install it now?` | Homebrew is missing | yes (asks for your Mac password) |
| 2 Apps | `Go ahead with Homebrew?` | a program is missing, or Homebrew's herdr is older than 0.9.5; the lines above it name which. No: nothing is installed, and the installer stops with the `brew` commands to run | yes |
| 3 Theme | `Theme` | always: a number from the preview that opens in your browser, or a name ([Themes](themes.md)) | the current theme |
| 4 Settings | `Keep your herdr settings and add herdr-fold's? No: herdr-fold's replace them, yours are kept` | `~/.config/herdr/config.toml` is your own | yes |
| 4 Settings | `Remove? A copy is kept first` | an earlier version left files this one no longer uses; listed above it, several in one folder by the folder; the copy goes to `~/.local/state/herdr-fold/<date>`. No: they stay, and the next install asks again | yes |
| 5 Status line | `What should the status line show next to the model?`: one checkbox list, a group for Claude Code and one for Codex, its title off for your own status line | always (↑ ↓ move, Space toggles, one Enter for both) | everything on |
| 5 Status line | `Trust them, so the status line shows there too? (Claude then also runs their own .claude settings and hooks)` | some of your Claude panes are in git repositories Claude does not trust yet (never a folder outside one, your home folder or a folder above it) | no |
| 6 Plugins | `Show your conversations in herdr's Agents list?` | herdr was set up before | yes, or your last answer |
| 6 Plugins | `Give every new tab the Conversations column, the sidebar and a terminal?` | herdr was set up before | yes, or your last answer |
| 7 GitHub | `Sign in to GitHub now?` | the Mac is not signed in to GitHub | yes |
| 7 GitHub | `Let git push through your GitHub sign-in?` | signed in, but git does not use it yet | yes |
| 7 GitHub | `Commit author name`, `Commit author email` | git has no author yet | signed in to GitHub: your login and its noreply address (`ID+login@users.noreply.github.com`), so a commit shows no real address; else none |

Step 8 connects remote machines. Every question there is optional:

| Question | When | Default |
|---|---|---|
| `Import machines from ~/.ssh/config?` | `~/.ssh/config` exists | no |
| `Import alpha (root@alpha.example)?` | for each machine in it, but one on your Tailscale network by its name or address: that one is asked about only after a yes to the Tailscale question (or with `./machines.sh tailscale`) | no |
| `Import alpha (root@alpha.example)? — already imported` | for a machine imported earlier: no takes it off the list | yes |
| `Import machines from your Tailscale network?` | Tailscale is installed | no |
| `Import mac-mini (macos, mac-mini.tail0000.ts.net)?` | for each machine there that is not on the list; for one `~/.ssh/config` names, the address that file connects to | no |
| `Import mac-mini (macos, mac-mini.tail0000.ts.net)? — already imported` | for a machine imported earlier | yes |
| `user` | the user to log in with over SSH, for a machine on your Tailscale network that `~/.ssh/config` does not name (by its name or address); one it names goes on under that name, with that file's user and key | `root` on Linux, your Mac's user name elsewhere |
| `Add a machine by hand?` | always | no |
| `user`, `IP address or host name` | for a machine you add by hand | `root`, none |
| `Add another machine?` | after each one | no |
| `Trust this ED25519 key of alpha (compare it with the machine's own)?` | a machine you add by hand that `~/.ssh/known_hosts` does not know yet: its ED25519 key's fingerprint is shown first; one that shows none is not added | no |
| `Create an SSH key for this Mac?` | before the first machine, when the Mac has no SSH key | yes |
| `Press Enter once it is on every machine` | after it shows the new public key, to put on each machine | Enter |

Type `y` only once the fingerprint matches the machine's own
([how to read it](remote-machines.md#what-the-installer-does-on-a-machine)); Enter alone is no, and the machine is not
added.

What the installer sets up on a machine: [Remote machines](remote-machines.md). herdr asks two questions of its own
when it connects a machine: whether it may install itself there (answer yes), and
whether it may stop an older herdr running there (answer no, the default).

## What changes on your Mac

- `~/.config/herdr-fold/`: the package's scripts, plugins, themes and texts, and this Mac's settings
  (`statusline.json`, `machines.txt`).
- `~/.config/ghostty/config`, `~/.config/starship.toml`: replaced. Your own versions are kept. Ghostty starts herdr
  from Homebrew's folders, or from `~/.local/bin`, where herdr's own installer puts it: a herdr that
  did not come from Homebrew stays the one, without a second from Homebrew. One elsewhere gets a link to make in
  `~/.local/bin` (mise's through its shim, which outlives `mise upgrade`); with a Homebrew herdr there too, the
  installer says which one Ghostty starts.
- `~/.config/herdr/config.toml`: replaced, or, if you answer yes to the question above, herdr-fold's are added to yours
  between `# >>> herdr-fold >>>` and `# <<< herdr-fold <<<` marks.
- `~/.zshrc`: one marked block that loads the herdr pane environment, only inside herdr panes.
- Claude Code's `statusLine` in `~/.claude/settings.json`, and Codex's `[tui] status_line` in `~/.codex/config.toml`.
- herdr plugins (the sidebar, AI Sessions, the tab layout) and the herdr integrations for Claude and Codex; a
  herdr-sidebar of your own stays, and is named ([The sidebar](sidebar.md)).
- The theme's colors for the sidebar, in `~/.local/state/herdr/plugins/herdr-fold.sidebar/colors.json`.
- `~/.config/ghostty/herdr-fold-icon`: which app icon Ghostty shows (the theme's), written into
  `~/.local/state/herdr-fold/ghostty-icon/`.
- `~/.local/share/herdr-fold`: only when installed from herdr's marketplace, the package itself: herdr keeps its
  copy in a folder per version, so Ctrl+B, Shift+M, the next update and the uninstaller run from this one.

Only when you say yes, or when something is missing:

- a new SSH key, `~/.ssh/id_ed25519` and `~/.ssh/id_ed25519.pub`, and a `Host *` block in `~/.ssh/config` that uses it
  for every host (with the macOS Keychain);
- `~/.ssh/known_hosts`: the key of each machine you trust;
- `~/.zprofile`: Homebrew's `brew shellenv` line, when the installer installs Homebrew;
- git's global commit author (`user.name`, `user.email`), only if none is set, and git's GitHub sign-in through `gh`;
- `~/.claude.json`: the projects you let Claude trust, so the status line shows there.

Everything it replaces is saved first, in `~/.local/state/herdr-fold/`:

- `original/`: your own files, as they were before the first install, your herdr settings too when herdr-fold's part
  is added to them. Replaced files come back when you uninstall; the copy of your herdr settings stays.
- dated folders: earlier versions of the installed files. The three newest are kept.
- `changed-<date>/`: installed files you edited, kept when a newer install replaces them. Never deleted.

It never touches your conversations (Claude and Codex sessions and their names) or herdr's own data.

## Run it again

Run `./install.sh` again any time, for example after getting a newer `herdr-fold` folder or to add a machine. What is
done is skipped, what changed is updated, and what an earlier version left behind is listed and removed once you say
yes (it is saved first). Your theme, status line choices and machine list stay.

## Switches

| Variable | Effect |
|---|---|
| `HERDR_FOLD_YES=1` | no questions: every answer is the default |
| `HERDR_FOLD_NO_BREW=1` | skip the Homebrew installs |
| `HERDR_FOLD_NO_MACHINES=1` | skip the remote machines step |
| `HERDR_FOLD_CONFIG=add` or `replace` | the answer for your own herdr settings, without the question |
| `HERDR_FOLD_VERBOSE=1` | show every item instead of one summary line per step |
| `HERDR_FOLD_LANG=<code>` | the language of the installer's texts (see [Translating](translating.md)) |

The commit message writer (Cmd + Shift + C and the sidebar's ✦) has a switch of its own, `HERDR_COMMIT_AI`: see
[Commit and push](usage.md#commit-and-push).

## GitHub sign-in

The sidebar's Sync and Cmd + Shift + C push with plain git, through your GitHub sign-in. The installer signs you in
with GitHub's command-line tool: your browser opens, and you approve with the one-time code shown. The access is kept
in the Mac's Keychain. Later, by hand:

```bash
gh auth login --web
gh auth setup-git
```
