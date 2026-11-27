"""Tests for core/networks.py: what a network says of its machines, read through its own command within a time limit of
its own: NetBird's peers by name, its state told apart, the machines announcing SSH on the local network by their .local
name, this Mac left out; each machine's network, and why one is away, the first check that fails."""
import calendar
import contextlib
import io
import ipaddress
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from support import (DNS_SD_FOUND, FAKE_DNS_SD, FAKE_NETBIRD, FAKE_SCUTIL, PACKAGE, dns_sd_name, fake_dns_sd, host_key,
                     netbird_status, set_attrs, set_env, stubs, tailscale_json)

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import machines  # noqa: E402
import networks  # noqa: E402


def peer(name, ip, status, path=None, latency=None):
    return {"name": name, "fqdn": f"{name}.netbird.cloud", "ip": ip, "status": status, "path": path,
            "latency_ms": latency}


def answers(code, text):
    """A run() that answers CODE and TEXT for any command."""
    return lambda argv, seconds: (code, text)


class NetBird(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.netbird = os.path.join(stubs(os.path.join(self.tmp, "stubs"), {"netbird": FAKE_NETBIRD}), "netbird")

    def peers(self, state):
        set_env(self, NETBIRD_STATE=state)
        return networks.netbird_peers(networks.bounded, self.netbird)

    def test_netbird_peers_from_its_json(self):
        found = self.peers("connected")
        self.assertEqual((found["state"], found["self_ip"]), ("on", "100.115.93.1"))       # its /16 left off
        self.assertEqual(found["suffix"], "netbird.cloud")                                 # this Mac's own name's
        self.assertEqual(found["peers"], [peer("dev-phone", "100.115.93.13", "idle"),
                                          peer("harbor-web", "100.115.93.12", "idle"),
                                          peer("kelp-ci", "100.115.93.11", "connected", "relayed", 48),
                                          peer("tidepool", "100.115.93.10", "connected", "direct", 12)])
        # the command it runs, with its own limit
        calls = []
        networks.netbird_peers(lambda argv, seconds: calls.append((argv, seconds)), "/opt/netbird")
        self.assertEqual(calls, [(["/opt/netbird", "status", "--json"], 5)])
        # what machines.sh reads: the state and this Mac's address, then a line a peer
        set_env(self, NETBIRD_STATE="connected")
        done = subprocess.run([sys.executable, "-B", os.path.join(PACKAGE, "core", "networks.py"), "netbird",
                               self.netbird], capture_output=True, text=True, timeout=20)
        self.assertEqual(done.stdout.splitlines(), [
            "on|100.115.93.1", "dev-phone|dev-phone.netbird.cloud|100.115.93.13|idle||",
            "harbor-web|harbor-web.netbird.cloud|100.115.93.12|idle||",
            "kelp-ci|kelp-ci.netbird.cloud|100.115.93.11|connected|relayed|48",
            "tidepool|tidepool.netbird.cloud|100.115.93.10|connected|direct|12"], done.stderr)

    def test_a_down_daemon_is_off_and_ends_in_time(self):
        self.assertEqual(self.peers("down"), {"state": "off", "self_ip": None, "suffix": None, "peers": []})
        # a daemon that never answers (its dial alone can take 10 s): off at the limit, with all it started killed
        pids = os.path.join(self.tmp, "pids")
        set_env(self, NETBIRD_PIDS=pids)
        set_attrs(self, networks, NETBIRD_SECONDS=0.5)
        start = time.monotonic()
        self.assertEqual(self.peers("slow")["state"], "off")
        self.assertLess(time.monotonic() - start, 2.5)
        with open(pids) as f:
            child = int(f.read())
        for _ in range(40):
            try:
                os.kill(child, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            self.fail("what the stand-in started still runs")
        self.assertEqual(networks.bounded([os.path.join(self.tmp, "nothing-here")], 1), (networks.NOT_FOUND, ""))

    def test_signed_out_and_an_expired_session_are_told_apart(self):
        self.assertEqual(self.peers("signed_out")["state"], "signed_out")
        self.assertEqual(self.peers("expired")["state"], "expired")
        self.assertEqual(self.peers("plain")["state"], "signed_out")              # before v0.70: a text
        older = "Daemon status: SessionExpired\n\nRun UP command to log in with SSO (interactive login):\n"
        self.assertEqual(networks.netbird_peers(answers(0, older), "netbird")["state"], "expired")
        self.assertEqual(networks.netbird_peers(answers(0, netbird_status((), "LoginFailed", False)),
                                                "netbird")["state"], "signed_out")
        self.assertEqual(networks.netbird_peers(answers(0, netbird_status((), "Idle", False)), "netbird")["state"],
                         "off")                                                   # netbird down: not connected
        self.assertEqual(networks.netbird_peers(answers(0, "something else"), "netbird")["state"], "off")
        # its management server out of reach: the peers it was told last stay, and the state says so
        found = networks.netbird_peers(answers(0, netbird_status(daemon="Connecting", management=False)), "netbird")
        self.assertEqual((found["state"], len(found["peers"])), ("no_management", 4))

    def test_a_peer_of_a_crafted_name_is_left_out(self):
        bad = ["-oProxyCommand=sh.netbird.cloud", "a;id.netbird.cloud", "x\nHost evil", "studio\x1b[31m.netbird.cloud",
               "$(id).netbird.cloud", "a b.netbird.cloud", "a" * 64 + ".netbird.cloud", "", None, 7, ["x"]]
        details = [{"fqdn": name, "netbirdIp": "100.115.93.20", "status": "Connected"} for name in bad]
        details += [{"fqdn": "lab-pi.netbird.cloud", "netbirdIp": "100.115.93.300; id", "status": "Connected\n|x",
                     "connectionType": ["P2P"], "latency": "fast"},
                    {"fqdn": "lab-pi.netbird.cloud", "netbirdIp": "100.115.93.21"},     # the same machine again
                    "not a peer", {"netbirdIp": "100.115.93.22"}]
        status = {"daemonStatus": "Connected", "management": {"connected": True}, "netbirdIp": ["100.115.93.1"],
                  "peers": {"details": details}}
        found = networks.netbird_peers(answers(0, json.dumps(status)), "netbird")
        self.assertEqual(found, {"state": "on", "self_ip": None, "suffix": None, "peers": [peer("lab-pi", None, None)]})
        # a list of 10 000: the first by name, at most PEERS of them
        many = [{"fqdn": f"m{n:05}.netbird.cloud", "netbirdIp": "100.115.93.30", "status": "Idle"}
                for n in range(10000)]
        status["peers"]["details"] = many
        found = networks.netbird_peers(answers(0, json.dumps(status)), "netbird")["peers"]
        self.assertEqual((len(found), found[0]["name"], found[-1]["name"]),
                         (networks.PEERS, "m00000", f"m{networks.PEERS - 1:05}"))
        # nothing but JSON's own shapes: a list, a number
        for text in ("[]", "7", '{"peers": []}', '{"peers": {"details": {}}}'):
            self.assertEqual(networks.netbird_peers(answers(0, text), "netbird")["peers"], [], text)


def announced(instance, host, port=22):
    return {"instance": instance, "host": host, "port": port}


def heard(found=DNS_SD_FOUND, calls=None, extra=None):
    """A listen() that hears what dns-sd says of FOUND (instance, host, port) without running it, EXTRA {instance: an
    answer of its own} too; CALLS gets each call's commands and seconds."""
    browse = "\n".join(f" 9:00:00.100  Add        2  11 local.               _ssh._tcp.           {instance}"
                       for instance in [one[0] for one in found] + list(extra or ()))
    said = {instance: f" 9:00:00.200  {dns_sd_name(instance)}._ssh._tcp.local. can be reached at {host}:{port} "
                      "(interface 11)" for instance, host, port in found}
    said.update(extra or {})

    def listen(argvs, seconds, enough=None):
        if calls is not None:
            calls.append((argvs, seconds))
        return [browse if argv[1] == "-B" else said.get(argv[2], "") for argv in argvs]
    return listen


# what the fake dns-sd's machines come to: by host, this Mac and every crafted host left out
OFFERED = [announced("build-01", "build-01.local", 2222), announced("Dev's MacBook Pro", "devs-macbook-pro.local"),
           announced("Evil]0;ownedBox", "evil-box.local"), announced("lab-pi", "lab-pi.local"),
           announced("studio", "studio.local")]


class Bonjour(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.stubs = stubs(os.path.join(self.tmp, "stubs"), {"dns-sd": FAKE_DNS_SD, "scutil": FAKE_SCUTIL})
        set_env(self, PATH=f"{self.stubs}:{os.environ['PATH']}")

    def test_bonjour_reads_for_its_seconds_and_kills_both_lookups(self):
        # the commands, with their own limits: 3 s for the browse, 2 s for the lookups, the service always SSH's
        calls = []
        networks.bonjour_ssh(heard(calls=calls), binary="/usr/bin/dns-sd", own="")
        self.assertEqual(calls[0], ([["/usr/bin/dns-sd", "-B", "_ssh._tcp", "local."]], 3))
        self.assertIn(["/usr/bin/dns-sd", "-L", "studio", "_ssh._tcp", "local."], calls[1][0])
        self.assertEqual((len(calls), len(calls[1][0]), calls[1][1]), (2, len(DNS_SD_FOUND), 2))
        # dns-sd never ends by itself: the browse is heard for its seconds, then every lookup at once for theirs (one
        # that answered is not waited on), then each is killed with all it started
        pids = os.path.join(self.tmp, "pids")
        set_env(self, DNS_SD_PIDS=pids)
        set_attrs(self, networks, LOOKUP_SECONDS=0.5)
        start = time.monotonic()
        self.assertEqual(networks.bonjour_ssh(seconds=0.5), OFFERED)
        took = time.monotonic() - start
        self.assertGreaterEqual(took, 0.5)
        self.assertLess(took, 2.5)
        with open(pids) as f:
            children = [int(line) for line in f]
        self.assertEqual(len(children), 1 + len(DNS_SD_FOUND))            # the browse, a lookup each (not kelp-ci's)
        for child in children:
            for _ in range(40):
                try:
                    os.kill(child, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.05)
            else:
                self.fail("what a stand-in dns-sd started still runs")
        # a reading that cannot start hears nothing; one that floods is cut at HEARD bytes, at once
        self.assertEqual(networks.listened([[os.path.join(self.tmp, "nothing-here")]], 1), [None])
        start = time.monotonic()
        flood = networks.listened([["/bin/sh", "-c", "yes 'Add x' | head -c 1000000; sleep 30"]], 5)[0]
        self.assertLessEqual(len(flood), networks.HEARD)
        self.assertLess(time.monotonic() - start, 3)

    def test_the_local_name_is_kept_never_the_address(self):
        # a machine there is offered by its .local name, which stays when its address changes: dns-sd -G is never
        # asked, and a host given as an address is left out
        calls = []
        self.assertEqual(networks.bonjour_ssh(heard(calls=calls), own="this-mac"), OFFERED)
        self.assertEqual([argv[1] for argvs, _ in calls for argv in argvs], ["-B"] + ["-L"] * len(DNS_SD_FOUND))
        # the same machine heard under two instances is offered once, under the first by name
        twice = DNS_SD_FOUND[:1] + (("studio (2)", "Studio.local.", 22),)
        self.assertEqual(networks.bonjour_ssh(heard(twice), own=""), [announced("studio", "studio.local")])
        # what machines.sh reads: a "host|port|instance" line each, the instance only where it says more than the host
        stubs(self.stubs, {"dns-sd": fake_dns_sd((("studio", "studio.local.", 22),
                                                  ("Dev's MacBook Pro", "devs-macbook-pro.local.", 22)))})
        done = subprocess.run([sys.executable, "-B", os.path.join(PACKAGE, "core", "networks.py"), "local",
                               os.path.join(self.stubs, "dns-sd")], capture_output=True, text=True, timeout=20)
        self.assertEqual(done.stdout.splitlines(), ["devs-macbook-pro.local|22|Dev's MacBook Pro", "studio.local|22|"],
                         done.stderr)

    def test_this_macs_own_instance_is_left_out(self):
        self.assertEqual(networks.this_mac(), "this-mac")                   # scutil's LocalHostName, the stand-in's
        hosts = lambda own: [one["host"] for one in networks.bonjour_ssh(heard(), own=own)]   # noqa: E731
        self.assertNotIn("this-mac.local", hosts(None))                     # None: scutil is asked
        self.assertIn("this-mac.local", hosts(""))                          # no name of its own: none left out
        # its answer is checked as anything else: no name, or an option, is none
        self.assertEqual(networks.this_mac(answers(0, "This-Mac\n")), "this-mac")
        self.assertIsNone(networks.this_mac(answers(0, "-oProxyCommand=x\n")))
        self.assertIsNone(networks.this_mac(answers(1, "")))
        self.assertIsNone(networks.this_mac(lambda argv, seconds: None))

    def test_a_crafted_instance_is_shown_cleaned_and_its_bad_host_left_out(self):
        found = {one["host"]: one for one in networks.bonjour_ssh(heard(), own="this-mac")}
        self.assertEqual(found["evil-box.local"]["instance"], "Evil]0;ownedBox")      # its control characters dropped
        for bad in ("-oproxycommand=sh.local", "x;id.local", "far.example.com", "192.0.2.30", "db-02.local"):
            self.assertNotIn(bad, found)
        # what a lookup prints after its answer (a TXT record) is never taken for one; a name too long for a DNS label
        # is not looked up
        txt = {"printer": " 9:00:00.200  printer._ssh._tcp.local. can be reached at -x.local.:22 (interface 11)\n"
                          " can be reached at kelp-ci.local.:22 (interface 1)",
               "a" * 64: " 9:00:00.200  aaa._ssh._tcp.local. can be reached at long.local.:22 (interface 11)"}
        calls = []
        self.assertEqual(networks.bonjour_ssh(heard((), calls, txt), own=""), [])
        self.assertEqual([argv[2] for argv in calls[1][0]], ["printer"])
        # a network of 10 000: the first by name, at most INSTANCES looked up
        many = tuple((f"m{n:05}", f"m{n:05}.local.", 22) for n in range(10000))
        calls = []
        found = networks.bonjour_ssh(heard(many, calls), own="")
        self.assertEqual((len(calls[1][0]), calls[1][0][0][2], len(found)), (networks.INSTANCES, "m00000",
                                                                             networks.INSTANCES))
        # nothing it hears is a line of its own: no answer, a line of no shape
        self.assertEqual(networks.bonjour_ssh(lambda argvs, seconds, enough=None: [None] * len(argvs), own=""), [])
        self.assertEqual(networks.bonjour_ssh(lambda argvs, seconds, enough=None: ["Add studio"] * len(argvs),
                                              own=""), [])


NOW = calendar.timegm((2026, 11, 26, 9, 0, 0))                     # when the checks run, UTC
AT = "@"                        # a user before a host: put together here, never an e-mail's look
STUDIO_KEY, STUDIO = host_key("FakeHostKeyOfStudio")
OTHER_KEY, _ = host_key("FakeHostKeyOfSomeoneElse")
# a home network's address, made: the privacy check takes any written one for a real home's
LAN = str(ipaddress.ip_address((10 << 24) + 20))
# Tailscale's machines (address, fields of its own): lumen-api direct, studio relayed through fra, vps-edge idle,
# harbor-web offline since 3 h 5 min before NOW, kelp-ci's key expired
TAILNET = {"lumen-api": ("100.115.92.10", {"Active": True, "CurAddr": "198.51.100.7:41641"}),
           "studio": ("100.115.92.13", {"Active": True}), "vps-edge": ("100.115.92.14", {}),
           "harbor-web": ("100.115.92.11", {"Online": False, "LastSeen": "2026-11-26T05:55:00Z"}),
           "kelp-ci": ("100.115.92.12", {"Online": False, "Expired": True, "LastSeen": "2026-10-01T09:00:00Z"})}
ZEROTIER = json.dumps([{"nwid": "8056c2e21c000001", "name": "lab", "status": "OK", "type": "PRIVATE",
                        "assignedAddresses": ["198.51.100.65/26"], "portDeviceName": "feth2001"}])
EVERY = {"tailscale": "tailscale", "netbird": "netbird", "zerotier": "zerotier-cli",
         "wireguard": "/Applications/WireGuard.app"}
HERE = {"studio.local": ("192.0.2.20", "en0")}             # studio answers on the local network, lab-pi does not


def runner(tailscale=tailscale_json(TAILNET), netbird=netbird_status(), zerotier=ZEROTIER, route=None, ifconfig=None,
           scans=None, ssh_config="", calls=None):
    """A run() that answers as this Mac would: the clients' status (None: none), route -n get {where: (address,
    interface)}, ifconfig {interface: address}, ssh-keyscan {host: key}, ssh -G's lines; CALLS gets each command."""
    def run(argv, seconds):
        if calls is not None:
            calls.append(argv)
        program, where = os.path.basename(argv[0]), argv[-1]
        if program in ("tailscale", "netbird", "zerotier-cli"):
            text = {"tailscale": tailscale, "netbird": netbird, "zerotier-cli": zerotier}[program]
            return (1, "") if text is None else (0, text)
        if program == "route":
            found = (route or {}).get(where)
            return (0, f"   route to: {found[0]}\n  interface: {found[1]}\n") if found else (68, "")
        if program == "ifconfig":
            found = (ifconfig or {}).get(where)
            return (0, f"{where}: flags=8051<UP>\n\tinet {found} --> {found} netmask 0xff\n") if found else (1, "")
        if program == "ssh-keyscan":
            found = (scans or {}).get(where)
            return 0, f"{where} {found}\n" if found else ""
        if program == "ssh" and argv[1] == "-G":
            return 0, ssh_config
        raise AssertionError(f"no check runs {argv}")
    return run


def talking(answers=None, calls=None):
    """A login's stand-in: ANSWERS {target: what ssh says, it then exits 255}, any other target logs in."""
    def talk(argv, seconds):
        target = argv[argv.index("--") + 1]
        if calls is not None:
            calls.append(target)
        said = (answers or {}).get(target)
        return (0, "") if said is None else (255, said)
    return talk


def route(network, address, user=None, through=None):
    return {"network": network, "address": address, "user": user, "port": None, "through": through}


def machine(name, target, routes=None, key=None):
    return {"name": name, "target": target, "os": "linux", "key": key,
            "routes": routes or [machines.target_route(target)]}


LUMEN = machine("lumen-api", "root" + AT + "lumen-api.tail0000.ts.net")
HARBOR = machine("harbor-web", "root" + AT + "harbor-web.tail0000.ts.net")
KELP = machine("kelp-ci", "root" + AT + "kelp-ci.tail0000.ts.net")
TIDEPOOL = machine("tidepool", "root" + AT + "tidepool.netbird.cloud")
LAB_PI = machine("lab-pi", "pi" + AT + "lab-pi.local")
STUDIO_ROUTES = [route("local", "studio.local", "dev"), route("tailscale", "studio.tail0000.ts.net", "dev")]
STUDIO_TWO = machine("studio", "herdr-fold.studio", STUDIO_ROUTES, STUDIO)
BUILD = machine("build-01", "herdr-fold.build-01", [route("through", "198.51.100.30", "root", "lumen-api")])
DB = machine("db-02", "herdr-fold.db-02", [route("through", "db-02.local", "root", "lumen-api")])
LISTED = [LUMEN, HARBOR, KELP, TIDEPOOL, LAB_PI, STUDIO_TWO, BUILD, DB]


def clients(missing=(), **answers):
    """This Mac's clients as runner() answers for them, those named in MISSING not installed."""
    return networks.clients(runner(**answers), dict(EVERY, **dict.fromkeys(missing)), NOW)


class EachMachinesNetwork(unittest.TestCase):
    def test_an_address_in_both_ranges_goes_to_the_client_listing_it(self):
        run = runner(route={"100.115.92.99": ("100.115.92.99", "en0")})
        found = networks.clients(run, EVERY, NOW)
        self.assertEqual([networks.network_of(one, found, run) for one in (
            "100.115.92.10", "100.115.93.10", "lumen-api.tail0000.ts.net", "tidepool.netbird.cloud", "lumen-api",
            "198.51.100.70")], ["tailscale", "netbird", "tailscale", "netbird", "tailscale", "zerotier"])
        # 100.64/10 alone decides nothing: an address there that neither lists, routed out through en0
        self.assertIsNone(networks.network_of("100.115.92.99", found, run))
        # with both off, a name their own domains tell is still theirs
        off = clients(tailscale=None, netbird=None)
        self.assertEqual((off["tailscale"]["state"], off["netbird"]["state"]), ("off", "off"))
        self.assertEqual((networks.network_of("harbor-web.tail0000.ts.net", off, run),
                          networks.network_of("kelp-ci.netbird.cloud", off, run)), ("tailscale", "netbird"))

    def test_a_utun_is_named_by_its_owners_address(self):
        table = {"198.51.100.40": ("198.51.100.40", "utun4"), "198.51.100.41": ("198.51.100.41", "utun100"),
                 "198.51.100.42": ("198.51.100.42", "utun7"), "198.51.100.43": ("198.51.100.43", "feth2001")}
        run = runner(route=table, ifconfig={"utun4": "100.115.92.1", "utun100": "100.115.93.1", "utun7": "203.0.113.9"})
        found = networks.clients(run, EVERY, NOW)
        self.assertEqual([networks.network_of(one, found, run) for one in table],
                         ["tailscale", "netbird", "wireguard", "zerotier"])
        # a tunnel no client claims, without the WireGuard app: a tunnel of some other kind
        found = networks.clients(run, dict(EVERY, wireguard=None), NOW)
        self.assertEqual(networks.network_of("198.51.100.42", found, run), "tunnel")

    def test_a_private_route_on_en0_is_local_and_a_global_one_public(self):
        table = {LAN: (LAN, "en0"), "203.0.113.5": ("203.0.113.5", "en0"),
                 "vps-edge.example.com": ("203.0.113.5", "en0"), "198.51.100.9": ("198.51.100.9", "bridge100"),
                 "127.0.0.1": ("127.0.0.1", "lo0"), "crafted.example.com": ("x;id", "en0")}
        calls = []
        run = runner(route=table, calls=calls)
        found = networks.clients(run, EVERY, NOW)
        self.assertEqual([networks.network_of(one, found, run) for one in (
            LAN, "203.0.113.5", "vps-edge.example.com", "198.51.100.9", "127.0.0.1", "crafted.example.com",
            "nowhere.example.com", "-oProxyCommand=sh")],
            ["local", "public", "public", "public", None, None, None, None])
        # a .local name is the local network's by its name alone: route is not asked
        del calls[:]
        self.assertEqual(networks.network_of("lab-pi.local", found, run), "local")
        self.assertEqual(calls, [])

    def test_a_routes_network_is_kept_else_told_and_a_cloudflared_host_is_cloudflare(self):
        web = machine("web", "web")                                       # a Host of ~/.ssh/config
        run = runner(ssh_config="hostname ssh.example.com\nproxycommand cloudflared access ssh --hostname %h\n")
        found = networks.clients(run, EVERY, NOW)
        self.assertEqual(networks.route_network(web, web["routes"][0], found, run), ("cloudflare", None))
        self.assertEqual(networks.route_network(STUDIO_TWO, STUDIO_ROUTES[1], found, run), ("tailscale", None))
        self.assertEqual(networks.route_network(BUILD, BUILD["routes"][0], found, run), ("through", "lumen-api"))
        run = runner(ssh_config="hostname 198.51.100.30\nproxyjump admin" + AT + "jump.example.com:2222\n")
        self.assertEqual(networks.route_network(web, web["routes"][0], found, run), ("through", "jump.example.com"))
        run = runner(ssh_config="hostname lumen-api.tail0000.ts.net\nproxyjump none\nproxycommand none\n")
        self.assertEqual(networks.route_network(web, web["routes"][0], found, run), ("tailscale", None))


class WhyOneIsAway(unittest.TestCase):
    def why(self, one, found, talk=None, here=HERE, scans=None, calls=None):
        run = runner(route=here, scans=scans)
        return networks.ladder(one, found, networks.Probe(LISTED, ["-o", "BatchMode=yes"], run, talking(talk, calls),
                                                          NOW))

    def test_every_rung_of_the_ladder_in_order(self):
        why, todo, on = networks.why, networks.todo, clients()
        turn_on = why("machines.why_tailscale_off", action=todo("machines.why_do_turn_on", command="tailscale up"))
        # 1 the client missing; 2 the client off
        self.assertEqual(self.why(TIDEPOOL, clients(missing=["netbird"])), why(
            "machines.why_missing", "NetBird", action=todo("machines.why_do_get", command=networks.PAGES["netbird"])))
        self.assertEqual(self.why(LUMEN, clients(tailscale=None)), turn_on)
        self.assertEqual(self.why(LUMEN, clients(tailscale=tailscale_json(TAILNET, "Stopped"))), turn_on)
        self.assertEqual(self.why(TIDEPOOL, clients(netbird=None)), why(
            "machines.why_netbird_off", action=todo("machines.why_do_start", command="netbird up")))
        # 3 signed out, its key expired, waiting for approval, its server out of reach
        for one, answers, expected in [
                (LUMEN, {"tailscale": tailscale_json({}, "NeedsLogin")}, why(
                    "machines.why_tailscale_signed_out",
                    action=todo("machines.why_do_sign_in", command="tailscale login"))),
                (LUMEN, {"tailscale": tailscale_json(TAILNET, expired=True)}, why(
                    "machines.why_tailscale_expired",
                    action=todo("machines.why_do_sign_in_again", command="tailscale login"))),
                (LUMEN, {"tailscale": tailscale_json({}, "NeedsMachineAuth")}, why(
                    "machines.why_tailscale_approval",
                    action=todo("machines.why_do_console", command=networks.CONSOLE))),
                (TIDEPOOL, {"netbird": netbird_status((), "NeedsLogin", False)}, why(
                    "machines.why_netbird_signed_out", action=todo("machines.why_do_sign_in", command="netbird up"))),
                (TIDEPOOL, {"netbird": netbird_status((), "SessionExpired", False)}, why(
                    "machines.why_netbird_expired",
                    action=todo("machines.why_do_sign_in_again", command="netbird up"))),
                (TIDEPOOL, {"netbird": netbird_status(daemon="Connecting", management=False)},
                 why("machines.why_netbird_management"))]:
            self.assertEqual(self.why(one, clients(**answers)), expected, answers)
        # 4 the machine offline there, its key expired, not in this Mac's network
        self.assertEqual(self.why(HARBOR, on), why("machines.why_offline", "harbor-web", "Tailscale", "3 h"))
        self.assertEqual(self.why(KELP, on), why("machines.why_peer_expired", "kelp-ci", "Tailscale",
                                                 action=todo("machines.why_do_console", command=networks.CONSOLE)))
        ci = machine("ci-runner", "root" + AT + "ci-runner.netbird.cloud")
        self.assertEqual(self.why(ci, on), why("machines.why_not_in", "ci-runner", "NetBird"))
        # 5 not on this local network; another route that shows the machine's own key answers
        self.assertEqual(self.why(LAB_PI, on), why("machines.why_not_here", "lab-pi"))
        missing = networks.Probe(LISTED, ["-o", "BatchMode=yes"], lambda argv, seconds: (networks.NOT_FOUND, ""),
                                 talking(), NOW)
        self.assertIsNone(networks.ladder(LAB_PI, on, missing))                 # no route here: its login tells
        self.assertEqual(self.why(STUDIO_TWO, on, here={}, scans={"studio.tail0000.ts.net": STUDIO_KEY}), why(
            "machines.why_not_here", "studio", action=todo("machines.why_do_route_on", "Tailscale")))
        # 6 no SSH answer, 7 another key, 8 the login refused, each in ssh's own words
        target = LUMEN["target"]
        for said, expected in [
                ("ssh: connect to host lumen-api.tail0000.ts.net port 22: Operation timed out",
                 why("machines.why_no_answer", "lumen-api")),
                ("ssh: connect to host lumen-api.tail0000.ts.net port 22: Connection refused",
                 why("machines.why_no_ssh", "lumen-api", action=todo("machines.why_do_ssh_on"))),
                ("ssh: Could not resolve hostname lumen-api.tail0000.ts.net: nodename nor servname provided",
                 why("machines.why_unknown_name", "lumen-api")),
                ("Host key verification failed.", why("machines.why_host_key", "lumen-api", action=todo(
                    "machines.why_do_host_key", command="ssh-keygen -R lumen-api.tail0000.ts.net"))),
                (target + ": Permission denied (publickey).",
                 why("machines.why_login", "lumen-api", action=todo("machines.why_do_login", command="ssh " + target))),
                ("# Tailscale SSH requires an additional check.\n# To authenticate, visit: https://login.tailscale.com"
                 "/a/0000\n", why("machines.why_tailscale_check", "lumen-api",
                                  action=todo("machines.why_do_once", command="ssh " + target))),
                ("kex_exchange_identification: read: Connection reset by peer\n", why(
                    "machines.why_other", "lumen-api", "kex_exchange_identification: read: Connection reset by peer"))]:
            self.assertEqual(self.why(LUMEN, on, {target: said}), expected, said)
        # a route of a machine reached by several: another key there is never used; its other route answers with its own
        self.assertEqual(self.why(STUDIO_TWO, on, {"herdr-fold.studio": "Host key verification failed."},
                                  scans={"studio.tail0000.ts.net": STUDIO_KEY}),
                         why("machines.why_route_key", "studio.local", "studio",
                             action=todo("machines.why_do_route_on", "Tailscale")))
        self.assertEqual(self.why(STUDIO_TWO, on, {"herdr-fold.studio": "Host key verification failed."},
                                  scans={"studio.tail0000.ts.net": OTHER_KEY}),
                         why("machines.why_route_key", "studio.local", "studio"))
        # 9 the jump host: down, its own rung after it; refusing to let connections through
        lost = {BUILD["target"]: "ssh: connect to host lumen-api.tail0000.ts.net port 22: Operation timed out\r\n"
                                 "Connection closed by UNKNOWN port 65535"}
        self.assertEqual(self.why(BUILD, clients(tailscale=None), lost),
                         why("machines.why_through", "build-01", "lumen-api", then=turn_on))
        refused = {DB["target"]: "channel 0: open failed: administratively prohibited: open failed\n"
                                 "stdio forwarding failed\nConnection closed by UNKNOWN port 65535"}
        self.assertEqual(self.why(DB, on, refused), why("machines.why_no_forwarding", "lumen-api"))
        silent = {DB["target"]: "ssh: connect to host db-02.local port 22: Operation timed out"}
        self.assertEqual(self.why(DB, on, silent), why("machines.why_no_answer", "db-02"))   # lumen-api up: db-02's own
        # a login that works: none; NetBird's Idle is no rung (a lazy connection that is up is idle too)
        self.assertIsNone(self.why(LUMEN, on))
        self.assertIsNone(self.why(machine("harbor-nb", "root" + AT + "harbor-web.netbird.cloud"), on))
        # in order: the first check that fails, and no login before the network's own checks pass
        calls = []
        self.assertEqual(self.why(HARBOR, clients(tailscale=None), calls=calls), turn_on)
        self.assertEqual(self.why(LAB_PI, clients(tailscale=None), calls=calls)["key"], "machines.why_not_here")
        self.assertEqual(calls, [])

    def test_the_admin_console_is_tailscales_own_only(self):
        # a tailnet of Tailscale's own (a .ts.net suffix) gets its admin console's link; Headscale's or another control
        # server's, the plain words, no link; while waiting for approval, the suffix of this Mac's own name tells
        console = networks.todo("machines.why_do_console", command=networks.CONSOLE)
        admin = networks.todo("machines.why_do_control_admin")
        headscale = "tail.example.test"
        kelp = machine("kelp-ci", "root" + AT + "kelp-ci." + headscale)
        for suffix, one, expected in [("tail0000.ts.net", KELP, console), (headscale, kelp, admin)]:
            found = clients(tailscale=tailscale_json(TAILNET, suffix=suffix))
            self.assertEqual(self.why(one, found),
                             networks.why("machines.why_peer_expired", "kelp-ci", "Tailscale", action=expected), suffix)
            waiting = clients(tailscale=tailscale_json({}, "NeedsMachineAuth", suffix=suffix))
            self.assertEqual(self.why(one, waiting), networks.why("machines.why_tailscale_approval", action=expected),
                             suffix)

    def test_a_failed_login_says_the_ladders_words(self):
        # reachable's words: networks.py said TARGET TEXT, the ladder's sentence and what to do, a line each
        target = "root" + AT + "dev-phone.netbird.cloud"
        done = subprocess.run([sys.executable, "-B", os.path.join(PACKAGE, "core", "networks.py"), "said", target,
                               "ssh: connect to host dev-phone.netbird.cloud port 22: Connection refused\n"],
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(done.stdout.splitlines(),
                         [f"away|machines.why_no_ssh|{target}", "note|machines.why_do_ssh_on"], done.stderr)
        # what ssh says is cleaned and stays one field; the jump host's own rung and its action follow on one note
        said = networks.said("box", "box", "kex_exchange_identification: \x1b]0;x\x07closed|by\n\n")
        self.assertEqual(networks.lines_of(said), [("away", "machines.why_other", "box",
                                                    "kex_exchange_identification: ]0;xclosed/by")])
        through = networks.why("machines.why_through", "build-01", "lumen-api", then=networks.why(
            "machines.why_tailscale_off", action=networks.todo("machines.why_do_turn_on", command="tailscale up")))
        self.assertEqual(networks.lines_of(through), [("away", "machines.why_through", "build-01", "lumen-api"),
                                                      ("note", "machines.why_tailscale_off"),
                                                      ("more", "machines.why_do_turn_on", "tailscale up")])


class Figures(unittest.TestCase):
    def test_a_relayed_peer_and_a_direct_one(self):
        on = clients()
        probe = networks.Probe(LISTED, ["-o", "BatchMode=yes"], runner(route=HERE), talking(), NOW)
        studio = machine("studio", "dev" + AT + "studio.tail0000.ts.net")
        vps = machine("vps-edge", "root" + AT + "vps-edge.tail0000.ts.net")
        kelp = machine("kelp-nb", "root" + AT + "kelp-ci.netbird.cloud")
        found = {one["name"]: networks.figures(one, on, probe) for one in (LUMEN, studio, vps, TIDEPOOL, kelp, HARBOR)}
        # before a login, the networks' own word alone: Tailscale's CurAddr or its relay, NetBird's type and latency
        self.assertEqual(found["lumen-api"], {"path": "direct", "relay": None, "login_ms": None, "seen": None})
        self.assertEqual(found["studio"], {"path": "relayed", "relay": "fra", "login_ms": None, "seen": None})
        self.assertIsNone(found["vps-edge"]["path"])                            # idle: no path word
        self.assertEqual(found["tidepool"], {"path": "direct", "relay": None, "login_ms": 12, "seen": None})
        self.assertEqual(found["kelp-nb"], {"path": "relayed", "relay": None, "login_ms": 48, "seen": None})
        self.assertEqual(found["harbor-web"]["seen"], calendar.timegm((2026, 11, 26, 5, 55, 0)))
        # after a login: how long it took, and when
        self.assertIsNone(networks.ladder(LUMEN, on, probe))
        after = networks.figures(LUMEN, on, probe)
        self.assertEqual((after["path"], after["seen"], type(after["login_ms"])), ("direct", NOW, int))

    def test_the_clients_read_it_all_as_json(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        logins = os.path.join(tmp, "logins")
        folder = stubs(os.path.join(tmp, "stubs"), {
            "tailscale": "#!/bin/sh\ncat <<'JSON'\n" + tailscale_json(TAILNET) + "\nJSON\n",
            "ssh": f"#!/bin/sh\n[ \"$1\" = -G ] && exit 0\necho \"$*\" >> '{logins}'\nexit 0\n"})
        listed = os.path.join(tmp, "machines.txt")
        with open(listed, "w") as f:
            f.write(f"lumen-api | root{AT}lumen-api.tail0000.ts.net | linux\n"
                    f"harbor-web | root{AT}harbor-web.tail0000.ts.net | linux\n")

        def read(*more):
            done = subprocess.run([sys.executable, "-B", os.path.join(PACKAGE, "core", "networks.py"), "machines",
                                   listed, os.path.join(folder, "tailscale"), "", "", "", *more],
                                  capture_output=True, text=True, timeout=30,
                                  env={"PATH": f"{folder}:/usr/bin:/bin", "HOME": tmp})
            return json.loads(done.stdout)
        # the 60 s look: the networks' own checks alone, no login; each network's own rung, and the machines its
        # import offers that are not on the list yet (kelp-ci's key expired: none offered)
        found = read()
        self.assertEqual((found["networks"]["tailscale"], found["networks"]["netbird"]), (
            {"installed": True, "state": "on", "why": None, "offered": ["studio", "vps-edge"]},
            {"installed": False, "state": None, "offered": [], "why": networks.why(
                "machines.why_missing", "NetBird", action=networks.todo("machines.why_do_get",
                                                                        command=networks.PAGES["netbird"]))}))
        by = {one["name"]: one for one in found["machines"]}
        self.assertEqual((by["lumen-api"]["network"], by["lumen-api"]["why"]), ("tailscale", None))
        self.assertEqual(by["harbor-web"]["why"]["key"], "machines.why_offline")
        self.assertEqual(by["lumen-api"]["routes"], [route("tailscale", "lumen-api.tail0000.ts.net", "root")])
        self.assertFalse(os.path.exists(logins))
        # the status check: a login to each machine whose network lets it through, timed
        found = read("--login", "--", "-o", "BatchMode=yes")
        lumen = next(one for one in found["machines"] if one["name"] == "lumen-api")
        self.assertEqual((lumen["why"], lumen["figures"]["path"], type(lumen["figures"]["login_ms"])),
                         (None, "direct", int))
        with open(logins) as f:
            self.assertEqual(f.read(), f"-o BatchMode=yes -- root{AT}lumen-api.tail0000.ts.net exit\n")


class ForTheApp(unittest.TestCase):
    """The Herdr app's look (networks.py here, every 60 s while a remote machine shows): this Mac's clients found as
    machines.sh finds them, the app's own machines read with the list's, what each network offers to add."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_the_app_finds_the_clients_where_machines_sh_does(self):
        bin_dir = stubs(os.path.join(self.tmp, "bin"), {"tailscale": "#!/bin/sh\nexit 0\n"})
        fixed = stubs(os.path.join(self.tmp, "fixed"), {"netbird": "#!/bin/sh\nexit 0\n"})
        os.makedirs(os.path.join(self.tmp, "WireGuard.app"))
        set_env(self, PATH=bin_dir)
        places = {"tailscale": ("tailscale", os.path.join(self.tmp, "nowhere")),
                  "netbird": ("netbird", os.path.join(self.tmp, "nowhere"), os.path.join(fixed, "netbird")),
                  "zerotier": ("zerotier-cli",)}
        self.assertEqual(networks.here(places, os.path.join(self.tmp, "WireGuard.app")), {
            "tailscale": os.path.join(bin_dir, "tailscale"), "netbird": os.path.join(fixed, "netbird"),
            "zerotier": None, "wireguard": os.path.join(self.tmp, "WireGuard.app")})
        self.assertEqual(networks.here(places, os.path.join(self.tmp, "none.app"))["wireguard"], None)
        # the places lib/common.sh's tailscale_bin and netbird_bin look, the same as networks.py's
        with open(os.path.join(PACKAGE, "lib", "common.sh"), encoding="utf-8") as f:
            common = f.read()
        for kind in ("tailscale", "netbird"):
            body = common[common.index(f"{kind}_bin() {{"):]
            body = body[:body.index("\n}\n")]
            places = set(re.findall(r"/[\w./-]+", body)) - {"/dev/null"}
            self.assertEqual(sorted(places), sorted(networks.PLACES[kind][1:]), kind)

    def test_the_apps_own_machines_are_read_with_the_list(self):
        folder = stubs(os.path.join(self.tmp, "stubs"), {
            "tailscale": "#!/bin/sh\ncat <<'JSON'\n" + tailscale_json(TAILNET) + "\nJSON\n",
            "ssh": "#!/bin/sh\nexit 0\n", "route": "#!/bin/sh\nexit 68\n"})
        set_env(self, PATH=f"{folder}:/usr/bin:/bin")
        set_attrs(self, networks, here=lambda: {"tailscale": os.path.join(folder, "tailscale"), "netbird": None,
                                                "zerotier": None, "wireguard": None})
        listed = os.path.join(self.tmp, "machines.txt")
        with open(listed, "w") as f:
            f.write(f"lumen-api | root{AT}lumen-api.tail0000.ts.net | linux\n")
        crafted = ["-oProxyCommand=x", "root" + AT + "evil.example", "evil", "-oProxyCommand=touch x",
                   "evil-2", "root" + AT + "a.example;touch x", "evil-3", "root" + AT + "evil\nbox"]
        pairs = ["vps-edge", "root" + AT + "vps-edge.tail0000.ts.net", "lumen-api", "dev" + AT + "elsewhere.example",
                 "studio", "dev" + AT + "studio.local", *crafted]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(networks.main(["networks.py", "here", listed, *pairs]), 0)
        found = json.loads(out.getvalue())
        by = {one["name"]: one for one in found["machines"]}
        # the list first, then the app's own in its order, each name once (the list's target wins), none crafted
        self.assertEqual(list(by), ["lumen-api", "vps-edge", "studio"])
        self.assertEqual(by["lumen-api"]["target"], "root" + AT + "lumen-api.tail0000.ts.net")
        self.assertEqual((by["vps-edge"]["network"], by["studio"]["network"]), ("tailscale", "local"))
        self.assertEqual(by["vps-edge"]["routes"], [route("tailscale", "vps-edge.tail0000.ts.net", "root")])
        # what the app has already is never offered again (vps-edge; kelp-ci's key expired); studio's tailnet name
        # is no route the app knows, so its import offers it (and finds it by its key)
        self.assertEqual(found["networks"]["tailscale"]["offered"], ["harbor-web", "studio"])
        # at most SHOWN of the app's own
        many = [one for n in range(networks.SHOWN + 5) for one in (f"m{n}", f"root{AT}m{n}.tail0000.ts.net")]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            networks.main(["networks.py", "here", listed, *many])
        self.assertEqual(len(json.loads(out.getvalue())["machines"]), 1 + networks.SHOWN)

    def test_the_apps_status_check_logs_in_as_machines_sh_does_and_only_when_asked(self):
        # the Machines tab's Refresh (here LIST --login …): a login to each machine whose network lets it through,
        # with machines.sh's own ssh options; the 60 s look none; --login anywhere else is no machine and asks none
        logins = os.path.join(self.tmp, "logins")
        folder = stubs(os.path.join(self.tmp, "stubs"), {
            "tailscale": "#!/bin/sh\ncat <<'JSON'\n" + tailscale_json(TAILNET) + "\nJSON\n",
            "ssh": f"#!/bin/sh\n[ \"$1\" = -G ] && exit 0\necho \"$*\" >> '{logins}'\nexit 0\n",
            "route": "#!/bin/sh\nexit 68\n"})
        set_env(self, PATH=f"{folder}:/usr/bin:/bin")
        set_attrs(self, networks, here=lambda: {"tailscale": os.path.join(folder, "tailscale"), "netbird": None,
                                                "zerotier": None, "wireguard": None})
        listed = os.path.join(self.tmp, "machines.txt")
        with open(listed, "w") as f:
            f.write(f"lumen-api | root{AT}lumen-api.tail0000.ts.net | linux\n"
                    f"harbor-web | root{AT}harbor-web.tail0000.ts.net | linux\n")
        vps = ["vps-edge", "root" + AT + "vps-edge.tail0000.ts.net"]

        def look(*more):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(networks.main(["networks.py", "here", listed, *more]), 0)
            return {one["name"]: one for one in json.loads(out.getvalue())["machines"]}
        self.assertEqual(list(look(*vps)), ["lumen-api", "harbor-web", "vps-edge"])
        self.assertEqual(list(look(*vps, "--login")), ["lumen-api", "harbor-web", "vps-edge"])
        self.assertFalse(os.path.exists(logins))
        found = look("--login", *vps)
        options = " ".join(networks.LOGIN_OPTIONS)
        with open(logins) as f:            # harbor-web is offline on Tailscale: no login
            self.assertEqual(f.read().splitlines(), [f"{options} -- root{AT}lumen-api.tail0000.ts.net exit",
                                                     f"{options} -- root{AT}vps-edge.tail0000.ts.net exit"])
        self.assertEqual((found["lumen-api"]["why"], type(found["lumen-api"]["figures"]["login_ms"])), (None, int))
        self.assertEqual(found["harbor-web"]["why"]["key"], "machines.why_offline")
        # the options are src/remote.sh's SSH_OPTS: nothing forwarded, no question asked
        with open(os.path.join(PACKAGE, "src", "remote.sh"), encoding="utf-8") as f:
            remote = f.read()
        start = remote.index("SSH_OPTS=(") + len("SSH_OPTS=(")
        self.assertEqual(tuple(shlex.split(remote[start:remote.index(")", start)])), networks.LOGIN_OPTIONS)

    def test_each_machine_carries_its_key_from_the_list(self):
        # the TUI's Machines view shows it (cut); one of the app's own, or a line with none, has none
        folder = stubs(os.path.join(self.tmp, "stubs"), {"route": "#!/bin/sh\nexit 68\n"})
        set_env(self, PATH=f"{folder}:/usr/bin:/bin")
        set_attrs(self, networks, here=lambda: dict.fromkeys(networks.CLIENTS))
        listed, key = os.path.join(self.tmp, "machines.txt"), "SHA256:Qm9vZ0x1" + "b" * 31 + "a7Fk"
        with open(listed, "w") as f:
            f.write(f"build-01 | root{AT}198.51.100.30 | linux | {key}\nlab-pi | pi{AT}lab-pi.local | linux\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            networks.main(["networks.py", "here", listed, "vps-edge", "root" + AT + "203.0.113.40"])
        found = {one["name"]: one["key"] for one in json.loads(out.getvalue())["machines"]}
        self.assertEqual(found, {"build-01": key, "lab-pi": None, "vps-edge": None})

    def test_a_network_offers_the_computers_its_import_would_that_are_not_on_the_list(self):
        odd = {"exit-node": ("100.115.92.20", {"Location": {"Country": "Sweden"}}),
               "zz-guest": ("100.115.92.21", {"ShareeNode": True}),
               "dev-phone": ("100.115.92.22", {"OS": "iOS"}),
               "dev-tv": ("100.115.92.23", {"OS": "tvOS"}),
               "reef-mac": ("100.115.92.24", {"OS": "macOS"})}
        on = clients(tailscale=tailscale_json({**TAILNET, **odd}))
        # Tailscale's computers alone, as its import offers them; one any route of the list reaches is not offered
        self.assertEqual(networks.offered("tailscale", on["tailscale"], LISTED), ["reef-mac", "vps-edge"])
        # NetBird tells no system: each machine it lists that the list does not have (tidepool is on it)
        self.assertEqual(networks.offered("netbird", on["netbird"], LISTED), ["dev-phone", "harbor-web", "kelp-ci"])
        # a network that is not on offers none; nor does one without names (ZeroTier, the local network)
        self.assertEqual(networks.offered("netbird", clients(netbird=None)["netbird"], LISTED), [])
        self.assertEqual(networks.offered("zerotier", on["zerotier"], LISTED), [])
        self.assertEqual(networks.offered("local", None, LISTED), [])


if __name__ == "__main__":
    unittest.main()
