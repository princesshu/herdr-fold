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

For a machine you add by hand, one announcing itself on the local network or one behind another machine
([A machine behind another](#a-machine-behind-another)) that `~/.ssh/known_hosts` does not know yet, it shows the
fingerprint of the machine's ED25519 key and asks whether to trust it: type `y` once it matches the
machine's own (on a Linux or Mac machine: `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`; on Windows: `ssh-keygen
-lf C:\ProgramData\ssh\ssh_host_ed25519_key.pub`). Only that key is trusted, so ssh refuses the machine if it later
shows another; a machine that shows no ED25519 key is not added. Machines from `~/.ssh/config` and your Tailscale or
NetBird network are not asked about: ssh trusts their key on the first connection and checks it from then on. The list
keeps each machine's key, the machine itself ([One machine, several routes](#one-machine-several-routes)).

## Adding a machine later

Ctrl + B, then Shift + M (or New space's Add machine…) opens Add a machine, a window framed as Settings whose close
button, Esc or Ctrl + C end it at any question. It asks the installer's machine questions (from `~/.ssh/config`, by
address, from a Tailscale or NetBird network where that one is installed, or from the local network) and sets up only
the new machine. It runs `machines.sh` from the `herdr-fold` folder, so keep that folder on the Mac: moved or deleted,
Add a machine says the folder `isn't where the installer left it`, and `./install.sh` run once in its new place records
it again. In the Herdr app, Add machine… (the sidebar's foot, the palette, Ctrl + B, then Shift + M) is the app's own: a
machine added there works once git and Python 3 are on it ([On another machine](app.md#on-another-machine)).

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

A machine offered again under another address, from `~/.ssh/config`, a Tailscale or NetBird network, the local network
or typed in, that shows the key of one on the list is that machine. The questions say so, and offer the route instead
of a second machine:

```text
  studio.tail0000.ts.net is studio, already on the list: also reachable on Tailscale.
  Add this route? [Y/n]
```

Its key is known from Tailscale's own record of it, where Tailscale gives one, or read from the machine before the
question (`ssh-keyscan`, 5 seconds at most), and only when a machine on the list could be it; NetBird and the local
network keep none, so the key of a machine there is always read. A machine offered with the name of one on the list and
another key is another machine: it is offered as `<name>-<network>` (`studio-tailscale`, `studio-netbird`,
`studio-local`), or `<name>-2` by address. So is one whose key cannot be compared (it did not answer): a name alone
tells nothing, so a no to it never takes the listed machine off the list. At the listed machine's own address it is that
machine.

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
route, and the questions say why. A NetBird or local network machine is a route of a listed one the same way, only by
the key it shows when asked, never by the network's word alone. A key read that takes over a second shows a waiting
line, as reading NetBird's status and listening to the local network do: `checking studio's key`, `asking NetBird`,
`looking for machines on this local network`.

The list, `~/.config/herdr-fold/machines.txt`, has a line per machine: `name | target | os | key | routes`. The target
is the address herdr connects with; the key the fingerprint; the routes each way to it, `<network> user@address` (the
network `local`, `tailscale`, `netbird`, `zerotier`, `wireguard`, `tunnel`, `cloudflare`, `public` or none), the one in
use first, and `through:<machine> user@address` for one reached through another machine on the list (`ProxyJump`). A
machine taken from a network keeps that network on its line where its address alone does not tell it (a NetBird
machine in your own server's domain); any other route's network is read each time
([When a machine is away](#when-a-machine-is-away)). A line of an
earlier version has the first three fields, and is read as it is: the list is written again only when a machine is
added or changed.

## Networks

herdr-fold reaches every machine over SSH, on any network on which the Mac reaches the machine's SSH port: the local
network, a public address, or a virtual network that joins your machines. The machine questions (the installer's step 8,
Add a machine) start by saying so: "Any network works: a machine is added by its address or name. Tailscale's,
NetBird's and this local network's machines are also offered by name." Add one by its address or name
(`./machines.sh new`), or give it a Host in `~/.ssh/config` and import it from there (`./machines.sh sshconfig`);
`./machines.sh tailscale` offers a Tailscale network's, `./machines.sh netbird` a NetBird network's and
`./machines.sh local` those announcing SSH on this local network.

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

Of the local network, the machines announcing SSH on it (Bonjour, as a Mac with Remote Login on does) are offered after
a question of their own, `Look for machines on this local network?`, whose default is no. A yes first says what they
are: "These are the machines announcing SSH on the network this Mac is on now (a café's too). Any of them can claim any
name, so each one's key is asked about." Nothing is scanned: the Mac's `dns-sd` is listened to for 3 seconds, then each
machine heard is looked up for 2 seconds, all at once. Each is offered, and kept, by its `.local` name (`lab-pi.local`),
never by the address it has today; the name it announces of itself (`Dev's MacBook Pro`) shows in its question where it
says more than that, and is never kept. This Mac is left out, and a machine announcing another port than 22 is named
with how to add it (a Host with that `Port` in `~/.ssh/config`). After a yes, the user offered is this Mac's own, then
the machine's fingerprint is shown and asked about, as for one added by hand, Enter alone a no.

| Network | What it is | How a machine is added |
|---|---|---|
| Local network | the network this Mac is on now: home, an office or a café's | offered when it announces SSH, by its `.local` name, its fingerprint asked about |
| Tailscale, Headscale | WireGuard-based, joins your own machines (Headscale: Tailscale's coordination server, run by yourself) | offered from the Tailscale network |
| NetBird | WireGuard-based, open source, joins your own machines | offered from the NetBird network |
| ZeroTier | a virtual network of your own machines | by its address |
| WireGuard | a tunnel you set up yourself | by its address |
| Cloudflare Zero Trust | the machine reached through Cloudflare's `cloudflared` | a `~/.ssh/config` Host with its `ProxyCommand`, imported from there |
| Cloudflare WARP alone | protects your traffic to the internet; it does not join your machines | — |

The Mac can be on several at once. Keep their address ranges apart (Tailscale and NetBird take the same range unless one
is changed), and mind a mode that sends all traffic through one network (Cloudflare WARP's full mode, a company's
private network, Tailscale's exit node): it can cut the others off. A machine reached only through another one is
added through it: [A machine behind another](#a-machine-behind-another).

"WireGuard" and the "WireGuard" logo are registered trademarks of Jason A. Donenfeld.

## A machine behind another

A machine this Mac does not reach itself, a server on a client's network or one next to a machine of yours, is reached
through a machine on the list that reaches it: `./machines.sh through lumen-api`. lumen-api must be a Linux or macOS
machine herdr-fold has prepared, as it lists what it sees with Python there (looking around from a Windows machine
comes later). It lists only what lumen-api knows already, and scans nothing:

- its Tailscale and NetBird peers that this Mac does not reach itself (one this Mac's own network lists is offered by
  that network's own question);
- the machines announcing SSH next to it (`dns-sd` on a Mac, `avahi-browse` on Linux; without it, a line says so);
- the Hosts of its `~/.ssh/config`, never a pattern, a git host or one with a jump or a proxy of its own.

Each of its commands is read for 5 seconds at most, and what comes back is checked here as any network's word: a host
name, an address, a user and a port each against a strict pattern, 1 MB and 200 machines at most, the rest counted in
a line after the questions. lumen-api itself, this Mac and the machines on the list are left out. Each machine is
offered on a question of its own, default no:

```text
== lumen-api (Tailscale, linux)
      lumen-api lists what it sees: its Tailscale and NetBird peers, the machines announcing SSH next to it, its
      ~/.ssh/config. Nothing is scanned.
  [✓] lumen-api sees 3 machines this Mac does not reach itself
  Import build-01 (198.51.100.30, from lumen-api's ~/.ssh/config) through lumen-api? [y/N] y
  user [root]:
      256 SHA256:Qm9vZ0x1bW5hcGlzYWZlMTIzNDU2Nzg5MGFiY2RlZmc 198.51.100.30 (ED25519)
  Trust this ED25519 key of build-01, read through lumen-api (compare it with the machine's own)? [y/N] y
  [!] build-01 does not take this Mac's key (it may accept lumen-api's own key only).
  Put this Mac's public key on build-01, through lumen-api's own login? [y/N] y
  [✓] build-01 added (linux), through lumen-api
```

Its key is read end to end through lumen-api before anything of it is trusted (with no login: ssh's `none` method
alone), and its fingerprint is shown and asked about, Enter alone a no, whatever lumen-api's list says of the machine:
compare it with the machine's own. Only that key is trusted, under the machine's own Host name (`herdr-fold.build-01`);
where `~/.ssh/known_hosts` trusts another key under that name already, the machine is not added. One that shows the key
of a machine on the list is that machine, never a second one.

This Mac then logs in with its own key, through lumen-api: lumen-api never gets this Mac's key or its agent. A machine
that takes lumen-api's own key alone says so, and on a yes, asked for each machine (default no), lumen-api logs in with
its own key and adds this Mac's public key, one line, to the machine's `~/.ssh/authorized_keys`, checking first that the
machine shows the key you trusted; never this Mac's private key, and never where lumen-api's Host for it logs in with a
certificate or a security key (ask its admin then). A no leaves the machine off the list: put the key there yourself,
then ask again.

A machine said yes to goes on the list reached by its own Host in herdr-fold's ssh file, `herdr-fold.build-01`, whose
`ProxyJump` is lumen-api's address (`build-01 | herdr-fold.build-01 | linux | SHA256:… | through:lumen-api
root@198.51.100.30`), so it needs the one `Include` line at the top of `~/.ssh/config`, asked at the first yes; then
`./machines.sh add build-01` sets it up as any machine. lumen-api sees that a connection goes to build-01's address and
port, when, and how much passes; never what passes (the connection is end to end, checked against build-01's key). One
whose SSH server lets nothing through (`AllowTcpForwarding no`) says `lumen-api does not let connections through to
other machines (AllowTcpForwarding no in its sshd_config).`, and with lumen-api away its own sentence comes under
build-01's ([When a machine is away](#when-a-machine-is-away)).

`./machines.sh remove lumen-api` asks first `build-01 and db-02 go through lumen-api: take them off too?`, default no. A
yes takes them off first, each through lumen-api, then lumen-api; a no keeps them working, lumen-api staying their jump
host by its address (`through:root@lumen-api.tail0000.ts.net` on their lines): `build-01 and db-02 stay: lumen-api
remains their jump host.` Its key stays pinned there: written to `~/.ssh/known_hosts` at that address (where it is
not there already), so the jump trusts only lumen-api's own key, as under its own name before. A jump host whose key
is not trusted here, whose address holds another key, or that is itself behind another machine stays on the list.

## When a machine is away

`./machines.sh` names each machine's network in its heading, `== lumen-api (Tailscale, linux)`, a machine behind
another `through lumen-api`, its other routes under it. A machine it cannot reach says why in one sentence, the first
of the checks below that fails, and under it what to do:

```text
== harbor-web (Tailscale, linux)
  [!] harbor-web is offline on Tailscale, last seen 3 h ago.
== studio (Local network, macos)
      also Tailscale: studio.tail0000.ts.net
  [!] The machine at studio.local shows another key than studio's: not used.
      On Tailscale it answers.
== tidepool (NetBird, linux)
  [!] NetBird is not running on this Mac.
      Start it: netbird up
```

| Check | What it says | What to do |
|---|---|---|
| The network's client on this Mac | `NetBird is not installed on this Mac.` | its download page |
| Its client on | `Tailscale is off on this Mac.`, `NetBird is not running on this Mac.` | `tailscale up`, `netbird up` |
| Its client signed in | `Tailscale is signed out on this Mac.`, `This Mac's Tailscale key has expired.`, `This Mac waits for approval on its tailnet.`, `NetBird is signed out on this Mac.`, `NetBird's session on this Mac has expired.`, `NetBird cannot reach its management server.` | `tailscale login`, the admin console (its link on a `.ts.net` tailnet; on Headscale or another control server, ask its admin), `netbird up` |
| The machine on that network | `harbor-web is offline on Tailscale, last seen 3 h ago.`, `kelp-ci's Tailscale key has expired.`, `tidepool is not in this Mac's NetBird network.` | for an expired key, the admin console |
| This local network | `lab-pi is not on this local network.` (its `.local` name gives no answer) | another route of it, where one shows its key: `On Tailscale it answers.` |
| Its SSH | `db-02 does not answer: is it on and awake?`, `lumen-api answers, but no SSH server runs on it.`, `alpha: no machine of that name here — check the name, and that the Mac reaches its network.` | how to turn SSH on |
| Its key | `lumen-api shows another host key than the one this Mac trusts.`; on a route of a machine with several: `The machine at studio.local shows another key than studio's: not used.` | `ssh-keygen -R`, after checking the new key on it; another route that answers |
| Its login | `lumen-api does not take this Mac's key.`, `Tailscale SSH on lumen-api asks for a sign-in in the browser.` | `ssh` to it by hand, once in a terminal |
| The machine in front of it | `build-01 is reached through lumen-api, which does not answer.` with lumen-api's own sentence under it, `lumen-api does not let connections through to other machines (AllowTcpForwarding no in its sshd_config).` | lumen-api's |

A network is told from what this Mac knows, the list first: the network a route keeps there, else a name or address
Tailscale's or NetBird's own list has (both take their addresses from the same range, so an address alone tells
neither), a name in one of their domains (`.ts.net`, `.netbird.cloud`, also while the client is off), a `.local`
name, else where the Mac's own routes send the address (`route -n get`): a tunnel by its own address (Tailscale's,
NetBird's, ZeroTier's, else WireGuard's where its app is installed), a home network's address as the local network, any
other as public. A `~/.ssh/config` Host with a `cloudflared` proxy is Cloudflare's, one with a jump host of its own
`through` it. NetBird's idle machines are no reason: an idle connection can be up too.

Nothing is scanned. The networks' own status is read once for the whole list (5 seconds at most each), `route -n get`
asked only for an address none of them lists (2 seconds), each machine logged into once, within ssh's own 10 seconds;
a route's key is read (`ssh-keyscan`, 3 seconds) only to find another route that answers. `./machines.sh add`,
`prepare` and `remove`, and the questions, say a failed login in the same sentences.

In the Herdr app, Spaces shows each machine with its network's mark, and once five or more are on two networks or more
it groups them under their network's head, in the order a machine's routes are tried: the local network, Tailscale,
NetBird, ZeroTier, WireGuard, another tunnel, Cloudflare, public. A network whose client is off says so on its head, in
the same sentences, and one with none of its machines added yet offers them there, asked about in a terminal tab
([Spaces](app.md#spaces)). The status bar's machine wears its mark. The app looks once a minute while it shows a remote
machine, and soon after one comes or goes: the networks' own status and the list as above, a machine added in the app's
own Settings → Machines read by its address, never a login.

## Systems

| System | Notes |
|---|---|
| Linux | x86_64 or ARM. The prompt applies only inside herdr panes. |
| macOS | System Settings → General → Sharing → turn on **Remote Login**. For repos in the Documents folder, in the same place: ⓘ → **Allow full disk access for remote users**. |
| Windows | x86_64, Windows 10 1803 or newer (for its tar). Needs OpenSSH Server (Settings → System → Optional features → OpenSSH Server, then start the sshd service), with cmd or PowerShell as its shell; no file transfer (scp, SFTP): the package goes in plain commands. For an admin user the key goes in `C:\ProgramData\ssh\administrators_authorized_keys`. The installer installs Python with winget, or, if that fails over SSH, with the python.org installer for the current user. The right column is the sidebar and a terminal here too (`sidebar.ps1`); Claude's status line is the same Python script as elsewhere, started through PowerShell. The prompt works only where PowerShell profiles are allowed. New spaces come from the command line, see [Using it](usage.md#spaces). |

## Commands

In the `herdr-fold` folder:

```bash
./machines.sh                   # each machine's network and state (connection, programs), or why it is away
./machines.sh new               # add a machine: the installer's questions, then only the new one is set up
./machines.sh sshconfig         # add machines from the Host lines of ~/.ssh/config (not those on Tailscale or NetBird)
./machines.sh tailscale         # add machines from your Tailscale network
./machines.sh netbird           # add machines from your NetBird network
./machines.sh local             # add machines announcing SSH on this local network, each key asked about
./machines.sh through lumen-api # add the machines lumen-api sees, reached through it
./machines.sh add alpha         # set one machine up again
./machines.sh prepare           # push changed settings out to the machines
./machines.sh remove alpha      # take a machine off the list and the package off the machine
./machines.sh include           # the line in ~/.ssh/config for herdr-fold's Hosts, asked again after a no
herdr machine list              # the connected machines
```

`./machines.sh remove` asks first about the machines that go through the one it removes
([A machine behind another](#a-machine-behind-another)), then puts Claude's earlier status line and the machine's own
files that the package replaced back on the machine (a linked file comes back as the link; the package never writes
through one), and takes it off the Herdr app when herdr-fold added it there. Files changed there since stay in its
`prepared-changed-<date>/` ([above](#what-the-installer-does-on-a-machine)).
