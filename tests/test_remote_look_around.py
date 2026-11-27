"""Tests for remote/look-around.py, which a prepared machine runs for ./machines.sh through: its own Tailscale and
NetBird peers, the machines announcing SSH next to it and its ~/.ssh/config Hosts in one JSON document, each command
read within its own time limit and killed with all it started after it. Run here, with stand-ins on PATH."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from support import (FAKE_SCUTIL, MULLVAD_NODE, PACKAGE, fake_dns_sd, fake_netbird, set_attrs, set_env, stubs,
                     tailscale_json)

SCRIPT = os.path.join(PACKAGE, "remote", "look-around.py")
SPEC = importlib.util.spec_from_file_location("look_around", SCRIPT)
LOOK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LOOK)

# lumen-api's tailnet: two machines of its own, then none to offer: a Mullvad exit node, a sharee's node, an expired one
# and a phone
TAILNET = tailscale_json({"ci-runner": ("100.115.92.40", {}), "harbor-web": ("100.115.92.11", {"Online": False}),
                          "exit": ("100.115.92.50", {"Location": {"Country": "Nowhere"}}),
                          "guest": ("100.115.92.51", {"ShareeNode": True}),
                          "old": ("100.115.92.52", {"Expired": True}), "phone": ("100.115.92.53", {"OS": "iOS"})})
TAILNET = TAILNET.replace("exit.tail0000.ts.net.", MULLVAD_NODE + ".")
# avahi-browse -tprkl as Linux's answers: an instance seen (+), then resolved (=); it waits for more, never ending
AVAHI = """#!/bin/sh
sleep 30 & echo $! >> "${AVAHI_PIDS:-/dev/null}"
printf '%s\\n' '+;eth0;IPv4;db-02;_ssh._tcp;local' \\
  '=;eth0;IPv4;db-02;_ssh._tcp;local;db-02.local;192.0.2.31;22;' \\
  '=;eth0;IPv4;Dev\\039s\\032MacBook;_ssh._tcp;local;devs-macbook.local;192.0.2.32;22;'
wait
"""
SSH_CONFIG = """Host build-01
  HostName 198.51.100.30
  User root

Host *.internal
  User ops

Host github.com
  User git

Host via-bastion
  HostName 198.51.100.40
  ProxyJump bastion

Host vault
  HostName 198.51.100.50
  CertificateFile ~/.ssh/vault-cert.pub

Include conf.d/*
"""


class LookAround(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(os.path.join(self.home, ".ssh", "conf.d"))
        with open(os.path.join(self.home, ".ssh", "config"), "w") as f:
            f.write(SSH_CONFIG)
        with open(os.path.join(self.home, ".ssh", "conf.d", "more"), "w") as f:
            f.write("Host kelp-ci\n  HostName kelp-ci.example.com\n  Port 2222\n  IdentityFile ~/.ssh/id_ed25519_sk\n")
        netbird = fake_netbird((("tidepool", "100.115.93.10", "Connected", "P2P", 3000000),))
        self.stubs = stubs(os.path.join(self.tmp, "stubs"), {
            "tailscale": "#!/bin/sh\ncat <<'JSON'\n" + TAILNET + "\nJSON\n", "netbird": netbird, "avahi-browse": AVAHI,
            "dns-sd": fake_dns_sd((("db-02", "db-02.local.", 22), ("this-mac", "this-mac.local.", 22))),
            "scutil": FAKE_SCUTIL})
        set_env(self, HOME=self.home, PATH=f"{self.stubs}:/usr/bin:/bin")
        set_attrs(self, LOOK, PLACES={})                    # the stand-ins alone: never a client installed here

    def pids(self, name):
        path = os.path.join(self.tmp, name)
        set_env(self, **{name: path})
        return path

    def gone(self, path):
        with open(path) as f:
            for child in [int(line) for line in f]:
                for _ in range(40):
                    try:
                        os.kill(child, 0)
                    except ProcessLookupError:
                        break
                    time.sleep(0.05)
                else:
                    self.fail("what a stand-in started still runs")

    def test_each_list_is_read_bounded(self):
        # Linux: NetBird's daemon never answers and avahi-browse never ends; each is read for its own seconds alone,
        # all at once, then killed with all it started
        set_attrs(self, LOOK, PLATFORM="linux", SECONDS=0.5)
        netbird, avahi = self.pids("NETBIRD_PIDS"), self.pids("AVAHI_PIDS")
        set_env(self, NETBIRD_STATE="slow")
        start = time.monotonic()
        sees = LOOK.look()
        self.assertLess(time.monotonic() - start, 2.5)
        self.gone(netbird)
        self.gone(avahi)
        self.assertEqual(sees["netbird"], "off")
        self.assertEqual(sees["tailscale"], [
            {"dns": "ci-runner.tail0000.ts.net", "ips": ["100.115.92.40"], "os": "linux", "online": True},
            {"dns": "harbor-web.tail0000.ts.net", "ips": ["100.115.92.11"], "os": "linux", "online": False}])
        self.assertEqual(sees["local"], [{"host": "db-02.local", "port": 22, "instance": "db-02"},
                                         {"host": "devs-macbook.local", "port": 22, "instance": "Dev's MacBook"}])
        # its ~/.ssh/config: one machine a Host each, never a pattern, a git host or one with a jump of its own; one
        # that logs in with a certificate or a security key says so
        self.assertEqual(sees["ssh_config"], [
            {"alias": "build-01", "host": "198.51.100.30", "user": "root", "port": None, "cert": False},
            {"alias": "vault", "host": "198.51.100.50", "user": None, "port": None, "cert": True},
            {"alias": "kelp-ci", "host": "kelp-ci.example.com", "user": None, "port": 2222, "cert": True}])
        # NetBird answering: its peers by name
        set_env(self, NETBIRD_STATE="connected")
        self.assertEqual(LOOK.look()["netbird"],
                         [{"fqdn": "tidepool.netbird.cloud", "ip": "100.115.93.10", "status": "Connected"}])
        # macOS, as the Mac runs it: python3 reads it from its input and prints one document; dns-sd's browse is
        # heard for its seconds, each machine looked up, the machine itself left out
        with open(SCRIPT, "rb") as f:
            done = subprocess.run(["/usr/bin/python3", "-"], stdin=f, capture_output=True, timeout=30,
                                  env={"HOME": self.home, "PATH": f"{self.stubs}:/usr/bin:/bin",
                                       "NETBIRD_STATE": "connected"})
        sees = json.loads(done.stdout)
        self.assertEqual((sees["local"], len(sees["tailscale"]), len(sees["netbird"]), len(sees["ssh_config"])),
                         ([{"host": "db-02.local", "port": 22, "instance": "db-02"}], 2, 1, 3), done.stderr)

    def test_a_missing_avahi_is_said_not_fatal(self):
        # a Linux machine without avahi-browse: the local list is a word, the others are read as ever; without a
        # client, its word too
        set_attrs(self, LOOK, PLATFORM="linux")
        os.remove(os.path.join(self.stubs, "avahi-browse"))
        os.remove(os.path.join(self.stubs, "netbird"))
        sees = LOOK.look()
        self.assertEqual((sees["local"], sees["netbird"]), ("skipped", "missing"))
        self.assertEqual(len(sees["tailscale"]), 2)
        self.assertEqual(sees["ssh_config"][0]["alias"], "build-01")


if __name__ == "__main__":
    unittest.main()
