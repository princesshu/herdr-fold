"""The Herdr app mod's way through a change on a machine, its core run as the mod runs it (Python with -I, the source
given, nothing installed there): stage, the question about a file named like a secret, the message the machine's
Claude writes (in the background too, as the mod's star does), commit and sync, the push checked in its origin."""
import json
import os
import pathlib
import subprocess
import time

PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESSAGE = "feat: change the lab files"             # what the lab's stand-in Claude answers first
# a repository with an origin, a change and a file named like a secret, in the folder the commands start in
REPO = ("git init -q --bare -b main origin.git && git init -q -b main app && cd app && git config user.name dev && "
        "git config user.email dev@example.com && echo one > a.txt && git add -A && git commit -q -m init && "
        "git remote add origin ../origin.git && git push -q -u origin main && echo two > a.txt && echo TOKEN=1 > .env")


def source(module):
    with open(os.path.join(PACKAGE, "core", module), encoding="utf-8") as f:
        return f.read()


# the mod's own commands for the star's job, from logic.js (FOLDER: the job's folder, once it has one)
MOD_JOB = """import(process.argv[1]).then(({ background, pythonCommand }) => {
  const [binary, git, writer, root, on] = JSON.parse(process.argv[2]);
  const job = background(binary, writer, ["write", root]);
  console.log(JSON.stringify({ stage: [...pythonCommand(binary), git, "stage", root], prepare: job.prepare,
    start: job.start("FOLDER", root, on), poll: job.poll("FOLDER"), clear: job.clear("FOLDER") }));
});"""


def mod_job(binary, root, on):
    logic = pathlib.Path(PACKAGE, "app", "mods", "herdr-fold", "logic.js").as_uri()
    given = json.dumps([binary, source("git.py"), source("commit_message.py"), root, on])
    out = subprocess.run(["node", "-e", MOD_JOB, logic, given], capture_output=True, text=True, timeout=60)
    if out.returncode:
        raise RuntimeError(out.stderr)
    return json.loads(out.stdout)


def write_in_the_background(test, hc, shell, root, binary, on=None):
    """The mod's star on a machine by its own commands through a core (HC(args): its code and what it printed; ON: the
    machine, None for HC's own): a change in ROOT staged, written by a job in a core terminal, then all of it gone."""
    commands = mod_job(binary, root, on)

    def exec_(argv, folder=""):
        return hc(["exec", *(["--on", on] if on else []), "--cwd", root, *(a.replace("FOLDER", folder) for a in argv)])

    shell("cd app && echo three > a.txt")
    test.assertEqual(json.loads(exec_(commands["stage"])[1]), {"ok": True, "advice": None})
    code, folder, said = exec_(commands["prepare"])
    test.assertEqual(code, 0, said)
    folder = folder.strip()
    code, started, said = hc([a.replace("FOLDER", folder) for a in commands["start"]])
    test.assertEqual(code, 0, said)
    terminal, deadline = json.loads(started)["address"], time.monotonic() + 120
    while (answer := exec_(commands["poll"], folder))[0] == 3 and time.monotonic() < deadline:
        time.sleep(0.5)
    test.assertEqual(answer[0], 0, answer[2])
    test.assertTrue(json.loads(answer[1])["message"].startswith(MESSAGE), answer[1])
    exec_(commands["clear"], folder)
    hc(["kill", terminal])
    gone = exec_([binary, "-c", "import os, sys; sys.exit(os.path.exists(sys.argv[1]))", folder])[0]
    test.assertEqual(gone, 0, f"{folder} is still there")


def commit_and_push(test, shell, python):
    """The way on a machine whose SHELL(command) and PYTHON(args, stdin) return what they printed; TEST's checks fail
    where it breaks."""
    def core(module, *args):
        return json.loads(python(["-I", "-", *args], source(module)))

    shell(REPO)
    test.assertEqual(core("git.py", "stage", "app"), {"ok": True, "advice": None})
    test.assertEqual(core("commit_message.py", "secrets", "app"), {"secret_looking": [".env"]})
    written = core("commit_message.py", "write", "app")["message"]
    test.assertTrue(written.startswith(MESSAGE), written)
    test.assertEqual(core("git.py", "commit", "app", MESSAGE), {"ok": True, "advice": None})
    test.assertEqual(core("git.py", "sync", "app"), {"ok": True, "advice": None})
    test.assertEqual(shell("git -C origin.git log -1 --format=%s").strip(), MESSAGE)
