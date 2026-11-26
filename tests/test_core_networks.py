"""Tests for core/networks.py: what a network says of its machines, read through its own command within a time limit of
its own: NetBird's peers by name, its state told apart, and the machines announcing SSH on the local network by their
.local name, this Mac left out; every name and address checked before anything is offered."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from support import (DNS_SD_FOUND, FAKE_DNS_SD, FAKE_NETBIRD, FAKE_SCUTIL, PACKAGE, dns_sd_name, fake_dns_sd,
                     netbird_status, set_attrs, set_env, stubs)

sys.path.insert(0, os.path.join(PACKAGE, "core"))
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
        self.assertEqual(self.peers("down"), {"state": "off", "self_ip": None, "peers": []})
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
        self.assertIsNone(networks.bounded([os.path.join(self.tmp, "nothing-here")], 1))

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
        self.assertEqual(found, {"state": "on", "self_ip": None, "peers": [peer("lab-pi", None, None)]})
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


if __name__ == "__main__":
    unittest.main()
