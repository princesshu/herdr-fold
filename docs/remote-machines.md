# Remote machines

The agents, the sidebar and the terminal run on the machine where the files are; the Mac shows them over SSH. Work on a
remote machine keeps running after you close the Mac.

## What the installer does on a machine

1. installs starship if it is missing, and git and Python: on Linux as root (with apt, dnf or yum) and on Windows (with
   winget); elsewhere a missing one is reported. Then it puts the settings in place;
2. connects the machine to herdr, which installs herdr there (a single file, no admin rights);
3. installs the herdr integrations for Claude and Codex, names a herdr-sidebar of the machine's own, and links the
   Sessions list and the tab layout; the sidebar comes with the settings, in the Mac's theme colors (a theme picked
   later reaches a machine with its next update), and runs with the machine's Python.

It does not install Claude Code or Codex or sign them in: do that once on each machine.

For a machine you add by hand that `~/.ssh/known_hosts` does not know yet, it shows the fingerprint of the machine's
ED25519 key and asks whether to trust it: type `y` once it matches the machine's own (on a Linux or Mac machine:
`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`; on Windows: `ssh-keygen -lf
C:\ProgramData\ssh\ssh_host_ed25519_key.pub`). Only that key is trusted, so ssh refuses the machine if it later shows
another; a machine that shows no ED25519 key is not added. Machines from `~/.ssh/config` and your Tailscale network are
not asked about: ssh trusts their key on the first connection and checks it from then on.

## Adding a machine later

Ctrl + B, then Shift + M asks the installer's machine questions (from `~/.ssh/config`, your Tailscale network, or by
address) and sets up only the new machine. It runs `machines.sh` from the `herdr-fold` folder, so keep that folder on
the Mac; after moving it, run `./install.sh` once in the new place.

A machine on the list (`~/.config/herdr-fold/machines.txt`) at the very address a `~/.ssh/config` Host names, its `User`
and `HostName`, goes through that Host from the next run of `machines.sh` on (the installer's step 8, Ctrl + B then
Shift + M, or `./machines.sh status`), unasked: its address on the list becomes the Host's name, so herdr-fold's own ssh
takes that file's key and options. The machine's name stays, and so does the address herdr connects it with: the same
machine. A Host with its own `Port`, `ProxyJump`, `ProxyCommand` or `HostKeyAlias` is left alone: that is another
endpoint, whose key ssh would take unasked.

## Systems

| System | Notes |
|---|---|
| Linux | x86_64 or ARM. The prompt applies only inside herdr panes. |
| macOS | System Settings → General → Sharing → turn on **Remote Login**. For repos in the Documents folder, in the same place: ⓘ → **Allow full disk access for remote users**. |
| Windows | x86_64, Windows 10 1803 or newer (for its tar). Needs OpenSSH Server (Settings → System → Optional features → OpenSSH Server, then start the sshd service), with cmd or PowerShell as its shell; no file transfer (scp, SFTP): the package goes in plain commands. For an admin user the key goes in `C:\ProgramData\ssh\administrators_authorized_keys`. The installer installs Python with winget, or, if that fails over SSH, with the python.org installer for the current user. The right column is the sidebar and a terminal here too (`sidebar.ps1`); Claude's status line is the same Python script as elsewhere, started through PowerShell. The prompt works only where PowerShell profiles are allowed. New workspaces come from the command line, see [Using it](usage.md#workspaces). |

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
the machine (a linked file comes back as the link; the package never writes through one). Files changed there since
stay in its backups (`~/.local/state/herdr-fold/prepared-*`).
