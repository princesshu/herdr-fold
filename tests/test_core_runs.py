"""Tests for core/runs.py in a temporary HOME: the agents' runs (Claude's background sessions, Codex's exec runs and
cloud tasks) with what each made and cost, the Chats list leaving them out, and each started or acted on with the
agent's own command. Stand-ins answer for claude and codex; the sessions, rollouts and tasks are invented."""
import json
import os
import sys
import time

from support import PACKAGE, set_attrs, set_env, stubs

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import chats  # noqa: E402
import runs  # noqa: E402
import test_core_tokens as made  # noqa: E402
from test_core_tokens import FOLDER, SESSION, THREAD, line, stamp  # noqa: E402

PROMPT = "Make a 16:9 hero image of a calm harbour at dawn; save it as WebP in renders/"
TASK = "task_e_6a1b2c3d4e5f"
# a stand-in for claude and codex: logs its folder and arguments, answers by its first word (codex cloud's by two)
STAND_IN = "\n".join([
    "#!/usr/bin/python3 -B", "import json, os, sys, time",
    "with open(os.environ['RUNS_STAND_IN_LOG'], 'a') as f:",
    "    f.write(json.dumps({'cwd': os.getcwd(), 'argv': [os.path.basename(sys.argv[0])] + sys.argv[1:]}) + '\\n')",
    "key = os.path.basename(sys.argv[0]) + ' ' + ' '.join(sys.argv[1:3 if sys.argv[1] == 'cloud' else 2])",
    "with open(os.environ['RUNS_STAND_IN_ANSWERS']) as f:",
    "    out, error, code, wait = ((json.load(f).get(key) or ['', 'No answer', 1]) + [0])[:4]",
    "time.sleep(wait)", "sys.stdout.write(out)", "sys.stderr.write(error)", "sys.exit(code)", ""])


def tool(name, id, minute, **told):
    return line({"isSidechain": False, "type": "assistant", "timestamp": stamp(minute), "cwd": FOLDER,
                 "message": {"model": made.OPUS, "id": f"msg_{id}", "role": "assistant",
                             "content": [{"type": "tool_use", "id": id, "name": name, "input": told}],
                             "usage": made.usage(input=1000, output=500)}})


def result(id, text, minute):
    return line({"isSidechain": False, "type": "user", "timestamp": stamp(minute), "cwd": FOLDER,
                 "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": id,
                                                          "content": [{"type": "text", "text": text}]}]}})


def event(kind, minute):
    return line({"timestamp": stamp(minute), "type": "event_msg", "payload": {"type": kind}})


def codex_said(payload, minute):
    return line({"timestamp": stamp(minute), "type": "response_item", "payload": payload})


def asked_codex(text, minute=0):
    return codex_said({"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}, minute)


def patch(call, *paths, minute=2):
    body = "*** Begin Patch\n" + "".join(f"*** Update File: {one}\n@@\n-a\n+b\n" for one in paths) + "*** End Patch"
    return codex_said({"type": "custom_tool_call", "name": "apply_patch", "call_id": call, "input": body}, minute)


class Runs(made.Home):
    def setUp(self):
        super().setUp()
        self.log, self.answers = os.path.join(self.home, "calls"), os.path.join(self.home, "answers.json")
        self.answer({})
        programs = stubs(os.path.join(self.home, "bin"), {"claude": STAND_IN, "codex": STAND_IN})
        set_env(self, PATH=os.pathsep.join([programs, "/usr/bin", "/bin"]), RUNS_STAND_IN_LOG=self.log,
                RUNS_STAND_IN_ANSWERS=self.answers, HERDR_PLUGIN_STATE_DIR=os.path.join(self.home, "sidebar"))
        os.makedirs(FOLDER.replace("/Users/dev", self.home), exist_ok=True)

    def answer(self, answers):
        with open(self.answers, "w", encoding="utf-8") as f:
            json.dump(answers, f)

    def agents(self, *listed, code=0, error=""):
        self.answer({"claude agents": [json.dumps(listed), error, code]})

    def calls(self, program=None):
        try:
            with open(self.log, encoding="utf-8") as f:
                found = [json.loads(one) for one in f]
        except FileNotFoundError:
            return []
        return [one for one in found if program in (None, one["argv"][0])]

    def listed(self):
        return {one["key"]: one for one in runs.runs(fresh=True)["runs"]}

    def hero(self, state="done", **more):
        """The background session that made the hero images, as `claude agents --json --all` lists it."""
        self.session(made.asked(PROMPT) + tool("Write", "t1", 1, file_path=f"{FOLDER}/renders/hero-dawn-a.webp")
                     + tool("Write", "t2", 3, file_path="renders/hero-dawn-b.webp")
                     + tool("Edit", "t3", 4, file_path=f"{FOLDER}/docs/api.md"))
        return {"kind": "background", "id": "7c5dcf5d", "sessionId": SESSION, "cwd": FOLDER, "state": state,
                "startedAt": made.TEN * 1000, **more}

    def test_a_background_session_with_its_prompt_media_cost_and_how_it_ran(self):
        self.agents(self.hero(), {"kind": "interactive", "cwd": FOLDER, "startedAt": made.TEN * 1000, "pid": 7})
        found = self.listed()
        self.assertEqual(list(found), ["claude:7c5dcf5d"])
        one = found["claude:7c5dcf5d"]
        self.assertEqual((one["title"], one["prompt"], one["place"], one["state"], one["made"], one["took"]),
                         (PROMPT, PROMPT, "lumen-api", "done", "2 images", "4 min"))
        self.assertEqual(one["media"], [{"path": f"{FOLDER}/renders/hero-dawn-{n}.webp", "kind": "image"}
                                        for n in "ab"])
        self.assertEqual(one["ran_as"], "Background session · Claude · Opus 5.5")
        self.assertTrue(one["cost"].startswith("~$"), one["cost"])
        self.assertTrue(one["cost_line"].endswith(" API value"), one["cost_line"])
        self.assertEqual((one["session"], one["now"], one["group"]), (SESSION, None, "Earlier"))
        self.assertEqual([call["argv"] for call in self.calls("claude")], [["claude", "agents", "--json", "--all"]])

    def test_the_chats_list_leaves_out_what_runs_lists(self):
        # one home a thing: a background session and a codex exec run are Runs', an interactive chat Chats'
        self.agents(self.hero())
        self.session(made.asked("Fix the page past the last one"), session=made.OTHER)
        self.rollout(made.meta("exec") + asked_codex("Paginate /shelves like /books"))
        listed = {one.id for one in chats.local(chats.state_folder())}
        self.assertEqual(listed, {SESSION, made.OTHER})      # the session is a chat until runs are read once
        self.assertEqual(set(self.listed()), {"claude:7c5dcf5d", f"codex:{THREAD}"})
        self.assertEqual({one.id for one in chats.local(chats.state_folder())}, {made.OTHER})

    def test_a_working_session_says_its_last_step_and_one_that_waits_on_you_runs_too(self):
        self.agents(self.hero("working"), {**self.hero("blocked"), "id": "9e8d7c6b", "status": "waiting",
                                          "waitingFor": "permission prompt"})
        found = self.listed()
        self.assertEqual({key: (one["state"], one["group"], one["now"], one["made"]) for key, one in found.items()},
                         {"claude:7c5dcf5d": ("running", "Running", "Edit docs/api.md", "2 images"),
                          "claude:9e8d7c6b": ("blocked", "Running", "Edit docs/api.md", "2 images")})
        self.assertEqual(found["claude:9e8d7c6b"]["waiting"], "permission prompt")
        self.assertEqual(runs.working(), 2)

    def test_a_pr_is_the_one_gh_pr_create_opened_never_one_only_viewed(self):
        self.session(made.asked("Bump dependencies, run the tests")
                     + tool("Bash", "t1", 1, command="gh pr view 12")
                     + result("t1", "https://github.com/lumenworks/lumen-api/pull/12", 1)
                     + tool("Bash", "t2", 2, command="gh pr create --fill")
                     + result("t2", "https://github.com/lumenworks/lumen-api/pull/61\n", 3))
        self.agents({"kind": "background", "id": "1a2b3c4d", "sessionId": SESSION, "cwd": FOLDER, "state": "done"})
        one = self.listed()["claude:1a2b3c4d"]
        self.assertEqual((one["made"], one["pr"]), ("PR #61", {"number": 61, "url":
                                                               "https://github.com/lumenworks/lumen-api/pull/61"}))

    def test_a_codex_exec_run_with_the_files_it_patched_and_how_it_ended(self):
        self.rollout(made.meta("exec") + made.turn(made.GPT) + asked_codex("Paginate /shelves like /books")
                     + event("task_started", 1) + patch("c1", "lumen/shelves.py", "tests/test_shelves.py")
                     + made.record("r1", minute=3, input_tokens=2000, output_tokens=400)
                     + event("task_complete", 4))
        self.rollout(made.meta("cli", id="0199c0de-0000-7000-8000-000000000002") + asked_codex("Talk it over"),
                     id="0199c0de-0000-7000-8000-000000000002")
        found = self.listed()
        self.assertEqual(list(found), [f"codex:{THREAD}"])
        one = found[f"codex:{THREAD}"]
        self.assertEqual((one["title"], one["state"], one["made"], one["took"], one["ran_as"]),
                         ("Paginate /shelves like /books", "done", "2 files", "4 min",
                          "codex exec · Codex · GPT-6 Astra"))
        self.assertEqual(one["files"], [f"{FOLDER}/lumen/shelves.py", f"{FOLDER}/tests/test_shelves.py"])

    def test_a_codex_run_aborted_failed_and_one_never_ended_runs_until_it_goes_quiet(self):
        path = self.rollout(made.meta("exec") + asked_codex("Draft the release notes") + event("task_started", 1)
                            + event("turn_aborted", 2))
        self.assertEqual(self.listed()[f"codex:{THREAD}"]["made"], "failed")
        self.rollout(made.meta("exec") + asked_codex("Draft the release notes") + event("task_started", 1))
        self.assertEqual(self.listed()[f"codex:{THREAD}"]["state"], "running")
        os.utime(path, (time.time() - runs.STALE - 60,) * 2)
        self.assertEqual(self.listed()[f"codex:{THREAD}"]["state"], "done")

    def test_a_cloud_task_with_its_diff_and_no_cost_its_environment_offered_again(self):
        task = {"id": TASK, "url": f"https://codex.example/tasks/{TASK}", "title": "Paginate /shelves like /books",
                "status": "ready", "updated_at": "2026-11-13T17:40:00Z", "environment_id": "env_lumen",
                "environment_label": "lumen-api", "summary": {"files_changed": 4, "lines_added": 62,
                                                              "lines_removed": 9}, "is_review": False,
                "attempt_total": 1}
        self.answer({"codex cloud list": [json.dumps({"tasks": [task], "cursor": None}), "", 0]})
        found = runs.runs(fresh=True)
        one = found["runs"][0]
        self.assertEqual((one["key"], one["place"], one["state"], one["made"], one["diff"], one["cost"], one["at"]),
                         (f"codex:{TASK}", "lumen-api", "ready", "4 files", "4 files +62 −9", "–", 1794591600))
        self.assertEqual((one["ran_as"], one["url"]), ("Codex cloud", task["url"]))
        self.assertEqual(found["envs"], [{"id": "env_lumen", "label": "lumen-api"}])

    def test_a_list_that_fails_says_the_agents_words_and_none_installed_lists_nothing(self):
        self.agents(code=1, error="Not logged in · Please run /login\n")
        self.assertEqual(runs.runs(fresh=True)["notes"], ["Couldn't list Claude's runs: Not logged in · Please run "
                                                          "/login", "Couldn't list Codex cloud's runs: No answer"])
        set_env(self, PATH="/usr/bin:/bin")
        self.assertEqual({key: runs.runs(fresh=True)[key] for key in ("runs", "notes")}, {"runs": [], "notes": []})

    def test_the_background_list_is_kept_a_while(self):
        self.agents(self.hero())
        runs.runs()
        runs.runs()
        runs.working()
        self.assertEqual(len(self.calls("claude")), 1)
        set_attrs(self, runs, KEEP=0)
        runs.working()
        self.assertEqual(len(self.calls("claude")), 2)

    def test_a_run_starts_as_the_agent_starts_one(self):
        folder = FOLDER.replace("/Users/dev", self.home)
        self.answer({"claude --bg": ["backgrounded · 7c5dcf5d · hero\n", "", 0],
                     "codex cloud exec": [f"https://codex.example/tasks/{TASK}\n", "", 0]})
        self.assertEqual(runs.start("claude", "here", folder, PROMPT),
                         {"ok": True, "said": "Started in the background"})
        self.assertEqual(runs.start("codex", "cloud", folder, "Paginate /shelves", "env_lumen"),
                         {"ok": True, "said": "Sent to Codex cloud"})
        self.assertEqual([(call["cwd"], call["argv"]) for call in self.calls()],
                         [(os.path.realpath(folder), ["claude", "--bg", PROMPT]),
                          (os.path.realpath(folder), ["codex", "cloud", "exec", "--env", "env_lumen",
                                                      "Paginate /shelves"])])
        self.assertEqual(runs.start("claude", "here", folder, "  "), {"ok": False,
                                                                     "said": "A prompt and a folder are needed"})

    def test_a_start_that_fails_says_the_agents_own_words(self):
        folder = FOLDER.replace("/Users/dev", self.home)
        self.answer({"claude --bg": ["", "Error: not logged in\n", 1], "codex exec": ["", "Not signed in\n", 1]})
        self.assertEqual(runs.start("claude", "here", folder, PROMPT),
                         {"ok": False, "said": "Claude didn't start it: Error: not logged in"})
        self.assertEqual(runs.start("codex", "here", folder, PROMPT),
                         {"ok": False, "said": "Codex didn't start it: Not signed in"})

    def test_a_codex_exec_run_left_running_on_its_own(self):
        folder = FOLDER.replace("/Users/dev", self.home)
        self.answer({"codex exec": ["", "", 0, 2]})
        set_attrs(self, runs, TOLD=0.3)
        self.assertEqual(runs.start("codex", "here", folder, PROMPT), {"ok": True, "said": "Started with codex exec"})

    def test_stop_remove_diff_and_apply_are_the_agents_commands(self):
        folder = FOLDER.replace("/Users/dev", self.home)
        self.answer({"claude stop": ["", "", 0], "claude rm": ["", "Unpushed commits in its worktree\n", 1],
                     "codex cloud diff": ["diff --git a/x b/x\n", "", 0], "codex cloud apply": ["Applied\n", "", 0],
                     "claude agents": ["[]", "", 0]})
        self.assertEqual(runs.act("stop", "7c5dcf5d"), {"ok": True, "said": "Stopped"})
        self.assertEqual(runs.act("remove", "7c5dcf5d"),
                         {"ok": False, "said": "Claude didn't remove it: Unpushed commits in its worktree"})
        shown = runs.act("diff", TASK)
        with open(shown["path"], encoding="utf-8") as f:
            self.assertEqual(f.read(), "diff --git a/x b/x\n")
        self.assertEqual(runs.act("apply", TASK, folder), {"ok": True, "said": "Applied"})
        self.assertEqual([call["argv"][1:] for call in self.calls()],
                         [["stop", "7c5dcf5d"], ["agents", "--json", "--all"], ["rm", "7c5dcf5d"],
                          ["cloud", "diff", TASK], ["cloud", "apply", TASK]])
        self.assertEqual(self.calls()[-1]["cwd"], os.path.realpath(folder))

    def test_a_runs_day_and_time(self):
        now = time.mktime((2026, 11, 25, 15, 0, 0, 0, 0, -1))
        self.assertEqual(runs.when(time.mktime((2026, 11, 25, 14, 2, 0, 0, 0, -1)), now), ("Today", "14:02"))
        self.assertEqual(runs.when(time.mktime((2026, 11, 24, 17, 40, 0, 0, 0, -1)), now), ("Yesterday", "17:40"))
        self.assertEqual(runs.when(time.mktime((2026, 11, 21, 9, 0, 0, 0, 0, -1)), now), ("Earlier", "Nov 21"))
        self.assertEqual([runs.took(times) for times in ([], [0, 20], [0, 240], [0, 3900])],
                         [None, "<1 min", "4 min", "1 h 5 min"])
