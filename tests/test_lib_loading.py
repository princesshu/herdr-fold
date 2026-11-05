"""Tests for loading() in lib/loading.sh: sheep jump fences during a silent step, then its output and exit code follow;
without a terminal (HERDR_FOLD_YES=1) the step just runs. Runs in a pty, as the animation goes to /dev/tty.
"""
import os
import pty
import re
import select
import shutil
import subprocess
import tempfile
import time
import unittest

PACKAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LIB = os.path.join(PACKAGE, "lib/common.sh")
SCENE = "▀"          # the half block the sheep, the fence and the grass are drawn with


def loading(command, **env):
    """loading "Working" <command> in a pty, the sheep drawn at once and gone with the step unless ENV says otherwise
    (LOADING_AFTER: the mark, LOADING_SHEEP: the sheep, LOADING_SHEEP_MIN: their least time); returns everything the
    terminal received."""
    return terminal(f'. "{LIB}"; loading "Working" {command}; echo "RC=$?"', **env)


def terminal(script, **env):
    """SCRIPT in bash in a pty, with loading()'s settings; everything the terminal received."""
    pid, fd = pty.fork()
    if pid == 0:
        os.execve("/bin/bash", ["bash", "-c", script],
                  {"PATH": "/usr/bin:/bin", "TERM": "xterm-256color", "LOADING_AFTER": "0", "LOADING_SHEEP": "0",
                   "LOADING_SHEEP_MIN": "0", **env})
    out, end = b"", time.time() + 20
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.1)
        if r:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
    os.waitpid(pid, 0)
    return out.decode("utf-8", "replace")


class Loading(unittest.TestCase):
    def test_the_scene_is_drawn_while_the_step_runs(self):
        out = loading("sleep 1")
        self.assertIn(SCENE, out)
        self.assertIn("Working", out)

    def test_a_blank_row_keeps_the_jump_off_the_line_above(self):
        # every frame starts with an empty row: a sheep over a fence never touches the text above the scene
        out = loading("sleep 1")
        frames = re.findall(r"\r\x1b\[\d+A(.*?)\r?\n", out)                 # the terminal ends a line with \r\n
        self.assertTrue(frames)
        self.assertEqual([f for f in frames if f != "\x1b[K"], [])

    def test_the_sheep_are_small(self):
        # four columns and two rows (4 x 3 pixels): a wool, a face and legs, no larger than that
        sizes = subprocess.run(["/bin/bash", "-c", f'. "{LIB}"; echo "$SHEEP_WIDTH $SHEEP_HEIGHT"'],
                               capture_output=True, text=True).stdout.split()
        self.assertEqual(sizes, ["4", "2"])

    def test_a_fence_is_one_row_high(self):
        # two pixels, a whole row, standing on the grass
        fence = subprocess.run(["/bin/bash", "-c", f'. "{LIB}"; printf %s "$FENCE_ROW"'],
                               capture_output=True, text=True).stdout
        self.assertIn("█", fence)

    def test_the_steps_output_comes_after_the_animation(self):
        out = loading("sh -c 'sleep 0.5; echo hello'")
        self.assertGreater(out.index("hello"), out.rindex("Working"))

    def test_the_exit_code_is_kept(self):
        self.assertIn("RC=3", loading("sh -c 'exit 3'"))

    def test_the_cursor_comes_back(self):
        out = loading("sleep 0.3")
        self.assertGreater(out.rindex("\x1b[?25h"), out.rindex("Working"))

    def test_a_short_step_shows_no_loading(self):
        # shorter than LOADING_AFTER (a second unless set): nothing drawn, only the step's own output
        out = loading("sh -c 'sleep 0.5; echo hello'", LOADING_AFTER="2")
        self.assertNotIn(SCENE, out)
        self.assertNotIn("Working", out)
        self.assertIn("hello", out)
        self.assertIn("RC=0", out)

    def test_a_step_over_a_second_shows_a_plain_mark_first(self):
        # a mark, the message and the time from LOADING_AFTER on; the sheep only from LOADING_SHEEP (five seconds)
        out = loading("sleep 1.8", LOADING_AFTER="1", LOADING_SHEEP="5")
        self.assertIn("Working", out)
        self.assertIn("0:0", out)
        self.assertNotIn(SCENE, out)

    def test_the_mark_turns_in_the_status_lines_column_inside_its_brackets(self):
        # a 2×2 of braille dots, the middle two rows only: never past the brackets above or below
        plain = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", loading("sleep 1.5", LOADING_AFTER="0", LOADING_SHEEP="5"))
        self.assertRegex(plain, r"\r  \[[⠖⠲⠴⠦]\] Working")
        self.assertNotRegex(plain, r"\[[^⠖⠲⠴⠦…✓!✗+-]\] Working")

    def test_the_mark_turns_a_quarter_every_three_tenths(self):
        # calm: one turn in 1.2 s, so a 1.5 s step shows at most five quarter turns
        plain = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", loading("sleep 1.5", LOADING_AFTER="0", LOADING_SHEEP="5"))
        marks = re.findall(r"\[([⠖⠲⠴⠦])\] Working", plain)
        self.assertLessEqual(sum(1 for a, b in zip(marks, marks[1:]) if a != b), 5, marks)

    def test_a_long_step_goes_on_to_the_sheep(self):
        out = loading("sleep 2.6", LOADING_AFTER="0", LOADING_SHEEP="1")
        mark, sheep = out.index("Working"), out.index(SCENE)
        self.assertLess(mark, sheep)                                         # the mark came first
        self.assertIn("\r\x1b[K", out[mark:sheep])                         # and its line went before the scene

    def test_the_sheep_come_only_for_a_long_step(self):
        # a step that crosses the threshold by a little would flash them for a moment: they come late, and stay
        out = subprocess.run(["/bin/bash", "-c", f'. "{LIB}"; echo "$LOADING_SHEEP $LOADING_SHEEP_MIN"'],
                             capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"}).stdout.split()
        self.assertEqual(out, ["8", "3"])

    def test_once_there_the_sheep_stay_a_while(self):
        started = time.monotonic()
        out = loading("sleep 1.2", LOADING_AFTER="0", LOADING_SHEEP="1", LOADING_SHEEP_MIN="2")
        self.assertIn(SCENE, out)
        self.assertGreater(time.monotonic() - started, 2.8)                 # 1 s to the sheep, then 2 s of them
        self.assertIn("RC=0", out)

    def test_the_step_says_what_it_is_doing(self):
        # what the step writes into LOADING_PHASE shows after the message, on the line and under the sheep
        step = "sh -c 'echo drawing the Nord icon > \"$LOADING_PHASE\"; sleep 1.6'"
        self.assertIn("Working · drawing the Nord icon", loading(step, LOADING_AFTER="0", LOADING_SHEEP="9"))
        self.assertIn("Working · drawing the Nord icon", loading(step, LOADING_AFTER="0", LOADING_SHEEP="0"))

    def test_a_shell_step_names_its_phase_with_loading_phase(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, "phase")
        script = f'. "{LIB}"; loading_phase "sending the files"; LOADING_PHASE={path} loading_phase "settings"'
        done = subprocess.run(["/bin/bash", "-c", script], capture_output=True, text=True,
                              env={"PATH": "/usr/bin:/bin"})
        self.assertEqual(done.returncode, 0, done.stderr)                    # outside a loading: nothing, no error
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "settings\n")

    def test_a_machines_reach_check_is_a_line_never_sheep(self):
        # it ends by ssh's own timeout (10 s): sheep would only come for a moment
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        with open(os.path.join(tmp, "ssh"), "w") as f:
            f.write("#!/bin/sh\nsleep 1.2\n")
        os.chmod(os.path.join(tmp, "ssh"), 0o755)
        out = terminal(f'cd "{PACKAGE}" && . ./machines.sh && reachable dev@box && echo REACHED',
                       PATH=f"{tmp}:/usr/bin:/bin", HOME=tmp)
        self.assertIn("REACHED", out)
        self.assertIn("dev@box", out)                                       # its line, while it waits
        self.assertNotIn(SCENE, out)

    def test_a_plain_line_has_no_sheep(self):
        # LOADING_PLAIN, for a step a timeout soon ends: a plain mark, the message and the time
        out = loading("sleep 1", LOADING_PLAIN="1")
        self.assertNotIn(SCENE, out)
        self.assertIn("Working", out)
        self.assertIn("0:0", out)

    def test_no_animation_without_a_terminal(self):
        out = loading("echo hello", HERDR_FOLD_YES="1")
        self.assertNotIn(SCENE, out)
        self.assertIn("hello", out)
        self.assertIn("RC=0", out)


class Colors(unittest.TestCase):
    """The scene in the theme's colors, from the file the theme setter writes (wool, face, wool, face, fence, grass);
    without it, or with one it did not write, its own."""

    TEXT, ACCENT, FAINT = "2;205;214;244", "2;203;166;247", "2;127;132;156"
    OWN = ("38;5;231", "38;5;94", "38;5;22")                          # a light sheep, a fence, the grass

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)

    def colors(self, line):
        folder = os.path.join(self.home, ".local", "state", "herdr-fold")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "loading-colors.txt"), "w") as f:
            f.write(line)

    def test_the_scene_takes_the_themes_colors(self):
        self.colors(" ".join((self.TEXT, self.FAINT, self.ACCENT, self.FAINT, self.ACCENT, self.FAINT)) + "\n")
        out = loading("sleep 1", HOME=self.home)
        self.assertEqual([color for color in (self.TEXT, self.ACCENT, self.FAINT) if "38;" + color not in out], [])
        self.assertEqual([own for own in self.OWN if own in out], [])        # no white, brown or green of its own

    def test_without_the_file_the_scene_keeps_its_own_colors(self):
        out = loading("sleep 1", HOME=self.home)
        self.assertEqual([own for own in self.OWN if own not in out], [])

    def test_a_file_the_theme_setter_did_not_write_changes_nothing(self):
        self.colors("2;1;2;3m\x1b[2J 2;1;2;3 2;1;2;3 2;1;2;3 2;1;2;3 2;1;2;3\n")
        out = loading("sleep 1", HOME=self.home)
        self.assertEqual([own for own in self.OWN if own not in out], [])
        self.assertNotIn("\x1b[2J", out)


class Rhythm(unittest.TestCase):
    """At any window width: the whole flock in view (four sheep, fewer in a narrow window) and more than one fence, and
    the light ones and the dark ones take turns jumping the fences — never one of each in the air at the same time. A
    jump goes a row and a pixel up, its legs as long as on the grass: a pixel of air between them and the fence."""

    def test_a_jumping_sheep_is_one_pixel_up_and_its_legs_stay_short(self):
        # the sheep's pixel rows, as the half blocks show them: on the grass, and up (the art one row higher)
        script = (f'. "{LIB}"; for r in "${{SHEEP_ART[@]}}"; do echo "$r"; done; echo --; '
                  'for r in "${SHEEP_UP[@]}"; do echo "$r"; done')
        ground, up = subprocess.run(["/bin/bash", "-c", script], capture_output=True, text=True).stdout.split("--\n")
        ground, up = ground.split(), up.split()
        self.assertEqual(up, ground[1:] + ["." * len(ground[0])])
        self.assertEqual(sum(row.count("L") for row in up), sum(row.count("L") for row in ground))

    def test_light_and_dark_take_turns_at_the_fences(self):
        for width in (50, 78, 120, 200):
            script = (f'. "{LIB}"; layout {width}; printf -v SPACES "%*s" {width} ""; '
                      'render_sheep 0 "${SHEEP_PALETTES[0]}"; render_sheep 1 "${SHEEP_PALETTES[1]}"; '
                      'for ((t = 4 * SHEEP_SPACING; t < 12 * SHEEP_SPACING; t++)); do scene $t; up= on=0; '
                      'for k in "${!UP[@]}"; do [ "${UP[k]}" = 0 ] && up+=L || up+=D; done; '
                      'for k in "${!ITEM[@]}"; do [ $k -ge 1000 ] && [ $k -lt 2000 ] && on=$((on + 1)); done; '
                      'echo "${up:--} $on ${#FENCES[@]} $FLOCK ${#ROWS[@]} $SHEEP_HEIGHT"; done')
            out = subprocess.run(["/bin/bash", "-c", script], capture_output=True, text=True,
                                 timeout=60).stdout.split("\n")
            frames = [line.split() for line in out if line.strip()]
            self.assertTrue(frames, width)
            self.assertGreaterEqual(int(frames[0][2]), 2, width)                          # more than one fence
            self.assertEqual({f[1] for f in frames}, {frames[0][3]}, width)    # the whole flock: part of each on row 1
            # the sky row a jump goes up into, and the sheep's rows
            self.assertEqual({int(f[4]) for f in frames}, {int(frames[0][5]) + 1}, width)
            if width >= 60:
                self.assertEqual(frames[0][3], "4", width)                    # four in a usual window
            ups = {f[0] for f in frames}
            self.assertFalse([up for up in ups if "L" in up and "D" in up], width)  # never light and dark up together
            self.assertTrue([u for u in ups if "L" in u] and [u for u in ups if "D" in u], width)  # both colors jump


if __name__ == "__main__":
    unittest.main()
