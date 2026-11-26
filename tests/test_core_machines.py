"""Tests for core/machines.py: a machine is its host key and a network one of its routes; the list reads its older
lines and keeps your comments; herdr-fold's ssh file gives each routed machine a Host of its own (read back through
ssh -G, nothing connected); an alias line comes only from a trusted key; what a network says is checked first."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import PACKAGE, host_key, set_env, stubs

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import machines  # noqa: E402

AT = "@"                        # a user before a host: put together here, never an e-mail's look
STUDIO_KEY, STUDIO = host_key("FakeHostKeyOfStudio")
OTHER_KEY, OTHER = host_key("FakeHostKeyOfAnotherStudio")


def route(network, address, user=None, port=None, through=None):
    return {"network": network, "address": address, "user": user, "port": port, "through": through}


def machine(name, target, os_="linux", key=None, routes=None):
    return {"name": name, "target": target, "os": os_, "key": key,
            "routes": routes or [machines.target_route(target)]}


# studio on the local network and on Tailscale, reached through its own Host; lab-pi as before; build-01 behind
# lumen-api, whose own target herdr was given
STUDIO_ROUTES = [route("local", "studio.local", "dev"), route("tailscale", "studio.tail0000.ts.net", "dev")]
LISTED = [machine("studio", "herdr-fold.studio", "macos", STUDIO, STUDIO_ROUTES),
          machine("lab-pi", "pi" + AT + "192.0.2.40"),
          machine("lumen-api", "root" + AT + "lumen-api.tail0000.ts.net"),
          machine("build-01", "herdr-fold.build-01", routes=[route("through", "198.51.100.30", "root",
                                                                   through="lumen-api")])]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.list = os.path.join(self.tmp, "machines.txt")
        # ssh -G reads the account's own ~/.ssh/config, whatever HOME says: a stand-in that knows no Host answers
        set_env(self, HOME=self.tmp, PATH=stubs(os.path.join(self.tmp, "stubs"), {"ssh": "#!/bin/sh\nexit 0\n"})
                + ":/usr/bin:/bin")

    def write_list(self, text):
        with open(self.list, "w") as f:
            f.write(text)

    def lines(self):
        with open(self.list) as f:
            return f.read().splitlines()


class TheList(Base):
    def test_an_old_line_reads_with_one_route_and_no_key(self):
        self.write_list("# mine\nstudio | dev" + AT + "studio.local | macos\n")
        self.assertEqual(machines.read(self.list), [
            {"name": "studio", "target": "dev" + AT + "studio.local", "os": "macos", "key": None,
             "routes": [route(None, "studio.local", "dev")]}])

    def test_routes_and_key_round_trip_and_comments_stay(self):
        older = (machines.HEADER[0],) + machines.OLD_HEADER                  # its first line is the same
        self.write_list("\n".join(older) + "\n# my clients\nstudio | dev" + AT + "studio.local | macos\n"
                        "# the lab\nlab-pi | pi" + AT + "192.0.2.40 | linux\n")
        found = machines.read(self.list)
        found[0].update(key=STUDIO, target="herdr-fold.studio",
                        routes=STUDIO_ROUTES + [route("public", "2001:db8::7", "dev", 2222)])
        found.append(machine("build-01", "herdr-fold.build-01", key=OTHER,
                             routes=[route("through", "198.51.100.30", "root", through="lumen-api")]))
        machines.write(self.list, found)
        self.assertEqual(machines.read(self.list), found)
        lines = self.lines()
        self.assertEqual(lines[:len(machines.HEADER)], list(machines.HEADER))        # the older header replaced
        self.assertEqual([line.split("|")[0].strip() for line in lines[len(machines.HEADER):]],
                         ["# my clients", "studio", "# the lab", "lab-pi", "build-01"])     # each where it was
        self.assertEqual([cell.strip() for cell in lines[-2].split("|")], ["lab-pi", "pi" + AT + "192.0.2.40", "linux"])
        self.assertEqual({line.index("|", line.index("|") + 1) for line in lines[-4:] if not line.startswith("#")},
                         {lines[-1].index("|", lines[-1].index("|") + 1)})        # the columns aligned
        self.assertIn("| local dev" + AT + "studio.local, tailscale dev" + AT + "studio.tail0000.ts.net, "
                      "public dev" + AT + "[2001:db8::7]:2222", lines[-4])
        self.assertTrue(lines[-1].endswith(f"| {OTHER} | through:lumen-api root" + AT + "198.51.100.30"))

    def test_a_new_list_starts_with_the_header_and_a_hand_written_one_gets_none(self):
        machines.write(self.list, LISTED[1:2])
        self.assertEqual(self.lines()[:len(machines.HEADER)], list(machines.HEADER))
        self.write_list("lab-pi | pi" + AT + "192.0.2.40 | linux\n")
        machines.write(self.list, machines.read(self.list) + LISTED[2:3])
        self.assertEqual([line.split("|")[0].strip() for line in self.lines()], ["lab-pi", "lumen-api"])


class TheSshFile(Base):
    def test_the_ssh_file_has_an_alias_host_per_routed_machine(self):
        text = machines.ssh_file(LISTED)
        self.assertEqual(text.splitlines()[0], "# Written by herdr-fold from machines.txt; edits here are lost.")
        self.assertIn("\nHost herdr-fold.studio\n  HostName studio.local\n  User dev\n"
                      "  HostKeyAlias herdr-fold.studio\n  CheckHostIP no\n  ForwardAgent no\n", text)
        self.assertNotIn("lab-pi", text)                            # its target is herdr's own: no Host of herdr-fold's
        on_a_port = [machine("vps-edge", "herdr-fold.vps-edge", routes=[route("public", "203.0.113.5", "dev", 2222)])]
        self.assertIn("  HostName 203.0.113.5\n  User dev\n  Port 2222\n", machines.ssh_file(on_a_port))

    def test_a_machine_behind_another_jumps_through_its_target(self):
        self.assertIn("\nHost herdr-fold.build-01\n  HostName 198.51.100.30\n  User root\n"
                      "  HostKeyAlias herdr-fold.build-01\n  CheckHostIP no\n  ForwardAgent no\n"
                      "  ProxyJump root" + AT + "lumen-api.tail0000.ts.net\n", machines.ssh_file(LISTED))
        # one whose own target is its Host jumps by that Host; after it left the list, by the target it had
        behind = LISTED[:2] + [dict(LISTED[2], target="herdr-fold.lumen-api",
                                    routes=[route("tailscale", "lumen-api.tail0000.ts.net", "root")]), LISTED[3]]
        self.assertIn("  ProxyJump herdr-fold.lumen-api\n", machines.ssh_file(behind))
        kept = [dict(LISTED[3], routes=[route("through", "198.51.100.30", "root",
                                              through="root" + AT + "lumen-api.tail0000.ts.net")])]
        self.assertIn("  ProxyJump root" + AT + "lumen-api.tail0000.ts.net\n", machines.ssh_file(kept))
        itself = [dict(LISTED[3], routes=[route("through", "198.51.100.30", "root", through="build-01")])]
        self.assertNotIn("Host ", machines.ssh_file(itself))

    @unittest.skipUnless(os.path.isfile("/usr/bin/ssh"), "OpenSSH's ssh")
    def test_no_host_forwards_the_agent(self):
        # each Host as ssh reads it (-G resolves it and connects nowhere; -F reads no other config)
        path = os.path.join(self.tmp, "ssh_config")
        with open(path, "w") as f:
            f.write(machines.ssh_file(LISTED))
        for name, jump in (("studio", None), ("build-01", "root" + AT + "lumen-api.tail0000.ts.net")):
            done = subprocess.run(["/usr/bin/ssh", "-G", "-F", path, f"herdr-fold.{name}"], capture_output=True,
                                  text=True, stdin=subprocess.DEVNULL, timeout=20, env={"HOME": self.tmp})
            conf = dict(line.split(" ", 1) for line in done.stdout.splitlines() if " " in line)
            self.assertEqual((conf.get("forwardagent"), conf.get("hostkeyalias"), conf.get("proxyjump")),
                             ("no", f"herdr-fold.{name}", jump), done.stderr)


class Keys(Base):
    def known_hosts(self, *lines):
        path = os.path.join(self.tmp, "known_hosts")
        with open(path, "w") as f:
            f.write("".join(line + "\n" for line in lines))
        return path

    def test_an_alias_line_comes_only_from_a_trusted_key(self):
        studio = LISTED[0]
        self.assertEqual(machines.trusted_alias(studio, self.known_hosts(f"studio.local {STUDIO_KEY}")),
                         f"herdr-fold.studio {STUDIO_KEY}")
        self.assertEqual(machines.trusted_alias(studio, self.known_hosts(f"elsewhere.example {STUDIO_KEY}")), None)
        self.assertEqual(machines.trusted_alias(studio, self.known_hosts(f"studio.local {OTHER_KEY}")), None)
        self.assertEqual(machines.trusted_alias(dict(studio, key=None), self.known_hosts(f"studio.local {STUDIO_KEY}")),
                         None)                                       # no key listed: none to check it against
        self.assertEqual(machines.alias_line("studio", "ssh-rsa AAAAB3NzaC1yc2E"), None)
        self.assertEqual(machines.alias_line("studio\nProxyCommand x", STUDIO_KEY), None)
        self.assertEqual(machines.fingerprint(STUDIO_KEY), STUDIO)              # as ssh-keygen -l prints it

    def test_a_candidate_with_a_listed_key_is_that_machine(self):
        listed = [machine("studio", "dev" + AT + "studio.local", "macos", STUDIO), LISTED[1]]
        self.assertIs(machines.same_machine(listed, STUDIO), listed[0])
        self.assertIsNone(machines.same_machine(listed, OTHER))
        self.assertIsNone(machines.same_machine(listed, None))
        known = {"studio": STUDIO}
        self.assertEqual(machines.identify(listed, known, [STUDIO], "tailscale", "studio", ["studio.tail0000.ts.net"]),
                         ("route", "studio"))                        # the same key elsewhere: another way to it
        self.assertEqual(machines.identify(listed, known, [STUDIO], None, "studio.local", ["studio.local"]),
                         ("listed", "studio"))
        known_hosts = self.known_hosts(f"studio.local {STUDIO_KEY}")
        found, alias = machines.add_route(listed, "studio", STUDIO, "tailscale", "studio.tail0000.ts.net", True,
                                          known_hosts)
        self.assertEqual(found[0]["target"], "herdr-fold.studio")            # herdr has not connected it: its Host
        self.assertEqual(found[0]["routes"], STUDIO_ROUTES)                   # the user its first route has
        self.assertEqual(alias, f"herdr-fold.studio {STUDIO_KEY}")
        self.assertEqual(machines.identify(found, known, [], "tailscale", "studio", ["studio.tail0000.ts.net"]),
                         ("known", "studio"))                         # now one of its routes
        # one herdr connected keeps the target it was given, and the route it connects by first
        kept, alias = machines.add_route([machine("studio", "dev" + AT + "studio.tail0000.ts.net", "macos", STUDIO)],
                                         "studio", STUDIO, "local", "studio.local", False, known_hosts)
        self.assertEqual((kept[0]["target"], [one["network"] for one in kept[0]["routes"]], alias),
                         ("dev" + AT + "studio.tail0000.ts.net", ["tailscale", "local"], None))

    def test_a_clashing_name_takes_its_network(self):
        listed = [machine("alpha", "root" + AT + "192.0.2.10", key=STUDIO), machine("beta", "root" + AT + "192.0.2.11")]
        self.assertEqual(machines.unique_name(listed, "alpha", "netbird"), "alpha-netbird")
        self.assertEqual(machines.unique_name(listed, "alpha", None), "alpha-2")
        self.assertEqual(machines.unique_name(listed + [machine("alpha-netbird", "x")], "alpha", "netbird"),
                         "alpha-netbird-2")
        self.assertEqual(machines.unique_name(listed, "gamma", "netbird"), "gamma")
        # a machine of the same name with another key is another machine; with no key to tell, the listed one
        known = {"alpha": STUDIO}
        self.assertEqual(machines.identify(listed, known, [OTHER], "netbird", "alpha", ["alpha.netbird.cloud"]),
                         ("new", "alpha-netbird"))
        self.assertEqual(machines.identify(listed, known, [], "netbird", "alpha", ["alpha.netbird.cloud"]),
                         ("listed", "alpha"))


class SetBack(Base):
    def test_a_moved_machine_goes_back_to_its_first_route(self):
        # before herdr-fold's Hosts go (the uninstaller): each machine at its own Host, with the address herdr takes
        vps = machine("vps-edge", "herdr-fold.vps-edge", routes=[route("public", "2001:db8::7", "dev", 2222)])
        listed = LISTED + [vps]
        self.assertEqual(machines.moved(listed), [("studio", "dev" + AT + "studio.local"), ("build-01", None),
                                                  ("vps-edge", "dev" + AT + "[2001:db8::7]:2222")])
        machines.write(self.list, listed)
        self.assertEqual(machines.main(["machines.py", "unmove", self.list, "studio"]), 0)
        self.assertEqual(machines.main(["machines.py", "unmove", self.list, "build-01"]), 1)    # behind another
        found = {one["name"]: one for one in machines.read(self.list)}
        self.assertEqual((found["studio"]["target"], found["studio"]["routes"]),
                         ("dev" + AT + "studio.local", STUDIO_ROUTES))                 # its routes stay on the list
        self.assertEqual(found["build-01"]["target"], "herdr-fold.build-01")


class Validators(Base):
    def test_validators_refuse_options_escapes_and_long_names(self):
        for good in ("studio.local", "build-01", "192.0.2.9", "a" * 63 + ".example"):
            self.assertTrue(machines.host_ok(good), good)
        for bad in ("", "-oProxyCommand=sh", "a;b", "a b", "studio\n", "$(id)", "a_b", "a" * 64, "a." * 127 + "ab",
                    "x\x1b[31m"):
            self.assertFalse(machines.host_ok(bad), repr(bad))
        self.assertTrue(machines.address_ok("2001:db8::7") and machines.address_ok("198.51.100.30"))
        self.assertFalse(machines.address_ok("192.0.2.300") or machines.address_ok("studio"))
        for good in ("dev", "root", "Admin", "_svc", "a.b-c"):
            self.assertTrue(machines.user_ok(good), good)
        for bad in ("", "-oX", "a b", "dev;id", "x" * 33, "dev\n"):
            self.assertFalse(machines.user_ok(bad), repr(bad))
        self.assertTrue(all(machines.port_ok(port) for port in (22, "2222", 65535)))
        self.assertFalse(any(machines.port_ok(port) for port in (0, "65536", "-1", "22a", "022", "")))
        self.assertEqual(machines.clean("a\x1b]0;b\x07c\x9bd" + "e" * 300, 10), "a]0;bcdeee")
        # nothing a network says goes into the ssh file unchecked: no Host for a bad name, address, user or jump
        bad = [machine("x\nProxyCommand sh", "herdr-fold.x\nProxyCommand sh", routes=[route(None, "192.0.2.9")]),
               machine("y", "herdr-fold.y", routes=[route(None, "-oProxyCommand=sh")]),
               machine("z", "herdr-fold.z", routes=[route(None, "192.0.2.9", "a b")]),
               machine("w", "herdr-fold.w", routes=[route("through", "192.0.2.9", through="-oProxyCommand=sh")])]
        self.assertEqual(machines.ssh_file(bad), machines.SSH_HEAD + "\n")
        self.assertIsNone(machines.parse_route("through 192.0.2.9"))
        self.assertIsNone(machines.parse_route("satellite 192.0.2.9"))


class Trust(unittest.TestCase):
    def test_security_md_tells_what_each_source_proves(self):
        with open(os.path.join(PACKAGE, "SECURITY.md"), encoding="utf-8") as f:
            rows = [[cell.strip() for cell in row.split("|")[1:-1]] for row in f.read().splitlines()
                    if row.startswith("| ")]
        for source, proves, key in machines.SOURCES:
            with self.subTest(source):
                self.assertTrue(any(row[0].strip("`") == source and row[1] == proves and key in row[2]
                                    for row in rows if len(row) == 3))


class TheInclude(Base):
    def test_the_include_comes_off_as_it_went_on(self):
        config = os.path.join(self.tmp, ".ssh", "config")
        machines.include(config)                                     # none yet: made, yours alone
        self.assertEqual(oct(os.stat(config).st_mode & 0o777), "0o600")
        self.assertEqual(oct(os.stat(os.path.dirname(config)).st_mode & 0o777), "0o700")
        theirs = "Host *\n  AddKeysToAgent yes\n"
        with open(config, "w") as f:
            f.write(theirs)
        machines.include(config)
        machines.include(config)                                     # once
        with open(config) as f:
            self.assertEqual(f.read(), "\n".join(machines.INCLUDE) + "\n\n" + theirs)
        self.assertTrue(machines.included(config))
        self.assertTrue(machines.uninclude(config))
        with open(config) as f:
            self.assertEqual(f.read(), theirs)
        self.assertFalse(machines.uninclude(config) or machines.included(config))


if __name__ == "__main__":
    unittest.main()
