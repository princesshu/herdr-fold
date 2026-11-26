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

It installs no coding agent (Claude Code, Codex, OpenCode, Copilot CLI) and signs none in: do that once on each machine.

For a machine you add by hand that `~/.ssh/known_hosts` does not know yet, it shows the fingerprint of the machine's
ED25519 key and asks whether to trust it: type `y` once it matches the machine's own (on a Linux or Mac machine:
`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`; on Windows: `ssh-keygen -lf
C:\ProgramData\ssh\ssh_host_ed25519_key.pub`). Only that key is trusted, so ssh refuses the machine if it later shows
another; a machine that shows no ED25519 key is not added. Machines from `~/.ssh/config` and your Tailscale or NetBird
network are not asked about: ssh trusts their key on the first connection and checks it from then on. The list keeps
each machine's key, the machine itself ([One machine, several routes](#one-machine-several-routes)).

## Adding a machine later

Ctrl + B, then Shift + M (or New space's Add machine…) opens Add a machine, a window framed as Settings whose close
button, Esc or Ctrl + C end it at any question. It asks the installer's machine questions (from `~/.ssh/config`, by
address, or from a Tailscale or NetBird network where that one is installed) and sets up only the new machine. It runs
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

## One machine, several routes

A machine is its SSH host key, its ED25519 key's fingerprint on the list: a network is only a way to it, a route. The
same Mac on the local network and on Tailscale is one machine with two routes, and two machines of the same name on
two networks stay two machines.

A machine offered again under another address, from `~/.ssh/config`, a Tailscale or NetBird network or typed in, that
shows the key of one on the list is that machine. The questions say so, and offer the route instead of a second machine:

```text
  studio.tail0000.ts.net is studio, already on the list: also reachable on Tailscale.
  Add this route? [Y/n]
```

Its key is known from Tailscale's own record of it, where Tailscale gives one, or read from the machine before the
question (`ssh-keyscan`, 5 seconds at most), and only when a machine on the list could be it; NetBird keeps no key, so
a NetBird machine's is always read. A machine offered with the name of one on the list and another key is another
machine: it is offered as `<name>-<network>` (`studio-tailscale`, `studio-netbird`), or `<name>-2` by address. So is
one whose key cannot be compared (it did not answer): a name alone tells nothing, so a no to it never takes the
listed machine off the list. At the listed machine's own address it is that machine.

A yes puts the route on the machine's line. herdr keeps the address it connects a machine with, so for one it has
connected already the route is recorded and shown, and the connection stays as it is. One herdr has not connected yet
is reached through a Host of herdr-fold's own from then on, `herdr-fold.<name>` in `~/.config/herdr-fold/ssh_config`,
which herdr-fold writes whole from the list (edits there are lost): its first route is the one ssh connects by (the
local network's first, then the virtual networks, then a public address), and every route looks the key up under that
one name (`HostKeyAlias`), so a route that answers with another key, a café's `studio.local`, is refused on every
route. Its key is trusted under that name only from the key `~/.ssh/known_hosts` already trusts for it, and the Host
forwards no agent. `./machines.sh` names a machine's other routes under its heading (`also Tailscale:
studio.tail0000.ts.net`).

herdr and the Herdr app reach those Hosts through one line at the top of `~/.ssh/config`, asked for at the first route:

```text
      herdr-fold reaches a machine by several routes, or through another one, with a Host of its own.
  Add one line at the top of ~/.ssh/config to include them (Include ~/.config/herdr-fold/ssh_config)? [Y/n]
```

A yes puts two lines there, a comment naming herdr-fold and `Include ~/.config/herdr-fold/ssh_config`, above every
Host line of yours, which stay as they are; every ssh on this Mac then knows `herdr-fold.<name>` too. A no is kept:
each machine keeps one route, and only `./machines.sh include` asks again. To take the line off, delete those two
lines (a machine whose address on the list is `herdr-fold.<name>` then needs its route back as its address);
`./uninstall.sh` sets each such machine back to its first route's address, in herdr and on the list, then takes the
lines off with the file ([Uninstalling](uninstall.md#what-goes-and-what-stays)).

A machine Tailscale knows a host key for is checked before anything of it goes on the list: when the key it shows
differs, the questions say `studio's key does not match the one Tailscale knows: not added`, and that key is never
trusted. Tailscale's record is what a machine says of itself, so a second route needs more: the machine must show
the listed machine's own key when asked; one that shows another, is offline or does not answer is not added as its
route, and the questions say why. A NetBird machine is a route of a listed one the same way, only by the key it shows
when asked, never by NetBird's word alone. A key read that takes over a second shows a waiting line, as reading
NetBird's status does: `checking studio's key`, `asking NetBird`.

The list, `~/.config/herdr-fold/machines.txt`, has a line per machine: `name | target | os | key | routes`. The target
is the address herdr connects with; the key the fingerprint; the routes each way to it, `<network> user@address` (the
network `local`, `tailscale`, `netbird`, another word or none), the one in use first, and
`through:<machine> user@address` for one reached through another machine on the list (`ProxyJump`). A line of an
earlier version has the first three fields, and is read as it is: the list is written again only when a machine is
added or changed.

## Networks

herdr-fold reaches every machine over SSH, on any network on which the Mac reaches the machine's SSH port: the local
network, a public address, or a virtual network that joins your machines. The machine questions (the installer's step 8,
Add a machine) start by saying so: "Any network works: a machine is added by its address or name. Tailscale's and
NetBird's machines are also offered by name." Add one by its address or name (`./machines.sh new`), or give it a Host
in `~/.ssh/config` and import it from there (`./machines.sh sshconfig`); `./machines.sh tailscale` offers a Tailscale
network's, `./machines.sh netbird` a NetBird network's.

Of a Tailscale network, its Linux, macOS and Windows machines are offered, tagged servers and machines shared in from
another tailnet among them. Left out, and counted in a line after the questions: Mullvad's exit nodes, the node of
someone one of your machines is shared with (it is on the network only to reach that machine), and a node whose key
expired. A subnet router's machines are on no list of the network: each is reached by its own address, so add it by
that address. Tailscale SSH in check mode asks for a sign-in in the browser now and then, which herdr's connection in
the background cannot answer: give the machines herdr-fold connects to `accept` in the tailnet's SSH rules.

Of a NetBird network, each machine NetBird lists is offered by its NetBird name (`tidepool.netbird.cloud`, or your own
server's domain). NetBird tells no system, so after a yes the machine is reached and its system read, the user offered
`root` (change it as you like); one that answers no SSH, such as a phone, is not added. NetBird's own status is read for
5 seconds at most; when it is signed out, its sign-in expired, or it is not connected, the questions say so in one line
(`NetBird is signed out — sign in first: netbird up`) and offer none of its machines.

| Network | What it is | How a machine is added |
|---|---|---|
| Tailscale, Headscale | WireGuard-based, joins your own machines (Headscale: Tailscale's coordination server, run by yourself) | offered from the Tailscale network |
| NetBird | WireGuard-based, open source, joins your own machines | offered from the NetBird network |
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
./machines.sh sshconfig         # add machines from the Host lines of ~/.ssh/config (not those on Tailscale or NetBird)
./machines.sh tailscale         # add machines from your Tailscale network
./machines.sh netbird           # add machines from your NetBird network
./machines.sh add alpha         # set one machine up again
./machines.sh prepare           # push changed settings out to the machines
./machines.sh remove alpha      # take a machine off the list and the package off the machine
./machines.sh include           # the line in ~/.ssh/config for herdr-fold's Hosts, asked again after a no
herdr machine list              # the connected machines
```

`./machines.sh remove` puts Claude's earlier status line and the machine's own files that the package replaced back on
the machine (a linked file comes back as the link; the package never writes through one), and takes it off the Herdr
app when herdr-fold added it there. Files changed there since stay in its `prepared-changed-<date>/`
([above](#what-the-installer-does-on-a-machine)).
