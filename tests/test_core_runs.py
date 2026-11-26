"""Tests for core/runs.py in a temporary HOME: the agents' runs with what each made (its connectors' media too) and
cost, where a file came from, the Chats list leaving them out, each started or acted on with the agent's own command.
Stand-ins answer for claude and codex; the sessions, rollouts, tasks and the services' answers are invented."""
import json
import os
import sys
import time

from support import PACKAGE, set_attrs, set_env, stubs

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import chats  # noqa: E402
import runs  # noqa: E402
from jsonl import claude_project_dir  # noqa: E402
import test_core_tokens as made  # noqa: E402
from test_core_tokens import FOLDER, SESSION, THREAD, line, stamp  # noqa: E402

PROMPT = "Make a 16:9 hero image of a calm harbour at dawn; save it as WebP in renders/"
TASK = "task_e_6a1b2c3d4e5f"
HERO = "tide chart behind a calm harbour at dawn, flat colour, no text, 16:9"
FAL = "https://v3.fal.media/files/koala/hero-7f3a.png"            # an invented address of the kind fal answers with
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


def made_media(folder):
    """A chat that asks fal for a picture (a job: asked, then its result), downloads it and makes a WebP of it, then
    asks ElevenLabs for a voice-over, whose result names the file it saved."""
    return (made.asked("Make the landing hero") + tool("Skill", "s1", 1, skill="hero-image")
            + tool("mcp__fal__run_model", "t1", 2, endpoint_id="fal-ai/flux-pro/v1.1",
                   input={"prompt": HERO, "image_size": "landscape_16_9"})
            + result("t1", '{"status":"processing","request_id":"req-1"}', 2)
            + tool("mcp__fal__get_job_result", "t2", 3, request_id="req-1")
            + result("t2", json.dumps({"images": [{"url": FAL, "width": 1920, "height": 1080}]}), 3)
            + tool("Bash", "t3", 4, command=f"curl -sL -o renders/hero-shot.png '{FAL}' && cwebp -q 90 "
                                            "renders/hero-shot.png -o renders/hero-shot.webp")
            + tool("mcp__elevenlabs__creative_generate_speech", "t4", 5, text="Tides, on time.",
                   model_id="eleven_multilingual_v2")
            + result("t4", f"Saved as {folder}/renders/voice-over.mp3.", 6))


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

    def test_what_a_chats_connectors_made_and_where_each_came_from(self):
        # a job's poll is the asking call's; a file its result names, or a download of an address a result gave
        read = runs.claude_read(self.session(made_media(FOLDER)), FOLDER)
        renders = f"{FOLDER}/renders"
        self.assertEqual(read["files"], [f"{renders}/hero-shot.png", f"{renders}/hero-shot.webp",
                                         f"{renders}/voice-over.mp3"])
        hero = {"server": "fal", "model": "fal-ai/flux-pro/v1.1", "prompt": HERO, "skill": "hero-image", "calls": 2}
        self.assertEqual(read["origins"], {f"{renders}/hero-shot.png": hero, f"{renders}/hero-shot.webp": hero,
                                           f"{renders}/voice-over.mp3": {
                                               "server": "elevenlabs", "model": "eleven_multilingual_v2",
                                               "prompt": "Tides, on time.", "skill": "hero-image", "calls": 1}})
        self.assertEqual(runs.made("done", read["files"], None), "2 images")

    def test_a_download_of_an_address_no_result_gave_and_a_words_mention_make_nothing(self):
        read = runs.claude_read(self.session(
            made.asked("Fetch the logo") + tool("Bash", "t1", 1, command="curl -o logo.png https://lumen.example/l.png")
            + tool("mcp__fal__search_models", "t2", 2, query="video") + result("t2", "Try *.mp4 or .webm", 2)), FOLDER)
        self.assertEqual((read["files"], read["origins"]), ([], {}))

    def test_runs_counts_what_a_background_sessions_connectors_made(self):
        self.session(made_media(FOLDER))
        self.agents({"kind": "background", "id": "2b3c4d5e", "sessionId": SESSION, "cwd": FOLDER, "state": "done"})
        one = self.listed()["claude:2b3c4d5e"]
        self.assertEqual((one["made"], [media["kind"] for media in one["media"]]),
                         ("2 images", ["image", "image", "audio"]))

    def test_a_codex_chats_connector_call_by_its_namespace(self):
        # Codex 0.166 names a server's tool by itself, the server in its namespace; its shell downloads
        call = {"type": "function_call", "name": "run_model", "namespace": "mcp__fal", "call_id": "c1",
                "arguments": json.dumps({"endpoint_id": "fal-ai/kling-video/v2/master",
                                         "input": {"prompt": "the harbour wakes, slow push in"}})}
        path = self.rollout(made.meta("exec") + asked_codex("Make the hero clip") + codex_said(call, 1)
                            + codex_said({"type": "function_call_output", "call_id": "c1",
                                          "output": json.dumps({"video": {"url": FAL[:-4] + ".mp4"}})}, 2)
                            + codex_said({"type": "function_call", "name": "exec_command", "call_id": "c2",
                                          "arguments": json.dumps({"cmd": f"curl -sLo renders/hero-shot.mp4 "
                                                                          f"{FAL[:-4]}.mp4"})}, 3))
        read = runs.codex_read(path)
        self.assertEqual(read["origins"], {f"{FOLDER}/renders/hero-shot.mp4": {
            "server": "fal", "model": "fal-ai/kling-video/v2/master", "prompt": "the harbour wakes, slow push in",
            "skill": None, "calls": 1}})

    def test_where_a_file_came_from_is_the_chat_that_made_it(self):
        folder = os.path.join(os.path.realpath(self.home), "lumen-api")
        os.makedirs(os.path.join(folder, "renders"))
        self.write(os.path.relpath(os.path.join(claude_project_dir(folder), f"{SESSION}.jsonl"), self.home),
                   made_media(folder))
        picture = os.path.join(folder, "renders", "hero-shot.webp")
        with open(picture, "wb") as f:
            f.write(b"RIFF")
        os.utime(picture, (time.time() - 30,) * 2)                  # made before its chat's last line
        self.assertEqual(runs.origin(picture), {
            "agent": "claude", "session": SESSION, "title": "Make the landing hero", "server": "fal",
            "model": "fal-ai/flux-pro/v1.1", "prompt": HERO, "skill": "hero-image", "calls": 2,
            "again": "Another take on renders/hero-shot.webp: the same prompt, model and skill, saved beside it."})
        other = os.path.join(folder, "renders", "logo.png")
        with open(other, "wb") as f:
            f.write(b"PNG")
        self.assertIsNone(runs.origin(other))                       # no chat names it
        os.utime(picture, (time.time() + 3600,) * 2)
        self.assertIsNone(runs.origin(picture))                     # made after its chat: another made it again

    def test_a_reading_of_an_earlier_version_is_read_again(self):
        path = self.session(made_media(FOLDER))
        info = os.stat(path)
        cache = {path: {"size": info.st_size, "mtime": info.st_mtime, "read": {"files": []}}}
        self.assertEqual(len(runs.cached(cache, path, lambda: runs.claude_read(path, FOLDER))["files"]), 3)
        self.assertEqual(cache[path]["version"], runs.READ)

    def test_a_runs_day_and_time(self):
        now = time.mktime((2026, 11, 25, 15, 0, 0, 0, 0, -1))
        self.assertEqual(runs.when(time.mktime((2026, 11, 25, 14, 2, 0, 0, 0, -1)), now), ("Today", "14:02"))
        self.assertEqual(runs.when(time.mktime((2026, 11, 24, 17, 40, 0, 0, 0, -1)), now), ("Yesterday", "17:40"))
        self.assertEqual(runs.when(time.mktime((2026, 11, 21, 9, 0, 0, 0, 0, -1)), now), ("Earlier", "Nov 21"))
        self.assertEqual([runs.took(times) for times in ([], [0, 20], [0, 240], [0, 3900])],
                         [None, "<1 min", "4 min", "1 h 5 min"])
