"""Tests for ./machines.sh through, a fake ssh answering with what lumen-api sees: its machines offered, default no,
what it says checked and capped; one behind it always asked about by its key read end to end, this Mac's public key put
there on a yes per machine alone, its Host jumping, forwarding nothing; removing lumen-api asks about those behind."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from support import (FAKE_SCUTIL, PACKAGE, catalog_text, copy_package, host_key, run_in_terminal, stubs,
                     tailscale_json)

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import machines  # noqa: E402
import networks  # noqa: E402

AT = "@"                        # a user before a host: put together here, never an e-mail's look
LUMEN = f"root{AT}lumen-api.tail0000.ts.net"
LUMEN_KEY, LUMEN_FP = host_key("FakeHostKeyOfLumenApi")
BUILD_KEY, BUILD = host_key("FakeHostKeyOfBuild01")
DB_KEY, DB = host_key("FakeHostKeyOfDb02")
CI_KEY, _ = host_key("FakeHostKeyOfCiRunner")
VAULT_KEY, _ = host_key("FakeHostKeyOfVault")
OTHER_KEY, _ = host_key("FakeHostKeyOfSomeoneElse")
MAC_PUBLIC, _ = host_key("FakePublicKeyOfThisMac")
PRIVATE = "-" * 5 + "BEGIN OPENSSH PRIVATE" + " KEY" + "-" * 5 + "\nFakePrivateHalfOfThisMac\n"
# what lumen-api sees: two machines of its ~/.ssh/config (one logging in with a certificate), one next to it, one on
# its tailnet, one on its NetBird network; then none to offer: a tailnet machine this Mac reaches itself, this Mac, its
# own loopback, a machine on the list, a Host whose name is an option
SEES = {"tailscale": [{"dns": "ci-runner.tail0000.ts.net", "ips": ["100.115.92.40"], "os": "linux", "online": True},
                      {"dns": "harbor-web.tail0000.ts.net", "ips": ["100.115.92.11"], "os": "linux", "online": True},
                      {"dns": "this-mac.tail0000.ts.net", "ips": ["100.115.92.1"], "os": "macOS", "online": True}],
        "netbird": [{"fqdn": "tidepool.netbird.cloud", "ip": "100.115.93.10", "status": "Connected"}],
        "local": [{"host": "db-02.local", "port": 22, "instance": "db-02"}],
        "ssh_config": [{"alias": "build-01", "host": "198.51.100.30", "user": "root", "port": None, "cert": False},
                       {"alias": "vault", "host": "198.51.100.50", "user": "ops", "port": None, "cert": True},
                       {"alias": "self", "host": "localhost", "user": None, "port": None, "cert": False},
                       {"alias": "edge", "host": "203.0.113.5", "user": "root", "port": None, "cert": False},
                       {"alias": "-oProxyCommand=sh", "host": "198.51.100.9", "user": None, "port": None,
                        "cert": False}]}
OFFERED = [
    "Import build-01 (198.51.100.30, from lumen-api's ~/.ssh/config) through lumen-api? [y/N]",
    "Import vault (198.51.100.50, from lumen-api's ~/.ssh/config) through lumen-api? [y/N]",
    "Import db-02 (db-02.local, next to lumen-api) through lumen-api? [y/N]",
    "Import ci-runner (ci-runner.tail0000.ts.net, lumen-api's Tailscale) through lumen-api? [y/N]",
    "Import tidepool (tidepool.netbird.cloud, lumen-api's NetBird) through lumen-api? [y/N]"]
INCLUDE_ASK = ("Add one line at the top of ~/.ssh/config to include them (Include ~/.config/herdr-fold/ssh_config)? "
               "[Y/n]")
TRUST = "Trust this ED25519 key of {}, read through lumen-api (compare it with the machine's own)? [y/N]"
COPY = "Put this Mac's public key on {}, through lumen-api's own login? [y/N]"
# ssh as lumen-api and those behind it answer, each call logged in $HOME/ssh-calls: what it sees ($HOME/look.json); a
# key read through it (the none method) from $HOME/keys, where it is asked to be written; a login refused by a machine
# in $HOME/refusing until lumen-api's own login put this Mac's key there
THROUGH_SSH = r"""#!/bin/sh
printf '%s\n' "$*" >> "$HOME/ssh-calls"
jump= alias= known= none=
while [ $# -gt 0 ]; do
  case "$1" in
    -G) exit 0 ;;
    -o) case "$2" in
          ProxyJump=*) jump=${2#ProxyJump=} ;;
          HostKeyAlias=*) alias=${2#HostKeyAlias=} ;;
          UserKnownHostsFile=*) known=${2#UserKnownHostsFile=} ;;
          PreferredAuthentications=none) none=1 ;;
        esac; shift 2 ;;
    -p|-l) shift 2 ;;
    --) shift; break ;;
    -*) shift ;;
    *) break ;;
  esac
done
host=$1; shift
case "$*" in
  *"python3 -"*) cat > /dev/null; cat "$HOME/look.json"; exit 0 ;;
  *authorized_keys*)
    while read -r address name; do
      case "$*" in *" -- $address "*|*" -- ${name:-.} "*) echo "$address" >> "$HOME/copied" ;; esac
    done < "$HOME/refusing"
    exit 0 ;;
esac
if [ -n "$none" ]; then
  key=$(awk -v h="$host" '$1 == h { print $2, $3 }' "$HOME/keys")
  [ -z "$key" ] || printf '%s %s\n' "$alias" "$key" >> "$known"
  echo "$host: Permission denied (publickey)." >&2; exit 255
fi
if [ -n "$jump" ] && awk -v h="$host" '$1 == h { found = 1 } END { exit !found }' "$HOME/refusing" \
    && ! grep -qxF "$host" "$HOME/copied" 2>/dev/null; then
  echo "$host: Permission denied (publickey)." >&2; exit 255
fi
case "$*" in *"uname -s"*) echo Linux ;; esac
exit 0
"""
HERDR = "#!/bin/sh\n[ \"$*\" = \"machine list --json\" ] && echo '[]'\nexit 0\n"
# this Mac's tailnet: lumen-api and harbor-web; its NetBird is down (NETBIRD_STATE)
MAC_TAILNET = tailscale_json({"lumen-api": ("100.115.92.10", {}), "harbor-web": ("100.115.92.11", {})})
LISTED = f"lumen-api        | {LUMEN} | linux\nvps-edge         | root{AT}203.0.113.5 | linux\n"


class Home(unittest.TestCase):
    """A Mac with lumen-api (prepared, on Tailscale) and vps-edge on its list, this Mac's key pair, the fakes."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(os.path.join(self.home, ".ssh"))
        os.makedirs(os.path.join(self.home, ".config", "herdr-fold"))
        self.write(".ssh/id_ed25519", PRIVATE)
        self.write(".ssh/id_ed25519.pub", MAC_PUBLIC + " dev@this-mac\n")
        self.write(".ssh/known_hosts", "lumen-api.tail0000.ts.net " + host_key("FakeHostKeyOfLumenApi")[0] + "\n")
        self.write(".config/herdr-fold/machines.txt", LISTED)
        self.write("look.json", json.dumps(SEES))
        self.write("keys", f"198.51.100.30 {BUILD_KEY}\n198.51.100.50 {VAULT_KEY}\ndb-02.local {DB_KEY}\n"
                           f"ci-runner.tail0000.ts.net {CI_KEY}\n")
        self.write("refusing", "")
        self.pkg = copy_package(os.path.join(self.tmp, "pkg"))
        self.stubs = stubs(os.path.join(self.tmp, "stubs"), {
            "ssh": THROUGH_SSH, "herdr": HERDR, "scutil": FAKE_SCUTIL,
            "tailscale": "#!/bin/sh\ncat <<'JSON'\n" + MAC_TAILNET + "\nJSON\n",
            "netbird": "#!/bin/sh\necho 'Error: failed to connect to daemon' >&2\nexit 1\n"})

    def path(self, rel):
        return os.path.join(self.home, rel)

    def write(self, rel, text):
        with open(self.path(rel), "w") as f:
            f.write(text)

    def read(self, rel):
        try:
            with open(self.path(rel)) as f:
                return f.read()
        except FileNotFoundError:
            return None

    def listed(self):
        return [[cell.strip() for cell in line.split("|")] for line in self.read(".config/herdr-fold/machines.txt")
                .splitlines() if line.strip() and not line.startswith("#")]

    def include(self):
        """The Include line said yes to before."""
        self.write(".ssh/config", "\n".join(machines.INCLUDE) + "\n")

    def run_questions(self, answers, *command):
        """./machines.sh COMMAND in a terminal, its questions answered in order; the questions it asked (and where it
        got stuck, waiting for more answers than given). What it showed: self.shown."""
        answers, prompts = list(answers), []

        def answer(line):
            if not answers:
                return None
            prompts.append(line.strip())
            return answers.pop(0)
        self.shown, ended = run_in_terminal(["/bin/bash", os.path.join(self.pkg, "machines.sh"), *command],
                                            {"PATH": f"{self.stubs}:/usr/bin:/bin", "TERM": "dumb", "HOME": self.home,
                                             "USER": "dev"}, answer, timeout=90, idle=0.3)
        if not ended:
            prompts.append("STUCK AT: " + self.shown.rstrip("\n").rsplit("\n", 1)[-1].strip())
        return prompts

    def calls(self, word):
        return [line for line in (self.read("ssh-calls") or "").splitlines() if word in line]


class Through(Home):
    def test_candidates_from_lumen_api_are_offered_default_no(self):
        prompts = self.run_questions(["y", "", "", "y", "", "", "", ""], "through", "lumen-api")
        self.assertEqual(prompts, [OFFERED[0], INCLUDE_ASK, "user [root]:", TRUST.format("build-01")] + OFFERED[1:])
        self.assertIn("== lumen-api (Tailscale, linux)\n      " + catalog_text("machines.through_line", "lumen-api")
                      + "\n", self.shown)
        self.assertIn("[✓] lumen-api sees 5 machines this Mac does not reach itself\n", self.shown)
        self.assertIn(f"      256 {BUILD} 198.51.100.30 (ED25519)\n", self.shown)
        self.assertIn("  [✓] build-01 added (linux), through lumen-api\n", self.shown)
        self.assertTrue(self.shown.endswith("  [-] 1 left out: its name is not a host name\n"), self.shown[-300:])
        self.assertEqual(self.listed()[2], ["build-01", "herdr-fold.build-01", "linux", BUILD,
                                            f"through:lumen-api root{AT}198.51.100.30"])
        self.assertEqual(self.read(".ssh/known_hosts").splitlines()[-1], f"herdr-fold.build-01 {BUILD_KEY}")
        self.assertEqual(self.read(".local/state/herdr-fold/outside.txt"),
                         "ssh-include\nknown-host herdr-fold.build-01\n")
        self.assertEqual(self.read(".ssh/config"), "\n".join(machines.INCLUDE) + "\n")
        # nothing of the no's: no key read, no login
        self.assertEqual([line for line in self.calls("ProxyJump=") if "198.51.100.30" not in line], [])

    def test_a_machine_behind_always_gets_the_fingerprint_question(self):
        # ci-runner from lumen-api's tailnet: never trusted on its first connection, as one of this Mac's own would be;
        # its fingerprint shows first and Enter alone is no
        self.include()
        prompts = self.run_questions(["", "", "", "y", "", "", ""], "through", "lumen-api")
        self.assertEqual(prompts, OFFERED[:4] + ["user [root]:", TRUST.format("ci-runner"), OFFERED[4]])
        _, ci = host_key("FakeHostKeyOfCiRunner")
        shown = f"      256 {ci} ci-runner.tail0000.ts.net (ED25519)\n"
        self.assertLess(self.shown.index(shown), self.shown.index(TRUST.format("ci-runner")))
        self.assertEqual(len(self.listed()), 2)
        self.assertNotIn("herdr-fold.ci-runner", self.read(".ssh/known_hosts"))
        # a key known_hosts trusts under that name already, another one: never a second one beside it
        self.write(".ssh/known_hosts", f"herdr-fold.ci-runner {OTHER_KEY}\n")
        self.run_questions(["", "", "", "y", "", "y", ""], "through", "lumen-api")
        self.assertIn("[!] " + catalog_text("machines.alias_taken", "ci-runner", "ci-runner")[:60], self.shown)
        self.assertEqual(self.read(".ssh/known_hosts"), f"herdr-fold.ci-runner {OTHER_KEY}\n")
        self.assertEqual(len(self.listed()), 2)

    def test_a_refused_key_says_so_and_asks_per_machine(self):
        # build-01, vault and db-02 take lumen-api's own key alone: each says so; this Mac's public key goes on build-01
        # on its yes, never on vault (lumen-api logs in there with a certificate), not on db-02 (a no)
        self.include()
        self.write("refusing", "198.51.100.30 build-01\n198.51.100.50 vault\ndb-02.local\n")
        prompts = self.run_questions(["y", "", "y", "y", "y", "", "y", "y", "", "y", "", "", ""],
                                     "through", "lumen-api")
        self.assertEqual(prompts, [OFFERED[0], "user [root]:", TRUST.format("build-01"), COPY.format("build-01"),
                                   OFFERED[1], "user [ops]:", TRUST.format("vault"),
                                   OFFERED[2], "user [root]:", TRUST.format("db-02"), COPY.format("db-02"),
                                   OFFERED[3], OFFERED[4]])
        for name in ("build-01", "vault", "db-02"):
            self.assertIn(f"  [!] {name} does not take this Mac's key (it may accept lumen-api's own key only).\n",
                          self.shown)
        self.assertIn("      " + catalog_text("machines.copy_key_cert", "lumen-api", "vault") + "\n", self.shown)
        self.assertEqual([row[0] for row in self.listed()], ["lumen-api", "vps-edge", "build-01"])
        # the one command, run by lumen-api: this Mac's public key alone (its comment left off), appended once, on the
        # machine showing the key read end to end; this Mac's private key is never read into a command
        copied = self.calls("authorized_keys")
        self.assertEqual(len(copied), 1, copied)
        self.assertTrue(copied[0].startswith("-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new"
                                             f" -o ClearAllForwardings=yes -o ForwardAgent=no -- {LUMEN} "), copied[0])
        for part in (MAC_PUBLIC + " herdr-fold", f"herdr-fold.build-01 {BUILD_KEY}", "StrictHostKeyChecking=yes",
                     "HostKeyAlias=herdr-fold.build-01", "ForwardAgent=no", " -- build-01 ", "grep -qxF"):
            self.assertIn(part, copied[0])
        self.assertNotIn("dev@this-mac", copied[0])
        self.assertNotIn("FakePrivateHalfOfThisMac", self.read("ssh-calls"))

    def test_a_crafted_list_is_validated_and_capped(self):
        # what lumen-api says is checked field by field: escapes, options, shell words, newlines, wrong types; a list
        # read up to 200 machines, a reply up to 1 MB, a document nested past reason none at all
        jump = machines.parse_line(f"lumen-api | {LUMEN} | linux")
        crafted = {"ssh_config": [{"alias": "ok\x1b]0;owned\x07", "host": "198.51.100.1"},
                                  {"alias": "-oProxyCommand=sh", "host": "198.51.100.2"},
                                  {"alias": "x", "host": "-oProxyCommand=sh"}, {"alias": "y", "host": "a;id"},
                                  {"alias": "z", "host": "198.51.100.3", "user": "root\nid"},
                                  {"alias": "w", "host": "198.51.100.4", "port": "22; id"}, "a text", None, [1],
                                  {"alias": ["list"], "host": {"a": 1}}],
                   "local": [{"host": "db-02.local", "port": 22, "instance": "Evil\x1b]0;owned\x07\nBox|x"},
                             {"host": "far.example.com", "port": 22}, {"host": "lab-pi.local", "port": 0}],
                   "tailscale": [{"dns": "kelp-ci.tail0000.ts.net", "os": ["linux"]},
                                 {"dns": "studio.tail0000.ts.net", "os": "iOS"}],
                   "netbird": "skipped"}
        found, left, skipped = networks.look_around_result(json.dumps(crafted), jump)
        self.assertEqual([(one["name"], one["address"]) for one in found], [("db-02", "db-02.local")])
        self.assertEqual(found[0]["instance"], "Evil]0;ownedBox|x")      # shown only, its controls dropped
        self.assertEqual(left, {"bad": 14, "over": 0})
        self.assertEqual(skipped, ["netbird"])
        many = {"ssh_config": [{"alias": f"m{n}", "host": f"198.51.100.{n % 250}"} for n in range(10000)]}
        found, left, _ = networks.look_around_result(json.dumps(many), jump)
        self.assertEqual((len(found), left), (200, {"bad": 0, "over": 9800}))
        self.assertIsNone(networks.look_around_result(json.dumps({"local": ["x" * (1 << 20)]}), jump))
        self.assertIsNone(networks.look_around_result("[" * 100000 + "]" * 100000, jump))
        self.assertIsNone(networks.look_around_result("not json", jump))
        # its reply read for a time and a size alone, then killed with all it started
        given = os.path.join(self.tmp, "given")
        with open(given, "w"):
            pass
        start = time.monotonic()
        self.assertEqual(networks.looked(["/bin/sh", "-c", "sleep 30"], 0.5, given)[:2], (None, None))
        self.assertEqual(networks.looked(["/bin/sh", "-c", "yes x; sleep 30"], 5, given)[:2], (None, None))
        self.assertLess(time.monotonic() - start, 3)
        self.assertEqual(networks.looked(["/bin/sh", "-c", "cat; echo said >&2"], 5, given), (0, "", "said\n"))
        # through machines.sh's own reading: each line's fields are checked ones, nothing of the controls
        self.write("look.json", json.dumps(dict(crafted, tailscale=many["ssh_config"][:3])))
        done = subprocess.run(["/usr/bin/python3", os.path.join(self.pkg, "core", "networks.py"), "through",
                               self.path(".config/herdr-fold/machines.txt"), os.path.join(self.stubs, "tailscale"),
                               "", "", "", "lumen-api", "--", "-o", "BatchMode=yes"], capture_output=True, text=True,
                              timeout=60, env={"PATH": f"{self.stubs}:/usr/bin:/bin", "HOME": self.home})
        lines = done.stdout.splitlines()
        self.assertEqual([line.split("|")[:3] for line in lines if line.startswith("candidate|")],
                         [["candidate", "db-02", "db-02.local"]], done.stderr)
        self.assertIn("sees|1", lines)
        self.assertIn("left|bad|15", lines)
        self.assertFalse(any(ch in done.stdout for ch in "\x1b\x07"))


class Behind(Home):
    def test_the_generated_host_jumps_and_never_forwards_the_agent(self):
        # its key read end to end with no login and nothing forwarded, its login as herdr-fold's own ssh
        script = ('. ./machines.sh; through_key build-01 "$1" root 198.51.100.30 ""; '
                  'through_ssh "$1" build-01 root 198.51.100.30 "" uname -s')
        done = subprocess.run(["bash", "-c", script, "machines.sh", LUMEN], cwd=self.pkg, capture_output=True,
                              text=True, timeout=30, env={"PATH": f"{self.stubs}:/usr/bin:/bin", "HOME": self.home})
        self.assertEqual(done.stdout, f"{BUILD_KEY}\nLinux\n", done.stderr)
        read, login = self.calls("ProxyJump=")
        for part in (f"-o ProxyJump={LUMEN}", "-o HostKeyAlias=herdr-fold.build-01", "-o PreferredAuthentications=none",
                     "-o HostKeyAlgorithms=ssh-ed25519", "-o StrictHostKeyChecking=accept-new",
                     "-o GlobalKnownHostsFile=/dev/null", "-o ForwardAgent=no", "-o ClearAllForwardings=yes",
                     "-o BatchMode=yes", "-l root -- 198.51.100.30 exit"):
            self.assertIn(part, read)
        self.assertEqual(self.read(".ssh/known_hosts").count("\n"), 1)                # nothing trusted by it
        for part in ("-o ForwardAgent=no", "-o ClearAllForwardings=yes", f"-o ProxyJump={LUMEN}",
                     "-o HostKeyAlias=herdr-fold.build-01", "-l root -- 198.51.100.30 uname -s"):
            self.assertIn(part, login)
        # on the list: its own Host, through lumen-api's target, its key under that Host's name, no agent forwarded
        listed = self.path(".config/herdr-fold/machines.txt")
        done = subprocess.run(["/usr/bin/python3", os.path.join(self.pkg, "core", "machines.py"), "behind", listed,
                               "build-01", "linux", BUILD, "lumen-api", f"root{AT}198.51.100.30"], capture_output=True,
                              text=True, timeout=30, env={"PATH": f"{self.stubs}:/usr/bin:/bin", "HOME": self.home})
        self.assertEqual(done.returncode, 0, done.stderr)
        hosts = self.path(".config/herdr-fold/ssh_config")
        self.assertIn("\nHost herdr-fold.build-01\n  HostName 198.51.100.30\n  User root\n"
                      "  HostKeyAlias herdr-fold.build-01\n  CheckHostIP no\n  ForwardAgent no\n"
                      f"  ProxyJump {LUMEN}\n", self.read(".config/herdr-fold/ssh_config"))
        if os.path.isfile("/usr/bin/ssh"):                  # as OpenSSH reads it: -G connects nowhere
            done = subprocess.run(["/usr/bin/ssh", "-G", "-F", hosts, "herdr-fold.build-01"], capture_output=True,
                                  text=True, stdin=subprocess.DEVNULL, timeout=20, env={"HOME": self.home})
            conf = dict(line.split(" ", 1) for line in done.stdout.splitlines() if " " in line)
            self.assertEqual((conf.get("forwardagent"), conf.get("proxyjump"), conf.get("hostkeyalias")),
                             ("no", LUMEN, "herdr-fold.build-01"), done.stderr)
        # one already listed, a bad address, user or key, a jump host not on the list: none of it written
        for bad in (["build-01", "linux", BUILD, "lumen-api", f"root{AT}198.51.100.31"],
                    ["db-02", "linux", DB, "lumen-api", f"root{AT}-oProxyCommand=sh"],
                    ["db-02", "linux", DB, "lumen-api", "-x@198.51.100.31"],
                    ["db-02", "linux", "SHA256:x;id", "lumen-api", f"root{AT}198.51.100.31"],
                    ["db-02", "linux", DB, "nowhere", f"root{AT}198.51.100.31"]):
            done = subprocess.run(["/usr/bin/python3", os.path.join(self.pkg, "core", "machines.py"), "behind", listed,
                                   *bad], capture_output=True, text=True, timeout=30, env={"HOME": self.home})
            self.assertEqual(done.returncode, 1, bad)
        self.assertEqual([row[0] for row in self.listed()], ["lumen-api", "vps-edge", "build-01"])

    def test_removing_lumen_api_asks_about_the_machines_behind(self):
        behind = (f"lumen-api | {LUMEN} | linux | {LUMEN_FP}\n"
                  f"build-01 | herdr-fold.build-01 | linux | {BUILD} | through:lumen-api root{AT}198.51.100.30\n"
                  f"db-02 | herdr-fold.db-02 | linux | {DB} | through:lumen-api root{AT}db-02.local\n")
        self.include()
        # without its key on the list it cannot stay their jump host: it stays on the list, nothing changes
        self.write(".config/herdr-fold/machines.txt", behind.replace(f" | {LUMEN_FP}", ""))
        prompts = self.run_questions([""], "remove", "lumen-api")
        self.assertIn(catalog_text("machines.remove_behind_nested", "lumen-api"), self.shown.replace("\n      ", " "))
        self.assertEqual([row[0] for row in self.listed()], ["lumen-api", "build-01", "db-02"])
        # a no: lumen-api goes, the two stay, jumping by its address from now on
        self.write(".config/herdr-fold/machines.txt", behind)
        prompts = self.run_questions([""], "remove", "lumen-api")
        self.assertEqual(prompts, ["build-01 and db-02 go through lumen-api: take them off too? [y/N]"])
        self.assertIn("== lumen-api (Tailscale, linux)\n", self.shown)
        self.assertIn("  [✓] lumen-api is off the machine list\n"
                      "      build-01 and db-02 stay: lumen-api remains their jump host.\n", self.shown)
        self.assertEqual([row[0] + " " + row[4] for row in self.listed()],
                         [f"build-01 through:{LUMEN} root{AT}198.51.100.30",
                          f"db-02 through:{LUMEN} root{AT}db-02.local"])
        self.assertEqual(self.read(".config/herdr-fold/ssh_config").count(f"  ProxyJump {LUMEN}\n"), 2)
        self.assertEqual(self.read(".ssh/known_hosts"),                   # its address held its key already
                         f"lumen-api.tail0000.ts.net {LUMEN_KEY}\n")
        # a yes: the two first, each through lumen-api, then lumen-api
        os.remove(self.path(".config/herdr-fold/ssh_config"))
        self.write(".config/herdr-fold/machines.txt", behind)
        prompts = self.run_questions(["y"], "remove", "lumen-api")
        self.assertEqual(prompts, ["build-01 and db-02 go through lumen-api: take them off too? [y/N]"])
        headings = [line for line in self.shown.splitlines() if line.startswith("== ")]
        self.assertEqual(headings, ["== build-01 (through lumen-api, linux)", "== db-02 (through lumen-api, linux)",
                                    "== lumen-api (Tailscale, linux)"])
        self.assertEqual(self.listed(), [])
        self.assertNotIn("remains", self.shown)


if __name__ == "__main__":
    unittest.main()
