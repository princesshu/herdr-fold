"""What the networks say of their machines and of this Mac, and what a machine on the list sees, each read within a
time limit of its own and killed with all it started after it, everything checked; each machine's network, why one is
away. Run as networks.py netbird|local|said|status|machines|heading|through|here … (machines.sh's; here the app's)."""
import base64
import binascii
import calendar
import contextlib
import hashlib
import ipaddress
import json
import os
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time

from machines import (NAME, PREFIX, address_ok, address_text, clean, guess_network, host_ok, parse_address, port_ok,
                      reachable_at, read, target_route, user_ok)

NETBIRD_SECONDS = 5             # netbird status's own limit: with its daemon down, a dial alone can take 10 s
TAILSCALE_SECONDS = 5           # tailscale status's, and zerotier-cli's
ROUTE_SECONDS = 2               # route -n get's (a name resolved first: an absent .local one takes seconds), ifconfig's
LOGIN_SECONDS = 30              # a login's, past ssh's own ConnectTimeout: what it said by then
SCAN_SECONDS = 5                # the key a route shows (ssh-keyscan -T 3)
CLIENTS = ("tailscale", "netbird", "zerotier", "wireguard")       # this Mac's network clients, as clients() reads them
# Tailscale's BackendState; one it does not know is taken as on, the login then telling
BACKEND = {"Running": "on", "Starting": "on", "Stopped": "off", "NoState": "off", "NeedsLogin": "signed_out",
           "NeedsMachineAuth": "approval"}
# the networks known by a brand's name, never translated
NAMES = {"tailscale": "Tailscale", "netbird": "NetBird", "zerotier": "ZeroTier", "wireguard": "WireGuard",
         "cloudflare": "Cloudflare"}
PAGES = {"tailscale": "https://tailscale.com/download", "netbird": "https://docs.netbird.io/how-to/installation",
         "zerotier": "https://www.zerotier.com/download/"}        # where each client is got
CONSOLE = "https://login.tailscale.com/admin/machines"
# where machines.sh finds this Mac's clients (lib/common.sh's tailscale_bin and netbird_bin; zerotier-cli on PATH): the
# name on PATH, else the first of its places that runs; the WireGuard app by its folder
PLACES = {"tailscale": ("tailscale", "/Applications/Tailscale.app/Contents/MacOS/Tailscale"),
          "netbird": ("netbird", "/usr/local/bin/netbird", "/opt/homebrew/bin/netbird",
                      "/Applications/NetBird.app/Contents/MacOS/netbird"),
          "zerotier": ("zerotier-cli",)}
WIREGUARD = "/Applications/WireGuard.app"
SHOWN = 64                      # the app's own machines one look of the app's reads at most
SHARED = ipaddress.ip_network((0x64400000, 10))                   # 100.64/10: Tailscale's and NetBird's addresses alike
# a home or office network's: RFC 1918's 10/8, 172.16/12 and 192.168/16, the link-local ones, IPv6's unique local
LAN = tuple(ipaddress.ip_network(one) for one in ((0x0A000000, 8), (0xAC100000, 12), (0xC0A80000, 16),
                                                  (0xA9FE0000, 16), "fc00::/7", "fe80::/10"))
TUNNELS = ("utun", "ipsec", "ppp")                                # a tunnel's interface on macOS (whose: its address)
DEVICE = re.compile(r"[a-z]{1,12}[0-9]{1,5}")                     # an interface's name (en0, utun4, feth2001)
RELAY = re.compile(r"[a-z0-9-]{1,32}")                            # a DERP region's code (fra)
NOT_THROUGH = ("administratively prohibited", "stdio forwarding failed")      # a jump host that lets nothing through
NO_ANSWER = ("timed out", "No route to host", "Network is unreachable", "Host is down")      # ssh's words for silence
PEERS = 256                     # the most machines a network's list offers
NOT_FOUND = 127                 # a command that cannot start, as a shell's exit status says it: it tells nothing
# NetBird's daemon states that end the reading (its JSON from v0.70 on, its text before)
DAEMON = {"NeedsLogin": "signed_out", "LoginFailed": "signed_out", "SessionExpired": "expired", "Idle": "off"}
PATHS = {"P2P": "direct", "Relayed": "relayed"}                 # a connected peer's connectionType ("-" for none)
STATUSES = ("Connected", "Connecting", "Idle")                  # Idle is also a lazy connection that is up
BROWSE_SECONDS = 3              # dns-sd -B never ends by itself: what it lists in this time
LOOKUP_SECONDS = 2              # each instance's dns-sd -L, all at once (none ends by itself either)
INSTANCES = 32                  # the most instances of the local network looked up
HEARD = 1 << 16                 # the most bytes read of one command that is listened to
SSH_SERVICE = ("_ssh._tcp", "local.")
STAMP = r"\s*\d{1,2}:\d\d:\d\d\.\d{3}\s+"                         # the time dns-sd puts before each of its lines
# dns-sd -B: Add or Rmv, the flags, the interface, the domain and the service, then the instance as it is announced
BROWSED = re.compile(STAMP + r"(Add|Rmv)\s+[0-9A-Fa-f]+\s+\d+\s+local\.\s+_ssh\._tcp\.\s+(.+)")
# dns-sd -L: the instance's full name (escaped: no space), then the host and port it is reached at
REACHED = re.compile(STAMP + r"\S+ can be reached at (\S+):(\d+) \(interface \d+\)")
# what a prepared machine sees (./machines.sh through): remote/look-around.py, sent over the machine's own ssh as
# python3's input, read up to LOOK_BYTES within LOOK_SECONDS (ssh's 10 s to connect, the machine's 5 s, room to spare)
LOOK = ("remote", "look-around.py")                               # beside core/ in the package (look_script())
LOOK_COMMAND = 'export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"; exec python3 -'
LOOK_SECONDS = 40
LOOK_BYTES = 1 << 20
CANDIDATES = 200                # the most machines offered of what one machine sees
SIGHTS = ("ssh_config", "local", "tailscale", "netbird")       # what it sees, in the order its machines are offered
SYSTEMS = {"linux": "linux", "macOS": "macos", "windows": "windows"}      # Tailscale's OS of a computer


def stopped(child):
    """CHILD killed with all it started (its own session), its pipe let go: a child of its own may still hold it."""
    with contextlib.suppress(OSError):
        os.killpg(child.pid, signal.SIGKILL)
    child.stdout.close()
    child.wait()


def bounded(argv, seconds):
    """ARGV's (exit status, output) when it ends within SECONDS, (NOT_FOUND, "") when it cannot start; None when it runs
    longer, then killed with all it started (its own session)."""
    try:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
    except OSError:
        return NOT_FOUND, ""
    try:
        out, _ = child.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        stopped(child)
        return None
    return child.returncode, out.decode("utf-8", "replace")


def ip_of(text):
    """An address NetBird gives (this Mac's with its /16), checked; None for anything else."""
    address = text.split("/")[0] if isinstance(text, str) else None
    return address if address_ok(address) else None


def peer(entry):
    """A NetBird peer as offered, its name its FQDN's first label; None for one whose FQDN is no host name."""
    fqdn = entry.get("fqdn") if isinstance(entry, dict) else None
    fqdn = fqdn.rstrip(".") if isinstance(fqdn, str) else ""
    if not host_ok(fqdn):
        return None
    status, kind, latency = entry.get("status"), entry.get("connectionType"), entry.get("latency")
    status = status if isinstance(status, str) and status in STATUSES else None
    return {"name": fqdn.split(".")[0], "fqdn": fqdn, "ip": ip_of(entry.get("netbirdIp")),
            "status": status.lower() if status else None,
            "path": PATHS.get(kind) if status == "Connected" and isinstance(kind, str) else None,
            "latency_ms": round(latency / 1e6) if type(latency) is int and latency > 0 else None}


def netbird_peers(run=bounded, binary="netbird"):
    """NetBird's state and machines from `netbird status --json`, RUN (bounded's shape) within NETBIRD_SECONDS: on, off
    (no answer, or disconnected), signed_out, expired, no_management (its peers the last it was told); this Mac's own
    address and its names' domain; the peers by FQDN, each once, at most PEERS."""
    found = {"state": "off", "self_ip": None, "suffix": None, "peers": []}
    done = run([binary, "status", "--json"], NETBIRD_SECONDS)
    if not done or done[0] != 0:
        return found
    try:
        status = json.loads(done[1])
    except ValueError:
        told = re.search(r"Daemon status: (\w+)", done[1])        # before v0.70: a text, even with --json
        found["state"] = DAEMON.get(told.group(1), "off") if told else "off"
        return found
    if not isinstance(status, dict):
        return found
    daemon = status.get("daemonStatus")
    if isinstance(daemon, str) and daemon in DAEMON:
        found["state"] = DAEMON[daemon]
        return found
    management = status.get("management")
    found["state"] = "on" if isinstance(management, dict) and management.get("connected") is True else "no_management"
    found["self_ip"] = ip_of(status.get("netbirdIp"))
    own = status.get("fqdn").rstrip(".").lower() if isinstance(status.get("fqdn"), str) else ""
    found["suffix"] = own.partition(".")[2] if host_ok(own) and "." in own else None
    details =status.get("peers").get("details") if isinstance(status.get("peers"), dict) else None
    peers = {}
    for one in map(peer, details if isinstance(details, list) else []):
        if one and one["fqdn"] not in peers:
            peers[one["fqdn"]] = one
    found["peers"] = sorted(peers.values(), key=lambda one: one["fqdn"])[:PEERS]
    return found


def listened(argvs, seconds, enough=None):
    """What each of ARGVS prints, all started at once, until SECONDS pass, ENOUGH(what it printed) is true or HEARD
    bytes came, then killed with all it started; None for one that cannot start."""
    children, said = [], []
    for argv in argvs:
        try:
            children.append(subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                             stderr=subprocess.DEVNULL, start_new_session=True))
        except OSError:
            children.append(None)
        said.append(b"")
    deadline = time.monotonic() + seconds
    with selectors.DefaultSelector() as listening:
        for n, child in enumerate(children):
            if child:
                listening.register(child.stdout, selectors.EVENT_READ, n)
        while listening.get_map() and time.monotonic() < deadline:
            for key, _ in listening.select(max(0, deadline - time.monotonic())):
                chunk = os.read(key.fd, 4096)
                said[key.data] += chunk
                if not chunk or len(said[key.data]) >= HEARD or enough and enough(
                        said[key.data].decode("utf-8", "replace")):
                    listening.unregister(key.fileobj)
    for child in children:
        if child:
            stopped(child)
    return [heard[:HEARD].decode("utf-8", "replace") if child else None for child, heard in zip(children, said)]


def this_mac(run=bounded):
    """This Mac's own name on the local network (its LocalHostName), in lower case; None where it has none."""
    done = run(["scutil", "--get", "LocalHostName"], 2)
    name = done[1].strip().lower() if done and done[0] == 0 else ""
    return name if host_ok(name) else None


def browsed(text):
    """The instances a dns-sd -B listing still has at its end (each added, and not removed since), each once."""
    found = {}
    for line in text.splitlines():
        heard = BROWSED.fullmatch(line)
        if heard and heard.group(1) == "Add":
            found.setdefault(heard.group(2), None)
        elif heard:
            found.pop(heard.group(2), None)
    return list(found)


def reached(text):
    """(host, port) of a dns-sd -L answer's first line that names a .local host and a port, else None."""
    for line in (text or "").splitlines():
        answer = REACHED.match(line)
        host = answer.group(1).rstrip(".").lower() if answer else ""
        if host_ok(host) and host.endswith(".local") and port_ok(answer.group(2)):
            return host, int(answer.group(2))
    return None


def bonjour_ssh(listen=listened, seconds=None, binary="dns-sd", own=None):
    """The machines announcing SSH on this local network: dns-sd -B heard for SECONDS (BROWSE_SECONDS), then each
    instance (at most INSTANCES, by name) looked up at once for LOOKUP_SECONDS; by host, its .local name, never an
    address, this Mac (OWN, else its LocalHostName) left out. The instance's name, cleaned, is for showing alone."""
    own = this_mac() if own is None else own
    browse = listen([[binary, "-B", *SSH_SERVICE]], BROWSE_SECONDS if seconds is None else seconds)[0]
    instances = [one for one in sorted(browsed(browse or ""), key=str.casefold)
                 if len(one.encode("utf-8")) <= 63][:INSTANCES]          # an instance is one DNS label
    answers = listen([[binary, "-L", one, *SSH_SERVICE] for one in instances], LOOKUP_SECONDS,
                     lambda text: reached(text) is not None) if instances else []
    found, mine = {}, f"{own}.local" if own else None
    for instance, answer in zip(instances, answers):
        where = reached(answer)
        if where and where[0] != mine and where[0] not in found:
            found[where[0]] = {"instance": clean(instance, 63), "host": where[0], "port": where[1]}
    return sorted(found.values(), key=lambda one: one["host"])


def answered(argv, seconds):
    """(ARGV's exit status, all it said, its errors too) once it ends; (None, what it said by then) when it runs over
    SECONDS, then killed with all it started; (None, "") when it cannot start."""
    try:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 start_new_session=True)
    except OSError:
        return None, ""
    try:
        out, _ = child.communicate(timeout=seconds)
    except subprocess.TimeoutExpired as late:
        stopped(child)
        return None, (late.output or b"").decode("utf-8", "replace")
    return child.returncode, out.decode("utf-8", "replace")


def when(text):
    """Seconds since 1970 of an RFC 3339 time (Tailscale's LastSeen, KeyExpiry); None for none or the zero time."""
    found = re.fullmatch(r"(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.\d{1,9})?(Z|[+-]\d\d:\d\d)",
                         text) if isinstance(text, str) else None
    if not found or int(found.group(1)) < 2000:
        return None
    try:
        seconds = calendar.timegm(tuple(int(one) for one in found.groups()[:6]))
    except ValueError:
        return None
    zone = found.group(7)
    return seconds if zone == "Z" else seconds - int(zone[0] + "1") * (int(zone[1:3]) * 3600 + int(zone[4:]) * 60)


def addresses(value, most=8):
    """The addresses of a list a network gives, each checked, at most MOST."""
    return [one for one in value if isinstance(one, str) and address_ok(one)][:most] if isinstance(value, list) else []


def computer(entry, dns):
    """Whether a Tailscale peer (ENTRY, its name DNS) is a computer of your own, as machines.sh's import offers one:
    Linux, macOS or Windows, no Mullvad exit node, no node of someone a machine is shared with, its key not expired."""
    return (entry.get("OS") in SYSTEMS and not entry.get("Location") and dns.split(".")[-3:] != ["mullvad", "ts", "net"]
            and not entry.get("ShareeNode") and entry.get("Expired") is not True)


def tailnet_peer(entry):
    """A Tailscale peer as the ladder and the figures read it, never its endpoint: its names and addresses, online or
    seen when, its key expired, the path to it, whether its import offers it; None for one whose name is no host
    name."""
    dns = entry.get("DNSName") if isinstance(entry, dict) else None
    dns = dns.rstrip(".").lower() if isinstance(dns, str) else ""
    if not host_ok(dns):
        return None
    relay = entry.get("Relay")
    return {"name": dns.split(".")[0], "dns": dns, "ips": addresses(entry.get("TailscaleIPs")),
            "online": entry.get("Online") is True, "seen": when(entry.get("LastSeen")),
            "expired": entry.get("Expired") is True, "active": entry.get("Active") is True,
            "direct": isinstance(entry.get("CurAddr"), str) and entry["CurAddr"] != "",
            "relay": relay if isinstance(relay, str) and RELAY.fullmatch(relay) else None,
            "peer_relay": isinstance(entry.get("PeerRelay"), str) and entry["PeerRelay"] != "",
            "offer": computer(entry, dns)}


def tailscale_status(run=bounded, binary="tailscale", now=None):
    """Tailscale on this Mac from `tailscale status --json` within TAILSCALE_SECONDS: on, off (stopped, or silent),
    signed_out, expired (this Mac's key), approval (waiting in the admin console); this Mac's addresses, the MagicDNS
    suffix, the peers by name (at most PEERS)."""
    found = {"installed": True, "state": "off", "self_ips": [], "suffix": None, "peers": []}
    done = run([binary, "status", "--json"], TAILSCALE_SECONDS)
    try:
        status = json.loads(done[1]) if done and done[0] == 0 else None
    except ValueError:
        status = None
    if not isinstance(status, dict):
        return found
    me = status.get("Self") if isinstance(status.get("Self"), dict) else {}
    backend, expiry = status.get("BackendState"), when(me.get("KeyExpiry"))
    found["state"] = BACKEND.get(backend, "on") if isinstance(backend, str) else "on"
    if found["state"] != "off" and (me.get("Expired") is True
                                    or expiry and expiry < (time.time() if now is None else now)):
        found["state"] = "expired"
    found["self_ips"] = addresses(me.get("TailscaleIPs"))
    tailnet = status.get("CurrentTailnet") if isinstance(status.get("CurrentTailnet"), dict) else {}
    own = me.get("DNSName") if isinstance(me.get("DNSName"), str) else ""          # its domain, while not connected
    suffix = tailnet.get("MagicDNSSuffix") or status.get("MagicDNSSuffix") or own.rstrip(".").partition(".")[2]
    suffix = suffix.rstrip(".").lower() if isinstance(suffix, str) else ""
    found["suffix"] = suffix if host_ok(suffix) else None
    peers = {}
    for one in map(tailnet_peer, status["Peer"].values() if isinstance(status.get("Peer"), dict) else []):
        if one and one["dns"] not in peers:
            peers[one["dns"]] = one
    found["peers"] = sorted(peers.values(), key=lambda one: one["dns"])[:PEERS]
    return found


def zerotier_networks(run=bounded, binary="zerotier-cli"):
    """ZeroTier on this Mac from `zerotier-cli -j listnetworks` within TAILSCALE_SECONDS: on, or off (the service not
    answering); its networks' ranges with this Mac's addresses there, their interfaces (feth on macOS)."""
    found = {"installed": True, "state": "off", "self_ips": [], "suffix": None, "peers": [], "ranges": [],
             "devices": []}
    done = run([binary, "-j", "listnetworks"], TAILSCALE_SECONDS)
    try:
        joined = json.loads(done[1]) if done and done[0] == 0 else None
    except ValueError:
        joined = None
    if not isinstance(joined, list):
        return found
    found["state"] = "on"
    for one in (one for one in joined[:32] if isinstance(one, dict)):
        given = one.get("assignedAddresses")
        for text in given[:16] if isinstance(given, list) else []:
            with contextlib.suppress(TypeError, ValueError):
                where = ipaddress.ip_interface(text)
                found["self_ips"].append(str(where.ip))
                found["ranges"].append(where.network)
        device = one.get("portDeviceName")
        if isinstance(device, str) and DEVICE.fullmatch(device):
            found["devices"].append(device)
    return found


def read_client(kind, run=bounded, binary=None, now=None):
    """Network client KIND of this Mac (BINARY its command line, the WireGuard app's folder; None: not installed): its
    state, its own addresses and names' domain, the machines it lists (peers)."""
    found = {"installed": bool(binary), "state": None, "self_ips": [], "suffix": None, "peers": []}
    if binary and kind == "tailscale":
        return tailscale_status(run, binary, now)
    if binary and kind == "zerotier":
        return zerotier_networks(run, binary)
    if binary and kind == "netbird":
        said = netbird_peers(run, binary)
        found.update(state=said["state"], self_ips=[said["self_ip"]] if said["self_ip"] else [], suffix=said["suffix"],
                     peers=[dict(one, dns=one["fqdn"], ips=[one["ip"]] if one["ip"] else []) for one in said["peers"]])
    return found


def clients(run=bounded, binaries=None, now=None):
    """This Mac's network clients, CLIENTS, each read_client()'s (BINARIES: {kind: its command line or app})."""
    return {kind: read_client(kind, run, (binaries or {}).get(kind), now) for kind in CLIENTS}


def here(places=PLACES, wireguard=WIREGUARD):
    """This Mac's clients as machines.sh finds them (PLACES), for the app: {kind: its command line, the WireGuard app's
    folder, or None}."""
    runs = lambda path: os.path.isfile(path) and os.access(path, os.X_OK)             # noqa: E731
    found = {kind: shutil.which(name) or next(filter(runs, fixed), None) for kind, (name, *fixed) in places.items()}
    return dict(found, wireguard=wireguard if os.path.isdir(wireguard) else None)


def app_machine(name, target):
    """A machine of the app's own list (its NAME and TARGET) as a list's line of one route reads; None for a name or a
    target that is none (a command, an option, a space)."""
    user, host, port = parse_address(target) if isinstance(target, str) else (None, "", None)
    if not (isinstance(name, str) and NAME.fullmatch(name)) or not reachable_at(user, host, port):
        return None
    return {"name": name, "target": target, "os": "", "key": None, "routes": [target_route(target)]}


def offered(kind, client, listed):
    """The names of the machines network KIND's CLIENT lists, while it is on, that its import offers (Tailscale's
    computers, NetBird's all) and no route of the LISTED machines reaches: what Spaces says there is to add."""
    if kind not in ("tailscale", "netbird") or (client or {}).get("state") != "on":
        return []
    taken = {one["dns"] for machine in listed for route in machine["routes"] if not route.get("through")
             for one in [peer_of(client, route["address"])] if one}
    return [one["name"] for one in client["peers"] if one.get("offer", True) and one["dns"] not in taken]


def peer_of(client, host):
    """The machine CLIENT lists at HOST, by its name, its short name or an address; None where it lists none."""
    host = str(host).lower().rstrip(".")
    return next((one for one in (client or {}).get("peers") or []
                 if host in (one["dns"], one["name"]) or host in one["ips"]), None)


def in_domain(kind, client, host):
    """Whether HOST is a name in network KIND's own domain: its CLIENT's, else the one a name alone tells."""
    suffix = (client or {}).get("suffix")
    return bool(suffix and host.endswith("." + suffix)) or guess_network(host) == kind


def in_ranges(client, host):
    """Whether HOST is an address in one of CLIENT's ranges (ZeroTier's networks)."""
    return address_ok(host) and any(ipaddress.ip_address(host) in one for one in (client or {}).get("ranges") or [])


def lan_or_public(ip):
    """local for an address of a home or office network, public for one on the internet; None for any other (100.64/10,
    a loopback, a multicast one)."""
    address = ipaddress.ip_address(ip)
    if any(address in one for one in LAN):
        return "local"
    odd = address.is_loopback or address.is_multicast or address.is_unspecified or address.is_reserved
    return None if odd or address in SHARED else "public"


def route_of(done):
    """(the address, the interface) of route -n get's answer DONE (bounded()'s); None for none, or one of no shape."""
    text = done[1] if done and done[0] == 0 else ""
    to, via = (re.search(rf"^\s*{word}: (\S+)\s*$", text, re.M) for word in ("route to", "interface"))
    if not to or not via or not address_ok(to.group(1)) or not DEVICE.fullmatch(via.group(1)):
        return None
    return to.group(1), via.group(1)


def route_to(host, run=bounded):
    """(the address, the interface) route -n get gives HOST, a name resolved first, within ROUTE_SECONDS; None for
    none."""
    return route_of(run(["route", "-n", "get", host], ROUTE_SECONDS))


def interface_addresses(device, run=bounded):
    """The addresses ifconfig gives DEVICE (a tunnel's): whose tunnel it is."""
    done = run(["ifconfig", device], ROUTE_SECONDS)
    found = re.findall(r"^\s*inet6? ([0-9A-Fa-f.:]+)", done[1] if done and done[0] == 0 else "", re.M)
    return {one for one in found if address_ok(one)}


def network_of(address, clients, run=bounded):
    """The network a route's ADDRESS goes through: a client's list first (100.64/10 alone tells nothing: both take it),
    then a name's own domain, then where route -n get leads it (a tunnel by its own address, a home network's or a
    public address by itself); None where nothing tells."""
    host = str(address).lower().rstrip(".")
    for kind in ("tailscale", "netbird"):
        if peer_of(clients.get(kind), host):
            return kind
    if in_ranges(clients.get("zerotier"), host):
        return "zerotier"
    for kind in ("tailscale", "netbird"):
        suffix = (clients.get(kind) or {}).get("suffix")
        if suffix and host.endswith("." + suffix):
            return kind
    if guess_network(host) or not (host_ok(host) or address_ok(host)):
        return guess_network(host)
    where = route_to(host, run)
    if not where:
        return None
    ip, device = where
    zerotier = clients.get("zerotier") or {}
    for kind in ("tailscale", "netbird"):
        if peer_of(clients.get(kind), ip):
            return kind
    if in_ranges(zerotier, ip) or device.startswith("feth") or device in zerotier.get("devices", []):
        return "zerotier"
    if device.startswith(TUNNELS):
        mine = interface_addresses(device, run)
        for kind in ("tailscale", "netbird"):
            if mine & set((clients.get(kind) or {}).get("self_ips") or []):
                return kind
        return "wireguard" if (clients.get("wireguard") or {}).get("installed") else "tunnel"
    return lan_or_public(ip) if device.startswith(("en", "bridge")) else None


def ssh_options(target, run=bounded):
    """What ssh's own config makes of TARGET (ssh -G connects nowhere): {option: its first value}."""
    done = run(["ssh", "-G", "--", target], SCAN_SECONDS)
    found = {}
    for line in (done[1] if done and done[0] == 0 else "").splitlines():
        key, _, value = line.partition(" ")
        found.setdefault(key.lower(), value.strip())
    return found


def route_network(machine, route, clients, run=bounded):
    """(network, the machine it goes through) of MACHINE's ROUTE: through another one, the network kept on the list,
    else as its address tells it; an older line's one route where ssh's own config leads its target (its own jump host,
    or cloudflared: Cloudflare)."""
    if route.get("through"):
        return "through", route["through"]
    if route.get("network"):
        return route["network"], None
    host = route["address"]
    if machine["routes"] == [target_route(machine["target"])]:
        found = ssh_options(machine["target"], run)
        if "cloudflared" in found.get("proxycommand", ""):
            return "cloudflare", None
        if found.get("proxyjump", "none") != "none":
            return "through", clean(parse_address(found["proxyjump"].split(",")[0])[1], 64)
        host = found.get("hostname") or host
    return network_of(host, clients, run), None


def key_fingerprint(line):
    """The SHA256 fingerprint of the ED25519 key on LINE ("host ssh-ed25519 AAAA…", ssh-keyscan's), as ssh-keygen -l
    prints it; None for a line with none."""
    parts = line.split()
    if len(parts) < 3 or parts[1] != "ssh-ed25519" or line.startswith("#"):
        return None
    try:
        blob = base64.b64decode(parts[2], validate=True)
    except (binascii.Error, ValueError):
        return None
    return ("SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
            if blob.startswith(b"\0\0\0\x0bssh-ed25519") else None)


class Probe:
    """What reaches out from this Mac, each once: a machine's login (ssh with OPTIONS, timed; none without OPTIONS),
    the key a route shows, whether a name answers, a route's network; MACHINES the list, HEARD(name) told of a login
    before it starts."""

    def __init__(self, machines=(), options=None, run=bounded, talk=answered, now=None, heard=None):
        self.machines, self.options, self.run, self.talk, self.heard = list(machines), options, run, talk, heard
        self.now = int(time.time()) if now is None else now
        self.logins, self.keys, self.resolved, self.networks = {}, {}, {}, {}

    def machine(self, name):
        """The listed machine called NAME, or at that target or host (a jump host as ssh names it); None."""
        return next((one for one in self.machines
                     if name in (one["name"], one["target"], parse_address(one["target"])[1])), None)

    def login(self, machine):
        """MACHINE's login: {"ok", "said": all ssh said, "ms": how long it took}; None without OPTIONS."""
        if self.options is None:
            return None
        if machine["name"] not in self.logins:
            if self.heard:
                self.heard(machine["name"])
            start = time.monotonic()
            code, text = self.talk(["ssh", *self.options, "--", machine["target"], "exit"], LOGIN_SECONDS)
            self.logins[machine["name"]] = {"ok": code == 0, "said": text,
                                            "ms": round((time.monotonic() - start) * 1000) if code == 0 else None}
        return self.logins[machine["name"]]

    def measured(self, machine):
        """MACHINE's login where one was made, never a new one."""
        return self.logins.get(machine["name"])

    def key(self, route):
        """The fingerprint of the ED25519 key ROUTE shows now (ssh-keyscan); None for none, or one through another."""
        host, port = route["address"], route.get("port")
        if route.get("through") or not (host_ok(host) or address_ok(host)) or not port_ok(port or 22):
            return None
        if (host, port) not in self.keys:
            done = self.run(["ssh-keyscan", "-T", "3", "-t", "ed25519", *(["-p", str(port)] if port else []), "--",
                             host], SCAN_SECONDS)
            lines = (done[1] if done and done[0] == 0 else "").splitlines()[:8]
            self.keys[(host, port)] = next(filter(None, map(key_fingerprint, lines)), None)
        return self.keys[(host, port)]

    def resolves(self, host):
        """Whether HOST, a name, answers now (route -n get resolves it); without route here, nothing tells: it does."""
        if host not in self.resolved:
            done = self.run(["route", "-n", "get", host], ROUTE_SECONDS)
            self.resolved[host] = bool(done and done[0] == NOT_FOUND) or route_of(done) is not None
        return self.resolved[host]

    def network(self, machine, route, clients):
        """ROUTE's (network, the machine it goes through): route_network()'s."""
        where = (machine["name"], route["address"], route.get("port"), route.get("through"))
        if where not in self.networks:
            self.networks[where] = route_network(machine, route, clients, self.run)
        return self.networks[where]


def arg(value):
    """VALUE as a sentence's argument: no control character and no bar (machines.sh's field mark), cut."""
    return clean(value, 300).replace("|", "/")


def why(key, *args, action=None, then=None):
    """A sentence of the ladder: its catalog key (src/lang/en.txt's machines.why_*) with its arguments, what to do about
    it (todo()), or what caused it, a jump host's own sentence (THEN)."""
    return {"key": key, "args": [arg(one) for one in args], "action": action, "then": then}


def todo(key, *args, command=None):
    """What to do about a sentence: its catalog key and arguments, the COMMAND to run last (its key's last %s)."""
    return {"key": key, "args": [arg(one) for one in args], "command": None if command is None else arg(command)}


def ago(seconds):
    """How long SECONDS are, as a sentence says it: 5 min, 3 h, 2 d."""
    minutes = max(1, int(seconds // 60))
    return f"{minutes} min" if minutes < 60 else f"{minutes // 60} h" if minutes < 48 * 60 else f"{minutes // 1440} d"


def console(client):
    """What to do in a tailnet's admin console: Tailscale's link where the tailnet is Tailscale's own (its CLIENT's
    suffix a .ts.net one); for Headscale or another control server, ask its admin."""
    if ((client or {}).get("suffix") or "").endswith(".ts.net"):
        return todo("machines.why_do_console", command=CONSOLE)
    return todo("machines.why_do_control_admin")


def client_rung(kind, clients):
    """The rungs of network KIND's own client on this Mac: missing, off, signed out or expired, out of reach."""
    client = clients.get(kind) or {}
    if kind not in ("tailscale", "netbird", "zerotier"):
        return None
    if not client.get("installed"):
        return why("machines.why_missing", NAMES[kind], action=todo("machines.why_do_get", command=PAGES[kind]))
    state = (kind, client.get("state"))
    if state == ("tailscale", "off"):
        return why("machines.why_tailscale_off", action=todo("machines.why_do_turn_on", command="tailscale up"))
    if state == ("netbird", "off"):
        return why("machines.why_netbird_off", action=todo("machines.why_do_start", command="netbird up"))
    if state == ("zerotier", "off"):
        return why("machines.why_zerotier_off")
    if state == ("tailscale", "signed_out"):
        return why("machines.why_tailscale_signed_out",
                   action=todo("machines.why_do_sign_in", command="tailscale login"))
    if state == ("tailscale", "expired"):
        return why("machines.why_tailscale_expired",
                   action=todo("machines.why_do_sign_in_again", command="tailscale login"))
    if state == ("tailscale", "approval"):
        return why("machines.why_tailscale_approval", action=console(client))
    if state == ("netbird", "signed_out"):
        return why("machines.why_netbird_signed_out", action=todo("machines.why_do_sign_in", command="netbird up"))
    if state == ("netbird", "expired"):
        return why("machines.why_netbird_expired", action=todo("machines.why_do_sign_in_again", command="netbird up"))
    if state == ("netbird", "no_management"):
        return why("machines.why_netbird_management")
    return None


def peer_rung(name, kind, route, clients, now):
    """The rungs of machine NAME as network KIND lists it: its key expired, offline (seen when), not in this Mac's
    network at all (a name in its domain, an address in its range: a subnet's machine is in no list)."""
    if kind not in ("tailscale", "netbird"):
        return None
    client, host = clients.get(kind) or {}, route["address"].lower().rstrip(".")
    peer = peer_of(client, host)
    if peer is None:
        listable = in_domain(kind, client, host) or address_ok(host) and ipaddress.ip_address(host) in SHARED
        return why("machines.why_not_in", name, NAMES[kind]) if listable else None
    if peer.get("expired"):
        return why("machines.why_peer_expired", name, NAMES[kind], action=console(client))
    if kind == "tailscale" and not peer["online"]:
        if peer["seen"]:
            return why("machines.why_offline", name, NAMES[kind], ago(now - peer["seen"]))
        return why("machines.why_offline_unseen", name, NAMES[kind])
    return None


def here_rung(name, kind, route, probe):
    """Machine NAME's .local name giving no answer: not on the local network this Mac is on now."""
    host = route["address"].lower().rstrip(".")
    return why("machines.why_not_here", name) if kind == "local" and host.endswith(".local") \
        and not probe.resolves(host) else None


def said(name, target, text, route=None):
    """What ssh's own words (TEXT, of a failed login to TARGET) say of machine NAME: the ladder's sentence, reachable's
    in machines.sh too; ROUTE, of a machine at its own Host: another key there is that route's, never used."""
    text = text or ""
    if "Tailscale SSH requires an additional check" in text:
        return why("machines.why_tailscale_check", name, action=todo("machines.why_do_once", command=f"ssh {target}"))
    if "Could not resolve hostname" in text:
        return why("machines.why_unknown_name", name)
    if "Connection refused" in text:
        return why("machines.why_no_ssh", name, action=todo("machines.why_do_ssh_on"))
    if any(word in text for word in NO_ANSWER):
        return why("machines.why_no_answer", name)
    if "Permission denied" in text:
        return why("machines.why_login", name, action=todo("machines.why_do_login", command=f"ssh {target}"))
    if "Host key verification failed" in text and route:
        return why("machines.why_route_key", route["address"], name)
    if "Host key verification failed" in text:
        return why("machines.why_host_key", name, action=todo("machines.why_do_host_key",
                                                              command=f"ssh-keygen -R {parse_address(target)[1]}"))
    return why("machines.why_other", name, next((line.strip() for line in reversed(text.splitlines())
                                                 if line.strip()), ""))


def said_through(name, jump, text):
    """What ssh's own words (TEXT) say of machine NAME, reached through JUMP before it is on the list: JUMP lets nothing
    through, NAME does not take this Mac's key (it may take JUMP's own alone), else said()'s, by its own Host's name."""
    text = text or ""
    if any(word in text for word in NOT_THROUGH):
        return why("machines.why_no_forwarding", jump)
    if "Permission denied" in text:
        return why("machines.key_refused_through", name, jump)
    return said(name, PREFIX + name, text)


def through_rung(machine, through, text, clients, probe, seen):
    """The rungs of the jump host of MACHINE, reached THROUGH it: it lets no connection through, or it is away
    itself (its own sentence after it)."""
    if not through:
        return None
    if any(word in text for word in NOT_THROUGH):
        return why("machines.why_no_forwarding", through)
    jump, seen = probe.machine(through), seen | {machine["name"]}
    cause = ladder(jump, clients, probe, seen) if jump and jump["name"] not in seen else None
    return why("machines.why_through", machine["name"], through, then=cause) if cause else None


def other_route(machine, clients, probe):
    """Another route of MACHINE that shows its own key now (On Tailscale it answers.); None for none."""
    for route in machine["routes"][1:] if machine.get("key") else []:
        if probe.key(route) == machine["key"]:
            kind = probe.network(machine, route, clients)[0]
            if kind in NAMES:
                return todo("machines.why_do_route_on", NAMES[kind])
            if kind == "local":
                return todo("machines.why_do_route_local")
            return todo("machines.why_do_route_at", address_text(None, route["address"], route.get("port")))
    return None


def ladder(machine, clients, probe, seen=frozenset()):
    """Why MACHINE is away, the first check that fails: its network's client here, the machine there, this local
    network, then its login in ssh's own words or its jump host's; another route that answers where nothing else is
    to do. None when it logs in, or PROBE makes no login (CLIENTS: clients()'s; SEEN: the machines in front of it)."""
    route, name = machine["routes"][0], machine["name"]
    kind, through = probe.network(machine, route, clients)
    found = (client_rung(kind, clients) or peer_rung(name, kind, route, clients, probe.now)
             or here_rung(name, kind, route, probe))
    if not found:
        login = probe.login(machine)
        if not login or login["ok"]:
            return None
        own = route if machine["target"] == PREFIX + name else None
        found = (through_rung(machine, through, login["said"], clients, probe, seen)
                 or said(name, machine["target"], login["said"], own))
    if not found["action"] and not found["then"]:
        found["action"] = other_route(machine, clients, probe)
    return found


def figures(machine, clients, probe):
    """What MACHINE's route in use shows: direct or relayed by its network's own word (Tailscale's CurAddr, its DERP
    region or a peer relay; NetBird's connection type), the login PROBE made, timed (else NetBird's latency), and when
    it was seen (that login, else Tailscale's LastSeen)."""
    route = machine["routes"][0]
    kind = probe.network(machine, route, clients)[0]
    peer = peer_of(clients.get(kind), route["address"]) if kind in ("tailscale", "netbird") else None
    path = relay = None
    if peer and kind == "tailscale" and peer["direct"]:
        path = "direct"
    elif peer and kind == "tailscale" and (peer["peer_relay"] or peer["active"] and peer["relay"]):
        path, relay = "relayed", None if peer["peer_relay"] else peer["relay"]
    elif peer and kind == "netbird":
        path = peer["path"]
    login = probe.measured(machine)
    done = bool(login and login["ok"])
    return {"path": path, "relay": relay, "login_ms": login["ms"] if done else (peer or {}).get("latency_ms"),
            "seen": probe.now if done else (peer or {}).get("seen")}


def look_script():
    """remote/look-around.py's path, beside core/ (read when a machine looks around: the app's copy has no file)."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, *LOOK)


def looked(argv, seconds, given, most=LOOK_BYTES):
    """(exit status, what ARGV printed, its errors) with the file GIVEN as its input, read until it ends, SECONDS pass
    or it prints over MOST bytes, then killed with all it started (its own session); its output None when it ran too
    long or printed too much. (None, None, "") when it cannot start."""
    try:
        with open(given, "rb") as source:
            child = subprocess.Popen(argv, stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     start_new_session=True)
    except OSError:
        return None, None, ""
    said, deadline, over = {"out": b"", "err": b""}, time.monotonic() + seconds, False
    with selectors.DefaultSelector() as listening:
        listening.register(child.stdout, selectors.EVENT_READ, "out")
        listening.register(child.stderr, selectors.EVENT_READ, "err")
        while listening.get_map() and not over:
            left = deadline - time.monotonic()
            over = left <= 0
            for key, _ in [] if over else listening.select(left):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    listening.unregister(key.fileobj)
                said[key.data] = (said[key.data] + chunk)[:most + 1 if key.data == "out" else HEARD]
                over = over or len(said["out"]) > most
    if over:
        with contextlib.suppress(OSError):
            os.killpg(child.pid, signal.SIGKILL)
    child.stdout.close()
    child.stderr.close()
    try:
        code = child.wait(timeout=2)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(OSError):
            os.killpg(child.pid, signal.SIGKILL)
        code = child.wait()
    err = said["err"].decode("utf-8", "replace")
    return (None, None, err) if over else (code, said["out"].decode("utf-8", "replace"), err)


def sighted(source, entry):
    """A machine of what another one sees, SOURCE its list (SIGHTS), every field checked: {name, address, user, port,
    source, instance (only shown), alias (its Host there), cert, ips}; None where a field is not what it should be."""
    if not isinstance(entry, dict):
        return None
    text = {key: value for key, value in entry.items() if isinstance(key, str) and isinstance(value, str)}
    found = {"user": None, "port": None, "source": source, "instance": "", "alias": None, "cert": False, "ips": []}
    if source == "ssh_config":
        user, port = entry.get("user"), entry.get("port")
        if user is not None and not user_ok(user) or port is not None and (type(port) is not int or not port_ok(port)):
            return None
        found.update(name=text.get("alias"), address=text.get("host"), user=user, port=port, alias=text.get("alias"),
                     cert=entry.get("cert") is True)
    elif source == "local":
        host, port = text.get("host", "").rstrip(".").lower(), entry.get("port")
        if not host.endswith(".local") or type(port) is not int or not port_ok(port):
            return None
        instance = clean(text.get("instance", ""), 63)            # shown only where it says more than its name
        found.update(name=host.split(".")[0], address=host, port=port,
                     instance="" if instance.casefold() == host.split(".")[0] else instance)
    elif source in ("tailscale", "netbird"):
        dns = text.get("dns" if source == "tailscale" else "fqdn", "").rstrip(".").lower()
        ips = addresses(entry.get("ips")) if source == "tailscale" else addresses([entry.get("ip")])
        if source == "tailscale" and text.get("os") not in SYSTEMS:
            return None
        found.update(name=dns.split(".")[0], address=dns if host_ok(dns) else None, ips=ips)
    name, address = found.get("name"), found.get("address")
    if not (isinstance(name, str) and NAME.fullmatch(name) and isinstance(address, str)
            and (host_ok(address) or address_ok(address))):
        return None
    found["port"] = None if found["port"] == 22 else found["port"]
    return found


def looking_at(machine, clients):
    """The names and addresses that are MACHINE: its target's host, its routes', and how a network of this Mac lists it
    (CLIENTS: clients()'s)."""
    own = {parse_address(machine["target"])[1].lower()} | {route["address"].lower() for route in machine["routes"]}
    for kind in ("tailscale", "netbird"):
        for address in list(own):
            found = peer_of(clients.get(kind), address)
            own |= {found["dns"], *found["ips"]} if found else set()
    return own


def unseen(address):
    """Whether ADDRESS is no other machine: this one's own loopback, by name or address."""
    host = address.lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    return address_ok(host) and (ipaddress.ip_address(host).is_loopback or ipaddress.ip_address(host).is_unspecified)


def look_around_result(text, jump, machines=(), clients=None, own=None):
    """What listed machine JUMP sees (TEXT: its look-around's JSON), each machine checked: ([those offered, in SIGHTS'
    order, at most CANDIDATES], {bad, over: how many left out}, [the lists it skipped]), never one in CLIENTS' lists,
    JUMP, this Mac (OWN: its LocalHostName) or a listed one; None for no such document, or one over LOOK_BYTES."""
    if not isinstance(text, str) or len(text.encode("utf-8", "replace")) > LOOK_BYTES:
        return None
    try:                                    # its last line: a shell's start-up file may print something before it
        sees = json.loads((text.strip().splitlines() or [""])[-1])
    except (ValueError, RecursionError):
        return None
    if not isinstance(sees, dict):
        return None
    clients = clients or {}
    known = looking_at(jump, clients) | {f"{own}.local" if own else ""}
    known |= {one for machine in machines for one in looking_at(machine, {})}
    known |= {ip for client in clients.values() for ip in (client or {}).get("self_ips") or []}
    found, left, seen = [], {"bad": 0, "over": 0}, set()
    for source in SIGHTS:
        listed = sees.get(source) if isinstance(sees.get(source), list) else []
        left["over"] += max(0, len(listed) - CANDIDATES)
        for one in map(lambda entry: sighted(source, entry), listed[:CANDIDATES]):
            if one is None:
                left["bad"] += 1
                continue
            mine = {one["address"].lower(), *one["ips"]}
            reached = any(peer_of(clients.get(kind), where) for kind in ("tailscale", "netbird") for where in mine)
            if not (mine & (known | seen) or reached or unseen(one["address"])):
                found.append(one)
            seen |= mine
    left["over"] += max(0, len(found) - CANDIDATES)
    skipped = [source for source in SIGHTS if sees.get(source) == "skipped"]
    return found[:CANDIDATES], left, skipped


def head(machine, found, probe):
    """MACHINE's heading line for machines.sh: its name, its route in use's network (and the machine it goes through),
    its OS and target."""
    kind, through = probe.network(machine, machine["routes"][0], found)
    emit("machine", machine["name"], kind or "", through or "", machine["os"], machine["target"])


def heading(argv):
    """LIST TAILSCALE NETBIRD ZEROTIER WIREGUARD NAME: machine NAME's heading line, as status says it; no login."""
    listed, binaries, rest, _ = arguments(argv)
    machine = next((one for one in listed if rest and one["name"] == rest[0]), None)
    if machine is None:
        return 1
    head(machine, clients(bounded, binaries), Probe(listed))
    return 0


def through(argv):
    """LIST TAILSCALE NETBIRD ZEROTIER WIREGUARD NAME -- SSH_OPTION…: what machine NAME sees (remote/look-around.py over
    its ssh) as machines.sh's lines: its heading, looking, why it could not tell (lines_of(), python, unreadable), or
    skipped|list, sees|count, candidate|name|address|user|port|list|instance|alias|cert each, left|why|count."""
    listed, binaries, rest, options = arguments(argv)
    jump = next((one for one in listed if rest and one["name"] == rest[0]), None)
    if jump is None:
        return 1
    found = clients(bounded, binaries)
    head(jump, found, Probe(listed))
    emit("looking", jump["name"])
    code, out, err = looked(["ssh", *options, "--", jump["target"], LOOK_COMMAND], LOOK_SECONDS, look_script())
    result = look_around_result(out, jump, listed, found, this_mac()) if code == 0 else None
    if code == 255:
        for line in lines_of(said(jump["name"], jump["target"], err)):
            emit(*line)
        return 0
    if result is None:
        emit("python" if code == NOT_FOUND else "unreadable", jump["name"])
        return 0
    candidates, left, skipped = result
    for source in skipped:
        emit("skipped", source)
    emit("sees", len(candidates))
    for one in candidates:
        emit("candidate", *("" if one[key] is None else one[key]
                            for key in ("name", "address", "user", "port", "source", "instance", "alias")),
             "1" if one["cert"] else "")
    for word, count in left.items():
        if count:
            emit("left", word, count)
    return 0


def lines_of(result):
    """The lines machines.sh says RESULT by: its sentence (away), under it what caused it or what to do (note), and
    each one's own after it on that line (more); a line a tuple of a kind, a catalog key and its arguments."""
    out, follow, kind = [("away", result["key"], *result["args"])], result.get("then") or result.get("action"), "note"
    while follow:
        out.append((kind, follow["key"], *follow["args"], *([follow["command"]] if follow.get("command") else [])))
        follow, kind = follow.get("then") or follow.get("action"), "more"
    return out


def emit(*fields):
    """One line for machines.sh, its fields between bars, written at once (it shows each machine as it comes)."""
    print("|".join(arg(one) for one in fields), flush=True)


def arguments(argv):
    """(the list, {client: its command line or None}, the rest before --, after it) of a status or machines command."""
    rest = argv[5:]
    split = rest.index("--") if "--" in rest else len(rest)
    return read(argv[0]), {kind: one or None for kind, one in zip(CLIENTS, argv[1:5])}, rest[:split], rest[split + 1:]


def status(argv):
    """LIST TAILSCALE NETBIRD ZEROTIER WIREGUARD [NAME…] -- SSH_OPTION…: machine|name|network|through|os|target a line
    each, also|network|through|address its other routes, reaching|name before a login, then lines_of() why it is away
    or up|name. machines.sh says them."""
    listed, binaries, names, options = arguments(argv)
    found = clients(bounded, binaries)
    probe = Probe(listed, options, heard=lambda name: emit("reaching", name))
    for machine in (one for one in listed if not names or one["name"] in names):
        head(machine, found, probe)
        for route in machine["routes"][1:]:
            emit("also", *("" if one is None else one for one in probe.network(machine, route, found)),
                 address_text(None, route["address"], route.get("port")))
        result = ladder(machine, found, probe)
        for line in lines_of(result) if result else [("up", machine["name"])]:
            emit(*line)
    return 0


def machines_json(argv, more=()):
    """LIST TAILSCALE NETBIRD ZEROTIER WIREGUARD [--login [-- SSH_OPTION…]]: what the clients show, as JSON: each
    network's state, its own rung and what it offers to add, each machine's (the list's, then MORE) network, routes and
    key, why it is away and its figures; logins only with --login, the network's state read again right after one."""
    listed, binaries, flags, options = arguments(argv)
    for one in more:
        if all(one["name"] != other["name"] for other in listed):
            listed.append(one)
    found = clients(bounded, binaries)
    probe, shown = Probe(listed, options if "--login" in flags else None), []
    for machine in listed:
        kind, through = probe.network(machine, machine["routes"][0], found)
        result = ladder(machine, found, probe)
        if (probe.measured(machine) or {}).get("ok") and kind in ("tailscale", "netbird"):
            found[kind] = read_client(kind, bounded, binaries[kind])
        shown.append({"name": machine["name"], "os": machine["os"], "target": machine["target"], "network": kind,
                      "through": through, "key": machine.get("key"), "why": result,
                      "figures": figures(machine, found, probe),
                      "routes": [dict(route, network=probe.network(machine, route, found)[0])
                                 for route in machine["routes"]]})
    print(json.dumps({"checked": probe.now, "machines": shown,
                      "networks": {kind: {"installed": one["installed"], "state": one["state"],
                                          "why": client_rung(kind, found), "offered": offered(kind, one, listed)}
                                   for kind, one in found.items()}}))
    return 0


def here_json(argv):
    """LIST [NAME TARGET]…: machines_json()'s for the Herdr app, every 60 s while it shows a remote machine: this Mac's
    clients found here, the app's own machines (at most SHOWN) read after the list's, no login."""
    found, pairs = here(), argv[1:1 + 2 * SHOWN]
    more = [one for one in map(app_machine, pairs[::2], pairs[1::2]) if one]
    return machines_json([argv[0], *(found[kind] or "" for kind in CLIENTS)], more)


def main(argv):
    """netbird COMMAND: a "state|this Mac's address" line, then "name|fqdn|ip|status|path|latency_ms" a peer; local
    COMMAND (dns-sd): "host|port|instance" a machine, the instance only where it says more than the host's name; said
    TARGET TEXT [JUMP]: why a login failed (reachable's lines; through JUMP, by name); the others: their docstrings'."""
    if len(argv) == 3 and argv[1] == "netbird":
        found = netbird_peers(bounded, argv[2])
        print(f"{found['state']}|{found['self_ip'] or ''}")
        for one in found["peers"]:
            print("|".join("" if one[key] is None else str(one[key])
                           for key in ("name", "fqdn", "ip", "status", "path", "latency_ms")))
        return 0
    if len(argv) == 3 and argv[1] == "local":
        for one in bonjour_ssh(listened, None, argv[2]):
            shown = "" if one["instance"].casefold() == one["host"].split(".")[0] else one["instance"]
            print(f"{one['host']}|{one['port']}|{shown}")
        return 0
    if len(argv) in (4, 5) and argv[1] == "said":
        found = said_through(argv[2], argv[4], argv[3]) if len(argv) == 5 else said(argv[2], argv[2], argv[3])
        for line in lines_of(found):
            emit(*line)
        return 0
    if len(argv) >= 3 and argv[1] == "here":
        return here_json(argv[2:])
    commands = {"status": status, "machines": machines_json, "heading": heading, "through": through}
    if len(argv) >= 7 and argv[1] in commands:
        return commands[argv[1]](argv[2:])
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
