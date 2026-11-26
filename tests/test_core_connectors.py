"""Tests for core/connectors.py: the agents' own commands for a connector, each one argv with the name and the address
as given or refused; a connector's brand by its name, else by its address; the address Claude prints while it waits
for a sign-in; the brands' logos in the mod, as SVG Logos has them; the media services the add form offers."""
import contextlib
import io
import json
import os
import re
import sys
import unittest
import xml.etree.ElementTree as ET

from support import PACKAGE

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import connectors  # noqa: E402

LOGOS = os.path.join(PACKAGE, "app", "mods", "herdr-fold", "icons", "logos")
BOX, DROPBOX = "https://mcp.box.com", "https://mcp.dropbox.com/mcp"
AT = "@"                        # before a host, a user's name in an address: put together here, never an e-mail's look
# what `claude mcp login` writes in a terminal while it waits (measured with a stand-in server): the address as a
# link's target and as its words, in color, then the line it reads a pasted address on
ASKED = ("http://127.0.0.1:47831/authorize?response_type=code&client_id=standin-client&code_challenge_method=S256"
         "&redirect_uri=http%3A%2F%2Flocalhost%3A56693%2Fcallback&state=J1MQ_TCM")
WAITING = ('Starting authentication for "standin"…\r\nIf the browser didn\'t open, visit:\r\n'
           f"  \x1b]8;;{ASKED}\x07\x1b[94m{ASKED}\x1b[39m\x1b]8;;\x07\r\n\r\n"
           "Waiting for authorization… (^C to cancel)\r\n\x1b[1G\x1b[0JOr paste the redirect URL here: \x1b[33G")


class Commands(unittest.TestCase):
    def test_a_sign_in_and_a_sign_out_are_the_agents_own_commands(self):
        self.assertEqual(connectors.login("claude", "claude.ai Box"), ["claude", "mcp", "login", "claude.ai Box"])
        self.assertEqual(connectors.logout("claude", "plugin:figma:figma"),
                         ["claude", "mcp", "logout", "plugin:figma:figma"])
        self.assertEqual(connectors.login("codex", "sentry"), ["codex", "mcp", "login", "sentry"])
        self.assertEqual(connectors.logout("codex", "sentry"), ["codex", "mcp", "logout", "sentry"])

    def test_claude_adds_for_this_folder_or_for_all_and_codex_for_all(self):
        self.assertEqual(connectors.add("claude", "dropbox", DROPBOX, "local"), [
            "claude", "mcp", "add", "--transport", "http", "--scope", "local", "dropbox", DROPBOX])
        self.assertEqual(connectors.add("claude", "dropbox", DROPBOX, "user")[5:7], ["--scope", "user"])
        self.assertEqual(connectors.add("codex", "dropbox", DROPBOX), ["codex", "mcp", "add", "dropbox", "--url",
                                                                       DROPBOX])
        self.assertEqual(connectors.add("claude", "metrics", "http://localhost:8080/mcp", "local")[-1],
                         "http://localhost:8080/mcp")
        self.assertEqual(connectors.add("codex", "metrics", "http://127.0.0.1:8080/mcp")[-1],
                         "http://127.0.0.1:8080/mcp")
        self.assertEqual(connectors.add("codex", "metrics", "http://[::1]:8080/mcp")[-1], "http://[::1]:8080/mcp")

    def test_the_add_form_makes_the_command_or_says_which_field_is_refused_and_why(self):
        self.assertEqual(connectors.form("claude", "dropbox", DROPBOX, "local"),
                         {"argv": connectors.add("claude", "dropbox", DROPBOX, "local"), "name": "dropbox"})
        self.assertEqual(connectors.form("codex", " dropbox ", f" {DROPBOX} "),      # typed with spaces round it
                         {"argv": ["codex", "mcp", "add", "dropbox", "--url", DROPBOX], "name": "dropbox"})
        self.assertEqual(connectors.form("claude", "", DROPBOX, "local"), {"field": "name", "error": "Name it"})
        self.assertEqual(connectors.form("claude", "my box", DROPBOX, "local"),
                         {"field": "name", "error": "Letters, digits, - and _ only"})
        self.assertEqual(connectors.form("claude", "--scope", DROPBOX, "local")["field"], "name")
        self.assertEqual(connectors.form("claude", "dropbox", "", "local"),
                         {"field": "url", "error": "Its address, starting with https://"})
        self.assertEqual(connectors.form("claude", "dropbox", "http://mcp.dropbox.com/mcp", "local")["field"], "url")
        self.assertIn("argv", connectors.form("claude", "tidepool", "http://localhost:8765/mcp", "user"))
        for agent, scope in (("gemini", "local"), ("claude", "project"), ("claude", None)):
            with self.subTest(agent=agent, scope=scope), self.assertRaises(ValueError):
                connectors.form(agent, "dropbox", DROPBOX, scope)

    def test_a_server_is_switched_by_claudes_own_command(self):
        self.assertEqual(connectors.toggle("claude.ai Notion", False), "/mcp disable claude.ai Notion")
        self.assertEqual(connectors.toggle("sentry", True), "/mcp enable sentry")

    def test_a_name_like_an_option_or_with_a_control_character_is_refused(self):
        for name in ("-h", "--scope", "", " ", "a\nb", "a\x1b[0m", "a\x00", "a;b", "a/b", "a$b", "é", "n" * 81, None,
                     7, " box", "box "):
            with self.subTest(name=name):
                for build in (lambda: connectors.login("claude", name), lambda: connectors.logout("codex", name),
                              lambda: connectors.toggle(name, True),
                              lambda: connectors.add("claude", name, DROPBOX, "local")):
                    with self.assertRaises(ValueError):
                        build()
        self.assertEqual(connectors.login("claude", "n" * 80)[-1], "n" * 80)

    def test_a_new_servers_name_is_one_both_agents_take(self):
        # `claude mcp add` takes letters, digits, - and _ alone; a name Claude gave itself (a connector's) is not added
        for name in ("claude.ai Box", "plugin:figma:figma", "drop box", "drop.box", "box(2)"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                connectors.add("claude", name, DROPBOX, "local")
        self.assertEqual(connectors.add("codex", "harbor_api-2", DROPBOX)[3], "harbor_api-2")

    def test_an_address_is_https_or_this_machines_own(self):
        for url in ("http://mcp.dropbox.com/mcp", "ftp://mcp.dropbox.com", "file:///etc/hosts", "mcp.dropbox.com",
                    "https://", "https:///mcp", "--url", "", "https://mcp.dropbox.com/a b", "https://box.com/\n",
                    "https://box.com/\x1b[0m", "http://localhost.box.com/mcp", f"http://localhost{AT}box.com/mcp",
                    f"https://me:secret{AT}box.com/mcp", "https://box.com:port/mcp", "https://" + "a" * 2048, None, 7):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    connectors.add("claude", "box", url, "local")
                with self.assertRaises(ValueError):
                    connectors.add("codex", "box", url)

    def test_an_unknown_agent_or_scope_is_refused(self):
        for build in (lambda: connectors.login("gemini", "box"), lambda: connectors.logout("", "box"),
                      lambda: connectors.add("gemini", "box", BOX, "local"),
                      lambda: connectors.add("claude", "box", BOX, "project"),
                      lambda: connectors.add("claude", "box", BOX, "--scope"),
                      lambda: connectors.add("claude", "box", BOX)):
            with self.assertRaises(ValueError):
                build()


class Brands(unittest.TestCase):
    def test_each_brand_has_its_name_logo_glyph_and_color(self):
        self.assertEqual(sorted(connectors.BRANDS), ["bfl", "box", "cartesia", "dropbox", "elevenlabs", "fal", "figma",
                                                     "github", "google-drive", "higgsfield", "linear", "luma", "meshy",
                                                     "notion", "onedrive", "runway", "sentry"])
        # SVG Logos' (CC0); FLUX's maker and Meshy give no logo to take: their letter
        self.assertEqual({key: one["logo"] for key, one in connectors.BRANDS.items()}, {
            "bfl": None, "box": "box", "cartesia": "cartesia-icon", "dropbox": "dropbox",
            "elevenlabs": "elevenlabs-icon",
            "fal": "fal-icon", "figma": "figma", "github": "github-icon", "google-drive": "google-drive-2020",
            "higgsfield": "higgsfield-icon",
            "linear": "linear-icon", "luma": "luma-icon", "meshy": None, "notion": "notion-icon",
            "onedrive": "microsoft-onedrive", "runway": "runway-icon", "sentry": "sentry-icon"})
        self.assertEqual(sorted(key for key, one in connectors.BRANDS.items() if one["mono"]),
                         ["elevenlabs", "fal", "github", "linear", "luma", "runway", "sentry"])
        self.assertEqual(sorted(key for key, one in connectors.BRANDS.items() if one["glyph"] is None),
                         ["bfl", "box", "cartesia", "elevenlabs", "fal", "higgsfield", "linear", "luma", "meshy",
                          "runway"])
        # Nerd Fonts' brand glyphs, each one cell: Material Design's, Font Awesome's, Devicons'
        self.assertEqual({key: one["glyph"] for key, one in connectors.BRANDS.items() if one["glyph"]}, {
            "google-drive": "\U000f02b6", "dropbox": "", "notion": "", "sentry": "", "github": "\uf09b",
            "figma": "", "onedrive": "\U000f03ca"})
        for key, one in connectors.BRANDS.items():
            with self.subTest(key):
                self.assertEqual(sorted(one), ["color", "glyph", "logo", "mono", "name"])
                self.assertRegex(one["color"], r"^#[0-9a-f]{6}$")
                self.assertTrue(one["name"])
        self.assertEqual(connectors.BRANDS["google-drive"]["name"], "Google Drive")
        # as each maker writes it: fal in lower case, FLUX as Black Forest Labs names its connector
        self.assertEqual([connectors.BRANDS[key]["name"] for key in ("fal", "elevenlabs", "bfl", "runway")],
                         ["fal", "ElevenLabs", "FLUX", "Runway"])

    def test_a_connector_is_known_by_its_name(self):
        for label, key in (("Box", "box"), ("Google Drive", "google-drive"), ("google-drive", "google-drive"),
                           ("google_drive", "google-drive"), ("gdrive", "google-drive"), ("Linear", "linear"),
                           ("Notion", "notion"), ("sentry", "sentry"), ("Dropbox", "dropbox"), ("figma", "figma"),
                           ("OneDrive", "onedrive"), ("Microsoft OneDrive", "onedrive"), ("Box (2)", "box"),
                           ("sentry-mcp", "sentry"), ("Notion MCP server", "notion"), ("  LINEAR ", "linear"),
                           ("elevenlabs", "elevenlabs"), ("ElevenLabs", "elevenlabs"), ("fal", "fal"),
                           ("fal-ai", "fal"), ("FLUX", "bfl"), ("flux", "bfl"), ("Black Forest Labs", "bfl"),
                           ("runway", "runway"), ("Higgsfield", "higgsfield"), ("Luma AI", "luma"),
                           ("cartesia-mcp", "cartesia"), ("meshy", "meshy")):
            with self.subTest(label=label):
                self.assertEqual(connectors.brand(label, None), key)

    def test_a_name_that_only_holds_a_brands_is_not_it(self):
        for label in ("Sandbox", "boxer", "notional", "linear-algebra", "harbor-api", "Google", "Drive", "falcon",
                      "fluxion", "runway-lights", "", None, 7):
            with self.subTest(label=label):
                self.assertIsNone(connectors.brand(label, None))

    def test_a_connector_is_known_by_its_address(self):
        for url, key in (("mcp.box.com", "box"), ("https://mcp.dropbox.com/mcp", "dropbox"),
                         ("mcp.figma.com/mcp", "figma"), ("mcp.linear.app/sse", "linear"),
                         ("https://mcp.notion.com/mcp", "notion"), ("mcp.sentry.dev/mcp", "sentry"),
                         ("https://sentry.io/mcp", "sentry"), ("https://MCP.Box.com:443/x?y=1", "box"),
                         (f"https://me{AT}mcp.box.com/", "box"), ("https://mcp.fal.ai/mcp-relay", "fal"),
                         ("https://api.elevenlabs.io/v1/mcp", "elevenlabs"), ("https://mcp.bfl.ai", "bfl"),
                         ("https://mcp.runwayml.com/mcp", "runway"), ("https://mcp.higgsfield.ai/mcp", "higgsfield"),
                         ("https://agents.lumalabs.ai/mcp", "luma"), ("https://mcp.cartesia.ai/mcp", "cartesia"),
                         ("https://mcp.meshy.ai/mcp", "meshy")):
            with self.subTest(url=url):
                self.assertEqual(connectors.brand("harbor", url), key)

    def test_an_address_that_only_looks_like_a_brands_is_not_it(self):
        for url in ("notbox.com", "https://box.com.harbor.dev/mcp", "https://harbor.dev/box.com", "api.harbor.dev/mcp",
                    f"https://mcp.box.com{AT}harbor.dev/mcp", "https://[box", "", None, 7):
            with self.subTest(url=url):
                self.assertIsNone(connectors.brand("harbor", url))

    def test_the_name_wins_over_the_address(self):
        self.assertEqual(connectors.brand("Notion", "mcp.box.com"), "notion")

    def test_every_brands_logo_is_in_the_mod(self):
        held = sorted(name[:-len(".svg")] for name in os.listdir(LOGOS))
        self.assertEqual(held, sorted(one["logo"] for one in connectors.BRANDS.values() if one["logo"]),
                         "out of date: /usr/bin/python3 tools/icons.py logos")

    def test_a_logo_draws_alone_with_nothing_fetched(self):
        # an SVG the app draws from the mod: no script, no link out, no picture inside it
        for name in sorted(os.listdir(LOGOS)):
            with self.subTest(name), open(os.path.join(LOGOS, name), encoding="utf-8") as f:
                text = f.read()
                root = ET.fromstring(text)
                self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
                self.assertTrue(root.get("viewBox"))
                tags = {node.tag.rpartition("}")[2] for node in root.iter()}
                self.assertFalse(tags & {"script", "image", "foreignObject", "a", "style"}, tags)
                self.assertFalse(re.findall(r"https?://(?!www\.w3\.org/2000/svg\")", text))

    def test_a_mono_mark_has_one_color_and_the_others_their_own(self):
        for key, one in ((key, one) for key, one in connectors.BRANDS.items() if one["logo"]):
            with self.subTest(key), open(os.path.join(LOGOS, one["logo"] + ".svg"), encoding="utf-8") as f:
                fills = {fill.lower() for fill in re.findall(r'fill="(#[0-9A-Fa-f]{3,8})"', f.read())}
                if one["mono"]:
                    self.assertLessEqual(len(fills), 1, fills)
                else:
                    self.assertTrue(fills)


class Offered(unittest.TestCase):
    def test_the_add_form_offers_the_media_services_by_their_makers_hosted_mcp(self):
        # each maker's documented address, a brand of its own, a name both agents take
        self.assertEqual([(key, name) for key, name, _ in connectors.OFFERED],
                         [("fal", "fal"), ("elevenlabs", "elevenlabs"), ("bfl", "flux"), ("runway", "runway"),
                          ("figma", "figma")])
        for key, name, url in connectors.OFFERED:
            with self.subTest(key):
                self.assertEqual(connectors.brand(name, url), key)
                self.assertEqual(connectors.add("claude", name, url, "local"),
                                 ["claude", "mcp", "add", "--transport", "http", "--scope", "local", name, url])
                self.assertEqual(connectors.add("codex", name, url), ["codex", "mcp", "add", name, "--url", url])


class LoginUrl(unittest.TestCase):
    def test_the_address_claude_waits_on_is_read_whole_and_once(self):
        self.assertEqual(connectors.login_url(WAITING), ASKED)

    def test_it_is_read_from_plain_lines_too(self):
        plain = f"If the browser didn't open, visit:\n  {ASKED}\n\nWaiting for authorization… (^C to cancel)\n"
        self.assertEqual(connectors.login_url(plain), ASKED)
        self.assertEqual(connectors.login_url(f"visit:\n  https://mcp.box.com/authorize?state=x1\n"),
                         "https://mcp.box.com/authorize?state=x1")

    def test_none_before_it_is_printed_or_where_it_is_cut(self):
        self.assertIsNone(connectors.login_url('Starting authentication for "standin"…\r\n'))
        self.assertIsNone(connectors.login_url(""))
        self.assertIsNone(connectors.login_url(None))
        # the line not ended yet: the address may be longer than what was read
        self.assertIsNone(connectors.login_url(f"If the browser didn't open, visit:\r\n  {ASKED[:60]}"))

    def test_an_address_that_is_not_one_to_open_is_none(self):
        for url in ("http://mcp.box.com/authorize", "file:///etc/hosts", "javascript:alert(1)", "https://",
                    "-https://box.com"):
            with self.subTest(url=url):
                self.assertIsNone(connectors.login_url(f"visit:\n  {url}\n"))

    def test_another_lines_address_is_not_it(self):
        self.assertIsNone(connectors.login_url("See https://docs.claude.com/mcp for help\n"))


class Cli(unittest.TestCase):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = connectors.main(["connectors.py", *args])
        return code, out.getvalue(), err.getvalue()

    def test_it_answers_each_command_in_json(self):
        for args, made in ((("login", "claude", "claude.ai Box"), ["claude", "mcp", "login", "claude.ai Box"]),
                           (("logout", "codex", "sentry"), ["codex", "mcp", "logout", "sentry"]),
                           (("add", "claude", "dropbox", DROPBOX, "user"), connectors.add("claude", "dropbox", DROPBOX,
                                                                                           "user")),
                           (("add", "codex", "dropbox", DROPBOX), connectors.add("codex", "dropbox", DROPBOX)),
                           (("form", "claude", "dropbox", DROPBOX, "local"),
                            {"argv": connectors.add("claude", "dropbox", DROPBOX, "local"), "name": "dropbox"}),
                           (("form", "codex", "my box", DROPBOX),
                            {"field": "name", "error": "Letters, digits, - and _ only"}),
                           (("toggle", "sentry", "off"), "/mcp disable sentry"),
                           (("toggle", "sentry", "on"), "/mcp enable sentry"),
                           (("brand", "Box"), "box"), (("brand", "harbor", "mcp.box.com"), "box"),
                           (("brand", "harbor"), None), (("login-url", WAITING), ASKED)):
            with self.subTest(args=args):
                code, out, _err = self.run_main(*args)
                self.assertEqual((code, json.loads(out)), (0, made))

    def test_a_refused_one_or_a_wrong_call_is_the_usage(self):
        for args in ((), ("login",), ("login", "claude", "--help"), ("add", "claude", "box", "http://box.com", "local"),
                     ("toggle", "sentry", "maybe"), ("form", "gemini", "box", BOX),
                     ("form", "claude", "box", BOX, "project"), ("toggle", "-x", "on"), ("remove", "claude", "box"),
                     ("login", "claude", "box", "more")):
            with self.subTest(args=args):
                code, out, err = self.run_main(*args)
                self.assertEqual((code, out), (2, ""))
                self.assertIn("usage: connectors.py", err)


class Page(unittest.TestCase):
    def test_claude_ais_connectors_are_added_on_its_own_page(self):
        self.assertEqual(connectors.CLAUDE_AI, "https://claude.ai/settings/connectors")


if __name__ == "__main__":
    unittest.main()
