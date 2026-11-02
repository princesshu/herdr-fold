#!/usr/bin/env python3
"""herdr-fold's test lab: a Linux machine in a container on this Mac (Apple's container tool), reached over SSH as a
remote machine is. Usage: python3 lab/lab.py up | down | status | test | reset | drop (lab/README.md). Its state is in
~/.local/share/herdr-fold-lab, never in the repository or ~/.ssh; drop takes all of it."""
import hashlib
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MACHINE = os.path.join(HERE, "linux")                  # what the machine's image is built from
HOME = os.path.join(os.path.expanduser("~"), ".local", "share", "herdr-fold-lab")
NAME = "herdr-fold-lab-linux"                          # the machine's container
IMAGE = "herdr-fold-lab"                               # its image, tagged by what it is built from
MARK = ".herdr-fold-lab"                               # in the lab's own folder: drop takes only a folder with it
# ssh and scp with the lab's settings first: a -F its caller gives (herdr's own) is read after them, and ~/.ssh never
WRAPPER = """#!/bin/sh
config=CONFIG
merged=
n=$#
while [ "$n" -gt 0 ]; do
  a=$1; shift; n=$((n - 1))
  if [ "$a" = -F ] && [ "$n" -gt 0 ]; then
    merged=$(mktemp "${config%/*}/merged.XXXXXX") || exit 1
    printf 'Include "%s"\\nInclude "%s"\\n' "$config" "$1" > "$merged"
    shift; n=$((n - 1)); set -- "$@" -F "$merged"
  else
    set -- "$@" "$a"
  fi
done
[ -n "$merged" ] || set -- -F "$config" "$@"
/usr/bin/PROGRAM "$@"; code=$?
[ -z "$merged" ] || rm -f "$merged"
exit $code
"""


class LabError(Exception):
    """What stopped the lab, in one line."""


def available():
    return bool(shutil.which("container"))


def last(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else "no answer"


class Lab:
    def __init__(self, home=HOME, wait=120.0):
        self.home, self.wait = home, wait
        self.bin, self.started = os.path.join(home, "bin"), os.path.join(home, "started")

    def container(self, *args, stdin=None):
        """The container program with ARGS: (its exit code, what it said)."""
        out = subprocess.run(["container", *args], input=stdin, capture_output=True, text=True, timeout=1800)
        return out.returncode, (out.stdout or "") + (out.stderr or "")

    def ssh(self, command):
        """COMMAND on the machine, as dev."""
        return subprocess.run([os.path.join(self.bin, "ssh"), "lab", command], capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=600)

    def up(self):
        """A new machine from its image (built first when there is none), its SSH answering as `lab`; anything that
        fails takes it down again."""
        os.makedirs(self.home, exist_ok=True)
        with open(os.path.join(self.home, MARK), "w"):
            pass
        try:
            self.services()
            tag = self.image()
            self.remove()
            with socket.socket() as free:                 # a port of its own on this Mac only
                free.bind(("127.0.0.1", 0))
                port = free.getsockname()[1]
            code, out = self.container("run", "--detach", "--name", NAME, "--publish", f"127.0.0.1:{port}:22", tag)
            if code:
                raise LabError(f"the machine did not start: {last(out)}")
            self.reach(port)
        except BaseException:
            self.down()
            raise

    def services(self):
        """The container services running, started with the lab's own data folder when they were not."""
        if self.container("system", "status")[0] == 0:
            return
        code, out = self.container("system", "start", "--app-root", os.path.join(self.home, "container"),
                                   "--enable-kernel-install")
        if code:
            raise LabError(f"the container services did not start: {last(out)}")
        with open(self.started, "w"):
            pass

    def image(self):
        """The machine's image for what lab/linux holds now, built when missing; an older one of the lab's goes."""
        digest = hashlib.sha256()
        for name in sorted(os.listdir(MACHINE)):
            with open(os.path.join(MACHINE, name), "rb") as f:
                digest.update(name.encode() + b"\0" + f.read())
        tag = f"{IMAGE}:{digest.hexdigest()[:12]}"
        _, listed = self.container("image", "list", "--format", "json")
        if tag not in listed:
            recipe = os.path.join(MACHINE, "Containerfile")
            code, out = self.container("build", "--tag", tag, "--file", recipe, MACHINE)
            if code:
                raise LabError(f"the machine's image was not built: {last(out)}")
        for old in set(re.findall(rf"{IMAGE}:[0-9a-f]{{12}}", listed)) - {tag}:
            self.container("image", "rm", old)
        return tag

    def reach(self, port):
        """The lab's key on the machine, the machine's key and SSH's settings here; then SSH asked until it answers."""
        key = os.path.join(self.home, "key")
        if not os.path.exists(key):                       # named for the lab, not this Mac's user and name
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "herdr-fold-lab", "-f", key],
                           check=True)
        with open(key + ".pub") as f:
            self.container("exec", "-i", NAME, "sh", "-c", "cat > /home/dev/.ssh/authorized_keys && chown dev:dev "
                           "/home/dev/.ssh/authorized_keys && chmod 600 /home/dev/.ssh/authorized_keys", stdin=f.read())
        _, host = self.container("exec", NAME, "cat", "/etc/ssh/ssh_host_ed25519_key.pub")
        with open(os.path.join(self.home, "known_hosts"), "w") as f:
            f.write(f"[127.0.0.1]:{port} {' '.join(host.split()[:2])}\n")
        config = os.path.join(self.home, "ssh_config")
        with open(config, "w") as f:
            f.write(f'Host lab\n  HostName 127.0.0.1\n  Port {port}\n  User dev\n  IdentityFile "{key}"\n'
                    f'  IdentitiesOnly yes\n  UserKnownHostsFile "{os.path.join(self.home, "known_hosts")}"\n'
                    "  StrictHostKeyChecking yes\n  BatchMode yes\n  ConnectTimeout 5\n")
        os.makedirs(self.bin, exist_ok=True)
        for program in ("ssh", "scp"):                    # first on a demo's PATH
            path = os.path.join(self.bin, program)
            with open(path, "w") as f:
                f.write(WRAPPER.replace("CONFIG", shlex.quote(config)).replace("PROGRAM", program))
            os.chmod(path, 0o755)
        deadline = time.monotonic() + self.wait
        while self.ssh("true").returncode != 0:
            if time.monotonic() >= deadline:
                raise LabError("the machine's SSH did not answer")
            time.sleep(0.5)

    def remove(self):
        self.container("stop", NAME)
        self.container("rm", NAME)

    def down(self):
        """The machine stopped and gone (its image stays), and the services stopped when the lab started them."""
        self.remove()
        if os.path.exists(self.started):
            self.container("system", "stop")
            os.remove(self.started)

    def running(self):
        return NAME in self.container("list", "--format", "json")[1]

    def status(self):
        _, images = self.container("image", "list", "--format", "json")
        size = sum(os.path.getsize(os.path.join(top, name)) for top, _, names in os.walk(self.home) for name in names)
        return {"machine": "running" if self.running() else "down",
                "image": ", ".join(sorted(set(re.findall(rf"{IMAGE}:[0-9a-f]{{12}}", images)))) or "none",
                "folder": f"{self.home} ({size / 2 ** 20:.0f} MiB)" if os.path.isdir(self.home) else "none"}

    def drop(self):
        """Everything of the lab's: its machine, images, services it started and its folder (only one with its mark)."""
        if os.path.isdir(self.home) and not os.path.exists(os.path.join(self.home, MARK)):
            raise LabError(f"{self.home} is not the lab's: left as it is")
        self.down()
        _, images = self.container("image", "list", "--format", "json")
        for image in set(re.findall(rf"{IMAGE}:[0-9a-f]{{12}}", images)):
            self.container("image", "rm", image)
        if os.path.isdir(self.home):
            shutil.rmtree(self.home)

    def test(self):
        """The lab's tests (lab/tests) on a machine of their own: brought up for them, unless one runs already."""
        brought = not self.running()
        if brought:
            self.up()
        try:
            suite = unittest.defaultTestLoader.discover(os.path.join(HERE, "tests"))
            return unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()
        finally:
            if brought:
                self.down()


def main(argv):
    command, machine = argv[1] if len(argv) == 2 else "", Lab()
    try:
        if command == "up":
            machine.up()
            print(f"the machine is up: {os.path.join(machine.bin, 'ssh')} lab")
        elif command in ("down", "drop"):
            getattr(machine, command)()
        elif command == "reset":
            machine.down()
            machine.up()
        elif command == "status":
            print("\n".join(f"{key}: {value}" for key, value in machine.status().items()))
        elif command == "test":
            return 0 if machine.test() else 1
        else:
            print("usage: lab.py up | down | status | test | reset | drop", file=sys.stderr)
            return 2
    except LabError as err:
        print(f"lab: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
