"""What the networks say of their machines: each read through the network's own command within a time limit of its own,
killed with all it started after it, every name and address checked before anything is offered. machines.sh runs it:
networks.py netbird <its command>."""
import contextlib
import json
import os
import re
import signal
import subprocess
import sys

from machines import address_ok, host_ok

NETBIRD_SECONDS = 5             # netbird status's own limit: with its daemon down, a dial alone can take 10 s
PEERS = 256                     # the most machines a network's list offers
# NetBird's daemon states that end the reading (its JSON from v0.70 on, its text before)
DAEMON = {"NeedsLogin": "signed_out", "LoginFailed": "signed_out", "SessionExpired": "expired", "Idle": "off"}
PATHS = {"P2P": "direct", "Relayed": "relayed"}                 # a connected peer's connectionType ("-" for none)
STATUSES = ("Connected", "Connecting", "Idle")                  # Idle is also a lazy connection that is up


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
        with contextlib.suppress(OSError):
            os.killpg(child.pid, signal.SIGKILL)
        child.stdout.close()            # not read to its end: a child of its own may still hold it
        child.wait()
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


def main(argv):
    """netbird COMMAND: a "state|this Mac's address" line, then "name|fqdn|ip|status|path|latency_ms" a peer; exit
    status 2 for a command it does not know."""
    if len(argv) == 3 and argv[1] == "netbird":
        found = netbird_peers(bounded, argv[2])
        print(f"{found['state']}|{found['self_ip'] or ''}")
        for one in found["peers"]:
            print("|".join("" if one[key] is None else str(one[key])
                           for key in ("name", "fqdn", "ip", "status", "path", "latency_ms")))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
