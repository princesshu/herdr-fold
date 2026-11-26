"""Tests for core/networks.py: what a network says of its machines, read through its own command within a time limit of
its own: NetBird's peers by name, its state told apart (off, signed out, its sign-in expired, no management server),
every name and address checked before anything is offered."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from support import FAKE_NETBIRD, PACKAGE, netbird_status, set_attrs, set_env, stubs

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


if __name__ == "__main__":
    unittest.main()
