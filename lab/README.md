# The lab

herdr-fold's test lab: a Linux machine in a container on this Mac, reached over SSH as a remote machine is, for the
remote way of the TUI and the Herdr app without a machine of your own. It runs only when called, and nothing of it
stays running afterwards.

It needs Apple's container tool (`brew install container`, macOS 26 or later); the first start fetches its kernel and
the machine's Debian image.

```bash
python3 lab/lab.py up       # a new machine from its image (built when lab/linux changed), its SSH as `lab`
python3 lab/lab.py test     # the lab's tests (lab/tests) on a machine brought up for them, and down again
python3 lab/lab.py status   # whether it runs, its image, the room its folder takes
python3 lab/lab.py reset    # a clean machine again
python3 lab/lab.py down     # the machine stopped and gone; its image stays for the next start
python3 lab/lab.py drop     # everything of the lab's gone: the machine, its images, its folder
```

| File | What it is |
|---|---|
| `lab.py` | the command above, and the `Lab` the tests use: `ssh()` runs a command on the machine as `dev` |
| `linux/Containerfile` | the machine: SSH, Python and git, a user `dev`, and `claude`, a stand-in that answers one message |
| `linux/sshd.conf`, `linux/claude` | its SSH settings (only `dev`, only by the lab's key) and the stand-in for Claude Code |
| `tests/test_machine.py` | the machine answers over SSH with what a remote machine of herdr-fold's needs |

Everything it keeps is in `~/.local/share/herdr-fold-lab`, never in the repository or `~/.ssh`: the container
tool's data (started with that folder when it was not running), the lab's SSH key (named `herdr-fold-lab`), the
machine's key, and `ssh_config` with `bin/ssh` and `bin/scp`, which read only it. The machine listens on
`127.0.0.1` alone, at a port of its own each time. `tests/test_lab_harness.py` checks the lab itself without a
machine, in the usual test run.
