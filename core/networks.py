"""What the networks say of their machines: each read through the network's own command within a time limit of its own,
killed with all it started after it, every name and address checked before anything is offered. machines.sh runs it:
networks.py netbird|local <its command>."""
import contextlib
import json
import os
import re
import selectors
import signal
import subprocess
import sys
import time

from machines import address_ok, clean, host_ok, port_ok

NETBIRD_SECONDS = 5             # netbird status's own limit: with its daemon down, a dial alone can take 10 s
PEERS = 256                     # the most machines a network's list offers
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


def stopped(child):
    """CHILD killed with all it started (its own session), its pipe let go: a child of its own may still hold it."""
    with contextlib.suppress(OSError):
        os.killpg(child.pid, signal.SIGKILL)
    child.stdout.close()
    child.wait()


def bounded(argv, seconds):
    """ARGV's (exit status, output) when it ends within SECONDS; None when it cannot start or runs longer, then killed
    with all it started (its own session)."""
    try:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
    except OSError:
        return None
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
    address; the peers by FQDN, each once, at most PEERS."""
    found = {"state": "off", "self_ip": None, "peers": []}
    done = run([binary, "status", "--json"], NETBIRD_SECONDS)
    if not done or done[0] != 0:
        return found
    try:
        status = json.loads(done[1])
    except ValueError:
        said = re.search(r"Daemon status: (\w+)", done[1])        # before v0.70: a text, even with --json
        found["state"] = DAEMON.get(said.group(1), "off") if said else "off"
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
    details = status.get("peers").get("details") if isinstance(status.get("peers"), dict) else None
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


def main(argv):
    """netbird COMMAND: a "state|this Mac's address" line, then "name|fqdn|ip|status|path|latency_ms" a peer; local
    COMMAND (dns-sd): "host|port|instance" a machine, the instance only where it says more than the host's name."""
    if len(argv) == 3 and argv[1] == "netbird":
        found = netbird_peers(bounded, argv[2])
        print(f"{found['state']}|{found['self_ip'] or ''}")
        for one in found["peers"]:
            print("|".join("" if one[key] is None else str(one[key])
                           for key in ("name", "fqdn", "ip", "status", "path", "latency_ms")))
        return 0
    if len(argv) == 3 and argv[1] == "local":
        for one in bonjour_ssh(listened, None, argv[2]):
            said = "" if one["instance"].casefold() == one["host"].split(".")[0] else one["instance"]
            print(f"{one['host']}|{one['port']}|{said}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
