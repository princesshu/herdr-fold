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
| `tests/test_whole_way.py` | the whole remote way: `install.sh` in a home of its own adds the machine to a demo herdr and the Herdr app's core, the mod's core commits and pushes on it, `uninstall.sh` takes the app's part off |
| `walk.py` | the Herdr app mod's way through a change on a machine (stage, the secret question, the written message, commit, sync), shared by the whole-way test and the runners |
| `ci/mac_machine.py` | on GitHub's macOS runner: a second user, `dev`, reached through an SSH server of its own, as the lab's machine |
| `ci/machine_side.py`, `ci/claude.cmd` | on GitHub's Linux and Windows runners: a machine's side as `machines.sh` runs it there, and a Windows stand-in for Claude Code |

Everything it keeps is in `~/.local/share/herdr-fold-lab`, never in the repository or `~/.ssh`: the container
tool's data (started with that folder when it was not running), the lab's SSH key (named `herdr-fold-lab`), the
machine's key, and `ssh_config` with `bin/ssh` and `bin/scp`, which read it first and a caller's `-F` (herdr's own)
after it, never `~/.ssh`. The machine listens on `127.0.0.1` alone, at a port of its own each time. A whole-way
run makes its demo home in that folder too and removes it afterwards: its herdr and the app's core keep their
sockets there (`XDG_RUNTIME_DIR`), within the 104 bytes macOS allows a socket's path. `tests/test_lab_harness.py`
checks the lab itself without a machine, in the usual test run.

## On GitHub's runners

`.github/workflows/lab.yml` runs the lab where this Mac cannot: a clean Mac, Linux on x86_64 and Windows. It runs only
when started by hand (`gh workflow run lab`, or Run workflow under Actions), on GitHub's own runners, with a token that
only reads and no secrets:

| Job | What it does |
|---|---|
| `mac` | the Herdr app from its installer, `./install.sh` as a person runs it (Homebrew installs what is missing), then `ci/mac_machine.py` and `python3 lab/lab.py test`: the whole way to the runner itself as `dev` |
| `linux`, `windows` | `ci/machine_side.py`: the payload `machines.sh` sends, its prepare script, the mod's core through a commit and a push, and the prepare script taking it off |

`ci/mac_machine.py` and `ci/machine_side.py` stop at once anywhere else: they add a user, start a server as root or
change the home they run in.
