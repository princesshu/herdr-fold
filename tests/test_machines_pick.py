"""Tests for machines.sh pick (installer step 8) and new (Ctrl+B, Shift+M) in a pty with fake ssh, Tailscale, NetBird
and herdr: any network works, then ~/.ssh/config, Tailscale (only what can be yours), NetBird, by hand; `new` sets up
only what it added; a Host's own address goes through that Host; a listed machine's host key makes a route of it."""
import os
import shutil
import subprocess
import tempfile
import unittest

from support import (FAKE_NETBIRD, FAKE_TAILSCALE, TAILNET_HOST_KEY_FINGERPRINT, catalog_text, copy_package,
                     fake_netbird, host_key, run_in_terminal, stubs)

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
  *dev-phone*) echo "ssh: connect to host dev-phone.netbird.cloud port 22: Connection refused" >&2; exit 255 ;;
  *"uname -s"*) case "$*" in *mac-mini*) echo Darwin ;; *) echo Linux ;; esac ;;
esac
exit 0
"""
# a machine typed in by hand: its key is not known yet, and its fingerprint is shown before the first connection. Like
# the real one, it answers with every key type unless asked for some (-t), one line each; a tailnet's machines do not
SSH_KEYSCAN = """#!/bin/sh
types=rsa,ecdsa,ed25519
while [ $# -gt 1 ]; do case "$1" in -t) types=$2; shift 2 ;; -T) shift 2 ;; *) shift ;; esac; done
case "$1" in *.ts.net) exit 0 ;; esac
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
FAKE_FINGERPRINT = "SHA256:FakeFingerprintForTests"        # SSH_KEYGEN's for any key: one added by hand keeps it


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
        self.stubs = stubs(os.path.join(self.tmp, "stubs"), {"ssh": FAKE_SSH, "tailscale": FAKE_TAILSCALE,
                                                              "herdr": HERDR, "ssh-keyscan": SSH_KEYSCAN,
                                                              "ssh-keygen": SSH_KEYGEN})

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
                                      "y", "y", "", "y", "",       # Tailscale: mac-mini, its user; srv; not vps-edge
                                      "y", "", "192.0.2.9", "y", "n"])  # by hand: user, address, its key; another
        self.assertEqual(prompts, [
            "Import machines from ~/.ssh/config? [y/N]",
            "Import alpha (root@alpha.example)? [y/N]",
            "Import beta (root@beta.example)? — already imported [Y/n]",
            "Import machines from your Tailscale network? [y/N]",
            "Import mac-mini (macos, mac-mini.tail0000.ts.net)? [y/N]",
            "user [dev]:",                                     # this Mac's own user name
            "Import srv (linux, server.tail0000.ts.net)? [y/N]",
            "Import vps-edge (linux, vps-edge.tail0000.ts.net)? [y/N]",
            "Add a machine by hand? [y/N]",
            "user [root]:",
            "IP address or host name:",
            "Trust this ED25519 key of 192.0.2.9 (compare it with the machine's own)? [y/N]",
            "Add another machine? [y/N]",
        ])
        self.assertEqual(self.listed(), [("192.0.2.9", "root@192.0.2.9", "linux", FAKE_FINGERPRINT),
                                         ("alpha", "alpha", "linux"),
                                         ("mac-mini", "dev@mac-mini.tail0000.ts.net", "macos"),
                                         ("srv", "srv", "linux")])

    def test_a_host_named_as_on_the_tailscale_network_goes_on_under_that_name(self):
        # its HostName another address of the machine (a public name): the ~/.ssh/config step leaves it to the
        # Tailscale step, which takes it with that file's user and key, not with a user asked for at its tailnet
        # address
        with open(os.path.join(self.home, ".ssh", "config"), "w") as f:
            f.write("Host server\n  HostName server.example\n  User dev\n")
        prompts = self.run_questions(["y", "y", "", "y", "", ""])  # ~/.ssh/config; Tailscale: server alone
        self.assertEqual(prompts, ["Import machines from ~/.ssh/config? [y/N]",
                                   "Import machines from your Tailscale network? [y/N]",
                                   "Import mac-mini (macos, mac-mini.tail0000.ts.net)? [y/N]",
                                   "Import server (linux, dev@server.example)? [y/N]",       # where it connects
                                   "Import vps-edge (linux, vps-edge.tail0000.ts.net)? [y/N]",
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

    def test_the_questions_start_with_the_line_any_network_works(self):
        # no network is needed above another: said once, as a note, before the first question
        prompts = self.run_questions(["", "", ""])
        line = "      " + catalog_text("machines.any_network") + "\n"
        self.assertEqual(self.shown.count(line), 1)
        self.assertEqual(prompts[0], "Import machines from ~/.ssh/config? [y/N]")
        self.assertLess(self.shown.index(line), self.shown.index(prompts[0]))

    def tailscale_prompts(self):
        """The questions with a yes to the Tailscale network alone, and no to each machine it offers."""
        return self.run_questions(["", "y"] + [""] * 6)

    def test_an_exit_node_of_mullvad_is_not_offered(self):
        # Mullvad's exit nodes (their Location, their domain) are Mullvad's servers, never a machine to add
        prompts = self.tailscale_prompts()
        self.assertEqual([p for p in prompts if "zz-tst-wg-001" in p], [])
        self.assertIn(catalog_text("machines.left_out_exit_node"), self.shown)

    def test_a_node_of_someone_the_tailnet_is_shared_to_is_not_offered(self):
        # in the list only because it may connect to the machine of yours shared with its owner
        prompts = self.tailscale_prompts()
        self.assertEqual([p for p in prompts if "guest-laptop" in p], [])
        self.assertIn(catalog_text("machines.left_out_shared_node"), self.shown)

    def test_an_expired_node_is_not_offered_and_counted(self):
        # a line after the questions counts what was left out; never the phone, which no computer was offered from
        prompts = self.tailscale_prompts()
        self.assertEqual([p for p in prompts if "kelp-ci" in p], [])
        left_out = catalog_text("machines.tailscale_skipped", "3", ", ".join(
            [catalog_text("machines.left_out_exit_node"), catalog_text("machines.left_out_shared_node"),
             catalog_text("machines.left_out_expired_node")]))
        self.assertIn("[-] " + left_out + "\n", self.shown)
        self.assertLess(self.shown.index("new machine(s) on the list"), self.shown.index(left_out))

    def test_a_tagged_server_is_offered(self):
        # servers are often tagged (the tailnet's, not a person's): a machine of yours as any other
        prompts = self.tailscale_prompts()
        self.assertEqual(prompts[2:6], ["Import mac-mini (macos, mac-mini.tail0000.ts.net)? [y/N]",
                                        "Import srv (linux, server.tail0000.ts.net)? [y/N]",
                                        "Import vps-edge (linux, vps-edge.tail0000.ts.net)? [y/N]",
                                        "Add a machine by hand? [y/N]"])

    def test_netbird_is_asked_after_tailscale_and_offers_its_peers(self):
        # NetBird tells no OS: it is read by logging in, so the phone, which answers no SSH, is not added
        stubs(self.stubs, {"netbird": FAKE_NETBIRD})
        prompts = self.run_questions(["", "", "y",                 # not ~/.ssh/config nor Tailscale; NetBird
                                      "y", "", "", "", "y", "",    # dev-phone and its user; tidepool and its user
                                      ""])                         # not by hand
        self.assertEqual(prompts, ["Import machines from ~/.ssh/config? [y/N]",
                                   "Import machines from your Tailscale network? [y/N]",
                                   "Import machines from your NetBird network? [y/N]",
                                   "Import dev-phone (dev-phone.netbird.cloud)? [y/N]",
                                   "user [root]:",
                                   "Import harbor-web (harbor-web.netbird.cloud)? [y/N]",
                                   "Import kelp-ci (kelp-ci.netbird.cloud)? [y/N]",
                                   "Import tidepool (tidepool.netbird.cloud)? [y/N]",
                                   "user [root]:",
                                   "Add a machine by hand? [y/N]"])
        self.assertIn(catalog_text("machines.ssh_refused", "root" + AT + "dev-phone.netbird.cloud"), self.shown)
        self.assertEqual(self.listed(), [("beta", "beta", "linux"),
                                         ("tidepool", "root" + AT + "tidepool.netbird.cloud", "linux")])

    def test_netbird_signed_out_says_so_and_offers_nothing(self):
        stubs(self.stubs, {"netbird": FAKE_NETBIRD.replace('"${NETBIRD_STATE:-connected}"', "signed_out")})
        prompts = self.run_questions(["", "", "y", ""])
        self.assertEqual(prompts[3:], ["Add a machine by hand? [y/N]"])
        self.assertIn("[!] " + catalog_text("machines.netbird_signed_out") + "\n", self.shown)

    def test_a_tailnet_machine_comes_with_its_host_key_fingerprint(self):
        # Tailscale's sshHostKeys, when it gives them: the ED25519 one (a machine's key), as ssh-keygen -l prints it
        done = subprocess.run(["bash", "-c", ". ./machines.sh; tailnet_peers"], cwd=self.pkg, capture_output=True,
                              text=True, env={"PATH": f"{self.stubs}:/usr/bin:/bin", "HOME": self.home}, timeout=20)
        self.assertEqual(done.stdout.splitlines(), [
            "mac-mini|mac-mini.tail0000.ts.net|macos|online|100.115.92.5|",
            "server|server.tail0000.ts.net|linux|online|100.115.92.6|",
            "vps-edge|vps-edge.tail0000.ts.net|linux|online|100.115.92.7|" + TAILNET_HOST_KEY_FINGERPRINT], done.stderr)

    def herdr_calls(self):
        try:
            with open(os.path.join(self.home, "herdr-calls")) as f:
                return f.read().splitlines()
        except OSError:
            return []

    def test_new_sets_up_only_the_machine_it_added(self):
        prompts = self.run_questions(["", "", "y", "", "192.0.2.9", "y", "n", " "], command="new")
        self.assertEqual(prompts[-1], "Press any key to exit.")       # the window stays open until then
        self.assertEqual(self.listed(), [("192.0.2.9", "root@192.0.2.9", "linux", FAKE_FINGERPRINT),
                                         ("beta", "beta", "linux")])
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
                                         ("web-2", "root@web.b.example", "linux", FAKE_FINGERPRINT)])
        self.assertEqual(prompts.count("Trust this ED25519 key of web.b.example (compare it with the machine's own)? "
                                       "[y/N]"), 1)

    def test_an_old_list_still_reads_and_is_not_rewritten_unasked(self):
        # three fields a line, the header of before: read as it is, and written only when a machine is added or changed
        old = ("# Remote machines in herdr (herdr-fold), filled in by the installer; edit by hand if you like. No "
               "passwords or keys\n# here: login uses this Mac's SSH key. Lines:  name | user@machine | os (linux / "
               "macos / windows)\n# my clients\nbeta | beta | linux\nweb  |  root@web.a.example | linux\n")
        path = os.path.join(self.home, ".config", "herdr-fold", "machines.txt")
        with open(path, "w") as f:
            f.write(old)
        self.run_questions(["", "", ""])
        done = subprocess.run(["bash", os.path.join(self.pkg, "machines.sh"), "status"], capture_output=True,
                              text=True, stdin=subprocess.DEVNULL, timeout=60,
                              env={"PATH": f"{self.stubs}:/usr/bin:/bin", "HOME": self.home, "HERDR_FOLD_YES": "1"})
        self.assertIn("== web (root@web.a.example, linux)\n", done.stdout)
        with open(path) as f:
            self.assertEqual(f.read(), old)

    def test_new_without_a_new_machine_sets_up_nothing(self):
        prompts = self.run_questions(["", "", "", " "], command="new")
        self.assertEqual(prompts[-1], "Press any key to exit.")
        self.assertEqual([call for call in self.herdr_calls() if call.startswith("herdr machine add")], [])


AT = "@"                        # a user before a host: put together here, never an e-mail's look
STUDIO_KEY, STUDIO = host_key("FakeHostKeyOfStudio")
# Tailscale with studio (its host key on record) and harbor-web (none); every other answer as Step8's fakes
TWO_ROUTES_TAILSCALE = """#!/bin/sh
cat <<'JSON'
{"Peer": {
  "a": {"DNSName": "harbor-web.tail0000.ts.net.", "OS": "linux", "Online": true, "TailscaleIPs": ["100.115.92.20"]},
  "b": {"DNSName": "studio.tail0000.ts.net.", "OS": "macOS", "Online": true, "TailscaleIPs": ["100.115.92.21"],
        "sshHostKeys": ["%s"]}
}}
JSON
""" % STUDIO_KEY
# studio shows its key at its tailnet name, its NetBird name and its other address; nothing else answers a key scan
TWO_ROUTES_KEYSCAN = """#!/bin/sh
for host; do :; done
case "$host" in 192.0.2.20|studio.tail0000.ts.net|studio.netbird.cloud) echo "$host %s" ;; esac
exit 0
""" % STUDIO_KEY
# NetBird with studio and tidepool (NetBird keeps no host key: a machine's is read from it)
TWO_ROUTES_NETBIRD = fake_netbird((("studio", "100.115.93.21", "Connected", "P2P", 3000000),
                                   ("tidepool", "100.115.93.10", "Idle", "-", 0)))
SILENT_KEYSCAN = "#!/bin/sh\nexit 0\n"             # no machine answers a key scan
# a machine answering with another key than the one Tailscale knows (someone between, or the wrong machine)
OTHER_KEY, _ = host_key("FakeHostKeyOfSomeoneElse")
HARBOR_KEY, _ = host_key("FakeHostKeyOfHarborWeb")
WRONG_KEYSCAN = """#!/bin/sh
for host; do :; done
echo "$host %s"
""" % OTHER_KEY
# OpenSSH's ssh-keygen, its known_hosts the test home's (its own default is the account's, whatever HOME says)
HOME_KEYGEN = """#!/bin/sh
[ "$1" = -F ] && [ $# -eq 2 ] && exec /usr/bin/ssh-keygen -F "$2" -f "$HOME/.ssh/known_hosts"
exec /usr/bin/ssh-keygen "$@"
"""


class TwoRoutes(unittest.TestCase):
    """studio is on the list by its local name, its key known; Tailscale offers it again under its tailnet name."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(os.path.join(self.home, ".ssh"))
        os.makedirs(os.path.join(self.home, ".config", "herdr-fold"))
        with open(os.path.join(self.home, ".ssh", "id_ed25519"), "w"):        # has a key: no key question
            pass
        with open(os.path.join(self.home, ".ssh", "known_hosts"), "w") as f:
            f.write(f"studio.local {STUDIO_KEY}\n")                       # trusted on its first connection
        self.line = f"studio           | dev{AT}studio.local | macos | {STUDIO}\n"
        with open(self.path(".config/herdr-fold/machines.txt"), "w") as f:
            f.write(self.line)
        self.pkg = copy_package(os.path.join(self.tmp, "pkg"))
        self.stubs = stubs(os.path.join(self.tmp, "stubs"), {"ssh": FAKE_SSH, "tailscale": TWO_ROUTES_TAILSCALE,
                                                              "herdr": HERDR, "ssh-keyscan": TWO_ROUTES_KEYSCAN,
                                                              "ssh-keygen": HOME_KEYGEN})

    def path(self, rel):
        return os.path.join(self.home, rel)

    def read(self, rel):
        try:
            with open(self.path(rel)) as f:
                return f.read()
        except FileNotFoundError:
            return None

    def run_questions(self, answers):
        answers, prompts = list(answers), []

        def answer(line):
            if not answers:
                return None
            prompts.append(line.strip())
            return answers.pop(0)
        self.shown, ended = run_in_terminal(["/bin/bash", os.path.join(self.pkg, "machines.sh"), "pick"],
                                            {"PATH": f"{self.stubs}:/usr/bin:/bin", "TERM": "dumb", "HOME": self.home,
                                             "USER": "dev"}, answer, timeout=30, idle=0.3)
        if not ended:
            prompts.append("STUCK AT: " + self.shown.rstrip("\n").rsplit("\n", 1)[-1].strip())
        return prompts

    def studio(self):
        lines = [line for line in self.read(".config/herdr-fold/machines.txt").splitlines()
                 if line.startswith("studio")]
        return [[cell.strip() for cell in line.split("|")] for line in lines]

    SAID = "  studio.tail0000.ts.net is studio, already on the list: also reachable on Tailscale.\n"

    def test_a_candidate_with_a_listed_key_becomes_its_route(self):
        prompts = self.run_questions(["y", "", "", "", ""])     # Tailscale; not harbor-web; the route; the Include
        self.assertEqual(prompts, [
            "Import machines from your Tailscale network? [y/N]",
            "Import harbor-web (linux, harbor-web.tail0000.ts.net)? [y/N]",
            "Add this route? [Y/n]",
            "Add one line at the top of ~/.ssh/config to include them (Include ~/.config/herdr-fold/ssh_config)? [Y/n]",
            "Add a machine by hand? [y/N]"])
        self.assertIn(self.SAID, self.shown)
        self.assertIn("0 new machine(s) on the list, 1 already there: studio", self.shown)
        # one machine, its two routes, the local one first; herdr has not connected it yet: its own Host from now on
        self.assertEqual(self.studio(), [["studio", "herdr-fold.studio", "macos", STUDIO,
                                          f"local dev{AT}studio.local, tailscale dev{AT}studio.tail0000.ts.net"]])
        self.assertIn("\nHost herdr-fold.studio\n  HostName studio.local\n  User dev\n"
                      "  HostKeyAlias herdr-fold.studio\n", self.read(".config/herdr-fold/ssh_config"))
        self.assertEqual(self.read(".ssh/known_hosts").splitlines()[-1], f"herdr-fold.studio {STUDIO_KEY}")
        self.assertEqual(self.read(".local/state/herdr-fold/outside.txt").splitlines(),
                         ["ssh-include", "known-host herdr-fold.studio"])

    def test_the_include_is_asked_once_and_goes_first_in_the_ssh_config(self):
        theirs = "Host lab-pi\n  HostName 192.0.2.40\n  User pi\n"
        with open(self.path(".ssh/config"), "w") as f:
            f.write(theirs)
        self.run_questions(["", "y", "", "", "", "n"])     # not from ~/.ssh/config; Tailscale: the route, the Include
        # studio's other address, typed in: its key is studio's, so it is a route too, and the Include is not asked
        prompts = self.run_questions(["", "", "y", "", "192.0.2.20", "", "n"])
        self.assertEqual(prompts, ["Import machines from ~/.ssh/config? [y/N]",
                                   "Import machines from your Tailscale network? [y/N]",
                                   "Add a machine by hand? [y/N]", "user [root]:", "IP address or host name:",
                                   "Add this route? [Y/n]", "Add another machine? [y/N]"])
        self.assertIn("  192.0.2.20 is studio, already on the list: also reachable at that address.\n", self.shown)
        config = self.read(".ssh/config")
        self.assertEqual(config, "# herdr-fold: its machines' own Hosts (./uninstall.sh takes these two lines off)\n"
                                 "Include ~/.config/herdr-fold/ssh_config\n\n" + theirs)
        self.assertEqual(self.studio()[0][-1], f"local dev{AT}studio.local, tailscale dev{AT}studio.tail0000.ts.net, "
                                               f"root{AT}192.0.2.20")

    def test_a_key_tailscale_does_not_know_is_refused(self):
        # harbor-web and studio both answer with a key Tailscale's record does not have: neither is added, nor trusted
        harbor = '"TailscaleIPs": ["100.115.92.20"]'
        stubs(self.stubs, {"ssh-keyscan": WRONG_KEYSCAN, "tailscale": TWO_ROUTES_TAILSCALE.replace(
            harbor, f'{harbor}, "sshHostKeys": ["{HARBOR_KEY}"]')})
        prompts = self.run_questions(["y", ""])
        self.assertEqual(prompts, ["Import machines from your Tailscale network? [y/N]",
                                   "Add a machine by hand? [y/N]"])
        self.assertIn("[!] " + catalog_text("machines.key_mismatch", "harbor-web") + "\n", self.shown)
        self.assertIn("[!] " + catalog_text("machines.route_key_mismatch", "studio.tail0000.ts.net", "studio") + "\n",
                      self.shown)                           # studio's route: it must show studio's own key
        self.assertEqual(self.read(".config/herdr-fold/machines.txt"), self.line)
        self.assertEqual(self.read(".ssh/known_hosts"), f"studio.local {STUDIO_KEY}\n")
        self.assertIsNone(self.read(".ssh/config"))

    def test_a_route_needs_the_machine_to_show_the_listed_key_now(self):
        # Tailscale's record is what a peer says of itself: studio's key there is not enough; no answer, no route
        stubs(self.stubs, {"ssh-keyscan": SILENT_KEYSCAN})
        prompts = self.run_questions(["y", "", ""])
        self.assertEqual(prompts, ["Import machines from your Tailscale network? [y/N]",
                                   "Import harbor-web (linux, harbor-web.tail0000.ts.net)? [y/N]",
                                   "Add a machine by hand? [y/N]"])
        unchecked = catalog_text("machines.route_unchecked", "studio.tail0000.ts.net", "studio")
        self.assertIn(f"[-] {unchecked}\n", self.shown)
        self.assertNotIn(self.SAID, self.shown)
        self.assertEqual(self.read(".config/herdr-fold/machines.txt"), self.line)
        self.assertEqual(self.read(".ssh/known_hosts"), f"studio.local {STUDIO_KEY}\n")
        self.assertIsNone(self.read(".ssh/config"))

    def test_a_refused_include_keeps_one_route(self):
        prompts = self.run_questions(["y", "", "", "n", ""])
        self.assertIn("Add this route? [Y/n]", prompts)
        refused = catalog_text("machines.include_refused", "studio")
        self.assertIn(f"[-] {refused}\n", self.shown)
        self.assertEqual(self.read(".config/herdr-fold/machines.txt"), self.line)        # untouched
        self.assertIsNone(self.read(".ssh/config"))
        self.assertIsNone(self.read(".config/herdr-fold/ssh_config"))
        # the no is kept: the next run says it is studio again, and asks neither question
        prompts = self.run_questions(["y", "", ""])
        self.assertEqual(prompts, ["Import machines from your Tailscale network? [y/N]",
                                   "Import harbor-web (linux, harbor-web.tail0000.ts.net)? [y/N]",
                                   "Add a machine by hand? [y/N]"])
        self.assertIn(self.SAID, self.shown)
        self.assertIn(f"[-] {refused}\n", self.shown)

    def test_a_netbird_peer_already_listed_by_key_is_a_route(self):
        stubs(self.stubs, {"netbird": TWO_ROUTES_NETBIRD})
        prompts = self.run_questions(["", "y", "", "", "", ""])  # NetBird; the route; the Include; not tidepool
        self.assertEqual(prompts, [
            "Import machines from your Tailscale network? [y/N]",
            "Import machines from your NetBird network? [y/N]",
            "Add this route? [Y/n]",
            "Add one line at the top of ~/.ssh/config to include them (Include ~/.config/herdr-fold/ssh_config)? [Y/n]",
            "Import tidepool (tidepool.netbird.cloud)? [y/N]",
            "Add a machine by hand? [y/N]"])
        self.assertIn("  studio.netbird.cloud is studio, already on the list: also reachable on NetBird.\n", self.shown)
        self.assertEqual(self.studio(), [["studio", "herdr-fold.studio", "macos", STUDIO,
                                          f"local dev{AT}studio.local, netbird dev{AT}studio.netbird.cloud"]])
        self.assertEqual(self.read(".ssh/known_hosts").splitlines()[-1], f"herdr-fold.studio {STUDIO_KEY}")

    def test_a_netbird_peer_that_shows_no_key_is_never_a_route(self):
        # NetBird's list is what a peer says of itself: studio's name there is no proof; no key shown, no route
        stubs(self.stubs, {"netbird": TWO_ROUTES_NETBIRD, "ssh-keyscan": SILENT_KEYSCAN})
        prompts = self.run_questions(["", "y", "", "", ""])
        self.assertNotIn("Add this route? [Y/n]", prompts)
        self.assertEqual(prompts[-1], "Add a machine by hand? [y/N]")
        self.assertEqual(self.read(".config/herdr-fold/machines.txt"), self.line)
        self.assertEqual(self.read(".ssh/known_hosts"), f"studio.local {STUDIO_KEY}\n")
        self.assertIsNone(self.read(".ssh/config"))


if __name__ == "__main__":
    unittest.main()
