"""Tests for machines.sh with the Herdr app part installed (install.sh's question): a machine joins the app's core
(hc) too, one the app has already stays as it is, and `remove` takes off only what herdr-fold added (fake ssh, hc)."""
import os
import unittest

from support import catalog_text, stubs
from test_remote_prepare import Prepare

# the app's core: logs its calls; lists the machines named in $STUB_HC_HAS
FAKE_HC = """#!/bin/sh
printf '%s\\n' "hc $*" >> "$HOME/hc-calls"
if [ "$*" = "machine ls --json" ]; then
  if [ -n "$STUB_HC_BROKEN" ]; then echo '{"error":{"message":"the socket path is too long"}}' >&2; exit 2
  elif [ -n "$STUB_HC_HAS" ]; then printf '{"machines": [{"name": "%s"}]}\\n' "$STUB_HC_HAS"
  else echo '{"machines": []}'; fi
fi
exit 0
"""


class AppMachines(Prepare, unittest.TestCase):
    os_name = "linux"

    def setUp(self):
        super().setUp()
        stubs(os.path.join(self.tmp, "stubs"), {"herdr-core": FAKE_HC})
        self.state = os.path.join(self.profile, ".local", "state", "herdr-fold")
        os.makedirs(self.state, exist_ok=True)

    def app_part(self):
        with open(os.path.join(self.state, "plugins.txt"), "w") as f:
            f.write("herdr-fold.sidebar\nherdr-fold.app\n")

    def hc_calls(self):
        path = os.path.join(self.profile, "hc-calls")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return f.read().splitlines()

    def recorded(self):
        path = os.path.join(self.state, "app-machines.txt")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return f.read().splitlines()

    def test_a_machine_joins_the_app_too(self):
        self.app_part()
        shown = self.add()
        self.assertIn("hc machine add box --name box --install", self.hc_calls())
        self.assertEqual(self.recorded(), ["box"])
        self.assertIn(catalog_text("machines.app_added", "box"), shown)

    def test_an_hc_that_cannot_list_is_said_in_a_line_not_a_traceback(self):
        self.app_part()
        self.env["STUB_HC_BROKEN"] = "1"
        shown = self.add()
        self.assertNotIn("Traceback", shown)
        self.assertIn("hc machine add box --name box --install", self.hc_calls())

    def test_without_the_app_part_hc_is_not_asked(self):
        self.add()
        self.assertEqual(self.hc_calls(), [])

    def test_a_machine_the_app_has_already_is_left_as_it_is(self):
        self.app_part()
        self.env["STUB_HC_HAS"] = "box"
        self.add()
        self.assertFalse([call for call in self.hc_calls() if call.startswith("hc machine add")])
        self.assertEqual(self.recorded(), [])

    def test_remove_takes_off_only_what_herdr_fold_added(self):
        self.app_part()
        self.add()
        self.remove()
        self.assertIn("hc machine rm box", self.hc_calls())
        self.assertEqual(self.recorded(), [])

    def test_remove_leaves_a_machine_herdr_fold_did_not_add(self):
        self.app_part()
        self.env["STUB_HC_HAS"] = "box"
        self.add()
        self.remove()
        self.assertNotIn("hc machine rm box", self.hc_calls())


if __name__ == "__main__":
    unittest.main()
