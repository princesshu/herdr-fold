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

herdr-fold's own code asks one thing of the network: once a day, api.github.com for its latest release, the request
alone. Check for Updates (the sidebar's ⋯ menu, a right click on the Herdr app panel's tabs) or
`HERDR_FOLD_NO_UPDATE_CHECK=1` turns it off: [A newer version](docs/installation.md#a-newer-version). Everything else
goes where you ask: git to the repository's remote, gh to GitHub, the AI tool to its own service.

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
- an issue handed to the agent goes as its number only, as anyone can write an issue.

A repository's filters and hooks still run when you stage, show a diff, commit or sync, as with git in a terminal:
open only folders whose `.git` you trust. The details:
[What it reads and writes](src/plugins/sidebar/README.md#what-it-reads-and-writes).

## What not to post in an issue

Remove these from logs and output before you paste them anywhere:

- SSH keys, tokens and passwords;
- your name and e-mail address (the installer shows git's commit author), folder paths and project names;
- `~/.config/herdr-fold/machines.txt` and other machine names and addresses;
- herdr's logs;
- the text of your Claude or Codex conversations.
