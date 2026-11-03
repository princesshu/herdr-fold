"""The Herdr app mod's way through a change on a machine, its core run as the mod runs it (Python with -I, the source
given, nothing installed there): stage, the question about a file named like a secret, the message the machine's
Claude writes, commit and sync, and the push checked in the machine's own origin."""
import json
import os

PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESSAGE = "feat: change the lab files"             # what the lab's stand-in Claude answers first
# a repository with an origin, a change and a file named like a secret, in the folder the commands start in
REPO = ("git init -q --bare -b main origin.git && git init -q -b main app && cd app && git config user.name dev && "
        "git config user.email dev@example.com && echo one > a.txt && git add -A && git commit -q -m init && "
        "git remote add origin ../origin.git && git push -q -u origin main && echo two > a.txt && echo TOKEN=1 > .env")


def commit_and_push(test, shell, python):
    """The way on a machine whose SHELL(command) and PYTHON(args, stdin) return what they printed; TEST's checks fail
    where it breaks."""
    def core(module, *args):
        with open(os.path.join(PACKAGE, "core", module), encoding="utf-8") as f:
            return json.loads(python(["-I", "-", *args], f.read()))

    shell(REPO)
    test.assertEqual(core("git.py", "stage", "app"), {"ok": True, "advice": None})
    test.assertEqual(core("commit_message.py", "secrets", "app"), {"secret_looking": [".env"]})
    written = core("commit_message.py", "write", "app")["message"]
    test.assertTrue(written.startswith(MESSAGE), written)
    test.assertEqual(core("git.py", "commit", "app", MESSAGE), {"ok": True, "advice": None})
    test.assertEqual(core("git.py", "sync", "app"), {"ok": True, "advice": None})
    test.assertEqual(shell("git -C origin.git log -1 --format=%s").strip(), MESSAGE)
