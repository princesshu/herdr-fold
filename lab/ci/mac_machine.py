#!/usr/bin/env python3
"""The lab's machine on a GitHub macOS runner: a second user, dev, reached at 127.0.0.1 through an SSH server of its
own with the lab's settings, so `python3 lab/lab.py test` runs on it. Only on GitHub's own runners: it adds a user and
starts a server as root."""
import os
import secrets
import socket
import subprocess
import sys
import tempfile

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, LAB)
import lab  # noqa: E402

USER, HOME = "dev", "/Users/dev"


def sudo(*argv, stdin=None):
    subprocess.run(["sudo", *argv], input=stdin, text=True, check=True)


def as_dev(command, stdin):
    sudo("-u", USER, "-H", "/bin/sh", "-c", command, stdin=stdin)


def main():
    if not lab.on_githubs_runner():
        print("mac_machine.py runs only on a GitHub-hosted runner: it adds a user and starts an SSH server as root",
              file=sys.stderr)
        return 1
    machine = lab.Lab()
    machine.folder()
    # a password nobody knows: dev logs in by the lab's key alone
    sudo("sysadminctl", "-addUser", USER, "-shell", "/bin/zsh", "-home", HOME, "-password", secrets.token_urlsafe(24))
    sudo("createhomedir", "-c", "-u", USER)
    as_dev("mkdir -p ~/.ssh ~/.local/bin && chmod 700 ~/.ssh && cat > ~/.ssh/authorized_keys "
           "&& chmod 600 ~/.ssh/authorized_keys", machine.key())
    with open(os.path.join(LAB, "linux", "claude")) as f:      # where Claude Code's own installer puts it
        as_dev("cat > ~/.local/bin/claude && chmod 755 ~/.local/bin/claude", f.read())
    run = tempfile.mkdtemp(prefix="sshd-", dir=machine.home)
    host = os.path.join(run, "host")
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "herdr-fold-lab", "-f", host], check=True)
    with socket.socket() as free:
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
    config = os.path.join(run, "sshd_config")
    with open(config, "w") as f:                          # the container machine's rules, and where this one listens
        f.write(f'Include "{os.path.join(LAB, "linux", "sshd.conf")}"\nPort {port}\nListenAddress 127.0.0.1\n'
                f'HostKey "{host}"\nPidFile "{os.path.join(run, "sshd.pid")}"\nSubsystem sftp internal-sftp\n')
    sudo("/usr/sbin/sshd", "-t", "-f", config)
    sudo("/usr/sbin/sshd", "-f", config)
    with open(host + ".pub") as f:
        machine.connect(port, f.read())
    print(f"the machine is up: {os.path.join(machine.bin, 'ssh')} lab")
    return 0


if __name__ == "__main__":
    sys.exit(main())
