"""The Herdr app mod's background job on a space's machine: prepare puts core/'s SOURCE in a folder of its own, run (in
a terminal of the core's, which outlives the 30 s an exec may take) runs it there and removes the folder KEEP seconds
after; poll answers 3 while it runs, then 0 and its output or 4 and its error; clear removes the folder."""
import os
import shutil
import subprocess
import sys
import tempfile
import time

PREFIX = "herdr-fold."                # a job's own folder in the temporary one: clear removes no other


def prepare(source):
    folder = tempfile.mkdtemp(prefix=PREFIX)
    with open(os.path.join(folder, "job.py"), "w", encoding="utf-8") as f:
        f.write(source)
    print(folder)
    return 0


def run(folder, keep, args):
    """The job's source with ARGS, isolated and in UTF-8 (a json.py where it runs is never imported); its exit code in
    done once its output is whole, the folder gone KEEP seconds later should nobody clear it."""
    with open(os.path.join(folder, "out"), "wb") as out, open(os.path.join(folder, "err"), "wb") as err:
        code = subprocess.call([sys.executable, "-X", "utf8", "-I", os.path.join(folder, "job.py"), *args],
                               stdin=subprocess.DEVNULL, stdout=out, stderr=err)
    with open(os.path.join(folder, "done.part"), "w") as f:
        f.write(str(code))
    os.replace(os.path.join(folder, "done.part"), os.path.join(folder, "done"))
    time.sleep(int(keep))
    return clear(folder)


def poll(folder):
    try:
        with open(os.path.join(folder, "done")) as f:
            code = f.read().strip()
    except OSError:
        return 3
    if code == "0":
        with open(os.path.join(folder, "out"), "rb") as f:
            sys.stdout.buffer.write(f.read())
        return 0
    with open(os.path.join(folder, "err"), "rb") as f:
        sys.stderr.buffer.write(b"\n".join(f.read().splitlines()[-3:]) + b"\n")
    return 4


def clear(folder):
    """FOLDER removed if it is a job's: right in the temporary folder, by its name."""
    path = os.path.realpath(folder)
    if os.path.dirname(path) == os.path.realpath(tempfile.gettempdir()) and os.path.basename(path).startswith(PREFIX):
        shutil.rmtree(path, ignore_errors=True)
    return 0


def main(argv):
    """prepare SOURCE (prints the job's folder), run FOLDER KEEP [ARGS...], poll FOLDER, clear FOLDER."""
    command, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    if command == "prepare" and len(args) == 1:
        return prepare(args[0])
    if command == "run" and len(args) >= 2:
        return run(args[0], args[1], args[2:])
    if command in ("poll", "clear") and len(args) == 1:
        return poll(args[0]) if command == "poll" else clear(args[0])
    print("usage: job.py prepare SOURCE | run FOLDER KEEP [ARGS...] | poll FOLDER | clear FOLDER", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
