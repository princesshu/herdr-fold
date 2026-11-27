"""The machine list, ~/.config/herdr-fold/machines.txt: a machine is its SSH host key, a network one of its routes, and
herdr-fold's own ssh file is written whole from it. machines.sh and uninstall.sh run it: machines.py add|identify|route|
behind|keep|copy-key|moved|hosts|include … (every command and its arguments: commands())."""
import base64
import binascii
import contextlib
import ipaddress
import os
import re
import shlex
import subprocess
import sys
import tempfile

PREFIX = "herdr-fold."          # a machine's own Host in herdr-fold's ssh file: herdr-fold.<name>
# the networks a route goes through, in the order a machine's routes are tried: the local network first, then the
# virtual networks, Cloudflare, a public address, and last through another machine
NETWORKS = ("local", "tailscale", "netbird", "zerotier", "wireguard", "tunnel", "cloudflare", "public", "through")
HEADER = (
    "# Remote machines in herdr (herdr-fold), filled in by the installer; edit by hand if you like. No passwords"
    " or keys",
    "# here: login uses this Mac's SSH key. Lines:  name | target | os | key | routes",
    "#   name: shown in herdr's sidebar (--machine <name>); target: how herdr reaches it: user@machine, a Host of",
    "#   ~/.ssh/config, or herdr-fold.<name>, herdr-fold's own Host for it; os: linux, macos or windows; key: its",
    "#   ED25519 host key's fingerprint, the machine itself; routes: each way to it, <network> user@address, the one",
    "#   in use first",
)
OLD_HEADER = (                  # the header of a list from before the routes, replaced when the list is written
    "# here: login uses this Mac's SSH key. Lines:  name | user@machine | os (linux / macos / windows)",
    "#   name: shown in herdr's sidebar (--machine <name>); machine: a DNS name, IP address or Tailscale name",
)
SSH_HEAD = "# Written by herdr-fold from machines.txt; edits here are lost."
INCLUDE = ("# herdr-fold: its machines' own Hosts (./uninstall.sh takes these two lines off)",
           "Include ~/.config/herdr-fold/ssh_config")
# What each source of a machine proves of it, and how its host key comes to be trusted: SECURITY.md's table
SOURCES = (
    ("~/.ssh/config", "your own Host", "ssh trusts it on the first connection (`accept-new`)"),
    ("Tailscale", "its coordination server signed the machine into your network", "trusted on the first connection"),
    ("NetBird", "its management server signed the machine into your network", "trusted on the first connection"),
    ("by address", "nothing: whatever answers there", "its fingerprint is shown and asked about first"),
    ("Bonjour", "nothing: any machine on the network this Mac is on can announce any name",
     "its fingerprint is shown and asked about first"),
    ("another machine's list", "nothing: what a machine on the list says it sees",
     "its fingerprint, read end to end through that machine, is shown and asked about first"),
)
OSES = ("linux", "macos", "windows")
# the public keys this Mac's own may be, as OpenSSH writes them: one of these is put on a machine behind another (a
# security key's type ends in OpenSSH's domain, written apart here: it reads as an e-mail address)
OPENSSH = "@" "openssh.com"
PUBLIC_KEYS = ("ssh-ed25519", "ssh-rsa", "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521",
               "sk-ssh-ed25519" + OPENSSH, "sk-ecdsa-sha2-nistp256" + OPENSSH)
KEY = re.compile(r"SHA256:[A-Za-z0-9+/]{1,64}")                 # a host key's fingerprint, as ssh-keygen -l prints it
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")           # a machine's name that can be a Host's
LABEL = re.compile(r"[A-Za-z0-9-]{1,63}")                       # a DNS name's part between two dots
USER = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{0,31}")             # a login name (Windows' have capitals)
PORT = re.compile(r"[1-9][0-9]{0,4}")
BASE64 = re.compile(r"[A-Za-z0-9+/]+={0,2}")
CONTROLS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def host_ok(text):
    """A DNS name: letters, digits and hyphens between dots, at most 253 characters, never starting as an option."""
    return (isinstance(text, str) and 0 < len(text) <= 253 and not text.startswith("-")
            and all(LABEL.fullmatch(label) for label in text.split(".")))


def address_ok(text):
    """An IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(text)
    except ValueError:
        return False
    return True


def user_ok(text):
    return isinstance(text, str) and bool(USER.fullmatch(text))


def port_ok(port):
    return bool(PORT.fullmatch(str(port))) and int(port) < 65536


def clean(text, limit=200):
    """TEXT without its control characters (C0, DEL, C1), cut at LIMIT characters: safe to print."""
    return CONTROLS.sub("", str(text))[:limit]


def reachable_at(user, host, port):
    """Whether [USER@]HOST[:PORT] can go into an ssh file or a command as it is: each part checked."""
    return ((host_ok(host) or address_ok(host)) and (user is None or user_ok(user))
            and (port is None or port_ok(port)))


def parse_address(text):
    """(user, host, port) of [user@]host[:port], an IPv6 host in brackets when a port follows; nothing checked."""
    user, _, rest = text.rpartition("@")
    port = None
    if rest.startswith("["):
        host, _, after = rest[1:].partition("]")
        port = after[1:] if after.startswith(":") else None
    elif rest.count(":") == 1:
        host, port = rest.split(":")
    else:
        host = rest
    return user or None, host, int(port) if port and port.isdigit() else None


def address_text(user, host, port):
    shown = f"[{host}]" if port and ":" in host else host
    return (f"{user}@" if user else "") + shown + (f":{port}" if port else "")


def guess_network(host):
    """A route's network as its address alone tells it: a Tailscale name, one in NetBird's own domains (its service's,
    a server of your own's default), a Bonjour name; None for any other."""
    host = (host or "").lower().rstrip(".")
    if host.endswith(".ts.net"):
        return "tailscale"
    if host.endswith((".netbird.cloud", ".netbird.selfhosted")):
        return "netbird"
    if host.endswith(".local"):
        return "local"
    return None


def target_route(target):
    """The one route of a line without routes: its target's, its network not known."""
    user, host, port = parse_address(target)
    return {"network": None, "address": host, "user": user, "port": port, "through": None}


def parse_route(text):
    """A route, "[network] [user@]address[:port]" (through:<machine> its network behind another); None if not one."""
    parts = text.split()
    if not 1 <= len(parts) <= 2:
        return None
    word, where = parts if len(parts) == 2 else (None, parts[0])
    through = None
    if word and word.startswith("through:"):
        word, through = "through", word[len("through:"):]
    if word is not None and word not in NETWORKS or word == "through" and not through:
        return None
    user, host, port = parse_address(where)
    if not host:
        return None
    return {"network": word, "address": host, "user": user, "port": port, "through": through}


def route_text(route):
    word = f"through:{route['through']}" if route.get("through") else route.get("network")
    where = address_text(route.get("user"), route["address"], route.get("port"))
    return f"{word} {where}" if word else where


def parse_line(line):
    """A machine of a list line, `name | target | os | key | routes`; an older one has the first three."""
    fields = [field.strip() for field in line.rstrip("\n").split("|")] + [""] * 4
    name, target, os_, key, routes = fields[:5]
    if not name or not target:
        return None
    found = [route for route in (parse_route(one) for one in routes.split(",") if one.strip()) if route]
    return {"name": name, "target": target, "os": os_, "key": key if KEY.fullmatch(key) else None,
            "routes": found or [target_route(target)]}


def read(path):
    """The machines of the list at PATH, in its order ([] without one)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    return [machine for machine in (parse_line(line) for line in lines
                                    if line.strip() and not line.lstrip().startswith("#")) if machine]


def fields(machine):
    """A machine's fields as written: its routes left out while they are only its target's, empty ones off the end."""
    routes = machine["routes"]
    said = "" if routes == [target_route(machine["target"])] else ", ".join(route_text(route) for route in routes)
    found = [machine["name"], machine["target"], machine.get("os") or "", machine.get("key") or "", said]
    while len(found) > 3 and not found[-1]:
        found.pop()
    return found


def lines_of(machines):
    """A line for each machine, its columns aligned (a column padded only where another follows it)."""
    rows = [fields(machine) for machine in machines]
    widths = [max([16] + [len(row[0]) for row in rows])]
    widths += [max([len(row[n]) for row in rows if len(row) > n + 1] or [0]) for n in (1, 2, 3)]
    return [" | ".join(cell.ljust(widths[n]) if n < len(row) - 1 else cell for n, cell in enumerate(row))
            for row in rows]


def replace(path, text, mode):
    """TEXT written whole beside PATH (a link's own file, the link kept), then put in its place with MODE."""
    real = os.path.realpath(path)
    folder = os.path.dirname(real)
    os.makedirs(folder, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=folder, prefix=f".{os.path.basename(real)}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, real)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise


def write(path, machines):
    """The list at PATH with MACHINES, one aligned line each where its line was (a new one at the end), every comment
    line of yours kept where it was; herdr-fold's header on top of a list that had it, or of a new one."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            old = f.read().splitlines()
        mode = os.stat(path).st_mode & 0o777
    except FileNotFoundError:
        old, mode = None, 0o644
    queued = {}
    for machine, line in zip(machines, lines_of(machines)):
        queued.setdefault(machine["name"], []).append(line)
    own = set(HEADER) | set(OLD_HEADER)
    out = list(HEADER) if old is None or own & set(old) else []
    for line in old or []:
        if line in own:
            continue
        machine = None if not line.strip() or line.lstrip().startswith("#") else parse_line(line)
        if machine is None:
            out.append(line)                    # a comment, an empty line or a line that is no machine: as it was
        elif queued.get(machine["name"]):
            out.append(queued[machine["name"]].pop(0))
    out += [line for name in dict.fromkeys(machine["name"] for machine in machines) for line in queued[name]]
    replace(path, "\n".join(out) + "\n", mode)


def jump_target(through, machines, name):
    """The target a route through THROUGH jumps by: that listed machine's, else THROUGH itself, a jump host kept for the
    machines behind it after its own removal; None where it is no address, or the machine itself."""
    targets = {machine["name"]: machine["target"] for machine in machines}
    jump = targets.get(through, through)
    if not through or through == name or jump == PREFIX + name:
        return None
    return jump if reachable_at(*parse_address(jump)) else None


def ssh_file(machines):
    """herdr-fold's ssh file: for each machine whose target is herdr-fold.<name>, that Host to its first route (through
    the machine it is behind), its key looked up under that one name on every route, the agent never forwarded."""
    lines = [SSH_HEAD]
    for machine in machines:
        name, route = machine["name"], (machine["routes"] or [None])[0]
        if machine["target"] != PREFIX + name or not NAME.fullmatch(name) or not route:
            continue
        user, host, port = route.get("user"), route["address"], route.get("port")
        if not reachable_at(user, host, port) or host.startswith(PREFIX):
            continue
        block = ["", f"Host {PREFIX}{name}", f"  HostName {host}"] + ([f"  User {user}"] if user else [])
        block += [f"  Port {port}"] if port and port != 22 else []
        block += [f"  HostKeyAlias {PREFIX}{name}", "  CheckHostIP no", "  ForwardAgent no"]
        if route.get("through"):
            jump = jump_target(route["through"], machines, name)
            if not jump:
                continue
            block.append(f"  ProxyJump {jump}")
        lines += block
    return "\n".join(lines) + "\n"


def run(argv, text=None):
    """ARGV's output, None when it fails, is missing or takes over 15 s."""
    try:
        done = subprocess.run(argv, input=text, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def fingerprint(public_key_line):
    """The SHA256 fingerprint of a public key ("ssh-ed25519 AAAA…", a known_hosts line too) as ssh-keygen -l prints it;
    None for no key."""
    for line in (run(["ssh-keygen", "-lf", "-"], public_key_line.strip() + "\n") or "").splitlines():
        found = line.split()
        if len(found) > 1 and KEY.fullmatch(found[1]):
            return found[1]
    return None


def trusted_key(host, known_hosts, port=None):
    """The ED25519 key KNOWN_HOSTS trusts for HOST ("ssh-ed25519 AAAA…"), as ssh-keygen -F finds it, a hashed name too;
    None where it has none."""
    if not (host_ok(host) or address_ok(host)) or not port_ok(port or 22):
        return None
    for line in (run(["ssh-keygen", "-F", f"[{host}]:{port}" if port and port != 22 else host, "-f", known_hosts])
                 or "").splitlines():
        found = line.split()
        if len(found) >= 3 and not found[0].startswith(("#", "@")) and found[1] == "ssh-ed25519":
            return f"{found[1]} {found[2]}"
    return None


def alias_line(name, key_line):
    """A known_hosts line for KEY_LINE under herdr-fold.<NAME>, the one name every route of the machine looks its key up
    by (HostKeyAlias). Only ever made from a key known_hosts already trusts: trusted_alias()."""
    found = key_line.split()
    if not NAME.fullmatch(name) or len(found) < 2 or found[0] != "ssh-ed25519" or not BASE64.fullmatch(found[1]):
        return None
    return f"{PREFIX}{name} {found[0]} {found[1]}"


def trusted_alias(machine, known_hosts):
    """MACHINE's alias line, from the ED25519 key KNOWN_HOSTS trusts at one of its routes that is the machine's own (its
    fingerprint the listed one); None while none is."""
    for route in machine["routes"] if machine.get("key") else []:
        key = trusted_key(route["address"], known_hosts, route.get("port"))
        if key and fingerprint(key) == machine["key"]:
            return alias_line(machine["name"], key)
    return None


def same_machine(machines, key):
    """The listed machine whose host key is KEY (a fingerprint), else None: a candidate showing it is that machine."""
    return next((machine for machine in machines if key and machine.get("key") == key), None)


def unique_name(machines, name, network=None):
    """NAME, else NAME-NETWORK (alpha-netbird), else NAME-2, NAME-3 …: one no listed machine has."""
    names = {machine["name"] for machine in machines}
    if name not in names:
        return name
    base = f"{name}-{network}" if network and network != "through" else name
    if base not in names:
        return base
    n = 2
    while f"{base}-{n}" in names:
        n += 1
    return f"{base}-{n}"


def resolve(target):
    """Where ssh reaches TARGET, its Hosts applied (ssh -G connects nowhere): (user, host, port, the name its key is
    kept under); None for one through a jump host or a proxy."""
    conf = {}
    for line in (run(["ssh", "-G", "--", target]) or "").splitlines():
        key, _, value = line.partition(" ")
        conf.setdefault(key.lower(), value.strip())
    if not conf.get("hostname"):
        user, host, port = parse_address(target)
        return user, host, port, host
    if conf.get("proxyjump", "none") != "none" or conf.get("proxycommand", "none") != "none":
        return None
    port = int(conf["port"]) if conf.get("port", "").isdigit() and conf["port"] != "22" else None
    alias = conf.get("hostkeyalias", "none")
    return conf.get("user") or None, conf["hostname"], port, conf["hostname"] if alias == "none" else alias


def key_of(target, known_hosts):
    """The fingerprint of the ED25519 key KNOWN_HOSTS trusts where TARGET leads, else None."""
    where = resolve(target)
    if not where:
        return None
    key = trusted_key(where[3], known_hosts, where[2] if where[3] == where[1] else None)
    return fingerprint(key) if key else None


def known_keys(machines, known_hosts):
    """{name: fingerprint} of the listed machines: the listed key, else that of the one known_hosts trusts where its
    target leads (an older line has none yet, and is not written for it)."""
    found = {}
    for machine in machines:
        key = machine.get("key") or key_of(machine["target"], known_hosts)
        if key:
            found[machine["name"]] = key
    return found


def place(machine, seen):
    """"listed" where SEEN (a candidate's names and addresses) holds MACHINE's target or first route, "known" where it
    holds another of its routes, else None."""
    own = {machine["target"], parse_address(machine["target"])[1]}
    own |= {machine["routes"][0]["address"]} if machine["routes"] else set()
    if own & seen:
        return "listed"
    return "known" if {route["address"] for route in machine["routes"][1:]} & seen else None


def identify(machines, known, keys, network, name, addresses=()):
    """What a candidate is: (listed, name) at a listed machine's own address (its target, a Host so named), (known,
    name) at another of its routes, (route, name) another way to the listed machine whose host key it shows, else (new,
    the name it gets): a name alone, its key not compared, is never taken for a listed machine (it may be another)."""
    seen, keys = {one for one in (name, *addresses) if one}, set(keys)
    for machine in machines:
        if keys and known.get(machine["name"]) in keys:
            return place(machine, seen) or "route", machine["name"]
    for machine in machines:
        where = place(machine, seen)
        if where:
            return where, machine["name"]
    return "new", unique_name(machines, name, network)


def add_route(machines, name, key, network, address, move, known_hosts):
    """MACHINES with ADDRESS (on NETWORK) a route of machine NAME, whose host key KEY is; with MOVE its target becomes
    its own Host when known_hosts trusts its key at a route already (the alias line, returned with the machines)."""
    machine = next(one for one in machines if one["name"] == name)
    machine["key"] = machine.get("key") or (key if KEY.fullmatch(key or "") else None)
    if machine["routes"] == [target_route(machine["target"])]:          # its target's route, as ssh reaches it
        where = resolve(machine["target"]) or parse_address(machine["target"]) + (None,)
        machine["routes"] = [{"network": guess_network(where[1]), "address": where[1], "user": where[0],
                              "port": where[2], "through": None}]
    user, host, port = parse_address(address)
    first = machine["routes"][0]
    route = {"network": network or guess_network(host), "address": host, "user": user or first.get("user"),
             "port": port, "through": None}
    if not any((one["address"], one.get("port")) == (host, port) for one in machine["routes"]):
        machine["routes"].append(route)
    rank = lambda one: NETWORKS.index(one["network"] or "public")                    # noqa: E731
    alias = None
    own = parse_address(machine["target"])[1] == (resolve(machine["target"]) or (None, None))[1]
    if move and own and "@" in machine["target"] and machine["target"] != PREFIX + name:
        alias = trusted_alias(machine, known_hosts)
        if alias or trusted_key(PREFIX + name, known_hosts):
            machine["target"] = PREFIX + name
    if machine["target"] == PREFIX + name:                  # its own Host: the routes in their order
        machine["routes"].sort(key=rank)
    else:                                                   # herdr's target: the route it connects by first
        machine["routes"][1:] = sorted(machine["routes"][1:], key=rank)
    return machines, alias


def moved(machines):
    """[(name, address)] of the machines at herdr-fold's own Host, ADDRESS their first route's as herdr takes it
    ([user@]host[:port]); None for one only reachable through another machine."""
    found = []
    for machine in machines:
        if machine["target"] == PREFIX + machine["name"]:
            route = (machine["routes"] or [{}])[0]
            where = (route.get("user"), route.get("address"), route.get("port"))
            usable = route and not route.get("through") and reachable_at(*where) and not where[1].startswith(PREFIX)
            found.append((machine["name"], address_text(*where) if usable else None))
    return found


def behind_of(machines, name):
    """The names of the machines whose route in use goes through machine NAME, in the list's order."""
    return [machine["name"] for machine in machines
            if machine["routes"] and machine["routes"][0].get("through") == name]


def jump_address(machines, name):
    """What the machines behind NAME jump by once it has left the list: its target, or, at its own Host, its first
    route's address; None where it is itself reached through another machine (or not listed)."""
    machine = next((one for one in machines if one["name"] == name), None)
    if machine is None:
        return None
    if machine["target"] == PREFIX + name:
        return dict(moved(machines)).get(name)
    return machine["target"] if reachable_at(*parse_address(machine["target"])) else None


def keep_behind(machines, name):
    """MACHINES with each route through NAME jumping by jump_address() instead, so it can leave the list; None where
    it has none."""
    jump = jump_address(machines, name)
    if not jump:
        return None
    for route in (route for machine in machines for route in machine["routes"]):
        if route.get("through") == name:
            route["through"] = jump
    return machines


def add_behind(machines, name, os_, key, through, address):
    """MACHINES with machine NAME (its OS and host key KEY) reached through THROUGH, a listed machine, at ADDRESS
    ([user@]host[:port], as THROUGH reaches it), by its own Host; None where a part is not what it should be."""
    user, host, port = parse_address(address)
    names = {machine["name"] for machine in machines}
    if (name in names or not NAME.fullmatch(name) or through not in names or os_ not in OSES or not KEY.fullmatch(key)
            or not user or not reachable_at(user, host, port) or host.startswith(PREFIX)):
        return None
    route = {"network": "through", "address": host, "user": user, "port": port, "through": through}
    return machines + [{"name": name, "target": PREFIX + name, "os": os_, "key": key, "routes": [route]}]


def public_key(path):
    """This Mac's public key in the file at PATH, "type base64 herdr-fold" (its own comment, which may name the account,
    left off); None for anything else, its private half above all."""
    try:
        with open(path, encoding="ascii") as f:
            lines = [line for line in f.read(16384).splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError):
        return None
    parts = lines[0].split() if len(lines) == 1 else []
    if len(parts) < 2 or parts[0] not in PUBLIC_KEYS or not BASE64.fullmatch(parts[1]):
        return None
    try:
        blob = base64.b64decode(parts[1], validate=True)
    except (binascii.Error, ValueError):
        return None
    kind = len(parts[0]).to_bytes(4, "big") + parts[0].encode()
    return f"{parts[0]} {parts[1]} herdr-fold" if blob.startswith(kind) else None


def copy_key_command(name, user, address, port, key_line, public, alias=None):
    """The command a jump host runs to put PUBLIC (this Mac's public key) on machine NAME with its own login: to
    ADDRESS, or its ~/.ssh/config Host ALIAS, there checked against KEY_LINE alone (the key read end to end and trusted
    here), forwarding nothing; the key appended once. None where a part is not what it should be."""
    known = alias_line(name, key_line or "")
    if not (known and public and user_ok(user) and reachable_at(user, address, port)
            and (alias is None or NAME.fullmatch(alias))):
        return None
    append = ('umask 077; mkdir -p "$HOME/.ssh" && touch "$HOME/.ssh/authorized_keys" && '
              '{ grep -qxF "$1" "$HOME/.ssh/authorized_keys" || printf "%s\\n" "$1" >> "$HOME/.ssh/authorized_keys"; }')
    there = "sh -c " + shlex.quote(append) + " sh " + shlex.quote(public)
    options = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ClearAllForwardings=yes", "-o",
               "ForwardAgent=no", "-o", "StrictHostKeyChecking=yes", "-o", "GlobalKnownHostsFile=/dev/null", "-o",
               f"HostKeyAlias={PREFIX}{name}", "-o", "HostKeyAlgorithms=ssh-ed25519", "-o", "CheckHostIP=no",
               *(["-p", str(port)] if port else []), "-l", user]
    return (f'f=$(mktemp) || exit 1; printf "%s\\n" {shlex.quote(known)} > "$f"; '
            f'ssh {" ".join(shlex.quote(one) for one in options)} -o UserKnownHostsFile="$f" -- '
            f'{shlex.quote(alias or address)} {shlex.quote(there)}; s=$?; rm -f "$f"; exit $s')


def write_ssh_file(path, machines):
    """herdr-fold's ssh file at PATH from MACHINES, when one of them needs a Host or the file is there already."""
    if os.path.exists(path) or any(machine["target"] == PREFIX + machine["name"] for machine in machines):
        replace(path, ssh_file(machines), 0o600)


def included(config):
    """Whether the ssh config at CONFIG has the Include line of herdr-fold's Hosts."""
    try:
        with open(config, encoding="utf-8", errors="replace") as f:
            return INCLUDE[1] in (line.strip() for line in f)
    except OSError:
        return False


def include(config):
    """The two INCLUDE lines on top of the ssh config at CONFIG (made, yours alone, where there is none), above every
    Host line, so they apply to all; nothing where it has them."""
    if included(config):
        return
    try:
        with open(config, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        mode = os.stat(config).st_mode & 0o777
    except FileNotFoundError:
        lines, mode = [], 0o600
        os.makedirs(os.path.dirname(config), mode=0o700, exist_ok=True)
    replace(config, "\n".join(list(INCLUDE) + ([""] if lines else []) + lines) + "\n", mode)


def uninclude(config):
    """INCLUDE's two lines off the ssh config at CONFIG again, with the empty line put after them; whether they were."""
    try:
        with open(config, encoding="utf-8", errors="replace") as f:
            text = f.read()
        mode = os.stat(config).st_mode & 0o777
    except OSError:
        return False
    lines = text.splitlines()
    at = next((n for n, line in enumerate(lines) if line.strip() == INCLUDE[1]), None)
    if at is None:
        return False
    start = at - 1 if at and lines[at - 1] == INCLUDE[0] else at
    end = at + 2 if at + 1 < len(lines) and not lines[at + 1].strip() and start == 0 else at + 1
    kept = lines[:start] + lines[end:]
    replace(config, "\n".join(kept) + ("\n" if kept else ""), mode)
    return True


def main(argv):
    """The commands machines.sh runs; exit status 1 when a file cannot be written, 2 for a command it does not know."""
    try:
        return commands(argv)
    except OSError:
        return 1


def commands(argv):
    """Each command with its arguments (LIST: the machine list's path)."""
    command, args = (argv[1] if len(argv) > 1 else ""), argv[2:]
    home = os.path.expanduser("~")
    known_hosts = os.path.join(home, ".ssh", "known_hosts")
    hosts = os.path.join(home, ".config", "herdr-fold", "ssh_config")
    if command == "add" and len(args) in (4, 5, 6):           # LIST NAME TARGET OS [KEY [NETWORK]]: onto the list
        machines = read(args[0])
        if any(machine["name"] == args[1] for machine in machines):
            return 1
        key = args[4] if len(args) > 4 and KEY.fullmatch(args[4]) else key_of(args[2], known_hosts)
        route = target_route(args[2])
        network = args[5] if len(args) > 5 and args[5] in NETWORKS and args[5] != "through" else None
        route["network"] = network if network != guess_network(route["address"]) else None   # kept where untold
        write(args[0], machines + [{"name": args[1], "target": args[2], "os": args[3], "key": key, "routes": [route]}])
        return 0
    if command == "keys" and len(args) == 1:                  # LIST: "name|fingerprint" of each machine with one
        print("".join(f"{name}|{key}\n" for name, key in known_keys(read(args[0]), known_hosts).items()), end="")
        return 0
    if command == "identify" and len(args) >= 4:              # LIST KEYS NETWORK NAME [ADDRESS…]; keys() on stdin
        known = dict(line.split("|", 1) for line in sys.stdin.read().splitlines() if "|" in line)
        network = args[2] or guess_network(next((one for one in args[4:] if one), args[3]))
        kind, name = identify(read(args[0]), known, [one for one in args[1].split(",") if one], network, args[3],
                              args[4:])
        print(f"{kind}|{name}|{network or ''}")
        return 0
    if command == "name" and len(args) in (2, 3):             # LIST NAME [NETWORK]: the name a new machine gets
        print(unique_name(read(args[0]), args[1], args[2] if len(args) > 2 else None))
        return 0
    if command == "resolve" and len(args) == 1:               # TARGET: "host|port|user@host[:port]", none past a jump
        where = resolve(args[0])
        if where and reachable_at(*where[:3]):
            print(f"{where[1]}|{where[2] or ''}|{address_text(*where[:3])}")
        return 0
    if command == "route" and len(args) in (5, 6):            # LIST NAME KEY NETWORK ADDRESS [move]: the alias line
        machines = read(args[0])
        if not any(machine["name"] == args[1] for machine in machines) or not reachable_at(*parse_address(args[4])):
            return 1
        machines, alias = add_route(machines, args[1], args[2], args[3] or None, args[4], args[5:] == ["move"],
                                    known_hosts)
        write(args[0], machines)
        write_ssh_file(hosts, machines)
        print(alias or "")
        return 0
    if command == "behind" and len(args) == 6:                # LIST NAME OS KEY THROUGH ADDRESS: one behind THROUGH
        machines = add_behind(read(args[0]), *args[1:])
        if machines is None:
            return 1
        write(args[0], machines)
        write_ssh_file(hosts, machines)
        return 0
    if command == "behind-of" and len(args) == 2:             # LIST NAME: the machines going through it, a line each
        print("".join(name + "\n" for name in behind_of(read(args[0]), args[1])), end="")
        return 0
    if command == "keep" and len(args) in (2, 3):             # LIST NAME [check]: those behind it jump by its target
        machines = read(args[0])
        if not any(route.get("through") == args[1] for machine in machines for route in machine["routes"]):
            return 0                                          # none: the list as it was
        machines = keep_behind(machines, args[1])
        if machines is None:
            return 1
        if args[2:] != ["check"]:
            write(args[0], machines)
            write_ssh_file(hosts, machines)
        return 0
    if command == "jump" and len(args) == 2:                  # LIST NAME: the target a machine behind NAME jumps by
        machines = read(args[0])
        jump = jump_target(args[1], machines, "") if any(one["name"] == args[1] for one in machines) else None
        print(jump or "")
        return 0 if jump else 1
    if command == "address" and len(args) == 3:               # USER HOST PORT: user@host[:port], each part checked
        port = int(args[2]) if port_ok(args[2]) else None
        if not user_ok(args[0]) or args[2] and not port or not reachable_at(args[0], args[1], port):
            return 1
        print(address_text(args[0], args[1], port if port != 22 else None))
        return 0
    if command == "copy-key" and len(args) in (6, 7):         # NAME USER HOST PORT KEY PUBFILE [ALIAS]: the command
        port = int(args[3]) if port_ok(args[3]) else None
        found = copy_key_command(args[0], args[1], args[2], port if port != 22 else None, args[4],
                                 public_key(args[5]), args[6] if len(args) > 6 and args[6] else None)
        print(found or "")
        return 0 if found and (port or not args[3]) else 1
    if command == "moved" and len(args) == 1:                 # LIST: "name|address" of each one at its own Host
        print("".join(f"{name}|{address or ''}\n" for name, address in moved(read(args[0]))), end="")
        return 0
    if command == "unmove" and len(args) == 2:                # LIST NAME: its target its first route's address again
        machines = read(args[0])
        address = dict(moved(machines)).get(args[1])
        if not address:
            return 1
        write(args[0], [dict(machine, target=address) if machine["name"] == args[1] else machine
                        for machine in machines])
        return 0
    if command == "hosts" and len(args) == 1:                 # LIST: herdr-fold's ssh file written again from it
        write_ssh_file(hosts, read(args[0]))
        return 0
    if command in ("included", "include", "uninclude") and len(args) == 1:   # CONFIG: ~/.ssh/config
        if command == "include":
            include(args[0])
            return 0
        return 0 if (included if command == "included" else uninclude)(args[0]) else 1
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
