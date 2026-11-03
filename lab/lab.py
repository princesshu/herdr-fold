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
# ssh and scp with the lab's settings, never ~/.ssh: where a caller (herdr) gives its own -F among the options, they go
# ahead of it as options and nothing is written (ssh may be ended at any moment); else the lab's own settings file
WRAPPER = """#!/bin/sh
own=
skip=
for a in "$@"; do
  if [ -n "$skip" ]; then skip=; [ "$own" = next ] && own=yes; continue; fi
  case "$a" in
    -F) own=next; skip=1 ;;
    -F?*) own=yes ;;
    -[bcDEeIiJLlmOoPpQRSWwX]) skip=1 ;;
    -*) ;;
    *) break ;;
  esac
done
[ "$own" = yes ] && exec /usr/bin/PROGRAM OPTIONS "$@"
exec /usr/bin/PROGRAM -F CONFIG "$@"
"""


class LabError(Exception):
    """What stopped the lab, in one line."""


def available():
    return bool(shutil.which("container"))


def on_githubs_runner():
    """Whether this runs on one of GitHub's own runners: a fresh machine, thrown away after its job."""
    return os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"


def last(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else "no answer"


class Lab:
    def __init__(self, home=HOME, wait=120.0):
        self.home, self.wait = home, wait
        self.bin, self.started = os.path.join(home, "bin"), os.path.join(home, "started")

    def folder(self):
        """The lab's folder, with its mark: drop takes only a folder that has it."""
        os.makedirs(self.home, exist_ok=True)
        with open(os.path.join(self.home, MARK), "w"):
            pass

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
        self.folder()
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

    def key(self):
        """The lab's SSH key, made the first time and named for the lab (not this Mac's user and name): its public
        half."""
        key = os.path.join(self.home, "key")
        if not os.path.exists(key):
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "herdr-fold-lab", "-f", key],
                           check=True)
        with open(key + ".pub") as f:
            return f.read()

    def reach(self, port):
        """The lab's key on the container's machine, and SSH to it with the machine's own key."""
        self.container("exec", "-i", NAME, "sh", "-c", "cat > /home/dev/.ssh/authorized_keys && chown dev:dev "
                       "/home/dev/.ssh/authorized_keys && chmod 600 /home/dev/.ssh/authorized_keys", stdin=self.key())
        _, host = self.container("exec", NAME, "cat", "/etc/ssh/ssh_host_ed25519_key.pub")
        self.connect(port, host)

    def connect(self, port, host_key):
        """SSH's settings for the machine at PORT on 127.0.0.1, known by HOST_KEY (its public key line), as `lab`;
        then SSH asked until it answers."""
        known = os.path.join(self.home, "known_hosts")
        with open(known, "w") as f:
            f.write(f"[127.0.0.1]:{port} {' '.join(host_key.split()[:2])}\n")
        settings = [("HostName", "127.0.0.1"), ("Port", str(port)), ("User", "dev"),
                    ("IdentityFile", os.path.join(self.home, "key")), ("IdentitiesOnly", "yes"),
                    ("UserKnownHostsFile", known), ("StrictHostKeyChecking", "yes"), ("BatchMode", "yes"),
                    ("ConnectTimeout", "5")]
        quoted = [(name, f'"{value}"' if os.sep in value else value) for name, value in settings]   # paths: spaces
        config = os.path.join(self.home, "ssh_config")
        with open(config, "w") as f:
            f.write("Host lab\n" + "".join(f"  {name} {value}\n" for name, value in quoted))
        options = " ".join(shlex.quote(f"-o{name}={value}") for name, value in quoted)
        os.makedirs(self.bin, exist_ok=True)
        for program in ("ssh", "scp"):                    # first on a demo's PATH
            path = os.path.join(self.bin, program)
            with open(path, "w") as f:
                f.write(WRAPPER.replace("OPTIONS", options).replace("CONFIG", shlex.quote(config))
                        .replace("PROGRAM", program))
            os.chmod(path, 0o755)
        deadline = time.monotonic() + self.wait
        while not self.answers():
            if time.monotonic() >= deadline:
                raise LabError("the machine's SSH did not answer")
            time.sleep(0.5)

    def answers(self):
        """Whether a machine answers SSH as `lab` with the lab's settings."""
        return os.path.exists(os.path.join(self.bin, "ssh")) and self.ssh("true").returncode == 0

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
        # the room the files take (a sparse disk's size says far more)
        size = sum(os.lstat(os.path.join(top, name)).st_blocks * 512 for top, _, names in os.walk(self.home)
                   for name in names)
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
        """The lab's tests (lab/tests) on its machine: brought up for them, unless one answers already (a runner's
        own, lab/ci)."""
        brought = not self.answers()
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
