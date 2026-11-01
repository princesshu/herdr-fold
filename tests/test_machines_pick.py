"""Tests for machines.sh pick (installer step 8) and new (Ctrl+B, Shift+M) in a pty with fake ssh, Tailscale and herdr:
~/.ssh/config, Tailscale, then by hand; `new` sets up only what it added; a Host's own address goes through that Host.
"""
import os
import shutil
import tempfile
import unittest

from support import copy_package, run_in_terminal, stubs

SSH_CONFIG = """Host alpha
  HostName alpha.example
  User root

Host beta
  HostName beta.example
  User root

Host srv
  HostName server.tail0000.ts.net
"""
FAKE_SSH = """#!/bin/sh
while [ $# -gt 0 ]; do case "$1" in -o) shift 2 ;; -*) shift ;; *) break ;; esac; done
case "$*" in
  *"uname -s"*) case "$*" in *mac-mini*) echo Darwin ;; *) echo Linux ;; esac ;;
esac
exit 0
"""
TAILSCALE = """#!/bin/sh
cat <<'JSON'
{"Peer": {
  "a": {"DNSName": "mac-mini.tail0000.ts.net.", "OS": "macOS", "Online": true, "TailscaleIPs": ["100.115.92.5"]},
  "b": {"DNSName": "server.tail0000.ts.net.", "OS": "linux", "Online": true, "TailscaleIPs": ["100.115.92.6"]}
}}
JSON
"""
# a machine typed in by hand: its key is not known yet, and its fingerprint is shown before the first connection. Like
# the real one, it answers with every key type unless asked for some (-t), one line each
SSH_KEYSCAN = """#!/bin/sh
types=rsa,ecdsa,ed25519
while [ $# -gt 1 ]; do case "$1" in -t) types=$2; shift 2 ;; -T) shift 2 ;; *) shift ;; esac; done
case ",$types," in *,rsa,*) echo "$1 ssh-rsa AAAAB3NzaC1yc2EFakeRsaKeyForTests" ;; esac
case ",$types," in *,ecdsa,*) echo "$1 ecdsa-sha2-nistp256 AAAAE2VjZHNhFakeEcdsaKeyForTests" ;; esac
case ",$types," in *,ed25519,*) echo "$1 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFakeKeyForTests" ;; esac
"""
SSH_KEYGEN = """#!/bin/sh
case "$1" in
  -F) exit 1 ;;
  -lf) grep -q . && echo "256 SHA256:FakeFingerprintForTests 192.0.2.9 (ED25519)" ;;
esac
"""
HERDR = ("#!/bin/sh\necho \"herdr $*\" >> \"$HOME/herdr-calls\"\n"
         "[ \"$*\" = \"machine list --json\" ] && echo '[]'\nexit 0\n")


class Step8(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(os.path.join(self.home, ".ssh"))
        with open(os.path.join(self.home, ".ssh", "id_ed25519"), "w"):        # has a key: no key question
            pass
        os.makedirs(os.path.join(self.home, ".config", "herdr-fold"))
        with open(os.path.join(self.home, ".ssh", "config"), "w") as f:
            f.write(SSH_CONFIG)
        with open(os.path.join(self.home, ".config", "herdr-fold", "machines.txt"), "w") as f:
            f.write("beta | beta | linux\n")                     # imported by an earlier run
        self.pkg = copy_package(os.path.join(self.tmp, "pkg"))
        self.stubs = stubs(os.path.join(self.tmp, "stubs"), {"ssh": FAKE_SSH, "tailscale": TAILSCALE, "herdr": HERDR,
                                                              "ssh-keyscan": SSH_KEYSCAN, "ssh-keygen": SSH_KEYGEN})

    def run_questions(self, answers, command="pick"):
        """The questions of ./machines.sh COMMAND (step 8: pick), answered in order; returns the questions it asked —
        and where it got stuck, if it waits for more answers than given. What it showed: self.shown."""
        answers, prompts = list(answers), []

        def answer(line):
            if not answers:
                return None
            prompts.append(line.strip())
            return answers.pop(0)
        self.shown, ended = run_in_terminal(["/bin/bash", os.path.join(self.pkg, "machines.sh"), command],
                                            {"PATH": f"{self.stubs}:/usr/bin:/bin", "TERM": "dumb", "HOME": self.home,
                                             "USER": "dev"}, answer, timeout=20, idle=0.3)
        if not ended:
            prompts.append("STUCK AT: " + self.shown.rstrip("\n").rsplit("\n", 1)[-1].strip())
        return prompts

    def listed(self):
        with open(os.path.join(self.home, ".config", "herdr-fold", "machines.txt")) as f:
            rows = [line for line in f if line.strip() and not line.lstrip().startswith("#")]
        return sorted(tuple(c.strip() for c in row.split("|")) for row in rows)

    def test_the_questions_come_in_order(self):
        prompts = self.run_questions(["y", "y", "n",               # ~/.ssh/config: yes; alpha, beta (drop it)
                                      "y", "y", "", "y",           # Tailscale: yes; mac-mini, its user; srv
                                      "y", "", "192.0.2.9", "y", "n"])  # by hand: user, address, its key; another
        self.assertEqual(prompts, [
            "Import machines from ~/.ssh/config? [y/N]",
            "Import alpha (root@alpha.example)? [y/N]",
            "Import beta (root@beta.example)? — already imported [Y/n]",
            "Import machines from your Tailscale network? [y/N]",
            "Import mac-mini (macos, mac-mini.tail0000.ts.net)? [y/N]",
            "user [dev]:",                                     # this Mac's own user name
            "Import srv (linux, server.tail0000.ts.net)? [y/N]",
            "Add a machine by hand? [y/N]",
            "user [root]:",
            "IP address or host name:",
            "Trust this ED25519 key of 192.0.2.9 (compare it with the machine's own)? [y/N]",
            "Add another machine? [y/N]",
        ])
        self.assertEqual(self.listed(), [("192.0.2.9", "root@192.0.2.9", "linux"), ("alpha", "alpha", "linux"),
                                         ("mac-mini", "dev@mac-mini.tail0000.ts.net", "macos"),
                                         ("srv", "srv", "linux")])

    def test_a_host_named_as_on_the_tailscale_network_goes_on_under_that_name(self):
        # its HostName another address of the machine (a public name): the ~/.ssh/config step leaves it to the
        # Tailscale step, which takes it with that file's user and key, not with a user asked for at its tailnet
        # address
        with open(os.path.join(self.home, ".ssh", "config"), "w") as f:
            f.write("Host server\n  HostName server.example\n  User dev\n")
        prompts = self.run_questions(["y", "y", "", "y", ""])     # ~/.ssh/config; Tailscale: mac-mini no, server
        self.assertEqual(prompts, ["Import machines from ~/.ssh/config? [y/N]",
                                   "Import machines from your Tailscale network? [y/N]",
                                   "Import mac-mini (macos, mac-mini.tail0000.ts.net)? [y/N]",
                                   "Import server (linux, dev@server.example)? [y/N]",       # where it connects
                                   "Add a machine by hand? [y/N]"])
        self.assertEqual(self.listed(), [("beta", "beta", "linux"), ("server", "server", "linux")])

    def test_a_listed_address_a_host_names_goes_through_that_host_unasked(self):
        # listed at its address (a list written by hand): ssh then takes the file's key and options, and the list
        # shows the Host's name; one that only looks alike stays as it is
        with open(os.path.join(self.home, ".ssh", "config"), "w") as f:
            f.write("Host server\n  HostName server.example\n  User dev\n\nHost other\n  HostName other.example\n")
        with open(os.path.join(self.home, ".config", "herdr-fold", "machines.txt"), "w") as f:
            f.write("# my machines\nsrv | dev@server.example | linux\nold | root@other.example | linux\n")
        self.run_questions(["", "", ""])
        self.assertEqual(self.listed(), [("old", "root@other.example", "linux"), ("srv", "server", "linux")])
        self.assertIn("srv: through its ~/.ssh/config entry from now on", self.shown)
        with open(os.path.join(self.home, ".config", "herdr-fold", "machines.txt")) as f:
            self.assertEqual(f.read().splitlines()[0], "# my machines")                # the rest as it was

    def test_a_host_that_changes_where_ssh_connects_is_left_alone(self):
        # its own port, jump host, proxy or host key name is another endpoint, whose key ssh would take unasked, while
        # the listed address had its fingerprint confirmed: the listed line stays; port 22 changes nothing
        with open(os.path.join(self.home, ".ssh", "config"), "w") as f:
            f.write("Host server\n  HostName server.example\n  User dev\n  Port 2222\n\n"
                    "Host via\n  HostName via.example\n  User dev\n  ProxyJump bastion\n\n"
                    "Host named\n  HostName named.example\n  User dev\n  HostKeyAlias other\n\n"
                    "Host plain\n  HostName plain.example\n  User dev\n  Port 22\n")
        with open(os.path.join(self.home, ".config", "herdr-fold", "machines.txt"), "w") as f:
            f.write("srv | dev@server.example | linux\nvia | dev@via.example | linux\n"
                    "nm | dev@named.example | linux\npl | dev@plain.example | linux\n")
        self.run_questions(["", "", ""])
        self.assertEqual(self.listed(), [("nm", "dev@named.example", "linux"), ("pl", "plain", "linux"),
                                         ("srv", "dev@server.example", "linux"), ("via", "dev@via.example", "linux")])

    def test_no_to_everything_asks_only_the_three_questions(self):
        prompts = self.run_questions(["", "", ""])
        self.assertEqual(prompts, ["Import machines from ~/.ssh/config? [y/N]",
                                   "Import machines from your Tailscale network? [y/N]",
                                   "Add a machine by hand? [y/N]"])
        self.assertEqual(self.listed(), [("beta", "beta", "linux")])

    def herdr_calls(self):
        try:
            with open(os.path.join(self.home, "herdr-calls")) as f:
                return f.read().splitlines()
        except OSError:
            return []

    def test_new_sets_up_only_the_machine_it_added(self):
        prompts = self.run_questions(["", "", "y", "", "192.0.2.9", "y", "n", " "], command="new")
        self.assertEqual(prompts[-1], "Press any key to exit.")       # the window stays open until then
        self.assertEqual(self.listed(), [("192.0.2.9", "root@192.0.2.9", "linux"), ("beta", "beta", "linux")])
        added = [call for call in self.herdr_calls() if call.startswith("herdr machine add")]
        self.assertEqual(added, ["herdr machine add root@192.0.2.9 --label 192.0.2.9"])     # beta is left alone

    def known_hosts(self):
        try:
            with open(os.path.join(self.home, ".ssh", "known_hosts")) as f:
                return f.read().splitlines()
        except OSError:
            return []

    def outside(self):
        try:
            with open(os.path.join(self.home, ".local", "state", "herdr-fold", "outside.txt")) as f:
                return f.read().splitlines()
        except OSError:
            return []

    def test_the_confirmed_key_is_the_one_ssh_trusts(self):
        # only the ED25519 key, the one the docs have you compare: another type the machine (or someone between)
        # shows is never trusted with it
        self.run_questions(["", "", "y", "", "192.0.2.9", "y", "n"])
        self.assertEqual(self.known_hosts(), ["192.0.2.9 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFakeKeyForTests"])

    def test_a_machine_that_shows_no_key_is_not_added(self):
        # no answer to the key scan (or no ED25519 key): ssh would trust whatever answers next, so it stops there
        stubs(self.stubs, {"ssh-keyscan": "#!/bin/sh\nexit 0\n"})
        prompts = self.run_questions(["", "", "y", "", "192.0.2.9", "n"])
        self.assertNotIn("Trust this ED25519 key of 192.0.2.9 (compare it with the machine's own)? [y/N]", prompts)
        self.assertIn("192.0.2.9 did not show its ED25519 key", self.shown)
        self.assertEqual(self.listed(), [("beta", "beta", "linux")])
        self.assertEqual(self.known_hosts(), [])
        self.assertEqual(self.outside(), [])

    def test_a_trusted_key_is_recorded_for_the_uninstaller(self):
        self.run_questions(["", "", "y", "", "192.0.2.9", "y", "n"])
        self.assertEqual(self.outside(), ["known-host 192.0.2.9"])

    def test_the_fingerprint_shows_before_the_question(self):
        self.run_questions(["", "", "y", "", "192.0.2.9", "y", "n"])
        shown = self.shown.index("SHA256:FakeFingerprintForTests")
        self.assertLess(shown, self.shown.index("Trust this ED25519 key of 192.0.2.9"))

    def test_enter_refuses_the_key_and_adds_nothing(self):
        # trusting a key is a typed yes, after comparing it: Enter on its own is no
        prompts = self.run_questions(["", "", "y", "", "192.0.2.9", "", "n"])
        self.assertIn("Trust this ED25519 key of 192.0.2.9 (compare it with the machine's own)? [y/N]", prompts)
        self.assertEqual(self.listed(), [("beta", "beta", "linux")])
        self.assertEqual(self.known_hosts(), [])
        self.assertEqual(self.outside(), [])

    def test_a_clashing_name_by_hand_gets_a_suffix_and_a_listed_address_is_not_added_twice(self):
        with open(os.path.join(self.home, ".config", "herdr-fold", "machines.txt"), "a") as f:
            f.write("web | root@web.a.example | linux\n")
        prompts = self.run_questions(["", "", "y", "", "web.b.example", "y", "y",      # web.b: a new machine named web
                                      "", "web.b.example", "n"])                        # the same address again
        self.assertEqual(self.listed(), [("beta", "beta", "linux"), ("web", "root@web.a.example", "linux"),
                                         ("web-2", "root@web.b.example", "linux")])
        self.assertEqual(prompts.count("Trust this ED25519 key of web.b.example (compare it with the machine's own)? "
                                       "[y/N]"), 1)

    def test_new_without_a_new_machine_sets_up_nothing(self):
        prompts = self.run_questions(["", "", "", " "], command="new")
        self.assertEqual(prompts[-1], "Press any key to exit.")
        self.assertEqual([call for call in self.herdr_calls() if call.startswith("herdr machine add")], [])


if __name__ == "__main__":
    unittest.main()
