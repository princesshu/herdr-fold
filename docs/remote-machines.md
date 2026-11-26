# Remote machines

The agents, the sidebar and the terminal run on the machine where the files are; the Mac shows them over SSH. Work on a
remote machine keeps running after you close the Mac.

## What the installer does on a machine

It prepares each machine for the parts installed on the Mac, the TUI, the Herdr app or both:

1. installs git and Python if they are missing: on Linux as root (with apt, dnf or yum) and on Windows (with winget);
   elsewhere a missing one is reported. With the TUI, starship too, and the prompt in herdr's panes. Then it puts the
   settings in place (with the Herdr app alone, only the status line's);
2. with the TUI: connects the machine to herdr, which installs herdr there (a single file, no admin rights);
3. with the TUI: installs the herdr integrations for Claude and Codex, names a herdr-sidebar of the machine's own, and
   links the sidebar, AI Sessions and Spaces; the sidebar comes with the settings, in the Mac's theme colors (a theme
   picked later reaches a machine with its next update), and runs with the machine's Python;
4. with the Herdr app ([The Herdr app](app.md)): adds the machine to the app, whose core (herdr-core) copies itself
   there, a single file as herdr's; a machine the app has already is left as it is.

What is the machine's own is saved first, in `~/.local/state/herdr-fold/` there (on Windows in the user folder):

- `prepared-original/`: its own files, as they were before herdr-fold first set it up, and Claude's earlier status
  line. They come back when you remove the machine.
- `prepared-changed-<date>/`: files herdr-fold put there that you edited on the machine, kept when an update replaces
  or drops them, or when you remove the machine. Never deleted.

No copy of herdr-fold's own files is kept: the package has them.

It installs no coding agent (Claude Code, Codex, OpenCode) and signs none in: do that once on each machine.

For a machine you add by hand that `~/.ssh/known_hosts` does not know yet, it shows the fingerprint of the machine's
ED25519 key and asks whether to trust it: type `y` once it matches the machine's own (on a Linux or Mac machine:
`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`; on Windows: `ssh-keygen -lf
C:\ProgramData\ssh\ssh_host_ed25519_key.pub`). Only that key is trusted, so ssh refuses the machine if it later shows
another; a machine that shows no ED25519 key is not added. Machines from `~/.ssh/config` and your Tailscale network are
not asked about: ssh trusts their key on the first connection and checks it from then on.

## Adding a machine later

Ctrl + B, then Shift + M (or New space's Add machine…) opens Add a machine, a window framed as Settings whose close
button, Esc or Ctrl + C end it at any question. It asks the installer's machine questions (from `~/.ssh/config`, by
address, or from a Tailscale network where Tailscale is installed) and sets up only the new machine. It runs
`machines.sh` from the `herdr-fold` folder, so keep that folder on the Mac: moved or deleted, Add a machine says the
folder `isn't where the installer left it`, and `./install.sh` run once in its new place records it again. In the Herdr
app, Add machine… (the sidebar's foot, the palette, Ctrl + B, then Shift + M) is the app's own: a machine added there
works once git and Python 3 are on it ([On another machine](app.md#on-another-machine)).

A machine on the list (`~/.config/herdr-fold/machines.txt`) at the very address a `~/.ssh/config` Host names, its `User`
and `HostName`, goes through that Host from the next run of `machines.sh` on (the installer's step 8, Ctrl + B then
Shift + M, or `./machines.sh status`), unasked: its address on the list becomes the Host's name, so herdr-fold's own ssh
takes that file's key and options. The machine's name stays, and so does the address herdr connects it with: the same
machine. A Host with its own `Port`, `ProxyJump`, `ProxyCommand` or `HostKeyAlias` is left alone: that is another
endpoint, whose key ssh would take unasked.

## Networks

herdr-fold reaches every machine over SSH, so any network works on which the Mac reaches the machine's SSH port: the
local network, a public address, or a virtual network that joins your machines. The machines of a Tailscale network are
offered by name (`./machines.sh tailscale`); on any other network add a machine by its address or name
(`./machines.sh new`), or give it a Host in `~/.ssh/config` and import it from there (`./machines.sh sshconfig`).

| Network | What it is | How a machine is added |
|---|---|---|
| Tailscale, Headscale | WireGuard-based, joins your own machines (Headscale: Tailscale's coordination server, run by yourself) | offered from the Tailscale network |
| NetBird | WireGuard-based, open source, joins your own machines | by its address or name |
| ZeroTier | a virtual network of your own machines | by its address |
| WireGuard | a tunnel you set up yourself | by its address |
| Cloudflare Zero Trust | the machine reached through Cloudflare's `cloudflared` | a `~/.ssh/config` Host with its `ProxyCommand`, imported from there |
| Cloudflare WARP alone | protects your traffic to the internet; it does not join your machines | — |

The Mac can be on several at once. Keep their address ranges apart (Tailscale and NetBird take the same range unless one
is changed), and mind a mode that sends all traffic through one network (Cloudflare WARP's full mode, a company's
private network, Tailscale's exit node): it can cut the others off. A machine reached only through another one goes
through a Host with `ProxyJump` in `~/.ssh/config`.

## Systems

| System | Notes |
|---|---|
| Linux | x86_64 or ARM. The prompt applies only inside herdr panes. |
| macOS | System Settings → General → Sharing → turn on **Remote Login**. For repos in the Documents folder, in the same place: ⓘ → **Allow full disk access for remote users**. |
| Windows | x86_64, Windows 10 1803 or newer (for its tar). Needs OpenSSH Server (Settings → System → Optional features → OpenSSH Server, then start the sshd service), with cmd or PowerShell as its shell; no file transfer (scp, SFTP): the package goes in plain commands. For an admin user the key goes in `C:\ProgramData\ssh\administrators_authorized_keys`. The installer installs Python with winget, or, if that fails over SSH, with the python.org installer for the current user. The right column is the sidebar and a terminal here too (`sidebar.ps1`); Claude's status line is the same Python script as elsewhere, started through PowerShell. The prompt works only where PowerShell profiles are allowed. New spaces come from the command line, see [Using it](usage.md#spaces). |

## Commands

In the `herdr-fold` folder:

```bash
./machines.sh                   # each machine's state: SSH, connection, programs
./machines.sh new               # add a machine: the installer's questions, then only the new one is set up
./machines.sh sshconfig         # add machines from the Host lines of ~/.ssh/config (not those on your tailnet)
./machines.sh tailscale         # add machines from your Tailscale network
./machines.sh add alpha         # set one machine up again
./machines.sh prepare           # push changed settings out to the machines
./machines.sh remove alpha      # take a machine off the list and the package off the machine
herdr machine list              # the connected machines
```

`./machines.sh remove` puts Claude's earlier status line and the machine's own files that the package replaced back on
the machine (a linked file comes back as the link; the package never writes through one), and takes it off the Herdr
app when herdr-fold added it there. Files changed there since stay in its `prepared-changed-<date>/`
([above](#what-the-installer-does-on-a-machine)).
