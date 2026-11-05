"""Tests for machines.sh's list (~/.config/herdr-fold/machines.txt): ~/.ssh/config hosts only when said yes to, one by
one, not offered again by Tailscale; herdr's machines taken over with no list yet; `prepare` restores right columns.
"""
import os
import shutil
import subprocess
import tempfile
import unittest

from support import FAKE_TAILSCALE, PACKAGE, catalog_text, copy_package, run_in_terminal, stubs
SSH_CONFIG = """Host *
  AddKeysToAgent yes

Host alpha beta
  HostName 192.0.2.10
  User root

Host github.com
  HostName github.com
  User git

Host gamma
  HostName gamma.example

Include conf.d/*
"""
FAKE_SSH = """#!/bin/sh
case "$*" in
  *gamma*) exit 255 ;;
  *"uname -s"*) case "$*" in *delta*) echo Darwin ;; *) echo Linux ;; esac ;;
esac
exit 0
"""


def list_path(home):
    return os.path.join(home, ".config", "herdr-fold", "machines.txt")


def add_to_list(home, line):
    os.makedirs(os.path.dirname(list_path(home)), exist_ok=True)
    with open(list_path(home), "a") as f:
        f.write(line)


def listed(home):
    with open(list_path(home)) as f:
        rows = [line for line in f if line.strip() and not line.lstrip().startswith("#")]
    return sorted(tuple(c.strip() for c in row.split("|")) for row in rows)


NO_TAILNET = """#!/bin/sh
echo '{"Peer": {}}'
"""


class SshConfigMachines(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        self.pkg = os.path.join(self.tmp, "pkg")
        copy_package(self.pkg)
        os.makedirs(os.path.join(self.home, ".ssh", "conf.d"))
        with open(os.path.join(self.home, ".ssh", "config"), "w") as f:
            f.write(SSH_CONFIG)
        with open(os.path.join(self.home, ".ssh", "conf.d", "extra"), "w") as f:
            f.write("Host delta\n  HostName delta.example\n  User dev\n")
        add_to_list(self.home, "beta             | beta | linux\n")
        stubs(os.path.join(self.tmp, "stubs"), {"ssh": FAKE_SSH, "tailscale": NO_TAILNET})
        self.env = {"HOME": self.home, "PATH": f"{self.tmp}/stubs:/usr/bin:/bin", "HERDR_FOLD_YES": "1", "TERM": "dumb"}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_offers_reachable_hosts_from_the_ssh_config(self):
        env = {k: v for k, v in self.env.items() if k != "HERDR_FOLD_YES"}
        ask = catalog_text("machines.sshconfig_ask", "", "").split()[0]          # "Import"
        shown, _ = run_in_terminal(["/bin/bash", os.path.join(self.pkg, "machines.sh"), "sshconfig"], env,
                                   lambda line: "y" if ask in line else "", timeout=60)
        self.assertEqual(listed(self.home), [("alpha", "alpha", "linux"), ("beta", "beta", "linux"),
                                           ("delta", "delta", "macos")])
        self.assertIn("gamma", shown)                # unreachable: reported, then skipped
        self.assertIn("2 new machine(s) on the list, 1 already there: beta", shown)   # alpha, delta; beta

    def test_a_host_is_imported_only_when_said_yes_to(self):
        done = subprocess.run(["bash", os.path.join(self.pkg, "machines.sh"), "sshconfig"], env=self.env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(listed(self.home), [("beta", "beta", "linux")])          # the one imported earlier stays


SSH_ANSWERS = "#!/bin/sh\nexit 0\n"         # every machine answers


class TailscaleAfterSshConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pkg = os.path.join(self.tmp, "pkg")
        copy_package(self.pkg)
        add_to_list(self.tmp, "mac-mini         | mac-mini | macos\n")          # from ~/.ssh/config, by its alias
        stubs(os.path.join(self.tmp, "stubs"), {"tailscale": FAKE_TAILSCALE, "ssh": SSH_ANSWERS})
        self.env = {"HOME": self.tmp, "PATH": f"{self.tmp}/stubs:/usr/bin:/bin", "HERDR_FOLD_YES": "1", "TERM": "dumb"}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_machine_from_the_ssh_config_is_not_offered_again(self):
        done = subprocess.run(["bash", os.path.join(self.pkg, "machines.sh"), "tailscale"], env=self.env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        # mac-mini is kept once (an imported one's default answer is yes), server is not taken (a new one's is no)
        self.assertEqual(listed(self.tmp), [("mac-mini", "mac-mini", "macos")])
        self.assertIn("0 new machine(s) on the list, 1 already there: mac-mini", done.stdout)


TAILNET_CONFIG = """Host office
  HostName office.example

Host srv
  HostName server.tail0000.ts.net

Host srvip
  HostName 100.115.92.6
"""


class SshConfigLeavesTailnetMachinesToTheTailscaleStep(unittest.TestCase):
    """The ~/.ssh/config step offers its machines that are not on the Tailscale network — by name, DNS name or address
    those are asked in the Tailscale step, after its own question."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        self.pkg = os.path.join(self.tmp, "pkg")
        copy_package(self.pkg)
        os.makedirs(os.path.join(self.home, ".ssh"))
        with open(os.path.join(self.home, ".ssh", "config"), "w") as f:
            f.write(TAILNET_CONFIG)
        stubs(os.path.join(self.tmp, "stubs"), {"ssh": FAKE_SSH, "tailscale": FAKE_TAILSCALE})
        self.env = {"HOME": self.home, "PATH": f"{self.tmp}/stubs:/usr/bin:/bin", "HERDR_FOLD_YES": "1", "TERM": "dumb"}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_only_the_machines_off_the_tailnet_are_offered(self):
        env = {k: v for k, v in self.env.items() if k != "HERDR_FOLD_YES"}
        ask = catalog_text("machines.sshconfig_ask", "", "").split()[0]          # "Import"
        shown, _ = run_in_terminal(["/bin/bash", os.path.join(self.pkg, "machines.sh"), "sshconfig"], env,
                                   lambda line: "y" if ask in line else "", timeout=60)
        self.assertEqual(listed(self.home), [("office", "office", "linux")])
        self.assertIn("1 new machine(s) on the list, 0 already there\n", shown)    # none already there: no names


# herdr with two connected machines; ssh: `uname -s` answers Linux on lin and fails on win (as on Windows)
HERDR_TWO_MACHINES = """#!/bin/sh
case "$*" in
  "machine list --json")
    echo '[{"id": "m1", "label": "lin", "target": "root@lin"}, {"id": "m2", "label": "win", "target": "dev@win"}]' ;;
esac
exit 0
"""
FAKE_SSH_OS = """#!/bin/sh
case "$*" in
  *"uname -s"*) case "$*" in *root@lin*) echo Linux ;; *) exit 1 ;; esac ;;
esac
exit 0
"""


class MachineList(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        self.pkg = os.path.join(self.tmp, "pkg")
        os.makedirs(self.home)
        copy_package(self.pkg)
        stubs(os.path.join(self.tmp, "stubs"), {"herdr": HERDR_TWO_MACHINES, "ssh": FAKE_SSH_OS})
        self.env = {"HOME": self.home, "PATH": f"{self.tmp}/stubs:/usr/bin:/bin", "HERDR_FOLD_YES": "1", "TERM": "dumb"}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def status(self):
        return subprocess.run(["bash", os.path.join(self.pkg, "machines.sh"), "status"], env=self.env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)

    def test_the_package_has_no_machine_list(self):
        self.assertFalse(os.path.exists(os.path.join(PACKAGE, "machines.txt")))

    def test_machines_connected_in_herdr_are_taken_over(self):
        self.status()
        self.assertEqual(listed(self.home), [("lin", "root@lin", "linux"), ("win", "dev@win", "windows")])

    def test_an_existing_list_is_left_as_it_is(self):
        # a machine taken off the list (step 8: "no" to an imported one) must not come back from herdr
        add_to_list(self.home, "lin | root@lin | linux\n")
        self.status()
        self.assertEqual(listed(self.home), [("lin", "root@lin", "linux")])


class PrepareRestoresTheColumns(unittest.TestCase):
    """After the update, restore_panes.py runs for each connected machine: workspaces left without the right column
    (sidebar + terminal) get it, and an old sidebar still running there gets herdr-fold's."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        self.pkg = os.path.join(self.tmp, "pkg")
        copy_package(self.pkg)
        add_to_list(self.home, "lin | root@lin | linux\n")
        self.log = os.path.join(self.tmp, "restore-calls")
        with open(os.path.join(self.home, ".config", "herdr-fold", "restore_panes.py"), "w") as f:
            f.write(f"import sys\nopen({self.log!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n")
        herdr = HERDR_TWO_MACHINES.replace(', {"id": "m2", "label": "win", "target": "dev@win"}', "")
        stubs(os.path.join(self.tmp, "stubs"), {"herdr": herdr, "ssh": FAKE_SSH_OS})
        self.env = {"HOME": self.home, "PATH": f"{self.tmp}/stubs:/usr/bin:/bin", "HERDR_FOLD_YES": "1", "TERM": "dumb"}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_connected_machine_gets_its_columns_back(self):
        subprocess.run(["bash", os.path.join(self.pkg, "machines.sh"), "prepare"], env=self.env,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
        with open(self.log) as f:
            self.assertEqual(f.read(), "--machine lin\n")


if __name__ == "__main__":
    unittest.main()
