"""What this machine sees, for herdr-fold on the Mac (./machines.sh through): its Tailscale and NetBird peers, the
machines announcing SSH next to it and its ~/.ssh/config Hosts, as one JSON document. Sent over SSH as python3's input;
it only reads and scans nothing, each command within its own time limit and killed with all it started after it."""
import glob
import json
import os
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time

PLATFORM = sys.platform
SECONDS = 5                     # a network's status, and avahi-browse's whole answer
BROWSE_SECONDS = 3              # dns-sd -B never ends by itself: what it lists in this time
LOOKUP_SECONDS = 2              # each instance's dns-sd -L, all at once
MOST = 256                      # the most machines of one list
HEARD = 1 << 20                 # the most bytes read of one command
CONFIG_BYTES = 1 << 18          # the most read of ~/.ssh/config with the files it includes
# where a client's command line is when it is not on the PATH (an app's, Homebrew's)
PLACES = {"tailscale": ("/Applications/Tailscale.app/Contents/MacOS/Tailscale",),
          "netbird": ("/usr/local/bin/netbird", "/opt/homebrew/bin/netbird",
                      "/Applications/NetBird.app/Contents/MacOS/netbird")}
COMPUTERS = ("linux", "macOS", "windows")        # Tailscale's OS of a machine that can be someone's (not a phone)
GIT = re.compile(r"(^|\.)(github\.com|gitlab\.com|bitbucket\.org|ssh\.dev\.azure\.com|vs-ssh\.visualstudio\.com)$",
                 re.I)
STAMP = r"\s*\d{1,2}:\d\d:\d\d\.\d{3}\s+"
BROWSED = re.compile(STAMP + r"(Add|Rmv)\s+[0-9A-Fa-f]+\s+\d+\s+local\.\s+_ssh\._tcp\.\s+(.+)")
REACHED = re.compile(STAMP + r"\S+ can be reached at (\S+):(\d+) \(interface \d+\)")


def binary(name):
    """NAME's command line: on the PATH, else in its usual place; None without it."""
    found = shutil.which(name)
    return found or next((place for place in PLACES.get(name, ()) if os.access(place, os.X_OK)), None)


def heard(argvs, seconds, enough=None):
    """What each of ARGVS prints, all started at once (SECONDS: a limit each), until its time is up, ENOUGH(what it
    printed) is true or HEARD bytes came, then killed with all it started; None for one that cannot start."""
    children, said, start = [], [], time.monotonic()
    for argv in argvs:
        try:
            children.append(subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                             stderr=subprocess.DEVNULL, start_new_session=True))
        except OSError:
            children.append(None)
        said.append(b"")
    limits = seconds if isinstance(seconds, (list, tuple)) else [seconds] * len(argvs)
    with selectors.DefaultSelector() as listening:
        for n, child in enumerate(children):
            if child:
                listening.register(child.stdout, selectors.EVENT_READ, n)
        while listening.get_map():
            now = time.monotonic() - start
            for key in [key for key in listening.get_map().values() if now >= limits[key.data]]:
                listening.unregister(key.fileobj)
            waits = [limits[key.data] - now for key in listening.get_map().values()]
            for key, _ in listening.select(max(0, min(waits))) if waits else []:
                chunk = os.read(key.fd, 65536)
                said[key.data] += chunk
                if not chunk or len(said[key.data]) >= HEARD or enough and enough(
                        said[key.data].decode("utf-8", "replace")):
                    listening.unregister(key.fileobj)
    for child in children:
        if child:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except OSError:
                pass
            child.stdout.close()
            child.wait()
    return [text[:HEARD].decode("utf-8", "replace") if child else None for child, text in zip(children, said)]


def as_json(text):
    try:
        return json.loads(text) if text else None
    except ValueError:
        return None


def tailscale_peers(text):
    """The machines of Tailscale's status that can be someone's: never a Mullvad exit node, a sharee's node, an expired
    one or a phone; "off" for no status."""
    status = as_json(text)
    if not isinstance(status, dict):
        return "off"
    found = []
    for peer in list((status.get("Peer") or {}).values())[:MOST] if isinstance(status.get("Peer"), dict) else []:
        dns = peer.get("DNSName") if isinstance(peer, dict) and isinstance(peer.get("DNSName"), str) else ""
        dns = dns.rstrip(".")
        if (not dns or peer.get("Location") or dns.lower().split(".")[-3:] == ["mullvad", "ts", "net"]
                or peer.get("ShareeNode") or peer.get("Expired") or peer.get("OS") not in COMPUTERS):
            continue
        ips = peer.get("TailscaleIPs") if isinstance(peer.get("TailscaleIPs"), list) else []
        found.append({"dns": dns[:253], "ips": [ip for ip in ips if isinstance(ip, str)][:8], "os": peer["OS"],
                      "online": peer.get("Online") is True})
    return found


def netbird_peers(text):
    """The machines of NetBird's status; "off" for none (no daemon, signed out, no answer)."""
    status = as_json(text)
    details = status.get("peers", {}).get("details") if isinstance(status, dict) and isinstance(
        status.get("peers"), dict) else None
    if not isinstance(details, list):
        return "off"
    found = []
    for peer in details[:MOST]:
        fqdn = peer.get("fqdn") if isinstance(peer, dict) and isinstance(peer.get("fqdn"), str) else ""
        if fqdn:
            ip = peer.get("netbirdIp") if isinstance(peer.get("netbirdIp"), str) else ""
            found.append({"fqdn": fqdn.rstrip(".")[:253], "ip": ip.split("/")[0][:45],
                          "status": str(peer.get("status"))[:16]})
    return found


def unescaped(text):
    """An avahi-browse name as it is: its \\DDD escapes (decimal) back to their characters."""
    return re.sub(r"\\(\d{3})", lambda m: chr(int(m.group(1))), text)


def avahi(text):
    """The machines avahi-browse -p resolved (its = lines): host, port, the instance they announce; each host once."""
    found = {}
    for line in (text or "").splitlines():
        parts = line.split(";")
        if len(parts) >= 9 and parts[0] == "=" and parts[8].isdigit() and parts[6] not in found:
            found[parts[6]] = {"host": parts[6][:253], "port": int(parts[8]), "instance": unescaped(parts[3])[:63]}
    return list(found.values())[:MOST]


def browsed(text):
    """The instances a dns-sd -B listing still has at its end (each added, and not removed since), each once."""
    found = {}
    for line in (text or "").splitlines():
        heard_line = BROWSED.fullmatch(line)
        if heard_line and heard_line.group(1) == "Add":
            found.setdefault(heard_line.group(2), None)
        elif heard_line:
            found.pop(heard_line.group(2), None)
    return list(found)[:MOST]


def reached(text):
    """(host, port) of a dns-sd -L answer's first line that names a host and a port, else None."""
    for line in (text or "").splitlines():
        answer = REACHED.match(line)
        if answer:
            return answer.group(1).rstrip(".").lower(), int(answer.group(2))
    return None


def dns_sd(browse, dns, own):
    """The machines a dns-sd -B listing (BROWSE) names, each looked up (DNS: dns-sd's command line) at once for
    LOOKUP_SECONDS; this machine itself (OWN: its LocalHostName) left out."""
    instances = [one for one in browsed(browse) if len(one.encode("utf-8")) <= 63]
    answers = heard([[dns, "-L", one, "_ssh._tcp", "local."] for one in instances], LOOKUP_SECONDS,
                    lambda text: reached(text) is not None) if instances else []
    found = {}
    for instance, answer in zip(instances, answers):
        where = reached(answer)
        if where and where[0] != f"{own}.local" and where[0] not in found:
            found[where[0]] = {"host": where[0][:253], "port": where[1], "instance": instance[:63]}
    return list(found.values())


def entries(path, depth=0, budget=None):
    """(key, value) pairs of an ssh config at PATH, the files it includes too (relative to ~/.ssh, patterns too), at
    most CONFIG_BYTES of them all."""
    budget = [CONFIG_BYTES] if budget is None else budget
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read(max(0, budget[0]))
    except OSError:
        return
    budget[0] -= len(text)
    for raw in text.splitlines():
        found = re.match(r"\s*([^\s=]+)\s*=?\s*(.*)", raw.split("#", 1)[0])
        if not found or not found.group(1):
            continue
        key, value = found.group(1).lower(), found.group(2).strip()
        if key == "include" and depth < 8:
            for pattern in value.split():
                pattern = os.path.expanduser(pattern)
                pattern = pattern if os.path.isabs(pattern) else os.path.join(os.path.expanduser("~/.ssh"), pattern)
                for included in sorted(glob.glob(pattern))[:64]:
                    yield from entries(included, depth + 1, budget)
        else:
            yield key, value


def ssh_config(path):
    """The Hosts of the ssh config at PATH that name one machine: never a pattern, a git host, one with a jump or a
    proxy of its own or herdr-fold's own; with its address, user, port and whether it logs in with a certificate or a
    security key."""
    order, conf, current = [], {}, []
    for key, value in entries(path):
        if key in ("host", "match"):
            current = value.split() if key == "host" else []
            for alias in current:
                if alias not in conf:
                    order.append(alias)
                    conf[alias] = {}
        elif key in ("hostname", "user", "port", "proxyjump", "proxycommand", "certificatefile",
                     "securitykeyprovider", "pkcs11provider", "identityfile"):
            for alias in current:
                conf[alias].setdefault(key, value)
    found = []
    for alias in order[:MOST]:
        one = conf[alias]
        host = one.get("hostname", alias)
        if (any(ch in alias for ch in "*?!") or one.get("user") == "git" or GIT.search(host) or GIT.search(alias)
                or alias.startswith("herdr-fold.") or one.get("proxyjump", "none") != "none"
                or one.get("proxycommand", "none") != "none"):
            continue
        key_file = one.get("identityfile", "")       # a security key's (id_ed25519_sk), or one with its certificate
        cert = bool(one.get("certificatefile") or one.get("securitykeyprovider") or one.get("pkcs11provider")
                    or re.search(r"_sk(\.pub)?$", key_file)
                    or key_file and os.path.exists(os.path.expanduser(key_file) + "-cert.pub"))
        port = one.get("port", "")
        found.append({"alias": alias[:64], "host": host[:253], "user": one.get("user", "")[:32] or None,
                      "port": int(port) if port.isdigit() and len(port) <= 5 else None, "cert": cert})
    return found


def look():
    """What this machine sees: Tailscale's and NetBird's peers ("missing" without the client, "off" when it does not
    answer), the machines announcing SSH next to it ("skipped" on Linux without avahi-browse), its ~/.ssh/config."""
    tailscale, netbird = binary("tailscale"), binary("netbird")
    mac = PLATFORM == "darwin"
    browse = binary("dns-sd" if mac else "avahi-browse")
    argvs = [[tailscale, "status", "--json"] if tailscale else ["false"],
             [netbird, "status", "--json"] if netbird else ["false"]]
    if browse:
        argvs.append([browse, "-B", "_ssh._tcp", "local."] if mac else [browse, "-tprkl", "_ssh._tcp"])
    said = heard(argvs, [SECONDS, SECONDS] + ([BROWSE_SECONDS if mac else SECONDS] if browse else []))
    if mac and browse:
        own = heard([["scutil", "--get", "LocalHostName"]], 2)[0]
        local = dns_sd(said[2], browse, (own or "").strip().lower())
    else:
        local = avahi(said[2]) if browse else "skipped"
    return {"tailscale": tailscale_peers(said[0]) if tailscale else "missing",
            "netbird": netbird_peers(said[1]) if netbird else "missing",
            "local": local, "ssh_config": ssh_config(os.path.expanduser("~/.ssh/config"))}


if __name__ == "__main__":
    print(json.dumps(look()))
