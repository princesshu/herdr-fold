"""Tests for core/agent_state.py in a temporary home and folder, with stand-in agents: which are installed, signed in
and on which plan, what stands in the place of a setup that cannot show, a server checked by a stand-in claude; nothing
of theirs written, nothing of an account kept."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

from support import PACKAGE, set_env, stubs

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import agent_setup    # noqa: E402
import agent_state    # noqa: E402

# `claude auth status --json` signed in on a plan, as Claude 2.1.325 prints it: its account's fields never kept
SIGNED_IN = {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty", "analyticsDisabled": False,
             "projectsDirectory": "~/.claude/projects", "configDirectory": "~/.claude", "loginExpiresAt": None,
             "email": "dev@lumen.example", "orgId": "0f6e5d4c-3b2a-4190-8a7b-6c5d4e3f2a1b", "orgName": "Lumen Labs",
             "subscriptionType": "max", "storedClaudeAiLogin": True, "planTier": "lumen_tier_20x"}


class AgentState(unittest.TestCase):
    def setUp(self):
        top = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, top)
        self.home = os.path.join(top, "home")
        self.folder = os.path.join(top, "work", "lumen-api")
        self.managed = os.path.join(top, "managed")     # the organization's folder, never this machine's own
        os.makedirs(self.folder)
        self.bin = os.path.join(self.home, "bin")       # the stand-in programs: the only ones a test finds
        for patch in (mock.patch.object(agent_setup, "MANAGED_DIR", self.managed),
                      mock.patch.object(agent_setup, "find", lambda name: shutil.which(name, path=self.bin))):
            patch.start()
            self.addCleanup(patch.stop)
        set_env(self, CODEX_HOME=None)

    def put(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def files(self):
        """Every file under the home, the folder and the managed folder, with its text: what a test checks nothing
        wrote."""
        found = {}
        for base in (self.home, self.folder, self.managed):
            for here, _, names in os.walk(base):
                for name in names:
                    with open(os.path.join(here, name), encoding="utf-8") as f:
                        found[os.path.join(here, name)] = f.read()
        return found

    def stand_in(self, answers):
        """A stand-in claude first on the PATH: `mcp get NAME` prints ANSWERS[NAME] ([out, error, exit code]); each
        call's folder and arguments go to the log, whose path it returns."""
        log, given = os.path.join(self.home, "claude-calls"), self.put(os.path.join(self.home, "answers.json"),
                                                                       json.dumps(answers))
        programs = stubs(self.bin, {"claude": "\n".join([
            "#!/usr/bin/python3 -B", "import json, os, sys, time",
            "with open(os.environ['CLAUDE_STAND_IN_LOG'], 'a') as f:",
            "    f.write(json.dumps({'cwd': os.getcwd(), 'argv': sys.argv[1:]}) + '\\n')",
            "if sys.argv[-1] == 'slow':", "    time.sleep(5)",
            "with open(os.environ['CLAUDE_STAND_IN_ANSWERS']) as f:",
            "    out, error, code = json.load(f).get(sys.argv[-1], ['', 'No answer', 1])",
            "sys.stdout.write(out)", "sys.stderr.write(error)", "sys.exit(code)", ""])})
        set_env(self, HOME=self.home, PATH=os.pathsep.join([programs, "/usr/bin", "/bin"]), CLAUDE_STAND_IN_LOG=log,
                CLAUDE_STAND_IN_ANSWERS=given)
        return log

    def calls(self, log):
        try:
            with open(log, encoding="utf-8") as f:
                return [json.loads(line) for line in f]
        except FileNotFoundError:
            return []

    def test_check_reads_claude_mcp_get(self):
        def got(name, status, *more):
            return ["\n".join([f"{name}:", "  Scope: Project config (shared via .mcp.json)", f"  Status: {status}",
                               *more, ""]), "", 0]
        log = self.stand_in({
            "sentry": got("sentry", "✗ Failed to connect", "  Issue: npx ENOENT", "  Type: stdio", "  Command: npx",
                          "  Args: -y @sentry/mcp-server", "  Environment:", "    SENTRY_AUTH_TOKEN=sntrys_ghi789", "",
                          'To remove this server, run: claude mcp remove "sentry" -s project'),
            "claude.ai Box": got("claude.ai Box", "! Needs authentication", "  Type: claudeai-proxy",
                                 "  URL: https://mcp.box.com/?session=b0x1"),
            "Dropbox": got("Dropbox", "✓ Connected", "  Type: http", "  URL: https://mcp.dropbox.com/mcp",
                           "  Headers:", "    Authorization: Bearer sl.def456"),
            # an unapproved server of the project's .mcp.json: Claude says so and starts nothing
            "harbor-api": got("harbor-api", "⏸ Pending approval (run `claude` to approve)", "  Type: http",
                              "  URL: https://api.harbor.dev/mcp"),
            "metrics": got("metrics", "⊘ Disabled for this project (re-enable via /mcp)", "  Type: stdio"),
            "claude.ai Linear": got("claude.ai Linear", "! Connected · tools fetch failed", "  Issue: HTTP 500"),
            "Notion": got("Notion", "✗ Connection error", "  Type: http", "  URL: https://mcp.notion.com/mcp"),
            "nope": ["", 'No MCP server found with name: "nope".\n', 1]})
        before = self.files()
        found = {name: agent_state.check(self.folder, name) for name in (
            "sentry", "claude.ai Box", "Dropbox", "harbor-api", "metrics", "claude.ai Linear", "Notion", "nope")}
        self.assertEqual(found, {
            "sentry": {"state": "failed", "error": "npx ENOENT", "url": None},
            "claude.ai Box": {"state": "sign in", "error": None, "url": "mcp.box.com"},
            "Dropbox": {"state": "on", "error": None, "url": "mcp.dropbox.com/mcp"},
            "harbor-api": {"state": "not approved", "error": None, "url": "api.harbor.dev/mcp"},
            "metrics": {"state": "off here", "error": None, "url": None},
            "claude.ai Linear": {"state": "failed", "error": "HTTP 500", "url": None},
            "Notion": {"state": "failed", "error": "Connection error", "url": "mcp.notion.com/mcp"},
            "nope": {"state": "not checked", "error": 'No MCP server found with name: "nope".', "url": None}})
        self.assertEqual(self.calls(log), [{"cwd": os.path.realpath(self.folder), "argv": ["mcp", "get", name]}
                                           for name in found])
        self.assertNotIn("sl.def456", json.dumps(found))
        self.assertEqual({k: v for k, v in self.files().items() if k != log}, before)
        # no answer in time: the stand-in is stopped, not waited for
        with mock.patch.object(agent_state, "CHECK_TIMEOUT", 0.5):
            start = time.monotonic()
            self.assertEqual(agent_state.check(self.folder, "slow"),
                             {"state": "not checked", "error": "No answer in 0.5 s", "url": None})
            self.assertLess(time.monotonic() - start, 3)
        with mock.patch.object(agent_setup, "find", return_value=None):
            self.assertEqual(agent_state.check(self.folder, "sentry"),
                             {"state": "not checked", "error": "claude is not on this machine's PATH", "url": None})

    def test_a_name_like_an_option_is_refused(self):
        log = self.stand_in({})
        for name in ("-h", "--help", "", "Box\x1b[2J", "sentry\nrm", None):
            with self.assertRaises(ValueError):
                agent_state.check(self.folder, name)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(agent_state.main(["agent_state.py", "check", "claude", self.folder, "--help"]), 2)
        self.assertEqual(self.calls(log), [])

    def programs(self, answers):
        """Stand-in agents in the test's bin, one for each of ANSWERS ({program: {its arguments: [out, error, exit code]
        or [out, error, exit code, seconds it waits first]}}), read at each call; each call's program, folder and
        arguments go to the log, whose path it returns."""
        log, self.answers = os.path.join(self.home, "agent-calls"), os.path.join(self.home, "agent-answers.json")
        self.answer(answers)
        script = "\n".join([
            "#!/usr/bin/python3 -B", "import json, os, sys, time",
            "name = os.path.basename(sys.argv[0])",
            "with open(os.environ['AGENT_STAND_IN_LOG'], 'a') as f:",
            "    f.write(json.dumps({'program': name, 'cwd': os.getcwd(), 'argv': sys.argv[1:]}) + '\\n')",
            "with open(os.environ['AGENT_STAND_IN_ANSWERS']) as f:",
            "    out, error, code, *wait = json.load(f).get(name, {}).get(' '.join(sys.argv[1:]), ['', 'unknown', 2])",
            "time.sleep(wait[0] if wait else 0)",
            "sys.stdout.write(out)", "sys.stderr.write(error)", "sys.exit(code)", ""])
        stubs(self.bin, dict.fromkeys(answers, script))
        set_env(self, HOME=self.home, AGENT_STAND_IN_LOG=log, AGENT_STAND_IN_ANSWERS=self.answers)
        patch = mock.patch.dict(agent_state.KEPT, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        return log

    def answer(self, answers):
        """What the stand-in agents answer from now on (programs()'s ANSWERS)."""
        self.put(self.answers, json.dumps(answers))

    def codex_home(self, *parts):
        return os.path.join(self.home, ".codex", *parts)

    def token_count(self, plan, limits=True):
        """A Codex chat's token_count line, as Codex 0.166 writes one: its rate limits naming the PLAN (no LIMITS: an
        API key's, none)."""
        return json.dumps({"timestamp": "2026-11-12T09:00:00.000Z", "type": "event_msg", "payload": {
            "type": "token_count", "info": None, "rate_limits": {
                "primary": {"used_percent": 12.0, "window_minutes": 300, "resets_at": 1762947600},
                "secondary": {"used_percent": 30.0, "window_minutes": 10080, "resets_at": 1763380800},
                "plan_type": plan} if limits else None}})

    def rollout(self, day, *lines, age=0):
        """A Codex chat of DAY (in November 2026) holding LINES, changed AGE seconds ago; its path."""
        path = self.put(self.codex_home("sessions", "2026", "11", day, f"rollout-2026-11-{day}T09-00-00-{age}.jsonl"),
                        "\n".join(lines) + "\n")
        os.utime(path, (time.time() - age, time.time() - age))
        return path

    def test_installed_agents_by_path(self):
        log = self.programs({"claude": {"auth status --json": [json.dumps(SIGNED_IN), "", 0]}})
        found = agent_state.machine_agents(self.home)
        self.assertEqual([(a["key"], a["name"], a["installed"]) for a in found],
                         [("claude", "Claude", True), ("codex", "Codex", False), ("opencode", "OpenCode", False),
                          ("copilot", "Copilot", False), ("gemini", "Gemini CLI", False)])
        self.assertEqual(found[1], {"key": "codex", "name": "Codex", "installed": False, "signed_in": None,
                                    "plan": None, "login": ["codex", "login"],
                                    "install": "npm install -g @openai/codex",
                                    "page": "https://developers.openai.com/codex/cli"})
        self.assertEqual([(a["login"], a["install"]) for a in found if a["key"] != "codex"], [
            (["claude", "auth", "login"], "npm install -g @anthropic-ai/claude-code"),
            (["opencode", "auth", "login"], "npm install -g @opencode/cli"),
            (["copilot", "login"], "npm install -g @github/copilot"),
            (["gemini"], "npm install -g @google/gemini-cli")])
        self.assertTrue(all(a["page"].startswith("https://") for a in found))
        # where the caller looks: Gemini CLI alone is there
        here = agent_state.machine_agents(self.home, which=lambda name: os.path.join(self.bin, name)
                                          if name == "gemini" else None)
        self.assertEqual([a["key"] for a in here if a["installed"]], ["gemini"])
        self.assertEqual([c["program"] for c in self.calls(log)], ["claude"])

    def test_claude_signed_in_and_plan_never_its_email(self):
        log = self.programs({"claude": {"auth status --json": [json.dumps(SIGNED_IN), "", 0]}})
        found = agent_state.machine_agents(self.home)
        self.assertEqual((found[0]["signed_in"], found[0]["plan"]), (True, "Max"))
        for private in ("dev@lumen.example", "Lumen Labs", SIGNED_IN["orgId"], "lumen_tier_20x", "projects"):
            self.assertNotIn(private, json.dumps(found))
        self.assertEqual(self.calls(log)[0]["argv"], ["auth", "status", "--json"])
        api_key = {"loggedIn": True, "authMethod": "api_key", "apiProvider": "firstParty",
                   "apiKeySource": "ANTHROPIC_API_KEY"}
        for said, code, expected in (
                ({**SIGNED_IN, "subscriptionType": "pro"}, 0, (True, "Pro")),
                ({**SIGNED_IN, "subscriptionType": "lumen-galaxy"}, 0, (True, None)),     # no word for it: none
                (api_key, 0, (True, "API key")), ({**api_key, "authMethod": "api_key_helper"}, 0, (True, "API key")),
                ({"loggedIn": True, "authMethod": "oauth_token", "apiProvider": "firstParty"}, 0, (True, None)),
                ({"loggedIn": False, "authMethod": "none", "apiProvider": "firstParty"}, 1, (False, None)),
                ("Not logged in. Run claude auth login to authenticate.", 1, (None, None)),     # no JSON: unknown
                ({"loggedIn": "yes", "authMethod": "claude.ai", "subscriptionType": ["max"]}, 0, (None, None))):
            with self.subTest(said):
                self.answer({"claude": {"auth status --json": [said if isinstance(said, str) else json.dumps(said), "",
                                                               code]}})
                claude = agent_state.machine_agents(self.home, fresh=True)[0]
                self.assertEqual((claude["signed_in"], claude["plan"]), expected)

    def test_codex_signed_in_by_exit_code_alone(self):
        log = self.programs({"codex": {"login status": ["", "Logged in using ChatGPT\n", 0]}})
        self.rollout("10", self.token_count("pro"), age=300)
        cut = '{"type": "event_msg", "payload": {"type": "token_count", "rate_limits": {"plan_type": "pro"'
        self.rollout("11", self.token_count("pro"), self.token_count("plus"), cut, age=200)
        self.rollout("12", json.dumps({"type": "session_meta", "payload": {"cwd": self.folder}}), age=100)   # no count
        codex = agent_state.machine_agents(self.home)[1]
        self.assertEqual((codex["installed"], codex["signed_in"], codex["plan"]), (True, True, "Plus"))
        self.assertNotIn("sk-proj", json.dumps(codex))
        self.assertEqual(self.calls(log), [{"program": "codex", "cwd": self.calls(log)[0]["cwd"],
                                            "argv": ["login", "status"]}])
        # the newest chat that names a plan tells it: a count that names none (a subagent's, one with no limits)
        # passed over; an id with no word, none
        for lines, plan in (([self.token_count(None), self.token_count("plus", limits=False)], "Plus"),
                            ([self.token_count("lumen-galaxy")], None), ([self.token_count("team")], "Team"),
                            # a newer id by its family's word: a self-serve Business seat, Pro's lighter tier
                            ([self.token_count("self_serve_business_prolite")], "Business"),
                            ([self.token_count("prolite")], "Pro")):
            with self.subTest(lines):
                self.rollout("13", *lines, age=len(lines))
                self.assertEqual(agent_state.machine_agents(self.home, fresh=True)[1]["plan"], plan)
        # an API key's chats name none
        shutil.rmtree(self.codex_home("sessions"))
        self.rollout("14", self.token_count(None, limits=False))
        self.assertIsNone(agent_state.machine_agents(self.home, fresh=True)[1]["plan"])
        self.answer({"codex": {"login status": ["", "Not logged in\n", 1]}})
        self.assertEqual([agent_state.machine_agents(self.home, fresh=True)[1][key] for key in ("signed_in", "plan")],
                         [False, None])

    def test_codex_on_an_api_key_by_its_status_words(self):
        # Codex 0.169 says how it is signed in on stderr; a plan an older chat named does not outlive the key
        said = "Logged in using an API key - sk-proj-***9f2c\n"
        self.programs({"codex": {"login status": ["", said, 0]}})
        self.rollout("10", self.token_count("pro"), age=300)
        codex = agent_state.machine_agents(self.home)[1]
        self.assertEqual((codex["signed_in"], codex["plan"]), (True, "API key"))
        self.assertNotIn("sk-proj", json.dumps(codex))
        self.assertNotIn("9f2c", json.dumps(agent_state.KEPT, default=str))
        for out, error, code, plan in ((said, "", 0, "API key"), ("", "  " + said, 0, "API key"),
                                       ("", "Logged in using ChatGPT\n", 0, "Pro"),
                                       ("", "Logged in using an access token\n", 0, "Pro"),
                                       ("", "note: Logged in using an API key\n", 0, "Pro"),
                                       ("", said, 1, None)):
            with self.subTest((out, error, code)):
                self.answer({"codex": {"login status": [out, error, code]}})
                self.assertEqual(agent_state.machine_agents(self.home, fresh=True)[1]["plan"], plan)

    def test_opencode_is_signed_in_where_its_own_list_names_an_integration(self):
        # `opencode auth list --format json` as OpenCode 2.4 prints it: an integration's name and how it is connected
        # (a stored credential's label, an environment variable's name), never a secret; its plan never told
        ask = "auth list --format json --standalone"
        stored = [{"id": "anthropic", "name": "Anthropic", "connections": [{"type": "credential", "label": "work"}]}]
        log = self.programs({"opencode": {ask: [json.dumps(stored), "", 0]}})
        opencode = agent_state.machine_agents(self.home)[2]
        self.assertEqual(opencode, {"key": "opencode", "name": "OpenCode", "installed": True, "signed_in": True,
                                    "plan": None, "login": ["opencode", "auth", "login"],
                                    "install": "npm install -g @opencode/cli", "page": "https://opencode.ai/docs/"})
        self.assertEqual([c["argv"] for c in self.calls(log)], [ask.split()])    # a private server, never its service
        env = [{"id": "openai", "name": "OpenAI", "connections": [{"type": "env", "name": "OPENAI_API_KEY"}]}]
        # none: its free models need no sign-in, so it is never said to be signed out; anything else tells nothing
        for out, code, signed in ((json.dumps(env), 0, True), ("[]\n", 0, None), ("No integrations\n", 0, None),
                                  (json.dumps({"error": "x"}), 0, None), ("", 1, None), (json.dumps(env), 1, None)):
            with self.subTest(out):
                self.answer({"opencode": {ask: [out, "", code]}})
                found = agent_state.machine_agents(self.home, fresh=True)[2]
                self.assertEqual((found["signed_in"], found["plan"]), (signed, None))
        self.assertIsNone(agent_state.standing(agent_state.machine_agents(self.home, fresh=True)[2]))

    def test_copilot_tells_no_sign_in_so_it_is_never_said_to_be_signed_out(self):
        # Copilot CLI 1.0 has no command that says whether it is signed in (its /user is asked inside it), and its
        # token is its own (the keychain, else its config.json): nothing is run or read, it is installed alone
        log = self.programs({"copilot": {}})
        copilot = agent_state.machine_agents(self.home)[3]
        self.assertEqual(copilot, {"key": "copilot", "name": "Copilot", "installed": True, "signed_in": None,
                                   "plan": None, "login": ["copilot", "login"],
                                   "install": "npm install -g @github/copilot",
                                   "page": "https://docs.github.com/copilot/how-tos/copilot-cli"})
        self.assertEqual(self.calls(log), [])
        self.assertIsNone(agent_state.standing(copilot))                      # its setup shows, never "sign in"
        self.assertEqual(agent_state.listed(copilot), {"group": "Agents on this Mac", "dim": False, "word": None,
                                                       "tone": None})

    def test_gemini_has_no_state(self):
        log = self.programs({"gemini": {}})
        self.assertEqual(agent_state.machine_agents(self.home)[4], {
            "key": "gemini", "name": "Gemini CLI", "installed": True, "signed_in": None, "plan": None,
            "login": ["gemini"], "install": "npm install -g @google/gemini-cli",
            "page": "https://github.com/google-gemini/gemini-cli"})
        self.assertEqual(self.calls(log), [])          # nothing tells it without its credentials: nothing run

    def test_an_agent_whose_setup_cannot_show_says_why_and_what_to_do(self):
        agent = {"key": "codex", "name": "Codex", "installed": True, "signed_in": True, "plan": "Plus"}
        self.assertIsNone(agent_state.standing(agent))                  # its setup shows
        self.assertIsNone(agent_state.standing({**agent, "signed_in": None}))     # not told: no state
        out = agent_state.standing({**agent, "signed_in": False})
        self.assertEqual((out["kind"], out["title"], out["command"], out["foot"]),
                         ("sign-in", "Codex is not signed in", None, "herdr-fold keeps no token."))
        self.assertEqual(out["words"], "It signs in its own way: Sign in opens it in a terminal tab, and you finish "
                                       "there, or in the browser if it asks.")
        self.assertEqual(out["actions"], [{"id": "sign-in", "label": "Sign in"}])
        # not installed wins over any state; its vendor's own line and page, nothing run
        gone = agent_state.standing({**agent, "installed": False, "signed_in": False,
                                     "install": "npm install -g @openai/codex", "page": "https://lumen.example/codex"})
        self.assertEqual((gone["kind"], gone["title"], gone["command"]),
                         ("install", "Codex is not installed", "npm install -g @openai/codex"))
        self.assertEqual(gone["actions"], [{"id": "copy", "label": "Copy"}, {"id": "page", "label": "Open its page"}])
        self.assertEqual(gone["foot"], "herdr-fold runs no installer.")
        # an agent whose setup herdr-fold does not show: nothing said in its place, nothing announced
        self.assertIsNone(agent_state.standing({"key": "gemini", "name": "Gemini CLI", "installed": True,
                                                "signed_in": None}))

    def test_the_cli_tells_each_agents_standing(self):
        self.programs({"claude": {"auth status --json": [json.dumps({"loggedIn": False, "authMethod": "none"}), "",
                                                         1]}})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(agent_state.main(["agent_state.py", "agents"]), 0)
        agents = json.loads(out.getvalue())
        self.assertEqual([(a["key"], (a["empty"] or {}).get("kind")) for a in agents],
                         [("claude", "sign-in"), ("codex", "install"), ("opencode", "install"), ("copilot", "install"),
                          ("gemini", "install")])
        self.assertEqual([a["listed"]["group"] for a in agents], ["Agents on this Mac"] + ["Not installed"] * 4)

    def test_an_agents_row_in_the_heads_list(self):
        agent = {"key": "codex", "name": "Codex", "installed": True, "signed_in": True, "plan": "Plus"}
        here = {"group": "Agents on this Mac", "dim": False}
        self.assertEqual(agent_state.listed(agent), {**here, "word": "Plus", "tone": None})
        # signed out: sign in, never a plan beside it; not told (Gemini CLI's): no word at all
        self.assertEqual(agent_state.listed({**agent, "signed_in": False}), {**here, "word": "sign in", "tone": "warn"})
        self.assertEqual(agent_state.listed({**agent, "signed_in": None, "plan": None}),
                         {**here, "word": None, "tone": None})
        # not installed: its own group, dim, whatever it last told
        self.assertEqual(agent_state.listed({**agent, "installed": False, "signed_in": False}),
                         {"group": "Not installed", "dim": True, "word": None, "tone": None})

    def test_an_answer_is_kept_a_minute(self):
        log = self.programs({"claude": {"auth status --json": [json.dumps(SIGNED_IN), "", 0]},
                             "codex": {"login status": ["", "", 0]}})
        for _ in range(2):
            self.assertEqual([a["signed_in"] for a in agent_state.machine_agents(self.home)], [True, True] + [None] * 3)
        self.assertEqual([c["program"] for c in self.calls(log)], ["claude", "codex"])
        self.answer({"claude": {"auth status --json": [json.dumps({"loggedIn": False, "authMethod": "none"}), "", 1]},
                     "codex": {"login status": ["", "", 1]}})
        # asked fresh (as after a sign-in), or a minute on: asked again
        self.assertEqual([a["signed_in"] for a in agent_state.machine_agents(self.home, fresh=True)],
                         [False, False] + [None] * 3)
        with mock.patch.object(agent_state, "KEEP", 0):
            agent_state.machine_agents(self.home)
        self.assertEqual([c["program"] for c in self.calls(log)], ["claude", "codex"] * 3)

    def test_an_agent_with_no_answer_in_time_tells_nothing(self):
        self.programs({"claude": {"auth status --json": [json.dumps(SIGNED_IN), "", 0, 5]}})
        with mock.patch.object(agent_setup, "ASK_TIMEOUT", 0.5):
            start = time.monotonic()
            claude = agent_state.machine_agents(self.home)[0]
            self.assertLess(time.monotonic() - start, 3)
        self.assertEqual((claude["installed"], claude["signed_in"], claude["plan"]), (True, None, None))

    def test_the_cli_answers_in_json(self):
        self.programs({"claude": {"auth status --json": [json.dumps(SIGNED_IN), "", 0]},
                       "codex": {"login status": ["", "", 0]}})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(agent_state.main(["agent_state.py", "agents"]), 0)
        self.assertEqual([(a["key"], a["installed"], a["signed_in"], a["plan"]) for a in json.loads(out.getvalue())],
                         [("claude", True, True, "Max"), ("codex", True, True, None), ("opencode", False, None, None),
                          ("copilot", False, None, None), ("gemini", False, None, None)])
        os.remove(os.path.join(self.bin, "claude"))
        self.stand_in({"sentry": ["sentry:\n  Status: ✓ Connected\n", "", 0]})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(agent_state.main(["agent_state.py", "check", "claude", self.folder, "sentry"]), 0)
        self.assertEqual(json.loads(out.getvalue()), {"state": "on", "error": None, "url": None})
        with contextlib.redirect_stderr(io.StringIO()) as said:
            for argv in (["agents", "--all"], ["check", "codex", self.folder, "sentry"], ["claude", self.folder], []):
                self.assertEqual(agent_state.main(["agent_state.py"] + argv), 2)
        self.assertIn("usage: agent_state.py", said.getvalue())


if __name__ == "__main__":
    unittest.main()
